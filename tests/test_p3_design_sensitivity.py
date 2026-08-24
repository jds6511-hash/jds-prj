"""P3 outcome-blind 설계 민감도 — 계약 테스트.

목적은 "정밀도 목표 ↔ 필요한 라벨 행 수"를 숫자로 보여주는 것뿐이다. 설계를 자동으로
고르지 않고, P3 자료를 만들지도 열지도 않는다.
"""
import ast
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p3_design_sensitivity as D     # noqa: E402


# ---- 산식 ------------------------------------------------------------------

def test_required_k_matches_closed_form():
    hw, m, s2b, s2w = 0.05, 5, 0.01, 0.16
    k = D.required_k(hw, m, s2b, s2w)
    want = math.ceil(D.Z95 ** 2 * (s2b + s2w / m) / hw ** 2)
    assert k == want


def test_smaller_half_width_needs_more_rows():
    a = D.required_k(0.06, 5, 0.0, 0.16) * 5
    b = D.required_k(0.04, 5, 0.0, 0.16) * 5
    assert b > a


def test_total_rows_constant_in_m_when_icc_zero():
    """ICC=0이면 총 행 수가 m과 (반올림 오차 빼고) 무관하다 — 중요한 성질이다."""
    totals = [D.required_k(0.05, m, 0.0, 0.16) * m for m in (3, 4, 5, 6, 9)]
    assert max(totals) - min(totals) <= max(3, 9)


def test_total_rows_grows_with_m_when_icc_positive():
    lo = D.required_k(0.05, 3, 0.02, 0.14) * 3
    hi = D.required_k(0.05, 9, 0.02, 0.14) * 9
    assert hi > lo


def test_required_k_rejects_nonpositive_target():
    with pytest.raises(D.DesignError):
        D.required_k(0.0, 5, 0.0, 0.16)


def test_required_k_rejects_bad_m():
    with pytest.raises(D.DesignError):
        D.required_k(0.05, 0, 0.0, 0.16)


# ---- 표 --------------------------------------------------------------------

def test_table_covers_declared_targets_and_grid():
    rows = D.design_table(0.0, 0.16)
    assert {r["half_width_target"] for r in rows} == set(D.TARGETS)
    assert {r["queries_per_video"] for r in rows} == set(D.M_GRID)
    for r in rows:
        assert r["total_gt_rows"] == r["video_clusters"] * \
            r["queries_per_video"]


def test_table_includes_p2_target_as_candidate():
    assert 0.04 in D.TARGETS


def test_table_marks_low_cluster_designs():
    """cluster가 적으면 bootstrap이 기술 통계로 떨어진다 — 표에 드러나야 한다."""
    rows = D.design_table(0.0, 0.001)          # 분산이 작아 k가 작게 나온다
    assert any(r["cluster_warning"] for r in rows)


# ---- 보고서 ----------------------------------------------------------------

def test_report_has_both_channels():
    r = D.report()
    assert set(r["channels"]) == {"rr_fus_alpha_0_5", "rr_cap_alpha_0_0"}


def test_report_primary_channel_is_fusion():
    r = D.report()
    assert r["primary_channel"] == "rr_fus_alpha_0_5"
    assert r["key_secondary_channel"] == "rr_cap_alpha_0_0"


def test_report_does_not_choose_a_design():
    r = D.report()
    assert r["decision"] == "사용자_승인_사항"
    assert "recommended_design" not in r
    assert r["auto_selection"] is False


def test_report_does_not_inherit_p2_threshold():
    r = D.report()
    assert r["p2_half_width_target"] == 0.04
    assert r["p2_target_auto_inherited"] is False


def test_report_lists_limitations():
    r = D.report()
    assert len(r["limitations"]) >= 6
    joined = " ".join(r["limitations"])
    assert "12" in joined            # 후보 풀 규모 차이
    assert "bf16" in joined          # 정밀도 차이


def test_report_records_historical_source():
    r = D.report()
    assert "aihub_caption_2x2_full_2026-08-17.json" in r["historical_source"]
    assert r["sample_reuse_note"]


def test_report_records_bootstrap_convention_with_source():
    r = D.report()
    b = r["reused_conventions"]["bootstrap_B"]
    assert b["value"] == 2000 and b["source"]


def test_report_defers_seed():
    r = D.report()
    assert r["bootstrap_seed"] == "prereg_freeze_시_결정"


def test_report_defers_noninferiority_margin():
    r = D.report()
    assert r["noninferiority_margin_delta"] == "P3-C 미선택 — defer"


def test_variance_components_are_measured_not_assumed():
    r = D.report()
    for ch in r["channels"].values():
        v = ch["variance_decomposition"]
        assert v["n"] == 1086 and v["k"] == 194
        assert v["sigma2_within"] > 0


def test_icc_scenarios_are_labelled_as_assumptions():
    r = D.report()
    for ch in r["channels"].values():
        assert ch["icc_scenarios_note"]
        assert {s["assumed_icc"] for s in ch["icc_scenarios"]} == set(D.ICC_GRID)


# ---- P3 자료를 만들지도 열지도 않는다 ---------------------------------------

