# 오염 캡션 harm 실측: 데모 인덱스(seg 125, 234)의 false-positive / false-negative 검증
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import numpy as np
import common
from m4_index import embed_texts
from m5_search import VideoIndex, search

cfg = common.load_config("config.yaml")
alpha = json.load(open("results/alpha_search_dev.json", encoding="utf-8"))["alpha_star"]
model = cfg["embed_model"]
vi = VideoIndex.load(cfg, "pland_costco_hosting")
doc = json.load(open("work/pland_costco_hosting/segments.json", encoding="utf-8"))
segs = doc["segments"]
CORRUPT = [125, 234]
print(f"embed={model} alpha={alpha} thr={cfg['static_threshold']}")
for i in CORRUPT:
    print(f"  seg {i}: 자막={segs[i]['subtitle']!r} 캡션(오염)={segs[i]['caption'][:34]!r}")

# ── 실험 1: FALSE POSITIVE ─ 무관/일반 질의에 오염 세그가 상위로 뜨는가
print("\n[실험1] false positive — 다양한 질의 top10에 오염 세그가 등장하는지")
probe_qs = [
    "요리 재료를 준비하는 장면", "마트에서 장을 보는 장면", "가방을 만드는 장면",
    "음식을 접시에 담는 장면", "인사하는 장면", "비트코인 시세 전망",
    "고양이가 뛰노는 장면", "자동차가 도로를 달리는 장면",
]
fp = 0
for q in probe_qs:
    order = [r.idx for r in search(q, vi, alpha, cfg)]
    ranks = {i: (order.index(i) + 1 if i in order else None) for i in CORRUPT}
    hit = [i for i in CORRUPT if ranks[i] and ranks[i] <= 10]
    if hit:
        fp += 1
    print(f"  {q:22s} → seg125 rank={ranks[125]}, seg234 rank={ranks[234]}"
          + ("  ⚠️TOP10" if hit else ""))
print(f"  => 오염 세그가 top10에 뜬 질의: {fp}/{len(probe_qs)}")

# ── 실험 2: FALSE NEGATIVE ─ 제 내용(중국어 캡션이 실제로 서술하는 것)으로 찾을 때
#    오염(중국어) vs 한국어 번역 캡션의 질의 정합도를 KURE로 직접 대조
print("\n[실험2] false negative — 오염 캡션의 실제 내용을 한국어로 질의했을 때")
cases = [
    (234, "빨간 나무 주걱으로 노란 냄비의 음식을 젓는 장면",
          "한 사람이 빨간색 나무 주걱으로 노란색 냄비 안의 음식을 젓고 있습니다."),
    (125, "감자와 버섯 당근이 담긴 접시",
          "접시 위에 작은 감자 몇 개와 버섯 몇 개, 당근 채가 놓여 있습니다."),
]
qtexts = [c[1] for c in cases]
ko_caps = [c[2] for c in cases]
zh_caps = [segs[c[0]]["caption"] for c in cases]
qv = embed_texts(qtexts, model)
kov = embed_texts(ko_caps, model)
zhv = embed_texts(zh_caps, model)
for k, (idx, q, _) in enumerate(cases):
    cos_zh = float(qv[k] @ zhv[k])   # 인덱스에 실제 들어있는 오염(중국어) 캡션
    cos_ko = float(qv[k] @ kov[k])   # 정상이었다면 얻었을 한국어 캡션
    # 실제 검색에서 이 질의로 오염 세그가 몇 위인지
    order = [r.idx for r in search(q, vi, alpha, cfg)]
    rank = order.index(idx) + 1 if idx in order else None
    print(f"  seg {idx}: cos(질의,오염중국어)={cos_zh:.3f}  cos(질의,정상한국어)={cos_ko:.3f}"
          f"  손실={cos_ko - cos_zh:+.3f}  실제검색순위={rank}")
