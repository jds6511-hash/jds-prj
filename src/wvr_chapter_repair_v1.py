"""WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1 계산기 (2026-09-10 · freeze).

사전등록:
`docs/preregistration/WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md`

```
교정 대상   ① 내부 경계 7/7이 region·24초 격자에 정렬 ② conflict chapter의
          uncertainty 미노출 ③ single-source chapter가 STABLE_DOMINANT
구조       Stage A(결정적 경계 추출 · LLM 없음) → 경계 동결 → Stage B(제목·요약만 LLM)
입력       conservative_event_map_v1.json (해시 동결) 하나뿐
금지       새 VLM 추론 · Track A 입력 · Event Map 재생성 · Overview 생성 ·
          LLM의 경계 추가·삭제·이동 · 격자 회피용 jitter · [0,24) 사실 생성 ·
          executor의 PASS/HOLD 계산
```

Stage A는 **event 내용 토큰의 domain 전환**에서만 후보를 만든다. region·격자 시각을
후보로 주입하지 않고, 사후 audit에서 일치 여부만 기록한다.
"""
import hashlib
import json
import re

import wvr_chapter_v1 as v1
import wvr_conservative_map_v1 as cmap
import wvr_density_v2 as v2

EVENT = "WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1"
PREREG = ("docs/preregistration/"
          "WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md")
ARTIFACT_TAG = "chapter_repair_v1"
SCHEMA = "wvr_chapter_repair_v1"
ARTIFACT_NAME = "SEMANTIC_CHAPTER_CANDIDATES_V2"      # 확정 Chapter가 아니다

# ── 입력 동결 ──────────────────────────────────────────────────────
SOURCE_MAP_NAME = v1.SOURCE_MAP_NAME
SOURCE_MAP_SHA256 = v1.SOURCE_MAP_SHA256              # 0ebecf34… (LF 정규형)
V1_CHAPTERS_NAME = "chapter_v1_chapters.json"
EXPECTED_SOURCE_EVENT_COUNT = cmap.EXPECTED_SOURCE_EVENT_COUNT      # 160
EXPECTED_REGION_COUNT = cmap.EXPECTED_REGION_COUNT                  # 11
VIDEO_START_SEC = cmap.VIDEO_START_SEC                              # 0.0
VIDEO_END_SEC = cmap.VIDEO_END_SEC                                  # 600.0
GRID_SEC = cmap.CELL_SEC                                            # 24.0
WINDOW_SEC = 48.0                                                   # 창 길이(감사용)

# ── 금지 플래그 ───────────────────────────────────────────────────
NEW_VLM_INFERENCE_ALLOWED = False
TRACK_A_INPUT_ALLOWED = False
EVENT_MAP_REBUILD_ALLOWED = False
LOCAL_EVENT_REEXTRACTION_ALLOWED = False
REGION_BOUNDARY_AS_CANDIDATE_ALLOWED = False          # §5
GRID_BOUNDARY_AS_CANDIDATE_ALLOWED = False            # §4
BOUNDARY_JITTER_ALLOWED = False                       # §8
LLM_MAY_CHANGE_BOUNDARIES_ALLOWED = False             # §9
LLM_MAY_SET_EVIDENCE_CLASS_ALLOWED = False            # §12
CONFLICT_RESOLUTION_ALLOWED = False
SYNTHETIC_FILL_ALLOWED = False
EVENT_TEXT_MUTATION_ALLOWED = False
OVERVIEW_GENERATION_ALLOWED = False
ANALYSIS_GENERATION_ALLOWED = False
REPORT_GENERATION_ALLOWED = False
RETRY_ALLOWED = False
VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False
FLAGS = ("NEW_VLM_INFERENCE_ALLOWED", "TRACK_A_INPUT_ALLOWED",
         "EVENT_MAP_REBUILD_ALLOWED", "LOCAL_EVENT_REEXTRACTION_ALLOWED",
         "REGION_BOUNDARY_AS_CANDIDATE_ALLOWED",
         "GRID_BOUNDARY_AS_CANDIDATE_ALLOWED", "BOUNDARY_JITTER_ALLOWED",
         "LLM_MAY_CHANGE_BOUNDARIES_ALLOWED",
         "LLM_MAY_SET_EVIDENCE_CLASS_ALLOWED", "CONFLICT_RESOLUTION_ALLOWED",
         "SYNTHETIC_FILL_ALLOWED", "EVENT_TEXT_MUTATION_ALLOWED",
         "OVERVIEW_GENERATION_ALLOWED", "ANALYSIS_GENERATION_ALLOWED",
         "REPORT_GENERATION_ALLOWED", "RETRY_ALLOWED", "VERDICT_BY_EXECUTOR",
         "PRODUCTION_PROMOTION_ALLOWED")
CHAPTER_LLM_ALLOWED = True                            # Stage B 제목·요약만

# ── Stage A 규칙 동결 (사전등록 §4~§8) ───────────────────────────────
DETECT_WINDOW_SEC = 30.0        # 경계 전후 근거 창 (24의 배수가 아니다)
SUSTAIN_WINDOW_SEC = 60.0       # 지속 전환 확인 창
MIN_CHAPTERS = 3
MAX_CHAPTERS = 10
# 최소 간격은 자유 선택이 아니라 chapter 상한에서 유도한다: 600/10 = 60
MIN_SEPARATION_SEC = round((VIDEO_END_SEC - VIDEO_START_SEC) / MAX_CHAPTERS, 3)

OBJECT_DOMAIN_CHANGE = "OBJECT_DOMAIN_CHANGE"
ACTIVITY_DOMAIN_CHANGE = "ACTIVITY_DOMAIN_CHANGE"
SCENE_OR_TASK_CHANGE = "SCENE_OR_TASK_CHANGE"
SUSTAINED_ACTIVITY_CHANGE = "SUSTAINED_ACTIVITY_CHANGE"
BOUNDARY_REASONS = (ACTIVITY_DOMAIN_CHANGE, SCENE_OR_TASK_CHANGE,
                    OBJECT_DOMAIN_CHANGE, SUSTAINED_ACTIVITY_CHANGE)
