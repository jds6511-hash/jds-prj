"""E-01 ERR 감사 — 실패 의미론 10건의 증거 귀속.

새 동작을 만들지 않는다. **기존 테스트가 각 failure contract를 실제로 증명하는지**
역추적한 결과를 고정한다.

```
PROVEN     7   (P0 6 · P1 1)
UNPROVEN   3   ERR-006 · ERR-009 · ERR-010
```

이름이 비슷한 테스트를 연결해 닫지 않았다. 세 건은 **부분 증거만 있다** — 그
사실을 지우지 않고 UNPROVEN으로 남긴다. 상세는
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

#: 부분 증거만 있는 것. **닫지 않는다.**
ERR_UNPROVEN = {
    "ERR-006": [
        "test_v2_1_highlight.py::test_an_unknown_episode_is_refused",
        "test_v2_1_highlight.py::test_hlt_003_canonical_structure_is_unchanged",
    ],
    "ERR-009": [
        "test_v2_1_llm_p1_contract.py::test_an_episode_with_no_usable_evidence_is_still_refused",
    ],
    "ERR-010": [
        "test_v2_1_fixed_window.py::test_fw_002_to_005_boundaries_ignore_every_content_channel",
        "test_v2_1_sanitation.py::test_san_001_instruction_echo_does_not_pass_as_valid",
        "test_v2_1_sanitation.py::test_s6_echo_and_foreign_caption_are_flagged_differently",
    ],
}


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


def test_the_tally_is_seven_and_three():
    assert len(ERR_PROVEN) == 7
    assert len(ERR_UNPROVEN) == 3


# ── 증거가 실재하는가 ────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(ERR_PROVEN))
def test_every_proven_id_has_existing_evidence(acceptance_id):
    missing = [node for node in ERR_PROVEN[acceptance_id] if not _defined(node)]
    assert not missing, "%s: %r" % (acceptance_id, missing)


@pytest.mark.parametrize("acceptance_id", sorted(ERR_UNPROVEN))
def test_partial_evidence_also_has_to_exist(acceptance_id):
    """부분 증거라도 실재해야 한다 — 없는 테스트를 근거로 적지 않는다."""
    missing = [node for node in ERR_UNPROVEN[acceptance_id] if not _defined(node)]
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


def test_each_unproven_item_is_classified():
    """증거 공백인가 구현 공백인가 — 둘을 섞지 않는다."""
    text = AUDIT.read_text(encoding="utf-8")
    for acceptance_id in ERR_UNPROVEN:
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


def test_err_is_not_wired_into_the_final_tally_yet():
    """부분 매핑을 전체 집계에 넣어 gap을 줄이지 않는다."""
    final = (ROOT / "tests/test_v2_1_final_acceptance.py").read_text(
        encoding="utf-8")
    assert "test_v2_1_err_acceptance.py" not in final
