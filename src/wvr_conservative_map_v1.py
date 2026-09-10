"""WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1 계산기 (2026-09-10 · freeze).

사전등록: `docs/preregistration/WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1_2026-09-10.md`

```
목적   리뷰어 STITCHABLE 판정은 상위 group으로 묶고 MATERIAL_CONFLICT는
      해결하지 않고 alternative source observations로 보존하는 whole-video 표현
입력   Local Event 160건(W01–W23) + 동결된 리뷰어 판정 22건 + frame bank
금지   승자 선택 · conflict 해결 · 새 inference/LLM · event 삭제·수정 ·
      [0,24) synthetic fill · W00 사용 · narrative 생성 · 사후 임계 ·
      executor의 PASS/HOLD 계산
```

이 모듈은 순수 계산만 한다. 파일 입출력은 `scripts/wvr_cmap_*.py`가 한다.
"""
import json

import wvr_event_map_v1 as em
import wvr_shadow_v1 as sh
import wvr_stitch_v1 as st

EVENT = "WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1"
PREREG = ("docs/preregistration/"
          "WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1_2026-09-10.md")
ARTIFACT_TAG = "conservative_event_map_v1"
ARTIFACT_NAME = "CONSERVATIVE_EVENT_MAP"       # 검증된 Event Map이 아니다
SCHEMA = "wvr_conservative_event_map_v1"

# ── 기하 (SHADOW_V1에서 동결 · 새로 정하지 않는다) ────────────────────
VIDEO_START_SEC = sh.RANGE_START_SEC                       # 0.0
VIDEO_END_SEC = sh.RANGE_END_SEC                           # 600.0
CELL_SEC = sh.STRIDE_SEC                                   # 24.0
VALID_SOURCE_WINDOWS = em.VALID_SOURCE_WINDOWS             # W01…W23
INVALID_SOURCE_WINDOWS = em.INVALID_SOURCE_WINDOWS         # ("W00",)
VALID_SOURCE_MANIFEST_SHA256 = em.VALID_SOURCE_MANIFEST_SHA256
VIDEO_SHA256 = ("ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe"
                "435676cc")

# ── 금지 플래그 (전부 닫혀 있어야 실행된다) ──────────────────────────
CONFLICT_RESOLUTION_ALLOWED = False
PREFERRED_SOURCE_ALLOWED = False
NEW_INFERENCE_ALLOWED = False
NEW_LLM_CALL_ALLOWED = False
TRACK_A_EVIDENCE_ALLOWED = False
SYNTHETIC_FILL_ALLOWED = False
EVENT_DELETION_ALLOWED = False
EVENT_TEXT_MUTATION_ALLOWED = False
NARRATIVE_GENERATION_ALLOWED = False
CHAPTER_ALLOWED = False
VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False
FLAGS = ("CONFLICT_RESOLUTION_ALLOWED", "PREFERRED_SOURCE_ALLOWED",
         "NEW_INFERENCE_ALLOWED", "NEW_LLM_CALL_ALLOWED",
         "TRACK_A_EVIDENCE_ALLOWED", "SYNTHETIC_FILL_ALLOWED",
         "EVENT_DELETION_ALLOWED", "EVENT_TEXT_MUTATION_ALLOWED",
         "NARRATIVE_GENERATION_ALLOWED", "CHAPTER_ALLOWED",
         "VERDICT_BY_EXECUTOR", "PRODUCTION_PROMOTION_ALLOWED")

# ── node 어휘 (사전등록 §4 동결) ────────────────────────────────────
CONSENSUS_EVENT = "CONSENSUS_EVENT"
CONTINUATION_GROUP = "CONTINUATION_GROUP"
TRANSITION = "TRANSITION"
CONFLICT_BLOCK = "CONFLICT_BLOCK"
SINGLE_SOURCE_EVENT = "SINGLE_SOURCE_EVENT"
UNRESOLVED_GAP = "UNRESOLVED_GAP"
NODE_TYPES = (CONSENSUS_EVENT, CONTINUATION_GROUP, TRANSITION,
              CONFLICT_BLOCK, SINGLE_SOURCE_EVENT, UNRESOLVED_GAP)
GROUP_TYPES = ("STITCH_GROUP", "CONFLICT_REGION")
RELATION_TO_NODE_TYPE = {"SAME_EVENT": CONSENSUS_EVENT,
                         "CONTINUATION": CONTINUATION_GROUP,
                         "TRANSITION": TRANSITION}

# region 분류
UNRESOLVED = "UNRESOLVED"
SINGLE_SOURCE = "SINGLE_SOURCE"
CONFLICT = "CONFLICT"
STITCHABLE = "STITCHABLE"
REGION_CLASSES = (UNRESOLVED, SINGLE_SOURCE, CONFLICT, STITCHABLE)

LINEAGE_TYPES = ("conflict_observation_member", "stitch_group_member",
                 "single_source_event")
CLASS_TO_LINEAGE = {CONFLICT: "conflict_observation_member",
                    STITCHABLE: "stitch_group_member",
                    SINGLE_SOURCE: "single_source_event"}

ORDERING_BASIS = ("source 창 id 오름차순 — 선호·우선순위가 아니다")
RESOLUTION_NONE = "NONE"
NOT_ADJUDICATED = "NOT_ADJUDICATED"
EXECUTOR_STATE = "EXECUTED / REVIEW_PENDING"
FINAL_VERDICTS = ("CONSERVATIVE_EVENT_MAP_PASS", "CONSERVATIVE_EVENT_MAP_HOLD",
                  "CONSERVATIVE_EVENT_MAP_INCONCLUSIVE")
