"""v2.1 parse contract layer — 표기는 받아들이고 존재는 지어내지 않는다 (A-04).

```
RAW → NORMALIZE → PARSE → RESOLVE → (의미 판정은 A-05 이후)
```

두 가지를 엄격히 가른다.

```
표기(notation)   55 · "55" · "seg#55" · 맨 배열   → 받아들인다
계약(contract)   실재하지 않는 참조 · 깨진 구조    → 실패로 분류한다
```

2026-08-29에 이 구분을 놓쳐 사고가 셋 났다. 앞의 둘(맨 배열 · `"seg#55"`)은 표기를
계약으로 착각해 멀쩡한 출력을 버린 것이고, 셋째는 깨진 JSON을 문장 경로로 흘려보내
raw JSON이 요약 필드에 실린 것이다. **구조 fallback은 여기서 금지한다.**

내용의 진위·오염은 판단하지 않는다. 그것은 A-05 소관이고, parse 계층이 미리
걸러 버리면 근거 자체가 사라진다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from v2_1_segments import CanonicalSegment

MODEL_FAILURE = "MODEL_FAILURE"
PARSE_CONTRACT_FAILURE = "PARSE_CONTRACT_FAILURE"
EMPTY = "EMPTY"
VALID_PARSE = "VALID_PARSE"

#: parse 계층이 낼 수 있는 status 전부. 닫힌 집합이다.
PARSE_STATUSES = (MODEL_FAILURE, PARSE_CONTRACT_FAILURE, EMPTY, VALID_PARSE)

#: A-03 raw store의 store-level 결과를 이 계층 어휘로 잇는다.
_STORE_STATUS = {"PARSE_OK": VALID_PARSE, "PARSE_FAILED": PARSE_CONTRACT_FAILURE}

_REF = re.compile(r"\s*(?:seg\s*#?\s*)?(\d+)\s*\Z", re.IGNORECASE)

#: 출력 전체가 코드펜스 하나로 감싸인 경우. 2026-08-31 B-02b에서
#: Qwen2.5-7B-Instruct가 세 호출 전부 이 형태로 답했다. **표기이지 계약이 아니다** —
#: 펜스를 거절하면 완전한 JSON을 결함으로 버리게 된다(seg#55 · 맨 배열과 같은 부류).
#: 펜스 밖에 설명문이 붙은 것은 받지 않는다. 어디까지가 출력인지 알 수 없기 때문이다.
_FENCED = re.compile(r"\A\s*```[A-Za-z0-9_-]*\s*\n(?P<body>.*?)\n?\s*```\s*\Z", re.S)


@dataclass(frozen=True, slots=True)
class ParseResult:
    """parse 한 건의 결과. 실패를 성공처럼 표현하지 않는다."""

    status: str
    value: Any = None
    reason: str | None = None
    references: Mapping[str, list[int]] = field(default_factory=dict)
    unresolved: list[int] = field(default_factory=list)
    error: str | None = None
    error_type: str | None = None


def normalize_segment_ref(value: Any) -> int | None:
    """표기 정규화만 한다. **없는 segment를 만들어내지 않는다.**

    `55` · `"55"` · `" seg#55 "` · `"SEG # 55"` · `"seg55"`는 모두 같은 표기다.
    실수·음수·빈 문자열·`True`는 참조가 아니다.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        m = _REF.fullmatch(value)
        return int(m.group(1)) if m else None
    return None


class SegmentRegistry:
    """canonical segment(A-01)의 존재 여부만 답한다. clamp도 최근접도 없다."""

    def __init__(self, segments: Iterable[CanonicalSegment]) -> None:
        self._ids = frozenset(s.segment_id for s in segments)

    def __contains__(self, segment_id: object) -> bool:
        return segment_id in self._ids

    def resolve(self, value: Any) -> int:
        """표기를 정규화하고 실재를 확인한다. 없으면 `KeyError`."""
        n = normalize_segment_ref(value)
        if n is None:
            raise KeyError("not a segment reference: %r" % (value,))
        if n not in self._ids:
            raise KeyError("segment does not exist: %d" % n)
        return n


def model_failure(exc: BaseException) -> ParseResult:
    """producer 호출 자체가 실패했을 때 **호출자가** 만든다.

    parse 계층은 payload 내용을 보고 이 상태를 추론하지 않는다 — 빈 출력은
    `EMPTY`이지 호출 실패가 아니다.
    """
    return ParseResult(
        status=MODEL_FAILURE, error=str(exc), error_type=type(exc).__name__
    )


