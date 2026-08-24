"""P2 annotation HOLD 동결 — **비용 때문에 멈춘 지점을 증명하는 기록.**

P2는 실패한 실험이 아니다. 표집·색인·프로토콜 준비는 끝났고 GT 작성이 라벨 비용
때문에 중단됐다. 그래서 이 산출물이 답해야 하는 질문은 두 개다.

```
어디까지 했나   활성 설계 · 완료 건수 · 완료 query_id · 관련 파일 sha256 전부
무엇을 안 봤나   retrieval·evaluate 미실행 · arm 산출물 미열람 · 지표 미계산
```

**라벨 내용(text·gt_start·gt_end)은 담지 않는다.** 이 파일이 나중에 AI 초안 프롬프트나
few-shot의 입력이 되면 사람이 쓴 분량이 초안으로 새어 든다. query_id만으로 provenance는
충분하다. 초안 생성 여부도 **디스크 상태에서 읽는다** — false를 손으로 박으면 그건
증거가 아니라 주장이다.

재현:
  python scripts/p2_annotation_hold.py
"""
import argparse
import csv
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_active_design as ACTIVE                                  # noqa: E402
import p2_adjudication as ADJ                                      # noqa: E402
import p2_ai_draft as DRAFT                                        # noqa: E402
import p2_gt_freeze as PREGT                                       # noqa: E402
import p2_label_intake as INTAKE                                   # noqa: E402

OUT = ROOT / "docs" / "probes" / "_scratch" / \
    "p2_annotation_hold_2026-08-24.json"
KIT = ROOT / "label_kit" / "p2"
ARCHIVE = KIT / "p2_label_intake_315_archive.csv"
DROPPED = KIT / "p2_dropped_audit.csv"
HANDOFF_CSV = ROOT / "label_kit" / "p2_ai_assist" / "handoff" / \
    "p2_scene_rows_for_ai.csv"
HUMAN = ("text", "gt_start", "gt_end")

# 색인 실행 정체성. run_root는 gitignore된 서버 경로이므로 로컬에서 RUN_COMPLETE의
# 해시를 재확인할 수 없다 — 그 사실을 숨기지 않고 필드로 적는다.
INDEX_RUN = {
    "run_id": "p2idx_0821d",
    "commit": "ab73e1c",
    "plan_hash_prefix": "d0bb2330e371c416",
    "mode": "FULL",
    "validator_checks_passed": 17,
    "validator_version": 2,
    "run_complete_recorded": True,
    "run_complete_locally_verifiable": False,
    "source": "docs/작업현황_2026-08-22.md §5",
    "note": ("run_root는 gitignore된 서버 경로다. RUN_COMPLETE.json은 그쪽에 있고 "
             "이 저장소에서 해시로 재확인할 수 없다 — 정체성만 기록한다"),
}

INVALIDATING_EVENTS = (
    "partial retrieval 실행",
    "arm result 열람",
    "RR/MRR 확인",
    "sample size 재변경",
    "query/type 수정",
    "175 → 315 top-up",
)


class AnnotationHoldError(RuntimeError):
    pass


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _rel(p: Path) -> str:
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


def _rows(intake: Path) -> list:
    if not intake.is_file():
        raise AnnotationHoldError(f"작업 CSV가 없다: {intake}")
    return list(csv.DictReader(
        intake.read_text(encoding="utf-8-sig").splitlines()))


def completed_ids(intake: Path) -> list:
    """세 칸이 다 찬 행의 query_id. **값은 반환하지 않는다.**"""
    return sorted((r.get("query_id") or "").strip() for r in _rows(intake)
                  if all((r.get(c) or "").strip() for c in HUMAN))


def draft_state(drafts: Path) -> dict:
    """초안 산출물 유무를 **파일에서** 읽는다. 내용은 세지 않고 행 수만 센다."""
    p = Path(drafts)
    if not p.is_file():
        return {"generated": False, "count": 0, "file": _rel(p),
                "sha256": None}
    n = sum(1 for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip())
    return {"generated": n > 0, "count": n, "file": _rel(p),
            "sha256": _sha256_file(p)}