FINAL_VERDICT_VOCABULARY_LINE = ("CONSERVATIVE_EVENT_MAP_PASS / HOLD / "
                                 "INCONCLUSIVE")
FORBIDDEN_FIELD_NAMES = ("hypothesis", "truth", "preferred", "winner",
                         "likely", "score", "confidence", "best")

# ── 동결 source (사전등록 §2) ──────────────────────────────────────
FROZEN_HASHES = {
    "event_map_v1_registry.json":
        "1885cda9fd567ccfb9bea79383bcb89260225cafb228253e8efca2cf3cdc4073",
    "stitch_v1_verdicts.json":
        "b27ef299057e807174c2f12ddbee84e294e94482810881a29fda66b70071338b",
    "stitch_v1_blind_map.json":
        "5b19b177efedaad1b989bf2b99be5f283096637a949bbd6a61b3993e6167aba9",
    "shadow_frame_bank.json":
        "64fb207a0617a371385a3736c224c6983f82deb035401f68448ff042f1eefcd3",
    "event_map_v1_coverage.json":
        "c7281388585d2c62a325e1bbd4ba65c4d8b813d1a91be340f1bd9e7942b41fdd",
}

EXPECTED_SOURCE_EVENT_COUNT = 160
EXPECTED_EVENTS_PER_WINDOW = {
    "W01": 11, "W02": 10, "W03": 9, "W04": 6, "W05": 6, "W06": 10, "W07": 8,
    "W08": 2, "W09": 6, "W10": 4, "W11": 6, "W12": 6, "W13": 2, "W14": 4,
    "W15": 9, "W16": 7, "W17": 6, "W18": 5, "W19": 12, "W20": 3, "W21": 8,
    "W22": 10, "W23": 10}

# 동결 verdict에서 §5 규칙으로 유도되는 region 구조 (tamper 감지용)
EXPECTED_REGION_SCHEDULE = (
    ("R01", 0.0, 24.0, UNRESOLVED, ()),
    ("R02", 24.0, 48.0, SINGLE_SOURCE, ()),
    ("R03", 48.0, 96.0, CONFLICT, ("O02", "O03")),
    ("R04", 96.0, 192.0, STITCHABLE, ("O04", "O05", "O06", "O07")),
    ("R05", 192.0, 264.0, CONFLICT, ("O08", "O09", "O10")),
    ("R06", 264.0, 312.0, STITCHABLE, ("O11", "O12")),
    ("R07", 312.0, 384.0, CONFLICT, ("O13", "O14", "O15")),
    ("R08", 384.0, 480.0, STITCHABLE, ("O16", "O17", "O18", "O19")),
    ("R09", 480.0, 528.0, CONFLICT, ("O20", "O21")),
    ("R10", 528.0, 576.0, STITCHABLE, ("O22", "O23")),
    ("R11", 576.0, 600.0, SINGLE_SOURCE, ()),
)
EXPECTED_REGION_COUNT = len(EXPECTED_REGION_SCHEDULE)

NORMATIVE_AUTHORITY = (
    "WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1 preregistration",
    "stitch_v1_verdicts.json (frozen reviewer verdicts)",
    "stitch_v1_blind_map.json (revealed mapping)",
    "event_map_v1_registry.json (W01–W23 local events)",
    "SHADOW_V1 window geometry / frame bank",
    "PROJECT_OVERVIEW.md",
)

PRIOR_STATE = {
    "WVR_EVENT_EXTRACTION_SHADOW_V1": "CLOSED / INCONCLUSIVE",
    "WVR_EVENT_MAP_COVERAGE_SHADOW_V1": "CLOSED / EVENT_MAP_SHADOW_HOLD",
    "WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1":
        "CLOSED / EVENT_STITCHING_SHADOW_HOLD",
    "W00": "WINDOW_INVALID (invalid source · 재실행 금지)",
}

ALLOWED_MAX_CONCLUSION = (
    "리뷰어가 PASS로 판정하면, 이 표현은 conflict를 숨기지 않은 채 Semantic "
    "Chapter 입력으로 쓸 수 있는 최소 조건을 만족한다.")
FORBIDDEN_CONCLUSIONS = (
    "conflict가 해결됐다", "Event Map이 검증됐다", "어느 창이 맞다",
    "0.5fps sufficient", "Chapter/Overview를 만들어도 된다", "production ready")


class MapError(RuntimeError):
    """Conservative Event Map 계약 위반."""


def assert_flags_closed() -> None:
    for name in FLAGS:
        if globals()[name] is not False:
            raise MapError("금지 플래그가 열렸다: %s" % name)


# ── 판정 · 창 기하 ────────────────────────────────────────────────
def verdict_index(verdict_state) -> dict:
    """동결된 리뷰어 판정만 읽는다. 미완결·어휘 위반은 거부한다."""
    if VERDICT_BY_EXECUTOR:
        raise MapError("executor는 판정을 만들지 않는다")
    rows = (verdict_state or {}).get("verdicts") or []
    if not (verdict_state or {}).get("complete"):
        raise MapError("판정이 완결되지 않았다")
    index = {}
    for row in rows:
        overlap_id = row.get("overlap_id")
        relation = row.get("relation")
        top = row.get("top_verdict")
        if relation not in st.RELATION_VERDICTS:
            raise MapError("허용되지 않은 relation: %r" % relation)
        if top not in st.TOP_VERDICTS:
            raise MapError("허용되지 않은 top_verdict: %r" % top)
        if not row.get("adjudicated"):
            raise MapError("미판정 overlap이 있다: %r" % overlap_id)
        index[overlap_id] = {"relation": relation, "top_verdict": top,
                             "note": row.get("note", "")}
    expected = [row["overlap_id"] for row in st.overlaps()]
    if sorted(index) != sorted(expected):
        raise MapError("판정 대상이 22개 overlap과 다르다")
    return index


