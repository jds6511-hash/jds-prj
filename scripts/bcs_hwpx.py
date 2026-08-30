"""BCS 정본 → HWPX. **표현 계층이다 — 새 사실을 만들지 않는다.**

결정: `docs/finalization/BCS_CORE_FREEZE_2026-08-29.md`

```
금지   LLM 호출 · 생성 문장 수정 · 지표 재계산 · 정본 수정
허용   형식 변환 · 레이블 통일 · 서식
```

**이 산출물은 `POST_M9_DELIVERABLE_SPEC`의 M9 게이트 산출물이 아니다.**
M9는 미실행이며, 파일명(`_bcs_aar.hwpx`)과 본문에서 분리해 표시한다.

한글(HWP) COM이 있는 로컬에서만 돈다. Markdown은 어디서나 나온다.

사용:
    python scripts/bcs_hwpx.py --source runs/bcs/bcs_v0_reparsed/wonyi_geoje.json
    python scripts/bcs_hwpx.py --source ... --md-only
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import bcs as B                                                     # noqa: E402
import bcs_present as P                                             # noqa: E402
import common                                                       # noqa: E402

SIZE = {"h1": 16, "h2": 13, "label": 11, "para": 11, "bullets": 11}


def write_hwpx(blocks: list, out: Path, title: str) -> None:
    from pyhwpx import Hwp
    hwp = Hwp(visible=False, new=True)
    try:
        def para(text: str, size: int, bold: bool) -> None:
            hwp.set_font(Height=size, Bold=bold)
            hwp.insert_text(text)
            hwp.BreakPara()

        para(title, 18, True)
        para("", 11, False)
        for b in blocks:
            k = b["kind"]
            if k == "bullets":
                for x in b["items"]:
                    para(f"· {x}", SIZE[k], False)
                para("", 11, False)
            else:
                para(b["text"], SIZE[k], k in ("h1", "h2", "label"))
                if k in ("h1", "h2"):
                    para("", 11, False)
        out.parent.mkdir(parents=True, exist_ok=True)
        if not hwp.save_as(str(out), format="HWPX"):
            raise SystemExit(f"HWPX 저장 실패: {out}")
    finally:
        hwp.quit()


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--md-only", action="store_true")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    seg_len = cfg["seg_len_sec"]

    sp = Path(a.source)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    vid = doc["video_id"]
    segs = None
    wpath = Path(common.work_dir(cfg, vid)) / "segments.json"
    if wpath.exists():
        segs = B.sanitize_stt(common.load_segments(
            wpath, require=["subtitle", "caption"], seg_len=seg_len)["segments"])

    blocks = P.sections(doc, segs, seg_len)
    out = Path(a.out) if a.out else sp.parent / f"{vid}_bcs_aar.hwpx"
    md = out.with_suffix(".md")
    md.parent.mkdir(parents=True, exist_ok=True)
    title = f"{vid} — 구간별 기록 (제품 prototype)"
    md.write_text(f"{title}\n\n" + P.to_markdown(blocks), encoding="utf-8")
    print(f"Markdown: {md}")

    if a.md_only:
        print("HWPX 생략 (--md-only)")
        return 0
    write_hwpx(blocks, out, title)
    print(f"HWPX: {out}  ({out.stat().st_size:,} bytes)")
    print("표현 계층 — LLM 미사용 · 생성 문장 무수정 · M9 산출물 아님")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
