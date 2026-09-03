"""TRI-005 counterexample — 회귀 fixture (CLOSED · 2026-09-03).

```
DECISION = C   기준을 좁히지도(A) waiver로 넘기지도(B) 않았다
remediation    C3 — sparse 구간에서 모델 요약의 정본 권한을 0으로 만든다
```

두 counterexample은 **어떤 해결책을 택하더라도 RED → GREEN을 만들어야 하는** 회귀
fixture였다. 실패 양상이 다르므로 하나로 합치지 않는다.

```
UNSUPPORTED_CONTINUATION  근거에 없는 후속 사건·행위·결과
UNSUPPORTED_NUMBER        근거에 없는 수량
```

두 테스트는 `xfail(strict=True)`였고, C3가 들어오면서 XPASS로 실패했다. 그 시점에
marker를 제거하고 **평범한 회귀 테스트로 승격**했다 — XPASS를 남긴 채 닫지 않는다.

계약 자체를 재는 것은 `test_v2_1_sparse_summary.py`다. 이 파일은 **사건**을 잠근다.

상세: `docs/finalization/V2_1_TRI_005_REMEDIATION_PREREG_2026-09-02.md`
"""
from pathlib import Path

from v2_1_gate_b import run_pipeline
from v2_1_grounding import (
    FAIL_INELIGIBLE_SUPPORT,
    FAIL_NO_SUPPORT,
    FAIL_UNSUPPORTED,
    PASS,
)
from v2_1_sparse_summary import SPARSE_EVIDENCE_DETERMINISTIC

ROOT = Path(__file__).resolve().parents[1]
TICKET = ROOT / "docs/finalization/V2_1_TRI_005_REMEDIATION_TICKET_2026-09-02.md"
PREREG = ROOT / "docs/finalization/V2_1_TRI_005_REMEDIATION_PREREG_2026-09-02.md"

TWO = ((0, 5), (6, 11))

#: sparse admissible evidence — 유효 발화 **한 건**. 0건이 아니다(ERR-009와 다른 계약).
SPARSE_ASR = {**{i: "" for i in range(12)}, 9: "남성이 문을 연다."}

#: 근거가 지지하는 범위 그대로. 통과해야 한다.
SUPPORTED = "남성이 문을 연다."

#: 근거에 없는 후속 사건을 이어 붙였다.
UNSUPPORTED_CONTINUATION = "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."

#: 근거에 없는 수량을 넣었다.
UNSUPPORTED_NUMBER = "남성이 문 3개를 연다."


#: 근거가 붙은 dialogue. 이것이 있어야 episode가 **accepted(PASS)** 상태가 되고,
#: "accepted summary가 근거를 넘어선다"를 잴 수 있다. dialogue가 없으면 grounding은
#: NOT_APPLICABLE이라 계약이 성립하지 않는다.
ACCEPTED_DIALOGUE = "문을 연다고 말한다."


def _episode(tmp_path, summary, *, dialogue=ACCEPTED_DIALOGUE, cites=(9,)):
    payload = {"summary": summary}
    if dialogue is not None:
        payload["dialogue_note"] = dialogue
        if cites:
            payload["stt_cites"] = list(cites)
    pipeline = run_pipeline(tmp_path, ({"summary": "앞 구간."}, payload),
                            name="S4", spans=TWO, asr_overrides=SPARSE_ASR)
    return pipeline, pipeline.document["episodes"][1]


# ── sparse는 absent가 아니다 ─────────────────────────────────────────────
def test_the_fixture_is_sparse_not_absent(tmp_path):
    """근거가 0건이면 ERR-009이고 다른 계약이다 — 여기서는 1건 있어야 한다."""
    from v2_1_sanitation import classify_channel, eligible_support

    usable = eligible_support(classify_channel(SPARSE_ASR, "asr").values())
    assert len(usable) == 1
    assert usable[0].text == SUPPORTED


