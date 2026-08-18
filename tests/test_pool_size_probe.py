"""P1 — 보충1 §5의 TDD 계약 10건을 결과 보기 전에 고정한다.

막는 것은 하나로 요약된다: **후보 선택이 성능을 볼 수 없게 한다.** arm·점수·순위가
후보 구성에 들어오면 그 시점에 조작이 아니라 선별이 된다.
"""
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import pool_size_probe as P                                    # noqa: E402

SEGS = [f"vA#{i}" for i in range(40)]
Q = [{"query_id": "q1", "video_id": "vA", "text": "t1"},
     {"query_id": "q2", "video_id": "vA", "text": "t2"}]
GOLD = {"q1": ["vA#5"], "q2": ["vA#30"]}
UNIV = {"vA": SEGS}


def _orders(cand_first, cur_first):
    """gold를 지정 순위에 놓은 전체 순위 2개."""
    def mk(first):
        rest = [s for s in SEGS if s != first]
        return [first] + rest
    return {"A4B": {"q1": mk(cand_first["q1"]), "q2": mk(cand_first["q2"])},
            "A3B": {"q1": mk(cur_first["q1"]), "q2": mk(cur_first["q2"])}}


# ---- 계약 1: 후보 선택 함수가 성능을 볼 수 없다 ---------------------------

def test_select_candidates_cannot_see_scores_or_arms():
    params = set(inspect.signature(P.select_candidates).parameters)
    for bad in ("arm", "arms", "captions", "caption", "emb", "embedding",
                "similarity", "score", "scores", "rank", "ranks", "rr", "order"):
        assert bad not in params, bad
    assert params == {"query_id", "video_id", "seg_ids", "gold", "pool_size",
                      "run_tag", "rule"}


def test_module_does_not_read_alpha_or_tau_keys():
    """계약 6 — α·τ로 부호를 구제하지 않는다."""
    body = (ROOT / "docs" / "probes" / "pool_size_probe.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("alpha_star", "alpha_curve", "mrr_alpha_fixed", "abstention_tau",
                "rr_alpha_fixed", "secondary"):
        assert bad not in body, bad


def test_no_vlm_or_caption_generation_entrypoint():
    """계약 5 — 새 캡션 생성·VLM 추론 경로가 없다."""
    src = (ROOT / "docs" / "probes" / "pool_size_probe.py").read_text(
        encoding="utf-8")
    for bad in ("m3_generate", "load_captioner", "gen_captions",
                "AutoModelForVision", "Qwen"):
        assert bad not in src, bad


# ---- 계약 2: arm 간 후보가 동일 -------------------------------------------

def test_candidates_are_identical_across_arms():
    a = P.select_candidates("q1", "vA", SEGS, GOLD["q1"], 12, "t")
    b = P.select_candidates("q1", "vA", SEGS, GOLD["q1"], 12, "t")
    assert a == b
    # 같은 인자면 byte-for-byte 같은 목록 — arm이 인자가 아니므로 arm별로 다를 수 없다
    assert json.dumps(a) == json.dumps(b)


def test_candidate_selection_is_deterministic_across_processes():
    """해시 기반이므로 프로세스를 바꿔도 같아야 한다 (PYTHONHASHSEED 무관)."""
    code = ("import sys; sys.path.insert(0, r'%s');"
            "import pool_size_probe as P, json;"
            "print(json.dumps(P.select_candidates('q1','vA',"
            "[f'vA#{i}' for i in range(40)],['vA#5'],12,'t')))"
            % (ROOT / "docs" / "probes"))
    outs = set()
    for seed in ("0", "1"):
        e = {**os.environ, "PYTHONHASHSEED": seed}
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env=e)
        assert r.returncode == 0, r.stderr[-300:]
        outs.add(r.stdout.strip())
    assert len(outs) == 1, outs


# ---- 계약 3: gold 보존 · fail-closed --------------------------------------

def test_all_gold_is_preserved():
    for k in (12, 24, 48):
        c = P.select_candidates("q1", "vA", SEGS, ["vA#5", "vA#6"], k, "t")
        assert set(["vA#5", "vA#6"]) <= set(c)
        assert len(c) == min(k, len(SEGS))


def test_gold_larger_than_pool_is_fail_closed():
    gold = [f"vA#{i}" for i in range(13)]
    with pytest.raises(P.ProbeError, match="gold"):
        P.select_candidates("q1", "vA", SEGS, gold, 12, "t")


def test_gold_outside_universe_is_refused():
    with pytest.raises(P.ProbeError, match="universe"):
        P.select_candidates("q1", "vA", SEGS, ["vB#1"], 12, "t")


