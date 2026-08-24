"""활성 설계 적용 — **원본 315를 보존하고 동결 mask에서 파생한다.**

2026-08-24 amendment(35영상 × 5 = 175)를 작업 파일에 반영한다.

```
보존   원본 315행 CSV를 archive로 **복사**한다. 삭제·수정하지 않는다
파생   동결 keep-mask가 유지하는 175행만 작업 CSV로 만든다
audit  drop된 140행은 지우지 않고 audit CSV로 남긴다. 작성분은 작성분으로 표시
불변   query_id 재번호 없음 · 새 질의 없음 · 사람 입력 칸은 그대로 복사
```

**역사를 없애지 않는 것이 이 스크립트의 목적이다.** 이미 작성된 행이 분석 대상에서
빠지더라도 그 사실 자체가 기록이다 — 나중에 "왜 이 질의는 없나"를 답할 수 있어야 한다.

`--dry-run`이 기본이 아니다. 대신 archive가 이미 있으면 거부한다 — 두 번 적용해서
축소본을 원본으로 착각하는 경로를 막는다.
"""
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_active_design as ACTIVE                                  # noqa: E402
import p2_label_intake as INTAKE                                   # noqa: E402

ARCHIVE_NAME = "p2_label_intake_315_archive.csv"
AUDIT_NAME = "p2_dropped_audit.csv"
STATUS_WRITTEN = "written_not_in_analysis"
STATUS_BLANK = "blank_not_in_analysis"
AUDIT_COLUMNS = tuple(INTAKE.COLUMNS) + ("status",)
HUMAN = ("text", "gt_start", "gt_end")


class ApplyError(RuntimeError):
    pass


def _read(path) -> list:
    return list(csv.DictReader(Path(path).read_text(encoding="utf-8-sig")
                               .splitlines()))


def _write(path, rows: list, columns) -> Path:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(columns))
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)
    return path


def _written(row: dict) -> bool:
    return all((row.get(c) or "").strip() for c in HUMAN)


def apply(source, out_dir=None, dry_run: bool = False) -> dict:
    """축소 작업 파일과 audit 파일을 만든다. 원본은 손대지 않는다."""
    source = Path(source)
    out_dir = Path(out_dir) if out_dir is not None else source.parent
    archive, audit = out_dir / ARCHIVE_NAME, out_dir / AUDIT_NAME
    if archive.exists() and not dry_run:
        raise ApplyError(f"archive가 이미 있다: {archive} — 두 번 적용하면 축소본이 "
                         "원본으로 기록된다. 먼저 상태를 확인해라")

    frozen = INTAKE.load_allocation()
    design = ACTIVE.load(allocation=frozen)
    by_id = {r["query_id"]: r for r in frozen}
    rows = _read(source)
    if len(rows) != design["frozen_allocation_total"]:
        raise ApplyError(f"원본이 {len(rows)}행이다 — 적용은 동결 배정표 "
                         f"{design['frozen_allocation_total']}행 상태에서만 한다")
    seen = set()
    for r in rows:
        qid = (r.get("query_id") or "").strip()
        a = by_id.get(qid)
        if a is None:
            raise ApplyError(f"{qid}: 동결 배정표에 없다")
        if qid in seen:
            raise ApplyError(f"{qid}: query_id 중복")
        seen.add(qid)
        if (r.get("video_id") or "").strip() != a["video_id"]:
            raise ApplyError(f"{qid}: video_id가 배정과 다르다")
        if (r.get("query_type") or "").strip() != a["query_type"]:
            raise ApplyError(f"{qid}: query_type이 배정과 다르다 — 유형은 동결이다")

    kept = set(design["kept_query_ids"])
    order = {q: i for i, q in enumerate(design["kept_query_ids"])}
    by_row = {(r.get("query_id") or "").strip(): r for r in rows}
    working_rows = [{c: (by_row[q].get(c) or "") for c in INTAKE.COLUMNS}
                    for q in sorted(kept, key=lambda q: order[q])]
    dropped_rows, dropped_written = [], 0
    for r in rows:
        qid = (r.get("query_id") or "").strip()
        if qid in kept:
            continue
        was = _written(r)
        dropped_written += int(was)
        dropped_rows.append({**{c: (r.get(c) or "") for c in INTAKE.COLUMNS},
                             "status": STATUS_WRITTEN if was else STATUS_BLANK})

    result = {"dry_run": dry_run, "design": design["design"],
              "frozen_total": len(rows), "kept": len(working_rows),
              "dropped": len(dropped_rows), "dropped_written": dropped_written,
              "kept_written": sum(1 for r in working_rows if _written(r)),
              "keep_mask_sha256": design["keep_mask_sha256"],
              "archive": str(archive), "working": str(source),
              "audit": str(audit)}
    if dry_run:
        return result
    shutil.copy2(source, archive)
    _write(audit, dropped_rows, AUDIT_COLUMNS)
    _write(source, working_rows, INTAKE.COLUMNS)
    return result


def main():
    ap = argparse.ArgumentParser(
        description="활성 설계를 작업 CSV에 반영 — 원본은 archive로 보존한다")
    ap.add_argument("--source", default=str(INTAKE.CSV_PATH))
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    r = apply(a.source, out_dir=a.out_dir, dry_run=a.dry_run)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
