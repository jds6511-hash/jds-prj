"""E-01a ERR 증거 보강 — 세 계약을 **그 결함 입력으로** 잰다.

E-01 감사에서 셋은 `evidence-gap`이었다. 동작은 있고, 그 동작을 실패 경로에서 재는
테스트가 없었다. 여기서 만드는 것은 검사뿐이다 — production 동작은 바꾸지 않는다.

```
ERR-006  highlight builder failure    실패 전후 canonical 지문 동일
ERR-009  all evidence absent          구조는 살아 있고 내용은 지어내지 않는다
ERR-010  instruction echo top signal  최대 peak가 창 경계를 밀지 못한다
```

`ERR-009`는 계층별 동작을 하나씩 확인하는 것으로 닫지 않는다. **전 채널 공백 하나를
정본 → 표현 → 세 renderer까지 태워** "구조는 있다"와 "내용은 없다"를 동시에 본다.
"""
import json
import re

import pytest

from v2_1_boundary import ProviderRegistry
from v2_1_episode import build_episodes
from v2_1_fixed_window import FixedWindowV1, window_spans
from v2_1_fixtures import INSTRUCTION_ECHO, scenario
from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightError, HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_parse import EMPTY, ParseResult
from v2_1_presentation import (
    SUMMARY_NO_RELIABLE_CONTENT,
    build_presentation,
    validate_presentation,
)
from v2_1_presentation_input import (
    presentation_input,
    summary_eligible_for_presentation,
)
from v2_1_prompt import PromptError, build_episode_prompt
from v2_1_render import render_markdown, render_preview
from v2_1_render_hwpx import hwpx_text, render_hwpx
from v2_1_render_probe import _projection
from v2_1_run import Manifest
from v2_1_sanitation import REJECTED, classify_channel
from v2_1_synthesis import (
    NO_RELIABLE_CONTENT,
    build_synthesis,
    validate_synthesis,
)
from v2_1_timeline import build_timeline

THREE = ((0, 3), (4, 7), (8, 11))
CONTENT = tuple({"summary": "구간 %d 요약이다." % i} for i in range(3))

REPORT = Manifest(video_id="S5", run_id="run-err009", analysis_mode="report",
                  config_hash="c0ffee", code_git_head="deadbeef")

#: 한국어 평서문 하나. 없어야 할 곳에 문장이 생기면 이것으로 잡힌다.
_SENTENCE = re.compile(r"[가-힣][^\n]*?다\.")


def _sentences(text: str) -> set:
    return set(_SENTENCE.findall(text))


# ── ERR-006 highlight builder failure ────────────────────────────────────
#: 실패 모드. 첫 spec은 전부 정상이다 — **부분 작업이 이미 일어난 뒤** 실패해야
#: "실패 후 정본 불변"이 의미를 갖는다.
BAD_SPECS = {
    "unknown_episode": (HighlightSpec(("EP01",)), HighlightSpec(("EP99",))),
    "empty_group": (HighlightSpec(("EP01",)), HighlightSpec(())),
    "repeat_in_group": (HighlightSpec(("EP01",)),
                        HighlightSpec(("EP02", "EP02"))),
}


def _fingerprint(document, presented):
    """실패 전후로 같아야 하는 것. 정본 문서와 표현 입구를 함께 본다."""
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True),
        tuple((e.episode_id, e.start_seg, e.end_seg, e.start_sec, e.end_sec)
              for e in presented.episodes),
        len(presented.episodes),
    )


@pytest.mark.parametrize("mode", sorted(BAD_SPECS))
def test_err_006_a_builder_failure_leaves_the_canonical_untouched(tmp_path, mode):
    """highlight builder가 실패해도 정본은 그대로다 — 실패 경로에서 잰다."""
    pipeline = run_pipeline(tmp_path, CONTENT, spans=THREE)
    presented = presentation_input(pipeline.document)
    before = _fingerprint(pipeline.document, presented)

    with pytest.raises(HighlightError):
        build_highlights(presented, BAD_SPECS[mode])

    assert _fingerprint(pipeline.document, presented) == before

    # 부분 산출물이 남지 않았다 — 다시 세우면 H01부터다.
    again = build_highlights(presented, [HighlightSpec(("EP01",))])
    assert [h.highlight_id for h in again] == ["H01"]

    # 정본 문서는 여전히 표현 입력으로 열린다(fallback 가능).
    reopened = presentation_input(pipeline.document)
    assert _fingerprint(pipeline.document, reopened) == before


# ── ERR-009 all evidence absent ──────────────────────────────────────────
#: 전 채널 공백에서 모델을 부르지 못한 상태. 상태를 가정하지 않는다 — 아래 테스트가
#: 프롬프트 거부를 먼저 확인한 뒤 이 값을 쓴다.
ABSENT = tuple(ParseResult(status=EMPTY, reason="no_usable_evidence")
               for _ in range(3))