def overlap_index() -> dict:
    return {row["overlap_id"]: row for row in st.overlaps()}


def cells() -> list:
    """24초 격자 cell 25개."""
    count = int(round((VIDEO_END_SEC - VIDEO_START_SEC) / CELL_SEC))
    return [(round(VIDEO_START_SEC + CELL_SEC * index, 3),
             round(VIDEO_START_SEC + CELL_SEC * (index + 1), 3))
            for index in range(count)]


def covering_windows(start: float, end: float) -> list:
    """구간을 완전히 덮는 valid 창."""
    rows = []
    for window_id in VALID_SOURCE_WINDOWS:
        low, high = em.window_span(window_id)
        if low <= start and end <= high:
            rows.append(window_id)
    return rows


def cell_class(start: float, end: float, verdicts: dict,
               overlaps: dict) -> tuple:
    """(분류, overlap_id 또는 None, source 창 목록)."""
    for overlap_id, row in overlaps.items():
        if row["start_sec"] == start and row["end_sec"] == end:
            top = verdicts[overlap_id]["top_verdict"]
            if top == st.MATERIAL_CONFLICT:
                return CONFLICT, overlap_id, [row["earlier"], row["later"]]
            if top == st.STITCHABLE:
                return STITCHABLE, overlap_id, [row["earlier"], row["later"]]
            raise MapError("판정이 STITCHABLE/MATERIAL_CONFLICT가 아니다: %r"
                           % top)
    windows = covering_windows(start, end)
    if not windows:
        return UNRESOLVED, None, []
    if len(windows) == 1:
        return SINGLE_SOURCE, None, windows
    raise MapError("overlap이 아닌데 창 %d개가 덮는다: %.1f–%.1f"
                   % (len(windows), start, end))


def regions(verdict_state) -> list:
    """§5 규칙으로 region을 유도하고 동결 구조와 대조한다."""
    assert_flags_closed()
    verdicts = verdict_index(verdict_state)
    overlaps = overlap_index()
    rows = []
    for start, end in cells():
        node_class, overlap_id, windows = cell_class(start, end, verdicts,
                                                     overlaps)
        if rows and rows[-1]["node_class"] == node_class \
                and rows[-1]["end_sec"] == start:
            rows[-1]["end_sec"] = end
            rows[-1]["overlap_ids"].extend(
                [overlap_id] if overlap_id else [])
            rows[-1]["source_windows"] = em.dedup(
                rows[-1]["source_windows"] + windows)
            continue
        rows.append({"region_id": None, "start_sec": start, "end_sec": end,
                     "node_class": node_class,
                     "overlap_ids": [overlap_id] if overlap_id else [],
                     "source_windows": em.dedup(windows)})
    for index, row in enumerate(rows):
        row["region_id"] = "R%02d" % (index + 1)
        row["source_windows"] = sorted(row["source_windows"])
    _assert_region_schedule(rows)
    return rows


def _assert_region_schedule(rows) -> None:
    if len(rows) != EXPECTED_REGION_COUNT:
        raise MapError("region 개수가 %d가 아니다: %d"
                       % (EXPECTED_REGION_COUNT, len(rows)))
    if rows[0]["start_sec"] != VIDEO_START_SEC \
            or rows[-1]["end_sec"] != VIDEO_END_SEC:
        raise MapError("region이 0–600초를 덮지 않는다")
    for left, right in zip(rows, rows[1:]):
        if left["end_sec"] != right["start_sec"]:
            raise MapError("region이 끊겼다: %r" % (left,))
    total = sum(row["end_sec"] - row["start_sec"] for row in rows)
    if round(total, 6) != VIDEO_END_SEC - VIDEO_START_SEC:
        raise MapError("region 합이 %.1f초가 아니다: %.1f"
                       % (VIDEO_END_SEC - VIDEO_START_SEC, total))
    derived = [(row["region_id"], row["start_sec"], row["end_sec"],
                row["node_class"], tuple(row["overlap_ids"])) for row in rows]
    if derived != [tuple(row) for row in EXPECTED_REGION_SCHEDULE]:
        raise MapError("유도된 region이 동결 구조와 다르다: %r" % (derived,))
    assigned = [overlap_id for row in rows for overlap_id in row["overlap_ids"]]
    if sorted(assigned) != sorted(row["overlap_id"] for row in st.overlaps()):
        raise MapError("22개 overlap이 region에 모두 배정되지 않았다")


def coverage(rows) -> dict:
    by_class = {name: round(sum(row["end_sec"] - row["start_sec"]
                                for row in rows
                                if row["node_class"] == name), 3)
                for name in REGION_CLASSES}
    return {
        "total_sec": round(sum(row["end_sec"] - row["start_sec"]
                               for row in rows), 3),
        "conflict_duration_sec": by_class[CONFLICT],
        "stitchable_duration_sec": by_class[STITCHABLE],
        "single_source_duration_sec": by_class[SINGLE_SOURCE],
        "unresolved_duration_sec": by_class[UNRESOLVED],
        "unresolved_intervals": [[row["start_sec"], row["end_sec"]]
                                 for row in rows
                                 if row["node_class"] == UNRESOLVED],
        "conflict_intervals": [[row["start_sec"], row["end_sec"]]
                               for row in rows
                               if row["node_class"] == CONFLICT],
        "stitchable_intervals": [[row["start_sec"], row["end_sec"]]
                                 for row in rows
                                 if row["node_class"] == STITCHABLE],
        "semantic_truth_percentage": None,
        "note": "구간 길이는 coverage일 뿐 semantic 정확도가 아니다",
    }


