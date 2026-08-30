"""B-01 Episode 구조 + content 스키마 — 구조는 코드가 갖는다.

티켓: Gate B / B-01
규격: SPEC §13(모델에게 요구하는 것은 summary 하나) · §14(support는 코드가 파생)

```
모델이 내는 것    summary · (선택) dialogue_note · stt_cites
코드가 정하는 것  episode_id · start_seg · end_seg · start_sec · end_sec
                 support_span · anchor_cites · source
```

이 파일은 **LLM을 호출하지 않는다.** 구조가 모델과 무관하게 결정된다는 것 자체가
LLM-001·003·004·005의 내용이다.
"""
import re
from pathlib import Path

import pytest

from v2_1_episode import (
    DERIVED_FIELDS,
    MAX_ANCHORS,
    MODEL_FIELDS,
    EpisodeContent,
    EpisodeError,
    anchors,
    build_episodes,
    derive_source,
)
from v2_1_fixed_window import window_spans
from v2_1_fixtures import CANONICAL_PARTITION, scenario
from v2_1_sanitation import classify_channel
from v2_1_scan import code_only
from v2_1_timeline import build_timeline

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_episode.py"


@pytest.fixture
def segments():
    return scenario("S1").segments


@pytest.fixture
def timeline():
    s = scenario("S1")
    judged = {
        "asr": classify_channel(s.asr, "asr"),
        "vlm": classify_channel(s.caption, "vlm"),
    }
    return build_timeline(s.segments, judged)


# ── LLM-003 episode_id는 코드 값 ─────────────────────────────────────────
def test_llm_003_episode_ids_are_code_derived_and_ordered(segments):
    episodes = build_episodes(CANONICAL_PARTITION, segments)
    assert [e.episode_id for e in episodes] == ["EP01", "EP02", "EP03"]


def test_llm_003_ids_are_stable_across_rebuilds(segments):
    first = [e.episode_id for e in build_episodes(CANONICAL_PARTITION, segments)]
    second = [e.episode_id for e in build_episodes(CANONICAL_PARTITION, segments)]
    assert first == second


def test_llm_003_id_width_survives_many_episodes():
    s = scenario("S2")
    spans = [(i, i) for i in s.segment_ids]
    episodes = build_episodes(spans, s.segments)
    assert episodes[0].episode_id == "EP01"
    assert episodes[-1].episode_id == "EP13"


# ── LLM-001 경계는 모델이 만들지 않는다 ─────────────────────────────────
def test_llm_001_episode_times_come_from_segments(segments):
    episodes = build_episodes(CANONICAL_PARTITION, segments)
    by_id = {s.segment_id: s for s in segments}
    for episode in episodes:
        assert episode.start_sec == by_id[episode.start_seg].start_sec
        assert episode.end_sec == by_id[episode.end_seg].end_sec


def test_llm_001_episodes_follow_the_given_partition(segments):
    episodes = build_episodes(CANONICAL_PARTITION, segments)
    assert [(e.start_seg, e.end_seg) for e in episodes] == CANONICAL_PARTITION


def test_llm_001_builder_takes_no_model_output(segments):
    """구조 생성에 모델 출력이 들어갈 자리가 없다."""
    import inspect

    parameters = set(inspect.signature(build_episodes).parameters)
    assert not parameters & {"summary", "content", "llm", "model", "response"}


def test_llm_001_source_has_no_model_call():
    code = code_only(SRC)
    for forbidden in ("make_llm", "generate", "prompt", "torch", "transformers"):
        assert forbidden not in code, "구조 계층이 모델을 부른다: " + forbidden


def test_llm_001_invalid_partition_is_refused(segments):
    with pytest.raises(EpisodeError):
        build_episodes([(4, 0)], segments)


def test_llm_001_unknown_segment_is_refused(segments):
    with pytest.raises(EpisodeError, match="unknown segment"):
        build_episodes([(0, 99)], segments)


# ── LLM-004 support span은 코드 파생 ─────────────────────────────────────
def test_llm_004_support_span_equals_the_episode_span(segments):
    for episode in build_episodes(CANONICAL_PARTITION, segments):
        assert episode.support_span == {"start_seg": episode.start_seg,
                                        "end_seg": episode.end_seg}


def test_llm_004_anchors_are_start_middle_end():
    assert anchors(51, 79) == [51, 65, 79]


def test_llm_004_short_span_lists_every_segment():
    assert anchors(4, 6) == [4, 5, 6]
    assert anchors(7, 7) == [7]


