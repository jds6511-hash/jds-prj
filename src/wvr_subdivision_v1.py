"""WVR_W00_SUBDIVISION_RECOVERY_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md`

```
질문     결정적으로 실패하는 W00 [0,48)를 24초/12초 overlap child로 분해하면
        prompt·runtime·표집을 바꾸지 않고 technically valid한 표현을 얻는가
측정     recovery efficacy 하나. "48초가 원인이다"·"24초가 안전하다"는 측정하지 않는다
변경     창 길이 48초 → 24초(12초 overlap) 하나. 그 밖은 전부 W00과 동일
금지     token cap 상향 · prompt·schema 수정 · retry · raw salvage ·
        원본 W00 소급 VALID 전환 · SHADOW_V1 소급 복구 · semantic 판정 · mapping reveal
```
"""
import hashlib

import wvr_shadow_v1 as sh
import wvr_w00_repro as rp

EVENT = "WVR_W00_SUBDIVISION_RECOVERY_V1"
ARTIFACT_TAG = "subdiv_v1"

# ── 분해 일정 (결과 보기 전 동결) ────────────────────────────────────
PARENT_WINDOW_ID = "W00"
PARENT_START_SEC = 0.0
PARENT_END_SEC = 48.0
CHILD_SEC = 24.0
STRIDE_SEC = 12.0
OVERLAP_SEC = 12.0
SAMPLING_FPS = 0.5
STEP_SEC = 1.0 / SAMPLING_FPS
FRAMES_PER_CHILD = 12
EXPECTED_CHILD_COUNT = 3
EXPECTED_OVERLAP_COUNT = 2
SHARED_FRAMES_PER_OVERLAP = 6

EXPECTED_CHILDREN = (("C0", 0.0, 24.0), ("C1", 12.0, 36.0), ("C2", 24.0, 48.0))
EXPECTED_OVERLAPS = (("R-O1", "C0", "C1", 12.0, 24.0),
                     ("R-O2", "C1", "C2", 24.0, 36.0))
CHILD_IDS = tuple(row[0] for row in EXPECTED_CHILDREN)

# 두 overlap 모두 frame audit 대상으로 사전등록됐다 (사후 확장·축소 금지)
AUDIT_OVERLAPS = tuple(row[0] for row in EXPECTED_OVERLAPS)
FRAME_AUDIT_EXPANSION_ALLOWED = False

# ── W00에서 그대로 가져오는 동결값 (창 기하만 빠진다) ─────────────────
GEOMETRY_KEYS = ("window_sec", "frames_per_window")
FROZEN_FROM_W00 = {key: value
                   for key, value in sh.FROZEN_FROM_SHORT_WINDOW.items()
                   if key not in GEOMETRY_KEYS}
DECLARED_GEOMETRY = {"window_sec": CHILD_SEC,
                     "frames_per_window": FRAMES_PER_CHILD}
ARCHITECTURE_CHANGE = {
    "from": "48-sec local window / 24 frames",
    "to": "24-sec local windows / 12-sec overlap / 12 frames",
    "sole_recovery_mechanism": True,
    "not_a_causal_claim": ("48초가 degeneracy의 원인이라는 주장을 하지 않는다 — "
                           "recovery efficacy만 잰다"),
}

# 원본 W00 산출물 (읽기 전용 · 무변경 확인용 · repro 사건에서 동결된 해시를 쓴다)
ORIGINAL_RECORD = rp.ORIGINAL_RECORD
ORIGINAL_RAW = rp.ORIGINAL_RAW
ORIGINAL_RECORD_SHA256 = rp.ORIGINAL_RECORD_SHA256
ORIGINAL_RAW_SHA256 = rp.ORIGINAL_RAW_SHA256

RETRY_ALLOWED = False
RAW_SALVAGE_ALLOWED = False
TOKEN_CAP_INCREASE_APPROVED = False
ORIGINAL_W00_MAY_BE_REVALIDATED = False
SHADOW_V1_RETROACTIVE_REPAIR_ALLOWED = False
MAPPING_REVEAL_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False
EVENT_MAP_PRODUCTION_APPROVED = False
STITCHING_PRODUCTION_ALLOWED = False
FULL_C01_RESUBDIVISION_ALLOWED = False

# ── 판정 어휘 ───────────────────────────────────────────────────────
CHILD_VALID = sh.WINDOW_VALID
CHILD_INVALID = sh.WINDOW_INVALID

