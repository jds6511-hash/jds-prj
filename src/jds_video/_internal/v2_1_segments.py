from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Iterable, Mapping


class SegmentContractError(ValueError):
    """Raised when a legacy or canonical segment violates the v2.1 contract."""


@dataclass(frozen=True, slots=True)
class CanonicalSegment:
    """v2.1 canonical segment representation.

    Legacy fields (idx/start/end) must not escape the ingest adapter.
    """

    segment_id: int
    start_sec: float
    end_sec: float
    duration_sec: float

    def __post_init__(self) -> None:
        if isinstance(self.segment_id, bool) or not isinstance(self.segment_id, int):
            raise SegmentContractError("segment_id must be an int")
        if self.segment_id < 0:
            raise SegmentContractError("segment_id must be >= 0")

        for name, value in (
            ("start_sec", self.start_sec),
            ("end_sec", self.end_sec),
            ("duration_sec", self.duration_sec),
        ):
            if isinstance(value, bool) or not isinstance(value, Real):
                raise SegmentContractError(f"{name} must be numeric")

        start = float(self.start_sec)
        end = float(self.end_sec)
        duration = float(self.duration_sec)
        if start < 0:
            raise SegmentContractError("start_sec must be >= 0")
        if end <= start:
            raise SegmentContractError("end_sec must be > start_sec")
        expected = end - start
        if abs(duration - expected) > 1e-9:
            raise SegmentContractError(
                "duration_sec must equal end_sec - start_sec"
            )

    def as_dict(self) -> dict[str, int | float]:
        return {
            "segment_id": self.segment_id,
            "start_sec": float(self.start_sec),
            "end_sec": float(self.end_sec),
            "duration_sec": float(self.duration_sec),
        }


_REQUIRED_LEGACY_KEYS = frozenset({"idx", "start", "end"})
_FORBIDDEN_CANONICAL_KEYS_AT_INGEST = frozenset(
    {"segment_id", "start_sec", "end_sec", "duration_sec"}
)


def _require_numeric(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise SegmentContractError(f"legacy {field} must be numeric")
    return float(value)


def legacy_segment_to_canonical(segment: Mapping[str, Any]) -> CanonicalSegment:
    """Single ingest-boundary adapter: idx/start/end -> v2.1 canonical schema.

    The adapter intentionally rejects mixed legacy/canonical field sets so the two
    schemas cannot silently coexist downstream.
    """

    missing = _REQUIRED_LEGACY_KEYS - segment.keys()
    if missing:
        raise SegmentContractError(
            f"legacy segment missing required fields: {sorted(missing)}"
        )

    mixed = _FORBIDDEN_CANONICAL_KEYS_AT_INGEST & segment.keys()
    if mixed:
        raise SegmentContractError(
            f"legacy/canonical schema mixing is forbidden: {sorted(mixed)}"
        )

    idx = segment["idx"]
    if isinstance(idx, bool) or not isinstance(idx, int):
        raise SegmentContractError("legacy idx must be an int")
    if idx < 0:
        raise SegmentContractError("legacy idx must be >= 0")

    start = _require_numeric(segment["start"], field="start")
    end = _require_numeric(segment["end"], field="end")
    if start < 0:
        raise SegmentContractError("legacy start must be >= 0")
    if end <= start:
        raise SegmentContractError("legacy end must be > start")

    return CanonicalSegment(
        segment_id=idx,
        start_sec=start,
        end_sec=end,
        duration_sec=end - start,
    )


def legacy_segments_to_canonical(
    segments: Iterable[Mapping[str, Any]],
) -> list[CanonicalSegment]:
    """Adapt a sequence of legacy segments at the v2.1 ingest boundary."""

    canonical = [legacy_segment_to_canonical(segment) for segment in segments]
    ids = [segment.segment_id for segment in canonical]
    if len(ids) != len(set(ids)):
        raise SegmentContractError("segment_id values must be unique")
    return canonical
