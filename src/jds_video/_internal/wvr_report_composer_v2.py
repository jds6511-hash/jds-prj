"""Report Composer V2 — 검증된 event를 **사용자가 읽는 사건 단위**로 묶는 표시 계층.

```
Claim → Event → Chapter ─┐
                         ├→ Report Episode → Report Row
검증·융합 결과 (동결)    ┘   표시용 aggregation. 새 사실을 만들지 않는다
```

분석·융합 계층은 하나도 건드리지 않는다 — STT·경계·관계·multimodal event·chapter·
요약 모델·가드는 전부 읽기 전용이다. 이 파일이 하는 일은 넷뿐이다.

```
① 보고 가치 판정   CONTENT / META_CONTENT / FILLER / UNCLEAR
                   META·FILLER는 행을 만들지 않는다(근거는 sidecar에 남는다)
② 사건 구성       이미 SAME_EVENT·COMPLEMENTARY로 판정된 짝은 한 사건으로 표시한다.
                   INDEPENDENT는 절대 합치지 않는다 — 시간 포함은 의미 병합이 아니다
③ 표현 정리       전사 덩어리를 그대로 내보내지 않는다. 승인된 요약이 우선이다
④ 근거 감사       제목·개요의 표현마다 지지 episode를 붙인다. 없으면 쓰지 않는다
```

**특정 영상·단어·시간대에 대한 조건문은 한 줄도 없다.** 쓰는 속성은 evidence type,
temporal relation, 이미 판정된 semantic relation, provenance, reportability뿐이다.
"""
from __future__ import annotations

import re

from wvr_display_sanitize_v1 import ACTIVITY_DISPLAY_LABEL
from wvr_report_usability_v1 import (GENERIC_CATEGORIES, NEUTRAL_SPEECH, NEUTRAL_VISUAL,
                                     is_generic_visual, lexically_supported, validate_category)

CONTENT = "CONTENT"
META_CONTENT = "META_CONTENT"
FILLER = "FILLER"
UNCLEAR = "UNCLEAR"
REPORTABILITY_LABELS = (CONTENT, META_CONTENT, FILLER, UNCLEAR)
# UNCLEAR는 숨기지 않는다 — 판정이 안 서는 발화를 지우는 쪽이 더 위험하다.
NON_REPORTABLE_LABELS = (META_CONTENT, FILLER)

MAJOR = "MAJOR"
SUPPORTING = "SUPPORTING"
MINOR = "MINOR"

AUDIO = "음성"
VISUAL = "화면"
VISUAL_AUDIO = "음성+화면"

SUBORDINATE_VISUAL_DETAIL = "SUBORDINATE_VISUAL_DETAIL"
GENERIC_VISUAL_COVERED = "GENERIC_VISUAL_COVERED_BY_AUDIO"
DUPLICATE_OVERLAP = "DUPLICATE_OVERLAP"
NON_REPORTABLE_SPEECH = "NON_REPORTABLE_SPEECH"

# 담화 표지·군말. 한국어 기능어이지 특정 영상의 어휘가 아니다.
DISCOURSE_OPENERS = ("그렇지만", "그러니까", "그런데", "그래서", "어쨌든", "근데", "아니",
                     "저기", "이제", "아까", "뭐", "음", "어", "자")
# 근거 없이 쓰면 안 되는 부각 표현(추가 E). 수사(修辭)이지 내용어가 아니다.
PROMINENCE_TERMS = ("주도", "중점적", "핵심적", "강조", "주요 목표", "중심이다", "가장 중요",
                    "전반적으로 주도", "핵심이다")

MAX_ROW_CHARS = 220           # 이보다 길면 전사 덩어리로 본다(문장 수와 함께 판단한다)
MAX_ROW_SENTENCES = 3
MIN_TOPIC_SENTENCES = 2

_WORD = re.compile(r"[가-힣A-Za-z0-9]+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {"있습니다", "합니다", "했습니다", "하는", "것을", "것이", "대해", "위해", "관련",
              "그리고", "또한", "특히", "이를", "통해", "대한", "하고", "있다", "한다", "된다"}
