"""WVR_EVENT_MAP_COVERAGE_SHADOW_V1 계측기 (2026-09-10 · freeze).

사전등록: `docs/preregistration/WVR_EVENT_MAP_COVERAGE_SHADOW_V1_2026-09-10.md`

```
목적   기존 SHADOW_V1의 23개 VALID 창 event만으로 whole-video 흐름을 어느 정도
      복원할 수 있는지 결정적으로 계산한다 (새 추론 0회 · GPU 불필요)
원칙   partial-failure tolerant — INVALID 창은 채우지 않고 unresolved로 남긴다
금지   synthetic event · silent concat · W00 재실행 · 새 LLM 호출 ·
      Overview/Analysis/Conclusion 생성 · semantic 최종 판정
```

이 모듈은 순수 계산만 한다. 파일 입출력은 `scripts/wvr_event_map_build.py`가 한다.
"""
import wvr_density_v2 as v2
import wvr_shadow_v1 as sh
import wvr_subdivision_v1 as sd

EVENT = "WVR_EVENT_MAP_COVERAGE_SHADOW_V1"
ARTIFACT_TAG = "event_map_v1"

# ── 입력 범위 (사전등록 §2) ────────────────────────────────────────
VIDEO_SEC = sh.RANGE_END_SEC                      # 600.0
VALID_SOURCE_WINDOWS = tuple("W%02d" % index for index in range(1, 24))
INVALID_SOURCE_WINDOWS = ("W00",)
EXPECTED_VALID_SOURCE_COUNT = 23
VALID_SOURCE_MANIFEST_SHA256 = (
    "a0726a4b13b4bd0f6e1ea692eec55e8cd0343132e32b532283e6e68511680631")
FRAME_BANK_MANIFEST = "shadow_frame_bank.json"
SAMPLING_FPS = sh.SAMPLING_FPS

# ── 동결 규칙값 ────────────────────────────────────────────────────
MIN_CHAPTER_SEC = 60.0
SUSTAINED_LOOKBACK = 2                            # k-1, k-2와 모두 disjoint
ARTIFACT_NAME = "CANDIDATE_EVENT_MAP"             # verified Event Map이 아니다

NEW_INFERENCE_ALLOWED = False
SYNTHETIC_EVENT_ALLOWED = False
CONCAT_FALLBACK_ALLOWED = False
W00_AS_EVENT_SOURCE_ALLOWED = False
W00_RERUN_ALLOWED = False
PROMPT_MUTATION_ALLOWED = False
BLIND_MAP_REVEAL_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False
CHAPTER_TITLE_GENERATION_ALLOWED = False
OVERVIEW_GENERATION_ALLOWED = False
SHADOW_V1_RETROACTIVE_PASS_ALLOWED = False
PRODUCTION_PROMOTION_ALLOWED = False

# ── relation 어휘 (reviewer 후보 라벨 · 판정 authority 아님) ────────
SAME_EVENT = "POSSIBLE_SAME_EVENT"
CONTINUATION = "POSSIBLE_CONTINUATION"
TRANSITION = "POSSIBLE_TRANSITION"
CONFLICT = "POSSIBLE_CONFLICT"
UNRESOLVED_RELATION = "UNRESOLVED"
RELATIONS = (SAME_EVENT, CONTINUATION, TRANSITION, CONFLICT,
             UNRESOLVED_RELATION)
GROUPING_RELATIONS = (SAME_EVENT, CONTINUATION)
RELATION_ROLE = "CANDIDATE_LABEL_NOT_FACTUAL_AUTHORITY"

# ── coverage 상태 어휘 ─────────────────────────────────────────────
MULTI_OBSERVED = "MULTI_WINDOW_OBSERVED"
SINGLE_OBSERVED = "SINGLE_WINDOW_OBSERVED"
OBSERVED = "OBSERVED"
INVALID_ONLY = "INVALID_WINDOW_ONLY"
UNRESOLVED_COVERAGE = "UNRESOLVED"
COVERAGE_STATUSES = (MULTI_OBSERVED, SINGLE_OBSERVED, INVALID_ONLY,
                     UNRESOLVED_COVERAGE)

# ── reviewer 전용 (executor가 계산하지 않는다) ──────────────────────
REVIEWER_QUESTIONS = ("FLOW_RECOVERABLE", "GAP_MATERIALITY",
                      "EVENT_MAP_USABLE")
