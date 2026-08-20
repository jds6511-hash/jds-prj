"""P2 입력 경로의 영상이 **검증한 그 바이트인지** 실행 직전에 다시 확인한다.

`p2_promote.py`가 로컬에서 승격했고, 그 파일이 서버로 옮겨졌다. 옮기는 동안 잘린
파일은 cv2가 열어버리고 duration까지 돌려주므로(2026-08-20 staging에서 실측한 결함),
**FULL 직전에 서버에서 다시 해시를 계산하는 것**이 유일한 방어다.

```
신규 31편   selected list의 file_sha256과 완전 일치해야 한다
기확보 4편  출처 해시가 없다(legacy_exempt) — 존재·크기만 확인하고 해시는 기록만 한다
```

**하나라도 어긋나면 exit 1.** 그 상태로 20시간 배치를 시작하지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import provenance as PV                                           # noqa: E402

SELECTED_REL = "docs/P2_선정표본_2026-08-20.json"


def verify(selected: list, videos_dir) -> dict:
    d = Path(videos_dir)
    rows, problems = [], []
    matched = legacy = 0
    for r in selected:
        vid = r["source_id"]
        f = d / f"{vid}.mp4"
        row = {"video_id": vid, "pre_indexed": bool(r.get("pre_indexed")),
               "present": f.is_file(), "size": None, "sha256": None,
               "status": None}
        if not f.is_file():
            row["status"] = "MISSING"
            problems.append(f"{vid}: 입력 경로에 없다 — {f}")
            rows.append(row)
            continue
        row["size"] = f.stat().st_size
        row["sha256"] = PV.sha256_file(f)
        if row["pre_indexed"]:
            # 출처 해시가 없는 기존 영상 — 기록만 한다(추측해서 채우지 않는다)
            row["status"] = "legacy_recorded"
            legacy += 1
        elif row["sha256"] == r.get("file_sha256"):
            row["status"] = "match"
            matched += 1
        else:
            row["status"] = "MISMATCH"
            problems.append(
                f"{vid}: sha256 불일치 — 실제 {row['sha256'][:12]} vs 등록 "
                f"{str(r.get('file_sha256'))[:12]}. 검증한 바이트가 아니다")
        rows.append(row)
    return {"n_selected": len(selected), "matched": matched,
            "legacy_recorded": legacy,
            "missing": sum(1 for x in rows if x["status"] == "MISSING"),
            "mismatched": sum(1 for x in rows if x["status"] == "MISMATCH"),
            "problems": problems, "ok": not problems, "rows": rows,
            "note": ("기확보 4편은 출처 해시가 없어 대조 대상이 아니다 — "
                     "해시를 기록만 한다")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", default=SELECTED_REL)
    ap.add_argument("--videos", default="data/videos")
    ap.add_argument("--out")
    a = ap.parse_args()
    sel = json.loads((ROOT / a.selected).read_text(encoding="utf-8"))["selected"]
    r = verify(sel, ROOT / a.videos)
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"selected: {r['n_selected']}  sha256 match: {r['matched']}  "
          f"legacy: {r['legacy_recorded']}  missing: {r['missing']}  "
          f"mismatch: {r['mismatched']}  ok: {r['ok']}")
    for p in r["problems"][:10]:
        print(f"  PROBLEM: {p}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
