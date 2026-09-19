"""Visual event(기존 WVR 산출물, 읽기 전용) + Speech event → 하나의 시간축.

```
visual event    기존 event_timeline.json — 새 visual 추론을 하지 않는다
speech event    wvr_speech_events_v1
      ↓  merge_timeline()
multimodal event  evidence_type ∈ {VISUAL, AUDIO, VISUAL_AUDIO}
```

연결 규칙(작업 지시 §12).

```
시간이 겹친다     → 그것만으로는 합치지 않는다
내용도 겹친다     → 같은 episode로 연결하되 두 provenance를 모두 남긴다
내용이 다르다     → 별개 event로 둔다
```
"""
from __future__ import annotations

from wvr_speech_events_v1 import cohesion, tokens

VISUAL, AUDIO, VISUAL_AUDIO = "VISUAL", "AUDIO", "VISUAL_AUDIO"
MIN_CONTENT_LINK = 0.12        # 시각·음성 요약의 어휘 자카드 임계
MIN_TIME_OVERLAP_SEC = 0.0     # 겹침이 0보다 크면 시간 조건 성립


def load_visual_events(timeline_obj):
    """기존 `event_timeline.json`(list) → 공통 event 모양. 원본을 수정하지 않는다."""
    events = timeline_obj.get("events", []) if isinstance(timeline_obj, dict) else timeline_obj
    out = []
    for event in events:
        intervals = event.get("support_intervals") or []
        starts = [i["start_sec"] for i in intervals] or [event.get("start", 0.0)]
        ends = [i["end_sec"] for i in intervals] or [event.get("end", 0.0)]
        claim_ids = event.get("claim_ids")
        if claim_ids is None:
            claim_ids = [c["claim_id"] for c in event.get("claims", [])
                         if isinstance(c, dict) and c.get("claim_id")]
        out.append({
            "event_id": event.get("event_id") or "EVT%03d" % (len(out) + 1),
            "start": round(float(min(starts)), 2),
            "end": round(float(max(ends)), 2),
            "category": event.get("category", ""),
            "summary": event.get("summary", ""),
            "claim_ids": list(claim_ids),
        })
    return sorted(out, key=lambda e: (e["start"], e["end"]))


def overlap_seconds(a, b):
    return min(a["end"], b["end"]) - max(a["start"], b["start"])


def content_link(visual_event, speech_event):
    """두 요약이 같은 대상을 말하는지. 어휘 겹침으로만 판단한다."""
    return cohesion(tokens(visual_event.get("summary", "")),
                    tokens(speech_event.get("summary", "")))


def _visual_entry(event):
    return {
        "event_id": event["event_id"],
        "start": event["start"],
        "end": event["end"],
        "category": event.get("category", ""),
        "summary": event.get("summary", ""),
        "evidence_type": VISUAL,
        "visual_event_ids": [event["event_id"]],
        "speech_event_ids": [],
        "visual_claim_ids": list(event.get("claim_ids", [])),
        "utterance_ids": [],
    }


def _speech_entry(event):
    return {
        "event_id": event["speech_event_id"],
        "start": event["start"],
        "end": event["end"],
        "category": event.get("category", ""),
        "summary": event.get("summary", ""),
        "evidence_type": AUDIO,
        "visual_event_ids": [],
        "speech_event_ids": [event["speech_event_id"]],
        "visual_claim_ids": [],
        "utterance_ids": list(event.get("supporting_utterance_ids", [])),
    }


def merge_timeline(visual_events, speech_events, min_content_link=MIN_CONTENT_LINK):
    """시간·내용이 함께 맞는 쌍만 연결한다. 나머지는 각자의 행으로 남는다."""
    visual = [dict(v) for v in visual_events]
    speech = [dict(s) for s in speech_events]
    linked_visual, linked_speech = {}, {}

    for v_index, v in enumerate(visual):
        for s_index, s in enumerate(speech):
            if overlap_seconds(v, s) <= MIN_TIME_OVERLAP_SEC:
                continue
            if content_link(v, s) < min_content_link:
                continue
            linked_visual.setdefault(v_index, set()).add(s_index)
            linked_speech.setdefault(s_index, set()).add(v_index)

    timeline = []
    merged_speech = set()
    for v_index, v in enumerate(visual):
        partners = sorted(linked_visual.get(v_index, ()))
        if not partners:
            timeline.append(_visual_entry(v))
            continue
        entry = _visual_entry(v)
        entry["evidence_type"] = VISUAL_AUDIO
        for s_index in partners:
            s = speech[s_index]
            merged_speech.add(s_index)
            entry["speech_event_ids"].append(s["speech_event_id"])
            entry["utterance_ids"].extend(s.get("supporting_utterance_ids", []))
            entry["start"] = min(entry["start"], s["start"])
            entry["end"] = max(entry["end"], s["end"])
            # 표시 문장은 정보가 더 많은 speech 요약을 쓰되 visual provenance를 유지한다
            if len(s.get("summary", "")) > len(entry["summary"]):
                entry["summary"] = s["summary"]
                entry["category"] = s.get("category", entry["category"])
        timeline.append(entry)

    for s_index, s in enumerate(speech):
        if s_index not in merged_speech:
            timeline.append(_speech_entry(s))

    return sorted(timeline, key=lambda e: (e["start"], e["end"]))
