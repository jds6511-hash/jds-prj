"""WVR_SEMANTIC_CHAPTER_SHADOW_V1 계산기 (2026-09-10 · freeze).

사전등록: `docs/preregistration/WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md`

```
질문   Conservative Event Map의 안정 관측과 명시적 conflict/unresolved 메타데이터로
      local window 격자가 아니라 의미 변화에 맞춘 Semantic Chapter를 만들 수 있는가
입력   conservative_event_map_v1.json (해시 동결) — 원본 영상 재추론 없음 ·
      Track A(STT·caption) 입력 없음
생성   chapter 후보 생성에만 text LLM 1회 (프롬프트·모델·런타임 동결)
금지   conflict 승자 선택 · 없는 consensus 합성 · [0,24) 사실 생성 ·
      region/창 격자 복사 · Overview·Analysis·Conclusion·HWPX 생성 ·
      재생성(retry) · executor의 PASS/HOLD 계산
```

이 모듈은 순수 계산만 한다. GPU·파일 입출력은 `scripts/wvr_chapter_*.py`가 한다.
"""
import hashlib
import json
import re

import wvr_conservative_map_v1 as cmap

EVENT = "WVR_SEMANTIC_CHAPTER_SHADOW_V1"
PREREG = ("docs/preregistration/"
          "WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md")
ARTIFACT_TAG = "chapter_v1"
SCHEMA = "wvr_semantic_chapter_v1"
ARTIFACT_NAME = "SEMANTIC_CHAPTER_CANDIDATES"        # 확정 Chapter가 아니다

VIDEO_START_SEC = cmap.VIDEO_START_SEC               # 0.0
VIDEO_END_SEC = cmap.VIDEO_END_SEC                   # 600.0
GRID_SEC = cmap.CELL_SEC                             # 24.0 (복사 금지 대상)

# ── 입력 동결 (사전등록 §2) ────────────────────────────────────────
SOURCE_MAP_NAME = "conservative_event_map_v1.json"
SOURCE_MAP_SHA256 = ("ab1876fd8e2b5c41f6e2791a9e8c80656ba2d5ce296f8c197b6fea5d"
                     "b5ab3119")
PROMPT_TEMPLATE_SHA256 = ("032fa497974b182a5a66afda5bc4b7a31251a9b8cd55c990bc26"
                          "005756a1f39f")
RENDERED_PROMPT_SHA256 = ("481a5f60630231ecee6935204326b1375b38eab5005d4fbde76a"
                          "4a44601c7d9e")
SOURCE_SUMMARY_NAME = "conservative_event_map_v1_summary.json"
EXPECTED_SOURCE_EVENT_COUNT = cmap.EXPECTED_SOURCE_EVENT_COUNT   # 160
EXPECTED_REGION_COUNT = cmap.EXPECTED_REGION_COUNT               # 11

# ── 금지 플래그 ───────────────────────────────────────────────────
CONFLICT_RESOLUTION_ALLOWED = False
PREFERRED_SOURCE_ALLOWED = False
NEW_VLM_INFERENCE_ALLOWED = False
TRACK_A_INPUT_ALLOWED = False
SYNTHETIC_FILL_ALLOWED = False
EVENT_TEXT_MUTATION_ALLOWED = False
OVERVIEW_GENERATION_ALLOWED = False
ANALYSIS_GENERATION_ALLOWED = False
REPORT_GENERATION_ALLOWED = False
RETRY_ALLOWED = False
VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False
CHAPTER_LLM_ALLOWED = True                            # 이 사건에서만 허용된다
FLAGS = ("CONFLICT_RESOLUTION_ALLOWED", "PREFERRED_SOURCE_ALLOWED",
         "NEW_VLM_INFERENCE_ALLOWED", "TRACK_A_INPUT_ALLOWED",
         "SYNTHETIC_FILL_ALLOWED", "EVENT_TEXT_MUTATION_ALLOWED",
         "OVERVIEW_GENERATION_ALLOWED", "ANALYSIS_GENERATION_ALLOWED",
         "REPORT_GENERATION_ALLOWED", "RETRY_ALLOWED",
         "VERDICT_BY_EXECUTOR", "PRODUCTION_PROMOTION_ALLOWED")

# ── 생성 런타임 동결 (사전등록 §4) ──────────────────────────────────
LLM_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
LLM_DTYPE = "bfloat16"
LLM_LOAD_4BIT = False                                 # 서버 4090 24GB
LLM_MAX_NEW_TOKENS = 4096
LLM_DO_SAMPLE = False                                 # greedy
GENERATION_ATTEMPTS = 1                               # 재생성 금지

