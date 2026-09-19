"""WVR_SAMPLING_SEMANTIC_DENSITY_V2 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V2_2026-09-09.md`

```
① event interval 파싱      (start·end + actor·action·object_or_state)
② consecutive run collapse  같은 signature가 연속하면 하나의 interval로 합친다
                           (global dedupe가 아니다 — 사이에 다른 사건이 끼면 남긴다)
③ 2단 매칭                 TEMPORALLY_COMPATIBLE → SEMANTICALLY_EQUIVALENT
                           확정 못 하면 ADJUDICATION_REQUIRED로 남긴다
```

**임계값을 만들지 않는다.** 의미 판정은 정규화 후 완전일치(=동일) 또는 공통 토큰
0(=상이)이라는 구조적 조건만 쓰고, 그 사이는 사람이 볼 목록으로 남긴다.
`distinct_event_ratio` 같은 비율 게이트도 만들지 않는다.
"""
import json
import re

import wvr_density as density

PARSE_OK = "OK"
PARSE_FAILURE = "PARSE_FAILURE"
CONTRACT_VIOLATION = "CONTRACT_VIOLATION"

ENGLISH_ONLY_CONTRACT = "ENGLISH_ONLY"
LANGUAGE_CONTRACT_FAILURE = "OUTPUT_LANGUAGE_CONTRACT_FAILURE"

TEMPORALLY_COMPATIBLE = "TEMPORALLY_COMPATIBLE"
SEMANTICALLY_EQUIVALENT = "SEMANTICALLY_EQUIVALENT"
SEMANTICALLY_DIFFERENT = "SEMANTICALLY_DIFFERENT"
ADJUDICATION_REQUIRED = "ADJUDICATION_REQUIRED"

PAIR_EVALUABLE = "EVALUABLE"
PAIR_NON_EVALUABLE = "NON_EVALUABLE"
DECISION_ELIGIBLE = "DECISION_ELIGIBLE"
INCONCLUSIVE = "INCONCLUSIVE"
REPRESENTATION_DEGENERACY = "EVENT_REPRESENTATION_DEGENERACY"

CONTENT_FIELDS = ("actor", "action", "object_or_state")
TOLERANCES = density.MATCH_TOLERANCE_SEC          # (4.0 primary, 8.0 sensitivity)

_HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
_CJK = re.compile(r"[぀-ヿ一-鿿]")
_LATIN = re.compile(r"[A-Za-z]")


class V2Error(ValueError):
    """계측기 계약 위반."""


