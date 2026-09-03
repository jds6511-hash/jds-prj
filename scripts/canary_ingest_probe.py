"""신규 영상 canary — M1→M2→M3 실행 특성 측정. **성능 실험이 아니다.**

```
목적    3분 고정 구간으로 wall time · VRAM · 산출물 상태 분포를 재고,
        전체 실행 시간을 추정할 근거를 만든다
아님    프롬프트·threshold·모델 튜닝. 결과를 보고 config를 고쳐 재실행하지 않는다
```

격리 규약을 지킨다.

```
config      config.yaml에서 **재생성** (수동 편집 금지)
paths       work_canary/ · results_canary/ — 본 인덱스와 분리 (.gitignore 대상)
provenance  data/provenance/videos.json에 먼저 기록해야 M1이 돈다.
            이 스크립트는 clip의 sha256을 계산해 항목을 추가한다.
            source_id에 구간을 붙여 원본 전체와 구분한다.
```

실행:

    python scripts/canary_ingest_probe.py \\
        --url https://www.youtube.com/watch?v=<id> --start 600 --duration 180
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml                                                   # noqa: E402

import common                                                 # noqa: E402

CONFIG_TEMPLATE = ROOT / "config.yaml"
CANARY_CONFIG = ROOT / "config_canary.yaml"
REGISTRY = ROOT / "data/provenance/videos.json"
VIDEO_DIR = ROOT / "data/videos"


def run(cmd, label, log):
    """한 단계를 돌리고 벽시계 시간을 남긴다. 실패는 그대로 올린다."""
    started = time.time()
    print("=== %s 시작 (%s) ===" % (label, time.strftime("%H:%M:%S")), flush=True)
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    seconds = round(time.time() - started, 1)
    log[label] = {"seconds": seconds, "returncode": result.returncode,
                  "tail": result.stdout[-600:] + result.stderr[-600:]}
    print("=== %s 완료 %ss rc=%d ===" % (label, seconds, result.returncode),
          flush=True)
    if result.returncode != 0:
        raise SystemExit("%s 실패 (rc=%d)" % (label, result.returncode))
    return seconds


def download_clip(url, start, duration, target: Path, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    source = work / "source.mp4"
    if not source.exists():
        subprocess.run(
            ["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
             "--no-warnings", "-o", str(source), url],
            cwd=ROOT, check=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start), "-t", str(duration), "-i", str(source),
         "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(target)],
        cwd=ROOT, check=True, capture_output=True)
    return target


def register(video_id: str, url: str, source_id: str, clip: Path) -> dict:
    """provenance를 **먼저** 기록한다. 값을 추측해 채우지 않는다."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entry = {
        "source_url": url,
        "source_id": source_id,
        "file_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
    }
    registry["videos"][video_id] = entry
    REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return entry


def write_config() -> Path:
    """config.yaml에서 재생성한다 — 손으로 고친 사본을 쓰지 않는다."""
    config = yaml.safe_load(CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    config["paths"] = {**config["paths"], "work": "work_canary",
                       "results": "results_canary"}
    CANARY_CONFIG.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return CANARY_CONFIG


def characterize(video_id: str) -> dict:
    """산출물 상태 분포. 판정하지 않고 센다."""
    config = common.load_config(CANARY_CONFIG)
    path = common.work_dir(config, video_id) / "segments.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    segments = document["segments"]

    corrupted = [s["idx"] for s in segments
                 if s.get("caption")
                 and common.is_corrupted_caption(s["caption"])]
    credits = [s["idx"] for s in segments
               if s.get("subtitle")
               and common.is_subtitle_credit(s["subtitle"])]
    return {
        "n_segments": document["n_segments"],
        "duration_sec": document["duration_sec"],
        "provenance": document.get("provenance"),
        "subtitle_nonempty": sum(1 for s in segments if (s.get("subtitle") or "").strip()),
        "caption_nonempty": sum(1 for s in segments if (s.get("caption") or "").strip()),
        "caption_corrupted": corrupted,
        "subtitle_credit": credits,
        "caption_chars_mean": round(
            sum(len(s.get("caption") or "") for s in segments) / len(segments), 1),
        "samples": [{"idx": s["idx"], "subtitle": s.get("subtitle"),
                     "caption": s.get("caption")} for s in segments[:5]],
    }


def gpu_peak_mib() -> int:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True)
    return int(out.stdout.strip().splitlines()[0]) if out.returncode == 0 else -1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--out", default="runs/canary/canary_probe.json")
    args = parser.parse_args()

    video_id = "canary_%s_%d_%d" % (args.source_id, args.start,
                                    args.start + args.duration)
    scratch = ROOT / "work_canary" / "_download"
    clip = VIDEO_DIR / ("%s.mp4" % video_id)

    log = {"video_id": video_id, "url": args.url,
           "clip": {"start": args.start, "duration": args.duration},
           "steps": {}}

    if not clip.exists():
        download_clip(args.url, args.start, args.duration, clip, scratch)
    log["clip"]["bytes"] = clip.stat().st_size
    log["provenance_entry"] = register(
        video_id, args.url,
        "%s#%d-%d" % (args.source_id, args.start, args.start + args.duration),
        clip)
    config = write_config()

    log["gpu_before_mib"] = gpu_peak_mib()
    for label, module in (("M1", "m1_preprocess"), ("M2", "m2_keyframe"),
                          ("M3", "m3_generate")):
        run([sys.executable, str(ROOT / "src" / ("%s.py" % module)),
             "--config", str(config), "--video-id", video_id],
            label, log["steps"])
        log["steps"][label]["gpu_after_mib"] = gpu_peak_mib()

    log["characterization"] = characterize(video_id)
    total = sum(step["seconds"] for step in log["steps"].values())
    log["total_seconds"] = round(total, 1)
    log["projection_2424s_hours"] = round(total * (2424 / args.duration) / 3600, 2)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print("보고서: %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
