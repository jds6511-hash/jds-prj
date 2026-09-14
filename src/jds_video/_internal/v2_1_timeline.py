"""v2.1 evidence timeline — 근거를 canonical 시간축에 올린다 (A-06).

```
segment_id · start_sec · end_sec · asr_refs[] · caption_refs[] · ocr_refs[]
```

두 가지를 하지 않는다.

```
텍스트 복제      원문은 raw store에 있다. 여기에는 참조만 둔다
eligibility 재계산  A-05가 정한 status·usable_for_claims를 그대로 옮긴다
```

두 벌의 정책이 생기면 언젠가 갈라지고, 그때 어느 쪽이 맞는지 알 수 없다.

`llm`은 raw store의 source type이지만 **evidence modality가 아니다.** 모델 출력이
근거인 척 섞이면 "무엇이 사건을 뒷받침하는가"가 무너진다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from v2_1_raw_store import EVIDENCE_MODALITIES
from v2_1_segments import CanonicalSegment

#: ref를 만들 수 있는 상태. 참조할 원문이 실제로 있는 경우만이다.
_REFERABLE = ("VALID", "SUSPECT", "REJECTED")

_FIELD = {"asr": "asr_refs", "vlm": "caption_refs", "ocr": "ocr_refs"}


class TimelineError(RuntimeError):
    """timeline 계약 위반."""


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """근거 하나에 대한 참조. 원문 텍스트는 담지 않는다."""

    ref_id: str
    source_type: str
    segment_id: int
    status: str
    preserved: bool
    usable_for_claims: bool
    at_sec: float | None = None


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    segment_id: int
    start_sec: float
    end_sec: float
    asr_refs: list[EvidenceRef] = field(default_factory=list)
    caption_refs: list[EvidenceRef] = field(default_factory=list)
    ocr_refs: list[EvidenceRef] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    failures: list[Failure] = field(default_factory=list)


def refs_for(entry: TimelineEntry) -> list[EvidenceRef]:
    return [*entry.asr_refs, *entry.caption_refs, *entry.ocr_refs]


def build_timeline(
    segments: Sequence[CanonicalSegment],
    judged: Mapping[str, Mapping[int, object]],
    timestamps: Mapping[tuple[str, int], float] | None = None,
) -> list[TimelineEntry]:
    """판정된 근거를 segment 시간축에 붙인다.

    `judged`는 `{source_type: {segment_id: Judgement}}`다. 없는 modality는 실패가
    아니라 빈 참조 목록이 된다.
    """
    unknown = [k for k in judged if k not in EVIDENCE_MODALITIES]
    if unknown:
        raise TimelineError(
            "not an evidence modality: %s (allowed: %s)"
            % (", ".join(sorted(unknown)), ", ".join(EVIDENCE_MODALITIES))
        )

    known = {s.segment_id: s for s in segments}
    for source_type, channel in judged.items():
        stray = sorted(set(channel) - set(known))
        if stray:
            raise TimelineError(
                "unknown segment in %s evidence: %r" % (source_type, stray)
            )

    at = dict(timestamps or {})
    entries: list[TimelineEntry] = []
    for segment in segments:
        buckets: dict[str, list[EvidenceRef]] = {name: [] for name in _FIELD.values()}
        for source_type in EVIDENCE_MODALITIES:
            judgement = judged.get(source_type, {}).get(segment.segment_id)
            if judgement is None or judgement.status not in _REFERABLE:
                continue
            at_sec = at.get((source_type, segment.segment_id))
            if at_sec is not None and not (
                segment.start_sec <= at_sec < segment.end_sec
            ):
                raise TimelineError(
                    "timestamp %.3f is outside seg#%d [%.3f, %.3f)"
                    % (at_sec, segment.segment_id, segment.start_sec, segment.end_sec)
                )
            buckets[_FIELD[source_type]].append(
                EvidenceRef(
                    ref_id="%s:%06d" % (source_type, segment.segment_id),
                    source_type=source_type,
                    segment_id=segment.segment_id,
                    status=judgement.status,
                    preserved=judgement.preserved,
                    usable_for_claims=judgement.usable_for_claims,
                    at_sec=at_sec,
                )
            )
        entries.append(
            TimelineEntry(
                segment_id=segment.segment_id,
                start_sec=segment.start_sec,
                end_sec=segment.end_sec,
                **buckets,
            )
        )
    return entries


def validate_timeline(
    timeline: Sequence[TimelineEntry],
    segments: Sequence[CanonicalSegment],
    store,
) -> ValidationResult:
    """모든 참조가 실재 artifact로 풀리고 시간축이 segment와 맞는지 본다."""
    failures: list[Failure] = []
    known = {s.segment_id: s for s in segments}

    for entry in timeline:
        segment = known.get(entry.segment_id)
        if segment is None:
            failures.append(
                Failure("UNKNOWN_SEGMENT", "no such segment: %d" % entry.segment_id)
            )
            continue
        if (entry.start_sec, entry.end_sec) != (segment.start_sec, segment.end_sec):
            failures.append(
                Failure("TIME_MISMATCH", "seg#%d times do not match" % entry.segment_id)
            )
        for ref in refs_for(entry):
            try:
                record = store.load(ref.source_type, ref.segment_id)
                record.read_bytes()
            except Exception as exc:
                failures.append(
                    Failure("UNRESOLVED_REF", "%s: %s" % (ref.ref_id, exc))
                )
    return ValidationResult(not failures, failures)