REVIEWER_VERDICTS = ("EVENT_MAP_SHADOW_PASS", "EVENT_MAP_SHADOW_HOLD",
                     "EVENT_MAP_SHADOW_INCONCLUSIVE")
EXECUTOR_STATE = "EXECUTED / REVIEW_PENDING"

ALLOWED_MAX_CONCLUSION = (
    "Existing valid C01 local-window observations were sufficient to construct "
    "a usable shadow candidate of the video's global event flow despite "
    "explicitly preserved unresolved coverage.")
FORBIDDEN_CONCLUSIONS = (
    "Event extraction solved", "0.5fps sufficient", "all events factual",
    "production ready", "SHADOW_V1이 PASS로 바뀐다",
    "unresolved 구간을 추정으로 채웠다", "chapter boundary가 확정됐다")
COVERAGE_CAVEAT = "coverage percentage ≠ semantic correctness"

PRIOR_STATE = {
    "WVR_EVENT_EXTRACTION_SHADOW_V1": "CLOSED / INCONCLUSIVE",
    "WVR_W00_TRIGGER_ISOLATION_V1":
        "CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED",
    "WVR_W00_VISUAL_CONTENT_ISOLATION_V1":
        "CLOSED / VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED",
    "SUBDIVISION_family": "STOPPED / NOT SUFFICIENT",
    "WVR_W00_ZERO_DURATION_EXEMPLAR_ISOLATION_V1":
        "NOT EXECUTED / SUPERSEDED (추론 0회 · 산출물 0건)",
    "W00": "WINDOW_INVALID (invalid source · 재실행 금지)",
}

NORMATIVE_AUTHORITY = (
    "WVR_EVENT_MAP_COVERAGE_SHADOW_V1 preregistration",
    "frozen SHADOW_V1 execution artifacts",
    "frozen parser/collapse/relation rules (wvr_density_v2)",
    "prior isolation results",
    "PROJECT_OVERVIEW.md",
)

BOUNDARY_CONTRACT = (
    "local window boundary ≠ event boundary ≠ chapter boundary ≠ report boundary")


class EventMapError(RuntimeError):
    """event map 계약 위반."""


def window_span(window_id: str) -> tuple:
    window = sh.window_by_id(window_id)
    return (window["start_sec"], window["end_sec"])


def event_id(window_id: str, index: int) -> str:
    return "%s_E%03d" % (window_id, index + 1)


def _content(event: dict) -> dict:
    return {"actor": event.get("actor", ""), "action": event.get("action", ""),
            "object_or_state": event.get("object_or_state", "")}


def registry(records: dict) -> list:
    """W01→W23 순서로 collapsed event를 그대로 읽어 ID를 붙인다."""
    if W00_AS_EVENT_SOURCE_ALLOWED:
        raise EventMapError("W00은 event source로 쓸 수 없다")
    rows = []
    for window_id in VALID_SOURCE_WINDOWS:
        record = records.get(window_id)
        if record is None:
            raise EventMapError("source가 없다: %s" % window_id)
        if window_id in INVALID_SOURCE_WINDOWS:
            raise EventMapError("invalid source가 섞였다: %s" % window_id)
        validity = record.get("validity") or {}
        if validity.get("status") != sh.WINDOW_VALID:
            raise EventMapError("%s가 VALID가 아니다: %r"
                                % (window_id, validity.get("status")))
        collapsed = ((record.get("parsed") or {}).get("collapsed")) or []
        start, end = window_span(window_id)
        for index, event in enumerate(collapsed):
            rows.append({
                "event_id": event_id(window_id, index),
                "source_window": window_id,
                "source_window_span": [start, end],
                "collapsed_index": index,
                "start_sec": round(float(event["start_sec"]), 3),
                "end_sec": round(float(event["end_sec"]), 3),
                "actor": event.get("actor", ""),
                "action": event.get("action", ""),
                "object_or_state": event.get("object_or_state", ""),
                "collapsed_count": event.get("collapsed_count"),
                "source_indices": list(event.get("source_indices") or []),
                "source_raw_hash": record.get("raw_output_hash"),
                "source_collapse_hash": record.get("collapse_output_hash"),
            })
    return rows


