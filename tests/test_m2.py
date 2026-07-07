import numpy as np
from m2_keyframe import select_rep_frame, is_static

def _frame(v):  # 단색 8x8 그레이 프레임 (float 0~1)
    return np.full((8, 8), v, dtype=np.float32)

def test_rep_frame_picks_most_dynamic():
    # 프레임 3→4 사이 변화가 가장 큼 → rep_idx는 diff argmax + 1 = 4
    frames = [_frame(v) for v in (0.0, 0.05, 0.1, 0.15, 0.9, 0.9, 0.9)]
    rep_idx, score = select_rep_frame(frames, sigma=0.0)  # sigma=0: 평활 없이 순수 검증
    assert rep_idx == 4
    assert score > 0

def test_static_segment_falls_back_to_middle():
    frames = [_frame(0.5)] * 7                        # 완전 정적
    rep_idx, score = select_rep_frame(frames)
    assert score == 0.0
    assert is_static(score, threshold=0.05)
    # 정적 판정 시 호출부에서 중간 프레임으로 fallback (rep_idx는 그대로 반환)

def test_single_frame_segment():
    rep_idx, score = select_rep_frame([_frame(0.3)])  # 마지막 짧은 세그먼트
    assert rep_idx == 0 and score == 0.0

def test_motion_score_scale_independent_of_size():
    # 픽셀 수로 정규화되어야 threshold(0.05)가 해상도 무관하게 유효
    small = [_frame(0.0), _frame(1.0)]
    big = [np.full((64, 64), 0.0, np.float32), np.full((64, 64), 1.0, np.float32)]
    _, s1 = select_rep_frame(small); _, s2 = select_rep_frame(big)
    assert abs(s1 - s2) < 1e-6