UNSUPPORTED_BY_CONFLICT = "BOUNDARY_UNSUPPORTED_BY_CONFLICT"

# ── evidence class 동결 (사전등록 §12 · executor가 계산한다) ───────────
STABLE_DOMINANT = "STABLE_DOMINANT"
MIXED_EVIDENCE = "MIXED_EVIDENCE"
LIMITED_EVIDENCE = "LIMITED_EVIDENCE"
EVIDENCE_CLASSES = (STABLE_DOMINANT, MIXED_EVIDENCE, LIMITED_EVIDENCE)
EVIDENCE_PRIORITY = (MIXED_EVIDENCE, LIMITED_EVIDENCE, STABLE_DOMINANT)

# conflict 노출 판정용 동결 어휘 (요약 문구를 강제하지 않고 존재만 본다)
DISCLOSURE_TERMS = ("disagree", "disagreement", "disagrees", "conflict",
                    "conflicting", "inconsistent", "differ", "differs",
                    "differing", "uncertain", "uncertainty")
MACHINE_DISCLOSURE = ("Local observations disagree on some actions or objects "
                      "in this interval; both source observations are kept "
                      "unresolved.")

# ── 생성 런타임 동결 (Stage B) ──────────────────────────────────────
LLM_MODEL_ID = v1.LLM_MODEL_ID                 # Qwen/Qwen2.5-7B-Instruct
LLM_DTYPE = v1.LLM_DTYPE                       # bfloat16
LLM_LOAD_4BIT = False
LLM_MAX_NEW_TOKENS = 4096
LLM_DO_SAMPLE = False
GENERATION_ATTEMPTS = 1

NOT_ADJUDICATED = "NOT_ADJUDICATED"
EXECUTOR_STATE = "EXECUTED / REVIEW_PENDING"
FINAL_VERDICTS = ("SEMANTIC_CHAPTER_REPAIR_PASS",
                  "SEMANTIC_CHAPTER_REPAIR_HOLD",
                  "SEMANTIC_CHAPTER_REPAIR_INCONCLUSIVE")
FINAL_VERDICT_VOCABULARY_LINE = ("SEMANTIC_CHAPTER_REPAIR_PASS / HOLD / "
                                 "INCONCLUSIVE")
FORBIDDEN_FIELD_NAMES = ("hypothesis", "truth", "preferred", "winner",
                         "likely", "score", "confidence_value", "best",
                         "overview", "analysis", "conclusion")
BLOCKERS = ("SOURCE_MAP_HASH_MISMATCH", "INSUFFICIENT_BOUNDARY_EVIDENCE",
            "BOUNDARY_SET_NOT_FROZEN", "RAW_NOT_PERSISTED", "PARSE_FAILURE",
            "SCHEMA_VIOLATION", "COVERAGE_VIOLATION", "LINEAGE_BROKEN",
            "LLM_CHANGED_BOUNDARIES", "EVIDENCE_CLASS_VIOLATION",
            "CONFLICT_DISCLOSURE_MISSING", "UNRESOLVED_FILLED",
            "RUNTIME_FAILURE", "CONFIG_MISMATCH")

PRIOR_STATE = {
    "WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1":
        "CLOSED / CONSERVATIVE_EVENT_MAP_PASS",
    "WVR_SEMANTIC_CHAPTER_SHADOW_V1": "CLOSED / SEMANTIC_CHAPTER_SHADOW_HOLD",
    "V1_reviewer_answers": {
        "WHOLE_VIDEO_STRUCTURE": "COARSELY YES",
        "BOUNDARY_QUALITY": "NO",
        "CONFLICT_SAFETY": "PARTIAL / NOT SUFFICIENT",
        "OVERVIEW_INPUT_USABILITY": "NO"},
    "W00": "WINDOW_INVALID (invalid source · 재실행 금지)",
}

ALLOWED_MAX_CONCLUSION = (
    "리뷰어가 PASS로 판정하면, chapter 경계를 window/region 기하가 아니라 event 수준 "
    "전환에서 만들고 conflict·근거 강도를 정직하게 표시한 chapter sequence를 "
    "Overview Shadow 입력으로 쓸 수 있다.")
FORBIDDEN_CONCLUSIONS = (
    "V1 HOLD가 해소됐다", "conflict가 해결됐다", "Event Map이 검증됐다",
    "0.5fps sufficient", "Overview를 만들어도 된다", "production ready")

# ── Stage B 프롬프트 (제목·요약만 · 경계는 이미 동결) ──────────────────
REPAIR_PROMPT_V1 = """You write titles and summaries for chapters of one video.

The chapter time ranges are already fixed. You must not change, add, remove or
merge them. You only name and describe what each chapter contains.

Each chapter below lists the observations recorded for its interval. Some
intervals were observed by two independent analysis passes that disagree; those
lines are marked CONFLICT and both readings are shown. Some intervals had only
one observing pass (SINGLE SOURCE). One interval has no valid observation at
all (NO OBSERVATION).

CHAPTERS
%(chapters)s
END OF CHAPTERS

For every chapter return:
- title: a short, broad, observable activity phrase in the style of
  "Vehicle maintenance" or "Whiteboard writing" — those two are style examples
  only and are unrelated to this video. Name what the listed observations show.
  No emotion, no intent, no purpose, no guessing beyond the observations.
- summary: one to three sentences about the recurring activity of the chapter.
  If the chapter is marked CONFLICT PRESENT, you must state in the summary that
  the local observations disagree about some actions or objects. Never pick one
  side as correct and never merge disagreeing readings into one asserted fact.
  If the chapter contains a NO OBSERVATION span, do not describe that span.
- dominant_activities: two to four short activity phrases.

Do not output times, chapter counts, confidence values, evidence labels or any
field other than the three above.

Return only JSON, no prose, no code fence, in exactly this form:

{"chapters": {"CH01": {"title": "...", "summary": "...",
"dominant_activities": ["...", "..."]}}}
"""
REPAIR_PROMPT_NAME = "REPAIR_PROMPT_V1"