def test_err_009_all_evidence_absent_keeps_structure_and_invents_nothing(tmp_path):
    """근거가 하나도 없을 때 구조는 남고 의미적 사건은 생기지 않는다."""
    pipeline = run_pipeline(tmp_path, ABSENT, name="S5", spans=THREE)

    # 1. EMPTY인 이유 — 프롬프트가 전 구간을 거부한다.
    for episode in pipeline.episodes:
        with pytest.raises(PromptError, match="no usable evidence"):
            build_episode_prompt(episode, pipeline.timeline, pipeline.store)

    presented = presentation_input(pipeline.document)

    # 2. 구조는 살아 있다.
    assert [e.episode_id for e in presented.episodes] == ["EP01", "EP02", "EP03"]
    assert [(e.start_seg, e.end_seg) for e in presented.episodes] == list(THREE)
    assert [e.end_sec for e in presented.episodes] == [20.0, 40.0, 60.0]

    # 3. 내용은 없고, 없다는 것이 상태로 남는다.
    assert all(e.summary is None for e in presented.episodes)
    assert all(e.dialogue_note is None for e in presented.episodes)
    assert all(e.content_status == EMPTY for e in presented.episodes)
    assert not any(summary_eligible_for_presentation(e)
                   for e in presented.episodes)

    highlights = build_highlights(
        presented, [HighlightSpec(("EP01", "EP02")), HighlightSpec(("EP03",))])
    lineage = build_lineage(presented, highlights)
    synthesis = build_synthesis(presented, lineage)
    records = build_presentation(presented, highlights)

    # 4. lineage는 남는다 — 무엇을 묶었는지는 내용과 무관하다.
    assert [r.source_episode_ids for r in lineage] == [("EP01", "EP02"),
                                                       ("EP03",)]

    # 5. 종합은 결론을 적지 않는다.
    assert synthesis.synthesis_status == NO_RELIABLE_CONTENT
    assert synthesis.overview == "" and synthesis.analysis == ()
    assert synthesis.source_episode_ids == ()
    assert synthesis.excluded_episode_ids == ("EP01", "EP02", "EP03")
    assert "결론을 적지 않는다" in synthesis.conclusion
    assert validate_synthesis(synthesis, presented) == []

    # 6. highlight summary는 자리표시자 문장이 아니라 부재 상태다.
    for record in records:
        assert record.summary is None
        assert record.summary_status == SUMMARY_NO_RELIABLE_CONTENT
        assert record.summary_source_episode_ids == ()
        assert record.excluded_summary_episode_ids == record.source_episode_ids
    assert validate_presentation(records, presented) == []

    # 7. 세 renderer 전부 — 구조는 적고 문장은 만들지 않는다.
    markdown = render_markdown(REPORT, records, synthesis)
    preview = render_preview(REPORT, records, synthesis)
    hwpx = hwpx_text(render_hwpx(REPORT, records, synthesis))

    for text in (markdown, hwpx):
        projection = _projection(text)
        assert set(projection["highlights"]) == {"H01", "H02"}
        assert projection["highlights"]["H01"][0] == "00:00–00:40"
        assert projection["highlights"]["H01"][2] == ("EP01", "EP02")
        assert projection["highlights"]["H01"][1] == (
            "(%s)" % SUMMARY_NO_RELIABLE_CONTENT)
        assert projection["synthesis_sources"] == "-"

    assert "H01 | 00:00–00:40" in preview
    assert "EP01 · EP02" in preview

    # 허용되는 평서문은 "결론을 적지 않는다"뿐이다. 자리표시자 서술이 어디서든
    # 생기면 여기서 깨진다.
    assert _sentences(markdown) == {synthesis.conclusion}
    assert _sentences(hwpx) == {synthesis.conclusion}
    assert _sentences(preview) == set()


# ── ERR-010 instruction echo top signal ──────────────────────────────────
#: S6에서 오염이 실린 구간. 3은 instruction echo, 7은 외국어 캡션이다.
ECHO_SEGMENTS = (3, 7)

#: 2026-08-30 C0 최대 peak 실측값. 오염 구간에 change-point 최대치를 준다.
PEAK = 0.6798


def _signal(segments, peaks):
    return [PEAK if s.segment_id in peaks else 0.01 for s in segments]


def _time_structure(name, window_sec):
    """시간 구조만 뽑는다. `source`는 채널 파생이라 비교하지 않는다 —
    채널이 다르면 달라지는 것이 정상이고, 여기서 재는 것은 경계다."""
    s = scenario(name)
    judged = {source_type: classify_channel(channel, source_type)
              for source_type, channel in (("asr", s.asr), ("vlm", s.caption),
                                           ("ocr", s.ocr))
              if channel}
    timeline = build_timeline(s.segments, judged)
    spans = window_spans(s.segments, window_sec)
    episodes = build_episodes(spans, s.segments, timeline=timeline)
    return spans, tuple((e.episode_id, e.start_seg, e.end_seg, e.start_sec,
                         e.end_sec, tuple(e.anchor_cites)) for e in episodes)


@pytest.mark.parametrize("window_sec", [15.0, 20.0, 60.0])
def test_err_010_an_instruction_echo_peak_does_not_move_the_fixed_window(
        window_sec):
    """instruction echo가 최대 peak여도 창 경계는 격자만 따른다."""
    echo = scenario("S6")

    # 그 결함이 실제로 이 fixture 안에 있다 — 없으면 아무것도 재지 않는다.
    assert echo.caption[3] == INSTRUCTION_ECHO
    # 보조 증거: sanitation은 그 캡션을 오염으로 판정한다.
    judged = classify_channel(echo.caption, "vlm")
    assert judged[3].status == REJECTED
    assert judged[3].reason == "instruction_echo"

    registry = ProviderRegistry()
    registry.register(FixedWindowV1())
    config = {"window_sec": window_sec}

    baseline = registry.run(None, scenario("S1").segments, config=config)
    contaminated = registry.run(
        None, echo.segments,
        caption_embeddings=[[1.0]] * len(echo.segments),
        boundary_signal=_signal(echo.segments, ECHO_SEGMENTS),
        config=config,
    )
    assert contaminated.boundary_positions == baseline.boundary_positions

    # 격자가 같으면 span도 episode 시간 구조도 같다.
    assert _time_structure("S6", window_sec) == _time_structure("S1", window_sec)
