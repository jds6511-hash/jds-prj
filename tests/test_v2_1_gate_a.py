"""Gate A 집계 — acceptance ID가 실제 테스트로 덮여 있는가.

Gate A = `SCH · RAW · SAN · EVT · BPI · FW · CAN`의 P0 전부 + REG-001~004.

이 파일은 **덮개 지도**다. 각 ID가 어느 테스트로 확인되는지 적고, 그 테스트가
실제로 존재하는지 검사한다. 지도가 코드와 어긋나면 여기서 먼저 깨진다.

지도는 테스트를 다시 실행하지 않는다 — 실행은 전체 스위트가 한다. 여기서 막는
것은 **"통과했다"고 적어 놓고 대응 테스트가 사라지는 것**이다.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: acceptance ID → 그것을 확인하는 테스트. 한 ID가 여러 테스트로 갈릴 수 있다.
GATE_A_P0 = {
    # ── Schema / Parse contract ──────────────────────────────────────────
    "SCH-001": ["test_v2_1_segments.py::test_sch_001_canonical_schema_valid"],
    "SCH-002": ["test_v2_1_segments.py::test_sch_002_required_legacy_field_missing"],
    "SCH-003": ["test_v2_1_segments.py::test_sch_003_invalid_type"],
    "SCH-004": ["test_v2_1_parse.py::test_sch_004_malformed_json_is_a_contract_failure",
                "test_v2_1_parse.py::test_sch_004_no_structure_fallback"],
    "SCH-005": ["test_v2_1_parse.py::test_sch_005_blank_output_is_empty_not_a_failure",
                "test_v2_1_parse.py::test_sch_005_empty_is_not_model_failure"],
    "SCH-007": ["test_v2_1_parse.py::test_sch_007_instruction_echo_parses_fine",
                "test_v2_1_parse.py::test_sch_007_parser_does_not_import_sanitation"],
    "SCH-008": ["test_v2_1_parse.py::test_sch_008_notation_variants_normalize_to_one_value",
                "test_v2_1_parse.py::test_sch_008_non_references_are_not_invented"],
    "SCH-009": ["test_v2_1_parse.py::test_sch_009_model_failure_is_declared_never_inferred",
                "test_v2_1_parse.py::test_sch_009_status_vocabulary_is_closed"],
    # ── Raw persistence ──────────────────────────────────────────────────
    "RAW-001": ["test_v2_1_raw_store.py::test_raw_001_raw_is_on_disk_before_parse_runs",
                "test_v2_1_raw_store.py::test_raw_001_store_precedes_parse_in_source"],
    "RAW-002": ["test_v2_1_raw_store.py::test_raw_002_raw_survives_parse_failure"],
    "RAW-003": ["test_v2_1_raw_store.py::test_raw_003_source_type_is_recorded_and_traceable"],
    "RAW-004": ["test_v2_1_raw_store.py::test_raw_004_segment_id_is_recoverable",
                "test_v2_1_raw_store.py::test_raw_004_provenance_survives_a_fresh_store_object"],
    # ── Sanitation ───────────────────────────────────────────────────────
    "SAN-001": ["test_v2_1_sanitation.py::test_san_001_instruction_echo_does_not_pass_as_valid"],
    "SAN-002": ["test_v2_1_sanitation.py::test_san_002_blank_is_empty"],
    "SAN-005": ["test_v2_1_sanitation.py::test_san_005_parse_failure_is_its_own_state"],
    "SAN-007": ["test_v2_1_sanitation.py::test_san_007_ocr_is_never_claim_support_on_its_own"],
    "SAN-010": ["test_v2_1_sanitation.py::test_san_010_excited_repetition_within_one_utterance_is_preserved",
                "test_v2_1_sanitation.py::test_san_010_every_status_preserves_the_original_text"],
    "SAN-011": ["test_v2_1_sanitation.py::test_san_011_repetition_at_threshold_is_suspect",
                "test_v2_1_sanitation.py::test_open_7_repetition_is_never_a_rejection_ground"],
    # ── Evidence timeline ────────────────────────────────────────────────
    "EVT-001": ["test_v2_1_timeline.py::test_evt_001_refs_land_on_their_own_segment"],
    "EVT-002": ["test_v2_1_timeline.py::test_evt_002_missing_modality_is_empty_refs_not_a_failure"],
    "EVT-003": ["test_v2_1_timeline.py::test_evt_003_unresolvable_ref_fails_validation"],
    "EVT-004": ["test_v2_1_timeline.py::test_evt_004_timestamp_outside_its_segment_is_rejected"],
    "EVT-007": ["test_v2_1_timeline.py::test_evt_007_status_and_eligibility_are_carried_verbatim",
                "test_v2_1_timeline.py::test_evt_007_valid_but_unusable_ocr_survives_as_such"],
    "EVT-008": ["test_v2_1_timeline.py::test_evt_008_llm_source_type_is_refused_by_the_timeline"],
    # ── BoundaryProvider ─────────────────────────────────────────────────
    "BPI-001": ["test_v2_1_boundary.py::test_bpi_001_provider_identity_is_recorded"],
    "BPI-002": ["test_v2_1_boundary.py::test_bpi_002_config_is_recorded"],
    "BPI-003": ["test_v2_1_boundary.py::test_bpi_003_embeddings_are_named_caption_not_visual"],
    "BPI-004": ["test_v2_1_boundary.py::test_bpi_004_default_provider_name_is_fixed_window_v1",
                "test_v2_1_boundary.py::test_bpi_004_missing_default_is_an_explicit_error"],
    "BPI-005": ["test_v2_1_boundary.py::test_bpi_005_provider_failure_is_not_replaced",
                "test_v2_1_boundary.py::test_bpi_005_unknown_provider_does_not_fall_back"],
    # ── fixed_window_v1 ──────────────────────────────────────────────────
    "FW-001": ["test_v2_1_fixed_window.py::test_fw_001_identical_input_gives_identical_partition"],
    "FW-002": ["test_v2_1_fixed_window.py::test_fw_002_to_005_boundaries_ignore_every_content_channel"],
    "FW-003": ["test_v2_1_fixed_window.py::test_fw_002_to_005_same_grid_different_content_same_partition"],
    "FW-004": ["test_v2_1_fixed_window.py::test_fw_002_to_005_same_grid_different_content_same_partition"],
    "FW-005": ["test_v2_1_fixed_window.py::test_provider_does_not_read_content_channels"],
    "FW-006": ["test_v2_1_fixed_window.py::test_fw_006_exact_sixty_seconds_is_one_window"],
    "FW-007": ["test_v2_1_fixed_window.py::test_fw_007_partial_tail_is_included"],
    "FW-008": ["test_v2_1_fixed_window.py::test_fw_008_video_shorter_than_one_segment_is_a_single_window"],
    "FW-009": ["test_v2_1_fixed_window.py::test_fw_009_empty_segment_list_fails_explicitly",
               "test_v2_1_fixed_window.py::test_fw_009_non_positive_window_is_refused"],
    # ── Canonical partition ──────────────────────────────────────────────
    "CAN-001": ["test_v2_1_partition.py::test_can_001_to_003_a_correct_partition_passes"],
    "CAN-002": ["test_v2_1_partition.py::test_can_001_to_003_a_correct_partition_passes"],
    "CAN-003": ["test_v2_1_partition.py::test_can_003_every_segment_is_assigned_exactly_once"],
    "CAN-004": ["test_v2_1_partition.py::test_can_004_partition_not_starting_at_video_start_fails"],
    "CAN-005": ["test_v2_1_partition.py::test_can_005_end_is_the_last_segment_end_not_a_rounded_duration",
                "test_v2_1_partition.py::test_can_005_partition_not_ending_at_video_end_fails"],
    "CAN-006": ["test_v2_1_partition.py::test_can_006_out_of_order_spans_fail"],
    "CAN-007": ["test_v2_1_partition.py::test_can_007_reversed_span_fails"],
    "CAN-008": ["test_v2_1_partition.py::test_can_008_discontinuity_between_adjacent_spans_fails"],
    "CAN-009": ["test_v2_1_partition.py::test_can_009_unknown_segment_reference_fails"],
    "CAN-010": ["test_v2_1_partition.py::test_can_010_overlap_injection_fails"],
    "CAN-011": ["test_v2_1_partition.py::test_can_011_gap_injection_fails"],
    "CAN-012": ["test_v2_1_partition.py::test_can_012_duplicate_injection_fails"],
    "CAN-013": ["test_v2_1_partition.py::test_can_013_unassigned_injection_fails"],
}

GATE_A_P1 = {
    "SCH-006": ["test_v2_1_parse.py::test_sch_006_unknown_optional_field_is_preserved"],
    "RAW-005": ["test_v2_1_raw_store.py::test_raw_005_producer_metadata_is_preserved"],
    "RAW-006": ["test_v2_1_raw_store.py::test_raw_006_reruns_do_not_collide",
                "test_v2_1_run.py::test_raw_006_two_runs_of_one_video_do_not_share_a_directory"],
    "SAN-003": ["test_v2_1_sanitation.py::test_s6_echo_and_foreign_caption_are_flagged_differently"],
    "SAN-004": ["test_v2_1_sanitation.py::test_san_011_repetition_at_threshold_is_suspect"],
    "SAN-006": ["test_v2_1_sanitation.py::test_san_001_ordinary_caption_is_valid"],
    "SAN-008": ["test_v2_1_sanitation.py::test_san_007_asr_valid_is_usable"],
    "SAN-009": ["test_v2_1_sanitation.py::test_s6_echo_and_foreign_caption_are_flagged_differently"],
    "EVT-005": ["test_v2_1_timeline.py::test_evt_005_sparse_evidence_builds"],
    "EVT-006": ["test_v2_1_timeline.py::test_evt_006_rich_asr_is_carried"],
    "BPI-006": ["test_v2_1_boundary.py::test_bpi_002_absent_config_is_recorded_as_empty_not_missing"],
    "FW-010": ["test_v2_1_fixed_window.py::test_fw_010_long_input_is_deterministic"],
}

#: Gate A 밖이지만 함께 잠근 것들. 집계에 같이 적는다.
ADJACENT = {
    "RPT-008": ["test_v2_1_run.py::test_rpt_008_non_report_mode_refuses_rendering",
                "test_v2_1_run.py::test_rpt_008_refusal_does_not_coerce_the_mode"],
    "REG-005": ["test_v2_1_guards.py::test_reg_005_editing_a_frozen_file_fails"],
    "REG-006": ["test_v2_1_guards.py::test_reg_006_rewriting_the_official_result_fails"],
    "REG-007": ["test_v2_1_guards.py::test_reg_007_an_m9_run_artifact_fails"],
    "REG-008": ["test_v2_1_guards.py::test_reg_008_a_new_label_file_fails"],
    "REG-009": ["test_v2_1_guards.py::test_reg_009_changing_the_default_provider_fails"],
    "REF-003": ["test_v2_1_guards.py::test_ref_003_a_new_comparison_artifact_fails"],
}

ALL = {**GATE_A_P0, **GATE_A_P1, **ADJACENT}


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(
        re.search(r"^def %s\(" % re.escape(function), path.read_text(encoding="utf-8"),
                  re.M)
    )


@pytest.mark.parametrize("acceptance_id", sorted(ALL))
def test_every_mapped_test_exists(acceptance_id):
    missing = [node for node in ALL[acceptance_id] if not _defined(node)]
    assert not missing, "%s의 대응 테스트가 없다: %r" % (acceptance_id, missing)


def test_the_map_covers_every_gate_a_p0_in_the_matrix():
    """matrix에서 직접 읽는다 — 지도를 손으로 맞추다 빠뜨리는 것을 막는다."""
    matrix = (ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md").read_text(
        encoding="utf-8"
    )
    rows = re.findall(r"^\|\s*([A-Z]+-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|", matrix, re.M)
    sections = ("SCH", "RAW", "SAN", "EVT", "BPI", "FW", "CAN")
    p0 = {i for i, priority in rows
          if priority == "P0" and i.split("-")[0] in sections}
    assert p0 - set(GATE_A_P0) == set(), "지도에 없는 Gate A P0: %r" % sorted(
        p0 - set(GATE_A_P0)
    )


def test_the_map_covers_every_gate_a_p1_in_the_matrix():
    matrix = (ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md").read_text(
        encoding="utf-8"
    )
    rows = re.findall(r"^\|\s*([A-Z]+-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|", matrix, re.M)
    sections = ("SCH", "RAW", "SAN", "EVT", "BPI", "FW", "CAN")
    p1 = {i for i, priority in rows
          if priority == "P1" and i.split("-")[0] in sections}
    assert p1 - set(GATE_A_P1) == set(), "지도에 없는 Gate A P1: %r" % sorted(
        p1 - set(GATE_A_P1)
    )


def test_gate_a_p0_count_is_fifty():
    assert len(GATE_A_P0) == 51        # matrix 50 + 신설 EVT-008
    assert "EVT-008" in GATE_A_P0
