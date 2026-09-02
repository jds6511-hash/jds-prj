"""E-04 GEO/TRI 감사 — dataset regression 10건의 증거 귀속.

```
E-04 감사(귀속)   PROVEN 2    GEO-003(P0) · TRI-006(P0)
                 UNPROVEN 8
                 GEO P0 1/2 · P1 0/2      TRI P0 1/3 · P1 0/3
                 evidence-gap 7 · implementation-gap 1 (TRI-005)

E-04 보강        GEO 4/4 CLOSED
                 TRI 5/6 — **TRI-005 미해결**
```

`TRI-005`(sparse evidence → narrative hallucination 금지)는 증거 공백이 아니다.
**summary 안의 발명된 서사를 거부하는 기제가 없다** — 그것이 v2.1의 명시된 한계
(`semantic entailment not automatically verified`)다. 실측으로 확인했고, 감사 문서에
적었다. 새 계약을 만들지 않았으므로 여기서 닫지 않는다.

따라서 **§19 Dataset Regression은 아직 final tally에 넣지 않는다.** GEO는 4/4지만
같은 절의 TRI가 열려 있고, 부분 매핑을 집계에 넣지 않는 원칙을 유지한다.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
AUDIT = ROOT / "docs/finalization/V2_1_E04_GEO_TRI_AUDIT_2026-09-02.md"

#: 감사 시점에 이미 증거가 있던 것.
PROVEN_BY_ATTRIBUTION = {
    "GEO-003": [
        "test_v2_1_err_evidence.py::test_err_010_an_instruction_echo_peak_does_not_move_the_fixed_window",
        "test_v2_1_geo_tri_evidence.py::test_geo_003_is_measured_by_the_err_010_perturbation",
        "test_v2_1_fixed_window.py::test_fw_002_to_005_boundaries_ignore_every_content_channel",
    ],
    "TRI-006": [
        "test_v2_1_geo_tri_evidence.py::test_tri_006_the_boilerplate_is_preserved_suspect_and_never_sole_support",
        "test_v2_1_sanitation.py::test_s1_separates_boilerplate_from_real_speech",
        "test_v2_1_sanitation.py::test_s1_usable_support_excludes_suspect",
        "test_v2_1_grounding.py::test_grd_011_suspect_only_support_is_ineligible",
        "test_v2_1_grounding.py::test_grd_012_suspect_beside_valid_does_not_auto_pass",
    ],
}

#: 감사에서 UNPROVEN(evidence-gap)이었고 E-04 증거 테스트로 닫힌 것.
CLOSED_BY_EVIDENCE = {
    "GEO-001": [
        "test_v2_1_geo_tri_evidence.py::test_geo_001_rich_stt_actually_becomes_the_dialogue_evidence",
        "test_v2_1_geo_tri_evidence.py::test_geo_001_a_dialogue_without_any_cite_does_not_pass",
        "test_v2_1_llm_p1_contract.py::test_llm_010_eligible_speech_reaches_the_evidence_block",
    ],
    "GEO-002": [
        "test_v2_1_geo_tri_evidence.py::test_geo_002_the_echo_is_distinguished_from_normal_captions",
        "test_v2_1_geo_tri_evidence.py::test_geo_002_the_echo_is_preserved_not_deleted",
        "test_v2_1_sanitation.py::test_san_001_ordinary_caption_is_valid",
    ],
    "GEO-004": [
        "test_v2_1_geo_tri_evidence.py::test_geo_004_a_dialogue_heavy_episode_is_processed",
        "test_v2_1_geo_tri_evidence.py::test_geo_004_source_is_derived_as_speech_for_a_dialogue_heavy_episode",
    ],
    "TRI-001": [
        "test_v2_1_geo_tri_evidence.py::test_tri_001_an_episode_without_stt_still_succeeds_structurally",
        "test_v2_1_llm_p1_contract.py::test_llm_006_caption_only_episode_still_has_claim_evidence",
    ],
    "TRI-002": [
        "test_v2_1_geo_tri_evidence.py::test_tri_002_contaminated_stt_cannot_support_a_dialogue",
        "test_v2_1_geo_tri_evidence.py::test_tri_002_a_repeated_stt_line_is_also_ineligible",
        "test_v2_1_sanitation.py::test_subtitle_credit_is_rejected",
    ],
    "TRI-003": [
        "test_v2_1_geo_tri_evidence.py::test_tri_003_the_foreign_caption_state_reaches_the_timeline",
        "test_v2_1_sanitation.py::test_s6_echo_and_foreign_caption_are_flagged_differently",
    ],
    "TRI-004": [
        "test_v2_1_geo_tri_evidence.py::test_tri_004_the_black_screen_transition_is_observable_in_the_diagnostic",
        "test_v2_1_geo_tri_evidence.py::test_tri_004_the_observation_is_not_wired_into_adoption",
    ],
}

PROVEN = {**PROVEN_BY_ATTRIBUTION, **CLOSED_BY_EVIDENCE}

#: 닫지 않은 것. **구현 공백이므로 증거를 늘려 닫을 수 없다.**
UNPROVEN = {
    "TRI-005": "implementation-gap",
}

REQUIRED_KEYWORD = {
    "GEO-001": "rich_stt_actually_becomes",
    "GEO-002": "distinguished_from_normal",
    "GEO-003": "does_not_move_the_fixed_window",
    "GEO-004": "dialogue_heavy_episode_is_processed",
    "TRI-001": "without_stt_still_succeeds_structurally",
    "TRI-002": "contaminated_stt_cannot_support",
    "TRI-003": "foreign_caption_state_reaches_the_timeline",
    "TRI-004": "black_screen_transition_is_observable",
    "TRI-006": "preserved_suspect_and_never_sole_support",
}


def _matrix_rows():
    text = MATRIX.read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*((?:GEO|TRI)-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                           text, re.M))


def _defined(node: str) -> bool:
    filename, function = node.split("::")
    path = ROOT / "tests" / filename
    if not path.is_file():
        return False
    return bool(re.search(r"^def %s\(" % re.escape(function),
                          path.read_text(encoding="utf-8"), re.M))


# ── 감사 범위 ────────────────────────────────────────────────────────────
def test_the_audit_covers_every_item():
    rows = _matrix_rows()
    assert len(rows) == 10
    assert sum(1 for i in rows if i.startswith("GEO-")) == 4
    assert sum(1 for i in rows if i.startswith("TRI-")) == 6
    assert sum(1 for p in rows.values() if p == "P0") == 5
    assert set(rows) == set(PROVEN) | set(UNPROVEN)


def test_the_p0_split_matches_the_matrix():
    rows = _matrix_rows()
    p0 = {i for i, p in rows.items() if p == "P0"}
    assert p0 == {"GEO-002", "GEO-003", "TRI-002", "TRI-005", "TRI-006"}


def test_geo_is_closed_and_tri_is_not():
    rows = _matrix_rows()
    geo = {i for i in rows if i.startswith("GEO-")}
    tri = {i for i in rows if i.startswith("TRI-")}
    assert geo <= set(PROVEN)
    assert tri & set(UNPROVEN) == {"TRI-005"}
    assert len(tri & set(PROVEN)) == 5


# ── 증거 실재 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("acceptance_id", sorted(PROVEN))
def test_every_proven_id_has_existing_evidence(acceptance_id):
    missing = [node for node in PROVEN[acceptance_id] if not _defined(node)]
    assert not missing, "%s: %r" % (acceptance_id, missing)


@pytest.mark.parametrize("acceptance_id", sorted(REQUIRED_KEYWORD))
def test_each_id_keeps_the_test_that_measures_its_contract(acceptance_id):
    keyword = REQUIRED_KEYWORD[acceptance_id]
    assert any(keyword in node for node in PROVEN[acceptance_id]), \
        (acceptance_id, keyword)


def test_the_keyword_map_covers_every_proven_id():
    assert set(REQUIRED_KEYWORD) == set(PROVEN)


def test_no_proven_id_rests_only_on_a_shared_test():
    usage = {}
    for nodes in PROVEN.values():
        for node in nodes:
            usage[node] = usage.get(node, 0) + 1
    for acceptance_id, nodes in PROVEN.items():
        assert any(usage[node] == 1 for node in nodes), acceptance_id


# ── 계약을 뭉치지 않았는가 ───────────────────────────────────────────────
def test_tri_005_is_not_closed_by_the_err_009_test():
    """`all evidence absent`와 `sparse evidence`는 다른 계약이다."""
    assert "TRI-005" in UNPROVEN
    for nodes in PROVEN.values():
        assert not any("err_009" in node for node in nodes)


def test_tri_001_is_not_closed_by_the_err_009_test():
    """TRI-001은 'STT만 사실상 없음'이고 ERR-009는 '전 채널 공백'이다."""
    assert not any("err_009" in node for node in PROVEN["TRI-001"])
    assert any("without_stt" in node for node in PROVEN["TRI-001"])


def test_geo_003_points_at_a_concrete_test_not_at_err_010_status():
    """상태 참조가 아니라 구체 테스트를 가리킨다."""
    assert any(node.startswith("test_v2_1_err_evidence.py::test_err_010_")
               for node in PROVEN["GEO-003"])


def test_geo_002_has_both_arms():
    """echo 단독 REJECTED는 계약의 절반이다 — 정상 caption arm이 함께 있어야 한다."""
    assert any("ordinary_caption_is_valid" in node
               for node in PROVEN["GEO-002"])
    assert any("distinguished_from_normal" in node
               for node in PROVEN["GEO-002"])


# ── TRI-005를 조용히 닫지 않는다 ─────────────────────────────────────────
def test_tri_005_is_classified_as_an_implementation_gap():
    assert UNPROVEN["TRI-005"] == "implementation-gap"
    text = AUDIT.read_text(encoding="utf-8")
    section = text.split("### TRI-005", 1)[1].split("### ", 1)[0]
    assert "implementation-gap" in section
    assert "evidence-gap이 아니다" in section


def test_the_audit_records_the_measured_proof_that_it_is_unenforced():
    """추론이 아니라 실측으로 확인했다는 것이 문서에 남아 있어야 한다."""
    section = AUDIT.read_text(encoding="utf-8").split(
        "### TRI-005", 1)[1].split("### ", 1)[0]
    assert "PASS" in section
    assert "semantic entailment not automatically verified" in section
    for enforced in ("FAIL_UNSUPPORTED", "FAIL_NO_SUPPORT",
                     "FAIL_INELIGIBLE_SUPPORT"):
        assert enforced in section, enforced


def test_the_audit_keeps_the_original_verdict_as_history():
    text = AUDIT.read_text(encoding="utf-8")
    assert "PROVEN 2" in text and "UNPROVEN 8" in text
    for acceptance_id in CLOSED_BY_EVIDENCE:
        assert re.search(r"%s[^\n]*UNPROVEN" % acceptance_id, text), acceptance_id


def test_the_audit_declares_geo_closed_and_tri_open():
    text = AUDIT.read_text(encoding="utf-8")
    assert "GEO CLOSED" in text
    assert "TRI = NOT CLOSED" in text
    assert "does not establish semantic event-detection accuracy" in text


def test_each_closed_gap_stays_classified():
    text = AUDIT.read_text(encoding="utf-8")
    for acceptance_id in CLOSED_BY_EVIDENCE:
        heading = "### %s" % acceptance_id
        assert heading in text, acceptance_id
        section = text.split(heading, 1)[1].split("### ", 1)[0]
        assert "evidence-gap" in section, acceptance_id


def test_the_missing_evidence_is_described_inside_its_own_section():
    text = AUDIT.read_text(encoding="utf-8")
    expected = {
        "GEO-001": "근거가 됐다",
        "GEO-002": "비교 arm",
        "GEO-004": "dialogue-heavy",
        "TRI-001": "구조",
        "TRI-002": "오염",
        "TRI-003": "timeline",
        "TRI-004": "진단",
    }
    for acceptance_id, phrase in expected.items():
        section = text.split("### %s" % acceptance_id, 1)[1].split("### ", 1)[0]
        assert phrase in section, (acceptance_id, phrase)


def test_the_fixture_provenance_is_recorded():
    """합성 fixture 문자열이 그 두 영상의 실측값이라는 근거."""
    text = AUDIT.read_text(encoding="utf-8")
    for token in ("INSTRUCTION_ECHO", "FOREIGN_CAPTION", "BOILERPLATE",
                  "EXCITED_SPEECH"):
        assert token in text, token
    assert "V2_1_IMPLEMENTATION_PLAN" in text


def test_section_19_is_not_wired_into_the_final_tally_yet():
    """GEO가 4/4여도 같은 절의 TRI가 열려 있으므로 집계에 넣지 않는다."""
    final = (ROOT / "tests/test_v2_1_final_acceptance.py").read_text(
        encoding="utf-8")
    assert "tests/test_v2_1_geo_tri_acceptance.py" not in final
