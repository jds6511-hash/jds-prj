"""v2.1 support/provenance 바인딩 (Gate B · B-05).

```
B-05   이 cite가 실제로 무엇을 가리키는가
B-06   그 결과로 이 claim을 통과시킬 수 있는가
```

invariant 하나만 지킨다.

> **조회 사실은 모두 보존하고, 판정은 하나도 하지 않는다.**

자격 없는 참조를 여기서 지우면 다음 계층이 "인용이 없었다"와 "SUSPECT를 실제로
인용했다"를 구분하지 못한다. 그 둘이 섞이면 `FAIL_INELIGIBLE_SUPPORT`가 다시
참조 실패와 한 덩어리가 된다 — OPEN-9가 막으려던 지점이다.

`support_span`과 provenance는 모델이 보낸 값이 아니라 **구조와 조회 결과에서
코드가 파생**한다(LLM-004 · LLM-005).
"""
from __future__ import annotations

from dataclasses import dataclass

from v2_1_parse import normalize_segment_ref

#: 표기가 읽혔고 그 구간이 실재한다.
RESOLVED = "RESOLVED"
#: 표기는 읽혔지만 그런 구간이 없다.
UNKNOWN_SEGMENT = "UNKNOWN_SEGMENT"
#: 표기 자체가 구간 참조가 아니다.
UNREADABLE = "UNREADABLE"

RESOLUTION_STATUSES = (RESOLVED, UNKNOWN_SEGMENT, UNREADABLE)

#: 발화 인용이 가리키는 채널. 인용은 발화에 대한 것이다(SPEC §15).
_CITE_CHANNEL = "asr"


@dataclass(frozen=True, slots=True)
class CiteBinding:
    """인용 하나가 실제로 무엇을 가리키는지. 통과 여부는 담지 않는다."""

    original_cite: object
    canonical_ref: int | None
    resolution_status: str
    segment_id: int | None
    inside_episode: bool | None
    sanitation_status: str | None
    usable_for_claims: bool | None
    source_type: str | None


@dataclass(frozen=True, slots=True)
class EvidenceBinding:
    """구간 안에 실제로 있던 근거 하나. 자격과 무관하게 전부 적는다."""

    ref_id: str
    segment_id: int
    source_type: str
    sanitation_status: str
    usable_for_claims: bool


@dataclass(frozen=True, slots=True)
class ContentBinding:
    episode_id: str
    content_status: str
    summary: str | None
    dialogue_note: str | None
    support_span: dict
    anchor_cites: tuple[int, ...]
    source: str
    cites: tuple[CiteBinding, ...]
    evidence: tuple[EvidenceBinding, ...]
    provenance: tuple[str, ...]


def _refs_in_span(episode, timeline):
    for entry in timeline:
        if episode.start_seg <= entry.segment_id <= episode.end_seg:
            for ref in [*entry.asr_refs, *entry.caption_refs, *entry.ocr_refs]:
                yield ref


def _bind_one(value, episode, registry, speech) -> CiteBinding:
    canonical = normalize_segment_ref(value)
    if canonical is None:
        return CiteBinding(value, None, UNREADABLE, None, None, None, None, None)
    if canonical not in registry:
        return CiteBinding(value, canonical, UNKNOWN_SEGMENT,
                           None, None, None, None, None)
    ref = speech.get(canonical)
    return CiteBinding(
        original_cite=value,
        canonical_ref=canonical,
        resolution_status=RESOLVED,
        segment_id=canonical,
        inside_episode=episode.start_seg <= canonical <= episode.end_seg,
        sanitation_status=ref.status if ref else None,
        usable_for_claims=ref.usable_for_claims if ref else None,
        source_type=ref.source_type if ref else None,
    )


def bind_cites(result, timeline, registry) -> ContentBinding:
    """구조·내용·근거를 묶어 **사실만** 적는다.

    인용은 영상 전체에서 조회한다 — 구간 밖을 가리켰다는 사실도 기록해야 하기
    때문이다. 구간 안이었는지는 `inside_episode`에 따로 적는다.
    """
    episode = result.episode
    speech = {
        ref.segment_id: ref
        for entry in timeline
        for ref in entry.asr_refs
        if ref.source_type == _CITE_CHANNEL
    }
    evidence = tuple(
        EvidenceBinding(
            ref_id=ref.ref_id,
            segment_id=ref.segment_id,
            source_type=ref.source_type,
            sanitation_status=ref.status,
            usable_for_claims=ref.usable_for_claims,
        )
        for ref in _refs_in_span(episode, timeline)
    )
    content = result.content
    cites = tuple(
        _bind_one(value, episode, registry, speech)
        for value in (content.stt_cites if content else ())
    )
    return ContentBinding(
        episode_id=episode.episode_id,
        content_status=result.content_status,
        summary=content.summary if content else None,
        dialogue_note=content.dialogue_note if content else None,
        support_span=dict(episode.support_span),
        anchor_cites=tuple(episode.anchor_cites),
        source=episode.source,
        cites=cites,
        evidence=evidence,
        provenance=tuple(item.ref_id for item in evidence),
    )
