"""Multimodal timeline → 기존 양식의 보고서(제목 / □ 개요 / □ 세부내용)와 evidence sidecar.

```
multimodal event
      ↓  select_rows()      말하는 모습만 담은 visual row는 speech row가 덮으면 생략
report row                  비고 = 화면 · 음성 · 음성+화면
      ↓  compose_overview() 행 요약에서만 만든다
      ↓  render_report()    개요가 행으로 뒷받침되지 않으면 거부한다
```

생략과 삭제는 다르다(작업 지시 §15) — 생략된 visual event도 `suppressed_visual()`과
sidecar에 남는다.
"""
from __future__ import annotations

import re

from wvr_speech_events_v1 import cohesion, tokens
from wvr_multimodal_timeline_v1 import AUDIO, VISUAL, VISUAL_AUDIO, overlap_seconds

EVIDENCE_LABEL = {VISUAL: "화면", AUDIO: "음성", VISUAL_AUDIO: "음성+화면"}

# "말하고 있다"는 사실만 전하는 시각 서술. 언어 일반 표현이며 특정 영상 유형 어휘가 아니다.
SPEAKING_VERBS = ("말한다", "말하고", "발표한다", "발표하고", "이야기한다", "얘기한다",
                  "설명한다", "설명하며", "발언한다", "말씀한다")
SPEAKING_OBJECT_HINTS = ("마이크", "노트북", "화면", "자리", "회의", "단상", "책상", "테이블")
MIN_OVERVIEW_SUPPORT = 0.6


def hhmmss(seconds):
    total = int(seconds)
    return "%02d:%02d:%02d" % (total // 3600, (total % 3600) // 60, total % 60)


def is_speaking_only(summary):
    """발화 행위만 말하고 내용이 없는 서술인가."""
    text = (summary or "").strip()
    if not any(verb in text for verb in SPEAKING_VERBS):
        return False
    content = tokens(text) - set(SPEAKING_OBJECT_HINTS)
    for verb in SPEAKING_VERBS:
        content -= tokens(verb)
    # 사람·장소 정도만 남으면 내용 없는 발화 묘사로 본다
    return len(content) <= 3


def select_rows(timeline, min_overlap_sec=0.0):
    """보고서에 넣을 행을 고른다. 근거 자체는 버리지 않는다."""
    speech_rows = [e for e in timeline if e["evidence_type"] in (AUDIO, VISUAL_AUDIO)]
    rows = []
    for event in sorted(timeline, key=lambda e: (e["start"], e["end"])):
        if event["evidence_type"] == VISUAL and is_speaking_only(event["summary"]):
            covered = any(overlap_seconds(event, other) > min_overlap_sec
                          for other in speech_rows)
            if covered:
                continue
        rows.append({
            "row_id": "ROW%03d" % (len(rows) + 1),
            "start": event["start"],
            "end": event["end"],
            "category": event.get("category", ""),
            "summary": event.get("summary", ""),
            "evidence": EVIDENCE_LABEL[event["evidence_type"]],
            "evidence_type": event["evidence_type"],
            "visual_event_ids": list(event.get("visual_event_ids", [])),
            "speech_event_ids": list(event.get("speech_event_ids", [])),
            "visual_claim_ids": list(event.get("visual_claim_ids", [])),
            "utterance_ids": list(event.get("utterance_ids", [])),
        })
    return rows


def suppressed_visual(timeline, min_overlap_sec=0.0):
    """보고서에서 생략된 visual event. evidence는 여기(그리고 sidecar)에 남는다."""
    speech_rows = [e for e in timeline if e["evidence_type"] in (AUDIO, VISUAL_AUDIO)]
    out = []
    for event in timeline:
        if event["evidence_type"] != VISUAL or not is_speaking_only(event["summary"]):
            continue
        if any(overlap_seconds(event, other) > min_overlap_sec for other in speech_rows):
            out.append(event)
    return out


def compose_overview(rows, max_sentences=4):
    """행 요약만으로 개요를 만든다. 행에 없는 사실을 넣지 않는다."""
    if not rows:
        return "보고할 구간이 없다."
    ordered = sorted(rows, key=lambda r: r["start"])
    picks = []
    step = max(1, len(ordered) // max_sentences)
    for index in range(0, len(ordered), step):
        row = ordered[index]
        sentence = row["summary"].strip().rstrip(".")
        picks.append("%s경 %s" % (hhmmss(row["start"])[:5], sentence))
        if len(picks) == max_sentences:
            break
    return ". ".join(picks) + "."


def validate_overview(overview, rows, min_support=MIN_OVERVIEW_SUPPORT):
    """개요 어휘가 행 요약으로 뒷받침되는지 본다."""
    vocabulary = set()
    for row in rows:
        vocabulary |= tokens(row["summary"]) | tokens(row.get("category", ""))
    overview_tokens = tokens(overview)
    if not overview_tokens:
        return ["개요가 비어 있다"]
    grounded = overview_tokens & vocabulary
    if len(grounded) / len(overview_tokens) < min_support:
        missing = sorted(overview_tokens - vocabulary)[:8]
        return ["개요에 세부내용으로 뒷받침되지 않는 표현이 있다: %s" % missing]
    return []


def render_report(title, overview, rows):
    problems = validate_overview(overview, rows)
    if problems:
        raise ValueError("; ".join(problems))
    lines = ["# %s" % title, "", "□ 개요", "", overview.strip(), "", "□ 세부내용", "",
             "| 구분 | 시간 | 내용 | 비고 |", "|---|---|---|---|"]
    for row in sorted(rows, key=lambda r: r["start"]):
        lines.append("| %s | %s ~ %s | %s | %s |"
                     % (row["category"], hhmmss(row["start"]), hhmmss(row["end"]),
                        row["summary"], row["evidence"]))
    return "\n".join(lines) + "\n"


def build_sidecar(rows, suppressed=(), transcript_path=None, visual_source=None):
    return {
        "event": "WVR_MULTIMODAL_FULL_VIDEO_REPORT_V1",
        "row_count": len(rows),
        "transcript_path": transcript_path,
        "visual_source": visual_source,
        "rows": [dict(row) for row in rows],
        # 호출자에 따라 event 형태(event_id)로도, 선택 단계의 행 형태(row_id)로도 온다
        "suppressed_visual_events": [
            {"event_id": e.get("event_id") or e.get("row_id"),
             "start": e["start"], "end": e["end"], "summary": e["summary"],
             "visual_claim_ids": list(e.get("visual_claim_ids", [])),
             **({"reason": e["reason"]} if e.get("reason") else {})}
            for e in suppressed],
    }


def report_statistics(rows, visual_events, speech_events, suppressed):
    counts = {"화면": 0, "음성": 0, "음성+화면": 0}
    for row in rows:
        counts[row["evidence"]] = counts.get(row["evidence"], 0) + 1
    return {
        "visual_events": len(visual_events),
        "speech_events": len(speech_events),
        "report_rows": len(rows),
        "suppressed_visual_rows": len(suppressed),
        "evidence_counts": counts,
        "rows_with_speech": sum(1 for r in rows if r["utterance_ids"]),
    }
