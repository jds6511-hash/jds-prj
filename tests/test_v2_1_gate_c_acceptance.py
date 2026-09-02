"""C-10 Gate C 집계 — acceptance ID ↔ 테스트 지도.

Gate C = `HLT · REF · GLS · RPT`.

```
matrix   29   P0 19 · P1 10
waiver    0
```

**새 동작을 만들지 않는다.** 이미 있는 증거를 ID에 귀속시키고, 지도가 코드·문서와
어긋나면 여기서 먼저 깨지게 한다.

한 ID에 테스트가 여럿 붙는 것은 정상이다(`RPT-003 · 004`는 Markdown과 HWPX 양쪽에서
증명된다). 반대로 **테스트 하나가 green이라고 비슷해 보이는 ID 여럿을 근거 없이
PASS로 적지 않는다** — ID마다 구체적인 테스트 이름을 남긴다.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
TICKETS = ROOT / "docs/finalization/V2_1_GATE_C_TICKETS_2026-08-31.md"
WAIVERS = ROOT / "docs/finalization/V2_1_P1_WAIVERS.md"

#: ID → (담당 티켓, 증거 테스트). 파일::함수로 적어 실재를 확인한다.
GATE_C = {
    # ── Highlight (C-02 · C-03 · C-08) ──────────────────────────────────
    "HLT-001": ("C-03", [
        "test_v2_1_lineage.py::test_hlt_001_every_highlight_carries_at_least_one_source",
        "test_v2_1_lineage.py::test_hlt_001_sources_are_real_canonical_episodes",
        "test_v2_1_lineage.py::test_lineage_comes_from_the_grouping_not_from_the_display_range",
    ]),
    "HLT-002": ("C-02", [
        "test_v2_1_highlight.py::test_hlt_002_highlights_may_overlap_in_time",
        "test_v2_1_lineage.py::test_overlapping_highlights_keep_separate_lineage",
    ]),
    "HLT-003": ("C-02", [
        "test_v2_1_highlight.py::test_hlt_003_canonical_structure_is_unchanged",
        "test_v2_1_highlight.py::test_the_episode_list_itself_is_not_reordered_or_trimmed",
    ]),
    "HLT-004": ("C-02", [
        "test_v2_1_highlight.py::test_hlt_004_highlight_count_follows_the_input",
        "test_v2_1_highlight.py::test_hlt_004_one_highlight_over_everything_is_allowed",
        "test_v2_1_highlight.py::test_hlt_004_no_group_at_all_is_allowed",
        "test_v2_1_highlight.py::test_hlt_004_many_highlights_are_not_capped",
        "test_v2_1_highlight.py::test_hlt_004_source_declares_no_target_count",
    ]),
    "HLT-005": ("C-02", [
        "test_v2_1_highlight.py::test_hlt_005_several_episodes_merge_into_one_highlight",
    ]),
    "HLT-006": ("C-02", [
        "test_v2_1_highlight.py::test_hlt_006_the_same_episode_may_join_two_highlights",
        "test_v2_1_lineage.py::test_a_shared_episode_is_recorded_in_every_highlight",
    ]),
    "HLT-007": ("C-02", [
        "test_v2_1_highlight.py::test_hlt_007_episode_boundaries_cannot_be_written",
        "test_v2_1_highlight.py::test_hlt_003_canonical_structure_is_unchanged",
    ]),
    "HLT-008": ("C-08", [
        "test_v2_1_render_fallback.py::test_hlt_008_a_highlight_without_a_summary_still_renders",
        "test_v2_1_render_fallback.py::test_hlt_008_a_weak_highlight_is_not_dropped",
        "test_v2_1_render_fallback.py::test_hlt_008_weak_highlights_are_not_merged",
        "test_v2_1_render_fallback.py::test_hlt_008_provenance_survives_when_the_content_does_not",
        "test_v2_1_render_fallback.py::test_hlt_008_no_highlight_at_all_is_still_a_document",
    ]),

    # ── 형식 참조 (C-05 · A-11 기존 가드) ────────────────────────────────
    "REF-001": ("C-05", [
        "test_v2_1_presentation.py::test_ref_001_the_format_reference_names_its_author",
    ]),
    "REF-002": ("C-05", [
        "test_v2_1_presentation.py::test_ref_002_the_format_reference_is_not_ground_truth",
        "test_v2_1_presentation.py::test_ref_002_a_ground_truth_claim_is_reported",
    ]),
    "REF-003": ("A-11", [
        "test_v2_1_guards.py::test_ref_003_preexisting_artifact_is_not_a_violation",
        "test_v2_1_guards.py::test_ref_003_a_new_comparison_artifact_fails",
    ]),
    # REF-004는 전용 테스트가 없다. 세 갈래가 함께 덮는다 — 문서에 그렇게 적었다.
    "REF-004": ("A-11 + A-07/08 + C-05", [
        "test_v2_1_guards.py::test_reg_009_changing_the_default_provider_fails",
        "test_v2_1_boundary.py::test_bpi_004_default_provider_name_is_fixed_window_v1",
        "test_v2_1_fixed_window.py::test_window_is_sixty_seconds",
        "test_v2_1_presentation.py::test_ref_005_no_row_count_is_read_from_the_format_reference",
    ]),
    "REF-005": ("C-05", [
        "test_v2_1_presentation.py::test_ref_005_any_number_of_highlights_serializes_the_same_way",
        "test_v2_1_presentation.py::test_ref_005_no_row_count_is_read_from_the_format_reference",
        "test_v2_1_highlight.py::test_hlt_004_many_highlights_are_not_capped",
    ]),
    "REF-006": ("C-05", [
        "test_v2_1_presentation.py::test_ref_006_only_section_names_come_from_the_reference",
        "test_v2_1_presentation.py::test_ref_006_no_sentence_from_the_human_report_reaches_the_output",
        "test_v2_1_presentation.py::test_ref_006_no_time_range_from_the_human_report_is_used",
    ]),

    # ── Global synthesis (C-04) ─────────────────────────────────────────
    "GLS-001": ("C-04", [
        "test_v2_1_synthesis.py::test_gls_001_overview_is_built_from_canonical_summaries",
    ]),
    "GLS-002": ("C-04", [
        "test_v2_1_synthesis.py::test_gls_002_analysis_is_structured_by_highlight",
    ]),
    "GLS-003": ("C-04", [
        "test_v2_1_synthesis.py::test_gls_003_conclusion_stays_inside_the_supported_range",
    ]),
    "GLS-004": ("C-04", [
        "test_v2_1_synthesis.py::test_gls_004_limitation_is_always_stated",
        "test_v2_1_synthesis.py::test_gls_004_no_assurance_wording_is_emitted",
        "test_v2_1_synthesis.py::test_gls_004_injected_assurance_wording_is_reported",
        "test_v2_1_synthesis.py::test_gls_004_a_missing_limitation_is_reported",
    ]),
    "GLS-005": ("C-04", [
        "test_v2_1_synthesis.py::test_gls_005_sources_resolve_to_canonical_episodes",
        "test_v2_1_synthesis.py::test_gls_005_an_unknown_source_is_reported",
        "test_v2_1_synthesis.py::test_gls_005_text_without_any_source_is_reported",
    ]),
    "GLS-006": ("C-04", [
        "test_v2_1_synthesis.py::test_gls_006_failed_episodes_are_excluded",
        "test_v2_1_synthesis.py::test_gls_006_a_mixed_video_keeps_only_the_usable_part",
        "test_v2_1_synthesis.py::test_gls_006_dialogue_is_never_a_synthesis_source",
        "test_v2_1_synthesis.py::test_gls_006_an_excluded_episode_named_as_source_is_reported",
        "test_v2_1_open11_e2e.py::test_case_d_passing_dialogue_still_never_becomes_presentation_content",
    ]),
    "GLS-007": ("C-04", [
        "test_v2_1_synthesis.py::test_gls_007_all_sources_usable_is_sufficient",
        "test_v2_1_synthesis.py::test_gls_007_no_reliable_content_produces_no_concrete_conclusion",
        "test_v2_1_synthesis.py::test_gls_007_a_concrete_conclusion_without_sources_is_reported",
    ]),

    # ── Report (C-01 · C-06 · C-07 · C-08) ──────────────────────────────
    "RPT-001": ("C-01 + C-06", [
        "test_v2_1_presentation_input.py::test_a_validated_canonical_document_is_accepted",
        "test_v2_1_render.py::test_rpt_001_preview_and_markdown_carry_the_same_identity",
        "test_v2_1_render.py::test_rpt_001_both_render_from_the_same_semantic_view",
        "test_v2_1_render.py::test_rpt_001_each_preview_row_carries_its_own_lineage",
        "test_v2_1_render.py::test_rpt_001_the_run_identity_is_shown",
    ]),
    "RPT-002": ("C-03 + C-06/07", [
        "test_v2_1_lineage.py::test_rpt_002_reordering_highlights_does_not_touch_canonical_identity",
        "test_v2_1_lineage.py::test_rpt_002_relabelling_does_not_change_lineage",
        "test_v2_1_lineage.py::test_rpt_002_source_records_carry_canonical_identity",
        "test_v2_1_render.py::test_rpt_003_lineage_is_not_reconstructed",
        "test_v2_1_render_hwpx.py::test_each_block_carries_its_own_lineage",
        "test_v2_1_render_hwpx.py::test_a_block_does_not_borrow_another_blocks_sources",
    ]),
    "RPT-003": ("C-06 + C-07", [
        "test_v2_1_render.py::test_rpt_003_times_come_from_the_artifact_not_from_a_recomputation",
        "test_v2_1_render.py::test_rpt_003_no_time_arithmetic_in_the_renderer",
        "test_v2_1_render_hwpx.py::test_rpt_003_times_come_from_the_artifact",
        "test_v2_1_render_hwpx.py::test_rpt_003_no_time_arithmetic_in_the_renderer",
        "test_v2_1_render_hwpx.py::test_rpt_003_highlights_are_not_regrouped",
    ]),
    "RPT-004": ("C-06 ↔ C-07", [
        "test_v2_1_render.py::test_rpt_004_the_two_outputs_differ_in_form",
        "test_v2_1_render.py::test_rpt_004_summaries_appear_in_both",
        "test_v2_1_render_hwpx.py::test_rpt_004_the_two_documents_look_different",
        "test_v2_1_render_hwpx.py::test_rpt_004_the_semantic_projection_is_identical",
        "test_v2_1_render_hwpx.py::test_rpt_004_a_missing_highlight_breaks_the_projection",
        "test_v2_1_render_hwpx.py::test_the_absence_reads_the_same_in_both_documents",
    ]),
    "RPT-005": ("C-01", [
        "test_v2_1_presentation_input.py::test_a_pre_grounding_object_is_refused",
        "test_v2_1_presentation_input.py::test_a_bare_episode_list_is_refused",
        "test_v2_1_presentation_input.py::test_the_module_does_not_import_pre_grounding_layers",
        "test_v2_1_open11_e2e.py::test_the_presentation_layer_cannot_reach_upstream_objects",
    ]),
    "RPT-006": ("C-08", [
        "test_v2_1_render_fallback.py::test_rpt_006_a_failed_hwpx_falls_back_to_markdown",
        "test_v2_1_render_fallback.py::test_rpt_006_the_chain_continues_to_preview",
        "test_v2_1_render_fallback.py::test_rpt_006_the_fallback_carries_the_same_semantics",
        "test_v2_1_render_fallback.py::test_rpt_006_the_fallback_does_not_touch_the_artifacts",
        "test_v2_1_render_fallback.py::test_rpt_006_every_format_failing_is_reported_not_faked",
    ]),
    "RPT-007": ("C-08", [
        "test_v2_1_render_fallback.py::test_rpt_007_an_invalid_structure_never_reaches_a_renderer",
        "test_v2_1_render_fallback.py::test_rpt_007_a_broken_lineage_is_not_repaired",
        "test_v2_1_render_fallback.py::test_rpt_007_structural_failure_is_not_a_fallback_case",
        "test_v2_1_render_fallback.py::test_rpt_007_the_module_does_not_rebuild_anything",
    ]),
    "RPT-008": ("C-06 + C-07", [
        "test_v2_1_render.py::test_rpt_008_preview_mode_refuses_report_rendering",
        "test_v2_1_render.py::test_rpt_008_the_manifest_is_not_rewritten",
        "test_v2_1_render.py::test_rpt_008_the_interlock_is_the_a_02_one",
        "test_v2_1_render_hwpx.py::test_hwpx_is_not_a_second_entry_point_around_the_interlock",
        "test_v2_1_render_fallback.py::test_rpt_007_the_interlock_is_not_bypassed_by_falling_back",
    ]),
}

#: Gate C에는 waiver가 없다. 있으면 대장에 있어야 하고, 그때는 이 집합이 바뀐다.
GATE_C_WAIVED: set[str] = set()

_PREFIXES = ("HLT", "REF", "GLS", "RPT")


def _matrix_rows():
    rows = re.findall(r"^\|\s*([A-Z]+-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                      MATRIX.read_text(encoding="utf-8"), re.M)
    return {i: p for i, p in rows if i.split("-")[0] in _PREFIXES}


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(re.search(r"^def %s\(" % re.escape(function),
                          path.read_text(encoding="utf-8"), re.M))


# ── 지도가 matrix와 일치하는가 ───────────────────────────────────────────
def test_the_map_covers_exactly_the_matrix():
    expected = set(_matrix_rows())
    mapped = set(GATE_C) | GATE_C_WAIVED
    assert mapped - expected == set(), "matrix에 없는 ID: %r" % sorted(mapped - expected)
    assert expected - mapped == set(), "지도에 없는 ID: %r" % sorted(expected - mapped)


def test_the_counts_match_the_matrix():
    rows = _matrix_rows()
    assert len(rows) == 29
    assert sum(1 for p in rows.values() if p == "P0") == 19
    assert sum(1 for p in rows.values() if p == "P1") == 10


def test_each_family_has_the_expected_size():
    rows = _matrix_rows()
    sizes = {prefix: sum(1 for i in rows if i.startswith(prefix))
             for prefix in _PREFIXES}
    assert sizes == {"HLT": 8, "REF": 6, "GLS": 7, "RPT": 8}


# ── 증거가 실재하는가 ────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(GATE_C))
def test_every_mapped_test_exists(acceptance_id):
    _, nodes = GATE_C[acceptance_id]
    missing = [node for node in nodes if not _defined(node)]
    assert not missing, "%s의 대응 테스트가 없다: %r" % (acceptance_id, missing)


@pytest.mark.parametrize("acceptance_id", sorted(GATE_C))
def test_every_id_names_its_own_evidence(acceptance_id):
    """비슷해 보인다는 이유로 빈 채로 두지 않는다."""
    owner, nodes = GATE_C[acceptance_id]
    assert owner and nodes


def test_no_id_is_closed_by_a_single_shared_test_alone():
    """한 테스트가 혼자서 여러 ID를 닫고 있지 않은지 본다.

    같은 테스트가 여러 ID의 **증거 중 하나**인 것은 정상이다. 그러나 어떤 ID가
    오직 공유 테스트 하나만으로 닫히면 그 ID 고유의 증거가 없는 것이다.
    """
    usage = {}
    for _, nodes in GATE_C.values():
        for node in nodes:
            usage[node] = usage.get(node, 0) + 1
    for acceptance_id, (_, nodes) in GATE_C.items():
        assert any(usage[node] == 1 for node in nodes), acceptance_id


# ── waiver 규칙 ──────────────────────────────────────────────────────────
def test_gate_c_has_no_waiver():
    assert GATE_C_WAIVED == set()
    register = WAIVERS.read_text(encoding="utf-8")
    for acceptance_id in _matrix_rows():
        assert acceptance_id not in register, acceptance_id


def test_the_hwpx_limitation_is_not_recorded_as_a_waiver():
    """한글 open 미검증은 acceptance 실패도, waiver도 아니다."""
    register = WAIVERS.read_text(encoding="utf-8")
    assert "hwpx" not in register.lower()
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "release/manual verification limitation" in tickets


# ── 판정을 문서와 대조한다 ───────────────────────────────────────────────
def test_the_verdict_is_recorded():
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "GATE C MATRIX ACCEPTANCE = PASS" in tickets
    assert "GATE C CLOSURE = COMPLETE" in tickets


def test_completion_is_not_overclaimed():
    """Gate C 통과가 구현 완료를 뜻하지 않는다."""
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "IMPLEMENTATION_COMPLETE = NO" in tickets
    for not_implied in ("Gate D", "M9", "official test"):
        assert not_implied in tickets


def test_the_known_limitations_are_recorded():
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "KNOWN-LIMITATION-C09" in tickets
    assert "Hancom open not yet verified" in tickets


def test_the_push_deviation_is_flagged_for_final_acceptance():
    """frozen matrix의 REG-010(push = NO)을 조용히 통과시키지 않는다."""
    tickets = TICKETS.read_text(encoding="utf-8")
    assert "REG-010" in tickets
