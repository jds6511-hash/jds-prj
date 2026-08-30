"""v2.1 canonical partition validator — hard gate (A-09).

```
overlap 0 · gap 0 · 모든 segment가 정확히 한 번
partition의 양끝 = canonical_video_start · canonical_video_end (OPEN-2)
```

**빌더와 코드를 공유하지 않는다.** 창을 만드는 쪽과 검사하는 쪽이 같은 helper를
쓰면 그 helper의 버그에서 둘이 함께 통과한다. 여기서는 span에서 시간축을 다시
구성해 독립적으로 잰다.

실패하면 canonical artifact를 만들지 않는다 — 무효 partition을 정상처럼 흘려보내지
않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from v2_1_segments import CanonicalSegment


class PartitionInvalid(RuntimeError):
    """canonical partition 불변식 위반. hard gate이므로 진행을 멈춘다."""


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    failures: list[Failure] = field(default_factory=list)
    assigned_once: bool = False


def canonical_video_start(segments: Sequence[CanonicalSegment]) -> float:
    return segments[0].start_sec


def canonical_video_end(segments: Sequence[CanonicalSegment]) -> float:
    """OPEN-2 — 마지막 segment의 끝이다. 창 길이로 반올림하지 않는다."""
    return segments[-1].end_sec


def validate_partition(
    spans: Sequence[tuple[int, int]], segments: Sequence[CanonicalSegment]
) -> ValidationResult:
    """span 목록이 canonical partition인지 검사한다. 첫 실패에서 멈추지 않는다."""
    failures: list[Failure] = []
    if not spans:
        return ValidationResult(False, [Failure("EMPTY_PARTITION", "no spans")])

    known = {s.segment_id: s for s in segments}
    order = {s.segment_id: i for i, s in enumerate(segments)}

    for start, end in spans:
        missing = [x for x in (start, end) if x not in known]
        if missing:
            failures.append(Failure("UNKNOWN_SEGMENT", "no such segment: %r" % missing))
        elif order[end] < order[start]:
            failures.append(
                Failure("NON_POSITIVE_DURATION", "span ends before it starts: %d..%d"
                        % (start, end))
            )

    resolvable = [
        (s, e) for s, e in spans
        if s in known and e in known and order[e] >= order[s]
    ]
    if not resolvable:
        return ValidationResult(False, failures)

    seen: set[tuple[int, int]] = set()
    for span in resolvable:
        if span in seen:
            failures.append(Failure("DUPLICATE_SPAN", "span appears twice: %r" % (span,)))
        seen.add(span)

    for (_, previous_end), (next_start, _) in zip(resolvable, resolvable[1:]):
        if order[next_start] <= order[previous_end]:
            failures.append(
                Failure("NON_MONOTONIC", "span order is not increasing at %d"
                        % next_start)
            )

    counts = {segment_id: 0 for segment_id in known}
    for start, end in resolvable:
        for index in range(order[start], order[end] + 1):
            counts[segments[index].segment_id] += 1

    duplicated = sorted(i for i, n in counts.items() if n > 1)
    if duplicated:
        failures.append(Failure("OVERLAP", "segments assigned twice: %r" % duplicated))
    unassigned = sorted(i for i, n in counts.items() if n == 0)
    if unassigned:
        code = "GAP" if _is_interior_hole(unassigned, order, segments) \
            else "UNASSIGNED_SEGMENT"
        failures.append(Failure(code, "segments never assigned: %r" % unassigned))

    ordered = sorted(resolvable, key=lambda span: order[span[0]])
    for (_, previous_end), (next_start, _) in zip(ordered, ordered[1:]):
        if order[next_start] > order[previous_end] + 1:
            failures.append(
                Failure("DISCONTINUITY", "gap between seg#%d and seg#%d"
                        % (previous_end, next_start))
            )

    first, last = ordered[0][0], ordered[-1][1]
    if known[first].start_sec != canonical_video_start(segments):
        failures.append(
            Failure("START_MISMATCH", "partition starts at %.3f, video at %.3f"
                    % (known[first].start_sec, canonical_video_start(segments)))
        )
    if known[last].end_sec != canonical_video_end(segments):
        failures.append(
            Failure("END_MISMATCH", "partition ends at %.3f, video at %.3f"
                    % (known[last].end_sec, canonical_video_end(segments)))
        )

    assigned_once = set(counts.values()) == {1}
    return ValidationResult(not failures, failures, assigned_once)


def _is_interior_hole(unassigned, order, segments) -> bool:
    """빠진 segment가 앞뒤 배정된 것 사이에 있으면 gap, 끝에 몰려 있으면 미배정."""
    positions = sorted(order[i] for i in unassigned)
    return positions[0] > 0 and positions[-1] < len(segments) - 1


def assert_valid_partition(
    spans: Sequence[tuple[int, int]], segments: Sequence[CanonicalSegment]
) -> None:
    """hard gate. 위반이 있으면 여기서 멈춘다."""
    result = validate_partition(spans, segments)
    if not result.ok:
        raise PartitionInvalid(
            "; ".join("%s: %s" % (f.code, f.detail) for f in result.failures)
        )
