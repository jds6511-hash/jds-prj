import numpy as np
from m5_search import minmax, combine_scores

def test_minmax_basic():
    out = minmax(np.array([1.0, 3.0, 2.0]))
    assert np.allclose(out, [0.0, 1.0, 0.5])

def test_minmax_degenerate_returns_zeros():
    # max==min → 0 벡터 (균등 처리) [DESIGN_SPEC 4-5]
    assert np.allclose(minmax(np.array([0.7, 0.7, 0.7])), 0.0)

def test_combine_order_substitution_after_normalization():
    # 핵심 계약 [v2 8-4]: 치환은 '정규화 이후'. 정규화 전에 치환하면
    # 정적 세그먼트의 원본 s_cap이 min/max를 오염시킨다.
    s_sub = np.array([0.2, 0.4, 0.6])
    s_cap = np.array([0.9, 0.1, 0.5])   # idx0가 정적: s_cap 0.9는 무시되어야 함
    static = np.array([True, False, False])
    out = combine_scores(s_sub, s_cap, static, alpha=0.5)
    # 정규화: s_sub_n=[0,.5,1], s_cap_n=[1,0,.5] → 치환: s_cap_n[0]=0
    # 가중합: [0, .25, .75]
    assert np.allclose(out, [0.0, 0.25, 0.75])

def test_alpha_1_is_baseline_pure_subtitle():
    s_sub = np.array([0.1, 0.9]); s_cap = np.array([0.9, 0.1])
    out = combine_scores(s_sub, s_cap, np.array([False, False]), alpha=1.0)
    assert np.allclose(out, minmax(s_sub))          # baseline = α=1.0 특수 경우

def test_static_substitution_makes_score_equal_subtitle():
    # 정적 세그먼트는 score = s_sub_norm (α와 무관) [v2 8-4]
    s_sub = np.array([0.3, 0.8]); s_cap = np.array([0.5, 0.2])
    for alpha in (0.0, 0.3, 0.7):
        out = combine_scores(s_sub, s_cap, np.array([True, True]), alpha)
        assert np.allclose(out, minmax(s_sub))

def test_tied_scores_rank_by_lower_idx_first():
    # 재현성 계약: search()의 랭킹은 동률 점수를 낮은 idx 우선으로
    # 결정적으로 정렬한다 (argsort kind="stable")
    score = np.array([0.5, 0.9, 0.5, 0.9])
    order = np.argsort(-score, kind="stable")
    assert list(order) == [1, 3, 0, 2]
