# 구조 점검: 점수 융합 방식 비교 — 현행 minmax+선형 vs RRF vs z-score (dev 96, dev 전용)
# minmax는 분포 꼬리에 민감하고 α의 실효 가중이 질의별 분산에 종속된다는 구조적 의문 검증.
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import numpy as np
import common
from m4_index import embed_texts
from m5_search import VideoIndex, minmax

cfg = common.load_config("config.yaml")
qs = [json.loads(l) for l in open("data/queries/queries_dev_only.jsonl", encoding="utf-8")]
vids = sorted({q["video_id"] for q in qs})
idx = {v: VideoIndex.load(cfg, v) for v in vids}
qv = embed_texts([q["text"] for q in qs], cfg["embed_model"])

def rr_of(order, gt):
    gtl = gt if isinstance(gt, list) else [gt]
    ranks = [list(order).index(g) + 1 for g in gtl if g in order]
    return 1.0 / min(ranks) if ranks else 0.0

def eval_fusion(fuse):
    rrs = []
    for q, v in zip(qs, qv):
        vi = idx[q["video_id"]]
        s_sub, s_cap = vi.emb_sub @ v, vi.emb_cap @ v
        order = np.argsort(-fuse(s_sub, s_cap), kind="stable")
        rrs.append(rr_of(order, q["gt_seg_idx"]))
    return np.array(rrs)

def z(x):
    sd = x.std()
    return np.zeros_like(x) if sd < 1e-9 else (x - x.mean()) / sd

def rrf(s_sub, s_cap, k=60):
    r_sub = np.empty_like(s_sub); r_sub[np.argsort(-s_sub, kind="stable")] = np.arange(1, len(s_sub) + 1)
    r_cap = np.empty_like(s_cap); r_cap[np.argsort(-s_cap, kind="stable")] = np.arange(1, len(s_cap) + 1)
    return 1 / (k + r_sub) + 1 / (k + r_cap)

variants = {
    "현행 minmax α=0.5": lambda s, c: 0.5 * minmax(s) + 0.5 * minmax(c),
    "현행 minmax α=0.4": lambda s, c: 0.4 * minmax(s) + 0.6 * minmax(c),
    "z-score α=0.5":     lambda s, c: 0.5 * z(s) + 0.5 * z(c),
    "z-score α=0.4":     lambda s, c: 0.4 * z(s) + 0.6 * z(c),
    "RRF k=60":          rrf,
    "RRF k=20":          lambda s, c: rrf(s, c, k=20),
    "raw합 α=0.5":       lambda s, c: 0.5 * s + 0.5 * c,   # 정규화 무용론 대조군
}
base = None
for name, f in variants.items():
    rrs = eval_fusion(f)
    if base is None: base = rrs
    diff = rrs - base
    # 간이 쌍체 부트스트랩(B=2000)
    rng = np.random.default_rng(42)
    bs = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"{name:18s} MRR={rrs.mean():.4f}  Δvs현행0.5={diff.mean():+.4f} CI[{lo:+.4f},{hi:+.4f}]")
