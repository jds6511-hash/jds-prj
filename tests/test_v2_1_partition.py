"""A-09 canonical partition validator — 만든 코드와 따로 검사한다.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-09
근거: ADDENDUM OPEN-2 (`canonical_video_end := last_segment.end_sec`)

**빌더(A-08)와 같은 helper로 coverage를 계산하면 공통 버그가 있을 때 둘이 함께
통과한다.** 그래서 이 계층은 span에서 시간축을 다시 구성해 독립적으로 잰다.

hard gate다 — 실패하면 canonical artifact를 만들지 않는다.
"""
import re
from pathlib import Path

import pytest

from v2_1_fixed_window import window_spans
from v2_1_fixtures import CANONICAL_PARTITION, CORRUPT_PARTITIONS, scenario
from v2_1_partition import (
    PartitionInvalid,
    assert_valid_partition,
    canonical_video_end,
    canonical_video_start,
    validate_partition,
)

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_partition.py"


@pytest.fixture
def segments():
    return scenario("S1").segments


def _codes(spans, segments):
    return {f.code for f in validate_partition(spans, segments).failures}


# ── CAN-001~003 기본 불변식 ──────────────────────────────────────────────
def test_can_001_to_003_a_correct_partition_passes(segments):
    result = validate_partition(CANONICAL_PARTITION, segments)
    assert result.ok
    assert result.failures == []


def test_can_003_every_segment_is_assigned_exactly_once(segments):
    result = validate_partition(CANONICAL_PARTITION, segments)
    assert result.assigned_once is True


def test_builder_output_passes_the_independent_validator():
    for name in ("S1", "S2", "S3"):
        segments = scenario(name).segments
        assert validate_partition(window_spans(segments), segments).ok, name


# ── CAN-004·005 시간축 양끝 ──────────────────────────────────────────────
def test_can_004_and_005_video_bounds_come_from_the_segment_list(segments):
    assert canonical_video_start(segments) == 0.0
    assert canonical_video_end(segments) == 60.0


def test_can_005_end_is_the_last_segment_end_not_a_rounded_duration():
    """OPEN-2 — 62s fixture의 끝은 65.0이 아니라 62.0이다."""
    segments = scenario("S2").segments
    assert canonical_video_end(segments) == 62.0


def test_can_004_partition_not_starting_at_video_start_fails(segments):
    assert "START_MISMATCH" in _codes([(1, 11)], segments)


def test_can_005_partition_not_ending_at_video_end_fails(segments):
    assert "END_MISMATCH" in _codes([(0, 10)], segments)


# ── CAN-006~008 순서·길이·연속 ───────────────────────────────────────────
def test_can_006_out_of_order_spans_fail(segments):
    assert "NON_MONOTONIC" in _codes([(4, 7), (0, 3), (8, 11)], segments)


def test_can_007_reversed_span_fails(segments):
    assert "NON_POSITIVE_DURATION" in _codes([(0, 3), (7, 4), (8, 11)], segments)


def test_can_008_discontinuity_between_adjacent_spans_fails(segments):
    codes = _codes([(0, 3), (5, 7), (8, 11)], segments)
    assert "DISCONTINUITY" in codes


# ── CAN-009 참조 유효성 ──────────────────────────────────────────────────
def test_can_009_unknown_segment_reference_fails(segments):
    assert "UNKNOWN_SEGMENT" in _codes([(0, 3), (4, 7), (8, 99)], segments)


def test_can_009_unknown_reference_does_not_crash_other_checks(segments):
    result = validate_partition([(0, 99)], segments)
    assert not result.ok
    assert "UNKNOWN_SEGMENT" in {f.code for f in result.failures}


# ── CAN-010~013 주입 4종은 반드시 FAIL ───────────────────────────────────
def test_can_010_overlap_injection_fails(segments):
    assert "OVERLAP" in _codes(CORRUPT_PARTITIONS["overlap"], segments)


def test_can_011_gap_injection_fails(segments):
    assert "GAP" in _codes(CORRUPT_PARTITIONS["gap"], segments)


def test_can_012_duplicate_injection_fails(segments):
    codes = _codes(CORRUPT_PARTITIONS["duplicate"], segments)
    assert "DUPLICATE_SPAN" in codes


def test_can_013_unassigned_injection_fails(segments):
    assert "UNASSIGNED_SEGMENT" in _codes(CORRUPT_PARTITIONS["unassigned"], segments)


def test_all_four_injections_fail(segments):
    for name, spans in CORRUPT_PARTITIONS.items():
        assert not validate_partition(spans, segments).ok, name


def test_every_failure_names_the_offending_segment(segments):
    for spans in CORRUPT_PARTITIONS.values():
        for failure in validate_partition(spans, segments).failures:
            assert failure.detail, failure.code


# ── hard gate ────────────────────────────────────────────────────────────
def test_assert_valid_partition_raises_on_failure(segments):
    with pytest.raises(PartitionInvalid) as caught:
        assert_valid_partition(CORRUPT_PARTITIONS["gap"], segments)
    assert "GAP" in str(caught.value)


def test_assert_valid_partition_returns_nothing_on_success(segments):
    assert assert_valid_partition(CANONICAL_PARTITION, segments) is None


def test_empty_partition_fails(segments):
    assert not validate_partition([], segments).ok


# ── 독립성 ───────────────────────────────────────────────────────────────
def test_validator_does_not_use_the_builder():
    """같은 코드로 만들고 검사하면 공통 버그에서 함께 통과한다."""
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("v2_1_fixed_window", "window_spans", "WINDOW_SEC"):
        assert forbidden not in src, "빌더를 끌어왔다: " + forbidden


def test_validator_catches_a_broken_builder_output(segments):
    """빌더가 틀렸을 때 실제로 잡는지 — 마지막 창을 하나 잘라 본다."""
    spans = window_spans(segments)
    broken = spans[:-1] + [(spans[-1][0], spans[-1][1] - 1)]
    assert not validate_partition(broken, segments).ok


def test_a09_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
