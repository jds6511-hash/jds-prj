"""dev 정밀도 3-arm — Δ 정의·paired 재표집·fail-closed. **결과 보기 전에 고정.**

사전등록: `dev_precision_3arm_사전등록_2026-08-18.md` +
`dev_precision_3arm_보충_CI해석_2026-08-18.md`.

**cluster = 3이다.** CI는 불확실성 진단용이고 formal adoption gate가 아니다.
그래서 여기서 고정하는 것은 유의성 판정이 아니라 **paired 대응이 깨지지 않는가**다.
질의 순서가 한 칸 밀리면 Δ가 조용히 오염된다 — 그쪽을 막는다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
sys.path.insert(0, str(ROOT / "src"))
import dev_precision_3arm as D                              # noqa: E402

Q = [{"query_id": "a1", "video_id": "vA"}, {"query_id": "a2", "video_id": "vA"},
     {"query_id": "b1", "video_id": "vB"}, {"query_id": "c1", "video_id": "vC"}]


def _sweep(**rr):
    """arm별 caption-only RR만 담은 최소 sweep 산출물."""
    arms = {}
    for key, vals in rr.items():
        arms[key.replace("__", "/")] = {
            "rr_caption_only": list(vals),
            "mrr_caption_only": round(sum(vals) / len(vals), 4)}
    return {"queries": Q, "arms": arms}


BASE = dict(qwen3vl_4b_q4__P0=[1.0, 0.5, 0.5, 0.0],
            qwen3vl_4b__P0=[1.0, 1.0, 0.5, 0.0],
            qwen25_3b_4bit__P0=[0.5, 0.5, 0.5, 0.0])


# ---- Δ 정의 ---------------------------------------------------------------

def test_deltas_are_paired_means_of_per_query_differences():
    r = D.analyze(_sweep(**BASE), n_boot=50, seed=0)
    # Δ_quant  = 4bit − bf16 = (0, −0.5, 0, 0) 평균 = −0.125
    # Δ_deploy = 4bit − 3B   = (+0.5, 0, 0, 0) 평균 = +0.125
    assert r["delta_quant"]["point"] == pytest.approx(-0.125, abs=1e-9)
    assert r["delta_deploy"]["point"] == pytest.approx(0.125, abs=1e-9)


def test_point_estimate_equals_difference_of_arm_mrr():
    r = D.analyze(_sweep(**BASE), n_boot=50, seed=0)
    a = r["arm_mrr"]
    assert r["delta_quant"]["point"] == pytest.approx(
        a["qwen3vl_4b_q4/P0"] - a["qwen3vl_4b/P0"], abs=1e-9)


def test_cluster_key_is_video_id_and_count_is_reported():
    r = D.analyze(_sweep(**BASE), n_boot=50, seed=0)
    assert r["cluster_key"] == "video_id" and r["n_clusters"] == 3
    assert r["n_queries"] == 4


def test_ci_is_marked_diagnostic_only():
    """cluster=3 — CI를 formal gate로 쓰지 않는다는 표시가 산출물에 있어야 한다."""
    r = D.analyze(_sweep(**BASE), n_boot=50, seed=0)
    assert r["ci_interpretation"] == "diagnostic_only"
    assert "formal" in r["ci_caveat"] and "3" in str(r["n_clusters"])


def test_bootstrap_settings_are_recorded():
    r = D.analyze(_sweep(**BASE), n_boot=123, seed=7)
    assert r["n_boot"] == 123 and r["seed"] == 7
    assert r["ci_method"] == "paired_video_cluster_bootstrap_percentile"


def test_bootstrap_is_reproducible_and_paired():
    a = D.analyze(_sweep(**BASE), n_boot=200, seed=1)
    b = D.analyze(_sweep(**BASE), n_boot=200, seed=1)
    assert a["delta_quant"]["ci"] == b["delta_quant"]["ci"]


def test_identical_arms_give_zero_delta_and_degenerate_ci():
    """paired가 실제로 대응을 지키는지 — 같은 값이면 모든 재표집에서 0이다."""
    same = [1.0, 0.5, 0.25, 0.0]
    r = D.analyze(_sweep(qwen3vl_4b_q4__P0=same, qwen3vl_4b__P0=same,
                         qwen25_3b_4bit__P0=same), n_boot=100, seed=3)
    assert r["delta_quant"]["point"] == 0.0
    assert r["delta_quant"]["ci"] == [0.0, 0.0]


# ---- fail-closed ----------------------------------------------------------

def test_missing_arm_is_refused():
    s = _sweep(**BASE)
    del s["arms"]["qwen25_3b_4bit/P0"]
    with pytest.raises(D.AnalysisError, match="arm"):
        D.analyze(s)


def test_length_mismatch_is_refused():
    s = _sweep(**BASE)
    s["arms"]["qwen3vl_4b/P0"]["rr_caption_only"] = [1.0, 1.0, 0.5]
    with pytest.raises(D.AnalysisError, match="길이"):
        D.analyze(s)


def test_duplicate_query_id_is_refused():
    s = _sweep(**BASE)
    s["queries"] = [{"query_id": "a1", "video_id": "vA"}] * 4
    with pytest.raises(D.AnalysisError, match="중복"):
        D.analyze(s)


def test_stored_mrr_inconsistent_with_rr_is_refused():
    """aggregate가 per-query 평균과 다르면 순서·집합이 어긋난 것이다."""
    s = _sweep(**BASE)
    s["arms"]["qwen3vl_4b/P0"]["mrr_caption_only"] = 0.9999
    with pytest.raises(D.AnalysisError, match="MRR"):
        D.analyze(s)


def test_missing_query_manifest_is_refused():
    s = _sweep(**BASE)
    del s["queries"]
    with pytest.raises(D.AnalysisError, match="queries"):
        D.analyze(s)


# ---- quadrant: 기술적 라벨만 ----------------------------------------------

@pytest.mark.parametrize("q,dp,label", [
    (-0.1, +0.1, "quant_loss_and_deploy_gain"),
    (-0.1, -0.1, "quant_loss_and_no_deploy_gain"),
    (+0.1, +0.1, "no_quant_loss_and_deploy_gain"),
    (0.0, 0.0, "no_quant_loss_and_no_deploy_gain"),
])
def test_quadrant_labels_describe_signs_only(q, dp, label):
    assert D.quadrant(q, dp) == label


def test_quadrant_has_no_evaluative_words():
    """`good`·`bad`·`equivalent`·`significant`를 코드가 붙이지 않는다."""
    for q in (-1, 0, 1):
        for dp in (-1, 0, 1):
            lab = D.quadrant(q, dp)
            for bad in ("good", "bad", "equivalent", "significant", "pass", "fail"):
                assert bad not in lab, (lab, bad)


def test_analyze_does_not_emit_verdict_keys():
    r = D.analyze(_sweep(**BASE), n_boot=50, seed=0)
    for k in ("verdict", "adopt", "pass", "significant", "recommendation"):
        assert k not in r


# ---- VRAM 키 이름 ---------------------------------------------------------

def test_vram_keys_are_server_scoped():
    """서버 4090 측정값이 6GB 적합성 수치로 오독되지 않게 이름에 서버를 박는다."""
    s = _sweep(**BASE)
    for k in s["arms"]:
        s["arms"][k]["server_peak_vram_gb"] = 11.4
    r = D.analyze(s, n_boot=20, seed=0)
    assert set(r["server_peak_vram_gb"]) == set(s["arms"])
    assert not any(k == "peak_vram_gb" for k in r)


# ---- 사전등록 대조 --------------------------------------------------------

def test_arm_keys_match_prereg():
    assert D.ARMS == {"quant_4bit": "qwen3vl_4b_q4/P0",
                      "quant_bf16": "qwen3vl_4b/P0",
                      "deploy_current": "qwen25_3b_4bit/P0"}


def test_prereg_files_exist():
    p = ROOT / "docs" / "preregistration"
    assert (p / "dev_precision_3arm_사전등록_2026-08-18.md").is_file()
    assert (p / "dev_precision_3arm_보충_CI해석_2026-08-18.md").is_file()