class RepairError(RuntimeError):
    """boundary repair 계약 위반."""


def assert_flags_closed() -> None:
    for name in FLAGS:
        if globals()[name] is not False:
            raise RepairError("금지 플래그가 열렸다: %s" % name)
    if CHAPTER_LLM_ALLOWED is not True:
        raise RepairError("Stage B LLM은 이 사건에서 허용된다")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)


# ── event 스트림 ─────────────────────────────────────────────────
def source_events(document) -> list:
    """map member 행을 event별로 1건씩 (원본 시각 기준) 모은다."""
    if EVENT_TEXT_MUTATION_ALLOWED:
        raise RepairError("event 텍스트 수정은 금지돼 있다")
    index = {}
    for row in cmap.all_members(document):
        index.setdefault(row["event_id"], {
            "event_id": row["event_id"],
            "source_window": row["source_window"],
            "start_sec": row["original_start"],
            "end_sec": row["original_end"],
            "actor": row["actor"], "action": row["action"],
            "object_or_state": row["object_or_state"]})
    rows = sorted(index.values(),
                  key=lambda row: (row["start_sec"], row["event_id"]))
    if len(rows) != EXPECTED_SOURCE_EVENT_COUNT:
        raise RepairError("source event 수가 %d가 아니다: %d"
                          % (EXPECTED_SOURCE_EVENT_COUNT, len(rows)))
    for row in rows:
        if row["source_window"] in cmap.INVALID_SOURCE_WINDOWS:
            raise RepairError("invalid source 창의 event다: %s"
                              % row["event_id"])
    return rows


def _domain_tokens(event, fields) -> set:
    words = set()
    for field in fields:
        words |= set(v2.normalize(event.get(field, "")).split())
    return words - v2.STOPWORDS


def action_tokens(event) -> set:
    return _domain_tokens(event, ("action",))


def object_tokens(event) -> set:
    return _domain_tokens(event, ("object_or_state",))


def domain_tokens(event) -> set:
    return action_tokens(event) | object_tokens(event)


def _overlap(start, end, low, high) -> float:
    return round(max(0.0, min(end, high) - max(start, low)), 6)


def events_between(events, start: float, end: float, windows=None) -> list:
    rows = [row for row in events
            if _overlap(start, end, row["start_sec"], row["end_sec"]) > 0
            and (windows is None or row["source_window"] in windows)]
    return sorted(rows, key=lambda row: (row["start_sec"], row["event_id"]))


# ── Stage A: 경계 후보 (event 전환에서만 · 격자·region 주입 없음) ───────
def candidate_times(events) -> list:
    """후보 시각은 **event 시작 시각**뿐이다. jitter·격자 시각 주입 금지."""
    if BOUNDARY_JITTER_ALLOWED:
        raise RepairError("경계 jitter는 금지돼 있다")
    if GRID_BOUNDARY_AS_CANDIDATE_ALLOWED \
            or REGION_BOUNDARY_AS_CANDIDATE_ALLOWED:
        raise RepairError("격자·region 시각을 후보로 주입할 수 없다")
    times = sorted({round(float(row["start_sec"]), 3) for row in events
                    if VIDEO_START_SEC < row["start_sec"] < VIDEO_END_SEC})
    return times


def _reasons(before, after, before_long, after_long) -> list:
    rows = []
    if before and after:
        actions_disjoint = not (set().union(*(action_tokens(row)
                                              for row in before))
                                & set().union(*(action_tokens(row)
                                                for row in after)))
        objects_disjoint = not (set().union(*(object_tokens(row)
                                              for row in before))
                                & set().union(*(object_tokens(row)
                                                for row in after)))
        if actions_disjoint:
            rows.append(ACTIVITY_DOMAIN_CHANGE)
        if objects_disjoint:
            rows.append(OBJECT_DOMAIN_CHANGE)
        if actions_disjoint and objects_disjoint:
            rows.append(SCENE_OR_TASK_CHANGE)
    if before_long and after_long:
        long_disjoint = not (set().union(*(domain_tokens(row)
                                           for row in before_long))
                             & set().union(*(domain_tokens(row)
                                             for row in after_long)))
        if long_disjoint and rows:
            rows.append(SUSTAINED_ACTIVITY_CHANGE)
    return [name for name in BOUNDARY_REASONS if name in rows]


def _breadth(before, after) -> int:
    if not before or not after:
        return 0
    before_tokens = set().union(*(domain_tokens(row) for row in before))
    after_tokens = set().union(*(domain_tokens(row) for row in after))
    return len(after_tokens - before_tokens)


def conflict_intervals(document) -> list:
    return [[row["start_sec"], row["end_sec"]]
            for row in document["nodes"]["conflict_blocks"]]


def conflict_sources_at(document, time: float) -> list:
    rows = []
    for block in document["nodes"]["conflict_blocks"]:
        if block["start_sec"] <= time < block["end_sec"]:
            rows.append(sorted({block["observation_set_1"]["source"],
                                block["observation_set_2"]["source"]}))
    return rows


