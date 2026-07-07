"""M1 전처리: mp4 → audio.wav(16kHz mono) + segments.json(idx/start/end). [DESIGN_SPEC 4-1]"""
import argparse, math, subprocess, sys
from pathlib import Path
import cv2
import common


def make_segments(duration_sec: float, seg_len: int = 5) -> list[dict]:
    segs = []
    for start in range(0, math.ceil(duration_sec), seg_len):
        segs.append({"idx": len(segs), "start": start,
                     "end": min(start + seg_len, duration_sec)})
    return segs


def get_video_info(video_path) -> tuple[float, float]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"영상 열기 실패: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return n_frames / fps, fps


def extract_audio(video_path, out_wav, sr: int = 16000) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(video_path),
           "-vn", "-ac", "1", "-ar", str(sr), "-f", "wav", str(out_wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{r.stderr[-800:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)

    video = Path(cfg["paths"]["data"]) / "videos" / f"{args.video_id}.mp4"
    wdir = common.work_dir(cfg, args.video_id)
    wdir.mkdir(parents=True, exist_ok=True)
    seg_path = wdir / "segments.json"
    if seg_path.exists() and not args.force:
        print(f"이미 존재: {seg_path} (--force로 재생성)"); return

    duration, fps = get_video_info(video)
    extract_audio(video, wdir / "audio.wav")
    segs = make_segments(duration, cfg["seg_len_sec"])

    # 검증 포인트 [DESIGN_SPEC 4-1]
    assert len(segs) == math.ceil(duration / cfg["seg_len_sec"])
    assert abs(segs[-1]["end"] - duration) < 0.5

    common.save_segments(seg_path, {
        "video_id": args.video_id, "duration_sec": duration, "fps": fps,
        "n_segments": len(segs), "segments": segs})
    print(f"M1 완료: {len(segs)}개 세그먼트, duration={duration:.1f}s → {seg_path}")


if __name__ == "__main__":
    main()
