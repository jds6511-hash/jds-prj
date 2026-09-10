"""TRIGGER_ISOLATION_V1 validator — GPU 사용 전 계약 확인 (2026-09-10).

추론하지 않는다. 4 arm의 조작 설계(픽셀 시각 고정 · prompt 창 값 · frames_indices) ·
동결 설정 · 선행 산출물 무변경 · 산출물 중복을 확인하고 실행 계획을 인쇄한다.
분리 가능성(hard blocker) 실측은 `wvr_trigger_selfcheck.py`가 따로 한다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_trigger_run as runner                            # noqa: E402
import wvr_trigger_v1 as tg                                 # noqa: E402

RATE_FOR_PLAN = 30.0        # 계획 인쇄용 가정 rate — 실행 시에는 실측 rate를 쓴다


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="trigger validator")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    report = {"event": tg.EVENT, "prereg": runner.PREREG,
              "event_kind": tg.EVENT_KIND,
              "source_window": tg.source_window(),
              "shift_sec": tg.SHIFT_SEC,
              "pixel_times": list(tg.pixel_times()),
              "plan_rate_assumed": RATE_FOR_PLAN,
              "arms": [], "checks": {}}

    for arm_id in tg.ARM_IDS:
        plan = runner.preflight(arm_id, runs, rate=RATE_FOR_PLAN)
        arm = plan["plan"]
        report["arms"].append({
            "arm_id": arm_id, "prompt_mode": arm["prompt_mode"],
            "metadata_mode": arm["metadata_mode"],
            "prompt_window": arm["prompt_window"],
            "rendered_prompt_hash": arm["rendered_prompt_hash"],
            "prompt_template_hash": arm["prompt_template_hash"],
            "metadata_times_first_last": [arm["metadata_times"][0],
                                          arm["metadata_times"][-1]],
            "frames_indices_first_last": [arm["frames_indices"][0],
                                          arm["frames_indices"][-1]],
            "pixel_times_first_last": [arm["pixel_times"][0],
                                       arm["pixel_times"][-1]],
            "frozen_artifacts_unchanged":
                plan["frozen_artifacts"]["unchanged"],
            "reference_pixel_hash_count": len(plan["reference_pixel_hashes"]),
            "inference_config_change":
                plan["change"]["inference_config_change"],
            "max_new_tokens": plan["max_new_tokens"],
        })

    by_id = {row["arm_id"]: row for row in report["arms"]}
    report["checks"] = {
        "arm_count": len(report["arms"]) == tg.EXPECTED_ARM_COUNT,
        "pixel_times_identical": all(
            row["pixel_times_first_last"] == [0.0, 46.0]
            for row in report["arms"]),
        "shift_is_120": tg.SHIFT_SEC == 120.0,
        "prompt_A_equals_B": by_id["A"]["rendered_prompt_hash"]
        == by_id["B"]["rendered_prompt_hash"],
        "prompt_C_equals_D": by_id["C"]["rendered_prompt_hash"]
        == by_id["D"]["rendered_prompt_hash"],
        "prompt_A_differs_C": by_id["A"]["rendered_prompt_hash"]
        != by_id["C"]["rendered_prompt_hash"],
        "prompt_template_single": len({row["prompt_template_hash"]
                                       for row in report["arms"]}) == 1,
        "indices_A_equal_C": by_id["A"]["frames_indices_first_last"]
        == by_id["C"]["frames_indices_first_last"],
        "indices_B_equal_D": by_id["B"]["frames_indices_first_last"]
        == by_id["D"]["frames_indices_first_last"],
        "indices_A_differ_B": by_id["A"]["frames_indices_first_last"]
        != by_id["B"]["frames_indices_first_last"],
        "config_change_none": all(row["inference_config_change"] == "NONE"
                                  for row in report["arms"]),
        "token_cap_frozen": all(row["max_new_tokens"] == 4096
                                for row in report["arms"]),
        "frozen_artifacts_unchanged": all(row["frozen_artifacts_unchanged"]
                                          for row in report["arms"]),
        "reference_pixels_present": all(row["reference_pixel_hash_count"]
                                        == tg.PIXEL_FRAME_COUNT
                                        for row in report["arms"]),
        "prompt_mutation_blocked": tg.PROMPT_TEXT_MUTATION_ALLOWED is False,
        "recovery_blocked": tg.RECOVERY_ATTEMPT_ALLOWED is False,
    }
    ok = all(report["checks"].values())
    report["validator"] = "PASS" if ok else "FAIL"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("validator=%s" % report["validator"])
        for row in report["arms"]:
            print("  %s %s/%s window=%s meta_times=%s indices=%s"
                  % (row["arm_id"], row["prompt_mode"], row["metadata_mode"],
                     row["prompt_window"], row["metadata_times_first_last"],
                     row["frames_indices_first_last"]))
        for name, value in report["checks"].items():
            print("  check %-30s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
