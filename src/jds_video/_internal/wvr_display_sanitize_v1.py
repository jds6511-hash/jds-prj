"""표시 계층 정화 — 원본 근거를 건드리지 않고 사용자 화면만 고친다.

```
문제 A  검증된 visual artifact 원문에 한자가 섞여 최종 보고서에 그대로 나갔다
        ("조리 도구에蛤蜊을 …"). 생성 경로가 아니라 VLM 원문이라 언어 게이트가 닿지 않았다
문제 B  ASR 정상 판정 구간의 추출식 fallback 안에 같은 낱말·구·문장이 이어서 반복된다
```

둘 다 semantic 문제가 아니라 **표시 위생** 문제로 다룬다.

```
원문 보존   visual claim · raw text · claim id · 구간 · 프레임 근거는 sidecar에 그대로
번역 금지   蛤蜊을 "조개"로 바꾸지 않는다. 외부·모델 지식으로 원문을 메우지 않는다
대체 순서   ① 같은 event의 깨끗한 한국어 category  ② 검증된 broad_activity 표시 라벨
            ③ 없으면 문장을 숨긴다(VISUAL_TEXT_WITHHELD_MIXED_SCRIPT)
반복 정리   **완전 일치 · 연속**만. 유사 문장(paraphrase)은 건드리지 않는다
```

언어 판정은 새로 만들지 않고 `wvr_generative_guard_v1.language_gate`를 그대로 쓴다.
"""
from __future__ import annotations

import re

from wvr_generative_guard_v1 import PASS, language_gate

ORIGINAL = "ORIGINAL"
SAFE_VISUAL_DOWNGRADE = "SAFE_VISUAL_DOWNGRADE"
VISUAL_TEXT_WITHHELD_MIXED_SCRIPT = "VISUAL_TEXT_WITHHELD_MIXED_SCRIPT"

# visual artifact의 닫힌 enum(`broad_activity`)에 붙이는 표시 라벨.
# 새 사실이 아니라 이미 검증된 상위 분류의 한국어 표기다 — 항목을 사례에 맞춰 늘리지 않는다.
ACTIVITY_DISPLAY_LABEL = {
    "FOOD_PREPARATION": "조리",
    "EATING": "식사",
    "TRAVEL_OR_MOVEMENT": "이동",
    "WORK_OR_STUDY": "작업",
    "SHOPPING_OR_BROWSING": "쇼핑",
    "CRAFT_REPAIR_OR_ASSEMBLY": "제작·수리",
}
# 내용이 없는 자리표시 분류 — 대체 문장으로 쓰지 않는다(행의 구분 칸과 같은 말이 된다).
GENERIC_CATEGORIES = ("관찰 장면",)
ACTIVITY_SUFFIX = " 활동"

MAX_PHRASE_TOKENS = 6          # 연속 반복을 볼 구(句)의 최대 길이
# 종결 부호 뒤에 공백이 올 때만 문장 경계로 본다 — "2.2%"를 자르지 않기 위해서다.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def activity_label(activity):
    return ACTIVITY_DISPLAY_LABEL.get(str(activity or "").strip().upper())


def script_clean(text):
    """사용자에게 나갈 문장인지 — 기존 언어 게이트를 그대로 쓴다."""
    return language_gate(text)["status"] == PASS


def sanitize_visual_text(text, category=None, broad_activity=()):
    """visual 원문을 표시용으로만 정한다. 원문은 결과에 그대로 담아 돌려준다."""
    raw = (text or "").strip()
    base = {"original_text": text, "display_text": raw or None}
    if raw and script_clean(raw):
        return {**base, "display_decision": ORIGINAL, "reason": "한국어 표기 정상"}

    gate = language_gate(raw)
    label = (category or "").strip()
    if label and label not in GENERIC_CATEGORIES and script_clean(label):
        return {**base, "display_decision": SAFE_VISUAL_DOWNGRADE, "display_text": label,
                "reason": "같은 event의 검증된 분류로 낮춰 표시했다(%s)" % gate.get("reason", "")}

    for activity in (broad_activity or []):
        name = activity_label(activity)
        if name:
            return {**base, "display_decision": SAFE_VISUAL_DOWNGRADE,
                    "display_text": name + ACTIVITY_SUFFIX,
                    "reason": "검증된 상위 활동(%s)까지만 표시했다(%s)"
                              % (activity, gate.get("reason", ""))}

    return {**base, "display_decision": VISUAL_TEXT_WITHHELD_MIXED_SCRIPT, "display_text": None,
            "reason": "대체할 깨끗한 한국어 표현이 없어 문장을 숨겼다(%s)" % gate.get("reason", "")}


# ── 연속·완전 일치 반복만 정리한다 ─────────────────────────────────────

def _sentences(text):
    return [p for p in _SENTENCE_SPLIT.split(text) if p.strip()]


def _dedup_sentences(text):
    parts, removed, kept = _sentences(text), [], []
    for part in parts:
        if kept and part.strip() == kept[-1].strip():
            if removed and removed[-1]["text"] == part.strip():
                removed[-1]["repeats"] += 1
            else:
                removed.append({"kind": "sentence", "text": part.strip(), "repeats": 1})
            continue
        kept.append(part)
    return " ".join(p.strip() for p in kept), removed


def _dedup_tokens(text):
    """짧은 단위부터 본다 — 긴 단위를 먼저 보면 낱말 4연속이 2연속으로만 줄어든다."""
    tokens, out, removed, index = text.split(), [], [], 0
    while index < len(tokens):
        collapsed = False
        for size in range(1, MAX_PHRASE_TOKENS + 1):
            block = tokens[index:index + size]
            if len(block) < size:
                break
            cursor, count = index + size, 1
            while tokens[cursor:cursor + size] == block:
                cursor += size
                count += 1
            if count > 1:
                out.extend(block)
                removed.append({"kind": "token" if size == 1 else "phrase",
                                "text": " ".join(block), "repeats": count - 1})
                index, collapsed = cursor, True
                break
        if not collapsed:
            out.append(tokens[index])
            index += 1
    return " ".join(out), removed


def dedup_local(text):
    """한 행 안의 **연속·완전 일치** 반복만 지운다. 의미 판단·재작성은 하지 않는다."""
    source = (text or "").strip()
    if not source:
        return {"text": "", "removed": [], "original_text": text}
    staged, removed = _dedup_sentences(source)
    staged, token_removed = _dedup_tokens(staged)
    return {"text": staged, "removed": removed + token_removed, "original_text": text}


def sanitation_counts(records):
    counts = {}
    for record in records:
        key = record.get("display_decision")
        counts[key] = counts.get(key, 0) + 1
    return counts
