"""WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1_2026-09-09.md`

```
질문     24초에서도 결정적으로 실패한 C0 [0,24)를 12초/6초 overlap child로 한 단계 더
        세분하면 frozen prompt·runtime·표집을 유지한 채 technically valid해지는가
측정     recursive fallback의 최소 feasibility 하나
변경     창 길이 12초 · overlap 6초 · 6프레임. 그 밖은 전부 C0와 동일
금지     C1·C2 재실행 · token cap 상향 · prompt·schema 수정 · retry · raw salvage ·
        6초로의 자동 재귀 · 원본 소급 VALID 전환 · semantic 판정 · mapping reveal
```
"""
import hashlib

import wvr_shadow_v1 as sh
import wvr_subdivision_v1 as sd

EVENT = "WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1"
ARTIFACT_TAG = "recur_v1"

# ── 분해 일정 (결과 보기 전 동결) ────────────────────────────────────
PARENT_CHILD_ID = "C0"
PARENT_START_SEC = 0.0
PARENT_END_SEC = 24.0
CHILD_SEC = 12.0
STRIDE_SEC = 6.0
OVERLAP_SEC = 6.0
SAMPLING_FPS = sd.SAMPLING_FPS
STEP_SEC = 1.0 / SAMPLING_FPS
FRAMES_PER_CHILD = 6
EXPECTED_CHILD_COUNT = 3
EXPECTED_OVERLAP_COUNT = 2
SHARED_FRAMES_PER_OVERLAP = 3
SUBDIVISION_DEPTH = 2                       # W00(48) → C0(24) → D*(12)

EXPECTED_CHILDREN = (("D0", 0.0, 12.0), ("D1", 6.0, 18.0), ("D2", 12.0, 24.0))
EXPECTED_OVERLAPS = (("RR-O1", "D0", "D1", 6.0, 12.0),
                     ("RR-O2", "D1", "D2", 12.0, 18.0))
CHILD_IDS = tuple(row[0] for row in EXPECTED_CHILDREN)

AUDIT_OVERLAPS = tuple(row[0] for row in EXPECTED_OVERLAPS)
FRAME_AUDIT_EXPANSION_ALLOWED = False

# ── C0에서 그대로 가져오는 동결값 (창 기하만 빠진다) ──────────────────
GEOMETRY_KEYS = sd.GEOMETRY_KEYS
FROZEN_FROM_C0 = dict(sd.FROZEN_FROM_W00)
DECLARED_GEOMETRY = {"window_sec": CHILD_SEC,
                     "frames_per_window": FRAMES_PER_CHILD}
ARCHITECTURE_CHANGE = {
    "from": "24-sec local window / 12 frames (failing C0)",
    "to": "12-sec local windows / 6-sec overlap / 6 frames",
    "scope": "실패 child C0 [0,24) 하나만 — C1·C2는 재실행하지 않는다",
    "sole_recovery_mechanism": True,
    "not_a_causal_claim": ("12초가 안전하다·0초 boundary가 원인이다·24초가 원인이다는 "
                           "주장을 하지 않는다 — recovery efficacy만 잰다"),
}

# ── 읽기 전용 선행 산출물 (무변경 확인용 · 사전등록 §0에 기재) ────────
PARENT_RECORD = "subdiv_v1_C0.json"
PARENT_RAW = "subdiv_v1_C0_raw.txt"
FROZEN_ARTIFACTS = {
    "subdiv_v1_C0.json":
        "7925172a83d3304730e6b21509bdc0c70dbe78ae0e5433e0809a7e074471d0f6",
    "subdiv_v1_C0_raw.txt":
        "7460a5b61821e41b15dd0281aa15580a2ac7752dab48be2bbf809f1d193105d0",
    "subdiv_v1_C1.json":
        "44b7f96c1f23a0760f6cc8fa975d058b86d813878c75898136bd368979d75f11",
    "subdiv_v1_C1_raw.txt":
        "9316f9f62b519ef0cc8a99a827fa71ed153b5efea3a673e5d53b2d084392f117",
    "subdiv_v1_C2.json":
        "cb77b4b283f988d150efcb1c780d4cc1c8c5ff6d7ce566517ca35b17cc68f126",
    "subdiv_v1_C2_raw.txt":
        "70815aeee2408bd174d0a031a08200bf9e6b12fdff6d46a9c8a0ec36ef453b10",
    "shadow_v1_W00.json": sd.ORIGINAL_RECORD_SHA256,
    "shadow_v1_W00_raw.txt": sd.ORIGINAL_RAW_SHA256,
}

