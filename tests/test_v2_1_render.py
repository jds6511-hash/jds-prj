"""C-06 Preview / Markdown renderer — 표시만 한다 (Gate C).

```
RPT-001  두 출력은 같은 run의 같은 artifact를 소비한다
RPT-003  renderer는 시간 경계를 만들지 않는다
RPT-008  analysis_mode != report 이면 거부한다 (보정하지 않는다)
RPT-004  표현은 달라도 의미는 같다 (C-07에서 다시 본다)
```

renderer는 **정본 episode를 아예 받지 않는다.** 받지 않으면 다시 계산할 수도 없고,
`dialogue_note`를 찾아 출력할 수도 없다(OPEN-11). 입력은 이미 확정된 표현 객체뿐이다.
"""
import ast
import re
from dataclasses import replace
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_presentation import build_presentation
from v2_1_presentation_input import FORBIDDEN_UPSTREAM, presentation_input
from v2_1_render import (
    RenderError,
    render_markdown,
    render_preview,
    semantic_view,
)
from v2_1_run import Manifest, RenderRefused
from v2_1_scan import code_only
from v2_1_synthesis import build_synthesis
from v2_1_lineage import build_lineage

MODULE = Path(__file__).resolve().parents[1] / "src/v2_1_render.py"

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
    highlights = build_presentation(
        presented, build_highlights(presented, [HighlightSpec(g) for g in groups])
    )
    synthesis = build_synthesis(
        presented,
        build_lineage(presented,
                      build_highlights(presented, [HighlightSpec(g) for g in groups])),
    )
    return presented, highlights, synthesis


@pytest.fixture
def artifacts(tmp_path):
    return _artifacts(tmp_path)


def _ids(text):
    """출력에서 identity·lineage만 뽑는다. 서식도 등장 횟수도 보지 않는다.

    Markdown은 분석 절에서 highlight id를 한 번 더 적는다 — 그 차이는 서식이다.
    """
    return (tuple(sorted(set(re.findall(r"\bH\d{2}\b", text)))),
            tuple(sorted(set(re.findall(r"\bEP\d{2}\b", text)))))


# ── RPT-001 같은 source를 쓴다 ───────────────────────────────────────────
def test_rpt_001_preview_and_markdown_carry_the_same_identity(artifacts):
    _, highlights, synthesis = artifacts
    assert _ids(render_preview(REPORT, highlights, synthesis)) == \
        _ids(render_markdown(REPORT, highlights, synthesis))


def test_rpt_001_both_render_from_the_same_semantic_view(artifacts):
    _, highlights, synthesis = artifacts
    view = semantic_view(highlights, synthesis)
    preview = render_preview(REPORT, highlights, synthesis)
    markdown = render_markdown(REPORT, highlights, synthesis)
    for record in view["highlights"]:
        for output in (preview, markdown):
            assert record["highlight_id"] in output
            for ref in record["source_episode_ids"]:
                assert ref in output


def test_rpt_001_each_preview_row_carries_its_own_lineage(artifacts):
    """행마다 출처가 붙어야 한다 — 문서 어딘가에 id가 있는 것으로는 부족하다.

    종합 절이 모든 구간 id를 한 번씩 적기 때문에, 문서 전체 검사만으로는
    highlight별 lineage가 빠져도 통과한다.
    """
    _, highlights, synthesis = artifacts
    rows = {line.split(" | ")[0]: line
            for line in render_preview(REPORT, highlights, synthesis).splitlines()
            if re.match(r"^H\d{2} \|", line)}
    assert len(rows) == len(highlights)
    for record in highlights:
        row = rows[record.highlight_id]
        for ref in record.source_episode_ids:
            assert ref in row


def test_rpt_001_the_run_identity_is_shown(artifacts):
    _, highlights, synthesis = artifacts
    markdown = render_markdown(REPORT, highlights, synthesis)
    assert REPORT.video_id in markdown and REPORT.run_id in markdown


# ── RPT-003 경계를 만들지 않는다 ─────────────────────────────────────────
def test_rpt_003_times_come_from_the_artifact_not_from_a_recomputation(artifacts):
    """upstream 값이 이상해도 renderer가 '고쳐주면' 안 된다."""
    _, highlights, synthesis = artifacts
    moved = (replace(highlights[0], start_sec=100.0, end_sec=160.0),
             *highlights[1:])
    for output in (render_preview(REPORT, moved, synthesis),
                   render_markdown(REPORT, moved, synthesis)):
        assert "01:40" in output and "02:40" in output
        assert "00:00" not in output.split("H02")[0]


