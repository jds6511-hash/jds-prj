"""v2.1 sanitation + claim eligibility — 보존과 승격을 가른다 (A-05).

```
상태            preserved   usable_for_claims
VALID              true          true
SUSPECT            true          false
REJECTED           true          false
EMPTY               -            false
PARSE_FAILED        -            false
```

원칙 셋.

```
삭제하지 않는다        의심스러운 근거도 원문 그대로 남긴다 (OPEN-7)
보존은 승격이 아니다    남아 있다는 것과 주장의 근거가 된다는 것은 다르다 (OPEN-9)
결정적 특징만 본다      모델에게 "이 발화가 진짜인가"를 묻지 않는다
```

반복은 **의심 근거일 뿐 삭제 근거가 아니다.** 2026-08-29 geoje dry-run에서 캡션용
반복 규칙을 STT에 적용해 실제 발화 11건이 사라졌다("나 잡았어!!! 나 잡았어!!!").
그래서 이 계층은 그 규칙을 쓰지 않는다.

세는 방식은 **완전일치**다. 유사도 매칭을 넣으면 서로 다른 실제 발화가 한 덩어리로
묶여 같은 사고가 다시 난다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import common

VALID = "VALID"
SUSPECT = "SUSPECT"
REJECTED = "REJECTED"
EMPTY = "EMPTY"
PARSE_FAILED = "PARSE_FAILED"

#: 이 계층이 낼 수 있는 상태 전부. 닫힌 집합이다.
STATUSES = (VALID, SUSPECT, REJECTED, EMPTY, PARSE_FAILED)

#: 영상 전체 완전일치 출현이 이 횟수 이상이면 SUSPECT. 근거는
#: `BCS_PROTOTYPE_SPEC_2026-08-29.md` §4(패널 18편 실측).
REPEAT_THRESHOLD = 8

#: 지시문 되뱉기. C0에서 관측된 최대 peak가 이것이었다(d=0.6798).
#: "알겠습니다"·"요청" 단독은 넣지 않는다 — 실제 발화라 오탐이 곧 발화 삭제다.
_ECHO = re.compile(
    r"다음은\s*주어진|주어진\s*요청에\s*따라|요청에\s*따라.{0,20}(묘사|설명)"
    r"|알겠습니다[.,]?\s*다음"
)

#: 화면 오버레이·채널 안내. BCS와 같은 규칙이지만 동결 모듈을 끌어오지 않고
#: 여기에 다시 선언한다 — 동결본에 대한 의존을 만들지 않기 위해서다.
_OVERLAY = re.compile(r"홈페이지|https?://|www\.|\.com|\.co\.kr|방송국")

#: 한국어 산출물에 섞인 한자·가나. 3자 이상이면 의심한다.
_FOREIGN = re.compile(r"[一-鿿぀-ヿ]")

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Judgement:
    """판정 하나. `text`는 **원문 그대로**다 — 정규화본을 저장하지 않는다."""

    text: str
    status: str
    reason: str | None
    preserved: bool
    usable_for_claims: bool


def normalize_for_counting(text: str | None) -> str:
    """세기 위한 정규화. **공백과 줄바꿈만** 건드린다.

    구두점·조사·표기 흔들림은 정규화하지 않는다. 그것까지 같게 보기 시작하면
    서로 다른 발화가 한 덩어리가 된다.
    """
    return _WHITESPACE.sub(" ", (text or "").strip())


def occurrence_counts(texts: Iterable[str | None]) -> dict[str, int]:
    """영상 전체의 완전일치 출현 횟수. 빈 문자열은 세지 않는다."""
    counts: dict[str, int] = {}
    for text in texts:
        key = normalize_for_counting(text)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _rejection_reason(text: str) -> str | None:
    """반복 횟수와 무관한 **독립 근거**만 본다."""
    if _ECHO.search(text):
        return "instruction_echo"
    if common.is_subtitle_credit(text):
        return "subtitle_credit"
    if _OVERLAY.search(text):
        return "overlay_or_url"
    return None


def classify(
    text: str | None,
    *,
    source_type: str,
    counts: Mapping[str, int] | None = None,
    parse_failed: bool = False,
) -> Judgement:
    """근거 하나를 판정한다. `counts`는 영상 전체의 완전일치 출현 횟수다."""
    raw = text or ""
    if parse_failed:
        return Judgement(raw, PARSE_FAILED, "parse_failed", False, False)

    stripped = raw.strip()
    if not stripped:
        return Judgement(raw, EMPTY, "blank", False, False)

    reason = _rejection_reason(stripped)
    if reason:
        return Judgement(raw, REJECTED, reason, True, False)

    if len(_FOREIGN.findall(stripped)) >= 3:
        return Judgement(raw, SUSPECT, "foreign_script", True, False)

    key = normalize_for_counting(raw)
    if (counts or {}).get(key, 0) >= REPEAT_THRESHOLD:
        return Judgement(raw, SUSPECT, "repeated", True, False)

    if source_type == "ocr":
        # 화면 문자는 그 자체로 사건을 입증하지 못한다. 상태는 VALID지만
        # 단독 근거로 승격하지 않는다 (SAN-007).
        return Judgement(raw, VALID, "ocr_unverified", True, False)

    return Judgement(raw, VALID, None, True, True)


def classify_channel(
    channel: Mapping[int, str], source_type: str
) -> dict[int, Judgement]:
    """채널 하나를 통째로 판정한다. 반복은 그 채널 안에서 센다."""
    counts = occurrence_counts(channel.values())
    return {
        segment_id: classify(text, source_type=source_type, counts=counts)
        for segment_id, text in channel.items()
    }


def eligible_support(judgements: Iterable[Judgement]) -> list[Judgement]:
    """주장의 근거로 쓸 수 있는 것만 남긴다.

    보존된 것 전부가 아니라 `usable_for_claims`가 참인 것만이다. 이 함수가
    주장의 성립 여부를 판정하지는 않는다 — 그것은 뒤 단계 책임이다.
    """
    return [j for j in judgements if j.usable_for_claims]
