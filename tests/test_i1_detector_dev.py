"""I1 detector development 탐색 — 격자·선택 규칙·종료 규칙을 결과 보기 전에 고정.

막는 것 셋.
1. 격자·제약을 결과 보고 바꾸는 것
2. 새 추정량이 현행 estimator를 잘못 재사용하는 것 — 새 규칙은 표집 셀에서도
   발동하므로 적중을 전수로 취급할 수 없다
3. 같은 development set에서 우열을 주장하는 것
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import i1_detector_dev as D                                    # noqa: E402

# 셀 모집단은 실제 표집틀과 같은 구조 — 전수 셀과 표집 셀이 섞여 있다
POP = {"C0": 8430, "C1": 1, "C2": 800, "C4": 78, "C5": 3}


def _inst(sid, cell, cjk, run, ratio, true):
    return {"sample_id": sid, "cell": cell, "cjk_count": cjk,
            "longest_cjk_run": run, "cjk_ratio": ratio, "true": true,
            "cell_population": POP[cell]}


# ---- 격자·상수 고정 ------------------------------------------------------

def test_grid_is_frozen():
    assert D.R_GRID == (2, 3, 4, 5, 6)
    assert D.T_GRID == (0.02, 0.05, 0.10, 0.15, 0.20)
    assert D.COMBINERS == ("R_only", "T_only", "R_or_T", "R_and_T")
    assert len(list(D.grid())) == 60


def test_precision_constraint_is_frozen():
    assert D.PRECISION_FLOOR == 0.95
    assert D.MAX_CANDIDATES == 2


def test_absolute_count_axis_is_absent():
    """개수 축을 넣으면 현행 규칙의 변형 탐색이 된다 — 대조군으로만 등장한다."""
    src = (ROOT / "docs" / "probes" / "i1_detector_dev.py").read_text(
        encoding="utf-8")
    body = src.split('"""', 2)[2]
    assert "N_GRID" not in body and "COUNT_GRID" not in body
    for cfg in D.grid():
        assert set(cfg) <= {"combiner", "R", "T"}


def test_baseline_is_the_current_rule():
    """현행 대조군은 cjk_count >= 3 OR cjk_ratio > 0.2다."""
    assert D.baseline_fires({"cjk_count": 3, "cjk_ratio": 0.01,
                             "longest_cjk_run": 1}) is True
    assert D.baseline_fires({"cjk_count": 1, "cjk_ratio": 0.25,
                             "longest_cjk_run": 1}) is True
    assert D.baseline_fires({"cjk_count": 2, "cjk_ratio": 0.1,
                             "longest_cjk_run": 2}) is False


# ---- 두 축 분리 ----------------------------------------------------------

def test_foreign_script_present_has_no_parameters():
    assert D.foreign_script_present({"cjk_count": 1}) is True
    assert D.foreign_script_present({"cjk_count": 0}) is False
    import inspect
    assert set(inspect.signature(D.foreign_script_present).parameters) == {"inst"}


def test_no_cjk_can_never_fire_any_candidate():
    """구조적 사실 — FP는 CJK가 있는 인스턴스에서만 나온다."""
    zero = {"cjk_count": 0, "longest_cjk_run": 0, "cjk_ratio": 0.0}
    for cfg in D.grid():
        assert D.fires(zero, cfg) is False
    assert D.baseline_fires(zero) is False


def test_combiners_behave_as_named():
    i = {"cjk_count": 5, "longest_cjk_run": 3, "cjk_ratio": 0.03}
    assert D.fires(i, {"combiner": "R_only", "R": 3, "T": None}) is True
    assert D.fires(i, {"combiner": "R_only", "R": 4, "T": None}) is False
    assert D.fires(i, {"combiner": "T_only", "R": None, "T": 0.02}) is True
    assert D.fires(i, {"combiner": "T_only", "R": None, "T": 0.05}) is False
    assert D.fires(i, {"combiner": "R_or_T", "R": 4, "T": 0.02}) is True
    assert D.fires(i, {"combiner": "R_and_T", "R": 4, "T": 0.02}) is False
    assert D.fires(i, {"combiner": "R_and_T", "R": 3, "T": 0.02}) is True


# ---- 추정량: 새 규칙은 적중이 전수가 아니다 -------------------------------

