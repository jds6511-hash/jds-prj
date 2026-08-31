"""v2.1 표현 계층 입구 — 정본 하나만 받는다 (Gate C · C-01).

```
aar_canonical (validated)  →  PresentationInput  →  highlight · synthesis · renderer
```

표현 계층이 정본을 **우회해** 앞 계층으로 손을 뻗으면 Gate B에서 막은 오염이
다시 살아난다(OPEN-11). 그래서 입구를 하나로 두고 두 층으로 잠근다.

```
층 1  import 차단   이 모듈 아래 표현 코드는 grounding 이전 모듈을 import하지 않는다
층 2  데이터 차단   FAIL · NOT_APPLICABLE인데 dialogue가 실린 문서를 거부한다
```

층 2가 따로 필요한 이유는 층 1이 **정직한 코드만 막기 때문**이다. 정본을 손으로
고치거나 앞 계층 버그로 dialogue가 남아 있으면 import 가드는 아무것도 못 한다.

이 모듈은 **판정하지 않는다.** grounding 상태를 그대로 옮기고, 정본이 이미 지운
것을 되살리려는 문서만 거절한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from v2_1_aar import validate_aar
from v2_1_grounding import PASS

#: 표현 계층이 import해서는 안 되는 grounding 이전 모듈.
FORBIDDEN_UPSTREAM = (
    "v2_1_content",
    "v2_1_binding",
    "v2_1_raw_store",
    "v2_1_parse",
    "v2_1_timeline",
)


class PresentationInputError(RuntimeError):
    """표현 계층 입력 계약 위반."""


@dataclass(frozen=True, slots=True)
class PresentationEpisode:
    """표현이 볼 수 있는 episode 전부. 앞 계층으로 되돌아갈 손잡이는 없다."""

    episode_id: str
    start_seg: int
    end_seg: int
    start_sec: float
    end_sec: float
    source: str
    content_status: str
    summary: str | None
    dialogue_note: str | None
    grounding_status: str
    anchor_cites: tuple[int, ...]
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PresentationInput:
    schema: str
    video_id: str
    run_id: str
    episodes: tuple[PresentationEpisode, ...]

    def episode(self, episode_id: str) -> PresentationEpisode:
        for episode in self.episodes:
            if episode.episode_id == episode_id:
                return episode
        raise KeyError(episode_id)


def _episode(raw: dict) -> PresentationEpisode:
    return PresentationEpisode(
        episode_id=raw["episode_id"],
        start_seg=raw["start_seg"],
        end_seg=raw["end_seg"],
        start_sec=raw["start_sec"],
        end_sec=raw["end_sec"],
        source=raw["source"],
        content_status=raw["content_status"],
        summary=raw["summary"],
        dialogue_note=raw["dialogue_note"],
        grounding_status=raw["grounding_status"],
        anchor_cites=tuple(raw["anchor_cites"]),
        provenance=tuple(raw["provenance"]),
    )


def presentation_input(document) -> PresentationInput:
    """검증된 정본 문서 하나를 표현 계층 입력으로 연다.

    정본이 아닌 것·검증에 실패한 것·grounding이 지운 dialogue를 다시 실은 것은
    전부 거절한다.
    """
    if not isinstance(document, dict):
        raise PresentationInputError(
            "presentation input must be an aar_canonical document, got %s"
            % type(document).__name__
        )
    # schema 검사는 여기서 다시 하지 않는다 — `validate_aar`가 그 계약의 주인이고,
    # 같은 규칙을 두 곳에 두면 갈라진다.
    verdict = validate_aar(document)
    if not verdict.ok:
        raise PresentationInputError(
            "canonical document is invalid: %s" % "; ".join(verdict.failures)
        )

    for raw in document["episodes"]:
        if raw["grounding_status"] != PASS and raw["dialogue_note"] is not None:
            raise PresentationInputError(
                "%s: dialogue removed by grounding (%s) is present again"
                % (raw["episode_id"], raw["grounding_status"])
            )

    return PresentationInput(
        schema=document["schema"],
        video_id=document["video_id"],
        run_id=document["run_id"],
        episodes=tuple(_episode(raw) for raw in document["episodes"]),
    )
