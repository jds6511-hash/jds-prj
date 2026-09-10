"""WVR_W00_TRIGGER_ISOLATION_V1 계측기 (2026-09-10 · freeze).

사전등록: `docs/preregistration/WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md`

```
질문   동일한 W00 픽셀에서 나는 degeneracy가 prompt 시간값(P)·metadata
      frames_indices(M)·둘의 interaction에 따라 달라지는가
설계   2×2 · A(P0M0) B(P0M1) C(P1M0) D(P1M1) · SHIFT_SEC +120.0
불변   픽셀 24장 · prompt 문구 · schema · token cap · 표집 · 창 길이 ·
      duration · total_num_frames · fps · width/height · backend
조작   ① rendered prompt의 window 숫자값  ② VideoMetadata.frames_indices
금지   recovery 시도 · prompt 문구 수정 · retry · raw salvage · 메커니즘 단정
```
"""
import hashlib

import wvr_density_prompt_v2 as diag
import wvr_shadow_v1 as sh
import wvr_subdivision_v1 as sd

EVENT = "WVR_W00_TRIGGER_ISOLATION_V1"
ARTIFACT_TAG = "trigger_v1"

# ── 픽셀 원천 (4 arm 동일 · 바꾸지 않는다) ──────────────────────────
SOURCE_WINDOW_ID = "W00"
PIXEL_FRAME_COUNT = 24
SAMPLING_FPS = sd.SAMPLING_FPS

# ── 조작 (사전 고정) ───────────────────────────────────────────────
SHIFT_SEC = 120.0
PROMPT_MODES = ("P0", "P1")
METADATA_MODES = ("M0", "M1")
ARMS = (("A", "P0", "M0"), ("B", "P0", "M1"),
        ("C", "P1", "M0"), ("D", "P1", "M1"))
ARM_IDS = tuple(row[0] for row in ARMS)
EXPECTED_ARM_COUNT = 4

# 4 arm 공통으로 고정하는 metadata (shift 대상 아님)
METADATA_FIXED_FIELDS = ("total_num_frames", "fps", "width", "height",
                         "duration", "video_backend")
METADATA_MANIPULATED_FIELD = "frames_indices"

# ── 읽기 전용 선행 산출물 ───────────────────────────────────────────
ORIGINAL_RECORD = sd.ORIGINAL_RECORD                 # shadow_v1_W00.json
ORIGINAL_RAW = sd.ORIGINAL_RAW                       # shadow_v1_W00_raw.txt
FROZEN_ARTIFACTS = {
    "shadow_v1_W00.json": sd.ORIGINAL_RECORD_SHA256,
    "shadow_v1_W00_raw.txt": sd.ORIGINAL_RAW_SHA256,
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
}

RETRY_ALLOWED = False
RAW_SALVAGE_ALLOWED = False
TOKEN_CAP_INCREASE_APPROVED = False
PROMPT_TEXT_MUTATION_ALLOWED = False
SCHEMA_MUTATION_ALLOWED = False
VISUAL_CONTENT_MANIPULATION_ALLOWED = False          # 후속 사건으로 분리
RECOVERY_ATTEMPT_ALLOWED = False
PROCESSOR_MONKEY_PATCH_ALLOWED = False
ORIGINAL_W00_MAY_BE_REVALIDATED = False
MAPPING_REVEAL_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False

# ── 판정 어휘 (사전 동결) ──────────────────────────────────────────
ARM_VALID = sh.WINDOW_VALID
ARM_INVALID = sh.WINDOW_INVALID

