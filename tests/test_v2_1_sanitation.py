"""A-05 sanitation + claim eligibility.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-05
근거: ADDENDUM OPEN-7(반복은 삭제 근거가 아니다) · OPEN-9(보존 ≠ 승격)

```
상태            preserved   usable_for_claims
VALID              true          true
SUSPECT            true          false
REJECTED           true          false
EMPTY               -            false
PARSE_FAILED        -            false
```

판정은 **결정적 특징만** 쓴다. LLM에게 "이 발화가 진짜인가"를 묻지 않는다.
"""
import re
from pathlib import Path

import pytest

from v2_1_fixtures import (
    BOILERPLATE,
    EXCITED_SPEECH,
    FOREIGN_CAPTION,
    INSTRUCTION_ECHO,
    scenario,
)
from v2_1_sanitation import (
    EMPTY,
    PARSE_FAILED,
    REJECTED,
    REPEAT_THRESHOLD,
    SUSPECT,
    VALID,
    classify,
    classify_channel,
    eligible_support,
    normalize_for_counting,
    occurrence_counts,
)

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_sanitation.py"


def _judge(text, source_type="asr", counts=None, **kw):
    return classify(text, source_type=source_type, counts=counts or {}, **kw)


# ── SAN-001 instruction echo ─────────────────────────────────────────────
def test_san_001_instruction_echo_does_not_pass_as_valid():
    j = _judge(INSTRUCTION_ECHO, source_type="vlm")
    assert j.status == REJECTED
    assert j.reason == "instruction_echo"
    assert j.usable_for_claims is False


def test_san_001_instruction_echo_is_rejected_on_its_own_grounds():
    """한 번만 나와도 REJECTED다 — 반복 횟수와 무관한 독립 근거."""
    assert _judge(INSTRUCTION_ECHO, source_type="vlm", counts={INSTRUCTION_ECHO: 1}).status == REJECTED


def test_san_001_ordinary_caption_is_valid():
    assert _judge("두 여성이 해변에 앉아 있습니다.", source_type="vlm").status == VALID


def test_san_001_agreement_alone_is_not_an_echo():
    """'알겠습니다'만으로 지우면 실제 발화가 사라진다."""
    assert _judge("네, 알겠습니다.").status == VALID
    assert _judge("요청하신 자리로 갈게요.").status == VALID


# ── SAN-002 empty ────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["", "   ", "\n\t", None])
def test_san_002_blank_is_empty(text):
    j = _judge(text)
    assert j.status == EMPTY
    assert j.usable_for_claims is False


def test_san_002_empty_is_not_rejected():
    assert _judge("").status != REJECTED


# ── SAN-005 parse failure ≠ rejected ─────────────────────────────────────
def test_san_005_parse_failure_is_its_own_state():
    j = _judge("아무 텍스트", parse_failed=True)
    assert j.status == PARSE_FAILED
    assert j.status != REJECTED
    assert j.status != EMPTY
    assert j.usable_for_claims is False


def test_san_005_parse_failure_wins_over_content_rules():
    """구조가 깨졌으면 내용 규칙을 적용할 근거 자체가 없다."""
    assert _judge(INSTRUCTION_ECHO, source_type="vlm", parse_failed=True).status == PARSE_FAILED


# ── SAN-007 OCR isolation ────────────────────────────────────────────────
def test_san_007_ocr_is_never_claim_support_on_its_own():
    j = _judge("출발 09:30 김해공항", source_type="ocr")
    assert j.status == VALID
    assert j.usable_for_claims is False
    assert j.reason == "ocr_unverified"


def test_san_007_ocr_only_scenario_yields_no_usable_support():
    s = scenario("S8")
    judged = classify_channel(s.ocr, "ocr")
    assert not eligible_support(judged.values())


def test_san_007_asr_valid_is_usable():
    assert _judge("여기 소스를 넣으면 돼.").usable_for_claims is True


# ── SAN-010 실제 발화 보존 ───────────────────────────────────────────────
def test_san_010_excited_repetition_within_one_utterance_is_preserved():
    """`is_corrupted_caption`의 반복 규칙을 쓰면 여기서 11건이 지워진다."""
    j = _judge(EXCITED_SPEECH, counts={EXCITED_SPEECH: 1})
    assert j.status == VALID
    assert j.usable_for_claims is True
    assert j.text == EXCITED_SPEECH


def test_san_010_source_does_not_use_the_caption_repetition_rule():
    src = SRC.read_text(encoding="utf-8")
    assert "is_corrupted_caption" not in src


def test_san_010_every_status_preserves_the_original_text():
    counts = {BOILERPLATE: 8}
    for text, source_type in (
        (INSTRUCTION_ECHO, "vlm"),
        (BOILERPLATE, "asr"),
        (EXCITED_SPEECH, "asr"),
        (FOREIGN_CAPTION, "vlm"),
        ("한글자막 by 홍길동", "asr"),
    ):
        j = classify(text, source_type=source_type, counts=counts)
        assert j.text == text, j.status
        assert j.preserved is True


