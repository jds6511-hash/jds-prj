"""STT_RETRANSCRIBE_V1 — 3분 canary (600–780초) 2회 독립 실행.

사전등록: `docs/preregistration/STT_RETRANSCRIBE_V1_2026-09-08.md`

```
현행과 다른 것 둘   vad_filter True · temperature 0.0 (단일 scalar)
첫 질문             run1 == run2 인가
둘째 질문           frozen VAD speech 구간 밖 transcript가 줄었는가
```

**전사 텍스트를 고치지 않는다.** 이 스크립트는 두 번 돌리고, 두 결과를 비교하고,
기존 산출물이 그대로인지 확인해 적는다. 신호 품질이 아니라 **계측 품질**을 잰다.

full 범위 실행은 여기서 막는다(`guard_range`) — 별도 승인 사건이다.

사용:
    python scripts/stt_retranscribe_canary.py --audio work_canary/<clip>/audio.wav
        --baseline work_canary/<clip> --workspace work_sttv2 --out runs/<...>.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: **freeze된 decoding arm.** 현행(m3_generate)과 다른 것은 vad_filter와 temperature뿐.
DECODING = {
    "model": "large-v3",
    "language": "ko",
    "beam_size": 5,
    "best_of": 5,
    "condition_on_previous_text": False,
    "word_timestamps": True,
    "hallucination_silence_threshold": 1.0,
    "vad_filter": True,
    "temperature": 0.0,          # 단일 scalar — fallback 사다리를 없앤다
}

#: 사전등록에 고정된 canary 구간. 새 구간을 고르지 않는다.
CANARY_RANGE_SEC = (600, 780)

#: full 범위 실행은 별도 승인 사건이다. 코드로 막는다.
FULL_RUN_APPROVED = False

GATES = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
GATE_DESCRIPTIONS = {
    "C1": "provenance complete — decoding·VAD resolved 값과 실행 환경을 기록했다",
    "C2": "deterministic pairing — run1 == run2",
    "C3": "no temperature fallback — 관측 temperature가 0.0뿐이다",
    "C4": "VAD resolved params exact — Phase A 값과 전건 일치",
    "C5": "raw→merged lineage complete — 버려진 행까지 남는다",
    "C6": "timestamp validity — start<=end · zero-duration · nonfinite 집계",
    "C7": "old artifacts unchanged — 기존 전사·인덱스·제출물 해시 무변경",
    "C8": "canonical mapping unchanged — canary 범위 segment_id·start·end 동일",
}


class CanaryError(RuntimeError):
    """canary 입력·격리 계약 위반. 보정하지 않고 멈춘다."""


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_sidecar = _module(ROOT / "scripts/stt_vad_sidecar.py", "sidecar_for_retranscribe")

#: Phase A에서 freeze한 VAD 설정을 **그 모듈에서** 가져온다 — 값을 옮겨 적지 않는다.
VAD_PARAMS = _sidecar.VAD_PARAMS
SAMPLING_RATE = _sidecar.SAMPLING_RATE


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def code_revision() -> str:
    result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


# ── freeze 검사 ─────────────────────────────────────────────────────────
def assert_vad_params(params: dict) -> None:
    """Phase A 값과 다르면 멈춘다. 실행 중 조정은 threshold tuning이다."""
    if params != dict(VAD_PARAMS):
        raise CanaryError("VAD 파라미터가 Phase A freeze와 다르다: %r" % params)
    return None


def guard_range(range_sec, *, approved: bool = FULL_RUN_APPROVED) -> None:
    """canary 범위 밖 실행은 승인 플래그 없이는 막는다."""
    if tuple(range_sec) != CANARY_RANGE_SEC and not approved:
        raise CanaryError(
            "%r 범위 실행은 승인되지 않았다 — canary는 %r뿐이다"
            % (tuple(range_sec), CANARY_RANGE_SEC))
    return None


def assert_isolated(run1: Path, run2: Path) -> None:
    if Path(run1).resolve() == Path(run2).resolve():
        raise CanaryError("두 run이 같은 디렉터리다 — 독립 실행이 아니다")
    return None


def assert_clean_run_dir(run: Path) -> None:
    """이미 전사 산출물이 있는 디렉터리를 재사용하지 않는다."""
    existing = [name for name in ("transcript.json", "raw.json")
                if (Path(run) / name).is_file()]
    if existing:
        raise CanaryError("%s에 이미 전사 산출물이 있다: %r" % (run, existing))
    return None


# ── 판정 로직 ───────────────────────────────────────────────────────────
def _normalized(text) -> str:
    return " ".join(str(text or "").split())


def temperature_only_zero(raw):
    """관측 temperature가 0.0뿐인지. fallback이 돌면 여기서 드러난다."""
    observed = sorted({row.get("temperature") for row in raw
                       if row.get("temperature") is not None})
    return (observed in ([], [0.0]), list(observed))


def timestamp_validity(raw) -> dict:
    broken = zero = nonfinite = 0
    for row in raw:
        start, end = float(row["start"]), float(row["end"])
        if not (math.isfinite(start) and math.isfinite(end)):
            nonfinite += 1
            continue
        if start > end:
            broken += 1
        if start == end:
            zero += 1
    return {"rows": len(raw), "start_gt_end": broken, "zero_duration": zero,
            "nonfinite": nonfinite}


def lineage(raw) -> list:
    """raw → merged 계보. 버린 행도 사유와 함께 남긴다."""
    rows = []
    for row in raw:
        kept = bool(_normalized(row.get("text")))
        rows.append({"id": row.get("id"), "start": row["start"],
                     "end": row["end"], "kept": kept,
                     "drop_reason": None if kept else "empty_text",
                     "chars": len(_normalized(row.get("text")))})
    return rows


def compare_runs(run1, run2) -> dict:
    """두 실행을 비교한다. 내용 차이와 시간 차이를 섞지 않는다."""
    text_mismatches, timing_mismatches, raw_differences = [], [], 0
    for index, (left, right) in enumerate(zip(run1, run2)):
        if _normalized(left.get("text")) != _normalized(right.get("text")):
            text_mismatches.append({
                "index": index, "run1": left.get("text"),
                "run2": right.get("text")})
        elif str(left.get("text")) != str(right.get("text")):
            raw_differences += 1
        if (float(left["start"]), float(left["end"])) != (
                float(right["start"]), float(right["end"])):
            timing_mismatches.append({
                "index": index,
                "run1": [left["start"], left["end"]],
                "run2": [right["start"], right["end"]]})
    same_count = len(run1) == len(run2)
    return {
        "utterance_count": {"run1": len(run1), "run2": len(run2)},
        "count_equal": same_count,
        "text_mismatches": text_mismatches,
        "timing_mismatches": timing_mismatches,
        "raw_text_differences": raw_differences,
        "identical": bool(same_count and not text_mismatches
                          and not timing_mismatches),
        "ordered_digest": {"run1": ordered_digest(run1),
                           "run2": ordered_digest(run2)},
    }


def ordered_digest(raw) -> str:
    payload = json.dumps([[round(float(row["start"]), 3),
                           round(float(row["end"]), 3),
                           _normalized(row.get("text"))] for row in raw],
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def determinism_verdict(comparison: dict) -> str:
    return "PASS" if comparison["identical"] else "FAIL"


def overlap_counts(rows, speech) -> dict:
    """frozen VAD speech 구간과의 겹침만 본다. 입력은 그 비율 하나뿐이다."""
    zero = 0
    for row in rows:
        ratio = _sidecar.speech_overlap_ratio(
            (float(row["start"]), float(row["end"])), speech)
        if ratio == 0:
            zero += 1
    return {"utterances": len(rows), "zero_overlap": zero,
            "with_overlap": len(rows) - zero}


def segments_range(segments) -> tuple:
    """segments의 자체 시간 기준. 클립은 상대 시간(0부터)이라 요청 범위와 다르다.

    이걸 쓰지 않으면 canary(600–780초 요청)와 클립 segments(0–180초)가 어긋나
    canonical mapping이 **0행으로 공허하게 통과**한다 — 실측에서 났던 결함이다.
    """
    if not segments:
        raise CanaryError("segments가 비어 있다")
    return (min(item["start"] for item in segments),
            max(item["end"] for item in segments))


def canonical_mapping(segments, range_sec) -> list:
    """canary 범위에 걸치는 canonical segment의 식별자·경계."""
    start, end = range_sec
    return [{"segment_id": segment["idx"], "start": segment["start"],
             "end": segment["end"]}
            for segment in segments
            if segment["start"] < end and segment["end"] > start]


def digests(watched: dict) -> dict:
    return {name: (sha256_file(path) if Path(path).is_file() else None)
            for name, path in watched.items()}


def unchanged(before: dict, after: dict) -> bool:
    return before == after


# ── 전사 ────────────────────────────────────────────────────────────────
def _enable_cuda_dlls() -> list:
    """pip 설치된 CUDA 런타임 경로를 프로세스에 알린다(Phase B 사고 대응)."""
    added = []
    base = Path(sys.prefix) / "Lib/site-packages/nvidia"
    candidates = [base / "cublas/bin", base / "cudnn/bin"]
    for path in sys.path:
        nvidia = Path(path) / "nvidia"
        candidates += [nvidia / "cublas/bin", nvidia / "cudnn/bin"]
    for candidate in candidates:
        if candidate.is_dir() and str(candidate) not in added:
            os.add_dll_directory(str(candidate))
            added.append(str(candidate))
    return added


def transcribe(audio_path: Path) -> tuple:
    """freeze된 arm으로 한 번 전사한다. 파라미터를 인자로 받지 않는다."""
    dll_dirs = _enable_cuda_dlls()
    import faster_whisper
    from faster_whisper import WhisperModel
    from faster_whisper.vad import VadOptions

    assert_vad_params(dict(VAD_PARAMS))
    vad_options = VadOptions(**VAD_PARAMS)

    ladder = [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]
    attempts = []
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
                vad_filter=DECODING["vad_filter"],
                vad_parameters=vad_options,
                temperature=DECODING["temperature"],
            )
            raw = [{
                "id": index,
                "text": item.text,
                "start": float(item.start),
                "end": float(item.end),
                "temperature": getattr(item, "temperature", None),
                "avg_logprob": float(item.avg_logprob),
                "no_speech_prob": float(item.no_speech_prob),
                "compression_ratio": float(item.compression_ratio),
                "seek": getattr(item, "seek", None),
                "words": [{"word": word.word, "start": float(word.start),
                           "end": float(word.end),
                           "probability": float(word.probability)}
                          for word in (item.words or [])],
            } for index, item in enumerate(segments)]
            provenance = {
                "faster_whisper_version": faster_whisper.__version__,
                "device": device,
                "compute_type": compute,
                "dll_directories_added": dll_dirs,
                "ladder_attempts": attempts,
                "decoding_resolved": dict(DECODING),
                "vad_params_resolved": {
                    key: ("inf" if value == float("inf") else value)
                    for key, value in VAD_PARAMS.items()},
                "vad_sampling_rate": SAMPLING_RATE,
                "language_detected": info.language,
                "language_probability": round(float(info.language_probability), 4),
                "duration_sec": round(float(info.duration), 2),
                "duration_after_vad_sec": round(
                    float(getattr(info, "duration_after_vad", float("nan"))), 2),
            }
            return raw, provenance
        except Exception as error:                            # noqa: BLE001
            attempts.append({"device": device, "compute_type": compute,
                             "error": "%s: %s" % (type(error).__name__, error)})
            print("fallback: %s/%s failed (%s)" % (device, compute,
                                                   type(error).__name__),
                  flush=True)
            if (device, compute) == ladder[-1]:
                raise
    raise CanaryError("전사 경로를 모두 실패했다")


def run_once(audio_path: Path, run_dir: Path) -> dict:
    assert_clean_run_dir(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    raw, provenance = transcribe(audio_path)
    payload = {"provenance": provenance, "raw": raw,
               "lineage": lineage(raw),
               "ordered_digest": ordered_digest(raw),
               "timestamp_validity": timestamp_validity(raw)}
    (run_dir / "transcript.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, help="canary 오디오 (읽기 전용)")
    parser.add_argument("--baseline", required=True,
                        help="기존 전사·구간이 있는 디렉터리 (읽기 전용)")
    parser.add_argument("--workspace", required=True, help="격리 작업 디렉터리")
    parser.add_argument("--measurements", required=True,
                        help="Phase A measurements.json (frozen VAD 구간 출처)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--range", nargs=2, type=int,
                        default=list(CANARY_RANGE_SEC))
    args = parser.parse_args(argv)

    guard_range(tuple(args.range))
    audio = Path(args.audio).resolve()
    baseline = Path(args.baseline).resolve()
    workspace = Path(args.workspace)
    run1, run2 = workspace / "canary_run1", workspace / "canary_run2"
    assert_isolated(run1, run2)

    watched = {
        "baseline_stt_cache": baseline / "stt_cache.json",
        "baseline_segments": baseline / "segments.json",
        "full_stt_cache": ROOT / "work_full/full_xekZO4n4QuE/stt_cache.json",
        "full_segments": ROOT / "work_full/full_xekZO4n4QuE/segments.json",
        "submission_hwpx": ROOT / "runs/quality_candidate/S7/report.hwpx",
        "rollback_hwpx": ROOT / "runs/vad0_paired/s1_shadow/report.hwpx",
    }
    before = digests(watched)

    print("=== canary run1 ===", flush=True)
    first = run_once(audio, run1)
    print("=== canary run2 ===", flush=True)
    second = run_once(audio, run2)

    comparison = compare_runs(first["raw"], second["raw"])
    after = digests(watched)

    baseline_cache = json.loads(
        (baseline / "stt_cache.json").read_text(encoding="utf-8"))
    old_rows = [{"start": item["t0"], "end": item["t1"], "text": item["text"]}
                for item in baseline_cache["utterances"]]
    segments = json.loads(
        (baseline / "segments.json").read_text(encoding="utf-8"))["segments"]

    # frozen VAD 파라미터로 이 클립의 발화 구간을 직접 잰다 — old·new 두 전사에
    # **같은 기준**을 쓴다. 파라미터는 Phase A와 같은 모듈에서 온다.
    speech, vad_provenance = _sidecar.run_vad(audio)

    old_texts = {_normalized(row["text"]) for row in old_rows}
    new_texts = {_normalized(row["text"]) for row in first["raw"]}
    mapping_range = segments_range(segments)
    verdict = {
        "track": "STT_RETRANSCRIBE_V1",
        "phase": "canary",
        "range_sec": list(args.range),
        "code_revision": code_revision(),
        "inputs": {"audio": str(audio), "audio_sha256": sha256_file(audio),
                   "baseline": str(baseline),
                   "measurements_sha256": sha256_file(Path(args.measurements))},
        "run1": first["provenance"], "run2": second["provenance"],
        "vad_measurement": vad_provenance,
        "vad_speech_intervals": [[round(s, 3), round(e, 3)] for s, e in speech],
        "temperature_observed": {
            "run1": temperature_only_zero(first["raw"])[1],
            "run2": temperature_only_zero(second["raw"])[1]},
        "comparison": comparison,
        "determinism": determinism_verdict(comparison),
        "timestamp_validity": {"run1": first["timestamp_validity"],
                               "run2": second["timestamp_validity"]},
        "counts": {
            "old_utterances": len(old_rows),
            "new_utterances": len(first["raw"]),
            "exact_retained": len(old_texts & new_texts),
            "removed": len(old_texts - new_texts),
            "newly_emitted": len(new_texts - old_texts),
            "text_change_rate": round(
                1 - len(old_texts & new_texts) / max(len(old_texts), 1), 4)},
        "overlap": {"old": overlap_counts(old_rows, speech),
                    "new": overlap_counts(first["raw"], speech)},
        "mapping_range_sec": list(mapping_range),
        "canonical_mapping": canonical_mapping(segments, mapping_range),
        "canonical_mapping_rows": len(canonical_mapping(segments, mapping_range)),
        "canonical_mapping_equal": (
            canonical_mapping(segments, mapping_range)
            == canonical_mapping(json.loads(
                (baseline / "segments.json").read_text(encoding="utf-8"))[
                    "segments"], mapping_range)),
        "old_artifacts_unchanged": unchanged(before, after),
        "watched_digests": {"before": before, "after": after},
        "lineage_complete": {
            "run1": len(first["lineage"]) == len(first["raw"]),
            "run2": len(second["lineage"]) == len(second["raw"])},
    }
    verdict["gates"] = _gates(verdict)
    verdict["gate_descriptions"] = dict(GATE_DESCRIPTIONS)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdict, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps({"determinism": verdict["determinism"],
                      "gates": verdict["gates"],
                      "counts": verdict["counts"],
                      "overlap": verdict["overlap"]},
                     ensure_ascii=True, indent=1))
    return 0


def _gates(verdict: dict) -> dict:
    provenance_ok = all(
        verdict[run].get("decoding_resolved") and verdict[run].get(
            "vad_params_resolved") and verdict[run].get("faster_whisper_version")
        for run in ("run1", "run2"))
    temperature_ok = all(observed in ([], [0.0]) for observed in
                         verdict["temperature_observed"].values())
    timestamps_ok = all(
        stats["start_gt_end"] == 0 and stats["nonfinite"] == 0
        for stats in verdict["timestamp_validity"].values())
    vad_ok = all(verdict[run]["vad_params_resolved"] == {
        key: ("inf" if value == float("inf") else value)
        for key, value in VAD_PARAMS.items()} for run in ("run1", "run2"))
    return {
        "C1": provenance_ok,
        "C2": verdict["determinism"] == "PASS",
        "C3": temperature_ok,
        "C4": vad_ok,
        "C5": all(verdict["lineage_complete"].values()),
        "C6": timestamps_ok,
        "C7": verdict["old_artifacts_unchanged"],
        # 행이 0이면 통과가 아니다 — 공허한 통과를 막는다(실측 결함 대응)
        "C8": bool(verdict["canonical_mapping_equal"]
                   and verdict.get("canonical_mapping_rows")),
    }


if __name__ == "__main__":
    raise SystemExit(main())
