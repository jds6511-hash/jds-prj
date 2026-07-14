"""[#2 적응형 α dev 탐색 — 채택 아님, realizable gain 유의성 재측정]
질의 텍스트만으로(leakage 방지: type 필드는 학습 라벨·평가 대상으로만, 입력 아님) 유형을
예측하는 임베딩 분류기(LOO nearest-centroid)가 규칙분류기 55%를 넘는지, 그 정확도로
유형별 α 라우팅이 단일 α 대비 유의 이득을 내는지 dev 96에서만 측정한다.
config·test 미접촉, 채택 없음. 출력: scratchpad JSON.
재현: python docs/probes/adaptive_alpha_probe.py
"""
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex, search
from m4_index import embed_texts


def rr(ranked, gt):
    gt = set(gt)
    for r, x in enumerate(ranked, 1):
        if x.idx in gt:
            return 1.0 / r
    return 0.0


def main():
    cfg = common.load_config("config.yaml")
    grid = cfg["alpha_grid"]
    qs = [json.loads(l) for l in
          Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}

    # per-query RR at each alpha
    types = [q["type"] for q in dev]
    rr_mat = np.zeros((len(dev), len(grid)))
    for i, q in enumerate(dev):
        for j, a in enumerate(grid):
            rr_mat[i, j] = rr(search(q["text"], idx[q["video_id"]], a, cfg), q["gt_seg_idx"])

    uniq = sorted(set(types))
    # 유형별 point-optimal α (dev 전체 기준)
    type_best_a = {}
    for t in uniq:
        mask = np.array([tt == t for tt in types])
        type_best_a[t] = grid[int(np.argmax(rr_mat[mask].mean(axis=0)))]
    # 단일 최적 α
    single_best_j = int(np.argmax(rr_mat.mean(axis=0)))
    single_best_a = grid[single_best_j]

    # 질의-텍스트-only 분류기: KURE 임베딩 LOO nearest-centroid
    qemb = embed_texts([q["text"] for q in dev], cfg["embed_model"])  # L2 정규화
    tarr = np.array(types)
    pred = []
    for i in range(len(dev)):
        cents = {}
        for t in uniq:
            m = (tarr == t).copy(); m[i] = False  # LOO: 자기 제외
            cents[t] = qemb[m].mean(axis=0)
        # 코사인(정규화 벡터라 내적) 최대 센트로이드
        pred.append(max(uniq, key=lambda t: float(qemb[i] @ cents[t])))
    pred = np.array(pred)
    clf_acc = float((pred == tarr).mean())

    aj = {a: j for j, a in enumerate(grid)}
    def mrr_for(alpha_of_query):
        return float(np.mean([rr_mat[i, aj[alpha_of_query(i)]] for i in range(len(dev))]))

    mrr_single = mrr_for(lambda i: single_best_a)
    mrr_fixed05 = mrr_for(lambda i: 0.5)
    mrr_oracle = mrr_for(lambda i: type_best_a[types[i]])       # 참 유형 α (상한)
    mrr_routed = mrr_for(lambda i: type_best_a[pred[i]])        # 예측 유형 α (실현)

    # paired bootstrap: routed - single_best
    n = len(dev); B = cfg["bootstrap_B"]
    rng = np.random.default_rng(cfg["seed"])
    ib = rng.integers(0, n, size=(B, n))
    rv_single = np.array([rr_mat[i, aj[single_best_a]] for i in range(n)])
    rv_routed = np.array([rr_mat[i, aj[type_best_a[pred[i]]]] for i in range(n)])
    diffs = rv_routed[ib].mean(1) - rv_single[ib].mean(1)
    ci = [round(float(x), 4) for x in np.percentile(diffs, [2.5, 97.5])]

    out = {
        "note": "dev-only 탐색, 채택 아님. type 필드는 라벨·평가용, 분류기 입력은 질의 텍스트뿐.",
        "type_point_optimal_alpha": type_best_a,
        "single_best_alpha": single_best_a,
        "classifier": {"method": "KURE LOO nearest-centroid (query text only)",
                       "accuracy": round(clf_acc, 3), "rule_baseline_ref": 0.55},
        "mrr": {"fixed_0.5": round(mrr_fixed05, 4), "single_best": round(mrr_single, 4),
                "routed_predicted_type": round(mrr_routed, 4), "oracle_true_type": round(mrr_oracle, 4)},
        "realizable_gain_routed_minus_single": {
            "delta": round(mrr_routed - mrr_single, 4), "ci95_paired": ci,
            "significant": not (ci[0] <= 0 <= ci[1])},
        "oracle_ceiling_minus_single": round(mrr_oracle - mrr_single, 4),
    }
    dest = Path(__file__).resolve().parent / "_scratch" / "adaptive_alpha.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)
    print(json.dumps(out["mrr"], ensure_ascii=False), "| clf_acc", out["classifier"]["accuracy"],
          "| routed-single", out["realizable_gain_routed_minus_single"])


if __name__ == "__main__":
    main()
