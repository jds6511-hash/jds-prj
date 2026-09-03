"""정본 → HWPX (순수 Python, OWPML 최소 패키지). **한글 설치가 필요 없다.**

```
A1   scripts/v2_1_hwpx_via_hangul.py   한글 COM · Windows 전용 · 호환성 기준
A2'  이 파일                            순수 Python · 서버·CI 가능
```

문장은 두 경로 모두 frozen `v2_1_render_hwpx._lines()`에서만 나온다. 그래서 두
산출물의 semantic text는 같아야 하고, 그것을 differential test로 잰다.

`src/v2_1_render_hwpx.py`가 만드는 패키지는 **참조 그래프가 끊겨 있어** 한글에서
열리지 않는다(보고서 §5 결함 기록). 여기서 고치는 것은 그 결함이 아니라 **새 경로**다.
결함 기록은 역사로 남는다.

만드는 파트는 최소로 둔다. 파트 개수를 한글 저장본에 맞추는 것이 목적이 아니라,
**참조 그래프가 닫힌 최소 문서**를 만드는 것이 목적이다.

```
mimetype                 application/hwp+zip · 무압축(STORED)
META-INF/container.xml   rootfile → Contents/content.hpf
Contents/content.hpf     manifest(header·section0) + spine
Contents/header.xml      fontface · charPr · paraPr · borderFill · style — section이 쓰는 것만
Contents/section0.xml    문단. 첫 run이 secPr(용지·여백)를 든다
Preview/PrvText.txt      진단·호환용 평문
```

`validate_package()`는 **자기가 만든 subset의 invariant만** 검사한다. OWPML 전체
validator가 아니다.

사용:

    python scripts/v2_1_hwpx_owpml.py --canonical <aar_canonical.json> \\
        --config-hash <hash> --out out/report.hwpx
"""
import argparse
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_run import Manifest, current_git_head            # noqa: E402


def _a1():
    """문장 생성 경로를 두 벌로 두지 않는다 — A1과 같은 함수를 쓴다."""
    spec = importlib.util.spec_from_file_location(
        "v2_1_hwpx_via_hangul", ROOT / "scripts/v2_1_hwpx_via_hangul.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIMETYPE = "application/hwp+zip"
HEADER_PART = "Contents/header.xml"
SECTION_PART = "Contents/section0.xml"
CONTENT_PART = "Contents/content.hpf"
CONTAINER_PART = "META-INF/container.xml"
PREVIEW_PART = "Preview/PrvText.txt"

NS = (
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
    'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
)

#: 본문·제목·박스 세 가지면 `_lines()`를 표현할 수 있다. 더 만들지 않는다.
CHAR_BODY, CHAR_HEAD, CHAR_BOX = 0, 1, 2
#: 글자 크기는 HWPUNIT(1pt = 100).
CHAR_SPEC = (
    (CHAR_BODY, 1000, 0, "0"),
    (CHAR_HEAD, 1300, 1, "0"),
    (CHAR_BOX, 950, 0, "1"),          # 고정폭 — 문자 박스 열을 맞춘다
)
FONTS = ("함초롬바탕", "굴림체")

_HEADING = "■"
_BOX_PREFIX = ("┌", "│", "└", "─")


def _char_id(line: str) -> int:
    if line.startswith(_BOX_PREFIX):
        return CHAR_BOX
    return CHAR_HEAD if line.startswith(_HEADING) else CHAR_BODY


def container_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<ocf:container '
        'xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf">'
        '<ocf:rootfiles>'
        '<ocf:rootfile full-path="%s" '
        'media-type="application/hwpml-package+xml"/>'
        '</ocf:rootfiles></ocf:container>' % CONTENT_PART
    )


def content_hpf(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" version="" '
        'unique-identifier="" id="">'
        '<opf:metadata>'
        '<opf:title>%s</opf:title>'
        '<opf:meta name="generator" content="v2_1_hwpx_owpml"/>'
        '</opf:metadata>'
        '<opf:manifest>'
        '<opf:item id="header" href="%s" media-type="application/xml"/>'
        '<opf:item id="section0" href="%s" media-type="application/xml"/>'
        '</opf:manifest>'
        '<opf:spine>'
        '<opf:itemref idref="header" linear="no"/>'
        '<opf:itemref idref="section0" linear="yes"/>'
        '</opf:spine></opf:package>'
        % (escape(title), HEADER_PART, SECTION_PART)
    )


def _fontface(lang: str) -> str:
    fonts = "".join(
        '<hh:font id="%d" face="%s" type="TTF" isEmbedded="0">'
        '<hh:typeInfo familyType="FCAT_GOTHIC" weight="6" proportion="4" '
        'contrast="0" strokeVariation="1" armStyle="1" letterform="1" '
        'midline="1" xHeight="1"/></hh:font>' % (index, face)
        for index, face in enumerate(FONTS)
    )
    return ('<hh:fontface lang="%s" fontCnt="%d">%s</hh:fontface>'
            % (lang, len(FONTS), fonts))


