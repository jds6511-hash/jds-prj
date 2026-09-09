"""RECURSIVE_SUBDIVISION_RECOVERY_V1 validator — GPU 사용 전 계약 확인.

사전등록:
`docs/preregistration/WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1_2026-09-09.md`

추론하지 않는다. 세 child의 일정·격자·coverage·겹침·동결 설정·선행 산출물(C0·C1·C2·
W00) 무변경·계보 대조표를 확인하고 실행 계획을 인쇄한다. 실패하면 0이 아닌 코드로 끝난다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_recur_run as runner                              # noqa: E402
import wvr_recursive_v1 as rc                               # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="recursive validator")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    coverage = rc.assert_coverage()
    report = {"event": rc.EVENT, "prereg": runner.PREREG,
              "parent_child": rc.parent_child(),
              "grandparent_window": rc.grandparent_window(),
              "subdivision_depth": rc.SUBDIVISION_DEPTH,
              "coverage": coverage,
              "architecture_change": rc.ARCHITECTURE_CHANGE,
              "stop_rule": rc.STOP_RULE,
              "children": [], "overlaps": [], "checks": {}}

    for child_id in rc.CHILD_IDS:
        plan = runner.preflight(child_id, runs)
        report["children"].append({
            "child_id": child_id, "start_sec": plan["child"]["start_sec"],
            "end_sec": plan["child"]["end_sec"],
            "frame_times": plan["stamps"],
            "frame_count": len(plan["stamps"]),
            "inference_config_change":
                plan["change"]["inference_config_change"],
            "geometry_as_declared": plan["change"]["geometry_as_declared"],
            "max_new_tokens": plan["max_new_tokens"],
            "prompt_hash": plan["requested"]["prompt_hash"],
            "model_revision": plan["requested"]["model_revision"],
            "lineage_sources": plan["reference"]["sources"],
            "reference_missing_times": plan["reference_missing_times"],
            "frozen_artifacts_unchanged":
                plan["frozen_artifacts"]["unchanged"],
        })

    for overlap in rc.overlaps():
        report["overlaps"].append({**overlap,
                                   "shared_times":
                                       list(rc.shared_times(overlap))})

    report["checks"] = {
        "child_count": len(report["children"]) == rc.EXPECTED_CHILD_COUNT,
        "coverage_no_gap": coverage["covered"],
        "frames_per_child": all(row["frame_count"] == rc.FRAMES_PER_CHILD
                                for row in report["children"]),
        "config_change_none": all(row["inference_config_change"] == "NONE"
                                  for row in report["children"]),
        "geometry_as_declared": all(row["geometry_as_declared"]
                                    for row in report["children"]),
        "shared_frames": all(len(row["shared_times"])
                             == rc.SHARED_FRAMES_PER_OVERLAP
                             for row in report["overlaps"]),
        "frozen_artifacts_unchanged": all(row["frozen_artifacts_unchanged"]
                                          for row in report["children"]),
        "lineage_reference_complete": all(not row["reference_missing_times"]
                                          for row in report["children"]),
        "deeper_subdivision_blocked": rc.DEEPER_SUBDIVISION_ALLOWED is False,
        "c1_c2_rerun_blocked": rc.C1_C2_RERUN_ALLOWED is False,
    }
    ok = all(report["checks"].values())
    report["validator"] = "PASS" if ok else "FAIL"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("validator=%s" % report["validator"])
        for row in report["children"]:
            print("  %s %5.1f-%5.1f frames=%d change=%s geom=%s "
                  "lineage_missing=%d frozen_ok=%s"
                  % (row["child_id"], row["start_sec"], row["end_sec"],
                     row["frame_count"], row["inference_config_change"],
                     row["geometry_as_declared"],
                     len(row["reference_missing_times"]),
                     row["frozen_artifacts_unchanged"]))
        for row in report["overlaps"]:
            print("  %s %5.1f-%5.1f shared=%d  %s"
                  % (row["overlap_id"], row["start_sec"], row["end_sec"],
                     len(row["shared_times"]),
                     ", ".join("%.0f" % time for time in row["shared_times"])))
        for name, value in report["checks"].items():
            print("  check %-30s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
