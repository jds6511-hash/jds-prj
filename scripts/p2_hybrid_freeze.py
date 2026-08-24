"""hybrid 전환 시점 동결 — **사람만으로 작성한 분량이 여기까지였다는 기록.**

AI-first / human-adjudicated 프로토콜로 넘어가기 직전 상태를 찍는다. 나중에
"어디까지가 human-only였나"를 산출물로 답할 수 있어야 한다.

```
기록   작업 CSV sha256 · 완료 건수 · 완료 query_id 목록 · 활성 설계 sha256 ·
       keep-mask sha256 · 시트 manifest sha256 · commit · timestamp ·
       retrieval·evaluation 미실행 = true
```

**완료분의 text·gt_start·gt_end 내용은 기록하지 않는다.** 이 파일이 AI 프롬프트
설계·few-shot·품질 튜닝의 입력이 되면 human-only 분량이 AI 초안에 새어 들어간다.
query_id만 남긴다 — 그것으로 provenance는 충분하다.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_active_design as ACTIVE                                  # noqa: E402
import p2_gt_freeze as PREGT                                       # noqa: E402
import p2_label_intake as INTAKE                                   # noqa: E402

OUT = ROOT / "docs" / "probes" / "_scratch" / \
    "p2_gt_hybrid_transition_freeze.json"
HUMAN = ("text", "gt_start", "gt_end")


class HybridFreezeError(RuntimeError):
    pass


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _rel(p: Path) -> str:
    """저장소 밖(테스트 tmp) 경로면 절대경로 그대로 남긴다."""
    try:
        return str(Path(p).relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _git(*args) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                           text=True)
        return r.stdout.strip()
    except Exception:
        return ""


def completed_ids(path=None) -> list:
    """세 칸이 다 찬 행의 query_id. **내용은 반환하지 않는다.**"""
    path = Path(path) if path is not None else INTAKE.CSV_PATH
    rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    return [(r.get("query_id") or "").strip() for r in rows
            if all((r.get(c) or "").strip() for c in HUMAN)]


def freeze(intake=None, sheets_dir=None, at: str = None) -> dict:
    """전환 시점 상태를 찍는다. 라벨 내용은 담지 않는다."""
    intake = Path(intake) if intake is not None else INTAKE.CSV_PATH
    sheets_dir = Path(sheets_dir) if sheets_dir is not None else PREGT.SHEETS
    if not intake.is_file():
        raise HybridFreezeError(f"작업 CSV가 없다: {intake}")
    design = ACTIVE.load(allocation=INTAKE.load_allocation())
    rows = list(csv.DictReader(intake.read_text(encoding="utf-8-sig")
                              .splitlines()))
    if len(rows) != design["total_queries"]:
        raise HybridFreezeError(f"작업 CSV가 {len(rows)}행이다 — 활성 설계는 "
                                f"{design['total_queries']}행이다. 축소 적용 전이거나 "
                                "다른 파일이다")
    ids = [(r.get("query_id") or "").strip() for r in rows]
    if set(ids) != set(design["kept_query_ids"]):
        raise HybridFreezeError("작업 CSV의 query_id가 동결 mask와 다르다")
    done = completed_ids(intake)
    if at is None:
        import datetime
        at = datetime.datetime.now().isoformat(timespec="seconds")
    return {
        "probe": "p2_gt_hybrid_transition_freeze",
        "purpose": ("AI-first / human-adjudicated 전환 직전 상태. 여기까지가 "
                    "human-only 분량이다"),
        "frozen_at": at,
        "commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "active_design": {
            "file": "docs/P2_활성설계_2026-08-24.json",
            "sha256": _sha256_file(ROOT / "docs" / "P2_활성설계_2026-08-24.json"),
            "design": design["design"], "total_queries": design["total_queries"],
            "queries_per_video": design["queries_per_video"],
            "quota": design["quota"],
            "keep_mask": design["keep_mask"],
            "keep_mask_sha256": design["keep_mask_sha256"]},
        "intake": {"file": _rel(intake), "sha256": _sha256_file(intake),
                   "n_rows": len(rows)},
        "archive": {
            "file": "label_kit/p2/p2_label_intake_315_archive.csv",
            "sha256": _sha256_file(
                ROOT / "label_kit" / "p2" / "p2_label_intake_315_archive.csv")},
        "dropped_audit": {
            "file": "label_kit/p2/p2_dropped_audit.csv",
            "sha256": _sha256_file(
                ROOT / "label_kit" / "p2" / "p2_dropped_audit.csv")},
        "contact_sheets": PREGT.sheet_manifest(sheets_dir),
        "human_only": {"n_completed": len(done), "query_ids": sorted(done),
                       "label_content_recorded": False,
                       "note": ("내용을 담지 않는다 — 이 파일이 AI 프롬프트·few-shot "
                                "입력이 되면 human-only 분량이 초안에 새어 든다")},
        "pre_gt_freeze_ref": {
            "file": "docs/probes/_scratch/p2_gt_freeze.json",
            "note": ("작성 시작 전 빈 315행 상태의 provenance다. 현재 175행 CSV와 "
                     "해시가 같아야 한다고 검사하면 안 된다 — 두 상태를 잇는 것은 "
                     "amendment + 동결 keep-mask다")},
        "outcome_access": {"p2_retrieval_run": False, "p2_evaluate_run": False,
                           "arm_output_opened": False,
                           "caption_opened": False,
                           "retrieval_metric_computed": False},
    }


def main():
    ap = argparse.ArgumentParser(
        description="hybrid 전환 직전 상태 동결 — 라벨 내용은 담지 않는다")
    ap.add_argument("--intake", default=None)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    r = freeze(intake=a.intake)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"human_only {r['human_only']['n_completed']}건 · intake "
          f"{r['intake']['sha256'][:16]} · 시트 manifest "
          f"{r['contact_sheets']['manifest_sha256'][:16]} -> {a.out}")


if __name__ == "__main__":
    main()
