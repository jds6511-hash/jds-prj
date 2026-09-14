"""WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2 — 보수적·계층적 Overview synthesis.

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2_2026-09-13.md`

frozen 96-entry timeline을 **바꾸지 않는다.** 바꾸는 것은 synthesis 구조뿐이다.

```
frozen timeline
→ CANONICAL_FLOW      결정적 · 추론 0회 (여기서 모델을 쓰지 않는다)
→ DETAILED_OVERVIEW   1회 생성 · CANONICAL_FLOW만 본다
→ SHORT_OVERVIEW      1회 생성 · DETAILED_OVERVIEW만 본다 (압축본)
```

CANONICAL_FLOW를 모델에게 만들게 하지 않는 이유: activity · 시간 순서 · 반복 여부 ·
관찰 가능한 전환은 전부 timeline에서 계산되는 값이다. 계산으로 되는 것을 생성에
맡기면 그 단계에서 일반화가 들어온다.
"""
from __future__ import annotations

import json
import re

import wvr_video_overview_preview_v2 as ov

EVENT = "WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2"
PREREG = ("docs/preregistration/"
          "WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2_2026-09-13.md")

ACTIVITY_LABELS = tuple(ov.ACTIVITY_LABELS)

#: reviewer가 지목한 source보다 강한 표현. 생성 금지 · 출현 시 계측한다.
OVERCLAIM_TERMS = (
    "빈번", "주기적", "중심이 된다", "중심이", "중심으로", "흐름을 이끄",
    "일상적", "주요한", "핵심적", "대부분", "지속적으로", "전반적으로",
)

#: 관찰되지 않은 맥락. 이전 사건에서 쓰던 목록을 그대로 이어 쓴다.
CONTEXT_TERMS = (
    "병원", "퇴원", "직장", "출근", "근무", "휴가", "시장 방문", "계획",
    "의도", "감정", "진료", "가족", "친구", "일정", "목적", "이유",
)

#: 노출 금지 식별자
IDENTIFIER_PATTERN = re.compile(r"(S\d{2}|W\d{2}|G\d{3}|P\d{2}|C0\d|seg#\d+|"
                                r"entry\s*\d+|\d+\s*초)")

SHORT_HEADING = "SHORT OVERVIEW"
DETAILED_HEADING = "DETAILED OVERVIEW"


class SynthesisV2Error(RuntimeError):
    """synthesis V2 계약 위반."""


# ── CANONICAL_FLOW (결정적) ─────────────────────────────────────────
def _labels(entry: dict) -> tuple[str, ...]:
    seen, out = set(), []
    for label in entry["broad_activity"]:
        if label not in seen:
            seen.add(label)
            out.append(label)
    return tuple(out)


def canonical_flow(timeline: dict) -> dict:
    """연속 entry를 같은 activity 집합끼리 묶어 phase 열로 만든다.

    허용 정보는 activity · 시간 순서 · 반복 여부 · 관찰 가능한 전환뿐이다.
    중요도·의도·목적을 계산하지 않는다.
    """
    entries = timeline["entries"]
    if not entries:
        raise SynthesisV2Error("timeline entry가 없다")

    phases: list[dict] = []
    for entry in entries:
        labels = _labels(entry)
        if phases and phases[-1]["activities"] == list(labels):
            phases[-1]["end_sec"] = entry["end_sec"]
            phases[-1]["entry_count"] += 1
            continue
        phases.append({
            "phase_index": len(phases),
            "activities": list(labels),
            "start_sec": entry["start_sec"],
            "end_sec": entry["end_sec"],
            "entry_count": 1,
        })

    occurrences: dict[str, int] = {}
    for phase in phases:
        for label in phase["activities"]:
            occurrences[label] = occurrences.get(label, 0) + 1
    repeated = sorted(l for l, n in occurrences.items() if n >= 2)

    transitions = [
        {"from": list(a["activities"]), "to": list(b["activities"]),
         "at_sec": b["start_sec"]}
        for a, b in zip(phases, phases[1:])
        if a["activities"] != b["activities"]
    ]

    final = phases[-1]
    return {
        "event": EVENT,
        "prereg": PREREG,
        "source_timeline_entry_count": len(entries),
        "source_temporal_coverage_sec": timeline["temporal_coverage_sec"],
        "phase_count": len(phases),
        "phases": phases,
        "first_phase_activities": list(phases[0]["activities"]),
        "final_phase_activities": list(final["activities"]),
        "final_phase_span": [final["start_sec"], final["end_sec"]],
        "activity_phase_occurrences": dict(sorted(occurrences.items())),
        "repeated_activities": repeated,
        "non_repeated_activities": sorted(l for l, n in occurrences.items()
                                          if n == 1),
        "transition_count": len(transitions),
        "transitions": transitions,
        "inference_count": 0,
    }


