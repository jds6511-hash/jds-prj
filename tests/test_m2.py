import cv2
import numpy as np
from m2_keyframe import select_rep_frame, is_static, sample_segments_sequential

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


def _make_synthetic_video(path, fps=10, n_frames=40, size=8):
    # 프레임마다 값이 다른 8x8 단색 프레임 (1개 급변 지점 포함) — 순차/시크 결과 대조용
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(path), fourcc, fps, (size, size), isColor=True)
    for k in range(n_frames):
        v = 250 if k in (17, 33) else int(255 * (k % 7) / 6)   # 튀는 지점 삽입
        vw.write(np.full((size, size, 3), v, dtype=np.uint8))
    vw.release()


def _seek_based_reference(cap, start, end, fps_sample):
    # 기존 sample_frames 로직(세그먼트마다 매 샘플 시각을 개별 시크)을 그대로 재현 —
    # 새 순차 구현(sample_segments_sequential)과의 동등성 대조 기준선
    frames, t = [], start
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            frames.append((g, t))
        t += 1.0 / fps_sample
    return frames


def test_sequential_sampler_matches_seek_based_reference(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    _make_synthetic_video(video_path)
    segments = [
        {"idx": 0, "start": 0.0, "end": 1.5},
        {"idx": 1, "start": 1.5, "end": 3.0},
        {"idx": 2, "start": 3.0, "end": 4.0},
    ]
    fps_sample = 3

    cap_ref = cv2.VideoCapture(str(video_path))
    cap_new = cv2.VideoCapture(str(video_path))
    try:
        new_by_idx = {s["idx"]: samples for s, samples in sample_segments_sequential(cap_new, segments, fps_sample)}
        for seg in segments:
            ref = _seek_based_reference(cap_ref, seg["start"], seg["end"], fps_sample)
            new = new_by_idx[seg["idx"]]

            assert len(ref) == len(new)                    # 세그먼트별 샘플 수 일치
            assert [t for _, t in ref] == [t for _, t in new]  # 채택된 샘플 시각 일치

            ref_rep = select_rep_frame([g for g, _ in ref])
            new_rep = select_rep_frame([g for g, _ in new])
            assert ref_rep == new_rep                       # (rep_idx, motion_score) 완전 일치
    finally:
        cap_ref.release(); cap_new.release()


def test_sequential_sampler_segment_boundary_shares_frame(tmp_path):
    # 인접 세그먼트의 끝/시작 요청 시각이 같은 프레임 인덱스로 매핑되는 경계 케이스 —
    # fps=10, fps_sample=100이면 seg0의 t=1.00과 seg1의 t=1.005가 모두 프레임 10을 요청.
    # sample_segments_sequential 내부의 "같은 k로 재확인" 분기를 강제로 통과시킨다.
    video_path = tmp_path / "synthetic.mp4"
    _make_synthetic_video(video_path, fps=10, n_frames=25)
    segments = [
        {"idx": 0, "start": 0.0, "end": 1.005},
        {"idx": 1, "start": 1.005, "end": 2.0},
    ]
    fps_sample = 100

    cap_new = cv2.VideoCapture(str(video_path))
    fps = cap_new.get(cv2.CAP_PROP_FPS)
    assert int(1.00 * fps + 0.5) == int(1.005 * fps + 0.5)  # 전제: 실제로 같은 프레임을 요청

    cap_ref = cv2.VideoCapture(str(video_path))
    try:
        new_by_idx = {s["idx"]: samples for s, samples in sample_segments_sequential(cap_new, segments, fps_sample)}
        for seg in segments:
            ref = _seek_based_reference(cap_ref, seg["start"], seg["end"], fps_sample)
            new = new_by_idx[seg["idx"]]
            assert len(ref) == len(new)
            assert [t for _, t in ref] == [t for _, t in new]
            assert all(np.array_equal(rg, ng) for (rg, _), (ng, _) in zip(ref, new))  # 픽셀 단위 동일 프레임
    finally:
        cap_ref.release(); cap_new.release()
