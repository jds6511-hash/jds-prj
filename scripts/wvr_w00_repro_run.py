"""W00 재현성 run 실행기 — run 하나당 fresh process (2026-09-09).

사전등록: `docs/preregistration/WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md`

```
입력   원본 W00과 동일해야 한다 — identity gate가 GPU 사용 전에 검사한다
순서   inference → raw persist → hash → parse → 분류 → 구조 분석
금지   retry · prompt·설정 변경 · raw salvage · 원본 W00 수정
```
"""
import argparse
import hashlib
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
import wvr_shadow_v1 as sh                                  # noqa: E402
import wvr_w00_repro as rp                                  # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md")


class RunError(RuntimeError):
    """실행 계약 위반."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def generation_config() -> dict:
    return {"do_sample": contract.DO_SAMPLE, "num_beams": contract.NUM_BEAMS,
            "max_new_tokens": events.tokens_for(events.EVENT_V2),
            "repetition_penalty": contract.REPETITION_PENALTY}


def original_identity(runs: Path) -> dict:
    record = json.loads((runs / rp.ORIGINAL_RECORD).read_text(
        encoding="utf-8"))
    requested = record.get("requested") or {}
    return {
        "video_sha256": record["video_sha256"],
        "window": record["window"],
        "frame_times": [round(float(time), 3)
                        for time in record["frame_times"]],
        "frame_hashes": list(record["frame_hashes"]),
        "prompt_text": rp.expected_prompt(),
        "prompt_hash": record["prompt_hash"],
        "model_revision": requested.get("model_revision"),
        "runtime_config_hash": record["runtime_config_hash"],
        "generation_config": {
            "do_sample": requested.get("do_sample"),
            "num_beams": requested.get("num_beams"),
            "max_new_tokens": requested.get("max_new_tokens"),
            "repetition_penalty": requested.get("repetition_penalty")},
    }


def preflight(run_id: str, runs: Path, video: Path) -> dict:
    if run_id not in rp.RUN_IDS:
        raise RunError("모르는 run: %r" % run_id)
    if rp.RETRY_ALLOWED or rp.SUBDIVISION_INFERENCE_ALLOWED:
        raise RunError("retry·subdivision은 금지돼 있다")

    window = rp.target_window()
    stamps = list(rp.frame_times())
    raw_path = runs / ("%s_%s_raw.txt" % (rp.ARTIFACT_TAG, run_id))
    out_path = runs / ("%s_%s.json" % (rp.ARTIFACT_TAG, run_id))
    for path in (raw_path, out_path):
        if path.exists():
            raise RunError("%s 산출물이 이미 있다 — run은 1회다" % path.name)

    original = original_identity(runs)
    unchanged = rp.original_unchanged(
        sha256_file(runs / rp.ORIGINAL_RECORD),
        sha256_file(runs / rp.ORIGINAL_RAW))
    if not unchanged["unchanged"]:
        raise RunError("원본 W00 산출물이 바뀌었다: %r" % unchanged["observed"])

    requested = {
        "sampling_fps": sh.SAMPLING_FPS, "frames": len(stamps),
        "frame_width": contract.FRAME_WIDTH,
        "frame_height": contract.FRAME_HEIGHT,
        "model_id": contract.MODEL_ID,
        "model_revision": contract.MODEL_REVISION,
        "dtype": contract.DTYPE,
        "attn_implementation": contract.ATTN_IMPLEMENTATION,
        "quantization": contract.QUANTIZATION,
        "device": contract.DEVICE, "device_map": contract.DEVICE_MAP,
        "do_sample": contract.DO_SAMPLE, "num_beams": contract.NUM_BEAMS,
        "max_new_tokens": events.tokens_for(events.EVENT_V2),
        "repetition_penalty": contract.REPETITION_PENALTY,
        "do_sample_frames": contract.DO_SAMPLE_FRAMES,
        "do_resize": contract.DO_RESIZE,
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_hash": diag.prompt_hash(),
        "output_language": diag.OUTPUT_LANGUAGE,
        "window_sec": sh.WINDOW_SEC,
        "frames_per_window": sh.FRAMES_PER_WINDOW,
    }
    change = sh.inference_config_change(requested)
    if change["inference_config_change"] != "NONE":
        raise RunError("inference 설정이 바뀌었다: %r" % change["differences"])
    runtime_hash = sha256_bytes(json.dumps(requested, sort_keys=True,
                                           ensure_ascii=False).encode("utf-8"))
    if runtime_hash != rp.ORIGINAL_RUNTIME_CONFIG_SHA256:
        raise RunError("runtime config 해시가 원본과 다르다: %s" % runtime_hash)

    return {"run_id": run_id, "window": window, "stamps": stamps,
            "requested": requested, "runtime_config_hash": runtime_hash,
            "prompt": rp.expected_prompt(), "raw_path": raw_path,
            "out_path": out_path, "original": original,
            "original_unchanged": unchanged, "video_sha256": sha256_file(video)}


def run(video: Path, run_id: str, runs: Path) -> dict:
    plan = preflight(run_id, runs, video)
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from transformers.video_utils import VideoMetadata

    window, stamps = plan["window"], plan["stamps"]
    raw_path, out_path = plan["raw_path"], plan["out_path"]

    record = {
        "schema": "wvr_w00_repro_v1", "event": rp.EVENT, "prereg": PREREG,
        "run_id": run_id, "window": window,
        "requested": plan["requested"],
        "runtime_config_hash": plan["runtime_config_hash"],
        "frame_times": list(stamps),
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_hash": diag.prompt_hash(),
        "generation_config": generation_config(),
        "video_sha256": plan["video_sha256"],
        "original_unchanged": plan["original_unchanged"],
        "code_git_head": os.environ.get("WVR_CODE_GIT_HEAD", "UNKNOWN"),
        "retry_allowed": rp.RETRY_ALLOWED,
        "production_selection_allowed": rp.PRODUCTION_SELECTION_ALLOWED,
        "semantic_verdict_by_executor": rp.SEMANTIC_VERDICT_BY_EXECUTOR,
        "raw_persisted": False,
        "raw_path": raw_path.name,
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
        frames, indices, times, rate = probe.sample_frames(video, stamps)
        metrics["delivered_frame_count"] = len(frames)
        metrics["frame_size"] = list(frames[0].size)
        record["frame_hashes"] = [sha256_bytes(frame.tobytes())
                                  for frame in frames]
        record["frame_indices"] = list(indices)
        record["decoded_times"] = list(times)
        record["decoded_fps"] = rate
        record["stage_status"]["VIDEO_PROCESS"] = "OK"

        observed = {
            "video_sha256": record["video_sha256"],
            "window": window,
            "frame_times": [round(float(time), 3) for time in stamps],
            "frame_hashes": list(record["frame_hashes"]),
            "prompt_text": plan["prompt"],
            "prompt_hash": record["prompt_hash"],
            "model_revision": contract.MODEL_REVISION,
            "runtime_config_hash": plan["runtime_config_hash"],
            "generation_config": {
                "do_sample": contract.DO_SAMPLE,
                "num_beams": contract.NUM_BEAMS,
                "max_new_tokens": events.tokens_for(events.EVENT_V2),
                "repetition_penalty": contract.REPETITION_PENALTY},
        }
        record["identity"] = rp.identity_report(plan["original"], observed)
        if not record["identity"]["identical"]:
            raise RunError("입력 identity 불일치: %r"
                           % record["identity"]["mismatched"])

        messages = [{"role": "user", "content": [{"type": "video"},
                                                 {"type": "text",
                                                  "text": plan["prompt"]}]}]
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

        infer_started = time.time()
        with torch.inference_mode():
            generated = model.generate(
                **inputs, do_sample=contract.DO_SAMPLE,
                num_beams=contract.NUM_BEAMS,
                max_new_tokens=events.tokens_for(events.EVENT_V2),
                repetition_penalty=contract.REPETITION_PENALTY)
        metrics["infer_wall_sec"] = round(time.time() - infer_started, 2)
        new_tokens = generated[0][inputs["input_ids"].shape[-1]:]
        metrics["generated_token_count"] = int(new_tokens.shape[-1])
        metrics["generation_cap_hit"] = bool(
            int(new_tokens.shape[-1]) >= events.tokens_for(events.EVENT_V2))
        metrics["finish_reason"] = ("length" if metrics["generation_cap_hit"]
                                    else "stop")
        raw_output = processor.tokenizer.decode(new_tokens,
                                                skip_special_tokens=True)

        # raw persist를 파싱보다 먼저 한다
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_output, encoding="utf-8")
        record["raw_persisted"] = True
        record["raw_output_hash"] = sha256_bytes(raw_output.encode("utf-8"))
        record["raw_output"] = raw_output
        record["stage_status"]["RAW_PERSIST"] = "OK"

        record["parsed"] = v2.parse_events(raw_output, window)
        record["representation"] = v2.representation(
            record["parsed"]["collapsed"])
        record["structure"] = rp.structure_audit(raw_output, metrics)
        record["degeneracy"] = rp.run_degeneracy(record["structure"])
        record["stage_status"]["INFERENCE"] = "OK"
        record["arm_status"] = record["parsed"]["status"]
    except Exception as error:                     # noqa: BLE001 — 전부 기록한다
        record["arm_status"] = "RUNTIME_FAILURE"
        record["error"] = {"type": type(error).__name__,
                           "message": str(error)[:2000]}
        for name in ("MODEL_LOAD", "VIDEO_PROCESS", "RAW_PERSIST",
                     "INFERENCE"):
            record["stage_status"].setdefault(name, "NOT_REACHED")
    finally:
        try:
            metrics["peak_vram_allocated_mib"] = round(
                torch.cuda.max_memory_allocated() / 1024 ** 2, 1)
            record["memory_stats"] = probe.memory_stats_subset()
        except Exception:
            pass
        metrics["total_wall_sec"] = round(time.time() - started, 2)
        record["validity"] = sh.window_validity(record,
                                                record.get("video_sha256"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="W00 재현성 run")
    parser.add_argument("--video", required=True)
    parser.add_argument("--run", required=True, choices=list(rp.RUN_IDS))
    parser.add_argument("--runs-dir", required=True)
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise RunError("영상이 없다: %s" % video)
    record = run(video, args.run, Path(args.runs_dir))
    metrics = record["metrics"]
    print("run=%s status=%s gen=%s cap=%s identity=%s"
          % (record["run_id"], record.get("arm_status"),
             metrics.get("generated_token_count"),
             metrics.get("generation_cap_hit"),
             (record.get("identity") or {}).get("status")))
    structure = record.get("structure") or {}
    print("  raw_chars=%s objects=%s uniq=%s zero_len=%s max_repeat=%s "
          "json_ok=%s degeneracy=%s"
          % (structure.get("raw_length"),
             structure.get("complete_object_count"),
             structure.get("unique_signature_count"),
             structure.get("zero_length_interval_count"),
             structure.get("max_signature_repeat"),
             structure.get("json_parse_ok"),
             (record.get("degeneracy") or {}).get("classification")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
