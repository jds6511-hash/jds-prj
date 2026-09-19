"""보고서 정본(`wvr_report.md`) → 관공서 서식 HWPX. **표현 계층이다 — 새 사실을 만들지 않는다.**

```
보고서 엔진 출력  wvr_report.md   ← 문장·시간은 여기서만 나온다
        ↓  parse_report()        제목 · 개요 · 표(구분·시간·내용·비고)
        ↓  build_html()          서식만 입힌다(셀 텍스트 변형 금지)
        ↓  한글 COM (pyhwpx)
   HWPX  (+ 진단용 PDF)
```

`scripts/v2_1_hwpx_via_hangul.py`와 같은 원칙이다.

```
새 문장           만들지 않는다 — 표의 셀과 개요 문단을 그대로 옮긴다
파생 허용 범위     구분별 건수 집계뿐이다(행에서만 계산, 합계 = 행 수)
silent fallback   한글 COM이 없으면 **명시적으로 실패**한다
```

사용:

    python scripts/wvr_report_hwpx.py \
        --report runs/.../wvr_report.md \
        --out 시연폴더/WVR_시연보고서.hwpx \
        --pdf 시연폴더/WVR_시연보고서_preview.pdf \
        --video-id 69E1sdSMaO4 --duration-min 40
"""
import argparse
import html as _html
import os
import re
import sys

NAVY = "#12355b"
INK = "#000000"
RULE = "#7f93a8"
ZEBRA = "#f4f7fa"
GRAY = "#333333"
FF = "'맑은 고딕','Malgun Gothic',sans-serif"

COLUMNS = ("구분", "시간", "내용", "비고")
FIXED_PHRASES = (
    "화면 이해 모델이 영상 구간을 직접 관찰 → 활동 타임라인 정리 → 요약",
    "검증된 기존 보고서의 사실·시간을 변경하지 않고 시연용 형식으로 변환함",
    "영상 전체를 빠짐없이 설명하는 문서가 아니라, 검증된 관찰 구간을 정리한 보고서임",
)


# ── 파싱 ────────────────────────────────────────────────────────────────

def _split_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def parse_report(md_text):
    """wvr_report.md 원문 → {title, overview, rows}. 문장은 손대지 않는다."""
    lines = md_text.splitlines()

    title = ""
    for ln in lines:
        if ln.startswith("# "):
            title = ln[2:].strip()
            break
    if not title:
        raise ValueError("제목(# ...)을 찾지 못했다")

    overview = ""
    for i, ln in enumerate(lines):
        if ln.strip().startswith("□") and "개요" in ln:
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if not s:
                    continue
                if s.startswith("□") or s.startswith("|"):
                    break
                overview = s
                break
            break
    if not overview:
        raise ValueError("개요 문단을 찾지 못했다")

    table = [ln for ln in lines if ln.strip().startswith("|")]
    if not table:
        raise ValueError("세부내용 표를 찾지 못했다")

    header = _split_row(table[0])
    if tuple(header) != COLUMNS:
        raise ValueError("표의 열 구성이 %s가 아니다: %s" % (list(COLUMNS), header))

    rows = []
    for ln in table[1:]:
        cells = _split_row(ln)
        if all(set(c) <= set("-: ") for c in cells):      # 구분선
            continue
        if len(cells) != len(COLUMNS):
            raise ValueError("표의 열 개수가 어긋난다: %s" % ln)
        rows.append({"category": cells[0], "time": cells[1],
                     "content": cells[2], "note": cells[3]})
    if not rows:
        raise ValueError("세부내용 표에 행이 없다")
    return {"title": title, "overview": overview, "rows": rows}


def category_counts(rows):
    """행에서만 파생되는 집계. 등장 순서를 유지한다."""
    out = []
    for r in rows:
        for i, (k, c) in enumerate(out):
            if k == r["category"]:
                out[i] = (k, c + 1)
                break
        else:
            out.append((r["category"], 1))
    return out


# ── HTML(표현 계층) ─────────────────────────────────────────────────────

def _t(text, pt=11, color=INK, bold=False, sp=None, escape=True):
    body = _html.escape(text, quote=False) if escape else text
    st = "font-family:%s; font-size:%spt; color:%s;" % (FF, pt, color)
    if bold:
        st += " font-weight:bold;"
    if sp:
        st += " letter-spacing:%spt;" % sp
    return '<span style="%s">%s</span>' % (st, body)