# ── event lineage ────────────────────────────────────────────────
def assert_source_events(events) -> None:
    if EVENT_DELETION_ALLOWED or EVENT_TEXT_MUTATION_ALLOWED:
        raise MapError("event 삭제·수정 플래그가 열렸다")
    for event in events:
        window = event.get("source_window")
        if window in INVALID_SOURCE_WINDOWS:
            raise MapError("invalid source 창의 event다: %r"
                           % event.get("event_id"))
        if window not in VALID_SOURCE_WINDOWS:
            raise MapError("모르는 source 창: %r" % window)
    if len(events) != EXPECTED_SOURCE_EVENT_COUNT:
        raise MapError("source event 수가 %d가 아니다: %d"
                       % (EXPECTED_SOURCE_EVENT_COUNT, len(events)))
    per_window = {}
    for event in events:
        per_window[event["source_window"]] = \
            per_window.get(event["source_window"], 0) + 1
    if per_window != EXPECTED_EVENTS_PER_WINDOW:
        raise MapError("창별 event 수가 동결값과 다르다: %r" % per_window)
    ids = [event["event_id"] for event in events]
    if len(set(ids)) != len(ids):
        raise MapError("event_id가 중복됐다")


def _intersection(event, start: float, end: float) -> float:
    low = max(float(event["start_sec"]), start)
    high = min(float(event["end_sec"]), end)
    return round(max(0.0, high - low), 6)


def primary_region(event, rows) -> dict:
    """교차 길이가 가장 큰 region (동률이면 이른 region)."""
    best = None
    for row in rows:
        length = _intersection(event, row["start_sec"], row["end_sec"])
        if length <= 0:
            continue
        if best is None or length > best[0]:
            best = (length, row)
    if best is None:
        raise MapError("어느 region과도 교차하지 않는 event다: %r"
                       % event.get("event_id"))
    return best[1]


def touched_regions(event, rows) -> list:
    return [row["region_id"] for row in rows
            if _intersection(event, row["start_sec"], row["end_sec"]) > 0]


def member(event, start: float, end: float) -> dict:
    """구간으로 clip한 member 행. 텍스트는 원문 그대로 둔다."""
    if EVENT_TEXT_MUTATION_ALLOWED:
        raise MapError("event 텍스트 수정은 금지돼 있다")
    clipped = sh.clip_event(event, start, end)
    if clipped is None:
        raise MapError("구간과 교차하지 않는 event다: %r"
                       % event.get("event_id"))
    return {"event_id": event["event_id"],
            "source_window": event["source_window"],
            "original_start": clipped["original_start"],
            "original_end": clipped["original_end"],
            "clipped_start": clipped["clipped_start"],
            "clipped_end": clipped["clipped_end"],
            "clipped": clipped["clipped"],
            "actor": event.get("actor", ""),
            "action": event.get("action", ""),
            "object_or_state": event.get("object_or_state", "")}


def _events_in(events, window_ids, start: float, end: float) -> list:
    rows = [event for event in events
            if event["source_window"] in window_ids
            and _intersection(event, start, end) > 0]
    rows.sort(key=lambda event: (max(float(event["start_sec"]), start),
                                 event["event_id"]))
    return rows


# ── node 생성 ───────────────────────────────────────────────────
def stitch_groups(events, verdicts, rows, bank_times) -> list:
    overlaps = overlap_index()
    nodes = []
    for region in rows:
        if region["node_class"] != STITCHABLE:
            continue
        for overlap_id in region["overlap_ids"]:
            overlap = overlaps[overlap_id]
            relation = verdicts[overlap_id]["relation"]
            node_type = RELATION_TO_NODE_TYPE.get(relation)
            if node_type is None:
                raise MapError("STITCHABLE인데 relation이 %r다" % relation)
            sources = [overlap["earlier"], overlap["later"]]
            members = [member(event, overlap["start_sec"], overlap["end_sec"])
                       for event in _events_in(events, sources,
                                               overlap["start_sec"],
                                               overlap["end_sec"])]
            if not members:
                raise MapError("stitch group이 비었다: %s" % overlap_id)
            nodes.append({
                "node_id": "SG%03d" % (len(nodes) + 1),
                "node_type": node_type,
                "group_type": "STITCH_GROUP",
                "overlap_id": overlap_id,
                "region_id": region["region_id"],
                "relation": relation,
                "reviewer_status": st.STITCHABLE,
                "sources": sorted(sources),
                "start_sec": overlap["start_sec"],
                "end_sec": overlap["end_sec"],
                "ordered_members": members,
                "member_count": len(members),
                "description_generated": False,
                "frame_stamps": em.frame_stamps(overlap["start_sec"],
                                                overlap["end_sec"],
                                                bank_times),
            })
    return nodes


def conflict_blocks(events, verdicts, rows, bank_times) -> list:
    overlaps = overlap_index()
    nodes = []
    for region in rows:
        if region["node_class"] != CONFLICT:
            continue
        for overlap_id in region["overlap_ids"]:
            overlap = overlaps[overlap_id]
            sets = []
            for window_id in sorted([overlap["earlier"], overlap["later"]]):
                members = [
                    member(event, overlap["start_sec"], overlap["end_sec"])
                    for event in _events_in(events, [window_id],
                                            overlap["start_sec"],
                                            overlap["end_sec"])]
                if not members:
                    raise MapError("conflict 관측 집합이 비었다: %s / %s"
                                   % (overlap_id, window_id))
                sets.append({"source": window_id, "event_count": len(members),
                             "events": members})
            nodes.append({
                "node_id": "CB%03d" % (len(nodes) + 1),
                "node_type": CONFLICT_BLOCK,
                "overlap_id": overlap_id,
                "region_id": region["region_id"],
                "start_sec": overlap["start_sec"],
                "end_sec": overlap["end_sec"],
                "observation_set_1": sets[0],
                "observation_set_2": sets[1],
                "reviewer_relation": st.CONFLICT,
                "reviewer_status": st.MATERIAL_CONFLICT,
                "resolution": RESOLUTION_NONE,
                "preferred_source": None,
                "ordering_basis": ORDERING_BASIS,
                "frame_stamps": em.frame_stamps(overlap["start_sec"],
                                                overlap["end_sec"],
                                                bank_times),
            })
    return nodes


