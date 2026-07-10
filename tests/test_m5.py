import json
import numpy as np
import pytest
import common
import m5_search
from m5_search import minmax, combine_scores, VideoIndex, search, search_with_stats

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
    # 이 17원소 값 배열은 quicksort와 stable의 argsort 결과가 실제로
    # 달라지는 것이 실험으로 확인된 픽스처다 (4원소 등 작은 배열에서는
    # 우연히 두 정렬 방식의 결과가 같아져 이 테스트가 kind="stable" 제거를
    # 잡아내지 못했음).
    vals = [0.0, 0.5, 0.0, 0.5, 0.5, 1.0, 0.0, 1.0, 0.0, 0.0,
            0.0, 1.0, 0.5, 1.0, 1.0, 0.0, 0.5]
    n = len(vals)
    q = np.array([1.0], dtype=np.float32)
    monkeypatch.setattr(m5_search, "embed_texts", lambda texts, model: np.array([q]))
    emb_sub = np.array(vals, dtype=np.float32).reshape(-1, 1)
    emb_cap = np.zeros_like(emb_sub)  # alpha=1.0이므로 무시됨
    video = VideoIndex(
        segments=[{"idx": i, "start": float(i * 5), "end": float(i * 5 + 5),
                   "subtitle": ""} for i in range(n)],
        emb_sub=emb_sub,
        emb_cap=emb_cap,
        static_mask=np.array([False] * n))
    # alpha=1.0 → score = minmax(s_sub) = s_sub (0/0.5/1.0 그대로) → 동일 점수 그룹 내
    # idx 오름차순이 stable argsort의 결정적 결과.
    results = search("query", video, alpha=1.0, cfg={"embed_model": "any-model"})
    expected = [5, 7, 11, 13, 14, 1, 3, 4, 12, 16, 0, 2, 6, 8, 9, 10, 15]
    assert [r.idx for r in results] == expected

def test_load_raises_on_n_segments_mismatch(tmp_path):
    # segments.json이 M4 이후 재생성됐는데 emb_*.npy가 갱신 안 된 경우 fail-fast [리뷰 반영]
    video_id = "v1"
    wdir = tmp_path / video_id
    wdir.mkdir()
    segments = [{"idx": i, "start": i * 5, "end": i * 5 + 5, "subtitle": "s",
                "caption": "c", "is_static": False, "motion_score": 0.1} for i in range(2)]
    common.save_segments(wdir / "segments.json", {"n_segments": 2, "segments": segments})
    np.save(wdir / "emb_sub.npy", np.zeros((2, 4), dtype=np.float32))
    np.save(wdir / "emb_cap.npy", np.zeros((2, 4), dtype=np.float32))
    (wdir / "meta.json").write_text(
        json.dumps({"embed_model": "m", "dim": 4, "n_segments": 3}), encoding="utf-8")
    cfg = {"embed_model": "m", "paths": {"work": str(tmp_path)}, "seg_len_sec": 5,
           "static_threshold": 0.05}
    with pytest.raises(ValueError, match="세그먼트 수 불일치"):
        VideoIndex.load(cfg, video_id)

def test_search_with_stats_matches_search_ranking_and_raw_stats(monkeypatch):
    # search_with_stats는 search와 동일 랭킹을 반환하고, 정규화 이전 raw 코사인
    # 통계(min-max 정규화로 가려지는 무관련 질의 판정 근거)를 함께 준다 [HIGH-2].
    q = np.array([1.0, 0.0], dtype=np.float32)
    monkeypatch.setattr(m5_search, "embed_texts", lambda texts, model: np.array([q]))
    emb_sub = np.array([[0.5, 0.5], [0.9, 0.1], [0.2, 0.8]], dtype=np.float32)
    emb_cap = np.array([[0.1, 0.9], [0.3, 0.7], [0.6, 0.4]], dtype=np.float32)
    video = VideoIndex(
        segments=[{"idx": i, "start": float(i * 5), "end": float(i * 5 + 5),
                   "subtitle": ""} for i in range(3)],
        emb_sub=emb_sub, emb_cap=emb_cap,
        static_mask=np.array([False, False, False]))
    cfg = {"embed_model": "any-model"}
    results_a = search("query", video, alpha=0.5, cfg=cfg)
    results_b, stats = search_with_stats("query", video, alpha=0.5, cfg=cfg)
    assert results_a == results_b                    # (a) 동일 랭킹
    s_sub = emb_sub @ q
    s_cap = emb_cap @ q
    assert stats == {                                 # (b) 손계산 코사인과 일치
        "raw_sub_max": pytest.approx(float(s_sub.max())),
        "raw_sub_mean": pytest.approx(float(s_sub.mean())),
        "raw_cap_max": pytest.approx(float(s_cap.max())),
        "raw_cap_mean": pytest.approx(float(s_cap.mean()))}

