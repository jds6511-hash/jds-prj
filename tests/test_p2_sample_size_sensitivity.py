"""P2 표본 규모 민감도 — **P2 결과를 보지 않고, 과거 자료로만 진단한다.**

```
쓰는 자료   AI Hub 2x2의 캡션 단독 per-query RR (194영상 · 1,086질의)
안 쓰는 것  P2 retrieval · P2 arm 산출물 · P2 캡션 · p2_evaluate
판정        하지 않는다. 140/175/315 선택은 사용자 승인 사항이다
불변        half-width 목표 0.04 · PRIMARY · alpha · cluster bootstrap · exclusion
```

과거 자료가 P2의 정밀도를 보장하지 않는다. 후보 풀(12 vs 약 260)·도메인·정밀도
(bf16 vs 4bit)가 다르므로 **절대값이 아니라 m에 따른 상대 변화**로만 읽는다.
"""
import ast
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_sample_size_sensitivity as S                             # noqa: E402

SRC = (ROOT / "scripts" / "p2_sample_size_sensitivity.py").read_text(
    encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


def _fake_source(tmp_path, per_video, n_videos, base_rr=0.4, delta=0.05,
                 spread_between=0.0, spread_within=0.0, seed=0):
    rng = np.random.default_rng(seed)
    a, b = [], []
    for v in range(n_videos):
        vshift = spread_between * rng.standard_normal()
        n = per_video if isinstance(per_video, int) else per_video[v]
        for i in range(n):
            qid = f"q_{v:03d}_{i:02d}"
            row = {"query_id": qid, "video_id": f"v{v:03d}", "n_seg": 12}
            d = delta + vshift + spread_within * rng.standard_normal()
            a.append(dict(row, rr_cap=base_rr, rr_fus=0.9, rr_sub=0.9))
            b.append(dict(row, rr_cap=base_rr + d, rr_fus=0.1, rr_sub=0.1))
    p = tmp_path / "src.json"
    p.write_text(json.dumps({"per_query": {S.BASE_KEY: a, S.CAND_KEY: b}},
                            ensure_ascii=False), encoding="utf-8")
    return p


# ------------------------------------------------------------- 자료 적재

def test_paired_deltas_use_the_caption_only_channel(tmp_path):
    p = _fake_source(tmp_path, 3, 5, base_rr=0.4, delta=0.05)
    d = S.paired_deltas(p)
    assert len(d) == 15
    assert all(abs(r["delta"] - 0.05) < 1e-9 for r in d)   # rr_fus/rr_sub 무시


def test_mismatched_query_order_is_refused(tmp_path):
    p = _fake_source(tmp_path, 3, 4)
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["per_query"][S.CAND_KEY].reverse()
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(S.SensitivityError, match="짝"):
        S.paired_deltas(p)


def test_a_missing_arm_is_refused(tmp_path):
    p = _fake_source(tmp_path, 3, 4)
    doc = json.loads(p.read_text(encoding="utf-8"))
    del doc["per_query"][S.CAND_KEY]
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(S.SensitivityError, match=S.CAND_KEY):
        S.paired_deltas(p)


# ------------------------------------------------------------- 분산 분해

def test_decomposition_recovers_a_known_within_variance(tmp_path):
    p = _fake_source(tmp_path, 20, 60, spread_between=0.0, spread_within=0.30,
                     seed=1)
    r = S.decompose(S.paired_deltas(p))
    assert r["k"] == 60 and r["n"] == 1200
    assert 0.06 < r["sigma2_within"] < 0.12          # 참값 0.09
    assert r["sigma2_between"] < 0.01


def test_decomposition_recovers_a_known_between_variance(tmp_path):
    p = _fake_source(tmp_path, 20, 80, spread_between=0.20, spread_within=0.10,
                     seed=2)
    r = S.decompose(S.paired_deltas(p))
    assert 0.02 < r["sigma2_between"] < 0.07         # 참값 0.04
    assert r["icc"] > 0.5


def test_between_variance_is_clamped_at_zero_not_negative(tmp_path):
    p = _fake_source(tmp_path, 12, 40, spread_between=0.0, spread_within=0.5,
                     seed=3)
    r = S.decompose(S.paired_deltas(p))
    assert r["sigma2_between"] >= 0.0


def test_decomposition_needs_more_than_one_cluster(tmp_path):
    p = _fake_source(tmp_path, 9, 1)
    with pytest.raises(S.SensitivityError, match="cluster"):
        S.decompose(S.paired_deltas(p))


# ------------------------------------------------------------- 투사

def test_more_queries_per_cluster_narrows_the_projection():
    hw = [S.projected_half_width(0.02, 0.09, 35, m) for m in (4, 5, 9)]
    assert hw[0] > hw[1] > hw[2]


def test_more_clusters_narrows_the_projection():
    assert S.projected_half_width(0.02, 0.09, 35, 5) > \
           S.projected_half_width(0.02, 0.09, 70, 5)


def test_projection_is_flat_in_m_when_all_variance_is_between_cluster():
    a = S.projected_half_width(0.02, 0.0, 35, 4)
    b = S.projected_half_width(0.02, 0.0, 35, 9)
    assert abs(a - b) < 1e-12


def test_ratio_relative_to_the_current_design_is_at_least_one():
    r = S.half_width_ratios(0.02, 0.09, 35)
    assert r[9] == 1.0 and r[5] > 1.0 and r[4] > r[5]


# ------------------------------------------------------------- 경험적 재표집

def test_empirical_reports_unusable_when_too_few_eligible_clusters(tmp_path):
    p = _fake_source(tmp_path, 4, 60, spread_between=0.1, spread_within=0.2)
    r = S.empirical_half_widths(S.paired_deltas(p), m=9, k=35, replicates=5,
                                boot=50)
    assert r["usable"] is False
    assert r["eligible_clusters"] == 0
    assert "9" in r["reason"]


def test_empirical_returns_a_distribution_when_feasible(tmp_path):
    p = _fake_source(tmp_path, 9, 60, spread_between=0.1, spread_within=0.2,
                     seed=4)
    r = S.empirical_half_widths(S.paired_deltas(p), m=4, k=35, replicates=20,
                                boot=100)
    assert r["usable"] is True and r["eligible_clusters"] == 60
    assert r["median"] > 0 and r["p75"] >= r["median"] and r["p90"] >= r["p75"]


def test_empirical_is_reproducible(tmp_path):
    p = _fake_source(tmp_path, 9, 60, spread_between=0.1, spread_within=0.2,
                     seed=5)
    d = S.paired_deltas(p)
    a = S.empirical_half_widths(d, m=5, k=35, replicates=10, boot=80)
    b = S.empirical_half_widths(d, m=5, k=35, replicates=10, boot=80)
    assert a == b


def test_empirical_records_the_eligibility_selection_bias(tmp_path):
    p = _fake_source(tmp_path, [4] * 30 + [9] * 30, 60, spread_between=0.1,
                     spread_within=0.2, seed=6)
    r = S.empirical_half_widths(S.paired_deltas(p), m=9, k=25, replicates=5,
                                boot=50)
    assert r["usable"] is True
    assert r["eligible_clusters"] == 30 and r["total_clusters"] == 60
    assert "선택" in r["selection_note"]


# ------------------------------------------------------------- dev 사용 가능성

def test_dev_is_reported_unusable_with_a_reason():
    r = S.dev_usability()
    assert r["usable"] is False
    assert "per-query" in r["reason"] or "질의 단위" in r["reason"]
    assert r["clusters"] == 3


# ------------------------------------------------------------- 보고

def test_report_has_no_recommendation(tmp_path):
    p = _fake_source(tmp_path, 9, 60, spread_between=0.1, spread_within=0.2,
                     seed=7)
    rep = S.report(source=p, replicates=5, boot=50)
    assert rep["decision"] == "사용자_승인_사항"
    assert "recommended_design" not in rep and "verdict" not in rep
    assert rep["half_width_target"] == 0.04
    assert len(rep["limitations"]) >= 4
    designs = {row["queries_per_video"] for row in rep["rows"]}
    assert designs == {4, 5, 9}


def test_report_rows_carry_their_source_and_limits(tmp_path):
    p = _fake_source(tmp_path, 9, 60, spread_between=0.1, spread_within=0.2,
                     seed=8)
    rep = S.report(source=p, replicates=5, boot=50)
    for row in rep["rows"]:
        assert row["clusters"] == 35
        assert row["total_queries"] == row["clusters"] * row["queries_per_video"]
        assert row["historical_source"]
        assert "projected_half_width" in row
        assert "relative_to_m9" in row


def test_report_does_not_pick_a_design_by_effect_sign(tmp_path):
    p = _fake_source(tmp_path, 9, 60, spread_between=0.1, spread_within=0.2,
                     seed=9)
    rep = S.report(source=p, replicates=5, boot=50)
    assert rep["sign_is_not_a_decision_input"] is True


# ------------------------------------------------------------- 경계

def test_the_half_width_target_is_not_changed():
    assert S.HALF_WIDTH_TARGET == 0.04
    assert "0.05" not in CODE


@pytest.mark.parametrize("token", ["work_p2", "p2_queries_staging",
                                   "results_p2", "arm_3b", "arm_4b",
                                   "p2_label_intake", "adoption", "verdict",
                                   "rr_fus", "rr_sub"])
def test_no_p2_outcome_or_other_channel_is_reachable(token):
    assert token not in CODE


def _imported(src: str) -> set:
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


@pytest.mark.parametrize("mod", ["p2_evaluate", "p2_retrieve", "m5_search",
                                 "m6_evaluate"])
def test_it_imports_no_retrieval_or_evaluation_module(mod):
    assert mod not in _imported(SRC)


def test_it_never_proposes_a_top_up():
    for token in ("top_up", "topup", "증량"):
        assert token not in CODE


# ------------------------------------------------------------- ICC 시나리오

def test_icc_scenarios_span_the_unknown_and_zero_is_the_worst_case():
    rows = S.icc_scenarios(0.16, 35)
    assert [r["assumed_icc"] for r in rows] == list(S.ICC_SCENARIOS)
    zero = next(r for r in rows if r["assumed_icc"] == 0.0)
    high = next(r for r in rows if r["assumed_icc"] == 0.25)
    assert zero["relative_to_m9"][4] > high["relative_to_m9"][4]
    assert zero["relative_to_m9"][4] == pytest.approx(1.5, abs=1e-3)


def test_icc_scenarios_keep_total_variance_fixed():
    rows = S.icc_scenarios(0.16, 35)
    at_m9 = {r["assumed_icc"]: r["half_width"][9] for r in rows}
    assert len(set(round(v, 6) for v in at_m9.values())) > 1


def test_icc_scenarios_are_labelled_as_assumptions_not_estimates(tmp_path):
    p = _fake_source(tmp_path, 9, 60, spread_between=0.1, spread_within=0.2,
                     seed=11)
    rep = S.report(source=p, replicates=5, boot=50)
    assert "추정이 아니다" in rep["icc_scenarios_note"]
    assert len(rep["icc_scenarios"]) == len(S.ICC_SCENARIOS)


def test_the_icc_upper_bound_claim_is_scoped_to_the_variance_model(tmp_path):
    """'상한'은 이 분산 모형 안에서의 상대 손실 상한이다 — 보편적 상한이 아니다."""
    p = _fake_source(tmp_path, 9, 60, spread_between=0.1, spread_within=0.2,
                     seed=12)
    note = S.report(source=p, replicates=5, boot=50)["icc_scenarios_note"]
    assert "모형 안에서" in note
    assert "보편적 상한이 아니다" in note
    assert "상대 손실" in note
