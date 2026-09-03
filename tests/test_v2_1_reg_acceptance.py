"""E-05 REG 감사 — Non-regression / Repository Gate 4건의 증거 귀속.

```
REG CLOSED   PROVEN 4 (P0 3 · P1 1) · UNPROVEN 0
```

`REG-005 ~ 010`은 이미 다른 지도에 있다(Gate A · Gate D · REG-010 addendum). 이
파일은 남아 있던 `REG-001 ~ 004`만 다룬다.

상세는 `docs/finalization/V2_1_E05_REG_AUDIT_2026-09-02.md`.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
AUDIT = ROOT / "docs/finalization/V2_1_E05_REG_AUDIT_2026-09-02.md"

REG_PROVEN = {
    "REG-001": [
        "test_v2_1_reg_evidence.py::test_reg_001_v2_1_did_not_touch_any_pre_existing_production_module",
        "test_v2_1_reg_evidence.py::test_reg_001_only_one_pre_existing_test_file_changed_and_it_was_strengthened",
        "test_v2_1_reg_evidence.py::test_reg_001_the_frozen_modules_are_still_frozen",
        "test_v2_1_reg_evidence.py::test_reg_001_the_search_pipeline_is_untouched",
    ],
    "REG-002": [
        "test_v2_1_reg_evidence.py::test_reg_002_every_mapped_node_exists",
        "test_v2_1_reg_evidence.py::test_reg_002_no_p0_is_closed_by_a_skip_or_an_xfail",
        "test_v2_1_reg_evidence.py::test_reg_002_the_former_marker_file_carries_no_marker_any_more",
        "test_v2_1_reg_evidence.py::test_reg_002_no_p0_is_left_unmapped",
        "test_v2_1_reg_evidence.py::test_reg_002_the_wired_map_list_matches_the_tally",
    ],
    "REG-003": [
        "test_v2_1_reg_evidence.py::test_reg_003_the_only_waived_item_is_grd_004",
        "test_v2_1_reg_evidence.py::test_reg_003_the_register_refuses_skip_as_a_waiver",
        "test_v2_1_reg_evidence.py::test_reg_003_the_waiver_records_every_required_field",
        "test_v2_1_reg_evidence.py::test_reg_003_the_waived_id_is_p1_in_the_matrix",
        "test_v2_1_gate_b_acceptance.py::test_waived_ids_have_no_test_and_a_registered_waiver",
    ],
    "REG-004": [
        "test_v2_1_reg_evidence.py::test_reg_004_no_tracked_file_is_modified",
        "test_v2_1_reg_evidence.py::test_reg_004_the_full_porcelain_is_recorded_in_the_audit",
        "test_v2_1_reg_evidence.py::test_reg_004_head_matches_the_remote",
    ],
}

REG_UNPROVEN = {}

REQUIRED_KEYWORD = {
    "REG-001": "did_not_touch_any_pre_existing",
    "REG-002": "no_p0_is_closed_by_a_skip",
    "REG-003": "the_only_waived_item_is_grd_004",
    "REG-004": "no_tracked_file_is_modified",
}


def _matrix_reg():
    text = MATRIX.read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*(REG-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                           text, re.M))


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(re.search(r"^def %s\(" % re.escape(function),
                          path.read_text(encoding="utf-8"), re.M))


# ── 범위 ─────────────────────────────────────────────────────────────────
def test_this_map_covers_only_reg_001_to_004():
    """005~010은 다른 지도의 소관이다 — 중복 귀속하지 않는다."""
    assert set(REG_PROVEN) == {"REG-001", "REG-002", "REG-003", "REG-004"}
    rows = _matrix_reg()
    assert len(rows) == 10


def test_the_priority_split_matches_the_matrix():
    rows = _matrix_reg()
    assert [rows[i] for i in ("REG-001", "REG-002", "REG-003", "REG-004")] == \
        ["P0", "P0", "P1", "P0"]


def test_the_tally_is_four_and_zero():
    assert len(REG_PROVEN) == 4
    assert REG_UNPROVEN == {}


# ── 증거 실재 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(REG_PROVEN))
def test_every_proven_id_has_existing_evidence(acceptance_id):
    missing = [node for node in REG_PROVEN[acceptance_id] if not _defined(node)]
    assert not missing, "%s: %r" % (acceptance_id, missing)


@pytest.mark.parametrize("acceptance_id", sorted(REQUIRED_KEYWORD))
def test_each_id_keeps_the_test_that_measures_its_contract(acceptance_id):
    keyword = REQUIRED_KEYWORD[acceptance_id]
    assert any(keyword in node for node in REG_PROVEN[acceptance_id]), \
        (acceptance_id, keyword)


def test_the_keyword_map_covers_every_proven_id():
    assert set(REQUIRED_KEYWORD) == set(REG_PROVEN)


def test_no_proven_id_rests_only_on_a_shared_test():
    usage = {}
    for nodes in REG_PROVEN.values():
        for node in nodes:
            usage[node] = usage.get(node, 0) + 1
    for acceptance_id, nodes in REG_PROVEN.items():
        assert any(usage[node] == 1 for node in nodes), acceptance_id


# ── 계약을 뭉치지 않았는가 ───────────────────────────────────────────────
def test_reg_001_is_not_closed_by_a_green_suite_claim():
    """"전부 green"은 REG-001의 증거가 아니다 — git diff 증거가 있어야 한다."""
    assert any("did_not_touch" in node for node in REG_PROVEN["REG-001"])
    assert any("frozen_modules" in node for node in REG_PROVEN["REG-001"])


def test_reg_002_and_reg_003_do_not_share_their_deciding_evidence():
    own_002 = {n for n in REG_PROVEN["REG-002"] if "skip_or_an_xfail" in n}
    own_003 = {n for n in REG_PROVEN["REG-003"] if "waived_item" in n}
    assert own_002 and own_003 and not own_002 & own_003


def test_reg_004_records_untracked_separately_from_tracked():
    text = AUDIT.read_text(encoding="utf-8")
    assert "tracked modified" in text and "untracked" in text
    assert "미추적을 숨기지 않는다" in text


# ── 문서 판정 ────────────────────────────────────────────────────────────
def test_the_audit_declares_reg_closed():
    text = AUDIT.read_text(encoding="utf-8")
    assert "REG CLOSED" in text
    assert "PROVEN 4" in text and "UNPROVEN 0" in text


def test_the_audit_records_the_silent_skip_finding():
    """감사 중 찾은 조용한 self-skip과 그 조치가 기록돼 있어야 한다."""
    text = AUDIT.read_text(encoding="utf-8")
    assert "조용한 self-skip" in text
    assert "GLS-007" in text
    assert "pytest.skip" in text
    source = (ROOT / "tests/test_v2_1_synthesis.py").read_text(encoding="utf-8")
    assert "pytest.skip" not in source


def test_the_closure_does_not_claim_implementation_complete():
    text = AUDIT.read_text(encoding="utf-8")
    assert "IMPLEMENTATION_COMPLETE" in text
    assert "This does not establish IMPLEMENTATION_COMPLETE" in text
    assert "TRI-005 remains an open P0" in text


def test_reg_is_wired_into_the_final_tally():
    final = (ROOT / "tests/test_v2_1_final_acceptance.py").read_text(
        encoding="utf-8")
    assert "tests/test_v2_1_reg_acceptance.py" in final