PROMPT_TIME_EFFECT = "PROMPT_TIME_EFFECT_SUPPORTED"
METADATA_TIME_EFFECT = "METADATA_TIME_EFFECT_SUPPORTED"
JOINT_EFFECT = "JOINT_OR_INTERACTION_EFFECT_SUPPORTED"
NOT_SUPPORTED = "ABSOLUTE_TIME_EFFECT_NOT_SUPPORTED"
CONTROL_NOT_REPRODUCED = "CONTROL_NOT_REPRODUCED"
INCONCLUSIVE = "INCONCLUSIVE"
VERDICTS = (PROMPT_TIME_EFFECT, METADATA_TIME_EFFECT, JOINT_EFFECT,
            NOT_SUPPORTED, CONTROL_NOT_REPRODUCED, INCONCLUSIVE)

IMPLEMENTATION_BLOCKED = "IMPLEMENTATION_BLOCKED"
PIXEL_IDENTITY_FAILURE = "PIXEL_IDENTITY_FAILURE"
METADATA_MANIPULATION_FAILURE = "METADATA_MANIPULATION_FAILURE"
RENDERED_PROMPT_MISMATCH = "RENDERED_PROMPT_MISMATCH"
CONFIG_MISMATCH = sd.CONFIG_MISMATCH
ARM_COUNT_MISMATCH = "ARM_COUNT_MISMATCH"
PRIOR_ARTIFACT_CHANGED = "PRIOR_ARTIFACT_CHANGED"

FAIL_REASONS = sd.FAIL_REASONS
BLOCKER_REASONS = tuple(sd.BLOCKER_REASONS) + (
    IMPLEMENTATION_BLOCKED, PIXEL_IDENTITY_FAILURE,
    METADATA_MANIPULATION_FAILURE, RENDERED_PROMPT_MISMATCH,
    ARM_COUNT_MISMATCH, PRIOR_ARTIFACT_CHANGED)

AUDIT_ROLE = "AUDIT_DIAGNOSTIC_ONLY"

ALLOWED_CLAIM_TEMPLATE = (
    "이번 W00 pixel set에서 %s absolute-time encoding과 degeneracy 상태의 "
    "연관이 관찰됨")
FORBIDDEN_CONCLUSIONS = (
    "근본 원인을 규명했다", "Qwen 내부 메커니즘을 규명했다",
    "start_sec=0 bug를 증명했다", "metadata가 모델을 망가뜨린다",
    "prompt가 잘못됐다", "recovery 방법을 찾았다",
    "12초/24초 subdivision이 해결책이다")

PRIOR_STATE = {
    "WVR_EVENT_EXTRACTION_SHADOW_V1": "CLOSED / INCONCLUSIVE",
    "WVR_W00_DEGENERACY_FORENSIC_V1": "CLOSED / MODEL_OUTPUT_DEGENERACY",
    "WVR_W00_DEGENERACY_REPRO_V1": "CLOSED / REPRODUCIBLE",
    "WVR_W00_SUBDIVISION_RECOVERY_V1": "CLOSED / SUBDIVISION_RECOVERY_FAIL",
    "WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1": "CLOSED / RECOVERY_FAIL",
    "original_W00": "WINDOW_INVALID (유지 · 소급 VALID 금지)",
}

NORMATIVE_AUTHORITY = (
    "WVR_W00_TRIGGER_ISOLATION_V1 preregistration",
    "frozen model/prompt/runtime configuration",
    "raw execution artifacts",
    "prior forensic/repro/recovery results",
    "PROJECT_OVERVIEW.md",
)

EVENT_KIND = "behavioral trigger isolation (causal mechanism proof 아님)"


class TriggerError(RuntimeError):
    """trigger isolation 계약 위반."""


def source_window() -> dict:
    window = sh.window_by_id(SOURCE_WINDOW_ID)
    if (window["start_sec"], window["end_sec"]) != (0.0, 48.0):
        raise TriggerError("픽셀 원천 창이 [0,48)이 아니다: %r" % (window,))
    return window


def pixel_times() -> tuple:
    """4 arm 공통 픽셀 시각 0,2,…,46 (W00 격자 그대로)."""
    stamps = sh.frame_times(source_window())
    if len(stamps) != PIXEL_FRAME_COUNT:
        raise TriggerError("픽셀이 %d장이 아니다: %d"
                           % (PIXEL_FRAME_COUNT, len(stamps)))
    return stamps


