"""BOUNDARY_REPAIR_V1 validator (2026-09-10).

사전등록:
`docs/preregistration/WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md`

Stage A 산출물은 항상 검사한다. Stage B 산출물이 있을 때만 chapter 검사도 한다
(Stage A가 blocker로 멈추면 Stage B 산출물이 없는 것이 정상이다).
최종 PASS/HOLD는 리뷰어가 낸다 — 이 도구는 계산하지 않는다.

사용: `python scripts/wvr_crepair_validate.py --runs runs/wvr_light_v1`
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_chapter_repair_v1 as cr                           # noqa: E402
import wvr_chapter_selfcheck as v1check                      # noqa: E402
import wvr_crepair_build as builder                          # noqa: E402
import wvr_crepair_run as runner                             # noqa: E402
import wvr_crepair_stagea as stagea                          # noqa: E402


def _load(runs: Path, name: str) -> dict:
    return json.loads((runs / name).read_text(encoding="utf-8"))


def stage_a_checks(runs: Path) -> dict:
    document = v1check.load_map(runs)
    candidates = _load(runs, stagea.CANDIDATES_NAME)
    rebuilt = stagea.stage_a(runs)
    rows = candidates["candidates"]
    events = cr.source_events(document)
    event_starts = {round(row["start_sec"], 3) for row in events}
    region_edges = {edge for region in document["regions"]
                    for edge in (region["start_sec"], region["end_sec"])}
    accepted = [row for row in rows if row["excluded"] is None]
    known_events = {row["event_id"] for row in events}
    return {
        "source_map_hash_frozen":
            stagea.sha256_file(runs / cr.SOURCE_MAP_NAME)
            == cr.SOURCE_MAP_SHA256,
        "no_vlm_inference_and_no_track_a":
            candidates["provenance"]["new_vlm_inference_count"] == 0
            and candidates["provenance"]["track_a_input_used"] is False
            and candidates["provenance"]["stage_a_rule"]["llm_used"] is False,
        "candidates_are_event_start_times_only": all(
            round(row["boundary_sec"], 3) in event_starts for row in rows),
        "no_grid_or_region_injection":
            candidates["provenance"]["stage_a_rule"]
            ["region_boundary_injected"] is False
            and candidates["provenance"]["stage_a_rule"]
            ["grid_boundary_injected"] is False
            and not (set(round(row["boundary_sec"], 3) for row in rows)
                     - event_starts),
        "no_jitter_applied":
            candidates["provenance"]["stage_a_rule"]["jitter_applied"] is False,
        "stage_a_rule_frozen":
            candidates["provenance"]["stage_a_rule"]["detect_window_sec"]
            == cr.DETECT_WINDOW_SEC
            and candidates["provenance"]["stage_a_rule"]["sustain_window_sec"]
            == cr.SUSTAIN_WINDOW_SEC
            and candidates["provenance"]["stage_a_rule"]["min_separation_sec"]
            == cr.MIN_SEPARATION_SEC,
        "every_candidate_carries_both_side_evidence": all(
            (row["before_event_ids"] and row["after_event_ids"])
            or row["excluded"] == "NO_EVIDENCE_ON_BOTH_SIDES"
            for row in rows),
        "candidate_event_ids_exist": all(
            event_id in known_events for row in rows
            for event_id in row["before_event_ids"] + row["after_event_ids"]),
        "accepted_candidates_have_reasons": all(
            row["reason"] and all(name in cr.BOUNDARY_REASONS
                                  for name in row["reason"])
            for row in accepted),
        "conflict_unsupported_boundaries_excluded": all(
            row["excluded"] is not None for row in rows
            if row["in_conflict_block"]
            and row["conflict_source_reasons"]
            and not set.intersection(*[
                set(value) for value in
                row["conflict_source_reasons"].values()])),
        "selection_ignores_geometry":
            candidates["rule_relaxed"] is False
            and cr.select_boundaries(rows) == cr.select_boundaries(
                [dict(row, boundary_sec=row["boundary_sec"]) for row in rows]),
        "deterministic_stage_a":
            cr.canonical(rebuilt["candidates"]["candidates"])
            == cr.canonical(rows)
            and rebuilt["candidates"]["selected_boundaries"]
            == candidates["selected_boundaries"],
        "blocker_recorded_consistently": (
            (candidates["blocker"] is None)
            == ((runs / stagea.BOUNDARIES_NAME).is_file())),
        "boundaries_not_frozen_when_blocked": (
            candidates["blocker"] is None
            or not (runs / stagea.BOUNDARIES_NAME).is_file()),
        "region_edges_not_used_as_candidate_source": not (
            {round(row["boundary_sec"], 3) for row in rows} <= region_edges),
    }


def stage_b_checks(runs: Path) -> dict:
    document = _load(runs, cr.SOURCE_MAP_NAME)
    chapters_doc = _load(runs, builder.CHAPTERS_NAME)
    summary = _load(runs, builder.SUMMARY_NAME)
    record = _load(runs, runner.RECORD_NAME)
    raw = (runs / runner.RAW_NAME).read_text(encoding="utf-8")
    packet = (runs / builder.PACKET_NAME).read_text(encoding="utf-8")
    frozen = _load(runs, stagea.BOUNDARIES_NAME)
    rebuilt = builder.build(runs)
    chapters = chapters_doc["chapters"]
    supports = chapters_doc["chapter_support"]
    classes = chapters_doc["evidence"]
    disclosures = chapters_doc["disclosure_audit"]
    known_events = {row["event_id"] for row in document["lineage"]}
    doc_text = json.dumps(chapters_doc, ensure_ascii=False).lower()
    return {
        "raw_persisted_before_parse":
            record["raw_persisted_before_parse"] is True
            and record["parsed_here"] is False
            and cr.sha256_text(raw) == record["raw_sha256"],
        "single_generation_attempt":
            record["generation_attempts"] == cr.GENERATION_ATTEMPTS
            and record["retry_allowed"] is False,
        "llm_did_not_change_boundaries":
            [row["start_sec"] for row in chapters[1:]]
            == [row["boundary_sec"] for row in frozen["boundaries"]]
            and record["llm_may_change_boundaries"] is False
            and record["llm_role"] == "title/summary/dominant_activities only",
        "timeline_is_continuous":
            chapters[0]["start_sec"] == cr.VIDEO_START_SEC
            and chapters[-1]["end_sec"] == cr.VIDEO_END_SEC
            and all(left["end_sec"] == right["start_sec"]
                    for left, right in zip(chapters, chapters[1:])),
        "chapter_count_in_bounds":
            cr.MIN_CHAPTERS <= len(chapters) <= cr.MAX_CHAPTERS,
        "evidence_class_assigned_by_executor": all(
            row["assigned_by"] == "executor" for row in classes)
            and record["llm_may_set_evidence_class"] is False
            and chapters_doc["provenance"]["evidence_class_assigned_by"]
            == "executor",
        "evidence_class_rules_hold":
            chapters_doc["evidence_audit"]["violations"] == []
            and cr.evidence_audit(chapters, supports, classes)["violations"]
            == [],
        "conflict_chapters_are_mixed_evidence": all(
            row["evidence_class"] == cr.MIXED_EVIDENCE
            for support, row in zip(supports, classes)
            if support["conflict_blocks"]),
        "single_source_chapters_are_not_stable": all(
            row["evidence_class"] != cr.STABLE_DOMINANT
            for support, row in zip(supports, classes)
            if support["single_source_seconds"]
            >= support["multi_window_seconds"]),
        "conflict_disclosure_present": all(
            row["conflict_disclosed"] for row in disclosures
            if row["disclosure_required"]),
        "unresolved_gap_preserved":
            chapters_doc["unresolved_audit"]["violations"] == []
            and chapters_doc["unresolved_audit"]["unresolved_intervals"]
            == [[0.0, 24.0]],
        "lineage_event_ids_exist": all(
            event_id in known_events for support in supports
            for event_id in support["source_event_ids"]),
        "grid_audit_recorded_not_used":
            chapters_doc["grid_audit"]["grid_used_for_selection"] is False
            and chapters_doc["grid_audit"]["jitter_applied"] is False,
        "no_forbidden_field_names": all(
            '"%s"' % word not in doc_text
            for word in cr.FORBIDDEN_FIELD_NAMES),
        "no_report_stage_output": not any(
            (runs / name).exists() for name in
            ("chapter_repair_v1_overview.md", "chapter_repair_v1_analysis.md",
             "chapter_repair_v1_conclusion.md",
             "chapter_repair_v1_report.hwpx")),
        "executor_filled_no_verdict":
            chapters_doc["executor_state"]["verdict"] is None
            and chapters_doc["executor_state"]["state"] == cr.EXECUTOR_STATE
            and summary["reviewer_final_verdict"] is None,
        "packet_asks_six_questions_and_answers_none": all(
            question in packet for question in
            ("Q1 STRUCTURE", "Q2 BOUNDARY_SEMANTICS",
             "Q3 GEOMETRY_INDEPENDENCE", "Q4 CONFLICT_SAFETY",
             "Q5 EVIDENCE_CALIBRATION", "Q6 OVERVIEW_READY"))
        and packet.count(cr.NOT_ADJUDICATED) >= 6,
        "deterministic_rebuild":
            cr.canonical(rebuilt["chapters_doc"]["chapters"])
            == cr.canonical(chapters)
            and rebuilt["packet"] == packet,
    }


def checks(runs: Path) -> dict:
    rows = {"stage_a." + name: value
            for name, value in stage_a_checks(runs).items()}
    if (runs / builder.CHAPTERS_NAME).is_file():
        rows.update({"stage_b." + name: value
                     for name, value in stage_b_checks(runs).items()})
    else:
        candidates = _load(runs, stagea.CANDIDATES_NAME)
        rows["stage_b.not_executed_because_blocker"] = bool(
            candidates["blocker"]) and candidates["stage_b_executed"] is False
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="repair validator")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    rows = checks(runs)
    ok = all(rows.values())
    if args.json:
        print(json.dumps({"validator": "PASS" if ok else "FAIL",
                          "checks": rows}, ensure_ascii=False, indent=1))
    else:
        print("validator=%s checks=%d/%d"
              % ("PASS" if ok else "FAIL",
                 sum(1 for value in rows.values() if value), len(rows)))
        for name, value in rows.items():
            print("  check %-56s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
