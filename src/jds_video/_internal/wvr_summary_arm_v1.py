"""PHASE A — frozen generative summary arm (표현만 바꾸는 실험).

```
동결(입력)   transcript · speech event 경계/구성원 · visual event · relation
             · multimodal membership · chapter membership · evidence id
바뀌는 것    category · event summary · chapter title/summary · 최종 제목 · 개요
```

생성은 구간 단위로만 한다 — 전사 전체를 한 번에 넣지 않는다. 각 호출에는 그 event의
발화만 들어가고, chapter 호출에는 그 chapter의 구성 event 요약만 들어간다.

근거 감사는 어휘 일치가 아니라 **임베딩 유사도**로 본다(paraphrase를 어휘로 재면
정상 요약도 미지원으로 걸린다). 대신 숫자는 별도로 원문 대조한다 — 임베딩은 "3개월"과
"한 달"을 구분하지 못한다.
"""
from __future__ import annotations

import json
import re

import numpy as np

SUPPORTED = "SUPPORTED"
UNCERTAIN = "UNCERTAIN"
UNSUPPORTED = "UNSUPPORTED"
LONG_EVENT_DIAGNOSTIC = "LONG_EVENT_DIAGNOSTIC"
LOW_ADDED_VALUE = "LOW_ADDED_VALUE"

SUPPORTED_SIM = 0.80
UNCERTAIN_SIM = 0.45
REDUNDANT_SIM = 0.92
LONG_EVENT_SEC = 300.0
PROMPT_VERSION = "WVR_SUMMARY_ARM_V1/2026-09-17-b"

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?\s*[가-힣%A-Za-z]*")


