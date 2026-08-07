"""[AI Hub 외부 평가 — 확정 config로 1회 실행. 채택 아님, 외부 검증용]

**사전 등록 (실행 전에 확정, 2026-08-07).**

- α는 dev 확정값 `alpha_star`(0.5)를 그대로 주입한다. **여기서 α를 재탐색하지 않는다** —
  하면 외부 검증이 아니라 또 하나의 dev가 된다.
- 주지표: 전체 질의(1,086건)의 baseline↔proposed **쌍체 차이**와 95% CI.
- 부지표: `gt_seg_idx` 길이 **3 이하**인 질의(817건, 75%)만의 같은 대비. 영상이 60초라
  세그먼트가 12개뿐인데 정답 구간이 6개 이상을 덮는 질의가 100건(9.2%) 있어, 그런
  질의는 아무 세그먼트나 맞혀도 hit이 된다. 변별력 있는 부분집합을 **결과를 보기 전에**
  정의해 둔다.
- 도메인별(드라마·여행·요리음식) 분해를 병기한다.
- **절대값을 우리 test와 비교하지 않는다.** 후보가 12개뿐이라 Recall@5의 무작위 기저가
  0.42다(우리 영상은 122~357세그먼트). 비교 가능한 것은 쌍체 차이뿐이다.
- α 곡선은 **사후 진단으로만** 병기한다. 라벨이 시각 동작 서술이라 자막 채널이 노이즈로
  작동할 가능성을 확인하려는 것이고, 어떤 결정에도 쓰지 않는다.

재현: python docs/probes/aihub_external_eval.py --config config_aihub.yaml
"""
import argparse, json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                                    # noqa: E402
from m5_search import VideoIndex                                 # noqa: E402
from m6_evaluate import evaluate, load_queries, validate_gt_seg_idx  # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
DISCRIMINATIVE_MAX_GT = 3            # 사전 등록: 부지표 기준


def rr(res):
    return np.array([r["mrr"] for r in res["per_query"]])


def hitk(res, k):
    return np.array([r[f"hit@{k}"] for r in res["per_query"]])


def paired_ci(base_v, cand_v, ib):
    d = cand_v[ib].mean(1) - base_v[ib].mean(1)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"delta": round(float(cand_v.mean() - base_v.mean()), 4),
            "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "significant": bool(lo > 0 or hi < 0)}


def block(qs, idx, alpha, cfg, ib):
    """baseline(자막 단독, α=1) 대비 proposed(α=alpha) 쌍체 대비."""
    base = evaluate(qs, idx, 1.0, cfg)
    prop = evaluate(qs, idx, alpha, cfg)
    out = {"n": len(qs),
           "baseline": base["metrics"], "proposed": prop["metrics"],
           "diff_mrr": paired_ci(rr(base), rr(prop), ib)}
    for k in cfg["eval_k"]:
        out[f"diff_hit@{k}"] = paired_ci(hitk(base, k), hitk(prop, k), ib)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    ap.add_argument("--alpha", type=float, default=None,
                    help="미지정 시 results/alpha_search_dev.json의 alpha_star를 읽는다")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    if a.alpha is None:
        dev = json.loads((ROOT / "results/alpha_search_dev.json").read_text(encoding="utf-8"))
        alpha = dev.get("alpha_star", dev.get("dev_search", {}).get("alpha_star"))
    else:
        alpha = a.alpha
    assert alpha is not None, "alpha 확정값을 찾지 못했다"

    qs = [q for q in load_queries(str(ROOT / a.queries)) if q["split"] == "external"]
    vids = sorted({q["video_id"] for q in qs})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}
    validate_gt_seg_idx(qs, idx, cfg["seg_len_sec"])

    rng = np.random.default_rng(cfg["seed"])
    B = cfg["bootstrap_B"]

    rep = {"note": "채택 아님. AI Hub 제3자 라벨 외부 검증, 확정 config 1회 실행.",
           "alpha_from_dev": alpha, "seed": cfg["seed"], "bootstrap_B": B,
           "n_videos": len(vids), "n_queries": len(qs),
           "caveat": ("영상 60초·세그먼트 12개라 절대값을 본 test(122~357세그먼트)와 "
                      "비교하지 말 것. 쌍체 차이만 비교 가능."),
           "prereg": {"primary": "전체 질의", "secondary": f"gt_seg_idx 길이<={DISCRIMINATIVE_MAX_GT}",
                      "declared_before_run": True}}

    ib = rng.integers(0, len(qs), size=(B, len(qs)))
    rep["overall"] = block(qs, idx, alpha, cfg, ib)

    sub = [q for q in qs if len(q["gt_seg_idx"]) <= DISCRIMINATIVE_MAX_GT]
    ib2 = rng.integers(0, len(sub), size=(B, len(sub)))
    rep["discriminative"] = block(sub, idx, alpha, cfg, ib2)

    rep["by_domain"] = {}
    for dom in sorted({q["type"] for q in qs}):
        dq = [q for q in qs if q["type"] == dom]
        ibd = rng.integers(0, len(dq), size=(B, len(dq)))
        rep["by_domain"][dom] = block(dq, idx, alpha, cfg, ibd)

    # 사후 진단 — 결정에 쓰지 않는다. 자막 채널이 이 라벨에서 기여하는지 확인용.
    rep["alpha_curve_posthoc"] = {
        str(x): evaluate(qs, idx, x, cfg)["metrics"]["mrr"]
        for x in [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "aihub_external_eval.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    o = rep["overall"]
    print(f"질의 {len(qs)} / 영상 {len(vids)} / α={alpha}")
    print(f"  전체       MRR {o['baseline']['mrr']:.4f} -> {o['proposed']['mrr']:.4f} "
          f"Δ{o['diff_mrr']['delta']:+.4f} CI{o['diff_mrr']['ci95']}")
    d = rep["discriminative"]
    print(f"  변별부분집합 MRR {d['baseline']['mrr']:.4f} -> {d['proposed']['mrr']:.4f} "
          f"Δ{d['diff_mrr']['delta']:+.4f} CI{d['diff_mrr']['ci95']} (n={d['n']})")
    print("->", p)


if __name__ == "__main__":
    main()