def test_rpt_003_no_time_arithmetic_in_the_renderer():
    """보조 가드 — min/max로 경계를 다시 세우는 코드가 없어야 한다."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    called = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not called & {"min", "max"}


def test_rpt_003_lineage_is_not_reconstructed(artifacts):
    """source_episode_ids를 시간 범위로 다시 만들지 않는다."""
    _, highlights, synthesis = artifacts
    trimmed = (replace(highlights[0], source_episode_ids=("EP01",),
                       summary_source_episode_ids=("EP01",),
                       excluded_summary_episode_ids=()),
               *highlights[1:])
    markdown = render_markdown(REPORT, trimmed, synthesis)
    assert "EP02" not in markdown.split("H02")[0]


# ── RPT-008 analysis_mode interlock ──────────────────────────────────────
def test_rpt_008_preview_mode_refuses_report_rendering(artifacts):
    _, highlights, synthesis = artifacts
    with pytest.raises(RenderRefused):
        render_markdown(PREVIEW_MODE, highlights, synthesis)


def test_rpt_008_the_manifest_is_not_rewritten(artifacts):
    _, highlights, synthesis = artifacts
    before = (PREVIEW_MODE.analysis_mode, PREVIEW_MODE.run_id)
    with pytest.raises(RenderRefused):
        render_markdown(PREVIEW_MODE, highlights, synthesis)
    assert (PREVIEW_MODE.analysis_mode, PREVIEW_MODE.run_id) == before


def test_rpt_008_preview_itself_is_allowed_in_preview_mode(artifacts):
    _, highlights, synthesis = artifacts
    assert render_preview(PREVIEW_MODE, highlights, synthesis)


def test_rpt_008_the_interlock_is_the_a_02_one():
    """새 규칙을 만들지 않는다 — A-02의 계약을 그대로 쓴다."""
    source = MODULE.read_text(encoding="utf-8")
    assert "require_report_mode" in source


# ── RPT-004 표현은 달라도 의미는 같다 ────────────────────────────────────
def test_rpt_004_the_two_outputs_differ_in_form(artifacts):
    _, highlights, synthesis = artifacts
    preview = render_preview(REPORT, highlights, synthesis)
    markdown = render_markdown(REPORT, highlights, synthesis)
    assert preview != markdown
    assert markdown.count("#") > preview.count("#")


def test_rpt_004_summaries_appear_in_both(artifacts):
    _, highlights, synthesis = artifacts
    preview = render_preview(REPORT, highlights, synthesis)
    markdown = render_markdown(REPORT, highlights, synthesis)
    for record in highlights:
        if record.summary:
            assert record.summary in preview
            assert record.summary in markdown


def test_rpt_004_the_limitation_survives_both(artifacts):
    _, highlights, synthesis = artifacts
    assert synthesis.limitation in render_markdown(REPORT, highlights, synthesis)
    assert synthesis.limitation in render_preview(REPORT, highlights, synthesis)


# ── 문장을 만들지 않는다 ─────────────────────────────────────────────────
def test_no_placeholder_claim_when_the_summary_is_missing(tmp_path):
    _, highlights, synthesis = _artifacts(tmp_path, (UNSUPPORTED,) * 3,
                                          groups=(("EP01", "EP02"),))
    assert highlights[0].summary is None
    markdown = render_markdown(REPORT, highlights, synthesis)
    assert "NO_RELIABLE_CONTENT" in markdown
    for invented in ("요약 없음", "내용 확인 필요", "중요한", "전환점"):
        assert invented not in markdown


def test_the_renderer_adds_no_semantic_claim(artifacts):
    """고정 UI 문구는 되지만 내용 주장은 안 된다."""
    _, highlights, synthesis = artifacts
    markdown = render_markdown(REPORT, highlights, synthesis)
    for claim in ("중요", "전환점", "흥미", "인상적", "성공적"):
        assert claim not in markdown


def test_the_synthesis_sections_are_carried_verbatim(artifacts):
    _, highlights, synthesis = artifacts
    markdown = render_markdown(REPORT, highlights, synthesis)
    assert synthesis.overview in markdown
    assert synthesis.conclusion in markdown
    for line in synthesis.analysis:
        assert line in markdown


# ── OPEN-11 보조 회귀 ────────────────────────────────────────────────────
def test_no_pre_grounding_information_reaches_the_output(tmp_path):
    presented, highlights, synthesis = _artifacts(tmp_path)
    markdown = render_markdown(REPORT, highlights, synthesis)
    preview = render_preview(REPORT, highlights, synthesis)
    for output in (markdown, preview):
        assert "raw:" not in output
        assert "llm:" not in output
        assert "asr:0" not in output and "vlm:0" not in output


def test_the_renderer_never_sees_canonical_episodes():
    """dialogue_note를 찾아 출력하는 코드가 있을 수 없게 만든다."""
    assert "dialogue_note" not in code_only(MODULE)
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    attributes = {node.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute)}
    assert "dialogue_note" not in attributes


# ── 임의 보정하지 않는다 ─────────────────────────────────────────────────
def test_an_inconsistent_summary_state_is_refused(artifacts):
    _, highlights, synthesis = artifacts
    broken = (replace(highlights[0], summary=None,
                      summary_status="AVAILABLE"), *highlights[1:])
    with pytest.raises(RenderError):
        render_markdown(REPORT, broken, synthesis)


def test_a_broken_summary_lineage_is_refused(artifacts):
    _, highlights, synthesis = artifacts
    broken = (replace(highlights[0], excluded_summary_episode_ids=("EP99",)),
              *highlights[1:])
    with pytest.raises(RenderError):
        render_markdown(REPORT, broken, synthesis)


def test_a_missing_limitation_is_refused(artifacts):
    _, highlights, synthesis = artifacts
    with pytest.raises(RenderError):
        render_markdown(REPORT, highlights, replace(synthesis, limitation=""))


def test_an_unknown_summary_status_is_refused(artifacts):
    _, highlights, synthesis = artifacts
    broken = (replace(highlights[0], summary_status="MAYBE"), *highlights[1:])
    with pytest.raises(RenderError):
        render_markdown(REPORT, broken, synthesis)


# ── 산출물을 건드리지 않는다 ─────────────────────────────────────────────
def test_the_artifacts_are_not_mutated(artifacts):
    _, highlights, synthesis = artifacts
    before = (tuple(highlights), synthesis)
    render_markdown(REPORT, highlights, synthesis)
    render_preview(REPORT, highlights, synthesis)
    assert (tuple(highlights), synthesis) == before


def test_the_module_does_not_import_pre_grounding_layers():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & set(FORBIDDEN_UPSTREAM), sorted(imported)


def test_the_module_does_not_do_hwpx_or_fallback():
    """C-07 · C-08의 몫을 여기서 먹지 않는다."""
    source = code_only(MODULE).lower()
    assert "hwpx" not in source
    assert "fallback" not in source
