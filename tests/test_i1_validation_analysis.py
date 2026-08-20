"""I1 validation 분석 — **라벨 도착 전에** 계약을 고정한다.

막는 것 넷.
1. fresh 성분과 carried-over 성분을 섞어 "fully fresh"로 부르는 것
2. 재현 게이트 없이 candidate 결과를 여는 것
3. 라벨이 덜 찼는데 지표를 내는 것
4. 결과를 보고 규칙을 조정할 수 있는 손잡이를 남기는 것
"""
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import i1_validation_analysis as A                             # noqa: E402

FRESH_POP = {"C0": 8114, "C2": 734}
CARRIED = {"C1": 1, "C4": 78, "C5": 3}


def _inst(sid, cell, cjk, run, ratio, hit=False):
    return {"sample_id": sid, "cell": cell, "cjk_count": cjk,
            "longest_cjk_run": run, "cjk_ratio": ratio, "i1a_hit": hit}


# ---- 고정된 것 -----------------------------------------------------------

def test_only_three_frozen_rules_are_evaluated():
    assert set(A.RULES) == {"baseline", "primary", "fallback"}
    import i1_detector_dev as D
    assert A.RULES["primary"] == D.FROZEN_PRIMARY
    assert A.RULES["fallback"] == D.FROZEN_FALLBACK


def test_no_tuning_knobs_in_the_api():
    """결과를 보고 조정할 손잡이를 남기지 않는다."""
    params = set(inspect.signature(A.analyze).parameters)
    for bad in ("threshold", "r", "t", "grid", "tune", "floor", "adjust"):
        assert bad not in params, bad


def test_carried_over_strata_are_declared():
    assert A.CARRIED_OVER_STRATA == ("C1", "C4", "C5")
    assert A.FRESH_STRATA == ("C0", "C2")


# ---- 라벨 완결성 ---------------------------------------------------------

def test_incomplete_a_labels_are_refused():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    with pytest.raises(A.AnalysisError, match="A 라벨"):
        A.analyze(rows, {"V001": ""}, {}, FRESH_POP)


def test_missing_b_label_for_cjk_text_present_is_refused():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    with pytest.raises(A.AnalysisError, match="B 라벨"):
        A.analyze(rows, {"V001": "cjk_text_present"}, {}, FRESH_POP)


def test_c0_needs_no_human_label():
    """C0은 `cjk_count == 0` 파생 규칙으로 처리한다(보충2)."""
    rows = [_inst("V001", "C0", 0, 0, 0.0)]
    r = A.analyze(rows, {}, {}, {"C0": 8114})
    assert r["fresh_strata_only"]["baseline"]["by_cell"]["C0"]["drift"] == 0


# ---- fresh / carried-over 분리 -------------------------------------------

def test_fresh_and_carried_over_are_separate_blocks():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP)
    assert "fresh_strata_only" in r
    assert r["fresh_strata_only"]["contains_carried_over"] is False
    assert "combined_with_carried_over" not in r      # carried 자료를 안 줬으면 없다


def test_combined_block_is_flagged_and_lists_carried_strata():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    carried = {"C4": {"population": 78, "analyzable": 68, "drift": 68,
                      "tp": {"baseline": 68, "primary": 68, "fallback": 67}}}
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP,
                  carried=carried)
    c = r["combined_with_carried_over"]
    assert c["contains_carried_over"] is True
    assert c["carried_over_strata"] == ["C4"]
    assert "재검증되지" in c["note"] or "not re-validated" in c["note"]


def test_output_never_claims_full_freshness():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    carried = {"C4": {"population": 78, "analyzable": 68, "drift": 68,
                      "tp": {"baseline": 68, "primary": 68, "fallback": 67}}}
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP,
                  carried=carried)
    flat = str(r)
    for bad in ("fully_fresh", "fully fresh", "all_fresh", "완전히 fresh"):
        assert bad not in flat, bad


def test_source_module_forbids_full_freshness_naming():
    body = (ROOT / "docs" / "probes" / "i1_validation_analysis.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("fully_fresh", "all_fresh"):
        assert bad not in body, bad


# ---- 재현 게이트 ---------------------------------------------------------

def test_reproduction_gate_refuses_mismatch():
    """carried-over 성분이 development 공표값을 재현하지 못하면 중단한다."""
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    carried = {"C4": {"population": 78, "analyzable": 68, "drift": 68,
                      "tp": {"baseline": 60, "primary": 68, "fallback": 67}}}
    with pytest.raises(A.AnalysisError, match="재현"):
        A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP,
                  carried=carried, published_carried_tp={"baseline": 71})


def test_reproduction_gate_passes_and_is_recorded():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    carried = {"C4": {"population": 78, "analyzable": 68, "drift": 68,
                      "tp": {"baseline": 68, "primary": 68, "fallback": 67}},
               "C5": {"population": 3, "analyzable": 3, "drift": 3,
                      "tp": {"baseline": 3, "primary": 3, "fallback": 3}}}
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP,
                  carried=carried, published_carried_tp={"baseline": 71})
    assert r["reproduction_check"]["match"] is True


