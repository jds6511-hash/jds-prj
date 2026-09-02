"""E-02 DET 감사 — 결정성 7건의 증거 귀속.

`fixed_window`이므로 deterministic할 것이다 — **이 추론을 PASS로 쓰지 않는다.**
계약마다 실제 실행 증거를 요구하고, 없으면 UNPROVEN으로 적었다.

```
감사(귀속)   PROVEN 2   DET-001 · DET-006
            UNPROVEN 5  DET-002 · 003 · 004 · 005 · 007   전부 evidence-gap
보강(E-02)   증거 테스트 추가 → PROVEN 7 · UNPROVEN 0
production 변경  없음
```

원 판정을 지우지 않는다. 무엇이 부족했고 무엇으로 닫혔는지가 기록이다. 상세는
`docs/finalization/V2_1_E02_DET_AUDIT_2026-09-02.md`.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
AUDIT = ROOT / "docs/finalization/V2_1_E02_DET_AUDIT_2026-09-02.md"

#: 감사 시점에 이미 실행 증거가 있던 것.
DET_PROVEN_BY_ATTRIBUTION = {
    "DET-001": [
        "test_v2_1_fixed_window.py::test_fw_001_identical_input_gives_identical_partition",
        "test_v2_1_aar.py::test_aar_006_structure_is_identical_across_runs",
        "test_v2_1_partition.py::test_builder_output_passes_the_independent_validator",
        "test_v2_1_episode.py::test_episodes_build_from_the_fixed_window_partition",
    ],
    "DET-006": [
        "test_v2_1_det_evidence.py::test_det_006_ids_and_ordering_survive_an_independent_rebuild",
        "test_v2_1_aar.py::test_aar_007_roundtrip_preserves_meaning",
        "test_v2_1_lineage.py::test_lineage_survives_a_roundtrip",
        "test_v2_1_aar.py::test_aar_007_serialization_is_deterministic",
    ],
}

#: 감사에서 UNPROVEN이었고 E-02 증거 테스트로 닫힌 것. 부분 증거는 지우지 않고
#: 새 증거를 앞에 둔다.
DET_CLOSED_BY_EVIDENCE = {
    "DET-002": [
        "test_v2_1_det_evidence.py::test_det_002_at_least_three_reruns_give_the_same_structure",
        "test_v2_1_det_evidence.py::test_det_002_reruns_of_the_full_pipeline_keep_the_same_structure",
        "test_v2_1_fixed_window.py::test_fw_001_identical_input_gives_identical_partition",
    ],
    "DET-003": [
        "test_v2_1_det_evidence.py::test_det_003_a_different_llm_output_does_not_move_the_partition",
        "test_v2_1_failure_injection.py::test_model_failure_does_not_lose_structure",
        "test_v2_1_aar.py::test_aar_006_signature_ignores_content",
    ],
    "DET-004": [
        "test_v2_1_det_evidence.py::test_det_004_a_different_vlm_caption_does_not_move_the_boundary",
        "test_v2_1_det_evidence.py::test_det_004_the_caption_change_is_visible_somewhere_else",
        "test_v2_1_fixed_window.py::test_fw_002_to_005_same_grid_different_content_same_partition",
        "test_v2_1_err_evidence.py::test_err_010_an_instruction_echo_peak_does_not_move_the_fixed_window",
    ],
    "DET-005": [
        "test_v2_1_det_evidence.py::test_det_005_changed_ocr_does_not_move_the_boundary",
        "test_v2_1_det_evidence.py::test_det_005_the_ocr_change_is_visible_in_the_timeline",
        "test_v2_1_fixed_window.py::test_provider_does_not_read_content_channels",
    ],
    "DET-007": [
        "test_v2_1_det_evidence.py::test_det_007_parallel_runs_do_not_interfere",
        "test_v2_1_det_evidence.py::test_det_007_a_shared_registry_is_safe_under_concurrent_reads",
    ],
}

DET_PROVEN = {**DET_PROVEN_BY_ATTRIBUTION, **DET_CLOSED_BY_EVIDENCE}

#: 아직 증거가 없는 것. E-02로 비었다 — dict을 지우지 않는다.
DET_UNPROVEN = {}

#: 계약 핵심어. 개수가 아니라 "그 계약을 재는 테스트가 있는가"를 본다.
REQUIRED_KEYWORD = {
    "DET-001": "identical_partition",
    "DET-002": "three_reruns",
    "DET-003": "different_llm",
    "DET-004": "different_vlm_caption",
    "DET-005": "changed_ocr",
    "DET-006": "independent_rebuild",
    "DET-007": "parallel",
}


def _matrix_det():
    text = MATRIX.read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*(DET-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                           text, re.M))


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(re.search(r"^def %s\(" % re.escape(function),
                          path.read_text(encoding="utf-8"), re.M))


# ── 감사 범위가 matrix와 맞는가 ──────────────────────────────────────────
def test_the_audit_covers_every_det_item():
    rows = _matrix_det()
    assert len(rows) == 7
    assert sum(1 for p in rows.values() if p == "P0") == 5
    assert sum(1 for p in rows.values() if p == "P1") == 2
    assert set(rows) == set(DET_PROVEN) | set(DET_UNPROVEN)


def test_the_tally_is_seven_and_zero():
    assert len(DET_PROVEN) == 7
    assert DET_UNPROVEN == {}
    rows = _matrix_det()
    assert sum(1 for i in DET_PROVEN if rows[i] == "P0") == 5
    assert sum(1 for i in DET_PROVEN if rows[i] == "P1") == 2


def test_attribution_and_closure_do_not_overlap():
    assert not set(DET_PROVEN_BY_ATTRIBUTION) & set(DET_CLOSED_BY_EVIDENCE)


# ── 증거가 실재하는가 ────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(DET_PROVEN))
def test_every_proven_id_has_existing_evidence(acceptance_id):
    missing = [node for node in DET_PROVEN[acceptance_id] if not _defined(node)]
    assert not missing, "%s: %r" % (acceptance_id, missing)


def test_any_remaining_partial_evidence_still_has_to_exist():
    for acceptance_id, nodes in DET_UNPROVEN.items():
        missing = [node for node in nodes if not _defined(node)]
        assert not missing, "%s: %r" % (acceptance_id, missing)


@pytest.mark.parametrize("acceptance_id", sorted(REQUIRED_KEYWORD))
def test_each_id_keeps_the_test_that_measures_its_contract(acceptance_id):
    keyword = REQUIRED_KEYWORD[acceptance_id]
    assert any(keyword in node for node in DET_PROVEN[acceptance_id]), \
        (acceptance_id, keyword)


def test_the_keyword_map_covers_every_proven_id():
    assert set(REQUIRED_KEYWORD) == set(DET_PROVEN)


def test_no_proven_id_rests_only_on_a_shared_test():
    usage = {}
    for nodes in DET_PROVEN.values():
        for node in nodes:
            usage[node] = usage.get(node, 0) + 1
    for acceptance_id, nodes in DET_PROVEN.items():
        assert any(usage[node] == 1 for node in nodes), acceptance_id


# ── 계약별 요구를 뭉치지 않았는가 ────────────────────────────────────────
def test_the_three_perturbation_contracts_have_separate_evidence():
    """DET-003 · 004 · 005를 content-independent 하나로 묶지 않는다."""
    own = {}
    for acceptance_id in ("DET-003", "DET-004", "DET-005"):
        own[acceptance_id] = {
            node for node in DET_PROVEN[acceptance_id]
            if node.startswith("test_v2_1_det_evidence.py::")
        }
        assert own[acceptance_id], acceptance_id
    assert not own["DET-003"] & own["DET-004"]
    assert not own["DET-004"] & own["DET-005"]
    assert not own["DET-003"] & own["DET-005"]


def test_det_001_and_det_002_are_not_the_same_evidence():
    """입력 결정성과 N≥3 재실행은 별도 계약이다."""
    unique_002 = set(DET_PROVEN["DET-002"]) - set(DET_PROVEN["DET-001"])
    assert any("three_reruns" in node or "full_pipeline" in node
               for node in unique_002)


def test_det_002_evidence_actually_repeats_at_least_three_times():
    """N≥3을 문서 문구가 아니라 소스에서 확인한다."""
    source = (ROOT / "tests/test_v2_1_det_evidence.py").read_text(
        encoding="utf-8")
    found = re.search(r"^REPEATS = (\d+)", source, re.M)
    assert found and int(found.group(1)) >= 3, "REPEATS가 3 미만이다"


def test_det_007_evidence_actually_runs_things_concurrently():
    """병렬 증거가 실제로 동시 실행인지 — 구조 추론으로 대체하지 않는다."""
    source = (ROOT / "tests/test_v2_1_det_evidence.py").read_text(
        encoding="utf-8")
    assert "ThreadPoolExecutor" in source
    # worker마다 다른 입력을 줘야 thread 간 누출이 결과에 드러난다.
    assert re.search(r"^WORK = \(", source, re.M)
    assert len(re.findall(r'\("S\d", \d+\.\d+\)', source)) >= 4


# ── UNPROVEN을 조용히 닫지 않는다 ────────────────────────────────────────
def test_the_audit_keeps_the_original_verdict_as_history():
    text = AUDIT.read_text(encoding="utf-8")
    assert "PROVEN 2" in text and "UNPROVEN 5" in text
    for acceptance_id in DET_CLOSED_BY_EVIDENCE:
        assert re.search(r"%s[^\n]*UNPROVEN" % acceptance_id, text), acceptance_id


def test_the_audit_declares_det_closed():
    text = AUDIT.read_text(encoding="utf-8")
    assert "DET = CLOSED" in text
    assert "PROVEN 7" in text and "UNPROVEN 0" in text


def test_each_closed_gap_stays_classified():
    """증거 공백인가 구현 공백인가 — 닫힌 뒤에도 구분을 지우지 않는다."""
    text = AUDIT.read_text(encoding="utf-8")
    for acceptance_id in DET_CLOSED_BY_EVIDENCE:
        heading = "### %s" % acceptance_id
        assert heading in text, acceptance_id
        section = text.split(heading, 1)[1].split("### ", 1)[0]
        assert "evidence-gap" in section or "implementation-gap" in section, \
            acceptance_id


def test_the_missing_evidence_is_described_inside_its_own_section():
    text = AUDIT.read_text(encoding="utf-8")
    expected = {
        "DET-002": "N≥3",
        "DET-003": "A vs B",
        "DET-004": "perturbation 미검증",
        "DET-005": "실행 증거",
        "DET-007": "동시 실행",
    }
    for acceptance_id, phrase in expected.items():
        section = text.split("### %s" % acceptance_id, 1)[1].split("### ", 1)[0]
        assert phrase in section, (acceptance_id, phrase)


def test_byte_equality_is_not_claimed_for_det_002():
    """OPEN-4 — DET-002는 byte equality를 요구하지 않는다."""
    text = AUDIT.read_text(encoding="utf-8")
    assert "byte equality" in text
    assert "OPEN-4" in text


def test_det_is_wired_into_the_final_tally():
    final = (ROOT / "tests/test_v2_1_final_acceptance.py").read_text(
        encoding="utf-8")
    assert "tests/test_v2_1_det_acceptance.py" in final