RETRY_ALLOWED = False
RAW_SALVAGE_ALLOWED = False
TOKEN_CAP_INCREASE_APPROVED = False
DEEPER_SUBDIVISION_ALLOWED = False           # 6초/3초 자동 진행 금지
C1_C2_RERUN_ALLOWED = False
PARENT_MAY_BE_REVALIDATED = False            # C0·W00 소급 VALID 금지
SHADOW_V1_RETROACTIVE_REPAIR_ALLOWED = False
MAPPING_REVEAL_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False
FALLBACK_POLICY_ADOPTION_ALLOWED = False
EVENT_MAP_PRODUCTION_APPROVED = False

# ── 판정 어휘 ───────────────────────────────────────────────────────
CHILD_VALID = sh.WINDOW_VALID
CHILD_INVALID = sh.WINDOW_INVALID

RECOVERY_PASS = "RECURSIVE_SUBDIVISION_TECHNICAL_PASS"
RECOVERY_FAIL = "RECURSIVE_SUBDIVISION_RECOVERY_FAIL"
INCONCLUSIVE = "INCONCLUSIVE"
RECOVERY_VERDICTS = (RECOVERY_PASS, RECOVERY_FAIL, INCONCLUSIVE)
SEMANTIC_REVIEW_PENDING = "SEMANTIC_REVIEW_PENDING"

RUNTIME_FAILURE = sd.RUNTIME_FAILURE
CONFIG_MISMATCH = sd.CONFIG_MISMATCH
CHILD_COUNT_MISMATCH = sd.CHILD_COUNT_MISMATCH
REPRESENTATION_DEGENERACY = sd.REPRESENTATION_DEGENERACY
LINEAGE_PIXEL_MISMATCH = "LINEAGE_PIXEL_MISMATCH"
PARENT_ARTIFACT_CHANGED = "PARENT_ARTIFACT_CHANGED"

FAIL_REASONS = sd.FAIL_REASONS
BLOCKER_REASONS = tuple(sd.BLOCKER_REASONS) + (LINEAGE_PIXEL_MISMATCH,
                                               PARENT_ARTIFACT_CHANGED)

SEMANTIC_VERDICTS = sh.SEMANTIC_VERDICTS
SUPPORT_VERDICTS = sh.SUPPORT_VERDICTS

ALLOWED_MAX_CONCLUSION = (
    "The known failing C0 [0,24) window was technically recoverable through "
    "one additional preregistered 12-second overlapping subdivision level "
    "under the frozen inference configuration.")
FORBIDDEN_CONCLUSIONS = (
    "12초 semantic stability proven", "12초 production approved",
    "hierarchical fallback production approved", "0.5fps sufficient",
    "Event extraction solved", "12초가 universally safe하다",
    "0초 boundary가 원인이다", "24초가 원인이다", "영상 내용이 원인이다",
    "prompt가 원인이다", "모든 더 짧은 window가 실패한다",
    "C0가 복구됐다", "SHADOW_V1이 복구됐다")

PRIOR_STATE = {
    "WVR_EVENT_EXTRACTION_SHADOW_V1": "CLOSED / INCONCLUSIVE",
    "WVR_W00_DEGENERACY_FORENSIC_V1": "CLOSED / MODEL_OUTPUT_DEGENERACY",
    "WVR_W00_DEGENERACY_REPRO_V1": "CLOSED / REPRODUCIBLE",
    "WVR_W00_SUBDIVISION_RECOVERY_V1": "CLOSED / SUBDIVISION_RECOVERY_FAIL",
    "C0": "WINDOW_INVALID (유지 · 소급 VALID 금지)",
    "C1": "WINDOW_VALID (재실행하지 않는다)",
    "C2": "WINDOW_VALID (재실행하지 않는다)",
}

# 기존 valid output과의 관계 (사전등록 §11)
CONTEXT_RELATION = {
    "C1_overlaps_D2": "C1 [12,36)과 D2 [12,24)는 시각을 일부 공유한다",
    "equivalence": "context가 다르므로 equivalent truth로 취급하지 않는다",
    "when_comparable": "기술 recovery PASS일 때만 reviewer packet에서 본다",
    "executor_judgment": False,
}

NORMATIVE_AUTHORITY = (
    "WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1 preregistration",
    "frozen prompt/model/runtime configuration",
    "raw execution artifacts",
    "prior W00 forensic/repro/subdivision results",
    "PROJECT_OVERVIEW.md",
)

STOP_RULE = ("12초에서 실패하면 STOP — 6초 window / 3초 overlap으로 자동 진행하지 "
             "않는다. recursive depth를 사후에 늘리지 않는다.")


class RecursiveError(RuntimeError):
    """recursive subdivision 계약 위반."""