RECOVERY_PASS = "SUBDIVISION_TECHNICAL_RECOVERY_PASS"
RECOVERY_FAIL = "SUBDIVISION_RECOVERY_FAIL"
INCONCLUSIVE = "INCONCLUSIVE"
RECOVERY_VERDICTS = (RECOVERY_PASS, RECOVERY_FAIL, INCONCLUSIVE)
SEMANTIC_REVIEW_PENDING = "SEMANTIC_REVIEW_PENDING"

RUNTIME_FAILURE = "RUNTIME_FAILURE"
CONFIG_MISMATCH = "CONFIG_MISMATCH"
CHILD_COUNT_MISMATCH = "CHILD_COUNT_MISMATCH"
REPRESENTATION_DEGENERACY = "EVENT_REPRESENTATION_DEGENERACY"
NO_PARSE_RECORD = "NO_PARSE_RECORD"

# model output 실패 = FAIL. 그 밖의 사유는 측정 불가(blocker)로 본다.
FAIL_REASONS = ("PARSE_FAILURE", "CONTRACT_VIOLATION", "NO_EVENT",
                "TRUNCATED_AT_CAP", "OUTPUT_LANGUAGE_CONTRACT_FAILURE",
                REPRESENTATION_DEGENERACY)
BLOCKER_REASONS = (sh.PROVENANCE_MISMATCH, sh.GRID_MISMATCH,
                   sh.FRAME_COUNT_MISMATCH, sh.RAW_NOT_PERSISTED,
                   sh.SHARED_FRAME_IDENTITY_FAILURE, RUNTIME_FAILURE,
                   CONFIG_MISMATCH, CHILD_COUNT_MISMATCH, NO_PARSE_RECORD)

# reviewer 전용 (executor는 채우지 않는다)
SEMANTIC_VERDICTS = sh.SEMANTIC_VERDICTS
SUPPORT_VERDICTS = sh.SUPPORT_VERDICTS

ALLOWED_MAX_CONCLUSION = (
    "The deterministic W00 degeneracy observed at 48 seconds was not "
    "reproduced in any of the three preregistered 24-second recovery children "
    "under the frozen inference configuration.")
FORBIDDEN_CONCLUSIONS = (
    "24초 semantic stability proven", "24초 production approved",
    "0.5fps sufficient", "Event extraction solved",
    "48초가 degeneracy의 원인이다", "24초가 universally safe하다",
    "24초 전체 architecture 불가능", "original W00이 복구됐다",
    "SHADOW_V1이 복구됐다")

PRIOR_STATE = {
    "WVR_EVENT_EXTRACTION_SHADOW_V1": "CLOSED / INCONCLUSIVE",
    "WVR_W00_DEGENERACY_FORENSIC_V1": "CLOSED / MODEL_OUTPUT_DEGENERACY",
    "WVR_W00_DEGENERACY_REPRO_V1": "CLOSED / REPRODUCIBLE",
    "original_W00": "WINDOW_INVALID (유지 · 소급 VALID 금지)",
}

NORMATIVE_AUTHORITY = (
    "WVR_W00_SUBDIVISION_RECOVERY_V1 preregistration",
    "frozen prompt/model/runtime configuration",
    "raw execution artifacts",
    "prior W00 forensic/repro results",
    "PROJECT_OVERVIEW.md",
)

BRANCHES = {
    "PASS + semantic overlap stable":
        "reviewer가 hierarchical fallback architecture를 검토",
    "PASS + semantic divergence":
        "shorter context가 technical loop는 풀고 representation 안정성은 못 푼 것",
    "RECOVERY FAIL":
        "24초 subdivision도 현행 prompt/runtime에서 recovery 불충분",
    "INCONCLUSIVE": "measurement/provenance repair",
}
BRANCH_EXECUTION_ALLOWED = False


class SubdivisionError(RuntimeError):
    """subdivision 계약 위반."""


def children() -> list:
    """parent [0,48)를 24초 창 · 12초 stride로 분해한다. 반열린 구간."""
    rows, start, index = [], PARENT_START_SEC, 0
    while start + CHILD_SEC <= PARENT_END_SEC + 1e-9:
        rows.append({"child_id": "C%d" % index, "index": index,
                     "start_sec": round(start, 3),
                     "end_sec": round(start + CHILD_SEC, 3)})
        index += 1
        start = round(start + STRIDE_SEC, 3)
    if len(rows) != EXPECTED_CHILD_COUNT:
        raise SubdivisionError("child 개수가 %d가 아니다: %d"
                               % (EXPECTED_CHILD_COUNT, len(rows)))
    observed = tuple((row["child_id"], row["start_sec"], row["end_sec"])
                     for row in rows)
    if observed != EXPECTED_CHILDREN:
        raise SubdivisionError("child 일정이 사전등록과 다르다: %r" % (observed,))
    return rows


