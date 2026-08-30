"""A-10 fixture 자체 검증.

fixture가 이름표대로 생기지 않았으면 그것을 쓰는 A-05·A-08·A-09 테스트가
**엉뚱한 것을 통과시킨다.** 여기서 각 시나리오의 선언을 실제로 확인한다.
"""
import re
from pathlib import Path

import pytest

from v2_1_scan import code_only
from v2_1_fixtures import (
    BOILERPLATE,
    CANONICAL_PARTITION,
    CORRUPT_PARTITIONS,
    EXCITED_SPEECH,
    INSTRUCTION_ECHO,
    MALFORMED_PAYLOAD,
    SCENARIOS,
    assigned_counts,
    scenario,
)

SRC = Path(__file__).resolve().parents[1] / "tests/v2_1_fixtures.py"


def test_all_eight_scenarios_exist():
    assert sorted(SCENARIOS) == ["S%d" % i for i in range(1, 9)]


def test_every_scenario_has_a_valid_canonical_segment_list():
    for name, s in SCENARIOS.items():
        assert s.segments, name
        assert s.segment_ids == sorted(set(s.segment_ids)), name
        for previous, current in zip(s.segments, s.segments[1:]):
            assert previous.end_sec == current.start_sec, name
            assert current.duration_sec == current.end_sec - current.start_sec


def test_s1_is_exactly_60_seconds():
    s = scenario("S1")
    assert len(s.segments) == 12
    assert s.duration_sec == 60.0
    assert {seg.duration_sec for seg in s.segments} == {5.0}


def test_s1_captions_are_distinct():
    """같은 캡션을 12번 두면 캡션 채널 전체가 반복 판정에 걸려 기준선이 퇴화한다."""
    caption = scenario("S1").caption
    assert len(set(caption.values())) == len(caption)


def test_s2_has_a_short_tail_only():
    s = scenario("S2")
    assert s.duration_sec == 62.0
    assert {seg.duration_sec for seg in s.segments[:-1]} == {5.0}
    assert s.segments[-1].duration_sec == 2.0


def test_s3_has_captions_and_no_stt():
    s = scenario("S3")
    assert s.caption and not s.asr


def test_s4_has_stt_and_no_captions():
    s = scenario("S4")
    assert s.asr and not s.caption


def test_s5_is_empty_but_present():
    """'채널이 없다'와 '채널이 비었다'는 다르다 — EMPTY 판정의 입력."""
    s = scenario("S5")
    assert set(s.asr) == set(s.caption) == set(s.ocr) == set(s.segment_ids)
    assert set(s.asr.values()) == set(s.caption.values()) == {""}


def test_s6_carries_the_real_instruction_echo():
    s = scenario("S6")
    assert s.caption[3] == INSTRUCTION_ECHO
    assert re.search(r"[一-鿿]", s.caption[7]), "외국어 캡션 표본이 없다"
    assert sum(1 for v in s.caption.values() if v == INSTRUCTION_ECHO) == 1


def test_s7_payload_is_broken_json():
    import json

    with pytest.raises(json.JSONDecodeError):
        json.loads(MALFORMED_PAYLOAD)
    assert scenario("S7").caption[5] == MALFORMED_PAYLOAD


def test_s8_asserts_only_through_ocr():
    s = scenario("S8")
    assert not s.asr and not s.caption
    assert sum(1 for v in s.ocr.values() if v.strip()) == 1


# ── SAN-010 vs SAN-011을 한 영상 안에서 가른다 ───────────────────────────
def test_s1_holds_both_repetition_cases():
    s = scenario("S1")
    assert sum(1 for v in s.asr.values() if v == BOILERPLATE) == 8
    assert EXCITED_SPEECH in s.asr.values()
    assert sum(1 for v in s.asr.values() if v == EXCITED_SPEECH) == 1


def test_excited_speech_is_not_boilerplate():
    """반복 부호가 있다고 boilerplate가 되지는 않는다 — 지웠던 사고의 표본."""
    assert EXCITED_SPEECH != BOILERPLATE
    assert EXCITED_SPEECH.count("나 잡았어") == 2


# ── partition fixture ────────────────────────────────────────────────────
def test_canonical_partition_assigns_every_segment_exactly_once():
    counts = assigned_counts(CANONICAL_PARTITION, scenario("S1").segment_ids)
    assert set(counts.values()) == {1}


def test_all_four_corruption_kinds_exist():
    assert sorted(CORRUPT_PARTITIONS) == ["duplicate", "gap", "overlap", "unassigned"]


def test_each_corrupt_partition_is_actually_corrupt():
    ids = scenario("S1").segment_ids
    assert assigned_counts(CORRUPT_PARTITIONS["overlap"], ids)[4] == 2
    assert assigned_counts(CORRUPT_PARTITIONS["gap"], ids)[4] == 0
    assert assigned_counts(CORRUPT_PARTITIONS["duplicate"], ids)[0] == 2
    assert assigned_counts(CORRUPT_PARTITIONS["unassigned"], ids)[11] == 0


def test_corrupt_partitions_differ_from_the_canonical_one():
    for name, spans in CORRUPT_PARTITIONS.items():
        assert spans != CANONICAL_PARTITION, name


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_fixtures_do_not_read_real_pipeline_artifacts():
    """`work/`·`runs/`에 의존하면 인덱스 재생성마다 Gate A가 흔들린다."""
    code = code_only(SRC)
    for forbidden in ("work/", "runs/", "segments.json", "open", "read_text"):
        assert forbidden not in code, "실제 산출물에 의존한다: " + forbidden


def test_fixtures_do_not_import_pipeline_modules():
    code = code_only(SRC)
    for forbidden in ("common", "m5_search", "m6_evaluate", "bcs"):
        assert forbidden not in code, "fixture가 파이프라인을 끌어온다: " + forbidden
