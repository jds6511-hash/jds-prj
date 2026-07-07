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


def sample_frames(cap, start: float, end: float, fps_sample: float) -> list:
    """[start, end)에서 fps_sample 간격으로 그레이스케일 float(0~1) 프레임 샘플."""
    frames, t = [], start
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            frames.append((g, t))
        t += 1.0 / fps_sample
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)

    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json")
    if "rep_frame" in doc["segments"][0] and not args.force:
        print("이미 완료 (--force로 재생성)"); return

    video = Path(cfg["paths"]["data"]) / "videos" / f"{args.video_id}.mp4"
    frames_dir = wdir / "frames"; frames_dir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(str(video))

    n_static = 0
    for seg in doc["segments"]:
        sampled = sample_frames(cap, seg["start"], seg["end"], cfg["frame_sample_fps"])
        grays = [g for g, _ in sampled]
        rep_idx, motion = select_rep_frame(grays, cfg["gaussian_sigma"])
        static = is_static(motion, cfg["static_threshold"])
        if static:
            rep_idx = len(sampled) // 2               # 중간 프레임 fallback [v2 2장]
            n_static += 1
        # 저장은 컬러 원본으로 다시 읽음
        t_rep = sampled[rep_idx][1] if sampled else seg["start"]
        cap.set(cv2.CAP_PROP_POS_MSEC, t_rep * 1000)
        ok, color = cap.read()
        out = frames_dir / f"seg_{seg['idx']:04d}.jpg"
        if ok:
            cv2.imwrite(str(out), color)
        if not out.exists():
            raise RuntimeError(f"프레임 저장 실패: seg {seg['idx']}")
        seg["rep_frame"] = f"frames/seg_{seg['idx']:04d}.jpg"
        seg["is_static"] = static
        seg["motion_score"] = round(motion, 6)
    cap.release()

    ratio = n_static / doc["n_segments"]
    print(f"M2 완료: is_static 비율 {ratio:.1%} ({n_static}/{doc['n_segments']})")
    if ratio > 0.5:
        print("⚠️ is_static 비율 50% 초과 — static_threshold 재검토 필요 [DESIGN_SPEC 4-2]")
    common.save_segments(wdir / "segments.json", doc)


if __name__ == "__main__":
    main()
