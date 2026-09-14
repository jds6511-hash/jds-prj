"""WVR_WHOLE_VIDEO_REPORT_V2 — 사용자-facing 본문 정리.

동결 Overview와 구조 입력을 읽고 Analysis/Conclusion 프롬프트를 만들며, 기존
β/v3 자연어 보조 요약 없이 최종 Markdown을 조립한다.
"""
from __future__ import annotations

import json

import wvr_overview_synthesis_v2 as sv

EVENT = "WVR_WHOLE_VIDEO_REPORT_V2"
MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"
MODEL_REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"


class ReportV2Error(RuntimeError):
    """사용자-facing 보고서 계약 위반."""


ANALYSIS_TEMPLATE = r'''아래 자료만 사용해 한국어 보고서의 분석 본문을 작성하십시오.

역할:
- Overview가 "무엇이 있었는가"를 설명한다면, Analysis는 활동의 반복·전환·배치에서
  관찰되는 구조적 패턴을 설명합니다.
- Overview 문장을 순서만 바꿔 다시 쓰거나 사건 목록을 반복하지 마십시오.

허용:
- 제공된 activity의 반복 여부와 전환
- 여러 activity group의 시간적 배치
- 제공된 final phase

금지:
- 새로운 사건이나 activity 이름
- 의도, 감정, 생활 습관, 장소·상황 추정, 원인·목적 추론
- 중요도나 지배성을 암시하는 표현
- 시각, segment/window/chunk/entry 식별자
- 다음 표현: 빈번하게, 주기적으로, 중심이 된다, 중심이, 중심으로, 흐름을 이끈다,
  일상적인, 주요한, 핵심적인, 대부분, 지속적으로, 전반적으로

작성:
- 자연스러운 한국어 2~4문장
- 마지막 문장은 final_phase_activities만 사용해 종료 활동을 명시
- heading, bullet, JSON, Markdown fence 없이 본문만 출력

CANONICAL_FLOW:
__FLOW__

FROZEN_DETAILED_OVERVIEW:
__DETAILED__

WHOLE_VIDEO_ACTIVITY_TIMELINE_AGGREGATE:
__TIMELINE__
'''

CONCLUSION_TEMPLATE = r'''동결 Overview와 아래 revised Analysis만 사용해 한국어 결론을 작성하십시오.

역할:
- Overview와 Analysis의 짧은 종합
- Overview를 그대로 복사하거나 사건을 다시 나열하지 않음

절대 규칙:
- 새 evidence, 사건, activity, 해석을 추가하지 마십시오.
- 의도, 감정, 생활 습관, 장소·상황 추정, 원인·목적 추론을 쓰지 마십시오.
- 중요도나 지배성을 암시하지 마십시오.
- 시각이나 내부 식별자를 쓰지 마십시오.
- 다음 표현: 빈번하게, 주기적으로, 중심이 된다, 중심이, 중심으로, 흐름을 이끈다,
  일상적인, 주요한, 핵심적인, 대부분, 지속적으로, 전반적으로
- 2~3문장으로 짧게 작성하고 마지막 문장은 식사로 끝남을 명시하십시오.
- heading, bullet, JSON, Markdown fence 없이 본문만 출력하십시오.

FROZEN_SHORT_OVERVIEW:
__SHORT__

FROZEN_DETAILED_OVERVIEW:
__DETAILED__

REVISED_ANALYSIS:
__ANALYSIS__
'''


def _flow_payload(flow: dict) -> dict:
    return {
        "phase_sequence": [list(p["activities"]) for p in flow["phases"]],
        "repeated_activities": list(flow["repeated_activities"]),
        "final_phase_activities": list(flow["final_phase_activities"]),
        "phase_count": int(flow["phase_count"]),
        "transition_count": int(flow["transition_count"]),
    }


def _timeline_payload(timeline: dict) -> dict:
    counts: dict[str, int] = {}
    ordered_groups = []
    for entry in timeline["entries"]:
        labels = list(entry["broad_activity"])
        ordered_groups.append(labels)
        for label in labels:
            counts[label] = counts.get(label, 0) + 1
    return {
        "ordered_activity_groups": ordered_groups,
        "activity_entry_occurrences": counts,
        "entry_count": int(timeline["entry_count"]),
    }


