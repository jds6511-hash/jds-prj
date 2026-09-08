"""STT_RETRANSCRIBE_V1 canary 계약 (2026-09-08 · TRACK B).

사전등록: `docs/preregistration/STT_RETRANSCRIBE_V1_2026-09-08.md`

```
첫 질문   run1 == run2 인가 (determinism)
둘째      frozen VAD speech 구간 밖 transcript가 줄었는가
```

GPU 없이 판정 로직만 잰다. 전사 실행은 스크립트 본체가 하고, 여기서는 계약을 잠근다.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/stt_retranscribe_canary.py"
SIDECAR = ROOT / "scripts/stt_vad_sidecar.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


canary = _load(SCRIPT, "stt_retranscribe_canary")
sidecar = _load(SIDECAR, "stt_vad_sidecar_for_canary")


def _raw(rows):
    """전사 결과 모양의 최소 행. temperature는 관측값이다."""
    return [{"id": index, "text": text, "start": start, "end": end,
             "temperature": temp, "avg_logprob": -0.3, "no_speech_prob": 0.1,
             "compression_ratio": 1.4, "words": []}
            for index, (text, start, end, temp) in enumerate(rows)]


RUN = _raw([("아이스크림 완성", 601.0, 602.5, 0.0),
            ("뚜껑을 덮는다", 610.2, 611.9, 0.0)])


# ── T1 · T2 · T3 decoding freeze ────────────────────────────────────────
def test_t1_there_is_no_temperature_fallback_ladder():
    assert canary.DECODING["temperature"] == 0.0
    assert not isinstance(canary.DECODING["temperature"], (list, tuple))
    source = SCRIPT.read_text(encoding="utf-8")
    assert "0.2" not in source and "0.4" not in source     # 사다리 값이 없다


def test_t2_observed_temperature_must_be_zero_only():
    ok, observed = canary.temperature_only_zero(RUN)
    assert ok and observed == [0.0]
    fell_back = _raw([("아이스크림 완성", 601.0, 602.5, 0.4)])
    ok, observed = canary.temperature_only_zero(fell_back)
    assert not ok and observed == [0.4]


def test_t3_vad_filter_is_on():
    assert canary.DECODING["vad_filter"] is True


def test_t4_the_vad_parameters_are_exactly_the_phase_a_values():
    assert canary.VAD_PARAMS == sidecar.VAD_PARAMS
    assert canary.assert_vad_params(dict(canary.VAD_PARAMS)) is None
    with pytest.raises(canary.CanaryError):
        canary.assert_vad_params(dict(canary.VAD_PARAMS, threshold=0.4))


def test_t5_the_canary_interval_is_the_frozen_one():
    assert canary.CANARY_RANGE_SEC == (600, 780)


# ── T6 · T7 격리 ────────────────────────────────────────────────────────
def test_t6_the_two_run_namespaces_must_differ(tmp_path):
    one, two = tmp_path / "canary_run1", tmp_path / "canary_run2"
    assert canary.assert_isolated(one, two) is None
    with pytest.raises(canary.CanaryError):
        canary.assert_isolated(one, one)


def test_t6_a_run_directory_that_already_holds_a_transcript_is_refused(tmp_path):
    used = tmp_path / "canary_run2"
    used.mkdir()
    (used / "transcript.json").write_text("{}", encoding="utf-8")
    with pytest.raises(canary.CanaryError):
        canary.assert_clean_run_dir(used)


def test_t7_a_changed_old_artifact_is_detected(tmp_path):
    watched = tmp_path / "stt_cache.json"
    watched.write_text('{"utterances": []}', encoding="utf-8")
    before = canary.digests({"stt_cache": watched})
    watched.write_text('{"utterances": [1]}', encoding="utf-8")
    after = canary.digests({"stt_cache": watched})
    assert canary.unchanged(before, before) is True
    assert canary.unchanged(before, after) is False


# ── T8 canonical mapping ────────────────────────────────────────────────
def test_t8_canonical_segment_metadata_must_be_identical():
    segments = [{"idx": 120, "start": 600, "end": 605},
                {"idx": 121, "start": 605, "end": 610}]
    assert canary.canonical_mapping(segments, (600, 780)) == [
        {"segment_id": 120, "start": 600, "end": 605},
        {"segment_id": 121, "start": 605, "end": 610}]
    moved = [{"idx": 120, "start": 600, "end": 606},
             {"idx": 121, "start": 606, "end": 610}]
    assert canary.canonical_mapping(segments, (600, 780)) != \
        canary.canonical_mapping(moved, (600, 780))


# ── T9 · T10 · T11 비교기 ────────────────────────────────────────────────
def test_t9_two_identical_runs_compare_equal():
    verdict = canary.compare_runs(RUN, [dict(row) for row in RUN])
    assert verdict["identical"] is True
    assert verdict["utterance_count"] == {"run1": 2, "run2": 2}
    assert verdict["text_mismatches"] == [] and verdict["timing_mismatches"] == []


def test_t10_a_text_mismatch_fails_the_canary():
    other = [dict(RUN[0], text="아이스크림 완성입니다"), dict(RUN[1])]
    verdict = canary.compare_runs(RUN, other)
    assert verdict["identical"] is False
    assert verdict["text_mismatches"]
    assert canary.determinism_verdict(verdict) == "FAIL"


def test_t10_a_count_mismatch_fails_the_canary():
    verdict = canary.compare_runs(RUN, RUN[:1])
    assert verdict["identical"] is False
    assert canary.determinism_verdict(verdict) == "FAIL"


def test_t11_a_timestamp_mismatch_is_detected_not_hidden():
    other = [dict(RUN[0], start=601.5), dict(RUN[1])]
    verdict = canary.compare_runs(RUN, other)
    assert verdict["identical"] is False
    assert verdict["timing_mismatches"]
    assert verdict["text_mismatches"] == []      # 내용 차이와 섞지 않는다


def test_whitespace_only_difference_is_reported_as_normalized_equal():
    other = [dict(RUN[0], text="  아이스크림   완성 "), dict(RUN[1])]
    verdict = canary.compare_runs(RUN, other)
    assert verdict["identical"] is True          # 정규화 후 같다
    assert verdict["raw_text_differences"] == 1  # 그래도 숨기지 않는다


def test_timestamp_validity_counts_the_broken_rows():
    broken = _raw([("가", 5.0, 4.0, 0.0), ("나", 7.0, 7.0, 0.0),
                   ("다", 8.0, 9.0, 0.0)])
    stats = canary.timestamp_validity(broken)
    assert stats == {"rows": 3, "start_gt_end": 1, "zero_duration": 1,
                     "nonfinite": 0}


# ── T12 zero-overlap metric ─────────────────────────────────────────────
def test_t12_zero_overlap_is_computed_from_the_frozen_intervals():
    speech = [(601.0, 602.0)]                     # frozen VAD speech 구간
    rows = _raw([("겹친다", 601.2, 601.8, 0.0), ("안 겹친다", 700.0, 701.0, 0.0)])
    counts = canary.overlap_counts(rows, speech)
    assert counts == {"utterances": 2, "zero_overlap": 1, "with_overlap": 1}


def test_t12_the_rule_input_is_only_the_overlap():
    source = SCRIPT.read_text(encoding="utf-8")
    body = source[source.index("def overlap_counts"):]
    body = body[:body.index("\ndef ")]
    for forbidden in ("no_speech_prob", "latin", "repeat", "compression"):
        assert forbidden not in body


# ── T13 lineage ─────────────────────────────────────────────────────────
def test_t13_the_lineage_keeps_every_raw_row_including_empty_ones():
    rows = _raw([("있다", 601.0, 602.0, 0.0), ("   ", 603.0, 604.0, 0.0)])
    lineage = canary.lineage(rows)
    assert len(lineage) == 2
    assert [item["kept"] for item in lineage] == [True, False]
    assert lineage[1]["drop_reason"] == "empty_text"


# ── T14 full run 차단 ───────────────────────────────────────────────────
def test_t14_a_full_range_run_needs_an_explicit_approval_flag():
    assert canary.guard_range(canary.CANARY_RANGE_SEC, approved=False) is None
    with pytest.raises(canary.CanaryError):
        canary.guard_range((0, 2424), approved=False)
    assert canary.FULL_RUN_APPROVED is False


def test_the_gate_table_matches_the_preregistration():
    assert canary.GATES == ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
    prereg = (ROOT / "docs/preregistration/STT_RETRANSCRIBE_V1_2026-09-08.md"
              ).read_text(encoding="utf-8")
    for gate in canary.GATES:
        assert gate in prereg


def test_the_script_never_edits_the_transcript_text():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (".replace(", "blacklist", "vocabulary", "hotword",
                      "initial_prompt"):
        assert forbidden not in source


def test_the_canary_never_applies_an_eligibility_rule():
    """VAD0 자동 승계 금지 — canary는 세지만 빼지 않는다."""
    speech = [(601.0, 602.0)]
    rows = _raw([("겹친다", 601.2, 601.8, 0.0), ("안 겹친다", 700.0, 701.0, 0.0)])
    assert len(canary.lineage(rows)) == len(rows)
    assert {item["drop_reason"] for item in canary.lineage(rows)} <= {
        None, "empty_text"}
    counts = canary.overlap_counts(rows, speech)
    assert counts["utterances"] == len(rows)          # 아무 행도 사라지지 않는다
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("usable_for_claims", "SUSPECT", "shadow_vad0"):
        assert forbidden not in source


def test_the_mapping_range_comes_from_the_segments_own_time_base():
    """클립 segments는 상대 시간이다 — 요청 범위로 필터하면 0행이 되어 공허히 통과한다."""
    segments = [{"idx": 0, "start": 0, "end": 5}, {"idx": 35, "start": 175,
                                                   "end": 180}]
    assert canary.segments_range(segments) == (0, 180)
    assert canary.canonical_mapping(segments, (600, 780)) == []      # 결함 재현
    assert len(canary.canonical_mapping(
        segments, canary.segments_range(segments))) == 2
    with pytest.raises(canary.CanaryError):
        canary.segments_range([])
