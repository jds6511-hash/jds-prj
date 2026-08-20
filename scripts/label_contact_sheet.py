"""신규 test 영상 라벨링용 프레임 컨택트시트 생성.

**왜 필요한가.** 라벨은 프레임 실물만 보고 만들어야 한다(절대규칙 3). 그런데 영상을
스크럽하며 장면을 찾으면 시간이 오래 걸리고, 웹 UI를 쓰면 검색 결과가 보여서 규칙을
어기게 된다. 대표 프레임을 타임스탬프와 함께 격자로 깔아 두면 **눈으로 훑어 후보
구간을 고르고 그 시각만 적으면 된다.**

**시트에 캡션·자막을 넣지 않는다.** 넣는 순간 "캡션을 보고 라벨을 쓴" 것이 되어
시스템이 자기 답안을 채점하게 된다. 들어가는 것은 **프레임 이미지와 시각뿐**이다.

세그먼트가 5초 격자이므로 대표 프레임 한 장이 5초를 대표한다. 시트에서 고른 시각을
gt_start/gt_end로 적되, **최종 확인은 반드시 영상 실물로** 한다 — 대표 프레임은
구간의 한 시점일 뿐이라 경계가 정확하지 않다.

work/·results/·config 불변. 읽기 전용.
재현: python scripts/label_contact_sheet.py --video jissi_farm
      python scripts/label_contact_sheet.py --all
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import label_guard

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402

OUT = ROOT / "label_kit" / "contact_sheets"
COLS, THUMB_W, PAD, LABEL_H = 6, 320, 8, 22
PER_SHEET = 60          # 시트당 세그먼트 수 — 한 화면에 들어오는 상한


def mmss(sec: float) -> str:
    s = int(sec)
    return f"{s // 60}:{s % 60:02d}"


def build(video_id: str, cfg) -> list[Path]:
    wdir = Path(common.work_dir(cfg, video_id))
    # **캡션·자막을 메모리에 들이지 않는다.** 같은 파일에 들어 있으므로
    # allowlist 로더를 거친다 (기확보 영상에는 캡션이 이미 존재한다)
    doc = label_guard.load_segments_for_labeling(wdir / "segments.json")
    segs = doc["segments"]
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for page, i0 in enumerate(range(0, len(segs), PER_SHEET), 1):
        chunk = segs[i0:i0 + PER_SHEET]
        rows = (len(chunk) + COLS - 1) // COLS
        first = Image.open(wdir / chunk[0]["rep_frame"])
        th = int(THUMB_W * first.height / first.width)
        cell_h = th + LABEL_H
        sheet = Image.new("RGB", (COLS * (THUMB_W + PAD) + PAD,
                                  rows * (cell_h + PAD) + PAD), "white")
        draw = ImageDraw.Draw(sheet)
        for k, s in enumerate(chunk):
            x = PAD + (k % COLS) * (THUMB_W + PAD)
            y = PAD + (k // COLS) * (cell_h + PAD)
            im = Image.open(wdir / s["rep_frame"]).convert("RGB").resize((THUMB_W, th))
            sheet.paste(im, (x, y))
            # 시각과 세그먼트 번호만 적는다 — 캡션·자막은 넣지 않는다(위 docstring)
            draw.text((x + 2, y + th + 4),
                      f"{mmss(s['start'])}-{mmss(s['end'])}  #{s['idx']}", fill="black")
        p = OUT / f"{video_id}_p{page:02d}.jpg"
        sheet.save(p, quality=88)
        made.append(p)
        print(f"  {p.name}  세그먼트 {chunk[0]['idx']}~{chunk[-1]['idx']}", flush=True)
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video")
    ap.add_argument("--all", action="store_true",
                    help="신규 test 후보 3편 전부")
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    vids = (["jissi_farm", "softyeon_ceramics", "baekmansonghee_jirisan"]
            if a.all else [a.video])
    if not vids or vids == [None]:
        ap.error("--video 또는 --all 이 필요하다")
    for v in vids:
        print(f"[{v}]", flush=True)
        build(v, cfg)
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
