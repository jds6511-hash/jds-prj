"""Stage 2 요약 — arm validity → pair evaluability → 사건 판정 (2026-09-09).

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1B_2026-09-09.md`

```
게이트 순서   arm validity  →  pair evaluability  →  event verdict
비교 내용은   세 pair 전부 EVALUABLE일 때만 낸다
```

한쪽 arm만으로 pair를 만들지 않고, 창 간 arm을 섞지 않는다. GPU를 쓰지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_density as density                               # noqa: E402
import wvr_density_compare as compare                       # noqa: E402
import wvr_density_v1b as events                            # noqa: E402

PAIRS = ("D1", "D2", "D3")
LABEL_OF = {"D1": "D1_highest_change", "D2": "D2_median_change",
            "D3": "D3_lowest_change"}


class SummaryError(RuntimeError):
    """요약 계약 위반."""


def load_arm(runs: Path, tag: str, pair: str, arm: str) -> dict:
    path = runs / ("%s_%s_%s.json" % (tag, pair, arm))
    if not path.is_file():
        raise SummaryError("산출물이 없다: %s" % path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(runs: Path, event: str) -> dict:
    tag = events.tag_for(event)
    stage1 = json.loads((runs / "density_stage1.json").read_text(
        encoding="utf-8"))

    rows, statuses = {}, []
    for pair in PAIRS:
        s0 = load_arm(runs, tag, pair, "S0")
        s1 = load_arm(runs, tag, pair, "S1")
        for record in (s0, s1):
            if record.get("event") != event:
                raise SummaryError("%s 산출물이 아니다" % event)
        evaluability = compare.pair_evaluability(s0, s1)
        statuses.append(evaluability["status"])
        rows[pair] = {
            "window": s0["window"], "stage1_score": s0["window"]["stage1_score"],
            "evaluability": evaluability,
            "arms": {arm: {
                "frames": record["metrics"].get("delivered_frame_count"),
                "input_tokens": record["metrics"].get("input_token_count"),
                "generated_tokens": record["metrics"].get(
                    "generated_token_count"),
                "truncated_at_cap": compare.truncated_at_cap(record),
                "event_count": len((record.get("parsed") or {}).get("events",
                                                                    [])),
                "parse_status": (record.get("parsed") or {}).get("status"),
                "language_contract_failure": compare.arm_validity(record)[
                    "language_contract_failure"],
                "infer_wall_sec": record["metrics"].get("infer_wall_sec"),
                "peak_vram_allocated_mib": record["metrics"].get(
                    "peak_vram_allocated_mib"),
            } for arm, record in (("S0", s0), ("S1", s1))},
        }
        if evaluability["status"] == compare.PAIR_EVALUABLE:
            rows[pair]["comparison"] = compare.compare(s0["parsed"],
                                                       s1["parsed"])

    verdict = compare.event_verdict(statuses)
    return {
        "schema": "wvr_density_stage2_summary_v1", "event": event,
        "prereg": ("docs/preregistration/"
                   "WVR_SAMPLING_SEMANTIC_DENSITY_V1B_2026-09-09.md"),
        "max_new_tokens": events.tokens_for(event),
        "escalation_approved": events.ESCALATION_APPROVED,
        "match_tolerances": list(density.MATCH_TOLERANCE_SEC),
        "stage1_selection": stage1["selection"],
        "pairs": rows, "pair_statuses": statuses, "event_verdict": verdict,
        "note": ("세 pair가 모두 EVALUABLE일 때만 PAIRED_OUTPUT_SENSITIVITY를 "
                 "낸다. 0.5fps arm은 ground truth가 아니고, D2·D3는 90초 겹치므로 "
                 "n=3 독립 표본으로 해석하지 않는다."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage 2 요약·게이트")
    parser.add_argument("--runs", required=True)
    parser.add_argument("--event", default=events.EVENT_V1B,
                        choices=list(events.MAX_NEW_TOKENS))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    record = summarize(Path(args.runs), args.event)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print("event_verdict=%s pairs=%s" % (record["event_verdict"],
                                         record["pair_statuses"]))
    for pair in PAIRS:
        row = record["pairs"][pair]
        print("%s %s %s S0(ev=%s trunc=%s lang_fail=%s) S1(ev=%s trunc=%s lang_fail=%s)"
              % (pair, row["window"]["window_id"],
                 row["evaluability"]["status"],
                 row["arms"]["S0"]["event_count"],
                 row["arms"]["S0"]["truncated_at_cap"],
                 row["arms"]["S0"]["language_contract_failure"],
                 row["arms"]["S1"]["event_count"],
                 row["arms"]["S1"]["truncated_at_cap"],
                 row["arms"]["S1"]["language_contract_failure"]))
    return 0 if record["event_verdict"] == compare.EVENT_MEASURED else 1


if __name__ == "__main__":
    raise SystemExit(main())
