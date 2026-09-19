"""WVR_GROUNDING_GUARD_AND_ASR_CONFIDENCE_DIAG_V1 — PHASE A.

근거에 없던 사람·역할·기관·장소·대상이 생성문에 새로 나타나는 것을 결정적 규칙으로 잡는다.
임계값이 없다 — 근거 문자열과의 대조와 고정 어휘집만 쓴다.
"""
import pytest

import wvr_grounding_guard_v1 as GG


EVIDENCE_JIGE = ["지게를 메고 언덕길을 올라갑니다",
                 "이 지게는 평소에 메고 다니는 것입니다"]


# ── 개체·역할 추출 ─────────────────────────────────────────────────────

def test_extract_role_from_generated_text():
    found = GG.extract_entities("서비스 제공자가 고객에게 지게를 이용해 내장을 옮기는 과정을 보여준다.")
    assert "제공자" in found["roles"] or "서비스 제공자" in found["roles"]
    assert "고객" in found["roles"]


def test_extract_place_and_org():
    found = GG.extract_entities("홍제역 근처 코스트코에서 구매하고 보건복지부에 보고한다.")
    assert "홍제역" in found["places"]
    assert any("복지부" in o for o in found["orgs"])


def test_extract_ignores_plain_activity_words():
    found = GG.extract_entities("치즈를 냉장 보관하는 방법을 설명한다.")
    assert found["roles"] == [] and found["orgs"] == [] and found["places"] == []


# ── 근거 대조 ──────────────────────────────────────────────────────────

def test_novel_role_is_flagged():
    result = GG.check_grounding("서비스 제공자가 고객에게 지게를 이용해 내장을 옮긴다.", EVIDENCE_JIGE)
    assert result["status"] == GG.NOVEL_ROLE
    assert "고객" in result["ungrounded"]


def test_paraphrase_of_existing_entity_is_grounded():
    result = GG.check_grounding("치즈를 냉장 보관한다.", ["치즈를 냉장고에 넣어 둔다"])
    assert result["status"] == GG.GROUNDED


def test_entity_present_in_evidence_is_grounded():
    result = GG.check_grounding("지게를 메고 이동한다.", EVIDENCE_JIGE)
    assert result["status"] == GG.GROUNDED


def test_novel_place_is_flagged():
    result = GG.check_grounding("홍제역 앞에서 구매한다.", ["시장에서 강판을 샀어요"])
    assert result["status"] == GG.NOVEL_ENTITY
    assert "홍제역" in result["ungrounded"]


def test_place_mentioned_in_evidence_is_grounded():
    result = GG.check_grounding("홍제역 근처에서 구매한다.", ["홍제역에 바이소가 있길래 가봤어요"])
    assert result["status"] == GG.GROUNDED


def test_neutral_person_words_do_not_trigger():
    result = GG.check_grounding("사람들이 음식을 준비한다.", ["다 같이 준비하고 있어요"])
    assert result["status"] == GG.GROUNDED


def test_role_present_in_evidence_is_allowed():
    result = GG.check_grounding("장관이 보고한다.", ["행안부 장관께서 내용을 파악하고 계신가요"])
    assert result["status"] == GG.GROUNDED


def test_partial_stem_match_is_uncertain_not_grounded():
    result = GG.check_grounding("운전자가 설명한다.", ["운전하는 방법을 설명할게요"])
    assert result["status"] in (GG.UNCERTAIN, GG.NOVEL_ROLE)


def test_visual_claims_count_as_evidence():
    result = GG.check_grounding("참석자가 마이크 앞에서 말한다.",
                                ["회의를 시작합니다"],
                                visual_texts=["여러 명의 참석자가 마이크 앞에 앉아 있다"])
    assert result["status"] == GG.GROUNDED


def test_report_lists_every_checked_entity():
    result = GG.check_grounding("고객이 지게를 멘다.", EVIDENCE_JIGE)
    assert result["checked"], "검사한 후보를 기록해야 한다"
    assert any(item["entity"] == "고객" for item in result["checked"])


# ── 승인 조건 결합 (§7) ────────────────────────────────────────────────

def test_approval_requires_grounded_even_if_semantics_supported():
    decision = GG.approve(language_pass=True, semantic_status="SUPPORTED",
                          grounding_status=GG.NOVEL_ROLE)
    assert decision["approved"] is False
    assert GG.NOVEL_ROLE in decision["reasons"]


def test_approval_blocks_uncertain_grounding():
    decision = GG.approve(language_pass=True, semantic_status="SUPPORTED",
                          grounding_status=GG.UNCERTAIN)
    assert decision["approved"] is False


def test_approval_passes_when_all_three_agree():
    decision = GG.approve(language_pass=True, semantic_status="SUPPORTED",
                          grounding_status=GG.GROUNDED)
    assert decision["approved"] is True and decision["reasons"] == []


def test_approval_blocks_unsupported_semantics():
    decision = GG.approve(language_pass=True, semantic_status="UNSUPPORTED",
                          grounding_status=GG.GROUNDED)
    assert decision["approved"] is False


def test_approval_blocks_language_failure():
    decision = GG.approve(language_pass=False, semantic_status="SUPPORTED",
                          grounding_status=GG.GROUNDED)
    assert decision["approved"] is False


# ── ASR 진단 (PHASE B) ────────────────────────────────────────────────

def test_asr_state_normal():
    segment = {"avg_logprob": -0.25, "no_speech_prob": 0.02, "compression_ratio": 1.4,
               "text": "예산 집행 현황을 보고드립니다."}
    assert GG.asr_state(segment) == GG.ASR_NORMAL


def test_asr_state_low_confidence():
    segment = {"avg_logprob": -1.3, "no_speech_prob": 0.05, "compression_ratio": 1.5,
               "text": "프리팬이 완성되었습니다."}
    assert GG.asr_state(segment) == GG.ASR_LOW_CONFIDENCE


def test_asr_state_repetition_anomaly():
    segment = {"avg_logprob": -0.4, "no_speech_prob": 0.01, "compression_ratio": 3.2,
               "text": "참기름 참기름 참기름 참기름 참기름"}
    assert GG.asr_state(segment) == GG.ASR_REPETITION_ANOMALY


def test_asr_state_unresolved_when_metrics_missing():
    assert GG.asr_state({"text": "프리팬이 완성되었습니다."}) == GG.ASR_UNRESOLVED


def test_asr_diagnostic_does_not_guess_correct_text():
    segment = {"avg_logprob": -1.4, "no_speech_prob": 0.1, "compression_ratio": 1.6,
               "text": "프리팬이 완성되었습니다."}
    record = GG.asr_record("SP002", segment)
    assert record["text"] == "프리팬이 완성되었습니다."
    assert "suggested_text" not in record          # 정답 복원 실험이 아니다
    assert record["state"] == GG.ASR_LOW_CONFIDENCE