def children() -> list:
    """실패 parent C0 [0,24)를 12초 창 · 6초 stride로 분해한다. 반열린 구간."""
    rows, start, index = [], PARENT_START_SEC, 0
    while start + CHILD_SEC <= PARENT_END_SEC + 1e-9:
        rows.append({"child_id": "D%d" % index, "index": index,
                     "start_sec": round(start, 3),
                     "end_sec": round(start + CHILD_SEC, 3)})
        index += 1
        start = round(start + STRIDE_SEC, 3)
    if len(rows) != EXPECTED_CHILD_COUNT:
        raise RecursiveError("child 개수가 %d가 아니다: %d"
                             % (EXPECTED_CHILD_COUNT, len(rows)))
    observed = tuple((row["child_id"], row["start_sec"], row["end_sec"])
                     for row in rows)
    if observed != EXPECTED_CHILDREN:
        raise RecursiveError("child 일정이 사전등록과 다르다: %r" % (observed,))
    return rows


def child_by_id(child_id: str) -> dict:
    for row in children():
        if row["child_id"] == child_id:
            return row
    raise RecursiveError("모르는 child: %r" % child_id)


def parent_child() -> dict:
    """실패한 24초 parent C0 — SUBDIVISION 일정에서 가져온다."""
    parent = sd.child_by_id(PARENT_CHILD_ID)
    if (parent["start_sec"], parent["end_sec"]) != (PARENT_START_SEC,
                                                    PARENT_END_SEC):
        raise RecursiveError("parent가 [0,24)이 아니다: %r" % (parent,))
    return parent


def grandparent_window() -> dict:
    """원본 48초 실패 창 W00 — 깊이 비교용(수정하지 않는다)."""
    return sd.parent_window()


def frame_times(child: dict) -> tuple:
    """child 안 0.5fps 격자 6개. 마지막은 start+10이고 창을 넘지 않는다."""
    start = float(child["start_sec"])
    stamps = tuple(round(start + STEP_SEC * i, 3)
                   for i in range(FRAMES_PER_CHILD))
    if stamps[-1] >= float(child["end_sec"]):
        raise RecursiveError("프레임이 child를 벗어난다: %r" % (stamps[-1],))
    return stamps


def coverage(rows=None) -> dict:
    """세 child가 parent C0 [0,24)를 빈틈없이 덮는지.

    rows를 주면 그 목록으로 계산한다(테스트가 빈틈 있는 배치를 넣어 확인한다).
    """
    rows = sorted(rows if rows is not None else children(),
                  key=lambda row: row["start_sec"])
    gaps, cursor = [], PARENT_START_SEC
    for row in rows:
        if row["start_sec"] > cursor + 1e-9:
            gaps.append([round(cursor, 3), row["start_sec"]])
        cursor = max(cursor, row["end_sec"])
    if cursor < PARENT_END_SEC - 1e-9:
        gaps.append([round(cursor, 3), PARENT_END_SEC])
    return {"parent": [PARENT_START_SEC, PARENT_END_SEC],
            "union": [rows[0]["start_sec"], round(cursor, 3)],
            "gaps": gaps,
            "covered": not gaps
            and rows[0]["start_sec"] == PARENT_START_SEC
            and round(cursor, 3) == PARENT_END_SEC}


def assert_coverage(rows=None) -> dict:
    row = coverage(rows)
    if not row["covered"]:
        raise RecursiveError("parent coverage가 깨졌다: %r" % row)
    return row


def overlaps() -> list:
    """인접 child 쌍 2개와 공유 구간."""
    rows, out = children(), []
    for index in range(len(rows) - 1):
        earlier, later = rows[index], rows[index + 1]
        low = max(earlier["start_sec"], later["start_sec"])
        high = min(earlier["end_sec"], later["end_sec"])
        if round(high - low, 6) != OVERLAP_SEC:
            raise RecursiveError("겹침이 %.1f초가 아니다: %r"
                                 % (OVERLAP_SEC, (low, high)))
        out.append({"overlap_id": "RR-O%d" % (index + 1),
                    "earlier": earlier["child_id"],
                    "later": later["child_id"],
                    "start_sec": low, "end_sec": high})
    if len(out) != EXPECTED_OVERLAP_COUNT:
        raise RecursiveError("겹침 개수가 %d가 아니다: %d"
                             % (EXPECTED_OVERLAP_COUNT, len(out)))
    observed = tuple((row["overlap_id"], row["earlier"], row["later"],
                      row["start_sec"], row["end_sec"]) for row in out)
    if observed != EXPECTED_OVERLAPS:
        raise RecursiveError("겹침 일정이 사전등록과 다르다: %r" % (observed,))
    return out


def overlap_by_id(overlap_id: str) -> dict:
    for row in overlaps():
        if row["overlap_id"] == overlap_id:
            return row
    raise RecursiveError("모르는 겹침: %r" % overlap_id)


