"""P2 축소 설계 keep-mask — **결과를 보지 않고 계산한다.**

```
입력       동결 배정표(query_id · video_id · query_type)와 seed뿐이다
금지 입력   text · gt_start · gt_end · note · caption · subtitle ·
           retrieval 결과 · score · rank · 작성 완료 여부 · 사람이 느낀 난이도
불변       35 video cluster 유지 · query_id 재번호 없음 · 새 질의 생성 없음
제약       영상당 정확히 m행 · 모든 영상에 세 유형 >= 1 · global quota 정확히 일치
```
"""
import ast
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_reduced_design as D                                     # noqa: E402

SRC = (ROOT / "scripts" / "p2_reduced_design.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


def _without_forbidden_declaration(src: str) -> str:
    """`FORBIDDEN_INPUTS` 선언은 '쓰지 않는 것의 목록'이다 — 사용처가 아니다.

    선언 자체를 토큰 스캔 대상에서 뺀다. 목록을 지워 테스트를 통과시키는 것과
    반대 방향이다 — 선언은 남기고 스캔에서만 제외한다.
    """
    tree = ast.parse(src)
    tree.body = [n for n in tree.body
                 if not (isinstance(n, ast.Assign)
                         and any(getattr(t, "id", None) == "FORBIDDEN_INPUTS"
                                 for t in n.targets))]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE_NO_DECL = _without_forbidden_declaration(SRC)
KO = ("복합형", "자막형", "장면형")


def _alloc(comp: dict) -> list:
    """comp = {video_id: {유형: n}} → 배정표 행. query_id는 영상 안에서 1부터."""
    rows = []
    for vid in sorted(comp):
        n = 0
        for t in KO:
            for _ in range(comp[vid].get(t, 0)):
                n += 1
                rows.append({"query_id": f"p2_{vid}_q{n:02d}", "video_id": vid,
                             "query_type": t})
    return rows


def _even(n_videos=35, per=9) -> list:
    base = {"복합형": 3, "자막형": 3, "장면형": 3}
    return _alloc({f"v{i:02d}": dict(base) for i in range(n_videos)})


# ------------------------------------------------------------- Hamilton

def test_hamilton_reproduces_the_frozen_315_quota():
    assert D.quota_for(315) == {"복합형": 111, "자막형": 79, "장면형": 125}


def test_hamilton_175():
    assert D.quota_for(175) == {"복합형": 62, "자막형": 44, "장면형": 69}


def test_hamilton_140():
    assert D.quota_for(140) == {"복합형": 50, "자막형": 35, "장면형": 55}


def test_quota_sums_to_the_total():
    for total in (140, 175, 315):
        assert sum(D.quota_for(total).values()) == total


def test_hamilton_base_is_the_declared_dev_proportion_not_the_achieved_quota():
    """기준을 achieved 315로 잡으면 140이 49/35/56으로 갈린다 — 기준을 고정한다."""
    assert D.base_proportions() == {"복합형": 34, "자막형": 24, "장면형": 38}


def test_an_unsupported_total_is_refused():
    with pytest.raises(D.DesignError, match="설계"):
        D.keep_mask(200, allocation=_even())


# ------------------------------------------------------------- 구조 제약

@pytest.mark.parametrize("total,m", [(140, 4), (175, 5)])
def test_mask_gives_every_video_exactly_m_rows(total, m):
    mask = D.keep_mask(total, allocation=_even())
    kept = set(mask["kept_query_ids"])
    per_video = {}
    for r in _even():
        if r["query_id"] in kept:
            per_video[r["video_id"]] = per_video.get(r["video_id"], 0) + 1
    assert set(per_video.values()) == {m}
    assert len(kept) == total


@pytest.mark.parametrize("total", [140, 175])
def test_every_video_keeps_at_least_one_of_each_type(total):
    alloc = _even()
    mask = D.keep_mask(total, allocation=alloc)
    kept = set(mask["kept_query_ids"])
    by = {}
    for r in alloc:
        if r["query_id"] in kept:
            by.setdefault(r["video_id"], set()).add(r["query_type"])
    assert len(by) == 35
    for vid, types in by.items():
        assert types == set(KO), f"{vid}: {types}"


@pytest.mark.parametrize("total", [140, 175])
def test_global_type_quota_is_exact(total):
    alloc = _even()
    mask = D.keep_mask(total, allocation=alloc)
    kept = set(mask["kept_query_ids"])
    got = {t: 0 for t in KO}
    for r in alloc:
        if r["query_id"] in kept:
            got[r["query_type"]] += 1
    assert got == D.quota_for(total)


def test_the_315_design_keeps_everything_and_drops_nothing():
    alloc = _even()
    mask = D.keep_mask(315, allocation=alloc)
    assert mask["dropped_query_ids"] == []
    assert len(mask["kept_query_ids"]) == 315


def test_35_video_clusters_are_preserved_in_every_design():
    alloc = _even()
    for total in (140, 175, 315):
        mask = D.keep_mask(total, allocation=alloc)
        kept = set(mask["kept_query_ids"])
        assert len({r["video_id"] for r in alloc if r["query_id"] in kept}) == 35
        assert mask["n_videos"] == 35


def test_kept_and_dropped_partition_the_frozen_allocation():
    alloc = _even()
    ids = {r["query_id"] for r in alloc}
    for total in (140, 175, 315):
        mask = D.keep_mask(total, allocation=alloc)
        kept, dropped = set(mask["kept_query_ids"]), set(mask["dropped_query_ids"])
        assert kept | dropped == ids
        assert kept & dropped == set()


def test_query_ids_are_never_renumbered():
    alloc = _even()
    mask = D.keep_mask(140, allocation=alloc)
    ids = {r["query_id"] for r in alloc}
    assert set(mask["kept_query_ids"]) <= ids
    assert all(q.startswith("p2_") for q in mask["kept_query_ids"])


# ------------------------------------------------------------- 결정성

def test_the_same_seed_gives_the_same_mask():
    alloc = _even()
    a = D.keep_mask(175, allocation=alloc)
    b = D.keep_mask(175, allocation=alloc)
    assert a["kept_query_ids"] == b["kept_query_ids"]


def test_row_order_does_not_change_the_mask():
    alloc = _even()
    shuffled = list(reversed(alloc))
    a = D.keep_mask(175, allocation=alloc)
    b = D.keep_mask(175, allocation=shuffled)
    assert a["kept_query_ids"] == b["kept_query_ids"]


def test_a_different_seed_may_give_a_different_mask_but_stays_valid():
    alloc = _even()
    other = D.keep_mask(175, allocation=alloc, seed=D.SEED + 1)
    assert len(other["kept_query_ids"]) == 175
    kept = set(other["kept_query_ids"])
    got = {t: 0 for t in KO}
    for r in alloc:
        if r["query_id"] in kept:
            got[r["query_type"]] += 1
    assert got == D.quota_for(175)


def test_the_mask_ignores_human_columns_entirely(tmp_path):
    """CSV 내용을 바꿔도 mask가 같다 — 사람 입력을 선택에 쓰지 않는다는 증거다."""
    alloc = _even()
    before = D.keep_mask(140, allocation=alloc)["kept_query_ids"]
    p = tmp_path / "intake.csv"
    cols = ("query_id", "video_id", "query_type", "text", "gt_start", "gt_end",
            "note")
    for filled in (0, 9, 315):
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(cols))
            w.writeheader()
            for i, r in enumerate(alloc):
                row = dict(r, text="", gt_start="", gt_end="", note="")
                if i < filled:
                    row.update({"text": f"질의 {i}", "gt_start": "10",
                                "gt_end": "20", "note": "메모"})
                w.writerow(row)
        assert D.keep_mask(140, allocation=alloc)["kept_query_ids"] == before


