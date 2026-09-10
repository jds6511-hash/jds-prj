"""Technical validator for executed boundary candidate V1 artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_bcand_build as builder  # noqa: E402
import wvr_bcand_selfcheck as selfcheck  # noqa: E402
import wvr_boundary_candidate_v1 as bc  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def checks(runs: Path, submission: Path) -> dict:
    rows = {}
    try:
        rebuilt = builder.build(runs)
        record = _load(runs / "bcand_v1_record.json")
        batches_doc = _load(runs / "bcand_v1_batches.json")
        proposals_doc = _load(runs / "bcand_v1_proposals.json")
        summary = _load(runs / "bcand_v1_summary.json")
        audit = _load(runs / "bcand_v1_leakage_audit.json")
        packet_ids_doc = _load(runs / "bcand_v1_packet_ids.json")
        packet = (runs / "bcand_v1_packet.md").read_text(encoding="utf-8")
        appendix = (runs / "bcand_v1_appendix_weak.md").read_text(encoding="utf-8")
    except (OSError, KeyError, json.JSONDecodeError, builder.BuildError):
        return {"status": "FAIL", "checks": {"required_artifacts_load": False}}
    proposals_list = proposals_doc.get("proposals") or []
    proposals = {row.get("candidate_id"): row for row in proposals_list
                 if isinstance(row, dict)}
    candidates = rebuilt["candidates"]
    events = rebuilt["events"]
    expected_ids = {row["candidate_id"] for row in candidates}
    raw_ok = True
    for batch in batches_doc["batches"]:
        batch_id = batch["batch_id"]
        raw_path = runs / ("bcand_v1_raw_%s.txt" % batch_id)
        raw_ok &= (raw_path.is_file()
                   and record.get("raw_sha256", {}).get(batch_id)
                   == (_sha256_file(raw_path) if raw_path.is_file() else None))
    try:
        expected_packet = bc.reviewer_packet(candidates, proposals)
        expected_appendix = bc.weak_appendix(candidates, proposals)
        recomputed_leakage = bc.leakage_audit([packet, appendix], events, candidates)
        vocabulary_ok = all(row.get("proposal") in bc.PROPOSALS
                            for row in proposals.values())
    except (KeyError, bc.CandidateError):
        expected_packet = expected_appendix = ""
        recomputed_leakage = {"violations": ["INVALID_PROPOSALS"]}
        vocabulary_ok = False
    downstream = ("bcand_v1_chapters.json", "bcand_v1_overview.json",
                  "bcand_v1_analysis.json", "bcand_v1_conclusion.json",
                  "bcand_v1_report.json", "bcand_v1_report.hwpx")
    requested_runtime = {
        "model_id": bc.LLM_MODEL_ID,
        "revision": bc.LLM_MODEL_REVISION,
        "dtype": bc.LLM_DTYPE,
        "attn_implementation": bc.LLM_ATTN_IMPLEMENTATION,
        "load_4bit": bc.LLM_LOAD_4BIT,
        "do_sample": bc.LLM_DO_SAMPLE,
        "max_new_tokens": bc.LLM_MAX_NEW_TOKENS,
    }
    effective = record.get("effective_runtime") or {}
    metrics = record.get("runtime_metrics") or {}
    runtime_exact = (
        record.get("requested_runtime") == requested_runtime
        and effective.get("effective_model_id") == bc.LLM_MODEL_ID
        and effective.get("effective_model_revision") == bc.LLM_MODEL_REVISION
        and str(effective.get("effective_dtype", "")).lower().endswith("bfloat16")
        and str(effective.get("attn_implementation", "")).lower() == "sdpa"
        and effective.get("effective_quantized") is False
        and metrics.get("cuda_available") is True
        and isinstance(metrics.get("device_count"), int)
        and metrics["device_count"] >= 1
        and any("4090" in str(name) for name in metrics.get("device_names", []))
        and isinstance(metrics.get("max_memory_allocated_bytes"), int)
        and metrics["max_memory_allocated_bytes"] >= 0
        and isinstance(metrics.get("max_memory_reserved_bytes"), int)
        and metrics["max_memory_reserved_bytes"] >= 0
    )
    rows.update({
        "preflight_still_passes":
            selfcheck.checks(runs, submission)["status"] == "PASS",
        "raw_all_present_and_hashed": raw_ok
            and len(record.get("raw_sha256", {})) == bc.EXPECTED_BATCH_COUNT,
        "raw_before_parse_recorded":
            record.get("raw_persisted_before_parse") is True
            and record.get("parsed_here") is False,
        "single_attempt_no_retry":
            record.get("generation_attempts_per_batch") == 1
            and record.get("retry_allowed") is False,
        "runtime_contract_exact": runtime_exact,
        "all_candidate_ids_exactly_once":
            len(proposals_list) == bc.EXPECTED_CANDIDATE_COUNT
            and len(proposals) == bc.EXPECTED_CANDIDATE_COUNT
            and set(proposals) == expected_ids,
        "allowed_vocabulary_only": vocabulary_ok,
        "reviewer_packet_exact": packet == expected_packet,
        "weak_appendix_exact": appendix == expected_appendix,
        "packet_ids_exact": packet_ids_doc.get("packet_candidate_ids")
            == bc.packet_ids(proposals),
        "leakage_zero": audit.get("violations") == []
            and recomputed_leakage.get("violations") == [],
        "mapping_remained_sealed":
            "candidate_to_time" not in packet
            and "observation_set_to_window" not in packet
            and summary.get("mapping_revealed") is False,
        "executor_has_no_verdict":
            summary.get("reviewer_final_verdict") is None
            and summary.get("executor_state", {}).get("verdict") is None
            and summary.get("executor_state", {}).get("verdict_by_executor") is False,
        "no_downstream_artifacts": not any((runs / name).exists()
                                             for name in downstream),
        "submission_unchanged": submission.is_file()
            and selfcheck.sha256_file(submission) == selfcheck.SUBMISSION_SHA256,
        "no_vlm_or_track_a": record.get("new_vlm_inference_count") == 0
            and record.get("track_a_input_used") is False,
        "no_chapter_or_overview": record.get("chapter_generated") is False
            and record.get("overview_generated") is False,
    })
    return {"status": "PASS" if all(rows.values()) else "FAIL", "checks": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--submission", default="runs/quality_candidate/S7/report.hwpx")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = checks(Path(args.runs), Path(args.submission))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True))
    else:
        print("validator=%s checks=%d/%d" %
              (report["status"], sum(report["checks"].values()),
               len(report["checks"])))
        for name, value in report["checks"].items():
            print("  check %-44s %s" % (name, value))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