def test_undeclared_rule_is_refused():
    with pytest.raises(P.ProbeError, match="규칙"):
        P.select_candidates("q1", "vA", SEGS, GOLD["q1"], 12, "t", rule="my_rule")


# ---- 계약 4: universe 무결성 ----------------------------------------------

def test_duplicate_query_id_is_refused():
    dup = Q + [{"query_id": "q1", "video_id": "vA", "text": "t"}]
    with pytest.raises(P.ProbeError, match="중복"):
        P.analyze(_orders({"q1": "vA#5", "q2": "vA#30"},
                          {"q1": "vA#5", "q2": "vA#30"}),
                  dup, UNIV, {**GOLD}, {"cand": "A4B", "cur": "A3B"}, "t")


def test_missing_arm_is_refused():
    with pytest.raises(P.ProbeError, match="arm"):
        P.analyze({"A4B": {}}, Q, UNIV, GOLD,
                  {"cand": "A4B", "cur": "A3B"}, "t")


# ---- 조작이 실제로 풀 크기만 바꾸는지 -------------------------------------

def test_local_window_is_contiguous_and_named_accordingly():
    c = P.select_candidates("q1", "vA", SEGS, ["vA#5"], 12, "t",
                            rule="P1a_local_window_12")
    idx = sorted(SEGS.index(s) for s in c)
    assert idx == list(range(idx[0], idx[0] + 12))            # 연속
    assert "local_window" in "P1a_local_window_12"            # 이름에 조작이 박혀 있다
    assert P.PRIMARY_RULE == "P1a_pool_size_random_negatives"


def test_random_negatives_rule_is_not_contiguous_in_general():
    c = P.select_candidates("q1", "vA", SEGS, ["vA#5"], 12, "t")
    idx = sorted(SEGS.index(s) for s in c)
    assert idx != list(range(idx[0], idx[0] + 12))


def test_pool_at_or_above_universe_returns_whole_universe():
    assert P.select_candidates("q1", "vA", SEGS, GOLD["q1"], 40, "t") == SEGS
    assert P.select_candidates("q1", "vA", SEGS, GOLD["q1"], 99, "t") == SEGS


# ---- RR 제한 계산 --------------------------------------------------------

def test_restricted_rr_uses_position_within_candidates():
    order = ["vA#0", "vA#1", "vA#5", "vA#7"]
    assert P.restricted_rr(order, ["vA#5"], order) == pytest.approx(1 / 3)
    # 앞의 negative 2개를 후보에서 빼면 gold가 1위가 된다
    assert P.restricted_rr(order, ["vA#5"], ["vA#5", "vA#7"]) == 1.0


def test_restricted_rr_is_zero_when_gold_not_in_candidates():
    assert P.restricted_rr(SEGS, ["vA#5"], ["vA#1", "vA#2"]) == 0.0


def test_zscore_monotonicity_assumption_holds_for_ranking():
    """부분집합 안의 상대 순서가 전체 순위와 같다는 가정 — 이게 깨지면 근거가 없다."""
    rng = np.random.default_rng(0)
    s = rng.normal(size=30)
    order = list(np.argsort(-s, kind="stable"))
    sub = sorted(rng.choice(30, 12, replace=False).tolist())
    sub_order_from_full = [i for i in order if i in set(sub)]
    z = (s - s.mean()) / s.std()
    sub_order_direct = sorted(sub, key=lambda i: (-z[i], i))
    assert sub_order_from_full == sub_order_direct


# ---- 계약 7·10: 기록과 재현 게이트 ---------------------------------------

def test_output_records_rule_and_version_and_run_tag():
    r = P.analyze(_orders({"q1": "vA#5", "q2": "vA#30"},
                          {"q1": "vA#5", "q2": "vA#30"}),
                  Q, UNIV, GOLD, {"cand": "A4B", "cur": "A3B"}, "tag1")
    assert r["candidate_rule"] == P.PRIMARY_RULE
    assert r["candidate_rule_version"] == P.RULE_VERSION
    assert r["run_tag"] == "tag1"
    assert r["primary"]["definition"].startswith("I_pool")


def test_reproduction_gate_refuses_mismatch():
    """계약 10 — 저장값과 다르면 중단한다. 조용히 계속하지 않는다."""
    orders = _orders({"q1": "vA#5", "q2": "vA#30"}, {"q1": "vA#5", "q2": "vA#30"})
    with pytest.raises(P.ProbeError, match="재현 게이트"):
        P.analyze(orders, Q, UNIV, GOLD, {"cand": "A4B", "cur": "A3B"}, "t",
                  stored_mrr={"A4B": 0.9999, "A3B": 0.9999})


