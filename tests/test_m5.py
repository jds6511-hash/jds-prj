import json
import numpy as np
import pytest
import common
import m5_search
from m5_search import minmax, combine_scores, VideoIndex, search

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

def test_tied_scores_rank_by_lower_idx_first(monkeypatch):
    # 재현성 계약: search()의 랭킹은 동률 점수를 낮은 idx 우선으로
    # 결정적으로 정렬한다 (argsort kind="stable"). 실제 모델 로드는 피하고
    # embed_texts를 고정 벡터로 대체해 search()의 정렬 로직 자체를 검증한다.
    q = np.array([1.0, 0.0], dtype=np.float32)
    monkeypatch.setattr(m5_search, "embed_texts", lambda texts, model: np.array([q]))
    emb_sub = np.array([[0.5, 0.0], [0.9, 0.0], [0.5, 0.0], [0.9, 0.0]], dtype=np.float32)
    video = VideoIndex(
        segments=[{"start": float(i * 5), "end": float(i * 5 + 5)} for i in range(4)],
        emb_sub=emb_sub,
        emb_cap=emb_sub.copy(),
        static_mask=np.array([False, False, False, False]))
    # alpha=1.0 → score = minmax(s_sub) = [0, 1, 0, 1] → 동률: (idx1,idx3)=1, (idx0,idx2)=0
    results = search("query", video, alpha=1.0, cfg={"embed_model": "any-model"})
    assert [r.idx for r in results] == [1, 3, 0, 2]

def test_load_raises_on_n_segments_mismatch(tmp_path):
    # segments.json이 M4 이후 재생성됐는데 emb_*.npy가 갱신 안 된 경우 fail-fast [리뷰 반영]
    video_id = "v1"
    wdir = tmp_path / video_id
    wdir.mkdir()
    segments = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
                "subtitle": "s", "caption": "c", "is_static": False} for i in range(2)]
    common.save_segments(wdir / "segments.json", {"n_segments": 2, "segments": segments})
    np.save(wdir / "emb_sub.npy", np.zeros((2, 4), dtype=np.float32))
    np.save(wdir / "emb_cap.npy", np.zeros((2, 4), dtype=np.float32))
    (wdir / "meta.json").write_text(
        json.dumps({"embed_model": "m", "dim": 4, "n_segments": 3}), encoding="utf-8")
    cfg = {"embed_model": "m", "paths": {"work": str(tmp_path)}}
    with pytest.raises(ValueError, match="세그먼트 수 불일치"):
        VideoIndex.load(cfg, video_id)