def test_tp_is_population_weighted_not_census():
    """C2(모집단 800, 표집 24)에서 발동한 TP를 표본 수로 세면 안 된다.

    C4는 전수 78, C2는 800중 1건 표집. 두 셀에서 각각 drift 1건을 잡았을 때
    가중 TP는 78과 800으로 크게 다르다 — 같은 1건으로 세면 C2를 지운다.
    """
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift"),
            _inst("b", "C2", 2, 2, 0.02, "drift")]
    cfg = {"combiner": "R_only", "R": 2, "T": None}
    m = D.evaluate(rows, cfg, POP)
    assert m["est_tp"] == pytest.approx(78 + 800, abs=1e-6)
    assert m["est_drift_total"] == pytest.approx(78 + 800, abs=1e-6)
    assert m["recall_est"] == pytest.approx(1.0)


def test_recall_denominator_uses_all_drift_not_only_fired():
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift"),      # 발동
            _inst("b", "C2", 2, 1, 0.02, "drift")]     # 미발동 (run 1 < 2)
    cfg = {"combiner": "R_only", "R": 2, "T": None}
    m = D.evaluate(rows, cfg, POP)
    assert m["est_tp"] == pytest.approx(78)
    assert m["est_drift_total"] == pytest.approx(878)
    assert m["recall_est"] == pytest.approx(78 / 878, abs=1e-4)


def test_both_precisions_are_reported_and_differ():
    """비가중은 전수 셀이, 가중은 C2가 지배한다 — 하나만 보면 오독한다."""
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift"),
            _inst("b", "C4", 5, 5, 0.1, "scene_text"),
            _inst("c", "C2", 2, 2, 0.02, "drift")]
    cfg = {"combiner": "R_only", "R": 2, "T": None}
    m = D.evaluate(rows, cfg, POP)
    assert m["precision_sample"] == pytest.approx(2 / 3, abs=1e-4)
    # 가중: 발동 모집단 78 + 800, TP 39 + 800  (C4 표본 2건 중 1건이 drift)
    assert m["precision_weighted"] == pytest.approx((39 + 800) / (78 + 800), abs=1e-4)
    assert m["precision_sample"] != m["precision_weighted"]


def test_excluded_unclear_is_dropped_from_both_numerator_and_denominator():
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift"),
            _inst("b", "C4", 5, 5, 0.1, "excluded_unclear")]
    cfg = {"combiner": "R_only", "R": 2, "T": None}
    m = D.evaluate(rows, cfg, POP)
    assert m["n_analyzable"] == 1
    assert m["n_excluded_unclear"] == 1
    assert m["precision_sample"] == pytest.approx(1.0)


def test_derived_cell_contributes_zero_drift_not_nan():
    rows = [_inst("z", "C0", 0, 0, 0.0, "not_cjk_drift"),
            _inst("a", "C4", 5, 5, 0.1, "drift")]
    cfg = {"combiner": "R_only", "R": 2, "T": None}
    m = D.evaluate(rows, cfg, POP)
    assert m["est_drift_total"] == pytest.approx(78)
    assert m["by_cell"]["C0"]["est_drift"] == 0.0
    assert m["by_cell"]["C0"]["uncertainty"] == "none_by_derivation"


def test_c2_leak_zone_is_reported_separately():
    """CJK 1-2자 영역을 전체 recall 하나로 뭉개지 않는다."""
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift"),
            _inst("b", "C2", 2, 2, 0.02, "drift")]
    m = D.evaluate(rows, {"combiner": "R_only", "R": 3, "T": None}, POP)
    c2 = m["by_cell"]["C2"]
    assert c2["est_drift"] == pytest.approx(800)
    assert c2["est_tp"] == pytest.approx(0.0)               # run 2 < 3 → 미발동
    assert c2["recall_est"] == pytest.approx(0.0)


# ---- 전수 셀은 스케일링하지 않는다 ---------------------------------------