def _char_pr(char_id: int, height: int, bold: int, font_id: str) -> str:
    seven = ' '.join('%s="%s"' % (key, font_id) for key in
                     ("hangul", "latin", "hanja", "japanese", "other",
                      "symbol", "user"))
    hundred = ' '.join('%s="100"' % key for key in
                       ("hangul", "latin", "hanja", "japanese", "other",
                        "symbol", "user"))
    zero = ' '.join('%s="0"' % key for key in
                    ("hangul", "latin", "hanja", "japanese", "other",
                     "symbol", "user"))
    return (
        '<hh:charPr id="%d" height="%d" textColor="#000000" shadeColor="none" '
        'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="1">'
        '<hh:fontRef %s/><hh:ratio %s/><hh:spacing %s/><hh:relSz %s/>'
        '<hh:offset %s/>'
        '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
        '<hh:strikeout shape="NONE" color="#000000"/>'
        '<hh:outline type="NONE"/>'
        '<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>'
        '%s</hh:charPr>'
        % (char_id, height, seven, hundred, zero, hundred, zero,
           "<hh:bold/>" if bold else "")
    )


def header_xml() -> str:
    chars = "".join(_char_pr(*spec) for spec in CHAR_SPEC)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<hh:head %s version="1.4" secCnt="1">'
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" '
        'equation="1"/>'
        '<hh:refList>'
        '<hh:fontfaces itemCnt="2">%s%s</hh:fontfaces>'
        '<hh:borderFills itemCnt="1">'
        '<hh:borderFill id="1" threeD="0" shadow="0" centerLine="NONE" '
        'breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        '</hh:borderFill></hh:borderFills>'
        '<hh:charProperties itemCnt="%d">%s</hh:charProperties>'
        '<hh:tabProperties itemCnt="1">'
        '<hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>'
        '</hh:tabProperties>'
        '<hh:paraProperties itemCnt="1">'
        '<hh:paraPr id="0" tabPrIDRef="0" condense="0" fontLineHeight="0" '
        'snapToGrid="1" suppressLineNumbers="0" checked="0">'
        '<hh:align horizontal="LEFT" vertical="BASELINE"/>'
        '<hh:heading type="NONE" idRef="0" level="0"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" '
        'breakNonLatinWord="KEEP_WORD" widowOrphan="0" keepWithNext="0" '
        'keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hh:margin><hc:intent value="0" unit="HWPUNIT"/>'
        '<hc:left value="0" unit="HWPUNIT"/>'
        '<hc:right value="0" unit="HWPUNIT"/>'
        '<hc:prev value="0" unit="HWPUNIT"/>'
        '<hc:next value="0" unit="HWPUNIT"/></hh:margin>'
        '<hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/>'
        '<hh:border borderFillIDRef="1" offsetLeft="0" offsetRight="0" '
        'offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/>'
        '</hh:paraPr></hh:paraProperties>'
        '<hh:styles itemCnt="1">'
        '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" '
        'lockForm="0"/></hh:styles>'
        '</hh:refList></hh:head>'
        % (NS, _fontface("HANGUL"), _fontface("LATIN"),
           len(CHAR_SPEC), chars)
    )


#: 첫 문단의 run이 용지·여백을 든다. A4 세로 · 여백은 한글 기본값(HWPUNIT).
_SEC_PR = (
    '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" '
    'tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" '
    'outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" '
    'masterPageCnt="0">'
    '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>'
    '<hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
    '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" '
    'hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" '
    'hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>'
    '<hp:pagePr landscape="WIDELY" width="59528" height="84186" '
    'gutterType="LEFT_ONLY">'
    '<hp:margin header="4252" footer="4252" gutter="0" left="8504" '
    'right="8504" top="5668" bottom="4252"/></hp:pagePr>'
    '</hp:secPr>'
)


def section_xml(lines) -> str:
    paragraphs = []
    for index, line in enumerate(lines):
        char_id = _char_id(line)
        inner = _SEC_PR if index == 0 else ""
        if line:
            inner += '<hp:t>%s</hp:t>' % escape(line)
        paragraphs.append(
            '<hp:p id="%d" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
            'columnBreak="0" merged="0"><hp:run charPrIDRef="%d">%s</hp:run>'
            '</hp:p>' % (index, char_id, inner)
        )
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<hs:sec %s>%s</hs:sec>' % (NS, "".join(paragraphs)))


def build_parts(lines, title: str) -> dict:
    return {
        CONTAINER_PART: container_xml(),
        CONTENT_PART: content_hpf(title),
        HEADER_PART: header_xml(),
        SECTION_PART: section_xml(lines),
        PREVIEW_PART: "\n".join(lines),
    }