def evaluate_candidate(events, document, time: float) -> dict:
    """한 시각의 전환 근거를 계산한다. conflict 안이면 양쪽 source 모두 요구한다."""
    before = events_between(events, max(VIDEO_START_SEC,
                                        time - DETECT_WINDOW_SEC), time)
    after = events_between(events, time,
                           min(VIDEO_END_SEC, time + DETECT_WINDOW_SEC))
    before_long = events_between(events, max(VIDEO_START_SEC,
                                             time - SUSTAIN_WINDOW_SEC), time)
    after_long = events_between(events, time,
                                min(VIDEO_END_SEC,
                                    time + SUSTAIN_WINDOW_SEC))
    reasons = _reasons(before, after, before_long, after_long)
    row = {
        "boundary_sec": time,
        "reason": reasons,
        "breadth": _breadth(before, after),
        "before_event_ids": [event["event_id"] for event in before],
        "after_event_ids": [event["event_id"] for event in after],
        "before_activity": ["%s | %s" % (event["action"],
                                         event["object_or_state"])
                            for event in before],
        "after_activity": ["%s | %s" % (event["action"],
                                        event["object_or_state"])
                           for event in after],
        "in_conflict_block": bool(conflict_sources_at(document, time)),
        "conflict_source_reasons": {},
        "excluded": None,
    }
    if not before or not after:
        row["excluded"] = "NO_EVIDENCE_ON_BOTH_SIDES"
        return row
    if not reasons:
        row["excluded"] = "NO_TRANSITION_EVIDENCE"
        return row
    for pair in conflict_sources_at(document, time):
        per_source = {}
        for window_id in pair:
            per_source[window_id] = _reasons(
                events_between(events,
                               max(VIDEO_START_SEC,
                                   time - DETECT_WINDOW_SEC), time,
                               windows={window_id}),
                events_between(events, time,
                               min(VIDEO_END_SEC,
                                   time + DETECT_WINDOW_SEC),
                               windows={window_id}),
                events_between(events,
                               max(VIDEO_START_SEC,
                                   time - SUSTAIN_WINDOW_SEC), time,
                               windows={window_id}),
                events_between(events, time,
                               min(VIDEO_END_SEC,
                                   time + SUSTAIN_WINDOW_SEC),
                               windows={window_id}))
        row["conflict_source_reasons"].update(per_source)
        shared = set(per_source[pair[0]]) & set(per_source[pair[1]])
        if not shared:
            row["excluded"] = UNSUPPORTED_BY_CONFLICT
            return row
    return row


def candidates(events, document) -> list:
    return [evaluate_candidate(events, document, time)
            for time in candidate_times(events)]


def select_boundaries(rows) -> list:
    """간격 %.0f초(=600/최대 chapter 수) 안에서 근거가 가장 넓은 후보를 고른다.

    격자·region과의 일치는 선택 기준에 **들어가지 않는다** — 사후 감사만 한다.
    """
    pool = [row for row in rows if row["excluded"] is None
            and MIN_SEPARATION_SEC <= row["boundary_sec"]
            <= VIDEO_END_SEC - MIN_SEPARATION_SEC]
    pool.sort(key=lambda row: row["boundary_sec"])
    selected = []
    cursor = MIN_SEPARATION_SEC
    while True:
        window = [row for row in pool
                  if cursor <= row["boundary_sec"] < cursor + MIN_SEPARATION_SEC]
        if window:
            best = sorted(window, key=lambda row: (-len(row["reason"]),
                                                   -row["breadth"],
                                                   row["boundary_sec"]))[0]
            selected.append(best)
            cursor = best["boundary_sec"] + MIN_SEPARATION_SEC
            continue
        remaining = [row for row in pool if row["boundary_sec"] >= cursor]
        if not remaining:
            break
        cursor = remaining[0]["boundary_sec"]
        if cursor > VIDEO_END_SEC - MIN_SEPARATION_SEC:
            break
    return selected


select_boundaries.__doc__ = select_boundaries.__doc__ % MIN_SEPARATION_SEC


def boundary_audit(row, document) -> dict:
    """격자·region 일치는 **기록**이다. 선택에 쓰지 않았다."""
    time = row["boundary_sec"]
    region_edges = sorted({edge for region in document["regions"]
                           for edge in (region["start_sec"],
                                        region["end_sec"])})
    return {"boundary_sec": time,
            "on_24s_grid": round(time % GRID_SEC, 6) == 0.0,
            "on_48s_grid": round(time % WINDOW_SEC, 6) == 0.0,
            "equals_region_boundary": time in region_edges,
            "reason": row["reason"],
            "used_for_selection": False}


def chapters_from_boundaries(selected) -> list:
    edges = [VIDEO_START_SEC] + [row["boundary_sec"] for row in selected] \
        + [VIDEO_END_SEC]
    rows = []
    for index in range(len(edges) - 1):
        rows.append({"chapter_id": "CH%02d" % (index + 1),
                     "start_sec": edges[index],
                     "end_sec": edges[index + 1]})
    if not (MIN_CHAPTERS <= len(rows) <= MAX_CHAPTERS):
        raise RepairError("INSUFFICIENT_BOUNDARY_EVIDENCE: chapter 수가 "
                          "%d–%d 범위를 벗어났다: %d"
                          % (MIN_CHAPTERS, MAX_CHAPTERS, len(rows)))
    for left, right in zip(rows, rows[1:]):
        if left["end_sec"] != right["start_sec"]:
            raise RepairError("COVERAGE_VIOLATION: chapter가 끊겼다")
    if rows[0]["start_sec"] != VIDEO_START_SEC \
            or rows[-1]["end_sec"] != VIDEO_END_SEC:
        raise RepairError("COVERAGE_VIOLATION: 0–600초를 덮지 않는다")
    return rows