def conflict_regions(rows, blocks) -> list:
    nodes = []
    for region in rows:
        if region["node_class"] != CONFLICT:
            continue
        members = [row for row in blocks
                   if row["region_id"] == region["region_id"]]
        if not members:
            raise MapError("conflict region에 block이 없다: %s"
                           % region["region_id"])
        nodes.append({
            "node_id": "CR%02d" % (len(nodes) + 1),
            "group_type": "CONFLICT_REGION",
            "region_id": region["region_id"],
            "start_sec": region["start_sec"],
            "end_sec": region["end_sec"],
            "member_overlaps": [row["overlap_id"] for row in members],
            "member_blocks": [row["node_id"] for row in members],
            "reviewer_status": st.MATERIAL_CONFLICT,
            "resolution": RESOLUTION_NONE,
            "note": "내부 block·관측 구조를 그대로 유지한다",
        })
    return nodes


def single_source_nodes(events, rows, bank_times) -> list:
    nodes = []
    for region in rows:
        if region["node_class"] != SINGLE_SOURCE:
            continue
        windows = covering_windows(region["start_sec"], region["end_sec"])
        if len(windows) != 1:
            raise MapError("single-source region의 창이 1개가 아니다: %r"
                           % (windows,))
        window_id = windows[0]
        members = [member(event, region["start_sec"], region["end_sec"])
                   for event in _events_in(events, [window_id],
                                           region["start_sec"],
                                           region["end_sec"])]
        if not members:
            raise MapError("single-source region이 비었다: %s"
                           % region["region_id"])
        nodes.append({
            "node_id": "SS%02d" % (len(nodes) + 1),
            "node_type": SINGLE_SOURCE_EVENT,
            "region_id": region["region_id"],
            "start_sec": region["start_sec"],
            "end_sec": region["end_sec"],
            "source_window": window_id,
            "events": members,
            "event_count": len(members),
            "note": "valid 창 하나만 관측한 구간 — 교차 검증 없음",
            "frame_stamps": em.frame_stamps(region["start_sec"],
                                            region["end_sec"], bank_times),
        })
    return nodes


def unresolved_gaps(rows, bank_times) -> list:
    nodes = []
    for region in rows:
        if region["node_class"] != UNRESOLVED:
            continue
        if SYNTHETIC_FILL_ALLOWED:
            raise MapError("synthetic fill 플래그가 열렸다")
        nodes.append({
            "node_id": "UG%02d" % (len(nodes) + 1),
            "node_type": UNRESOLVED_GAP,
            "region_id": region["region_id"],
            "start_sec": region["start_sec"],
            "end_sec": region["end_sec"],
            "events": [],
            "filled": False,
            "resolution": RESOLUTION_NONE,
            "invalid_source_windows": list(INVALID_SOURCE_WINDOWS),
            "reason": ("이 구간을 덮는 창은 W00뿐이고 W00은 WINDOW_INVALID다 "
                       "— 대체 생성 금지"),
            "frame_stamps": em.frame_stamps(region["start_sec"],
                                            region["end_sec"], bank_times),
        })
    return nodes


# ── lineage · 위반 감지 ─────────────────────────────────────────
def all_members(document) -> list:
    rows = []
    for node in document["nodes"]["stitch_groups"]:
        rows.extend(node["ordered_members"])
    for node in document["nodes"]["conflict_blocks"]:
        rows.extend(node["observation_set_1"]["events"])
        rows.extend(node["observation_set_2"]["events"])
    for node in document["nodes"]["single_source"]:
        rows.extend(node["events"])
    for node in document["nodes"]["unresolved_gaps"]:
        rows.extend(node["events"])
    return rows


def _memberships(document) -> dict:
    index = {}
    for node in document["nodes"]["stitch_groups"]:
        for row in node["ordered_members"]:
            index.setdefault(row["event_id"], []).append(node["node_id"])
    for node in document["nodes"]["conflict_blocks"]:
        for key in ("observation_set_1", "observation_set_2"):
            for row in node[key]["events"]:
                index.setdefault(row["event_id"], []).append(node["node_id"])
    for node in document["nodes"]["single_source"]:
        for row in node["events"]:
            index.setdefault(row["event_id"], []).append(node["node_id"])
    return index


def lineage(events, rows, document) -> list:
    memberships = _memberships(document)
    result = []
    for event in sorted(events, key=lambda row: row["event_id"]):
        region = primary_region(event, rows)
        touched = touched_regions(event, rows)
        result.append({
            "event_id": event["event_id"],
            "source_window": event["source_window"],
            "start_sec": float(event["start_sec"]),
            "end_sec": float(event["end_sec"]),
            "primary_region": region["region_id"],
            "primary_region_class": region["node_class"],
            "also_in_regions": [name for name in touched
                                if name != region["region_id"]],
            "lineage_type": CLASS_TO_LINEAGE[region["node_class"]],
            "node_memberships": sorted(
                em.dedup(memberships.get(event["event_id"], []))),
        })
    return result


