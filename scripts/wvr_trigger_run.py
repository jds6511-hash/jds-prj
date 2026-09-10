"""TRIGGER_ISOLATION_V1 실행기 — arm 하나당 fresh process 1회 (2026-09-10).

사전등록: `docs/preregistration/WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md`

```
픽셀    항상 W00 [0,48) 0.5fps 24장 — arm 사이에서 바뀌지 않는다
조작    ① rendered prompt의 window 숫자값 ② VideoMetadata.frames_indices
고정    prompt 문구·schema·token cap·표집·창 길이 ·
       duration·total_num_frames·fps·width/height·backend
순서    raw persist → parse → collapse → 구조 audit
금지    retry · raw salvage · processor monkey-patch · recovery 시도
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
import wvr_trigger_v1 as tg                                 # noqa: E402
import wvr_w00_forensic as fx                               # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md")


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


def requested_config() -> dict:
    """4 arm 공통 설정 표 — arm 조작은 여기에 들어가지 않는다."""
    return {
        "sampling_fps": tg.SAMPLING_FPS, "frames": tg.PIXEL_FRAME_COUNT,
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


def observed_artifacts(runs: Path) -> dict:
    rows = {}
    for name in tg.FROZEN_ARTIFACTS:
        path = runs / name
        if path.is_file():
            rows[name] = sha256_file(path)
    return rows


def reference_pixel_hashes(runs: Path) -> list:
    """원본 W00 record가 기록한 24 픽셀 해시 (계보 기준)."""
    path = runs / tg.ORIGINAL_RECORD
    if not path.is_file():
        return []
    record = json.loads(path.read_text(encoding="utf-8"))
    times = [round(float(time), 3) for time in record.get("frame_times") or []]
    if times != list(tg.pixel_times()):
        raise RunError("원본 W00 격자가 픽셀 시각과 다르다: %r" % times[:4])
    return list(record.get("frame_hashes") or [])


def preflight(arm_id: str, runs: Path, rate=None) -> dict:
    """GPU를 쓰기 전에 arm 설계·동결값·선행 산출물·중복을 확인한다."""
    if arm_id not in tg.ARM_IDS:
        raise RunError("모르는 arm: %r" % arm_id)
    if tg.RETRY_ALLOWED or tg.RAW_SALVAGE_ALLOWED:
        raise RunError("retry·raw salvage는 금지돼 있다")
    if tg.TOKEN_CAP_INCREASE_APPROVED or tg.PROMPT_TEXT_MUTATION_ALLOWED \
            or tg.SCHEMA_MUTATION_ALLOWED:
        raise RunError("token cap·prompt 문구·schema 변경은 승인되지 않았다")
    if tg.PROCESSOR_MONKEY_PATCH_ALLOWED:
        raise RunError("processor monkey-patch는 금지돼 있다")

    requested = requested_config()
    sh.assert_video_only(requested)
    change = sh.inference_config_change(requested)
    if change["inference_config_change"] != "NONE":
        raise RunError("W00 대비 inference 설정이 바뀌었다: %r"
                       % change["differences"])
    max_new_tokens = events.tokens_for(events.EVENT_V2)
    events.assert_allowed(max_new_tokens)

    raw_path = runs / ("%s_%s_raw.txt" % (tg.ARTIFACT_TAG, arm_id))
    out_path = runs / ("%s_%s.json" % (tg.ARTIFACT_TAG, arm_id))
    for path in (raw_path, out_path):
        if path.exists():
            raise RunError("%s 산출물이 이미 있다 — arm은 1회다" % path.name)

    unchanged = tg.frozen_artifacts_unchanged(observed_artifacts(runs))
    if not unchanged["unchanged"]:
        raise RunError("선행 산출물이 바뀌었거나 없다: changed=%r missing=%r"
                       % (unchanged["changed"], unchanged["missing"]))

    reference = reference_pixel_hashes(runs)
    if len(reference) != tg.PIXEL_FRAME_COUNT:
        raise RunError("원본 W00 픽셀 해시 %d개를 읽지 못했다: %d"
                       % (tg.PIXEL_FRAME_COUNT, len(reference)))

    plan = tg.arm_plan(arm_id, rate) if rate else None
    return {"arm_id": arm_id, "requested": requested, "change": change,
            "max_new_tokens": max_new_tokens, "raw_path": raw_path,
            "out_path": out_path, "frozen_artifacts": unchanged,
            "reference_pixel_hashes": reference, "plan": plan}


def run(video: Path, arm_id: str, runs: Path) -> dict:
    plan = preflight(arm_id, runs)
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from transformers.video_utils import VideoMetadata

    raw_path, out_path = plan["raw_path"], plan["out_path"]
    stamps = list(tg.pixel_times())

    record = {
        "schema": "wvr_trigger_v1", "event": tg.EVENT, "prereg": PREREG,
        "arm": tg.arm_by_id(arm_id),
        "source_window": tg.source_window(),
        "shift_sec": tg.SHIFT_SEC,
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
        "frozen_artifacts_unchanged": plan["frozen_artifacts"],
        "raw_persisted": False, "raw_path": raw_path.name,
        "retry_allowed": tg.RETRY_ALLOWED,
        "processor_monkey_patch_allowed": tg.PROCESSOR_MONKEY_PATCH_ALLOWED,
        "semantic_verdict_by_executor": tg.SEMANTIC_VERDICT_BY_EXECUTOR,
        "event_kind": tg.EVENT_KIND,
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
        record["pixel_identity"] = tg.pixel_identity(
            record["frame_hashes"], plan["reference_pixel_hashes"])
        if not record["pixel_identity"]["identical"]:
            raise RunError("픽셀이 원본 W00과 다르다: %r"
                           % record["pixel_identity"]["mismatched_positions"])
        record["stage_status"]["VIDEO_PROCESS"] = "OK"

        # ── arm 조작은 여기서만 들어간다 ────────────────────────────
        arm = tg.arm_plan(arm_id, rate)
        record["arm_plan"] = {key: value for key, value in arm.items()
                              if key != "rendered_prompt"}
        record["rendered_prompt_hash"] = arm["rendered_prompt_hash"]
        record["prompt_window"] = arm["prompt_window"]
        record["metadata_times"] = arm["metadata_times"]
        if arm["metadata_mode"] == "M0" and \
                list(arm["frames_indices"]) != list(decoded_indices):
            raise RunError("M0 indices가 디코드 index와 다르다: %r"
                           % arm["frames_indices"][:4])

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
        record["prompt_text_sha256"] = sha256_bytes(text.encode("utf-8"))
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
        record["validity"] = tg.arm_validity(record,
                                             record.get("video_sha256"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return record


def _markers(decoded_prompt: str) -> list:
    """프롬프트에 실제로 들어간 <X.X seconds> 마커 (조작 확인용)."""
    import re

    return re.findall(r"<(\d+(?:\.\d+)?) seconds>", decoded_prompt)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="trigger isolation 실행기")
    parser.add_argument("--video", required=True)
    parser.add_argument("--arm", required=True, choices=list(tg.ARM_IDS))
    parser.add_argument("--runs-dir", required=True)
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise RunError("영상이 없다: %s" % video)
    record = run(video, args.arm, Path(args.runs_dir))
    metrics = record["metrics"]
    arm = record["arm"]
    markers = record.get("timestamp_markers") or []
    print("arm=%s %s/%s status=%s frames=%s in=%s gen=%s cap=%s"
          % (arm["arm_id"], arm["prompt_mode"], arm["metadata_mode"],
             record.get("arm_status"), metrics.get("delivered_frame_count"),
             metrics.get("input_token_count"),
             metrics.get("generated_token_count"),
             metrics.get("generation_cap_hit")))
    structure = record.get("structure") or {}
    shape = record.get("representation") or {}
    validity = record.get("validity") or {}
    print("  window=%s markers=%s..%s obj=%s uniq=%s zero=%s coll=%s json=%s "
          "pixel_ok=%s %s %s"
          % (record.get("prompt_window"),
             markers[0] if markers else None, markers[-1] if markers else None,
             structure.get("complete_object_count"),
             structure.get("unique_signature_count"),
             structure.get("zero_length_interval_count"),
             shape.get("collapsed_event_count"),
             structure.get("json_parse_ok"),
             (record.get("pixel_identity") or {}).get("identical"),
             validity.get("status"), validity.get("reasons")))
    return 0 if validity.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