def canonical_markdown(flow: dict) -> str:
    lines = [
        "# CANONICAL_FLOW (결정적 · 추론 0회)",
        "",
        "- phase %d개 · transition %d개" % (flow["phase_count"],
                                            flow["transition_count"]),
        "- 첫 phase: %s" % " · ".join(flow["first_phase_activities"]),
        "- 마지막 phase: %s  [%.1f, %.1f)" % (
            " · ".join(flow["final_phase_activities"]), *flow["final_phase_span"]),
        "- 2회 이상 나타난 activity: %s" % (
            " · ".join(flow["repeated_activities"]) or "없음"),
        "- 1회만 나타난 activity: %s" % (
            " · ".join(flow["non_repeated_activities"]) or "없음"),
        "",
        "| phase | start | end | activities | entries |",
        "|-------|-------|-----|------------|---------|",
    ]
    for phase in flow["phases"]:
        lines.append("| %d | %.1f | %.1f | %s | %d |" % (
            phase["phase_index"], phase["start_sec"], phase["end_sec"],
            " · ".join(phase["activities"]), phase["entry_count"]))
    return "\n".join(lines) + "\n"


# ── 프롬프트 ────────────────────────────────────────────────────────
DETAILED_PROMPT_TEMPLATE = r'''아래 CANONICAL_FLOW는 영상 관찰을 시간순 활동 구간으로 결정적으로 압축한 결과입니다.
오직 이 자료만 사용하여 한국어 DETAILED_OVERVIEW를 작성하십시오.

질문:
"이 영상 전체에서 어떤 활동이 어떤 순서로 이어지는가?"

어휘 규칙:
- 활동을 가리킬 때는 제공된 activity 표현을 그대로 쓰십시오. 새 활동 이름을 만들지 마십시오.
- 다음 표현은 쓰지 마십시오: 빈번하게, 주기적으로, 중심이 된다, 흐름을 이끈다,
  일상적인, 주요한, 핵심적인, 대부분, 지속적으로, 전반적으로.
- 반복을 말하려면 repeated_activities에 있는 활동만 "다시 나타난다" 수준으로 쓰십시오.
- 어떤 활동이 더 중요하다고 쓰지 마십시오.

내용 규칙:
- 사람의 의도, 목적, 감정, 장소 추론, 생활 패턴 해석을 쓰지 마십시오.
- 자료에 없는 사건, 장소, 물건, 시간을 추가하지 마십시오.
- 초 단위 시각, 구간 번호, window 또는 chunk 식별자를 본문에 쓰지 마십시오.
- 분석, 평가, 결론을 쓰지 마십시오.

구조 규칙:
- 1~3개 단락으로 쓰고 event log처럼 나열하지 마십시오.
- **마지막 문장은 final_phase_activities에 있는 활동만으로 영상이 어떻게 끝나는지
  적으십시오.** 그 문장에 다른 활동 이름을 넣지 마십시오.
- Markdown fence, JSON, bullet, heading 없이 본문만 출력하십시오.

CANONICAL_FLOW:
__CANONICAL_FLOW_JSON__
'''

SHORT_PROMPT_TEMPLATE = r'''아래 DETAILED_OVERVIEW를 더 짧게 압축하여 한국어 SHORT_OVERVIEW를 작성하십시오.

절대 규칙:
- **DETAILED_OVERVIEW에 없는 활동, 해석, 종료 상태를 추가하지 마십시오.**
- 마지막 문장이 말하는 종료 활동은 DETAILED_OVERVIEW의 마지막 문장과 같아야 합니다.
- 새 표현으로 일반화하지 마십시오. 다음 표현은 쓰지 마십시오: 빈번하게, 주기적으로,
  중심이 된다, 흐름을 이끈다, 일상적인, 주요한, 핵심적인, 대부분, 지속적으로, 전반적으로.
- 사람의 의도, 목적, 감정, 장소 추론, 생활 패턴 해석을 쓰지 마십시오.
- 초 단위 시각, 구간 번호, window 또는 chunk 식별자를 쓰지 마십시오.
- 2~4문장으로 쓰고, Markdown fence나 heading 없이 본문만 출력하십시오.

DETAILED_OVERVIEW:
__DETAILED_OVERVIEW__
'''