def hhmmss(seconds):
    total = int(seconds)
    return "%02d:%02d:%02d" % (total // 3600, (total % 3600) // 60, total % 60)


# ── 프롬프트 ───────────────────────────────────────────────────────────

_RULES = """규칙
- 아래 발화에서 확인되는 내용만 쓴다. 발화에 없는 사실·수치·이름·배경지식을 넣지 마라.
- 추측하지 마라. 의견을 사실로, 한 사람의 제안을 전체의 결정으로 쓰지 마라.
- 전사가 깨졌거나 뜻이 불분명하면 그 부분은 빼고 확실한 것만 쓴다.
- category는 이 구간의 주제를 나타내는 짧은 명사구다(예: 식재료 보관, 예산 편성).
  "너무", "같아요", "앉아주시기" 같은 조각 표현을 쓰지 마라.
- summary는 한국어 1~2문장. 발화를 길게 그대로 옮기지 말고 무엇을 말했는지 정리한다.
- 발화 번호(U0001 같은 것)나 화자 번호를 요약 문장에 쓰지 마라.
- 전사가 잘못 들린 것으로 보이는 낱말은 그 뜻을 지어내지 말고 빼라.
- 설명한다 / 보고한다 / 논의한다 / 제안한다 / 질문한다 / 답변한다 를 근거에 맞게 구분한다.
- 출력은 JSON 하나만. 다른 말을 덧붙이지 마라: {"category": "...", "summary": "..."}"""


def build_event_prompt(event, utterances):
    lines = ["다음은 한 영상의 %s ~ %s 구간에서 나온 발화다."
             % (hhmmss(event["start"]), hhmmss(event["end"])),
             "EVENT_ID: %s" % event.get("speech_event_id", event.get("event_id", "")),
             "", "발화"]
    for item in utterances:
        lines.append("%s (%s) %s" % (item["id"], hhmmss(item["start"]), item["text"]))
    lines += ["", _RULES]
    return "\n".join(lines)


def build_chapter_prompt(chapter, events):
    lines = ["다음은 한 영상의 %s ~ %s 구간을 이루는 장면·발언 요약이다."
             % (hhmmss(chapter["start"]), hhmmss(chapter["end"])),
             "CHAPTER_ID: %s" % chapter["chapter_id"], "", "구성 요소"]
    for event in events:
        lines.append("- [%s] %s" % (event.get("evidence_type", ""), event.get("summary", "")))
    lines += ["", "규칙",
              "- 위 요약에서 확인되는 내용만 쓴다. 새로운 사실을 추가하지 마라.",
              "- category(title)는 이 구간 전체를 대표하는 짧은 명사구다.",
              '- "일상 활동", "여러 활동"처럼 뭉뚱그린 제목을 쓰지 마라.',
              "- summary는 한국어 1~2문장으로 이 구간의 흐름을 정리한다.",
              "- 발화 번호나 event id를 문장에 쓰지 마라.",
              '- 출력은 JSON 하나만: {"category": "...", "summary": "..."}']
    return "\n".join(lines)


def build_overview_prompt(chapters, events):
    lines = ["다음은 한 영상을 시간 순서로 정리한 구간 요약이다.", "", "구간"]
    for chapter in chapters:
        lines.append("- %s~%s %s: %s" % (hhmmss(chapter["start"]), hhmmss(chapter["end"]),
                                         chapter.get("title", ""), chapter.get("summary", "")))
    lines += ["", "규칙",
              "- 위 구간 요약에 없는 사실을 추가하지 마라.",
              "- 영상 전체의 흐름을 2~4문장으로 정리한다. 구간을 그대로 나열하지 마라.",
              '- 출력은 JSON 하나만: {"category": "전체 흐름", "summary": "..."}']
    return "\n".join(lines)


def build_title_prompt(chapters):
    lines = ["다음은 한 영상의 구간 제목과 요약이다.", ""]
    for chapter in chapters:
        lines.append("- %s: %s" % (chapter.get("title", ""), chapter.get("summary", "")))
    lines += ["", "규칙",
              "- 영상 전체를 대표하는 제목을 하나 만든다. 한 장면만 보고 짓지 마라.",
              "- 위 내용에서 확인되지 않는 고유명사·기관명을 넣지 마라.",
              "- 제목은 20자 안팎의 명사구다.",
              '- 출력은 JSON 하나만: {"category": "제목", "summary": "..."}']
    return "\n".join(lines)


# ── 출력 파싱 ──────────────────────────────────────────────────────────

def parse_summary_output(raw):
    """모델 출력에서 JSON 객체 하나를 꺼낸다. 코드펜스·앞뒤 산문을 허용한다."""
    text = (raw or "").strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("JSON 객체를 찾지 못했다: %r" % text[:120])
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError("JSON 파싱 실패: %s" % exc) from exc
    if not isinstance(parsed, dict):
        raise ValueError("JSON 객체가 아니다")
    for field in ("category", "summary"):
        value = parsed.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("%s 필드가 없다" % field)
    return {"category": parsed["category"].strip(), "summary": parsed["summary"].strip()}


# ── 근거 감사 ──────────────────────────────────────────────────────────

def _unit(vector):
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array)) or 1.0
    return array / norm


def audit_summary(generated, evidence_texts, encode,
                  supported_sim=SUPPORTED_SIM, uncertain_sim=UNCERTAIN_SIM):
    """생성 문장이 근거 발화와 얼마나 가까운지. 어휘가 아니라 의미로 잰다."""
    texts = [generated] + list(evidence_texts)
    vectors = [_unit(v) for v in encode(texts)]
    target, evidence = vectors[0], vectors[1:]
    if not evidence:
        return {"status": UNSUPPORTED, "max_similarity": 0.0,
                "threshold_supported": supported_sim, "threshold_uncertain": uncertain_sim,
                "reason": "근거 발화가 없다"}
    sims = [float(np.dot(target, vector)) for vector in evidence]
    best = max(sims)
    pooled = _unit(np.mean(np.stack(evidence), axis=0))
    pooled_sim = float(np.dot(target, pooled))
    score = max(best, pooled_sim)
    if score >= supported_sim:
        status, reason = SUPPORTED, "근거 발화와 의미가 가깝다(최대 %.3f)" % score
    elif score >= uncertain_sim:
        status, reason = UNCERTAIN, "근거와 부분적으로만 맞는다(최대 %.3f)" % score
    else:
        status, reason = UNSUPPORTED, "근거 발화에서 확인되지 않는다(최대 %.3f)" % score
    return {"status": status, "max_similarity": round(best, 4),
            "pooled_similarity": round(pooled_sim, 4),
            "threshold_supported": supported_sim, "threshold_uncertain": uncertain_sim,
            "reason": reason}


