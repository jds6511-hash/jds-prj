"""정답 사건 목록(event inventory) 작성 도구 — 규격·검증·동결.

사전등록: `docs/preregistration/event_inventory_사전등록_2026-08-18.md`(작성 전 커밋).

**왜 이 도구가 필요한가.** M8의 `event coverage`를 재려면 분모가 있어야 하는데,
그 분모를 M8 자신의 출력으로 두면 자기참조다. 사람이 쓴 목록이 필요하고, 그 목록이
**M8 출력을 보기 전에** 만들어져야 한다.

**오염 경계를 코드로 강제한다.**
  - 화면에 나가는 것: 원본 영상·시각·탐색용 스토리보드(프레임+시각)뿐이다.
    캡션·자막·M8 출력·검색 결과는 이 도구가 **읽지도 않는다.**
  - `--freeze` 전에는 `load_reference`가 목록을 돌려주지 않는다.
  - 동결 후 CSV를 고치면 해시 불일치로 걸린다.

**사람은 seg 번호를 쓰지 않는다.** 초만 적고 span은 `derive_gt_seg_idx`가 파생한다 —
검색 라벨의 `gt_seg_idx`와 같은 규칙이다. 이 한 함수만 가져오는 것은
`scripts/label_intake.py`(CLAUDE.md 3조가 허용 도구로 명시)와 같은 선례다.
`evaluate`·`search`는 부르지 않는다.

사용:
    python scripts/event_inventory_kit.py init      --video-id VID
    python scripts/event_inventory_kit.py storyboard --video-id VID
    python scripts/event_inventory_kit.py validate  --video-id VID
    python scripts/event_inventory_kit.py freeze    --video-id VID
"""
import argparse, csv, hashlib, io, json, subprocess, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402
from m6_evaluate import derive_gt_seg_idx                  # noqa: E402

OUT = ROOT / "label_kit" / "event_inventory"
HEADER = ["start_sec", "end_sec", "event", "unclear"]
COLS, THUMB_W, PAD, LABEL_H, PER_SHEET = 6, 260, 8, 22, 60


class InventoryError(RuntimeError):
    pass


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def read_csv_text(path) -> str:
    """**한국어 Windows Excel은 CSV를 cp949로 저장한다.** utf-8 고정이면 한글이
    들어간 순간 UnicodeDecodeError로 터진다(2026-08-18 실측). BOM도 함께 처리한다."""
    b = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    raise InventoryError(f"{path}: utf-8/cp949 어느 쪽으로도 못 읽는다")


def parse_rows(text: str) -> list:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if not any((r.get(k) or "").strip() for k in HEADER):
            continue
        # Excel이 붙인 이름 없는 여분 열. 값이 들어 있으면 **조용히 버리지 않는다** —
        # 사용자가 뭔가 적었는데 파싱이 무시하는 상황이다(validate가 잡는다).
        extra = [str(x) for x in (r.get(None) or []) if str(x).strip()]
        extra += [v for k, v in r.items()
                  if k is not None and k not in HEADER and (v or "").strip()]
        rows.append({"start_sec": float(r["start_sec"] or 0),
                     "end_sec": float(r["end_sec"] or 0),
                     "event": (r["event"] or "").strip(),
                     "unclear": (r.get("unclear") or "").strip() in ("1", "true", "y"),
                     "extra": extra})
    return rows


def validate(rows: list, duration_sec: float, seg_len: int) -> list:
    """V1~V4만 거부 사유다. 겹침(V5)·unclear(V6)는 기록만 한다 — 동시에 일어나는
    별개 사건은 정상이고, 판단 불가를 억지로 채우게 만들면 목록이 오염된다."""
    errs = []
    for i, r in enumerate(rows, 1):
        if r["start_sec"] >= r["end_sec"]:
            errs.append(f"{i}행 V1: start_sec({r['start_sec']}) >= end_sec({r['end_sec']})")
        if r["start_sec"] < 0 or r["end_sec"] > duration_sec:
            errs.append(f"{i}행 V2: 영상 길이({duration_sec}초) 밖 — "
                        f"{r['start_sec']}~{r['end_sec']}")
        if not r["event"]:
            errs.append(f"{i}행 V3: event 이름이 비어 있다")
        if r.get("extra"):
            errs.append(f"{i}행 V3b: 여분 열에 값이 있다 {r['extra']} — "
                        f"파싱이 버리는 자리다. 의도한 값이면 제 열로 옮기고, "
                        f"아니면 지워라")
    return errs


def to_reference(rows: list, n_segments: int, seg_len: int) -> list:
    """`unclear`는 제외한다(수는 summarize가 보고). span은 코드가 파생한다."""
    out = []
    for r in rows:
        if r["unclear"]:
            continue
        idx = derive_gt_seg_idx(r["start_sec"], r["end_sec"], n_segments, seg_len)
        out.append({"event": r["event"], "start_sec": r["start_sec"],
                    "end_sec": r["end_sec"], "span": [min(idx), max(idx)],
                    "seg_idx": idx})
    return sorted(out, key=lambda e: (e["span"][0], e["event"]))


def summarize(rows: list, n_segments: int, seg_len: int) -> dict:
    ref = to_reference(rows, n_segments, seg_len)
    sp = [e["span"] for e in ref]
    return {"events": len(ref), "unclear": sum(1 for r in rows if r["unclear"]),
            "overlap_pairs": sum(1 for i in range(len(sp)) for j in range(i + 1, len(sp))
                                 if min(sp[i][1], sp[j][1]) >= max(sp[i][0], sp[j][0])),
            "span_len_dist": [s[1] - s[0] + 1 for s in sp],
            "total_seconds": round(sum(e["end_sec"] - e["start_sec"] for e in ref), 2)}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_path(video_id: str, out_dir=None) -> Path:
    return Path(out_dir or OUT) / f"FROZEN_{video_id}.json"