# 앞 문장을 잇는 접속어로 시작하면 새 주제가 아니다 — 같은 안건의 세부 설명이다(추가 A).
_CONTINUATION = ("또한", "그리고", "이어서", "특히", "아울러", "한편", "게다가", "다만", "이때",
                 "그래서", "따라서", "이에")


def words(text):
    return _WORD.findall(text or "")


def content_words(text, min_len=2):
    return [w for w in words(text) if len(w) >= min_len and w not in _STOPWORDS and not w.isdigit()]


def sentences(text):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]


# ── ① 보고 가치 ────────────────────────────────────────────────────────

def normalize_reportability(raw_label):
    """모델이 돌려준 라벨을 정규화한다. 모르면 UNCLEAR — 숨기지 않는 쪽으로 넘긴다."""
    value = str(raw_label or "").strip().upper().replace("-", "_")
    return value if value in REPORTABILITY_LABELS else UNCLEAR


def is_reportable(label):
    return normalize_reportability(label) not in NON_REPORTABLE_LABELS


# ── ② 주제 분할 (표시 전용 · 실제 utterance 경계에서만) ────────────────

def _group_sentences(items):
    """내용어를 하나도 공유하지 않는 곳에서만 끊는다."""
    groups = []
    for sentence in items:
        tokens = set(content_words(sentence))
        continued = sentence.split()[0].startswith(_CONTINUATION) if sentence.split() else False
        if groups and (continued or (groups[-1]["tokens"] & tokens)):
            groups[-1]["sentences"].append(sentence)
            groups[-1]["tokens"] |= tokens
            continue
        groups.append({"sentences": [sentence], "tokens": set(tokens)})
    return groups


def split_summary_by_topic(summary, utterances):
    """승인된 요약을 주제별로 나눈다. **문장을 새로 만들지 않는다** — 원문을 나눠 쓴다.

    나눌 수 있는 조건이 하나라도 어긋나면 나누지 않는다(보수적).
    """
    items = sentences(summary)
    single = [{"summary": (summary or "").strip(),
               "utterance_ids": [u["id"] for u in utterances],
               "start": utterances[0]["start"] if utterances else None,
               "end": utterances[-1]["end"] if utterances else None,
               "split": False}]
    if len(items) < MIN_TOPIC_SENTENCES or not utterances:
        return single
    groups = _group_sentences(items)
    if len(groups) < 2:
        return single

    spans = []
    for group in groups:
        hits = [index for index, utterance in enumerate(utterances)
                if any(token in utterance.get("text", "") for token in group["tokens"])]
        if not hits:
            return single                        # 근거 구간을 못 찾으면 나누지 않는다
        spans.append((min(hits), max(hits)))
    for before, after in zip(spans, spans[1:]):
        if after[0] <= before[1]:
            return single                        # 구간이 겹치면 경계가 아니다
    out = []
    for group, (first, last) in zip(groups, spans):
        block = utterances[first:last + 1]
        out.append({"summary": " ".join(group["sentences"]),
                    "utterance_ids": [u["id"] for u in block],
                    "start": block[0]["start"], "end": block[-1]["end"], "split": True})
    return out


# ── ② 사건 구성 ────────────────────────────────────────────────────────

def modality_clause(visual_text, visual_start, visual_end, episode_start, episode_end):
    """화면 근거의 시간 범위가 사건 전체와 다르면 그 사실을 문장에 남긴다(§11)."""
    text = (visual_text or "").strip().rstrip(".")
    if not text:
        return None
    narrower = (visual_start is not None and visual_end is not None
                and (visual_start > episode_start or visual_end < episode_end))
    # 화면 서술은 완결된 문장일 수도, 명사구일 수도 있다. 어느 쪽이든 문법이 깨지지 않게
    # 별도 문장으로 덧붙인다 — 원문을 고쳐 쓰지 않는다.
    return ("일부 장면에서 확인된 내용: %s." % text if narrower
            else "화면에서 확인된 내용: %s." % text)


def compose_fused_summary(speech_summary, visual_clause):
    """융합 사건의 문장. 두 근거가 각각 지지하는 내용만 이어 붙인다 — 새 의미 합성 없음."""
    base = (speech_summary or "").strip()
    if not visual_clause:
        return base
    if not base:
        return visual_clause
    return "%s %s" % (base if base.endswith((".", "!", "?")) else base + ".", visual_clause)


