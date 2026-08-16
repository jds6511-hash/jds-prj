"""[abstention τ 재캘리브레이션 — dev 전용, 인덱스 읽기만, test 미접촉]

**왜 새로 만드나.** `results/abstention_calibration.json`은 2026-07-13에 만든 뒤
생성 스크립트가 저장소에 없다. `abstention_max_channel.py`는 그 **저장된 per_query
점수를 재분석**할 뿐이라, 캡션을 재생성하면 근거 수치가 낡은 것이 된다.
8회차 프로토콜 4단계(τ 재캘리브레이션)를 실제로 돌리려면 **현재 인덱스에서 원점수를
다시 계산**해야 한다.

**규칙은 현행 그대로다**(프로토콜 §2: "규칙은 현행 그대로"). 여기서 정하는 것은
τ 값뿐이고, 선택 규칙 자체는 바꾸지 않는다.

- 채널: `max(raw_sub_max, raw_cap_max)` — 2026-07-13 확정
- 선택 규칙: **오배제 0을 유지하는 최대 τ** (0.01 격자)
- 표본: dev 96 유관 + `queries_negative.jsonl` 20 무관

재현: python docs/probes/abstention_recalibrate.py --config config_server.yaml
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                             # noqa: E402
from m5_search import VideoIndex, search_with_stats       # noqa: E402


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines()
            if l.strip()]


def channel_max(rows):
    return [max(r["raw_sub_max"], r["raw_cap_max"]) for r in rows]


def pick_tau(rel, neg, lo=40, hi=80):
    """오배제 0을 유지하는 최대 τ. 규칙은 2026-07-13 확정분 그대로다."""
    sweep = []
    for t100 in range(lo, hi + 1):
        t = t100 / 100
        sweep.append({"tau": round(t, 2),
                      "false_abstention": sum(1 for x in rel if x < t),
                      "detected": sum(1 for x in neg if x < t)})
    zero = [s["tau"] for s in sweep if s["false_abstention"] == 0]
    return (max(zero) if zero else None), sweep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--alpha", type=float, default=0.5,
                    help="원점수는 α와 무관하지만 provenance로 기록한다")
    ap.add_argument("--out", default="abstention_calibration_recal.json")
    args = ap.parse_args()
    cfg = common.load_config(args.config)

    qs = load_jsonl(ROOT / "data/queries/queries.jsonl")
    dev = [q for q in qs if q["split"] == "dev"]
    neg_qs = load_jsonl(ROOT / "data/queries/queries_negative.jsonl")
    assert dev and neg_qs, "dev 또는 무관 질의가 비었다"

    vids = sorted({q["video_id"] for q in dev} | {q["video_id"] for q in neg_qs})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}

    def rows(queries):
        out = []
        for q in queries:
            _, st = search_with_stats(q["text"], idx[q["video_id"]], args.alpha, cfg)
            out.append({"query_id": q.get("query_id"), "video_id": q["video_id"],
                        "raw_sub_max": st["raw_sub_max"],
                        "raw_cap_max": st["raw_cap_max"]})
        return out

    rel_rows, neg_rows = rows(dev), rows(neg_qs)
    rel, neg = channel_max(rel_rows), channel_max(neg_rows)
    tau, sweep = pick_tau(rel, neg)
    at = next((s for s in sweep if s["tau"] == tau), None)

    res = {"note": __doc__.strip().splitlines()[0],
           "channel": "max(raw_sub_max, raw_cap_max)",
           "rule": "오배제 0을 유지하는 최대 τ (0.01 격자) — 2026-07-13 확정 규칙 그대로",
           "embed_model": cfg["embed_model"], "alpha_provenance": args.alpha,
           "n_relevant": len(rel), "n_negative": len(neg),
           "relevant_min": round(min(rel), 4), "negative_max": round(max(neg), 4),
           "tau": tau,
           "false_abstention": f"{at['false_abstention']}/{len(rel)}" if at else None,
           "negative_detected": f"{at['detected']}/{len(neg)}" if at else None,
           "previous_tau": 0.55,
           "margin_note": ("유관 최솟값과 τ의 간격이 좁으면 한 건만 움직여도 오배제가 난다 — "
                           "값과 함께 이 간격을 반드시 병기한다"),
           "margin": round(min(rel) - tau, 4) if tau is not None else None,
           "sweep": sweep,
           "per_query": {"relevant": rel_rows, "negative": neg_rows}}

    rdir = Path(cfg["paths"]["results"]); rdir.mkdir(exist_ok=True)
    (rdir / args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    print(f"유관 {len(rel)}건 최솟값 {min(rel):.4f} · 무관 {len(neg)}건 최댓값 {max(neg):.4f}")
    print(f"=> τ={tau}  오배제 {res['false_abstention']}  무관감지 {res['negative_detected']}"
          f"  여유 {res['margin']}")
    print("저장:", rdir / args.out)


if __name__ == "__main__":
    main()
