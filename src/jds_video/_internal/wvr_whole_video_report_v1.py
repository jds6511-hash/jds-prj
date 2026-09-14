"""WVR_WHOLE_VIDEO_REPORT_V1 — Analysis · Conclusion · β/v3 report input adapter.

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_REPORT_V1_2026-09-13.md`

Overview branch(timeline · CANONICAL_FLOW · Overview)는 **읽기 전용**이다.
여기서 하는 일은 셋이다.

```
1. Analysis / Conclusion 프롬프트와 검사 규칙 (생성은 실행기가 한다)
2. β/v3 report input adapter — 24초 격자 정규화 · caption · subtitle 재집계
3. 최종 보고서 조립
```

새 관찰을 만들지 않는다. 새 inference를 여기서 하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import re
from types import SimpleNamespace

import rei_c01_adapter as rei
import wvr_overview_synthesis_v2 as sv
from v2_1_presentation_input import exclusion_reasons

EVENT = "WVR_WHOLE_VIDEO_REPORT_V1"
PREREG = ("docs/preregistration/"
          "WVR_WHOLE_VIDEO_REPORT_V1_2026-09-13.md")

SEG_LEN_SEC = 24.0
EXPECTED_SEGMENT_COUNT = 101
TOTAL_COVERAGE_SEC = 2424.0
EMPTY_CAPTION = rei.EMPTY_CAPTION

M3_SEGMENTS_SHA256 = \
    "aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92"


class ReportError(RuntimeError):
    """report 계약 위반."""


def frozen_text_sha(path) -> str:
    """텍스트 checkout의 CRLF만 LF로 맞춘 portable SHA256."""
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


# ── §4-1 24초 격자 정규화 ───────────────────────────────────────────
def split_entries(timeline: dict) -> list[dict]:
    """48초 entry를 24초 둘로 나눈다. 내용을 바꾸지 않는다.

    chunk 소유 경계 때문에 각 chunk의 마지막 entry만 48초다(실측 5개).
    두 조각은 같은 broad_activity와 같은 source lineage를 갖는다.
    """
    rows: list[dict] = []
    for entry in timeline["entries"]:
        start, end = float(entry["start_sec"]), float(entry["end_sec"])
        span = round(end - start, 6)
        if span == SEG_LEN_SEC:
            pieces = [(start, end)]
        elif span == SEG_LEN_SEC * 2:
            pieces = [(start, start + SEG_LEN_SEC), (start + SEG_LEN_SEC, end)]
        else:
            raise ReportError("예상 밖 entry 길이 %r (entry %r)"
                              % (span, entry["entry_index"]))
        for part, (s, e) in enumerate(pieces):
            rows.append({
                "idx": len(rows),
                "start": round(s, 6),
                "end": round(e, 6),
                "broad_activity": list(entry["broad_activity"]),
                "source_entry_index": entry["entry_index"],
                "source_entry_part": part,
                "source_entry_part_count": len(pieces),
                "source_chunk": entry["source_chunk"],
                "source_window": dict(entry["source_window"]),
            })
    if len(rows) != EXPECTED_SEGMENT_COUNT:
        raise ReportError("segment 수가 %d가 아니다: %d"
                          % (EXPECTED_SEGMENT_COUNT, len(rows)))
    for row in rows:
        if row["start"] != row["idx"] * SEG_LEN_SEC:
            raise ReportError("start 불변식 위반 idx=%d start=%r"
                              % (row["idx"], row["start"]))
    if rows[-1]["end"] != TOTAL_COVERAGE_SEC:
        raise ReportError("마지막 segment가 %r 에서 끝난다" % rows[-1]["end"])
    return rows


def build_caption(broad_activity: list[str]) -> str:
    """§4-2 — 원문 label을 재작성하지 않는다."""
    parts = [str(x).strip() for x in broad_activity if str(x).strip()]
    return rei.JOIN.join(parts) if parts else EMPTY_CAPTION


def build_segments(timeline: dict, m3_segments: list[dict]) -> dict:
    """β/v3가 받는 segments.json. 새 inference 없음."""
    rows = split_entries(timeline)
    segments, lineage = [], []
    for row in rows:
        picked = rei.aggregate_subtitle(m3_segments, row["start"], row["end"])
        caption = build_caption(row["broad_activity"])
        segments.append({
            "idx": row["idx"],
            "start": row["start"],
            "end": row["end"],
            "subtitle": rei.subtitle_text(picked),
            "caption": caption,
        })
        lineage.append({
            "idx": row["idx"],
            "span": [row["start"], row["end"]],
            "source_entry_index": row["source_entry_index"],
            "source_entry_part": row["source_entry_part"],
            "source_entry_part_count": row["source_entry_part_count"],
            "source_chunk": row["source_chunk"],
            "source_window": row["source_window"],
            "broad_activity": row["broad_activity"],
            "subtitle_source_m3_idx": [int(s["idx"]) for s in picked],
        })

    doc = {
        "video_id": "wvr_whole_video",
        "duration_sec": TOTAL_COVERAGE_SEC,
        "fps": None,
        "n_segments": len(segments),
        "segments": segments,
        "provenance": {
            "event": EVENT,
            "prereg": PREREG,
            "seg_len_sec": SEG_LEN_SEC,
            "new_inference_count": 0,
            "m3_segments_sha256": M3_SEGMENTS_SHA256,
        },
    }
    stats = {
        "segment_count": len(segments),
        "temporal_coverage_sec": round(
            sum(s["end"] - s["start"] for s in segments), 6),
        "duplicate_coverage_sec": round(
            sum(max(0.0, a["end"] - b["start"])
                for a, b in zip(segments, segments[1:])), 6),
        "subtitle_populated": sum(1 for s in segments if s["subtitle"]),
        "caption_populated": sum(1 for s in segments
                                 if s["caption"] and s["caption"] != EMPTY_CAPTION),
        "split_entry_count": len({
            r["source_entry_index"] for r in rows
            if r["source_entry_part_count"] > 1
        }),
    }
    return {"doc": doc, "lineage": lineage, "stats": stats}


# ── §2 Analysis 프롬프트 ────────────────────────────────────────────
ANALYSIS_PROMPT_TEMPLATE = r'''아래 자료는 한 영상 전체의 관찰을 시간순 활동 구간으로 결정적으로 압축한 결과와,
그 위에서 작성된 Overview입니다. 오직 이 자료만 사용하여 한국어 ANALYSIS를 작성하십시오.

질문:
"이 영상 전체에서 활동들이 어떻게 배치되고 어떤 구조적 패턴이 관찰되는가?"

쓸 수 있는 것:
- 활동의 반복 여부
- 시간적 전환
- 여러 활동이 묶여 나타나는 배치
- 영상 전반에서 관찰되는 구조적 패턴

쓰면 안 되는 것:
- 사람의 의도, 감정, 생활 습관
- 장소나 상황 추정, 원인이나 목적 추론
- 자료에 없는 사건, 물건, 장소, 맥락
- 새로운 사건을 만들어 내는 서술

표현 규칙:
- 활동을 가리킬 때는 제공된 activity 표현을 그대로 쓰십시오. 새 활동 이름을 만들지 마십시오.
- 다음 표현은 쓰지 마십시오: 빈번하게, 주기적으로, 중심이 된다, 흐름을 이끈다,
  일상적인, 주요한, 핵심적인, 대부분, 지속적으로, 전반적으로.
- 반복을 말하려면 repeated_activities에 있는 활동만 쓰십시오.
- 어떤 활동이 더 중요하다고 쓰지 마십시오.
- 초 단위 시각, 구간 번호, window 또는 chunk 식별자를 본문에 쓰지 마십시오.

구조 규칙:
- 2~4개 단락으로 쓰고 event log처럼 나열하지 마십시오.
- **마지막 문장은 final_phase_activities에 있는 활동만으로 영상이 어떻게 끝나는지
  적으십시오.** 그 문장에 다른 활동 이름을 넣지 마십시오.
- Markdown fence, JSON, bullet, heading 없이 본문만 출력하십시오.

CANONICAL_FLOW:
__CANONICAL_FLOW_JSON__

DETAILED_OVERVIEW:
__DETAILED_OVERVIEW__
'''

CONCLUSION_PROMPT_TEMPLATE = r'''아래 Overview와 Analysis를 최종적으로 압축·종합하여 한국어 CONCLUSION을 작성하십시오.

절대 규칙:
- **새로운 근거를 추가하지 마십시오.** Overview와 Analysis에 없는 활동, 사건,
  해석, 종료 상태를 쓰면 안 됩니다.
- 마지막 문장이 말하는 종료 활동은 Overview·Analysis의 종료 활동과 같아야 합니다.
- 사람의 의도, 감정, 생활 습관, 장소나 상황 추정, 원인이나 목적 추론을 쓰지 마십시오.
- 다음 표현은 쓰지 마십시오: 빈번하게, 주기적으로, 중심이 된다, 흐름을 이끈다,
  일상적인, 주요한, 핵심적인, 대부분, 지속적으로, 전반적으로.
- 초 단위 시각, 구간 번호, window 또는 chunk 식별자를 쓰지 마십시오.
- 3~5문장으로 쓰고, Markdown fence나 heading 없이 본문만 출력하십시오.

SHORT_OVERVIEW:
__SHORT_OVERVIEW__

DETAILED_OVERVIEW:
__DETAILED_OVERVIEW__

ANALYSIS:
__ANALYSIS__
'''


def analysis_prompt(flow: dict, detailed_overview: str) -> str:
    payload = {
        "phase_sequence": [
            {"order": phase["phase_index"] + 1,
             "activities": list(phase["activities"]),
             "consecutive_entry_count": phase["entry_count"]}
            for phase in flow["phases"]],
        "first_phase_activities": list(flow["first_phase_activities"]),
        "final_phase_activities": list(flow["final_phase_activities"]),
        "repeated_activities": list(flow["repeated_activities"]),
        "non_repeated_activities": list(flow["non_repeated_activities"]),
        "activity_phase_occurrences": dict(flow["activity_phase_occurrences"]),
        "phase_count": flow["phase_count"],
        "transition_count": flow["transition_count"],
    }
    return (ANALYSIS_PROMPT_TEMPLATE
            .replace("__CANONICAL_FLOW_JSON__",
                     json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                indent=2))
            .replace("__DETAILED_OVERVIEW__", detailed_overview.strip()))


def conclusion_prompt(short_overview: str, detailed_overview: str,
                      analysis: str) -> str:
    return (CONCLUSION_PROMPT_TEMPLATE
            .replace("__SHORT_OVERVIEW__", short_overview.strip())
            .replace("__DETAILED_OVERVIEW__", detailed_overview.strip())
            .replace("__ANALYSIS__", analysis.strip()))


# ── §8 machine check ────────────────────────────────────────────────
def machine_checks(flow: dict, overview: dict, analysis: str,
                   conclusion: str) -> dict:
    canonical_final = set(flow["final_phase_activities"])
    detailed = overview["detailed_overview"]
    short = overview["short_overview"]
    allowed = sv.activity_set(detailed) | sv.activity_set(short) \
        | sv.activity_set(analysis)

    checks = {
        "analysis_unknown_label": {
            "pass": sv.unknown_label_count(analysis) == 0,
            "count": sv.unknown_label_count(analysis)},
        "analysis_identifier_exposure": {
            "pass": not sv.identifier_hits(analysis),
            "hits": sv.identifier_hits(analysis)},
        "analysis_overclaim_terms": {
            "pass": not sv.overclaim_hits(analysis),
            "hits": sv.overclaim_hits(analysis)},
        "analysis_context_terms": {
            "pass": not sv.context_hits(analysis),
            "hits": sv.context_hits(analysis)},
        "analysis_final_phase_matches_canonical": {
            "pass": sv.final_phase_labels(analysis) == canonical_final,
            "analysis_final": sorted(sv.final_phase_labels(analysis)),
            "canonical_final": sorted(canonical_final)},
        "conclusion_activity_subset_of_overview_and_analysis": {
            "pass": sv.activity_set(conclusion) <= allowed,
            "conclusion_only": sorted(sv.activity_set(conclusion) - allowed),
            "allowed": sorted(allowed)},
        "conclusion_identifier_exposure": {
            "pass": not sv.identifier_hits(conclusion),
            "hits": sv.identifier_hits(conclusion)},
        "conclusion_overclaim_terms": {
            "pass": not sv.overclaim_hits(conclusion),
            "hits": sv.overclaim_hits(conclusion)},
        "conclusion_context_terms": {
            "pass": not sv.context_hits(conclusion),
            "hits": sv.context_hits(conclusion)},
        "conclusion_final_phase_matches_canonical": {
            "pass": sv.final_phase_labels(conclusion) == canonical_final,
            "conclusion_final": sorted(sv.final_phase_labels(conclusion)),
            "canonical_final": sorted(canonical_final)},
    }
    checks["all_pass"] = all(v["pass"] for k, v in checks.items()
                             if isinstance(v, dict) and "pass" in v)
    return checks


# ── 최종 보고서 조립 ────────────────────────────────────────────────
def extract_beta_support(engine_report: str) -> str:
    """β/v3 보고서에서 보조 구간 절만 꺼낸다.

    엔진이 자체 생성한 개요·분석·결론은 승인된 whole-video 본문을 대체할 수
    없으므로 가져오지 않는다. heading 이름은 기존 β/v3 renderer 계약이다.
    """
    match = re.search(
        r"^## 주요 사건 및 내용\s*\n(?P<body>.*?)(?=^## 핵심 내용 분석\s*$)",
        engine_report, re.MULTILINE | re.DOTALL)
    if not match:
        raise ReportError("β/v3 보고서에서 '주요 사건 및 내용' 절을 찾지 못했다")
    body = match.group("body").strip()
    if not body:
        raise ReportError("β/v3 보조 구간 절이 비어 있다")
    return body


def report_lines(markdown: str) -> list[str]:
    """최종 Markdown을 의미 변경 없이 HWPX 문단 열로 바꾼다."""
    return markdown.replace("\r\n", "\n").rstrip("\n").split("\n")


def beta_metrics(canonical: dict, presentation: dict,
                 run_manifest: dict) -> dict:
    """기존 β/v3 산출물에서 적격·제외·fallback 사실만 집계한다."""
    distributions = run_manifest["distributions"]
    presented = distributions["presentation"]
    counters = distributions["counters"]
    excluded_ids = {
        episode_id
        for highlight in presentation.get("highlights", [])
        for episode_id in highlight.get("excluded_summary_episode_ids", [])
    }
    raw_by_id = {row["episode_id"]: row for row in canonical["episodes"]}
    quality_exclusions = {}
    for episode_id in sorted(excluded_ids):
        raw = raw_by_id[episode_id]
        episode = SimpleNamespace(
            content_status=raw.get("content_status"),
            grounding_status=raw.get("grounding_status", "NOT_APPLICABLE"),
            summary=raw.get("summary"),
        )
        reasons = exclusion_reasons(episode)
        quality_exclusions[episode_id] = (
            " + ".join(reasons) if reasons else "PRESENTATION_EXCLUDED")
    return {
        "episodes": int(presented["episodes"]),
        "eligible": int(presented["eligible"]),
        "excluded": int(presented["episodes"]) - int(presented["eligible"]),
        "excluded_by_dialogue_grounding": int(
            presented.get("excluded_by_dialogue_grounding", 0)),
        "quality_exclusions": quality_exclusions,
        "fallback": {
            "prompt_refusals": int(counters.get("prompt_refusals", 0)),
            "llm_failures": int(counters.get("llm_failures", 0)),
            "retries": int(counters.get("retries", 0)),
        },
    }


def final_report_markdown(overview: dict, analysis: str, conclusion: str,
                          stats: dict, beta_support: str | None = None) -> str:
    lines = [
        "# 영상 전체 보고서 — full_xekZO4n4QuE",
        "",
        "- 원본 길이 2424.186485초 · 관찰 union [0, 2424) · "
        "terminal remainder 0.186485초",
        "- 관찰 창 116개(C01~C05) → 중복 제거 timeline entry 96개 → "
        "보고서 입력 segment %d개" % stats["segment_count"],
        "- 사건: `%s`" % EVENT,
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
    ]
    if beta_support:
        lines += [
            "",
            "## β/v3 보조 구간 요약",
            "",
            beta_support.strip(),
        ]
    lines += [
        "",
        "## 근거 및 생성 정보",
        "",
        "- 시각 관찰: Qwen3-VL-8B-Instruct · 48초 창 · 24초 stride · 0.5fps",
        "- 발화: 기존 M3 STT 재집계(새 STT 없음)",
        "- 활동 timeline은 결정적 병합 산출물이며 모든 구간이 원본 창까지 추적된다",
        "- 한계: 관찰되지 않은 맥락은 기록하지 않는다",
        "",
    ]
    return "\n".join(lines) + "\n"
