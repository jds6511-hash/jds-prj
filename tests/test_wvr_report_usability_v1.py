"""WVR_REPORT_USABILITY_POLISH_V1 — 사용자-facing 표현 계층만 검사한다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))

import wvr_report_usability_v1 as usability  # noqa: E402


# ── category 검증 ──────────────────────────────────────────────────────

def test_good_noun_phrases_pass():
    for text in ("경제 정책", "봉사활동", "식재료 보관", "예산 편성", "조리", "질의·응답"):
        assert usability.validate_category(text)["ok"], text


def test_meaningless_fragments_fail():
    for text in ("이거", "저거", "그것", "동안", "하지만", "아까", "너무", "즉시"):
        assert not usability.validate_category(text)["ok"], text


def test_verb_and_ending_forms_fail():
    for text in ("선택하실", "같아요", "했습니다", "합니다", "먹었어요", "하고"):
        assert not usability.validate_category(text)["ok"], text


def test_sentence_is_rejected():
    assert not usability.validate_category("자막을 설정에서 선택할 수 있습니다.")["ok"]


def test_too_long_is_rejected():
    assert not usability.validate_category("아주 길고 자세한 설명이 들어간 구분 이름")["ok"]


def test_non_korean_category_is_rejected():
    assert not usability.validate_category("预算编制")["ok"]


def test_acronym_category_is_allowed():
    assert usability.validate_category("AI 정책")["ok"]


# ── category 선택 우선순위 ─────────────────────────────────────────────

def test_approved_generative_category_wins():
    out = usability.choose_category(
        generative_category="봉사활동", display="GENERATIVE",
        summary="참가자들이 지게를 이용해 물건을 옮기는 봉사활동을 하고 있다.",
        existing_category="사라다", evidence="음성", broad_activity=[], activity_labels_useful=True)
    assert out["category"] == "봉사활동" and out["source"] == usability.FROM_GENERATIVE


def test_rejected_summary_requires_lexical_support():
    """생성 요약이 막힌 행은 그 요약에서 나온 구분도 그대로 믿지 않는다."""
    out = usability.choose_category(
        generative_category="봉사활동", display="EXTRACTIVE_FALLBACK",
        summary="그건 나중에 따로 드시면 된다고 하네요 네 알겠습니다",
        existing_category="설탕", evidence="음성", broad_activity=[], activity_labels_useful=True)
    assert out["category"] != "봉사활동"


def test_rejected_summary_keeps_supported_category():
    out = usability.choose_category(
        generative_category="라면", display="EXTRACTIVE_FALLBACK",
        summary="집에서 먹는 라면이 가장 맛있다고 생각한다.",
        existing_category="라면", evidence="음성", broad_activity=[], activity_labels_useful=True)
    assert out["category"] == "라면"


def test_visual_row_uses_activity_label_when_it_discriminates():
    out = usability.choose_category(
        generative_category=None, display="VISUAL_EVIDENCE",
        summary="식재료를 준비하고 조리하는 활동", existing_category="관찰 장면",
        evidence="화면", broad_activity=["FOOD_PREPARATION"], activity_labels_useful=True)
    assert out["category"] == "조리" and out["source"] == usability.FROM_ACTIVITY


def test_single_activity_video_falls_back_to_neutral():
    """영상 전체가 같은 activity면 그 라벨은 아무것도 구분하지 못한다."""
    out = usability.choose_category(
        generative_category=None, display="VISUAL_EVIDENCE",
        summary="남성이 마이크 앞에서 말하고 있습니다", existing_category="관찰 장면",
        evidence="화면", broad_activity=["WORK_OR_STUDY"], activity_labels_useful=False)
    assert out["category"] == usability.NEUTRAL_VISUAL
    assert out["source"] == usability.FROM_NEUTRAL


def test_neutral_fallback_for_speech_row():
    out = usability.choose_category(
        generative_category="동안", display="EXTRACTIVE_FALLBACK",
        summary="그렇지만 행안부 차원에서 어쨌든 그쪽은 어려운 지역이니까",
        existing_category="동안", evidence="음성", broad_activity=[], activity_labels_useful=True)
    assert out["category"] == usability.NEUTRAL_SPEECH


def test_category_never_introduces_unseen_concept_on_fallback_rows():
    out = usability.choose_category(
        generative_category="연탄 봉사", display="VISUAL_ONLY_DOWNGRADE",
        summary="사람들이 검은색 원통형 물체를 다루고 있습니다",
        existing_category="이렇게", evidence="화면", broad_activity=[],
        activity_labels_useful=True)
    assert "연탄" not in out["category"]


# ── 라틴 문자 표시 검사 ────────────────────────────────────────────────

def test_latin_token_present_in_evidence_is_kept():
    out = usability.display_language_check("SRT 철도 합병을 논의했다", ["SRT 얘기가 나왔습니다"])
    assert out["status"] == usability.PASS


def test_acronym_is_kept_even_without_exact_evidence():
    out = usability.display_language_check("AI 산업을 지원한다", ["인공지능 산업 지원"])
    assert out["status"] == usability.PASS


def test_unsupported_english_word_fails():
    out = usability.display_language_check("안전 확보를 위한 various 정책을 발표한다",
                                           ["여러 가지 정책을 발표합니다"])
    assert out["status"] == usability.FAIL
    assert out["tokens"] == ["various"]


def test_pure_korean_passes():
    assert usability.display_language_check("예산안을 편성했다", ["예산안"])["status"] == usability.PASS


# ── 중복 정리 ──────────────────────────────────────────────────────────

def row(rid, start, end, summary, evidence="화면", category="관찰 장면"):
    return {"row_id": rid, "start": start, "end": end, "summary": summary,
            "evidence": evidence, "category": category}


def test_identical_overlapping_rows_collapse_to_the_longer_one():
    rows = [row("R1", 24, 32, "사람이 빵을 준비하고 있습니다"),
            row("R2", 27, 76, "사람이 빵을 준비하고 있습니다")]
    kept, suppressed = usability.reduce_redundancy(rows)
    assert [r["row_id"] for r in kept] == ["R2"]
    assert suppressed[0]["suppression_reason"] == usability.EXACT_DUPLICATE_OVERLAP


def test_identical_rows_far_apart_are_both_kept():
    rows = [row("R1", 0, 60, "식재료를 조리하는 활동"),
            row("R2", 1800, 1860, "식재료를 조리하는 활동")]
    kept, _ = usability.reduce_redundancy(rows)
    assert len(kept) == 2


def test_contained_row_is_suppressed():
    rows = [row("R1", 100, 400, "식사 준비를 위해 음식을 접시에 올리는 행동"),
            row("R2", 150, 200, "음식을 접시에 올리는 행동")]
    kept, suppressed = usability.reduce_redundancy(rows)
    assert [r["row_id"] for r in kept] == ["R1"]
    assert suppressed[0]["suppression_reason"] == usability.CONTAINED_IN_OVERLAPPING_ROW


def test_generic_visual_row_is_suppressed_when_audio_covers_it():
    rows = [row("R1", 100, 400, "예산안 편성 방향을 보고한다", evidence="음성", category="예산 편성"),
            row("R2", 150, 200, "남성이 마이크 앞에서 말하고 있습니다")]
    kept, suppressed = usability.reduce_redundancy(rows)
    assert [r["row_id"] for r in kept] == ["R1"]
    assert suppressed[0]["suppression_reason"] == usability.GENERIC_VISUAL_COVERED_BY_AUDIO


def test_generic_visual_row_is_kept_without_audio_coverage():
    rows = [row("R1", 100, 400, "남성이 마이크 앞에서 말하고 있습니다")]
    kept, suppressed = usability.reduce_redundancy(rows)
    assert len(kept) == 1 and suppressed == []


def test_informative_visual_row_is_never_suppressed_by_audio():
    rows = [row("R1", 100, 400, "예산안 편성 방향을 보고한다", evidence="음성", category="예산 편성"),
            row("R2", 150, 200, "사람이 지게로 연탄을 옮기고 있다")]
    kept, _ = usability.reduce_redundancy(rows)
    assert len(kept) == 2


def test_suppression_keeps_evidence_fields():
    rows = [row("R1", 24, 32, "같은 문장"), row("R2", 27, 76, "같은 문장")]
    _, suppressed = usability.reduce_redundancy(rows)
    assert suppressed[0]["suppressed"] is True
    assert suppressed[0]["row_id"] == "R1"


def test_withheld_audio_category_does_not_leak_into_visual_row():
    """음성을 내린 행에서 그 음성의 구분이 라벨로 되살아나면 안 된다."""
    out = usability.choose_category(
        generative_category="재료 추가", display="VISUAL_ONLY_DOWNGRADE",
        summary="식재료를 준비하고 조리하는 활동", existing_category="관찰 장면",
        evidence="화면", broad_activity=["FOOD_PREPARATION"], activity_labels_useful=True)
    assert out["category"] == "조리" and out["source"] == usability.FROM_ACTIVITY


def test_longer_noun_phrase_category_is_allowed():
    assert usability.validate_category("채불 문제 해결 방안")["ok"]
    assert usability.validate_category("추석 시즌 물가와 지역화폐 지원")["ok"] is False


def test_audio_row_with_발표_verb_still_covers_generic_visual():
    rows = [row("R1", 100, 400, "정부는 지원 정책을 발표하였으며 계획을 설명했다",
                evidence="음성", category="민생 지원"),
            row("R2", 150, 200, "회의실에서 발표를 하고 있는 사람")]
    kept, suppressed = usability.reduce_redundancy(rows)
    assert [r["row_id"] for r in kept] == ["R1"]