def lineage_summary(events, rows) -> dict:
    missing = [row["event_id"] for row in rows if not row["node_memberships"]]
    return {"source_events_total": len(events),
            "events_represented": len(events) - len(missing),
            "events_missing": len(missing),
            "missing_event_ids": missing,
            "straddling_event_count": sum(1 for row in rows
                                          if row["also_in_regions"])}


def false_resolutions(document) -> list:
    """conflict가 해결·병합·선호된 흔적을 구조로 잡는다."""
    violations = []
    blocks = document["nodes"]["conflict_blocks"]
    stitched = {node["overlap_id"]: node["node_id"]
                for node in document["nodes"]["stitch_groups"]}
    conflict_overlaps = {node["overlap_id"] for node in blocks}
    for node in blocks:
        one, two = node["observation_set_1"], node["observation_set_2"]
        if one["source"] == two["source"]:
            violations.append({"node_id": node["node_id"],
                               "reason": "관측 집합의 source가 같다"})
        if not one["events"] or not two["events"]:
            violations.append({"node_id": node["node_id"],
                               "reason": "관측 집합이 비었다"})
        if node.get("resolution") != RESOLUTION_NONE:
            violations.append({"node_id": node["node_id"],
                               "reason": "resolution이 NONE이 아니다"})
        if node.get("preferred_source") is not None:
            violations.append({"node_id": node["node_id"],
                               "reason": "선호 source가 지정됐다"})
        if node["overlap_id"] in stitched:
            violations.append({"node_id": node["node_id"],
                               "reason": "conflict가 stitch group으로도 있다"})
    for overlap_id, node_id in stitched.items():
        if overlap_id in conflict_overlaps:
            violations.append({"node_id": node_id,
                               "reason": "conflict overlap이 병합됐다"})
    return violations


def invalid_source_dependencies(document) -> list:
    rows = []
    for row in all_members(document):
        if row["source_window"] in INVALID_SOURCE_WINDOWS:
            rows.append({"event_id": row["event_id"],
                         "reason": "invalid source 창"})
    for node in document["nodes"]["single_source"]:
        if node["source_window"] in INVALID_SOURCE_WINDOWS:
            rows.append({"node_id": node["node_id"],
                         "reason": "invalid source 창"})
    for node in document["nodes"]["unresolved_gaps"]:
        if node["events"] or node["filled"]:
            rows.append({"node_id": node["node_id"],
                         "reason": "unresolved gap이 채워졌다"})
    for row in all_members(document):
        if row["clipped_start"] < 24.0:
            rows.append({"event_id": row["event_id"],
                         "reason": "unresolved 구간에 event가 들어갔다"})
    return rows


# ── 문서 조립 ───────────────────────────────────────────────────
def provenance_stub() -> dict:
    return {"prereg": PREREG, "event": EVENT,
            "prereg_commit": "unknown", "code_git_head": "unknown",
            "source_hashes": dict(FROZEN_HASHES),
            "source_manifest_sha256": VALID_SOURCE_MANIFEST_SHA256,
            "video_sha256": VIDEO_SHA256,
            "new_inference_count": 0, "new_llm_call_count": 0}


def build_document(events, verdict_state, bank_times, provenance) -> dict:
    assert_flags_closed()
    assert_source_events(events)
    verdicts = verdict_index(verdict_state)
    rows = regions(verdict_state)
    groups = stitch_groups(events, verdicts, rows, bank_times)
    blocks = conflict_blocks(events, verdicts, rows, bank_times)
    singles = single_source_nodes(events, rows, bank_times)
    gaps = unresolved_gaps(rows, bank_times)
    crs = conflict_regions(rows, blocks)
    nodes = {"stitch_groups": groups, "conflict_blocks": blocks,
             "conflict_regions": crs, "single_source": singles,
             "unresolved_gaps": gaps}
    node_ids = {}
    for node in groups + blocks + singles + gaps:
        node_ids.setdefault(node["region_id"], []).append(node["node_id"])
    for region in rows:
        region["node_ids"] = node_ids.get(region["region_id"], [])
        region["status"] = {
            CONFLICT: "MATERIAL_CONFLICT / RESOLUTION NONE",
            STITCHABLE: "STITCHABLE (리뷰어 판정)",
            SINGLE_SOURCE: "SINGLE_SOURCE (교차 검증 없음)",
            UNRESOLVED: "UNRESOLVED (valid 관측 없음)"}[region["node_class"]]
        region["reviewer_relations"] = [
            verdicts[overlap_id]["relation"]
            for overlap_id in region["overlap_ids"]]
        region["frame_stamp_count"] = len(
            em.frame_stamps(region["start_sec"], region["end_sec"],
                            bank_times))
    document = {
        "schema": SCHEMA,
        "event": EVENT,
        "prereg": PREREG,
        "artifact_name": ARTIFACT_NAME,
        "provenance": dict(provenance),
        "policy": {
            "conflict_resolution": "NONE",
            "preferred_source": None,
            "ordering_basis": ORDERING_BASIS,
            "flags": {name: globals()[name] for name in FLAGS},
            "node_types": list(NODE_TYPES),
            "group_types": list(GROUP_TYPES),
            "final_verdict_vocabulary": FINAL_VERDICT_VOCABULARY_LINE,
            "verdict_by_executor": VERDICT_BY_EXECUTOR,
            "allowed_max_conclusion": ALLOWED_MAX_CONCLUSION,
            "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS),
        },
        "prior_state": dict(PRIOR_STATE),
        "regions": rows,
        "nodes": nodes,
        "coverage": coverage(rows),
        "silent_concat": False,
    }
    document["lineage"] = lineage(events, rows, document)
    document["lineage_summary"] = lineage_summary(events, document["lineage"])
    if document["lineage_summary"]["events_missing"]:
        raise MapError("lineage 누락 event가 있다: %r"
                       % document["lineage_summary"]["missing_event_ids"])
    document["summary_counts"] = summary_counts(document)
    if document["summary_counts"]["false_resolution_count"]:
        raise MapError("conflict가 해결·병합됐다")
    if document["summary_counts"]["invalid_source_dependency_count"]:
        raise MapError("invalid source 의존이 있다")
    document["executor_state"] = executor_state(document)
    return document


