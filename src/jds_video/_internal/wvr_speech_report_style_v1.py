"""발화 근거 → 사용자가 읽는 보고서 문장. 전사를 그대로 내보내지 않는다.

```
Speech Event
   ↓ report-style semantic compression   생성(동결 모델) · 정보 제거는 하되 추가는 안 한다
   ↓ 기존 가드 전량                      언어 게이트 · claim 검증 · 역할/개체 · 수치
   ↓ 이 파일의 두 검사                   전사 복사(§7) · 보고 문체(§6)
PASS      → 보고서 문장
1회 재생성 → 보고서 문장
그래도 실패 → 안전한 범위 요약(category 범위 안) · 그것도 불가하면 음성 보류
```

**전사 원문은 fallback 문장이 아니다.** 원문은 근거로만 남고(sidecar · utterance id),
사용자 화면에는 "무엇을 말했는가"만 나간다. 전사를 숨기는 것이 목적이 아니라
**보고서와 근거를 분리**하는 것이 목적이다.

판정에 쓰는 것은 두 가지뿐이다.

```
구조   요약이 근거 발화를 얼마나 그대로 복사했는가 — 토큰 연속 일치·부분 문자열·이어붙임
문법   한국어 종결어미 · 1인칭 주어 형태 · 담화 표지 · 반복 (닫힌 문법 범주)
```

특정 영상의 낱말·주제·고유명사로 만든 목록은 없다. 내용어 blacklist를 두지 않는 이유는
그것이 다른 영상에서 곧바로 틀리기 때문이다(§6·§20).
"""
from __future__ import annotations

import re

from wvr_generative_guard_v1 import PASS as LANGUAGE_PASS
from wvr_generative_guard_v1 import language_gate
from wvr_report_composer_v2 import DISCOURSE_OPENERS, content_words, sentences
from wvr_report_composer_v2 import _with_particle as with_particle
from wvr_report_usability_v1 import GENERIC_CATEGORIES, lexically_supported, validate_category

# ── 표시 상태 ──────────────────────────────────────────────────────────

GENERATIVE_REPORT_SUMMARY = "GENERATIVE_REPORT_SUMMARY"
REGENERATED_REPORT_SUMMARY = "REGENERATED_REPORT_SUMMARY"
SAFE_BROAD_SUMMARY = "SAFE_BROAD_SUMMARY"
# 압축이 두 번 실패했는데 **이미 동결 가드를 통과해 쓰이고 있던** 요약이 보고 문체
# 조건까지 만족하면 그것을 유지한다. 원문 발췌가 아니라 같은 생성 계층의 문장이다.
# 이 단계가 없으면 이번 작업이 §27의 "정보가 거의 사라짐"을 스스로 만든다.
APPROVED_SUMMARY_RETAINED = "APPROVED_SUMMARY_RETAINED"
AUDIO_WITHHELD = "AUDIO_WITHHELD"
# 원문 발췌는 근거 계층의 이름이다 — 사용자 보고서 행이 아니다(§3).
EVIDENCE_EXTRACTIVE_ONLY = "EVIDENCE_EXTRACTIVE_ONLY"

APPROVED_REPORT_DISPLAYS = (GENERATIVE_REPORT_SUMMARY, REGENERATED_REPORT_SUMMARY,
                            APPROVED_SUMMARY_RETAINED, SAFE_BROAD_SUMMARY)

TRANSCRIPT_STYLE_PASS = "TRANSCRIPT_STYLE_PASS"
TRANSCRIPT_STYLE_FAIL = "TRANSCRIPT_STYLE_FAIL"

# ── 신호 이름 ──────────────────────────────────────────────────────────

SUMMARY_IS_UTTERANCE_SUBSTRING = "SUMMARY_IS_UTTERANCE_SUBSTRING"
LONG_VERBATIM_RUN = "LONG_VERBATIM_RUN"
CONCATENATED_UTTERANCES = "CONCATENATED_UTTERANCES"
HIGH_VERBATIM_RATIO = "HIGH_VERBATIM_RATIO"

CONVERSATIONAL_ENDING = "CONVERSATIONAL_ENDING"
NON_DECLARATIVE_ENDING = "NON_DECLARATIVE_ENDING"
INTERROGATIVE = "INTERROGATIVE"
FIRST_PERSON_SUBJECT = "FIRST_PERSON_SUBJECT"
FILLER_OPENER = "FILLER_OPENER"
INTERNAL_REPETITION = "INTERNAL_REPETITION"