def html_to_text(html_str):
    """테스트·검증용 — 태그를 걷어낸 평문."""
    txt = re.sub(r"<[^>]+>", " ", html_str)
    txt = _html.unescape(txt).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", txt)


def build_html(doc, video_id, duration_min=None):
    rows = doc["rows"]
    counts = category_counts(rows)
    o = []
    w = o.append

    w('<!doctype html><html lang="ko"><head><meta charset="utf-8">')
    w("<title>" + _html.escape(doc["title"]) + "</title></head><body bgcolor=\"#ffffff\">")

    # 제목 — 상하 굵은 띠
    w('<table width="100%" border="0" cellspacing="0" cellpadding="0">')
    w('<tr><td bgcolor="%s" height="4">%s</td></tr>' % (NAVY, _t("&nbsp;", 2, NAVY, escape=False)))
    w('<tr><td style="padding:7pt 0 7pt 6pt;">%s</td></tr>' % _t(doc["title"], 20, NAVY, True, 1.5))
    w('<tr><td bgcolor="%s" height="2">%s</td></tr>' % (NAVY, _t("&nbsp;", 1, NAVY, escape=False)))
    w("</table>")
    w('<p style="margin:14pt 0 0 0;">%s</p>' % _t("&nbsp;", 4, escape=False))

    def sq(text):
        w('<p style="margin:0 0 5pt 0;">%s</p>' % _t("□ " + text, 13, NAVY, True))

    def ci(label, value):
        w('<p style="margin:0 0 3pt 0;">&nbsp;&nbsp;%s</p>'
          % _t("○ %s : %s" % (label, value), 11))

    sq("보고 개요")
    target = video_id if duration_min is None else "%s (약 %s분)" % (video_id, duration_min)
    ci("대상 영상", target)
    ci("생성 방식", FIXED_PHRASES[0])
    ci("관찰 구간", "%d건" % len(rows))
    w('<p style="margin:2pt 0 4pt 0;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s</p>' % _t("- 구분별 건수", 11))
    w('<table width="92%" align="center" border="1" bordercolor="' + RULE
      + '" cellspacing="0" cellpadding="5">')
    w('<tr bgcolor="%s">' % NAVY)
    for k, _c in counts:
        w('<td align="center" nowrap>%s</td>' % _t(k, 10, "#ffffff", True))
    w("</tr><tr>")
    for _k, c in counts:
        w('<td align="center" nowrap>%s</td>' % _t("%d건" % c, 10))
    w("</tr></table>")
    w('<p style="margin:3pt 0 0 0;">&nbsp;&nbsp;%s</p>' % _t("※ " + FIXED_PHRASES[1], 10, GRAY))
    w('<p style="margin:12pt 0 0 0;">%s</p>' % _t("&nbsp;", 4, escape=False))

    sq("영상 개요")
    w('<table width="100%" border="1" bordercolor="' + RULE
      + '" cellspacing="0" cellpadding="9" bgcolor="' + ZEBRA + '">')
    w("<tr><td>%s</td></tr></table>" % _t(doc["overview"], 11))
    w('<p style="margin:12pt 0 0 0;">%s</p>' % _t("&nbsp;", 4, escape=False))

    sq("세부 관찰 내용")
    w('<table width="100%" border="1" bordercolor="' + RULE
      + '" cellspacing="0" cellpadding="7">')
    w('<tr bgcolor="%s">' % NAVY)
    for h, wd in (("연 번", "8%"), ("구 분", "16%"), ("시 간", "22%"),
                  ("내 용", "38%"), ("비 고", "16%")):
        w('<td width="%s" align="center">%s</td>' % (wd, _t(h, 11, "#ffffff", True, 1)))
    w("</tr>")
    for i, r in enumerate(rows, 1):
        w('<tr bgcolor="%s">' % (ZEBRA if i % 2 == 0 else "#ffffff"))
        w('<td align="center">%s</td>' % _t(str(i), 10.5))
        w('<td align="center">%s</td>' % _t(r["category"], 10.5, NAVY, True))
        w('<td align="center">%s</td>' % _t(r["time"], 10.5))
        w("<td>%s</td>" % _t(r["content"], 10.5))
        w('<td align="center">%s</td>' % _t(r["note"], 9.5, GRAY))
        w("</tr>")
    w("</table>")
    w('<p style="margin:10pt 0 0 0;">&nbsp;&nbsp;%s</p>' % _t("※ " + FIXED_PHRASES[2], 10, GRAY))
    w("</body></html>")
    return "\n".join(o)


