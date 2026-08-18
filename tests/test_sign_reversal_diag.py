"""부호 역전 조사 — 분석 항목을 **SECONDARY 열람 전에** 고정한다.

사전등록: `부호역전_조사_사전등록_2026-08-18.md`.

산출은 **원인 확정이 아니라 heterogeneity localization**이다. 그래서 여기서 막는
것은 두 가지다 — 코드가 원인을 단정하는 키를 내지 않는 것, 그리고 결과를 보고
strata를 새로 만들 수 없게 층 정의를 파일에 묶어두는 것.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import sign_reversal_diag as D                              # noqa: E402

Q = [{"query_id": "a1", "video_id": "vA", "type": "자막형"},
     {"query_id": "a2", "video_id": "vA", "type": "시각형"},
     {"query_id": "b1", "video_id": "vB", "type": "자막형"},
     {"query_id": "c1", "video_id": "vC", "type": "시각형"}]


def _sweep(cand, cur, bf16=None):
    arms = {"qwen3vl_4b_q4/P0": {"rr_caption_only": cand,
                                 "mrr_caption_only": round(sum(cand) / len(cand), 4),
                                 "corrupted": 14, "len_mean": 82.0,
                                 "provenance": {"effective_model_revision": "r4",
                                                "effective_quantized": True,
                                                "prompt_sha256": "p"}},
            "qwen25_3b_4bit/P0": {"rr_caption_only": cur,
                                  "mrr_caption_only": round(sum(cur) / len(cur), 4),
                                  "corrupted": 3, "len_mean": 131.4,
                                  "provenance": {"effective_model_revision": "r3",
                                                 "effective_quantized": True,
                                                 "prompt_sha256": "p"}}}
    if bf16:
        arms["qwen3vl_4b/P0"] = {"rr_caption_only": bf16,
                                 "mrr_caption_only": round(sum(bf16) / len(bf16), 4),
                                 "corrupted": 15, "len_mean": 71.9,
                                 "provenance": {"effective_model_revision": "r4",
                                                "effective_quantized": False,
                                                "prompt_sha256": "p"}}
    return {"queries": Q, "arms": arms}


CAND = [1.0, 0.0, 0.5, 0.5]
CUR = [0.5, 0.5, 0.5, 1.0]                                   # Δ = +0.5, −0.5, 0, −0.5


# ---- (2) paired 분포 -----------------------------------------------------

def test_delta_is_paired_and_sign_distribution_reported():
    """평균만 보지 않는다 — 부호 분포를 함께 낸다."""
    r = D.analyze(_sweep(CAND, CUR), Q)
    d = r["paired_delta"]
    assert d["mean"] == pytest.approx(-0.125, abs=1e-9)
    assert d["n_positive"] == 1 and d["n_negative"] == 2 and d["n_zero"] == 1
    assert d["n"] == 4


def test_delta_records_extremes_so_domination_is_visible():
    r = D.analyze(_sweep(CAND, CUR), Q)
    d = r["paired_delta"]
    assert d["min"] == -0.5 and d["max"] == 0.5
    assert d["sum_negative"] == pytest.approx(-1.0, abs=1e-9)


# ---- (3) 영상 분해 + LOVO ------------------------------------------------

def test_per_video_and_leave_one_video_out():
    r = D.analyze(_sweep(CAND, CUR), Q)
    pv = r["by_video"]
    assert set(pv) == {"vA", "vB", "vC"}
    assert pv["vA"]["mean_delta"] == pytest.approx(0.0, abs=1e-9)
    assert pv["vC"]["mean_delta"] == pytest.approx(-0.5, abs=1e-9)
    lovo = r["leave_one_video_out"]
    assert set(lovo) == {"vA", "vB", "vC"}
    # vC를 빼면 남는 것은 vA(+0.5,−0.5) + vB(0) → 0.0
    assert lovo["vC"]["mean_delta"] == pytest.approx(0.0, abs=1e-9)
    assert lovo["vC"]["n"] == 3


def test_lovo_flags_when_one_video_dominates():
    r = D.analyze(_sweep(CAND, CUR), Q)
    assert r["leave_one_video_out"]["vC"]["sign_flips_vs_overall"] is True
    assert r["leave_one_video_out"]["vA"]["sign_flips_vs_overall"] is False


# ---- (4) strata는 파일 값만 -----------------------------------------------

def test_strata_come_from_query_file_only():
    r = D.analyze(_sweep(CAND, CUR), Q)
    assert set(r["by_query_type"]) == {"자막형", "시각형"}
    assert r["strata_source"] == "queries.jsonl:type"


def test_unknown_stratum_key_is_refused():
    """결과를 보고 새 strata를 만들 수 없게 한다."""
    with pytest.raises(D.DiagError, match="strata"):
        D.analyze(_sweep(CAND, CUR), Q, stratum_key="difficulty")


# ---- (1) parity audit ----------------------------------------------------

def test_parity_audit_reports_fields_and_mismatches():
    r = D.analyze(_sweep(CAND, CUR), Q)
    p = r["parity_audit"]
    assert p["prompt_sha256"]["match"] is True
    assert p["effective_quantized"]["values"] == {"qwen3vl_4b_q4/P0": True,
                                                 "qwen25_3b_4bit/P0": True}
    # 모델 revision은 arm마다 다른 것이 정상 — 불일치로 세지 않는다
    assert "effective_model_revision" in p


def test_parity_audit_flags_prompt_mismatch():
    s = _sweep(CAND, CUR)
    s["arms"]["qwen25_3b_4bit/P0"]["provenance"]["prompt_sha256"] = "other"
    r = D.analyze(s, Q)
    assert r["parity_audit"]["prompt_sha256"]["match"] is False


# ---- (5) exploratory 표시 -------------------------------------------------

def test_corruption_association_is_marked_exploratory():
    r = D.analyze(_sweep(CAND, CUR), Q)
    e = r["exploratory"]
    assert e["label"] == "exploratory_not_a_cause_claim"
    assert "corrupted_by_arm" in e and "len_mean_by_arm" in e


def test_no_cause_or_verdict_keys():
    """코드가 원인을 단정하지 않는다."""
    r = D.analyze(_sweep(CAND, CUR), Q)
    flat = str(sorted(r.keys()))
    for bad in ("cause", "verdict", "conclusion", "root_cause", "recommendation",
                "winner", "better"):
        assert bad not in flat, bad


def test_output_declares_it_is_localization_not_confirmation():
    r = D.analyze(_sweep(CAND, CUR), Q)
    assert r["purpose"].startswith("heterogeneity localization")
    assert "확정" in r["limits"] or "확증" in r["limits"]


# ---- (6) baseline 대조 ---------------------------------------------------

def test_baseline_arm_mrr_is_reported_for_cross_sample_comparison():
    r = D.analyze(_sweep(CAND, CUR), Q)
    assert r["arm_mrr"]["qwen25_3b_4bit/P0"] == pytest.approx(0.625, abs=1e-4)
    assert r["arm_mrr"]["qwen3vl_4b_q4/P0"] == pytest.approx(0.5, abs=1e-4)


def test_bf16_contrast_is_secondary_reference_only():
    r = D.analyze(_sweep(CAND, CUR, bf16=[1.0, 0.0, 0.5, 0.5]), Q)
    assert "paired_delta_bf16_reference" in r
    assert r["paired_delta_bf16_reference"]["note"]


# ---- fail-closed ---------------------------------------------------------

def test_missing_arm_is_refused():
    s = _sweep(CAND, CUR)
    del s["arms"]["qwen25_3b_4bit/P0"]
    with pytest.raises(D.DiagError, match="arm"):
        D.analyze(s, Q)


def test_query_manifest_length_mismatch_is_refused():
    s = _sweep(CAND, CUR)
    s["arms"]["qwen3vl_4b_q4/P0"]["rr_caption_only"] = [1.0, 0.0, 0.5]
    with pytest.raises(D.DiagError, match="길이"):
        D.analyze(s, Q)


def test_no_alpha_or_tau_anywhere():
    """α·τ로 PRIMARY 부호를 구제하지 않는다 — 산출에 들어오지 못하게 한다."""
    r = D.analyze(_sweep(CAND, CUR), Q)
    flat = str(r)
    for bad in ("alpha_star", "mrr_alpha_fixed", "tau", "alpha_curve"):
        assert bad not in flat, bad


def test_cli_survives_cp949_console(tmp_path):
    """콘솔이 cp949다 — stdout에 U+2212를 쓰면 산출을 낸 뒤에 죽는다.

    소스 문자열만 훑으면 놓친다(문제의 `−`가 print의 **다음 물리행**에 있었다).
    실제 실행으로 잡는다.
    """
    import json
    import os
    import subprocess
    sw = tmp_path / "sweep.json"
    sw.write_text(json.dumps(_sweep(CAND, CUR)), encoding="utf-8")
    out = tmp_path / "r.json"
    env = {**os.environ, "PYTHONIOENCODING": "cp949"}
    p = subprocess.run([sys.executable,
                        str(ROOT / "docs" / "probes" / "sign_reversal_diag.py"),
                        "--sweep", str(sw), "--out", str(out)],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr[-400:]
    assert out.exists()


def test_source_module_does_not_read_alpha_keys():
    src = (ROOT / "docs" / "probes" / "sign_reversal_diag.py").read_text(
        encoding="utf-8")
    body = src.split('"""', 2)[2]
    for bad in ("alpha_star", "mrr_alpha_fixed", "alpha_curve"):
        assert bad not in body, bad
