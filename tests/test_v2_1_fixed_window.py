"""A-08 fixed_window_v1 — 내용을 보지 않는 결정적 시간 partition.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-08
규격: SPEC §"default: fixed_window_v1" — 60초 창

```
의미적 경계를 확신할 수 없으므로 canonical 시간 partition을 단순하고 결정적인
방식으로 유지한다.
```

근거는 모델 진단이다. **붕괴하지 않은 arm도 간격 10(50초) 등차수열**을 냈다
(Qwen `[110,120,130,140,150]` · Kanana `[225,245,255,265,275]`). 정상으로 보이는
출력조차 사실상 균등 분할이었으므로, 균등 분할을 모델에게 시킬 이유가 없다.
"""
import re
from pathlib import Path

import pytest

from v2_1_boundary import DEFAULT_PROVIDER_NAME, ProviderError, ProviderRegistry
from v2_1_fixed_window import WINDOW_SEC, FixedWindowV1, window_spans
from v2_1_fixtures import scenario
from v2_1_segments import legacy_segments_to_canonical

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_fixed_window.py"


def _segments(count, seg_sec=5.0, tail_sec=None):
    legacy = [{"idx": i, "start": i * seg_sec, "end": i * seg_sec + seg_sec}
              for i in range(count)]
    if tail_sec is not None:
        last = legacy[-1]
        legacy[-1] = {"idx": last["idx"], "start": last["start"],
                      "end": last["start"] + tail_sec}
    return legacy_segments_to_canonical(legacy)


@pytest.fixture
def registry():
    r = ProviderRegistry()
    r.register(FixedWindowV1())
    return r


# ── 등록 ─────────────────────────────────────────────────────────────────
def test_it_registers_under_the_default_name(registry):
    assert FixedWindowV1.name == DEFAULT_PROVIDER_NAME
    result = registry.run(None, _segments(12))
    assert result.provider_name == DEFAULT_PROVIDER_NAME


def test_window_is_sixty_seconds():
    assert WINDOW_SEC == 60.0


def test_config_is_recorded_even_when_defaulted(registry):
    result = registry.run(None, _segments(12))
    assert result.provider_config["window_sec"] == 60.0


# ── FW-001 deterministic ─────────────────────────────────────────────────
def test_fw_001_identical_input_gives_identical_partition(registry):
    segments = _segments(37)
    runs = [registry.run(None, segments).boundary_positions for _ in range(5)]
    assert all(r == runs[0] for r in runs)


def test_fw_010_long_input_is_deterministic(registry):
    segments = _segments(720)          # 1시간
    first = registry.run(None, segments).boundary_positions
    assert first == registry.run(None, segments).boundary_positions
    assert len(first) == 60


# ── FW-002~005 채널 독립 ─────────────────────────────────────────────────
def test_fw_002_to_005_boundaries_ignore_every_content_channel(registry):
    segments = _segments(37)
    baseline = registry.run(None, segments).boundary_positions
    assert registry.run(
        None, segments,
        caption_embeddings=[[0.9]] * 37,
        boundary_signal=[1.0] * 37,
    ).boundary_positions == baseline


def test_fw_002_to_005_same_grid_different_content_same_partition():
    """S1·S3·S4·S5는 채널만 다르고 segment 격자는 같다."""
    partitions = {
        name: window_spans(scenario(name).segments)
        for name in ("S1", "S3", "S4", "S5")
    }
    assert len(set(map(tuple, partitions.values()))) == 1


def test_provider_does_not_read_content_channels():
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("caption", "asr", "ocr", "subtitle", "text"):
        assert forbidden not in src.lower().replace("caption_embeddings", ""), (
            "내용 채널을 읽고 있다: " + forbidden
        )


# ── FW-006 exact duration ────────────────────────────────────────────────
def test_fw_006_exact_sixty_seconds_is_one_window():
    segments = scenario("S1").segments
    spans = window_spans(segments)
    assert spans == [(0, 11)]
    assert _covered(spans, segments) == 60.0


# ── FW-007 partial tail ──────────────────────────────────────────────────
def test_fw_007_partial_tail_is_included():
    segments = scenario("S2").segments          # 62s
    spans = window_spans(segments)
    assert spans == [(0, 11), (12, 12)]
    assert _covered(spans, segments) == 62.0


def test_fw_007_only_the_last_segment_may_be_short():
    segments = scenario("S2").segments
    assert {s.duration_sec for s in segments[:-1]} == {5.0}
    assert segments[-1].duration_sec == 2.0


def test_fw_007_boundary_lands_on_a_segment_start():
    segments = _segments(25)
    starts = {s.segment_id: s.start_sec for s in segments}
    for segment_id in FixedWindowV1()(segments).boundary_positions:
        assert segment_id in starts


# ── FW-008 very short video ──────────────────────────────────────────────
def test_fw_008_video_shorter_than_one_segment_is_a_single_window():
    segments = legacy_segments_to_canonical([{"idx": 0, "start": 0, "end": 3.0}])
    spans = window_spans(segments)
    assert spans == [(0, 0)]
    assert _covered(spans, segments) == 3.0


def test_fw_008_short_video_still_records_provider(registry):
    segments = legacy_segments_to_canonical([{"idx": 0, "start": 0, "end": 3.0}])
    assert registry.run(None, segments).boundary_positions == [0]


# ── FW-009 zero duration ─────────────────────────────────────────────────
def test_fw_009_empty_segment_list_fails_explicitly(registry):
    with pytest.raises(ProviderError, match="no segments"):
        registry.run(None, [])


def test_fw_009_window_spans_refuses_empty_input():
    with pytest.raises(ValueError, match="no segments"):
        window_spans([])


def test_fw_009_non_positive_window_is_refused():
    with pytest.raises(ValueError, match="window_sec"):
        window_spans(_segments(12), window_sec=0)


# ── partition 성질 ───────────────────────────────────────────────────────
def test_windows_are_contiguous_and_complete():
    segments = _segments(37)
    spans = window_spans(segments)
    assert spans[0][0] == 0
    assert spans[-1][1] == 36
    for (_, end), (start, _) in zip(spans, spans[1:]):
        assert start == end + 1


def test_each_window_holds_twelve_segments_when_the_grid_divides_evenly():
    spans = window_spans(_segments(36))
    assert spans == [(0, 11), (12, 23), (24, 35)]


def test_a_segment_is_assigned_by_its_start_time():
    """창 경계에 걸친 segment는 시작 시각으로 귀속된다 — 규칙 하나뿐이다."""
    segments = _segments(9, seg_sec=7.0)        # 63s · 창 경계가 segment 안쪽
    spans = window_spans(segments)
    assert spans == [(0, 8)]                    # seg#8은 56s에서 시작한다
    assert window_spans(_segments(10, seg_sec=7.0)) == [(0, 8), (9, 9)]


def _covered(spans, segments):
    by_id = {s.segment_id: s for s in segments}
    total = 0.0
    for start, end in spans:
        total += by_id[end].end_sec - by_id[start].start_sec
    return total


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_a08_does_not_validate_partitions():
    """검증은 A-09가 독립적으로 한다 — 같은 코드로 만들고 검사하면 같이 틀린다."""
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("validate", "invariant", "CAN-"):
        assert forbidden not in src, "A-09 책임을 침범했다: " + forbidden


def test_a08_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
