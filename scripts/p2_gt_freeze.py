"""GT 작성 **전** 입력 상태를 동결한다.

라벨을 쓰는 동안 컨택트시트가 다시 생성되거나 배정표가 바뀌면 GT의 의미가 조용히
달라진다. 나중에 "무엇을 보고 썼나"를 답할 수 있어야 하므로 작성 전에 해시를 찍는다.

```
동결 대상   빈 intake CSV · 질의 쿼터(배정) · 선정표본 · 컨택트시트 전량
기록       파일별 sha256 + 시트 manifest 해시 + 생성 commit·config·arm
거부       CSV가 이미 채워져 있으면 동결하지 않는다 (작성 전 상태가 아니다)
```

**여기서 동결하지 않는 것**: 캡션·색인·임베딩. GT 작성자는 그것을 보지 않으므로
동결 대상도 아니다. 평가 단계에서 별도로 다룬다.

재현: python scripts/p2_gt_freeze.py --out docs/probes/_scratch/p2_gt_freeze.json
"""
import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "label_kit" / "p2" / "p2_label_intake.csv"
SHEETS = ROOT / "label_kit" / "p2" / "contact_sheets"
QUOTA = ROOT / "docs" / "P2_질의쿼터_2026-08-20.json"
SELECTION = ROOT / "docs" / "P2_선정표본_2026-08-20.json"
OUT = ROOT / "docs" / "probes" / "_scratch" / "p2_gt_freeze.json"
HUMAN_COLUMNS = ("text", "gt_start", "gt_end")
# 시트를 만든 경로. 3B arm의 m2 프레임이 공통 소스이고 4B는 그것을 미러링했다 —
# 즉 두 arm이 같은 프레임을 봤고, 시트는 arm 선택과 무관하다.
SHEET_SOURCE = {"arm": "3b", "config": "config_p2_3b.yaml",
                "frames_note": ("3b arm의 m2 프레임이 공통 소스다. 4b는 "
                                "mirror_frames로 같은 프레임을 받았으므로 시트는 "
                                "arm 선택과 무관하다"),
                "tile_content": "프레임 · mm:ss-mm:ss · 세그먼트 번호뿐",
                "guard": "scripts/label_guard.py allowlist(idx·start·end·rep_frame)"}


class FreezeError(RuntimeError):
    pass


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_fact(p: Path) -> dict:
    if not p.is_file():
        raise FreezeError(f"동결 대상 파일이 없다: {p}")
    return {"path": (str(p.relative_to(ROOT)).replace("\\", "/")
                     if p.is_relative_to(ROOT) else str(p)),
            "sha256": _sha256_file(p), "bytes": p.stat().st_size}


def _assert_blank(p: Path) -> int:
    rows = list(csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines()))
    filled = [r.get("query_id") for r in rows
              if any((r.get(c) or "").strip() for c in HUMAN_COLUMNS)]
    if filled:
        raise FreezeError(
            f"intake CSV가 이미 채워져 있다({len(filled)}행, 예: {filled[:3]}) — "
            f"동결은 작성 전 상태를 찍는 것이므로 기준이 될 수 없다")
    return len(rows)


def sheet_manifest(sheets_dir: Path) -> dict:
    d = Path(sheets_dir)
    if not d.is_dir():
        raise FreezeError(f"컨택트시트 디렉터리가 없다: {d}")
    files = sorted(d.glob("*.jpg"))
    if not files:
        raise FreezeError(f"컨택트시트가 없다: {d}")
    per = {p.name: _sha256_file(p) for p in files}
    # manifest 해시 = (이름, 해시) 목록의 해시. 한 장만 바뀌어도 값이 바뀐다
    buf = io.StringIO()
    for name in sorted(per):
        buf.write(f"{name}\x1f{per[name]}\x1e")
    return {"dir": (str(d.relative_to(ROOT)).replace("\\", "/")
                    if d.is_relative_to(ROOT) else str(d)),
            "n_sheets": len(files),
            "n_videos": len({p.stem.rsplit("_p", 1)[0] for p in files}),
            "bytes": sum(p.stat().st_size for p in files),
            "manifest_sha256": _sha256_bytes(buf.getvalue().encode("utf-8")),
            "files": per}


def freeze(csv_path=CSV_PATH, sheets_dir=SHEETS, quota=QUOTA,
           selection=SELECTION) -> dict:
    csv_path = Path(csv_path)
    n_rows = _assert_blank(csv_path)
    return {
        "artifact": "p2_gt_freeze",
        "stage": "before_labeling",
        "why": ("라벨 작성 중 입력물이 바뀌었는지 나중에 확인할 기준을 남긴다"),
        "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                 capture_output=True,
                                 encoding="utf-8").stdout.strip(),
        "inputs": {"intake_csv": {**_file_fact(csv_path), "n_rows": n_rows,
                                  "human_columns_blank": True},
                   "quota": _file_fact(Path(quota)),
                   "selection": _file_fact(Path(selection)),
                   "contact_sheets": sheet_manifest(sheets_dir)},
        "contact_sheet_source": dict(SHEET_SOURCE),
        "not_frozen_here": ("caption · 색인 · 임베딩 — GT 작성자가 보지 않으므로 "
                            "동결 대상이 아니다. 평가 단계에서 별도로 다룬다"),
        "burned_in_text_note": ("시트의 프레임에 보이는 글자는 영상 자체에 박힌 "
                                "자막·그래픽이다. 파이프라인 STT·캡션 산출물이 "
                                "아니며, 영상을 보면 어차피 보이는 원본 증거다"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    r = freeze()
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    i = r["inputs"]
    print(f"{p}")
    print(f"  intake  {i['intake_csv']['n_rows']}행 빈 상태 "
          f"{i['intake_csv']['sha256'][:16]}")
    print(f"  quota   {i['quota']['sha256'][:16]}")
    print(f"  sample  {i['selection']['sha256'][:16]}")
    cs = i["contact_sheets"]
    print(f"  sheets  {cs['n_videos']}편 {cs['n_sheets']}장 "
          f"manifest {cs['manifest_sha256'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
