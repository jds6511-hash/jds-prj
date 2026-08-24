"""심사 provenance — **audit metadata일 뿐이고 평가에 넘기지 않는다.**

최종 text·gt_start·gt_end는 작업 CSV 하나에만 있다. label_origin으로 가중·선택·
제외하지 않고, label_origin별 성능을 사후에 갈라 보지 않는다.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_adjudication as A                                        # noqa: E402

SRC = (ROOT / "scripts" / "p2_adjudication.py").read_text(encoding="utf-8")
EVAL_SRC = (ROOT / "scripts" / "p2_evaluate.py").read_text(encoding="utf-8")
RETR_SRC = (ROOT / "scripts" / "p2_retrieve.py").read_text(encoding="utf-8")
ALLOC = [{"query_id": f"p2_v0_q{i:02d}", "video_id": "v0",
          "query_type": "장면형"} for i in range(1, 6)]


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


# ------------------------------------------------------------- 스키마

def test_the_audit_never_holds_the_final_label():
    assert set(A.AUDIT_COLUMNS) == {"query_id", "label_origin", "draft_action",
                                     "recorded_at"}
    for c in ("text", "gt_start", "gt_end", "note"):
        assert c not in A.AUDIT_COLUMNS


def test_the_vocabularies_are_closed():
    assert set(A.LABEL_ORIGIN) == {"human_only", "ai_first_human_adjudicated"}
    assert set(A.DRAFT_ACTION) == {"not_applicable", "accepted", "edited",
                                    "rejected_manual"}


# ------------------------------------------------------------- 짝 검사

@pytest.mark.parametrize("origin,action", [
    ("human_only", "not_applicable"),
    ("ai_first_human_adjudicated", "accepted"),
    ("ai_first_human_adjudicated", "edited"),
    ("ai_first_human_adjudicated", "rejected_manual"),
])
def test_valid_pairs_pass(origin, action):
    assert A.check_pair(origin, action) is None


def test_human_only_with_a_draft_action_is_refused():
    with pytest.raises(A.AdjudicationError, match="human_only"):
        A.check_pair("human_only", "accepted")


def test_ai_first_without_an_action_is_refused():
    with pytest.raises(A.AdjudicationError, match="not_applicable"):
        A.check_pair("ai_first_human_adjudicated", "not_applicable")


@pytest.mark.parametrize("origin", ["ai_only", "machine", ""])
def test_an_unknown_origin_is_refused(origin):
    with pytest.raises(A.AdjudicationError, match="label_origin"):
        A.check_pair(origin, "accepted")


@pytest.mark.parametrize("action", ["auto_accepted", "copied", ""])
def test_an_unknown_action_is_refused(action):
    with pytest.raises(A.AdjudicationError, match="draft_action"):
        A.check_pair("ai_first_human_adjudicated", action)


# ------------------------------------------------------------- 기록

def test_record_writes_one_row_per_query(tmp_path):
    p = tmp_path / "audit.csv"
    A.record("p2_v0_q01", "human_only", "not_applicable", p,
             at="2026-08-24T00:00:00", allocation=ALLOC)
    A.record("p2_v0_q02", "ai_first_human_adjudicated", "edited", p,
             at="2026-08-24T00:01:00", allocation=ALLOC)
    rows = A.load(p)
    assert [r["query_id"] for r in rows] == ["p2_v0_q01", "p2_v0_q02"]
    assert rows[1]["draft_action"] == "edited"


def test_recording_the_same_query_updates_it(tmp_path):
    p = tmp_path / "audit.csv"
    A.record("p2_v0_q01", "ai_first_human_adjudicated", "accepted", p,
             at="t1", allocation=ALLOC)
    A.record("p2_v0_q01", "ai_first_human_adjudicated", "edited", p,
             at="t2", allocation=ALLOC)
    rows = A.load(p)
    assert len(rows) == 1 and rows[0]["draft_action"] == "edited"
    assert rows[0]["recorded_at"] == "t2"


def test_rows_follow_the_frozen_allocation_order(tmp_path):
    p = tmp_path / "audit.csv"
    for qid in ("p2_v0_q05", "p2_v0_q01", "p2_v0_q03"):
        A.record(qid, "human_only", "not_applicable", p, at="t",
                 allocation=ALLOC)
    assert [r["query_id"] for r in A.load(p)] == ["p2_v0_q01", "p2_v0_q03",
                                                  "p2_v0_q05"]


def test_an_unknown_query_id_is_refused(tmp_path):
    with pytest.raises(A.AdjudicationError, match="활성 설계"):
        A.record("p2_zz_q99", "human_only", "not_applicable",
                 tmp_path / "audit.csv", allocation=ALLOC)


def test_seeding_human_only_uses_ids_only(tmp_path):
    p = tmp_path / "audit.csv"
    got = A.seed_human_only(["p2_v0_q01", "p2_v0_q02"], p, at="t",
                            allocation=ALLOC)
    assert got["n_seeded"] == 2 and got["n_rows"] == 2
    rows = A.load(p)
    assert all(r["label_origin"] == "human_only" for r in rows)
    assert all(r["draft_action"] == "not_applicable" for r in rows)


def test_seeding_an_unknown_id_is_refused(tmp_path):
    with pytest.raises(A.AdjudicationError, match="활성 설계"):
        A.seed_human_only(["p2_zz_q99"], tmp_path / "audit.csv",
                          allocation=ALLOC)


def test_seeding_is_idempotent(tmp_path):
    p = tmp_path / "audit.csv"
    A.seed_human_only(["p2_v0_q01"], p, at="t", allocation=ALLOC)
    A.seed_human_only(["p2_v0_q01"], p, at="t", allocation=ALLOC)
    assert len(A.load(p)) == 1


def test_seeding_does_not_clobber_an_adjudicated_row(tmp_path):
    p = tmp_path / "audit.csv"
    A.record("p2_v0_q02", "ai_first_human_adjudicated", "accepted", p, at="t",
             allocation=ALLOC)
    A.seed_human_only(["p2_v0_q01"], p, at="t", allocation=ALLOC)
    rows = {r["query_id"]: r for r in A.load(p)}
    assert rows["p2_v0_q02"]["label_origin"] == "ai_first_human_adjudicated"


# ------------------------------------------------------------- 검증

def test_validate_counts_and_lists_what_is_missing(tmp_path):
    p = tmp_path / "audit.csv"
    A.record("p2_v0_q01", "human_only", "not_applicable", p, at="t",
             allocation=ALLOC)
    A.record("p2_v0_q02", "ai_first_human_adjudicated", "rejected_manual", p,
             at="t", allocation=ALLOC)
    r = A.validate(p, allocation=ALLOC)
    assert r["n_rows"] == 2 and r["n_design"] == 5
    assert r["by_label_origin"]["human_only"] == 1
    assert r["by_draft_action"]["rejected_manual"] == 1
    assert r["missing"] == ["p2_v0_q03", "p2_v0_q04", "p2_v0_q05"]


def test_validate_refuses_an_audit_that_smuggles_the_final_label(tmp_path):
    import csv
    p = tmp_path / "audit.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(A.AUDIT_COLUMNS) + ["text"])
        w.writeheader()
        w.writerow({"query_id": "p2_v0_q01", "label_origin": "human_only",
                    "draft_action": "not_applicable", "recorded_at": "t",
                    "text": "질의"})
    with pytest.raises(A.AdjudicationError, match="열 구성이 다르다|audit에 있다"):
        A.validate(p, allocation=ALLOC)


def test_validate_states_it_is_not_for_evaluation(tmp_path):
    r = A.validate(tmp_path / "none.csv", allocation=ALLOC)
    joined = " ".join(r["not_for_evaluation"])
    assert "가중" in joined and "사전등록" in joined


# ------------------------------------------------------------- 경계

def test_the_evaluator_does_not_know_about_label_origin():
    """audit metadata가 PRIMARY 경로에 닿지 않는다."""
    for src in (EVAL_SRC, RETR_SRC):
        for token in ("label_origin", "draft_action", "adjudication",
                      "p2_ai_draft"):
            assert token not in src


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


def test_it_stores_no_label_content(tmp_path):
    p = tmp_path / "audit.csv"
    A.record("p2_v0_q01", "ai_first_human_adjudicated", "edited", p, at="t",
             allocation=ALLOC)
    body = p.read_text(encoding="utf-8")
    assert "gt_start" not in body and "text" not in body