# ---- primary / fallback 해소 ---------------------------------------------

def test_primary_fallback_resolution_is_simple_rule():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP)
    p = r["primary_vs_fallback"]
    assert p["separable_on_fresh_data"] is False
    assert p["resolution"] == "simple_rule_preference"
    assert "R_only" in p["resolved_to"]


def test_c4_census_is_not_used_to_separate_candidates():
    body = (ROOT / "docs" / "probes" / "i1_validation_analysis.py").read_text(
        encoding="utf-8")
    seg = body.split("primary_vs_fallback")[1][:600]
    assert "C4" not in seg or "쓰지 않는다" in seg or "안 쓴다" in seg


# ---- 지표 --------------------------------------------------------------

def test_both_precisions_and_wilson_are_reported():
    rows = [_inst("V001", "C2", 2, 2, 0.02), _inst("V002", "C2", 2, 2, 0.02)]
    a = {"V001": "korean_text_only", "V002": "cjk_text_present"}
    b = {"V002": "matches_screen"}
    r = A.analyze(rows, a, b, FRESH_POP)
    m = r["fresh_strata_only"]["primary"]
    assert "precision_sample" in m and "precision_weighted" in m
    assert "precision_ci_wilson" in m
    assert r["ci_interpretation"] == "descriptive_only"


def test_wilson_is_declared_descriptive_with_cluster_caveat():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP)
    assert "클러스터" in r["limits"] or "cluster" in r["limits"]


def test_c2_is_reported_separately():
    rows = [_inst("V001", "C2", 2, 2, 0.02), _inst("V002", "C0", 0, 0, 0.0)]
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP)
    assert set(r["fresh_strata_only"]["primary"]["by_cell"]) == {"C0", "C2"}


def test_fp_accounting_invariant_holds():
    rows = [_inst("V001", "C2", 2, 2, 0.02), _inst("V002", "C2", 2, 2, 0.02)]
    a = {"V001": "cjk_text_present", "V002": "korean_text_only"}
    b = {"V001": "matches_screen"}
    r = A.analyze(rows, a, b, FRESH_POP)
    m = r["fresh_strata_only"]["primary"]
    assert m["n_fired"] - m["n_tp"] == (sum(m["fp_breakdown"].values())
                                       + sum(m["fp_outside_declared"].values()))


def test_no_verdict_or_adoption_keys():
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP)
    flat = str(sorted(r.keys()))
    for bad in ("verdict", "adopt", "winner", "promote", "recommendation"):
        assert bad not in flat, bad


def test_cli_output_is_ascii_safe():
    src = (ROOT / "docs" / "probes" / "i1_validation_analysis.py").read_text(
        encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line


# ---- 보충4: combined precision 제거 · 게이트 CLI 배선 ----------------------

def test_combined_block_omits_precision():
    """carried 셀 FP를 0으로 가정하는 구현이었다 — 고쳐서 남기지 않고 지운다."""
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    carried = {"C4": {"population": 78, "analyzable": 68, "drift": 68,
                      "tp": {"baseline": 68, "primary": 68, "fallback": 67}}}
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP,
                  carried=carried)
    c = r["combined_with_carried_over"]
    for name in A.RULES:
        assert "precision_weighted" not in c[name], name
        assert "est_fired" not in c[name], name
        assert "recall_est" in c[name]
    assert c["precision_omitted"]


def test_primary_evidence_block_is_declared_fresh_only():
    """판정 근거 블록을 산출물에 박는다. **판정 자체를 내리지는 않는다** —
    키 이름에 `verdict`를 쓰지 않는 기존 계약과 양립해야 한다."""
    rows = [_inst("V001", "C2", 2, 2, 0.02)]
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP)
    assert r["primary_evidence_block"] == "fresh_strata_only"
    assert "rule-expansion" in r["precision_name"]


def test_fresh_precision_is_ratio_of_estimated_totals_not_cell_average():
    """C0은 `n_fired == 0`이다 — 층별 precision 평균이면 0/0 대입이 판정을 정한다."""
    rows = [_inst("V001", "C2", 2, 2, 0.02), _inst("V002", "C0", 0, 0, 0.0)]
    r = A.analyze(rows, {"V001": "korean_text_only"}, {}, FRESH_POP)
    m = r["fresh_strata_only"]["primary"]
    assert m["by_cell"]["C0"]["est_fired"] == 0.0
    assert m["precision_weighted"] == round(m["est_tp"] / m["est_fired"], 4)


def test_published_carried_baseline_is_a_module_constant():
    assert A.PUBLISHED_CARRIED_TP == {"baseline": 71}


def test_cli_wires_the_reproduction_gate():
    """`--carried`만 주고 게이트 없이 combined를 내는 경로가 없어야 한다."""
    src = (ROOT / "docs" / "probes" / "i1_validation_analysis.py").read_text(
        encoding="utf-8")
    call = src.split("r = A.analyze")[-1] if "r = A.analyze" in src else src
    body = src.split("def main()")[1]
    assert "PUBLISHED_CARRIED_TP" in body
