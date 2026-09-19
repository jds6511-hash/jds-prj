"""WVR Speech channel — utterance-level 전사에서 보고 가능한 speech event를 만든다.

```
raw utterance (m3_generate.transcribe 형식 {text,t0,t1} 또는 {id,start,end,text})
      ↓  normalize_utterances()      보존 · 병합하지 않는다
reportable utterance                 filler·호응·잡음은 event 후보에서만 제외
      ↓  group_utterances()          시간 인접 + 어휘 결속으로 topic 경계 판단
speech event                         요약은 원문 발췌(extractive)가 기본
      ↓  validate_speech_events()    원문에 없는 어휘가 요약에 들어오면 거부
```

영상 유형에 독립이다 — 회의·강의·조리·현장 어디에도 같은 규칙을 쓴다. 회의 어휘,
안건명, 기관명을 코드에 넣지 않는다. 화자 전환은 그 자체로 topic 경계가 아니다
(작업 지시 §7).

요약 정책.

```
기본      extractive — 발화 원문 문장을 그대로 고른다. 새 사실이 0이다
주입      summarizer 콜러블을 주면 그 결과를 쓰되 validate가 근거를 강제한다
금지      원문에 없는 어휘로 결론·의도·평가를 만드는 것
```
"""
from __future__ import annotations

import re

SOURCE = "AUDIO"

# 발화 자체로는 보고 가치가 없는 짧은 호응·인사. 영상 유형과 무관한 일반 표현만 둔다.
FILLER_TOKENS = {
    "네", "넵", "예", "응", "음", "어", "아", "야", "자", "그", "저", "뭐",
    "맞아요", "맞습니다", "그렇죠", "그렇습니다", "알겠습니다", "알겠어요",
    "감사합니다", "고맙습니다", "죄송합니다", "안녕하세요", "안녕히계세요",
    "좋습니다", "좋아요", "okay", "ok", "오케이", "하하", "와", "우와", "아이고",
}
MIN_REPORTABLE_CHARS = 12          # 이보다 짧은 발화는 단독 event가 되지 않는다
MIN_REPORTABLE_SEC = 1.2
MAX_GAP_SEC = 45.0                 # 이보다 오래 끊기면 같은 topic으로 잇지 않는다
MIN_COHESION = 0.10                # 어휘 자카드 임계 — 이 아래면 topic 전환 후보
NEAR_GAP_SEC = 8.0                 # 이보다 짧게 끊기면 같은 흐름으로 보고 임계를 낮춘다
NEAR_GAP_FACTOR = 0.5
MIN_LINK = 0.18                    # 앞뒤 창 어휘의 overlap 계수 임계(gap 보조 판정용)
WINDOW_UTTERANCES = 5              # 경계 판정에 쓰는 앞뒤 발화 수
MIN_EVENT_SEC = 60.0               # 이보다 짧은 조각은 이웃 구간으로 흡수한다
DEPTH_FACTOR = 0.0                 # 컷오프 = 평균 depth - DEPTH_FACTOR * 표준편차
                                   # (0.5·1.0은 실측에서 72분 회의를 4·1구간으로 뭉갰다)
MIN_EVENT_UTTERANCES = 1
SUMMARY_MAX_CHARS = 150

# 조사 + 흔한 활용 어미. 형태소 분석기 없이 어근만 남기려는 최소 장치다 — 같은 뜻을
# 다르게 활용한 말("설명한다" / "설명드리겠습니다")이 다른 토큰으로 갈리면 근거 검증이
# 헛돈다(실측: 사실이 맞는 요약 4건이 미지원으로 걸렸다).
_PARTICLE = re.compile(r"(은|는|이|가|을|를|에|에서|에게|으로|로|와|과|도|만|의|께서|"
                       r"입니다|습니다|합니다|했습니다|하겠습니다|드립니다|드리겠습니다|"
                       r"되었습니다|하고|한다|했다|하며|하는|하지|해야|해서|하기|하자고|"
                       r"되고|된다|됐다|되는|되어|있는|있다|없는|없다|이다|라고|처럼|보다|"
                       r"까지|부터|마다|이나|나|중에|에는|에도|으로서|으로써)$")
_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")


# ── 전사 정규화 ─────────────────────────────────────────────────────────