# ── chapter 계보·근거 (결정적) ────────────────────────────────────
def chapter_support(chapter, document, events) -> dict:
    seconds = {name: 0.0 for name in cmap.REGION_CLASSES}
    regions = []
    for region in document["regions"]:
        length = _overlap(chapter["start_sec"], chapter["end_sec"],
                          region["start_sec"], region["end_sec"])
        if length > 0:
            seconds[region["node_class"]] = round(
                seconds[region["node_class"]] + length, 3)
            regions.append(region["region_id"])
    blocks = [row["node_id"] for row in document["nodes"]["conflict_blocks"]
              if _overlap(chapter["start_sec"], chapter["end_sec"],
                          row["start_sec"], row["end_sec"]) > 0]
    unresolved = [[row["start_sec"], row["end_sec"]]
                  for row in document["nodes"]["unresolved_gaps"]
                  if _overlap(chapter["start_sec"], chapter["end_sec"],
                              row["start_sec"], row["end_sec"]) > 0]
    rows = events_between(events, chapter["start_sec"], chapter["end_sec"])
    if not rows:
        raise RepairError("LINEAGE_BROKEN: %s에 source event가 없다"
                          % chapter["chapter_id"])
    conflict_sources = sorted({
        source for block in document["nodes"]["conflict_blocks"]
        if block["node_id"] in blocks
        for source in (block["observation_set_1"]["source"],
                       block["observation_set_2"]["source"])})
    return {"chapter_id": chapter["chapter_id"],
            "source_regions": regions,
            "region_seconds": seconds,
            "conflict_blocks": blocks,
            "conflict_sources_preserved": conflict_sources,
            "unresolved_intervals": unresolved,
            "source_event_ids": [row["event_id"] for row in rows],
            "source_event_count": len(rows),
            "source_windows": sorted({row["source_window"] for row in rows}),
            "multi_window_seconds": seconds[cmap.STITCHABLE],
            "single_source_seconds": seconds[cmap.SINGLE_SOURCE],
            "conflict_seconds": seconds[cmap.CONFLICT],
            "unresolved_seconds": seconds[cmap.UNRESOLVED]}


def evidence_class(support) -> dict:
    """사전등록 §12: executor가 결정적으로 계산한다. LLM이 고르지 않는다."""
    if LLM_MAY_SET_EVIDENCE_CLASS_ALLOWED:
        raise RepairError("evidence class는 LLM이 정하지 않는다")
    reasons = []
    if support["conflict_blocks"]:
        reasons.append("material conflict 포함")
        label = MIXED_EVIDENCE
    elif support["single_source_seconds"] >= support["multi_window_seconds"] \
            or support["unresolved_seconds"] > 0:
        if support["single_source_seconds"] >= support["multi_window_seconds"]:
            reasons.append("single-source 지배 (%.0f초 ≥ %.0f초)"
                           % (support["single_source_seconds"],
                              support["multi_window_seconds"]))
        if support["unresolved_seconds"] > 0:
            reasons.append("unresolved %.0f초 포함"
                           % support["unresolved_seconds"])
        label = LIMITED_EVIDENCE
    else:
        reasons.append("multi-window 지지 · conflict 없음 · unresolved 없음")
        label = STABLE_DOMINANT
    return {"evidence_class": label, "reason": reasons,
            "assigned_by": "executor",
            "priority": list(EVIDENCE_PRIORITY)}


# ── Stage B 프롬프트 렌더 ────────────────────────────────────────
def _chapter_block(chapter, support, document, events) -> str:
    lines = ["%s  %.0f-%.0f sec" % (chapter["chapter_id"],
                                    chapter["start_sec"], chapter["end_sec"])]
    if support["conflict_blocks"]:
        lines.append("  CONFLICT PRESENT (%d disagreeing intervals)"
                     % len(support["conflict_blocks"]))
    if support["unresolved_intervals"]:
        lines.append("  NO OBSERVATION span: %s"
                     % ", ".join("%.0f-%.0f" % (row[0], row[1])
                                 for row in support["unresolved_intervals"]))
    if support["single_source_seconds"] > 0:
        lines.append("  SINGLE SOURCE span: %.0f sec"
                     % support["single_source_seconds"])
    blocks = {row["node_id"]: row
              for row in document["nodes"]["conflict_blocks"]}
    conflict_ids = set()
    for node_id in support["conflict_blocks"]:
        block = blocks[node_id]
        lines.append("  CONFLICT %.0f-%.0f — reading A:"
                     % (block["start_sec"], block["end_sec"]))
        for row in block["observation_set_1"]["events"]:
            lines.append("    %.0f-%.0f %s | %s" % (row["clipped_start"],
                                                    row["clipped_end"],
                                                    row["action"],
                                                    row["object_or_state"]))
            conflict_ids.add(row["event_id"])
        lines.append("  CONFLICT %.0f-%.0f — reading B:"
                     % (block["start_sec"], block["end_sec"]))
        for row in block["observation_set_2"]["events"]:
            lines.append("    %.0f-%.0f %s | %s" % (row["clipped_start"],
                                                    row["clipped_end"],
                                                    row["action"],
                                                    row["object_or_state"]))
            conflict_ids.add(row["event_id"])
    rest = [row for row in events_between(events, chapter["start_sec"],
                                          chapter["end_sec"])
            if row["event_id"] not in conflict_ids]
    if rest:
        lines.append("  observations:")
        for row in rest:
            lines.append("    %.0f-%.0f %s | %s" % (row["start_sec"],
                                                    row["end_sec"],
                                                    row["action"],
                                                    row["object_or_state"]))
    return "\n".join(lines)


def render_prompt(chapters, supports, document, events) -> str:
    blocks = [_chapter_block(chapter, support, document, events)
              for chapter, support in zip(chapters, supports)]
    return REPAIR_PROMPT_V1 % {"chapters": "\n\n".join(blocks)}


# ── Stage B 파싱 (경계를 바꿀 수 없다) ────────────────────────────
def extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise RepairError("PARSE_FAILURE: JSON 객체가 없다")
    try:
        payload = json.loads(text[start:end + 1])
    except ValueError as error:
        raise RepairError("PARSE_FAILURE: %s" % error)
    if not isinstance(payload, dict):
        raise RepairError("PARSE_FAILURE: 최상위가 객체가 아니다")
    return payload


TIME_FIELDS = ("start_sec", "end_sec", "boundary_sec", "time", "start", "end")


