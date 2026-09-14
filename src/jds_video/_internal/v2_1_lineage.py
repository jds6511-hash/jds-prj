"""v2.1 Highlight lineage — 표현이 바뀌어도 출처는 흔들리지 않는다 (Gate C · C-03).

```
HLT-001   모든 highlight는 실재하는 canonical episode에서 온다
RPT-002   highlight를 바꿔도 canonical episode identity는 그대로다
```

**문장을 만들지 않는다.** summary · dialogue · claim은 여기 없고, 이 모듈이 만드는
것은 "어디서 왔는가" 하나다. SPEC §4의 `Highlight.summary`는 표현 스키마 소관이며
(C-05), lineage 소유가 아니다 — schema ownership과 content-generation ownership을
가른다.

lineage는 **grouping 입력에서 파생한다.** label이나 display_range에서 역추론하면
표현을 손볼 때마다 provenance가 따라 움직인다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from v2_1_presentation_input import PresentationInput

LINEAGE_SCHEMA = "highlight_lineage_v2_1"


class LineageError(RuntimeError):
    """lineage 계약 위반."""


@dataclass(frozen=True, slots=True)
class SourceEpisode:
    """출처 episode의 canonical identity. 내용은 담지 않는다."""

    episode_id: str
    start_seg: int
    end_seg: int
    start_sec: float
    end_sec: float


@dataclass(frozen=True, slots=True)
class HighlightLineage:
    highlight_id: str
    source_episode_ids: tuple[str, ...]
    sources: tuple[SourceEpisode, ...]
    canonical_span: dict
    display_range: dict


def _source(presented: PresentationInput, episode_id) -> SourceEpisode:
    try:
        episode = presented.episode(episode_id)
    except (KeyError, TypeError):
        raise LineageError(
            "not a canonical episode: %r" % (episode_id,)
        ) from None
    return SourceEpisode(
        episode_id=episode.episode_id,
        start_seg=episode.start_seg,
        end_seg=episode.end_seg,
        start_sec=episode.start_sec,
        end_sec=episode.end_sec,
    )


def build_lineage(presented, highlights) -> tuple[HighlightLineage, ...]:
    """highlight마다 출처를 고정한다. 순서는 grouping 순서 그대로다."""
    if not isinstance(presented, PresentationInput):
        raise LineageError(
            "lineage is derived against a PresentationInput, got %s"
            % type(presented).__name__
        )

    records = []
    for highlight in highlights:
        if not highlight.episode_refs:
            raise LineageError(
                "%s has no source episode" % highlight.highlight_id
            )
        sources = tuple(_source(presented, ref) for ref in highlight.episode_refs)
        records.append(HighlightLineage(
            highlight_id=highlight.highlight_id,
            source_episode_ids=tuple(s.episode_id for s in sources),
            sources=sources,
            canonical_span={
                "start_seg": min(s.start_seg for s in sources),
                "end_seg": max(s.end_seg for s in sources),
            },
            display_range=dict(highlight.display_range),
        ))
    return tuple(records)


def validate_lineage(records, presented) -> list[str]:
    """lineage가 정본과 여전히 맞는지 본다. 첫 실패에서 멈추지 않는다."""
    failures = []
    for record in records:
        label = record.highlight_id
        if not record.source_episode_ids:
            failures.append("%s: no source episode" % label)
            continue
        for source in record.sources:
            try:
                episode = presented.episode(source.episode_id)
            except KeyError:
                failures.append("%s: unknown source %s" % (label, source.episode_id))
                continue
            if (source.start_seg, source.end_seg) != (episode.start_seg,
                                                      episode.end_seg):
                failures.append(
                    "%s: %s span drifted from canonical" % (label, source.episode_id)
                )
        expected = {"start_seg": min(s.start_seg for s in record.sources),
                    "end_seg": max(s.end_seg for s in record.sources)}
        if record.canonical_span != expected:
            failures.append("%s: canonical_span does not match its sources" % label)
    return failures


def serialize_lineage(records) -> str:
    payload = {
        "schema": LINEAGE_SCHEMA,
        "highlights": [
            {
                "highlight_id": record.highlight_id,
                "source_episode_ids": list(record.source_episode_ids),
                "sources": [
                    {"episode_id": s.episode_id, "start_seg": s.start_seg,
                     "end_seg": s.end_seg, "start_sec": s.start_sec,
                     "end_sec": s.end_sec}
                    for s in record.sources
                ],
                "canonical_span": record.canonical_span,
                "display_range": record.display_range,
            }
            for record in records
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def load_lineage(text: str) -> tuple[HighlightLineage, ...]:
    payload = json.loads(text)
    if payload.get("schema") != LINEAGE_SCHEMA:
        raise LineageError("not a lineage document: %r" % payload.get("schema"))
    return tuple(
        HighlightLineage(
            highlight_id=record["highlight_id"],
            source_episode_ids=tuple(record["source_episode_ids"]),
            sources=tuple(SourceEpisode(**source) for source in record["sources"]),
            canonical_span=record["canonical_span"],
            display_range=record["display_range"],
        )
        for record in payload["highlights"]
    )