def overlaps(a_start, a_end, b_start, b_end):
    return min(a_end, b_end) > max(a_start, b_start)


def contains(outer_start, outer_end, inner_start, inner_end):
    return outer_start <= inner_start and inner_end <= outer_end


def is_subordinate_visual(episode, containers):
    """상위 사건 안에 들어 있고 새 정보를 더하지 않는 짧은 화면 관찰인가.

    시간 포함만으로는 접지 않는다(§9) — **같은 화면 활동**이 이미 상위 사건의 근거로
    들어가 있을 때만 접는다. relation을 새로 판정하지 않는다.
    """
    if episode["evidence"] != VISUAL:
        return None
    tokens = set(content_words(episode["summary"]))
    span = episode["end"] - episode["start"]
    for other in containers:
        if other["episode_id"] == episode["episode_id"]:
            continue
        other_tokens = set(content_words(other["summary"]))
        other_span = other["end"] - other["start"]
        # 같은 문장이 겹쳐 있으면 긴 쪽만 남긴다(구간 포함까지는 요구하지 않는다)
        if (tokens and tokens == other_tokens
                and overlaps(episode["start"], episode["end"], other["start"], other["end"])
                and (other_span > span or (other_span == span
                                           and other["start"] < episode["start"]))):
            return (DUPLICATE_OVERLAP, other["episode_id"])
        # 내용 없는 화면 서술은 같은 시간대에 음성 사건이 있으면 접는다(구간 포함까지 요구하지
        # 않는다 — 시작이 0.6초 어긋났다고 남길 이유가 없다).
        if (is_generic_visual(episode["summary"]) and other["evidence"] in (AUDIO, VISUAL_AUDIO)
                and overlaps(episode["start"], episode["end"], other["start"], other["end"])):
            return (GENERIC_VISUAL_COVERED, other["episode_id"])
        if not contains(other["start"], other["end"], episode["start"], episode["end"]):
            continue
        if tokens and tokens < other_tokens:
            return (DUPLICATE_OVERLAP, other["episode_id"])
        shared = set(episode.get("broad_activity") or []) & set(other.get("broad_activity") or [])
        if shared and other["evidence"] in (VISUAL, VISUAL_AUDIO):
            return (SUBORDINATE_VISUAL_DETAIL, other["episode_id"])
    return None


# ── ③ 표현 정리 ────────────────────────────────────────────────────────

def looks_like_transcript(text):
    value = (text or "").strip()
    if not value:
        return False
    opener = value.split()[0] if value.split() else ""
    return (len(value) > MAX_ROW_CHARS
            or len(sentences(value)) > MAX_ROW_SENTENCES
            or opener.startswith(DISCOURSE_OPENERS))


def compress_transcript_text(text, max_chars=MAX_ROW_CHARS):
    """전사 덩어리를 줄인다. **문장을 새로 쓰지 않는다** — 앞의 군말을 떼고 잘라 쓴다."""
    value = (text or "").strip()
    removed = []
    items = sentences(value)
    while items:
        opener = items[0].split()[0] if items[0].split() else ""
        if opener.startswith(DISCOURSE_OPENERS) and len(items) > 1:
            removed.append(items.pop(0))
            continue
        break
    kept = []
    for sentence in items:
        if kept and len(" ".join(kept + [sentence])) > max_chars:
            removed.append(sentence)
            continue
        kept.append(sentence)
    return {"text": " ".join(kept).strip() or value[:max_chars].strip(),
            "removed_sentences": removed,
            "compressed": bool(removed)}


def uncertain_terms(summary, utterances, asr_states, unreliable_states):
    """저신뢰 발화에서만 나온 낱말 — 확정 표현으로 쓰면 안 되는 후보(추가 C)."""
    reliable, suspect = set(), set()
    for utterance in utterances:
        bucket = (suspect if asr_states.get(utterance["id"]) in unreliable_states else reliable)
        bucket.update(content_words(utterance.get("text", "")))
    return sorted({word for word in content_words(summary)
                   if word in suspect and word not in reliable})