def normalize_utterances(raw):
    """`{text,t0,t1}`(m3_generate) · `{id,start,end,text}` 양쪽을 같은 모양으로 읽는다.

    발화 경계를 다시 자르거나 붙이지 않는다 — raw 보존이 원칙(작업 지시 §4).
    """
    if isinstance(raw, dict):
        raw = raw.get("utterances", [])
    out = []
    for item in raw:
        start = item.get("start", item.get("t0"))
        end = item.get("end", item.get("t1"))
        text = (item.get("text") or "").strip()
        if start is None or end is None or not text:
            continue
        entry = {
            "id": item.get("id") or "U%04d" % (len(out) + 1),
            "start": round(float(start), 2),
            "end": round(float(end), 2),
            "text": text,
        }
        for optional in ("speaker_id", "low_confidence"):
            if optional in item:
                entry[optional] = item[optional]
        out.append(entry)
    return out


def tokens(text):
    out = set()
    for word in _TOKEN.findall(text):
        stem = _PARTICLE.sub("", word)
        if len(stem) >= 2:
            out.add(stem)
    return out


def _strip(text):
    return re.sub(r"[.,!?~…·\"'\s]", "", text)


def is_filler(utterance):
    """짧은 호응·인사·감탄인가. 길면 filler로 보지 않는다."""
    text = _strip(utterance["text"])
    duration = utterance["end"] - utterance["start"]
    if text.lower() in FILLER_TOKENS:
        return True
    if len(text) < MIN_REPORTABLE_CHARS and duration < MIN_REPORTABLE_SEC:
        return True
    if len(text) < MIN_REPORTABLE_CHARS and all(
            part in FILLER_TOKENS for part in re.split(r"[.,!?~…\s]+", utterance["text"]) if part):
        return True
    return False


def is_reportable(utterance):
    return not is_filler(utterance)


# ── topic grouping ─────────────────────────────────────────────────────

def cohesion(left, right):
    """두 어휘 집합의 자카드. 어느 쪽이든 비면 0."""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def link_strength(left, right):
    """겹침을 **작은 쪽 크기**로 나눈다(overlap 계수).

    자카드를 쓰면 그룹이 길어질수록 분모(합집합)가 커져 새 발화가 아무리 같은 주제여도
    결속이 0에 수렴한다 — 실측에서 777발화가 570그룹으로 흩어졌다. 한 주제를 이어
    말할 때 뒤 문장이 새 어휘를 더하는 것은 정상이므로, 판단은 "앞서 나온 어휘를
    얼마나 다시 쓰는가"로 한다.
    """
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _window_tokens(utterances, start, end):
    out = set()
    for utterance in utterances[max(0, start):end]:
        out |= tokens(utterance["text"])
    return out


def boundary_scores(utterances, window=WINDOW_UTTERANCES):
    """경계 후보마다 앞뒤 창의 어휘 결속을 잰다(TextTiling 계열).

    발화 쌍끼리 비교하면 한국어 구어에서는 겹치는 토큰이 대부분 0이라 모든 자리가
    경계로 잡힌다(실측: 777발화 → 570그룹). 앞뒤 여러 발화를 뭉쳐서 비교하면 한
    주제 안에서 반복되는 어휘가 살아나고, 주제가 바뀌는 자리에서만 값이 내려간다.
    """
    scores = []
    for index in range(1, len(utterances)):
        left = _window_tokens(utterances, index - window, index)
        right = _window_tokens(utterances, index, index + window)
        scores.append(link_strength(left, right))
    return scores


def depth_scores(scores):
    """각 경계 후보의 골 깊이. 좌우로 올라가는 높이를 더한다(TextTiling depth).

    결속 값 자체에 임계를 걸면 그 임계가 영상마다 달라진다(실측: 같은 임계에서 한
    영상은 470구간, 다른 설정에선 1구간). 깊이는 **그 영상 안에서의 상대적 골**이라
    영상 유형이 달라도 같은 규칙을 쓸 수 있다.
    """
    depths = []
    for index, value in enumerate(scores):
        left = value
        cursor = index
        while cursor > 0 and scores[cursor - 1] >= left:
            left = scores[cursor - 1]
            cursor -= 1
        right = value
        cursor = index
        while cursor < len(scores) - 1 and scores[cursor + 1] >= right:
            right = scores[cursor + 1]
            cursor += 1
        depths.append((left - value) + (right - value))
    return depths


def _cutoff(depths, factor=DEPTH_FACTOR):
    positive = [d for d in depths if d > 0]
    if not positive:
        return float("inf")
    mean = sum(positive) / len(positive)
    variance = sum((d - mean) ** 2 for d in positive) / len(positive)
    return mean - factor * (variance ** 0.5)


