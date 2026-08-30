"""v2.1 grounding validator — 사실을 판정으로 바꾼다 (Gate B · B-06).

```
B-05   이 cite가 무엇을 가리키는가        사실
B-06   이 claim을 통과시킬 수 있는가      판정
```

강한 근거를 요구하는 대상은 **dialogue claim 하나**다(SPEC §15). 실패해도
summary는 남고 구조는 그대로다.

```
grounding FAIL
  → canonical episode 구조 유지
  → summary 유지
  → dialogue만 제거
  → grounding_status는 FAIL로 보존 · PASS처럼 숨기지 않는다
```

**short-circuit하지 않는다.** 결정 가능한 위반을 전부 기록한 뒤 상태 하나를 고른다.
첫 실패에서 멈추면 회귀 분석에서 나머지 결함이 보이지 않는다.

`GRD-004`(unsupported concrete event)는 P1이다. 의미 함의는 문자열·참조·자격으로
결정되지 않는다. 여기서 규칙으로 흉내내지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PASS = "PASS"
NOT_APPLICABLE = "NOT_APPLICABLE"
FAIL_REFERENCE = "FAIL_REFERENCE"
FAIL_OUTSIDE_EPISODE = "FAIL_OUTSIDE_EPISODE"
FAIL_INELIGIBLE_SUPPORT = "FAIL_INELIGIBLE_SUPPORT"
FAIL_NO_SUPPORT = "FAIL_NO_SUPPORT"
FAIL_UNSUPPORTED = "FAIL_UNSUPPORTED"

GROUNDING_STATUSES = (
    PASS,
    NOT_APPLICABLE,
    FAIL_REFERENCE,
    FAIL_OUTSIDE_EPISODE,
    FAIL_INELIGIBLE_SUPPORT,
    FAIL_NO_SUPPORT,
    FAIL_UNSUPPORTED,
)

#: 상태 하나를 고를 때의 순서. 구조 문제가 자격 문제보다 앞선다.
_PRECEDENCE = (
    FAIL_NO_SUPPORT,
    FAIL_REFERENCE,
    FAIL_OUTSIDE_EPISODE,
    FAIL_INELIGIBLE_SUPPORT,
    FAIL_UNSUPPORTED,
)

#: 문자열로 결정 가능한 앵커만 본다. 한국어 고유명사 일반은 여기서 판정하지
#: 않는다 — 그것이 GRD-004가 P1인 이유다.
ANCHOR_KINDS = ("digits", "quoted", "latin")

_DIGITS = re.compile(r"\d+")
_QUOTED = re.compile(r"[\"'“”‘’「」『』]([^\"'“”‘’「」『』]{1,40})[\"'“”‘’「」『』]")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9._-]{1,}")


@dataclass(frozen=True, slots=True)
class Reason:
    code: str
    detail: str
    cite: object = None
    status: str = ""


@dataclass(frozen=True, slots=True)
class GroundingResult:
    episode_id: str
    status: str
    reasons: tuple[Reason, ...]
    dialogue_retained: bool


@dataclass(frozen=True, slots=True)
class GroundedEpisode:
    """판정을 붙인 구간. 구조와 summary는 그대로 남는다."""

    episode_id: str
    content_status: str
    summary: str | None
    dialogue_note: str | None
    support_span: dict
    anchor_cites: tuple
    source: str
    provenance: tuple
    grounding_status: str
    grounding_reasons: tuple[Reason, ...]


def anchors_in(text: str) -> set[str]:
    """결정 가능한 앵커 문자열만 뽑는다."""
    found = set(_DIGITS.findall(text or ""))
    found |= {m.strip() for m in _QUOTED.findall(text or "")}
    found |= set(_LATIN.findall(text or ""))
    return {a for a in found if a}


def _cited_text(binding, store) -> str:
    parts = []
    for cite in binding.cites:
        if cite.segment_id is None or cite.source_type is None:
            continue
        parts.append(store.load(cite.source_type, cite.segment_id).read_text())
    return "\n".join(parts)


def validate_grounding(binding, store) -> GroundingResult:
    """dialogue claim을 판정한다. 위반은 전부 모은 뒤 상태를 고른다."""
    if not binding.dialogue_note:
        return GroundingResult(binding.episode_id, NOT_APPLICABLE, (), True)

    reasons: list[Reason] = []
    if not binding.cites:
        reasons.append(
            Reason("no_support_ref", "dialogue claim has no cite",
                   status=FAIL_NO_SUPPORT)
        )

    eligible = sum(
        1 for c in binding.cites
        if c.resolution_status == "RESOLVED" and c.inside_episode
        and c.usable_for_claims
    )
    for cite in binding.cites:
        label = cite.original_cite
        if cite.resolution_status == "UNREADABLE":
            reasons.append(Reason("unreadable_cite", "not a segment reference",
                                  label, FAIL_REFERENCE))
            continue
        if cite.resolution_status == "UNKNOWN_SEGMENT":
            reasons.append(Reason("unknown_segment", "no such segment: %s" % label,
                                  label, FAIL_REFERENCE))
            continue
        if cite.sanitation_status is None:
            reasons.append(Reason("no_evidence_at_segment",
                                  "segment exists but carries no speech evidence",
                                  label, FAIL_REFERENCE))
            continue
        if not cite.inside_episode:
            reasons.append(Reason("outside_episode",
                                  "cite lies outside the episode span",
                                  label, FAIL_OUTSIDE_EPISODE))
            continue
        if not cite.usable_for_claims:
            # 자격 없는 인용은 **eligible이 하나도 없을 때만** 실패 사유다.
            # VALID이 따로 있으면 claim은 그 VALID으로 서고, 이 인용은 진단으로만
            # 남는다. 반대로 SUSPECT를 VALID 옆에 붙였다고 자동 통과시키지도
            # 않는다 — 통과 조건은 eligible >= 1이지 인용 개수가 아니다(GRD-012).
            reasons.append(Reason(
                "ineligible_support",
                "evidence is %s and cannot support a claim" % cite.sanitation_status,
                label,
                FAIL_INELIGIBLE_SUPPORT if not eligible else "",
            ))

    if eligible:
        supported = anchors_in(_cited_text(binding, store))
        for anchor in sorted(anchors_in(binding.dialogue_note) - supported):
            reasons.append(Reason("unsupported_anchor",
                                  "%r does not appear in the cited evidence" % anchor,
                                  None, FAIL_UNSUPPORTED))

    status = PASS
    for candidate in _PRECEDENCE:
        if any(r.status == candidate for r in reasons):
            status = candidate
            break
    return GroundingResult(
        episode_id=binding.episode_id,
        status=status,
        reasons=tuple(reasons),
        dialogue_retained=status in (PASS, NOT_APPLICABLE),
    )


def apply_grounding(binding, result: GroundingResult) -> GroundedEpisode:
    """판정을 붙인다. 실패는 dialogue만 지우고 상태로 남긴다."""
    return GroundedEpisode(
        episode_id=binding.episode_id,
        content_status=binding.content_status,
        summary=binding.summary,
        dialogue_note=binding.dialogue_note if result.dialogue_retained else None,
        support_span=binding.support_span,
        anchor_cites=binding.anchor_cites,
        source=binding.source,
        provenance=binding.provenance,
        grounding_status=result.status,
        grounding_reasons=result.reasons,
    )