# ---- CI 부호 판정의 산식 ---------------------------------------------------

def test_min_confirmable_effect_equals_half_width():
    """CI로 0 배제를 보장하려면 |Δ|가 half-width를 넘어야 한다."""
    assert D.min_confirmable_effect(0.04) == 0.04
    assert D.min_confirmable_effect(0.06) == 0.06


def test_effect_smaller_than_half_width_is_not_confirmable():
    assert D.confirmable(0.0191, half_width=0.04) is False
    assert D.confirmable(0.0764, half_width=0.04) is True


def test_rows_for_effect_grows_as_effect_shrinks():
    big = D.rows_for_effect(0.08, 0.0, 0.142003, m=5)["total_gt_rows"]
    small = D.rows_for_effect(0.019, 0.0, 0.142003, m=5)["total_gt_rows"]
    assert small > big * 5


def test_rows_for_effect_matches_required_k():
    r = D.rows_for_effect(0.05, 0.0, 0.16, m=4)
    assert r["video_clusters"] == D.required_k(0.05, 4, 0.0, 0.16)


def test_report_illustrations_are_endpoint_separated():
    r = D.report()
    ill = r["historical_effect_illustrations"]
    assert set(ill) == {"rr_fus_alpha_0_5", "rr_cap_alpha_0_0"}
    fus = {e["sample"]: e for e in ill["rr_fus_alpha_0_5"]}
    cap = {e["sample"]: e for e in ill["rr_cap_alpha_0_0"]}
    assert fus["aihub"]["delta"] == 0.0191
    assert cap["aihub"]["delta"] == 0.0310
    assert fus["dev"]["delta"] == -0.0764
    assert cap["dev"]["delta"] == -0.0903
    for e in ill["rr_fus_alpha_0_5"] + ill["rr_cap_alpha_0_0"]:
        assert e["source"]


def test_report_does_not_claim_small_positive_is_confirmable_at_004():
    r = D.report()
    rows = [x for x in r["confirmability"]
            if x["half_width_target"] == 0.04
            and x["channel"] == "rr_fus_alpha_0_5"]
    small = [x for x in rows if abs(x["delta"]) < 0.04]
    assert small and all(x["confirmable"] is False for x in small)


def test_confirmability_reports_rows_needed_for_each_effect():
    r = D.report()
    e = [x for x in r["confirmability"]
         if x["channel"] == "rr_fus_alpha_0_5" and x["delta"] == 0.0191][0]
    assert e["total_gt_rows_to_confirm"] > 1000


# ---- 표본 규모 driver: PRIMARY 주도 vs 양쪽 동일 정밀도 ----------------------

def test_sample_size_options_has_two_variants():
    r = D.report()
    opts = r["sample_size_options"]
    assert set(opts) == {"A_primary_driven", "B_primary_and_secondary"}
    # A안 동결 후에도 두 안을 나란히 남긴다 — 무엇을 고르지 않았는지가 기록이다
    assert r["sample_size_driver"] == "PRIMARY"


def test_option_a_is_sized_by_primary_only():
    r = D.report()
    a = [x for x in r["sample_size_options"]["A_primary_driven"]
         if x["half_width_target"] == 0.04 and x["queries_per_video"] == 5][0]
    prim = [x for x in
            r["channels"][D.PRIMARY_CHANNEL]["design_table"]
            if x["half_width_target"] == 0.04 and x["queries_per_video"] == 5][0]
    assert a["video_clusters"] == prim["video_clusters"]
    assert a["secondary_achieved_half_width"] > 0.04


def test_option_b_is_never_smaller_than_option_a():
    r = D.report()
    a = {(x["half_width_target"], x["queries_per_video"]): x
         for x in r["sample_size_options"]["A_primary_driven"]}
    b = {(x["half_width_target"], x["queries_per_video"]): x
         for x in r["sample_size_options"]["B_primary_and_secondary"]}
    assert set(a) == set(b)
    for key in a:
        assert b[key]["total_gt_rows"] >= a[key]["total_gt_rows"]


def test_secondary_is_not_co_primary_in_report():
    r = D.report()
    assert r["secondary_is_co_primary"] is False
    assert r["secondary_precision_rule_approved"] is False


# ---- ICC robustness -------------------------------------------------------

def test_icc_robustness_shows_degradation_of_icc0_designs():
    r = D.report()
    rob = r["channels"][D.PRIMARY_CHANNEL]["icc_robustness"]
    row = [x for x in rob if x["assumed_icc"] == 0.10
           and x["half_width_target"] == 0.05]
    by_m = {x["queries_per_video"]: x for x in row}
    # ICC=0으로 잡은 설계를 ICC>0 세계에 놓으면 정밀도가 나빠지고,
    # m이 큰(영상 수가 적은) 설계가 더 크게 나빠진다
    assert by_m[9]["achieved_half_width_if_icc_true"] > \
        by_m[3]["achieved_half_width_if_icc_true"]
    assert by_m[9]["achieved_half_width_if_icc_true"] > 0.05


