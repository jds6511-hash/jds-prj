"""A1 — 한글 COM HWPX 경로의 계약. COM 없이 잴 수 있는 것만 여기서 잰다.

```
A1-4  _lines() 문장 순서 보존
A1-5  새 semantic text 0
A1-6  sparse 정본 문장 보존
A1-7  canonical mutation 0
A1-8  COM 없으면 명시적 실패 · hand-built 렌더러로 대체 금지
```

실제 저장·열기(A1-1~3)와 화면 렌더(A1-9)는 한글이 있는 기계에서만 잴 수 있다.
**그것을 조건부 skip으로 숨기지 않는다** — 별도 검증 스크립트가 산출물을 남기고,
그 결과는 문서에 적는다.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_render_hwpx import _lines, semantic_view
from v2_1_run import Manifest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/v2_1_hwpx_via_hangul.py"


def _load():
    spec = importlib.util.spec_from_file_location("v2_1_hwpx_via_hangul", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hangul = _load()

THREE = ((0, 3), (4, 7), (8, 11))
TWO = ((0, 5), (6, 11))
NORMAL = (
    {"summary": "두 여성이 해변에 앉아 주변을 둘러본다."},
    {"summary": "두 여성이 가방을 열고 음료를 나눠 마신다."},
    {"summary": "두 여성이 돗자리를 펴고 간식을 꺼낸다."},
)
SPARSE_ASR = {**{i: "" for i in range(12)}, 9: "남성이 문을 연다."}
INVENTED = "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."
SPARSE = ({"summary": "앞 구간."}, {"summary": INVENTED})


class _Writer:
    """저장 대신 줄을 받아 적는다. COM 없이 계약을 재기 위한 것이다."""

    def __init__(self):
        self.lines = None
        self.calls = 0

    def __call__(self, lines, out, pdf):
        self.lines = list(lines)
        self.calls += 1
        return {"hwpx": str(out), "pdf": None}


def _manifest(document):
    return Manifest(video_id=document["video_id"], run_id=document["run_id"],
                    analysis_mode="report", config_hash="test",
                    code_git_head="head")


def _document(tmp_path, payloads=NORMAL, spans=THREE, asr=None, name="S1"):
    return run_pipeline(tmp_path, payloads, name=name, spans=spans,
                        asr_overrides=asr).document


# ── A1-4 · A1-5 문장은 frozen _lines()에서만 나온다 ──────────────────────
def test_a1_4_the_written_lines_are_exactly_the_frozen_ones(tmp_path):
    document = _document(tmp_path)
    manifest = _manifest(document)
    writer = _Writer()
    hangul.render(document, tmp_path / "out.hwpx", manifest=manifest,
                  writer=writer)

    from v2_1_highlight import HighlightSpec, build_highlights
    from v2_1_lineage import build_lineage
    from v2_1_presentation import build_presentation
    from v2_1_presentation_input import presentation_input
    from v2_1_synthesis import build_synthesis

    presented = presentation_input(document)
    highlights = build_highlights(
        presented, [HighlightSpec((e["episode_id"],))
                    for e in document["episodes"]])
    synthesis = build_synthesis(presented, build_lineage(presented, highlights))
    presentation = build_presentation(presented, highlights)
    expected = _lines(manifest, semantic_view(presentation, synthesis),
                      presentation)

    assert writer.lines == expected


def test_a1_5_no_sentence_is_added_outside_the_frozen_lines(tmp_path):
    """쓰인 줄 전부가 `_lines()`가 낸 줄이어야 한다 — 한 줄도 더 만들지 않는다."""
    document = _document(tmp_path)
    manifest = _manifest(document)
    writer = _Writer()
    hangul.render(document, tmp_path / "out.hwpx", manifest=manifest,
                  writer=writer)
    allowed = set(hangul.report_lines(document,
                                      hangul.default_groups(document), manifest))
    assert set(writer.lines) <= allowed
    assert any("두 여성이" in line for line in writer.lines)


def test_the_section_headings_survive(tmp_path):
    document = _document(tmp_path)
    writer = _Writer()
    hangul.render(document, tmp_path / "out.hwpx",
                  manifest=_manifest(document), writer=writer)
    for section in ("개요", "주요 사건 및 내용", "핵심 내용 분석", "결론",
                    "근거 및 생성 정보"):
        assert any(line == "■ " + section for line in writer.lines), section


# ── A1-6 sparse 정본 문장 ────────────────────────────────────────────────
def test_a1_6_the_sparse_canonical_sentence_reaches_the_document(tmp_path):
    document = _document(tmp_path, SPARSE, spans=TWO, asr=SPARSE_ASR, name="S4")
    assert document["episodes"][1]["summary"] == "남성이 문을 연다."
    writer = _Writer()
    hangul.render(document, tmp_path / "out.hwpx",
                  manifest=_manifest(document), writer=writer)
    body = "\n".join(writer.lines)
    assert "남성이 문을 연다." in body
    for invented in ("건물", "훔친", "달아난다"):
        assert invented not in body, invented


# ── A1-7 정본은 읽기 전용 ────────────────────────────────────────────────
def test_a1_7_the_canonical_file_is_not_mutated(tmp_path):
    document = _document(tmp_path)
    path = tmp_path / "aar_canonical.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    hangul.render(loaded, tmp_path / "out.hwpx", manifest=_manifest(loaded),
                  writer=_Writer())
    assert path.read_bytes() == before
    assert loaded == document


# ── A1-8 COM이 없으면 명시적으로 실패한다 ────────────────────────────────
def test_a1_8_a_missing_com_fails_explicitly(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pyhwpx", None)
    document = _document(tmp_path)
    out = tmp_path / "out.hwpx"
    with pytest.raises(hangul.HwpxComError):
        hangul.render(document, out, manifest=_manifest(document))
    assert not out.exists()


def test_a1_8_the_broken_hand_built_renderer_is_never_a_fallback():
    """손으로 만든 패키지는 한글에서 열리지 않는다 — 대체 경로로 두지 않는다."""
    source = SCRIPT.read_text(encoding="utf-8")
    # `_lines`·`semantic_view`는 가져다 쓴다. 금지되는 것은 **패키지를 만드는**
    # 함수를 부르는 것이다.
    assert not re.search(r"render_hwpx\s*\(", source)
    assert not re.search(r"write_hwpx\s*\(", source)


def test_a_failed_save_is_not_reported_as_success(tmp_path):
    def refuses(lines, out, pdf):
        raise hangul.HwpxComError("HWPX 저장 실패")

    document = _document(tmp_path)
    with pytest.raises(hangul.HwpxComError):
        hangul.render(document, tmp_path / "out.hwpx",
                      manifest=_manifest(document), writer=refuses)


# ── 인터록·묶음 ──────────────────────────────────────────────────────────
def test_a_non_report_run_is_refused(tmp_path):
    document = _document(tmp_path)
    manifest = Manifest(video_id="S1", run_id="r", analysis_mode="research",
                        config_hash="c", code_git_head="h")
    with pytest.raises(Exception):
        hangul.render(document, tmp_path / "out.hwpx", manifest=manifest,
                      writer=_Writer())


def test_the_default_grouping_is_one_highlight_per_episode(tmp_path):
    document = _document(tmp_path)
    assert hangul.default_groups(document) == (("EP01",), ("EP02",), ("EP03",))


def test_an_explicit_grouping_is_honoured(tmp_path):
    document = _document(tmp_path)
    writer = _Writer()
    hangul.render(document, tmp_path / "out.hwpx", manifest=_manifest(document),
                  groups=(("EP01", "EP02"), ("EP03",)), writer=writer)
    body = "\n".join(writer.lines)
    assert "│ 구성 구간: EP01 · EP02" in body
