"""Stage 2 비교 논리 — PAIRED_OUTPUT_SENSITIVITY (2026-09-08 · freeze).

```
0.5fps arm 출력을 ground truth로 부르지 않는다. 둘 다 같은 Qwen3-VL 출력이다.
매칭 허용오차는 (4.0, 8.0) 두 값을 나란히 보고한다 — 사후에 하나를 고르지 않는다.
```

문자 유사도는 **매칭 동률을 가르는 보조 키**로만 쓴다. 유사도 임계값을 만들지
않는다 — 매칭 여부는 시간 허용오차만으로 결정된다.
"""
import json
import re

import wvr_density as density

TOLERANCES = density.MATCH_TOLERANCE_SEC

PARSE_OK = "OK"
PARSE_FAILURE = "PARSE_FAILURE"
CONTRACT_VIOLATION = "CONTRACT_VIOLATION"


class CompareError(ValueError):
    """비교 계약 위반."""


def parse_events(raw: str, window) -> dict:
    """진단 출력 파싱. 실패는 실패로 남기고 되살리지 않는다."""
    text = (raw or "").strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {"status": PARSE_FAILURE, "events": [], "violations": [],
                "reason": "JSON 객체가 없다"}
    try:
        payload = json.loads(match.group(0))
    except ValueError as error:
        return {"status": PARSE_FAILURE, "events": [], "violations": [],
                "reason": str(error)[:200]}
    rows = payload.get("observed_events")
    if not isinstance(rows, list):
        return {"status": CONTRACT_VIOLATION, "events": [], "violations": [],
                "reason": "observed_events가 목록이 아니다"}

    events, violations = [], []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            violations.append({"index": index, "reason": "객체가 아니다"})
            continue
        stamp = row.get("approx_time")
        if not isinstance(stamp, (int, float)):
            violations.append({"index": index, "reason": "approx_time이 수가 아니다"})
            continue
        stamp = float(stamp)
        inside = window["start_sec"] <= stamp <= window["end_sec"]
        if not inside:
            violations.append({"index": index, "reason": "창 밖 시각",
                               "approx_time": stamp})
        entities = row.get("visible_entities")
        events.append({
            "index": index, "approx_time": stamp,
            "event": str(row.get("event", "")),
            "visible_entities": [str(item) for item in entities]
            if isinstance(entities, list) else [],
            "activity": str(row.get("activity", "")),
            "inside_window": inside,
        })
    status = PARSE_OK if events else CONTRACT_VIOLATION
    return {"status": status, "events": events, "violations": violations,
            "reason": "" if status == PARSE_OK else "event가 없다"}


def truncated_at_cap(record) -> bool:
    """생성이 max_new_tokens에서 끊겼는가 — 끊긴 JSON은 비교 대상이 아니다."""
    metrics = record.get("metrics") or {}
    generated = metrics.get("generated_token_count")
    cap = (record.get("requested") or {}).get("max_new_tokens")
    return bool(generated and cap and generated >= cap)


def non_degenerate(record) -> bool:
    """비교가 성립할 최소 조건.

    **2026-09-09 실행분을 이 조건으로 재판정하지 않는다** — 그 실행은
    `INCONCLUSIVE / OUTPUT_TRUNCATED_AT_CAP`으로 동결됐다. 이 함수는 다음
    사건에서 공허한 통과를 막기 위한 전제조건이다.
    """
    parsed = record.get("parsed") or {}
    return bool(parsed.get("status") == PARSE_OK and parsed.get("events")
                and not truncated_at_cap(record))


def bigrams(text: str) -> set:
    cleaned = re.sub(r"\s+", "", text or "")
    return {cleaned[index:index + 2] for index in range(len(cleaned) - 1)}


def similarity(left: str, right: str) -> float:
    """문자 bigram Jaccard. 매칭 동률을 가르는 보조 키다."""
    first, second = bigrams(left), bigrams(right)
    if not first and not second:
        return 1.0
    if not first or not second:
        return 0.0
    return round(len(first & second) / len(first | second), 4)


