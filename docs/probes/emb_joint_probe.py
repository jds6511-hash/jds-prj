# 8-4 결합 임베딩 제3 arm — dev 비교 (설계서 [예정] 소화, dev 전용·GPU 임베딩만)
# joint: "자막: {sub}\n장면: {cap}"를 한 텍스트로 임베딩 → 질의 코사인 → z-score 단독
#        (치환·α 없음, 결합이 임베딩 내부에서 일어남 — 8-4 정의).
# 비교: proposed(분리 임베딩 + z-score α 결합, 현행) vs joint vs baseline(자막 단독).
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import numpy as np
import common
from m4_index import embed_texts
from m5_search import VideoIndex, combine_scores, zscore

cfg = common.load_config("config.yaml")
qs = [json.loads(l) for l in open("data/queries/queries_dev_only.jsonl", encoding="utf-8")]
vids = sorted({q["video_id"] for q in qs})

def rr(order, gt):
    gtl = gt if isinstance(gt, list) else [gt]
    rks = [list(order).index(g) + 1 for g in gtl if g in order]
    return 1.0 / min(rks) if rks else 0.0

# 영상별 joint 임베딩 계산(대칭성: 빈 자막도 템플릿 유지)
idx, joint = {}, {}
for v in vids:
    vi = VideoIndex.load(cfg, v)
    idx[v] = vi
    doc = json.load(open(common.work_dir(cfg, v) / "segments.json", encoding="utf-8"))
    texts = [f"자막: {s['subtitle']}\n장면: {s['caption']}" for s in doc["segments"]]
    joint[v] = embed_texts(texts, cfg["embed_model"])

qv = embed_texts([q["text"] for q in qs], cfg["embed_model"])
from collections import defaultdict
rrs = defaultdict(lambda: defaultdict(list))  # arm -> type -> [rr]
allrr = defaultdict(list)
for q, v in zip(qs, qv):
    vi = idx[q["video_id"]]
    s_sub, s_cap = vi.emb_sub @ v, vi.emb_cap @ v
    s_joint = joint[q["video_id"]] @ v
    arms = {
        "baseline(α=1)": combine_scores(s_sub, s_cap, vi.static_mask, 1.0),
        "proposed(α=0.5)": combine_scores(s_sub, s_cap, vi.static_mask, 0.5),
        "joint": zscore(s_joint),
    }
    for name, score in arms.items():
        r = rr(np.argsort(-score, kind="stable"), q["gt_seg_idx"])
        rrs[name][q["type"]].append(r)
        allrr[name].append(r)

print(f"{'arm':18s} {'전체':>7s} {'자막형':>7s} {'장면형':>7s} {'복합형':>7s}")
for name in ("baseline(α=1)", "proposed(α=0.5)", "joint"):
    by = rrs[name]
    row = [sum(allrr[name]) / len(allrr[name])]
    row += [sum(by[t]) / len(by[t]) for t in ("자막형", "장면형", "복합형")]
    print(f"{name:18s} " + " ".join(f"{x:7.4f}" for x in row))

# proposed vs joint 쌍체 부트스트랩 CI
rng = np.random.default_rng(42)
diff = np.array(allrr["proposed(α=0.5)"]) - np.array(allrr["joint"])
bs = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
lo, hi = np.percentile(bs, [2.5, 97.5])
print(f"\nproposed - joint = {diff.mean():+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]")
