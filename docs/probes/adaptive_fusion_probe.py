"""[C 적응형 융합 dev 탐색 — 채택 아님] 전역 상수 α 대신 세그먼트 신뢰도로 α_i를 조정.
가설(#4 오류분석): '세그먼트마다 믿을 채널이 다르다'. 빈 자막 세그먼트는 자막 임베딩이
노이즈이므로 캡션만(α_i=0), 오염 캡션 세그먼트는 자막만(α_i=1) 신뢰.
config·test 미접촉, dev-only, 채택 없음. 출력: scratchpad JSON.
재현: python docs/probes/adaptive_fusion_probe.py
"""
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex, zscore
from m4_index import embed_texts


def seg_alpha(vi, base):
    """세그먼트별 α_i(자막 가중). 빈 자막→0(캡션만), 오염 캡션→1(자막만), 둘 다→base."""
    a = np.full(len(vi.segments), base, dtype=float)
    for i, s in enumerate(vi.segments):
        empty = not (s.get("subtitle") or "").strip()
        corr = common.is_corrupted_caption(s.get("caption") or "")
        if empty and not corr:
            a[i] = 0.0
        elif corr and not empty:
            a[i] = 1.0
    return a


def rr_of(order, gt):
    gt = set(gt)
    for r, idx in enumerate(order, 1):
        if idx in gt:
            return 1.0 / r
    return 0.0


def main():
    cfg = common.load_config("config.yaml")
    qs = [json.loads(l) for l in
          Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}
    # 세그먼트 프로파일
    prof = {v: {"empty_sub": int(sum(not (s.get("subtitle") or "").strip() for s in idx[v].segments)),
                "corrupt_cap": int(sum(common.is_corrupted_caption(s.get("caption") or "")
                                       for s in idx[v].segments)),
                "n": len(idx[v].segments)} for v in vids}

    # 질의 임베딩 캐시
    qemb = {}
    allq = list({q["text"] for q in dev})
    E = embed_texts(allq, cfg["embed_model"])
    for t, e in zip(allq, E):
        qemb[t] = e

    types = [q["type"] for q in dev]
    # 변형별 per-query RR
    def eval_variant(alpha_mode, base):
        rrs = []
        for q in dev:
            vi = idx[q["video_id"]]
            e = qemb[q["text"]]
            s_sub = zscore(vi.emb_sub @ e)
            s_cap = zscore(vi.emb_cap @ e)
            if alpha_mode == "fixed":
                a = base
            elif alpha_mode == "adaptive":
                a = seg_alpha(vi, base)
            score = a * s_sub + (1 - a) * s_cap
            order = np.argsort(-score, kind="stable")
            rrs.append(rr_of([int(i) for i in order], q["gt_seg_idx"]))
        return np.array(rrs)

    variants = {
        "fixed_0.5": eval_variant("fixed", 0.5),
        "fixed_0.4": eval_variant("fixed", 0.4),
        "adaptive_base0.5": eval_variant("adaptive", 0.5),
        "adaptive_base0.4": eval_variant("adaptive", 0.4),
    }

    def by_type(rr):
        out = {}
        for t in sorted(set(types)):
            m = np.array([tt == t for tt in types])
            out[t] = round(float(rr[m].mean()), 4)
        return out

    # paired bootstrap: adaptive_base0.5 - fixed_0.5
    n = len(dev); B = cfg["bootstrap_B"]
    rng = np.random.default_rng(cfg["seed"]); ib = rng.integers(0, n, size=(B, n))
    def ci(a, b):
        d = a[ib].mean(1) - b[ib].mean(1)
        lo, hi = (round(float(x), 4) for x in np.percentile(d, [2.5, 97.5]))
        return {"delta": round(float(a.mean() - b.mean()), 4), "ci95": [lo, hi],
                "significant": not (lo <= 0 <= hi)}

    out = {
        "note": "dev-only 탐색, 채택 아님. α_i는 세그먼트 자막/캡션 상태로만 결정(질의 무관).",
        "segment_profile": prof,
        "mrr_overall": {k: round(float(v.mean()), 4) for k, v in variants.items()},
        "mrr_by_type": {k: by_type(v) for k, v in variants.items()},
        "adaptive0.5_vs_fixed0.5": ci(variants["adaptive_base0.5"], variants["fixed_0.5"]),
        "adaptive0.4_vs_fixed0.4": ci(variants["adaptive_base0.4"], variants["fixed_0.4"]),
        "caveat": "dev 오염 캡션 0건이라 α_i=1(오염→자막) 게이트는 dev에서 미발동 — "
                  "빈자막→캡션 게이트만 실효. 오염 게이트는 미세정/서버 캡션에서만 검증 가능.",
    }
    dest = Path(__file__).resolve().parent / "_scratch" / "adaptive_fusion.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)
    print("overall:", out["mrr_overall"])
    print("adaptive0.5 vs fixed0.5:", out["adaptive0.5_vs_fixed0.5"])


if __name__ == "__main__":
    main()
