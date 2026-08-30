import pytest

from v2_1_segments import (
    CanonicalSegment,
    SegmentContractError,
    legacy_segment_to_canonical,
    legacy_segments_to_canonical,
)


def test_sch_001_canonical_schema_valid():
    segment = legacy_segment_to_canonical({"idx": 7, "start": 35, "end": 40})
    assert segment.as_dict() == {
        "segment_id": 7,
        "start_sec": 35.0,
        "end_sec": 40.0,
        "duration_sec": 5.0,
    }


@pytest.mark.parametrize("missing", ["idx", "start", "end"])
def test_sch_002_required_legacy_field_missing(missing):
    raw = {"idx": 0, "start": 0, "end": 5}
    raw.pop(missing)
    with pytest.raises(SegmentContractError):
        legacy_segment_to_canonical(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("idx", "0"),
        ("start", "0"),
        ("end", "5"),
        ("idx", True),
        ("start", False),
    ],
)
def test_sch_003_invalid_type(field, value):
    raw = {"idx": 0, "start": 0, "end": 5}
    raw[field] = value
    with pytest.raises(SegmentContractError):
        legacy_segment_to_canonical(raw)


def test_open_1_mapping_is_exact():
    segment = legacy_segment_to_canonical({"idx": 3, "start": 10.25, "end": 15.0})
    assert segment.segment_id == 3
    assert segment.start_sec == 10.25
    assert segment.end_sec == 15.0
    assert segment.duration_sec == 4.75


def test_open_1_mixed_legacy_and_canonical_schema_is_contract_violation():
    raw = {
        "idx": 0,
        "start": 0,
        "end": 5,
        "segment_id": 0,
    }
    with pytest.raises(SegmentContractError, match="mixing"):
        legacy_segment_to_canonical(raw)


def test_duplicate_segment_ids_are_rejected():
    raw = [
        {"idx": 1, "start": 0, "end": 5},
        {"idx": 1, "start": 5, "end": 10},
    ]
    with pytest.raises(SegmentContractError, match="unique"):
        legacy_segments_to_canonical(raw)


def test_invalid_interval_is_rejected():
    with pytest.raises(SegmentContractError):
        legacy_segment_to_canonical({"idx": 0, "start": 5, "end": 5})


def test_canonical_segment_rejects_inconsistent_duration():
    with pytest.raises(SegmentContractError, match="duration_sec"):
        CanonicalSegment(
            segment_id=0,
            start_sec=0,
            end_sec=5,
            duration_sec=4.9,
        )


# ── A-01 티켓 추가 요구: adapter 왕복 · adapter 외부 legacy 필드 미사용 ──────

def test_a01_adapter_roundtrip_preserves_legacy_values():
    """canonical 값에서 legacy 값을 손실 없이 되읽을 수 있다."""
    raw = [
        {"idx": 0, "start": 0, "end": 5},
        {"idx": 1, "start": 5, "end": 10.5},
        {"idx": 2, "start": 10.5, "end": 12.25},
    ]
    canonical = legacy_segments_to_canonical(raw)
    recovered = [
        {"idx": s.segment_id, "start": s.start_sec, "end": s.end_sec}
        for s in canonical
    ]
    assert recovered == [
        {"idx": 0, "start": 0.0, "end": 5.0},
        {"idx": 1, "start": 5.0, "end": 10.5},
        {"idx": 2, "start": 10.5, "end": 12.25},
    ]
    for s in canonical:
        assert s.duration_sec == s.end_sec - s.start_sec


def test_a01_legacy_fields_are_not_consumed_outside_the_adapter():
    """OPEN-1: adapter 밖에서 idx·start·end를 소비하면 contract violation."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    adapter = root / "src/v2_1_segments.py"
    sources = sorted(root.glob("src/v2_1_*.py")) + sorted(root.glob("scripts/v2_1_*.py"))
    assert adapter in sources, "adapter 모듈이 스캔 대상에 없다 — 스캔 경로가 틀렸다"

    legacy_access = re.compile(
        r"""(\[\s*["'](?:idx|start|end)["']\s*\]|\.get\(\s*["'](?:idx|start|end)["'])"""
    )
    offenders = []
    for path in sources:
        if path == adapter:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if legacy_access.search(line):
                offenders.append(f"{path.relative_to(root)}:{n}: {line.strip()}")
    assert not offenders, "adapter 외부 legacy 필드 접근:\n" + "\n".join(offenders)
