"""Stage 2 — PAIRED_OUTPUT_SENSITIVITY 실행기 (2026-09-08).

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md`

```
창    D1·D2·D3  (Stage 1 점수로 결정적으로 선택된 180초 창)
arm   S0 = 0.5fps 90프레임 · S1 = 0.25fps 45프레임 (S0의 KEEP 부분집합)
호출  창×arm 하나당 fresh process 1회 → 총 6회
```

진단 프롬프트만 쓴다. 보고서를 만들지 않고, 출력을 event evidence로 재사용하지
않는다.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_contract as contract                            # noqa: E402
import wvr_capacity_probe as probe                          # noqa: E402
import wvr_density as density                               # noqa: E402
import wvr_density_compare as compare                       # noqa: E402
import wvr_density_prompt as diag                           # noqa: E402
import wvr_density_v1b as events                            # noqa: E402

STAGE1_ARTIFACT = "density_stage1.json"
ARM_S0 = "S0"          # 0.5fps · reference 밀도
ARM_S1 = "S1"          # 0.25fps · KEEP 부분집합
ARMS = (ARM_S0, ARM_S1)

EVENT_EXTRACTION_APPROVED = False
SEMANTIC_VERDICT_ALLOWED = False       # 이 사건은 판정을 내지 않는다


class Stage2Error(RuntimeError):
    """실행 계약 위반."""


def window_for(label: str, stage1: dict) -> dict:
    if label not in density.SELECTION_LABELS:
        raise Stage2Error("모르는 창 표지: %r" % label)
    row = stage1["selection"][label]
    return {"window_id": row["window_id"], "start_sec": row["start_sec"],
            "end_sec": row["end_sec"], "label": label,
            "stage1_score": row["score"]}


def arm_timestamps(window, arm: str) -> tuple:
    """S0는 창 안 기준 프레임 전부, S1은 그 KEEP 부분집합."""
    keep, drop = density.keep_drop()
    frames = density.window_frames(window, keep, drop)
    if arm == ARM_S0:
        return frames["reference"]
    if arm == ARM_S1:
        density.assert_contained(frames["reference"], frames["keep"])
        return frames["keep"]
    raise Stage2Error("모르는 arm: %r" % arm)


def run(video: Path, label: str, arm: str, out_dir: Path,
        event: str = events.EVENT_V1) -> dict:
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from transformers.video_utils import VideoMetadata

    stage1 = json.loads((out_dir / STAGE1_ARTIFACT).read_text(encoding="utf-8"))
    if stage1["stage"] != density.STAGE1:
        raise Stage2Error("Stage 1 산출물이 아니다")
    window = window_for(label, stage1)
    stamps = arm_timestamps(window, arm)
    fps = density.REFERENCE_FPS if arm == ARM_S0 else density.DENSITY_FPS
    max_new_tokens = events.tokens_for(event)
    events.assert_allowed(max_new_tokens)
    out_path = out_dir / ("%s_%s_%s.json" % (events.tag_for(event),
                                             label.split("_")[0], arm))
    if out_path.exists():
        raise Stage2Error("%s 산출물이 이미 있다 — arm은 1회다" % out_path.name)

    prompt = diag.SAMPLING_DIAG_PROMPT_V1 % {"window_start": window["start_sec"],
                                             "window_end": window["end_sec"]}
    record = {
        "schema": "wvr_density_stage2_v1", "stage": density.STAGE2,
        "prereg": ("docs/preregistration/"
                   "WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md"),
        "window": window, "arm": arm, "requested": {
            "fps": fps, "frames": len(stamps),
            "frame_size": [contract.FRAME_WIDTH, contract.FRAME_HEIGHT],
            "model_id": contract.MODEL_ID,
            "model_revision": contract.MODEL_REVISION,
            "dtype": contract.DTYPE, "attn_implementation":
            contract.ATTN_IMPLEMENTATION, "quantization": contract.QUANTIZATION,
            "device": contract.DEVICE, "device_map": contract.DEVICE_MAP,
            "do_sample": contract.DO_SAMPLE, "num_beams": contract.NUM_BEAMS,
            "max_new_tokens": max_new_tokens,
            "repetition_penalty": contract.REPETITION_PENALTY,
            "do_sample_frames": contract.DO_SAMPLE_FRAMES,
            "do_resize": contract.DO_RESIZE,
        },
        "event": event,
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_hash": diag.prompt_hash(),
        "is_production_contract": diag.IS_PRODUCTION_CONTRACT,
        "timestamps_first_last": [stamps[0], stamps[-1]],
        "event_extraction_approved": EVENT_EXTRACTION_APPROVED,
        "semantic_verdict_allowed": SEMANTIC_VERDICT_ALLOWED,
        "code_git_head": os.environ.get("WVR_CODE_GIT_HEAD", "UNKNOWN"),
        "metrics": {}, "stage_status": {},
    }
    metrics = record["metrics"]
    started = time.time()
    try:
        torch.cuda.reset_peak_memory_stats()
        load_started = time.time()
        processor = AutoProcessor.from_pretrained(
            contract.MODEL_ID, revision=contract.MODEL_REVISION,
            local_files_only=True)
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            contract.MODEL_ID, revision=contract.MODEL_REVISION,
            local_files_only=True, dtype=getattr(torch, contract.DTYPE),
            attn_implementation=contract.ATTN_IMPLEMENTATION)
        model.to(contract.DEVICE)
        model.eval()
        metrics["load_wall_sec"] = round(time.time() - load_started, 2)
        record["allocator_observed"] = probe.allocator_observation()
        record["stage_status"]["MODEL_LOAD"] = "OK"

        meta = probe.video_metadata(video)
        sample_started = time.time()
        frames, indices, times, rate = probe.sample_frames(video, stamps)
        metrics["video_process_wall_sec"] = round(time.time() - sample_started, 2)
        metrics["delivered_frame_count"] = len(frames)
        metrics["frame_size"] = list(frames[0].size)
        metrics["frame_times_first_last"] = [times[0], times[-1]]
        record["frame_indices_first_last"] = [indices[0], indices[-1]]

        messages = [{"role": "user", "content": [{"type": "video"},
                                                 {"type": "text",
                                                  "text": prompt}]}]
        text = processor.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True)
        metadata = VideoMetadata(
            total_num_frames=meta["nb_frames"], fps=rate, width=meta["width"],
            height=meta["height"], duration=meta["duration_sec"],
            video_backend="pyav", frames_indices=indices)
        inputs = processor(text=[text], videos=[frames],
                           video_metadata=[metadata],
                           do_sample_frames=contract.DO_SAMPLE_FRAMES,
                           do_resize=contract.DO_RESIZE, return_tensors="pt")
        inputs = inputs.to(contract.DEVICE)
        metrics["input_token_count"] = int(inputs["input_ids"].shape[-1])
        video_token_id = getattr(model.config, "video_token_id", None)
        metrics["video_token_count"] = (
            int((inputs["input_ids"] == video_token_id).sum().item())
            if video_token_id is not None else None)
        record["stage_status"]["VIDEO_PROCESS"] = "OK"

        infer_started = time.time()
        with torch.inference_mode():
            generated = model.generate(
                **inputs, do_sample=contract.DO_SAMPLE,
                num_beams=contract.NUM_BEAMS,
                max_new_tokens=max_new_tokens,
                repetition_penalty=contract.REPETITION_PENALTY)
        metrics["infer_wall_sec"] = round(time.time() - infer_started, 2)
        new_tokens = generated[0][inputs["input_ids"].shape[-1]:]
        metrics["generated_token_count"] = int(new_tokens.shape[-1])
        record["raw_output"] = processor.tokenizer.decode(
            new_tokens, skip_special_tokens=True)
        record["parsed"] = compare.parse_events(record["raw_output"], window)
        record["stage_status"]["INFERENCE"] = "OK"
        record["arm_status"] = record["parsed"]["status"]
    except Exception as error:                     # noqa: BLE001 — 전부 기록한다
        record["arm_status"] = "RUNTIME_FAILURE"
        record["error"] = {"type": type(error).__name__,
                           "message": str(error)[:2000]}
        for name in ("MODEL_LOAD", "VIDEO_PROCESS", "INFERENCE"):
            record["stage_status"].setdefault(name, "NOT_REACHED")
    finally:
        try:
            metrics["peak_vram_allocated_mib"] = round(
                torch.cuda.max_memory_allocated() / 1024 ** 2, 1)
            metrics["peak_vram_reserved_mib"] = round(
                torch.cuda.max_memory_reserved() / 1024 ** 2, 1)
            record["memory_stats"] = probe.memory_stats_subset()
        except Exception:
            pass
        metrics["total_wall_sec"] = round(time.time() - started, 2)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage 2 paired sensitivity")
    parser.add_argument("--video", required=True)
    parser.add_argument("--window", required=True,
                        choices=list(density.SELECTION_LABELS))
    parser.add_argument("--arm", required=True, choices=list(ARMS))
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--event", default=events.EVENT_V1,
                        choices=list(events.MAX_NEW_TOKENS))
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise Stage2Error("영상이 없다: %s" % video)
    record = run(video, args.window, args.arm, Path(args.out_dir),
                 event=args.event)
    print("event=%s window=%s arm=%s status=%s frames=%s tokens=%s events=%s"
          % (record.get("event"), record["window"]["window_id"], record["arm"],
             record.get("arm_status"),
             record["metrics"].get("delivered_frame_count"),
             record["metrics"].get("input_token_count"),
             len((record.get("parsed") or {}).get("events", []))))
    return 0 if record.get("arm_status") == compare.PARSE_OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
