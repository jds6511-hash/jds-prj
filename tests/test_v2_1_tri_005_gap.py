"""TRI-005 implementation gap — counterexample을 회귀 fixture로 고정한다.

```
DECISION = C   implementation gap으로 유지 · 별도 remediation 사전등록 필요
A  REJECTED    실패한 P0의 기준을 사후에 좁히지 않는다
B  REJECTED    실제 counterexample을 P0 waiver로 넘기지 않는다
```

두 counterexample은 **어떤 해결책을 택하더라도 RED → GREEN을 만들어야 하는** 회귀
fixture다. 실패 양상이 다르므로 하나로 합치지 않는다.

```
UNSUPPORTED_CONTINUATION  근거에 없는 후속 사건·행위·결과
UNSUPPORTED_NUMBER        근거에 없는 수량
```

계약 테스트는 `xfail(strict=True)`다. remediation이 들어오면 XPASS가 실패로 잡히고,
그때 marker를 제거하며 티켓을 닫아야 한다 — **조용히 지나갈 수 없다.**

상세: `docs/finalization/V2_1_TRI_005_REMEDIATION_TICKET_2026-09-02.md`
"""
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_grounding import (
    FAIL_INELIGIBLE_SUPPORT,
    FAIL_NO_SUPPORT,
    FAIL_UNSUPPORTED,
    PASS,
)

ROOT = Path(__file__).resolve().parents[1]
TICKET = ROOT / "docs/finalization/V2_1_TRI_005_REMEDIATION_TICKET_2026-09-02.md"

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


# ── 아직 막히지 않는 것 — remediation 목표 ───────────────────────────────
@pytest.mark.xfail(strict=True, reason="TRI-005 implementation gap · DECISION C")
def test_tri_005_an_unsupported_continuation_must_not_be_accepted(tmp_path):
    """근거에 없는 후속 사건을 단 요약이 accepted 상태로 남아서는 안 된다."""
    _, episode = _episode(tmp_path, UNSUPPORTED_CONTINUATION)
    accepted = (episode["grounding_status"] == PASS
                and episode["summary"] == UNSUPPORTED_CONTINUATION)
    assert not accepted


@pytest.mark.xfail(strict=True, reason="TRI-005 implementation gap · DECISION C")
def test_tri_005_an_unsupported_quantity_must_not_be_accepted(tmp_path):
    """근거에 없는 수량을 넣은 요약이 accepted 상태로 남아서는 안 된다."""
    _, episode = _episode(tmp_path, UNSUPPORTED_NUMBER)
    accepted = (episode["grounding_status"] == PASS
                and episode["summary"] == UNSUPPORTED_NUMBER)
    assert not accepted


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


def test_the_gap_is_not_closed_anywhere():
    """어딘가에서 TRI-005를 PROVEN으로 적으면 여기서 깨진다."""
    acceptance = (ROOT / "tests/test_v2_1_geo_tri_acceptance.py").read_text(
        encoding="utf-8")
    assert '"TRI-005": "implementation-gap"' in acceptance
    report = (ROOT / "docs/finalization/V2_1_FINAL_ACCEPTANCE_2026-09-02.md"
              ).read_text(encoding="utf-8")
    assert "IMPLEMENTATION_COMPLETE = NO" in report
