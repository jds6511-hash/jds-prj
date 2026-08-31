"""B-09 Gate B 집계 — acceptance ID ↔ 테스트 지도.

Gate B = `LLM · GRD · AAR`.

```
matrix P0   22   전부 테스트로 덮인다
matrix P1    7   6 PASS + 1 WAIVED (GRD-004)
```

**matrix 통과와 Gate B 완료 선언은 다르다.** 두 층 모두 문서와 대조해 고정한다.
closure는 2026-08-31에 `BLOCKED`(OPEN-10)에서 `COMPLETE`로 바뀌었고, **푼 근거와
막았던 기록이 둘 다 남아 있는지**까지 검사한다. 잔여 결함 OPEN-11은 non-blocking
으로 등록되며 waiver로 덮이지 않아야 한다.

지도가 코드·문서와 어긋나면 여기서 먼저 깨진다.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
TICKETS = ROOT / "docs/finalization/V2_1_GATE_B_TICKETS_2026-08-30.md"
WAIVERS = ROOT / "docs/finalization/V2_1_P1_WAIVERS.md"
INTEGRATION = ROOT / "runs/v2_1/b02b_integration_run2.json"

GATE_B_P0 = {
    "LLM-001": ["test_v2_1_episode.py::test_llm_001_episode_times_come_from_segments",
                "test_v2_1_episode.py::test_llm_001_builder_takes_no_model_output"],
    "LLM-002": ["test_v2_1_episode.py::test_llm_002_model_fields_are_exactly_three",
                "test_v2_1_prompt.py::test_llm_002_required_output_is_summary_only",
                "test_v2_1_prompt.py::test_llm_002_prompt_does_not_ask_for_derived_fields"],
    "LLM-003": ["test_v2_1_episode.py::test_llm_003_episode_ids_are_code_derived_and_ordered"],
    "LLM-004": ["test_v2_1_episode.py::test_llm_004_support_span_equals_the_episode_span",
                "test_v2_1_episode.py::test_llm_004_anchors_are_start_middle_end"],
    "LLM-005": ["test_v2_1_episode.py::test_llm_005_source_is_stt_when_usable_speech_exists",
                "test_v2_1_episode.py::test_llm_005_suspect_speech_does_not_make_it_stt"],
    "LLM-009": ["test_v2_1_content.py::test_llm_009_model_failure_keeps_the_episode_structure",
                "test_v2_1_content.py::test_llm_009_every_episode_survives_a_partial_outage",
                "test_v2_1_llm_adapter.py::test_generator_exception_is_model_failure"],
    "GRD-001": ["test_v2_1_grounding.py::test_grd_001_valid_refs_pass"],
    "GRD-002": ["test_v2_1_grounding.py::test_grd_002_nonexistent_ref_is_a_reference_failure",
                "test_v2_1_grounding.py::test_grd_002_existing_segment_without_evidence_is_distinguished"],
    "GRD-003": ["test_v2_1_grounding.py::test_grd_003_outside_episode_ref_fails",
                "test_v2_1_grounding.py::test_grd_003_outside_is_not_reported_as_a_missing_reference"],
    "GRD-005": ["test_v2_1_grounding.py::test_grd_005_unsupported_number_in_the_claim_fails",
                "test_v2_1_grounding.py::test_grd_005_supported_anchor_passes"],
    "GRD-006": ["test_v2_1_grounding.py::test_grd_006_ocr_only_evidence_cannot_support_a_claim",
                "test_v2_1_grounding.py::test_grd_006_ocr_evidence_is_never_usable"],
    "GRD-008": ["test_v2_1_grounding.py::test_grd_008_status_is_attached_to_the_binding",
                "test_v2_1_aar.py::test_aar_004_failure_reasons_are_serialized"],
    "GRD-009": ["test_v2_1_grounding.py::test_grd_009_failure_removes_dialogue_but_keeps_summary",
                "test_v2_1_grounding.py::test_grd_009_failure_is_not_reported_as_pass",
                "test_v2_1_failure_injection.py::test_serializer_carries_every_grounding_status_verbatim"],
    "GRD-010": ["test_v2_1_grounding.py::test_grd_010_dialogue_without_any_cite_fails",
                "test_v2_1_grounding.py::test_grd_010_is_not_confused_with_ineligible_support"],
    "GRD-011": ["test_v2_1_grounding.py::test_grd_011_suspect_only_support_is_ineligible",
                "test_v2_1_grounding.py::test_grd_011_is_not_a_reference_failure"],
    "GRD-012": ["test_v2_1_grounding.py::test_grd_012_valid_plus_suspect_passes_on_the_valid_one",
                "test_v2_1_grounding.py::test_grd_012_suspect_beside_valid_does_not_auto_pass",
                "test_v2_1_grounding.py::test_grd_012_ineligible_cite_is_still_recorded_when_valid_exists"],
    "AAR-001": ["test_v2_1_aar.py::test_aar_001_document_is_valid_on_its_own"],
    "AAR-002": ["test_v2_1_aar.py::test_aar_002_every_episode_is_present",
                "test_v2_1_aar.py::test_aar_002_a_missing_episode_is_refused"],
    "AAR-003": ["test_v2_1_aar.py::test_aar_003_every_episode_carries_provenance"],
    "AAR-004": ["test_v2_1_aar.py::test_aar_004_grounding_status_is_present_on_every_episode",
                "test_v2_1_aar.py::test_aar_004_failure_is_not_normalized_to_pass"],
    "AAR-005": ["test_v2_1_aar.py::test_aar_005_presentation_keys_inside_an_episode_are_refused",
                "test_v2_1_aar.py::test_aar_005_episode_list_is_the_fixed_point"],
    "AAR-006": ["test_v2_1_aar.py::test_aar_006_structure_is_identical_across_runs",
                "test_v2_1_aar.py::test_aar_006_byte_equality_is_not_required"],
}

GATE_B_P1 = {
    "LLM-006": ["test_v2_1_llm_p1_contract.py::test_llm_006_caption_only_episode_builds_a_prompt"],
    "LLM-007": ["test_v2_1_llm_p1_contract.py::test_llm_007_asr_only_episode_builds_a_prompt"],
    "LLM-008": ["test_v2_1_prompt.py::test_episode_without_usable_evidence_is_refused"],
    "LLM-010": ["test_v2_1_llm_p1_contract.py::test_llm_010_eligible_speech_reaches_the_evidence_block"],
    "GRD-007": ["test_v2_1_grounding.py::test_grd_012_ineligible_cite_is_still_recorded_when_valid_exists"],
    "AAR-007": ["test_v2_1_aar.py::test_aar_007_roundtrip_preserves_meaning"],
}

#: 테스트가 아니라 waiver로 닫은 항목.
GATE_B_WAIVED = {"GRD-004"}

#: B-02b 실모델 실행으로만 확인되는 것. 테스트가 아니라 산출물이 근거다.
INTEGRATION_CONFIRMED = ("LLM-006", "LLM-007", "LLM-010")

ALL = {**GATE_B_P0, **GATE_B_P1}


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(re.search(r"^def %s\(" % re.escape(function),
                          path.read_text(encoding="utf-8"), re.M))


def _matrix_ids(priority):
    rows = re.findall(r"^\|\s*([A-Z]+-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                      MATRIX.read_text(encoding="utf-8"), re.M)
    return {i for i, p in rows
            if p == priority and i.split("-")[0] in ("LLM", "GRD", "AAR")}


# ── 지도가 실재하는가 ────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(ALL))
def test_every_mapped_test_exists(acceptance_id):
    missing = [node for node in ALL[acceptance_id] if not _defined(node)]
    assert not missing, "%s의 대응 테스트가 없다: %r" % (acceptance_id, missing)


def test_the_map_covers_every_gate_b_p0():
    assert _matrix_ids("P0") - set(GATE_B_P0) == set()


def test_the_map_covers_every_gate_b_p1():
    uncovered = _matrix_ids("P1") - set(GATE_B_P1) - GATE_B_WAIVED
    assert uncovered == set(), "지도에 없는 P1: %r" % sorted(uncovered)


def test_counts_match_the_matrix():
    assert len(GATE_B_P0) == 22
    assert len(GATE_B_P1) + len(GATE_B_WAIVED) == 7


def test_waived_ids_have_no_test_and_a_registered_waiver():
    """waiver는 테스트 부재를 정당화하는 유일한 경로다. skip은 waiver가 아니다."""
    register = WAIVERS.read_text(encoding="utf-8")
    for acceptance_id in GATE_B_WAIVED:
        assert acceptance_id not in ALL
        assert acceptance_id in register
        assert "WAIVED" in register


# ── 실모델 integration 근거 ──────────────────────────────────────────────
def test_integration_artifact_exists():
    assert INTEGRATION.is_file()


def test_integration_confirmed_the_three_p1_paths():
    report = json.loads(INTEGRATION.read_text(encoding="utf-8"))
    assert report["status"] == "COMPLETE"
    by_id = {c["acceptance_id"]: c for c in report["cases"]}
    assert set(by_id) == set(INTEGRATION_CONFIRMED)
    for case in by_id.values():
        assert case["content_status"] == "VALID_PARSE"
        assert case["episode_structure_intact"] is True
        assert case["raw_ref"]


def test_integration_used_the_decided_model():
    report = json.loads(INTEGRATION.read_text(encoding="utf-8"))
    assert report["model_id"] == "Qwen/Qwen2.5-7B-Instruct"
    assert report["generation"]["do_sample"] is False
    assert "none" in report["quantization"]


def test_integration_did_not_compare_models():
    report = json.loads(INTEGRATION.read_text(encoding="utf-8"))
    blob = json.dumps(report, ensure_ascii=False)
    for forbidden in ("kanana", "qwen3", "exaone", "temperature_sweep"):
        assert forbidden not in blob.lower(), "모델 비교 흔적: " + forbidden


# ── 통과와 완료를 가른다 ─────────────────────────────────────────────────
def test_matrix_acceptance_is_recorded_as_pass():
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "MATRIX ACCEPTANCE = PASS" in tickets


def test_gate_b_closure_is_recorded_as_complete():
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "GATE B CLOSURE = COMPLETE" in tickets
    assert "OPEN-10 — Prompt example placeholder leakage  **CLOSED" in tickets


def test_the_earlier_blocked_verdict_is_not_erased():
    """판정을 바꿀 때 앞의 판정을 지우면 왜 막혔는지가 사라진다."""
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "GATE B CLOSURE = BLOCKED" in tickets
    assert "2026-08-31 이전" in tickets


def test_open_11_is_registered_as_a_known_non_blocking_defect():
    """닫으면서 남은 결함을 참고사항으로 낮추지 않는다."""
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "OPEN-11" in tickets
    assert "NON-BLOCKING" in tickets
    assert "runs/v2_1/b02b_integration_run3.json" in tickets


def test_open_11_is_not_folded_into_the_grd_004_waiver():
    register = WAIVERS.read_text(encoding="utf-8")
    assert "OPEN-11" not in register


def test_gate_c_must_not_consume_pre_grounding_content():
    """OPEN-11이 non-blocking인 전제는 grounding을 지나야 밖으로 나간다는 것이다.

    Gate C가 B-06 이전 content를 주워 가면 그 전제가 깨진다. 요구를 문서에
    고정해 두고, Gate C 착수 때 실제 interlock으로 구현한다.
    """
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "presentation input에 재등장 금지" in tickets
    assert "pre-grounding" in tickets


def test_open_10_is_not_folded_into_the_grd_004_waiver():
    """GRD-004 waiver는 semantic entailment 한계에 대한 것이다.

    프롬프트가 넣어 둔 placeholder가 복사되는 것은 재현 가능한 구현 결함이라
    기존 waiver 범위를 넓혀 덮으면 waiver가 너무 많은 것을 덮게 된다.
    """
    register = WAIVERS.read_text(encoding="utf-8")
    assert "OPEN-10" not in register
    assert "placeholder" not in register.lower()


def test_the_defect_is_reproducible_from_the_stored_run():
    """주장이 아니라 산출물로 남아 있어야 한다.

    OPEN-10을 닫아도 **결함이 있었다는 증거는 지우지 않는다** — run 2 산출물이
    사라지면 "고쳤다"를 검증할 방법이 없다(대조는 open10 follow-up이 한다).
    """
    report = json.loads(INTEGRATION.read_text(encoding="utf-8"))
    notes = [c["dialogue_note"] for c in report["cases"]]
    assert "선택" in notes, "결함 증거가 산출물에 없다"
