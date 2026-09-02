"""v2.1 HWPX renderer — 같은 의미의 두 번째 serializer (Gate C · C-07).

```
semantic_view  ├─ preview   (C-06)
               ├─ Markdown  (C-06)
               └─ HWPX      (여기)
```

**새 의미 계층이 아니다.** Markdown과의 차이는 typography · layout이어야 하고
분석 결과의 차이가 되어서는 안 된다. 그래서 이 모듈도 정본 episode를 받지 않고,
`semantic_view`와 `LABELS`를 C-06과 공유한다.

```
허용   구역 · 문단 · 표 · 상자 글리프 · mm:ss 표기 · 사람이 읽는 provenance 문자열
금지   episode 조회 · 시간 재계산 · 재그룹 · summary 재작성 · 종합 축약
       누락값 의미 보정 · grounding 판단 · human reference에서 내용 가져오기
```

BCS v0는 동결돼 있다. 이 모듈은 **BCS renderer를 import하지 않는다** — 수정하지
않았다는 것을 넘어 구현에 의존하지도 않는다.

한계: 여기서는 한글(HWP)로 열어 확인할 수 없다. 패키지 구조는 OWPML 배치를 따라
작성했고, **실제 한글에서의 열림 여부는 검증되지 않았다**(C-10에 기록한다).
"""
from __future__ import annotations

import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape, unescape

from v2_1_render import LABELS, format_clock, semantic_view, summary_cell
from v2_1_run import require_report_mode

MIMETYPE = "application/hwp+zip"

_CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<odf:container xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:container">
  <odf:rootfiles>
    <odf:rootfile full-path="Contents/content.hpf" media-type="application/hwpml-package+xml"/>
  </odf:rootfiles>
</odf:container>
"""

_VERSION = """<?xml version="1.0" encoding="UTF-8"?>
<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version"
               tagetApplication="WORDPROCESSOR" major="5" minor="1"
               micro="1" buildNumber="0"/>
"""

_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" version="1.4"
         secCnt="1"/>
"""

_SECTION_OPEN = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"\n'
    '        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">\n'
)
_SECTION_CLOSE = "</hs:sec>\n"

#: 상자 글리프 — 서식이지 내용이 아니다.
_TOP = "┌───────────────────────────"
_MID = "│ "
_BOTTOM = "└───────────────────────────"


def _paragraph(text: str) -> str:
    return ('  <hp:p><hp:run><hp:t>%s</hp:t></hp:run></hp:p>\n'
            % escape(text))


def _lines(manifest, view, highlights) -> list[str]:
    """문서에 실을 줄. 값은 view에서 오고, 서식만 여기서 붙는다."""
    lines = [
        manifest.video_id,
        "run %s · config %s · code %s" % (manifest.run_id, manifest.config_hash,
                                          manifest.code_git_head),
        "",
        "■ 개요",
        view["overview"] or "—",
        "",
        "■ 주요 사건 및 내용",
    ]
    for record, source in zip(view["highlights"], highlights):
        lines += [
            _TOP,
            "%s%s%s" % (_MID, record["highlight_id"],
                        " · %s" % record["label"] if record["label"] else ""),
            "%s%s: %s–%s" % (_MID, LABELS["time"], format_clock(record["start_sec"]),
                             format_clock(record["end_sec"])),
            "%s%s: %s" % (_MID, LABELS["summary"], summary_cell(source)),
            "%s%s: %s" % (_MID, LABELS["sources"],
                          " · ".join(record["source_episode_ids"])),
            "%s%s: %s" % (_MID, LABELS["summary_sources"],
                          " · ".join(record["summary_source_episode_ids"]) or "-"),
            _BOTTOM,
        ]
    lines += ["", "■ 핵심 내용 분석"]
    lines += list(view["analysis"]) or ["—"]
    lines += [
        "",
        "■ 결론",
        view["conclusion"],
        "",
        "■ 근거 및 생성 정보",
        "%s: %s" % (LABELS["synthesis_sources"],
                    " · ".join(view["synthesis_sources"]) or "-"),
        "%s: %s" % (LABELS["limitation"], view["limitation"]),
    ]
    return lines


def render_hwpx(manifest, highlights, synthesis) -> bytes:
    """HWPX 패키지 하나를 만든다. `analysis_mode != report`이면 멈춘다.

    인터록은 C-06과 **같은 것**을 쓴다 — HWPX 전용 판정 규칙을 만들지 않는다.
    """
    require_report_mode(manifest)
    view = semantic_view(highlights, synthesis)

    section = _SECTION_OPEN + "".join(
        _paragraph(line) for line in _lines(manifest, view, highlights)
    ) + _SECTION_CLOSE

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            zipfile.ZipInfo("mimetype"), MIMETYPE, zipfile.ZIP_STORED
        )
        package.writestr("META-INF/container.xml", _CONTAINER)
        package.writestr("version.xml", _VERSION)
        package.writestr("Contents/header.xml", _HEADER)
        package.writestr("Contents/section0.xml", section)
    return buffer.getvalue()


def write_hwpx(path, manifest, highlights, synthesis):
    """패키지를 파일로 쓴다. 실패를 다른 형식으로 대체하지 않는다(C-08 소관)."""
    payload = render_hwpx(manifest, highlights, synthesis)
    path.write_bytes(payload)
    return path


def hwpx_text(payload: bytes) -> str:
    """패키지 안의 본문 문단을 순서대로 읽는다. 검증·비교용이다."""
    with zipfile.ZipFile(BytesIO(payload)) as package:
        section = package.read("Contents/section0.xml").decode("utf-8")
    return "\n".join(unescape(text) for text in
                     re.findall(r"<hp:t>(.*?)</hp:t>", section, re.S))
