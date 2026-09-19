"""안전한 fallback + 자막 크레딧 필터 — downstream 표시 판단만 바꾼다.

```
문제 A  생성문을 "근거가 의심스럽다"는 이유로 막아 놓고, 그 의심스러운 원문을
        추출식으로 다시 보여주고 있었다. 안전 논리가 스스로를 뒤집는 자리다.
문제 B  자막 크레딧 환각("한글자막 by …")이 보고서 첫 행으로 올라왔다.
        기존 canonical 필터가 이 경로에 연결돼 있지 않았다.
```

실패를 원인별로 가른다.

```
표현 문제   언어 이탈 · 근거 없는 주장 · 새 역할/개체   → 추출식으로 되돌린다(근거는 멀쩡하다)
근거 문제   강한 ASR 이상에 기대고 있다                 → 음성을 화면에서 내린다
            화면 근거가 있으면                          → 화면 서술만으로 내려 쓴다
            없으면                                      → 행을 보여주지 않는다
```

**숨기는 것은 표시일 뿐 근거가 아니다** — utterance id·진단·사유는 sidecar에 남는다.
임계는 기존 모듈 정의를 그대로 가져온다. 이 파일에서 숫자를 만들지 않는다.
"""
from __future__ import annotations

import re

from wvr_grounding_guard_v1 import ASR_LOW_CONFIDENCE, ASR_REPETITION_ANOMALY

GENERATIVE = "GENERATIVE"
REGENERATED = "REGENERATED"
EXTRACTIVE_FALLBACK = "EXTRACTIVE_FALLBACK"
AUDIO_WITHHELD_ASR_UNRELIABLE = "AUDIO_WITHHELD_ASR_UNRELIABLE"
VISUAL_ONLY_DOWNGRADE = "VISUAL_ONLY_DOWNGRADE"
NON_REPORTABLE_EVENT = "NON_REPORTABLE_EVENT"
NON_REPORTABLE_SUBTITLE_CREDIT = "NON_REPORTABLE_SUBTITLE_CREDIT"

STRONG_ASR_STATES = (ASR_REPETITION_ANOMALY, ASR_LOW_CONFIDENCE)
SOURCE_FAILURE_REASONS = ("STT_ANOMALY_DEPENDENCY",)
EXPRESSION_FAILURE_REASONS = ("LANGUAGE_GATE_FAIL", "UNSUPPORTED_CLAIM", "UNSUPPORTED_NUMBER",
                              "NOVEL_ROLE", "NOVEL_ENTITY", "UNCERTAIN")


def subtitle_credit_flags(utterances):
    """canonical 판정(`common.is_subtitle_credit`)을 그대로 쓴다. 새 정규식을 만들지 않는다."""
    from common import is_subtitle_credit

    return {u["id"]: bool(is_subtitle_credit(u.get("text", ""))) for u in utterances}


def reportable_utterances(utterances, subtitle_flags):
    return [u for u in utterances if not subtitle_flags.get(u["id"])]


def _strip_credit_lines(text, utterances, subtitle_flags):
    """추출식 문장에 섞인 자막 크레딧 조각을 걷어낸다."""
    cleaned = text or ""
    for utterance in utterances:
        if subtitle_flags.get(utterance["id"]):
            cleaned = cleaned.replace(utterance.get("text", ""), " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def depends_on_strong_anomaly(utterances, asr_states, subtitle_flags=None):
    """보고 가능한 근거 중 강한 ASR 이상이 차지하는 비중."""
    items = reportable_utterances(utterances, subtitle_flags or {})
    if not items:
        return {"ratio": 0.0, "strong": False, "counts": {}}
    counts = {}
    strong = 0
    for utterance in items:
        state = asr_states.get(utterance["id"], "ASR_UNRESOLVED")
        counts[state] = counts.get(state, 0) + 1
        if state in STRONG_ASR_STATES:
            strong += 1
    ratio = strong / len(items)
    return {"ratio": round(ratio, 3), "strong": strong > 0 and strong == len(items),
            "counts": counts}


def display_decision(approved, reasons, generated, extractive, utterances,
                     subtitle_flags, asr_states, visual_summary,
                     summary_source=None):
    """행을 어떻게 보여줄지 정한다. 근거는 어느 경우에도 지우지 않는다."""
    utterance_ids = [u["id"] for u in utterances]
    base = {"utterance_ids": utterance_ids,
            "subtitle_credit_ids": [uid for uid in utterance_ids
                                    if subtitle_flags.get(uid)]}

    usable = reportable_utterances(utterances, subtitle_flags)
    if utterances and not usable:
        return {**base, "display": NON_REPORTABLE_EVENT, "summary": None,
                "evidence": None,
                "reason": "구성 발화가 모두 자막 크레딧이라 보고 내용이 없다"}

    if approved and (generated or "").strip():
        return {**base, "display": summary_source or GENERATIVE,
                "summary": generated, "evidence": "음성",
                "reason": "가드를 모두 통과했다"}

    anomaly = depends_on_strong_anomaly(utterances, asr_states, subtitle_flags)
    source_problem = (any(reason in SOURCE_FAILURE_REASONS for reason in reasons)
                      or anomaly["strong"])
    unknown_reason = bool(reasons) and not any(
        reason in SOURCE_FAILURE_REASONS or reason in EXPRESSION_FAILURE_REASONS
        for reason in reasons)

    if source_problem or (unknown_reason and anomaly["ratio"] > 0):
        if (visual_summary or "").strip():
            return {**base, "display": VISUAL_ONLY_DOWNGRADE,
                    "summary": visual_summary.strip(), "evidence": "화면",
                    "reason": "음성 근거가 신뢰 불가라 화면 근거만으로 낮춰 썼다",
                    "asr": anomaly}
        return {**base, "display": AUDIO_WITHHELD_ASR_UNRELIABLE, "summary": None,
                "evidence": None,
                "reason": "음성 근거가 신뢰 불가하고 대체할 화면 근거가 없다",
                "asr": anomaly}

    cleaned = _strip_credit_lines(extractive, utterances, subtitle_flags)
    if not cleaned:
        return {**base, "display": NON_REPORTABLE_EVENT, "summary": None,
                "evidence": None, "reason": "보여줄 원문이 남지 않았다"}
    return {**base, "display": EXTRACTIVE_FALLBACK, "summary": cleaned, "evidence": "음성",
            "reason": "생성 표현에만 문제가 있어 원문 발췌로 되돌렸다", "asr": anomaly}


def overview_input_texts(rows):
    """개요·제목 입력 — 화면에 실제로 나가는 문장만 넘긴다(§12)."""
    blocked = {AUDIO_WITHHELD_ASR_UNRELIABLE, NON_REPORTABLE_EVENT,
               NON_REPORTABLE_SUBTITLE_CREDIT}
    return [row["summary"] for row in rows
            if row.get("summary") and row.get("display") not in blocked]


def display_counts(rows):
    counts = {}
    for row in rows:
        counts[row.get("display")] = counts.get(row.get("display"), 0) + 1
    return counts
