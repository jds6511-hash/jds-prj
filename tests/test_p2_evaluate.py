"""P2 PRIMARY 평가기 — **결과를 보기 전에 고정한다.**

사전등록 `부호역전_확증_보충2_P2설계_2026-08-20.md` §2·§4-2·§5·§6·§7.
합성 fixture로만 테스트한다 — 실제 3B/4B 검색 결과는 GT 완성 전에 열지 않는다.

고정하는 것.

```
PRIMARY   Δ = MRR_cap(4b) − MRR_cap(3b), α=0.0 캡션 단독
단위       paired video-cluster bootstrap (cluster = 영상)
판정       CI가 0 배제·음수 → dev 방향 / 0 배제·양수 → AI Hub 방향 /
          0 포함 → 판정 불가 / half-width > 0.04 → 판정 불가 / k < 16 → 기술용
제외       사전 정의 목록으로만. 조용히 분모에서 빼지 않는다
공통 지지   두 arm이 같은 질의 집합이어야 한다
안 하는 것  채택 판단 · α·τ 재탐색 · 층별 유리한 층 선택 · 추가 표집
```
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_evaluate as E                                          # noqa: E402

SRC = (ROOT / "scripts" / "p2_evaluate.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


def _pq(vals: dict, alpha=0.0) -> dict:
    """arm 산출물 fixture — query_id → rr. 영상은 query_id 접두어에서 온다."""
    return {"alpha": alpha, "channel": "caption_only",
            "per_query": [{"query_id": q, "video_id": q.split("__")[0],
                           "rr": rr} for q, rr in vals.items()]}


def _pair(n_videos=20, per_video=3, base=0.4, delta=0.05):
    a, b = {}, {}
    for v in range(n_videos):
        for i in range(per_video):
            q = f"v{v:02d}__q{i}"
            a[q] = base
            b[q] = base + delta
    return _pq(a), _pq(b)


# ------------------------------------------------------- 고정된 계약

def test_primary_definition_is_frozen_in_the_module():
    assert E.PRIMARY_ALPHA == 0.0
    assert E.CLUSTER_KEY == "video_id"
    assert E.HALF_WIDTH_TARGET == 0.04
    assert E.MIN_CLUSTERS_FOR_VERDICT == 16
    assert E.BASE_ARM == "3b" and E.CANDIDATE_ARM == "4b"


def test_exclusion_reasons_are_a_closed_list():
    assert set(E.EXCLUSION_REASONS) == {
        "gold_count_exceeds_pool", "gold_span_incompatible_with_rule",
        "caption_missing"}


@pytest.mark.parametrize("token", ["alpha_search", "tau", "retune",
                                   "grid_search"])
def test_it_never_retunes(token):
    assert token not in CODE


def test_adoption_is_assigned_exactly_once_and_only_as_a_refusal():
    """`adoption` 키에 값을 넣는 곳은 한 군데이고 그 값은 거절 문구다."""
    assigns = [ln for ln in CODE.splitlines() if "'adoption':" in ln]
    assert len(assigns) == 1
    assert "하지_않는다" in assigns[0]


def test_module_does_not_touch_test_split_or_frozen_results():
    for token in ("eval_test", "alpha_search_dev", "queries.jsonl"):
        assert token not in CODE
    assert '"test"' not in CODE


# ------------------------------------------------------- 공통 지지·정합성

def test_alpha_other_than_zero_is_refused():
    a, b = _pair()
    a["alpha"] = 0.5
    with pytest.raises(E.EvalError, match="alpha"):
        E.analyze(a, b)


def test_arm_query_set_mismatch_is_refused():
    a, b = _pair(n_videos=3)
    b["per_query"] = b["per_query"][:-1]
    with pytest.raises(E.EvalError, match="공통 지지"):
        E.analyze(a, b)


def test_duplicate_query_id_is_refused():
    a, b = _pair(n_videos=2)
    a["per_query"].append(dict(a["per_query"][0]))
    b["per_query"].append(dict(b["per_query"][0]))
    with pytest.raises(E.EvalError, match="중복"):
        E.analyze(a, b)


def test_incomplete_arm_stops_before_computing_primary():
    """한 arm이라도 완주하지 못하면 PRIMARY를 계산하지 않는다(§6)."""
    a, b = _pair(n_videos=3)
    with pytest.raises(E.EvalError, match="완주"):
        E.analyze(a, b, arm_failures={"4b": 2})


def test_rr_out_of_range_is_refused():
    a, b = _pair(n_videos=2)
    a["per_query"][0]["rr"] = 1.5
    with pytest.raises(E.EvalError, match="rr"):
        E.analyze(a, b)


# ------------------------------------------------------- 제외 규칙

def test_exclusion_requires_a_predefined_reason():
    a, b = _pair(n_videos=3)
    qid = a["per_query"][0]["query_id"]
    with pytest.raises(E.EvalError, match="사전 정의"):
        E.analyze(a, b, exclude={qid: "결과가 이상해서"})


def test_exclusions_are_applied_to_both_arms_and_counted():
    a, b = _pair(n_videos=18)
    qid = a["per_query"][0]["query_id"]
    r = E.analyze(a, b, exclude={qid: "caption_missing"})
    assert r["n_queries_analyzed"] == 18 * 3 - 1
    assert r["exclusions"] == [{"query_id": qid, "reason": "caption_missing"}]
    assert r["n_excluded"] == 1
    assert r["common_support_recomputed"] is True


# ------------------------------------------------------- 점추정·CI

def test_delta_is_the_paired_mean_of_per_query_differences():
    a, b = _pair(n_videos=20, delta=0.05)
    r = E.analyze(a, b)
    assert r["delta_point"] == pytest.approx(0.05, abs=1e-9)
    assert r["mrr"]["3b"] == pytest.approx(0.4, abs=1e-9)
    assert r["mrr"]["4b"] == pytest.approx(0.45, abs=1e-9)
    assert r["delta_point"] == pytest.approx(r["mrr"]["4b"] - r["mrr"]["3b"],
                                             abs=1e-9)


def test_identical_arms_give_zero_delta_and_a_degenerate_ci():
    a, b = _pair(n_videos=20, delta=0.0)
    r = E.analyze(a, b)
    assert r["delta_point"] == 0.0
    assert r["ci"] == [0.0, 0.0]


def test_bootstrap_is_reproducible_and_clusters_by_video():
    a, b = _pair(n_videos=20)
    r1, r2 = E.analyze(a, b), E.analyze(a, b)
    assert r1["ci"] == r2["ci"]
    assert r1["ci_method"] == "paired_video_cluster_bootstrap_percentile"
    assert r1["cluster_key"] == "video_id" and r1["n_clusters"] == 20
    assert r1["bootstrap"]["seed"] == E.SEED and r1["bootstrap"]["B"] == E.B


# ------------------------------------------------------- 판정식

def test_wide_ci_is_reported_as_undecidable():
    a, b = _pair(n_videos=20, base=0.1, delta=0.0)
    # 영상 간 분산을 크게 만들어 half-width가 목표를 넘게 한다
    for row_a, row_b in zip(a["per_query"], b["per_query"]):
        v = int(row_a["video_id"][1:])
        row_b["rr"] = 1.0 if v % 2 else 0.0
        row_a["rr"] = 0.0 if v % 2 else 1.0
    r = E.analyze(a, b)
    assert r["half_width"] > E.HALF_WIDTH_TARGET
    assert r["verdict"] == "판정_불가"
    assert "이 규모로는" in r["verdict_text"]


def test_ci_including_zero_is_undecidable_even_when_narrow():
    a, b = _pair(n_videos=20, delta=0.0)
    r = E.analyze(a, b)
    assert r["ci"][0] <= 0 <= r["ci"][1]
    assert r["verdict"] == "판정_불가"


def test_negative_ci_excluding_zero_reproduces_the_dev_direction():
    a, b = _pair(n_videos=20, delta=-0.05)
    r = E.analyze(a, b)
    assert r["ci"][1] < 0 and r["verdict"] == "dev_방향_재현"


def test_positive_ci_excluding_zero_reproduces_the_aihub_direction():
    a, b = _pair(n_videos=20, delta=0.05)
    r = E.analyze(a, b)
    assert r["ci"][0] > 0 and r["verdict"] == "aihub_방향_재현"


def test_few_clusters_downgrade_to_descriptive_only():
    a, b = _pair(n_videos=3, delta=0.05)
    r = E.analyze(a, b)
    assert r["n_clusters"] == 3
    assert r["verdict"] == "기술용_판정하지_않음"
    assert "16" in r["verdict_text"]


def test_verdict_is_never_an_adoption_decision():
    a, b = _pair(n_videos=20, delta=0.05)
    r = E.analyze(a, b)
    assert r["adoption"] == "이_분석에서_하지_않는다"
    assert "I1" in r["remaining_barrier"]


# ------------------------------------------------------- 부수 보고

def test_strata_and_per_video_deltas_are_reported_but_not_the_verdict_basis():
    a, b = _pair(n_videos=18)
    types = {row["query_id"]: ("자막형" if i % 3 == 0 else "장면형")
             for i, row in enumerate(a["per_query"])}
    r = E.analyze(a, b, query_types=types)
    assert set(r["by_type"]) == {"자막형", "장면형"}
    assert len(r["by_video"]) == 18
    assert r["verdict_basis"] == "overall_delta_only"


def test_pool_size_is_recorded_as_continuous_not_binned():
    a, b = _pair(n_videos=18)
    pools = {row["video_id"]: 150 + int(row["video_id"][1:]) * 10
             for row in a["per_query"]}
    r = E.analyze(a, b, pool_sizes=pools)
    assert r["pool_sizes"] == pools
    assert "구간" not in json.dumps(r["pool_size_note"], ensure_ascii=False)


def test_run_is_gated_until_the_gt_file_is_frozen():
    """실행 진입점은 GT 동결 해시를 요구한다 — 부분 GT로 돌리지 않는다."""
    with pytest.raises(E.EvalError, match="동결"):
        E.require_frozen_gt({"n": 200, "sha256": None})
    assert E.require_frozen_gt({"n": 315, "sha256": "a" * 64})["ok"] is True


def test_partial_gt_is_refused_by_count():
    with pytest.raises(E.EvalError, match="315"):
        E.require_frozen_gt({"n": 200, "sha256": "a" * 64})
