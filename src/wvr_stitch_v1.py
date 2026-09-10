"""WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1 계측기 (2026-09-10 · freeze).

사전등록: `docs/preregistration/WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md`

```
질문   인접 창의 공유 24초에서 서로 다른 표현의 Local Event를 의미적으로
      SAME / CONTINUATION / TRANSITION / CONFLICT로 구분할 수 있는가
단위   event 한 줄이 아니라 overlap-local event sequence
대상   valid-valid adjacency 22개 (O02…O23) · 새 추론 0회
금지   판정 채우기 · 새 임계/유사도 컷 · Event Map 재생성 · Semantic Chapter ·
      새 LLM 호출 · event 텍스트 수정 · mapping 조기 reveal
```

이 모듈은 순수 계산만 한다. 파일 입출력은 `scripts/wvr_stitch_*.py`가 한다.
"""
import hashlib

import wvr_density_v2 as v2
import wvr_event_map_v1 as em
import wvr_shadow_v1 as sh
import wvr_subdivision_v1 as sd

EVENT = "WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1"
ARTIFACT_TAG = "stitch_v1"

# ── 대상 (사전등록 §3) ─────────────────────────────────────────────
VALID_SOURCE_WINDOWS = em.VALID_SOURCE_WINDOWS
INVALID_SOURCE_WINDOWS = em.INVALID_SOURCE_WINDOWS
EXCLUDED_OVERLAPS = ("O01",)                  # W00–W01 (W00은 invalid source)
EXPECTED_OVERLAP_COUNT = 22
OVERLAP_SEC = sh.OVERLAP_SEC                  # 24.0
SHARED_FRAMES_PER_OVERLAP = sh.SHARED_FRAMES_PER_OVERLAP   # 12
COMPARISON_UNIT = "overlap_local_event_sequence"
VALID_SOURCE_MANIFEST_SHA256 = em.VALID_SOURCE_MANIFEST_SHA256

NEW_INFERENCE_ALLOWED = False
NEW_LLM_CALL_ALLOWED = False
EVENT_TEXT_MUTATION_ALLOWED = False
EVENT_MAP_REBUILD_ALLOWED = False
ADJUDICATED_MAP_BUILD_ALLOWED = False
SEMANTIC_CHAPTER_ALLOWED = False
OVERVIEW_GENERATION_ALLOWED = False
SIMILARITY_THRESHOLD_ALLOWED = False          # 임계·점수 컷 금지
VERDICT_BY_EXECUTOR = False
MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED = False
W00_RERUN_ALLOWED = False
PRODUCTION_PROMOTION_ALLOWED = False

# ── reviewer 어휘 (executor가 채우지 않는다) ────────────────────────
SAME_EVENT = "SAME_EVENT"
CONTINUATION = "CONTINUATION"
TRANSITION = "TRANSITION"
CONFLICT = "CONFLICT"
UNRESOLVED = "UNRESOLVED"
RELATION_VERDICTS = (SAME_EVENT, CONTINUATION, TRANSITION, CONFLICT,
                     UNRESOLVED)

STITCHABLE = "STITCHABLE"
MATERIAL_CONFLICT = "MATERIAL_CONFLICT"
TOP_UNRESOLVED = "UNRESOLVED"
TOP_VERDICTS = (STITCHABLE, MATERIAL_CONFLICT, TOP_UNRESOLVED)

NOT_ADJUDICATED = "NOT_ADJUDICATED"
FINAL_VERDICTS = ("STITCHING_SHADOW_PASS", "STITCHING_SHADOW_HOLD",
                  "STITCHING_SHADOW_INCONCLUSIVE")
EXECUTOR_STATE = "EXECUTED / REVIEW_PENDING"

AUDIT_ROLE = "AUDIT_DIAGNOSTIC_ONLY"
JUDGMENT_BASIS = ("문자열 일치가 아니라 report-material contradiction으로 본다")
ALLOWED_MAX_CONCLUSION = (
    "사람이 22개 overlap 대부분을 stitchable로 판정했다면, Local Event 표현은 "
    "Adjudicated Event Map 구축을 시도할 최소 조건을 만족한다.")