def test_load_raises_friendly_error_when_meta_missing(tmp_path):
    # meta.json만 없는 부분 산출물(중단된 M4 실행) → 친절한 FileNotFoundError,
    # read_text의 원시 에러가 아니라 "run m4_index.py first" 메시지여야 함 [리뷰 반영]
    video_id = "v1"
    wdir = tmp_path / video_id
    wdir.mkdir()
    segments = [{"idx": i, "start": i * 5, "end": i * 5 + 5, "subtitle": "s",
                "caption": "c", "is_static": False, "motion_score": 0.1} for i in range(2)]
    common.save_segments(wdir / "segments.json", {"n_segments": 2, "segments": segments})
    np.save(wdir / "emb_sub.npy", np.zeros((2, 4), dtype=np.float32))
    np.save(wdir / "emb_cap.npy", np.zeros((2, 4), dtype=np.float32))
    cfg = {"embed_model": "m", "paths": {"work": str(tmp_path)}, "seg_len_sec": 5,
           "static_threshold": 0.05}
    with pytest.raises(FileNotFoundError, match="run m4_index.py first"):
        VideoIndex.load(cfg, video_id)

def _static_threshold_fixture(tmp_path, video_id="v1"):
    wdir = tmp_path / video_id
    wdir.mkdir()
    segments = [
        {"idx": 0, "start": 0, "end": 5, "subtitle": "s", "caption": "c",
         "is_static": True, "motion_score": 0.02},
        {"idx": 1, "start": 5, "end": 10, "subtitle": "s", "caption": "c",
         "is_static": False, "motion_score": 0.08},
        {"idx": 2, "start": 10, "end": 15, "subtitle": "s", "caption": "c",
         "is_static": False, "motion_score": 0.01}]
    common.save_segments(wdir / "segments.json", {"n_segments": 3, "segments": segments})
    np.save(wdir / "emb_sub.npy", np.zeros((3, 4), dtype=np.float32))
    np.save(wdir / "emb_cap.npy", np.zeros((3, 4), dtype=np.float32))
    (wdir / "meta.json").write_text(
        json.dumps({"embed_model": "m", "dim": 4, "n_segments": 3}), encoding="utf-8")
    return wdir

def test_load_static_threshold_recomputes_mask_and_file_unchanged(tmp_path):
    # [DESIGN_SPEC 8-5(2)] static_threshold 지정 시 motion_score<thr로 static_mask
    # 재계산. segments.json은 읽기 전용(파일 내용·mtime 불변).
    video_id = "v1"
    wdir = _static_threshold_fixture(tmp_path, video_id)
    cfg = {"embed_model": "m", "paths": {"work": str(tmp_path)}, "seg_len_sec": 5,
           "static_threshold": 0.0}   # 인자 지정이 config보다 우선함도 함께 검증
    before_mtime = (wdir / "segments.json").stat().st_mtime
    before_content = (wdir / "segments.json").read_text(encoding="utf-8")

    video = VideoIndex.load(cfg, video_id, static_threshold=0.05)

    # motion_score < 0.05 → idx0(0.02) True, idx1(0.08) False, idx2(0.01) True
    assert list(video.static_mask) == [True, False, True]
    # 저장된 is_static은 그대로(재계산 결과와 다름) — segments.json 읽기 전용 확인
    assert [s["is_static"] for s in video.segments] == [True, False, False]
    assert (wdir / "segments.json").stat().st_mtime == before_mtime
    assert (wdir / "segments.json").read_text(encoding="utf-8") == before_content

def test_load_static_threshold_none_uses_config_value(tmp_path):
    # static_threshold=None(기본)이면 config 값으로 motion_score에서 재판정 —
    # 저장된 is_static(M2 당시 threshold 산물)은 무시된다 [8-5(2) 확장, 2026-07-11]
    video_id = "v1"
    _static_threshold_fixture(tmp_path, video_id)
    cfg = {"embed_model": "m", "paths": {"work": str(tmp_path)}, "seg_len_sec": 5,
           "static_threshold": 0.05}
    video = VideoIndex.load(cfg, video_id)
    # motion_score < 0.05 → [0.02, 0.08, 0.01] = [True, False, True]
    # (저장된 is_static은 [True, False, False]로 이와 다름 — 무시됨을 증명)
    assert list(video.static_mask) == [True, False, True]


def test_load_static_threshold_zero_disables_substitution(tmp_path):
    # config static_threshold=0이면 모든 세그먼트 비정적 → 치환 off [ablation 2-4-2 확정]
    video_id = "v1"
    _static_threshold_fixture(tmp_path, video_id)
    cfg = {"embed_model": "m", "paths": {"work": str(tmp_path)}, "seg_len_sec": 5,
           "static_threshold": 0}
    video = VideoIndex.load(cfg, video_id)
    assert list(video.static_mask) == [False, False, False]
