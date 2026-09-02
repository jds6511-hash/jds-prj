"""C-08 실패·fallback 정책 (Gate C).

```
RPT-006  표현 실패 → 같은 semantic_view를 더 단순한 형식으로       허용
RPT-007  구조 실패 → 고쳐서 살리지 않는다                          금지
HLT-008  약한 내용 → 구조·출처는 살고 내용만 빈다                  실패가 아니다
```

셋이 섞이면 "사용자에게 뭔가 보여줘야 하니 알아서 고쳤다"가 된다. 그래서 상태를
뭉치지 않는다 — `STRUCTURAL_INVALID`은 fallback 대상이 **아니다.**
"""
import ast
from dataclasses import replace
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_presentation import build_presentation
from v2_1_presentation_input import FORBIDDEN_UPSTREAM, presentation_input
from v2_1_render import render_markdown, render_preview
from v2_1_render_fallback import (
    PRESENTATION_FALLBACK_FAILED,
    PRESENTATION_FALLBACK_USED,
    PRIMARY,
    RenderOutcome,
    StructuralFailure,
    render_with_fallback,
)
from v2_1_render_hwpx import hwpx_text
from v2_1_render_probe import _blocks, _projection
from v2_1_run import Manifest, RenderRefused
from v2_1_synthesis import build_synthesis

MODULE = Path(__file__).resolve().parents[1] / "src/v2_1_render_fallback.py"

THREE = ((0, 3), (4, 7), (8, 11))
GOOD = ({"summary": "창고 문을 연다."},
        {"summary": "상자를 옮긴다."},
        {"summary": "불을 끄고 나간다."})
UNSUPPORTED = {"summary": "제나가 42번 상자를 연다.",
               "dialogue_note": "42번이라고 말한다.", "stt_cites": [1]}

REPORT = Manifest(video_id="S1", run_id="run-001", analysis_mode="report",
                  config_hash="c0ffee", code_git_head="deadbeef")
PREVIEW_MODE = replace(REPORT, analysis_mode="preview")


def _artifacts(tmp_path, payloads=GOOD, groups=(("EP01", "EP02"), ("EP03",))):
    presented = presentation_input(
        run_pipeline(tmp_path, payloads, spans=THREE).document
    )
    specs = [HighlightSpec(group) for group in groups]
    highlights = build_presentation(presented, build_highlights(presented, specs))
    synthesis = build_synthesis(
        presented, build_lineage(presented, build_highlights(presented, specs))
    )
    return presented, highlights, synthesis


@pytest.fixture
def artifacts(tmp_path):
    return _artifacts(tmp_path)


def _fingerprint(highlights, synthesis):
    """fallback 전후로 변하면 안 되는 것 전부."""
    return (
        tuple((r.highlight_id, r.start_sec, r.end_sec, r.source_episode_ids,
               r.summary, r.summary_status, r.summary_source_episode_ids,
               r.excluded_summary_episode_ids) for r in highlights),
        synthesis.source_episode_ids, synthesis.excluded_episode_ids,
        synthesis.limitation, synthesis.analysis,
    )


def _break(monkeypatch, name, error=RuntimeError("serialization failed")):
    """표현 단계에서만 나는 실패를 주입한다 — 구조는 멀쩡하다."""
    def boom(*_args, **_kwargs):
        raise error
    monkeypatch.setitem(
        __import__("v2_1_render_fallback")._RENDERERS, name, boom
    )


# ── RPT-006 표현만 줄인다 ────────────────────────────────────────────────
def test_rpt_006_the_primary_format_is_used_when_it_works(artifacts):
    _, highlights, synthesis = artifacts
    outcome = render_with_fallback(REPORT, highlights, synthesis)
    assert outcome.status == PRIMARY
    assert outcome.format == "hwpx"
    assert outcome.primary_error is None


def test_rpt_006_a_failed_hwpx_falls_back_to_markdown(monkeypatch, artifacts):
    _, highlights, synthesis = artifacts
    _break(monkeypatch, "hwpx")
    outcome = render_with_fallback(REPORT, highlights, synthesis)
    assert outcome.status == PRESENTATION_FALLBACK_USED
    assert outcome.format == "markdown"
    assert "serialization failed" in outcome.primary_error


def test_rpt_006_the_chain_continues_to_preview(monkeypatch, artifacts):
    _, highlights, synthesis = artifacts
    _break(monkeypatch, "hwpx")
    _break(monkeypatch, "markdown")
    outcome = render_with_fallback(REPORT, highlights, synthesis)
    assert outcome.format == "preview"
    assert [name for name, _ in outcome.fallback_errors] == ["hwpx", "markdown"]


