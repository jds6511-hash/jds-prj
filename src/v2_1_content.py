"""v2.1 content 병합 + 실패 격리 (Gate B · B-04).

셋을 분리한다.

```
episode structure   canonical episode 자체 — 언제나 유지
content state       MODEL_FAILURE · PARSE_CONTRACT_FAILURE · EMPTY · VALID_PARSE
content payload     summary (+ 선택 dialogue_note · stt_cites)
```

모델이 죽어도 `episode_id` · 시간 · segment 소속 · 순서는 그대로 남는다. SPEC §16이
말하는 것이 이것이다 — **구조 자체가 깨졌을 때만** 문서를 거부한다.

반대 방향도 막는다. 실패를 `summary=""`나 "생성 실패" 같은 문구로 메우면 downstream이
정상 내용으로 읽는다. 실패는 상태로 남고 내용은 비어 있다.

근거 자격·named entity 검증은 여기서 하지 않는다. B-05·B-06 소관이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from v2_1_episode import DERIVED_FIELDS, EpisodeContent
from v2_1_parse import (
    PARSE_CONTRACT_FAILURE,
    PARSE_STATUSES,
    VALID_PARSE,
    normalize_segment_ref,
)

#: A-04와 같은 어휘를 쓴다. 두 벌을 만들지 않는다.
CONTENT_STATUSES = PARSE_STATUSES


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    """구조 하나 + 그 구조에 붙은 내용의 상태."""

    episode: object
    content_status: str
    content: EpisodeContent | None
    reason: str | None = None
    error: str | None = None
    error_type: str | None = None
    ignored_fields: tuple[str, ...] = ()


def _cites(values) -> tuple[int, ...]:
    """표기를 정규화하고 읽히지 않는 것은 버린다. 없는 것을 만들지 않는다."""
    if not isinstance(values, (list, tuple)):
        return ()
    found = {n for n in (normalize_segment_ref(v) for v in values) if n is not None}
    return tuple(sorted(found))


def merge_content(episode, outcome) -> EpisodeResult:
    """parse 결과를 구조에 붙인다. 실패해도 구조는 그대로 돌려준다."""
    if outcome.status != VALID_PARSE:
        return EpisodeResult(
            episode=episode,
            content_status=outcome.status,
            content=None,
            reason=outcome.reason,
            error=outcome.error,
            error_type=outcome.error_type,
        )

    payload = outcome.value or {}
    summary = str(payload.get("summary", "")).strip()
    if not summary:
        return EpisodeResult(
            episode=episode,
            content_status=PARSE_CONTRACT_FAILURE,
            content=None,
            reason="missing_summary",
        )

    note = str(payload.get("dialogue_note", "")).strip() or None
    ignored = tuple(sorted(set(DERIVED_FIELDS) & set(payload)))
    return EpisodeResult(
        episode=episode,
        content_status=VALID_PARSE,
        content=EpisodeContent(
            summary=payload["summary"],
            dialogue_note=note,
            stt_cites=_cites(payload.get("stt_cites")),
        ),
        ignored_fields=ignored,
    )


def merge_all(episodes: Sequence, outcomes: Sequence) -> list[EpisodeResult]:
    """구간 수와 결과 수는 같아야 한다. 짝이 어긋나면 조용히 맞추지 않는다."""
    if len(episodes) != len(outcomes):
        raise ValueError(
            "one outcome per episode required: %d episodes, %d outcomes"
            % (len(episodes), len(outcomes))
        )
    return [merge_content(e, o) for e, o in zip(episodes, outcomes)]