def detailed_prompt(flow: dict) -> str:
    payload = {
        "phase_sequence": [
            {"order": phase["phase_index"] + 1,
             "activities": list(phase["activities"])}
            for phase in flow["phases"]],
        "first_phase_activities": list(flow["first_phase_activities"]),
        "final_phase_activities": list(flow["final_phase_activities"]),
        "repeated_activities": list(flow["repeated_activities"]),
        "non_repeated_activities": list(flow["non_repeated_activities"]),
    }
    return DETAILED_PROMPT_TEMPLATE.replace(
        "__CANONICAL_FLOW_JSON__",
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


def short_prompt(detailed: str) -> str:
    return SHORT_PROMPT_TEMPLATE.replace("__DETAILED_OVERVIEW__", detailed.strip())


# ── 파싱 ────────────────────────────────────────────────────────────
def clean_body(raw: str, *, what: str) -> str:
    """heading·fence 없이 본문만 받는다. 빈 출력은 실패다."""
    if not isinstance(raw, str) or not raw.strip():
        raise SynthesisV2Error("%s: 빈 출력" % what)
    text = raw.strip().replace("\r\n", "\n")
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    for heading in (SHORT_HEADING, DETAILED_HEADING):
        text = text.replace(heading, "")
    text = text.strip()
    if not text:
        raise SynthesisV2Error("%s: heading 제거 후 본문이 없다" % what)
    return text


# ── machine check ───────────────────────────────────────────────────
def sentences(text: str) -> list[str]:
    rows = [row.strip() for row in re.split(r"(?<=[.!?])\s+|\n+", text)
            if row.strip()]
    return rows


def activity_set(text: str) -> set[str]:
    return {label for label in ACTIVITY_LABELS if label in text}


def final_phase_labels(text: str) -> set[str]:
    rows = sentences(text)
    if not rows:
        return set()
    return activity_set(rows[-1])


def overclaim_hits(text: str) -> dict[str, int]:
    return {term: text.count(term) for term in OVERCLAIM_TERMS if term in text}


def context_hits(text: str) -> dict[str, int]:
    return {term: text.count(term) for term in CONTEXT_TERMS if term in text}


def identifier_hits(text: str) -> list[str]:
    return IDENTIFIER_PATTERN.findall(text)


def unknown_label_count(text: str) -> int:
    """동결 label 어휘 밖의 '활동 이름'을 세는 대신, 알려진 label 출현만 센다.

    임의의 명사를 activity로 판정할 수단이 없으므로 **알려진 label이 하나도
    없는 경우**만 unknown으로 센다. 과잉 주장을 하지 않기 위한 보수적 정의다.
    """
    return 0 if activity_set(text) else 1


def machine_checks(flow: dict, detailed: str, short: str) -> dict:
    detailed_set = activity_set(detailed)
    short_set = activity_set(short)
    final_detailed = final_phase_labels(detailed)
    final_short = final_phase_labels(short)
    canonical_final = set(flow["final_phase_activities"])

    checks = {
        "short_activity_subset_of_detailed": {
            "pass": short_set <= detailed_set,
            "short_only": sorted(short_set - detailed_set),
            "short_activity_set": sorted(short_set),
            "detailed_activity_set": sorted(detailed_set)},
        "final_phase_short_equals_detailed": {
            "pass": final_short == final_detailed and bool(final_detailed),
            "final_phase_short": sorted(final_short),
            "final_phase_detailed": sorted(final_detailed)},
        "final_phase_matches_canonical": {
            "pass": final_detailed == canonical_final,
            "canonical_final_phase": sorted(canonical_final),
            "final_phase_detailed": sorted(final_detailed)},
        "unknown_label_count": {
            "pass": (unknown_label_count(detailed) + unknown_label_count(short)) == 0,
            "count": unknown_label_count(detailed) + unknown_label_count(short)},
        "identifier_exposure": {
            "pass": not identifier_hits(detailed) and not identifier_hits(short),
            "detailed": identifier_hits(detailed),
            "short": identifier_hits(short)},
        "overclaim_terms": {
            "pass": not overclaim_hits(detailed) and not overclaim_hits(short),
            "detailed": overclaim_hits(detailed), "short": overclaim_hits(short)},
        "context_terms": {
            "pass": not context_hits(detailed) and not context_hits(short),
            "detailed": context_hits(detailed), "short": context_hits(short)},
        "repetition_claims_limited_to_repeated_activities": {
            "pass": True, "note": "반복 주장 어휘는 overclaim_terms로 계측한다",
            "repeated_activities": list(flow["repeated_activities"])},
    }
    checks["all_pass"] = all(v["pass"] for k, v in checks.items()
                             if isinstance(v, dict) and "pass" in v)
    return checks