def arms() -> list:
    rows = [{"arm_id": arm_id, "prompt_mode": prompt_mode,
             "metadata_mode": metadata_mode}
            for arm_id, prompt_mode, metadata_mode in ARMS]
    if len(rows) != EXPECTED_ARM_COUNT:
        raise TriggerError("arm이 %d개가 아니다: %d"
                           % (EXPECTED_ARM_COUNT, len(rows)))
    return rows


def arm_by_id(arm_id: str) -> dict:
    for row in arms():
        if row["arm_id"] == arm_id:
            return row
    raise TriggerError("모르는 arm: %r" % arm_id)


def prompt_window(prompt_mode: str) -> tuple:
    """P0 = 원본 창 · P1 = +SHIFT_SEC 창. 문구가 아니라 숫자값만 바뀐다."""
    window = source_window()
    if prompt_mode == "P0":
        return (window["start_sec"], window["end_sec"])
    if prompt_mode == "P1":
        return (round(window["start_sec"] + SHIFT_SEC, 3),
                round(window["end_sec"] + SHIFT_SEC, 3))
    raise TriggerError("모르는 prompt mode: %r" % prompt_mode)


def rendered_prompt(prompt_mode: str) -> str:
    start, end = prompt_window(prompt_mode)
    return diag.SAMPLING_DIAG_PROMPT_V2 % {"window_start": start,
                                           "window_end": end}


def prompt_template_hash() -> str:
    return diag.prompt_hash()


def rendered_prompt_hash(prompt_mode: str) -> str:
    return hashlib.sha256(
        rendered_prompt(prompt_mode).encode("utf-8")).hexdigest()


def metadata_times(metadata_mode: str) -> tuple:
    """M0 = 픽셀 시각 그대로 · M1 = +SHIFT_SEC. 픽셀은 바뀌지 않는다."""
    if metadata_mode == "M0":
        return pixel_times()
    if metadata_mode == "M1":
        return tuple(round(time + SHIFT_SEC, 3) for time in pixel_times())
    raise TriggerError("모르는 metadata mode: %r" % metadata_mode)


def frame_indices(metadata_mode: str, rate: float) -> tuple:
    """frames_indices = round(시각 × rate). rate는 4 arm 동일하다."""
    if not rate or rate <= 0:
        raise TriggerError("rate가 유효하지 않다: %r" % rate)
    return tuple(int(round(time * float(rate)))
                 for time in metadata_times(metadata_mode))


def arm_plan(arm_id: str, rate: float) -> dict:
    row = arm_by_id(arm_id)
    start, end = prompt_window(row["prompt_mode"])
    return {
        **row,
        "prompt_window": [start, end],
        "rendered_prompt": rendered_prompt(row["prompt_mode"]),
        "rendered_prompt_hash": rendered_prompt_hash(row["prompt_mode"]),
        "prompt_template_hash": prompt_template_hash(),
        "pixel_times": list(pixel_times()),
        "metadata_times": list(metadata_times(row["metadata_mode"])),
        "frames_indices": list(frame_indices(row["metadata_mode"], rate)),
        "shift_sec": SHIFT_SEC,
        "manipulated_metadata_field": METADATA_MANIPULATED_FIELD,
        "fixed_metadata_fields": list(METADATA_FIXED_FIELDS),
    }


def pixel_identity(observed, reference) -> dict:
    """arm이 실제로 먹인 픽셀 해시가 원본 W00의 해시와 같은지 (순서 포함)."""
    observed, reference = list(observed), list(reference)
    if not reference:
        return {"identical": False, "reason": "NO_REFERENCE",
                "checked": 0, "mismatched_positions": []}
    mismatched = [index for index in range(min(len(observed),
                                               len(reference)))
                  if observed[index] != reference[index]]
    same_length = len(observed) == len(reference) == PIXEL_FRAME_COUNT
    return {"identical": bool(same_length and not mismatched),
            "checked": min(len(observed), len(reference)),
            "expected_count": PIXEL_FRAME_COUNT,
            "observed_count": len(observed),
            "mismatched_positions": mismatched,
            "reason": "" if same_length and not mismatched
            else PIXEL_IDENTITY_FAILURE}


