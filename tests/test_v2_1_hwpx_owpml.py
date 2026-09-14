"""A2' — 순수 Python OWPML 패키지의 계약.

```
A2-01 ~ 07   패키지 구조·참조 그래프
A2-08 ~ 10   문장 보존 (frozen `_lines()`가 낸 것만, 그대로)
mutation     끊어 놓으면 **한글을 켜기 전에** validator가 RED
differential A1(COM)과 semantic text가 같다
```

한글 open()·PDF·화면 확인(A2-13~16)은 한글이 있는 기계에서만 잴 수 있다. 조건부
skip으로 숨기지 않고 별도 검증 스크립트가 산출물을 남기며, 결과는 문서에 적는다.
"""
import importlib.util
import re
import zipfile
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_run import Manifest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/v2_1_hwpx_owpml.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owpml = _load(SCRIPT, "v2_1_hwpx_owpml")
a1 = _load(ROOT / "scripts/v2_1_hwpx_via_hangul.py", "v2_1_hwpx_via_hangul")

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


def _manifest(document):
    return Manifest(video_id=document["video_id"], run_id=document["run_id"],
                    analysis_mode="report", config_hash="test",
                    code_git_head="head")


def _document(tmp_path, payloads=NORMAL, spans=THREE, asr=None, name="S1"):
    return run_pipeline(tmp_path, payloads, name=name, spans=spans,
                        asr_overrides=asr).document


def _render(tmp_path, **kwargs):
    document = _document(tmp_path, **kwargs)
    out = tmp_path / "out.hwpx"
    owpml.render(document, out, manifest=_manifest(document))
    return document, out


def _rewrite(source: Path, target: Path, edits: dict) -> Path:
    """부분 하나를 바꿔 다시 묶는다. mutation 주입용이다."""
    with zipfile.ZipFile(source) as package:
        parts = {name: package.read(name) for name in package.namelist()}
    for name, value in edits.items():
        if value is None:
            parts.pop(name, None)
        else:
            parts[name] = value.encode("utf-8")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(zipfile.ZipInfo("mimetype"), parts.pop("mimetype"),
                         zipfile.ZIP_STORED)
        for name, data in parts.items():
            package.writestr(name, data)
    return target


# ── A2-01 ~ 07 구조 ──────────────────────────────────────────────────────
def test_a2_01_to_07_a_fresh_package_passes_every_structural_invariant(tmp_path):
    _, out = _render(tmp_path)
    assert owpml.validate_package(out) == []


def test_a2_02_the_mimetype_is_stored_uncompressed(tmp_path):
    _, out = _render(tmp_path)
    with zipfile.ZipFile(out) as package:
        info = package.getinfo("mimetype")
        assert package.read("mimetype").decode() == "application/hwp+zip"
        assert info.compress_type == zipfile.ZIP_STORED
        assert package.namelist()[0] == "mimetype"


def test_the_package_stays_minimal(tmp_path):
    """파트 개수를 한글 저장본에 맞추지 않는다 — 참조 그래프만 닫는다."""
    _, out = _render(tmp_path)
    with zipfile.ZipFile(out) as package:
        assert set(package.namelist()) == {
            "mimetype", "META-INF/container.xml", "Contents/content.hpf",
            "Contents/header.xml", "Contents/section0.xml",
            "Preview/PrvText.txt"}


def test_every_id_the_section_uses_is_declared_in_the_header(tmp_path):
    _, out = _render(tmp_path)
    with zipfile.ZipFile(out) as package:
        section = package.read("Contents/section0.xml").decode("utf-8")
        header = package.read("Contents/header.xml").decode("utf-8")
    used = {int(v) for v in re.findall(r'charPrIDRef="(\d+)"', section)}
    declared = {int(v) for v in re.findall(r'<hh:charPr id="(\d+)"', header)}
    assert used and used <= declared


# ── A2-08 ~ 10 문장 ──────────────────────────────────────────────────────
def test_a2_08_the_document_text_is_exactly_the_frozen_lines(tmp_path):
    document, out = _render(tmp_path)
    manifest = _manifest(document)
    expected = [line for line in
                a1.report_lines(document, a1.default_groups(document), manifest)
                if line]
    assert owpml.semantic_text(out) == expected


def test_a2_09_no_sentence_is_added(tmp_path):
    document, out = _render(tmp_path)
    allowed = set(a1.report_lines(document, a1.default_groups(document),
                                  _manifest(document)))
    assert set(owpml.semantic_text(out)) <= allowed