def overlap_length(left: dict, right: dict) -> float:
    low = max(float(left["start_sec"]), float(right["start_sec"]))
    high = min(float(left["end_sec"]), float(right["end_sec"]))
    return round(max(0.0, high - low), 3)


def gap_length(left: dict, right: dict) -> float:
    if overlap_length(left, right) > 0:
        return 0.0
    if float(left["end_sec"]) <= float(right["start_sec"]):
        return round(float(right["start_sec"]) - float(left["end_sec"]), 3)
    return round(float(left["start_sec"]) - float(right["end_sec"]), 3)


def relation_label(left: dict, right: dict) -> dict:
    """사전등록 §6. 기존 frozen v2 규칙 + 시간 교차/접함만 쓴다."""
    relation = v2.semantic_relation(_content(left), _content(right))
    overlap = overlap_length(left, right)
    gap = gap_length(left, right)
    if overlap > 0:
        if relation["relation"] == v2.SEMANTICALLY_EQUIVALENT:
            label = SAME_EVENT
        elif relation["relation"] == v2.SEMANTICALLY_DIFFERENT:
            label = CONFLICT
        else:
            label = UNRESOLVED_RELATION
    elif gap == 0.0:
        label = (CONTINUATION
                 if relation["relation"] == v2.SEMANTICALLY_EQUIVALENT
                 else TRANSITION)
    else:
        return {}
    return {"relation": label, "overlap_sec": overlap, "gap_sec": gap,
            "semantic_relation": relation["relation"],
            "shared_token_count": len(
                v2.tokens(_content(left)) & v2.tokens(_content(right))),
            "role": RELATION_ROLE}


def adjacent_window_pairs() -> list:
    """인접 VALID window 쌍 (W01–W02 … W22–W23)."""
    rows = []
    for index in range(len(VALID_SOURCE_WINDOWS) - 1):
        earlier = VALID_SOURCE_WINDOWS[index]
        later = VALID_SOURCE_WINDOWS[index + 1]
        low = max(window_span(earlier)[0], window_span(later)[0])
        high = min(window_span(earlier)[1], window_span(later)[1])
        rows.append({"earlier": earlier, "later": later,
                     "shared_start_sec": low, "shared_end_sec": high})
    return rows


def relation_candidates(rows) -> list:
    """인접 VALID window 쌍의 event 쌍에만 relation 후보를 만든다."""
    by_window = {}
    for row in rows:
        by_window.setdefault(row["source_window"], []).append(row)
    out = []
    for pair in adjacent_window_pairs():
        for left in by_window.get(pair["earlier"], []):
            for right in by_window.get(pair["later"], []):
                label = relation_label(left, right)
                if not label:
                    continue
                out.append({"earlier_event": left["event_id"],
                            "later_event": right["event_id"],
                            "earlier_window": pair["earlier"],
                            "later_window": pair["later"],
                            "shared_start_sec": pair["shared_start_sec"],
                            "shared_end_sec": pair["shared_end_sec"],
                            **label})
    return out


def bucket_members(rows, find) -> dict:
    """root별 member 묶음. group_events가 이 결과의 총원을 다시 검사한다."""
    buckets = {}
    for row in rows:
        buckets.setdefault(find(row["event_id"]), []).append(row)
    return buckets


def group_events(rows, relations) -> list:
    """SAME_EVENT·CONTINUATION 관계로 union-find. 단순 concat이 아니다."""
    if CONCAT_FALLBACK_ALLOWED:
        raise EventMapError("silent concat fallback은 금지돼 있다")
    parent = {row["event_id"]: row["event_id"] for row in rows}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        parent[second] = first

    for relation in relations:
        if relation["relation"] in GROUPING_RELATIONS:
            union(relation["earlier_event"], relation["later_event"])

    index_by_id = {row["event_id"]: row for row in rows}
    buckets = bucket_members(rows, find)

    groups = []
    for members in buckets.values():
        members = sorted(members, key=lambda row: (row["start_sec"],
                                                   row["event_id"]))
        signatures = {v2.signature(_content(row)) for row in members}
        groups.append({
            "members": [row["event_id"] for row in members],
            "member_count": len(members),
            "start_sec": min(row["start_sec"] for row in members),
            "end_sec": max(row["end_sec"] for row in members),
            "source_windows": sorted({row["source_window"]
                                      for row in members}),
            "actor": members[0]["actor"], "action": members[0]["action"],
            "object_or_state": members[0]["object_or_state"],
            "distinct_signature_count": len(signatures),
            "mixed_signature": len(signatures) > 1,
        })
    groups.sort(key=lambda group: (group["start_sec"], group["members"][0]))
    for index, group in enumerate(groups):
        group["group_id"] = "G%03d" % (index + 1)
    if len(index_by_id) != sum(group["member_count"] for group in groups):
        raise EventMapError("group member 수가 event 수와 다르다")
    return groups


