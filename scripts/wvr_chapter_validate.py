"""SEMANTIC_CHAPTER_SHADOW_V1 validator (2026-09-10).

사전등록: `docs/preregistration/WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md`

산출물이 계약을 지켰는지 **파일에서 다시 계산해서** 확인한다.
최종 PASS/HOLD는 리뷰어가 낸다 — 이 도구는 그것을 계산하지 않는다.

사용: `python scripts/wvr_chapter_validate.py --runs runs/wvr_light_v1`
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_chapter_build as builder                          # noqa: E402
import wvr_chapter_v1 as ch                                  # noqa: E402
import wvr_conservative_map_v1 as cmap                       # noqa: E402


def _load(runs: Path, name: str) -> dict:
    return json.loads((runs / name).read_text(encoding="utf-8"))


def checks(runs: Path) -> dict:
    document = _load(runs, ch.SOURCE_MAP_NAME)
    chapters_doc = _load(runs, builder.CHAPTERS_NAME)
    summary = _load(runs, builder.SUMMARY_NAME)
    record = _load(runs, builder.RECORD_NAME)
    raw = (runs / builder.RAW_NAME).read_text(encoding="utf-8")
    prompt = (runs / builder.PROMPT_NAME).read_text(encoding="utf-8")
    packet = (runs / builder.PACKET_NAME).read_text(encoding="utf-8")

    rebuilt = builder.build(runs)
    chapters = chapters_doc["chapters"]
    lineage = chapters_doc["lineage"]
    boundaries = chapters_doc["boundary_evidence"]
    known_events = {row["event_id"] for row in document["lineage"]}
    blocks = {row["node_id"]: row
              for row in document["nodes"]["conflict_blocks"]}
    doc_text = json.dumps(chapters_doc, ensure_ascii=False).lower()

    return {
        "schema_and_event_frozen": chapters_doc["schema"] == ch.SCHEMA
        and chapters_doc["event"] == ch.EVENT
        and chapters_doc["artifact_name"] == ch.ARTIFACT_NAME,
        "source_map_hash_frozen":
            chapters_doc["provenance"]["source_map_sha256"]
            == ch.SOURCE_MAP_SHA256
            and record["source_map_sha256"] == ch.SOURCE_MAP_SHA256,
        "prompt_hash_frozen":
            ch.sha256_text(prompt) == ch.RENDERED_PROMPT_SHA256
            and record["prompt_sha256"] == ch.RENDERED_PROMPT_SHA256
            and ch.sha256_text(ch.CHAPTER_PROMPT_V1)
            == ch.PROMPT_TEMPLATE_SHA256,
        "raw_persisted_before_parse":
            record["raw_persisted_before_parse"] is True
            and record["parsed_here"] is False
            and ch.sha256_text(raw) == record["raw_sha256"],
        "single_generation_attempt":
            record["generation_attempts"] == ch.GENERATION_ATTEMPTS
            and record["retry_allowed"] is False,
        "runtime_matches_freeze":
            record["requested_runtime"]["model_id"] == ch.LLM_MODEL_ID
            and record["requested_runtime"]["load_4bit"] is False
            and record["requested_runtime"]["max_new_tokens"]
            == ch.LLM_MAX_NEW_TOKENS
            and record["effective_runtime"]["do_sample"] is False
            and record["effective_runtime"]["quantization_mismatch"] is False,
        "no_new_vlm_inference":
            record["new_vlm_inference_count"] == 0
            and record["track_a_input_used"] is False
            and chapters_doc["provenance"]["new_vlm_inference_count"] == 0,
        "chapter_count_in_bounds":
            ch.MIN_CHAPTERS <= len(chapters) <= ch.MAX_CHAPTERS,
        "chapter_ids_deterministic":
            [row["chapter_id"] for row in chapters]
            == ["CH%02d" % index for index in range(1, len(chapters) + 1)],
        "timeline_is_continuous_and_monotonic": (
            chapters[0]["start_sec"] == ch.VIDEO_START_SEC
            and chapters[-1]["end_sec"] == ch.VIDEO_END_SEC
            and all(row["end_sec"] > row["start_sec"] for row in chapters)
            and all(left["end_sec"] == right["start_sec"]
                    for left, right in zip(chapters, chapters[1:]))),
        "vocabulary_frozen": all(
            row["confidence_class"] in ch.CONFIDENCE_CLASSES
            and row["boundary_reason"]
            and all(reason in ch.BOUNDARY_REASONS
                    for reason in row["boundary_reason"])
            for row in chapters),
        "no_numeric_confidence": all(
            not isinstance(row.get("confidence"), (int, float))
            and "confidence_value" not in row for row in chapters),
        "boundaries_not_all_on_the_24s_grid":
            chapters_doc["grid_alignment"]["all_internal_boundaries_on_grid"]
            is False,
        "every_chapter_has_source_lineage": all(
            rows["source_regions"] and rows["source_nodes"]
            and rows["source_event_count"] > 0 for rows in lineage),
        "declared_event_ids_exist": all(
            event_id in known_events
            for rows in lineage
            for event_id in rows["stable_source_events"]
            + rows["conflict_source_events"])
        and all(event_id in known_events for event_id
                in chapters_doc["provenance"]["declared_event_ids_in_output"]),
        "conflict_sources_preserved": all(
            {blocks[node_id]["observation_set_1"]["source"],
             blocks[node_id]["observation_set_2"]["source"]}
            <= set(rows["conflict_sources_preserved"])
            for rows in lineage for node_id in rows["conflict_blocks"]),
        "no_conflict_resolution":
            chapters_doc["conflict_safety"]["violations"] == []
            and ch.conflict_safety(chapters, lineage, document)["violations"]
            == [],
        "all_conflict_blocks_are_covered":
            sorted(chapters_doc["conflict_safety"]["conflict_blocks_covered"])
            == sorted(blocks),
        "unresolved_gap_not_filled":
            chapters_doc["unresolved_safety"]["violations"] == []
            and chapters_doc["unresolved_safety"]["unresolved_intervals"]
            == [[0.0, 24.0]]
            and any(rows["unresolved_intervals"] for rows in lineage),
        "unresolved_chapter_has_real_events": all(
            rows["stable_source_events"] or rows["conflict_source_events"]
            for rows in lineage if rows["unresolved_intervals"]),
        "boundary_evidence_is_complete": (
            len(boundaries) == len(chapters)
            and all(row["boundary_sec"] == chapter["start_sec"]
                    and row["boundary_reason"] == chapter["boundary_reason"]
                    and (row["after_activity_evidence"]
                         or row["boundary_sec"] >= ch.VIDEO_END_SEC)
                    for row, chapter in zip(boundaries, chapters))
            and all(row["before_activity_evidence"]
                    for row in boundaries[1:])),
        "boundary_event_ids_exist": all(
            event_id in known_events for row in boundaries
            for event_id in row["before_source_event_ids"]
            + row["after_source_event_ids"]),
        "no_forbidden_field_names": all(
            '"%s"' % word not in doc_text
            for word in ch.FORBIDDEN_FIELD_NAMES),
        "no_report_stage_output": not any(
            (runs / name).exists() for name in
            ("chapter_v1_overview.md", "chapter_v1_analysis.md",
             "chapter_v1_conclusion.md", "chapter_v1_report.hwpx")),
        "flags_closed": all(value is False for value
                            in chapters_doc["policy"]["flags"].values()),
        "executor_filled_no_verdict":
            chapters_doc["executor_state"]["verdict"] is None
            and chapters_doc["executor_state"]["state"] == ch.EXECUTOR_STATE
            and summary["reviewer_final_verdict"] is None,
        "packet_asks_four_questions_and_answers_none": all(
            question in packet for question in
            ("Q1 WHOLE_VIDEO_STRUCTURE", "Q2 BOUNDARY_QUALITY",
             "Q3 CONFLICT_SAFETY", "Q4 OVERVIEW_INPUT_USABILITY"))
        and packet.count(ch.NOT_ADJUDICATED) >= 4,
        "packet_shows_every_chapter": all(
            "## %s " % row["chapter_id"] in packet for row in chapters),
        "summary_matches_the_document":
            summary["chapter_count"] == len(chapters)
            and summary["chapter_titles"] == [row["title"]
                                              for row in chapters]
            and summary["conflict_block_total"] == len(blocks),
        "map_untouched_by_this_event":
            document["schema"] == cmap.SCHEMA
            and builder.selfcheck.sha256_file(runs / ch.SOURCE_MAP_NAME)
            == ch.SOURCE_MAP_SHA256,
        "deterministic_rebuild":
            ch.canonical(rebuilt["chapters_doc"]["chapters"])
            == ch.canonical(chapters)
            and ch.canonical(rebuilt["chapters_doc"]["lineage"])
            == ch.canonical(lineage)
            and rebuilt["packet"] == packet,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="chapter validator")
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
            print("  check %-46s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