# ── chapter 어휘 동결 (사전등록 §7·§13) ─────────────────────────────
CONFIDENCE_CLASSES = ("STABLE_DOMINANT", "MIXED_EVIDENCE", "LIMITED_EVIDENCE")
BOUNDARY_REASONS = ("ACTIVITY_CHANGE", "SCENE_OR_TASK_CHANGE",
                    "OBJECT_DOMAIN_CHANGE", "SUSTAINED_TRANSITION")
MIN_CHAPTERS = 3
MAX_CHAPTERS = 10
SHORT_CHAPTER_SEC = 20.0          # 이보다 짧으면 boundary_reason 2개 이상 요구
UNRESOLVED_OPENING_POLICY = ("coverage_from_zero_with_unresolved_opening_"
                             "metadata")
NOT_ADJUDICATED = "NOT_ADJUDICATED"
EXECUTOR_STATE = "EXECUTED / REVIEW_PENDING"
FINAL_VERDICTS = ("SEMANTIC_CHAPTER_SHADOW_PASS", "SEMANTIC_CHAPTER_SHADOW_HOLD",
                  "SEMANTIC_CHAPTER_SHADOW_INCONCLUSIVE")
FINAL_VERDICT_VOCABULARY_LINE = ("SEMANTIC_CHAPTER_SHADOW_PASS / HOLD / "
                                 "INCONCLUSIVE")
FORBIDDEN_FIELD_NAMES = ("hypothesis", "truth", "preferred", "winner",
                         "likely", "score", "confidence_value", "best",
                         "overview", "analysis", "conclusion")

# 측정 blocker (→ reviewer가 INCONCLUSIVE로 쓸 수 있는 사유)
BLOCKERS = ("SOURCE_MAP_HASH_MISMATCH", "RAW_NOT_PERSISTED", "PARSE_FAILURE",
            "SCHEMA_VIOLATION", "COVERAGE_VIOLATION", "VOCABULARY_VIOLATION",
            "LINEAGE_BROKEN", "CONFLICT_RESOLVED_BY_GENERATOR",
            "UNRESOLVED_FILLED", "RUNTIME_FAILURE", "CONFIG_MISMATCH")

PRIOR_STATE = {
    "WVR_EVENT_MAP_COVERAGE_SHADOW_V1": "CLOSED / EVENT_MAP_SHADOW_HOLD",
    "WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1":
        "CLOSED / EVENT_STITCHING_SHADOW_HOLD",
    "WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1":
        "CLOSED / CONSERVATIVE_EVENT_MAP_PASS",
    "W00": "WINDOW_INVALID (invalid source · 재실행 금지)",
}

ALLOWED_MAX_CONCLUSION = (
    "리뷰어가 PASS로 판정하면, Conservative Event Map은 conflict를 확정 사실로 "
    "바꾸지 않고도 whole-video Semantic Chapter 후보를 만들 수 있는 입력이다.")
FORBIDDEN_CONCLUSIONS = (
    "Event extraction이 해결됐다", "240초 conflict가 해결됐다",
    "모든 event가 사실이다", "0.5fps sufficient",
    "production Event Map 승인", "Overview를 만들어도 된다")

