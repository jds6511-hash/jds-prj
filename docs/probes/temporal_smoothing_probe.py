"""[시간적 점수 평활 — dev 전용, 채택 아님, 실측용]

**구조 점검에서 빠져 있던 구간.** 지금 M5는 세그먼트를 **서로 독립인 문서**로 취급해
점수를 매긴다. 그런데 우리가 찾는 것은 "순간"이고, **순간은 보통 여러 세그먼트에
걸쳐 있다**(dev GT 세그먼트 수 중앙 2, test도 1~2). 이웃 세그먼트의 점수가 서로
정보를 준다는 뜻인데 그 정보를 안 쓰고 있다.

모먼트 검색에서 흔히 쓰는 후처리다: 점수 수열에 작은 창을 씌워 평활하면 **단발성
잡음 히트가 눌리고 연속된 구간이 올라간다.** 정답이 연속 구간이라는 사전지식과
맞는다.

**비용이 0에 가깝다** — 캡션·자막·임베딩을 다시 만들 필요가 없다. 이미 있는 점수
수열에 씌우기만 한다. 검색 시점에 계산되므로 인덱스도 불변이다.

두 가지를 잰다.
  box   score'[i] = score[i] + w*(score[i-1] + score[i+1])
  gauss score' = gaussian_filter1d(score, sigma)
w=0 / sigma=0이 현행과 동일하므로 그 지점이 대조군이다.

**주의**: 이건 GT가 연속 구간이라는 성질을 이용하는 것이라, 만약 채택한다면
"평가 지표에 맞춘 후처리 아니냐"는 지적을 받을 수 있다. 그래서 유형별 분해를
병기한다 — 장면형(무발화 연속 구간)에서만 오르고 자막형에서 떨어지면 그건
일반적 개선이 아니라 특정 유형에 맞춘 것이다.

work/·results/ 불변, test 미접촉.
재현: python docs/probes/temporal_smoothing_probe.py
"""
import json, sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                          # noqa: E402
import m5_search                                       # noqa: E402
from m5_search import VideoIndex, combine_scores, expand_query   # noqa: E402
from m4_index import embed_texts                       # noqa: E402
from m6_evaluate import evaluate                       # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
BOX_W = [0.0, 0.1, 0.2, 0.3, 0.5]
GAUSS_S = [0.0, 0.5, 1.0, 1.5]


def make_search(kind: str, param: float):
    """m6.evaluate에 주입할 search_fn. 평활 외에는 운영 경로와 동일하다."""
    def search_fn(query, video, alpha, cfg):
        variants = expand_query(query, cfg)
        qs = embed_texts(variants, cfg["embed_model"])
        s_sub = np.max(video.emb_sub @ qs.T, axis=1)
        s_cap = np.max(video.emb_cap @ qs.T, axis=1)
        score = combine_scores(s_sub, s_cap, video.static_mask, alpha)
        if kind == "box" and param > 0:
            pad = np.pad(score, 1, mode="edge")
            score = score + param * (pad[:-2] + pad[2:])
        elif kind == "gauss" and param > 0:
            score = gaussian_filter1d(score, sigma=param, mode="nearest")
        order = np.argsort(-score, kind="stable")
        return [m5_search.Result(int(i), float(score[i]),
                                 video.segments[i]["start"], video.segments[i]["end"])
                for i in order]
    return search_fn


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}

    rep = {"note": "dev-only, 채택 아님. 인덱스 불변(검색 시점 후처리). test 미접촉.",
           "seed": cfg["seed"], "alphas": [0.0, 0.5], "by_setting": {}}
    vecs = {}
    for kind, grid in (("box", BOX_W), ("gauss", GAUSS_S)):
        for p in grid:
            key = f"{kind}{p}"
            if p == 0.0 and "baseline" in vecs:
                continue
            name = "baseline" if p == 0.0 else key
            blk = {}
            for alpha in (0.0, 0.5):
                r = evaluate(dev, idx, alpha, cfg, search_fn=make_search(kind, p))
                blk[f"mrr_a{alpha}"] = r["metrics"]["mrr"]
                blk[f"by_type_a{alpha}"] = {t: m["mrr"]
                                            for t, m in r["metrics"]["by_type"].items()}
                vecs[(name, alpha)] = np.array([x["mrr"] for x in r["per_query"]])
            rep["by_setting"][name] = blk
            print(f"[{name:10s}] α=0 {blk['mrr_a0.0']:.4f} | α=0.5 {blk['mrr_a0.5']:.4f}",
                  flush=True)

    n, B = len(dev), cfg["bootstrap_B"]
    ib = np.random.default_rng(cfg["seed"]).integers(0, n, size=(B, n))
    rep["contrasts"] = {}
    for (name, alpha) in vecs:
        if name == "baseline":
            continue
        b, k = vecs[("baseline", alpha)], vecs[(name, alpha)]
        d = k[ib].mean(1) - b[ib].mean(1)
        lo, hi = np.percentile(d, [2.5, 97.5])
        rep["contrasts"][f"{name}_vs_baseline/a{alpha}"] = {
            "delta": round(float(k.mean() - b.mean()), 4),
            "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "significant": bool(lo > 0 or hi < 0)}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "temporal_smoothing.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in rep["contrasts"].items():
        if v["significant"]:
            print(f"  ** {k}: {v['delta']:+.4f} CI{v['ci95']}")
    print("->", p)


if __name__ == "__main__":
    main()