def test_icc_robustness_reports_required_rows_under_assumed_icc():
    r = D.report()
    rob = r["channels"][D.PRIMARY_CHANNEL]["icc_robustness"]
    for x in rob:
        assert x["total_gt_rows_under_assumed_icc"] >= x["total_gt_rows_icc0"]


def test_icc_robustness_is_labelled_diagnostic_not_prediction():
    r = D.report()
    assert r["icc_robustness_note"]
    assert "예측" in r["icc_robustness_note"]
    assert r["icc_zero_assumed_as_truth"] is False


# ---- 채택 기준 항목 --------------------------------------------------------

def test_report_carries_the_frozen_adoption_criterion():
    r = D.report()
    assert r["minimum_deployment_relevant_gain"] == 0.02
    assert r["adoption_utility_note"]


def test_module_reads_only_historical_artifact():
    src = (ROOT / "scripts" / "p3_design_sensitivity.py").read_text(
        encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m5_search", "m6_evaluate", "p2_retrieve", "p2_evaluate",
                 "torch", "transformers"} & mods)


def test_module_has_no_write_path_to_p3_data():
    src = (ROOT / "scripts" / "p3_design_sensitivity.py").read_text(
        encoding="utf-8")
    assert "p2_queries_staging" not in src
    assert "results_p3" not in src


def test_artifact_matches_module_output():
    """추적 중인 산출물이 현재 코드의 결과와 같다."""
    p = ROOT / "docs" / "P3_설계민감도_2026-08-24.json"
    if not p.is_file():
        pytest.skip("산출물이 아직 없다")
    saved = json.loads(p.read_text(encoding="utf-8"))
    now = D.report()
    assert saved["channels"]["rr_fus_alpha_0_5"]["design_table"] == \
        now["channels"]["rr_fus_alpha_0_5"]["design_table"]


# ---- 동결된 결정 (사용자 결정, 결과 열람 전) --------------------------------

def test_targets_include_frozen_policy_threshold():
    """정책 임계 0.02가 설계표에 들어간다."""
    assert 0.02 in D.TARGETS


def test_required_k_matches_frozen_design_math():
    """ICC=0 근사·PRIMARY σ²_w로 hw 0.02·m 5의 수학적 최소는 273편이다."""
    assert D.required_k(0.02, 5, 0.0, 0.142003) == 273


def test_frozen_decision_records_the_design():
    r = D.report()
    f = r["frozen_decision"]
    assert f["video_clusters"] == 300
    assert f["queries_per_video"] == 5
    assert f["total_gt_rows"] == 1500
    assert f["sample_size_driver"] == "PRIMARY"
    assert f["minimum_deployment_relevant_gain"] == 0.02
    assert f["primary_half_width_target"] == 0.02


def test_frozen_min_gain_is_a_policy_threshold_not_a_measured_constant():
    """+0.02는 데이터가 알려준 상수가 아니라 배포 정책 임계다."""
    f = D.report()["frozen_decision"]
    assert f["gain_kind"] == "deployment_policy_threshold"
    assert f["gain_is_measured_constant"] is False
    assert f["decided_before_outcome_access"] is True


def test_frozen_design_targets_a_half_width_below_the_threshold():
    """300×5는 diagnostic 근사에서 0.019급을 목표로 한다 — 검출 보장이 아니다."""
    f = D.report()["frozen_decision"]
    assert f["primary_projected_half_width"] < 0.02
    assert round(f["primary_projected_half_width"], 4) == 0.0191
    assert f["math_minimum_video_clusters"] == 273
    assert f["math_minimum_total_gt_rows"] == 1365
    assert "보장" in f["precision_claim_rule"]


def test_frozen_design_does_not_force_secondary_precision():
    """α=0.0은 mandatory key secondary — 같은 정밀도를 맞추려고 N을 키우지 않는다."""
    f = D.report()["frozen_decision"]
    assert f["secondary_forced_to_same_half_width"] is False
    assert f["secondary_projected_half_width"] > f[
        "primary_projected_half_width"]
    assert f["secondary_reported_always"] is True
    assert "rescue" in f["secondary_role_rule"]


def test_frozen_design_forbids_outcome_driven_topup():
    f = D.report()["frozen_decision"]
    assert f["topup_after_results_allowed"] is False


def test_frozen_design_records_m_rationale():
    f = D.report()["frozen_decision"]
    assert "9" in f["m_rationale"] and "3" in f["m_rationale"]
    assert "ICC" in f["m_rationale"]


def test_frozen_labeling_route_is_external_annotator():
    f = D.report()["frozen_decision"]
    assert f["labeling_route"] == "external_human_annotator"
    assert f["scene_only_ai_route_used_for_p3a"] is False


def test_execution_remains_hold_with_annotation_blocker():
    f = D.report()["frozen_decision"]
    assert f["p3a_execution"] == "HOLD"
    assert f["blocking_item"] == "annotation_logistics"


def test_report_replaces_user_decision_placeholders():
    r = D.report()
    assert r["sample_size_driver"] == "PRIMARY"
    assert r["minimum_deployment_relevant_gain"] == 0.02
