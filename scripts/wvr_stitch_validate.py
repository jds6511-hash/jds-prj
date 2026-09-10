"""STITCHING_SHADOW_V1 validator (2026-09-10).

추론하지 않는다. 생성된 packet·audit·mapping이 사전등록 invariant를 지키는지 확인한다.

```
overlap 22개(O02…O23) · 각 24초 · 공유 프레임 12개 · W00/O01 제외
clip이 원본 구간을 보존 · 비교 단위가 sequence · packet에 창 id 미노출 ·
blinding 상보적·결정적 · audit에 임계 없음 · 판정 미기록(NOT_ADJUDICATED) ·
mapping reveal 거부 · 같은 입력 재계산 결과 동일
```
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_stitch_build as builder                         # noqa: E402
import wvr_stitch_v1 as st                                 # noqa: E402


def _load(runs: Path, name: str) -> dict:
    path = runs / name
    if not path.is_file():
        raise builder.BuildError("산출물이 없다: %s" % name)
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="stitching validator")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--prereg-sha", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    pairs = _load(runs, builder.PAIRS_NAME)
    audit = _load(runs, builder.AUDIT_NAME)
    mapping = _load(runs, builder.MAPPING_NAME)
    summary = _load(runs, builder.SUMMARY_NAME)
    packet = (runs / builder.PACKET_NAME).read_text(encoding="utf-8")
    verdict_path = runs / "stitch_v1_verdicts.json"
    verdicts = (json.loads(verdict_path.read_text(encoding="utf-8"))
                if verdict_path.is_file() else st.parse_verdicts(None))

    rebuilt = builder.build(runs, args.prereg_sha)
    rebuilt_again = builder.build(runs, args.prereg_sha)
    expected_ids = [row["overlap_id"] for row in st.overlaps()]
    all_rows = [row for pair in pairs["pairs"]
                for arm in pair["arms"].values() for row in arm]

    checks = {
        "overlap_count_22": pairs["overlap_count"]
        == st.EXPECTED_OVERLAP_COUNT == 22,
        "overlap_ids_are_o02_to_o23": [row["overlap_id"]
                                       for row in pairs["pairs"]]
        == expected_ids == ["O%02d" % index for index in range(2, 24)],
        "o01_and_w00_excluded": "O01" not in expected_ids
        and all(row["earlier"] != "W00" and row["later"] != "W00"
                for row in st.overlaps()),
        "pairs_carry_no_window_or_event_ids": all(
            set(row) == {"local_id", "original_start", "original_end",
                         "clipped_start", "clipped_end", "clipped", "actor",
                         "action", "object_or_state"}
            for row in all_rows),
        "local_ids_unique": len({row["local_id"] for row in all_rows})
        == len(all_rows),
        "mapping_holds_the_real_ids": all(
            set(mapping["mapping"][overlap_id]["local_id_map"])
            == {row["local_id"] for pair in pairs["pairs"]
                if pair["overlap_id"] == overlap_id
                for arm in pair["arms"].values() for row in arm}
            for overlap_id in expected_ids),
        "each_overlap_is_24_sec": all(
            round(row["end_sec"] - row["start_sec"], 6) == 24.0
            for row in pairs["pairs"]),
        "shared_frames_12": all(row["shared_frame_count"] == 12
                                for row in pairs["pairs"]),
        "arms_are_a_and_b": all(set(row["arms"]) == {"A", "B"}
                                for row in pairs["pairs"]),
        "original_intervals_preserved": all(
            row["original_start"] <= row["clipped_start"]
            and row["original_end"] >= row["clipped_end"]
            for row in all_rows),
        "clipped_inside_overlap": all(
            pair["start_sec"] <= row["clipped_start"]
            and row["clipped_end"] <= pair["end_sec"]
            for pair in pairs["pairs"]
            for arm in pair["arms"].values() for row in arm),
        "comparison_unit_is_sequence": all(
            row["comparison_unit"] == "overlap_local_event_sequence"
            for row in pairs["pairs"]),
        "packet_hides_window_ids": not any(
            ("W%02d" % index) in packet for index in range(24)),
        "packet_lists_both_arms": packet.count("### Arm A") == 22
        and packet.count("### Arm B") == 22,
        "blinding_complementary": all(
            {st.blind_label(overlap_id, "earlier", args.prereg_sha),
             st.blind_label(overlap_id, "later", args.prereg_sha)}
            == {"A", "B"} for overlap_id in expected_ids),
        "blinding_deterministic": all(
            st.blind_label(overlap_id, "earlier", args.prereg_sha)
            == st.blind_label(overlap_id, "earlier", args.prereg_sha)
            for overlap_id in expected_ids),
        "mapping_sealed": summary["mapping_sealed"] is True
        and mapping["reveal_allowed_before_verdicts"] is False,
        "audit_is_blind": all(
            not any(key.startswith(("earlier_", "later_"))
                    for key in row) for row in audit["overlaps"]),
        "audit_has_no_threshold": audit["threshold_used"] is False and all(
            row["threshold_used"] is False for row in audit["overlaps"]),
        "audit_role_diagnostic": audit["role"] == "AUDIT_DIAGNOSTIC_ONLY",
        "no_new_inference": summary["new_inference_count"] == 0
        and summary["new_llm_call_count"] == 0,
        "executor_state_review_pending":
            summary["executor_state"]["state"] == st.EXECUTOR_STATE,
        "executor_filled_no_verdict":
            summary["executor_state"]["verdict"] is None
            and verdicts["adjudicated_count"] == 0
            and all(row["relation"] == "NOT_ADJUDICATED"
                    for row in verdicts["verdicts"]),
        "reveal_refused_now":
            st.reveal_allowed(verdicts)["allowed"] is False,
        "registry_lineage_recorded": bool(summary["registry_sha256"])
        and summary["source_manifest_sha256"]
        == st.VALID_SOURCE_MANIFEST_SHA256,
        "deterministic_rebuild": (
            json.dumps(rebuilt["pairs"], sort_keys=True)
            == json.dumps(rebuilt_again["pairs"], sort_keys=True)
            and rebuilt["packet"] == rebuilt_again["packet"]),
        "event_map_rebuild_blocked":
            summary["executor_state"]["event_map_rebuild_allowed"] is False
            and summary["executor_state"]["adjudicated_map_build_allowed"]
            is False
            and summary["executor_state"]["semantic_chapter_allowed"] is False,
    }
    ok = all(checks.values())
    report = {"event": st.EVENT, "validator": "PASS" if ok else "FAIL",
              "checks": checks, "overlap_count": pairs["overlap_count"],
              "arm_event_total": summary["arm_event_total"]}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("validator=%s overlaps=%s arm_events=%s"
              % (report["validator"], report["overlap_count"],
                 report["arm_event_total"]))
        for name, value in checks.items():
            print("  check %-38s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
