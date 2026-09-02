"""C-07 HWPX renderer — 같은 의미의 두 번째 serializer (Gate C).

```
RPT-003   renderer는 경계를 만들지 않는다 (HWPX 쪽 증명)
RPT-004   Markdown과 서식은 달라도 의미는 같다
```

검사는 **패키지 안을 열어서** 한다. 함수 반환값만 보면 실제로 문서에 무엇이
적혔는지를 보지 않는 것이다.

BCS v0는 동결이다. 이 모듈이 BCS를 import하지 않는다는 것까지 확인한다 — "고치지
않았다"보다 강한 조건이다.
"""
import ast
import re
import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_presentation import build_presentation
from v2_1_presentation_input import FORBIDDEN_UPSTREAM, presentation_input
from v2_1_render import LABELS, RenderError, render_markdown
from v2_1_render_hwpx import MIMETYPE, hwpx_text, render_hwpx, write_hwpx
from v2_1_run import Manifest, RenderRefused
from v2_1_scan import code_only
from v2_1_synthesis import build_synthesis

MODULE = Path(__file__).resolve().parents[1] / "src/v2_1_render_hwpx.py"

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


def _blocks(text):
    """highlight id로 블록을 가른다. 서식이 무엇이든 id 다음의 label 줄들이 블록이다.

    id는 문서에 여러 번 나온다(종합 분석 절이 다시 적는다). **첫 등장만** 블록의
    시작으로 보고, label이 없는 줄이 나오면 블록을 닫는다. 그래야 다른 절의 언급이
    블록에 섞여 들어오지 않는다.
    """
    blocks, current = {}, None
    for line in text.splitlines():
        found = re.search(r"\bH\d{2}\b", line)
        has_label = any(name in line for name in LABELS.values())
        if found and found.group(0) not in blocks and not has_label:
            current = found.group(0)
            blocks[current] = [line]
        elif current is not None:
            if has_label:
                blocks[current].append(line)
            elif blocks[current][1:]:
                current = None
    return {key: "\n".join(value) for key, value in blocks.items()}


def _projection(text):
    """서식을 벗기고 의미만 남긴다. 두 renderer를 이것으로 대조한다."""
    def value(source, key):
        found = re.search(r"%s\s*[:：]\s*(.+)" % LABELS[key], source)
        return found.group(1).strip() if found else None

    highlights = {
        key: (value(block, "time"), value(block, "summary"),
              tuple(sorted(set(re.findall(r"\bEP\d{2}\b", value(block, "sources")
                                          or "")))),
              value(block, "summary_sources"))
        for key, block in _blocks(text).items()
    }
    return {
        "highlights": highlights,
        "synthesis_sources": value(text, "synthesis_sources"),
        "limitation": value(text, "limitation"),
    }


# ── 패키지가 만들어진다 ──────────────────────────────────────────────────
def test_the_package_has_the_owpml_layout(artifacts):
    _, highlights, synthesis = artifacts
    with zipfile.ZipFile(BytesIO(render_hwpx(REPORT, highlights, synthesis))) as pkg:
        names = pkg.namelist()
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert "Contents/section0.xml" in names
        assert pkg.read("mimetype").decode() == MIMETYPE
        assert pkg.getinfo("mimetype").compress_type == zipfile.ZIP_STORED


def test_the_body_text_is_readable_from_the_package(artifacts):
    _, highlights, synthesis = artifacts
    text = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    assert REPORT.video_id in text
    for record in highlights:
        assert record.highlight_id in text


def test_write_hwpx_produces_a_file(tmp_path, artifacts):
    _, highlights, synthesis = artifacts
    path = write_hwpx(tmp_path / "report.hwpx", REPORT, highlights, synthesis)
    assert path.exists() and path.stat().st_size > 0
    assert zipfile.is_zipfile(path)


def test_the_result_is_deterministic_in_content(artifacts):
    _, highlights, synthesis = artifacts
    first = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    second = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    assert first == second


# ── RPT-003 경계를 만들지 않는다 ─────────────────────────────────────────
def test_rpt_003_times_come_from_the_artifact(artifacts):
    """upstream 실제 구간이 00:20이어도 확정된 값 01:40을 적어야 한다."""
    presented, highlights, synthesis = artifacts
    assert presented.episode("EP01").start_sec == 0.0
    moved = (replace(highlights[0], start_sec=100.0, end_sec=150.0),
             *highlights[1:])
    block = _blocks(hwpx_text(render_hwpx(REPORT, moved, synthesis)))["H01"]
    assert "01:40" in block and "02:30" in block
    assert "00:00" not in block


def test_rpt_003_no_time_arithmetic_in_the_renderer():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    called = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not called & {"min", "max", "sorted"}


def test_rpt_003_highlights_are_not_regrouped(artifacts):
    _, highlights, synthesis = artifacts
    text = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    assert set(_blocks(text)) == {record.highlight_id for record in highlights}