def arm_validity(record: dict, video_sha256: str) -> dict:
    """기존 기술 검증 어휘 그대로. 게이트를 바꾸지 않는다."""
    import wvr_density_v2 as v2

    base = v2.arm_validity(record)
    reasons = list(base["reasons"])
    if record.get("arm_status") == sd.RUNTIME_FAILURE:
        reasons.append(sd.RUNTIME_FAILURE)
    metrics = record.get("metrics") or {}
    if metrics.get("delivered_frame_count") != PIXEL_FRAME_COUNT:
        reasons.append(sh.FRAME_COUNT_MISMATCH)
    if [round(float(time), 3) for time in
            (record.get("pixel_times") or [])] != list(pixel_times()):
        reasons.append(sh.GRID_MISMATCH)
    if not record.get("raw_persisted"):
        reasons.append(sh.RAW_NOT_PERSISTED)
    if record.get("video_sha256") != video_sha256:
        reasons.append(sh.PROVENANCE_MISMATCH)
    if not (record.get("pixel_identity") or {}).get("identical"):
        reasons.append(PIXEL_IDENTITY_FAILURE)
    if (record.get("representation") or {}).get("degenerate"):
        reasons.append(sd.REPRESENTATION_DEGENERACY)
    reasons = sd.dedup(reasons)
    return {"valid": not reasons, "reasons": reasons,
            "status": ARM_VALID if not reasons else ARM_INVALID,
            "language": base["language"],
            "blockers": [reason for reason in reasons
                         if reason not in FAIL_REASONS],
            "output_failures": [reason for reason in reasons
                                if reason in FAIL_REASONS]}


def manipulation_audit(records: dict) -> dict:
    """조작이 실제로 걸렸고 그 밖은 동일한지 (사전등록 §9)."""
    missing = [arm_id for arm_id in ARM_IDS if arm_id not in records]
    if missing:
        return {"ok": False, "reasons": [ARM_COUNT_MISMATCH],
                "missing_arms": missing, "checks": {}}

    def field(arm_id, name):
        return (records[arm_id].get("metadata") or {}).get(name)

    indices = {arm_id: list(field(arm_id, METADATA_MANIPULATED_FIELD) or [])
               for arm_id in ARM_IDS}
    prompts = {arm_id: records[arm_id].get("rendered_prompt_hash")
               for arm_id in ARM_IDS}
    templates = {records[arm_id].get("prompt_template_hash")
                 for arm_id in ARM_IDS}
    checks = {
        "A_indices_equal_C": indices["A"] == indices["C"],
        "B_indices_equal_D": indices["B"] == indices["D"],
        "A_indices_differ_B": indices["A"] != indices["B"],
        "prompt_A_equals_B": prompts["A"] == prompts["B"],
        "prompt_C_equals_D": prompts["C"] == prompts["D"],
        "prompt_A_differs_C": prompts["A"] != prompts["C"],
        "prompt_template_single": len(templates) == 1,
        "prompt_template_frozen": templates == {prompt_template_hash()},
    }
    for name in METADATA_FIXED_FIELDS:
        values = {repr(field(arm_id, name)) for arm_id in ARM_IDS}
        checks["metadata_%s_identical" % name] = len(values) == 1
    reasons = []
    if not all(checks[key] for key in checks
               if key.startswith("metadata_") or key.startswith("A_indices")
               or key.startswith("B_indices")):
        reasons.append(METADATA_MANIPULATION_FAILURE)
    if not all(checks[key] for key in ("prompt_A_equals_B",
                                       "prompt_C_equals_D",
                                       "prompt_A_differs_C")):
        reasons.append(RENDERED_PROMPT_MISMATCH)
    if not checks["prompt_template_single"] or \
            not checks["prompt_template_frozen"]:
        reasons.append(CONFIG_MISMATCH)
    return {"ok": not reasons, "reasons": sd.dedup(reasons),
            "checks": checks,
            "indices_first_last": {arm_id: ([row[0], row[-1]] if row else None)
                                   for arm_id, row in indices.items()},
            "rendered_prompt_hashes": prompts,
            "prompt_template_hash": prompt_template_hash()}


