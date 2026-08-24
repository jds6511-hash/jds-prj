"""hybrid 전환 동결 — **라벨 내용을 담지 않는다.**

이 파일이 AI 프롬프트·few-shot 입력이 되면 human-only 분량이 초안에 새어 든다.
그래서 완료 query_id만 남기고 text·gt_start·gt_end는 기록하지 않는다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_hybrid_freeze as F                                       # noqa: E402
import p2_label_intake as I                                        # noqa: E402

SRC = (ROOT / "scripts" / "p2_hybrid_freeze.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


def _intake(tmp_path, n_done=3, rows=None):
    import csv
    rows = rows if rows is not None else I.active_allocation()
    p = tmp_path / "intake.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(I.COLUMNS))
        w.writeheader()
        for i, r in enumerate(rows):
            row = {**r, "text": "", "gt_start": "", "gt_end": "", "note": ""}
            if i < n_done:
                row.update({"text": f"비밀 질의 {i}", "gt_start": "10",
                            "gt_end": "20"})
            w.writerow(row)
    return p


# ------------------------------------------------------------- 내용 미기록

def test_the_freeze_records_ids_but_never_label_content(tmp_path):
    r = F.freeze(intake=_intake(tmp_path, n_done=3))
    blob = json.dumps(r, ensure_ascii=False)
    assert "비밀 질의" not in blob
    assert r["human_only"]["n_completed"] == 3
    assert len(r["human_only"]["query_ids"]) == 3
    assert r["human_only"]["label_content_recorded"] is False


def test_completed_ids_returns_ids_only(tmp_path):
    got = F.completed_ids(_intake(tmp_path, n_done=2))
    assert len(got) == 2
    assert all(q.startswith("p2_") for q in got)


def test_partially_filled_rows_do_not_count(tmp_path):
    import csv
    rows = I.active_allocation()
    p = tmp_path / "partial.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(I.COLUMNS))
        w.writeheader()
        for i, r in enumerate(rows):
            row = {**r, "text": "", "gt_start": "", "gt_end": "", "note": ""}
            if i == 0:
                row.update({"text": "쓰다 만 질의", "gt_start": "5"})
            w.writerow(row)
    assert F.completed_ids(p) == []


# ------------------------------------------------------------- provenance

def test_it_carries_the_design_and_mask_provenance(tmp_path):
    r = F.freeze(intake=_intake(tmp_path))
    d = r["active_design"]
    assert d["design"] == "p2_175" and d["total_queries"] == 175
    assert d["quota"] == {"복합형": 62, "자막형": 44, "장면형": 69}
    assert len(d["keep_mask_sha256"]) == 64 and len(d["sha256"]) == 64
    assert len(r["intake"]["sha256"]) == 64
    assert r["contact_sheets"]["n_sheets"] == 172
    assert len(r["archive"]["sha256"]) == 64
    assert len(r["dropped_audit"]["sha256"]) == 64


def test_it_declares_that_no_outcome_was_accessed(tmp_path):
    r = F.freeze(intake=_intake(tmp_path))
    assert r["outcome_access"] == {"p2_retrieval_run": False,
                                   "p2_evaluate_run": False,
                                   "arm_output_opened": False,
                                   "caption_opened": False,
                                   "retrieval_metric_computed": False}


def test_it_warns_against_comparing_the_pre_gt_hash(tmp_path):
    r = F.freeze(intake=_intake(tmp_path))
    note = r["pre_gt_freeze_ref"]["note"]
    assert "같아야 한다고 검사하면 안 된다" in note


def test_the_timestamp_can_be_pinned_for_reproducibility(tmp_path):
    r = F.freeze(intake=_intake(tmp_path), at="2026-08-24T12:00:00")
    assert r["frozen_at"] == "2026-08-24T12:00:00"


# ------------------------------------------------------------- fail-closed

def test_a_row_count_that_is_not_the_active_design_is_refused(tmp_path):
    rows = I.active_allocation()[:-1]
    with pytest.raises(F.HybridFreezeError, match="175"):
        F.freeze(intake=_intake(tmp_path, rows=rows))


def test_a_query_id_set_that_differs_from_the_mask_is_refused(tmp_path):
    rows = [dict(r) for r in I.active_allocation()]
    rows[0]["query_id"] = "p2_zz_q99"
    with pytest.raises(F.HybridFreezeError, match="mask"):
        F.freeze(intake=_intake(tmp_path, rows=rows))


def test_a_missing_intake_is_refused(tmp_path):
    with pytest.raises(F.HybridFreezeError, match="작업 CSV"):
        F.freeze(intake=tmp_path / "nope.csv")


# ------------------------------------------------------------- 경계

def _imported(src: str) -> set:
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


@pytest.mark.parametrize("mod", ["p2_retrieve", "p2_evaluate", "m5_search",
                                 "m6_evaluate", "frame_human_kit"])
def test_it_imports_no_retrieval_or_evaluation_module(mod):
    assert mod not in _imported(SRC)


@pytest.mark.parametrize("token", ["rr_cap", "mrr", "rank", "score", "arm_3b",
                                   "arm_4b", "work_p2", "segments.json"])
def test_no_outcome_path_exists(token):
    assert token.lower() not in CODE.lower()
