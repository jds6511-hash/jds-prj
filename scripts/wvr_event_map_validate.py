"""EVENT_MAP_COVERAGE_SHADOW_V1 validator (2026-09-10).

추론하지 않는다. 생성된 산출물이 사전등록 invariant를 지키는지 결정적으로 확인한다.

```
source manifest 무변경 · W00이 event source에서 제외 · synthetic event 0건 ·
event 수 = group member 수 · 시간 순서 보존 · coverage union 산술 일치 ·
unresolved 구간 보존 · chapter boundary가 24/48초 격자에 종속되지 않음 ·
같은 입력 → 같은 출력(2회 생성 결과 동일)
```
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_event_map_build as builder                      # noqa: E402
import wvr_event_map_v1 as em                              # noqa: E402

WINDOW_GRID_SEC = 24.0


def _load(runs: Path, name: str) -> dict:
    path = runs / name
    if not path.is_file():
        raise builder.BuildError("산출물이 없다: %s" % name)
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="event map validator")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    registry = _load(runs, builder.REGISTRY_NAME)
    coverage = _load(runs, builder.COVERAGE_NAME)
    candidate = _load(runs, builder.CANDIDATE_NAME)
    chapters = _load(runs, builder.CHAPTER_NAME)
    summary = _load(runs, builder.SUMMARY_NAME)

    # 같은 입력으로 다시 계산해 결정성을 확인한다 (추론 없음)
    rebuilt = builder.build(runs)
    rebuilt_again = builder.build(runs)

    events = registry["events"]
    groups = candidate["groups"]
    members = [event_id for group in groups for event_id in group["members"]]
    boundaries = [row["start_sec"] for row in chapters["chapters"][1:]]
    event_union = em.union_length([(row["start_sec"], row["end_sec"])
                                   for row in events])
    unresolved = em.complement_intervals(
        [(row["start_sec"], row["end_sec"]) for row in events])

    checks = {
        "source_manifest_unchanged":
            registry["source_manifest"]["unchanged"] is True,
        "valid_source_count":
            len(registry["events_per_window"]) == 23,
        "w00_not_an_event_source": all(
            row["source_window"] in em.VALID_SOURCE_WINDOWS
            for row in events),
        "w00_still_invalid": all(
            row["status"] == "WINDOW_INVALID"
            for row in registry["invalid_sources"].values()),
        "no_synthetic_event": len(events) == sum(
            registry["events_per_window"].values()),
        "event_ids_unique": len({row["event_id"] for row in events})
        == len(events),
        "event_ids_deterministic": all(
            row["event_id"] == em.event_id(row["source_window"],
                                           row["collapsed_index"])
            for row in events),
        "group_membership_complete": sorted(members) == sorted(
            row["event_id"] for row in events),
        "group_membership_disjoint": len(members) == len(set(members)),
        "groups_time_ordered": all(
            groups[index]["start_sec"] <= groups[index + 1]["start_sec"]
            for index in range(len(groups) - 1)),
        "events_time_ordered_within_window": all(
            events[index]["start_sec"] <= events[index + 1]["start_sec"]
            for index in range(len(events) - 1)
            if events[index]["source_window"]
            == events[index + 1]["source_window"]),
        "no_mixed_signature_group": all(
            group["mixed_signature"] is False for group in groups),
        "coverage_union_matches": coverage["event_coverage_sec"]
        == event_union,
        "unresolved_matches_complement":
            coverage["unresolved_intervals"] == unresolved,
        "unresolved_preserved": coverage["unresolved_sec"] > 0.0,
        "coverage_sums_to_video": abs(
            sum(coverage["status_seconds"].values()) - em.VIDEO_SEC) < 1e-6,
        "chapters_cover_groups": sum(
            row["group_count"] for row in chapters["chapters"])
        == len(groups),
        "chapter_boundaries_not_all_on_window_grid": bool(boundaries)
        and not all(abs(value % WINDOW_GRID_SEC) < 1e-6
                    for value in boundaries),
        "chapter_boundaries_from_group_starts": all(
            any(abs(group["start_sec"] - value) < 1e-6 for group in groups)
            for value in boundaries),
        "min_chapter_sec_respected": all(
            boundaries[index] - (chapters["chapters"][index]["start_sec"])
            >= em.MIN_CHAPTER_SEC - 1e-6
            for index in range(len(boundaries))),
        "relation_vocabulary_frozen": set(
            candidate["relation_counts"]) == set(em.RELATIONS),
        "relations_only_between_adjacent_windows": all(
            any(pair["earlier"] == row["earlier_window"]
                and pair["later"] == row["later_window"]
                for pair in candidate["adjacent_window_pairs"])
            for row in candidate["relations"]),
        "no_new_inference": registry["new_inference_count"] == 0
        and summary["executor_state"]["new_inference_count"] == 0,
        "executor_state_review_pending":
            summary["executor_state"]["state"] == em.EXECUTOR_STATE,
        "no_semantic_verdict":
            summary["executor_state"]["semantic_verdict"] is None,
        "deterministic_rebuild": (
            json.dumps(rebuilt["registry"]["events"], sort_keys=True)
            == json.dumps(rebuilt_again["registry"]["events"],
                          sort_keys=True)
            and json.dumps(rebuilt["candidate_map"]["groups"],
                           sort_keys=True)
            == json.dumps(rebuilt_again["candidate_map"]["groups"],
                          sort_keys=True)
            and rebuilt["packet"] == rebuilt_again["packet"]),
        "artifact_named_candidate":
            candidate["artifact_name"] == "CANDIDATE_EVENT_MAP",
        "blind_map_not_revealed":
            summary["blind_map_reveal_allowed"] is False,
    }
    ok = all(checks.values())
    report = {"event": em.EVENT, "validator": "PASS" if ok else "FAIL",
              "checks": checks,
              "event_count": len(events), "group_count": len(groups),
              "chapter_count": len(chapters["chapters"]),
              "chapter_boundaries": boundaries,
              "unresolved_intervals": coverage["unresolved_intervals"]}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("validator=%s" % report["validator"])
        print("  events=%s groups=%s chapters=%s boundaries=%s"
              % (report["event_count"], report["group_count"],
                 report["chapter_count"], report["chapter_boundaries"]))
        print("  unresolved=%s" % report["unresolved_intervals"])
        for name, value in checks.items():
            print("  check %-46s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