def group_transitions(groups) -> list:
    """연속 group 쌍의 transition 후보 (같은 §6 규칙)."""
    rows = []
    for index in range(len(groups) - 1):
        left, right = groups[index], groups[index + 1]
        label = relation_label(left, right)
        rows.append({
            "from_group": left["group_id"], "to_group": right["group_id"],
            "at_sec": right["start_sec"],
            "relation": label.get("relation") or "NO_TEMPORAL_RELATION",
            "semantic_relation": label.get("semantic_relation")
            or v2.semantic_relation(_content(left),
                                    _content(right))["relation"],
            "gap_sec": round(max(0.0, right["start_sec"] - left["end_sec"]),
                             3),
            "overlap_sec": overlap_length(left, right),
            "actor_changed": v2.normalize(left["actor"])
            != v2.normalize(right["actor"]),
            "role": RELATION_ROLE,
        })
    return rows


def _content_tokens(group: dict) -> set:
    """action+object 토큰만 (actor는 별도 신호로 본다)."""
    return v2.tokens({"actor": "", "action": group.get("action", ""),
                      "object_or_state": group.get("object_or_state", "")})


def boundary_signals(groups) -> list:
    """사전등록 §9. actor 변경 또는 지속된 토큰 disjoint."""
    rows = []
    for index in range(1, len(groups)):
        current, previous = groups[index], groups[index - 1]
        actor_changed = (v2.normalize(current["actor"])
                         != v2.normalize(previous["actor"]))
        tokens_now = _content_tokens(current)
        disjoint_prev = not (tokens_now & _content_tokens(previous))
        disjoint_prev2 = True
        if index >= SUSTAINED_LOOKBACK:
            disjoint_prev2 = not (tokens_now
                                  & _content_tokens(groups[index - 2]))
        sustained = disjoint_prev and disjoint_prev2
        rows.append({
            "group_id": current["group_id"], "at_sec": current["start_sec"],
            "actor_changed": actor_changed,
            "content_disjoint_prev": disjoint_prev,
            "content_disjoint_prev2": disjoint_prev2,
            "sustained_content_change": sustained,
            "is_boundary_candidate": bool(actor_changed or sustained),
        })
    return rows


def chapter_candidates(groups) -> dict:
    """boundary 후보에 MIN_CHAPTER_SEC를 적용해 chapter 후보를 만든다."""
    if CHAPTER_TITLE_GENERATION_ALLOWED:
        raise EventMapError("chapter 제목 생성은 이번 사건에서 금지다")
    if not groups:
        return {"chapters": [], "signals": [], "suppressed": [],
                "min_chapter_sec": MIN_CHAPTER_SEC}
    signals = boundary_signals(groups)
    used, suppressed = [], []
    current_start = groups[0]["start_sec"]
    for signal in signals:
        if not signal["is_boundary_candidate"]:
            continue
        if signal["at_sec"] - current_start < MIN_CHAPTER_SEC:
            suppressed.append({**signal, "reason": "MIN_CHAPTER_SEC",
                               "chapter_start_sec": current_start})
            continue
        used.append(signal)
        current_start = signal["at_sec"]

    boundary_ids = {signal["group_id"] for signal in used}
    chapters, bucket = [], []
    for group in groups:
        if bucket and group["group_id"] in boundary_ids:
            chapters.append(bucket)
            bucket = []
        bucket.append(group)
    if bucket:
        chapters.append(bucket)

    rows = []
    for index, bucket in enumerate(chapters):
        rows.append({
            "chapter_id": "CH%02d" % (index + 1),
            "start_sec": bucket[0]["start_sec"],
            "end_sec": max(group["end_sec"] for group in bucket),
            "group_ids": [group["group_id"] for group in bucket],
            "group_count": len(bucket),
            "source_windows": sorted({window for group in bucket
                                      for window in group["source_windows"]}),
            "boundary_signal": ("FIRST_CHAPTER" if index == 0 else next(
                (signal for signal in used
                 if signal["group_id"] == bucket[0]["group_id"]), None)),
            "semantic_boundary_confirmed": False,
        })
    return {"chapters": rows, "signals": signals, "suppressed": suppressed,
            "min_chapter_sec": MIN_CHAPTER_SEC,
            "boundary_source": "event content (actor 변경 · 지속된 토큰 disjoint)",
            "window_grid_used_as_boundary": False,
            "semantic_verdict_by_executor": SEMANTIC_VERDICT_BY_EXECUTOR}