def shared_times(overlap: dict) -> tuple:
    """겹침 구간 안 공유 시각 3개 — 양쪽 child 격자에 모두 있어야 한다."""
    earlier = set(frame_times(child_by_id(overlap["earlier"])))
    later = set(frame_times(child_by_id(overlap["later"])))
    shared = tuple(sorted(earlier & later))
    if len(shared) != SHARED_FRAMES_PER_OVERLAP:
        raise RecursiveError("공유 프레임이 %d개가 아니다: %d"
                             % (SHARED_FRAMES_PER_OVERLAP, len(shared)))
    if any(time < overlap["start_sec"] or time >= overlap["end_sec"]
           for time in shared):
        raise RecursiveError("공유 프레임이 겹침 구간 밖이다: %r" % (shared,))
    return shared


def audit_times() -> dict:
    """사전등록된 두 overlap의 공유 시각 (확장 금지)."""
    if FRAME_AUDIT_EXPANSION_ALLOWED:
        raise RecursiveError("audit overlap 확장은 금지돼 있다")
    return {overlap_id: list(shared_times(overlap_by_id(overlap_id)))
            for overlap_id in AUDIT_OVERLAPS}


def inference_config_change(requested: dict) -> dict:
    """창 기하 외에 inference 설정이 바뀌지 않았는지 확인한다."""
    differences = {}
    for key, value in FROZEN_FROM_C0.items():
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
        "subdivision_depth": SUBDIVISION_DEPTH,
        "deeper_subdivision_allowed": DEEPER_SUBDIVISION_ALLOWED,
    }


def child_validity(record: dict, video_sha256: str) -> dict:
    """SHADOW/V2 기술 검증 어휘를 그대로 쓰고 child 기하만 바꾼다."""
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
    reasons = sd.dedup(reasons)
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
    """child가 먹인 픽셀이 기존 계보(C0 record · frame bank)와 같은지."""
    return sd.lineage_report(frame_tables, reference)


def frozen_artifacts_unchanged(observed: dict) -> dict:
    """C0·C1·C2·W00 산출물이 그대로인지. 하나라도 다르면 blocker다."""
    rows, changed, missing = {}, [], []
    for name, expected in sorted(FROZEN_ARTIFACTS.items()):
        digest = observed.get(name)
        if digest is None:
            missing.append(name)
            rows[name] = {"status": "MISSING", "expected": expected}
            continue
        same = digest == expected
        rows[name] = {"status": "OK" if same else "CHANGED",
                      "expected": expected, "observed": digest}
        if not same:
            changed.append(name)
    return {"unchanged": not changed and not missing, "checks": rows,
            "changed": changed, "missing": missing,
            "parent_status_retained": PRIOR_STATE["C0"],
            "c1_c2_rerun_allowed": C1_C2_RERUN_ALLOWED,
            "may_be_revalidated": PARENT_MAY_BE_REVALIDATED}


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
    blockers = sd.dedup(blockers)
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
        "stop_rule": STOP_RULE,
        "deeper_subdivision_allowed": DEEPER_SUBDIVISION_ALLOWED,
    }


def depth_comparison(grandparent: dict, parent: dict, child_rows) -> dict:
    """W00 [0,48) · C0 [0,24) · D0 [0,12) 구조 비교. 셋 다 0초에서 시작한다."""
    zero_start = [row for row in child_rows
                  if row.get("start_sec") == PARENT_START_SEC]
    return {
        "axis": ("generated tokens · cap hit · completed objects · "
                 "raw unique signatures · zero-duration · positive-duration · "
                 "JSON completion · degeneracy · raw hash"),
        "depth_0_w00_48s": grandparent,
        "depth_1_c0_24s": parent,
        "depth_2_children_12s": list(child_rows),
        "zero_start_children": [row.get("child_id") for row in zero_start],
        "claim": "실패가 어느 subdivision depth까지 지속되는지만 기록한다",
        "start_sec_zero_is_not_claimed_as_cause": True,
        "semantic_superiority_claimed": False,
        "context_relation": CONTEXT_RELATION,
    }


def blind_label(overlap_id: str, role: str, prereg_sha: str) -> str:
    """earlier·later를 Arm A/B로 가린다 — prereg SHA와 overlap id의 결정적 함수.

    사전등록 §13에서 동결된 절차다. 결과를 보고 사람이 고르지 않는다.
    """
    if role not in ("earlier", "later"):
        raise RecursiveError("모르는 role: %r" % role)
    if not prereg_sha:
        raise RecursiveError("prereg SHA가 비어 있다")
    digest = hashlib.sha256(("%s|%s" % (prereg_sha, overlap_id))
                            .encode("utf-8"))
    flip = digest.digest()[0] & 1
    if role == "earlier":
        return "B" if flip else "A"
    return "A" if flip else "B"
