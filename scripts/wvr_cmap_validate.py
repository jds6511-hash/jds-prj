"""CONSERVATIVE_EVENT_MAP_SHADOW_V1 validator (2026-09-10).

사전등록:
`docs/preregistration/WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1_2026-09-10.md`

산출물이 사전등록 계약을 지켰는지 **파일에서 다시 계산해서** 확인한다.
최종 PASS/HOLD는 리뷰어가 낸다 — 이 도구는 그것을 계산하지 않는다.

사용: `python scripts/wvr_cmap_validate.py --runs runs/wvr_light_v1`
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_cmap_build as builder                             # noqa: E402
import wvr_conservative_map_v1 as cm                         # noqa: E402
import wvr_shadow_v1 as sh                                   # noqa: E402
import wvr_stitch_v1 as st                                   # noqa: E402


def _load(runs: Path, name: str) -> dict:
    return json.loads((runs / name).read_text(encoding="utf-8"))


def _strip_head(payload: dict) -> dict:
    copy = json.loads(json.dumps(payload))
    copy.get("provenance", {}).pop("code_git_head", None)
    copy.get("provenance", {}).pop("prereg_commit", None)
    return copy


def checks(runs: Path) -> dict:
    document = _load(runs, builder.MAP_NAME)
    summary = _load(runs, builder.SUMMARY_NAME)
    verdicts = _load(runs, builder.VERDICTS_NAME)
    map_md = (runs / builder.MAP_MD_NAME).read_text(encoding="utf-8")
    packet = (runs / builder.PACKET_NAME).read_text(encoding="utf-8")

    rebuilt = builder.build(runs)
    rebuilt_again = builder.build(runs)
    derived = [(row["region_id"], row["start_sec"], row["end_sec"],
                row["node_class"], tuple(row["overlap_ids"]))
               for row in cm.regions(verdicts)]
    members = cm.all_members(document)
    blocks = document["nodes"]["conflict_blocks"]
    groups = document["nodes"]["stitch_groups"]
    verdict_index = cm.verdict_index(verdicts)
    conflict_overlaps = sorted(key for key, row in verdict_index.items()
                               if row["top_verdict"] == st.MATERIAL_CONFLICT)
    stitchable_overlaps = sorted(key for key, row in verdict_index.items()
                                 if row["top_verdict"] == st.STITCHABLE)
    document_text = json.dumps(document, ensure_ascii=False).lower()

    return {
        "schema_and_event_frozen": document["schema"] == cm.SCHEMA
        and document["event"] == cm.EVENT
        and document["artifact_name"] == cm.ARTIFACT_NAME,
        "source_hashes_frozen": all(
            document["provenance"]["source_hashes"][name]
            == cm.FROZEN_HASHES[name] for name in builder.REQUIRED_SOURCES),
        "regions_match_frozen_schedule":
            derived == [tuple(row) for row in cm.EXPECTED_REGION_SCHEDULE],
        "regions_tile_the_video": (
            document["regions"][0]["start_sec"] == cm.VIDEO_START_SEC
            and document["regions"][-1]["end_sec"] == cm.VIDEO_END_SEC
            and all(left["end_sec"] == right["start_sec"]
                    for left, right in zip(document["regions"],
                                           document["regions"][1:]))),
        "every_overlap_hangs_on_a_node": (
            sorted([row["overlap_id"] for row in blocks]
                   + [row["overlap_id"] for row in groups])
            == sorted(row["overlap_id"] for row in st.overlaps())),
        "conflict_overlaps_are_conflict_blocks":
            sorted(row["overlap_id"] for row in blocks) == conflict_overlaps
            and len(blocks) == 10,
        "stitchable_overlaps_are_stitch_groups":
            sorted(row["overlap_id"] for row in groups) == stitchable_overlaps
            and len(groups) == 12,
        "stitch_group_types_follow_reviewer_relations": all(
            row["node_type"]
            == cm.RELATION_TO_NODE_TYPE[verdict_index[row["overlap_id"]]
                                        ["relation"]] for row in groups),
        "conflict_keeps_two_observation_sets": all(
            row["observation_set_1"]["source"]
            != row["observation_set_2"]["source"]
            and row["observation_set_1"]["events"]
            and row["observation_set_2"]["events"] for row in blocks),
        "no_conflict_is_resolved":
            cm.false_resolutions(document) == []
            and document["summary_counts"]["false_resolution_count"] == 0,
        "no_preferred_source": all(row["preferred_source"] is None
                                   for row in blocks),
        "resolution_is_none": all(row["resolution"] == "NONE"
                                  for row in blocks),
        "no_forbidden_field_names": all(
            '"%s"' % word not in document_text
            for word in cm.FORBIDDEN_FIELD_NAMES),
        "all_source_events_are_represented":
            document["lineage_summary"]["events_missing"] == 0
            and document["lineage_summary"]["source_events_total"]
            == cm.EXPECTED_SOURCE_EVENT_COUNT
            and len({row["event_id"] for row in members})
            == cm.EXPECTED_SOURCE_EVENT_COUNT,
        "every_event_has_one_primary_region": all(
            row["primary_region"] and row["lineage_type"] in cm.LINEAGE_TYPES
            and row["node_memberships"] for row in document["lineage"]),
        "no_invalid_source_dependency":
            cm.invalid_source_dependencies(document) == []
            and document["summary_counts"]
            ["invalid_source_dependency_count"] == 0,
        "unresolved_gap_is_preserved": (
            [(row["start_sec"], row["end_sec"])
             for row in document["nodes"]["unresolved_gaps"]] == [(0.0, 24.0)]
            and all(not row["events"] and row["filled"] is False
                    for row in document["nodes"]["unresolved_gaps"])),
        "no_event_lands_in_the_unresolved_gap": all(
            row["clipped_start"] >= 24.0 for row in members),
        "conflict_regions_group_adjacent_blocks": (
            len(document["nodes"]["conflict_regions"]) == 4
            and all(set(row["member_blocks"])
                    <= {node["node_id"] for node in blocks}
                    for row in document["nodes"]["conflict_regions"])),
        "durations_add_up": (
            document["coverage"]["conflict_duration_sec"]
            + document["coverage"]["stitchable_duration_sec"]
            + document["coverage"]["single_source_duration_sec"]
            + document["coverage"]["unresolved_duration_sec"]
            == cm.VIDEO_END_SEC - cm.VIDEO_START_SEC),
        "no_semantic_truth_percentage":
            document["coverage"]["semantic_truth_percentage"] is None
            and summary["semantic_truth_percentage"] is None,
        "frame_stamps_are_traceability_only": all(
            len(row["frame_stamps"]) == sh.SHARED_FRAMES_PER_OVERLAP
            and all(row["start_sec"] <= stamp < row["end_sec"]
                    for stamp in row["frame_stamps"])
            for row in blocks + groups),
        "no_new_inference": document["provenance"]["new_inference_count"] == 0
        and document["provenance"]["new_llm_call_count"] == 0
        and document["provenance"]["gpu_used"] is False,
        "no_group_description_generated": all(
            row["description_generated"] is False and "description" not in row
            for row in groups),
        "flags_closed": all(value is False for value
                            in document["policy"]["flags"].values()),
        "executor_filled_no_verdict":
            document["executor_state"]["verdict"] is None
            and document["executor_state"]["state"] == cm.EXECUTOR_STATE
            and summary["reviewer_final_verdict"] is None,
        "packet_asks_four_questions_and_answers_none": all(
            question in packet for question in
            ("Q1 STRUCTURAL_USABILITY", "Q2 CONFLICT_LOCALIZATION",
             "Q3 NO_FALSE_RESOLUTION", "Q4 CHAPTER_INPUT_USABILITY"))
        and packet.count(cm.NOT_ADJUDICATED) >= 4,
        "map_markdown_covers_every_region": all(
            "## %s " % row["region_id"] in map_md
            for row in document["regions"]),
        "summary_matches_the_document": (
            summary["events_missing"]
            == document["lineage_summary"]["events_missing"]
            and summary["conflict_block_count"]
            == document["summary_counts"]["conflict_block_count"]
            and summary["region_count"] == len(document["regions"])),
        "deterministic_rebuild": (
            cm.canonical(_strip_head(rebuilt["document"]))
            == cm.canonical(_strip_head(rebuilt_again["document"]))
            and cm.canonical(_strip_head(rebuilt["document"]))
            == cm.canonical(_strip_head(document))
            and rebuilt["markdown"] == map_md
            and rebuilt["packet"] == packet),
        "verdicts_untouched":
            builder.sha256_file(runs / builder.VERDICTS_NAME)
            == cm.FROZEN_HASHES[builder.VERDICTS_NAME],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="conservative map validator")
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
            print("  check %-52s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