FORBIDDEN_CONCLUSIONS = (
    "Event Map이 검증됐다", "stitching이 해결됐다", "0.5fps sufficient",
    "Semantic Chapter로 바로 간다", "production ready",
    "Local Event representation이 근본적으로 실패다",
    "문자열 일치율이 곧 품질이다")

PRIOR_STATE = {
    "WVR_EVENT_MAP_COVERAGE_SHADOW_V1": "CLOSED / EVENT_MAP_SHADOW_HOLD",
    "WVR_EVENT_EXTRACTION_SHADOW_V1": "CLOSED / INCONCLUSIVE",
    "SUBDIVISION_family": "STOPPED / NOT SUFFICIENT",
    "reviewer_answers": {
        "Q1_FLOW_RECOVERABLE": "COARSELY YES",
        "Q2_GAP_MATERIALITY": "NOT PRIMARY BLOCKER",
        "Q3_EVENT_MAP_USABLE": "NO"},
    "bottleneck": "Local Events → ★ Event stitching → Event Map",
    "W00": "WINDOW_INVALID (invalid source · 재실행 금지)",
}

NORMATIVE_AUTHORITY = (
    "WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1 preregistration",
    "frozen SHADOW_V1 execution artifacts",
    "frozen parser/collapse rules (wvr_density_v2)",
    "EVENT_MAP_COVERAGE_SHADOW_V1 registry lineage",
    "PROJECT_OVERVIEW.md",
)


class StitchError(RuntimeError):
    """stitching 계약 위반."""


def overlaps() -> list:
    """valid-valid adjacency 22개 (O01 제외)."""
    rows = [row for row in sh.overlaps()
            if row["overlap_id"] not in EXCLUDED_OVERLAPS
            and row["earlier"] not in INVALID_SOURCE_WINDOWS
            and row["later"] not in INVALID_SOURCE_WINDOWS]
    if len(rows) != EXPECTED_OVERLAP_COUNT:
        raise StitchError("overlap 개수가 %d가 아니다: %d"
                          % (EXPECTED_OVERLAP_COUNT, len(rows)))
    for row in rows:
        if round(row["end_sec"] - row["start_sec"], 6) != OVERLAP_SEC:
            raise StitchError("겹침이 %.1f초가 아니다: %r"
                              % (OVERLAP_SEC, row))
    return rows


def overlap_by_id(overlap_id: str) -> dict:
    for row in overlaps():
        if row["overlap_id"] == overlap_id:
            return row
    raise StitchError("모르는 겹침: %r" % overlap_id)


def shared_times(overlap: dict) -> tuple:
    return sh.shared_times(overlap)


def clip_sequence(events, overlap: dict) -> list:
    """공유 구간과 교차하는 event만 그 구간으로 clip한다. 원본 미변경."""
    if EVENT_TEXT_MUTATION_ALLOWED:
        raise StitchError("event 텍스트 수정은 금지돼 있다")
    rows = []
    for event in events:
        clipped = sh.clip_event(event, overlap["start_sec"],
                                overlap["end_sec"])
        if clipped is None:
            continue
        rows.append({
            "event_id": event.get("event_id"),
            "source_window": event.get("source_window"),
            "original_start": clipped["original_start"],
            "original_end": clipped["original_end"],
            "clipped_start": clipped["clipped_start"],
            "clipped_end": clipped["clipped_end"],
            "clipped": clipped["clipped"],
            "actor": event.get("actor", ""),
            "action": event.get("action", ""),
            "object_or_state": event.get("object_or_state", ""),
        })
    rows.sort(key=lambda row: (row["clipped_start"],
                               row["event_id"] or ""))
    return rows