def jaccard(left, right) -> float:
    first, second = set(left or ()), set(right or ())
    if not first and not second:
        return 1.0
    if not first or not second:
        return 0.0
    return round(len(first & second) / len(first | second), 4)


def match(reference_events, arm_events, tolerance: float) -> dict:
    """시간 허용오차 안에서 1:1 매칭. 유사도는 동률 정렬에만 쓴다."""
    if tolerance <= 0:
        raise CompareError("허용오차가 0 이하다: %r" % tolerance)
    candidates = []
    for left in reference_events:
        for right in arm_events:
            delta = abs(left["approx_time"] - right["approx_time"])
            if delta <= tolerance:
                candidates.append((
                    -similarity(left["event"], right["event"]), delta,
                    left["index"], right["index"], left, right))
    candidates.sort(key=lambda row: row[:4])

    used_left, used_right, pairs = set(), set(), []
    for negative_similarity, delta, left_index, right_index, left, right \
            in candidates:
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        pairs.append({
            "reference_index": left_index, "arm_index": right_index,
            "reference_time": left["approx_time"],
            "arm_time": right["approx_time"], "time_delta": round(delta, 3),
            "event_similarity": round(-negative_similarity, 4),
            "entity_jaccard": jaccard(left["visible_entities"],
                                      right["visible_entities"]),
            "activity_similarity": similarity(left["activity"],
                                              right["activity"]),
            "reference_event": left["event"], "arm_event": right["event"],
        })
    pairs.sort(key=lambda row: row["reference_index"])
    return {
        "tolerance_sec": tolerance, "pairs": pairs,
        "only_reference": [event for event in reference_events
                           if event["index"] not in used_left],
        "only_arm": [event for event in arm_events
                     if event["index"] not in used_right],
    }


def order_inversions(pairs) -> int:
    """매칭된 쌍에서 순서가 뒤집힌 횟수 (Kendall tau distance)."""
    ranks = [pair["arm_index"] for pair in pairs]
    return sum(1 for left in range(len(ranks))
               for right in range(left + 1, len(ranks))
               if ranks[left] > ranks[right])


def compare(reference_parsed, arm_parsed) -> dict:
    """두 arm 비교. 허용오차별 결과를 모두 남긴다."""
    reference_events = reference_parsed["events"]
    arm_events = arm_parsed["events"]
    per_tolerance = {}
    for tolerance in TOLERANCES:
        matched = match(reference_events, arm_events, tolerance)
        similarities = [pair["event_similarity"] for pair in matched["pairs"]]
        entity_scores = [pair["entity_jaccard"] for pair in matched["pairs"]]
        per_tolerance["tol_%.1f" % tolerance] = {
            **matched,
            "matched_count": len(matched["pairs"]),
            "only_reference_count": len(matched["only_reference"]),
            "only_arm_count": len(matched["only_arm"]),
            "order_inversions": order_inversions(matched["pairs"]),
            "event_similarity": density.distribution(similarities)
            if similarities else None,
            "entity_jaccard": density.distribution(entity_scores)
            if entity_scores else None,
            "identical_entity_pairs": sum(
                1 for pair in matched["pairs"] if pair["entity_jaccard"] == 1.0),
        }
    return {
        "reference_status": reference_parsed["status"],
        "arm_status": arm_parsed["status"],
        "reference_event_count": len(reference_events),
        "arm_event_count": len(arm_events),
        "event_count_delta": len(arm_events) - len(reference_events),
        "reference_violations": len(reference_parsed["violations"]),
        "arm_violations": len(arm_parsed["violations"]),
        "per_tolerance": per_tolerance,
        "note": ("0.5fps arm은 ground truth가 아니다. 둘 다 같은 모델 출력이고, "
                 "허용오차 두 값의 결과를 함께 본다."),
    }
