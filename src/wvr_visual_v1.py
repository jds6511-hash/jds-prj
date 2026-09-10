"""WVR_W00_VISUAL_CONTENT_ISOLATION_V1 계측기 (2026-09-10 · freeze).

사전등록: `docs/preregistration/WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md`

```
질문   같은 0–48 absolute-time encoding에서 W00 초반 픽셀 대신 W05 [120,168) 픽셀을
      넣어도 degeneracy가 나는가
설계   2×2의 남은 한 칸만 채운다 — arm E = W05 pixels + T0(P0M0) · 새 inference 1회
동결   기존 세 칸(Trigger A · Trigger D · SHADOW W05)은 재실행하지 않고 해시로 확인
금지   prompt 문구·zero-duration 예시·schema·token cap·penalty 변경 · subdivision 재개 ·
      retry · 기존 칸 재실행 · 메커니즘 단정
```
"""
import wvr_shadow_v1 as sh
import wvr_subdivision_v1 as sd
import wvr_trigger_v1 as tg

EVENT = "WVR_W00_VISUAL_CONTENT_ISOLATION_V1"
ARTIFACT_TAG = "visual_v1"

# ── arm E (새 측정 1회) ────────────────────────────────────────────
ARM_ID = "E"
EXPECTED_ARM_COUNT = 1
PIXEL_SOURCE_WINDOW_ID = "W05"          # 실제 120,122,…,166초 픽셀
PIXEL_FRAME_COUNT = tg.PIXEL_FRAME_COUNT
SAMPLING_FPS = tg.SAMPLING_FPS
TIME_ENCODING = "T0"                    # prompt 0–48 + M0 indices (= Trigger A)
TIME_REFERENCE_ARM = "A"                # 시간 인코딩을 그대로 물려받는 arm
PROMPT_MODE = "P0"
METADATA_MODE = "M0"

# ── 2×2 표 (세 칸은 frozen · 재실행 금지) ──────────────────────────
CELL_X0T0 = {"cell": "X0T0", "pixels": "W00 [0,48)", "time": "T0 (0–48)",
             "source": "trigger_v1_A", "status": sh.WINDOW_INVALID}
CELL_X0T1 = {"cell": "X0T1", "pixels": "W00 [0,48)", "time": "T1 (120–168)",
             "source": "trigger_v1_D", "status": sh.WINDOW_VALID}
CELL_X1T1 = {"cell": "X1T1", "pixels": "W05 [120,168)", "time": "T1 (120–168)",
             "source": "shadow_v1_W05", "status": sh.WINDOW_VALID}
CELL_X1T0 = {"cell": "X1T0", "pixels": "W05 [120,168)", "time": "T0 (0–48)",
             "source": "visual_v1_E", "status": "MEASURED_BY_THIS_EVENT"}
FROZEN_CELLS = (CELL_X0T0, CELL_X0T1, CELL_X1T1)
RERUN_OF_FROZEN_CELLS_ALLOWED = False

# ── 읽기 전용 선행 산출물 (사전등록 §1) ────────────────────────────
PIXEL_REFERENCE_RECORD = "shadow_v1_W05.json"
TIME_REFERENCE_RECORD = "trigger_v1_A.json"
FROZEN_ARTIFACTS = {
    "shadow_v1_W05.json":
        "ebcd438d8ccd91b248622a626c2932b26e2787a95e31aee8a332fc45a92ee241",
    "shadow_v1_W05_raw.txt":
        "38caf8e6cfde38ce8da49bc6fcdd68e7c85454f8db828fdf27906843758564eb",
    "trigger_v1_A.json":
        "6de08ac56322a25edea8dd3294b039e8f942d5ec2ae63720b634074bcc2c0180",
    "trigger_v1_A_raw.txt":
        "c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6",
    "trigger_v1_D.json":
        "e406ae2520e63739d8758fa23590bbe0c443d6bc4f8a6512cee9f0de240a86b3",
    "trigger_v1_D_raw.txt":
        "01496012501858fb0a6f3668194a5e936819d59efb588d5792680d55e591f1a5",
    "shadow_v1_W00.json": sd.ORIGINAL_RECORD_SHA256,
    "shadow_v1_W00_raw.txt": sd.ORIGINAL_RAW_SHA256,
}

RETRY_ALLOWED = False
RAW_SALVAGE_ALLOWED = False
TOKEN_CAP_INCREASE_APPROVED = False
PROMPT_TEXT_MUTATION_ALLOWED = False
ZERO_DURATION_EXAMPLE_MUTATION_ALLOWED = False
SCHEMA_MUTATION_ALLOWED = False
SUBDIVISION_RESTART_ALLOWED = False
ADDITIONAL_SHIFT_ALLOWED = False
PROCESSOR_MONKEY_PATCH_ALLOWED = False
MAPPING_REVEAL_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False
MECHANISM_CLAIM_ALLOWED = False

