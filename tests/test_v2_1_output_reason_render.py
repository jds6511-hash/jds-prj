"""요약 부재 사유를 두 renderer가 같은 코드로 표시하는지 (2026-09-08 · P2-1).

```
요약: (NO_RELIABLE_CONTENT)              기존 잠금 그대로 — 상태 코드다
제외 구간: EP13 (OUTPUT_LANGUAGE_DRIFT)   새로 적는 것 — **episode 단위** 사유
```

group 전체가 실패한 것처럼 읽히면 안 된다. highlight 상태와 episode 제외 사유는
다른 것이다 — 어느 구간이 왜 빠졌는지를 구간 이름과 함께 적는다.

사람이 원인을 추측해 써 넣지 않는다. 사유는 `exclusion_reasons()`가 만든 코드뿐이다.
"""
import pytest

from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_output_quality import REASON_LANGUAGE_DRIFT
from v2_1_presentation import (
    PresentationHighlight,
    SUMMARY_NO_RELIABLE_CONTENT,
    build_presentation,
    validate_presentation,
)
from v2_1_presentation_input import PresentationEpisode, PresentationInput
from v2_1_render import LABELS, render_markdown
from v2_1_render_hwpx import render_hwpx
from v2_1_run import Manifest
from v2_1_synthesis import build_synthesis

from v2_1_render_probe import _projection

REPORT = Manifest(video_id="QG", run_id="run-quality", analysis_mode="report",
                  config_hash="c0ffee", code_git_head="deadbeef")
DRIFT = ("두 사람이 빵을 만드는 모습을 보여주고, 마지막으로 베이킹용품"
         "尤其是关于蛋糕，是否有售？价格在这里，请看样品。")


def _episode(episode_id, summary, *, index=0, content_status="VALID_PARSE",
             grounding="NOT_APPLICABLE"):
    return PresentationEpisode(
        episode_id=episode_id, start_seg=index * 4, end_seg=index * 4 + 3,
        start_sec=index * 60.0, end_sec=index * 60.0 + 60.0, source="stt",
        content_status=content_status, summary=summary, dialogue_note=None,
        grounding_status=grounding, anchor_cites=(),
        provenance=("m3_generate",))


def _presented(*episodes):
    return PresentationInput(schema="aar_canonical_v2_1", video_id="QG",
                             run_id="run-quality", episodes=tuple(episodes))


def _build(presented, groups):
    highlights = build_highlights(presented, [HighlightSpec(g) for g in groups])
    lineage = build_lineage(presented, highlights)
    return (build_presentation(presented, highlights),
            build_synthesis(presented, lineage))


def _hwpx_text(payload: bytes) -> str:
    import re
    import zipfile
    from io import BytesIO
    from xml.sax.saxutils import unescape
    with zipfile.ZipFile(BytesIO(payload)) as package:
        section = package.read("Contents/section0.xml").decode("utf-8")
    return "\n".join(unescape(text) for text in
                     re.findall(r"<hp:t>(.*?)</hp:t>", section, re.S))


@pytest.fixture
def drifted():
    presented = _presented(_episode("EP01", DRIFT))
    return presented, _build(presented, (("EP01",),))


# ── 사유가 표현 객체에 실린다 ────────────────────────────────────────────
def test_the_highlight_carries_the_deterministic_reason(drifted):
    _, (records, _) = drifted
    assert records[0].summary is None
    assert records[0].summary_status == SUMMARY_NO_RELIABLE_CONTENT
    assert records[0].excluded_summary_reasons == (
        ("EP01", (REASON_LANGUAGE_DRIFT,)),)


def test_a_parse_failure_reports_its_own_reason():
    presented = _presented(_episode("EP01", None,
                                    content_status="PARSE_CONTRACT_FAILURE"))
    records, _ = _build(presented, (("EP01",),))
    assert records[0].excluded_summary_reasons == (
        ("EP01", ("PARSE_CONTRACT_FAILURE",)),)


def test_an_available_summary_has_no_reason():
    presented = _presented(_episode("EP01", "여성이 재료를 고른다."))
    records, _ = _build(presented, (("EP01",),))
    assert records[0].summary is not None
    assert records[0].excluded_summary_reasons == ()


