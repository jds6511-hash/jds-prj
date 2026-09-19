"""WVR_SPEECH_REPORT_STYLE_COMPRESSION_V1 — 발화 근거를 보고서 문장으로 바꾸는 계층.

여기서 검사하는 것은 **표현 계층**뿐이다. STT·경계·관계·chapter·episode 구성은
이 파일의 관심사가 아니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))

import wvr_speech_report_style_v1 as style  # noqa: E402

# 픽스처는 합성 문장이다 — 개발 영상 전사는 저장소에 넣지 않는다(§20·공개 저장소 규칙).
# 검사하는 성질(토큰 run 길이·어미·1인칭)만 유지하면 되고 실제 발화일 필요가 없다.
RAW_VOLUNTEER = [
    "제가 지난주에 모임 공지를 보고 참가 신청을 미리 해두었거든요.",
    "내일 기온이 많이 떨어진다고 해서 옷을 두껍게 챙겨 입어야 할 것 같아요.",
]
REPORT_VOLUNTEER = "모임에 참가하게 된 배경을 설명하고, 추운 날씨에 대비해 외출을 준비한다."


# ── 전사 복사 검사(§7) ────────────────────────────────────────────────

def test_summary_equal_to_utterance_is_flagged_as_substring():
    result = style.leakage_audit(RAW_VOLUNTEER[0], RAW_VOLUNTEER)
    assert style.SUMMARY_IS_UTTERANCE_SUBSTRING in result["signals"]


def test_long_verbatim_run_is_flagged():
    summary = "제가 지난주에 모임 공지를 보고 참가 신청을 하게 된 배경을 설명한다."
    result = style.leakage_audit(summary, RAW_VOLUNTEER)
    assert style.LONG_VERBATIM_RUN in result["signals"]
    assert result["longest_run"] >= style.VERBATIM_RUN_TOKENS


def test_two_utterances_pasted_together_are_flagged_as_concatenation():
    summary = " ".join(RAW_VOLUNTEER)
    result = style.leakage_audit(summary, RAW_VOLUNTEER)
    assert style.CONCATENATED_UTTERANCES in result["signals"]


def test_compressed_report_sentence_has_no_leakage_signal():
    result = style.leakage_audit(REPORT_VOLUNTEER, RAW_VOLUNTEER)
    assert result["signals"] == []


def test_shared_proper_noun_and_number_alone_are_allowed():
    """고유명사·수치가 겹치는 것은 복사가 아니다(§7 단서)."""
    evidence = ["연간 신청 건수가 3만 건 정도 접수되고 있다고 합니다."]
    summary = "연간 신청 건수가 3만 건 수준이라고 보고한다."
    assert style.leakage_audit(summary, evidence)["signals"] == []


def test_leakage_ratio_is_reported_even_when_no_signal_fires():
    result = style.leakage_audit(REPORT_VOLUNTEER, RAW_VOLUNTEER)
    assert 0.0 <= result["verbatim_ratio"] <= 1.0


# ── 문체 검사(§6) ─────────────────────────────────────────────────────

def test_conversational_ending_fails():
    result = style.style_audit("오늘 봉사활동을 하러 가려고 해요.")
    assert style.CONVERSATIONAL_ENDING in result["signals"]


def test_non_declarative_ending_fails():
    result = style.style_audit("국무회의 개회 및 참석자 안내.")
    assert style.NON_DECLARATIVE_ENDING in result["signals"]


def test_question_form_fails():
    result = style.style_audit("내일 기온이 영하 5도인가?")
    assert style.INTERROGATIVE in result["signals"]


def test_first_person_subject_fails():
    result = style.style_audit("제가 봉사활동 신청 배경을 설명한다.")
    assert style.FIRST_PERSON_SUBJECT in result["signals"]


def test_discourse_opener_fails():
    result = style.style_audit("그렇지만 예산 편성 방향을 논의한다.")
    assert style.FILLER_OPENER in result["signals"]


def test_repeated_sentence_fails():
    result = style.style_audit("저녁 메뉴를 준비한다. 저녁 메뉴를 준비한다.")
    assert style.INTERNAL_REPETITION in result["signals"]


def test_repeated_phrase_inside_one_sentence_fails():
    result = style.style_audit("오늘의 저녁 메뉴는 고추튀김과 오늘의 저녁 메뉴는 고추튀김을 준비한다.")
    assert style.INTERNAL_REPETITION in result["signals"]


def test_report_style_sentence_passes_style_audit():
    assert style.style_audit(REPORT_VOLUNTEER)["signals"] == []


def test_declarative_formal_ending_is_allowed():
    """'-습니다'로 끝나는 서술문은 문체 위반이 아니다 — 대화체 판정과 구분한다."""
    assert style.style_audit("예산 편성 방향을 설명합니다.")["signals"] == []


def test_sentence_count_is_diagnostic_not_a_failure():
    text = "예산 편성 방향을 설명한다. 지원 대상을 검토한다. 집행 시기를 논의한다."
    result = style.style_audit(text)
    assert result["sentence_count"] == 3
    assert result["signals"] == []


# ── 통합 판정 ─────────────────────────────────────────────────────────

def test_audit_report_style_passes_clean_summary():
    result = style.audit_report_style(REPORT_VOLUNTEER, RAW_VOLUNTEER)
    assert result["status"] == style.TRANSCRIPT_STYLE_PASS


def test_audit_report_style_fails_raw_transcript():
    result = style.audit_report_style(" ".join(RAW_VOLUNTEER), RAW_VOLUNTEER)
    assert result["status"] == style.TRANSCRIPT_STYLE_FAIL
    assert result["signals"]


def test_empty_summary_fails():
    assert style.audit_report_style("", RAW_VOLUNTEER)["status"] == style.TRANSCRIPT_STYLE_FAIL


# ── Safe Broad Summary(§14) ───────────────────────────────────────────

def test_safe_broad_summary_uses_particle_by_batchim():
    assert style.safe_broad_summary("봉사활동 준비").startswith("봉사활동 준비와")
    assert style.safe_broad_summary("예산 편성").startswith("예산 편성과")


def test_safe_broad_summary_passes_its_own_style_audit():
    text = style.safe_broad_summary("실종 사건")
    assert style.style_audit(text)["signals"] == []


def test_safe_broad_summary_adds_no_new_noun():
    """category 밖의 낱말은 고정 틀뿐이다 — 새 명사를 만들지 않는다."""
    category = "실종 사건"
    parts = style.tokens(category)
    extra = [w for w in style.tokens(style.safe_broad_summary(category))
             if not any(w.startswith(part) for part in parts)]
    assert extra == list(style.SAFE_BROAD_TEMPLATE_WORDS)


def test_unsafe_category_is_rejected():
    assert not style.category_is_safe("동안", ["예산 편성 방향을 논의했습니다."])["ok"]
    assert not style.category_is_safe("", ["예산 편성"])["ok"]
    assert not style.category_is_safe("관찰 장면", ["예산 편성"])["ok"]


def test_category_must_be_supported_by_evidence():
    assert not style.category_is_safe("주택 공급", ["오늘 저녁 메뉴를 준비합니다."])["ok"]
    assert style.category_is_safe("예산 편성", ["내년 예산 편성 방향을 설명합니다."])["ok"]


def test_category_with_foreign_script_is_rejected():
    assert not style.category_is_safe("蛤蜊 손질", ["蛤蜊 손질을 합니다."])["ok"]


# ── 단계별 결정(§2) ───────────────────────────────────────────────────

def ok(summary, category="예산 편성"):
    return {"summary": summary, "category": category, "approved": True, "reasons": []}


def bad(summary, category="예산 편성", reasons=("TRANSCRIPT_STYLE_FAIL",)):
    return {"summary": summary, "category": category, "approved": False,
            "reasons": list(reasons)}


def test_first_attempt_pass_is_generative_report_summary():
    out = style.resolve_decision([ok(REPORT_VOLUNTEER)], ["봉사활동 준비"], RAW_VOLUNTEER)
    assert out["decision"] == style.GENERATIVE_REPORT_SUMMARY
    assert out["summary"] == REPORT_VOLUNTEER
    assert out["attempt_index"] == 0


def test_second_attempt_pass_is_regenerated_report_summary():
    out = style.resolve_decision([bad("제가 갑니다."), ok(REPORT_VOLUNTEER)],
                                 ["봉사활동 준비"], RAW_VOLUNTEER)
    assert out["decision"] == style.REGENERATED_REPORT_SUMMARY
    assert out["attempt_index"] == 1


def test_both_attempts_fail_falls_back_to_safe_broad_summary():
    out = style.resolve_decision([bad("제가 갑니다."), bad("제가 또 갑니다.")],
                                 ["봉사활동 준비"],
                                 ["봉사활동 준비를 하고 있습니다."])
    assert out["decision"] == style.SAFE_BROAD_SUMMARY
    assert out["summary"] == style.safe_broad_summary("봉사활동 준비")


def test_raw_transcript_is_never_the_fallback_summary():
    out = style.resolve_decision([bad("제가 갑니다."), bad("제가 또 갑니다.")],
                                 ["봉사활동 준비"],
                                 ["봉사활동 준비를 하고 있습니다."])
    for text in RAW_VOLUNTEER:
        assert text not in out["summary"]


def test_no_safe_category_means_audio_withheld():
    out = style.resolve_decision([bad("제가 갑니다."), bad("제가 또 갑니다.")],
                                 ["동안", ""], ["예산 편성 방향을 설명합니다."])
    assert out["decision"] == style.AUDIO_WITHHELD
    assert out["summary"] is None


def test_later_category_candidate_is_used_when_first_is_unsafe():
    out = style.resolve_decision([bad("제가 갑니다."), bad("제가 또 갑니다.")],
                                 ["동안", "예산 편성"],
                                 ["내년 예산 편성 방향을 설명합니다."])
    assert out["decision"] == style.SAFE_BROAD_SUMMARY
    assert out["category"] == "예산 편성"


def test_decision_records_every_attempt_reason():
    out = style.resolve_decision([bad("제가 갑니다.", reasons=["A"]),
                                  bad("제가 또 갑니다.", reasons=["B"])],
                                 ["동안"], ["예산 편성"])
    assert out["attempt_reasons"] == [["A"], ["B"]]


# ── 이미 승인된 요약 유지(§27 정보 손실 방지) ────────────────────────

def test_attempt_can_carry_an_explicit_decision_name():
    attempt = ok(REPORT_VOLUNTEER)
    attempt["decision"] = style.APPROVED_SUMMARY_RETAINED
    out = style.resolve_decision([bad("제가 갑니다."), bad("제가 또 갑니다."), attempt],
                                 ["봉사활동 준비"], RAW_VOLUNTEER)
    assert out["decision"] == style.APPROVED_SUMMARY_RETAINED
    assert out["summary"] == REPORT_VOLUNTEER


def test_retained_summary_still_has_to_be_approved():
    attempt = bad(REPORT_VOLUNTEER)
    attempt["decision"] = style.APPROVED_SUMMARY_RETAINED
    out = style.resolve_decision([bad("제가 갑니다."), bad("제가 또 갑니다."), attempt],
                                 ["봉사활동 준비"],
                                 ["봉사활동 준비를 하고 있습니다."])
    assert out["decision"] == style.SAFE_BROAD_SUMMARY


def test_approved_category_does_not_need_literal_evidence_support():
    """동결 파이프라인이 승인한 구분은 이미 통과한 것이다 — 어휘 일치를 다시 요구하지 않는다."""
    evidence = ["일단 4개까지만 부탁할게요.", "3개 먼저 드릴게요."]
    assert not style.category_is_safe("봉사활동", evidence)["ok"]
    assert style.category_is_safe("봉사활동", evidence, approved=True)["ok"]


def test_approved_flag_does_not_bypass_the_other_checks():
    assert not style.category_is_safe("동안", ["예산 편성"], approved=True)["ok"]
    assert not style.category_is_safe("蛤蜊 손질", ["蛤蜊"], approved=True)["ok"]
    assert not style.category_is_safe("관찰 장면", ["예산 편성"], approved=True)["ok"]


def test_category_candidates_accept_approved_markers():
    out = style.resolve_decision([bad("제가 갑니다."), bad("제가 또 갑니다.")],
                                 [{"category": "봉사활동", "approved": True}],
                                 ["일단 4개까지만 부탁할게요."])
    assert out["decision"] == style.SAFE_BROAD_SUMMARY
    assert out["category"] == "봉사활동"


# ── 정보 손실 확인(§23) ───────────────────────────────────────────────

def test_information_retention_reports_dropped_numbers():
    before = "아동 실종 신고가 매월 14만 건, 성인 실종 신고가 18만 건입니다."
    after = "아동·성인 실종 신고 현황을 보고한다."
    result = style.information_retention(after, before, [before])
    assert "14만" in " ".join(result["dropped_numbers"])


def test_information_retention_keeps_numbers_that_survive():
    before = "추납 신청자는 전체의 2.2%입니다."
    after = "추납 신청자 비율이 전체의 2.2% 수준이라고 보고한다."
    result = style.information_retention(after, before, [before])
    assert result["dropped_numbers"] == []


def test_information_retention_measures_topic_overlap():
    before = "예산 편성 방향을 설명했습니다."
    result = style.information_retention("예산 편성 방향을 설명한다.", before, [before])
    assert result["topic_retention"] > 0.5


def test_information_retention_detects_collapse_to_nothing():
    before = "내년 예산 편성 방향과 청년 지원 계획을 설명했습니다."
    result = style.information_retention("관련 내용을 다룬다.", before, [before])
    assert result["topic_retention"] == 0.0


# ── 영상 독립성(§20) ──────────────────────────────────────────────────

def test_module_source_has_no_video_specific_strings():
    source = (ROOT / "src" / "jds_video" / "_internal" / "wvr_speech_report_style_v1.py").read_text(encoding="utf-8")
    for token in ("BOaiHUx5mQs", "69E1sdSMaO4", "softyeon", "xekZO4n4QuE",
                  "봉사활동", "고추튀김", "실종", "예산", "케이크", "라면", "국무회의"):
        assert token not in source, token
