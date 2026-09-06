"""Phase B canary — 600–780초 구간에서 decoder metadata를 회수한다.

사전등록: `docs/preregistration/STT_EVIDENCE_SANITATION_V1_2026-09-06.md`

```
입력   work_canary/canary_xekZO4n4QuE_600_780/{audio.wav,stt_cache.json}   읽기 전용
출력   work_sttv1/<name>/ · runs/stt_sanitation_v1/phase_b_canary/
```

목적은 **계측 품질 확인**이다. 기존 전사에 없던 `avg_logprob`·`no_speech_prob`·
`compression_ratio`를 회수하되, 그 값이 무엇을 가르는지는 여기서 판단하지 않는다.

```
decoding parameter   production과 동일 (word_timestamps 포함) · VAD filter OFF
aggregation 규칙      고르지 않는다 — raw와 lineage를 전부 저장하고 D freeze에서 정한다
θ                    고르지 않는다
판정·claim eligibility 바꾸지 않는다
```

`no_speech_prob`가 overlap 0에서 높게 나오는지는 **통과 조건이 아니다.** 통과 조건으로
두면 canary 결과를 보고 Phase C 실행 여부를 성능으로 고르게 된다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_sanitation import normalize_for_counting                # noqa: E402

_SIDECAR = ROOT / "scripts/stt_vad_sidecar.py"

#: production 값 그대로. m3_generate.transcribe와 같아야 같은 전사를 잰다.
DECODING = {
    "model": "large-v3",
    "language": "ko",
    "beam_size": 5,
    "best_of": 5,
    "word_timestamps": True,
    "condition_on_previous_text": False,
    "hallucination_silence_threshold": 1.0,
    "vad_filter": False,
    "temperature": None,          # 지정하지 않는다 = 라이브러리 기본 사다리
}

METADATA_FIELDS = ("avg_logprob", "no_speech_prob", "compression_ratio")

GATES = ("B-C1", "B-C2", "B-C3", "B-C4", "B-C5", "B-C6", "B-C7", "B-C8")
GATE_DESCRIPTIONS = {
    "B-C1": "격리 namespace에만 쓴다",
    "B-C2": "입력·모델·파라미터 provenance를 기록했다",
    "B-C3": "metadata가 결측·비유한 값 없이 회수됐다",
    "B-C4": "raw→merged lineage가 버려진 것까지 완결이다",
    "B-C5": "baseline 전사와 production 동등 경로 결과가 일치한다",
    "B-C6": "Phase A sidecar와 join이 완결이다",
    "B-C7": "기존 판정·claim eligibility가 그대로다",
    "B-C8": "제출 산출물이 그대로다",
}

_LATIN = re.compile(r"[A-Za-z]{3,}")
_OVERLAP_BUCKETS = ("0", "(0, .25]", "(.25, .50]", "(.50, .75]", "(.75, 1.0]")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_revision() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


# ── production 동등 경로 · parity ────────────────────────────────────────
def production_equivalent(raw) -> list[dict]:
    """m3의 규칙 그대로: strip 후 빈 것은 버린다. 그 외에는 손대지 않는다."""
    return [{"text": item["text"].strip(), "t0": float(item["start"]),
             "t1": float(item["end"])}
            for item in raw if item["text"].strip()]


def parity(baseline, produced) -> dict:
    """기존 전사와 대응되는지 본다. 텍스트가 다르면 FAIL이다."""
    mismatch = None
    for index, (left, right) in enumerate(zip(baseline, produced)):
        if left["text"].strip() != right["text"]:
            mismatch = {"index": index, "baseline": left["text"],
                        "produced": right["text"]}
            break
    drift = max((abs(left["t0"] - right["t0"]) for left, right
                 in zip(baseline, produced)), default=0.0)
    drift = max([drift] + [abs(left["t1"] - right["t1"]) for left, right
                           in zip(baseline, produced)])
    return {
        "count_baseline": len(baseline),
        "count_produced": len(produced),
        "text_equal": mismatch is None and len(baseline) == len(produced),
        "first_mismatch": mismatch,
        "timestamp_max_abs_diff": drift,
    }


# ── lineage · metadata 건전성 ───────────────────────────────────────────
def lineage(raw) -> list[dict]:
    """raw 하나하나가 어느 merged evidence가 됐는지 남긴다. 버려진 것도 남긴다."""
    rows, merged_id = [], 0
    for item in raw:
        kept = bool(item["text"].strip())
        row = {
            "raw_whisper_segment_id": item["id"],
            "start": float(item["start"]),
            "end": float(item["end"]),
            "text": item["text"],
            "merged_stt_id": merged_id if kept else None,
            "dropped_reason": None if kept else "blank_after_strip",
        }
        row.update({field: item.get(field) for field in METADATA_FIELDS})
        rows.append(row)
        if kept:
            merged_id += 1
    return rows


def metadata_health(raw) -> dict:
    """결측·비유한 값을 센다. 채워 넣지 않는다."""
    missing = {field: 0 for field in METADATA_FIELDS}
    nonfinite = {field: 0 for field in METADATA_FIELDS}
    for item in raw:
        for field in METADATA_FIELDS:
            value = item.get(field)
            if value is None:
                missing[field] += 1
            elif not math.isfinite(float(value)):
                nonfinite[field] += 1
    return {
        "n": len(raw),
        "missing": {k: v for k, v in missing.items() if v},
        "nonfinite": {k: v for k, v in nonfinite.items() if v},
    }


# ── 분포 ─────────────────────────────────────────────────────────────────
def _bucket(value: float) -> str:
    if value <= 0:
        return "0"
    if value <= 0.25:
        return "(0, .25]"
    if value <= 0.50:
        return "(.25, .50]"
    if value <= 0.75:
        return "(.50, .75]"
    return "(.75, 1.0]"


def _stats(values) -> dict | None:
    ordered = sorted(values)
    if not ordered:
        return None

    def at(fraction):
        index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
        return round(ordered[index], 4)

    return {"min": round(ordered[0], 4), "p10": at(0.10), "median": at(0.50),
            "p90": at(0.90), "max": round(ordered[-1], 4)}


def crosstab(rows) -> dict:
    """overlap 구간별 metadata 분포. 임계값을 고르지 않는다."""
    grouped: dict[str, list[dict]] = {name: [] for name in _OVERLAP_BUCKETS}
    for row in rows:
        grouped[_bucket(row["speech_overlap_ratio"])].append(row)
    table = {}
    for name, members in grouped.items():
        entry = {"n": len(members)}
        for field in METADATA_FIELDS:
            entry[field] = _stats([row[field] for row in members
                                   if row.get(field) is not None])
        entry["latin_present"] = sum(1 for row in members if row["latin_present"])
        entry["repeated_2_or_more"] = sum(
            1 for row in members if row["normalized_repeat_count"] >= 2)
        table[name] = entry
    return {"unit": "raw whisper segment", "by_overlap_bucket": table,
            "note": "diagnostic only — 이 표로 판정하지 않는다"}


def phase_c_recommendation(verdict: dict) -> str:
    return ("ELIGIBLE_FOR_APPROVAL" if all(verdict.get(name) for name in GATES)
            else "HOLD")


# ── 실행 ─────────────────────────────────────────────────────────────────
def _load_sidecar():
    import importlib.util
    spec = importlib.util.spec_from_file_location("stt_vad_sidecar", _SIDECAR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _enable_cuda_dlls() -> list[str]:
    """Windows에서 CTranslate2가 cuBLAS·cuDNN을 찾게 한다.

    2026-09-06 canary가 여기서 멈췄다 — `cublas64_12.dll is not found`. DLL은
    site-packages/nvidia/*/bin에 있으나 검색 경로에 없었다. **decoding 파라미터가
    아니라 환경 문제**이므로 여기서만 고치고 파라미터는 건드리지 않는다.
    """
    import os
    import sys as _sys

    added = []
    if os.name != "nt":
        return added
    for base in _sys.path:
        if not base.endswith("site-packages"):
            continue
        for name in ("cublas", "cudnn", "cuda_runtime"):
            folder = Path(base) / "nvidia" / name / "bin"
            if folder.is_dir():
                os.add_dll_directory(str(folder))
                os.environ["PATH"] = str(folder) + os.pathsep + os.environ["PATH"]
                added.append(str(folder))
    return added


def transcribe_with_metadata(audio_path: Path) -> tuple[list[dict], dict]:
    """production과 같은 파라미터로 다시 돌리되 metadata를 버리지 않는다."""
    dll_dirs = _enable_cuda_dlls()
    import faster_whisper
    from faster_whisper import WhisperModel

    ladder = [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]
    attempts, last_error = [], None
    for device, compute in ladder:
        try:
            model = WhisperModel(DECODING["model"], device=device,
                                 compute_type=compute)
            segments, info = model.transcribe(
                str(audio_path),
                language=DECODING["language"],
                word_timestamps=DECODING["word_timestamps"],
                condition_on_previous_text=DECODING["condition_on_previous_text"],
                hallucination_silence_threshold=DECODING[
                    "hallucination_silence_threshold"],
                beam_size=DECODING["beam_size"],
                best_of=DECODING["best_of"],
            )
            raw = [{
                "id": index,
                "text": item.text,
                "start": float(item.start),
                "end": float(item.end),
                "avg_logprob": float(item.avg_logprob),
                "no_speech_prob": float(item.no_speech_prob),
                "compression_ratio": float(item.compression_ratio),
                "temperature": getattr(item, "temperature", None),
                "seek": getattr(item, "seek", None),
                "words": [{"word": w.word, "start": float(w.start),
                           "end": float(w.end), "probability": float(w.probability)}
                          for w in (item.words or [])],
            } for index, item in enumerate(segments)]
            return raw, {
                "faster_whisper_version": faster_whisper.__version__,
                "device": device, "compute_type": compute,
                "dll_directories_added": dll_dirs,
                "ladder_attempts": attempts,
                "decoding_resolved": {k: v for k, v in DECODING.items()},
                "language_detected": info.language,
                "language_probability": round(float(info.language_probability), 4),
                "duration_sec": round(float(info.duration), 2),
            }
        except Exception as error:                            # noqa: BLE001
            last_error = error
            # 실패 사유를 provenance에 남긴다. 콘솔은 cp949라 ASCII로만 찍는다.
            attempts.append({"device": device, "compute_type": compute,
                             "error": "%s: %s" % (type(error).__name__, error)})
            print("fallback: %s/%s failed (%s)" % (device, compute,
                                                   type(error).__name__),
                  flush=True)
            if (device, compute) == ladder[-1]:
                raise
    raise RuntimeError(last_error)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True,
                        help="baseline canary 디렉터리 (읽기 전용)")
    parser.add_argument("--workspace", required=True, help="격리 작업 디렉터리")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    source = Path(args.source)
    workspace = Path(args.workspace)
    out = Path(args.out)
    workspace.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    audio_path = source / "audio.wav"
    baseline = json.loads(
        (source / "stt_cache.json").read_text(encoding="utf-8"))["utterances"]

    raw, provenance = transcribe_with_metadata(audio_path)
    produced = production_equivalent(raw)
    pairing = parity(baseline, produced)
    trace = lineage(raw)
    health = metadata_health(raw)

    sidecar = _load_sidecar()
    speech, vad_manifest = sidecar.run_vad(audio_path)
    joined = []
    counts: dict[str, int] = {}
    for item in raw:
        key = normalize_for_counting(item["text"])
        if key:
            counts[key] = counts.get(key, 0) + 1
    for item in raw:
        interval = (float(item["start"]), float(item["end"]))
        joined.append({
            "raw_whisper_segment_id": item["id"],
            "speech_overlap_ratio": round(
                sidecar.speech_overlap_ratio(interval, speech), 4),
            "nearest_speech_gap_sec": sidecar.nearest_speech_gap(interval, speech),
            "latin_present": bool(_LATIN.search(item["text"])),
            "normalized_repeat_count": counts.get(
                normalize_for_counting(item["text"]), 0),
            **{field: item.get(field) for field in METADATA_FIELDS},
        })
    table = crosstab(joined)

    verdict = {
        "B-C1": str(workspace).startswith("work_sttv1") or "work_sttv1" in str(
            workspace),
        "B-C2": bool(provenance["decoding_resolved"] and vad_manifest),
        "B-C3": not health["missing"] and not health["nonfinite"],
        "B-C4": all(row["merged_stt_id"] is not None
                    or row["dropped_reason"] is not None for row in trace),
        "B-C5": bool(pairing["text_equal"]),
        "B-C6": len(joined) == len(raw),
        "B-C7": None,       # 아래에서 실측으로 채운다
        "B-C8": None,
    }

    # B-C7 · B-C8: 이 실행이 확정 인덱스와 제출 산출물을 건드리지 않았는지 실측한다.
    watched = {
        "work_full_segments": ROOT / "work_full/full_xekZO4n4QuE/segments.json",
        "work_full_stt_cache": ROOT / "work_full/full_xekZO4n4QuE/stt_cache.json",
        "canary_stt_cache": source / "stt_cache.json",
        "submission_manifest": ROOT / "runs/v3_paired/submission_manifest.json",
    }
    digests = {name: sha256_file(path) for name, path in watched.items()
               if path.is_file()}
    expected = {
        "work_full_segments":
            "aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92",
        "work_full_stt_cache":
            "59c98df1e0ea18e93623074a538b63b91794a8fca686e68a345c85dfc1c1a90d",
    }
    verdict["B-C7"] = all(digests.get(name) == value
                          for name, value in expected.items())
    submission = json.loads(
        (ROOT / "runs/v3_paired/submission_manifest.json").read_text(
            encoding="utf-8"))
    verdict["B-C8"] = submission["artifact"]["hwpx_sha256"].startswith("f874f643")

    manifest = {
        "phase": "B-canary",
        "track": "STT_EVIDENCE_SANITATION_V1",
        "range_sec": [600, 780],
        "source": str(source),
        "workspace": str(workspace),
        "code_revision": code_revision(),
        "inputs": {"audio_sha256": sha256_file(audio_path),
                   "baseline_stt_cache_sha256": sha256_file(
                       source / "stt_cache.json")},
        "whisper": provenance,
        "vad": vad_manifest,
        "parity": pairing,
        "metadata_health": health,
        "gates": verdict,
        "gate_descriptions": GATE_DESCRIPTIONS,
        "phase_c_recommendation": phase_c_recommendation(verdict),
        "watched_digests": digests,
        "not_done": ["aggregation 규칙 선정", "임계값 선정", "판정 변경",
                     "확정 인덱스 수정"],
    }
    (workspace / "raw_segments.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "lineage.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "joined.json").write_text(
        json.dumps(joined, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "crosstab.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"gates": verdict, "parity": pairing,
                      "phase_c": manifest["phase_c_recommendation"]},
                     ensure_ascii=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
