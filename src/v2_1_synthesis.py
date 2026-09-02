"""v2.1 Global Synthesis — 검증된 것만 결정적으로 조합한다 (Gate C · C-04).

```
새 사실을 만들지 않는다.
canonical에 남은 summary를 시간순으로 재배열·구조화할 뿐이다.
```

**LLM을 부르지 않는다.** 여기서 생성을 다시 열면 Gate B에서 만든 grounding 경계를
표현 단계에서 되돌리게 된다. 사람이 읽기에 너무 기계적이라는 문제가 뒤에 생기면
그때 **별도 티켓·별도 prompt contract·별도 containment contract**로 세운다.

dialogue는 **아예 입력으로 쓰지 않는다.** 그러면 grounding이 제거한 dialogue가
종합에 섞일 경로 자체가 없다(GLS-006 · OPEN-11).

자동 완전 검증을 주장하지 않는다(GLS-004). 한계는 지우지 않고 항상 함께 싣는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from v2_1_presentation_input import (
    PresentationInput,
    summary_eligible_for_presentation,
)

SUFFICIENT = "SUFFICIENT"
LIMITED = "LIMITED"
NO_RELIABLE_CONTENT = "NO_RELIABLE_CONTENT"

SYNTHESIS_STATUSES = (SUFFICIENT, LIMITED, NO_RELIABLE_CONTENT)

#: 종합문에 함께 싣는 한계. 지우면 GLS-004 위반이다.
LIMITATION = "semantic entailment not automatically verified"

#: 자동 완전 검증을 주장하는 표현. 만들지도 않고, 들어오면 보고한다.
ASSURANCE_PHRASES = (
    "fully grounded",
    "fully verified",
    "entailment verified",
    "fact checked",
    "완전 검증",
    "전부 검증",
)

_NO_CONTENT_CONCLUSION = "근거가 확인된 구간이 없어 결론을 적지 않는다."


class SynthesisError(RuntimeError):
    """종합 입력 계약 위반."""


@dataclass(frozen=True, slots=True)
class GlobalSynthesis:
    overview: str
    analysis: tuple[str, ...]
    conclusion: str
    source_episode_ids: tuple[str, ...]
    excluded_episode_ids: tuple[str, ...]
    synthesis_status: str
    limitation: str


def _usable(episode) -> bool:
    """종합에 쓸 수 있는 episode인가 — 표현 자격은 C-01이 소유한다(OPEN-12).

    여기서 조건식을 다시 쓰지 않는다. 예전에는 "FAIL이 아니면 통과"였는데, 그러면
    새 상태가 생겼을 때 자동으로 통과해 버린다. dialogue는 자격과 무관하게 어느
    쪽에서도 쓰지 않는다.
    """
    return summary_eligible_for_presentation(episode)


def build_synthesis(presented, lineage) -> GlobalSynthesis:
    """정본에 남은 summary를 시간순으로 조합한다. 해석을 덧붙이지 않는다."""
    if not isinstance(presented, PresentationInput):
        raise SynthesisError(
            "synthesis is built from a PresentationInput, got %s"
            % type(presented).__name__
        )

    ordered = sorted(presented.episodes, key=lambda e: e.start_seg)
    usable = [episode for episode in ordered if _usable(episode)]
    excluded = [episode.episode_id for episode in ordered if not _usable(episode)]
    by_id = {episode.episode_id: episode for episode in usable}

    if not usable:
        return GlobalSynthesis(
            overview="", analysis=(), conclusion=_NO_CONTENT_CONCLUSION,
            source_episode_ids=(), excluded_episode_ids=tuple(excluded),
            synthesis_status=NO_RELIABLE_CONTENT, limitation=LIMITATION,
        )

    analysis = []
    for record in lineage:
        kept = [by_id[ref] for ref in record.source_episode_ids if ref in by_id]
        if not kept:
            continue
        analysis.append("%s (%s): %s" % (
            record.highlight_id,
            " · ".join(episode.episode_id for episode in kept),
            " / ".join(episode.summary for episode in kept),
        ))

    return GlobalSynthesis(
        overview=" ".join(episode.summary for episode in usable),
        analysis=tuple(analysis),
        conclusion="확인된 구간 %d개를 시간순으로 정리하면 처음은 «%s», 마지막은 «%s»다."
                   % (len(usable), usable[0].summary, usable[-1].summary),
        source_episode_ids=tuple(episode.episode_id for episode in usable),
        excluded_episode_ids=tuple(excluded),
        synthesis_status=SUFFICIENT if not excluded else LIMITED,
        limitation=LIMITATION,
    )


def validate_synthesis(synthesis: GlobalSynthesis, presented) -> list[str]:
    """종합문이 정본과 여전히 맞는지 본다. 첫 실패에서 멈추지 않는다."""
    failures = []
    known = {episode.episode_id: episode for episode in presented.episodes}

    for episode_id in synthesis.source_episode_ids:
        episode = known.get(episode_id)
        if episode is None:
            failures.append("unknown source episode: %s" % episode_id)
        elif not _usable(episode):
            failures.append(
                "%s is not eligible as a synthesis source (%s)"
                % (episode_id, episode.grounding_status)
            )

    if synthesis.limitation != LIMITATION:
        failures.append("limitation must be stated verbatim")

    blob = " ".join([synthesis.overview, synthesis.conclusion,
                     *synthesis.analysis, synthesis.limitation]).lower()
    for phrase in ASSURANCE_PHRASES:
        if phrase.lower() in blob:
            failures.append("assurance wording is not permitted: %s" % phrase)

    if synthesis.synthesis_status not in SYNTHESIS_STATUSES:
        failures.append("unknown status: %r" % synthesis.synthesis_status)

    if not synthesis.source_episode_ids:
        if synthesis.overview or synthesis.analysis:
            failures.append("synthesis text without any source episode")
        if synthesis.conclusion != _NO_CONTENT_CONCLUSION:
            failures.append("concrete conclusion without any source episode")

    return failures