# ── 동결 프롬프트 (사전등록 §4에 전문 수록 · 해시 대조) ────────────────
CHAPTER_PROMPT_V1 = """You segment one video into a small number of semantic chapters.

You are given a CONSERVATIVE EVENT MAP built from overlapping local analysis
windows of a single %(video_end).0f-second video. It has four kinds of regions:

- STITCHABLE: two windows described the same span compatibly (reviewer-judged).
- CONFLICT: two windows described the same span in materially different ways.
  Both descriptions are kept. They are alternative observations, not ranked.
- SINGLE_SOURCE: only one window observed that span.
- UNRESOLVED: no valid observation exists for that span.

MAP
%(digest)s
END OF MAP

Task: return between %(min_chapters)d and %(max_chapters)d chapters that cover
%(video_start).1f to %(video_end).1f seconds continuously, in time order, with
no gaps and no overlaps.

Rules you must follow:
1. Put chapter boundaries where the observed activity, task, scene or object
   domain changes. Do not place boundaries just because the map lists a region
   or window boundary there. Region boundaries are analysis artifacts, not
   activity changes.
2. Never decide which side of a CONFLICT region is true. Never merge conflicting
   descriptions into one asserted fact. Never invent agreement that is not in
   the map. If two observations of the same span disagree on details, keep the
   details out of the title and say in the summary that local observations
   disagree.
3. For UNRESOLVED spans, do not invent content. A chapter may cover such a span,
   but its title and summary must not describe what happens there.
4. Titles: short, broad, observable activity phrases in the style of
   "Vehicle maintenance" or "Whiteboard writing" — those two are style
   examples only and are unrelated to this video. Name what the map shows.
   No emotion, no intent, no speculation about who the person is or why
   they act.
5. Summaries: one to three sentences about the recurring activity of the
   chapter. State disagreement where the map shows conflict.
6. confidence_class must be exactly one of: %(confidence)s.
   It describes evidence, not probability. Do not output numbers for it.
7. boundary_reason lists why the chapter starts where it starts. Use one or more
   of: %(reasons)s. The first chapter uses ["ACTIVITY_CHANGE"] only if it truly
   starts at an activity change; otherwise use ["SCENE_OR_TASK_CHANGE"].
8. Chapters shorter than %(short_sec).0f seconds need at least two
   boundary_reason values.

Return only JSON, no prose, no code fence, in exactly this form:

{"chapters": [{"start_sec": 0.0, "end_sec": 0.0, "title": "...",
"summary": "...", "dominant_activities": ["...", "..."],
"confidence_class": "...", "boundary_reason": ["..."]}]}
"""
CHAPTER_PROMPT_NAME = "CHAPTER_PROMPT_V1"


class ChapterError(RuntimeError):
    """Semantic Chapter 계약 위반."""


def assert_flags_closed() -> None:
    for name in FLAGS:
        if globals()[name] is not False:
            raise ChapterError("금지 플래그가 열렸다: %s" % name)
    if CHAPTER_LLM_ALLOWED is not True:
        raise ChapterError("chapter LLM 사용은 이 사건에서 허용된다")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── 입력 digest (결정적 · event 텍스트 원문 그대로) ───────────────────
def _event_line(row) -> str:
    origin = ""
    if row.get("clipped"):
        origin = "  (source event spans %.1f-%.1f)" % (row["original_start"],
                                                       row["original_end"])
    return "    %.1f-%.1f  %s | %s | %s%s" % (
        row["clipped_start"], row["clipped_end"], row["actor"],
        row["action"], row["object_or_state"], origin)


def map_digest(document) -> str:
    """Conservative Event Map을 프롬프트용 텍스트로 편다. 내용 추가·요약 없음."""
    if EVENT_TEXT_MUTATION_ALLOWED:
        raise ChapterError("event 텍스트 수정은 금지돼 있다")
    groups = {row["node_id"]: row for row in document["nodes"]["stitch_groups"]}
    blocks = {row["node_id"]: row
              for row in document["nodes"]["conflict_blocks"]}
    singles = {row["node_id"]: row
               for row in document["nodes"]["single_source"]}
    gaps = {row["node_id"]: row for row in document["nodes"]["unresolved_gaps"]}
    lines = []
    for region in document["regions"]:
        lines.append("[REGION %s] %.0f-%.0f %s"
                     % (region["region_id"], region["start_sec"],
                        region["end_sec"], region["node_class"]))
        for node_id in region["node_ids"]:
            if node_id in gaps:
                lines.append("  [UNRESOLVED %.0f-%.0f] no valid observation "
                             "— do not describe this span"
                             % (gaps[node_id]["start_sec"],
                                gaps[node_id]["end_sec"]))
            elif node_id in singles:
                node = singles[node_id]
                lines.append("  [SINGLE_SOURCE %.0f-%.0f] one window only"
                             % (node["start_sec"], node["end_sec"]))
                lines.extend(_event_line(row) for row in node["events"])
            elif node_id in groups:
                node = groups[node_id]
                lines.append("  [STITCHABLE %.0f-%.0f] reviewer relation %s"
                             % (node["start_sec"], node["end_sec"],
                                node["relation"]))
                lines.extend(_event_line(row)
                             for row in node["ordered_members"])
            elif node_id in blocks:
                node = blocks[node_id]
                lines.append("  [CONFLICT %.0f-%.0f] two alternative "
                             "observations — do not choose"
                             % (node["start_sec"], node["end_sec"]))
                for key in ("observation_set_1", "observation_set_2"):
                    lines.append("   observation set (%d events):"
                                 % node[key]["event_count"])
                    lines.extend(_event_line(row) for row in node[key]["events"])
    return "\n".join(lines)


