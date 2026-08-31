"""v2.1 Highlight Builder core — 정본을 묶기만 한다 (Gate C · C-02).

```
Canonical Episode   overlap 0 · gap 0 · exactly once · 시간순     기계의 구조
Highlight           중첩 허용 · 같은 episode 다중 참여 · 개수 자유  사람의 구조
```

**두 구조는 규칙이 다르다.** 그래서 이 모듈은 A-09 partition 검증기를 부르지
않는다 — highlight의 중첩을 canonical 기준으로 재면 설계가 무너진다(SPEC §2).

입력은 `PresentationInput` 하나뿐이다. C-01이 pre-grounding 접근과 제거된
dialogue 재등장을 이미 막았으므로, 그 타입만 받으면 안전성이 그대로 상속된다.

**행 수를 목표로 삼지 않는다.** 형식 참조의 9행은 format reference이지 target
count가 아니다(SPEC §3 · REF-005). 개수는 입력 구성을 따라간다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from v2_1_presentation_input import PresentationInput


class HighlightError(RuntimeError):
    """highlight 조합 계약 위반."""


@dataclass(frozen=True, slots=True)
class HighlightSpec:
    """무엇을 묶을지에 대한 입력. label은 넣어 준 문자열을 그대로 쓴다."""

    episode_refs: tuple[str, ...]
    label: str | None = None


@dataclass(frozen=True, slots=True)
class Highlight:
    """표현 구조. 정본이 아니므로 실패해도 정본은 유효하다."""

    highlight_id: str
    label: str | None
    episode_refs: tuple[str, ...]
    segment_refs: tuple[int, ...]
    display_range: dict = field(default_factory=dict)


def _members(presented: PresentationInput, spec: HighlightSpec):
    if not spec.episode_refs:
        raise HighlightError("highlight must reference at least one episode")
    seen = set()
    members = []
    for episode_id in spec.episode_refs:
        if episode_id in seen:
            raise HighlightError(
                "%s appears twice in one highlight" % episode_id
            )
        seen.add(episode_id)
        try:
            members.append(presented.episode(episode_id))
        except KeyError:
            raise HighlightError(
                "episode does not exist: %s" % episode_id
            ) from None
    return members


def build_highlights(presented, specs) -> tuple[Highlight, ...]:
    """정본 episode들을 사건 묶음으로 조합한다. 정본은 읽기만 한다."""
    if not isinstance(presented, PresentationInput):
        raise HighlightError(
            "highlights are built from a PresentationInput, got %s"
            % type(presented).__name__
        )

    highlights = []
    for index, spec in enumerate(specs, start=1):
        members = _members(presented, spec)
        segments = sorted(
            segment_id
            for member in members
            for segment_id in range(member.start_seg, member.end_seg + 1)
        )
        highlights.append(Highlight(
            highlight_id="H%02d" % index,
            label=spec.label,
            episode_refs=tuple(spec.episode_refs),
            segment_refs=tuple(segments),
            display_range={
                "start_sec": min(member.start_sec for member in members),
                "end_sec": max(member.end_sec for member in members),
            },
        ))
    return tuple(highlights)