# ── 정규화·signature ───────────────────────────────────────────────────
def normalize(text: str) -> str:
    """소문자·공백 정리·구두점 제거. 시간은 포함하지 않는다."""
    cleaned = re.sub(r"[^0-9a-z가-힣\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def signature(event) -> tuple:
    """content signature. **시간 필드는 제외한다.**"""
    return tuple(normalize(event.get(field, "")) for field in CONTENT_FIELDS)


# 관사·전치사는 겹침 판정에서 제외한다. 이것을 빼지 않으면 "a"만 공유해도
# 공통 토큰 0이 되지 않아 SEMANTICALLY_DIFFERENT가 사실상 발생하지 않는다.
# 고정 목록이고 결과를 보고 늘리지 않는다.
STOPWORDS = frozenset("""a an the of in on at to and or with without into from
by for is are was were be being been it its this that these those his her
their there while as up down out over under near""".split())


def tokens(event) -> set:
    """의미 겹침 판정용 토큰. 불용어는 제외한다."""
    words = set()
    for field in CONTENT_FIELDS:
        words |= set(normalize(event.get(field, "")).split())
    return words - STOPWORDS


# ── 언어 계약 ──────────────────────────────────────────────────────────
def english_only(events) -> dict:
    """content 필드에 한글·가나·한자가 없고 라틴 문자가 있어야 한다."""
    body = " ".join(str(event.get(field, "")) for event in events
                    for field in CONTENT_FIELDS)
    hangul = len(_HANGUL.findall(body))
    cjk = len(_CJK.findall(body))
    latin = len(_LATIN.findall(body))
    satisfied = hangul == 0 and cjk == 0 and latin > 0
    return {"contract": ENGLISH_ONLY_CONTRACT, "satisfied": bool(satisfied),
            "hangul_chars": hangul, "cjk_chars": cjk, "latin_chars": latin}


# ── 파싱 ───────────────────────────────────────────────────────────────
def parse_events(raw: str, window) -> dict:
    """실패는 실패로 남긴다. 되살리지 않는다."""
    text = (raw or "").strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {"status": PARSE_FAILURE, "events": [], "collapsed": [],
                "violations": [], "reason": "JSON 객체가 없다"}
    try:
        payload = json.loads(match.group(0))
    except ValueError as error:
        return {"status": PARSE_FAILURE, "events": [], "collapsed": [],
                "violations": [], "reason": str(error)[:200]}
    rows = payload.get("events")
    if not isinstance(rows, list):
        return {"status": CONTRACT_VIOLATION, "events": [], "collapsed": [],
                "violations": [], "reason": "events가 목록이 아니다"}

    events, violations = [], []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            violations.append({"index": index, "reason": "객체가 아니다"})
            continue
        start, end = row.get("start_sec"), row.get("end_sec")
        if not isinstance(start, (int, float)) or not isinstance(end,
                                                                 (int, float)):
            violations.append({"index": index, "reason": "시간이 수가 아니다"})
            continue
        start, end = float(start), float(end)
        if end < start:
            violations.append({"index": index, "reason": "end < start",
                               "start_sec": start, "end_sec": end})
        inside = (window["start_sec"] <= start <= window["end_sec"]
                  and window["start_sec"] <= end <= window["end_sec"])
        if not inside:
            violations.append({"index": index, "reason": "창 밖 구간",
                               "start_sec": start, "end_sec": end})
        events.append({
            "index": index, "start_sec": start, "end_sec": end,
            "actor": str(row.get("actor", "")),
            "action": str(row.get("action", "")),
            "object_or_state": str(row.get("object_or_state", "")),
            "inside_window": inside,
        })
    status = PARSE_OK if events else CONTRACT_VIOLATION
    collapsed = collapse_runs(events) if events else []
    return {"status": status, "events": events, "collapsed": collapsed,
            "violations": violations,
            "language": english_only(events),
            "reason": "" if status == PARSE_OK else "event가 없다"}


# ── consecutive run collapse ──────────────────────────────────────────
def collapse_runs(events) -> list:
    """같은 signature가 **연속**할 때만 하나의 interval로 합친다."""
    ordered = sorted(events, key=lambda event: (event["start_sec"],
                                                event["index"]))
    collapsed = []
    for event in ordered:
        current = signature(event)
        if collapsed and collapsed[-1]["signature"] == current:
            previous = collapsed[-1]
            previous["end_sec"] = max(previous["end_sec"], event["end_sec"])
            previous["start_sec"] = min(previous["start_sec"],
                                        event["start_sec"])
            previous["source_indices"].append(event["index"])
            previous["collapsed_count"] += 1
            continue
        collapsed.append({
            "index": len(collapsed), "start_sec": event["start_sec"],
            "end_sec": event["end_sec"], "actor": event["actor"],
            "action": event["action"],
            "object_or_state": event["object_or_state"],
            "signature": current, "source_indices": [event["index"]],
            "collapsed_count": 1,
        })
    return collapsed


def representation(collapsed) -> dict:
    """collapse 뒤의 표현이 비교 가능한 모양인지. 비율 임계값을 쓰지 않는다."""
    signatures = {tuple(event["signature"]) for event in collapsed}
    degenerate = len(signatures) <= 1
    return {"collapsed_event_count": len(collapsed),
            "unique_signature_count": len(signatures),
            "max_collapsed_run": max((event["collapsed_count"]
                                      for event in collapsed), default=0),
            "degenerate": bool(degenerate),
            "reason": REPRESENTATION_DEGENERACY if degenerate else ""}


# ── 2단 매칭 ──────────────────────────────────────────────────────────
def temporally_compatible(left, right, tolerance: float) -> bool:
    """구간이 겹치거나, 가장 가까운 끝점 간격이 허용오차 이내."""
    if tolerance <= 0:
        raise V2Error("허용오차가 0 이하다: %r" % tolerance)
    if left["start_sec"] <= right["end_sec"] and right["start_sec"] \
            <= left["end_sec"]:
        return True
    gap = (right["start_sec"] - left["end_sec"] if right["start_sec"]
           > left["end_sec"] else left["start_sec"] - right["end_sec"])
    return gap <= tolerance


def semantic_relation(left, right) -> dict:
    """정규화 완전일치 → 동일. 공통 토큰 0 → 상이. 그 사이는 사람이 본다."""
    if signature(left) == signature(right):
        relation = SEMANTICALLY_EQUIVALENT
    elif not (tokens(left) & tokens(right)):
        relation = SEMANTICALLY_DIFFERENT
    else:
        relation = ADJUDICATION_REQUIRED
    fields = {field: (normalize(left.get(field, ""))
                      == normalize(right.get(field, "")))
              for field in CONTENT_FIELDS}
    return {"relation": relation, "field_equal": fields,
            "shared_tokens": sorted(tokens(left) & tokens(right))}


def align(reference, arm, tolerance: float) -> dict:
    """시간으로 후보를 좁히고, 의미 관계를 따로 적는다. 1:1로 고정하지 않는다."""
    candidates = []
    for left in reference:
        for right in arm:
            if not temporally_compatible(left, right, tolerance):
                continue
            relation = semantic_relation(left, right)
            candidates.append({
                "reference_index": left["index"], "arm_index": right["index"],
                "reference_span": [left["start_sec"], left["end_sec"]],
                "arm_span": [right["start_sec"], right["end_sec"]],
                "reference": {field: left[field] for field in CONTENT_FIELDS},
                "arm": {field: right[field] for field in CONTENT_FIELDS},
                **relation,
            })
    candidates.sort(key=lambda row: (row["reference_index"], row["arm_index"]))

    equivalent = [row for row in candidates
                  if row["relation"] == SEMANTICALLY_EQUIVALENT]
    adjudication = [row for row in candidates
                    if row["relation"] == ADJUDICATION_REQUIRED]
    equivalent_left = {row["reference_index"] for row in equivalent}
    equivalent_right = {row["arm_index"] for row in equivalent}
    compatible_left = {row["reference_index"] for row in candidates}
    compatible_right = {row["arm_index"] for row in candidates}

    merges = [index for index in sorted(equivalent_right)
              if sum(1 for row in equivalent if row["arm_index"] == index) > 1]
    splits = [index for index in sorted(equivalent_left)
              if sum(1 for row in equivalent
                     if row["reference_index"] == index) > 1]

    return {
        "tolerance_sec": tolerance, "candidates": candidates,
        "equivalent": equivalent, "adjudication": adjudication,
        "equivalent_count": len(equivalent),
        "adjudication_count": len(adjudication),
        "temporally_compatible_count": len(candidates),
        "reference_only": [event["index"] for event in reference
                           if event["index"] not in compatible_left],
        "arm_only": [event["index"] for event in arm
                     if event["index"] not in compatible_right],
        "reference_without_equivalent": [event["index"] for event in reference
                                         if event["index"]
                                         not in equivalent_left],
        "arm_without_equivalent": [event["index"] for event in arm
                                   if event["index"] not in equivalent_right],
        "merge_candidates": merges, "split_candidates": splits,
        "order_inversions": order_inversions(equivalent),
    }


def order_inversions(equivalent) -> int:
    """의미가 같다고 확정된 쌍에서만 순서 뒤집힘을 센다."""
    ranks = [row["arm_index"] for row in
             sorted(equivalent, key=lambda row: row["reference_index"])]
    return sum(1 for left in range(len(ranks))
               for right in range(left + 1, len(ranks))
               if ranks[left] > ranks[right])


def field_divergence(alignment) -> dict:
    """actor·action·object_or_state가 각각 얼마나 갈리는지 (동일 확정 쌍 기준)."""
    rows = alignment["equivalent"] + alignment["adjudication"]
    if not rows:
        return {field: None for field in CONTENT_FIELDS}
    return {field: sum(1 for row in rows if not row["field_equal"][field])
            for field in CONTENT_FIELDS}


# ── validity·pair·판정 ────────────────────────────────────────────────
def arm_validity(record) -> dict:
    parsed = record.get("parsed") or {}
    reasons = []
    if parsed.get("status") != PARSE_OK:
        reasons.append(parsed.get("status") or "NO_PARSE_RECORD")
    if not parsed.get("events"):
        reasons.append("NO_EVENT")
    if truncated_at_cap(record):
        reasons.append("TRUNCATED_AT_CAP")
    language = parsed.get("language") or english_only([])
    if not language.get("satisfied"):
        reasons.append(LANGUAGE_CONTRACT_FAILURE)
    return {"valid": not reasons, "reasons": reasons, "language": language}


def truncated_at_cap(record) -> bool:
    metrics = record.get("metrics") or {}
    generated = metrics.get("generated_token_count")
    cap = (record.get("requested") or {}).get("max_new_tokens")
    return bool(generated and cap and generated >= cap)


def pair_evaluability(reference_record, arm_record) -> dict:
    left, right = arm_validity(reference_record), arm_validity(arm_record)
    reasons = (["S0:%s" % reason for reason in left["reasons"]]
               + ["S1:%s" % reason for reason in right["reasons"]])
    for label, record in (("S0", reference_record), ("S1", arm_record)):
        parsed = record.get("parsed") or {}
        shape = representation(parsed.get("collapsed") or [])
        if shape["degenerate"]:
            reasons.append("%s:%s" % (label, REPRESENTATION_DEGENERACY))
    return {"status": PAIR_EVALUABLE if not reasons else PAIR_NON_EVALUABLE,
            "reasons": reasons, "S0": left, "S1": right}


def probe_verdict(pair_statuses) -> str:
    values = list(pair_statuses)
    if len(values) != 3 or any(value != PAIR_EVALUABLE for value in values):
        return INCONCLUSIVE
    return DECISION_ELIGIBLE
