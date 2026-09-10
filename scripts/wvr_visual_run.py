"""VISUAL_CONTENT_ISOLATION_V1 실행기 — arm E 1회 (2026-09-10).

사전등록: `docs/preregistration/WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md`

```
픽셀    실제 120,122,…,166초 24장 — 기존 W05와 pixel-identical해야 한다
시간    prompt 0–48 + frames_indices 0…1,380 (Trigger arm A와 동일)
고정    prompt 문구·schema·token cap·penalty·표집·metadata 6필드
순서    raw persist → parse → 구조 audit
금지    retry · raw salvage · 기존 세 칸 재실행 · processor monkey-patch
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
import wvr_trigger_run as trigger_runner                    # noqa: E402
import wvr_trigger_v1 as tg                                 # noqa: E402
import wvr_visual_v1 as vc                                  # noqa: E402
import wvr_w00_forensic as fx                               # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md")


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


def observed_artifacts(runs: Path) -> dict:
    rows = {}
    for name in vc.FROZEN_ARTIFACTS:
        path = runs / name
        if path.is_file():
            rows[name] = sha256_file(path)
    return rows


def pixel_reference(runs: Path) -> list:
    """기존 W05 record의 24 픽셀 해시 (계보 기준)."""
    path = runs / vc.PIXEL_REFERENCE_RECORD
    if not path.is_file():
        return []
    record = json.loads(path.read_text(encoding="utf-8"))
    times = [round(float(time), 3) for time in record.get("frame_times") or []]
    if times != list(vc.pixel_times()):
        raise RunError("W05 격자가 픽셀 시각과 다르다: %r" % times[:4])
    return list(record.get("frame_hashes") or [])


def time_reference(runs: Path) -> dict:
    """Trigger arm A record에서 시간 인코딩 기준을 읽는다 (수정하지 않는다)."""
    path = runs / vc.TIME_REFERENCE_RECORD
    if not path.is_file():
        return {}
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("arm", {}).get("arm_id") != vc.TIME_REFERENCE_ARM:
        raise RunError("시간 기준 arm이 %s가 아니다" % vc.TIME_REFERENCE_ARM)
    return {"rendered_prompt_hash": record.get("rendered_prompt_hash"),
            "prompt_window": record.get("prompt_window"),
            "prompt_template_hash": record.get("prompt_template_hash"),
            "metadata": record.get("metadata") or {}}


def preflight(runs: Path, rate=None) -> dict:
    """GPU를 쓰기 전에 설계·동결값·기존 세 칸·중복을 확인한다."""
    for flag in ("RETRY_ALLOWED", "RAW_SALVAGE_ALLOWED",
                 "TOKEN_CAP_INCREASE_APPROVED",
                 "PROMPT_TEXT_MUTATION_ALLOWED",
                 "ZERO_DURATION_EXAMPLE_MUTATION_ALLOWED",
                 "SCHEMA_MUTATION_ALLOWED", "SUBDIVISION_RESTART_ALLOWED",
                 "ADDITIONAL_SHIFT_ALLOWED",
                 "PROCESSOR_MONKEY_PATCH_ALLOWED",
                 "RERUN_OF_FROZEN_CELLS_ALLOWED"):
        if getattr(vc, flag):
            raise RunError("%s가 열려 있다 — 사전등록 위반" % flag)

    # 설정 표는 TRIGGER_ISOLATION_V1과 같은 코드 경로에서 만든다 (동일성 보장)
    requested = trigger_runner.requested_config()
    sh.assert_video_only(requested)
    change = sh.inference_config_change(requested)
    if change["inference_config_change"] != "NONE":
        raise RunError("동결 설정이 바뀌었다: %r" % change["differences"])
    max_new_tokens = events.tokens_for(events.EVENT_V2)
    events.assert_allowed(max_new_tokens)

    raw_path = runs / ("%s_%s_raw.txt" % (vc.ARTIFACT_TAG, vc.ARM_ID))
    out_path = runs / ("%s_%s.json" % (vc.ARTIFACT_TAG, vc.ARM_ID))
    for path in (raw_path, out_path):
        if path.exists():
            raise RunError("%s 산출물이 이미 있다 — arm E는 1회다" % path.name)

    cells = vc.frozen_cells_unchanged(observed_artifacts(runs))
    if not cells["unchanged"]:
        raise RunError("기존 세 칸·원본 산출물이 바뀌었거나 없다: "
                       "changed=%r missing=%r"
                       % (cells["changed"], cells["missing"]))

    pixels = pixel_reference(runs)
    if len(pixels) != vc.PIXEL_FRAME_COUNT:
        raise RunError("W05 픽셀 해시 %d개를 읽지 못했다: %d"
                       % (vc.PIXEL_FRAME_COUNT, len(pixels)))
    times = time_reference(runs)
    if not times.get("rendered_prompt_hash"):
        raise RunError("Trigger arm A 시간 기준을 읽지 못했다")
    if times["rendered_prompt_hash"] != \
            tg.rendered_prompt_hash(vc.PROMPT_MODE):
        raise RunError("A의 rendered prompt hash가 T0와 다르다: %s"
                       % times["rendered_prompt_hash"])

    return {"requested": requested, "change": change,
            "max_new_tokens": max_new_tokens, "raw_path": raw_path,
            "out_path": out_path, "frozen_cells": cells,
            "pixel_reference": pixels, "time_reference": times,
            "plan": vc.arm_plan(rate) if rate else None}


def run(video: Path, runs: Path) -> dict:
    plan = preflight(runs)
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from transformers.video_utils import VideoMetadata

    raw_path, out_path = plan["raw_path"], plan["out_path"]
    stamps = list(vc.pixel_times())

    record = {
        "schema": "wvr_visual_v1", "event": vc.EVENT, "prereg": PREREG,
        "arm": {"arm_id": vc.ARM_ID, "cell": vc.CELL_X1T0["cell"],
                "pixel_source": vc.PIXEL_SOURCE_WINDOW_ID,
                "time_encoding": vc.TIME_ENCODING,
                "prompt_mode": vc.PROMPT_MODE,
                "metadata_mode": vc.METADATA_MODE},
        "pixel_source_window": vc.pixel_source_window(),
        "requested": plan["requested"],
        "inference_config_change": plan["change"],
        "pixel_times": list(stamps),
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_template_hash": tg.prompt_template_hash(),
        "is_production_contract": diag.IS_PRODUCTION_CONTRACT,
        "output_language": diag.OUTPUT_LANGUAGE,
        "video_sha256": sha256_file(video),
        "code_git_head": os.environ.get("WVR_CODE_GIT_HEAD", "UNKNOWN"),
        "runtime_config_hash": sha256_bytes(
            json.dumps(plan["requested"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8")),
        "frozen_cells_unchanged": plan["frozen_cells"],
        "raw_persisted": False, "raw_path": raw_path.name,
        "retry_allowed": vc.RETRY_ALLOWED,
        "rerun_of_frozen_cells_allowed": vc.RERUN_OF_FROZEN_CELLS_ALLOWED,
        "semantic_verdict_by_executor": vc.SEMANTIC_VERDICT_BY_EXECUTOR,
        "event_kind": vc.EVENT_KIND,
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
        frames, decoded_indices, times, rate = probe.sample_frames(video,
                                                                   stamps)
        metrics["delivered_frame_count"] = len(frames)
        metrics["frame_size"] = list(frames[0].size)
        record["frame_hashes"] = [sha256_bytes(frame.tobytes())
                                  for frame in frames]
        record["decoded_frame_indices"] = list(decoded_indices)
        record["decoded_times"] = list(times)
        record["decoded_fps"] = rate
        record["pixel_identity"] = vc.pixel_identity(
            record["frame_hashes"], plan["pixel_reference"])
        if not record["pixel_identity"]["identical"]:
            raise RunError("픽셀이 기존 W05와 다르다: %r"
                           % record["pixel_identity"]["mismatched_positions"])
        record["stage_status"]["VIDEO_PROCESS"] = "OK"

        arm = vc.arm_plan(rate)
        record["arm_plan"] = {key: value for key, value in arm.items()
                              if key != "rendered_prompt"}
        record["prompt_window"] = arm["prompt_window"]
        record["rendered_prompt_hash"] = arm["rendered_prompt_hash"]

        messages = [{"role": "user",
                     "content": [{"type": "video"},
                                 {"type": "text",
                                  "text": arm["rendered_prompt"]}]}]
        text = processor.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True)
        metadata_used = {
            "total_num_frames": meta["nb_frames"], "fps": rate,
            "width": meta["width"], "height": meta["height"],
            "duration": meta["duration_sec"], "video_backend": "pyav",
            "frames_indices": list(arm["frames_indices"])}
        record["metadata"] = metadata_used
        record["time_encoding_identity"] = vc.time_encoding_identity(
            record, plan["time_reference"])
        if not record["time_encoding_identity"]["identical"]:
            raise RunError("시간 인코딩이 Trigger A와 다르다: %r"
                           % record["time_encoding_identity"]["mismatched"])

        metadata = VideoMetadata(
            total_num_frames=metadata_used["total_num_frames"],
            fps=metadata_used["fps"], width=metadata_used["width"],
            height=metadata_used["height"],
            duration=metadata_used["duration"],
            video_backend=metadata_used["video_backend"],
            frames_indices=list(metadata_used["frames_indices"]))
        inputs = processor(text=[text], videos=[frames],
                           video_metadata=[metadata],
                           do_sample_frames=contract.DO_SAMPLE_FRAMES,
                           do_resize=contract.DO_RESIZE, return_tensors="pt")
        record["pixel_values_sha256"] = sha256_bytes(
            inputs["pixel_values_videos"].cpu().numpy().tobytes())
        inputs = inputs.to(contract.DEVICE)
        metrics["input_token_count"] = int(inputs["input_ids"].shape[-1])
        video_token_id = getattr(model.config, "video_token_id", None)
        metrics["video_token_count"] = (
            int((inputs["input_ids"] == video_token_id).sum().item())
            if video_token_id is not None else None)
        decoded_prompt = processor.tokenizer.decode(inputs["input_ids"][0])
        record["timestamp_markers"] = _markers(decoded_prompt)
        record["stage_status"]["PROMPT_BUILD"] = "OK"

        infer_started = time.time()
        with torch.inference_mode():
            generated = model.generate(
                **inputs, do_sample=contract.DO_SAMPLE,
                num_beams=contract.NUM_BEAMS,
                max_new_tokens=plan["max_new_tokens"],
                repetition_penalty=contract.REPETITION_PENALTY)
        metrics["infer_wall_sec"] = round(time.time() - infer_started, 2)
        new_tokens = generated[0][inputs["input_ids"].shape[-1]:]
        metrics["generated_token_count"] = int(new_tokens.shape[-1])
        metrics["generation_cap_hit"] = bool(
            int(new_tokens.shape[-1]) >= plan["max_new_tokens"])
        raw_output = processor.tokenizer.decode(new_tokens,
                                                skip_special_tokens=True)

        # ── raw persist를 파싱보다 먼저 한다 ─────────────────────────
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_output, encoding="utf-8")
        record["raw_persisted"] = True
        record["raw_output_hash"] = sha256_bytes(raw_output.encode("utf-8"))
        record["raw_output"] = raw_output
        record["stage_status"]["RAW_PERSIST"] = "OK"

        parse_window = {"start_sec": arm["prompt_window"][0],
                        "end_sec": arm["prompt_window"][1]}
        record["parse_window"] = parse_window
        record["parsed"] = v2.parse_events(raw_output, parse_window)
        record["parsed_output_hash"] = sha256_bytes(
            json.dumps(record["parsed"]["events"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8"))
        record["representation"] = v2.representation(
            record["parsed"]["collapsed"])
        record["collapse_output_hash"] = sha256_bytes(
            json.dumps(record["parsed"]["collapsed"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8"))
        record["structure"] = fx.raw_structure(raw_output)
        record["stage_status"]["INFERENCE"] = "OK"
        record["arm_status"] = record["parsed"]["status"]
        record["finish_reason"] = ("length" if metrics["generation_cap_hit"]
                                   else "stop")
    except Exception as error:                     # noqa: BLE001 — 전부 기록한다
        record["arm_status"] = "RUNTIME_FAILURE"
        record["error"] = {"type": type(error).__name__,
                           "message": str(error)[:2000]}
        for name in ("MODEL_LOAD", "VIDEO_PROCESS", "PROMPT_BUILD",
                     "RAW_PERSIST", "INFERENCE"):
            record["stage_status"].setdefault(name, "NOT_REACHED")
    finally:
        try:
            metrics["peak_vram_allocated_mib"] = round(
                torch.cuda.max_memory_allocated() / 1024 ** 2, 1)
            record["memory_stats"] = probe.memory_stats_subset()
        except Exception:
            pass
        metrics["total_wall_sec"] = round(time.time() - started, 2)
        record["validity"] = vc.arm_validity(record,
                                             record.get("video_sha256"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return record


def _markers(decoded_prompt: str) -> list:
    import re

    return re.findall(r"<(\d+(?:\.\d+)?) seconds>", decoded_prompt)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="visual content isolation 실행기 (arm E 1회)")
    parser.add_argument("--video", required=True)
    parser.add_argument("--runs-dir", required=True)
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise RunError("영상이 없다: %s" % video)
    record = run(video, Path(args.runs_dir))
    metrics = record["metrics"]
    markers = record.get("timestamp_markers") or []
    print("arm=E cell=%s pixels=%s time=%s status=%s frames=%s in=%s gen=%s "
          "cap=%s" % (record["arm"]["cell"], record["arm"]["pixel_source"],
                      record["arm"]["time_encoding"],
                      record.get("arm_status"),
                      metrics.get("delivered_frame_count"),
                      metrics.get("input_token_count"),
                      metrics.get("generated_token_count"),
                      metrics.get("generation_cap_hit")))
    structure = record.get("structure") or {}
    shape = record.get("representation") or {}
    validity = record.get("validity") or {}
    print("  window=%s markers=%s..%s obj=%s uniq=%s zero=%s coll=%s json=%s "
          "pixel_ok=%s time_ok=%s %s %s"
          % (record.get("prompt_window"),
             markers[0] if markers else None, markers[-1] if markers else None,
             structure.get("complete_object_count"),
             structure.get("unique_signature_count"),
             structure.get("zero_length_interval_count"),
             shape.get("collapsed_event_count"),
             structure.get("json_parse_ok"),
             (record.get("pixel_identity") or {}).get("identical"),
             (record.get("time_encoding_identity") or {}).get("identical"),
             validity.get("status"), validity.get("reasons")))
    return 0 if validity.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
