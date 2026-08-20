"""P2 질의 유형 쿼터 — **규칙이 배정보다 먼저 커밋된다.**

막는 것 여섯.
1. 행 합이 영상당 질의 수와 달라지는 것
2. 열 합이 global quota와 달라지는 것
3. `achieved_k`가 줄었을 때 111/79/125의 뒤를 잘라 쓰는 것
4. seed 없이·다른 소비 순서로 배정하는 것
5. 특정 유형이 어떤 영상에서 0이 되는 것 (기본 배정이 보장한다)
6. 캡션·검색·제목이 배정에 들어오는 것
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p2_query_quota as Q                                       # noqa: E402

V35 = [f"v{i:02d}" for i in range(35)]


# ---- 규칙이 선언돼 있다 ---------------------------------------------------

def test_frozen_constants():
    assert Q.SEED == 20260820
    assert Q.QUERIES_PER_VIDEO == 9
    assert Q.DEV_COUNTS == {"mixed": 34, "subtitle": 24, "scene": 38}
    assert Q.TIE_ORDER == ("mixed", "scene", "subtitle")
    assert Q.BASE_PER_TYPE == 1


def test_rng_consumption_order_is_recorded():
    """같은 RNG를 두 곳에서 쓰면 소비 순서가 결과를 바꾼다."""
    r = Q.allocate(V35)
    assert r["rng_consumption_order"] == ["video_permutation",
                                          "type_label_pool"]
    assert r["video_sort_before_shuffle"] == "(program, source_id) ascending"


def test_allocation_does_not_look_at_outcomes():
    import inspect
    src = inspect.getsource(Q.allocate) + inspect.getsource(Q.hamilton_types)
    for bad in ("caption", "mrr", "score", "qwen", "alpha", "title"):
        assert bad not in src.lower(), bad


# ---- global quota --------------------------------------------------------

def test_hamilton_matches_the_documented_315_split():
    assert Q.hamilton_types(315) == {"mixed": 111, "subtitle": 79,
                                     "scene": 125}


def test_smaller_k_recomputes_instead_of_truncating():
    """`achieved_k`가 줄면 111/79/125의 뒤를 자르지 않는다."""
    q30 = Q.hamilton_types(270)
    assert sum(q30.values()) == 270
    assert q30 != {"mixed": 111, "subtitle": 79, "scene": 125}
    # 비율은 유지된다
    assert q30["scene"] > q30["mixed"] > q30["subtitle"]


def test_hamilton_total_is_exact_for_every_k():
    for k in range(1, 40):
        q = Q.hamilton_types(9 * k)
        assert sum(q.values()) == 9 * k


# ---- 행·열 합 -----------------------------------------------------------

def test_row_sums_equal_queries_per_video():
    r = Q.allocate(V35)
    for v, q in r["per_video_quota"].items():
        assert sum(q.values()) == 9, v


def test_column_sums_equal_global_quota():
    r = Q.allocate(V35)
    assert r["achieved_type_quota"] == r["global_target_quota"]
    assert r["achieved_type_quota"] == {"mixed": 111, "subtitle": 79,
                                        "scene": 125}


def test_every_video_gets_at_least_one_of_each_type():
    """기본 배정이 보장한다 — 최소 지분 0.25 × 9k = 2.25k >= k."""
    for k in (16, 24, 30, 35):
        r = Q.allocate([f"x{i}" for i in range(k)])
        for v, q in r["per_video_quota"].items():
            assert all(q[t] >= 1 for t in Q.TYPES), (k, v)


def test_base_allocation_is_feasible_for_every_k():
    for k in range(1, 40):
        g = Q.hamilton_types(9 * k)
        assert all(g[t] >= k for t in Q.TYPES), k


# ---- 결정성 ------------------------------------------------------------

def test_allocation_is_deterministic():
    a = Q.allocate(V35)
    b = Q.allocate(V35)
    assert a["per_video_quota"] == b["per_video_quota"]
    assert a["seed_order"] == b["seed_order"]


def test_a_different_seed_changes_the_allocation():
    a = Q.allocate(V35, seed=Q.SEED)
    b = Q.allocate(V35, seed=1)
    assert a["per_video_quota"] != b["per_video_quota"]
    # 그래도 열 합은 같다 — global quota는 seed와 무관하다
    assert a["achieved_type_quota"] == b["achieved_type_quota"]


def test_input_order_does_not_change_column_sums():
    r = Q.allocate(list(reversed(V35)))
    assert r["achieved_type_quota"] == {"mixed": 111, "subtitle": 79,
                                        "scene": 125}


def test_deviation_starts_empty_and_is_declared():
    r = Q.allocate(V35)
    assert r["deviation"] == {}
    assert "deviation" in r["note"]


def test_cli_output_is_ascii_safe():
    src = (ROOT / "scripts" / "p2_query_quota.py").read_text(encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line
