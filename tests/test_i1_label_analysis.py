"""I1 human label 분석 — **라벨을 한 건도 보기 전에** 계산 규칙을 고정한다.

사전등록: `I1검증셋_사전등록_2026-08-18.md` + `I1검증셋_보충_B단계경계_2026-08-18.md`.

두 가지가 핵심이다.

**(1) 두 추정량을 섞지 않는다.**
  - `I1a 적중 82건`은 사실상 **전수**다 → 그 집합에 대한 precision은 표집오차가 없다.
  - `I1a 음성`은 C0(8,430 중 24)·C2(800 중 24) **표본**이다 → 모집단 유병률을
    말하려면 **셀 가중**이 필요하다. 표본 비율을 그대로 쓰면 틀린다.

**(2) A 단계만으로 "recall"을 말하지 않는다.**
  A는 화면에 글자가 있는지만 답한다. 캡션의 외국어가 그 글자를 옮긴 것인지는
  B가 답한다. A만 있는 시점의 값은 `..._vs_frame_text_proxy`로만 부른다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import i1_label_analysis as A                              # noqa: E402

MANIFEST = {"population_by_cell": {"C0": 8430, "C1": 1, "C2": 800, "C4": 78, "C5": 3},
            "instances": [
                # I1a 적중(전수) — C4 두 건, arm이 다르다
                {"sample_id": "S1", "cell": "C4", "arm": "qwen25_3b__P0", "i1a_hit": True,
                 "cjk_count": 5, "video_id": "V1"},
                {"sample_id": "S2", "cell": "C4", "arm": "qwen3vl_4b__P0", "i1a_hit": True,
                 "cjk_count": 4, "video_id": "V1"},
                # I1a 음성(표본)
                {"sample_id": "S3", "cell": "C2", "arm": "qwen3vl_4b__P0", "i1a_hit": False,
                 "cjk_count": 2, "video_id": "V2"},
                {"sample_id": "S4", "cell": "C0", "arm": "qwen25_3b__P0", "i1a_hit": False,
                 "cjk_count": 0, "video_id": "V2"},
            ]}
# S1은 화면에 한자 있음(= 검출기 오탐 후보), S2는 화면에 글자 없음(= drift)
LABELS = {"S1": "cjk_text_present", "S2": "no_text",
          "S3": "cjk_text_present", "S4": "no_text"}


def _rows(labels=None):
    return A.join(MANIFEST, labels if labels is not None else LABELS)


# ---- 조인·전건 -----------------------------------------------------------

def test_join_attaches_label_to_every_instance_of_that_frame():
    rows = _rows()
    assert len(rows) == 4 and all(r["label"] for r in rows)


def test_missing_label_is_not_silently_dropped():
    """라벨이 안 들어온 표본을 조용히 빼면 분모가 줄어 값이 부풀려진다."""
    with pytest.raises(A.AnalysisError, match="미기입"):
        A.join(MANIFEST, {"S1": "no_text"})


def test_unclear_excluded_from_main_but_counted():
    rows = A.join(MANIFEST, {**LABELS, "S2": "unclear"})
    assert A.unclear_rate(rows) == 0.25
    assert all(r["label"] != "unclear" for r in A.analyzable(rows))


# ---- (1) 전수 추정량: I1a precision --------------------------------------

def test_i1a_precision_uses_only_hits_and_is_a_census():
    """`I1a 적중`은 전수라 표집오차가 없다 — 그 사실을 결과에 박는다."""
    r = A.i1a_precision(_rows())
    assert r["n"] == 2 and r["drift_proxy"] == 1        # S2만 drift 후보
    assert r["precision_vs_frame_text_proxy"] == 0.5
    assert r["is_census"] is True


def test_i1a_precision_name_does_not_claim_semantic_drift():
    """A 단계만으로는 `precision`이라고 단정하지 않는다 — 이름에 proxy를 박는다."""
    assert "precision_vs_frame_text_proxy" in A.i1a_precision(_rows())


def test_precision_none_when_no_hits():
    m = {**MANIFEST, "instances": [i for i in MANIFEST["instances"]
                                   if not i["i1a_hit"]]}
    assert A.i1a_precision(A.join(m, {"S3": "no_text", "S4": "no_text"}))[
        "precision_vs_frame_text_proxy"] is None


# ---- (2) 표본 추정량: 셀 가중 유병률 --------------------------------------

def test_negative_prevalence_reports_weighted_and_unweighted():
    r = A.foreign_script_prevalence(_rows())
    # 표본: C2 1건 중 1건 present(1.0), C0 1건 중 0건(0.0)
    assert r["unweighted"] == 0.5
    # 가중: (800*1.0 + 8430*0.0) / 9230
    assert r["weighted"] == round(800 / 9230, 4)
    assert r["weights"] == {"C2": 800, "C0": 8430}


def test_weighted_prevalence_differs_from_unweighted_by_design():
    """이 둘이 같으면 가중이 안 걸린 것이다 — 섞어 쓰면 8,430을 24처럼 센다."""
    r = A.foreign_script_prevalence(_rows())
    assert r["weighted"] != r["unweighted"]


def test_prevalence_excludes_i1a_hits():
    """적중분은 전수 추정량 쪽이다. 여기 섞으면 두 추정량이 뒤엉킨다."""
    assert A.foreign_script_prevalence(_rows())["n"] == 2


# ---- 분포 ---------------------------------------------------------------

def test_by_arm_distribution():
    d = A.by_arm(_rows())
    assert d["qwen25_3b__P0"]["n"] == 2
    assert d["qwen3vl_4b__P0"]["labels"]["cjk_text_present"] == 1


def test_by_cjk_stratum_uses_prefixed_buckets():
    d = A.by_cjk_stratum(_rows())
    assert set(d) == {"0", "1-2", "3-9", "10+"}
    assert d["3-9"]["n"] == 2 and d["1-2"]["n"] == 1 and d["0"]["n"] == 1


# ---- 영상 클러스터 CI ----------------------------------------------------

def test_cluster_ci_resamples_videos_not_samples():
    """같은 영상의 프레임은 상관된다 — 표본 단위로 재표집하면 CI가 좁아진다."""
    rows = _rows()
    ci = A.cluster_ci([1.0 if r["label"] == "no_text" else 0.0 for r in rows],
                      [r["video_id"] for r in rows], B=200, seed=42)
    assert ci["n_videos"] == 2 and ci["ci95"][0] <= ci["point"] <= ci["ci95"][1]


# ---- B 단계 경계 ---------------------------------------------------------

def test_stage_b_pending_list_covers_both_required_sets():
    """보충 사전등록 (가)·(나) — B가 필요한 집합을 코드가 짚어준다."""
    p = A.stage_b_pending(_rows())
    assert p["a_cjk_present_with_caption_cjk"] == ["S1", "S3"]   # 화면 글자 + 캡션 CJK
    assert p["b_i1a_negative_sample"] == ["S3", "S4"]


def test_report_refuses_to_emit_recall_before_stage_b():
    """A만 있는 상태에서 recall을 내놓으면 안 된다 — 이름부터 막는다."""
    out = A.summarize(_rows(), MANIFEST)
    assert not any("recall" in k for k in out)
    assert out["stage"] == "A_only"
