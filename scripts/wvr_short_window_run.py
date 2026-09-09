"""SHORT_WINDOW_V1 실행기 — 48초 창 × 2 arm (2026-09-09).

사전등록: `docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md`

```
창    P1 360–408 · P2 416–464 · P3 104–152   (미해결 충돌 cluster에서 결정적 파생)
arm   S0 = 0.5fps 24프레임 · S1 = 0.25fps 12프레임 (S0의 KEEP 부분집합)
호출  창×arm 하나당 fresh process 1회 → 총 6회
```

V2의 프롬프트·파서·생성 설정을 그대로 쓴다. 유일한 변경은 context 길이다.
판정하지 않는다 — 판정은 blinded adjudication에서 사람이 한다.
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
import wvr_density_prompt_v2 as diag                        # noqa: E402
import wvr_density_v1b as events                            # noqa: E402
import wvr_density_v2 as v2                                 # noqa: E402
import wvr_short_window as sw                               # noqa: E402

PREREG = "docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md"


class RunError(RuntimeError):
    """실행 계약 위반."""


def load_windows(out_dir: Path) -> list:
    path = out_dir / sw.SOURCE_ARTIFACT
    if not path.is_file():
        raise RunError("evidence resolution 산출물이 없다: %s" % path)
    resolution = json.loads(path.read_text(encoding="utf-8"))
    windows = sw.derive_windows(resolution)
    sw.assert_expected(windows)
    return windows


def window_for(window_id: str, windows: list) -> dict:
    for row in windows:
        if row["window_id"] == window_id:
            return row
    raise RunError("모르는 창: %r" % window_id)


def preflight(window_id: str, arm: str, out_dir: Path) -> dict:
    """GPU를 쓰기 전에 창·프레임·동결값·산출물 중복을 확인한다."""
    window = window_for(window_id, load_windows(out_dir))
    stamps = sw.arm_timestamps(window, arm)
    fps = (sw.FROZEN_FROM_V2["reference_fps"] if arm == sw.ARM_S0
           else sw.FROZEN_FROM_V2["density_fps"])
    max_new_tokens = events.tokens_for(events.EVENT_V2)
    events.assert_allowed(max_new_tokens)

    out_path = out_dir / ("%s_%s_%s.json" % (sw.ARTIFACT_TAG, window_id, arm))
    if out_path.exists():
        raise RunError("%s 산출물이 이미 있다 — arm은 1회다" % out_path.name)

    prompt = diag.SAMPLING_DIAG_PROMPT_V2 % {
        "window_start": window["start_sec"], "window_end": window["end_sec"]}
    requested = {
        "fps": fps, "frames": len(stamps),
        "frame_width": contract.FRAME_WIDTH,
        "frame_height": contract.FRAME_HEIGHT,
        "model_id": contract.MODEL_ID,
        "model_revision": contract.MODEL_REVISION,
        "dtype": contract.DTYPE,
        "attn_implementation": contract.ATTN_IMPLEMENTATION,
        "quantization": contract.QUANTIZATION,
        "device": contract.DEVICE, "device_map": contract.DEVICE_MAP,
        "do_sample": contract.DO_SAMPLE, "num_beams": contract.NUM_BEAMS,
        "max_new_tokens": max_new_tokens,
        "repetition_penalty": contract.REPETITION_PENALTY,
        "do_sample_frames": contract.DO_SAMPLE_FRAMES,
        "do_resize": contract.DO_RESIZE,
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_hash": diag.prompt_hash(),
        "output_language": diag.OUTPUT_LANGUAGE,
    }
    change = sw.single_change(requested)
    if not change["single_change"]:
        raise RunError("V2 동결값이 바뀌었다: %r" % change["differences"])
    return {"window": window, "stamps": stamps, "requested": requested,
            "change": change, "prompt": prompt, "out_path": out_path,
            "max_new_tokens": max_new_tokens}


def run(video: Path, window_id: str, arm: str, out_dir: Path) -> dict:
    plan = preflight(window_id, arm, out_dir)
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from transformers.video_utils import VideoMetadata

    window, stamps = plan["window"], plan["stamps"]
    requested, change = plan["requested"], plan["change"]
    prompt, out_path = plan["prompt"], plan["out_path"]
    max_new_tokens = plan["max_new_tokens"]

    record = {
        "schema": "wvr_short_window_v1", "event": sw.EVENT, "prereg": PREREG,
        "window": window, "arm": arm, "requested": requested,
        "single_change": change,
        "context_length_sec": sw.WINDOW_SEC,
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_hash": diag.prompt_hash(),
        "is_production_contract": diag.IS_PRODUCTION_CONTRACT,
        "output_language": diag.OUTPUT_LANGUAGE,
        "timestamps_first_last": [stamps[0], stamps[-1]],
        "automatic_matcher_role": sw.AUTOMATIC_MATCHER_ROLE,
        "semantic_sufficiency_claim_allowed":
            sw.SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED,
        "event_extraction_approved": sw.EVENT_EXTRACTION_APPROVED,
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
        metrics["video_process_wall_sec"] = round(
            time.time() - sample_started, 2)
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
                num_beams=contract.NUM_BEAMS, max_new_tokens=max_new_tokens,
                repetition_penalty=contract.REPETITION_PENALTY)
        metrics["infer_wall_sec"] = round(time.time() - infer_started, 2)
        new_tokens = generated[0][inputs["input_ids"].shape[-1]:]
        metrics["generated_token_count"] = int(new_tokens.shape[-1])
        record["raw_output"] = processor.tokenizer.decode(
            new_tokens, skip_special_tokens=True)
        record["parsed"] = v2.parse_events(record["raw_output"], window)
        record["representation"] = v2.representation(
            record["parsed"]["collapsed"])
        record["arm_validity"] = v2.arm_validity(record)
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
    parser = argparse.ArgumentParser(description="48초 short-window probe")
    parser.add_argument("--video", required=True)
    parser.add_argument("--window", required=True,
                        choices=[row[0] for row in sw.EXPECTED_WINDOWS])
    parser.add_argument("--arm", required=True, choices=list(sw.ARMS))
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise RunError("영상이 없다: %s" % video)
    record = run(video, args.window, args.arm, Path(args.out_dir))
    print("window=%s arm=%s status=%s frames=%s input_tok=%s gen_tok=%s"
          % (record["window"]["window_id"], record["arm"],
             record.get("arm_status"),
             record["metrics"].get("delivered_frame_count"),
             record["metrics"].get("input_token_count"),
             record["metrics"].get("generated_token_count")))
    shape = record.get("representation") or {}
    print("  raw=%s collapsed=%s unique_sig=%s degenerate=%s valid=%s %s"
          % (len((record.get("parsed") or {}).get("events", [])),
             shape.get("collapsed_event_count"),
             shape.get("unique_signature_count"), shape.get("degenerate"),
             (record.get("arm_validity") or {}).get("valid"),
             (record.get("arm_validity") or {}).get("reasons")))
    return 0 if record.get("arm_status") == v2.PARSE_OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
