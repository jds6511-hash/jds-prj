"""P2 annotation HOLD 동결 — 계약 테스트.

동결의 목적은 "여기서 멈췄고, 결과는 한 번도 열지 않았다"를 산출물로 증명하는 것이다.
따라서 지켜야 하는 것은 두 가지다 — **라벨 내용을 복제하지 않는다**, 그리고
**초안 생성 여부를 실제 디스크 상태에서 읽는다**(하드코딩 false 금지).
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import p2_active_design as ACTIVE          # noqa: E402
import p2_annotation_hold as H             # noqa: E402
import p2_label_intake as INTAKE           # noqa: E402

SENTINEL_TEXT = "SENTINEL사람이쓴질의문장"
COLUMNS = ("query_id", "video_id", "query_type", "text", "gt_start", "gt_end",
           "note")


@pytest.fixture(scope="module")
def design():
    return ACTIVE.load(allocation=INTAKE.load_allocation())


def _write_csv(path: Path, design: dict, n_done: int) -> None:
    """동결 mask 순서 그대로 쓰고 앞 n_done행만 채운다."""
    by_id = {r["query_id"]: r for r in INTAKE.load_allocation()}
    rows = []
    for i, qid in enumerate(design["kept_query_ids"]):
        src = by_id[qid]
        done = i < n_done
        rows.append({
            "query_id": qid, "video_id": src["video_id"],
            "query_type": src["query_type"],
            "text": f"{SENTINEL_TEXT}{i}" if done else "",
            "gt_start": "12.5" if done else "",
            "gt_end": "34.5" if done else "", "note": ""})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def kit(tmp_path, design):
    """freeze가 읽는 파일 일체를 tmp에 만든다."""
    d = tmp_path / "kit"
    intake = d / "p2_label_intake.csv"
    _write_csv(intake, design, n_done=3)
    (d / "archive.csv").write_text("query_id\nx\n", encoding="utf-8")
    (d / "dropped.csv").write_text("query_id\ny\n", encoding="utf-8")
    (d / "audit.csv").write_text("query_id,label_origin\nz,human_only\n",
                                 encoding="utf-8")
    (d / "handoff.csv").write_text("query_id,video_id,query_type\n",
                                   encoding="utf-8")
    sheets = d / "sheets"
    sheets.mkdir()
    (sheets / "vid_p01.jpg").write_bytes(b"\xff\xd8jpg")
    return {"intake": intake, "archive": d / "archive.csv",
            "dropped": d / "dropped.csv", "audit": d / "audit.csv",
            "handoff_csv": d / "handoff.csv", "sheets": sheets,
            "drafts": d / "p2_ai_drafts.jsonl"}


def _freeze(kit, **kw):
    return H.freeze(intake=kit["intake"], archive=kit["archive"],
                    dropped=kit["dropped"], audit=kit["audit"],
                    handoff_csv=kit["handoff_csv"], sheets_dir=kit["sheets"],
                    drafts=kit["drafts"], at="2026-08-24T00:00:00", **kw)


# ---- 필수 필드 ------------------------------------------------------------

def test_required_fields_present(kit):
    r = _freeze(kit)
    for k in ("active_design", "fixed_n", "completed_count",
              "incomplete_count", "completed_query_ids", "intake_sha256",
              "active_design_sha256", "keep_mask_sha256",
              "archive_315_sha256", "dropped_audit_sha256",
              "contact_sheet_manifest_sha256", "adjudication_audit_sha256",
              "handoff_csv_sha256", "index_run", "git_commit", "timestamp",
              "outcome_access", "annotation_status", "hold_reason",
              "result_status", "ai_drafts_generated",
              "ai_draft_artifact_count"):
        assert k in r, k


def test_status_values(kit):
    r = _freeze(kit)
    assert r["annotation_status"] == "HOLD"
    assert r["hold_reason"] == "annotation_burden"
    assert r["result_status"] == "unresolved"
    assert r["fixed_n"] is True


def test_counts_sum_to_design_total(kit, design):
    r = _freeze(kit)
    assert r["completed_count"] == 3
    assert r["completed_count"] + r["incomplete_count"] == \
        design["total_queries"]
    assert len(r["completed_query_ids"]) == 3


def test_completed_ids_sorted_and_identity_only(kit):
    r = _freeze(kit)
    assert r["completed_query_ids"] == sorted(r["completed_query_ids"])
    assert all(isinstance(q, str) for q in r["completed_query_ids"])


def test_outcome_access_all_false(kit):
    r = _freeze(kit)
    acc = r["outcome_access"]
    for k in ("retrieval_run", "arm_outputs_opened", "rr_mrr_computed",
              "p2_evaluate_run"):
        assert acc[k] is False, k


# ---- 라벨 내용 비복제 ------------------------------------------------------

def test_no_human_label_content_anywhere(kit):
    """직렬화한 전문에서 sentinel 문장·경계값이 나오면 안 된다."""
    blob = json.dumps(_freeze(kit), ensure_ascii=False)
    assert SENTINEL_TEXT not in blob
    assert "12.5" not in blob and "34.5" not in blob
    assert "label_content_recorded" in blob


def test_declares_content_not_recorded(kit):
    assert _freeze(kit)["label_content_recorded"] is False


# ---- 초안 생성 여부는 디스크에서 읽는다 -------------------------------------

def test_drafts_absent_reports_zero(kit):
    r = _freeze(kit)
    assert r["ai_drafts_generated"] is False
    assert r["ai_draft_artifact_count"] == 0


def test_drafts_present_is_reported_not_hardcoded(kit):
    kit["drafts"].write_text(
        json.dumps({"query_id": "p2_x_q01"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    r = _freeze(kit)
    assert r["ai_drafts_generated"] is True
    assert r["ai_draft_artifact_count"] == 1


def test_draft_content_not_copied(kit):
    kit["drafts"].write_text(json.dumps(
        {"query_id": "p2_x_q01", "text": SENTINEL_TEXT}) + "\n",
        encoding="utf-8")
    assert SENTINEL_TEXT not in json.dumps(_freeze(kit), ensure_ascii=False)


# ---- fail-closed ----------------------------------------------------------

def test_row_count_mismatch_refused(tmp_path, kit, design):
    rows = list(csv.DictReader(
        kit["intake"].read_text(encoding="utf-8-sig").splitlines()))[:-1]
    with kit["intake"].open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(H.AnnotationHoldError):
        _freeze(kit)


def test_query_id_mismatch_refused(kit):
    txt = kit["intake"].read_text(encoding="utf-8-sig").splitlines()
    txt[1] = txt[1].replace(txt[1].split(",")[0], "p2_NOT_IN_MASK_q01", 1)
    kit["intake"].write_text("\n".join(txt) + "\n", encoding="utf-8")
    with pytest.raises(H.AnnotationHoldError):
        _freeze(kit)


def test_missing_intake_refused(kit):
    kit["intake"].unlink()
    with pytest.raises(H.AnnotationHoldError):
        _freeze(kit)


def test_freeze_does_not_modify_intake(kit):
    before = hashlib.sha256(kit["intake"].read_bytes()).hexdigest()
    _freeze(kit)
    assert hashlib.sha256(kit["intake"].read_bytes()).hexdigest() == before


def test_write_refuses_overwrite(tmp_path, kit):
    out = tmp_path / "hold.json"
    H.write(_freeze(kit), out)
    with pytest.raises(H.AnnotationHoldError):
        H.write(_freeze(kit), out)


# ---- 해석 경계 ------------------------------------------------------------

def test_interpretation_guards_present(kit):
    g = _freeze(kit)["interpretation"]
    assert g["is_evidence_3b_superior"] is False
    assert g["is_evidence_rejecting_4b"] is False
    assert g["is_failed_experiment"] is False
    assert g["partial_gt_usable_for_analysis"] is False
    assert g["fresh_sign_evidence_produced"] is False


def test_resume_conditions_recorded(kit):
    r = _freeze(kit)
    assert r["resume"]["no_outcome_based_top_up"] is True
    assert isinstance(r["resume"]["invalidating_events"], list)
    assert len(r["resume"]["invalidating_events"]) >= 5


def test_index_run_identity_recorded(kit):
    ix = _freeze(kit)["index_run"]
    assert ix["run_id"] == "p2idx_0821d"
    assert ix["commit"] == "ab73e1c"
    assert ix["run_complete_recorded"] is True
    # run_root는 gitignore된 서버 경로다 — 로컬에서 해시를 재확인할 수 없다
    assert ix["run_complete_locally_verifiable"] is False
    assert ix["source"]


# ---- 실입력 -------------------------------------------------------------

def test_real_intake_freezes(design):
    r = H.freeze(at="2026-08-24T00:00:00")
    assert r["completed_count"] + r["incomplete_count"] == \
        design["total_queries"]
    assert r["annotation_status"] == "HOLD"
    assert r["intake_sha256"] == hashlib.sha256(
        INTAKE.CSV_PATH.read_bytes()).hexdigest()


def test_real_freeze_carries_no_label_content():
    """실 CSV의 채워진 문장이 산출물에 들어가지 않는다."""
    rows = list(csv.DictReader(
        INTAKE.CSV_PATH.read_text(encoding="utf-8-sig").splitlines()))
    texts = [(r.get("text") or "").strip() for r in rows]
    filled = [t for t in texts if t]
    blob = json.dumps(H.freeze(at="2026-08-24T00:00:00"), ensure_ascii=False)
    for t in filled:
        assert t not in blob