def test_selection_inputs_are_declared_and_forbidden_ones_listed():
    mask = D.keep_mask(140, allocation=_even())
    assert set(mask["selection_inputs"]) == {"query_id", "video_id", "query_type",
                                             "frozen_allocation_order", "seed"}
    for f in ("text", "gt_start", "gt_end", "note", "caption", "subtitle",
              "rank", "score", "written_already"):
        assert f in mask["forbidden_inputs"]


# ------------------------------------------------------------- fail-closed

def test_a_video_missing_a_type_is_refused():
    comp = {f"v{i:02d}": {"복합형": 3, "자막형": 3, "장면형": 3} for i in range(35)}
    comp["v00"] = {"복합형": 6, "자막형": 3, "장면형": 0}
    with pytest.raises(D.DesignError, match="v00"):
        D.keep_mask(140, allocation=_alloc(comp))


def test_an_infeasible_extra_quota_is_refused_not_silently_relaxed():
    """모든 영상이 자막형 1건뿐이면 자막형 extra를 배치할 곳이 없다."""
    comp = {f"v{i:02d}": {"복합형": 4, "자막형": 1, "장면형": 4} for i in range(35)}
    with pytest.raises(D.DesignError, match="배치할 수 없다"):
        D.keep_mask(175, allocation=_alloc(comp))