def union_length(intervals) -> float:
    total, cursor_end = 0.0, None
    for start, end in sorted((float(start), float(end))
                             for start, end in intervals):
        if end <= start:
            continue
        if cursor_end is None or start > cursor_end:
            total += end - start
            cursor_end = end
        elif end > cursor_end:
            total += end - cursor_end
            cursor_end = end
    return round(total, 3)


def union_intervals(intervals) -> list:
    out = []
    for start, end in sorted((float(start), float(end))
                             for start, end in intervals):
        if end <= start:
            continue
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return [[round(start, 3), round(end, 3)] for start, end in out]


def complement_intervals(intervals, start=0.0, end=None) -> list:
    end = VIDEO_SEC if end is None else end
    out, cursor = [], start
    for low, high in union_intervals(intervals):
        if low > cursor:
            out.append([round(cursor, 3), round(low, 3)])
        cursor = max(cursor, high)
    if cursor < end:
        out.append([round(cursor, 3), round(end, 3)])
    return out


def coverage_map(rows) -> dict:
    """window/event/redundant/unresolved coverage와 구간 상태 timeline."""
    valid_spans = [window_span(window_id)
                   for window_id in VALID_SOURCE_WINDOWS]
    invalid_spans = [window_span(window_id)
                     for window_id in INVALID_SOURCE_WINDOWS]
    event_spans = [(row["start_sec"], row["end_sec"]) for row in rows]

    edges = {0.0, VIDEO_SEC}
    for start, end in valid_spans + invalid_spans + event_spans:
        edges.add(round(float(start), 3))
        edges.add(round(float(end), 3))
    marks = sorted(value for value in edges if 0.0 <= value <= VIDEO_SEC)

    segments, redundant_window, redundant_event = [], [], []
    for index in range(len(marks) - 1):
        low, high = marks[index], marks[index + 1]
        if high <= low:
            continue
        middle = (low + high) / 2.0
        windows = [window_id for window_id in VALID_SOURCE_WINDOWS
                   if window_span(window_id)[0] <= middle
                   < window_span(window_id)[1]]
        sources = sorted({row["source_window"] for row in rows
                          if row["start_sec"] <= middle < row["end_sec"]})
        events = [row["event_id"] for row in rows
                  if row["start_sec"] <= middle < row["end_sec"]]
        if len(windows) >= 2:
            redundant_window.append((low, high))
        if len(sources) >= 2:
            redundant_event.append((low, high))
        if sources:
            status = (MULTI_OBSERVED if len(sources) >= 2
                      else SINGLE_OBSERVED)
        elif any(start <= middle < end for start, end in invalid_spans):
            status = INVALID_ONLY
        else:
            status = UNRESOLVED_COVERAGE
        segments.append({"start_sec": round(low, 3),
                         "end_sec": round(high, 3),
                         "duration_sec": round(high - low, 3),
                         "status": status,
                         "valid_windows": windows,
                         "event_source_windows": sources,
                         "event_ids": events})

    def merged(status_names):
        return union_intervals([(row["start_sec"], row["end_sec"])
                                for row in segments
                                if row["status"] in status_names])

    window_cov = union_length(valid_spans)
    event_cov = union_length(event_spans)
    unresolved = merged((UNRESOLVED_COVERAGE, INVALID_ONLY))
    return {
        "video_sec": VIDEO_SEC,
        "window_coverage_sec": window_cov,
        "window_coverage_pct": round(100.0 * window_cov / VIDEO_SEC, 2),
        "event_coverage_sec": event_cov,
        "event_coverage_pct": round(100.0 * event_cov / VIDEO_SEC, 2),
        "redundant_window_coverage_sec": union_length(redundant_window),
        "redundant_window_coverage_pct": round(
            100.0 * union_length(redundant_window) / VIDEO_SEC, 2),
        "redundant_event_coverage_sec": union_length(redundant_event),
        "redundant_event_coverage_pct": round(
            100.0 * union_length(redundant_event) / VIDEO_SEC, 2),
        "unresolved_sec": round(VIDEO_SEC - event_cov, 3),
        "unresolved_pct": round(100.0 * (VIDEO_SEC - event_cov) / VIDEO_SEC,
                                2),
        "event_coverage_intervals": union_intervals(event_spans),
        "unresolved_intervals": unresolved,
        "invalid_window_only_intervals": merged((INVALID_ONLY,)),
        "single_window_intervals": merged((SINGLE_OBSERVED,)),
        "multi_window_intervals": merged((MULTI_OBSERVED,)),
        "segments": segments,
        "status_seconds": {
            status: round(sum(row["duration_sec"] for row in segments
                              if row["status"] == status), 3)
            for status in COVERAGE_STATUSES},
        "caveat": COVERAGE_CAVEAT,
        "synthetic_event_inserted": SYNTHETIC_EVENT_ALLOWED,
    }


