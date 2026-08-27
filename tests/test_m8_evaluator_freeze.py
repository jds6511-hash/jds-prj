"""evaluator 동결 artifact — M8 공식 생성 **전** 시점의 대조 가능성.

테스트는 pytest를 재귀 실행하지 않는다(`run_tests=False`).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import m8_evaluator_freeze as F                                    # noqa: E402


@pytest.fixture(scope="module")
def art():
    return F.build_artifact(run_tests=False)


def test_records_gt_aggregate_hash(art):
    assert len(art["aggregate_gt_sha256"]) == 64
    assert art["n_reference_events"] == 68 and art["n_videos"] == 8


def test_has_a_hash_per_gate(art):
    assert set(art["gate_implementation_sha256"]) == {"C1", "C2", "C3"}
    for v in art["gate_implementation_sha256"].values():
        assert len(v) == 64


def test_gate_hash_changes_when_its_functions_change():
    """구현이 바뀌면 해시가 움직여야 대조가 의미를 가진다."""
    a = F.gate_hash("C3")
    b = F.gate_hash("C3", extra_sources=["# 한 줄 추가"])
    assert a != b


def test_spec_docs_are_hashed(art):
    d = art["spec_doc_sha256"]
    assert d["gate_spec"] and d["gate_rules"] and d["event_metric_spec"]
    assert d["gt_freeze"]


def test_evaluator_sources_are_hashed(art):
    s = art["evaluator_source_sha256"]
    for k in ("m8_c1", "m8_metrics", "m8_gates", "event_inventory_kit"):
        assert len(s[k]) == 64


def test_official_output_not_viewed_is_evidenced(art):
    """선언이 아니라 실측이다 — 패널 8편에 리포트 파일이 없다는 것을 센다."""
    assert art["official_m8_output_viewed"] is False
    ev = art["official_output_evidence"]
    assert ev["report_files_found"] == 0 and ev["videos_scanned"] == 8


def test_c2_metric_gap_is_recorded_not_filled(art):
    """C2 판정 지표는 아직 확정되지 않았다. **artifact가 그것을 숨기지 않는다.**"""
    assert art["c2_metric_decided"] is False
    assert art["c2_metric"] is None
    assert art["c2_metric_candidates"]


def test_frozen_gate_constants_are_recorded(art):
    g = art["frozen_gate_constants"]
    assert g["C1_threshold_videos"] == 0
    assert g["C1_statuses"] == ["PRESENT", "ABSENT", "UNCLEAR"]
    assert g["C1_repetition_min_run"] == 3
    assert g["C2_statistic"] == "median" and g["C2_threshold"] == 0.70
    assert g["C3_statistic"] == "max" and g["C3_threshold"] == 2.0


def test_verify_reports_no_drift_right_after_build(art):
    assert F.verify(art) == []


def test_verify_detects_drift(art):
    bad = {**art, "evaluator_source_sha256":
           {**art["evaluator_source_sha256"], "m8_metrics": "0" * 64}}
    diffs = F.verify(bad)
    assert any("m8_metrics" in d for d in diffs)


def test_build_refuses_when_gt_not_frozen(tmp_path):
    with pytest.raises(Exception):
        F.build_artifact(run_tests=False, gt_dir=tmp_path)