def test_a_summary_within_the_evidence_passes(tmp_path):
    """근거 범위 안의 요약은 통과해야 한다 — 과잉 격리로 닫는 것을 막는다."""
    _, episode = _episode(tmp_path, SUPPORTED)
    assert episode["grounding_status"] == PASS
    assert episode["summary"] == SUPPORTED
    assert episode["dialogue_note"] == ACCEPTED_DIALOGUE
    assert episode["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC


# ── 지금 이미 막히는 것 (remediation 이후에도 참이어야 한다) ─────────────
def test_the_dialogue_side_is_already_evidence_qualified(tmp_path):
    """dialogue claim은 이미 근거 자격으로 게이트된다."""
    _, no_cite = _episode(tmp_path / "a", SUPPORTED, cites=())
    assert no_cite["grounding_status"] == FAIL_NO_SUPPORT

    _, bad_number = _episode(tmp_path / "b", SUPPORTED,
                             dialogue="문 5개를 연다고 말한다.")
    assert bad_number["grounding_status"] == FAIL_UNSUPPORTED
    assert bad_number["dialogue_note"] is None


def test_contaminated_support_is_already_rejected(tmp_path):
    """오염 근거만으로는 dialogue가 서지 않는다(TRI-002)."""
    contaminated = {**SPARSE_ASR, 9: "한글자막 by 홍길동"}
    pipeline = run_pipeline(
        tmp_path, ({"summary": "앞."},
                   {"summary": SUPPORTED, "dialogue_note": "메모",
                    "stt_cites": [9]}),
        name="S4", spans=TWO, asr_overrides=contaminated)
    assert pipeline.grounding[1].status == FAIL_INELIGIBLE_SUPPORT


# ── remediation으로 닫힌 것 (C3 · 2026-09-03) ────────────────────────────
def test_tri_005_an_unsupported_continuation_must_not_be_accepted(tmp_path):
    """근거에 없는 후속 사건을 단 요약이 accepted 상태로 남아서는 안 된다."""
    _, episode = _episode(tmp_path, UNSUPPORTED_CONTINUATION)
    accepted = (episode["grounding_status"] == PASS
                and episode["summary"] == UNSUPPORTED_CONTINUATION)
    assert not accepted
    # "지어낸 문장이 그대로가 아니다"로는 부족하다 — 발명된 사건 자체가 없어야 한다.
    for invented in ("건물", "훔친", "달아난다"):
        assert invented not in episode["summary"], invented
    assert episode["summary"] == SUPPORTED
    assert episode["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC


def test_tri_005_an_unsupported_quantity_must_not_be_accepted(tmp_path):
    """근거에 없는 수량을 넣은 요약이 accepted 상태로 남아서는 안 된다."""
    _, episode = _episode(tmp_path, UNSUPPORTED_NUMBER)
    accepted = (episode["grounding_status"] == PASS
                and episode["summary"] == UNSUPPORTED_NUMBER)
    assert not accepted
    assert "3개" not in episode["summary"]
    assert episode["summary"] == SUPPORTED
    assert episode["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC


def test_the_raw_model_output_is_still_preserved(tmp_path):
    """정본 권한만 뺏는다 — 모델이 무엇을 냈는지는 raw store에 그대로 남는다."""
    pipeline, _ = _episode(tmp_path, UNSUPPORTED_CONTINUATION)
    raw = pipeline.store.load("llm", 1).read_text()
    assert UNSUPPORTED_CONTINUATION in raw


def test_the_two_failure_modes_are_kept_separate():
    """숫자와 서사는 실패 양상이 다르다 — 하나로 합치지 않는다."""
    assert UNSUPPORTED_CONTINUATION != UNSUPPORTED_NUMBER
    # 서사는 사건을 덧붙이고, 숫자는 수량을 바꾼다.
    assert "훔친" in UNSUPPORTED_CONTINUATION and "3개" in UNSUPPORTED_NUMBER


# ── 티켓과 fixture가 어긋나지 않는다 ─────────────────────────────────────
def test_the_ticket_records_decision_c_and_rejects_a_and_b():
    text = TICKET.read_text(encoding="utf-8")
    assert "DECISION = C" in text
    assert "A  REJECTED" in text and "B  REJECTED" in text
    assert "status = OPEN" in text
    assert "severity = P0" in text


def test_the_preregistration_fixes_the_design_before_implementation():
    """사전등록이 C3 primary · C1 미적용 · C2 제외와 sparse 정의를 고정한다."""
    text = PREREG.read_text(encoding="utf-8")
    assert "PRIMARY       C3" in text
    assert "EXCLUDED      C2" in text
    assert "SPARSE_V1(episode) :=" in text
    assert 'e.usable_for_claims]) == 1' in text
    assert "구현 승인은 아직 없다" in text


def test_the_preregistration_does_not_claim_general_entailment():
    """closure 문구가 일반 semantic entailment 해결을 주장하지 않는다."""
    text = PREREG.read_text(encoding="utf-8")
    assert "This does not establish general semantic entailment verification" in text
    assert "does not revoke the GRD-004 waiver" in text


def test_the_ticket_quotes_both_counterexamples_verbatim():
    """티켓의 문장과 fixture가 다르면 회귀 기준이 흔들린다."""
    text = TICKET.read_text(encoding="utf-8")
    for phrase in (SUPPORTED, UNSUPPORTED_CONTINUATION, UNSUPPORTED_NUMBER):
        assert phrase in text, phrase


def test_the_ticket_keeps_the_adjudication_decision_open():
    """해결책을 NLI 하나로 확정하지 않았다 — 세 설계를 비교 대상으로 남긴다."""
    text = TICKET.read_text(encoding="utf-8")
    for option in ("C1", "C2", "C3"):
        assert option in text, option
    assert "decision-open" in text
    assert "NO_RELIABLE_CONTENT" in text


def test_the_ticket_links_the_grd_004_waiver():
    """같은 무능을 P1에서 waive하고 P0에서 hard-gate한 상태를 기록한다."""
    text = TICKET.read_text(encoding="utf-8")
    assert "GRD-004" in text
    assert "P1" in text and "WAIVED" in text
    assert "semantic entailment not automatically verified" in text


def test_the_closure_is_recorded_where_it_can_be_audited():
    """구현으로 닫혔다는 사실과 그 한계가 함께 기록돼 있어야 한다."""
    acceptance = (ROOT / "tests/test_v2_1_geo_tri_acceptance.py").read_text(
        encoding="utf-8")
    assert '"TRI-005": [' in acceptance
    assert "CLOSED_BY_REMEDIATION" in acceptance
    closure = (ROOT / "docs/finalization/V2_1_TRI_005_CLOSURE_2026-09-03.md"
               ).read_text(encoding="utf-8")
    assert "TRI-005   P0 · CLOSED" in closure
    assert "GRD-004" in closure
