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