# ── 판정 어휘 (사전 동결) ──────────────────────────────────────────
TIME_CONFIG_EFFECT = "ABSOLUTE_TIME_CONFIGURATION_EFFECT_SUPPORTED"
CONTENT_TIME_INTERACTION = "VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED"
INCONCLUSIVE = "INCONCLUSIVE"
VERDICTS = (TIME_CONFIG_EFFECT, CONTENT_TIME_INTERACTION, INCONCLUSIVE)

PIXEL_IDENTITY_FAILURE = tg.PIXEL_IDENTITY_FAILURE
TIME_ENCODING_MISMATCH = "TIME_ENCODING_MISMATCH"
FROZEN_CELL_CHANGED = "FROZEN_CELL_CHANGED"
CONFIG_MISMATCH = sd.CONFIG_MISMATCH
ARM_COUNT_MISMATCH = tg.ARM_COUNT_MISMATCH

FAIL_REASONS = sd.FAIL_REASONS
BLOCKER_REASONS = tuple(sd.BLOCKER_REASONS) + (
    PIXEL_IDENTITY_FAILURE, TIME_ENCODING_MISMATCH, FROZEN_CELL_CHANGED,
    ARM_COUNT_MISMATCH)

ALLOWED_CLAIMS = {
    TIME_CONFIG_EFFECT: ("이번 두 pixel set 범위에서 0–48 absolute-time "
                         "configuration과 degeneracy 상태의 연관이 관찰됨"),
    CONTENT_TIME_INTERACTION: ("W00 초반 visual content 자체가 아니라 그것이 "
                               "0–48 time encoding과 결합될 때만 이번 failure가 "
                               "관찰됨"),
}
FORBIDDEN_CONCLUSIONS = (
    "0초 버그의 내부 원인을 증명했다", "Qwen 내부 메커니즘을 규명했다",
    "prompt가 잘못됐다", "metadata가 모델을 망가뜨린다",
    "두 채널을 +120초로 옮기면 무조건 해결된다", "recovery 방법을 찾았다",
    "production Event extraction이 가능해졌다",
    "다른 창·다른 영상·다른 shift에서도 같다")
MEASUREMENT_SCOPE = "pixel set 2개 · time encoding 2개 · shift 1개(+120초)"

PRIOR_STATE = {
    "WVR_W00_TRIGGER_ISOLATION_V1":
        "CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED",
    "WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1": "CLOSED / RECOVERY_FAIL",
    "WVR_W00_SUBDIVISION_RECOVERY_V1": "CLOSED / SUBDIVISION_RECOVERY_FAIL",
    "WVR_W00_DEGENERACY_REPRO_V1": "CLOSED / REPRODUCIBLE",
    "WVR_W00_DEGENERACY_FORENSIC_V1": "CLOSED / MODEL_OUTPUT_DEGENERACY",
    "WVR_EVENT_EXTRACTION_SHADOW_V1": "CLOSED / INCONCLUSIVE",
    "recursive_subdivision_hypothesis": "STOPPED / NOT SUFFICIENT",
}

NORMATIVE_AUTHORITY = (
    "WVR_W00_VISUAL_CONTENT_ISOLATION_V1 preregistration",
    "frozen model/prompt/runtime configuration",
    "raw execution artifacts",
    "prior trigger/forensic/repro/recovery results",
    "PROJECT_OVERVIEW.md",
)

EVENT_KIND = ("visual-content isolation — 2×2의 남은 한 칸만 채운다. "
              "causal mechanism proof가 아니다")


class VisualError(RuntimeError):
    """visual content isolation 계약 위반."""


def pixel_source_window() -> dict:
    """픽셀을 뽑을 실제 창 W05 [120,168)."""
    window = sh.window_by_id(PIXEL_SOURCE_WINDOW_ID)
    if (window["start_sec"], window["end_sec"]) != (120.0, 168.0):
        raise VisualError("픽셀 원천 창이 [120,168)이 아니다: %r" % (window,))
    return window


def pixel_times() -> tuple:
    """120,122,…,166 — W05 격자 그대로."""
    stamps = sh.frame_times(pixel_source_window())
    if len(stamps) != PIXEL_FRAME_COUNT:
        raise VisualError("픽셀이 %d장이 아니다: %d"
                          % (PIXEL_FRAME_COUNT, len(stamps)))
    if stamps[0] != 120.0 or stamps[-1] != 166.0:
        raise VisualError("픽셀 시각이 120…166이 아니다: %r"
                          % ((stamps[0], stamps[-1]),))
    return stamps


def time_encoding() -> dict:
    """시간 인코딩은 Trigger arm A에서 그대로 가져온다 (T0 = P0 + M0)."""
    return {"time_encoding": TIME_ENCODING,
            "reference_arm": TIME_REFERENCE_ARM,
            "prompt_mode": PROMPT_MODE, "metadata_mode": METADATA_MODE,
            "prompt_window": list(tg.prompt_window(PROMPT_MODE)),
            "rendered_prompt_hash": tg.rendered_prompt_hash(PROMPT_MODE),
            "prompt_template_hash": tg.prompt_template_hash()}


def rendered_prompt() -> str:
    return tg.rendered_prompt(PROMPT_MODE)