# ── 중요도 (진단용 · 도메인 중립) ──────────────────────────────────────

APPROVED_DISPLAYS = ("GENERATIVE", "REGENERATED")


def assign_importance(episodes, approved_displays=APPROVED_DISPLAYS):
    """구조 신호만 쓴다 — 지속 시간 분포, 근거 종류, 승인 여부. 분야 분류표를 쓰지 않는다."""
    durations = sorted(e["end"] - e["start"] for e in episodes) or [0.0]
    median = durations[len(durations) // 2]
    out = []
    for episode in episodes:
        duration = episode["end"] - episode["start"]
        approved = episode.get("display") in approved_displays
        if episode["evidence"] == VISUAL_AUDIO or (approved and duration >= median):
            level = MAJOR
        elif episode.get("transcript_like") or (episode["evidence"] == VISUAL and duration < median):
            level = MINOR
        else:
            level = SUPPORTING
        out.append(level)
    return out


# ── ④ 근거 감사 ────────────────────────────────────────────────────────

def support_map(text, episodes, min_len=2):
    """표현의 내용어를 지지하는 episode id. 없으면 빈 목록이다."""
    found = {}
    for word in content_words(text, min_len):
        support = [e["episode_id"] for e in episodes
                   if word in (e.get("summary") or "") or word in (e.get("category") or "")]
        if support:
            found[word] = support
    return found


def claim_support(text, episodes):
    """제목·개요의 한 표현이 근거를 갖는가 — 내용어 중 하나라도 지지되면 통과."""
    support = support_map(text, episodes)
    covered = sorted(support)
    missing = [w for w in content_words(text) if w not in support]
    episode_ids = sorted({eid for ids in support.values() for eid in ids})
    return {"text": text, "supported_by": episode_ids,
            "supported_words": covered, "unsupported_words": missing,
            "grounded": bool(episode_ids) and not missing}


def prominence_violations(text, episodes, min_repeat=2):
    """부각 표현은 반복·명시 근거가 있을 때만 허용한다(추가 E)."""
    bad = []
    for term in PROMINENCE_TERMS:
        if term not in (text or ""):
            continue
        stated = sum(1 for e in episodes if term in (e.get("summary") or ""))
        if stated < min_repeat:
            bad.append({"term": term, "stated_in_episodes": stated})
    return bad


def audit_overview(overview, episodes):
    """개요 문장마다 지지 episode를 붙인다. 지지 없는 문장은 쓰지 않는다."""
    records = []
    for index, sentence in enumerate(sentences(overview), start=1):
        record = claim_support(sentence, episodes)
        record["sentence_id"] = "S%02d" % index
        record["prominence_violations"] = prominence_violations(sentence, episodes)
        record["usable"] = bool(record["supported_by"]) and not record["prominence_violations"]
        records.append(record)
    return records


def audit_title(title, episodes):
    claims = []
    for part in [p.strip() for p in re.split(r"[·,]|과 |와 |및 ", title or "") if p.strip()]:
        record = claim_support(part, episodes)
        record["prominence_violations"] = prominence_violations(part, episodes)
        claims.append(record)
    # 제목은 가장 엄격하게 본다 — 내용어 하나라도 근거가 없으면 쓰지 않는다(§15).
    usable = bool(claims) and all(c["grounded"] and not c["prominence_violations"]
                                 for c in claims)
    return {"title": title, "title_claims": claims, "usable": usable}


# ── 구분 ───────────────────────────────────────────────────────────────

def choose_episode_category(approved_category, summary, broad_activity, evidence,
                            activity_labels_useful=True, blocked_terms=(), approved=True):
    """승인된 구분 → 검증된 활동 라벨 → 중립. 새 개념을 만들지 않는다(§19).

    가드를 통과한 요약의 구분은 그대로 쓴다(같은 출력에서 나온 짝이다). 요약이 막힌
    행에서는 표시 문장이 그 구분을 뒷받침할 때만 쓴다.
    """
    candidate = (approved_category or "").strip()
    if (candidate and candidate not in GENERIC_CATEGORIES and validate_category(candidate)["ok"]
            and not any(term in candidate for term in blocked_terms)
            and (approved or lexically_supported(candidate, [summary]))):
        return {"category": candidate, "source": "APPROVED_CATEGORY"}
    if activity_labels_useful:
        for activity in (broad_activity or []):
            label = ACTIVITY_DISPLAY_LABEL.get(str(activity).strip().upper())
            if label:
                return {"category": label, "source": "VERIFIED_BROAD_ACTIVITY"}
    return {"category": NEUTRAL_SPEECH if evidence in (AUDIO, VISUAL_AUDIO) else NEUTRAL_VISUAL,
            "source": "NEUTRAL_FALLBACK"}


def composer_counts(episodes, suppressed):
    evidence = {}
    importance = {}
    for episode in episodes:
        evidence[episode["evidence"]] = evidence.get(episode["evidence"], 0) + 1
        importance[episode["importance"]] = importance.get(episode["importance"], 0) + 1
    reasons = {}
    for record in suppressed:
        reasons[record["reason"]] = reasons.get(record["reason"], 0) + 1
    return {"evidence": evidence, "importance": importance, "suppressed": reasons}


# ── 융합 무결성 (provenance-first) ─────────────────────────────────────

EPISODE_GROUNDED = "EPISODE_GROUNDED"
EPISODE_PROVENANCE_ERROR = "EPISODE_PROVENANCE_ERROR"
EPISODE_TEMPORAL_ERROR = "EPISODE_TEMPORAL_ERROR"
LINKED_RELATIONS = ("SAME_EVENT", "COMPLEMENTARY")
# timeline은 시각을 소수 둘째 자리로 저장하고 원본 구간은 더 정밀하다. 그 표기 차이일 뿐인
# 어긋남을 시간 오류로 보지 않기 위한 여유값이다(의미 임계가 아니다).
TEMPORAL_TOLERANCE_SEC = 0.05

CLAUSE_VISUAL = "VISUAL"
CLAUSE_AUDIO = "AUDIO"
CLAUSE_VISUAL_AUDIO = "VISUAL_AUDIO"


def linked_speech_ids(multimodal_event):
    """이 multimodal event에서 **이미 연결된 것으로 판정된** speech event만 돌려준다."""
    return [r.get("speech_event_id") for r in (multimodal_event.get("relations") or [])
            if r.get("relation") in LINKED_RELATIONS and r.get("speech_event_id")]


def has_frozen_link(multimodal_event, speech_id):
    return speech_id in linked_speech_ids(multimodal_event)


def audit_episode(episode, visual_spans):
    """episode가 실제 provenance로만 구성됐는지 본다.

    `visual_spans`는 visual_event_id → (start, end). 근접·같은 chapter·비슷한 구분 같은
    이유로 끌어온 화면 근거는 여기서 걸린다.
    """
    problems = []
    visual_ids = list(episode.get("visual_event_ids") or [])
    speech_ids = list(episode.get("speech_event_ids") or [])

    if episode.get("evidence") == VISUAL_AUDIO and not (visual_ids and speech_ids
                                                       and episode.get("frozen_link")):
        problems.append(("PROVENANCE", "음성+화면 표기에 필요한 근거나 relation이 없다"))
    if visual_ids and speech_ids and not episode.get("frozen_link"):
        problems.append(("PROVENANCE", "화면 근거가 frozen relation으로 연결돼 있지 않다"))

    for visual_id in visual_ids:
        span = visual_spans.get(visual_id)
        if span is None:
            problems.append(("PROVENANCE", "화면 근거 %s의 구간을 찾을 수 없다" % visual_id))
            continue
        if not (episode["start"] - TEMPORAL_TOLERANCE_SEC <= span[0]
                and span[1] <= episode["end"] + TEMPORAL_TOLERANCE_SEC):
            problems.append(("TEMPORAL",
                             "화면 근거 %s(%.1f~%.1f)가 사건 구간(%.1f~%.1f) 밖이다"
                             % (visual_id, span[0], span[1], episode["start"], episode["end"])))

    if not problems:
        return {"status": EPISODE_GROUNDED, "problems": []}
    kind = "TEMPORAL" if all(p[0] == "TEMPORAL" for p in problems) else "PROVENANCE"
    status = EPISODE_TEMPORAL_ERROR if kind == "TEMPORAL" else EPISODE_PROVENANCE_ERROR
    return {"status": status, "problems": [p[1] for p in problems]}


def clause_provenance(summary, visual_clause, evidence):
    """문장마다 어느 근거에서 왔는지 적는다. 화면 문장은 우리가 붙인 그 문장뿐이다."""
    records = []
    for index, sentence in enumerate(sentences(summary), start=1):
        if visual_clause and sentence.strip() == visual_clause.strip():
            kind = CLAUSE_VISUAL
        elif evidence == VISUAL_AUDIO:
            kind = CLAUSE_VISUAL_AUDIO
        elif evidence == VISUAL:
            kind = CLAUSE_VISUAL
        else:
            kind = CLAUSE_AUDIO
        records.append({"clause_id": "C%02d" % index, "text": sentence, "evidence": kind})
    return records


def drop_uncertain_clauses(summary, terms):
    """불확실 고유명사가 든 문장을 뺀다. 교정하거나 다른 말로 바꾸지 않는다(§12)."""
    if not terms:
        return {"text": (summary or "").strip(), "removed": []}
    items = sentences(summary)
    kept = [s for s in items if not any(term in s for term in terms)]
    removed = [s for s in items if s not in kept]
    if not kept:
        return {"text": (summary or "").strip(), "removed": []}   # 전부 빠지면 그대로 둔다
    return {"text": " ".join(kept), "removed": removed}


def _with_particle(word, has_batchim, without_batchim):
    """받침 유무로 조사를 고른다 — 한국어 표기 규칙이지 어휘 목록이 아니다."""
    last = (word or "").strip()[-1:]
    if not last or not ("가" <= last <= "힣"):
        return word + without_batchim
    return word + (has_batchim if (ord(last) - 0xAC00) % 28 else without_batchim)


def _sample_flow(names, limit):
    """앞쪽만 자르면 영상 뒷부분이 통째로 빠진다 — 고르게 뽑는다."""
    if len(names) <= limit:
        return names
    step = (len(names) - 1) / float(limit - 1)
    picked, seen = [], set()
    for index in range(limit):
        name = names[int(round(index * step))]
        if name not in seen:
            seen.add(name)
            picked.append(name)
    return picked


def narrative_overview(episodes, limit=5):
    """구분 나열이 아니라 흐름으로 쓴다 — 순서는 실제 episode 순서에서만 온다(§13)."""
    order = []
    for episode in sorted(episodes, key=lambda e: (e["start"], e["end"])):
        name = episode.get("category")
        if name in (NEUTRAL_SPEECH, NEUTRAL_VISUAL) or not name:
            continue
        if not order or order[-1][0] != name:
            if name not in [o[0] for o in order]:
                order.append((name, episode["episode_id"]))
    if not order:
        return "", []
    # 오래 이어진 구분을 고르고, 순서는 실제 등장 순서를 그대로 쓴다.
    weight = {}
    for ep in episodes:
        name = ep.get("category")
        if name in (NEUTRAL_SPEECH, NEUTRAL_VISUAL) or not name:
            continue
        weight[name] = weight.get(name, 0.0) + (ep["end"] - ep["start"])
    ranked = {name for name, _ in sorted(weight.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]}
    names = [name for name, _ in order if name in ranked]
    if not names:
        names = _sample_flow([name for name, _ in order], limit)
    if len(names) == 1:
        text = "%s 활동이 영상 전체에 이어진다." % names[0]
    elif len(names) == 2:
        text = "%s에서 시작해 %s 이어진다." % (
            names[0], _with_particle(names[1], "으로", "로"))
    else:
        middle = ", ".join(names[1:-1])
        text = "%s에서 시작해 %s 거쳐 %s 이어진다." % (
            names[0], _with_particle(middle, "을", "를"),
            _with_particle(names[-1], "으로", "로"))
    evidence = [{"sentence_id": "S01", "flow": names,
                 "report_episode_ids": [eid for _, eid in order]}]
    return text, evidence
