"""v2.1 Episode 구조 + content 스키마 (Gate B · B-01).

```
모델이 내는 것    summary · (선택) dialogue_note · stt_cites
코드가 정하는 것  episode_id · start_seg · end_seg · start_sec · end_sec
                 support_span · anchor_cites · source
```

SPEC §13·§14를 그대로 옮긴다. **필수 필드가 늘어나는 만큼 문서 전체가 죽을 확률이
는다** — v1·v3·v4·softyeon에서 실제로 그랬다. 그래서 모델에게 요구하는 것은
`summary` 하나다.

`support_span`·`anchor_cites`·`source`는 pipeline-generated field다. 모델이
자기 근거를 자기가 정하면 검증할 것이 남지 않는다.

이 모듈은 LLM을 부르지 않는다. 구조는 모델과 무관하게 선다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from v2_1_segments import CanonicalSegment

#: anchor 개수 상한. 인용을 늘린다고 근거가 강해지지 않는다.
MAX_ANCHORS = 3

#: 모델이 낼 수 있는 것 전부. 이 밖은 받지 않는다.
MODEL_FIELDS = ("summary", "dialogue_note", "stt_cites")

#: 코드가 정하는 것. 모델 출력으로 덮을 수 없다.
DERIVED_FIELDS = (
    "episode_id",
    "start_seg",
    "end_seg",
    "start_sec",
    "end_sec",
    "support_span",
    "anchor_cites",
    "source",
)


class EpisodeError(RuntimeError):
    """Episode 구조 계약 위반."""


@dataclass(frozen=True, slots=True)
class EpisodeContent:
    """모델이 낸 내용. `summary` 하나만 필수다."""

    summary: str
    dialogue_note: str | None = None
    stt_cites: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.summary).strip():
            raise EpisodeError("summary is required")


@dataclass(frozen=True, slots=True)
class Episode:
    """canonical episode 하나. 생성 시점에는 내용이 비어 있다."""

    episode_id: str
    start_seg: int
    end_seg: int
    start_sec: float
    end_sec: float
    support_span: dict
    anchor_cites: list[int]
    source: str
    content: EpisodeContent | None = None


def anchors(start_seg: int, end_seg: int) -> list[int]:
    """span의 시작·중간·끝. 짧으면 전부 든다.

    m8_hier가 쓰던 규칙과 같지만 그 모듈을 import하지 않는다 — v2.1이 legacy
    파이프라인에 의존을 만들지 않기 위해서다.
    """
    if end_seg < start_seg:
        raise EpisodeError("bad support span: %d..%d" % (start_seg, end_seg))
    if end_seg - start_seg + 1 <= MAX_ANCHORS:
        return list(range(start_seg, end_seg + 1))
    return sorted({start_seg, (start_seg + end_seg) // 2, end_seg})


def derive_source(start_seg: int, end_seg: int, timeline=None) -> str:
    """span 안에 **근거로 쓸 수 있는** 발화가 있으면 stt, 아니면 visual.

    보존된 발화가 아니라 `usable_for_claims`가 참인 것만 센다. SUSPECT가 남아
    있다는 이유로 source가 stt가 되면 A-05의 판정이 무의미해진다.
    """
    if timeline is None:
        return "visual"
    for entry in timeline:
        if start_seg <= entry.segment_id <= end_seg:
            if any(ref.usable_for_claims for ref in entry.asr_refs):
                return "stt"
    return "visual"


def build_episodes(
    spans: Sequence[tuple[int, int]],
    segments: Sequence[CanonicalSegment],
    timeline=None,
) -> list[Episode]:
    """canonical partition에서 Episode 구조를 만든다. 모델 출력은 받지 않는다."""
    known = {s.segment_id: s for s in segments}
    episodes = []
    for number, (start_seg, end_seg) in enumerate(spans, start=1):
        missing = [x for x in (start_seg, end_seg) if x not in known]
        if missing:
            raise EpisodeError("unknown segment: %r" % missing)
        episodes.append(
            Episode(
                episode_id="EP%02d" % number,
                start_seg=start_seg,
                end_seg=end_seg,
                start_sec=known[start_seg].start_sec,
                end_sec=known[end_seg].end_sec,
                support_span={"start_seg": start_seg, "end_seg": end_seg},
                anchor_cites=anchors(start_seg, end_seg),
                source=derive_source(start_seg, end_seg, timeline),
            )
        )
    return episodes