def parse_titles(payload, chapters) -> dict:
    """제목·요약·활동만 받는다. 시각·evidence class·개수 변경은 거부한다."""
    if LLM_MAY_CHANGE_BOUNDARIES_ALLOWED:
        raise RepairError("LLM은 경계를 바꿀 수 없다")
    for name in ("overview", "analysis", "conclusion", "report", "boundaries",
                 "chapter_count"):
        if name in (payload or {}):
            raise RepairError("SCHEMA_VIOLATION: 금지된 필드가 있다: %s" % name)
    rows = (payload or {}).get("chapters")
    if isinstance(rows, list):
        raise RepairError("SCHEMA_VIOLATION: chapters는 chapter_id 사전이어야 "
                          "한다 (배열은 경계 재정의로 읽힌다)")
    if not isinstance(rows, dict):
        raise RepairError("SCHEMA_VIOLATION: chapters 사전이 없다")
    expected = [chapter["chapter_id"] for chapter in chapters]
    if sorted(rows) != sorted(expected):
        raise RepairError("LLM_CHANGED_BOUNDARIES: chapter 집합이 다르다: %r"
                          % sorted(rows))
    result = {}
    for chapter_id in expected:
        row = rows[chapter_id]
        if not isinstance(row, dict):
            raise RepairError("SCHEMA_VIOLATION: %s가 객체가 아니다"
                              % chapter_id)
        for field in TIME_FIELDS:
            if field in row:
                raise RepairError("LLM_CHANGED_BOUNDARIES: %s에 시각 필드가 "
                                  "있다: %s" % (chapter_id, field))
        for field in ("confidence_class", "evidence_class", "confidence"):
            if field in row:
                raise RepairError("EVIDENCE_CLASS_VIOLATION: %s가 evidence "
                                  "class를 지정했다" % chapter_id)
        title = str(row.get("title") or "").strip()
        summary = str(row.get("summary") or "").strip()
        activities = row.get("dominant_activities") or []
        if not title or not summary:
            raise RepairError("SCHEMA_VIOLATION: %s의 title/summary가 비었다"
                              % chapter_id)
        if not isinstance(activities, list) or not activities:
            raise RepairError("SCHEMA_VIOLATION: %s의 dominant_activities가 "
                              "없다" % chapter_id)
        result[chapter_id] = {
            "title": title, "summary": summary,
            "dominant_activities": [str(value).strip() for value in activities]}
    return result


# ── conflict 노출 · unresolved 안전 ──────────────────────────────
def disclosure_audit(chapter, support, text) -> dict:
    required = bool(support["conflict_blocks"])
    lowered = (text or "").lower()
    found = any(term in lowered for term in DISCLOSURE_TERMS)
    return {"chapter_id": chapter["chapter_id"],
            "conflict_present": required,
            "disclosure_required": required,
            "disclosed_by_generator": bool(required and found),
            "machine_disclosure": MACHINE_DISCLOSURE if required else "",
            "conflict_disclosed": bool(required
                                       and (found or MACHINE_DISCLOSURE))
            or not required,
            "terms_checked": list(DISCLOSURE_TERMS)}


def unresolved_audit(chapters, supports, document) -> dict:
    gaps = [[row["start_sec"], row["end_sec"]]
            for row in document["nodes"]["unresolved_gaps"]]
    covered = [row for support in supports
               for row in support["unresolved_intervals"]]
    violations = []
    if SYNTHETIC_FILL_ALLOWED:
        violations.append({"reason": "synthetic fill 플래그가 열렸다"})
    for interval in gaps:
        if interval not in covered:
            violations.append({"reason": "unresolved 구간이 계보에서 사라졌다: "
                                         "%r" % (interval,)})
    for chapter, support in zip(chapters, supports):
        if support["unresolved_intervals"] and not support["source_event_ids"]:
            violations.append({"chapter_id": chapter["chapter_id"],
                               "reason": "unresolved 구간만으로 chapter를 "
                                         "만들었다"})
    return {"unresolved_intervals": gaps, "covered_by_chapters": covered,
            "violations": violations}


def evidence_audit(chapters, supports, classes) -> dict:
    """§12 계산 규칙이 실제로 지켜졌는지 구조로 검사한다."""
    violations = []
    for chapter, support, row in zip(chapters, supports, classes):
        label = row["evidence_class"]
        if support["conflict_blocks"] and label != MIXED_EVIDENCE:
            violations.append({"chapter_id": chapter["chapter_id"],
                               "reason": "conflict 포함인데 %s다" % label})
        if label == STABLE_DOMINANT:
            if support["single_source_seconds"] \
                    >= support["multi_window_seconds"]:
                violations.append({"chapter_id": chapter["chapter_id"],
                                   "reason": "single-source 지배인데 "
                                             "STABLE_DOMINANT다"})
            if support["unresolved_seconds"] > 0:
                violations.append({"chapter_id": chapter["chapter_id"],
                                   "reason": "unresolved 포함인데 "
                                             "STABLE_DOMINANT다"})
            if support["conflict_blocks"]:
                violations.append({"chapter_id": chapter["chapter_id"],
                                   "reason": "conflict 포함인데 "
                                             "STABLE_DOMINANT다"})
        if row["assigned_by"] != "executor":
            violations.append({"chapter_id": chapter["chapter_id"],
                               "reason": "evidence class를 executor가 계산하지 "
                                         "않았다"})
    return {"violations": violations,
            "class_counts": {name: sum(1 for row in classes
                                       if row["evidence_class"] == name)
                             for name in EVIDENCE_CLASSES}}


def grid_audit(selected, document) -> dict:
    rows = [boundary_audit(row, document) for row in selected]
    return {"boundaries": rows,
            "internal_boundary_count": len(rows),
            "on_24s_grid_count": sum(1 for row in rows if row["on_24s_grid"]),
            "on_48s_grid_count": sum(1 for row in rows if row["on_48s_grid"]),
            "equals_region_boundary_count": sum(
                1 for row in rows if row["equals_region_boundary"]),
            "grid_used_for_selection": False,
            "jitter_applied": BOUNDARY_JITTER_ALLOWED,
            "note": "격자·region 일치는 사후 기록이고 선택 기준이 아니다"}


