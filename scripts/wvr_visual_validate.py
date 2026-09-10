"""VISUAL_CONTENT_ISOLATION_V1 validator — GPU 사용 전 계약 확인 (2026-09-10).

추론하지 않는다. arm E 설계(W05 픽셀 시각 · Trigger A 시간 인코딩) · 동결 설정 ·
기존 세 칸 해시 무변경 · 산출물 중복을 확인하고 실행 계획을 인쇄한다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_trigger_v1 as tg                                 # noqa: E402
import wvr_visual_run as runner                             # noqa: E402
import wvr_visual_v1 as vc                                  # noqa: E402

RATE_FOR_PLAN = 30.0        # 계획 인쇄용 가정 rate — 실행 시에는 실측 rate를 쓴다


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="visual isolation validator")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    plan = runner.preflight(runs, rate=RATE_FOR_PLAN)
    arm = plan["plan"]
    times = plan["time_reference"]

    report = {
        "event": vc.EVENT, "prereg": runner.PREREG,
        "event_kind": vc.EVENT_KIND,
        "new_inference_count": vc.EXPECTED_ARM_COUNT,
        "arm": {
            "arm_id": vc.ARM_ID, "cell": arm["cell"],
            "pixel_source_window": arm["pixel_source_window"],
            "pixel_times_first_last": [arm["pixel_times"][0],
                                       arm["pixel_times"][-1]],
            "pixel_frame_count": len(arm["pixel_times"]),
            "time_encoding": arm["time_encoding"],
            "prompt_window": arm["prompt_window"],
            "rendered_prompt_hash": arm["rendered_prompt_hash"],
            "prompt_template_hash": arm["prompt_template_hash"],
            "frames_indices_first_last": [arm["frames_indices"][0],
                                          arm["frames_indices"][-1]],
        },
        "frozen_cells": plan["frozen_cells"],
        "reference_pixel_hash_count": len(plan["pixel_reference"]),
        "time_reference": {
            "rendered_prompt_hash": times.get("rendered_prompt_hash"),
            "prompt_window": times.get("prompt_window"),
            "frames_indices_first_last": (
                [times["metadata"]["frames_indices"][0],
                 times["metadata"]["frames_indices"][-1]]
                if times.get("metadata", {}).get("frames_indices") else None),
        },
        "max_new_tokens": plan["max_new_tokens"],
        "inference_config_change": plan["change"]["inference_config_change"],
        "checks": {},
    }

    report["checks"] = {
        "one_new_inference": vc.EXPECTED_ARM_COUNT == 1,
        "pixels_are_w05_grid": report["arm"]["pixel_times_first_last"]
        == [120.0, 166.0],
        "pixel_frame_count_24": report["arm"]["pixel_frame_count"] == 24,
        "prompt_window_is_T0": report["arm"]["prompt_window"] == [0.0, 48.0],
        "rendered_prompt_matches_trigger_A":
            report["arm"]["rendered_prompt_hash"]
            == report["time_reference"]["rendered_prompt_hash"],
        "indices_match_trigger_A":
            report["arm"]["frames_indices_first_last"]
            == report["time_reference"]["frames_indices_first_last"],
        "prompt_template_frozen": report["arm"]["prompt_template_hash"]
        == tg.prompt_template_hash(),
        "config_change_none": report["inference_config_change"] == "NONE",
        "token_cap_frozen": report["max_new_tokens"] == 4096,
        "frozen_cells_unchanged": plan["frozen_cells"]["unchanged"],
        "reference_pixels_present": report["reference_pixel_hash_count"] == 24,
        "rerun_of_frozen_cells_blocked":
            vc.RERUN_OF_FROZEN_CELLS_ALLOWED is False,
        "prompt_mutation_blocked": vc.PROMPT_TEXT_MUTATION_ALLOWED is False,
        "zero_duration_example_frozen":
            vc.ZERO_DURATION_EXAMPLE_MUTATION_ALLOWED is False,
        "subdivision_restart_blocked":
            vc.SUBDIVISION_RESTART_ALLOWED is False,
    }
    ok = all(report["checks"].values())
    report["validator"] = "PASS" if ok else "FAIL"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("validator=%s" % report["validator"])
        row = report["arm"]
        print("  E %s pixels=%s..%s window=%s indices=%s"
              % (row["cell"], row["pixel_times_first_last"][0],
                 row["pixel_times_first_last"][1], row["prompt_window"],
                 row["frames_indices_first_last"]))
        for cell in vc.FROZEN_CELLS:
            print("  frozen %s %-16s %-14s %s"
                  % (cell["cell"], cell["pixels"], cell["time"],
                     cell["status"]))
        for name, value in report["checks"].items():
            print("  check %-36s %s" % (name, value))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
