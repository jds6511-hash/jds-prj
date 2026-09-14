"""v2.1 Report output quality — 최종 출력 문장의 결정적 품질 판정 (2026-09-08).

```
parse 성공        JSON 계약을 지켰다
output 품질       사람에게 보여도 되는 문장인가
```

둘은 다르다. H13은 parse에 성공했지만 한국어 요약 중간에서 중국어로 넘어갔다.
그것을 정상 content로 세지 않기 위한 계층이다.

**LLM을 부르지 않는다. 문장을 고치지 않는다. 사람이 고르지 않는다.**
입력은 요약 문자열 하나이고, 판정은 결정적이다.

```
PASS      정상
SUSPECT   diagnostic 있음 · 자동 제외 아님
FAIL      presentation eligibility 제외
```

상수는 결과를 보기 전에 freeze했다 —
`docs/finalization/V2_1_OUTPUT_QUALITY_ADDENDUM_2026-09-08.md`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

QUALITY_POLICY_VERSION = "output_quality_v1"

PASS = "PASS"
SUSPECT = "SUSPECT"
FAIL = "FAIL"

#: 판정 순서이기도 하다 — 뒤가 세다.
QUALITY_STATUSES = (PASS, SUSPECT, FAIL)

REASON_LANGUAGE_DRIFT = "OUTPUT_LANGUAGE_DRIFT"
REASON_LANGUAGE_CONTRACT = "OUTPUT_LANGUAGE_CONTRACT_FAILURE"
REASON_BROKEN_MIXED_SCRIPT = "OUTPUT_BROKEN_MIXED_SCRIPT"
REASON_EXCESSIVE_REPETITION = "OUTPUT_EXCESSIVE_REPETITION"

#: FAIL 사유 — 이 둘만 자동 제외다. Q2 · Q3는 diagnostic이다.
BLOCKING_REASONS = (REASON_LANGUAGE_DRIFT, REASON_LANGUAGE_CONTRACT)

#: **freeze된 값.** 결과를 보고 조정하지 않는다(addendum §1).
FOREIGN_SCRIPT_RUN_MIN = 8

_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_LATIN = re.compile(r"[A-Za-z]")
#: 한국어 계약에서 이질 script로 세는 문자 — 한자 · 가나.
_FOREIGN = re.compile(r"[㐀-䶿一-鿿豈-﫿"
                      r"぀-ヿ]")
#: run을 **잇기만** 하는 문자(CJK 구두점 · 전각). 길이에는 세지 않는다 —
#: 문장부호로 끊어서 규칙을 피해 가는 것을 막되, 부호만으로 drift가 되지는 않게.
_JOINER = re.compile(r"[　-〿＀-･\s]")


class OutputQualityError(RuntimeError):
    """품질 판정 계약 위반."""


@dataclass(frozen=True, slots=True)
class ReportOutputQuality:
    text: str | None
    status: str
    reasons: tuple[str, ...]
    diagnostics: dict = field(default_factory=dict)


def longest_foreign_run(text: str) -> int:
    """연속 이질 script run의 길이. 사이의 CJK 구두점은 run을 끊지 않는다."""
    best = current = 0
    for char in text:
        if _FOREIGN.match(char):
            current += 1
            best = max(best, current)
        elif _JOINER.match(char) and current:
            continue                      # 잇기만 한다 — 길이에 세지 않는다
        else:
            current = 0
    return best


def _mixed_tokens(text: str) -> tuple[str, ...]:
    """Hangul 뒤에 Latin이 붙은 토큰 — `카레우don` 형태.

    방향을 본다. `AI가` · `MBTI는`처럼 Latin 뒤에 조사가 붙는 것은 정상이므로
    Hangul → Latin 전이만 잡는다.
    """
    broken = []
    for token in text.split():
        seen_hangul = False
        for char in token:
            if _HANGUL.match(char):
                seen_hangul = True
            elif _LATIN.match(char) and seen_hangul:
                broken.append(token)
                break
    return tuple(broken)


def _adjacent_repeat(text: str) -> str | None:
    """바로 이어서 반복된 토큰 또는 2-gram. 횟수 임계값을 쓰지 않는다."""
    tokens = [token.strip(".,!?·「」\"'()") for token in text.split()]
    tokens = [token for token in tokens if len(token) >= 2]
    for index in range(len(tokens) - 1):
        if tokens[index] == tokens[index + 1]:
            return tokens[index]
    for index in range(len(tokens) - 3):
        if tokens[index:index + 2] == tokens[index + 2:index + 4]:
            return " ".join(tokens[index:index + 2])
    return None


def evaluate_summary(text) -> ReportOutputQuality:
    """요약 하나를 판정한다. 문장을 바꾸지 않는다."""
    if text is None or not str(text).strip():
        return ReportOutputQuality(
            text=text, status=FAIL, reasons=(REASON_LANGUAGE_CONTRACT,),
            diagnostics={"policy": QUALITY_POLICY_VERSION, "empty": True})

    body = str(text)
    reasons = []
    run = longest_foreign_run(body)
    hangul = len(_HANGUL.findall(body))
    mixed = _mixed_tokens(body)
    repeat = _adjacent_repeat(body)

    if run >= FOREIGN_SCRIPT_RUN_MIN:
        reasons.append(REASON_LANGUAGE_DRIFT)
    if not hangul:
        reasons.append(REASON_LANGUAGE_CONTRACT)
    if mixed:
        reasons.append(REASON_BROKEN_MIXED_SCRIPT)
    if repeat is not None:
        reasons.append(REASON_EXCESSIVE_REPETITION)

    if any(reason in BLOCKING_REASONS for reason in reasons):
        status = FAIL
    elif reasons:
        status = SUSPECT
    else:
        status = PASS

    return ReportOutputQuality(
        text=body, status=status, reasons=tuple(sorted(reasons)),
        diagnostics={
            "policy": QUALITY_POLICY_VERSION,
            "longest_foreign_run": run,
            "foreign_run_min": FOREIGN_SCRIPT_RUN_MIN,
            "hangul_chars": hangul,
            "mixed_tokens": mixed,
            "adjacent_repeat": repeat,
        })


def blocks_presentation(verdict: ReportOutputQuality) -> bool:
    """FAIL만 표현에서 뺀다. SUSPECT는 diagnostic이다(addendum §2)."""
    if verdict.status not in QUALITY_STATUSES:
        raise OutputQualityError("unknown quality status %r" % verdict.status)
    return verdict.status == FAIL
