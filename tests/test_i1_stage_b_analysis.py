"""I1 B단계 분석 — 도출 규칙과 recall 분모. **규칙을 새로 만들지 않는다.**

사전등록: `I1검증셋_사전등록_2026-08-18.md` §도출 규칙 · `보충_B단계경계` · `보충2`.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import i1_stage_b_analysis as S                             # noqa: E402


def _i(cjk=2, cell="C2", hit=False, pop=800, sid="S1"):
    return {"sample_id": sid, "cjk_count": cjk, "cell": cell,
            "i1a_hit": hit, "cell_population": pop}


# ---- 도출 규칙 -----------------------------------------------------------

@pytest.mark.parametrize("a,b,want", [
    ("cjk_text_present", "matches_screen", "scene_text"),
    ("cjk_text_present", "drift_despite_text", "drift"),
    ("no_text", None, "drift"),
    ("korean_text_only", None, "drift"),
    ("unclear", None, "excluded_unclear"),
    ("no_text", "unclear", "excluded_unclear"),
])
def test_derivation_matches_prereg_table(a, b, want):
    assert S.true_label(_i(), a, b) == want


def test_no_caption_cjk_is_never_cjk_drift():
    """캡션 CJK가 0이면 도출 규칙상 CJK drift가 아니다 — C0의 근거다."""
    assert S.true_label(_i(cjk=0, cell="C0"), "no_text", None) == "not_cjk_drift"


def test_cjk_present_without_b_label_is_refused():
    """(가)는 B 없이 참 라벨을 정할 수 없다 — 조용히 추측하지 않는다."""
    with pytest.raises(S.AnalysisError, match="B 라벨이 없다"):
        S.true_label(_i(), "cjk_text_present", None)


# ---- 완결성 -------------------------------------------------------------

POP = {"C0": 8430, "C1": 1, "C2": 800, "C4": 78, "C5": 3}


def _man(insts):
    return {"instances": insts, "population_by_cell": POP}


def _bundle(b_labels, insts=None):
    insts = insts or [_i(sid="S1"), _i(sid="S2", cjk=5, cell="C4", hit=True, pop=78)]
    man = _man(insts)
    a = {"S1": "cjk_text_present", "S2": "no_text"}
    bman = {"targets": ["S1"], "prereg": "p", "a_labels_sha256": "h"}
    return man, a, b_labels, bman


def test_incomplete_b_labels_block_precision_and_recall():
    """**B 완결 전에는 precision·recall을 산출하지 않는다.**"""
    with pytest.raises(S.AnalysisError, match="완결"):
        S.analyze(*_bundle({"S1": ""}))


def test_invalid_b_label_is_refused():
    with pytest.raises(S.AnalysisError, match="완결"):
        S.analyze(*_bundle({"S1": "yes"}))


# ---- precision / recall -------------------------------------------------

def test_precision_counts_scene_text_as_false_positive():
    """적중이 scene text면 오탐이다 — precision이 내려가야 한다."""
    insts = [_i(sid="H1", cjk=5, cell="C4", hit=True, pop=78),
             _i(sid="H2", cjk=6, cell="C4", hit=True, pop=78)]
    man = _man(insts)
    a = {"H1": "cjk_text_present", "H2": "no_text"}
    bman = {"targets": ["H1"], "prereg": "p", "a_labels_sha256": "h"}
    r = S.analyze(man, a, {"H1": "matches_screen"}, bman)
    p = r["i1a_precision"]
    assert p["n_scene_text"] == 1 and p["n_drift"] == 1
    assert p["precision"] == 0.5
    assert p["precision_ci"][0] < 0.5 < p["precision_ci"][1]


def test_unclear_is_excluded_from_precision_but_counted():
    insts = [_i(sid="H1", cjk=5, cell="C4", hit=True, pop=78),
             _i(sid="H2", cjk=5, cell="C4", hit=True, pop=78)]
    r = S.analyze(_man(insts), {"H1": "no_text", "H2": "unclear"},
                  {}, {"targets": [], "prereg": "p", "a_labels_sha256": "h"})
    p = r["i1a_precision"]
    assert p["n_hits_census"] == 2 and p["n_analyzable"] == 1
    assert p["n_excluded_unclear"] == 1 and p["precision"] == 1.0


def test_miss_zone_is_population_weighted():
    """C2 표본 비율을 모집단 800으로 가중한다 — 표본 수를 그대로 쓰지 않는다."""
    insts = ([_i(sid=f"N{i}") for i in range(10)]
             + [_i(sid="H1", cjk=5, cell="C4", hit=True, pop=78)])
    a = {f"N{i}": "no_text" for i in range(10)}
    a["H1"] = "no_text"
    r = S.analyze(_man(insts), a, {},
                  {"targets": [], "prereg": "p", "a_labels_sha256": "h"})
    m = r["miss_zone_by_cell"]["C2"]
    assert m["population"] == 800 and m["analyzable"] == 10 and m["drift"] == 10
    assert m["drift_rate"] == 1.0
    assert m["est_drift_population"] == 800.0
    # 10/10이어도 CI 폭이 생긴다 — 하한이 1.0 미만
    assert m["drift_rate_ci"][0] < 1.0


def test_recall_denominator_includes_estimated_missed():
    insts = ([_i(sid=f"N{i}") for i in range(10)]
             + [_i(sid="H1", cjk=5, cell="C4", hit=True, pop=78)])
    a = {f"N{i}": "no_text" for i in range(10)}
    a["H1"] = "no_text"
    r = S.analyze(_man(insts), a, {},
                  {"targets": [], "prereg": "p", "a_labels_sha256": "h"})
    rec = r["i1a_recall"]
    assert rec["detected_drift"] == 1
    assert rec["est_missed_drift"] == 800.0
    assert rec["recall"] == pytest.approx(1 / 801, abs=1e-4)
    assert rec["recall_ci_from_miss_ci"][0] <= rec["recall"] <= \
        rec["recall_ci_from_miss_ci"][1]


def test_c0_is_derived_not_human_labeled():
    """C0은 사람이 안 봤지만 분모 구조에 남는다 — 근거를 명시한다."""
    insts = [_i(sid="Z1", cjk=0, cell="C0", pop=8430),
             _i(sid="H1", cjk=5, cell="C4", hit=True, pop=78)]
    r = S.analyze(_man(insts), {"Z1": "no_text", "H1": "no_text"}, {},
                  {"targets": [], "prereg": "p", "a_labels_sha256": "h"})
    m = r["miss_zone_by_cell"]["C0"]
    assert m["human_labeled"] == 0 and m["drift"] == 0
    assert "derived" in m["basis"] and m["est_drift_population"] == 0.0


def test_scope_is_limited_to_cjk_drift():
    insts = [_i(sid="H1", cjk=5, cell="C4", hit=True, pop=78)]
    r = S.analyze(_man(insts), {"H1": "no_text"}, {},
                  {"targets": [], "prereg": "p", "a_labels_sha256": "h"})
    assert "CJK drift" in r["scope"] and r["stage"] == "A_and_B"
    assert r["i1a_recall"]["limits"]


# ---- 파생 셀에는 표집 불확실성이 없다 (2026-08-18 수정) --------------------

def test_derived_cell_contributes_zero_with_no_ci():
    """C0은 `cjk_count == 0`으로 **정의된** 셀이다. 표본에서 drift가 0으로 나온 것이
    아니라 도출 규칙상 될 수 없다 — Wilson CI를 붙이면 모집단 8430이 곱해져
    허구의 상한(1553)이 생기고 recall 하한을 그것이 지배한다."""
    insts = ([_i(sid=f"Z{i}", cjk=0, cell="C0", pop=8430) for i in range(24)]
             + [_i(sid="H1", cjk=5, cell="C4", hit=True, pop=78)])
    a = {f"Z{i}": ("unclear" if i < 7 else "no_text") for i in range(24)}
    a["H1"] = "no_text"
    r = S.analyze(_man(insts), a, {},
                  {"targets": [], "prereg": "p", "a_labels_sha256": "h"})
    m = r["miss_zone_by_cell"]["C0"]
    assert m["est_drift_population"] == 0.0
    assert m["est_drift_population_ci"] == [0.0, 0.0]
    assert m["uncertainty"] == "none_by_derivation"
    # A가 unclear여도 C0은 도출로 결정된다 — 제외 대상이 아니다
    assert m["unclear"] == 0 and m["analyzable"] == 24


def test_caption_cjk_zero_beats_unclear_in_derivation():
    """보충2는 `caption_cjk_count == 0`이면 파생값으로 false라고 못박았다 —
    A가 unclear여도 그렇다. 규칙 순서를 그렇게 고정한다."""
    assert S.true_label(_i(cjk=0, cell="C0"), "unclear", None) == "not_cjk_drift"


def test_recall_ci_is_not_inflated_by_derived_cells():
    insts = ([_i(sid=f"Z{i}", cjk=0, cell="C0", pop=8430) for i in range(24)]
             + [_i(sid=f"N{i}") for i in range(20)]
             + [_i(sid="H1", cjk=5, cell="C4", hit=True, pop=78)])
    a = {f"Z{i}": "no_text" for i in range(24)}
    a.update({f"N{i}": "no_text" for i in range(20)})
    a["H1"] = "no_text"
    r = S.analyze(_man(insts), a, {},
                  {"targets": [], "prereg": "p", "a_labels_sha256": "h"})
    rec = r["i1a_recall"]
    # 분모는 C2 800만 — C0은 0을 정확히 기여한다
    assert rec["est_missed_drift"] == 800.0
    lo, hi = rec["recall_ci_from_miss_ci"]
    assert lo == pytest.approx(1 / 801, abs=1e-3)      # 상한 800에서 나온 하한
    assert hi > lo
