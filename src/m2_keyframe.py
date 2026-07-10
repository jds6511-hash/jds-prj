"""M2 대표 프레임 선택: SMART STC 1단계 차용(차분 L2 → 가우시안 평활 → argmax).
정적 세그먼트는 중간 프레임 fallback + is_static 기록. [DESIGN_SPEC 4-2, v2 2장·8-4]"""
import argparse
from pathlib import Path
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
import common


def select_rep_frame(frames: list, sigma: float = 1.0) -> tuple[int, float]:
    """returns (rep_idx, motion_score). motion_score = 인접 차분 RMS 평균(픽셀 정규화)."""
    if len(frames) < 2:
        return 0, 0.0
    diffs = np.array([
        float(np.sqrt(np.mean((frames[i] - frames[i - 1]) ** 2)))
        for i in range(1, len(frames))])
    motion_score = float(diffs.mean())
    if sigma > 0:
        diffs = gaussian_filter1d(diffs, sigma=sigma)   # 지터 억제 [v2 2장]
    rep_idx = int(np.argmax(diffs)) + 1
    return rep_idx, motion_score


def is_static(motion_score: float, threshold: float) -> bool:
    return motion_score < threshold


def _request_grid(start: float, end: float, fps_sample: float, fps: float) -> tuple:
    """[start, end)에서 fps_sample 간격의 요청 시각과, 각 시각이 CAP_PROP_POS_MSEC 시크로
    매핑되는 프레임 인덱스를 함께 반환한다 (기존 sample_frames와 동일한 시각 그리드).

    실측(FFmpeg 백엔드): POS_MSEC 시크는 "t 이상인 첫 프레임"이 아니라 "t*fps에 가장 가까운
    프레임"(round-half-up: floor(t*fps+0.5))을 반환한다 — 순차 디코딩에서 같은 프레임을
    골라내려면 이 반올림 규칙을 그대로 재현해야 한다(동등성 검증으로 실증).
    """
    ts, idxs, t = [], [], start
    while t < end:
        ts.append(t)
        idxs.append(int(t * fps + 0.5))     # round-half-up (t*fps는 항상 >= 0)
        t += 1.0 / fps_sample
    return ts, idxs


def sample_segments_sequential(cap, segments: list, fps_sample: float):
    """영상 1회 순차 디코딩(cap.read())으로 세그먼트를 완성되는 순서대로 yield하는 제너레이터.

    기존 sample_frames는 세그먼트마다 시각 t=start+j/fps_sample로 랜덤 시크
    (CAP_PROP_POS_MSEC)했다 — 26분 영상 기준 약 5,000회 시크가 병목 [설계점검 HIGH-1].
    여기서는 프레임을 순서대로 읽으며 각 요청 시각이 매핑되는 프레임 인덱스(_request_grid)에
    도달하면 그 프레임을 샘플로 채택한다. 세그먼트가 완성되는 즉시 (seg, samples)를
    yield하므로, 호출부는 그 자리에서 select_rep_frame을 호출하고 그레이스케일 버퍼를
    버릴 수 있다 — 영상 전체 프레임을 메모리에 쌓지 않는다.
    yield: (seg, [(gray, t), ...]) — 기존 sample_frames가 반환하던 (gray, t) 튜플 리스트.
    """
    fps = cap.get(cv2.CAP_PROP_FPS)
    seg_iter = iter(segments)
    seg = next(seg_iter, None)
    if seg is None:
        return

    ts, idxs = _request_grid(seg["start"], seg["end"], fps_sample, fps)
    pi, cur, k = 0, [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        g = None
        while True:
            while pi < len(idxs) and idxs[pi] == k:
                if g is None:
                    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
                cur.append((g, ts[pi]))
                pi += 1
            if pi < len(idxs):
                break                        # 이 세그먼트의 다음 목표 프레임은 아직 미도달
            yield seg, cur
            seg = next(seg_iter, None)
            if seg is None:
                return
            ts, idxs = _request_grid(seg["start"], seg["end"], fps_sample, fps)
            pi, cur = 0, []
            # 세그먼트 경계가 같은 프레임에 걸릴 수 있으므로 같은 k로 재확인
        k += 1
    # 영상 조기 종료 — 기존과 동일하게 남은 세그먼트는 샘플 없이(또는 부분만) 처리
    yield seg, cur
    for remaining in seg_iter:
        yield remaining, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)

    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json", seg_len=cfg["seg_len_sec"])
    if "rep_frame" in doc["segments"][0] and not args.force:
        print("이미 완료 (--force로 재생성)"); return

    video = Path(cfg["paths"]["data"]) / "videos" / f"{args.video_id}.mp4"
    frames_dir = wdir / "frames"; frames_dir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(str(video))

    n_static = 0
    t_reps = {}
    for seg, sampled in sample_segments_sequential(cap, doc["segments"], cfg["frame_sample_fps"]):
        grays = [g for g, _ in sampled]
        rep_idx, motion = select_rep_frame(grays, cfg["gaussian_sigma"])
        static = is_static(motion, cfg["static_threshold"])
        if static:
            rep_idx = len(sampled) // 2               # 중간 프레임 fallback [v2 2장]
            n_static += 1
        t_reps[seg["idx"]] = sampled[rep_idx][1] if sampled else seg["start"]
        seg["is_static"] = static
        seg["motion_score"] = round(motion, 6)

    # 2차 통과: 대표 프레임만 시크로 읽어 컬러 저장 (세그먼트 수만큼 — 무해, [설계점검 HIGH-1])
    for seg in doc["segments"]:
        cap.set(cv2.CAP_PROP_POS_MSEC, t_reps[seg["idx"]] * 1000)
        ok, color = cap.read()
        out = frames_dir / f"seg_{seg['idx']:04d}.jpg"
        if not ok or not cv2.imwrite(str(out), color):
            raise RuntimeError(f"프레임 저장 실패: seg {seg['idx']}")
        seg["rep_frame"] = f"frames/seg_{seg['idx']:04d}.jpg"
    cap.release()

    ratio = n_static / doc["n_segments"]
    print(f"M2 완료: is_static 비율 {ratio:.1%} ({n_static}/{doc['n_segments']})")
    if ratio > 0.5:
        print("⚠️ is_static 비율 50% 초과 — static_threshold 재검토 필요 [DESIGN_SPEC 4-2]")
    common.save_segments(wdir / "segments.json", doc)


if __name__ == "__main__":
    main()