def summary_counts(document) -> dict:
    groups = document["nodes"]["stitch_groups"]
    return {
        "region_count": len(document["regions"]),
        "consensus_event_count": sum(1 for row in groups
                                     if row["node_type"] == CONSENSUS_EVENT),
        "continuation_group_count": sum(
            1 for row in groups if row["node_type"] == CONTINUATION_GROUP),
        "transition_count": sum(1 for row in groups
                                if row["node_type"] == TRANSITION),
        "stitch_group_count": len(groups),
        "conflict_block_count": len(document["nodes"]["conflict_blocks"]),
        "conflict_region_count": len(document["nodes"]["conflict_regions"]),
        "single_source_count": len(document["nodes"]["single_source"]),
        "single_source_event_count": sum(
            row["event_count"] for row in document["nodes"]["single_source"]),
        "unresolved_gap_count": len(document["nodes"]["unresolved_gaps"]),
        "false_resolution_count": len(false_resolutions(document)),
        "invalid_source_dependency_count": len(
            invalid_source_dependencies(document)),
    }


def executor_state(document) -> dict:
    return {"state": EXECUTOR_STATE,
            "verdict": None,
            "verdict_by_executor": VERDICT_BY_EXECUTOR,
            "final_verdict_vocabulary": FINAL_VERDICT_VOCABULARY_LINE,
            "new_inference_count": 0, "new_llm_call_count": 0,
            "chapter_generated": CHAPTER_ALLOWED,
            "narrative_generated": NARRATIVE_GENERATION_ALLOWED,
            "region_count": len(document["regions"]),
            "allowed_max_conclusion": ALLOWED_MAX_CONCLUSION}


def summary_document(document) -> dict:
    counts = document["summary_counts"]
    lineage_rows = document["lineage_summary"]
    return {"schema": "wvr_conservative_event_map_v1_summary",
            "event": EVENT, "prereg": PREREG,
            "provenance": document["provenance"],
            "source_events_total": lineage_rows["source_events_total"],
            "events_represented": lineage_rows["events_represented"],
            "events_missing": lineage_rows["events_missing"],
            "straddling_event_count": lineage_rows["straddling_event_count"],
            **counts,
            "conflict_duration_sec":
                document["coverage"]["conflict_duration_sec"],
            "stitchable_duration_sec":
                document["coverage"]["stitchable_duration_sec"],
            "single_source_duration_sec":
                document["coverage"]["single_source_duration_sec"],
            "unresolved_duration_sec":
                document["coverage"]["unresolved_duration_sec"],
            "total_sec": document["coverage"]["total_sec"],
            "semantic_truth_percentage": None,
            "new_inference_count": 0, "new_llm_call_count": 0,
            "executor_state": document["executor_state"],
            "reviewer_final_verdict": None,
            "final_verdict_vocabulary": FINAL_VERDICT_VOCABULARY_LINE}


def canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)


# ── 사람이 읽는 산출물 (narrative 생성 없음 · 원문 나열만) ────────────
def _member_line(row) -> str:
    origin = ""
    if row["clipped"]:
        origin = "  (원본 %.1f–%.1f)" % (row["original_start"],
                                       row["original_end"])
    return "  %6.1f–%6.1f | %-4s | %s | %s | %s%s" % (
        row["clipped_start"], row["clipped_end"], row["source_window"],
        row["actor"], row["action"], row["object_or_state"], origin)