def test_rpt_006_every_format_failing_is_reported_not_faked(monkeypatch,
                                                            artifacts):
    _, highlights, synthesis = artifacts
    for name in ("hwpx", "markdown", "preview"):
        _break(monkeypatch, name)
    outcome = render_with_fallback(REPORT, highlights, synthesis)
    assert outcome.status == PRESENTATION_FALLBACK_FAILED
    assert outcome.format is None and outcome.payload is None
    assert len(outcome.fallback_errors) == 3


def test_rpt_006_the_fallback_carries_the_same_semantics(monkeypatch, artifacts):
    """형식만 내려간다 — 의미는 primary가 받았던 것과 같아야 한다."""
    _, highlights, synthesis = artifacts
    expected = _projection(hwpx_text(
        render_with_fallback(REPORT, highlights, synthesis).payload))
    _break(monkeypatch, "hwpx")
    outcome = render_with_fallback(REPORT, highlights, synthesis)
    assert _projection(outcome.payload) == expected


def test_rpt_006_the_fallback_does_not_touch_the_artifacts(monkeypatch,
                                                           artifacts):
    _, highlights, synthesis = artifacts
    before = _fingerprint(highlights, synthesis)
    _break(monkeypatch, "hwpx")
    render_with_fallback(REPORT, highlights, synthesis)
    assert _fingerprint(highlights, synthesis) == before


# ── RPT-007 구조는 복구하지 않는다 ───────────────────────────────────────
def test_rpt_007_an_invalid_structure_never_reaches_a_renderer(artifacts):
    _, highlights, synthesis = artifacts
    broken = (replace(highlights[0], summary=None,
                      summary_status="AVAILABLE"), *highlights[1:])
    with pytest.raises(StructuralFailure):
        render_with_fallback(REPORT, broken, synthesis)


def test_rpt_007_a_broken_lineage_is_not_repaired(artifacts):
    """없는 source id를 지워서 통과시키지 않는다."""
    _, highlights, synthesis = artifacts
    broken = (replace(highlights[0], excluded_summary_episode_ids=("EP99",)),
              *highlights[1:])
    with pytest.raises(StructuralFailure):
        render_with_fallback(REPORT, broken, synthesis)


def test_rpt_007_structural_failure_is_not_a_fallback_case(monkeypatch,
                                                           artifacts):
    """구조 실패에는 표현 fallback을 적용하지 않는다 — 두 상태를 뭉치지 않는다."""
    _, highlights, synthesis = artifacts
    broken = (replace(highlights[0], summary_status="MAYBE"), *highlights[1:])
    calls = []
    for name in ("hwpx", "markdown", "preview"):
        monkeypatch.setitem(
            __import__("v2_1_render_fallback")._RENDERERS, name,
            lambda *a, _n=name, **k: calls.append(_n),
        )
    with pytest.raises(StructuralFailure):
        render_with_fallback(REPORT, broken, synthesis)
    assert calls == []


def test_rpt_007_a_missing_limitation_is_structural(artifacts):
    _, highlights, synthesis = artifacts
    with pytest.raises(StructuralFailure):
        render_with_fallback(REPORT, highlights, replace(synthesis,
                                                         limitation=""))


def test_rpt_007_the_interlock_is_not_bypassed_by_falling_back(artifacts):
    """preview 형식이 뒤에 있다고 report 인터록을 우회하면 안 된다."""
    _, highlights, synthesis = artifacts
    with pytest.raises(RenderRefused):
        render_with_fallback(PREVIEW_MODE, highlights, synthesis)


def test_rpt_007_an_unknown_format_is_refused(artifacts):
    _, highlights, synthesis = artifacts
    with pytest.raises(StructuralFailure):
        render_with_fallback(REPORT, highlights, synthesis, primary="pdf")