def group_utterances(utterances, max_gap_sec=MAX_GAP_SEC, min_link=MIN_LINK,
                     near_gap_sec=NEAR_GAP_SEC, near_gap_factor=NEAR_GAP_FACTOR,
                     window=WINDOW_UTTERANCES, min_event_sec=MIN_EVENT_SEC,
                     depth_factor=DEPTH_FACTOR):
    """시간 간격 + 창 단위 어휘 결속의 골로 발화를 묶는다.

    화자 전환은 경계 근거가 아니다(작업 지시 §7). 경계는 둘 중 하나일 때 만든다.

    ```
    오래 끊김        gap > max_gap_sec
    어휘 흐름 단절   앞뒤 창 결속이 그 영상 기준으로 깊은 골을 이루는 지점
    ```
    """
    if not utterances:
        return []
    if len(utterances) == 1:
        return [list(utterances)]
    scores = boundary_scores(utterances, window)
    depths = depth_scores(scores)
    cutoff = _cutoff(depths, depth_factor)

    cuts = set()
    for index in range(1, len(utterances)):
        gap = utterances[index]["start"] - utterances[index - 1]["end"]
        if gap > max_gap_sec:
            cuts.add(index)
            continue
        score = scores[index - 1]
        if score == 0.0 and gap > near_gap_sec:
            cuts.add(index)
            continue
        position = index - 1
        local_min = (score <= scores[position - 1] if position > 0 else True) and                     (score <= scores[position + 1] if position + 1 < len(scores) else True)
        if depths[position] >= cutoff and local_min:
            cuts.add(index)

    groups, current = [], [utterances[0]]
    for index in range(1, len(utterances)):
        if index in cuts:
            groups.append(current)
            current = [utterances[index]]
        else:
            current.append(utterances[index])
    groups.append(current)
    return _absorb_short(groups, min_event_sec, max_gap_sec)


def _absorb_short(groups, min_event_sec, max_gap_sec):
    """너무 짧은 조각은 시간상 이웃에 붙인다 — 한 문장짜리 행이 쏟아지는 것을 막는다."""
    merged = []
    for group in groups:
        span = group[-1]["end"] - group[0]["start"]
        if merged:
            gap = group[0]["start"] - merged[-1][-1]["end"]
            if span < min_event_sec and gap <= max_gap_sec:
                merged[-1].extend(group)
                continue
        merged.append(list(group))
    if len(merged) >= 2:
        last_span = merged[-1][-1]["end"] - merged[-1][0]["start"]
        gap = merged[-1][0]["start"] - merged[-2][-1]["end"]
        if last_span < min_event_sec and gap <= max_gap_sec:
            merged[-2].extend(merged.pop())
    return merged


def extractive_summary(group, max_chars=SUMMARY_MAX_CHARS, sentences=2):
    """그룹에서 가장 중심적인 발화 몇 개를 **그대로** 잇는다. 새 문장을 쓰지 않는다.

    한 문장만 뽑으면 긴 구간(실측: 11분짜리 speech event)이 지나가는 말 한 마디로
    대표된다. 중심성 상위 문장을 시간 순서대로 이어 붙이면 구간이 무엇에 대한
    것이었는지가 남는다. 문장 자체는 전사 원문 그대로이므로 사실이 늘지 않는다.
    """
    if len(group) == 1:
        return group[0]["text"][:max_chars]
    vocabulary = set()
    for utterance in group:
        vocabulary |= tokens(utterance["text"])
    scored = []
    for index, utterance in enumerate(group):
        own = tokens(utterance["text"])
        score = cohesion(own, vocabulary) * min(len(utterance["text"]), max_chars)
        scored.append((score, index, utterance))
    picked = sorted(sorted(scored, key=lambda item: -item[0])[:max(1, sentences)],
                    key=lambda item: item[1])
    text = " ".join(item[2]["text"].strip() for item in picked)
    return text[:max_chars]


# 어느 영상에나 나오는 상투어·기능어. 구분(category)에 올라오면 내용을 가린다
# (실측: "앉아주시기", "폭발적인" 같은 말이 구분으로 뽑혔다). 주제어가 아니다.
CATEGORY_STOPWORDS = {
    "말씀", "생각", "경우", "부분", "정도", "지금", "오늘", "우리", "여러분", "이번",
    "바랍니다", "있습니다", "없습니다", "합니다", "하겠습니다", "드립니다", "같습니다",
    "때문", "대해", "위해", "관련", "그것", "이것", "하나", "그런", "이런", "저런",
    "그리고", "그런데", "하지만", "어쨌든", "사실", "정말", "굉장히", "조금", "많이",
    "제가", "저희", "여기", "거기", "다음", "먼저", "마지막", "관해", "통해", "통한",
    "라고", "라는", "이라고", "것이", "것을", "것은", "수가", "수도", "때도", "해서",
}


