# 점검5: 빈 자막 임베딩의 실제 동작 — degenerate 벡터가 per-query minmax를 왜곡하는가
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import numpy as np
import common
from m4_index import embed_texts

cfg = common.load_config("config.yaml")
model = cfg["embed_model"]
doc = json.load(open("work/pland_costco_hosting/segments.json", encoding="utf-8"))
segs = doc["segments"]
emb_sub = np.load("work/pland_costco_hosting/emb_sub.npy")

# 1) 빈 자막 세그먼트들의 임베딩이 실제로 동일한 하나의 벡터인가
empty_idx = [i for i, s in enumerate(segs) if not s["subtitle"].strip()]
nonempty_idx = [i for i, s in enumerate(segs) if s["subtitle"].strip()]
ev = emb_sub[empty_idx]
pair_max_diff = float(np.abs(ev - ev[0]).max()) if len(ev) > 1 else 0.0
print(f"빈 자막 세그: {len(empty_idx)}/{len(segs)} ({len(empty_idx)/len(segs):.0%})")
print(f"빈 자막 임베딩들 최대 편차(0이면 전부 동일): {pair_max_diff:.2e}")
emptyvec = ev[0]
# 직접 임베딩한 빈 문자열과도 대조
direct = embed_texts([""], model)[0]
print(f"저장된 빈자막벡터 vs 직접임베딩('') 코사인: {float(emptyvec @ direct):.4f}")
print(f"빈자막벡터 노름: {float(np.linalg.norm(emptyvec)):.4f} (정규화면 ~1)")

# 2) 여러 질의에 대해 빈자막벡터의 코사인이 per-query 분포에서 어디 위치하는가
#    (max나 min이면 minmax 정규화 범위를 그 세그가 지배 → 왜곡)
queries = [
    "요리하는 장면", "마트에서 장보는 장면", "가방 만드는 장면", "인사하는 장면",
    "설탕을 넣는 장면", "음식을 접시에 담는 장면", "비트코인 시세", "자동차 주행",
]
qv = embed_texts(queries, model)
print("\n질의별 빈자막 코사인 위치 (전체 세그 대비 백분위·최댓값·최솟값 여부):")
for k, q in enumerate(queries):
    cos_all = emb_sub @ qv[k]              # 전 세그 s_sub 코사인
    c_empty = float(emptyvec @ qv[k])
    pct = float((cos_all < c_empty).mean()) * 100
    is_max = c_empty >= cos_all.max() - 1e-6
    is_min = c_empty <= cos_all.min() + 1e-6
    tag = "  <<MAX" if is_max else ("  <<MIN" if is_min else "")
    print(f"  {q:20s} 빈자막코사인={c_empty:+.3f}  분포백분위={pct:4.0f}%  "
          f"[min={cos_all.min():+.3f} max={cos_all.max():+.3f}]{tag}")