LEAKAGE_SIGNALS = (SUMMARY_IS_UTTERANCE_SUBSTRING, LONG_VERBATIM_RUN,
                   CONCATENATED_UTTERANCES, HIGH_VERBATIM_RATIO)
STYLE_SIGNALS = (CONVERSATIONAL_ENDING, NON_DECLARATIVE_ENDING, INTERROGATIVE,
                 FIRST_PERSON_SUBJECT, FILLER_OPENER, INTERNAL_REPETITION)

# ── 임계 ───────────────────────────────────────────────────────────────
# 전부 **토큰 개수**다. 어떤 낱말인지는 보지 않는다.

VERBATIM_RUN_TOKENS = 7        # 이만큼 연달아 같으면 문장을 옮긴 것이다
CONCAT_RUN_TOKENS = 5          # 서로 다른 발화에서 이만큼씩 오면 이어 붙인 것이다
VERBATIM_RATIO_RUN = 4         # 비율을 잴 때 "복사"로 셀 최소 연속 길이
VERBATIM_RATIO = 0.85          # 요약의 이 비율 이상이 복사면 압축이 아니다
SUBSTRING_MIN_TOKENS = 4       # 너무 짧은 문장은 우연히 포함될 수 있다
REPEAT_NGRAM_TOKENS = 3        # 같은 연속 낱말이 두 번 나오면 반복이다

SAFE_BROAD_TEMPLATE_WORDS = ("관련된", "내용을", "다룬다")

# 1인칭 **주어** 형태(대명사 + 격조사). 대명사는 닫힌 문법 범주다.
FIRST_PERSON_SUBJECTS = ("제가", "저는", "저도", "저희는", "저희가", "저희도",
                         "내가", "나는", "나도", "우리는", "우리가")
# 의문형 종결어미. 낱말이 아니라 어미다.
INTERROGATIVE_ENDINGS = ("까", "까요", "나요", "니", "냐", "런가", "인가", "ㄹ까")
DECLARATIVE_ENDING = "다"      # 서술형 종결어미(§5)
POLITE_ENDING = "요"           # 해요체 종결어미

_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|퍼센트|[가-힣]{1,2})?")
_TRAILING_MARKS = " \t.!?…·,\"'“”‘’)]}"


def tokens(text):
    return _TOKEN.findall(text or "")


def _compact(text):
    return "".join(tokens(text))


def _numbers(text):
    return [re.sub(r"\s+", "", m) for m in _NUMBER.findall(text or "")]


# ── 전사 복사 검사(§7) ────────────────────────────────────────────────

def _runs_against(summary_tokens, source_tokens):
    """요약 토큰이 한 발화와 연속으로 몇 개까지 일치하는가.

    낱말의 뜻은 보지 않는다 — 위치와 길이만 센다. 고유명사·수치가 겹치는 것은
    길이가 짧아 신호가 되지 않는다(§7 단서).
    """
    if not summary_tokens or not source_tokens:
        return 0, set()
    width = len(source_tokens) + 1
    previous = [0] * width
    best, covered = 0, set()
    for i, token in enumerate(summary_tokens):
        current = [0] * width
        for j, other in enumerate(source_tokens):
            if token != other:
                continue
            length = previous[j] + 1
            current[j + 1] = length
            if length >= VERBATIM_RATIO_RUN:
                covered.update(range(i - length + 1, i + 1))
            best = max(best, length)
        previous = current
    return best, covered


