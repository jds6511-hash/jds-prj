"""WVR_SAMPLING_SEMANTIC_DENSITY_EVIDENCE_RESOLUTION_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_EVIDENCE_RESOLUTION_V1_2026-09-09.md`

```
새 추론 없음. frozen V2 산출물 + 채택 제출본 canonical evidence만 읽는다.
evidence 채널은 사실 권위가 아니다 —
  caption  = Qwen2.5-VL-3B-4bit 출력(다른 모델·다른 표집) → 기기간 일치, 진리 아님
  subtitle = Whisper ASR(발화 채널) → 발화된 것만 덮는다
따라서 판정값은 참·거짓이 아니라 이 evidence 층에 대한
SUPPORTS·CONTRADICTS·UNRESOLVED다. evidence에 없음은 절대 CONTRADICTS가 아니다.
```
"""
import wvr_density as density
import wvr_density_v2 as v2
import wvr_evidence_lexicon as lex

EVENT = "WVR_SAMPLING_SEMANTIC_DENSITY_EVIDENCE_RESOLUTION_V1"
TOLERANCES = density.MATCH_TOLERANCE_SEC
PRIMARY_TOLERANCE = TOLERANCES[0]
CHANNELS = ("caption", "subtitle")

NEW_INFERENCE_ALLOWED = False
SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED = False
PROMOTION_ALLOWED = False
EVENT_EXTRACTION_APPROVED = False

EXPECTED_SEGMENTS_SHA256 = (
    "aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92")
EXPECTED_VIDEO_SHA256 = (
    "ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc")
CANONICAL_PATH = "runs/vad0_paired/s1_shadow/S5/aar_canonical.json"
SEGMENTS_PATH = "work_full/full_xekZO4n4QuE/segments.json"

# evidence로 쓰지 않는 것 (episode summary는 하류 LLM 출력이다)
NON_EVIDENCE_FIELDS = ("summary", "dialogue_note")

# 사전등록 전에 이미 열람한 구간 (감사 공개 · idx 60~63 = 300~320초)
PRE_FREEZE_VIEWED_SEG_IDX = (60, 61, 62, 63)

EVIDENCE_SUPPORTS = "EVIDENCE_SUPPORTS"
EVIDENCE_CONTRADICTS = "EVIDENCE_CONTRADICTS"
EVIDENCE_UNRESOLVED = "EVIDENCE_UNRESOLVED"

REFERENCE_ONLY = "REFERENCE_ONLY_SUPPORTED"
ARM_ONLY = "ARM_ONLY_SUPPORTED"
BOTH_SUPPORTED = "BOTH_SUPPORTED_AT_DIFFERENT_SEGMENTS"
NEITHER_RESOLVED = "NEITHER_RESOLVED"

BRANCH_A = "BRANCH_A_HIGHER_DENSITY_COLLAPSE_SUPPORTED"
BRANCH_B = "BRANCH_B_REDUCED_SAMPLING_DETAIL_UNSUPPORTED"
BRANCH_C = "BRANCH_C_EVIDENCE_INCONCLUSIVE"

LEXICON_UNCOVERED = "LEXICON_UNCOVERED"
SELECTOR_INCOMPLETE = "SELECTOR_INCOMPLETE"

SOURCE_DETERMINISTIC = "DETERMINISTIC_DOUBLY_DISJOINT"
SOURCE_REVIEWER = "REVIEWER_NAMED"

# 리뷰어가 지목한 충돌 (메시지 원문 기준 · 동결). (pair, reference 구간, arm 구간)
REVIEWER_NAMED_CONFLICTS = (
    ("D1", (312.0, 480.0), (380.0, 390.0)),
    ("D1", (312.0, 480.0), (420.0, 450.0)),
    ("D1", (312.0, 480.0), (450.0, 460.0)),
    ("D1", (312.0, 480.0), (470.0, 480.0)),
    ("D2", (96.0, 210.0), (104.0, 112.0)),
    ("D2", (96.0, 210.0), (112.0, 120.0)),
    ("D2", (96.0, 210.0), (128.0, 136.0)),
    ("D2", (96.0, 210.0), (136.0, 152.0)),
)


def claim_terms(event) -> dict:
    """claim의 action·object 토큰을 사전 표면형 집합으로 바꾼다."""
    action_tokens = sorted(v2.tokens({"action": event.get("action", "")}))
    object_tokens = sorted(v2.tokens(
        {"object_or_state": event.get("object_or_state", "")}))
    action = sorted({term for token in action_tokens
                     for term in lex.action_terms(token)})
    obj = sorted({term for token in object_tokens
                  for term in lex.object_terms(token)})
    return {
        "action_tokens": action_tokens, "object_tokens": object_tokens,
        "action_terms": action, "object_terms": obj,
        "covered": bool(action) and bool(obj),
    }


def doubly_disjoint(reference, arm) -> bool:
    """action 토큰도, object 토큰도 서로 겹치지 않는 쌍."""
    ref_action = v2.tokens({"action": reference.get("action", "")})
    arm_action = v2.tokens({"action": arm.get("action", "")})
    ref_obj = v2.tokens(
        {"object_or_state": reference.get("object_or_state", "")})
    arm_obj = v2.tokens({"object_or_state": arm.get("object_or_state", "")})
    return not (ref_action & arm_action) and not (ref_obj & arm_obj)


