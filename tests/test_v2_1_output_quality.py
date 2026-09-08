"""report output quality gate — 최종 출력 문장의 결정적 품질 판정 (2026-09-08).

사전등록: `docs/finalization/V2_1_OUTPUT_QUALITY_ADDENDUM_2026-09-08.md`

```
PASS      정상
SUSPECT   diagnostic 있음 · 자동 제외 아님
FAIL      presentation eligibility 제외
```

parse 성공과 output-language 성공을 가른다. LLM을 부르지 않고, 문장을 고치지 않는다.
"""
import pytest

from v2_1_output_quality import (
    FAIL,
    FOREIGN_SCRIPT_RUN_MIN,
    PASS,
    QUALITY_POLICY_VERSION,
    QUALITY_STATUSES,
    REASON_BROKEN_MIXED_SCRIPT,
    REASON_EXCESSIVE_REPETITION,
    REASON_LANGUAGE_CONTRACT,
    REASON_LANGUAGE_DRIFT,
    SUSPECT,
    evaluate_summary,
)

# H13 실측 문장 (제출본에 실제로 실린 형태)
H13 = ("두 사람이 빵을 만드는 모습을 보여주고, 여성들이 다양한 상품을 구매하며, "
       "마지막으로 베이킹용품尤其是关于蛋糕，是否有售？价格在这里，请看样品，"
       "厚度差不多的话可以坐下挑选。")


# ── freeze된 상수 ────────────────────────────────────────────────────────
def test_the_frozen_constants_are_named_not_hidden():
    assert FOREIGN_SCRIPT_RUN_MIN == 8
    assert QUALITY_POLICY_VERSION == "output_quality_v1"
    assert QUALITY_STATUSES == (PASS, SUSPECT, FAIL)


# ── T1 정상 한국어 ───────────────────────────────────────────────────────
def test_t1_normal_korean_summary_passes():
    verdict = evaluate_summary(
        "여성이 주방에서 재료를 손질하고 조리 도구를 정리하는 모습이 이어진다.")
    assert verdict.status == PASS
    assert verdict.reasons == ()


# ── T2 정상 영어 브랜드명·MBTI·URL ────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "여성이 Nike 운동화를 신고 시장을 걷는다.",
    "출연자가 ENFP 성향을 언급하며 대화한다.",
    "화면 하단에 https://example.com 주소가 표시된다.",
    "테이블에 KF94 마스크와 A4 용지가 놓여 있다.",
])
def test_t2_latin_names_and_codes_pass(text):
    """ASCII가 하나라도 있으면 실패하는 규칙은 금지다."""
    assert evaluate_summary(text).status == PASS


# ── T3 H13 형태의 긴 중국어 drift ─────────────────────────────────────────
def test_t3_long_foreign_script_drift_fails():
    verdict = evaluate_summary(H13)
    assert verdict.status == FAIL
    assert REASON_LANGUAGE_DRIFT in verdict.reasons
    assert verdict.diagnostics["longest_foreign_run"] >= FOREIGN_SCRIPT_RUN_MIN


def test_cjk_punctuation_does_not_break_the_run():
    """문장부호로 끊어서 규칙을 피해 가지 못한다."""
    verdict = evaluate_summary("빵을 만든다关于蛋糕，是否有售？")
    assert verdict.status == FAIL
    assert REASON_LANGUAGE_DRIFT in verdict.reasons


def test_the_run_threshold_is_the_frozen_boundary():
    seven = evaluate_summary("빵을 만든다" + "关" * (FOREIGN_SCRIPT_RUN_MIN - 1))
    eight = evaluate_summary("빵을 만든다" + "关" * FOREIGN_SCRIPT_RUN_MIN)
    assert REASON_LANGUAGE_DRIFT not in seven.reasons
    assert REASON_LANGUAGE_DRIFT in eight.reasons


# ── T4 짧은 loanword·한두 자 한자 ─────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "테이블에 케이크와 커피가 놓여 있다.",
    "간판에 大자가 적혀 있다.",
    "포장지에 中자와 小자가 보인다.",
])
def test_t4_short_loanwords_and_short_han_pass(text):
    assert evaluate_summary(text).status == PASS


# ── T5 비정상 mixed token ────────────────────────────────────────────────
def test_t5_mixed_hangul_latin_token_is_a_diagnostic_not_a_removal():
    verdict = evaluate_summary("주인공이 카레우don과 밀가루를 처리한다.")
    assert verdict.status == SUSPECT
    assert REASON_BROKEN_MIXED_SCRIPT in verdict.reasons
    assert verdict.status != FAIL
    assert any("카레우don" in token
               for token in verdict.diagnostics["mixed_tokens"])


# ── Q3 반복 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "여성이 재료를 재료를 손질한다.",
    "고추를 넣는다 고추를 넣는다 그리고 젓는다.",
])
def test_q3_adjacent_repetition_is_a_diagnostic(text):
    verdict = evaluate_summary(text)
    assert verdict.status == SUSPECT
    assert REASON_EXCESSIVE_REPETITION in verdict.reasons


def test_q3_uses_adjacency_not_a_count_threshold():
    """같은 단어가 떨어져서 여러 번 나오는 것은 실제 반복 발화일 수 있다."""
    verdict = evaluate_summary(
        "여성이 고추를 씻고 야채를 다듬은 뒤 다시 고추를 볶는다.")
    assert REASON_EXCESSIVE_REPETITION not in verdict.reasons


# ── Q4 출력 언어 계약 ────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "A woman prepares ingredients in the kitchen.",
    "关于蛋糕是否有售",
    "",
    None,
])
def test_q4_a_summary_without_hangul_fails_the_language_contract(text):
    verdict = evaluate_summary(text)
    assert verdict.status == FAIL
    assert REASON_LANGUAGE_CONTRACT in verdict.reasons


# ── 판정 성질 ────────────────────────────────────────────────────────────
def test_fail_outranks_suspect():
    verdict = evaluate_summary("주인공이 카레우don을 먹는다" + "关" * 12)
    assert verdict.status == FAIL
    assert REASON_LANGUAGE_DRIFT in verdict.reasons
    assert REASON_BROKEN_MIXED_SCRIPT in verdict.reasons


def test_the_verdict_is_deterministic_and_sorted():
    first, second = evaluate_summary(H13), evaluate_summary(H13)
    assert first == second
    assert list(first.reasons) == sorted(first.reasons)


def test_the_text_is_never_modified():
    verdict = evaluate_summary(H13)
    assert verdict.text == H13