def child_by_id(child_id: str) -> dict:
    for row in children():
        if row["child_id"] == child_id:
            return row
    raise SubdivisionError("모르는 child: %r" % child_id)


def parent_window() -> dict:
    """원본 실패 창 W00 [0,48) — SHADOW_V1 일정에서 가져온다."""
    window = sh.window_by_id(PARENT_WINDOW_ID)
    if (window["start_sec"], window["end_sec"]) != (PARENT_START_SEC,
                                                    PARENT_END_SEC):
        raise SubdivisionError("parent 창이 [0,48)이 아니다: %r" % (window,))
    return window


def frame_times(child: dict) -> tuple:
    """child 안 0.5fps 격자 12개. 마지막은 start+22이고 창을 넘지 않는다."""
    start = float(child["start_sec"])
    stamps = tuple(round(start + STEP_SEC * i, 3)
                   for i in range(FRAMES_PER_CHILD))
    if stamps[-1] >= float(child["end_sec"]):
        raise SubdivisionError("프레임이 child를 벗어난다: %r" % (stamps[-1],))
    return stamps


def coverage(rows=None) -> dict:
    """세 child가 parent [0,48)를 빈틈없이 덮는지.

    rows를 주면 그 목록으로 계산한다(테스트가 빈틈 있는 배치를 넣어 확인한다).
    """
    rows = sorted(rows if rows is not None else children(),
                  key=lambda row: row["start_sec"])
    gaps = []
    cursor = PARENT_START_SEC
    for row in rows:
        if row["start_sec"] > cursor + 1e-9:
            gaps.append([round(cursor, 3), row["start_sec"]])
        cursor = max(cursor, row["end_sec"])
    if cursor < PARENT_END_SEC - 1e-9:
        gaps.append([round(cursor, 3), PARENT_END_SEC])
    return {"parent": [PARENT_START_SEC, PARENT_END_SEC],
            "union": [rows[0]["start_sec"], round(cursor, 3)],
            "gaps": gaps, "covered": not gaps
            and rows[0]["start_sec"] == PARENT_START_SEC
            and round(cursor, 3) == PARENT_END_SEC}


def assert_coverage(rows=None) -> dict:
    row = coverage(rows)
    if not row["covered"]:
        raise SubdivisionError("parent coverage가 깨졌다: %r" % row)
    return row


def overlaps() -> list:
    """인접 child 쌍 2개와 공유 구간."""
    rows, out = children(), []
    for index in range(len(rows) - 1):
        earlier, later = rows[index], rows[index + 1]
        low = max(earlier["start_sec"], later["start_sec"])
        high = min(earlier["end_sec"], later["end_sec"])
        if round(high - low, 6) != OVERLAP_SEC:
            raise SubdivisionError("겹침이 %.1f초가 아니다: %r"
                                   % (OVERLAP_SEC, (low, high)))
        out.append({"overlap_id": "R-O%d" % (index + 1),
                    "earlier": earlier["child_id"],
                    "later": later["child_id"],
                    "start_sec": low, "end_sec": high})
    if len(out) != EXPECTED_OVERLAP_COUNT:
        raise SubdivisionError("겹침 개수가 %d가 아니다: %d"
                               % (EXPECTED_OVERLAP_COUNT, len(out)))
    observed = tuple((row["overlap_id"], row["earlier"], row["later"],
                      row["start_sec"], row["end_sec"]) for row in out)
    if observed != EXPECTED_OVERLAPS:
        raise SubdivisionError("겹침 일정이 사전등록과 다르다: %r" % (observed,))
    return out


def overlap_by_id(overlap_id: str) -> dict:
    for row in overlaps():
        if row["overlap_id"] == overlap_id:
            return row
    raise SubdivisionError("모르는 겹침: %r" % overlap_id)


def shared_times(overlap: dict) -> tuple:
    """겹침 구간 안 공유 시각 6개 — 양쪽 child 격자에 모두 있어야 한다."""
    earlier = set(frame_times(child_by_id(overlap["earlier"])))
    later = set(frame_times(child_by_id(overlap["later"])))
    shared = tuple(sorted(earlier & later))
    if len(shared) != SHARED_FRAMES_PER_OVERLAP:
        raise SubdivisionError("공유 프레임이 %d개가 아니다: %d"
                               % (SHARED_FRAMES_PER_OVERLAP, len(shared)))
    if any(time < overlap["start_sec"] or time >= overlap["end_sec"]
           for time in shared):
        raise SubdivisionError("공유 프레임이 겹침 구간 밖이다: %r" % (shared,))
    return shared