def blind_label(overlap_id: str, role: str, prereg_sha: str) -> str:
    """earlier·later를 Arm A/B로 가린다 (사전등록 §4 · 결정적)."""
    if role not in ("earlier", "later"):
        raise StitchError("모르는 role: %r" % role)
    if not prereg_sha:
        raise StitchError("prereg SHA가 비어 있다")
    digest = hashlib.sha256(("%s|%s" % (prereg_sha, overlap_id))
                            .encode("utf-8"))
    flip = digest.digest()[0] & 1
    if role == "earlier":
        return "B" if flip else "A"
    return "A" if flip else "B"


def _content(event: dict) -> dict:
    return {"actor": event.get("actor", ""), "action": event.get("action", ""),
            "object_or_state": event.get("object_or_state", "")}


def sequence_tokens(rows) -> set:
    tokens = set()
    for row in rows:
        tokens |= v2.tokens(_content(row))
    return tokens


def pair_audit(arm_a_rows, arm_b_rows) -> dict:
    """AUDIT_DIAGNOSTIC_ONLY. 임계·점수 컷을 만들지 않는다.

    입력은 **blind 라벨 순서(Arm A · Arm B)**로 받는다 — earlier/later를 키 이름으로
    쓰면 audit 파일만 봐도 창 순서가 드러나므로 blinding이 깨진다.
    """
    if SIMILARITY_THRESHOLD_ALLOWED:
        raise StitchError("유사도 임계 도입은 금지돼 있다")
    relations = {v2.SEMANTICALLY_EQUIVALENT: 0, v2.SEMANTICALLY_DIFFERENT: 0,
                 v2.ADJUDICATION_REQUIRED: 0}
    exact_pairs = []
    for left in arm_a_rows:
        for right in arm_b_rows:
            relation = v2.semantic_relation(_content(left),
                                            _content(right))["relation"]
            relations[relation] = relations.get(relation, 0) + 1
            if relation == v2.SEMANTICALLY_EQUIVALENT:
                exact_pairs.append([left["event_id"], right["event_id"]])
    arm_a_tokens = sequence_tokens(arm_a_rows)
    arm_b_tokens = sequence_tokens(arm_b_rows)
    return {
        "role": AUDIT_ROLE,
        "arm_a_event_count": len(arm_a_rows),
        "arm_b_event_count": len(arm_b_rows),
        "event_count_difference": abs(len(arm_a_rows) - len(arm_b_rows)),
        "arm_a_described_sec": round(sum(row["clipped_end"]
                                         - row["clipped_start"]
                                         for row in arm_a_rows), 3),
        "arm_b_described_sec": round(sum(row["clipped_end"]
                                         - row["clipped_start"]
                                         for row in arm_b_rows), 3),
        "pairwise_relation_counts": relations,
        "exact_signature_pairs": exact_pairs,
        "exact_signature_pair_count": len(exact_pairs),
        "arm_a_actors": sorted({v2.normalize(row["actor"])
                                for row in arm_a_rows}),
        "arm_b_actors": sorted({v2.normalize(row["actor"])
                                for row in arm_b_rows}),
        "arm_a_actions": sorted({v2.normalize(row["action"])
                                 for row in arm_a_rows}),
        "arm_b_actions": sorted({v2.normalize(row["action"])
                                 for row in arm_b_rows}),
        "shared_token_count": len(arm_a_tokens & arm_b_tokens),
        "arm_a_only_token_count": len(arm_a_tokens - arm_b_tokens),
        "arm_b_only_token_count": len(arm_b_tokens - arm_a_tokens),
        "shared_tokens": sorted(arm_a_tokens & arm_b_tokens),
        "arm_a_span": ([arm_a_rows[0]["clipped_start"],
                        arm_a_rows[-1]["clipped_end"]]
                       if arm_a_rows else None),
        "arm_b_span": ([arm_b_rows[0]["clipped_start"],
                        arm_b_rows[-1]["clipped_end"]]
                       if arm_b_rows else None),
        "threshold_used": False,
        "note": "판정 authority가 아니다 — reviewer가 sequence 단위로 본다",
    }


