"""STT_EVIDENCE_SANITATION_V1 Phase A — VAD sidecar 계측 (읽기 전용).

사전등록: `docs/preregistration/STT_EVIDENCE_SANITATION_V1_2026-09-06.md`

```
입력   work_*/<vid>/audio.wav        읽기 전용
       work_*/<vid>/stt_cache.json   읽기 전용 (기존 전사 · 재전사 없음)
       work_*/<vid>/segments.json    읽기 전용
출력   runs/stt_sanitation_v1/<vid>/{manifest,measurements,distribution}.json
```

**VAD를 절단기로 쓰지 않는다.** 오디오를 자르지 않고 speech 구간만 재고, 기존 전사
구간과의 겹침을 계산한다. 과거 VAD가 실제 발화를 잘라먹은 사고를 피하는 배치다.

이 단계는 측정만 한다 — 판정(VALID/SUSPECT)·claim eligibility·텍스트를 바꾸지 않고,
임계값 후보도 고르지 않는다.

```
speech_overlap_ratio    |ASR구간 ∩ ∪(VAD speech)| / |ASR구간|
nearest_speech_gap_sec  overlap > 0 → 0 · 아니면 가장 가까운 speech까지 거리
```

VAD 구간은 **padding까지 적용된 최종 구간**이다(faster-whisper가 그렇게 돌려준다).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_sanitation import (                                   # noqa: E402
    classify_channel, normalize_for_counting)

SAMPLING_RATE = 16000

#: **freeze 대상.** characterization을 본 뒤 이 값을 바꾸면 threshold tuning이 된다.
#: faster-whisper 기본값을 그대로 쓰되 resolved value로 적어 둔다.
VAD_PARAMS = {
    "threshold": 0.5,
    "neg_threshold": 0.35,          # 기본은 None → max(threshold - 0.15, 0.01)
    "min_speech_duration_ms": 0,
    "max_speech_duration_s": float("inf"),
    "min_silence_duration_ms": 2000,
    "speech_pad_ms": 400,
}

_LATIN = re.compile(r"[A-Za-z]{3,}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── metric ───────────────────────────────────────────────────────────────
def merge(intervals) -> tuple[tuple[float, float], ...]:
    """겹치거나 맞닿은 구간을 합친다 — 합집합으로 세야 비율이 1을 넘지 않는다."""
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return tuple((start, end) for start, end in merged)


def to_seconds(chunks, sampling_rate: int = SAMPLING_RATE):
    """VAD는 sample index를 돌려준다. 초 변환은 여기 한 곳에서만 한다."""
    return tuple((chunk["start"] / sampling_rate, chunk["end"] / sampling_rate)
                 for chunk in chunks)


def speech_overlap_ratio(interval, speech) -> float:
    start, end = interval
    span = end - start
    if span <= 0:
        return 0.0
    covered = sum(max(0.0, min(end, s_end) - max(start, s_start))
                  for s_start, s_end in merge(speech))
    return covered / span


def nearest_speech_gap(interval, speech):
    """겹치면 0. 겹치지 않으면 가장 가까운 speech까지 거리. speech가 없으면 None."""
    merged = merge(speech)
    if not merged:
        return None
    start, end = interval
    gaps = [max(0.0, max(s_start - end, start - s_end))
            for s_start, s_end in merged]
    return min(gaps)


# ── 측정 표 ──────────────────────────────────────────────────────────────
def measure(work: Path, speech) -> dict:
    """utterance·segment 두 층의 측정 행을 만든다. 어떤 판정도 바꾸지 않는다."""
    document = json.loads((work / "segments.json").read_text(encoding="utf-8"))
    cache = json.loads((work / "stt_cache.json").read_text(encoding="utf-8"))
    utterances = cache["utterances"]

    channel = {entry["idx"]: (entry.get("subtitle") or "")
               for entry in document["segments"]}
    judged = classify_channel(channel, "asr")

    # 반복은 **정규화 완전일치**로 센다 — 유사도 매칭을 넣으면 서로 다른 실제
    # 발화가 한 덩어리가 된다(A-05와 같은 규칙을 쓴다).
    utterance_counts: dict[str, int] = {}
    for item in utterances:
        key = normalize_for_counting(item["text"])
        utterance_counts[key] = utterance_counts.get(key, 0) + 1

    utterance_rows = []
    for index, item in enumerate(utterances):
        interval = (float(item["t0"]), float(item["t1"]))
        key = normalize_for_counting(item["text"])
        utterance_rows.append({
            "utterance_index": index,
            "stt_start_sec": interval[0],
            "stt_end_sec": interval[1],
            "text": item["text"],
            "text_sha256": hashlib.sha256(
                item["text"].encode("utf-8")).hexdigest(),
            "speech_overlap_ratio": round(
                speech_overlap_ratio(interval, speech), 4),
            "nearest_speech_gap_sec": _round(nearest_speech_gap(interval, speech)),
            "latin_present": bool(_LATIN.search(item["text"])),
            "normalized_repeat_count": utterance_counts[key],
        })

    segment_counts: dict[str, int] = {}
    for text in channel.values():
        key = normalize_for_counting(text)
        if key:
            segment_counts[key] = segment_counts.get(key, 0) + 1

    segment_rows = []
    for entry in document["segments"]:
        interval = (float(entry["start"]), float(entry["end"]))
        text = channel[entry["idx"]]
        verdict = judged[entry["idx"]]
        covered = sum(max(0.0, min(interval[1], s_end) - max(interval[0], s_start))
                      for s_start, s_end in merge(speech))
        segment_rows.append({
            "segment_id": entry["idx"],
            "stt_start_sec": interval[0],
            "stt_end_sec": interval[1],
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "speech_overlap_ratio": round(
                speech_overlap_ratio(interval, speech), 4),
            "nearest_speech_gap_sec": _round(nearest_speech_gap(interval, speech)),
            "vad_speech_duration_sec": round(covered, 3),
            "latin_present": bool(_LATIN.search(text)),
            "normalized_repeat_count": segment_counts.get(
                normalize_for_counting(text), 0),
            "existing_sanitation_status": verdict.status,
            "existing_usable_for_claims": bool(verdict.usable_for_claims),
        })

    return {"utterances": utterance_rows, "segments": segment_rows}


def _round(value):
    return None if value is None else round(value, 3)


# ── 분포 ─────────────────────────────────────────────────────────────────
_OVERLAP_BUCKETS = ("0", "(0, .25]", "(.25, .50]", "(.50, .75]", "(.75, 1.0]")
_GAP_BUCKETS = ("0", "(0, .25]", "(.25, .50]", "(.50, 1.0]", "> 1.0", "speech 없음")


def _overlap_bucket(value: float) -> str:
    if value <= 0:
        return "0"
    if value <= 0.25:
        return "(0, .25]"
    if value <= 0.50:
        return "(.25, .50]"
    if value <= 0.75:
        return "(.50, .75]"
    return "(.75, 1.0]"


def _gap_bucket(value) -> str:
    if value is None:
        return "speech 없음"
    if value <= 0:
        return "0"
    if value <= 0.25:
        return "(0, .25]"
    if value <= 0.50:
        return "(.25, .50]"
    if value <= 1.0:
        return "(.50, 1.0]"
    return "> 1.0"


def distribution(table: dict) -> dict:
    """현행 usable STT를 bucket으로 센다. 판정 후보를 만들지 않는다.

    `overlap == 0`을 환각이라 부르지 않는다 — VAD false negative·시간 정렬 오차가
    섞여 있으므로 정확한 이름은 `low/no-VAD-speech STT`다.
    """
    usable = [row for row in table["segments"] if row["existing_usable_for_claims"]]
    overlap = {name: 0 for name in _OVERLAP_BUCKETS}
    gap = {name: 0 for name in _GAP_BUCKETS}
    latin_cross = {name: 0 for name in _OVERLAP_BUCKETS}
    repeat_cross = {name: 0 for name in _OVERLAP_BUCKETS}
    for row in usable:
        bucket = _overlap_bucket(row["speech_overlap_ratio"])
        overlap[bucket] += 1
        gap[_gap_bucket(row["nearest_speech_gap_sec"])] += 1
        if row["latin_present"]:
            latin_cross[bucket] += 1
        if row["normalized_repeat_count"] >= 2:
            repeat_cross[bucket] += 1
    return {
        "unit": "segment (existing usable_for_claims only)",
        "n": len(usable),
        "overlap_buckets": overlap,
        "gap_buckets": gap,
        "latin_by_overlap_bucket": latin_cross,
        "repeated_by_overlap_bucket": repeat_cross,
        "note": "diagnostic only — overlap 0을 환각이라 부르지 않는다",
    }


# ── 실행 ─────────────────────────────────────────────────────────────────
def run_vad(audio_path: Path):
    """오디오를 디코드해 speech 구간만 잰다. 오디오를 자르지 않는다."""
    import faster_whisper
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_assets_path, get_speech_timestamps

    audio = decode_audio(str(audio_path), sampling_rate=SAMPLING_RATE)
    options = VadOptions(**{k: v for k, v in VAD_PARAMS.items()
                            if k != "neg_threshold"},
                         neg_threshold=VAD_PARAMS["neg_threshold"])
    chunks = get_speech_timestamps(audio, options, sampling_rate=SAMPLING_RATE)
    assets = Path(get_assets_path())
    model_file = assets / "silero_vad_v6.onnx"
    return to_seconds(chunks), {
        "faster_whisper_version": faster_whisper.__version__,
        "vad_model": model_file.name,
        "vad_model_sha256": sha256_file(model_file) if model_file.is_file()
                            else "unavailable",
        "vad_params_resolved": {k: (None if v == float("inf") else v)
                                for k, v in VAD_PARAMS.items()},
        "max_speech_duration_s": "inf",
        "sampling_rate": SAMPLING_RATE,
        "audio_seconds": round(len(audio) / SAMPLING_RATE, 2),
        "speech_chunks": len(chunks),
    }


def code_revision() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True,
                        help="work 디렉터리 (audio.wav · stt_cache.json · segments.json)")
    parser.add_argument("--out", required=True, help="출력 디렉터리")
    args = parser.parse_args(argv)

    work = Path(args.work)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    audio_path = work / "audio.wav"
    speech, vad_manifest = run_vad(audio_path)
    table = measure(work, speech)
    report = distribution(table)

    manifest = {
        "phase": "A",
        "track": "STT_EVIDENCE_SANITATION_V1",
        "work": str(work),
        "code_revision": code_revision(),
        "inputs": {
            "audio_sha256": sha256_file(audio_path),
            "segments_sha256": sha256_file(work / "segments.json"),
            "stt_cache_sha256": sha256_file(work / "stt_cache.json"),
        },
        "vad": vad_manifest,
        "counts": {
            "utterances": len(table["utterances"]),
            "segments": len(table["segments"]),
            "usable_segments": report["n"],
        },
        "not_done": ["재전사", "판정 변경", "claim eligibility 변경",
                     "텍스트 수정", "임계값 선정"],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "measurements.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "distribution.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    # 콘솔은 cp949라 한글이 깨진다. 수치는 UTF-8 JSON 파일에서 읽는다.
    print(json.dumps({"out": str(out), "vad": vad_manifest,
                      "distribution": report}, ensure_ascii=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