def leakage_audit(summary, utterance_texts):
    """요약이 발화 원문을 그대로 옮겼는가. 결정적이고 임계는 토큰 개수뿐이다."""
    summary_tokens = tokens(summary)
    sources = [tokens(text) for text in (utterance_texts or [])]
    signals, per_source, covered = [], [], set()
    longest = 0
    compact_summary = _compact(summary)

    for index, source in enumerate(sources):
        run, hits = _runs_against(summary_tokens, source)
        per_source.append(run)
        covered |= hits
        longest = max(longest, run)
        if (compact_summary and len(summary_tokens) >= SUBSTRING_MIN_TOKENS
                and compact_summary in _compact(utterance_texts[index])):
            if SUMMARY_IS_UTTERANCE_SUBSTRING not in signals:
                signals.append(SUMMARY_IS_UTTERANCE_SUBSTRING)

    if longest >= VERBATIM_RUN_TOKENS:
        signals.append(LONG_VERBATIM_RUN)
    if sum(1 for run in per_source if run >= CONCAT_RUN_TOKENS) >= 2:
        signals.append(CONCATENATED_UTTERANCES)
    ratio = (len(covered) / len(summary_tokens)) if summary_tokens else 0.0
    if summary_tokens and ratio >= VERBATIM_RATIO:
        signals.append(HIGH_VERBATIM_RATIO)

    return {"signals": signals, "longest_run": longest,
            "verbatim_ratio": round(ratio, 3),
            "runs_per_utterance": per_source}


# ── 보고 문체 검사(§6) ────────────────────────────────────────────────

def _core(sentence):
    return (sentence or "").strip().strip(_TRAILING_MARKS)


def _last_eojeol(sentence):
    parts = _core(sentence).split()
    return parts[-1] if parts else ""


def _repeated_ngram(items, size=REPEAT_NGRAM_TOKENS):
    seen = set()
    for index in range(len(items) - size + 1):
        gram = tuple(items[index:index + size])
        if gram in seen:
            return " ".join(gram)
        seen.add(gram)
    return None


def style_audit(summary):
    """보고서 문장으로 읽히는가. 어미·대명사·담화 표지 같은 **문법 범주**만 본다."""
    text = (summary or "").strip()
    items = sentences(text)
    signals, detail = [], {}
    if not text:
        return {"signals": [NON_DECLARATIVE_ENDING], "sentence_count": 0,
                "detail": {"empty": True}}

    endings = [_last_eojeol(s) for s in items]
    detail["endings"] = endings
    if any("?" in s for s in items) or any(
            end.endswith(INTERROGATIVE_ENDINGS) for end in endings):
        signals.append(INTERROGATIVE)
    if any(end.endswith(POLITE_ENDING) for end in endings):
        signals.append(CONVERSATIONAL_ENDING)
    if any(not end.endswith(DECLARATIVE_ENDING) for end in endings):
        signals.append(NON_DECLARATIVE_ENDING)

    words = tokens(text)
    first_person = [w for w in words if w in FIRST_PERSON_SUBJECTS]
    if first_person:
        signals.append(FIRST_PERSON_SUBJECT)
        detail["first_person"] = sorted(set(first_person))

    opener = (items[0].split()[0].strip(_TRAILING_MARKS) if items and items[0].split() else "")
    if opener in DISCOURSE_OPENERS:
        signals.append(FILLER_OPENER)
        detail["opener"] = opener

    normalized = [" ".join(tokens(s)) for s in items]
    repeated_sentence = len(normalized) != len(set(normalized))
    repeated_gram = _repeated_ngram(words)
    if repeated_sentence or repeated_gram:
        signals.append(INTERNAL_REPETITION)
        detail["repeated"] = repeated_gram or "문장 반복"

    return {"signals": signals, "sentence_count": len(items), "detail": detail}


def audit_report_style(summary, utterance_texts):
    """전사 복사 + 문체를 한 번에 본다. 하나라도 걸리면 그 문장은 쓰지 않는다."""
    if not (summary or "").strip():
        return {"status": TRANSCRIPT_STYLE_FAIL, "signals": [NON_DECLARATIVE_ENDING],
                "leakage": {"signals": [], "longest_run": 0, "verbatim_ratio": 0.0,
                            "runs_per_utterance": []},
                "style": {"signals": [NON_DECLARATIVE_ENDING], "sentence_count": 0,
                          "detail": {"empty": True}}}
    leakage = leakage_audit(summary, utterance_texts)
    style = style_audit(summary)
    signals = leakage["signals"] + style["signals"]
    return {"status": TRANSCRIPT_STYLE_FAIL if signals else TRANSCRIPT_STYLE_PASS,
            "signals": signals, "leakage": leakage, "style": style}


# ── 안전한 범위 요약(§14) ─────────────────────────────────────────────