def anomalies(chapters, supports, classes, disclosures, grid) -> list:
    rows = []
    if grid["internal_boundary_count"] \
            and grid["equals_region_boundary_count"] \
            == grid["internal_boundary_count"]:
        rows.append({"kind": "ALL_BOUNDARIES_EQUAL_REGION_BOUNDARIES",
                     "detail": "내부 경계 %d개가 전부 region 경계와 같다"
                               % grid["internal_boundary_count"]})
    if grid["internal_boundary_count"] \
            and grid["on_24s_grid_count"] == grid["internal_boundary_count"]:
        rows.append({"kind": "ALL_BOUNDARIES_ON_24S_GRID",
                     "detail": "내부 경계 %d개가 전부 24초 격자에 있다"
                               % grid["internal_boundary_count"]})
    for row in disclosures:
        if row["disclosure_required"] and not row["disclosed_by_generator"]:
            rows.append({"kind": "CONFLICT_NOT_DISCLOSED_BY_GENERATOR",
                         "chapter_id": row["chapter_id"],
                         "detail": "요약에 불일치 표현이 없어 machine "
                                   "disclosure로 보완했다"})
    for chapter, support in zip(chapters, supports):
        length = chapter["end_sec"] - chapter["start_sec"]
        if length < MIN_SEPARATION_SEC:
            rows.append({"kind": "CHAPTER_SHORTER_THAN_MIN_SEPARATION",
                         "chapter_id": chapter["chapter_id"],
                         "detail": "%.1f초" % length})
    return rows