def test_invented_reasons_are_reported_by_the_validator(drifted):
    presented, (records, _) = drifted
    tampered = (PresentationHighlight(
        **{**{field: getattr(records[0], field)
              for field in records[0].__slots__},
           "excluded_summary_reasons": (("EP01", ("사람이 보기에 이상해서 뺐다",)),)}),)
    assert validate_presentation(tampered, presented)


# ── 두 renderer가 같은 코드를 적는다 ─────────────────────────────────────
def test_both_renderers_print_the_reason_code(drifted):
    _, (records, synthesis) = drifted
    markdown = render_markdown(REPORT, records, synthesis)
    hwpx = _hwpx_text(render_hwpx(REPORT, records, synthesis))
    for text in (markdown, hwpx):
        assert "%s: EP01 (%s)" % (LABELS["excluded"], REASON_LANGUAGE_DRIFT) in text
        # 기존 잠금 — 요약 셀은 상태 코드 그대로다.
        assert _projection(text)["highlights"]["H01"][1] == (
            "(%s)" % SUMMARY_NO_RELIABLE_CONTENT)


def test_the_reason_line_is_absent_when_nothing_was_excluded():
    presented = _presented(_episode("EP01", "여성이 재료를 고른다."))
    records, synthesis = _build(presented, (("EP01",),))
    markdown = render_markdown(REPORT, records, synthesis)
    assert "%s:" % LABELS["excluded"] not in markdown


def test_a_group_that_kept_a_summary_still_reports_the_excluded_reason():
    """묶음에 정상 구간이 남아 있어도 왜 하나가 빠졌는지 보여야 한다."""
    presented = _presented(_episode("EP01", "여성이 재료를 고른다."),
                           _episode("EP02", DRIFT, index=1))
    records, synthesis = _build(presented, (("EP01", "EP02"),))
    assert records[0].summary is not None
    assert records[0].excluded_summary_reasons == (
        ("EP02", (REASON_LANGUAGE_DRIFT,)),)
    markdown = render_markdown(REPORT, records, synthesis)
    # 살아 있는 구간이 아니라 **빠진 구간**의 이름이 붙는다.
    assert "%s: EP02 (%s)" % (LABELS["excluded"], REASON_LANGUAGE_DRIFT) in markdown
    assert "EP01 (" not in markdown


def test_the_renderer_invents_no_prose_for_the_reason(drifted):
    _, (records, synthesis) = drifted
    markdown = render_markdown(REPORT, records, synthesis)
    for invented in ("이상해서", "중국어", "환각", "품질이 낮아"):
        assert invented not in markdown


def test_a_group_state_is_not_reported_as_the_whole_group_failing():
    """H03처럼 5구간 중 1구간만 빠진 묶음이 전체 실패로 읽히면 안 된다."""
    presented = _presented(
        _episode("EP11", "여성이 재료를 고른다.", index=0),
        _episode("EP12", "여성이 반죽을 만든다.", index=1),
        _episode("EP13", DRIFT, index=2),
        _episode("EP14", "여성이 오븐을 연다.", index=3))
    records, synthesis = _build(presented, (("EP11", "EP12", "EP13", "EP14"),))
    markdown = render_markdown(REPORT, records, synthesis)
    assert "%s: EP13 (%s)" % (LABELS["excluded"], REASON_LANGUAGE_DRIFT) in markdown
    # 살아 있는 구간 이름에 사유가 붙지 않는다.
    for kept in ("EP11", "EP12", "EP14"):
        assert "%s (" % kept not in markdown
    assert records[0].summary_source_episode_ids == ("EP11", "EP12", "EP14")


def test_several_excluded_episodes_are_listed_each_with_its_own_reason():
    presented = _presented(
        _episode("EP16", "여성이 시장을 걷는다.", index=0),
        _episode("EP17", None, index=1, content_status="PARSE_CONTRACT_FAILURE"),
        _episode("EP18", DRIFT, index=2))
    records, synthesis = _build(presented, (("EP16", "EP17", "EP18"),))
    markdown = render_markdown(REPORT, records, synthesis)
    assert "EP17 (PARSE_CONTRACT_FAILURE)" in markdown
    assert "EP18 (%s)" % REASON_LANGUAGE_DRIFT in markdown