def frame_stamps(start: float, end: float, bank_times) -> list:
    """구간 안 0.5fps stamp (traceability 전용 · 지지 판정 아님)."""
    return [round(float(value), 3) for value in bank_times
            if float(start) <= float(value) < float(end)]


def anomalies(rows, relations, groups, coverage) -> dict:
    """리뷰어가 먼저 봐야 할 이상 항목만 모은다."""
    conflicts = [relation for relation in relations
                 if relation["relation"] == CONFLICT]
    unresolved_relations = [relation for relation in relations
                            if relation["relation"] == UNRESOLVED_RELATION]
    single = coverage["single_window_intervals"]
    return {
        "conflicting_relation_count": len(conflicts),
        "conflicting_relations": conflicts,
        "unresolved_relation_count": len(unresolved_relations),
        "single_window_only_intervals": single,
        "single_window_only_sec": union_length(
            [(row[0], row[1]) for row in single]),
        "invalid_source_dependencies": [row["event_id"] for row in rows
                                        if row["source_window"]
                                        in INVALID_SOURCE_WINDOWS],
        "mixed_signature_groups": [group["group_id"] for group in groups
                                   if group["mixed_signature"]],
        "uncovered_intervals": coverage["unresolved_intervals"],
    }


def executor_state(rows, groups, coverage) -> dict:
    """executor는 여기까지만 기록한다 — reviewer verdict를 계산하지 않는다."""
    return {
        "state": EXECUTOR_STATE,
        "artifact_name": ARTIFACT_NAME,
        "event_count": len(rows), "group_count": len(groups),
        "source_window_count": EXPECTED_VALID_SOURCE_COUNT,
        "new_inference_count": 0,
        "reviewer_questions": list(REVIEWER_QUESTIONS),
        "reviewer_verdicts": list(REVIEWER_VERDICTS),
        "semantic_verdict": None,
        "semantic_verdict_by_executor": SEMANTIC_VERDICT_BY_EXECUTOR,
        "allowed_max_conclusion": ALLOWED_MAX_CONCLUSION,
        "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS),
        "coverage_caveat": COVERAGE_CAVEAT,
        "boundary_contract": BOUNDARY_CONTRACT,
        "unresolved_pct": coverage["unresolved_pct"],
        "shadow_v1_retroactive_pass_allowed":
            SHADOW_V1_RETROACTIVE_PASS_ALLOWED,
    }


def source_manifest(observed: dict) -> dict:
    """valid source 46파일 해시가 동결 manifest와 같은지."""
    import hashlib

    lines = "\n".join("%s %s" % (name, observed[name])
                      for name in sorted(observed))
    digest = hashlib.sha256(lines.encode("utf-8")).hexdigest()
    return {"observed_count": len(observed),
            "expected_count": EXPECTED_VALID_SOURCE_COUNT * 2,
            "manifest_sha256": digest,
            "expected_manifest_sha256": VALID_SOURCE_MANIFEST_SHA256,
            "unchanged": digest == VALID_SOURCE_MANIFEST_SHA256
            and len(observed) == EXPECTED_VALID_SOURCE_COUNT * 2}


def dedup(values) -> list:
    return sd.dedup(values)
