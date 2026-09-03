"""정본(canonical) → 한글(COM) HWPX. **표현 계층이다 — 새 사실을 만들지 않는다.**

```
canonical + presentation + synthesis
        ↓
v2_1_render_hwpx._lines()        ← 문장은 여기서만 나온다
        ↓
한글 COM (pyhwpx)
        ↓
SaveAs HWPX  (+ 진단용 PDF)
```

`src/v2_1_render_hwpx.py`가 손으로 만드는 패키지는 **한글에서 열리지 않는다**(결함
기록: `docs/finalization/V2_1_FINAL_ACCEPTANCE_2026-09-02.md` §5). 이 스크립트는 그
결함을 우회하는 **제출용 경로**이고, 같은 본문 줄을 한글이 직접 저장하게 한다.

두 가지를 하지 않는다.

```
새 문장           만들지 않는다 — `_lines()`가 낸 줄만 쓴다
silent fallback   COM이 없으면 **명시적으로 실패**한다.
                  손으로 만든(열리지 않는) 패키지로 대체하지 않는다
```

`BCS_CORE_FREEZE`가 정한 것과 같은 원칙이다. 형식 변환·서식만 하고 정본은 읽기
전용으로 다룬다.

사용:

    python scripts/v2_1_hwpx_via_hangul.py \\
        --canonical runs/v2_1/<video>/aar_canonical.json \\
        --config-hash <hash> --out out/report.hwpx --pdf out/report.pdf
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_highlight import HighlightSpec, build_highlights   # noqa: E402
from v2_1_lineage import build_lineage                       # noqa: E402
from v2_1_presentation import build_presentation             # noqa: E402
from v2_1_presentation_input import presentation_input       # noqa: E402
from v2_1_render_hwpx import _lines, semantic_view           # noqa: E402
from v2_1_run import Manifest, current_git_head, require_report_mode  # noqa: E402
from v2_1_synthesis import build_synthesis                   # noqa: E402

#: 제목 줄 표시. `_lines()`가 절 머리에 쓰는 기호와 같다.
_HEADING = "■"
SIZE_HEAD, SIZE_BODY = 13, 11

#: `_lines()`가 박스를 **문자로** 그린다(`┌ │ └ ─`). 가변폭 글꼴 + 양쪽정렬에서는
#: 세로선과 가로선이 어긋나므로, 그 줄만 고정폭으로 둔다. 문장은 건드리지 않는다 —
#: 서식만 바꾼다.
_BOX_PREFIX = ("┌", "│", "└", "─")
BOX_FACE = "굴림체"
BODY_FACE = "함초롬바탕"
SIZE_BOX = 9.5


class HwpxComError(RuntimeError):
    """한글 COM 경로 실패. 다른 렌더러로 대체하지 않는다."""


def default_groups(document: dict) -> tuple:
    """구간 하나당 highlight 하나. 묶음을 임의로 만들지 않는다."""
    return tuple((episode["episode_id"],) for episode in document["episodes"])


def report_lines(document: dict, groups, manifest: Manifest) -> list[str]:
    """정본에서 본문 줄을 만든다. 문장은 `_lines()`가 내는 것뿐이다."""
    require_report_mode(manifest)
    presented = presentation_input(document)
    highlights = build_highlights(presented, [HighlightSpec(g) for g in groups])
    synthesis = build_synthesis(presented, build_lineage(presented, highlights))
    presentation = build_presentation(presented, highlights)
    return _lines(manifest, semantic_view(presentation, synthesis), presentation)


def hangul_writer(lines, out: Path, pdf: Path | None) -> dict:
    """한글로 직접 저장한다. COM이 없으면 여기서 멈춘다."""
    try:
        from pyhwpx import Hwp
    except Exception as error:                      # noqa: BLE001
        raise HwpxComError(
            "한글 COM(pyhwpx)을 쓸 수 없다: %s — 손으로 만든 패키지로 대체하지 않는다"
            % error
        ) from error

    try:
        hwp = Hwp(visible=False, new=True)
    except Exception as error:                      # noqa: BLE001
        raise HwpxComError("한글을 띄우지 못했다: %s" % error) from error

    try:
        for line in lines:
            head = line.startswith(_HEADING)
            box = line.startswith(_BOX_PREFIX)
            # 양쪽정렬은 단어 간격을 늘려 박스 문자 열을 흐트러뜨린다.
            hwp.ParagraphShapeAlignLeft()
            if box:
                hwp.set_font(FaceName=BOX_FACE, Height=SIZE_BOX, Bold=False)
            else:
                hwp.set_font(FaceName=BODY_FACE,
                             Height=SIZE_HEAD if head else SIZE_BODY, Bold=head)
            if line:
                hwp.insert_text(line)
            hwp.BreakPara()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not hwp.save_as(str(out), format="HWPX"):
            raise HwpxComError("HWPX 저장 실패: %s" % out)
        saved_pdf = None
        if pdf is not None:
            # PDF는 **렌더 검증용 진단물**이다. 제출물 계약에 넣지 않는다.
            pdf.parent.mkdir(parents=True, exist_ok=True)
            if not hwp.save_as(str(pdf), format="PDF"):
                raise HwpxComError("PDF 저장 실패: %s" % pdf)
            saved_pdf = str(pdf)
    finally:
        hwp.quit()
    return {"hwpx": str(out), "pdf": saved_pdf}


def render(document: dict, out: Path, *, manifest: Manifest, groups=None,
           pdf: Path | None = None, writer=hangul_writer) -> dict:
    """정본 하나를 HWPX로 저장한다. 정본은 읽기만 한다."""
    lines = report_lines(document, groups or default_groups(document), manifest)
    result = writer(lines, out, pdf)
    result["lines"] = len(lines)
    return result


def _manifest(document: dict, config_hash: str, code_head: str) -> Manifest:
    return Manifest(
        video_id=document["video_id"],
        run_id=document["run_id"],
        analysis_mode="report",
        config_hash=config_hash,
        code_git_head=code_head,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config-hash", required=True)
    parser.add_argument("--code-head", default=None)
    parser.add_argument("--pdf", default=None)
    parser.add_argument("--group", action="append", default=None,
                        help="쉼표로 묶은 episode_id 목록. 반복 지정한다.")
    args = parser.parse_args(argv)

    document = json.loads(Path(args.canonical).read_text(encoding="utf-8"))
    groups = tuple(tuple(g.split(",")) for g in args.group) if args.group else None
    manifest = _manifest(document, args.config_hash,
                         args.code_head or current_git_head(ROOT))
    result = render(document, Path(args.out), manifest=manifest, groups=groups,
                    pdf=Path(args.pdf) if args.pdf else None)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
