"""carried census 파생 — **공표값을 타이핑하지 않았음**을 고정한다.

재현 게이트는 census 합을 공표값과 대조한다. census를 공표값에서 만들면 게이트가
자기 입력을 자기와 비교하는 셈이라 아무것도 막지 못한다. 그래서 여기서 고정하는 것은
정확도가 아니라 **출처**다 — dev 산출물 by_cell에서만 온다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import i1_carried_census as C                                    # noqa: E402
import i1_validation_analysis as V                               # noqa: E402

SRC = (ROOT / "docs" / "probes" / "i1_carried_census.py").read_text(
    encoding="utf-8")


def _dev():
    return json.loads(C.DEV_JSON.read_text(encoding="utf-8"))


def test_published_numbers_are_not_hardcoded():
    for n in ("71", "70"):
        assert f"= {n}" not in SRC.split('"""', 2)[2]


def test_sums_reproduce_the_published_gate_values():
    carried = C.build(_dev())
    tp = {k: sum(c["tp"][k] for c in carried.values())
          for k in ("baseline", "primary", "fallback")}
    assert tp == V.PUBLISHED_CARRIED_TP
    assert sum(c["drift"] for c in carried.values()) == V.PUBLISHED_CARRIED_DRIFT


def test_only_census_cells_are_carried():
    carried = C.build(_dev())
    assert tuple(carried) == C.CELLS
    assert all(c["carried_over_census"] and not c["revalidated_in_validation"]
               for c in carried.values())


def test_candidate_blocks_are_matched_by_frozen_config_not_order():
    dev = _dev()
    dev["candidates"] = list(reversed(dev["candidates"]))
    assert C.build(dev) == C.build(_dev())


def test_non_census_cell_is_refused():
    dev = _dev()
    dev["baseline"]["by_cell"]["C4"]["sampled"] = 70
    with pytest.raises(C.CensusError, match="전수가 아니다"):
        C.build(dev)


def test_changed_census_cell_list_is_refused():
    dev = _dev()
    dev["census_cells"] = ["C1", "C4"]
    with pytest.raises(C.CensusError, match="전수 셀"):
        C.build(dev)


def test_rule_dependent_drift_is_refused():
    """참 라벨은 규칙과 무관하다 — 규칙마다 다르면 이어받은 census가 오염됐다."""
    dev = _dev()
    dev["candidates"][0]["by_cell"]["C4"]["drift"] = 67
    with pytest.raises(C.CensusError, match="drift가 규칙마다 다르다"):
        C.build(dev)


def test_provenance_records_the_four_required_facts():
    carried = C.build(_dev())
    p = C.provenance(carried, {"a": "no_text", "b": "korean_text_only"})
    assert len(p["analysis_commit"]) == 40
    assert len(p["labels_v_csv_sha256"]) == 64
    assert p["b_target_count"] == 0
    assert p["carried_reproduction_gate_enabled"] is True


def test_provenance_counts_b_targets_when_they_exist():
    p = C.provenance(C.build(_dev()), {"a": "cjk_text_present", "b": "no_text"})
    assert p["b_target_count"] == 1