def render_prompt(document) -> str:
    return CHAPTER_PROMPT_V1 % {
        "digest": map_digest(document),
        "video_start": VIDEO_START_SEC, "video_end": VIDEO_END_SEC,
        "min_chapters": MIN_CHAPTERS, "max_chapters": MAX_CHAPTERS,
        "confidence": ", ".join(CONFIDENCE_CLASSES),
        "reasons": ", ".join(BOUNDARY_REASONS),
        "short_sec": SHORT_CHAPTER_SEC}


# ── 생성물 파싱 (raw 보존 후에만 호출한다) ───────────────────────────
def extract_json(raw: str) -> dict:
    """생성물에서 JSON 객체만 꺼낸다. 실패는 PARSE_FAILURE다."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ChapterError("PARSE_FAILURE: JSON 객체가 없다")
    try:
        payload = json.loads(text[start:end + 1])
    except ValueError as error:
        raise ChapterError("PARSE_FAILURE: %s" % error)
    if not isinstance(payload, dict):
        raise ChapterError("PARSE_FAILURE: 최상위가 객체가 아니다")
    return payload


def parse_chapters(payload) -> list:
    """스키마·어휘·시간축을 검사한다. 위반은 예외이고 고쳐서 통과시키지 않는다."""
    for name in ("overview", "analysis", "conclusion", "report"):
        if name in (payload or {}):
            raise ChapterError("SCHEMA_VIOLATION: 이번 단계에서 금지된 산출물 "
                               "필드가 있다: %s" % name)
    rows = (payload or {}).get("chapters")
    if not isinstance(rows, list) or not rows:
        raise ChapterError("SCHEMA_VIOLATION: chapters 배열이 없다")
    if not (MIN_CHAPTERS <= len(rows) <= MAX_CHAPTERS):
        raise ChapterError("SCHEMA_VIOLATION: chapter 수가 %d–%d 범위를 벗어났다: %d"
                           % (MIN_CHAPTERS, MAX_CHAPTERS, len(rows)))
    chapters = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ChapterError("SCHEMA_VIOLATION: chapter가 객체가 아니다")
        try:
            start = float(row["start_sec"])
            end = float(row["end_sec"])
        except (KeyError, TypeError, ValueError):
            raise ChapterError("SCHEMA_VIOLATION: start_sec/end_sec가 없다")
        if end <= start:
            raise ChapterError("SCHEMA_VIOLATION: end<=start (%s)" % (row,))
        title = str(row.get("title") or "").strip()
        summary = str(row.get("summary") or "").strip()
        if not title or not summary:
            raise ChapterError("SCHEMA_VIOLATION: title/summary가 비었다")
        confidence = row.get("confidence_class")
        if confidence not in CONFIDENCE_CLASSES:
            raise ChapterError("VOCABULARY_VIOLATION: confidence_class %r"
                               % (confidence,))
        reasons = row.get("boundary_reason")
        if isinstance(reasons, str):
            reasons = [reasons]
        if not isinstance(reasons, list) or not reasons:
            raise ChapterError("SCHEMA_VIOLATION: boundary_reason이 없다")
        for reason in reasons:
            if reason not in BOUNDARY_REASONS:
                raise ChapterError("VOCABULARY_VIOLATION: boundary_reason %r"
                                   % (reason,))
        activities = row.get("dominant_activities") or []
        if not isinstance(activities, list) or not activities:
            raise ChapterError("SCHEMA_VIOLATION: dominant_activities가 없다")
        chapters.append({
            "chapter_id": "CH%02d" % (index + 1),
            "start_sec": round(start, 3), "end_sec": round(end, 3),
            "title": title, "summary": summary,
            "dominant_activities": [str(value).strip() for value in activities],
            "confidence_class": confidence,
            "boundary_reason": list(dict.fromkeys(reasons)),
        })
    assert_timeline(chapters)
    return chapters


def assert_timeline(chapters) -> None:
    if chapters[0]["start_sec"] != VIDEO_START_SEC:
        raise ChapterError("COVERAGE_VIOLATION: 첫 chapter가 %.1f에서 시작하지 않는다"
                           % VIDEO_START_SEC)
    if chapters[-1]["end_sec"] != VIDEO_END_SEC:
        raise ChapterError("COVERAGE_VIOLATION: 마지막 chapter가 %.1f에서 끝나지 않는다"
                           % VIDEO_END_SEC)
    for left, right in zip(chapters, chapters[1:]):
        if right["start_sec"] != left["end_sec"]:
            raise ChapterError("COVERAGE_VIOLATION: 시간축이 끊기거나 겹친다: "
                               "%s → %s" % (left["chapter_id"],
                                            right["chapter_id"]))
        if right["start_sec"] <= left["start_sec"]:
            raise ChapterError("COVERAGE_VIOLATION: chapter 순서가 단조롭지 않다")
    total = sum(row["end_sec"] - row["start_sec"] for row in chapters)
    if round(total, 3) != VIDEO_END_SEC - VIDEO_START_SEC:
        raise ChapterError("COVERAGE_VIOLATION: chapter 합이 %.1f초가 아니다: %.1f"
                           % (VIDEO_END_SEC - VIDEO_START_SEC, total))


# ── lineage 유도 (executor가 결정적으로 계산 · 모델이 id를 말하지 않는다) ──
def _overlap(start, end, low, high) -> float:
    return round(max(0.0, min(end, high) - max(start, low)), 6)


def region_membership(chapter, document) -> list:
    return [row["region_id"] for row in document["regions"]
            if _overlap(chapter["start_sec"], chapter["end_sec"],
                        row["start_sec"], row["end_sec"]) > 0]


def events_in_span(document, start: float, end: float) -> list:
    rows = [row for row in document["lineage"]
            if _overlap(start, end, row["start_sec"], row["end_sec"]) > 0]
    return sorted(rows, key=lambda row: (row["start_sec"], row["event_id"]))


def derive_lineage(chapters, document) -> list:
    """chapter마다 region·node·event 계보를 계산한다. 끊기면 예외."""
    conflict_regions = {row["region_id"]: row
                        for row in document["nodes"]["conflict_regions"]}
    blocks = document["nodes"]["conflict_blocks"]
    rows = []
    for chapter in chapters:
        regions = region_membership(chapter, document)
        events = events_in_span(document, chapter["start_sec"],
                               chapter["end_sec"])
        stable = [row["event_id"] for row in events
                  if row["primary_region_class"] in (cmap.STITCHABLE,
                                                     cmap.SINGLE_SOURCE)]
        conflicted = [row["event_id"] for row in events
                      if row["primary_region_class"] == cmap.CONFLICT]
        touched_blocks = [row for row in blocks
                          if _overlap(chapter["start_sec"], chapter["end_sec"],
                                      row["start_sec"], row["end_sec"]) > 0]
        unresolved = [[row["start_sec"], row["end_sec"]]
                      for row in document["nodes"]["unresolved_gaps"]
                      if _overlap(chapter["start_sec"], chapter["end_sec"],
                                  row["start_sec"], row["end_sec"]) > 0]
        node_ids = sorted({node_id for region in document["regions"]
                           if region["region_id"] in regions
                           for node_id in region["node_ids"]})
        if not regions or not node_ids:
            raise ChapterError("LINEAGE_BROKEN: %s에 region/node가 없다"
                               % chapter["chapter_id"])
        if not events:
            raise ChapterError("LINEAGE_BROKEN: %s에 source event가 없다"
                               % chapter["chapter_id"])
        rows.append({
            "chapter_id": chapter["chapter_id"],
            "source_regions": regions,
            "source_nodes": node_ids,
            "stable_source_events": stable,
            "conflict_source_events": conflicted,
            "source_event_count": len(events),
            "conflict_regions": [region for region in regions
                                 if region in conflict_regions],
            "conflict_blocks": [row["node_id"] for row in touched_blocks],
            "conflict_sources_preserved": sorted({
                row[key]["source"] for row in touched_blocks
                for key in ("observation_set_1", "observation_set_2")}),
            "unresolved_intervals": unresolved,
            "source_windows": sorted({row["source_window"]
                                      for row in events}),
        })
    return rows


def assert_declared_ids(payload, document) -> list:
    """모델이 event id를 적었다면 실재하는 것만 허용한다."""
    known = {row["event_id"] for row in document["lineage"]}
    declared = []
    for row in (payload or {}).get("chapters") or []:
        if not isinstance(row, dict):
            continue
        for key in ("stable_source_events", "source_event_ids",
                    "evidence_event_ids", "conflict_source_events"):
            for value in row.get(key) or []:
                declared.append(str(value))
    unknown = sorted({value for value in declared if value not in known})
    if unknown:
        raise ChapterError("LINEAGE_BROKEN: 존재하지 않는 event id: %r" % unknown)
    return sorted(set(declared))


def boundary_evidence(chapters, document) -> list:
    """경계마다 앞·뒤 관측 근거를 붙인다 (사전등록 §13)."""
    rows = []
    for index, chapter in enumerate(chapters):
        boundary = chapter["start_sec"]
        before = events_in_span(document, max(VIDEO_START_SEC, boundary - 12.0),
                                boundary) if index else []
        after = events_in_span(document, boundary, boundary + 12.0)
        regions = [row["region_id"] for row in document["regions"]
                   if row["start_sec"] <= boundary < row["end_sec"]
                   or row["end_sec"] == boundary]
        conflict_involved = any(
            row["node_class"] == cmap.CONFLICT for row in document["regions"]
            if row["region_id"] in regions)
        unresolved_involved = any(
            row["node_class"] == cmap.UNRESOLVED for row in document["regions"]
            if row["region_id"] in regions)
        rows.append({
            "chapter_id": chapter["chapter_id"],
            "boundary_sec": boundary,
            "is_video_start": index == 0,
            "on_24s_grid": round(boundary % GRID_SEC, 6) == 0.0,
            "boundary_reason": chapter["boundary_reason"],
            "before_activity_evidence": [
                "%.1f-%.1f %s | %s | %s"
                % (row["start_sec"], row["end_sec"], _event_actor(row, document),
                   _event_action(row, document), _event_object(row, document))
                for row in before],
            "after_activity_evidence": [
                "%.1f-%.1f %s | %s | %s"
                % (row["start_sec"], row["end_sec"], _event_actor(row, document),
                   _event_action(row, document), _event_object(row, document))
                for row in after],
            "before_source_event_ids": [row["event_id"] for row in before],
            "after_source_event_ids": [row["event_id"] for row in after],
            "source_regions": regions,
            "conflict_involved": conflict_involved,
            "unresolved_involved": unresolved_involved,
        })
    return rows


def _member_index(document) -> dict:
    index = {}
    for row in cmap.all_members(document):
        index.setdefault(row["event_id"], row)
    return index


def _event_actor(row, document) -> str:
    return _member_index(document).get(row["event_id"], {}).get("actor", "")


def _event_action(row, document) -> str:
    return _member_index(document).get(row["event_id"], {}).get("action", "")


def _event_object(row, document) -> str:
    return _member_index(document).get(row["event_id"], {}).get(
        "object_or_state", "")


# ── 구조 이상·안전 검사 (판정이 아니다) ──────────────────────────────
def grid_alignment(chapters) -> dict:
    internal = [row["start_sec"] for row in chapters[1:]]
    on_grid = [value for value in internal
               if round(value % GRID_SEC, 6) == 0.0]
    return {"internal_boundary_count": len(internal),
            "on_24s_grid_count": len(on_grid),
            "off_grid_count": len(internal) - len(on_grid),
            "all_internal_boundaries_on_grid": bool(internal)
            and len(on_grid) == len(internal),
            "grid_sec": GRID_SEC}


def conflict_safety(chapters, lineage, document) -> dict:
    """conflict가 chapter에서 한쪽으로 정리됐는지 구조로 본다."""
    blocks = {row["node_id"]: row
              for row in document["nodes"]["conflict_blocks"]}
    violations = []
    for chapter, rows in zip(chapters, lineage):
        for node_id in rows["conflict_blocks"]:
            block = blocks[node_id]
            sources = {block["observation_set_1"]["source"],
                       block["observation_set_2"]["source"]}
            if not sources <= set(rows["conflict_sources_preserved"]):
                violations.append({"chapter_id": chapter["chapter_id"],
                                   "node_id": node_id,
                                   "reason": "관측 source 한쪽이 사라졌다"})
        for key in ("preferred_source", "resolved_source", "winner"):
            if chapter.get(key):
                violations.append({"chapter_id": chapter["chapter_id"],
                                   "reason": "승자 필드가 있다: %s" % key})
    return {"violations": violations,
            "conflict_blocks_covered": sorted({
                node_id for rows in lineage
                for node_id in rows["conflict_blocks"]}),
            "conflict_block_total": len(blocks)}


def unresolved_safety(chapters, lineage, document) -> dict:
    """[0,24)를 사실로 채우지 않았는지 구조로 본다."""
    gaps = [[row["start_sec"], row["end_sec"]]
            for row in document["nodes"]["unresolved_gaps"]]
    covered = [row for rows in lineage for row in rows["unresolved_intervals"]]
    violations = []
    if SYNTHETIC_FILL_ALLOWED:
        violations.append({"reason": "synthetic fill 플래그가 열렸다"})
    for interval in gaps:
        if interval not in covered:
            violations.append({"reason": "unresolved 구간이 chapter 계보에서 "
                                         "사라졌다: %r" % (interval,)})
    for chapter, rows in zip(chapters, lineage):
        if not rows["unresolved_intervals"]:
            continue
        events = [event_id for event_id in rows["stable_source_events"]
                  + rows["conflict_source_events"]]
        if not events:
            violations.append({"chapter_id": chapter["chapter_id"],
                               "reason": "unresolved 구간만으로 chapter 내용을 "
                                         "만들었다"})
    return {"policy": UNRESOLVED_OPENING_POLICY,
            "unresolved_intervals": gaps,
            "covered_by_chapters": covered,
            "violations": violations}


def anomalies(chapters, lineage, document) -> list:
    """리뷰어가 먼저 봐야 할 구조 이상. 자동 수정·재생성하지 않는다."""
    rows = []
    grid = grid_alignment(chapters)
    if grid["all_internal_boundaries_on_grid"]:
        rows.append({"kind": "ALL_BOUNDARIES_ON_24S_GRID",
                     "detail": "내부 경계 %d개가 전부 24초 격자에 있다"
                               % grid["internal_boundary_count"]})
    for chapter in chapters:
        length = chapter["end_sec"] - chapter["start_sec"]
        if length < SHORT_CHAPTER_SEC and len(chapter["boundary_reason"]) < 2:
            rows.append({"kind": "SHORT_CHAPTER_WITHOUT_STRONG_TRANSITION",
                         "chapter_id": chapter["chapter_id"],
                         "detail": "%.1f초인데 boundary_reason이 %d개"
                                   % (length, len(chapter["boundary_reason"]))})
    covered = {node_id for rows_ in lineage
               for node_id in rows_["conflict_blocks"]}
    missing = [row["node_id"] for row in document["nodes"]["conflict_blocks"]
               if row["node_id"] not in covered]
    if missing:
        rows.append({"kind": "CONFLICT_BLOCK_NOT_COVERED",
                     "detail": ", ".join(missing)})
    for chapter, rows_ in zip(chapters, lineage):
        if rows_["conflict_regions"] and \
                chapter["confidence_class"] == "STABLE_DOMINANT":
            rows.append({"kind": "STABLE_LABEL_OVER_CONFLICT_REGION",
                         "chapter_id": chapter["chapter_id"],
                         "detail": "conflict region %s 포함"
                                   % ", ".join(rows_["conflict_regions"])})
    return rows


def executor_state(chapters, anomaly_rows) -> dict:
    return {"state": EXECUTOR_STATE,
            "verdict": None,
            "verdict_by_executor": VERDICT_BY_EXECUTOR,
            "final_verdict_vocabulary": FINAL_VERDICT_VOCABULARY_LINE,
            "chapter_count": len(chapters),
            "anomaly_count": len(anomaly_rows),
            "generation_attempts": GENERATION_ATTEMPTS,
            "retry_allowed": RETRY_ALLOWED,
            "new_vlm_inference_count": 0,
            "track_a_input_used": TRACK_A_INPUT_ALLOWED,
            "overview_generated": OVERVIEW_GENERATION_ALLOWED,
            "allowed_max_conclusion": ALLOWED_MAX_CONCLUSION,
            "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS)}


def canonical(payload) -> str:
    return cmap.canonical(payload)


# ── reviewer packet ─────────────────────────────────────────────
def timeline_table(chapters, lineage) -> str:
    lines = ["%-5s %-13s %-9s %-18s %s"
             % ("id", "time", "sec", "confidence", "title")]
    for chapter, rows in zip(chapters, lineage):
        lines.append("%-5s %6.0f-%-6.0f %-9.0f %-18s %s"
                     % (chapter["chapter_id"], chapter["start_sec"],
                        chapter["end_sec"],
                        chapter["end_sec"] - chapter["start_sec"],
                        chapter["confidence_class"], chapter["title"]))
        lines.append("      region %s%s%s"
                     % (",".join(rows["source_regions"]),
                        (" · conflict " + ",".join(rows["conflict_blocks"]))
                        if rows["conflict_blocks"] else "",
                        (" · unresolved " + str(rows["unresolved_intervals"]))
                        if rows["unresolved_intervals"] else ""))
    return "\n".join(lines)


def packet(document, chapters, lineage, boundaries, anomaly_rows,
           provenance) -> str:
    lines = ["# SEMANTIC_CHAPTER_SHADOW_V1 reviewer packet", "",
             "Conservative Event Map(PASS) 하나만 입력으로 써서 만든 chapter "
             "후보다. 새 VLM 추론 0회 · Track A 입력 없음 · 생성 1회(재생성 금지). "
             "**executor는 판정을 쓰지 않는다.**", "",
             "```",
             "source map      %s" % provenance.get("source_map_sha256", "-"),
             "chapter prompt  %s (%s)" % (provenance.get("prompt_sha256", "-"),
                                          CHAPTER_PROMPT_NAME),
             "generator       %s · %s · 4bit=%s · greedy · max_new_tokens=%d"
             % (LLM_MODEL_ID, LLM_DTYPE, LLM_LOAD_4BIT, LLM_MAX_NEW_TOKENS),
             "chapter 수       %d (허용 %d–%d)" % (len(chapters), MIN_CHAPTERS,
                                                MAX_CHAPTERS),
             "```", "", "## timeline", "", "```", timeline_table(chapters,
                                                                 lineage),
             "```", ""]
    grid = grid_alignment(chapters)
    lines += ["## 경계 격자 정렬 (판정 아님)", "", "```",
              "내부 경계 %d개 중 24초 격자 위 %d개 · 격자 밖 %d개"
              % (grid["internal_boundary_count"], grid["on_24s_grid_count"],
                 grid["off_grid_count"]),
              "```", ""]
    for chapter, rows, boundary in zip(chapters, lineage, boundaries):
        lines += ["## %s  %.0f–%.0f  %s"
                  % (chapter["chapter_id"], chapter["start_sec"],
                     chapter["end_sec"], chapter["title"]), "",
                  "```",
                  "confidence_class  %s" % chapter["confidence_class"],
                  "dominant          %s" % ", ".join(
                      chapter["dominant_activities"]),
                  "boundary %.0f      %s%s"
                  % (boundary["boundary_sec"],
                     ", ".join(boundary["boundary_reason"]),
                     " · 24초 격자 위" if boundary["on_24s_grid"] else ""),
                  "region            %s" % ", ".join(rows["source_regions"]),
                  "conflict          %s"
                  % (", ".join(rows["conflict_blocks"]) or "없음"),
                  "conflict source   %s"
                  % (", ".join(rows["conflict_sources_preserved"]) or "-"),
                  "unresolved        %s"
                  % (rows["unresolved_intervals"] or "없음"),
                  "source event      %d건 (stable %d · conflict %d)"
                  % (rows["source_event_count"],
                     len(rows["stable_source_events"]),
                     len(rows["conflict_source_events"])),
                  "창                %s" % ", ".join(rows["source_windows"]),
                  "```", "",
                  "summary: %s" % chapter["summary"], "",
                  "```",
                  "boundary 앞 근거 (최대 12초):"]
        lines += ["  %s" % line for line in
                  boundary["before_activity_evidence"] or ["(영상 시작)"]]
        lines += ["boundary 뒤 근거 (최대 12초):"]
        lines += ["  %s" % line for line in
                  boundary["after_activity_evidence"] or ["(없음)"]]
        lines += ["```", ""]
    lines += ["## 구조 이상 (자동 수정·재생성하지 않았다)", "", "```"]
    lines += ["%s %s" % (row["kind"], row.get("detail", ""))
              for row in anomaly_rows] or ["없음"]
    lines += ["```", "", "## 판정 질문 (리뷰어 전용)", ""]
    for question, detail in (
            ("Q1 WHOLE_VIDEO_STRUCTURE",
             "chapter sequence를 읽으면 영상의 주요 활동 흐름이 이해되는가"),
            ("Q2 BOUNDARY_QUALITY",
             "경계가 window/region 격자가 아니라 의미 변화에 대응하는가"),
            ("Q3 CONFLICT_SAFETY",
             "material conflict가 확정 사실로 잘못 해결되지 않았는가"),
            ("Q4 OVERVIEW_INPUT_USABILITY",
             "이 sequence를 다음 Overview 생성 입력으로 쓸 수 있는가")):
        lines += ["```", question, detail, "판정: %s" % NOT_ADJUDICATED,
                  "```", ""]
    lines += ["## 최종 어휘 (리뷰어 전용)", "", "```",
              FINAL_VERDICT_VOCABULARY_LINE,
              "executor 상태: %s · verdict %s" % (EXECUTOR_STATE,
                                                 NOT_ADJUDICATED),
              "```", "",
              "말할 수 있는 최대 결론: %s" % ALLOWED_MAX_CONCLUSION, ""]
    return "\n".join(lines) + "\n"