def test_rpt_007_the_module_does_not_rebuild_anything():
    """거슬러 올라가는 함수를 아예 부르지 않는다."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            names.update(alias.name for alias in node.names)
    assert not names & {"build_highlights", "build_episodes", "build_lineage",
                        "build_presentation", "build_synthesis", "window_spans",
                        "FixedWindowV1"}
    assert not imported & set(FORBIDDEN_UPSTREAM)


# ── HLT-008 약한 내용은 실패가 아니다 ────────────────────────────────────
def test_hlt_008_a_highlight_without_a_summary_still_renders(tmp_path):
    _, highlights, synthesis = _artifacts(tmp_path, (UNSUPPORTED,) * 3,
                                          groups=(("EP01", "EP02"), ("EP03",)))
    assert highlights[0].summary is None
    outcome = render_with_fallback(REPORT, highlights, synthesis)
    assert outcome.status == PRIMARY


def test_hlt_008_a_weak_highlight_is_not_dropped(tmp_path):
    _, highlights, synthesis = _artifacts(tmp_path, (UNSUPPORTED,) * 3,
                                          groups=(("EP01", "EP02"), ("EP03",)))
    text = hwpx_text(render_with_fallback(REPORT, highlights, synthesis).payload)
    assert set(_blocks(text)) == {r.highlight_id for r in highlights}


def test_hlt_008_weak_highlights_are_not_merged(tmp_path):
    _, highlights, synthesis = _artifacts(tmp_path, (UNSUPPORTED,) * 3,
                                          groups=(("EP01",), ("EP02",), ("EP03",)))
    text = hwpx_text(render_with_fallback(REPORT, highlights, synthesis).payload)
    blocks = _blocks(text)
    assert len(blocks) == 3
    for record in highlights:
        assert record.source_episode_ids[0] in blocks[record.highlight_id]


def test_hlt_008_provenance_survives_when_the_content_does_not(tmp_path):
    """내용이 비어도 출처는 살아 있다 — 그것이 graceful degradation이다."""
    _, highlights, synthesis = _artifacts(tmp_path, (UNSUPPORTED,) * 3,
                                          groups=(("EP01", "EP02"),))
    text = hwpx_text(render_with_fallback(REPORT, highlights, synthesis).payload)
    assert "EP01" in text and "EP02" in text
    assert "NO_RELIABLE_CONTENT" in text


def test_hlt_008_no_highlight_at_all_is_still_a_document(tmp_path):
    presented, _, _ = _artifacts(tmp_path)
    synthesis = build_synthesis(presented, ())
    outcome = render_with_fallback(REPORT, (), synthesis)
    assert outcome.status == PRIMARY
    text = hwpx_text(outcome.payload)
    assert synthesis.limitation in text
    for invented in ("확인할 수 없습니다", "주요 사건이 없습니다"):
        assert invented not in text


# ── 실패 어휘를 뭉치지 않는다 ────────────────────────────────────────────
def test_the_two_failure_kinds_have_different_types(monkeypatch, artifacts):
    _, highlights, synthesis = artifacts
    _break(monkeypatch, "hwpx")
    rendered = render_with_fallback(REPORT, highlights, synthesis)
    assert isinstance(rendered, RenderOutcome)

    broken = (replace(highlights[0], summary_status="MAYBE"), *highlights[1:])
    with pytest.raises(StructuralFailure):
        render_with_fallback(REPORT, broken, synthesis)


def test_the_outcome_records_which_formats_failed(monkeypatch, artifacts):
    _, highlights, synthesis = artifacts
    _break(monkeypatch, "hwpx", ValueError("bad zip"))
    outcome = render_with_fallback(REPORT, highlights, synthesis)
    assert outcome.primary_format == "hwpx"
    assert outcome.fallback_errors[0][0] == "hwpx"
    assert "ValueError" in outcome.fallback_errors[0][1]


def test_markdown_as_primary_falls_back_to_preview(monkeypatch, artifacts):
    _, highlights, synthesis = artifacts
    _break(monkeypatch, "markdown")
    outcome = render_with_fallback(REPORT, highlights, synthesis,
                                   primary="markdown")
    assert outcome.format == "preview"
    assert outcome.payload == render_preview(REPORT, highlights, synthesis)


def test_preview_has_nowhere_to_fall_back_to(monkeypatch, artifacts):
    _, highlights, synthesis = artifacts
    _break(monkeypatch, "preview")
    outcome = render_with_fallback(REPORT, highlights, synthesis,
                                   primary="preview")
    assert outcome.status == PRESENTATION_FALLBACK_FAILED
    assert len(outcome.fallback_errors) == 1


def test_a_working_markdown_primary_is_not_downgraded(artifacts):
    _, highlights, synthesis = artifacts
    outcome = render_with_fallback(REPORT, highlights, synthesis,
                                   primary="markdown")
    assert outcome.status == PRIMARY
    assert outcome.payload == render_markdown(REPORT, highlights, synthesis)
