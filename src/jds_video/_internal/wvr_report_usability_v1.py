"""보고서 가독성 마무리 — 사용자-facing 표현 계층만 손댄다.

```
문제 1  구분 칸에 "선택하실"·"사라다"·"이거"·"동안"처럼 내용 없는 낱말이 온다
        (derive_category가 발화에서 가장 자주 나온 낱말 하나를 뽑는다)
문제 2  한국어 문장 사이에 근거에 없는 영어 낱말이 끼어든다("various 정책")
문제 3  인접·겹치는 구간에서 같은 문장이 두 번 나온다
```

**의미 구조는 건드리지 않는다** — STT·경계·관계·chapter·요약 모델·가드는 모두 동결이다.
새 추론도 기본 0회다. 구분 칸은 **이미 생성돼 있던 요약의 category 필드**를 읽어 쓴다.

```
category 우선순위   ① 승인된 생성 요약의 category      ② 근거로 뒷받침되는 기존 구분
                    ③ 검증된 broad_activity 표시 라벨   ④ 중립 라벨
중복 정리           겹치는 구간 안에서만. 멀리 떨어진 같은 활동은 합치지 않는다
숨김 ≠ 삭제         원행·근거·id는 sidecar에 남는다
```
"""
from __future__ import annotations

import re

from wvr_display_sanitize_v1 import ACTIVITY_DISPLAY_LABEL, script_clean

PASS = "PASS"
FAIL = "FAIL"
DISPLAY_LANGUAGE_MIX_FAIL = "DISPLAY_LANGUAGE_MIX_FAIL"

FROM_GENERATIVE = "APPROVED_GENERATIVE_CATEGORY"
FROM_EXISTING = "EVIDENCE_SUPPORTED_EXISTING"
FROM_ACTIVITY = "VERIFIED_BROAD_ACTIVITY"
FROM_NEUTRAL = "NEUTRAL_FALLBACK"

NEUTRAL_SPEECH = "음성 내용"
NEUTRAL_VISUAL = "화면 활동"
GENERIC_CATEGORIES = ("관찰 장면",)

EXACT_DUPLICATE_OVERLAP = "EXACT_DUPLICATE_OVERLAP"
CONTAINED_IN_OVERLAPPING_ROW = "CONTAINED_IN_OVERLAPPING_ROW"
GENERIC_VISUAL_COVERED_BY_AUDIO = "GENERIC_VISUAL_COVERED_BY_AUDIO"

MAX_CATEGORY_CHARS = 16        # "채불 문제 해결 방안"처럼 정상 명사구가 걸리지 않을 만큼만 준다
MAX_CATEGORY_WORDS = 4
MIN_CATEGORY_CHARS = 2
# 영상 전체가 같은 activity면 그 라벨은 행을 구분하지 못한다 — 중립 라벨을 쓴다.
MIN_DISTINCT_ACTIVITIES = 2

# 대명사·접속어·시간 부사처럼 내용이 없는 낱말. 지시 대상이 없어 구분으로 쓸 수 없다.
BANNED_CATEGORIES = {
    "이거", "저거", "그거", "이것", "저것", "그것", "여기", "거기", "저기",
    "동안", "하지만", "그래서", "그런데", "그리고", "아까", "너무", "정말", "사실",
    "지금", "오늘", "다음", "먼저", "마지막", "즉시", "우리", "저희", "제가", "여러분",
    "발언", "말씀", "생각", "경우", "부분", "정도", "이번", "하나", "때문",
}
# 어미·조사로 끝나면 명사구가 아니다.
_TAIL_FORBIDDEN = (
    "습니다", "했습니다", "합니다", "입니다", "니다", "같아요", "어요", "아요", "해요",
    "예요", "에요", "이죠", "거든요", "잖아요", "네요", "세요", "구요",
    "하실", "하는", "하고", "해서", "하며", "으며", "지만", "는데", "면서",
    "에서", "으로", "부터", "까지", "보다", "처럼", "라고", "이라", "이고",
    "한다", "된다", "있다", "없다", "였다", "이다", "든지", "거나",
)
_WORD = re.compile(r"[가-힣A-Za-z0-9]+")
_LATIN = re.compile(r"[A-Za-z]{2,}")
_SENTENCE_MARK = re.compile(r"[.!?]")
# §11-C가 열거한 "내용 없는 화면 서술" — 말하기·발표·화면 보기.
_GENERIC_VISUAL = (
    "말하고", "말한다", "말하며", "말하는", "발표를", "발표하", "발언하",
    "화면을 보", "화면에 표시된", "마이크 앞에서",
)


