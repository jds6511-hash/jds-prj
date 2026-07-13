# 한계1(동의어 갭) 처방 실증: 사전 기반 질의 확장 + max 풀링 프로토타입
# 본 시스템 미반영(dev 프로브) — 정식 반영은 dev 검증→승인→test 재평가 절차 필요.
# 근거: 질의 '초밥'은 스시 캡션 세그(82)를 21위로 놓치지만 '스시'로는 1위(2026-07-13 실측).
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import numpy as np
import common
from m4_index import embed_texts
from m5_search import VideoIndex, combine_scores

SYNONYMS = {"초밥": ["스시"], "스시": ["초밥"]}  # 프로토타입용 최소 사전

def search_expanded(query, vi, alpha, cfg, level="score"):
    """level='score': 변형별 (정규화+결합) 점수의 max — 변형 간 정규화 스케일이 섞임.
    level='raw': 채널별 raw 코사인을 변형 간 max 풀링 후 단일 정규화+결합 — 동일
    임베딩 공간의 코사인이라 스케일이 호환되고, 기존 combine_scores 경로를 그대로 탄다."""
    variants = [query] + SYNONYMS.get(query, [])
    qs = [embed_texts([v], cfg["embed_model"])[0] for v in variants]
    if level == "raw":
        s_sub = np.max(np.stack([vi.emb_sub @ q for q in qs]), axis=0)
        s_cap = np.max(np.stack([vi.emb_cap @ q for q in qs]), axis=0)
        final = combine_scores(s_sub, s_cap, vi.static_mask, alpha)
    else:
        scores = [combine_scores(vi.emb_sub @ q, vi.emb_cap @ q, vi.static_mask, alpha)
                  for q in qs]
        final = np.max(np.stack(scores), axis=0)
    return list(np.argsort(-final, kind="stable")), variants

cfg = common.load_config("config.yaml")
alpha = json.load(open("results/alpha_search_dev.json", encoding="utf-8"))["alpha_star"]
vi = VideoIndex.load(cfg, "pland_costco_hosting")
GT_SUSHI = 82  # 6:50~6:55 코스트코 초밥 매대(프레임 실물 확인, 2026-07-13)

print("질의        | 확장 전 | score풀링 | raw풀링 | 변형")
for q in ("초밥", "새우전을 부치는 장면", "가방"):  # 뒤 2개 = 사전 미적중 대조군
    qv = embed_texts([q], cfg["embed_model"])[0]
    s0 = combine_scores(vi.emb_sub @ qv, vi.emb_cap @ qv, vi.static_mask, alpha)
    order0 = list(np.argsort(-s0, kind="stable"))
    order_s, variants = search_expanded(q, vi, alpha, cfg, level="score")
    order_r, _ = search_expanded(q, vi, alpha, cfg, level="raw")
    r0 = order0.index(GT_SUSHI) + 1
    rs = order_s.index(GT_SUSHI) + 1
    rr = order_r.index(GT_SUSHI) + 1
    same = order0[:10] == order_r[:10]
    tag = f"top10 동일={same}" if len(variants) == 1 else ""
    print(f"{q:12s} | {r0:3d} | {rs:3d} | {rr:3d} | {variants} {tag}")