def test_llm_004_anchor_count_is_capped():
    assert MAX_ANCHORS == 3
    assert len(anchors(0, 500)) <= MAX_ANCHORS


def test_llm_004_anchors_lie_inside_the_span(segments):
    for episode in build_episodes(CANONICAL_PARTITION, segments):
        for cite in episode.anchor_cites:
            assert episode.start_seg <= cite <= episode.end_seg


def test_llm_004_reversed_span_is_refused():
    with pytest.raises(EpisodeError, match="support span"):
        anchors(9, 4)


# ── LLM-005 provenance는 코드 파생 ───────────────────────────────────────
def test_llm_005_source_is_stt_when_usable_speech_exists(segments, timeline):
    episodes = build_episodes(CANONICAL_PARTITION, segments, timeline=timeline)
    assert episodes[2].source == "stt"       # seg#8~11에 실제 발화가 있다


def test_llm_005_source_is_visual_without_usable_speech(segments, timeline):
    episodes = build_episodes(CANONICAL_PARTITION, segments, timeline=timeline)
    assert episodes[0].source == "visual"    # seg#0~3은 boilerplate뿐이다


def test_llm_005_suspect_speech_does_not_make_it_stt(segments, timeline):
    """SUSPECT는 보존되지만 근거가 아니다 — source도 그것으로 바뀌지 않는다."""
    first = build_episodes(CANONICAL_PARTITION, segments, timeline=timeline)[0]
    entry_refs = [r for e in timeline[0:4] for r in e.asr_refs]
    assert entry_refs and all(r.status == "SUSPECT" for r in entry_refs)
    assert first.source == "visual"


def test_llm_005_source_is_visual_without_a_timeline(segments):
    for episode in build_episodes(CANONICAL_PARTITION, segments):
        assert episode.source == "visual"


def test_llm_005_derive_source_is_deterministic(segments, timeline):
    assert derive_source(0, 3, timeline) == derive_source(0, 3, timeline) == "visual"
    assert derive_source(8, 11, timeline) == "stt"


# ── LLM-002 모델 출력은 최소 ─────────────────────────────────────────────
def test_llm_002_model_fields_are_exactly_three():
    assert MODEL_FIELDS == ("summary", "dialogue_note", "stt_cites")


def test_llm_002_derived_fields_do_not_overlap_model_fields():
    assert not set(DERIVED_FIELDS) & set(MODEL_FIELDS)


def test_llm_002_summary_is_the_only_required_content_field():
    content = EpisodeContent(summary="해변에서 소스를 넣는다.")
    assert content.dialogue_note is None
    assert content.stt_cites == ()


def test_llm_002_blank_summary_is_refused():
    with pytest.raises(EpisodeError, match="summary"):
        EpisodeContent(summary="   ")


def test_llm_002_banned_canonical_fields_are_absent(segments):
    episode = build_episodes(CANONICAL_PARTITION, segments)[0]
    for banned in ("title", "key_actions", "actors", "importance",
                   "uncertainty_note"):
        assert not hasattr(episode, banned), banned


def test_llm_002_episodes_start_without_content(segments):
    """구조가 먼저 선다. 내용은 나중에 붙는다."""
    assert all(e.content is None for e in build_episodes(CANONICAL_PARTITION, segments))


def test_llm_002_episode_is_immutable(segments):
    episode = build_episodes(CANONICAL_PARTITION, segments)[0]
    with pytest.raises(Exception):
        episode.episode_id = "EP99"


# ── 빌더 출력과 이어진다 ─────────────────────────────────────────────────
def test_episodes_build_from_the_fixed_window_partition():
    s = scenario("S2")
    episodes = build_episodes(window_spans(s.segments), s.segments)
    assert [(e.start_seg, e.end_seg) for e in episodes] == [(0, 11), (12, 12)]
    assert episodes[-1].end_sec == 62.0


def test_every_segment_belongs_to_exactly_one_episode(segments):
    episodes = build_episodes(CANONICAL_PARTITION, segments)
    owned = [seg for e in episodes for seg in range(e.start_seg, e.end_seg + 1)]
    assert sorted(owned) == [s.segment_id for s in segments]


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_b01_does_not_reimplement_gate_a():
    code = code_only(SRC)
    for forbidden in ("REPEAT_THRESHOLD", "window_spans", "RawStore",
                      "validate_partition", "classify"):
        assert forbidden not in code, "Gate A 기능을 다시 구현했다: " + forbidden


def test_b01_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