# ── SAN-011 반복 → SUSPECT, 삭제 아님 ────────────────────────────────────
def test_san_011_repetition_at_threshold_is_suspect():
    j = _judge(BOILERPLATE, counts={BOILERPLATE: REPEAT_THRESHOLD})
    assert j.status == SUSPECT
    assert j.reason == "repeated"
    assert j.preserved is True
    assert j.usable_for_claims is False
    assert j.text == BOILERPLATE


def test_san_011_below_threshold_stays_valid():
    j = _judge(BOILERPLATE, counts={BOILERPLATE: REPEAT_THRESHOLD - 1})
    assert j.status == VALID


def test_san_011_threshold_is_eight():
    assert REPEAT_THRESHOLD == 8


def test_open_7_repetition_is_never_a_rejection_ground():
    for count in (8, 50, 500):
        assert _judge(BOILERPLATE, counts={BOILERPLATE: count}).status == SUSPECT


def test_open_7_counting_normalizes_only_whitespace():
    assert normalize_for_counting("  다음 영상에서\r\n만나요.  ") == normalize_for_counting(
        "다음 영상에서 만나요."
    )
    assert normalize_for_counting("다음 영상에서 만나요!") != normalize_for_counting(
        "다음 영상에서 만나요."
    )


def test_open_7_no_similarity_matching():
    """유사도 매칭을 넣으면 서로 다른 실제 발화가 한 덩어리로 묶인다."""
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("difflib", "SequenceMatcher", "Levenshtein", "ratio", "fuzzy"):
        assert forbidden not in src, "유사도 매칭이 들어왔다: " + forbidden


def test_occurrence_counts_uses_exact_normalized_full_text():
    counts = occurrence_counts(["a b", " a  b ", "a b!", ""])
    assert counts["a b"] == 2
    assert counts["a b!"] == 1
    assert "" not in counts


# ── 채널 판정 · S1에서 두 규칙이 동시에 걸린다 ───────────────────────────
def test_s1_separates_boilerplate_from_real_speech():
    s = scenario("S1")
    judged = classify_channel(s.asr, "asr")
    assert [j.status for j in judged.values() if j.text == BOILERPLATE] == [SUSPECT] * 8
    assert judged[8].status == VALID and judged[8].text == EXCITED_SPEECH
    assert judged[11].status == EMPTY


def test_s1_usable_support_excludes_suspect():
    judged = classify_channel(scenario("S1").asr, "asr")
    usable = eligible_support(judged.values())
    assert {j.text for j in usable} == {
        EXCITED_SPEECH,
        "여기 소스를 넣으면 돼.",
        "해변으로 내려가 보자.",
    }


def test_s5_all_empty_channel_has_no_support():
    judged = classify_channel(scenario("S5").asr, "asr")
    assert {j.status for j in judged.values()} == {EMPTY}
    assert not eligible_support(judged.values())


def test_s6_echo_and_foreign_caption_are_flagged_differently():
    judged = classify_channel(scenario("S6").caption, "vlm")
    assert judged[3].status == REJECTED and judged[3].reason == "instruction_echo"
    assert judged[7].status == SUSPECT and judged[7].reason == "foreign_script"


# ── 독립 근거 ────────────────────────────────────────────────────────────
def test_subtitle_credit_is_rejected():
    j = _judge("한글자막 by 홍길동")
    assert j.status == REJECTED
    assert j.reason == "subtitle_credit"


def test_credit_phrase_inside_a_sentence_is_real_speech():
    """전체 일치로만 판정한다 — 문장 안에 섞이면 실제 발화다."""
    assert _judge("이 영상은 한글자막 by 누가 달아주신 걸로 봤어요.").status == VALID


def test_url_and_broadcaster_are_rejected():
    assert _judge("자세한 내용은 홈페이지 참고").reason == "overlay_or_url"
    assert _judge("https://example.com 에서 확인").status == REJECTED


def test_independent_ground_wins_over_repetition():
    credit = "한글자막 by 홍길동"
    assert _judge(credit, counts={credit: 40}).status == REJECTED


# ── 계층 경계 ────────────────────────────────────────────────────────────
def test_a05_does_not_implement_grounding():
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("FAIL_INELIGIBLE_SUPPORT", "FAIL_REFERENCE", "GRD-",
                      "anchor_cites", "episode"):
        assert forbidden not in src, "Gate B 책임을 침범했다: " + forbidden


def test_a05_does_not_call_an_llm():
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("llm", "generate", "prompt", "torch"):
        assert forbidden not in src.lower(), "판정에 모델을 끌어들였다: " + forbidden


def test_a05_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
