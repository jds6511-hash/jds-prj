"""3B vs 4B 운영비 프로파일 — 계약 테스트.

이 모듈은 **생성 비용 사실만** 읽는다. 검색 성능(rr·rank·hit·MRR)을 읽으면 채택 효용
기준을 결과에 맞춰 정하는 통로가 열린다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p3_operational_cost as OC     # noqa: E402


# ---- outcome-blind 구조 ----------------------------------------------------

def test_declares_read_allowlist():
    assert OC.READ_ALLOWLIST
    assert "provenance" in OC.READ_ALLOWLIST


def test_source_never_mentions_outcome_keys():
    src = (ROOT / "scripts" / "p3_operational_cost.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    # 문서화 목적의 금지 목록 선언은 제외하고 본다
    lits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lits.append(node.value)
    joined = "\n".join(lits)
    forbidden_decl = " ".join(OC.FORBIDDEN_KEYS) + " " + \
        " ".join(OC.FORBIDDEN_FIELDS)
    residual = joined.replace(forbidden_decl, "")
    for bad in ("rr_cap", "rr_fus", "rank_cap", "hit1_", "mrr_caption"):
        assert bad not in residual, bad


def test_forbidden_keys_are_declared():
    for k in ("arms", "per_query", "contrasts"):
        assert k in OC.FORBIDDEN_KEYS


def test_profile_records_read_keys():
    r = OC.profile()
    assert set(r["read_keys"]) <= set(OC.READ_ALLOWLIST)


def test_profile_contains_no_outcome_numbers():
    """산출물 전문에 arm별 MRR 값이 들어가지 않는다."""
    blob = json.dumps(OC.profile(), ensure_ascii=False)
    for bad in ("rr_cap", "rr_fus", "mrr", "0.4773", "0.5083", "0.4932"):
        assert bad not in blob, bad


def test_module_does_not_import_search_or_eval():
    src = (ROOT / "scripts" / "p3_operational_cost.py").read_text(
        encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m5_search", "m6_evaluate", "p2_retrieve", "p2_evaluate",
                 "p3_design_sensitivity"} & mods)


# ---- 비교 가능성 게이트 ----------------------------------------------------

def test_matched_conditions_are_checked():
    r = OC.profile()
    m = r["comparability"]
    assert m["matched"] is True
    assert set(m["matched_fields"]) >= {"gpu", "git_head",
                                        "config_vlm_max_pixels",
                                        "config_vlm_max_new_tokens"}
    assert m["mismatched_fields"] == []


def test_unmatched_conditions_are_reported_not_hidden(tmp_path):
    doc = {"n_segments": 100,
           "provenance": {
               "a/P0": {"gpu": "X", "git_head": "h", "elapsed_sec": 10.0,
                        "sec_per_segment": 0.1, "dtype_effective": "bf16",
                        "quantized_effective": False,
                        "config_vlm_max_pixels": 1, "config_vlm_max_new_tokens": 8,
                        "model_id_effective": "A", "model_revision": "r"},
               "b/P0": {"gpu": "Y", "git_head": "h", "elapsed_sec": 20.0,
                        "sec_per_segment": 0.2, "dtype_effective": "bf16",
                        "quantized_effective": False,
                        "config_vlm_max_pixels": 1, "config_vlm_max_new_tokens": 8,
                        "model_id_effective": "B", "model_revision": "r"}}}
    p = tmp_path / "src.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    r = OC.profile(source=p, arms=("a/P0", "b/P0"))
    assert r["comparability"]["matched"] is False
    assert "gpu" in r["comparability"]["mismatched_fields"]
    assert r["ratio"] is None            # 조건이 다르면 비율을 내지 않는다


def test_missing_arm_is_refused(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps({"provenance": {}}), encoding="utf-8")
    with pytest.raises(OC.CostError):
        OC.profile(source=p, arms=("a/P0", "b/P0"))


# ---- 비용 사실 -------------------------------------------------------------

def test_reports_per_arm_generation_cost():
    r = OC.profile()
    for arm in (OC.BASE_ARM, OC.CAND_ARM):
        a = r["arms"][arm]
        assert a["sec_per_segment"] > 0
        assert a["elapsed_sec"] > 0
        assert a["dtype_effective"]
        assert a["quantized_effective"] is False    # 이 표본은 bf16이다
        assert a["caption_len_mean_chars"] > 0


def test_ratio_is_candidate_over_base():
    r = OC.profile()
    b = r["arms"][OC.BASE_ARM]["sec_per_segment"]
    c = r["arms"][OC.CAND_ARM]["sec_per_segment"]
    assert abs(r["ratio"]["sec_per_segment_candidate_over_base"] -
               c / b) < 1e-9


def test_precision_gap_is_flagged():
    r = OC.profile()
    assert r["deployment_precision"] == "4bit"
    assert r["sample_precision"] == "bf16"
    assert r["precision_gap_warning"]


def test_projection_uses_declared_corpus_sizes():
    r = OC.profile()
    for p in r["recaption_projection"]:
        assert p["n_segments"] > 0 and p["source"]
        assert p["base_hours"] > 0 and p["candidate_hours"] > 0


# ---- 빠진 측정과 프로토콜 --------------------------------------------------

def test_missing_measurements_are_enumerated():
    r = OC.profile()
    names = {m["item"] for m in r["missing_measurements"]}
    assert {"peak_vram", "throughput_at_4bit", "load_overhead",
            "storage_delta", "oom_failure"} <= names
    for m in r["missing_measurements"]:
        assert m["why_it_matters"] and m["how_to_get_it"]


def test_protocol_is_frozen_before_any_run():
    r = OC.profile()
    p = r["measurement_protocol"]
    assert p["executed"] is False
    assert p["requires_user_approval"] is True
    assert p["labels_required"] == 0
    assert p["reads_retrieval_outcome"] is False
    assert len(p["matched_conditions"]) >= 6
    assert len(p["steps"]) >= 4


def test_no_adoption_threshold_is_invented():
    r = OC.profile()
    assert r["minimum_deployment_relevant_gain"] == "사용자_결정_사항"
    assert r["decision"] == "사용자_결정_사항"
    assert "recommended_threshold" not in r


def test_p2_stage_timing_is_reported_as_upper_bound_only():
    r = OC.profile()
    s = r["p2_full_stage_timing"]
    assert s["base_stage_includes_stt"] is True
    assert s["base_caption_sec_per_segment_upper_bound"] > \
        s["candidate_caption_sec_per_segment"]
    assert s["note"]


def test_artifact_matches_module_output():
    p = ROOT / "docs" / "P3_운영비_2026-08-24.json"
    if not p.is_file():
        pytest.skip("산출물이 아직 없다")
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert saved["arms"] == OC.profile()["arms"]