def analysis_prompt(flow: dict, overview: dict, timeline: dict) -> str:
    return (ANALYSIS_TEMPLATE
            .replace("__FLOW__", json.dumps(_flow_payload(flow),
                                              ensure_ascii=False, indent=2))
            .replace("__DETAILED__", overview["detailed_overview"].strip())
            .replace("__TIMELINE__", json.dumps(_timeline_payload(timeline),
                                                  ensure_ascii=False, indent=2)))


def conclusion_prompt(overview: dict, analysis: str) -> str:
    return (CONCLUSION_TEMPLATE
            .replace("__SHORT__", overview["short_overview"].strip())
            .replace("__DETAILED__", overview["detailed_overview"].strip())
            .replace("__ANALYSIS__", analysis.strip()))


def clean_body(raw: str, what: str) -> str:
    return sv.clean_body(raw, what=what)


def machine_checks(flow: dict, overview: dict, analysis: str,
                   conclusion: str) -> dict:
    allowed = (sv.activity_set(overview["short_overview"])
               | sv.activity_set(overview["detailed_overview"])
               | sv.activity_set(analysis))
    final = set(flow["final_phase_activities"])
    checks = {
        "analysis_unknown_activity": sv.unknown_label_count(analysis) == 0,
        "analysis_context": not sv.context_hits(analysis),
        "analysis_overclaim": not sv.overclaim_hits(analysis),
        "analysis_identifier": not sv.identifier_hits(analysis),
        "analysis_final": sv.final_phase_labels(analysis) == final,
        "conclusion_activity_subset": sv.activity_set(conclusion) <= allowed,
        "conclusion_context": not sv.context_hits(conclusion),
        "conclusion_overclaim": not sv.overclaim_hits(conclusion),
        "conclusion_identifier": not sv.identifier_hits(conclusion),
        "conclusion_final": sv.final_phase_labels(conclusion) == final,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def _validate_new_prose(analysis: str, conclusion: str) -> None:
    identifier_hits = sv.identifier_hits(analysis) + sv.identifier_hits(conclusion)
    if identifier_hits:
        raise ReportV2Error("identifier exposure: %r" % identifier_hits)


def final_report_markdown(overview: dict, analysis: str, conclusion: str,
                          timeline: dict, beta: dict) -> str:
    _validate_new_prose(analysis, conclusion)
    exclusions = beta.get("quality_exclusions", {})
    exclusion_text = " · ".join(
        "%s %s" % (episode, reason)
        for episode, reason in sorted(exclusions.items())) or "없음"
    lines = [
        "# 영상 전체 보고서",
        "",
        "## 개요",
        "",
        overview["short_overview"].strip(),
        "",
        "## 상세 개요",
        "",
        overview["detailed_overview"].strip(),
        "",
        "## 분석",
        "",
        analysis.strip(),
        "",
        "## 결론",
        "",
        conclusion.strip(),
        "",
        "## 근거 및 생성 정보",
        "",
        "- 원본 길이: %.6f초" % float(timeline["video_duration_sec"]),
        "- 관찰 범위: [0, %.1f)초" % float(timeline["temporal_coverage_sec"]),
        "- 시각 모델: %s · revision %s" % (MODEL_ID, MODEL_REVISION),
        "- 관찰 설정: 48초 window · 24초 stride · 0.5fps",
        "- 정규화 timeline/lineage: %d개 entry · 중복 제거 후 연속 범위"
        % int(timeline["entry_count"]),
        "- M3 STT: auxiliary evidence로만 사용 · 새 STT 없음",
        "- β/v3 processing: eligible %d/%d" % (
            int(beta["eligible"]), int(beta["episodes"])),
        "- quality exclusions %d건: %s" % (len(exclusions), exclusion_text),
        "- terminal remainder: %.6f초" % float(
            timeline["terminal_remainder_sec"]),
        "- 알려진 한계: 일부 구간의 STT·생성 품질 문제로 제외가 발생했으며, "
        "제외된 자연어 요약과 β/v3 episode별 생성문은 사용자 본문에 포함하지 않았다.",
        "",
    ]
    text = "\n".join(lines)
    if "## β/v3 보조 구간 요약" in text or "seg#" in text:
        raise ReportV2Error("user-facing body contains forbidden beta narrative")
    return text