# ── 블록 단위 lineage (C-06에서 배운 것) ─────────────────────────────────
def test_each_block_carries_its_own_lineage(artifacts):
    """종합 절이 모든 id를 적으므로 문서 전체 검사로는 부족하다."""
    _, highlights, synthesis = artifacts
    blocks = _blocks(hwpx_text(render_hwpx(REPORT, highlights, synthesis)))
    for record in highlights:
        block = blocks[record.highlight_id]
        for ref in record.source_episode_ids:
            assert ref in block


def test_a_block_does_not_borrow_another_blocks_sources(artifacts):
    _, highlights, synthesis = artifacts
    trimmed = (replace(highlights[0], source_episode_ids=("EP01",),
                       summary_source_episode_ids=("EP01",),
                       excluded_summary_episode_ids=()),
               *highlights[1:])
    blocks = _blocks(hwpx_text(render_hwpx(REPORT, trimmed, synthesis)))
    assert "EP02" not in blocks["H01"]


# ── RPT-004 서식은 다르고 의미는 같다 ────────────────────────────────────
def test_rpt_004_the_two_documents_look_different(artifacts):
    _, highlights, synthesis = artifacts
    markdown = render_markdown(REPORT, highlights, synthesis)
    hwpx = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    assert markdown != hwpx
    assert "###" in markdown and "###" not in hwpx
    assert "┌" in hwpx and "┌" not in markdown


def test_rpt_004_the_semantic_projection_is_identical(artifacts):
    _, highlights, synthesis = artifacts
    markdown = render_markdown(REPORT, highlights, synthesis)
    hwpx = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    assert _projection(markdown) == _projection(hwpx)


def test_rpt_004_a_missing_highlight_breaks_the_projection(artifacts):
    """같은 semantic_view인데 한쪽에서 highlight가 빠지면 대조가 깨져야 한다."""
    _, highlights, synthesis = artifacts
    markdown = render_markdown(REPORT, highlights, synthesis)
    hwpx = hwpx_text(render_hwpx(REPORT, highlights[:1], synthesis))
    assert _projection(markdown) != _projection(hwpx)


def test_rpt_004_the_analysis_is_carried_verbatim(artifacts):
    _, highlights, synthesis = artifacts
    text = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    for line in synthesis.analysis:
        assert line in text
    assert synthesis.overview in text
    assert synthesis.conclusion in text
    assert synthesis.limitation in text


# ── 없는 내용을 만들지 않는다 ────────────────────────────────────────────
def test_a_missing_summary_is_shown_as_absence_not_as_a_sentence(tmp_path):
    _, highlights, synthesis = _artifacts(tmp_path, (UNSUPPORTED,) * 3,
                                          groups=(("EP01", "EP02"),))
    assert highlights[0].summary is None
    text = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    assert "NO_RELIABLE_CONTENT" in text
    for invented in ("확인되지 않았습니다", "요약 없음", "내용 확인 필요"):
        assert invented not in text


def test_the_absence_reads_the_same_in_both_documents(tmp_path):
    _, highlights, synthesis = _artifacts(tmp_path, (UNSUPPORTED,) * 3,
                                          groups=(("EP01", "EP02"),))
    markdown = render_markdown(REPORT, highlights, synthesis)
    hwpx = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    assert _projection(markdown) == _projection(hwpx)


def test_the_renderer_adds_no_semantic_claim(artifacts):
    _, highlights, synthesis = artifacts
    text = hwpx_text(render_hwpx(REPORT, highlights, synthesis))
    for claim in ("중요", "전환점", "흥미", "인상적", "성공적"):
        assert claim not in text


# ── interlock을 우회하지 않는다 ──────────────────────────────────────────
def test_hwpx_is_not_a_second_entry_point_around_the_interlock(artifacts):
    _, highlights, synthesis = artifacts
    with pytest.raises(RenderRefused):
        render_hwpx(PREVIEW_MODE, highlights, synthesis)


def test_the_interlock_is_the_shared_one():
    assert "require_report_mode" in code_only(MODULE)


def test_a_broken_artifact_is_refused_not_repaired(artifacts):
    _, highlights, synthesis = artifacts
    broken = (replace(highlights[0], summary=None,
                      summary_status="AVAILABLE"), *highlights[1:])
    with pytest.raises(RenderError):
        render_hwpx(REPORT, broken, synthesis)


def test_a_missing_limitation_is_refused(artifacts):
    _, highlights, synthesis = artifacts
    with pytest.raises(RenderError):
        render_hwpx(REPORT, highlights, replace(synthesis, limitation=""))


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_the_module_does_not_import_bcs_or_legacy_renderers():
    """BCS v0는 동결이다. 고치지 않는 것을 넘어 의존하지도 않는다."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name.startswith(("bcs", "m8", "legacy")) for name in imported)
    assert imported <= {"__future__", "re", "zipfile", "io", "xml.sax.saxutils",
                        "v2_1_render", "v2_1_run"}


def test_the_module_does_not_import_pre_grounding_layers():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & set(FORBIDDEN_UPSTREAM)


def test_the_module_does_not_do_fallback():
    """실패 시 무엇으로 대체할지는 C-08의 몫이다."""
    assert "fallback" not in code_only(MODULE).lower()