# ── 구분(category) ─────────────────────────────────────────────────────

def _words(text):
    return _WORD.findall(text or "")


def validate_category(text):
    """구분 칸에 그대로 내보낼 수 있는 한국어 명사구인가."""
    value = (text or "").strip()
    if not value:
        return {"ok": False, "reason": "빈 값"}
    if _SENTENCE_MARK.search(value):
        return {"ok": False, "reason": "문장이다"}
    if not (MIN_CATEGORY_CHARS <= len(value) <= MAX_CATEGORY_CHARS):
        return {"ok": False, "reason": "길이 %d" % len(value)}
    if len(value.split()) > MAX_CATEGORY_WORDS:
        return {"ok": False, "reason": "어절이 많다"}
    if not script_clean(value):
        return {"ok": False, "reason": "한국어 표기가 아니다"}
    for word in value.split():
        if word in BANNED_CATEGORIES:
            return {"ok": False, "reason": "내용 없는 낱말(%s)" % word}
    if value.split()[-1].endswith(_TAIL_FORBIDDEN):
        return {"ok": False, "reason": "어미·조사로 끝난다"}
    return {"ok": True, "reason": "명사구"}


def lexically_supported(category, texts):
    """구분의 내용어가 표시 문장에 실제로 나오는가 — 새 사실 유입을 막는다."""
    haystack = " ".join(t for t in texts if t)
    return any(word in haystack for word in _words(category) if len(word) >= 2)


def choose_category(generative_category, display, summary, existing_category, evidence,
                    broad_activity=(), activity_labels_useful=True):
    """우선순위대로 구분을 정한다. 새 개념을 만들지 않는다."""
    approved = display in ("GENERATIVE", "REGENERATED")
    speech_displayed = evidence in ("음성", "음성+화면")
    neutral = NEUTRAL_SPEECH if speech_displayed else NEUTRAL_VISUAL

    candidate = (generative_category or "").strip()
    # 음성을 내린 행(화면 강등·보류)에서는 그 음성에서 나온 구분도 쓰지 않는다.
    # 표시에서 뺀 근거가 라벨로 되살아나면 안전 판단이 무의미해진다.
    if candidate and speech_displayed and validate_category(candidate)["ok"]:
        # 생성 요약이 막힌 행은 그 요약에서 나온 구분도 그대로 믿지 않는다.
        if approved or lexically_supported(candidate, [summary]):
            return {"category": candidate, "source": FROM_GENERATIVE,
                    "reason": "승인된 생성 구분" if approved else "표시 문장이 뒷받침한다"}

    existing = (existing_category or "").strip()
    if (existing and existing not in GENERIC_CATEGORIES
            and validate_category(existing)["ok"]
            and lexically_supported(existing, [summary])):
        return {"category": existing, "source": FROM_EXISTING,
                "reason": "기존 구분이 표시 문장에 나온다"}

    if activity_labels_useful:
        for activity in (broad_activity or []):
            label = ACTIVITY_DISPLAY_LABEL.get(str(activity).strip().upper())
            if label:
                return {"category": label, "source": FROM_ACTIVITY,
                        "reason": "검증된 상위 활동(%s)" % activity}

    return {"category": neutral, "source": FROM_NEUTRAL,
            "reason": "안전한 구분 후보가 없다"}


def activity_labels_discriminate(all_broad_activities):
    """영상 안에서 activity 라벨이 행을 실제로 구분하는가."""
    distinct = {str(a).strip().upper() for group in all_broad_activities for a in (group or [])}
    return len(distinct) >= MIN_DISTINCT_ACTIVITIES


# ── 라틴 문자 표시 검사 ────────────────────────────────────────────────