def evidence_window(reference, arm) -> tuple:
    """겹치면 겹친 구간만, 안 겹치면 두 구간의 hull."""
    low = max(float(reference["start_sec"]), float(arm["start_sec"]))
    high = min(float(reference["end_sec"]), float(arm["end_sec"]))
    if low < high:
        return (low, high)
    return (min(float(reference["start_sec"]), float(arm["start_sec"])),
            max(float(reference["end_sec"]), float(arm["end_sec"])))


def candidate_pairs(reference_events, arm_events, tolerance) -> list:
    """시간 호환 + 이중 불일치인 쌍만 결정적으로 뽑는다."""
    rows = []
    for i, ref in enumerate(reference_events):
        for j, arm in enumerate(arm_events):
            if not v2.temporally_compatible(ref, arm, tolerance):
                continue
            if not doubly_disjoint(ref, arm):
                continue
            rows.append({
                "reference_index": i, "arm_index": j,
                "reference": ref, "arm": arm,
                "evidence_window": evidence_window(ref, arm),
                "source": [SOURCE_DETERMINISTIC],
            })
    return rows


def evidence_segments(segments, start, end) -> list:
    """[start, end)와 겹치는 5초 구간. 필요한 필드만 통과시킨다."""
    rows = []
    for seg in segments:
        if float(seg["start"]) < end and float(seg["end"]) > start:
            rows.append({
                "idx": seg["idx"], "start": float(seg["start"]),
                "end": float(seg["end"]),
                "caption": seg.get("caption") or "",
                "subtitle": seg.get("subtitle") or "",
                "pre_freeze_viewed": seg["idx"] in PRE_FREEZE_VIEWED_SEG_IDX,
            })
    return rows


def match_terms(text, terms) -> list:
    return [term for term in terms if term and term in (text or "")]


def claim_support(terms, segments) -> dict:
    """같은 구간·같은 채널에서 action 표면형과 object 표면형이 함께 나오면 지지."""
    hits, partial = [], []
    for seg in segments:
        for channel in CHANNELS:
            text = seg[channel]
            action_hit = match_terms(text, terms["action_terms"])
            object_hit = match_terms(text, terms["object_terms"])
            if action_hit and object_hit:
                shared = sorted(set(action_hit) & set(object_hit))
                independent = bool(set(action_hit) - set(object_hit)) and \
                    bool(set(object_hit) - set(action_hit))
                hits.append({"idx": seg["idx"], "channel": channel,
                             "action_matched": action_hit,
                             "object_matched": object_hit,
                             "shared_terms": shared,
                             "independent": independent,
                             "quote": text[:200]})
            elif action_hit or object_hit:
                partial.append({"idx": seg["idx"], "channel": channel,
                                "action_matched": action_hit,
                                "object_matched": object_hit})
    return {
        "supported": bool(hits), "hits": hits, "partial": partial,
        "lexicon_covered": terms["covered"],
        "independent_support": any(hit["independent"] for hit in hits),
        "shared_term_only_hits": sum(
            1 for hit in hits if not hit["independent"]),
        "segment_count": len(segments),
    }


def claim_verdict(support, competing_support) -> dict:
    """CONTRADICTS는 경쟁 claim의 적극적 지지가 있을 때만 성립한다."""
    reasons = []
    if not support["lexicon_covered"]:
        reasons.append(LEXICON_UNCOVERED)
    if support["supported"]:
        verdict = EVIDENCE_SUPPORTS
    elif competing_support["supported"] and support["lexicon_covered"]:
        verdict = EVIDENCE_CONTRADICTS
    else:
        verdict = EVIDENCE_UNRESOLVED
    return {"verdict": verdict, "reasons": reasons}


def pair_resolution(reference_verdict, arm_verdict) -> str:
    ref = reference_verdict == EVIDENCE_SUPPORTS
    arm = arm_verdict == EVIDENCE_SUPPORTS
    if ref and arm:
        return BOTH_SUPPORTED
    if ref:
        return REFERENCE_ONLY
    if arm:
        return ARM_ONLY
    return NEITHER_RESOLVED


def event_verdict(reference_only, arm_only) -> str:
    """분기는 사전등록된 두 수치로만 갈린다(both_supported는 별도 보고)."""
    if arm_only > 0 and reference_only == 0:
        return BRANCH_A
    if reference_only > 0 and arm_only == 0:
        return BRANCH_B
    return BRANCH_C


def reviewer_coverage(candidates, pair) -> dict:
    """리뷰어 지목 충돌이 결정적 selector에 들어왔는지 확인한다."""
    named = [row for row in REVIEWER_NAMED_CONFLICTS if row[0] == pair]
    found, missing = [], []
    for _, ref_span, arm_span in named:
        hit = any(
            (float(row["reference"]["start_sec"]),
             float(row["reference"]["end_sec"])) == ref_span
            and (float(row["arm"]["start_sec"]),
                 float(row["arm"]["end_sec"])) == arm_span
            for row in candidates)
        (found if hit else missing).append({"reference": list(ref_span),
                                            "arm": list(arm_span)})
    return {"named_count": len(named), "found": found, "missing": missing,
            "status": SELECTOR_INCOMPLETE if missing else "COMPLETE"}
