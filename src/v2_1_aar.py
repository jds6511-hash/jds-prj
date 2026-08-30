"""v2.1 `aar_canonical` — 정본 문서 (Gate B · B-07).

```
Canonical Episodes → Content → Grounding → aar_canonical.json   ← 여기까지가 정본
                                              ↓
                                    Presentation Highlights     중첩 허용
```

이 문서는 **표현 계층 없이 단독으로 유효**해야 한다. 표현이 무엇을 묶든 여기의
episode 목록은 바뀌지 않는다 — 그것이 AAR-005다.

직렬화기는 **재판정하지 않는다.** grounding 실패를 누락하거나 통과처럼 정규화하면
그 자체가 GRD-009 위반이다. 앞 계층이 정한 것을 그대로 옮긴다.

재실행 동일성은 **구조**에 대한 것이다. run id가 달라 파일 바이트가 달라지는 것은
위반이 아니다(AAR-006).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence

from v2_1_grounding import GROUNDING_STATUSES, PASS
from v2_1_parse import PARSE_STATUSES
from v2_1_partition import validate_partition

SCHEMA = "aar_canonical_v2_1"

#: 정본 episode에 들어와서는 안 되는 표현 계층 어휘.
_PRESENTATION_KEYS = (
    "highlight",
    "highlights",
    "highlight_group",
    "synthesis",
    "rendered",
    "display",
    "section",
)

_EPISODE_KEYS = (
    "episode_id", "start_seg", "end_seg", "start_sec", "end_sec",
    "support_span", "anchor_cites", "source", "content_status",
    "summary", "dialogue_note", "provenance",
    "grounding_status", "grounding_reasons",
)


class AarInvalid(RuntimeError):
    """정본 문서 계약 위반."""


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    failures: list[str] = field(default_factory=list)


def _quality_notes(timeline, grounded) -> dict:
    """결정적 집계만 적는다. 모델의 자기 신고는 넣지 않는다(SPEC §15)."""
    usable = excluded = 0
    ocr = False
    for entry in timeline or ():
        for ref in entry.asr_refs:
            if ref.usable_for_claims:
                usable += 1
            else:
                excluded += 1
        ocr = ocr or bool(entry.ocr_refs)
    rejected = sum(
        1 for episode in grounded
        if episode.grounding_status not in (PASS, "NOT_APPLICABLE")
    )
    return {
        "usable_stt_count": usable,
        "excluded_stt_count": excluded,
        "rejected_claims": rejected,
        "ocr_available": ocr,
    }


def build_aar_canonical(
    *,
    video_id: str,
    run_id: str,
    segments: Sequence,
    grounded: Sequence,
    timeline=None,
    boundary=None,
    prompt=None,
) -> dict:
    """정본 문서를 만든다. 앞 계층의 판정을 그대로 옮긴다."""
    document = {
        "schema": SCHEMA,
        "video_id": video_id,
        "run_id": run_id,
        "segment_count": len(segments),
        "episodes": [
            {
                "episode_id": episode.episode_id,
                "start_seg": episode.support_span["start_seg"],
                "end_seg": episode.support_span["end_seg"],
                "start_sec": _bounds(segments, episode)[0],
                "end_sec": _bounds(segments, episode)[1],
                "support_span": dict(episode.support_span),
                "anchor_cites": list(episode.anchor_cites),
                "source": episode.source,
                "content_status": episode.content_status,
                "summary": episode.summary,
                "dialogue_note": episode.dialogue_note,
                "provenance": list(episode.provenance),
                "grounding_status": episode.grounding_status,
                "grounding_reasons": [
                    {"code": reason.code, "detail": reason.detail,
                     "cite": reason.cite}
                    for reason in episode.grounding_reasons
                ],
            }
            for episode in grounded
        ],
        "quality_notes": _quality_notes(timeline, grounded),
    }
    if boundary is not None:
        document["boundary"] = {
            "provider_name": boundary.provider_name,
            "provider_version": boundary.provider_version,
            "provider_config": dict(boundary.provider_config),
        }
    if prompt is not None:
        document["prompt"] = {
            "prompt_version": prompt.prompt_version,
            "prompt_hash": prompt.prompt_hash,
        }
    return document


def _bounds(segments, episode):
    by_id = {s.segment_id: s for s in segments}
    return (by_id[episode.support_span["start_seg"]].start_sec,
            by_id[episode.support_span["end_seg"]].end_sec)


def structural_signature(document: dict):
    """시간 구조만 뽑는다. 내용·run id·판정은 들어가지 않는다."""
    return tuple(
        (e["episode_id"], e["start_seg"], e["end_seg"], e["start_sec"], e["end_sec"])
        for e in document.get("episodes", ())
    )


def validate_aar(document: dict) -> ValidationResult:
    """정본 문서가 단독으로 유효한지 본다. 첫 실패에서 멈추지 않는다."""
    failures: list[str] = []
    if document.get("schema") != SCHEMA:
        failures.append("schema: expected %s" % SCHEMA)

    episodes = document.get("episodes")
    if not episodes:
        return ValidationResult(False, failures + ["episodes: empty"])

    for key in _PRESENTATION_KEYS:
        if key in document:
            failures.append("presentation section does not belong here: %s" % key)

    for episode in episodes:
        label = episode.get("episode_id", "?")
        missing = [k for k in _EPISODE_KEYS if k not in episode]
        if missing:
            failures.append("%s: missing fields %r" % (label, missing))
        stray = [k for k in episode if k in _PRESENTATION_KEYS]
        if stray:
            failures.append("%s: presentation key inside canonical episode %r"
                            % (label, stray))
        if episode.get("grounding_status") not in GROUNDING_STATUSES:
            failures.append("%s: unknown grounding_status %r"
                            % (label, episode.get("grounding_status")))
        if episode.get("content_status") not in PARSE_STATUSES:
            failures.append("%s: unknown content_status %r"
                            % (label, episode.get("content_status")))

    spans = [(e["start_seg"], e["end_seg"]) for e in episodes
             if "start_seg" in e and "end_seg" in e]
    count = document.get("segment_count")
    if spans and isinstance(count, int):
        segments = [_Segment(i) for i in range(count)]
        partition = validate_partition(spans, segments)
        if not partition.ok:
            failures.append("partition: %s" % "; ".join(
                "%s(%s)" % (f.code, f.detail) for f in partition.failures))

    return ValidationResult(not failures, failures)


@dataclass(frozen=True, slots=True)
class _Segment:
    """partition 검증에 필요한 최소 형태. 시간은 1초 격자로 세운다."""

    segment_id: int

    @property
    def start_sec(self) -> float:
        return float(self.segment_id)

    @property
    def end_sec(self) -> float:
        return float(self.segment_id + 1)


def serialize_aar(document: dict) -> str:
    """결정적 직렬화. 판정을 건드리지 않는다."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_aar(text: str) -> dict:
    document = json.loads(text)
    if document.get("schema") != SCHEMA:
        raise AarInvalid("not an %s document: %r" % (SCHEMA, document.get("schema")))
    return document