def category_is_safe(category, evidence_texts, approved=False):
    """구분 자체가 안전하게 확인되는가 — 이것 없이는 범위 요약도 만들지 않는다.

    `approved`는 **동결 파이프라인이 이미 승인한 구분**이라는 뜻이다. 그 경우 어휘
    일치를 다시 요구하지 않는다 — `choose_episode_category`의 동결 규칙과 같다.
    거부된 출력에서 나온 구분은 어휘 근거가 있어야 쓴다.
    """
    value = (category or "").strip()
    if not value:
        return {"ok": False, "reason": "구분이 없다"}
    if value in GENERIC_CATEGORIES:
        return {"ok": False, "reason": "내용 없는 구분"}
    if language_gate(value)["status"] != LANGUAGE_PASS:
        return {"ok": False, "reason": "한국어 표기가 아니다"}
    verdict = validate_category(value)
    if not verdict["ok"]:
        return {"ok": False, "reason": verdict["reason"]}
    if not approved and not lexically_supported(value, list(evidence_texts or [])):
        return {"ok": False, "reason": "근거 발화가 구분을 뒷받침하지 않는다"}
    return {"ok": True, "reason": "확인된 구분"}


def safe_broad_summary(category):
    """구분 범위를 넘지 않는 한 문장. 새 사실을 한 낱말도 더하지 않는다."""
    head = with_particle((category or "").strip(), "과", "와")
    return "%s %s." % (head, " ".join(SAFE_BROAD_TEMPLATE_WORDS))


# ── 단계별 결정(§2) ───────────────────────────────────────────────────

def resolve_decision(attempts, category_candidates, evidence_texts):
    """생성 → 1회 재생성 → (이미 승인된 요약 유지) → 범위 요약 → 보류.

    **원문 발췌는 어느 단계에도 없다**(§3). 각 시도는 `decision`으로 자기 이름을
    정할 수 있고, 없으면 순서대로 생성/재생성으로 본다.
    """
    records = [list(attempt.get("reasons") or []) for attempt in attempts]
    for index, attempt in enumerate(attempts):
        text = (attempt.get("summary") or "").strip()
        if attempt.get("approved") and text:
            return {"decision": attempt.get("decision") or (
                        GENERATIVE_REPORT_SUMMARY if index == 0
                        else REGENERATED_REPORT_SUMMARY),
                    "summary": text, "category": attempt.get("category"),
                    "attempt_index": index, "attempt_reasons": records,
                    "reason": "가드를 모두 통과했다"}
    for candidate in category_candidates or []:
        name = candidate.get("category") if isinstance(candidate, dict) else candidate
        approved = bool(candidate.get("approved")) if isinstance(candidate, dict) else False
        verdict = category_is_safe(name, evidence_texts, approved=approved)
        if verdict["ok"]:
            return {"decision": SAFE_BROAD_SUMMARY,
                    "summary": safe_broad_summary(name), "category": name,
                    "attempt_index": None, "attempt_reasons": records,
                    "reason": "생성이 두 번 실패해 구분 범위 안에서만 썼다"}
    return {"decision": AUDIO_WITHHELD, "summary": None, "category": None,
            "attempt_index": None, "attempt_reasons": records,
            "reason": "구분조차 안전하게 확인되지 않아 음성을 내렸다"}


# ── 정보 손실 확인(§23) ───────────────────────────────────────────────

def information_retention(after, before, evidence_texts):
    """짧아진 것과 없어진 것을 가른다. 판정이 아니라 측정이다."""
    after_words = set(content_words(after))
    before_words = content_words(before)
    evidence_flat = _compact(" ".join(evidence_texts or []))
    compact_after = _compact(after)
    dropped = [number for number in _numbers(before)
               if _compact(number) and _compact(number) not in compact_after]
    grounded = [word for word in after_words if word in evidence_flat]
    return {
        "topic_retention": round(
            len(after_words & set(before_words)) / len(set(before_words)), 3)
        if before_words else 0.0,
        "content_grounding": round(len(grounded) / len(after_words), 3) if after_words else 0.0,
        "dropped_numbers": dropped,
        "numbers_before": _numbers(before),
        "numbers_after": _numbers(after),
        "chars_before": len(before or ""),
        "chars_after": len(after or ""),
    }


def style_counts(records):
    """행 감사 결과를 상태별로 센다."""
    counts = {}
    for record in records:
        counts[record.get("status")] = counts.get(record.get("status"), 0) + 1
    return counts