def audit_times() -> dict:
    """사전등록된 두 overlap의 공유 시각 (확장 금지)."""
    if FRAME_AUDIT_EXPANSION_ALLOWED:
        raise SubdivisionError("audit overlap 확장은 금지돼 있다")
    return {overlap_id: list(shared_times(overlap_by_id(overlap_id)))
            for overlap_id in AUDIT_OVERLAPS}


def inference_config_change(requested: dict) -> dict:
    """창 기하 외에 inference 설정이 바뀌지 않았는지 확인한다.

    창 길이 변경은 이 사건이 시험하는 architecture change이므로 별도 필드로 적고,
    나머지 동결값 중 하나라도 다르면 `DETECTED`다.
    """
    differences = {}
    for key, value in FROZEN_FROM_W00.items():
        if key not in requested:
            continue
        if requested[key] != value:
            differences[key] = {"expected": value, "observed": requested[key]}
    geometry = {key: requested.get(key) for key in GEOMETRY_KEYS
                if key in requested}
    declared = all(requested.get(key) == value
                   for key, value in DECLARED_GEOMETRY.items()
                   if key in requested) and bool(geometry)
    return {
        "inference_config_change": "NONE" if not differences else "DETECTED",
        "differences": differences,
        "architecture_change": ARCHITECTURE_CHANGE,
        "declared_geometry": DECLARED_GEOMETRY,
        "observed_geometry": geometry,
        "geometry_as_declared": declared,
        "not_an_ablation_of_content_or_prompt": True,
    }


def dedup(reasons) -> list:
    out = []
    for reason in reasons:
        if reason not in out:
            out.append(reason)
    return out


def child_validity(record: dict, video_sha256: str) -> dict:
    """SHADOW_V1 기술 검증 어휘를 그대로 쓰고 child 기하만 바꾼다."""
    import wvr_density_v2 as v2

    base = v2.arm_validity(record)
    reasons = list(base["reasons"])
    if record.get("arm_status") == RUNTIME_FAILURE:
        reasons.append(RUNTIME_FAILURE)
    metrics = record.get("metrics") or {}
    if metrics.get("delivered_frame_count") != FRAMES_PER_CHILD:
        reasons.append(sh.FRAME_COUNT_MISMATCH)
    expected = list(frame_times(record["child"]))
    if [round(float(time), 3) for time in
            (record.get("frame_times") or [])] != expected:
        reasons.append(sh.GRID_MISMATCH)
    if not record.get("raw_persisted"):
        reasons.append(sh.RAW_NOT_PERSISTED)
    if record.get("video_sha256") != video_sha256:
        reasons.append(sh.PROVENANCE_MISMATCH)
    if (record.get("representation") or {}).get("degenerate"):
        reasons.append(REPRESENTATION_DEGENERACY)
    reasons = dedup(reasons)
    return {"valid": not reasons, "reasons": reasons,
            "status": CHILD_VALID if not reasons else CHILD_INVALID,
            "language": base["language"],
            "blockers": [reason for reason in reasons
                         if reason not in FAIL_REASONS],
            "output_failures": [reason for reason in reasons
                                if reason in FAIL_REASONS]}


def shared_frame_identity(frame_tables: dict) -> list:
    """두 child가 같은 공유 시각에서 같은 픽셀 해시를 먹었는지."""
    rows = []
    for overlap in overlaps():
        shared = list(shared_times(overlap))
        earlier = frame_tables.get(overlap["earlier"]) or {}
        later = frame_tables.get(overlap["later"]) or {}
        missing = [time for time in shared
                   if time not in earlier or time not in later]
        mismatched = [time for time in shared
                      if time in earlier and time in later
                      and earlier[time] != later[time]]
        rows.append({"overlap_id": overlap["overlap_id"],
                     "start_sec": overlap["start_sec"],
                     "end_sec": overlap["end_sec"],
                     "shared_expected": SHARED_FRAMES_PER_OVERLAP,
                     "shared_observed": len(shared) - len(missing),
                     "missing_times": missing,
                     "pixel_hash_mismatches": mismatched,
                     "identity_ok": not missing and not mismatched})
    return rows


