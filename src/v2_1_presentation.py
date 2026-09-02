"""v2.1 Presentation schema — 표현 객체를 확정한다 (Gate C · C-05).

```
canonical episode  →  Highlight(C-02)  →  lineage(C-03)  →  PresentationHighlight
```

**새 사건 서술을 만들지 않는다.** `summary`는 canonical episode summary의 결정적
조합이고, 그 이상은 아니다. 관계어(`이후 · 때문에 · 따라서 · 함께 · 이를 통해`)를
끼워 넣지 않는다 — 원문에 없던 관계 주장이 되기 때문이다.

두 lineage를 **가른다.**

```
source_episode_ids           이 highlight가 무엇으로 구성됐는가
summary_source_episode_ids   그중 무엇이 문장에 실제로 쓰였는가
excluded_summary_episode_ids 쓰이지 않은 것 — 지우지 않고 남긴다
```

섞으면 실패한 구간이 문장에 들어왔는지를 사후에 가릴 수 없다.

형식 참조는 **형식일 뿐**이다(REF-001 · 002 · 005 · 006). 절 구성만 가져오고,
문장 · 시간 · 사건 수는 가져오지 않는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from v2_1_lineage import LineageError, build_lineage
from v2_1_presentation_input import PresentationInput

PRESENTATION_SCHEMA = "presentation_highlights_v2_1"

SUMMARY_AVAILABLE = "AVAILABLE"
SUMMARY_NO_RELIABLE_CONTENT = "NO_RELIABLE_CONTENT"

SUMMARY_STATUSES = (SUMMARY_AVAILABLE, SUMMARY_NO_RELIABLE_CONTENT)

#: summary 조합에 쓰는 구분자. 문장을 잇는 접속이 아니라 나열 표시다.
SUMMARY_SEPARATOR = " / "

#: 사람이 쓴 형식 참조의 신분. 내용의 근거가 아니라 formatting provenance다.
FORMAT_REFERENCE = {
    "author": "user",
    "role": "format_reference",
    "is_ground_truth": False,
    "document": "docs/finalization/REPORT_FORMAT_REFERENCE_2026-08-30.md",
}

#: 형식 참조에서 가져오는 것은 절 구성뿐이다.
SECTION_NAMES = ("개요", "주요 사건 및 내용", "핵심 내용 분석", "결론",
                 "근거 및 생성 정보")


class PresentationError(RuntimeError):
    """표현 객체 계약 위반."""


@dataclass(frozen=True, slots=True)
class PresentationHighlight:
    highlight_id: str
    label: str | None
    start_sec: float
    end_sec: float
    source_episode_ids: tuple[str, ...]
    segment_refs: tuple[int, ...]
    summary: str | None
    summary_status: str
    summary_source_episode_ids: tuple[str, ...]
    excluded_summary_episode_ids: tuple[str, ...]


def _eligible_for_summary(episode) -> bool:
    """문장에 쓸 수 있는 episode인가.

    grounding을 통과한 것만 쓴다 — 표현 계층은 자격을 다시 판정하지 않는다.
    """
    return (
        episode.content_status == "VALID_PARSE"
        and episode.grounding_status == "PASS"
        and bool(episode.summary and episode.summary.strip())
    )


def build_presentation(presented, highlights) -> tuple[PresentationHighlight, ...]:
    """Highlight를 최종 표현 객체로 확정한다. 문장을 만들지 않는다."""
    if not isinstance(presented, PresentationInput):
        raise PresentationError(
            "presentation is built from a PresentationInput, got %s"
            % type(presented).__name__
        )
    try:
        lineage = build_lineage(presented, highlights)
    except LineageError as exc:
        raise PresentationError(str(exc)) from None

    records = []
    for highlight, record in zip(highlights, lineage):
        members = [presented.episode(ref) for ref in record.source_episode_ids]
        # canonical 시간순으로 세운다 — 묶은 순서가 문장 순서를 바꾸면 안 된다.
        usable = sorted(
            (e for e in members if _eligible_for_summary(e)),
            key=lambda e: e.start_seg,
        )
        excluded = [e.episode_id for e in members if not _eligible_for_summary(e)]
        records.append(PresentationHighlight(
            highlight_id=record.highlight_id,
            label=highlight.label,
            start_sec=record.display_range["start_sec"],
            end_sec=record.display_range["end_sec"],
            source_episode_ids=record.source_episode_ids,
            segment_refs=tuple(highlight.segment_refs),
            summary=(SUMMARY_SEPARATOR.join(e.summary for e in usable)
                     if usable else None),
            summary_status=(SUMMARY_AVAILABLE if usable
                            else SUMMARY_NO_RELIABLE_CONTENT),
            summary_source_episode_ids=tuple(e.episode_id for e in usable),
            excluded_summary_episode_ids=tuple(excluded),
        ))
    return tuple(records)


def validate_presentation(records, presented, format_reference=None) -> list[str]:
    """표현 객체가 정본과 맞는지 본다. 첫 실패에서 멈추지 않는다."""
    failures = []
    reference = FORMAT_REFERENCE if format_reference is None else format_reference
    if reference.get("is_ground_truth") is not False:
        failures.append("format reference must not be marked as ground truth")
    if reference.get("author") != "user":
        failures.append("format reference author must be recorded")

    known = {episode.episode_id: episode for episode in presented.episodes}
    for record in records:
        label = record.highlight_id
        if record.summary_status not in SUMMARY_STATUSES:
            failures.append("%s: unknown summary status %r"
                            % (label, record.summary_status))

        missing = [ref for ref in record.source_episode_ids if ref not in known]
        if missing:
            failures.append("%s: unknown source episode %r" % (label, missing))

        if set(record.summary_source_episode_ids) | set(
                record.excluded_summary_episode_ids) != set(
                record.source_episode_ids):
            failures.append("%s: summary lineage does not cover its sources" % label)

        for ref in record.summary_source_episode_ids:
            episode = known.get(ref)
            if episode is not None and not _eligible_for_summary(episode):
                failures.append(
                    "%s: %s is not eligible for the summary (%s)"
                    % (label, ref, episode.grounding_status)
                )

        if record.summary is None:
            if record.summary_status != SUMMARY_NO_RELIABLE_CONTENT:
                failures.append("%s: missing summary must be stated as %s"
                                % (label, SUMMARY_NO_RELIABLE_CONTENT))
            continue

        if not record.summary_source_episode_ids:
            failures.append("%s: summary without any source episode" % label)
            continue

        # 조합이 아닌 문장은 새 서술이다. 정확히 재구성되는지로 판단한다.
        expected = SUMMARY_SEPARATOR.join(
            known[ref].summary for ref in record.summary_source_episode_ids
            if ref in known
        )
        if record.summary != expected:
            failures.append(
                "%s: summary is not a composition of its source summaries" % label
            )
    return failures


def serialize_presentation(records) -> str:
    payload = {
        "schema": PRESENTATION_SCHEMA,
        "format_reference": dict(FORMAT_REFERENCE),
        "sections": list(SECTION_NAMES),
        "highlights": [
            {
                "highlight_id": record.highlight_id,
                "label": record.label,
                "start_sec": record.start_sec,
                "end_sec": record.end_sec,
                "source_episode_ids": list(record.source_episode_ids),
                "segment_refs": list(record.segment_refs),
                "summary": record.summary,
                "summary_status": record.summary_status,
                "summary_source_episode_ids":
                    list(record.summary_source_episode_ids),
                "excluded_summary_episode_ids":
                    list(record.excluded_summary_episode_ids),
            }
            for record in records
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