def _is_acronym(token):
    return token.isupper() and 2 <= len(token) <= 6


def display_language_check(summary, evidence_texts):
    """근거에 없는 일반 영어 낱말이 한국어 문장에 섞였는가.

    약어·고유명사·근거에 실제로 있는 표기는 통과시킨다. 번역하지 않는다 —
    걸리면 그 문장을 쓰지 않을 뿐이다.
    """
    text = summary or ""
    haystack = " ".join(evidence_texts or []).lower()
    bad = []
    for token in _LATIN.findall(text):
        if _is_acronym(token) or token.lower() in haystack:
            continue
        bad.append(token)
    if bad:
        return {"status": FAIL, "reason_code": DISPLAY_LANGUAGE_MIX_FAIL, "tokens": bad,
                "reason": "근거에 없는 영어 낱말: %s" % ", ".join(bad)}
    return {"status": PASS, "tokens": [], "reason": "표기 정상"}


# ── 중복 정리 (겹치는 구간 안에서만) ───────────────────────────────────

def _normalize(text):
    return " ".join(_words(text))


def _overlaps(a, b):
    return min(a["end"], b["end"]) > max(a["start"], b["start"])


def is_generic_visual(summary):
    text = (summary or "").strip()
    return any(mark in text for mark in _GENERIC_VISUAL)


def reduce_redundancy(rows):
    """겹치는 구간 안에서 정보를 더하지 않는 행만 접는다. 행을 새로 만들지 않는다."""
    ordered = sorted(rows, key=lambda r: (r["start"], -(r["end"] - r["start"]), r["row_id"]))
    normalized = {r["row_id"]: _normalize(r["summary"]) for r in ordered}
    token_sets = {r["row_id"]: set(_words(r["summary"])) for r in ordered}
    # 음성 행은 발화 **내용** 요약이지 장면 묘사가 아니다. 여기에 화면 서술용 판정을 걸면
    # "정책을 발표하였으며" 같은 정상 문장이 내용 없는 행으로 잘못 걸린다(실측).
    informative_audio = [r for r in ordered if r["evidence"] in ("음성", "음성+화면")]

    kept, suppressed = [], []
    for row in ordered:
        rid = row["row_id"]
        decision = None
        for other in ordered:
            if other["row_id"] == rid or not _overlaps(row, other):
                continue
            longer = (other["end"] - other["start"]) > (row["end"] - row["start"])
            same_span = (other["end"] - other["start"]) == (row["end"] - row["start"])
            if normalized[other["row_id"]] == normalized[rid] and (
                    longer or (same_span and other["start"] < row["start"])):
                decision = (EXACT_DUPLICATE_OVERLAP, other["row_id"])
                break
            if (token_sets[rid] and token_sets[rid] < token_sets[other["row_id"]]
                    and (longer or same_span)):
                decision = (CONTAINED_IN_OVERLAPPING_ROW, other["row_id"])
                break
        if decision is None and row["evidence"] == "화면" and is_generic_visual(row["summary"]):
            for other in informative_audio:
                if _overlaps(row, other):
                    decision = (GENERIC_VISUAL_COVERED_BY_AUDIO, other["row_id"])
                    break
        if decision:
            entry = dict(row)
            entry["suppressed"] = True
            entry["suppression_reason"] = decision[0]
            entry["suppressed_for"] = decision[1]
            suppressed.append(entry)
            continue
        kept.append(row)

    kept.sort(key=lambda r: (r["start"], r["end"], r["row_id"]))
    return kept, suppressed


def usability_counts(category_decisions, language_decisions, suppressed):
    sources = {}
    for record in category_decisions:
        sources[record["source"]] = sources.get(record["source"], 0) + 1
    reasons = {}
    for record in suppressed:
        reasons[record["suppression_reason"]] = reasons.get(record["suppression_reason"], 0) + 1
    return {"category_sources": sources,
            "category_invalid_input": sum(1 for r in category_decisions
                                          if not r.get("input_valid", True)),
            "language_mix_fail": sum(1 for r in language_decisions
                                     if r["status"] == FAIL),
            "suppressed": reasons}