def lineage_report(frame_tables: dict, reference: dict) -> dict:
    """child가 먹인 픽셀이 기존 C01 계보(frame bank · 원본 W00)와 같은지.

    reference는 {시각: 픽셀해시} 표다. 대조 대상이 없으면 checked=0으로 남기고
    일치를 주장하지 않는다.
    """
    checked, mismatches, uncovered = 0, [], []
    for child_id, table in sorted(frame_tables.items()):
        for time, digest in sorted(table.items()):
            if time not in reference:
                uncovered.append({"child_id": child_id, "time_sec": time})
                continue
            checked += 1
            if reference[time] != digest:
                mismatches.append({"child_id": child_id, "time_sec": time,
                                   "reference_sha256": reference[time],
                                   "child_sha256": digest})
    return {"checked": checked, "mismatches": mismatches,
            "uncovered": uncovered,
            "identity_ok": not mismatches and checked > 0,
            "note": ("대조 대상이 없으면 checked=0이고 일치를 주장하지 않는다")}


def recovery_verdict(child_rows, identity_rows, extra_blockers=()) -> dict:
    """사전등록 §9 게이트. 우선순위 INCONCLUSIVE → FAIL → PASS."""
    rows = list(child_rows)
    blockers = list(extra_blockers)
    if len(rows) != EXPECTED_CHILD_COUNT:
        blockers.append(CHILD_COUNT_MISMATCH)
    if [row for row in identity_rows if not row.get("identity_ok")]:
        blockers.append(sh.SHARED_FRAME_IDENTITY_FAILURE)
    for row in rows:
        blockers.extend(row.get("blockers") or [])
    blockers = dedup(blockers)
    invalid = [row for row in rows if not row.get("valid")]
    if blockers:
        verdict, reason = INCONCLUSIVE, "MEASUREMENT_BLOCKED"
    elif invalid:
        verdict, reason = RECOVERY_FAIL, "CHILD_TECHNICAL_INVALID"
    else:
        verdict, reason = RECOVERY_PASS, "ALL_CHILDREN_VALID"
    return {
        "recovery_verdict": verdict, "reason": reason,
        "valid_child_count": len(rows) - len(invalid),
        "expected_child_count": EXPECTED_CHILD_COUNT,
        "invalid_children": [row.get("child_id") for row in invalid],
        "blockers": blockers,
        "packet_generation_allowed": verdict == RECOVERY_PASS,
        "event_status": ("%s + %s" % (RECOVERY_PASS, SEMANTIC_REVIEW_PENDING)
                         if verdict == RECOVERY_PASS else verdict),
        "semantic_verdict": None,
        "semantic_verdict_by_executor": SEMANTIC_VERDICT_BY_EXECUTOR,
        "allowed_max_conclusion": ALLOWED_MAX_CONCLUSION,
        "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS),
    }


def parent_comparison(parent_row: dict, child_rows) -> dict:
    """48초 W00과 24초 child의 구조적 비교. 우열 주장을 만들지 않는다."""
    return {
        "parent": parent_row,
        "children": list(child_rows),
        "axis": ("구조 항목만 비교한다 — generated tokens · cap hit · "
                 "완성 object · unique signature · zero-duration · JSON 완결"),
        "semantic_superiority_claimed": False,
        "original_parent_status": PRIOR_STATE["original_W00"],
        "shadow_v1_retroactive_repair_allowed":
            SHADOW_V1_RETROACTIVE_REPAIR_ALLOWED,
    }


def blind_label(overlap_id: str, role: str, prereg_sha: str) -> str:
    """earlier·later를 Arm A/B로 가린다 — prereg SHA와 overlap id의 결정적 함수.

    사전등록 §12에서 동결된 절차다. 결과를 보고 사람이 고르지 않고, 실행 후
    바뀌지 않는다(같은 입력 → 같은 출력).
    """
    if role not in ("earlier", "later"):
        raise SubdivisionError("모르는 role: %r" % role)
    if not prereg_sha:
        raise SubdivisionError("prereg SHA가 비어 있다")
    digest = hashlib.sha256(("%s|%s" % (prereg_sha, overlap_id))
                            .encode("utf-8"))
    flip = digest.digest()[0] & 1
    if role == "earlier":
        return "B" if flip else "A"
    return "A" if flip else "B"


def original_unchanged(record_sha: str, raw_sha: str) -> dict:
    """원본 W00 산출물이 그대로인지 (repro 사건에서 동결된 해시 사용)."""
    row = rp.original_unchanged(record_sha, raw_sha)
    return {**row, "may_be_revalidated": ORIGINAL_W00_MAY_BE_REVALIDATED}