def test_reproduction_gate_passes_on_exact_match():
    orders = _orders({"q1": "vA#5", "q2": "vA#30"}, {"q1": "vA#5", "q2": "vA#30"})
    r = P.analyze(orders, Q, UNIV, GOLD, {"cand": "A4B", "cur": "A3B"}, "t",
                  stored_mrr={"A4B": 1.0, "A3B": 1.0})
    assert all(v["match"] for v in r["reproduction_check"].values())


# ---- I_pool 방향 ---------------------------------------------------------

def test_i_pool_sign_and_prediction_flag():
    """4B가 전체 풀에서만 불리하면 I_pool < 0이고 예측과 맞는다."""
    orders = {"A4B": {"q1": ["vA#0"] * 0 + [s for s in SEGS], "q2": list(SEGS)},
              "A3B": {"q1": list(SEGS), "q2": list(SEGS)}}
    # 4B: gold를 뒤로, 3B: gold를 앞으로 — 전체 풀에서 3B가 유리
    orders["A4B"]["q1"] = [s for s in SEGS if s != "vA#5"] + ["vA#5"]
    orders["A4B"]["q2"] = [s for s in SEGS if s != "vA#30"] + ["vA#30"]
    orders["A3B"]["q1"] = ["vA#5"] + [s for s in SEGS if s != "vA#5"]
    orders["A3B"]["q2"] = ["vA#30"] + [s for s in SEGS if s != "vA#30"]
    r = P.analyze(orders, Q, UNIV, GOLD, {"cand": "A4B", "cur": "A3B"}, "t")
    assert r["primary"]["d_large"] < 0
    assert r["primary"]["i_pool"] < 0
    assert r["primary"]["matches_prediction"] is True


def test_no_cause_or_verdict_keys():
    r = P.analyze(_orders({"q1": "vA#5", "q2": "vA#30"},
                          {"q1": "vA#5", "q2": "vA#30"}),
                  Q, UNIV, GOLD, {"cand": "A4B", "cur": "A3B"}, "t")
    flat = str(sorted(r.keys()))
    for bad in ("cause", "verdict", "conclusion", "root_cause", "winner",
                "adopt", "recommendation"):
        assert bad not in flat, bad
    assert "plausible" in r["limits"] or "확정" in r["limits"]


def test_grid_is_declared_in_advance():
    """결과를 보고 격자를 늘리지 않는다 — 값이 코드에 박혀 있다."""
    assert P.DEV_GRID == (12, 24, 48, 96)
    assert P.AIHUB_GRID == (12, 24, 48, 96, 192, 384, 768, 2328)
    assert P.SMALL_POOL == 12


# ---- 계약 9: cp949 콘솔 --------------------------------------------------

def test_cli_output_is_ascii_safe():
    """산출물 존재와 run 성공은 별개다 — stdout에서 죽으면 exit != 0이다."""
    src = (ROOT / "docs" / "probes" / "pool_size_probe.py").read_text(
        encoding="utf-8")
    body = src.split('if __name__')[0]
    prints = [l for l in body.splitlines() if l.strip().startswith("print(")]
    assert prints
    for l in prints:
        l.encode("cp949")                                     # 죽으면 테스트 실패
        assert l.isascii(), l


def test_cli_survives_cp949_console():
    """실제 subprocess로 검사한다. 본 실행은 임베딩이 필요해 단위테스트에 넣지
    못하므로, CLI 진입 자체가 cp949에서 exit 0인지까지만 여기서 잡는다."""
    env = {**os.environ, "PYTHONIOENCODING": "cp949"}
    r = subprocess.run([sys.executable,
                        str(ROOT / "docs" / "probes" / "pool_size_probe.py"),
                        "--help"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr[-400:]
    assert r.stdout.isascii()


# ---- 계약 8: parity 어휘 --------------------------------------------------

def test_parity_uses_unknown_not_recorded_vocabulary():
    """기록 없음은 PASS도 FAIL도 아니다. 구현을 둘로 만들지 않고 재사용한다."""
    sys.path.insert(0, str(ROOT / "docs" / "probes"))
    import sign_reversal_diag as D
    sweep = {"arms": {"A4B": {"provenance": {"prompt_sha256": "p"}},
                      "A3B": {"provenance": {"prompt_sha256": "p"}}}}
    p = P.parity_audit(sweep, ["A4B", "A3B"])
    assert p is D.parity_audit(sweep, ["A4B", "A3B"]) or p == D.parity_audit(
        sweep, ["A4B", "A3B"])
    assert p["prompt_sha256"]["status"] == "match"
    assert p["dtype"]["status"] == "unknown_not_recorded"
    assert p["dtype"]["match"] is None
