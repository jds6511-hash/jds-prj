"""SUBDIVISION_RECOVERY_V1 실행기 — child 하나당 fresh process 1회 (2026-09-09).

사전등록: `docs/preregistration/WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md`

```
입력    video-only. 자막·캡션·canonical evidence·과거 arm 텍스트·사람 판정 금지
동결    prompt·schema·model·runtime·표집·token cap 전부 W00과 동일
변경    창 길이 24초 · 12초 overlap · 12프레임 (이것만)
순서    raw persist → parse → collapse (정리 전에 원문을 먼저 남긴다)
재시도  없다. 실패한 child는 INVALID provenance로 남긴다
판정    기술 검증까지만. semantic 판정은 하지 않는다
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
import wvr_subdivision_v1 as sd                             # noqa: E402
import wvr_w00_forensic as fx                               # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md")
BANK_MANIFEST = "shadow_frame_bank.json"


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


def requested_config(child: dict, stamps) -> dict:
    """W00 requested와 창 기하만 다른 설정 표."""
    return {
        "sampling_fps": sd.SAMPLING_FPS, "frames": len(stamps),
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
        "window_sec": sd.CHILD_SEC,
        "frames_per_window": sd.FRAMES_PER_CHILD,
    }


def reference_hashes(runs: Path) -> dict:
    """기존 C01 계보 픽셀 해시 표 — 원본 W00 record + frame bank."""
    table, sources, conflicts = {}, [], []

    w00 = runs / sd.ORIGINAL_RECORD
    if w00.is_file():
        record = json.loads(w00.read_text(encoding="utf-8"))
        for time, digest in zip(record.get("frame_times") or [],
                                record.get("frame_hashes") or []):
            table[round(float(time), 3)] = digest
        sources.append(sd.ORIGINAL_RECORD)

    bank = runs / BANK_MANIFEST
    if bank.is_file():
        manifest = json.loads(bank.read_text(encoding="utf-8"))
        for row in manifest.get("frames") or []:
            time = round(float(row["time_sec"]), 3)
            digest = row["pixel_sha256"]
            if time in table and table[time] != digest:
                conflicts.append({"time_sec": time,
                                  "w00_sha256": table[time],
                                  "bank_sha256": digest})
            table.setdefault(time, digest)
        sources.append(BANK_MANIFEST)

    return {"table": table, "sources": sources, "conflicts": conflicts}


def preflight(child_id: str, runs: Path) -> dict:
    """GPU를 쓰기 전에 일정·동결값·원본 무변경·산출물 중복을 확인한다."""
    if child_id not in sd.CHILD_IDS:
        raise RunError("모르는 child: %r" % child_id)
    if sd.RETRY_ALLOWED or sd.RAW_SALVAGE_ALLOWED:
        raise RunError("retry·raw salvage는 금지돼 있다")
    if sd.TOKEN_CAP_INCREASE_APPROVED:
        raise RunError("token cap 상향은 승인되지 않았다")

    child = sd.child_by_id(child_id)
    stamps = list(sd.frame_times(child))
    sd.assert_coverage()
    sd.overlaps()

    requested = requested_config(child, stamps)
    sh.assert_video_only(requested)
    change = sd.inference_config_change(requested)
    if change["inference_config_change"] != "NONE":
        raise RunError("W00 대비 inference 설정이 바뀌었다: %r"
                       % change["differences"])
    if not change["geometry_as_declared"]:
        raise RunError("창 기하가 사전등록 값과 다르다: %r"
                       % change["observed_geometry"])
    max_new_tokens = events.tokens_for(events.EVENT_V2)
    events.assert_allowed(max_new_tokens)

    raw_path = runs / ("%s_%s_raw.txt" % (sd.ARTIFACT_TAG, child_id))
    out_path = runs / ("%s_%s.json" % (sd.ARTIFACT_TAG, child_id))
    for path in (raw_path, out_path):
        if path.exists():
            raise RunError("%s 산출물이 이미 있다 — child는 1회다" % path.name)

    unchanged = sd.original_unchanged(sha256_file(runs / sd.ORIGINAL_RECORD),
                                      sha256_file(runs / sd.ORIGINAL_RAW))
    if not unchanged["unchanged"]:
        raise RunError("원본 W00 산출물이 바뀌었다: %r" % unchanged["observed"])

    reference = reference_hashes(runs)
    if reference["conflicts"]:
        raise RunError("계보 대조표가 서로 다르다: %r" % reference["conflicts"][:3])
    missing = [time for time in stamps if time not in reference["table"]]

    prompt = diag.SAMPLING_DIAG_PROMPT_V2 % {
        "window_start": child["start_sec"], "window_end": child["end_sec"]}
    return {"child": child, "stamps": stamps, "requested": requested,
            "change": change, "prompt": prompt, "raw_path": raw_path,
            "out_path": out_path, "max_new_tokens": max_new_tokens,
            "original_unchanged": unchanged, "reference": reference,
            "reference_missing_times": missing}


def run(video: Path, child_id: str, runs: Path) -> dict:
    plan = preflight(child_id, runs)
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from transformers.video_utils import VideoMetadata

    child, stamps = plan["child"], plan["stamps"]
    raw_path, out_path = plan["raw_path"], plan["out_path"]

    record = {
        "schema": "wvr_subdivision_v1", "event": sd.EVENT, "prereg": PREREG,
        "child": child, "parent_window": sd.parent_window(),
        "requested": plan["requested"],
        "inference_config_change": plan["change"],
        "coverage": sd.coverage(),
        "frame_times": list(stamps),
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_hash": diag.prompt_hash(),
        "is_production_contract": diag.IS_PRODUCTION_CONTRACT,
        "output_language": diag.OUTPUT_LANGUAGE,
        "video_sha256": sha256_file(video),
        "code_git_head": os.environ.get("WVR_CODE_GIT_HEAD", "UNKNOWN"),
        "runtime_config_hash": sha256_bytes(
            json.dumps(plan["requested"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8")),
        "original_w00_unchanged": plan["original_unchanged"],
        "lineage_sources": plan["reference"]["sources"],
        "reference_missing_times": plan["reference_missing_times"],
        "raw_persisted": False, "raw_path": raw_path.name,
        "retry_allowed": sd.RETRY_ALLOWED,
        "semantic_verdict_by_executor": sd.SEMANTIC_VERDICT_BY_EXECUTOR,
        "production_promotion_allowed": sd.PRODUCTION_PROMOTION_ALLOWED,
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
        record["frame_hashes"] = [sha256_bytes(frame.tobytes())
                                  for frame in frames]
        record["frame_indices"] = list(indices)
        record["decoded_times"] = list(times)
        record["decoded_fps"] = rate
        record["lineage"] = sd.lineage_report(
            {child["child_id"]: dict(zip([round(float(time), 3)
                                          for time in stamps],
                                         record["frame_hashes"]))},
            plan["reference"]["table"])
        record["stage_status"]["VIDEO_PROCESS"] = "OK"

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
        video_token_id = getattr(model.config, "video_token_id", None)
        metrics["video_token_count"] = (
            int((inputs["input_ids"] == video_token_id).sum().item())
            if video_token_id is not None else None)

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

        record["parsed"] = v2.parse_events(raw_output, child)
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
        for name in ("MODEL_LOAD", "VIDEO_PROCESS", "RAW_PERSIST",
                     "INFERENCE"):
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
        record["validity"] = sd.child_validity(record, record["video_sha256"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="24초 subdivision recovery 실행기")
    parser.add_argument("--video", required=True)
    parser.add_argument("--child", required=True, choices=list(sd.CHILD_IDS))
    parser.add_argument("--runs-dir", required=True)
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise RunError("영상이 없다: %s" % video)
    record = run(video, args.child, Path(args.runs_dir))
    metrics = record["metrics"]
    print("child=%s %s status=%s frames=%s in=%s gen=%s cap=%s"
          % (record["child"]["child_id"],
             "%.0f-%.0f" % (record["child"]["start_sec"],
                            record["child"]["end_sec"]),
             record.get("arm_status"), metrics.get("delivered_frame_count"),
             metrics.get("input_token_count"),
             metrics.get("generated_token_count"),
             metrics.get("generation_cap_hit")))
    shape = record.get("representation") or {}
    validity = record.get("validity") or {}
    lineage = record.get("lineage") or {}
    print("  raw=%s collapsed=%s uniq=%s degenerate=%s lineage=%s/%s "
          "validity=%s %s"
          % (len((record.get("parsed") or {}).get("events", [])),
             shape.get("collapsed_event_count"),
             shape.get("unique_signature_count"), shape.get("degenerate"),
             lineage.get("checked"), len(lineage.get("mismatches") or []),
             validity.get("status"), validity.get("reasons")))
    return 0 if validity.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
