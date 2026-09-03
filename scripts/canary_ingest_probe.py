"""신규 영상 ingest probe — M1→M2→M3 실행 특성 측정. **성능 실험이 아니다.**

```
목적    wall time · VRAM · 산출물 상태 분포를 재고 기록한다
        canary(고정 구간)와 본 실행(전체) 모두 이 스크립트로 돈다
아님    프롬프트·threshold·모델 튜닝. 결과를 보고 config를 고쳐 재실행하지 않는다
```

격리 규약을 지킨다.

```
config      config.yaml에서 **재생성** (수동 편집 금지)
paths       work_<namespace>/ · results_<namespace>/ — 본 인덱스와 분리 (.gitignore 대상)
            canary 산출물을 본 실행이 덮어쓰지 않는다
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
import re
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml                                                   # noqa: E402

import common                                                 # noqa: E402
from v2_1_sanitation import normalize_for_counting            # noqa: E402

CONFIG_TEMPLATE = ROOT / "config.yaml"
REGISTRY = ROOT / "data/provenance/videos.json"
VIDEO_DIR = ROOT / "data/videos"

#: canary에서 관측된 문구. **필터가 아니다** — 본 실행에서 몇 번 나오는지만 센다.
OBSERVED_STRINGS = ("오븐에 2분간 구워주세요", "크림치즈를 넣어주세요")


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


def download_full(url, target: Path, work: Path) -> Path:
    """영상 전체를 그대로 쓴다. 재인코딩하지 않는다."""
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
         "--no-warnings", "--merge-output-format", "mp4", "-o", str(target), url],
        cwd=ROOT, check=True)
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


def write_config(namespace: str) -> Path:
    """config.yaml에서 재생성한다 — 손으로 고친 사본을 쓰지 않는다."""
    config = yaml.safe_load(CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    config["paths"] = {**config["paths"],
                       "work": "work_%s" % namespace,
                       "results": "results_%s" % namespace}
    target = ROOT / ("config_%s.yaml" % namespace)
    target.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return target


class GpuPoll:
    """실행 내내 VRAM·이용률을 주기적으로 적는다. config·모델을 건드리지 않는다."""

    def __init__(self, path: Path, interval: float = 5.0):
        self.path = path
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self.samples = []

    def _sample(self):
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True)
        if out.returncode != 0:
            return None
        used, total, util = [int(x) for x in
                             out.stdout.strip().splitlines()[0].split(", ")]
        return {"t": round(time.time(), 1), "used_mib": used,
                "total_mib": total, "util_pct": util}

    def _loop(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            while not self._stop.is_set():
                sample = self._sample()
                if sample:
                    self.samples.append(sample)
                    handle.write(json.dumps(sample) + "\n")
                    handle.flush()
                self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join(timeout=self.interval * 2)

    def summary(self) -> dict:
        used = [s["used_mib"] for s in self.samples]
        if not used:
            return {"samples": 0, "note": "측정 실패 — 값을 추정해 적지 않는다"}
        ordered = sorted(used)
        return {
            "samples": len(used),
            "interval_sec": self.interval,
            "peak_mib": max(used),
            "median_mib": int(statistics.median(used)),
            "p95_mib": ordered[int(len(ordered) * 0.95) - 1],
            "total_mib": self.samples[0]["total_mib"],
            "util_peak_pct": max(s["util_pct"] for s in self.samples),
        }


def stt_anomaly_proxies(segments) -> dict:
    """**anomaly proxy만** 센다 — hallucination rate가 아니다.

    새 human GT가 없으므로 "환각 몇 %"라고 부르지 않는다. 결정적으로 셀 수 있는
    것만 적고, 판정은 하지 않는다. 여기서 새 필터 정책을 만들지 않는다.
    """
    texts = [normalize_for_counting(s.get("subtitle")) for s in segments]
    nonempty = [t for t in texts if t]

    consecutive = sum(1 for a, b in zip(texts, texts[1:]) if a and a == b)
    counts = {}
    for text in nonempty:
        counts[text] = counts.get(text, 0) + 1

    longest, current, current_text = 0, 0, None
    for text in texts:
        if text and text == current_text:
            current += 1
        else:
            current, current_text = 1 if text else 0, text
        longest = max(longest, current)

    observed = {phrase: sum(1 for t in nonempty if phrase in t)
                for phrase in OBSERVED_STRINGS}

    overlaps = []
    for segment in segments:
        subtitle = set((segment.get("subtitle") or "").split())
        caption = set((segment.get("caption") or "").split())
        if subtitle and caption:
            overlaps.append(len(subtitle & caption) / len(subtitle | caption))

    return {
        "nonempty_count": len(nonempty),
        "nonempty_ratio": round(len(nonempty) / max(len(texts), 1), 3),
        "consecutive_duplicate_count": consecutive,
        "consecutive_duplicate_ratio": round(
            consecutive / max(len(nonempty), 1), 3),
        "distinct_transcripts": len(counts),
        "top_repeats": sorted(counts.items(), key=lambda kv: -kv[1])[:10],
        "max_repeat_run_length": longest,
        "canary_observed_strings": observed,
        "caption_subtitle_token_jaccard_mean": (
            round(statistics.mean(overlaps), 3) if overlaps else None),
        "note": "diagnostic only — 사실 여부 판정이 아니다",
    }


def characterize(video_id: str, config_path: Path) -> dict:
    """산출물 상태 분포. 판정하지 않고 센다."""
    config = common.load_config(config_path)
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
        "caption_quotes_screen_text": sum(
            1 for s in segments
            if re.search(r"['\"‘’“”][A-Za-z][^'\"‘’“”]{2,}",
                         s.get("caption") or "")),
        "stt_anomaly_proxies": stt_anomaly_proxies(segments),
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
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--namespace", default="canary")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--full", action="store_true",
                        help="구간을 자르지 않고 영상 전체를 쓴다")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.full:
        video_id = "%s_%s" % (args.namespace, args.source_id)
        source_id = args.source_id
    else:
        video_id = "%s_%s_%d_%d" % (args.namespace, args.source_id, args.start,
                                    args.start + args.duration)
        source_id = "%s#%d-%d" % (args.source_id, args.start,
                                  args.start + args.duration)
    out = ROOT / (args.out or "runs/%s/%s_probe.json" % (args.namespace,
                                                         args.namespace))
    scratch = ROOT / ("work_%s" % args.namespace) / "_download"
    clip = VIDEO_DIR / ("%s.mp4" % video_id)

    log = {"video_id": video_id, "url": args.url, "namespace": args.namespace,
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "clip": {"full": args.full, "start": args.start,
                    "duration": None if args.full else args.duration},
           "code_git_head": subprocess.run(
               ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
               text=True).stdout.strip(),
           "steps": {}}

    if not clip.exists():
        if args.full:
            download_full(args.url, clip, scratch)
        else:
            download_clip(args.url, args.start, args.duration, clip, scratch)
    log["clip"]["bytes"] = clip.stat().st_size
    log["provenance_entry"] = register(video_id, args.url, source_id, clip)

    config = write_config(args.namespace)
    log["config"] = {
        "path": str(config),
        "sha256": hashlib.sha256(config.read_bytes()).hexdigest()[:16],
    }
    settings = common.load_config(config)
    log["models"] = {key: settings.get(key) for key in
                     ("stt_model", "caption_model", "vlm_4bit",
                      "vlm_max_new_tokens", "embed_model", "seg_len_sec")}

    poll = GpuPoll(ROOT / ("runs/%s/gpu_poll.jsonl" % args.namespace))
    with poll:
        for label, module in (("M1", "m1_preprocess"), ("M2", "m2_keyframe"),
                              ("M3", "m3_generate")):
            run([sys.executable, str(ROOT / "src" / ("%s.py" % module)),
                 "--config", str(config), "--video-id", video_id],
                label, log["steps"])
    log["gpu"] = poll.summary()

    log["characterization"] = characterize(video_id, config)
    total = sum(step["seconds"] for step in log["steps"].values())
    log["total_seconds"] = round(total, 1)
    log["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if not args.full:
        log["projection_2424s_hours"] = round(
            total * (2424 / args.duration) / 3600, 2)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print("보고서: %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