def executor_state(chapters, anomaly_rows) -> dict:
    return {"state": EXECUTOR_STATE, "verdict": None,
            "verdict_by_executor": VERDICT_BY_EXECUTOR,
            "final_verdict_vocabulary": FINAL_VERDICT_VOCABULARY_LINE,
            "chapter_count": len(chapters),
            "anomaly_count": len(anomaly_rows),
            "generation_attempts": GENERATION_ATTEMPTS,
            "retry_allowed": RETRY_ALLOWED,
            "new_vlm_inference_count": 0,
            "track_a_input_used": TRACK_A_INPUT_ALLOWED,
            "overview_generated": OVERVIEW_GENERATION_ALLOWED,
            "boundaries_frozen_before_generation": True,
            "evidence_class_assigned_by": "executor",
            "allowed_max_conclusion": ALLOWED_MAX_CONCLUSION,
            "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS)}


# ── V1 대조 (V1을 정답으로 쓰지 않는다) ───────────────────────────
def v1_comparison(v1_document, chapters, classes, disclosures, grid) -> dict:
    v1_chapters = v1_document["chapters"]
    v1_grid = v1_document["grid_alignment"]
    v1_conflict = {row["chapter_id"]: row["conflict_blocks"]
                   for row in v1_document["lineage"]}
    return {
        "note": "V1은 historical comparison이며 정답이 아니다",
        "v1": {
            "chapter_count": len(v1_chapters),
            "internal_boundaries": [row["start_sec"]
                                    for row in v1_chapters[1:]],
            "on_24s_grid_count": v1_grid["on_24s_grid_count"],
            "internal_boundary_count": v1_grid["internal_boundary_count"],
            "confidence_classes": [row["confidence_class"]
                                   for row in v1_chapters],
            "confidence_assigned_by": "generator (LLM)",
            "conflict_chapters": [key for key, value in v1_conflict.items()
                                  if value],
            "conflict_disclosure_enforced": False},
        "v2": {
            "chapter_count": len(chapters),
            "internal_boundaries": [row["boundary_sec"]
                                    for row in grid["boundaries"]],
            "on_24s_grid_count": grid["on_24s_grid_count"],
            "internal_boundary_count": grid["internal_boundary_count"],
            "equals_region_boundary_count":
                grid["equals_region_boundary_count"],
            "evidence_classes": [row["evidence_class"] for row in classes],
            "evidence_assigned_by": "executor (deterministic)",
            "conflict_chapters": [row["chapter_id"] for row in disclosures
                                  if row["conflict_present"]],
            "conflict_disclosure_enforced": True},
    }


# ── reviewer packet ────────────────────────────────────────────
def timeline_table(chapters, supports, classes) -> str:
    lines = ["%-5s %-13s %-6s %-17s %s" % ("id", "time", "sec", "evidence",
                                           "title")]
    for chapter, support, row in zip(chapters, supports, classes):
        lines.append("%-5s %6.0f-%-6.0f %-6.0f %-17s %s"
                     % (chapter["chapter_id"], chapter["start_sec"],
                        chapter["end_sec"],
                        chapter["end_sec"] - chapter["start_sec"],
                        row["evidence_class"], chapter.get("title", "")))
        lines.append("      region %s%s%s"
                     % (",".join(support["source_regions"]),
                        (" · conflict " + ",".join(support["conflict_blocks"]))
                        if support["conflict_blocks"] else "",
                        (" · unresolved " + str(support["unresolved_intervals"]))
                        if support["unresolved_intervals"] else ""))
    return "\n".join(lines)


def packet(chapters, supports, classes, disclosures, boundaries, grid,
           anomaly_rows, comparison, provenance) -> str:
    lines = ["# SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1 reviewer packet", "",
             "경계는 Stage A가 event 전환에서 **결정적으로** 뽑아 동결했고, "
             "Stage B LLM은 제목·요약만 썼다. evidence class는 executor가 "
             "계산했다. **executor는 판정을 쓰지 않는다.**", "",
             "```",
             "source map      %s" % provenance.get("source_map_sha256", "-"),
             "stage A rule    detect %.0fs · sustain %.0fs · min separation "
             "%.0fs (=600/%d)" % (DETECT_WINDOW_SEC, SUSTAIN_WINDOW_SEC,
                                  MIN_SEPARATION_SEC, MAX_CHAPTERS),
             "stage B prompt  %s (%s)" % (provenance.get("prompt_sha256", "-"),
                                          REPAIR_PROMPT_NAME),
             "generator       %s · greedy · 1회" % LLM_MODEL_ID,
             "chapter 수       %d (허용 %d–%d)" % (len(chapters), MIN_CHAPTERS,
                                                MAX_CHAPTERS),
             "```", "", "## timeline", "", "```",
             timeline_table(chapters, supports, classes), "```", "",
             "## 경계 감사 (선택 기준이 아니다 · 기록)", "", "```",
             "내부 경계 %d개 · 24초 격자 %d · 48초 격자 %d · region 경계 일치 %d · "
             "jitter %s"
             % (grid["internal_boundary_count"], grid["on_24s_grid_count"],
                grid["on_48s_grid_count"], grid["equals_region_boundary_count"],
                grid["jitter_applied"]), "```", ""]
    for row in boundaries:
        lines += ["### 경계 %.0f초  %s" % (row["boundary_sec"],
                                        ", ".join(row["reason"])), "",
                  "```",
                  "24초 격자 %s · 48초 격자 %s · region 경계 %s"
                  % (round(row["boundary_sec"] % GRID_SEC, 6) == 0.0,
                     round(row["boundary_sec"] % WINDOW_SEC, 6) == 0.0,
                     row.get("equals_region_boundary", "-")),
                  "앞 근거 (%.0f초):" % DETECT_WINDOW_SEC]
        lines += ["  %s" % text for text in row["before_activity"]]
        lines += ["뒤 근거 (%.0f초):" % DETECT_WINDOW_SEC]
        lines += ["  %s" % text for text in row["after_activity"]]
        if row["in_conflict_block"]:
            lines += ["conflict 안 경계 — source별 근거: %s"
                      % json.dumps(row["conflict_source_reasons"],
                                   ensure_ascii=False)]
        lines += ["```", ""]
    lines += ["## chapter", ""]
    for chapter, support, row, disclosure in zip(chapters, supports, classes,
                                                 disclosures):
        lines += ["### %s  %.0f–%.0f  %s"
                  % (chapter["chapter_id"], chapter["start_sec"],
                     chapter["end_sec"], chapter.get("title", "")), "",
                  "```",
                  "evidence_class    %s  (%s · executor 계산)"
                  % (row["evidence_class"], "; ".join(row["reason"])),
                  "region 초         multi %.0f · single %.0f · conflict %.0f · "
                  "unresolved %.0f"
                  % (support["multi_window_seconds"],
                     support["single_source_seconds"],
                     support["conflict_seconds"],
                     support["unresolved_seconds"]),
                  "conflict          %s"
                  % (", ".join(support["conflict_blocks"]) or "없음"),
                  "conflict source   %s"
                  % (", ".join(support["conflict_sources_preserved"]) or "-"),
                  "unresolved        %s"
                  % (support["unresolved_intervals"] or "없음"),
                  "source event      %d건 · 창 %s"
                  % (support["source_event_count"],
                     ", ".join(support["source_windows"])),
                  "dominant          %s"
                  % ", ".join(chapter.get("dominant_activities", [])),
                  "```", "",
                  "summary: %s" % chapter.get("summary", ""), ""]
        if disclosure["disclosure_required"]:
            lines += ["```",
                      "conflict 노출: 생성기 요약에 %s"
                      % ("있음" if disclosure["disclosed_by_generator"]
                         else "없음 → machine disclosure로 보완"),
                      "machine disclosure: %s"
                      % disclosure["machine_disclosure"], "```", ""]
    lines += ["## V1 대조 (V1은 정답이 아니다)", "", "```",
              "V1 chapter %d · 내부 경계 %s"
              % (comparison["v1"]["chapter_count"],
                 comparison["v1"]["internal_boundaries"]),
              "V1 24초 격자 %d/%d · confidence 지정자 %s"
              % (comparison["v1"]["on_24s_grid_count"],
                 comparison["v1"]["internal_boundary_count"],
                 comparison["v1"]["confidence_assigned_by"]),
              "V2 chapter %d · 내부 경계 %s"
              % (comparison["v2"]["chapter_count"],
                 comparison["v2"]["internal_boundaries"]),
              "V2 24초 격자 %d/%d · region 경계 일치 %d · evidence 지정자 %s"
              % (comparison["v2"]["on_24s_grid_count"],
                 comparison["v2"]["internal_boundary_count"],
                 comparison["v2"]["equals_region_boundary_count"],
                 comparison["v2"]["evidence_assigned_by"]),
              "```", "", "## 구조 이상 (자동 수정·재생성 없음)", "", "```"]
    lines += ["%s %s" % (row["kind"], row.get("detail", ""))
              for row in anomaly_rows] or ["없음"]
    lines += ["```", "", "## 판정 질문 (리뷰어 전용)", ""]
    for question, detail in (
            ("Q1 STRUCTURE", "whole-video 주요 활동 흐름이 읽히는가"),
            ("Q2 BOUNDARY_SEMANTICS",
             "각 내부 경계가 event 수준 전환으로 방어 가능한가"),
            ("Q3 GEOMETRY_INDEPENDENCE",
             "segmentation이 window/region 기하를 복제하지 않았는가"),
            ("Q4 CONFLICT_SAFETY",
             "conflict 포함 chapter가 불확실성을 명시하는가"),
            ("Q5 EVIDENCE_CALIBRATION",
             "single-source·conflict·stable 지지가 evidence class에 정직히 "
             "반영됐는가"),
            ("Q6 OVERVIEW_READY",
             "이 sequence를 Overview Shadow 입력으로 쓸 수 있는가")):
        lines += ["```", question, detail, "판정: %s" % NOT_ADJUDICATED,
                  "```", ""]
    lines += ["## 최종 어휘 (리뷰어 전용)", "", "```",
              FINAL_VERDICT_VOCABULARY_LINE,
              "executor 상태: %s · verdict %s" % (EXECUTOR_STATE,
                                                 NOT_ADJUDICATED),
              "```", "",
              "말할 수 있는 최대 결론: %s" % ALLOWED_MAX_CONCLUSION, ""]
    return "\n".join(lines) + "\n"
