"""AV1 입력을 H.264로 변환한다 — **서버 cv2가 AV1을 디코드하지 못하기 때문이다.**

2026-08-21 P2 FULL이 m2에서 죽었다. 원인은 파일 손상이 아니라 코덱이다.

```
서버 ffmpeg CLI      libdav1d 있음 — AV1 디코드 가능
서버 cv2 5.0.0       내장 FFmpeg에 AV1 소프트웨어 디코더 없음.
                     OPENCV_FFMPEG_CAPTURE_OPTIONS(hwaccel;none · video_codec;libdav1d)로
                     우회되지 않는다 (실측)
결과                 AV1 영상에서 `cap.read()`가 전부 False → "프레임 저장 실패: seg 0"
```

그래서 **AV1인 것만** 시스템 ffmpeg으로 H.264로 옮긴다. 지켜야 할 것 넷.

```
1  원본을 지우지 않는다 — `<id>.av1source.mp4`로 남긴다
2  오디오는 재인코딩하지 않는다(`-c:a copy`) — STT 입력이 바뀌면 자막이 달라진다
3  프레임 타이밍을 그대로 옮긴다(`-fps_mode passthrough`)
4  **변환 후 n_segments가 사전등록값과 같아야 한다** — 다르면 되돌리고 멈춘다
```

두 arm은 **같은 변환 결과**를 입력으로 받으므로 arm 대조는 영향받지 않는다. 다만 이
4편(기확보분)은 출처 해시가 없는 legacy_exempt이고, 변환본의 해시를 새로 기록한다 —
과거 값을 추측해 채우지 않는다.
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import provenance as PV                                           # noqa: E402

SELECTED_REL = "docs/P2_선정표본_2026-08-20.json"
SUFFIX = ".av1source.mp4"
SEG_LEN = 5
# 화질 손실을 캡션에 옮기지 않도록 낮은 crf를 쓴다. veryslow는 필요 없다 —
# 목적은 압축률이 아니라 디코드 가능성이다.
VCODEC = ["-c:v", "libx264", "-crf", "16", "-preset", "medium",
          "-pix_fmt", "yuv420p", "-fps_mode", "passthrough"]
ACODEC = ["-c:a", "copy"]


class TranscodeError(RuntimeError):
    pass


def probe_codec(path) -> str:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
        capture_output=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def cv2_segments(path) -> tuple:
    """m1과 **같은 경로**로 잰다 — ffprobe duration이 아니라 cv2 frame_count/fps다."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise TranscodeError(f"cv2가 열지 못한다: {path}")
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    ok, _ = cap.read()
    cap.release()
    if not fps:
        raise TranscodeError(f"fps를 읽지 못한다: {path}")
    dur = n / fps
    return dur, fps, math.ceil(dur / SEG_LEN), ok


def transcode(video: Path, expected_segments: int) -> dict:
    src_backup = video.with_name(video.stem + SUFFIX)
    out_tmp = video.with_name(video.stem + ".h264.tmp.mp4")
    row = {"video_id": video.stem, "codec_before": probe_codec(video),
           "sha256_before": PV.sha256_file(video)}
    if row["codec_before"] != "av1":
        row["status"] = "skipped_not_av1"
        return row
    if src_backup.exists():
        raise TranscodeError(f"{src_backup.name}가 이미 있다 — 두 번 변환하지 않는다")

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(video), *VCODEC, *ACODEC, str(out_tmp)]
    row["ffmpeg_cmd"] = " ".join(cmd)
    r = subprocess.run(cmd)
    if r.returncode != 0 or not out_tmp.is_file():
        out_tmp.unlink(missing_ok=True)
        raise TranscodeError(f"{video.name}: ffmpeg 실패 rc={r.returncode}")

    dur, fps, segs, readable = cv2_segments(out_tmp)
    row.update({"duration_sec": round(dur, 2), "fps": fps,
                "n_segments_after": segs,
                "n_segments_expected": expected_segments,
                "cv2_readable": bool(readable)})
    if not readable:
        out_tmp.unlink(missing_ok=True)
        raise TranscodeError(f"{video.name}: 변환본도 cv2가 못 읽는다")
    if segs != expected_segments:
        # 구간 격자가 바뀌면 사전등록된 표집틀 검증값과 어긋난다 — 되돌린다
        out_tmp.unlink(missing_ok=True)
        raise TranscodeError(
            f"{video.name}: 변환 후 n_segments {segs} != 사전등록 {expected_segments} "
            f"— 되돌렸다. 이 상태로 색인하지 않는다")

    video.replace(src_backup)
    out_tmp.replace(video)
    row["sha256_after"] = PV.sha256_file(video)
    row["source_kept_as"] = src_backup.name
    row["codec_after"] = probe_codec(video)
    row["status"] = "transcoded"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", default=SELECTED_REL)
    ap.add_argument("--videos", default="data/videos")
    ap.add_argument("--out")
    a = ap.parse_args()
    sel = json.loads((ROOT / a.selected).read_text(encoding="utf-8"))["selected"]
    vdir = ROOT / a.videos
    rows = []
    for r in sel:
        f = vdir / f"{r['source_id']}.mp4"
        if not f.is_file():
            rows.append({"video_id": r["source_id"], "status": "missing"})
            continue
        rows.append(transcode(f, r["n_segments"]))
    rep = {"n_checked": len(rows),
           "transcoded": sum(1 for x in rows if x.get("status") == "transcoded"),
           "skipped": sum(1 for x in rows if x.get("status") == "skipped_not_av1"),
           "rows": rows,
           "reason": ("서버 cv2 5.0.0이 AV1을 디코드하지 못한다 — 파일 손상이 아니다"),
           "note": ("두 arm이 같은 변환본을 입력으로 받으므로 arm 대조는 영향받지 "
                    "않는다. 원본은 .av1source.mp4로 보존한다")}
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"checked {rep['n_checked']}  transcoded {rep['transcoded']}  "
          f"skipped(not av1) {rep['skipped']}")
    for x in rows:
        if x.get("status") == "transcoded":
            print(f"  {x['video_id']}: av1 → {x['codec_after']} · "
                  f"segments {x['n_segments_after']} (기대 {x['n_segments_expected']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
