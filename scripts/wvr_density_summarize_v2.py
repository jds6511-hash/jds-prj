"""V2 요약 — arm validity → pair evaluability → probe 판정 (2026-09-09).

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V2_2026-09-09.md`

```
비교는 collapse된 event interval로 한다
매칭은 2단 — TEMPORALLY_COMPATIBLE → SEMANTICALLY_EQUIVALENT
확정 못 한 쌍은 ADJUDICATION_REQUIRED 목록으로 남긴다
```

GPU를 쓰지 않는다. `matched`라는 단일 이름을 쓰지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_density as density                               # noqa: E402
import wvr_density_prompt_v2 as diag                        # noqa: E402
import wvr_density_v1b as events                            # noqa: E402
import wvr_density_v2 as v2                                 # noqa: E402

PAIRS = ("D1", "D2", "D3")


class SummaryError(RuntimeError):
    """요약 계약 위반."""


def load_arm(runs: Path, pair: str, arm: str) -> dict:
    path = runs / ("%s_%s_%s.json" % (events.tag_for(events.EVENT_V2), pair,
                                      arm))
    if not path.is_file():
        raise SummaryError("산출물이 없다: %s" % path.name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != events.EVENT_V2:
        raise SummaryError("V2 산출물이 아니다: %s" % path.name)
    return record


def arm_view(record) -> dict:
    parsed = record.get("parsed") or {}
    shape = v2.representation(parsed.get("collapsed") or [])
    return {
        "frames": record["metrics"].get("delivered_frame_count"),
        "input_tokens": record["metrics"].get("input_token_count"),
        "generated_tokens": record["metrics"].get("generated_token_count"),
        "truncated_at_cap": v2.truncated_at_cap(record),
        "raw_event_count": len(parsed.get("events", [])),
        "collapsed_event_count": shape["collapsed_event_count"],
        "unique_signature_count": shape["unique_signature_count"],
        "max_collapsed_run": shape["max_collapsed_run"],
        "degenerate": shape["degenerate"],
        "parse_status": parsed.get("status"),
        "violations": len(parsed.get("violations", [])),
        "language": parsed.get("language"),
        "validity": v2.arm_validity(record),
        "infer_wall_sec": record["metrics"].get("infer_wall_sec"),
        "peak_vram_allocated_mib": record["metrics"].get(
            "peak_vram_allocated_mib"),
    }


def compare_pair(s0: dict, s1: dict) -> dict:
    reference = (s0.get("parsed") or {}).get("collapsed") or []
    arm = (s1.get("parsed") or {}).get("collapsed") or []
    per_tolerance = {}
    for tolerance in v2.TOLERANCES:
        alignment = v2.align(reference, arm, tolerance)
        per_tolerance["tol_%.1f" % tolerance] = {
            **alignment, "field_divergence": v2.field_divergence(alignment)}
    return {
        "reference_collapsed_count": len(reference),
        "arm_collapsed_count": len(arm),
        "collapsed_count_delta": len(arm) - len(reference),
        "per_tolerance": per_tolerance,
        "note": ("0.5fps arm은 ground truth가 아니다. S0-only는 놓친 사건이 "
                 "아니고 S1-only는 환각이 아니다. 시간 정렬만으로 동일 사건이라 "
                 "부르지 않는다."),
    }


def summarize(runs: Path) -> dict:
    stage1 = json.loads((runs / "density_stage1.json").read_text(
        encoding="utf-8"))
    rows, statuses = {}, []
    for pair in PAIRS:
        s0, s1 = load_arm(runs, pair, "S0"), load_arm(runs, pair, "S1")
        evaluability = v2.pair_evaluability(s0, s1)
        statuses.append(evaluability["status"])
        rows[pair] = {
            "window": s0["window"], "evaluability": evaluability,
            "arms": {"S0": arm_view(s0), "S1": arm_view(s1)},
        }
        if evaluability["status"] == v2.PAIR_EVALUABLE:
            rows[pair]["comparison"] = compare_pair(s0, s1)

    verdict = v2.probe_verdict(statuses)
    return {
        "schema": "wvr_density_v2_summary_v1", "event": events.EVENT_V2,
        "prereg": ("docs/preregistration/"
                   "WVR_SAMPLING_SEMANTIC_DENSITY_V2_2026-09-09.md"),
        "prompt_contract": diag.DIAG_CONTRACT_NAME,
        "prompt_hash": diag.prompt_hash(),
        "output_language": diag.OUTPUT_LANGUAGE,
        "max_new_tokens": events.tokens_for(events.EVENT_V2),
        "match_tolerances": list(v2.TOLERANCES),
        "primary_tolerance_sec": v2.TOLERANCES[0],
        "stage1_selection": stage1["selection"],
        "pairs": rows, "pair_statuses": statuses, "probe_verdict": verdict,
        "semantic_sufficiency_claim_allowed": False,
        "note": ("세 pair가 모두 EVALUABLE일 때만 리뷰 판정을 낸다. collapse 뒤에도 "
                 "표현이 축퇴면 EVENT_REPRESENTATION_DEGENERACY로 닫는다. "
                 "D2·D3는 90초 겹치므로 n=3 독립 표본이 아니다."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V2 요약·게이트")
    parser.add_argument("--runs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    record = summarize(Path(args.runs))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print("probe_verdict=%s pairs=%s" % (record["probe_verdict"],
                                         record["pair_statuses"]))
    for pair in PAIRS:
        row = record["pairs"][pair]
        s0, s1 = row["arms"]["S0"], row["arms"]["S1"]
        print("%s %s %s  S0 raw=%s coll=%s uniq=%s  S1 raw=%s coll=%s uniq=%s"
              % (pair, row["window"]["window_id"],
                 row["evaluability"]["status"], s0["raw_event_count"],
                 s0["collapsed_event_count"], s0["unique_signature_count"],
                 s1["raw_event_count"], s1["collapsed_event_count"],
                 s1["unique_signature_count"]))
        if "comparison" in row:
            primary = row["comparison"]["per_tolerance"][
                "tol_%.1f" % v2.TOLERANCES[0]]
            print("   equiv=%s adjud=%s S0_no_equiv=%s S1_no_equiv=%s "
                  "merge=%s split=%s inversions=%s"
                  % (primary["equivalent_count"], primary["adjudication_count"],
                     len(primary["reference_without_equivalent"]),
                     len(primary["arm_without_equivalent"]),
                     len(primary["merge_candidates"]),
                     len(primary["split_candidates"]),
                     primary["order_inversions"]))
    return 0 if record["probe_verdict"] == v2.DECISION_ELIGIBLE else 1


if __name__ == "__main__":
    raise SystemExit(main())
