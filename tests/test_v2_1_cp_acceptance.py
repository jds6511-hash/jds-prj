"""E-03 CP 감사 — non-adoption safeguard 9건의 증거 귀속.

이 family는 성능 검증이 아니다. matrix 절 이름이 `Caption Change-Point —
non-adoption safeguard`다.

```
감사(귀속)   PROVEN 3    CP-001(P0) · CP-008(P2) · CP-009(P2)
            UNPROVEN 6  CP-002 · 003 · 004 · 005 (P0) · CP-006 · 007 (P1)
            P0 1/5 · P1 0/2 · P2 2/2 · 전부 evidence-gap

보강(E-03)   PROVEN 9    P0 5/5 · P1 2/2 · P2 2/2 · UNPROVEN 0
production 변경  없음
```

**P0/P1과 P2를 같은 칸에 세지 않는다.** P2 2건은 진단이며 acceptance를 닫기 위한
기능 요구가 아니다(matrix가 CP-009를 "기록만 · acceptance와 분리"로 둔다).

상세는 `docs/finalization/V2_1_E03_CP_AUDIT_2026-09-02.md`.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
AUDIT = ROOT / "docs/finalization/V2_1_E03_CP_AUDIT_2026-09-02.md"

#: 감사 시점에 이미 실행/기록 증거가 있던 것.
CP_PROVEN_BY_ATTRIBUTION = {
    "CP-001": [
        "test_v2_1_boundary.py::test_bpi_004_default_provider_name_is_fixed_window_v1",
        "test_v2_1_boundary.py::test_bpi_004_unspecified_provider_resolves_to_the_default",
        "test_v2_1_guards.py::test_reg_009_changing_the_default_provider_fails",
        "test_v2_1_gate_d.py::test_adopting_the_change_point_provider_fails",
    ],
    # P2 — 진단. acceptance 요구로 취급하지 않는다.
    "CP-008": [
        "test_c0_probe.py::test_인접거리는_코사인이고_첫_구간은_0이다",
        "test_c0_probe.py::test_국소최대는_cutoff없이_모양으로만_뽑는다",
        "test_c0_probe.py::test_백분위는_첫_구간을_분포에서_뺀다",
        "test_final_report_supplement.py::test_C0_분포가_좁다",
    ],
    "CP-009": [
        "test_final_report_supplement.py::test_C0는_MIXED_SIGNAL이다",
        "test_final_report_supplement.py::test_change_point는_채택되지_않았다",
        "test_v2_1_sanitation.py::test_san_001_instruction_echo_does_not_pass_as_valid",
    ],
}

#: 감사에서 UNPROVEN이었고 E-03 증거 테스트로 닫힌 것.
CP_CLOSED_BY_EVIDENCE = {
    "CP-002": [
        "test_v2_1_cp_evidence.py::test_cp_002_the_candidate_is_never_called_without_an_explicit_name",
        "test_v2_1_cp_evidence.py::test_cp_002_no_production_module_registers_a_change_point_provider",
        "test_v2_1_cp_evidence.py::test_cp_002_asking_for_it_when_absent_fails_instead_of_falling_back",
        "test_v2_1_boundary.py::test_bpi_005_unknown_provider_does_not_fall_back",
    ],
    "CP-003": [
        "test_v2_1_cp_evidence.py::test_cp_003_the_adoption_path_carries_no_tuning_parameter",
        "test_v2_1_cp_evidence.py::test_cp_003_config_threshold_keys_are_all_pre_c0_search_keys",
        "test_v2_1_cp_evidence.py::test_cp_003_the_diagnostic_side_is_allowed_to_have_shape_parameters",
        "test_c0_probe.py::test_임계나_채택_판단을_하지_않는다",
        "test_final_report_supplement.py::test_C0는_임계를_정하지_않았다",
        "test_v2_1_gate_d.py::test_a_tuning_artifact_fails",
    ],
    "CP-004": [
        "test_v2_1_cp_evidence.py::test_cp_004_no_gt_identifier_appears_in_the_cp_path",
        "test_v2_1_cp_evidence.py::test_cp_004_no_selection_is_driven_by_anything_in_the_cp_path",
        "test_v2_1_cp_evidence.py::test_cp_004_step_a_used_gt_for_measurement_with_a_frozen_criterion",
        "test_v2_1_cp_evidence.py::test_cp_004_a_passing_gate_still_did_not_adopt_the_provider",
        "test_aarv2_step_a.py::test_NMS를_쓰지_않는다",
    ],
    "CP-005": [
        "test_v2_1_cp_evidence.py::test_cp_005_the_probe_does_measure_llm_agreement",
        "test_v2_1_cp_evidence.py::test_cp_005_the_agreement_never_selects_anything",
        "test_v2_1_cp_evidence.py::test_cp_005_using_llm_boundaries_as_truth_is_recorded_as_impossible",
        "test_aarv2_step_a.py::test_생성_경로를_참조하지_않는다",
    ],
    "CP-006": [
        "test_v2_1_cp_evidence.py::test_cp_006_the_sanitation_prerequisite_is_in_its_own_section",
        "test_v2_1_cp_evidence.py::test_cp_006_the_prerequisite_names_the_concrete_defects",
    ],
    "CP-007": [
        "test_v2_1_cp_evidence.py::test_cp_007_the_vlm_dependence_is_stated_in_the_invariance_section",
        "test_v2_1_cp_evidence.py::test_cp_007_the_candidate_section_records_what_the_signal_measures",
        "test_v2_1_cp_evidence.py::test_cp_007_removing_the_statement_breaks_the_contract",
    ],
}

CP_PROVEN = {**CP_PROVEN_BY_ATTRIBUTION, **CP_CLOSED_BY_EVIDENCE}

CP_UNPROVEN = {}

#: 진단 항목. acceptance-relevant와 **따로 센다.**
CP_DIAGNOSTIC = ("CP-008", "CP-009")

REQUIRED_KEYWORD = {
    "CP-001": "default_provider_name",
    "CP-002": "explicit_name",
    "CP-003": "no_tuning_parameter",
    "CP-004": "no_selection_is_driven",
    "CP-005": "never_selects_anything",
    "CP-006": "sanitation_prerequisite",
    "CP-007": "vlm_dependence",
    "CP-008": "cutoff없이",
    "CP-009": "MIXED_SIGNAL",
}


def _matrix_cp():
    text = MATRIX.read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*(CP-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                           text, re.M))


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(re.search(r"^def %s\(" % re.escape(function),
                          path.read_text(encoding="utf-8"), re.M))


# ── 감사 범위 ────────────────────────────────────────────────────────────
def test_the_audit_covers_every_cp_item():
    rows = _matrix_cp()
    assert len(rows) == 9
    assert sum(1 for p in rows.values() if p == "P0") == 5
    assert sum(1 for p in rows.values() if p == "P1") == 2
    assert sum(1 for p in rows.values() if p == "P2") == 2
    assert set(rows) == set(CP_PROVEN) | set(CP_UNPROVEN)


def test_the_matrix_section_is_a_non_adoption_safeguard():
    """이 family의 성격을 matrix에서 확인한다 — 성능 절이 아니다."""
    text = MATRIX.read_text(encoding="utf-8")
    assert "Caption Change-Point — non-adoption safeguard" in text


def test_the_tally_separates_acceptance_from_diagnostic():
    rows = _matrix_cp()
    relevant = {i for i in CP_PROVEN if rows[i] in ("P0", "P1")}
    diagnostic = {i for i in CP_PROVEN if rows[i] == "P2"}
    assert len(relevant) == 7
    assert diagnostic == set(CP_DIAGNOSTIC)
    assert CP_UNPROVEN == {}


def test_p2_items_are_not_counted_as_acceptance_requirements():
    """P2 gap이 P0/P1 판정을 흔들지 않는다 — 계산 자체를 분리한다."""
    rows = _matrix_cp()
    for acceptance_id in CP_DIAGNOSTIC:
        assert rows[acceptance_id] == "P2"
    text = AUDIT.read_text(encoding="utf-8")
    assert "acceptance-relevant" in text
    assert re.search(r"CP diagnostic\s*\n?\s*P2 2", text) or "P2 2" in text


# ── 증거 실재 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(CP_PROVEN))
def test_every_proven_id_has_existing_evidence(acceptance_id):
    missing = [node for node in CP_PROVEN[acceptance_id] if not _defined(node)]
    assert not missing, "%s: %r" % (acceptance_id, missing)


@pytest.mark.parametrize("acceptance_id", sorted(REQUIRED_KEYWORD))
def test_each_id_keeps_the_test_that_measures_its_contract(acceptance_id):
    keyword = REQUIRED_KEYWORD[acceptance_id]
    assert any(keyword in node for node in CP_PROVEN[acceptance_id]), \
        (acceptance_id, keyword)


def test_the_keyword_map_covers_every_proven_id():
    assert set(REQUIRED_KEYWORD) == set(CP_PROVEN)


def test_no_proven_id_rests_only_on_a_shared_test():
    usage = {}
    for nodes in CP_PROVEN.values():
        for node in nodes:
            usage[node] = usage.get(node, 0) + 1
    for acceptance_id, nodes in CP_PROVEN.items():
        assert any(usage[node] == 1 for node in nodes), acceptance_id


# ── 계약을 뭉치지 않았는가 ───────────────────────────────────────────────
def test_cp_001_and_cp_002_do_not_share_their_deciding_evidence():
    """default identity와 호출 0은 별도 계약이다."""
    own_001 = {n for n in CP_PROVEN["CP-001"] if "default_provider_name" in n}
    own_002 = {n for n in CP_PROVEN["CP-002"] if "explicit_name" in n}
    assert own_001 and own_002
    assert not own_001 & own_002


@pytest.mark.parametrize("acceptance_id", ["CP-003", "CP-004", "CP-005"])
def test_each_promotion_route_has_its_own_evidence(acceptance_id):
    """tuning · GT · LLM 일치도는 서로 다른 승격 경로다. 하나로 닫지 않는다."""
    own = {n for n in CP_PROVEN[acceptance_id]
           if n.startswith("test_v2_1_cp_evidence.py::")}
    assert own, acceptance_id
    for other in ("CP-003", "CP-004", "CP-005"):
        if other == acceptance_id:
            continue
        peer = {n for n in CP_PROVEN[other]
                if n.startswith("test_v2_1_cp_evidence.py::")}
        assert not own & peer, (acceptance_id, other)


def test_cp_005_admits_that_agreement_is_measured():
    """"일치도를 재지 않는다"고 적으면 거짓이다 — 재는 사실을 증거에 포함한다."""
    assert any("does_measure_llm_agreement" in node
               for node in CP_PROVEN["CP-005"])


# ── 문서 판정 ────────────────────────────────────────────────────────────
def test_the_audit_keeps_the_original_verdict_as_history():
    text = AUDIT.read_text(encoding="utf-8")
    assert "PROVEN 3" in text and "UNPROVEN 6" in text
    for acceptance_id in CP_CLOSED_BY_EVIDENCE:
        assert re.search(r"%s[^\n]*UNPROVEN" % acceptance_id, text), acceptance_id


def test_the_audit_declares_cp_closed():
    text = AUDIT.read_text(encoding="utf-8")
    assert "CP CLOSED" in text
    assert "PROVEN 9" in text and "UNPROVEN 0" in text


def test_the_closure_does_not_claim_change_point_validity():
    """이 family를 닫은 것이 성능 검증이 아니라는 것을 문구로 못 박는다."""
    text = AUDIT.read_text(encoding="utf-8")
    assert "does not establish caption change-point validity" in text
    assert "NOT ADOPTED" in text


def test_each_closed_gap_stays_classified():
    text = AUDIT.read_text(encoding="utf-8")
    for acceptance_id in CP_CLOSED_BY_EVIDENCE:
        heading = "### %s" % acceptance_id
        assert heading in text, acceptance_id
        section = text.split(heading, 1)[1].split("### ", 1)[0]
        assert "evidence-gap" in section or "implementation-gap" in section, \
            acceptance_id


def test_the_missing_evidence_is_described_inside_its_own_section():
    text = AUDIT.read_text(encoding="utf-8")
    expected = {
        "CP-002": "호출 수",
        "CP-003": "채택 경로",
        "CP-004": "최적화 의존",
        "CP-005": "채택 기준",
        "CP-006": "절",
        "CP-007": "절",
    }
    for acceptance_id, phrase in expected.items():
        section = text.split("### %s" % acceptance_id, 1)[1].split("### ", 1)[0]
        assert phrase in section, (acceptance_id, phrase)


def test_the_three_audit_findings_are_recorded():
    """감사 중 드러난 사실을 문서가 담고 있는가."""
    text = AUDIT.read_text(encoding="utf-8")
    assert "구현 자체가 없다" in text                     # provider 미구현
    assert "on_local_peak_share" in text                  # 일치도는 실제로 계산된다
    assert "STEP A" in text and "GO" in text              # 통과했는데도 미채택
    assert "abstention_tau" in text                       # 0.55 우연 일치 정리


def test_cp_is_wired_into_the_final_tally():
    final = (ROOT / "tests/test_v2_1_final_acceptance.py").read_text(
        encoding="utf-8")
    assert "tests/test_v2_1_cp_acceptance.py" in final
