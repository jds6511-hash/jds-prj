"""E-01 · E-01a ERR 감사 — 실패 의미론 10건의 증거 귀속.

새 동작을 만들지 않는다. **기존 테스트가 각 failure contract를 실제로 증명하는지**
역추적한 결과를 고정한다.

```
E-01    PROVEN 7 · UNPROVEN 3 (ERR-006 · 009 · 010)   ERR = NOT CLOSED
E-01a   그 세 건을 그 결함 입력으로 재는 테스트 추가     ERR = CLOSED
        PROVEN 10 (P0 8 · P1 2) · UNPROVEN 0
```

E-01a도 production 동작을 바꾸지 않았다 — `evidence-gap`이었으므로 검사만 늘렸다.
원 판정을 지우지 않는다. 상세는
`docs/finalization/V2_1_E01_ERR_AUDIT_2026-09-02.md`.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
AUDIT = ROOT / "docs/finalization/V2_1_E01_ERR_AUDIT_2026-09-02.md"

#: 증거가 확인된 것. 각 ID는 자기 계약을 실제로 검사하는 테스트를 갖는다.
ERR_PROVEN = {
    "ERR-001": [
        "test_v2_1_partition.py::test_can_010_overlap_injection_fails",
        "test_v2_1_partition.py::test_assert_valid_partition_raises_on_failure",
        "test_v2_1_partition.py::test_every_failure_names_the_offending_segment",
    ],
    "ERR-002": [
        "test_v2_1_partition.py::test_can_011_gap_injection_fails",
        "test_v2_1_partition.py::test_can_013_unassigned_injection_fails",
    ],
    "ERR-003": [
        "test_v2_1_parse.py::test_registry_never_clamps_or_snaps",
        "test_v2_1_binding.py::test_nonexistent_segment_is_recorded_as_unknown",
        "test_v2_1_grounding.py::test_grd_002_nonexistent_ref_is_a_reference_failure",
    ],
    "ERR-004": [
        "test_v2_1_raw_store.py::test_raw_002_raw_survives_parse_failure",
        "test_v2_1_raw_store.py::test_raw_bytes_are_unchanged_by_a_failed_parse",
        "test_v2_1_parse.py::test_sch_004_no_structure_fallback",
    ],
    "ERR-005": [
        "test_v2_1_content.py::test_llm_009_model_failure_keeps_the_episode_structure",
        "test_v2_1_content.py::test_llm_009_parse_failure_keeps_the_episode_structure",
        "test_v2_1_content.py::test_failure_reason_is_kept",
    ],
    "ERR-007": [
        "test_v2_1_render_fallback.py::test_rpt_006_a_failed_hwpx_falls_back_to_markdown",
        "test_v2_1_render_fallback.py::test_rpt_006_the_fallback_carries_the_same_semantics",
        "test_v2_1_render_fallback.py::test_rpt_006_the_fallback_does_not_touch_the_artifacts",
    ],
    "ERR-008": [
        "test_v2_1_boundary.py::test_bpi_005_provider_failure_is_not_replaced",
        "test_v2_1_boundary.py::test_bpi_005_unknown_provider_does_not_fall_back",
        "test_v2_1_boundary.py::test_bpi_005_source_has_no_fallback_path",
    ],
}

#: E-01a에서 닫힌 셋. 부분 증거는 **지우지 않고** 새 증거를 앞에 둔다 — 무엇이
#: 부족했고 무엇으로 닫혔는지가 같은 자리에 남아야 한다.
ERR_CLOSED_BY_E01A = {
    "ERR-006": [
        "test_v2_1_err_evidence.py::test_err_006_a_builder_failure_leaves_the_canonical_untouched",
        "test_v2_1_highlight.py::test_an_unknown_episode_is_refused",
        "test_v2_1_highlight.py::test_hlt_003_canonical_structure_is_unchanged",
    ],
    "ERR-009": [
        "test_v2_1_err_evidence.py::test_err_009_all_evidence_absent_keeps_structure_and_invents_nothing",
        "test_v2_1_llm_p1_contract.py::test_an_episode_with_no_usable_evidence_is_still_refused",
    ],
    "ERR-010": [
        "test_v2_1_err_evidence.py::test_err_010_an_instruction_echo_peak_does_not_move_the_fixed_window",
        "test_v2_1_fixed_window.py::test_fw_002_to_005_boundaries_ignore_every_content_channel",
        "test_v2_1_sanitation.py::test_san_001_instruction_echo_does_not_pass_as_valid",
        "test_v2_1_sanitation.py::test_s6_echo_and_foreign_caption_are_flagged_differently",
    ],
}

ERR_PROVEN.update(ERR_CLOSED_BY_E01A)

#: 아직 증거가 없는 것. E-01a로 비었다 — **dict을 지우지 않는다.** 다시 열리면
#: 여기로 돌아오고, 아래 테스트가 그 상태를 그대로 검사한다.
ERR_UNPROVEN = {}


#: 각 ID의 계약 핵심어. 증거 목록에 이 단어를 담은 테스트가 반드시 있어야 한다.
#: "테스트가 셋 있다"가 아니라 "그 계약을 재는 테스트가 있다"를 본다.
REQUIRED_KEYWORD = {
    "ERR-001": "overlap",
    "ERR-002": "gap",
    "ERR-003": "clamp",
    "ERR-004": "raw",
    "ERR-005": "structure",
    "ERR-007": "hwpx",
    "ERR-008": "provider",
    # E-01a — 계약을 재는 테스트가 그 실패 경로에 있어야 한다.
    "ERR-006": "canonical_untouched",
    "ERR-009": "absent",
    "ERR-010": "echo",
}


def _matrix_err():
    text = MATRIX.read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*(ERR-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                           text, re.M))


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(re.search(r"^def %s\(" % re.escape(function),
                          path.read_text(encoding="utf-8"), re.M))


# ── 감사 범위가 matrix와 맞는가 ──────────────────────────────────────────
def test_the_audit_covers_every_err_item():
    rows = _matrix_err()
    assert len(rows) == 10
    assert sum(1 for p in rows.values() if p == "P0") == 8
    assert set(rows) == set(ERR_PROVEN) | set(ERR_UNPROVEN)


def test_proven_and_unproven_do_not_overlap():
    assert not set(ERR_PROVEN) & set(ERR_UNPROVEN)


def test_the_tally_is_ten_and_zero():
    """E-01a 이후. 여기가 10/0이 아니면 최종 집계에 넣을 수 없다."""
    assert len(ERR_PROVEN) == 10
    assert ERR_UNPROVEN == {}
    rows = _matrix_err()
    assert sum(1 for i in ERR_PROVEN if rows[i] == "P0") == 8
    assert sum(1 for i in ERR_PROVEN if rows[i] == "P1") == 2


def test_the_three_gaps_were_closed_by_new_evidence():
    """기존 테스트 이름을 바꿔 단 것이 아니라 새 증거로 닫혔다."""
    for acceptance_id, nodes in ERR_CLOSED_BY_E01A.items():
        added = [n for n in nodes if n.startswith("test_v2_1_err_evidence.py::")]
        assert len(added) == 1, acceptance_id
        assert _defined(added[0]), added


# ── 증거가 실재하는가 ────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(ERR_PROVEN))
def test_every_proven_id_has_existing_evidence(acceptance_id):
    missing = [node for node in ERR_PROVEN[acceptance_id] if not _defined(node)]
    assert not missing, "%s: %r" % (acceptance_id, missing)


def test_any_remaining_partial_evidence_still_has_to_exist():
    """UNPROVEN이 다시 생기면 그 부분 증거도 실재해야 한다."""
    for acceptance_id, nodes in ERR_UNPROVEN.items():
        missing = [node for node in nodes if not _defined(node)]
        assert not missing, "%s: %r" % (acceptance_id, missing)


@pytest.mark.parametrize("acceptance_id", sorted(REQUIRED_KEYWORD))
def test_each_proven_id_keeps_the_test_that_measures_its_contract(acceptance_id):
    """개수가 아니라 계약을 본다 — overlap 주입 테스트를 빼면 ERR-001은 닫히지 않는다."""
    keyword = REQUIRED_KEYWORD[acceptance_id]
    nodes = ERR_PROVEN[acceptance_id]
    assert any(keyword in node for node in nodes), (acceptance_id, keyword)


def test_the_keyword_map_covers_every_proven_id():
    assert set(REQUIRED_KEYWORD) == set(ERR_PROVEN)


def test_no_proven_id_rests_only_on_a_shared_test():
    usage = {}
    for nodes in ERR_PROVEN.values():
        for node in nodes:
            usage[node] = usage.get(node, 0) + 1
    for acceptance_id, nodes in ERR_PROVEN.items():
        assert any(usage[node] == 1 for node in nodes), acceptance_id


# ── UNPROVEN을 조용히 닫지 않는다 ────────────────────────────────────────
def test_the_unproven_items_are_recorded_in_the_audit():
    text = AUDIT.read_text(encoding="utf-8")
    for acceptance_id in ERR_UNPROVEN:
        assert re.search(r"%s[^\n]*UNPROVEN" % acceptance_id, text), acceptance_id


def test_the_audit_declares_err_not_closed():
    text = AUDIT.read_text(encoding="utf-8")
    assert "ERR = NOT CLOSED" in text
    assert "PROVEN 7" in text and "UNPROVEN 3" in text


def test_each_closed_gap_stays_classified():
    """증거 공백인가 구현 공백인가 — 닫힌 뒤에도 그 구분을 지우지 않는다."""
    text = AUDIT.read_text(encoding="utf-8")
    for acceptance_id in ERR_CLOSED_BY_E01A:
        # 절 제목으로 자른다 — 머리말의 첫 등장으로 자르면 엉뚱한 절을 본다.
        heading = "### %s" % acceptance_id
        assert heading in text, acceptance_id
        section = text.split(heading, 1)[1].split("### ", 1)[0]
        assert "evidence-gap" in section or "implementation-gap" in section, \
            acceptance_id


def test_the_missing_evidence_is_described_inside_its_own_section():
    """문서 어딘가가 아니라 **그 ID의 절 안에** 무엇이 없는지 적혀 있어야 한다."""
    text = AUDIT.read_text(encoding="utf-8")
    expected = {
        "ERR-006": "실패 후 canonical 불변",
        "ERR-009": "S5 전 구간",
        "ERR-010": "S6",
    }
    for acceptance_id, phrase in expected.items():
        section = text.split("### %s" % acceptance_id, 1)[1].split("### ", 1)[0]
        assert phrase in section, (acceptance_id, phrase)


def test_err_is_wired_into_the_final_tally():
    """10/0이 됐으므로 이제 집계에 들어간다 — 부분 매핑으로는 넣지 않았다."""
    final = (ROOT / "tests/test_v2_1_final_acceptance.py").read_text(
        encoding="utf-8")
    assert "tests/test_v2_1_err_acceptance.py" in final
