"""STT_EVIDENCE_SANITATION_V1 Phase A — VAD sidecar 계측 계약.

사전등록: `docs/preregistration/STT_EVIDENCE_SANITATION_V1_2026-09-06.md`

```
speech_overlap_ratio   |ASR구간 ∩ ∪(VAD speech)| / |ASR구간|
nearest_speech_gap_sec overlap > 0 이면 0, 아니면 가장 가까운 speech까지 거리
```

VAD interval은 **padding까지 적용된 최종 구간**이다. unpadded 원본과 섞지 않는다.

이 단계는 **측정만** 한다. 판정을 바꾸거나 텍스트를 고치는 코드가 들어오면 이 파일이
막는다.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/stt_vad_sidecar.py"


def _load():
    spec = importlib.util.spec_from_file_location("stt_vad_sidecar", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sidecar = _load()

#: 초 단위 speech 구간. 실제 VAD 출력 자리에 넣는 고정 입력.
SPEECH = ((1.0, 2.0), (5.0, 6.5), (10.0, 10.4))


# ── metric 정의 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("interval,expected", [
    ((1.0, 2.0), 1.0),          # 완전 포함
    ((0.5, 1.5), 0.5),          # 절반
    ((3.0, 4.0), 0.0),          # 겹침 없음
    ((0.5, 6.5), (1.0 + 1.5) / 6.0),   # 두 구간에 걸침 — 합집합으로 센다
    ((5.5, 5.5), 0.0),          # 길이 0 — 0으로 정의한다(나눗셈 없음)
])
def test_speech_overlap_ratio(interval, expected):
    assert sidecar.speech_overlap_ratio(interval, SPEECH) == pytest.approx(expected)


def test_overlap_never_double_counts_touching_intervals():
    """붙어 있는 speech 두 개를 각각 더하면 비율이 1을 넘는다."""
    touching = ((1.0, 2.0), (2.0, 3.0), (1.5, 2.5))
    assert sidecar.speech_overlap_ratio((1.0, 3.0), touching) == pytest.approx(1.0)


@pytest.mark.parametrize("interval,expected", [
    ((1.2, 1.8), 0.0),          # 겹치면 0
    ((3.0, 4.0), 1.0),          # 앞 speech(끝 2.0)까지 1.0 · 뒤(시작 5.0)까지 1.0
    ((2.5, 2.9), 0.5),
    ((7.0, 8.0), 0.5),          # 5.0–6.5 끝에서 0.5
    ((20.0, 21.0), 9.6),        # 마지막 speech 끝 10.4에서 9.6
])
def test_nearest_speech_gap(interval, expected):
    assert sidecar.nearest_speech_gap((interval), SPEECH) == pytest.approx(expected)


def test_gap_is_none_when_there_is_no_speech_at_all():
    """speech가 0개면 거리를 지어내지 않는다."""
    assert sidecar.nearest_speech_gap((1.0, 2.0), ()) is None


def test_merge_produces_disjoint_sorted_intervals():
    merged = sidecar.merge(((5.0, 6.0), (1.0, 2.0), (1.5, 3.0), (6.0, 7.0)))
    assert merged == ((1.0, 3.0), (5.0, 7.0))


def test_samples_are_converted_with_the_declared_rate():
    """VAD는 sample index를 돌려준다. 초 변환을 한 곳에서만 한다."""
    assert sidecar.to_seconds([{"start": 16000, "end": 24000}], 16000) == \
        ((1.0, 1.5),)


# ── 측정 표 ──────────────────────────────────────────────────────────────
SEGMENTS = {
    "video_id": "V1",
    "segments": [
        {"idx": 0, "start": 0, "end": 5, "subtitle": "안녕하세요", "caption": "x"},
        {"idx": 1, "start": 5, "end": 10, "subtitle": "icular 볶고", "caption": "x"},
        {"idx": 2, "start": 10, "end": 15, "subtitle": "", "caption": "x"},
    ],
}
CACHE = {"meta": {"model": "large-v3", "lang": "ko", "beam_size": 5},
         "utterances": [{"text": "안녕하세요", "t0": 1.0, "t1": 1.9},
                        {"text": "icular 볶고", "t0": 5.2, "t1": 6.0},
                        {"text": "icular 볶고", "t0": 12.0, "t1": 12.6}]}


@pytest.fixture
def work(tmp_path):
    root = tmp_path / "work_x" / "V1"
    root.mkdir(parents=True)
    (root / "segments.json").write_text(json.dumps(SEGMENTS, ensure_ascii=False),
                                        encoding="utf-8")
    (root / "stt_cache.json").write_text(json.dumps(CACHE, ensure_ascii=False),
                                         encoding="utf-8")
    return root


def test_the_table_measures_both_levels(work):
    table = sidecar.measure(work, SPEECH)
    assert len(table["utterances"]) == 3
    assert len(table["segments"]) == 3
    row = table["utterances"][0]
    assert row["speech_overlap_ratio"] == pytest.approx(1.0)
    assert row["nearest_speech_gap_sec"] == 0.0


def test_segment_rows_carry_the_existing_verdict_unchanged(work):
    """현행 판정을 **읽기만** 한다. 이 단계에서 바꾸지 않는다."""
    table = sidecar.measure(work, SPEECH)
    rows = {row["segment_id"]: row for row in table["segments"]}
    assert rows[0]["existing_sanitation_status"] == "VALID"
    assert rows[0]["existing_usable_for_claims"] is True
    assert rows[2]["existing_sanitation_status"] == "EMPTY"
    assert rows[2]["existing_usable_for_claims"] is False


def test_diagnostic_features_are_recorded_but_not_verdicts(work):
    table = sidecar.measure(work, SPEECH)
    rows = {row["segment_id"]: row for row in table["segments"]}
    assert rows[1]["latin_present"] is True
    assert rows[0]["latin_present"] is False
    # 반복은 정규화 완전일치로 센다(유사도 매칭 금지).
    assert rows[1]["normalized_repeat_count"] == 1
    utterance_repeats = {row["text"]: row["normalized_repeat_count"]
                         for row in table["utterances"]}
    assert utterance_repeats["icular 볶고"] == 2


def test_the_measurement_never_writes_a_verdict_field(work):
    table = sidecar.measure(work, SPEECH)
    for row in table["utterances"] + table["segments"]:
        for banned in ("suspect", "hallucination", "reject", "new_status"):
            assert not any(banned in key for key in row), row


def test_text_is_carried_over_unmodified(work):
    table = sidecar.measure(work, SPEECH)
    assert [row["text"] for row in table["utterances"]] == \
        [item["text"] for item in CACHE["utterances"]]


def test_buckets_cover_every_usable_segment(work):
    table = sidecar.measure(work, SPEECH)
    report = sidecar.distribution(table)
    usable = [row for row in table["segments"] if row["existing_usable_for_claims"]]
    assert sum(report["overlap_buckets"].values()) == len(usable)
    assert sum(report["gap_buckets"].values()) == len(usable)
    assert set(report["overlap_buckets"]) == {
        "0", "(0, .25]", "(.25, .50]", "(.50, .75]", "(.75, 1.0]"}


def test_the_cross_tab_stays_diagnostic(work):
    """라틴·반복이 어느 overlap 영역에 있는지 **보기만** 한다."""
    report = sidecar.distribution(sidecar.measure(work, SPEECH))
    assert "latin_by_overlap_bucket" in report
    assert "rule" not in json.dumps(report)


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_the_script_does_not_transcribe_or_mutate():
    code = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("WhisperModel", "transcribe(", "vad_filter",
                      "write_text(json.dumps(doc", "usable_for_claims ="):
        assert forbidden not in code, forbidden


def test_the_script_declares_resolved_vad_parameters():
    """implicit default로 남기면 나중에 값이 바뀌어도 알 수 없다."""
    code = SCRIPT.read_text(encoding="utf-8")
    for key in ("threshold", "neg_threshold", "min_speech_duration_ms",
                "max_speech_duration_s", "min_silence_duration_ms",
                "speech_pad_ms"):
        assert key in code, key