def freeze(intake=None, archive=None, dropped=None, audit=None,
           handoff_csv=None, sheets_dir=None, drafts=None,
           at: str = None) -> dict:
    intake = Path(intake) if intake is not None else INTAKE.CSV_PATH
    archive = Path(archive) if archive is not None else ARCHIVE
    dropped = Path(dropped) if dropped is not None else DROPPED
    audit = Path(audit) if audit is not None else ADJ.AUDIT
    handoff_csv = Path(handoff_csv) if handoff_csv is not None else HANDOFF_CSV
    sheets_dir = Path(sheets_dir) if sheets_dir is not None else PREGT.SHEETS
    drafts = Path(drafts) if drafts is not None else DRAFT.DRAFTS

    design = ACTIVE.load(allocation=INTAKE.load_allocation())
    rows = _rows(intake)
    if len(rows) != design["total_queries"]:
        raise AnnotationHoldError(
            f"작업 CSV가 {len(rows)}행이다 — 활성 설계는 "
            f"{design['total_queries']}행이다. 다른 파일이거나 설계가 어긋났다")
    ids = [(r.get("query_id") or "").strip() for r in rows]
    if set(ids) != set(design["kept_query_ids"]):
        raise AnnotationHoldError("작업 CSV의 query_id가 동결 mask와 다르다")

    done = completed_ids(intake)
    ds = draft_state(drafts)
    at = at or datetime.datetime.now().isoformat(timespec="seconds")
    return {
        "probe": "p2_annotation_hold",
        "purpose": ("라벨 비용으로 GT 작성을 중단한 지점의 동결. 실패 실험이 아니고 "
                    "4B 기각도 아니다"),
        "timestamp": at,
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),

        "annotation_status": "HOLD",
        "hold_reason": "annotation_burden",
        "result_status": "unresolved",

        "active_design": design["design"],
        "fixed_n": design["fixed_n"],
        "total_queries": design["total_queries"],
        "queries_per_video": design["queries_per_video"],
        "n_videos": design["n_videos"],
        "quota": design["quota"],
        "completed_count": len(done),
        "incomplete_count": design["total_queries"] - len(done),
        "completed_query_ids": done,
        "label_content_recorded": False,
        "label_content_note": ("내용을 담지 않는다 — 이 파일이 AI 프롬프트·few-shot "
                               "입력이 되면 사람이 쓴 분량이 초안에 새어 든다"),

        "intake_file": _rel(intake),
        "intake_sha256": _sha256_file(intake),
        "active_design_file": _rel(ACTIVE.ACTIVE),
        "active_design_sha256": _sha256_file(ACTIVE.ACTIVE),
        "keep_mask_file": design["keep_mask"],
        "keep_mask_sha256": design["keep_mask_sha256"],
        "archive_315_file": _rel(archive),
        "archive_315_sha256": _sha256_file(archive),
        "dropped_audit_file": _rel(dropped),
        "dropped_audit_sha256": _sha256_file(dropped),
        "adjudication_audit_file": _rel(audit),
        "adjudication_audit_sha256": _sha256_file(audit),
        "handoff_csv_file": _rel(handoff_csv),
        "handoff_csv_sha256": _sha256_file(handoff_csv),
        "contact_sheet_manifest_sha256":
            PREGT.sheet_manifest(sheets_dir)["manifest_sha256"],

        # handoff 패키지 생성과 실제 초안 생성은 다른 사건이다
        "handoff_package_prepared": handoff_csv.is_file(),
        "ai_drafts_generated": ds["generated"],
        "ai_draft_artifact_count": ds["count"],
        "ai_draft_artifact": ds,

        "index_run": dict(INDEX_RUN),

        "outcome_access": {
            "retrieval_run": False,
            "arm_outputs_opened": False,
            "rr_mrr_computed": False,
            "p2_evaluate_run": False,
        },

        "interpretation": {
            "is_failed_experiment": False,
            "is_evidence_3b_superior": False,
            "is_evidence_rejecting_4b": False,
            "fresh_sign_evidence_produced": False,
            "partial_gt_usable_for_analysis": False,
            "statement": ("current deployment remains 3B because there is "
                          "insufficient fresh deployment-relevant evidence to "
                          "justify switching, not because 3B has been "
                          "established as universally superior"),
        },

        "resume": {
            "resumable_under_frozen_protocol": True,
            "no_outcome_based_top_up": True,
            "invalidating_events": list(INVALIDATING_EVENTS),
            "note": ("위 사건이 하나라도 발생하면 현재 P2의 continuation이 아니다 — "
                     "별도 사전등록/amendment 사건이다"),
        },

        "pre_gt_freeze_ref": {
            "file": "docs/probes/_scratch/p2_gt_freeze.json",
            "note": ("작성 시작 전 빈 315행 상태다. 현재 175행 CSV와 해시가 같아야 "
                     "한다고 검사하면 안 된다"),
        },
        "hybrid_transition_ref":
            "docs/probes/_scratch/p2_gt_hybrid_transition_freeze.json",
    }


def write(doc: dict, out=None) -> Path:
    """덮어쓰지 않는다 — 동결은 한 번이다."""
    p = Path(out) if out is not None else OUT
    if p.exists():
        raise AnnotationHoldError(
            f"이미 동결돼 있다: {p} — 덮어쓰지 않는다. 재개했다가 다시 멈췄으면 "
            "새 날짜 파일로 남겨라")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return p


def main():
    ap = argparse.ArgumentParser(
        description="P2 annotation HOLD 동결 — 라벨 내용은 담지 않는다")
    ap.add_argument("--intake", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = freeze(intake=a.intake)
    p = write(r, a.out)
    print(f"HOLD {r['completed_count']}/{r['total_queries']} · intake "
          f"{r['intake_sha256'][:16]} · drafts {r['ai_draft_artifact_count']} "
          f"-> {_rel(p)}")


if __name__ == "__main__":
    main()