def map_markdown(document) -> str:
    lines = ["# CONSERVATIVE_EVENT_MAP (%s)" % EVENT, "",
             "리뷰어 판정을 그대로 쓰고 conflict는 해결하지 않는다. "
             "상위 narrative 문구는 생성하지 않았다.", "",
             "```", "region %d · 0–600초 연속 · source event %d건 · 유실 %d건"
             % (len(document["regions"]),
                document["lineage_summary"]["source_events_total"],
                document["lineage_summary"]["events_missing"]),
             "conflict %.0f초 · stitchable %.0f초 · single-source %.0f초 · "
             "unresolved %.0f초"
             % (document["coverage"]["conflict_duration_sec"],
                document["coverage"]["stitchable_duration_sec"],
                document["coverage"]["single_source_duration_sec"],
                document["coverage"]["unresolved_duration_sec"]),
             "```", ""]
    groups = {row["node_id"]: row for row in document["nodes"]["stitch_groups"]}
    blocks = {row["node_id"]: row
              for row in document["nodes"]["conflict_blocks"]}
    singles = {row["node_id"]: row
               for row in document["nodes"]["single_source"]}
    gaps = {row["node_id"]: row for row in document["nodes"]["unresolved_gaps"]}
    crs = {row["region_id"]: row
           for row in document["nodes"]["conflict_regions"]}
    for region in document["regions"]:
        lines.append("## %s  %.0f–%.0f  %s"
                     % (region["region_id"], region["start_sec"],
                        region["end_sec"], region["node_class"]))
        lines.append("")
        lines.append("```")
        lines.append("창        %s" % (", ".join(region["source_windows"])
                                      or "없음 (valid 관측 없음)"))
        lines.append("overlap   %s" % (", ".join(region["overlap_ids"])
                                       or "-"))
        lines.append("판정      %s" % (", ".join(region["reviewer_relations"])
                                      or "-"))
        lines.append("상태      %s" % region["status"])
        lines.append("frame     %d개 (0.5fps · traceability 전용)"
                     % region["frame_stamp_count"])
        if region["region_id"] in crs:
            lines.append("conflict region %s (block %s)"
                         % (crs[region["region_id"]]["node_id"],
                            ", ".join(crs[region["region_id"]]
                                      ["member_blocks"])))
        lines.append("```")
        lines.append("")
        for node_id in region["node_ids"]:
            if node_id in gaps:
                node = gaps[node_id]
                lines += ["### %s UNRESOLVED_GAP  %.0f–%.0f" % (
                    node_id, node["start_sec"], node["end_sec"]), "",
                    "```", node["reason"],
                    "event 0건 · filled=False · resolution=NONE", "```", ""]
            elif node_id in singles:
                node = singles[node_id]
                lines += ["### %s SINGLE_SOURCE_EVENT  %.0f–%.0f  (%s · %d건)"
                          % (node_id, node["start_sec"], node["end_sec"],
                             node["source_window"], node["event_count"]), "",
                          "```"]
                lines += [_member_line(row) for row in node["events"]]
                lines += ["```", ""]
            elif node_id in groups:
                node = groups[node_id]
                lines += ["### %s %s  %.0f–%.0f  (%s · %s · %d건)"
                          % (node_id, node["node_type"], node["start_sec"],
                             node["end_sec"], " + ".join(node["sources"]),
                             node["relation"], node["member_count"]), "",
                          "```"]
                lines += [_member_line(row) for row in node["ordered_members"]]
                lines += ["```", ""]
            elif node_id in blocks:
                node = blocks[node_id]
                lines += ["### %s CONFLICT_BLOCK  %.0f–%.0f  (resolution NONE)"
                          % (node_id, node["start_sec"], node["end_sec"]), "",
                          "```"]
                for key in ("observation_set_1", "observation_set_2"):
                    observation = node[key]
                    lines.append("%s  source %s (%d건)"
                                 % (key, observation["source"],
                                    observation["event_count"]))
                    lines += [_member_line(row)
                              for row in observation["events"]]
                lines += ["두 관측은 alternative source observations다 — "
                          "선호·승자 없음", "```", ""]
    return "\n".join(lines) + "\n"


def chapter_input_packet(document) -> str:
    counts = document["summary_counts"]
    lines = ["# CONSERVATIVE_EVENT_MAP chapter-input packet", "",
             "리뷰어 판정용 재료다. **executor는 답을 쓰지 않는다.** "
             "Chapter·narrative 문구는 생성하지 않았다.", "",
             "## region 구조 (0–600초)", "", "```"]
    for region in document["regions"]:
        lines.append("%s %6.0f–%6.0f  %-13s  overlap %-20s node %s"
                     % (region["region_id"], region["start_sec"],
                        region["end_sec"], region["node_class"],
                        ",".join(region["overlap_ids"]) or "-",
                        ",".join(region["node_ids"]) or "-"))
    lines += ["```", "", "## 수치", "", "```",
              "source event %d · 표현됨 %d · 유실 %d"
              % (document["lineage_summary"]["source_events_total"],
                 document["lineage_summary"]["events_represented"],
                 document["lineage_summary"]["events_missing"]),
              "CONSENSUS_EVENT %d · CONTINUATION_GROUP %d · TRANSITION %d"
              % (counts["consensus_event_count"],
                 counts["continuation_group_count"],
                 counts["transition_count"]),
              "CONFLICT_BLOCK %d · CONFLICT_REGION %d · SINGLE_SOURCE %d · "
              "UNRESOLVED_GAP %d"
              % (counts["conflict_block_count"],
                 counts["conflict_region_count"],
                 counts["single_source_count"],
                 counts["unresolved_gap_count"]),
              "conflict %.0f초 · stitchable %.0f초 · single-source %.0f초 · "
              "unresolved %.0f초"
              % (document["coverage"]["conflict_duration_sec"],
                 document["coverage"]["stitchable_duration_sec"],
                 document["coverage"]["single_source_duration_sec"],
                 document["coverage"]["unresolved_duration_sec"]),
              "false_resolution %d · invalid_source_dependency %d"
              % (counts["false_resolution_count"],
                 counts["invalid_source_dependency_count"]),
              "```", "", "## 판정 질문 (리뷰어 전용)", ""]
    for question, detail in (
            ("Q1 STRUCTURAL_USABILITY",
             "whole-video temporal structure가 보이는가"),
            ("Q2 CONFLICT_LOCALIZATION",
             "material conflict가 명시적 block으로 격리됐는가"),
            ("Q3 NO_FALSE_RESOLUTION",
             "conflict가 consensus처럼 병합된 곳이 없는가"),
            ("Q4 CHAPTER_INPUT_USABILITY",
             "이 map으로 conflict를 숨기지 않은 Chapter 후보를 만들 수 있는가")):
        lines += ["```", "%s" % question, detail,
                  "판정: %s" % NOT_ADJUDICATED, "```", ""]
    lines += ["## 최종 어휘 (리뷰어 전용)", "", "```",
              FINAL_VERDICT_VOCABULARY_LINE,
              "executor 상태: %s · verdict %s" % (EXECUTOR_STATE,
                                                 NOT_ADJUDICATED),
              "```", "",
              "말할 수 있는 최대 결론: %s" % ALLOWED_MAX_CONCLUSION, ""]
    return "\n".join(lines) + "\n"


def dedup(values) -> list:
    return em.dedup(values)