def freeze(csv_path, video_id: str, duration_sec: float, n_segments: int,
           seg_len: int, out_dir=None) -> Path:
    """검증 통과분만 동결한다. **여기서만** 목록이 읽기 가능해진다."""
    csv_path = Path(csv_path)
    rows = parse_rows(read_csv_text(csv_path))
    errs = validate(rows, duration_sec, seg_len)
    if errs:
        raise InventoryError("검증 실패 — 동결하지 않는다:\n  " + "\n  ".join(errs))
    p = frozen_path(video_id, out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"video_id": video_id, "prereg": "docs/preregistration/"
                                         "event_inventory_사전등록_2026-08-18.md",
         "sha256": _sha(csv_path), "csv": csv_path.name,
         "git_head": _git("rev-parse", "HEAD"),
         "frozen_at": datetime.datetime.now().isoformat(timespec="seconds"),
         "duration_sec": duration_sec, "n_segments": n_segments, "seg_len": seg_len,
         "summary": summarize(rows, n_segments, seg_len),
         "events": to_reference(rows, n_segments, seg_len)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_reference(video_id: str, out_dir=None, csv_path=None) -> list:
    """**오염 경계.** 동결 전에는 목록을 돌려주지 않는다 — 사람이 M8 출력을 보기
    전에 목록이 확정돼 있어야 한다(사전등록 §0). 동결 후 CSV를 고쳤으면 해시로 걸린다."""
    p = frozen_path(video_id, out_dir)
    if not p.is_file():
        raise InventoryError(
            f"{video_id}의 사건 목록이 **동결되지 않았다** — `freeze`를 먼저 하라. "
            f"동결 전 열람은 분모 오염이다")
    d = json.loads(p.read_text(encoding="utf-8"))
    if csv_path and Path(csv_path).is_file() and _sha(Path(csv_path)) != d["sha256"]:
        raise InventoryError(
            f"{video_id}: 동결 이후 CSV가 바뀌었다(해시 불일치). 사유를 기록하고 "
            f"다시 동결하라 — 조용히 덮어쓰지 마라")
    return d["events"]


def storyboard(video_id: str, cfg) -> list:
    """**탐색용** 스토리보드. 프레임과 시각만 넣는다 — 캡션·자막은 넣지 않는다.
    경계는 이 시트가 아니라 **영상을 재생하며** 정한다(정지 프레임으로는 못 잡는다)."""
    from PIL import Image, ImageDraw
    wdir = Path(common.work_dir(cfg, video_id))
    doc = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
    segs = doc["segments"]
    d = OUT / video_id
    d.mkdir(parents=True, exist_ok=True)
    made = []
    for page, i0 in enumerate(range(0, len(segs), PER_SHEET), 1):
        chunk = segs[i0:i0 + PER_SHEET]
        rows = (len(chunk) + COLS - 1) // COLS
        first = Image.open(wdir / chunk[0]["rep_frame"])
        th = int(THUMB_W * first.height / first.width)
        cell = th + LABEL_H
        sheet = Image.new("RGB", (COLS * (THUMB_W + PAD) + PAD,
                                  rows * (cell + PAD) + PAD), "white")
        draw = ImageDraw.Draw(sheet)
        for k, s in enumerate(chunk):
            x = PAD + (k % COLS) * (THUMB_W + PAD)
            y = PAD + (k // COLS) * (cell + PAD)
            sheet.paste(Image.open(wdir / s["rep_frame"]).convert("RGB")
                        .resize((THUMB_W, th)), (x, y))
            t = int(s["start"])
            draw.text((x + 2, y + th + 4), f"{t // 60}:{t % 60:02d}  ({t}s)",
                      fill="black")
        p = d / f"storyboard_{page:02d}.jpg"
        sheet.save(p, quality=88)
        made.append(p)
    return made


def _video_facts(cfg, video_id: str) -> tuple:
    doc = json.loads((Path(common.work_dir(cfg, video_id)) / "segments.json")
                     .read_text(encoding="utf-8"))
    return float(doc["duration_sec"]), int(doc["n_segments"])


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["init", "storyboard", "validate", "freeze"])
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    dur, nseg = _video_facts(cfg, a.video_id)
    seg_len = cfg["seg_len_sec"]
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{a.video_id}.csv"

    if a.stage == "init":
        if f.exists():
            print(f"이미 있다: {f} — 덮어쓰지 않는다")
        else:
            f.write_text(",".join(HEADER) + "\n", encoding="utf-8")
            print(f"생성: {f}")
        print(f"영상 길이 {dur:.1f}초 · 구간 {nseg}개 · seg_len {seg_len}초")
        print("초만 적어라. seg 번호는 코드가 파생한다.")
        print("**이 영상의 M8 출력을 동결 전에 열지 마라** (사전등록 §0)")
        return 0

    if a.stage == "storyboard":
        made = storyboard(a.video_id, cfg)
        print(f"스토리보드 {len(made)}장: {OUT / a.video_id}")
        print("탐색용이다 — 경계는 영상을 재생하며 정한다")
        return 0

    rows = parse_rows(read_csv_text(f))
    errs = validate(rows, dur, seg_len)
    s = summarize(rows, nseg, seg_len)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    if errs:
        print("검증 실패:\n  " + "\n  ".join(errs))
        return 1
    print("검증 통과")
    if a.stage == "freeze":
        p = freeze(f, a.video_id, dur, nseg, seg_len)
        print(f"동결: {p}\n이 시점 이후에만 M8 출력을 열람한다")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InventoryError as e:
        print(f"차단: {e}", file=sys.stderr)
        sys.exit(2)