def frame_indices(rate: float) -> tuple:
    """metadata frames_indices = T0 표현(0,2,…,46)에 대응하는 index."""
    return tg.frame_indices(METADATA_MODE, rate)


def arm_plan(rate: float) -> dict:
    encoding = time_encoding()
    return {
        "arm_id": ARM_ID, **encoding,
        "pixel_source_window": pixel_source_window(),
        "pixel_times": list(pixel_times()),
        "frames_indices": list(frame_indices(rate)),
        "rendered_prompt": rendered_prompt(),
        "cell": CELL_X1T0["cell"],
        "fixed_metadata_fields": list(tg.METADATA_FIXED_FIELDS),
        "manipulated_metadata_field": tg.METADATA_MANIPULATED_FIELD,
    }


def pixel_identity(observed, reference) -> dict:
    """arm E 픽셀이 기존 W05 픽셀과 순서까지 같은지."""
    return tg.pixel_identity(observed, reference)


def time_encoding_identity(record: dict, reference: dict) -> dict:
    """rendered prompt와 frames_indices가 Trigger A와 같은지."""
    rows = {
        "rendered_prompt_hash": (record.get("rendered_prompt_hash")
                                 == reference.get("rendered_prompt_hash")),
        "prompt_window": ([round(float(value), 3) for value in
                           (record.get("prompt_window") or [])]
                          == [round(float(value), 3) for value in
                              (reference.get("prompt_window") or [])]),
        "frames_indices": (list((record.get("metadata") or {}).get(
            "frames_indices") or [])
            == list((reference.get("metadata") or {}).get(
                "frames_indices") or [])),
        "prompt_template_hash": (record.get("prompt_template_hash")
                                 == reference.get("prompt_template_hash")),
    }
    for name in tg.METADATA_FIXED_FIELDS:
        rows["metadata_%s" % name] = (
            (record.get("metadata") or {}).get(name)
            == (reference.get("metadata") or {}).get(name))
    mismatched = [name for name, same in rows.items() if not same]
    return {"identical": not mismatched, "checks": rows,
            "mismatched": mismatched,
            "reason": "" if not mismatched else TIME_ENCODING_MISMATCH,
            "reference_arm": TIME_REFERENCE_ARM}


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
    if not (record.get("time_encoding_identity") or {}).get("identical"):
        reasons.append(TIME_ENCODING_MISMATCH)
    if (record.get("representation") or {}).get("degenerate"):
        reasons.append(sd.REPRESENTATION_DEGENERACY)
    reasons = sd.dedup(reasons)
    return {"valid": not reasons, "reasons": reasons,
            "status": sh.WINDOW_VALID if not reasons else sh.WINDOW_INVALID,
            "language": base["language"],
            "blockers": [reason for reason in reasons
                         if reason not in FAIL_REASONS],
            "output_failures": [reason for reason in reasons
                                if reason in FAIL_REASONS]}


def frozen_cells_unchanged(observed: dict) -> dict:
    """기존 세 칸과 원본 W00 산출물이 그대로인지. 재실행은 금지다."""
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
            "rerun_allowed": RERUN_OF_FROZEN_CELLS_ALLOWED,
            "frozen_cells": [dict(cell) for cell in FROZEN_CELLS]}


def table(arm_row: dict) -> dict:
    """2×2 표를 채운다. 세 칸은 frozen 값을 그대로 쓴다."""
    measured = dict(CELL_X1T0)
    measured["status"] = arm_row.get("status")
    measured["valid"] = arm_row.get("valid")
    return {
        "X0T0": dict(CELL_X0T0), "X0T1": dict(CELL_X0T1),
        "X1T1": dict(CELL_X1T1), "X1T0": measured,
        "axes": {"pixels": ["W00 [0,48)", "W05 [120,168)"],
                 "time_encoding": ["T0 (0–48)", "T1 (120–168)"]},
        "rerun_of_frozen_cells": RERUN_OF_FROZEN_CELLS_ALLOWED,
    }


def verdict(arm_row: dict, blockers=()) -> dict:
    """사전등록 §9·§10. INCONCLUSIVE → E 판정에 따른 두 어휘."""
    blocking = list(blockers) + list(arm_row.get("blockers") or [])
    blocking = sd.dedup(blocking)
    valid = arm_row.get("valid")
    if blocking or valid is None:
        name, reason = INCONCLUSIVE, "MEASUREMENT_BLOCKED"
    elif valid:
        name, reason = CONTENT_TIME_INTERACTION, "E_VALID"
    else:
        name, reason = TIME_CONFIG_EFFECT, "E_INVALID"
    return {
        "verdict": name, "reason": reason,
        "arm_status": arm_row.get("status"),
        "blockers": blocking,
        "table": table(arm_row),
        "allowed_claim": ALLOWED_CLAIMS.get(name),
        "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS),
        "measurement_scope": MEASUREMENT_SCOPE,
        "event_kind": EVENT_KIND,
        "mechanism_claimed": MECHANISM_CLAIM_ALLOWED,
        "new_inference_count": EXPECTED_ARM_COUNT,
    }