def pixel_agreement(records: dict) -> dict:
    """4 arm이 먹인 픽셀 해시가 서로 완전히 같은지."""
    tables = {arm_id: list(records[arm_id].get("frame_hashes") or [])
              for arm_id in records}
    reference_id = ARM_IDS[0] if ARM_IDS[0] in tables else \
        (sorted(tables)[0] if tables else None)
    if reference_id is None:
        return {"identical": False, "reason": ARM_COUNT_MISMATCH,
                "compared": 0}
    reference = tables[reference_id]
    differing = [arm_id for arm_id, row in tables.items()
                 if row != reference]
    return {"identical": not differing and len(reference) == PIXEL_FRAME_COUNT,
            "reference_arm": reference_id, "compared": len(tables),
            "differing_arms": differing,
            "frame_count": len(reference),
            "reason": "" if not differing else PIXEL_IDENTITY_FAILURE}


def causal_pattern(arm_rows, blockers=()) -> dict:
    """사전등록 §13·§14. 우선순위 INCONCLUSIVE → CONTROL_NOT_REPRODUCED → 2×2."""
    rows = list(arm_rows)
    blocking = list(blockers)
    if len(rows) != EXPECTED_ARM_COUNT:
        blocking.append(ARM_COUNT_MISMATCH)
    for row in rows:
        blocking.extend(row.get("blockers") or [])
    blocking = sd.dedup(blocking)
    valid = {row.get("arm_id"): bool(row.get("valid")) for row in rows}

    if blocking or set(valid) != set(ARM_IDS):
        verdict, reason = INCONCLUSIVE, "MEASUREMENT_BLOCKED"
    elif valid["A"]:
        verdict, reason = CONTROL_NOT_REPRODUCED, "CONTROL_ARM_VALID"
    elif not any(valid.values()):
        verdict, reason = NOT_SUPPORTED, "ALL_ARMS_INVALID"
    elif not valid["B"] and valid["C"] and valid["D"]:
        verdict, reason = PROMPT_TIME_EFFECT, "P0_INVALID_P1_VALID"
    elif not valid["C"] and valid["B"] and valid["D"]:
        verdict, reason = METADATA_TIME_EFFECT, "M0_INVALID_M1_VALID"
    else:
        verdict, reason = JOINT_EFFECT, "MIXED_PATTERN"

    claim_channel = {PROMPT_TIME_EFFECT: "prompt",
                     METADATA_TIME_EFFECT: "metadata"}.get(verdict)
    return {
        "verdict": verdict, "reason": reason,
        "pattern": {arm_id: (ARM_VALID if valid.get(arm_id) else ARM_INVALID)
                    for arm_id in ARM_IDS if arm_id in valid},
        "valid_arms": [arm_id for arm_id in ARM_IDS if valid.get(arm_id)],
        "blockers": blocking,
        "allowed_claim": (ALLOWED_CLAIM_TEMPLATE % claim_channel
                          if claim_channel else None),
        "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS),
        "event_kind": EVENT_KIND,
        "mechanism_claimed": False,
        "recovery_attempt_allowed": RECOVERY_ATTEMPT_ALLOWED,
    }


def frozen_artifacts_unchanged(observed: dict) -> dict:
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
            "original_status_retained": PRIOR_STATE["original_W00"],
            "may_be_revalidated": ORIGINAL_W00_MAY_BE_REVALIDATED}
