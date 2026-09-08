"""300초 presentation grouping · 중복 제거 · 결론 문구 (2026-09-08 · P1 · P2-2).

사전등록: `docs/finalization/V2_1_OUTPUT_QUALITY_ADDENDUM_2026-09-08.md` §5

```
presentation_group_window_sec = 300   presentation-format 상수 (canonical 파생 아님)
anchor                        = 0초
assignment                    = episode.start_sec가 속한 bin
canonical episode split       금지
```
"""
from pathlib import Path

from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_presentation import (
    PRESENTATION_GROUP_WINDOW_SEC,
    presentation_groups,
)
from v2_1_presentation_input import PresentationEpisode, PresentationInput
from v2_1_synthesis import build_synthesis

ROOT = Path(__file__).resolve().parents[1]


def _presented(count=41, window=60.0):
    episodes = tuple(
        PresentationEpisode(
            episode_id="EP%02d" % (index + 1), start_seg=index * 12,
            end_seg=index * 12 + 11, start_sec=index * window,
            end_sec=(index + 1) * window, source="stt",
            content_status="VALID_PARSE",
            summary="구간 %d 요약이다." % (index + 1), dialogue_note=None,
            grounding_status="NOT_APPLICABLE", anchor_cites=(),
            provenance=("m3_generate",))
        for index in range(count))
    return PresentationInput(schema="aar_canonical_v2_1", video_id="QG",
                             run_id="run-group", episodes=episodes)


# ── freeze된 상수 ────────────────────────────────────────────────────────
def test_the_window_is_a_named_frozen_constant():
    assert PRESENTATION_GROUP_WINDOW_SEC == 300


def test_the_orchestrator_does_not_inline_the_window():
    """창 길이는 상수 한 곳에서만 온다 — 호출부가 숫자를 넘기지 않는다."""
    source = (ROOT / "scripts/v2_1_b2_orchestrate.py").read_text(encoding="utf-8")
    assert "presentation_groups(presented)" in source
    s6 = source[source.index("def s6_presentation"):]
    s6 = s6[:s6.index("def s7_hwpx")]
    assert "window_sec=" not in s6
    assert "PRESENTATION_GROUP_WINDOW_SEC =" not in source


# ── grouping 성질 ────────────────────────────────────────────────────────
def test_every_episode_appears_exactly_once():
    presented = _presented()
    groups = presentation_groups(presented)
    flat = [ref for group in groups for ref in group]
    assert flat == [episode.episode_id for episode in presented.episodes]


def test_a_forty_minute_video_of_sixty_second_episodes_makes_nine_groups():
    """41 × 60초를 300초 bin에 넣으면 9개다. 개수를 목표로 삼지 않는다 — 결과다."""
    assert len(presentation_groups(_presented())) == 9


def test_each_group_holds_the_episodes_of_its_own_bin():
    groups = presentation_groups(_presented())
    assert groups[0] == ("EP01", "EP02", "EP03", "EP04", "EP05")
    assert groups[-1] == ("EP41",)


def test_empty_bins_produce_no_group():
    presented = _presented(count=2, window=1200.0)     # 0초 · 1200초
    groups = presentation_groups(presented)
    assert groups == (("EP01",), ("EP02",))


def test_the_grouping_is_deterministic_and_ignores_input_order():
    presented = _presented(count=6)
    reversed_input = PresentationInput(
        schema=presented.schema, video_id=presented.video_id,
        run_id=presented.run_id, episodes=tuple(reversed(presented.episodes)))
    assert presentation_groups(presented) == presentation_groups(reversed_input)


def test_no_canonical_episode_is_split():
    presented = _presented()
    for group in presentation_groups(presented):
        for ref in group:
            episode = presented.episode(ref)
            assert episode.start_seg < episode.end_seg          # 경계 무변경


def test_the_grouping_reads_no_content():
    """내용 기반 boundary provider를 만들지 않았다."""
    source = (ROOT / "src/v2_1_presentation.py").read_text(encoding="utf-8")
    body = source.split("def presentation_groups")[1].split("\ndef ")[0]
    for forbidden in ("summary", "caption", "subtitle", "dialogue"):
        assert forbidden not in body


# ── 중복 제거 (P1-3) ─────────────────────────────────────────────────────
def _synthesis(presented):
    groups = presentation_groups(presented)
    highlights = build_highlights(presented, [HighlightSpec(g) for g in groups])
    return build_synthesis(presented, build_lineage(presented, highlights))


def test_the_analysis_section_no_longer_reprints_the_summaries():
    presented = _presented()
    synthesis = _synthesis(presented)
    for line in synthesis.analysis:
        for episode in presented.episodes:
            assert episode.summary not in line


def test_the_analysis_still_carries_the_highlight_lineage():
    """GLS-002 계약 — highlight 구조와 구성 episode는 그대로 적는다."""
    synthesis = _synthesis(_presented())
    assert synthesis.analysis[0].startswith("H01")
    assert "EP01" in synthesis.analysis[0]
    assert len(synthesis.analysis) == 9


# ── 결론 문구 (P2-2) ─────────────────────────────────────────────────────
def test_the_conclusion_no_longer_says_verified():
    synthesis = _synthesis(_presented())
    assert "확인된 구간" not in synthesis.conclusion
    assert "요약이 제공된 구간" in synthesis.conclusion


def test_the_no_content_conclusion_also_avoids_the_verified_wording():
    from v2_1_synthesis import _NO_CONTENT_CONCLUSION
    assert "확인된" not in _NO_CONTENT_CONCLUSION
    assert "결론을 적지 않는다" in _NO_CONTENT_CONCLUSION