def test_a_wrong_cluster_count_is_refused():
    with pytest.raises(D.DesignError, match="영상 수"):
        D.keep_mask(140, allocation=_even(n_videos=30))


def test_a_video_with_the_wrong_row_count_is_refused():
    comp = {f"v{i:02d}": {"복합형": 3, "자막형": 3, "장면형": 3} for i in range(35)}
    comp["v01"] = {"복합형": 4, "자막형": 3, "장면형": 3}
    with pytest.raises(D.DesignError, match="v01"):
        D.keep_mask(140, allocation=_alloc(comp))


def test_verify_mask_recomputes_every_constraint():
    alloc = _even()
    mask = D.keep_mask(175, allocation=alloc)
    r = D.verify_mask(mask, allocation=alloc)
    assert r["ok"] is True
    assert r["checks"]["per_video_rows_exact"] is True
    assert r["checks"]["global_quota_exact"] is True
    assert r["checks"]["all_types_present_per_video"] is True
    assert r["checks"]["clusters_preserved"] is True
    assert r["checks"]["no_new_query_id"] is True


def test_verify_mask_catches_a_tampered_mask():
    alloc = _even()
    mask = D.keep_mask(175, allocation=alloc)
    mask["kept_query_ids"] = mask["kept_query_ids"][:-1]
    r = D.verify_mask(mask, allocation=alloc)
    assert r["ok"] is False


# ------------------------------------------------------------- 실 배정표

def test_the_real_frozen_allocation_supports_both_reduced_designs():
    alloc = D.frozen_allocation()
    assert len(alloc) == 315
    for total in (140, 175):
        mask = D.keep_mask(total, allocation=alloc)
        assert D.verify_mask(mask, allocation=alloc)["ok"] is True


# ------------------------------------------------------------- 경계

@pytest.mark.parametrize("token", ["caption", "subtitle", "mrr", "score",
                                   "rank", "retriev", "bootstrap", "verdict",
                                   "work_p2", "3b", "4b", "adoption"])
def test_no_outcome_path_exists(token):
    assert token.lower() not in CODE_NO_DECL.lower()


def test_the_forbidden_input_list_is_still_declared():
    """위 스캔이 선언을 제외하므로, 선언이 실제로 있는지는 따로 확인한다."""
    for f in ("text", "gt_start", "gt_end", "note", "caption", "subtitle",
              "rank", "score", "written_already"):
        assert f in D.FORBIDDEN_INPUTS


def _imported(src: str) -> set:
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


@pytest.mark.parametrize("mod", ["p2_evaluate", "p2_retrieve", "m5_search",
                                 "m6_evaluate", "csv"])
def test_it_imports_neither_evaluators_nor_the_working_csv_reader(mod):
    assert mod not in _imported(SRC)


def test_it_does_not_touch_the_working_intake_or_the_staging_file():
    for token in ("p2_label_intake.csv", "p2_queries_staging", "CSV_PATH",
                  "OUT_JSONL"):
        assert token not in CODE


def test_no_automatic_choice_between_designs():
    mask = D.keep_mask(140, allocation=_even())
    assert mask["decision"] == "사용자_승인_사항"