# ── HWPX 변환 ───────────────────────────────────────────────────────────

def render_hwpx(html_path, out_path, pdf_path=None,
                margins=(15, 13, 20, 20)):
    """한글 COM으로 저장한다. COM이 없으면 손으로 만든 패키지로 대체하지 않고 실패한다."""
    try:
        from pyhwpx import Hwp
    except ImportError as exc:                              # noqa: BLE001
        raise RuntimeError(
            "pyhwpx/한글이 없다. 이 경로는 한글 COM 전용이다(대체 저장 없음)") from exc

    top, bottom, left, right = margins
    hwp = Hwp(new=True, visible=False)
    try:
        if not hwp.open(os.path.abspath(html_path), format="HTML"):
            raise RuntimeError("한글이 HTML을 열지 못했다: %s" % html_path)
        pd = hwp.get_pagedef_as_dict()
        pd["TopMargin"], pd["BottomMargin"] = top, bottom
        pd["LeftMargin"], pd["RightMargin"] = left, right
        pd["HeaderLen"], pd["FooterLen"] = 0, 0
        hwp.set_pagedef(pd, apply="all")
        if not hwp.save_as(os.path.abspath(out_path), format="HWPX"):
            raise RuntimeError("HWPX 저장 실패: %s" % out_path)
        if pdf_path and not hwp.save_as(os.path.abspath(pdf_path), format="PDF"):
            raise RuntimeError("PDF 저장 실패: %s" % pdf_path)
    finally:
        hwp.quit(save=False)
    return out_path


def verify_hwpx(out_path, doc):
    """저장본 본문(section*.xml)에 모든 시간·문장이 남아 있는지 확인한다.

    `Preview/PrvText.txt`는 길이가 잘리므로 검증 근거로 쓰지 않는다.
    """
    import zipfile

    with zipfile.ZipFile(out_path) as z:
        sections = [n for n in z.namelist()
                    if re.match(r"Contents/section\d+\.xml$", n)]
        if not sections:
            return {"checked": False, "missing": []}
        body = "".join(z.read(n).decode("utf-8", "ignore") for n in sorted(sections))
    text = _html.unescape(re.sub(r"<[^>]+>", "", body))
    flat = re.sub(r"\s+", "", text)
    missing = []
    for r in doc["rows"]:
        for key in ("time", "content"):
            if re.sub(r"\s+", "", r[key]) not in flat:
                missing.append("%s/%s" % (r["time"], key))
    return {"checked": True, "missing": missing}


def main(argv=None):
    ap = argparse.ArgumentParser(description="wvr_report.md → 관공서 서식 HWPX")
    ap.add_argument("--report", required=True, help="보고서 정본 마크다운")
    ap.add_argument("--out", required=True, help="출력 HWPX 경로")
    ap.add_argument("--pdf", help="진단용 PDF 경로(선택)")
    ap.add_argument("--html", help="중간 HTML 저장 경로(기본: --out 옆 .html)")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--duration-min", help="영상 길이(분). 생략하면 표기하지 않는다")
    args = ap.parse_args(argv)

    with open(args.report, encoding="utf-8") as fh:
        doc = parse_report(fh.read())

    html_path = args.html or os.path.splitext(args.out)[0] + "_source.html"
    with open(html_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_html(doc, args.video_id, args.duration_min))

    render_hwpx(html_path, args.out, args.pdf)
    result = verify_hwpx(args.out, doc)
    print("행 %d · 구분 %s" % (len(doc["rows"]), category_counts(doc["rows"])))
    print("출력 %s" % args.out)
    if args.pdf:
        print("PDF %s" % args.pdf)
    if result["checked"] and result["missing"]:
        print("검증 실패 — 미리보기에서 누락: %s" % result["missing"], file=sys.stderr)
        return 1
    print("검증 %s" % ("PASS" if result["checked"] else "SKIP(미리보기 없음)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