def test_census_cell_is_not_population_scaled():
    """전수 셀에서 `pop / analyzable`로 곱하면 unclear를 관측률로 대입한 것이 된다.

    C4는 모집단 78 = 표집 78이다. unclear 1건이 있으면 analyzable 77이고,
    78 × (drift/77)로 곱하면 **관측하지 않은 1건을 drift로 대입**해 개수가
    부풀려진다. 전수 셀은 원 개수를 쓴다.
    """
    rows = [_inst(f"a{i}", "C4", 5, 5, 0.1, "drift") for i in range(77)]
    rows.append(_inst("x", "C4", 5, 5, 0.1, "excluded_unclear"))
    m = D.evaluate(rows, {"combiner": "R_only", "R": 2, "T": None},
                   {"C4": 78}, census={"C4"})
    assert m["est_drift_total"] == pytest.approx(77.0)          # 78이 아니다
    assert m["by_cell"]["C4"]["is_census"] is True


def test_sampled_cell_is_population_scaled():
    rows = [_inst("a", "C2", 2, 2, 0.02, "drift")]
    m = D.evaluate(rows, {"combiner": "R_only", "R": 2, "T": None},
                   {"C2": 800}, census=set())
    assert m["est_drift_total"] == pytest.approx(800.0)
    assert m["by_cell"]["C2"]["is_census"] is False


def test_census_set_is_derived_from_sampled_vs_population():
    assert D.census_cells({"C4": 78, "C2": 800},
                          {"C4": 78, "C2": 24}) == {"C4"}


# ---- 대조군은 현행 detector 전체다 ---------------------------------------

def test_baseline_uses_full_current_detector_not_cjk_only():
    """현행 detector는 CJK 규칙 **또는** 반복 규칙이다.

    C1(CJK 0인데 적중)은 반복 규칙에서 나왔다. 대조군을 CJK 규칙만으로 세우면
    그 적중이 사라져 대조군 precision이 실제보다 좋아 보인다.
    """
    rep_only = {"cjk_count": 0, "longest_cjk_run": 0, "cjk_ratio": 0.0,
                "i1a_hit": True}
    assert D.baseline_fires(rep_only) is True                   # 반복으로 적중
    assert D.repetition_component(rep_only) is True
    cjk_hit = {"cjk_count": 5, "longest_cjk_run": 5, "cjk_ratio": 0.1,
               "i1a_hit": True}
    assert D.repetition_component(cjk_hit) is False


def test_candidate_keeps_repetition_component():
    """재설계 후 배포 규칙은 `language_drift(CJK) OR 반복`이다 — 비교 대상이 같아야 한다."""
    rep_only = {"cjk_count": 0, "longest_cjk_run": 0, "cjk_ratio": 0.0,
                "i1a_hit": True}
    cfg = {"combiner": "R_only", "R": 2, "T": None}
    assert D.fires(rep_only, cfg) is False                      # CJK 축은 미발동
    assert D.fires_total(rep_only, cfg) is True                 # 반복은 유지된다


# ---- 대조군 재현 게이트 --------------------------------------------------

def test_baseline_reproduction_gate_refuses_mismatch():
    """대조군이 공표값을 재현하지 못하면 추정량이 틀린 것이다."""
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift")]
    for r in rows:
        r["i1a_hit"] = True
    with pytest.raises(D.DevError, match="재현"):
        D.run(rows, {"C4": 78}, census={"C4"},
              published={"precision_sample": 0.9861, "recall_est": 0.0815})


# ---- false positive 범주 -------------------------------------------------

def test_fp_categories_are_predeclared():
    assert D.FP_CATEGORIES == ("scene_text", "normal_foreign_expression")
    assert D.FP_UNSEPARABLE == ("normal_foreign_expression",)


def test_fp_outside_declared_categories_is_not_silently_dropped():
    """선언 범주 밖의 FP도 개수를 남긴다 — 사라지면 사람이 못 본다.

    실제 사례: C1(CJK 0인데 반복 규칙으로 적중)은 `not_cjk_drift`라 선언한 두
    범주에 없다. 범주로 걸러 버리면 FP 1건이 회계에서 없어진다.
    """
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift"),
            _inst("r", "C1", 0, 0, 0.0, "not_cjk_drift")]
    rows[1]["i1a_hit"] = True                                # 반복 규칙 적중
    m = D.evaluate(rows, {"combiner": "R_only", "R": 2, "T": None}, POP)
    assert m["fp_breakdown"] == {}                            # 선언 범주에는 없다
    assert m["fp_outside_declared"] == {"not_cjk_drift": 1}
    assert m["n_fired"] - m["n_tp"] == (sum(m["fp_breakdown"].values())
                                       + sum(m["fp_outside_declared"].values()))