def test_a2_10_the_sparse_sentence_survives_exactly(tmp_path):
    document, out = _render(tmp_path, payloads=SPARSE, spans=TWO,
                            asr=SPARSE_ASR, name="S4")
    assert document["episodes"][1]["summary"] == "남성이 문을 연다."
    body = "\n".join(owpml.semantic_text(out))
    assert "남성이 문을 연다." in body
    for invented in ("건물", "훔친", "달아난다"):
        assert invented not in body, invented


def test_the_two_renderers_agree_on_the_semantic_text(tmp_path):
    """A1(COM)과 A2'(Python)는 같은 문장을 실어야 한다 — differential."""
    document, out = _render(tmp_path)
    from_a1 = [line for line in
               a1.report_lines(document, a1.default_groups(document),
                               _manifest(document)) if line]
    assert owpml.semantic_text(out) == from_a1


# ── mutation — 한글을 켜기 전에 잡는다 ───────────────────────────────────
@pytest.mark.parametrize("label,edits", [
    ("M1_content_hpf_removed", {"Contents/content.hpf": None}),
    ("M2_rootfile_dangling", {"META-INF/container.xml": (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<ocf:rootfiles><ocf:rootfile full-path="Contents/missing.hpf" '
        'media-type="application/hwpml-package+xml"/></ocf:rootfiles>'
        '</ocf:container>')}),
])
def test_a_broken_package_reference_is_caught(tmp_path, label, edits):
    _, out = _render(tmp_path)
    broken = _rewrite(out, tmp_path / ("%s.hwpx" % label), edits)
    assert owpml.validate_package(broken), label


def test_m3_a_dangling_spine_idref_is_caught(tmp_path):
    _, out = _render(tmp_path)
    with zipfile.ZipFile(out) as package:
        content = package.read("Contents/content.hpf").decode("utf-8")
    broken = _rewrite(out, tmp_path / "m3.hwpx", {
        "Contents/content.hpf": content.replace('idref="section0"',
                                                'idref="ghost"')})
    failures = owpml.validate_package(broken)
    assert any("spine" in failure for failure in failures), failures


@pytest.mark.parametrize("attribute", ["charPrIDRef", "paraPrIDRef"])
def test_m4_m5_a_dangling_style_reference_is_caught(tmp_path, attribute):
    _, out = _render(tmp_path)
    with zipfile.ZipFile(out) as package:
        section = package.read("Contents/section0.xml").decode("utf-8")
    broken = _rewrite(out, tmp_path / ("m4_%s.hwpx" % attribute), {
        "Contents/section0.xml": section.replace('%s="0"' % attribute,
                                                 '%s="99"' % attribute, 1)})
    failures = owpml.validate_package(broken)
    assert any(attribute in failure for failure in failures), failures


def test_m6_a_dropped_line_changes_the_semantic_text(tmp_path):
    """구조 검사로는 못 잡는다 — 문장 대조가 그 자리를 맡는다."""
    document, out = _render(tmp_path)
    with zipfile.ZipFile(out) as package:
        section = package.read("Contents/section0.xml").decode("utf-8")
    dropped = re.sub(r"<hp:t>■ 결론</hp:t>", "", section, count=1)
    broken = _rewrite(out, tmp_path / "m6.hwpx",
                      {"Contents/section0.xml": dropped})
    expected = [line for line in
                a1.report_lines(document, a1.default_groups(document),
                                _manifest(document)) if line]
    assert owpml.validate_package(broken) == []      # 구조는 멀쩡하다
    assert owpml.semantic_text(broken) != expected   # 문장이 다르다


def test_m7_a_substituted_sentence_changes_the_semantic_text(tmp_path):
    document, out = _render(tmp_path, payloads=SPARSE, spans=TWO,
                            asr=SPARSE_ASR, name="S4")
    with zipfile.ZipFile(out) as package:
        section = package.read("Contents/section0.xml").decode("utf-8")
    broken = _rewrite(out, tmp_path / "m7.hwpx", {
        "Contents/section0.xml": section.replace("남성이 문을 연다.", INVENTED)})
    body = "\n".join(owpml.semantic_text(broken))
    assert "훔친" in body                              # mutation이 실제로 들어갔다
    expected = [line for line in
                a1.report_lines(document, a1.default_groups(document),
                                _manifest(document)) if line]
    assert owpml.semantic_text(broken) != expected


# ── 이 경로가 무엇이 아닌지 ──────────────────────────────────────────────
def test_the_broken_hand_built_renderer_is_not_reused():
    source = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"render_hwpx\s*\(", source)
    assert not re.search(r"write_hwpx\s*\(", source.split("def write_hwpx", 1)[0])


def test_no_hangul_com_dependency():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "pyhwpx" not in source
    assert "win32com" not in source