def unsupported_numbers(generated, evidence_texts):
    """생성문의 수치가 근거에 있는지. 임베딩은 숫자를 구분하지 못하므로 따로 본다."""
    flat = re.sub(r"\s+", "", " ".join(evidence_texts))
    missing = []
    for token in _NUMBER.findall(generated or ""):
        compact = re.sub(r"\s+", "", token)
        if compact and compact not in flat:
            digits = re.sub(r"[^\d.,]", "", compact)
            if digits and digits in flat:
                continue
            missing.append(compact)
    return missing


def audit_event(event, utterances, generated, encode, visual_claim_ids=None):
    texts = [u["text"] for u in utterances]
    result = audit_summary(generated, texts, encode)
    return {
        "id": event.get("speech_event_id") or event.get("event_id") or event.get("chapter_id"),
        "generated": generated,
        "supporting_utterance_ids": [u["id"] for u in utterances],
        "visual_claim_ids": list(visual_claim_ids or []),
        "status": result["status"],
        "reason": result["reason"],
        "max_similarity": result["max_similarity"],
        "pooled_similarity": result.get("pooled_similarity"),
        "unsupported_numbers": unsupported_numbers(generated, texts),
    }


def audit_counts(entries):
    counts = {SUPPORTED: 0, UNCERTAIN: 0, UNSUPPORTED: 0}
    for entry in entries:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    return counts


# ── 진단 ───────────────────────────────────────────────────────────────

def event_diagnostic(event, utterances, encode, long_event_sec=LONG_EVENT_SEC):
    """긴 구간이 실제로 하나의 주제인지 볼 수 있는 값들. 여기서 split하지 않는다."""
    duration = round(event["end"] - event["start"], 2)
    texts = [u["text"] for u in utterances]
    diagnostic = {
        "id": event.get("speech_event_id") or event.get("event_id"),
        "start": event["start"], "end": event["end"], "duration": duration,
        "utterance_count": len(utterances),
        "internal_cohesion": None, "half_similarity": None, "flag": None,
    }
    if len(texts) >= 2:
        vectors = np.stack([_unit(v) for v in encode(texts)])
        pairs = [float(np.dot(vectors[i], vectors[j]))
                 for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
        diagnostic["internal_cohesion"] = round(float(np.mean(pairs)), 4)
        middle = len(vectors) // 2
        first = _unit(vectors[:middle].mean(axis=0)) if middle else None
        second = _unit(vectors[middle:].mean(axis=0))
        if first is not None:
            diagnostic["half_similarity"] = round(float(np.dot(first, second)), 4)
    if duration > long_event_sec:
        diagnostic["flag"] = LONG_EVENT_DIAGNOSTIC
    return diagnostic


def chapter_diagnostic(chapter, events):
    index = {e["event_id"]: e for e in events}
    members = [index[eid] for eid in chapter["event_ids"] if eid in index]
    speech = sum(1 for m in members if m.get("speech_event_ids"))
    visual = sum(1 for m in members if m.get("visual_event_ids"))
    return {
        "chapter_id": chapter["chapter_id"],
        "duration": chapter.get("duration", round(chapter["end"] - chapter["start"], 2)),
        "member_events": len(members),
        "speech_events": speech,
        "visual_events": visual,
        "evidence_types": chapter.get("evidence_types", []),
        "flag": LOW_ADDED_VALUE if len(members) <= 1 else None,
    }


def row_redundancy(rows, encode, threshold=REDUNDANT_SIM):
    """같은 말을 반복하는 행을 표시한다. 행을 삭제하지는 않는다."""
    if not rows:
        return []
    vectors = [_unit(v) for v in encode([r.get("summary", "") for r in rows])]
    out = []
    for index, row in enumerate(rows):
        duplicate, best = None, 0.0
        for earlier in range(index):
            similarity = float(np.dot(vectors[index], vectors[earlier]))
            if similarity > best:
                duplicate, best = rows[earlier]["row_id"], similarity
        out.append({
            "row_id": row["row_id"],
            "duplicate_of": duplicate if best >= threshold else None,
            "max_similarity_to_earlier": round(best, 4),
            "unique_information": not (best >= threshold),
        })
    return out