def test_fp_breakdown_only_uses_declared_categories():
    rows = [_inst("b", "C4", 5, 5, 0.1, "scene_text"),
            _inst("a", "C4", 5, 5, 0.1, "drift")]
    m = D.evaluate(rows, {"combiner": "R_only", "R": 2, "T": None}, POP)
    assert set(m["fp_breakdown"]) <= set(D.FP_CATEGORIES)
    assert m["fp_breakdown"]["scene_text"] == 1


# ---- 선택 규칙 -----------------------------------------------------------

def test_selection_respects_precision_floor():
    """제약을 만족하지 않는 구성은 recall이 아무리 높아도 후보가 아니다."""
    cands = D.select([
        {"config": {"combiner": "R_only", "R": 2, "T": None},
         "recall_est": 0.9, "precision_weighted": 0.90},
        {"config": {"combiner": "R_only", "R": 3, "T": None},
         "recall_est": 0.4, "precision_weighted": 0.96}])
    assert len(cands) == 1
    assert cands[0]["config"]["R"] == 3


def test_selection_returns_nothing_when_no_config_qualifies():
    """제약을 결과 보고 완화하지 않는다 — 빈 결과가 정답이다."""
    assert D.select([{"config": {"combiner": "R_only", "R": 2, "T": None},
                      "recall_est": 0.9, "precision_weighted": 0.5}]) == []


def test_selection_caps_candidate_count():
    rows = [{"config": {"combiner": "R_only", "R": r, "T": None},
             "recall_est": 0.5 - i * 0.01, "precision_weighted": 0.99}
            for i, r in enumerate(D.R_GRID)]
    assert len(D.select(rows)) == D.MAX_CANDIDATES


def test_tiebreak_prefers_simpler_rule_then_smaller_R_then_larger_T():
    rows = [{"config": {"combiner": "R_or_T", "R": 3, "T": 0.05},
             "recall_est": 0.5, "precision_weighted": 0.99},
            {"config": {"combiner": "R_only", "R": 4, "T": None},
             "recall_est": 0.5, "precision_weighted": 0.99}]
    assert D.select(rows)[0]["config"]["combiner"] == "R_only"

    rows = [{"config": {"combiner": "R_only", "R": 4, "T": None},
             "recall_est": 0.5, "precision_weighted": 0.99},
            {"config": {"combiner": "R_only", "R": 2, "T": None},
             "recall_est": 0.5, "precision_weighted": 0.99}]
    assert D.select(rows)[0]["config"]["R"] == 2

    rows = [{"config": {"combiner": "T_only", "R": None, "T": 0.05},
             "recall_est": 0.5, "precision_weighted": 0.99},
            {"config": {"combiner": "T_only", "R": None, "T": 0.15},
             "recall_est": 0.5, "precision_weighted": 0.99}]
    assert D.select(rows)[0]["config"]["T"] == 0.15


# ---- 금지 표현·종료 규칙 --------------------------------------------------

def test_output_forbids_superiority_language():
    src = (ROOT / "docs" / "probes" / "i1_detector_dev.py").read_text(
        encoding="utf-8")
    body = src.split('"""', 2)[2]
    for bad in ("개선됐", "우월", "improved", "better_than", "outperform"):
        assert bad not in body, bad


def test_output_declares_development_only():
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift")]
    r = D.run(rows, POP)
    assert r["stage"] == "development_only"
    assert "선택 근거" in r["limits"] or "성능 판정" in r["limits"]
    for bad in ("verdict", "winner", "adopted", "recommendation"):
        assert bad not in str(sorted(r.keys())), bad


def test_run_computes_every_grid_config_once_plus_baseline():
    rows = [_inst("a", "C4", 5, 5, 0.1, "drift"),
            _inst("b", "C2", 2, 2, 0.02, "drift")]
    r = D.run(rows, POP)
    assert len(r["grid_results"]) == 60
    assert r["baseline"]["config"] == ("current: is_corrupted_caption "
                                      "(CJK rule OR repetition rule)")
    keys = [str(x["config"]) for x in r["grid_results"]]
    assert len(set(keys)) == 60                              # 중복 계산 없음


def test_cli_output_is_ascii_safe():
    src = (ROOT / "docs" / "probes" / "i1_detector_dev.py").read_text(
        encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line