def write_hwpx(lines, out: Path, title: str) -> Path:
    """mimetype을 **무압축으로 먼저** 넣는다 — 패키지 인식 조건이다."""
    parts = build_parts(lines, title)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE,
                         zipfile.ZIP_STORED)
        for name, text in parts.items():
            package.writestr(name, text)
    return out


# ── 구조 검증 — 자기가 만든 subset의 invariant만 본다 ────────────────────
_ID_REF = re.compile(r'(charPrIDRef|paraPrIDRef|styleIDRef)="(\d+)"')
_HEADER_ID = {
    "charPrIDRef": re.compile(r'<hh:charPr id="(\d+)"'),
    "paraPrIDRef": re.compile(r'<hh:paraPr id="(\d+)"'),
    "styleIDRef": re.compile(r'<hh:style id="(\d+)"'),
}


def validate_package(path: Path) -> list[str]:
    """끊긴 참조를 **한글을 켜기 전에** 잡는다. 실패 사유를 전부 모은다."""
    failures = []
    with zipfile.ZipFile(path) as package:
        if package.testzip() is not None:
            failures.append("zip: 손상된 항목이 있다")
        names = set(package.namelist())
        info = {i.filename: i for i in package.infolist()}

        if "mimetype" not in names:
            failures.append("mimetype: 없다")
        else:
            if package.read("mimetype").decode() != MIMETYPE:
                failures.append("mimetype: 내용이 %s가 아니다" % MIMETYPE)
            if info["mimetype"].compress_type != zipfile.ZIP_STORED:
                failures.append("mimetype: 무압축(STORED)이 아니다")

        for part in (CONTAINER_PART, CONTENT_PART, HEADER_PART, SECTION_PART):
            if part not in names:
                failures.append("%s: 없다" % part)
        if failures:
            return failures

        texts = {part: package.read(part).decode("utf-8")
                 for part in (CONTAINER_PART, CONTENT_PART, HEADER_PART,
                              SECTION_PART)}
        for part, text in texts.items():
            try:
                ElementTree.fromstring(text)
            except ElementTree.ParseError as error:
                failures.append("%s: XML 파싱 실패 (%s)" % (part, error))
        if failures:
            return failures

        for root in re.findall(r'full-path="([^"]+)"', texts[CONTAINER_PART]):
            if root not in names:
                failures.append("container rootfile이 없다: %s" % root)

        manifest = dict(re.findall(
            r'<opf:item id="([^"]+)" href="([^"]+)"', texts[CONTENT_PART]))
        for item_id, href in manifest.items():
            if href not in names:
                failures.append("manifest href가 없다: %s → %s" % (item_id, href))
        for idref in re.findall(r'<opf:itemref idref="([^"]+)"',
                                texts[CONTENT_PART]):
            if idref not in manifest:
                failures.append("spine idref가 manifest에 없다: %s" % idref)

        declared = {key: set(pattern.findall(texts[HEADER_PART]))
                    for key, pattern in _HEADER_ID.items()}
        for kind, value in _ID_REF.findall(texts[SECTION_PART]):
            if value not in declared[kind]:
                failures.append("section의 %s=%s가 header에 없다" % (kind, value))
    return failures


def semantic_text(path: Path) -> list[str]:
    """문서에 실린 문장을 순서대로 읽는다. 대조·검증용이다."""
    from xml.sax.saxutils import unescape

    with zipfile.ZipFile(path) as package:
        section = package.read(SECTION_PART).decode("utf-8")
    return [unescape(text) for text in re.findall(r"<hp:t>(.*?)</hp:t>",
                                                  section, re.S)]


def render(document: dict, out: Path, *, manifest: Manifest, groups=None) -> dict:
    a1 = _a1()
    lines = a1.report_lines(document, groups or a1.default_groups(document),
                            manifest)
    write_hwpx(lines, out, manifest.video_id)
    failures = validate_package(out)
    if failures:
        raise SystemExit("패키지 검증 실패:\n" + "\n".join(failures))
    return {"hwpx": str(out), "lines": len(lines),
            "bytes": out.stat().st_size}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config-hash", required=True)
    parser.add_argument("--code-head", default=None)
    parser.add_argument("--group", action="append", default=None)
    args = parser.parse_args(argv)

    document = json.loads(Path(args.canonical).read_text(encoding="utf-8"))
    groups = tuple(tuple(g.split(",")) for g in args.group) if args.group else None
    manifest = Manifest(video_id=document["video_id"], run_id=document["run_id"],
                        analysis_mode="report", config_hash=args.config_hash,
                        code_git_head=args.code_head or current_git_head(ROOT))
    print(json.dumps(render(document, Path(args.out), manifest=manifest,
                            groups=groups), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