def empty_verdict(overlap_id: str) -> dict:
    """executor 기본값: 아무 판정도 채우지 않는다."""
    return {"overlap_id": overlap_id, "relation": NOT_ADJUDICATED,
            "top_verdict": NOT_ADJUDICATED, "note": "",
            "adjudicated": False}


def parse_verdicts(payload) -> dict:
    """리뷰어 입력만 기록한다. 동결 어휘 외 입력은 거부한다."""
    if VERDICT_BY_EXECUTOR:
        raise StitchError("executor는 판정을 채우지 않는다")
    rows = {row["overlap_id"]: empty_verdict(row["overlap_id"])
            for row in overlaps()}
    entries = (payload or {}).get("verdicts") or []
    for entry in entries:
        overlap_id = entry.get("overlap_id")
        if overlap_id not in rows:
            raise StitchError("모르는 overlap: %r" % overlap_id)
        relation = entry.get("relation")
        top = entry.get("top_verdict")
        if relation not in RELATION_VERDICTS:
            raise StitchError("허용되지 않은 relation: %r" % relation)
        if top not in TOP_VERDICTS:
            raise StitchError("허용되지 않은 top_verdict: %r" % top)
        rows[overlap_id] = {"overlap_id": overlap_id, "relation": relation,
                            "top_verdict": top,
                            "note": str(entry.get("note") or "")[:500],
                            "adjudicated": True}
    adjudicated = [row for row in rows.values() if row["adjudicated"]]
    counts = {name: sum(1 for row in adjudicated if row["relation"] == name)
              for name in RELATION_VERDICTS}
    top_counts = {name: sum(1 for row in adjudicated
                            if row["top_verdict"] == name)
                  for name in TOP_VERDICTS}
    return {
        "verdicts": [rows[row["overlap_id"]] for row in overlaps()],
        "adjudicated_count": len(adjudicated),
        "expected_count": EXPECTED_OVERLAP_COUNT,
        "complete": len(adjudicated) == EXPECTED_OVERLAP_COUNT,
        "relation_counts": counts, "top_verdict_counts": top_counts,
        "final_verdict": None,
        "final_verdict_by_executor": VERDICT_BY_EXECUTOR,
        "final_verdict_vocabulary": list(FINAL_VERDICTS),
        "judgment_basis": JUDGMENT_BASIS,
    }


def reveal_allowed(verdict_state: dict) -> dict:
    """모든 overlap 판정이 기록된 뒤에만 mapping reveal이 허용된다."""
    complete = bool((verdict_state or {}).get("complete"))
    return {"allowed": complete
            and not MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED is True,
            "complete": complete,
            "adjudicated_count": (verdict_state or {}).get(
                "adjudicated_count", 0),
            "expected_count": EXPECTED_OVERLAP_COUNT,
            "reason": "" if complete else "VERDICTS_INCOMPLETE"}


def executor_state(pairs, audits) -> dict:
    return {
        "state": EXECUTOR_STATE,
        "overlap_count": len(pairs),
        "expected_overlap_count": EXPECTED_OVERLAP_COUNT,
        "comparison_unit": COMPARISON_UNIT,
        "new_inference_count": 0,
        "new_llm_call_count": 0,
        "relation_vocabulary": list(RELATION_VERDICTS),
        "top_verdict_vocabulary": list(TOP_VERDICTS),
        "final_verdict_vocabulary": list(FINAL_VERDICTS),
        "verdict": None,
        "verdict_by_executor": VERDICT_BY_EXECUTOR,
        "judgment_basis": JUDGMENT_BASIS,
        "allowed_max_conclusion": ALLOWED_MAX_CONCLUSION,
        "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS),
        "audit_role": AUDIT_ROLE,
        "threshold_used": any(row.get("threshold_used") for row in audits),
        "event_map_rebuild_allowed": EVENT_MAP_REBUILD_ALLOWED,
        "adjudicated_map_build_allowed": ADJUDICATED_MAP_BUILD_ALLOWED,
        "semantic_chapter_allowed": SEMANTIC_CHAPTER_ALLOWED,
    }


def dedup(values) -> list:
    return sd.dedup(values)