def status_for_store_outcome(outcome) -> str:
    """A-03 store 결과를 이 계층 어휘로 옮긴다. 두 어휘가 갈라지지 않게 한다."""
    try:
        return _STORE_STATUS[outcome.status]
    except KeyError:
        raise ValueError("unknown store status: %r" % (outcome.status,)) from None


def _fail(reason: str, unresolved: Sequence[int] = ()) -> ParseResult:
    return ParseResult(
        status=PARSE_CONTRACT_FAILURE, reason=reason, unresolved=list(unresolved)
    )


def _is_blank(raw: Any) -> bool:
    return raw is None or not str(raw).strip()


def _unfence(raw: str) -> str:
    """출력 전체를 감싼 코드펜스만 벗긴다. 안의 내용은 건드리지 않는다."""
    match = _FENCED.match(raw)
    return match.group("body") if match else raw


def _has_content(obj: Mapping[str, Any]) -> bool:
    for value in obj.values():
        if isinstance(value, str):
            if value.strip():
                return True
        elif isinstance(value, (list, tuple, dict, set)):
            if len(value):
                return True
        elif value is not None:
            return True
    return False


def _resolve_all(values: Sequence[Any], registry: SegmentRegistry):
    """(정규화된 값, 실재하지 않는 값, 표기조차 아닌 값)."""
    resolved, missing, invalid = set(), set(), []
    for value in values:
        n = normalize_segment_ref(value)
        if n is None:
            invalid.append(value)
        elif n in registry:
            resolved.add(n)
        else:
            missing.add(n)
    return sorted(resolved), sorted(missing), invalid


def parse_json_payload(
    raw: str | None,
    registry: SegmentRegistry,
    *,
    reference_keys: Sequence[str] = (),
) -> ParseResult:
    """JSON 객체 하나를 읽고, 선언된 키의 segment 참조를 해석한다.

    깨진 JSON을 문장으로 건져 올리는 경로는 **없다**. 구조가 깨졌으면 실패다.
    """
    if _is_blank(raw):
        return ParseResult(status=EMPTY, reason="blank_output")
    try:
        obj = json.loads(_unfence(raw))
    except (json.JSONDecodeError, ValueError):
        return _fail("not_json_object")
    if not isinstance(obj, dict):
        return _fail("not_json_object")
    if not _has_content(obj):
        return ParseResult(status=EMPTY, reason="no_content")

    references: dict[str, list[int]] = {}
    for key in reference_keys:
        if key not in obj:
            continue
        values = obj[key]
        if not isinstance(values, (list, tuple)):
            return _fail("not_a_list")
        resolved, missing, invalid = _resolve_all(values, registry)
        if invalid:
            return _fail("invalid_reference")
        if missing:
            return _fail("unresolved_reference", missing)
        references[key] = resolved

    return ParseResult(status=VALID_PARSE, value=obj, references=references)


def parse_reference_list(
    raw: str | None, key: str, registry: SegmentRegistry
) -> ParseResult:
    """segment 참조 목록 하나를 읽는다. `{"key": [...]}`와 맨 배열을 둘 다 받는다.

    맨 배열은 표기 차이다 — 2026-08-29 canary에서 이것을 거절해 경계가 0개가 됐고
    영상 전체가 사건 하나가 됐다. 빈 목록은 성공이 아니라 `EMPTY`다.
    """
    if _is_blank(raw):
        return ParseResult(status=EMPTY, reason="blank_output")
    try:
        obj = json.loads(_unfence(raw))
    except (json.JSONDecodeError, ValueError):
        return _fail("not_json_object")

    if isinstance(obj, dict):
        if key not in obj:
            return _fail("missing_key")
        values = obj[key]
    elif isinstance(obj, list):
        values = obj
    else:
        return _fail("not_json_object")
    if not isinstance(values, (list, tuple)):
        return _fail("not_a_list")

    resolved, missing, invalid = _resolve_all(values, registry)
    if invalid:
        return _fail("invalid_reference")
    if missing:
        return _fail("unresolved_reference", missing)
    if not resolved:
        return ParseResult(status=EMPTY, reason="no_references")
    return ParseResult(status=VALID_PARSE, value=resolved)
