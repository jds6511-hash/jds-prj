"""[B2 BM25 어휘 baseline — dev 비교, 심사 방어용] 순수 어휘 매칭(BM25) baseline을
현행 시맨틱 baseline(α=1.0, 자막 임베딩)·proposed(α=0.5)와 dev에서 비교한다.
"왜 키워드 검색과 비교 안 했나"에 대한 근거. 한국어 교착어 대응으로 문자 n-gram(2,3) 토큰.
config·test 미접촉, dev-only. 외부 의존 없이 Okapi BM25 직접 구현.
재현: python docs/probes/bm25_baseline_probe.py
"""
import json, sys, math
from pathlib import Path
from collections import Counter
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex, search


def toks(text):
    """문자 2·3-gram(공백 제거). 한국어 교착·조사 변이에 강건, 형태소기 의존 없음."""
    s = "".join((text or "").split())
    return [s[i:i+2] for i in range(len(s)-1)] + [s[i:i+3] for i in range(len(s)-2)]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [toks(d) for d in docs]
        self.dl = [len(d) for d in self.docs]
        self.avgdl = (sum(self.dl) / len(self.dl)) if self.dl else 0.0
        self.tf = [Counter(d) for d in self.docs]
        df = Counter()
        for d in self.tf:
            df.update(d.keys())
        N = len(self.docs)
        self.idf = {t: math.log(1 + (N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, query):
        q = toks(query)
        out = np.zeros(len(self.docs))
        for i, tf in enumerate(self.tf):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.dl[i] / (self.avgdl or 1)))
            out[i] = s
        return out


def rr(order, gt):
    gt = set(gt)
    for r, i in enumerate(order, 1):
        if i in gt:
            return 1.0 / r
    return 0.0


def main():
    cfg = common.load_config("config.yaml")
    qs = [json.loads(l) for l in
          Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}
    bm_sub = {v: BM25([s.get("subtitle", "") for s in idx[v].segments]) for v in vids}
    bm_subcap = {v: BM25([(s.get("subtitle", "") + " " + s.get("caption", "")) for s in idx[v].segments])
                 for v in vids}

    types = [q["type"] for q in dev]
    rr_bm_sub, rr_bm_subcap, rr_sem_sub, rr_prop = [], [], [], []
    for q in dev:
        vi = idx[q["video_id"]]
        o1 = list(np.argsort(-bm_sub[q["video_id"]].scores(q["text"]), kind="stable"))
        o2 = list(np.argsort(-bm_subcap[q["video_id"]].scores(q["text"]), kind="stable"))
        rr_bm_sub.append(rr([int(i) for i in o1], q["gt_seg_idx"]))
        rr_bm_subcap.append(rr([int(i) for i in o2], q["gt_seg_idx"]))
        rr_sem_sub.append(rr([r.idx for r in search(q["text"], vi, 1.0, cfg)], q["gt_seg_idx"]))
        rr_prop.append(rr([r.idx for r in search(q["text"], vi, 0.5, cfg)], q["gt_seg_idx"]))

    arrs = {"BM25_sub": np.array(rr_bm_sub), "BM25_sub+cap": np.array(rr_bm_subcap),
            "semantic_sub(baseline α=1.0)": np.array(rr_sem_sub),
            "proposed(α=0.5)": np.array(rr_prop)}

    def bt(a):
        return {t: round(float(a[np.array([x == t for x in types])].mean()), 4)
                for t in sorted(set(types))}

    n = len(dev); B = cfg["bootstrap_B"]
    rng = np.random.default_rng(cfg["seed"]); ib = rng.integers(0, n, size=(B, n))
    def ci(a, b):
        d = a[ib].mean(1) - b[ib].mean(1)
        lo, hi = (round(float(x), 4) for x in np.percentile(d, [2.5, 97.5]))
        return {"delta": round(float(a.mean() - b.mean()), 4), "ci95": [lo, hi],
                "significant": not (lo <= 0 <= hi)}

    out = {
        "note": "dev-only. BM25 문자 2·3-gram 토큰. 심사 '어휘 baseline' 대비 근거.",
        "mrr_overall": {k: round(float(v.mean()), 4) for k, v in arrs.items()},
        "mrr_by_type": {k: bt(v) for k, v in arrs.items()},
        "semantic_sub_vs_BM25_sub": ci(arrs["semantic_sub(baseline α=1.0)"], arrs["BM25_sub"]),
        "proposed_vs_BM25_sub": ci(arrs["proposed(α=0.5)"], arrs["BM25_sub"]),
        "proposed_vs_BM25_subcap": ci(arrs["proposed(α=0.5)"], arrs["BM25_sub+cap"]),
    }
    dest = Path(__file__).resolve().parent / "_scratch" / "bm25_baseline.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)
    print("overall:", out["mrr_overall"])


if __name__ == "__main__":
    main()