def derive_category(group, max_chars=18, stopwords=CATEGORY_STOPWORDS):
    """그룹에서 가장 자주 나오는 내용어로 구분을 만든다. 외부 분류 체계를 쓰지 않는다."""
    counts = {}
    for utterance in group:
        for token in tokens(utterance["text"]):
            if token in stopwords or len(token) < 2 or token.isdigit():
                continue
            counts[token] = counts.get(token, 0) + 1
    if not counts:
        return "발언"
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    # 토큰 두 개를 붙이면 "같아요 미사일"처럼 말이 되지 않는 구분이 나온다(실측).
    # 가장 자주 나온 내용어 하나만 쓴다.
    return ranked[0][0][:max_chars]


def build_speech_events(utterances, summarizer=None, max_gap_sec=MAX_GAP_SEC,
                        min_link=MIN_LINK, near_gap_sec=NEAR_GAP_SEC):
    """utterance 목록 → speech event 목록. filler만 있는 구간은 event가 되지 않는다."""
    normalized = normalize_utterances(utterances)
    reportable = [u for u in normalized if is_reportable(u)]
    events = []
    for group in group_utterances(reportable, max_gap_sec, min_link, near_gap_sec):
        if len(group) < MIN_EVENT_UTTERANCES:
            continue
        summary = (summarizer(group) if summarizer else extractive_summary(group)).strip()
        speakers = [u["speaker_id"] for u in group if u.get("speaker_id")]
        events.append({
            "speech_event_id": "SP%03d" % (len(events) + 1),
            "start": group[0]["start"],
            "end": group[-1]["end"],
            "category": derive_category(group),
            "summary": summary,
            "supporting_utterance_ids": [u["id"] for u in group],
            "speaker_ids": sorted(set(speakers)),
            "low_confidence_utterances": [u["id"] for u in group if u.get("low_confidence")],
            "source": SOURCE,
        })
    return events


# ── 검증 ────────────────────────────────────────────────────────────────

def validate_speech_events(events, utterances, time_margin_sec=5.0, min_support=0.6):
    """요약이 근거 발화의 어휘로 뒷받침되는지, 시간이 근거를 넘지 않는지 본다."""
    index = {u["id"]: u for u in normalize_utterances(utterances)}
    problems = []
    for event in events:
        eid = event.get("speech_event_id", "?")
        support = event.get("supporting_utterance_ids") or []
        if not support:
            problems.append("%s: 뒷받침 발화가 없다" % eid)
            continue
        unknown = [sid for sid in support if sid not in index]
        if unknown:
            problems.append("%s: 알 수 없는 발화 id %s" % (eid, unknown))
            continue
        starts = [index[sid]["start"] for sid in support]
        ends = [index[sid]["end"] for sid in support]
        if (event["start"] < min(starts) - time_margin_sec
                or event["end"] > max(ends) + time_margin_sec):
            problems.append("%s: 시간 범위가 근거 발화 범위를 넘어선다 "
                            "(%.1f~%.1f / 근거 %.1f~%.1f)"
                            % (eid, event["start"], event["end"], min(starts), max(ends)))
        vocabulary = set()
        for sid in support:
            vocabulary |= tokens(index[sid]["text"])
        summary_tokens = tokens(event.get("summary", ""))
        if not summary_tokens:
            problems.append("%s: 요약이 비어 있다" % eid)
            continue
        flat = re.sub(r"\s+", "", " ".join(index[sid]["text"] for sid in support))
        grounded = {token for token in summary_tokens
                    if token in vocabulary or token in flat
                    or any(token.startswith(word) or word.startswith(token)
                           for word in vocabulary if min(len(token), len(word)) >= 3)}
        if len(grounded) / len(summary_tokens) < min_support:
            missing = sorted(summary_tokens - grounded)[:6]
            problems.append("%s: 요약에 근거 발화에 없는 표현이 있다 %s" % (eid, missing))
    return problems


# ── transcript 렌더 (m7_webui의 다운로드 형식과 같은 모양) ───────────────

def _timestamp(seconds, separator="."):
    millis = round(float(seconds) * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return "%02d:%02d:%02d%s%03d" % (hours, minutes, secs, separator, millis)


def render_transcript(utterances, fmt):
    items = normalize_utterances(utterances)
    if fmt == "txt":
        return "\n\n".join("[%s - %s]\n%s" % (_timestamp(u["start"]), _timestamp(u["end"]),
                                              u["text"]) for u in items) + ("\n" if items else "")
    if fmt == "srt":
        return "\n\n".join("%d\n%s --> %s\n%s"
                           % (i, _timestamp(u["start"], ","), _timestamp(u["end"], ","), u["text"])
                           for i, u in enumerate(items, start=1)) + ("\n" if items else "")
    raise ValueError(fmt)
