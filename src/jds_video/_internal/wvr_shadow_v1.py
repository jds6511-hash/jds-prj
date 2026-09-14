"""WVR_EVENT_EXTRACTION_SHADOW_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md`

```
Inference configuration change   NONE (SHORT_WINDOW_V1 S0 대비)
Architecture under characterization   결정적 48초 / 24초 overlap tiling
New measurement instrumentation   overlap 비교 + 사전등록 7 overlap frame audit
측정 축 두 개   A. overlap/context stability   B. frame-grounded event validity
               두 축을 섞지 않는다
금지           Overview·Chapter·Highlight·stitching production · semantic 최종 판정
```

이것은 인과효과 하나를 재는 ablation이 아니라 **architecture shadow characterization**이다.
`single_change = true`를 주장하지 않는다.

`0.5fps`는 provisional working density다 — production default도 truth도 아니다.
"""
import hashlib

import wvr_contract as contract
import wvr_density as density
import wvr_density_prompt_v2 as diag
import wvr_density_v1b as events
import wvr_short_window as sw

EVENT = "WVR_EVENT_EXTRACTION_SHADOW_V1"
ARTIFACT_TAG = "shadow_v1"

# ── 창 일정 (결과 보기 전 동결) ──────────────────────────────────────
RANGE_START_SEC = 0.0
RANGE_END_SEC = 600.0
WINDOW_SEC = 48.0
STRIDE_SEC = 24.0
OVERLAP_SEC = 24.0
SAMPLING_FPS = 0.5
FRAMES_PER_WINDOW = 24
STEP_SEC = 1.0 / SAMPLING_FPS
EXPECTED_WINDOW_COUNT = 24
EXPECTED_OVERLAP_COUNT = 23
SHARED_FRAMES_PER_OVERLAP = 12

# frame bank (reviewer audit 전용 · inference 입력 경로를 바꾸지 않는다)
BANK_FRAME_COUNT = 300

# 사전등록된 frame-audit overlap 7개 (결과 보고 고르지 않는다)
AUDIT_OVERLAPS = ("O01", "O04", "O05", "O12", "O18", "O19", "O23")
AUDIT_STRESS = ("O04", "O05", "O18", "O19")      # 과거 material-conflict 시간대 포함
AUDIT_CONTROL = ("O01", "O12", "O23")            # temporal-spread 대조

# ── SHORT_WINDOW_V1 S0에서 그대로 가져오는 동결값 ────────────────────
FROZEN_FROM_SHORT_WINDOW = {
    "model_id": contract.MODEL_ID,
    "model_revision": contract.MODEL_REVISION,
    "dtype": contract.DTYPE,
    "quantization": contract.QUANTIZATION,
    "attn_implementation": contract.ATTN_IMPLEMENTATION,
    "device_map": contract.DEVICE_MAP,
    "frame_width": contract.FRAME_WIDTH,
    "frame_height": contract.FRAME_HEIGHT,
    "do_sample": contract.DO_SAMPLE,
    "num_beams": contract.NUM_BEAMS,
    "repetition_penalty": contract.REPETITION_PENALTY,
    "do_sample_frames": contract.DO_SAMPLE_FRAMES,
    "do_resize": contract.DO_RESIZE,
    "max_new_tokens": events.tokens_for(events.EVENT_V2),
    "prompt_contract": diag.DIAG_CONTRACT_NAME,
    "prompt_hash": diag.prompt_hash(),
    "output_language": diag.OUTPUT_LANGUAGE,
    "window_sec": sw.WINDOW_SEC,
    "frames_per_window": sw.S0_FRAME_COUNT,
    "sampling_fps": density.REFERENCE_FPS,
    "match_tolerances": list(density.MATCH_TOLERANCE_SEC),
}

# 이번 사건이 절대 입력으로 받지 않는 것
FORBIDDEN_INPUTS = ("subtitle", "caption", "canonical_evidence",
                    "prior_arm_text", "human_verdict", "search_result")

NEW_INFERENCE_PER_WINDOW = 1
RUNTIME_RETRY_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False
STITCHING_PRODUCTION_ALLOWED = False
EVENT_MAP_PRODUCTION_APPROVED = False
CHAPTER_APPROVED = False
OVERVIEW_APPROVED = False
AUTOMATIC_MATCHER_ROLE = "AUDIT_DIAGNOSTIC_ONLY"

# ── 판정 어휘 ───────────────────────────────────────────────────────
TECHNICAL_OK = "TECHNICAL_GATE_OK"
TECHNICAL_INCONCLUSIVE = "INCONCLUSIVE"

# reviewer 전용 (executor는 채우지 않는다)
SEMANTIC_VERDICTS = ("STABLE", "GRANULARITY_SHIFT", "MATERIAL_DIVERGENCE",
                     "UNRESOLVED")
SUPPORT_VERDICTS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED",
                    "FRAMES_INSUFFICIENT")

WINDOW_VALID = "WINDOW_VALID"
WINDOW_INVALID = "WINDOW_INVALID"
FRAME_COUNT_MISMATCH = "FRAME_COUNT_MISMATCH"
GRID_MISMATCH = "SAMPLING_GRID_MISMATCH"
RAW_NOT_PERSISTED = "RAW_NOT_PERSISTED"
PROVENANCE_MISMATCH = "VIDEO_PROVENANCE_MISMATCH"
SHARED_FRAME_IDENTITY_FAILURE = "SHARED_FRAME_IDENTITY_FAILURE"

# PASS 시 허용되는 최대 결론 — 두 부분으로 나눠 적는다(리뷰어 정정 2026-09-09)
ALLOWED_MAX_CONCLUSION = (
    "Within C01: (1) all 23 adjacent overlaps passed the report-material "
    "overlap-stability gate, and (2) the 7 preregistered frame-audit overlaps "
    "contained no disqualifying frame-grounding failure.")
GATE_SCOPE = {"overlap_stability": "23/23 adjacent overlaps",
              "frame_grounding": "7/23 preregistered audit overlaps only"}
FRAME_AUDIT_EXPANSION_ALLOWED = False
SUPPORT_FRAME_TIMES_IN_SCHEMA = False
FORBIDDEN_CONCLUSIONS = (
    "0.5fps universally sufficient", "0.5fps factual authority",
    "production Event extraction approved", "whole-video understanding solved",
    "Overview quality proven", "report factuality proven",
    "all C01 events are frame-grounded",
    "entire Event Map factuality verified")

# 48초의 지위 (리뷰어 정정) — technically executable이고 semantic stability는 미검증
WINDOW_LENGTH_STATUS = {
    "48s": "technically executable / technically valid diagnostic length",
    "semantic_stability": "NOT validated — SHORT_WINDOW_V1 = HOLD"}

# Track A canonical evidence의 지위 (리뷰어 정정)
CANONICAL_EVIDENCE_ROLE = {
    "role": "downstream auxiliary claim-verification layer",
    "discriminative_coverage": "LIMITED (EVIDENCE_RESOLUTION_V1 실측)",
    "on_no_support_and_no_contradiction": "UNRESOLVED 유지"}

# 이번 사건의 normative authority 우선순위 (리뷰어 확정)
NORMATIVE_AUTHORITY = (
    "WVR_EVENT_EXTRACTION_SHADOW_V1 preregistration",
    "frozen prompt/schema/runtime hash",
    "execution artifacts / raw results",
    "PROJECT_OVERVIEW.md (지도이지 실험 계약서가 아니다)")


class ShadowError(RuntimeError):
    """shadow 계약 위반."""


def windows() -> list:
    """[0,600)을 48초 창 · 24초 stride로 tile한다. 반열린 구간."""
    rows, start, index = [], RANGE_START_SEC, 0
    while start + WINDOW_SEC <= RANGE_END_SEC + 1e-9:
        rows.append({"window_id": "W%02d" % index, "index": index,
                     "start_sec": round(start, 3),
                     "end_sec": round(start + WINDOW_SEC, 3)})
        index += 1
        start = round(start + STRIDE_SEC, 3)
    if len(rows) != EXPECTED_WINDOW_COUNT:
        raise ShadowError("창 개수가 %d가 아니다: %d"
                          % (EXPECTED_WINDOW_COUNT, len(rows)))
    if rows[0]["start_sec"] != 0.0 or rows[-1]["end_sec"] != RANGE_END_SEC:
        raise ShadowError("창 범위가 [0,600)을 덮지 않는다")
    return rows


def window_by_id(window_id: str) -> dict:
    for row in windows():
        if row["window_id"] == window_id:
            return row
    raise ShadowError("모르는 창: %r" % window_id)


def frame_times(window: dict) -> tuple:
    """창 안 0.5fps 격자 24개. 마지막은 start+46이고 창을 넘지 않는다."""
    start = float(window["start_sec"])
    stamps = tuple(round(start + STEP_SEC * i, 3)
                   for i in range(FRAMES_PER_WINDOW))
    if stamps[-1] >= float(window["end_sec"]):
        raise ShadowError("프레임이 창을 벗어난다: %r" % (stamps[-1],))
    return stamps


def overlaps() -> list:
    """인접 창 쌍 23개와 그 공유 구간."""
    rows = windows()
    out = []
    for index in range(len(rows) - 1):
        earlier, later = rows[index], rows[index + 1]
        low = max(earlier["start_sec"], later["start_sec"])
        high = min(earlier["end_sec"], later["end_sec"])
        if round(high - low, 6) != OVERLAP_SEC:
            raise ShadowError("겹침이 %.1f초가 아니다: %r"
                              % (OVERLAP_SEC, (low, high)))
        out.append({"overlap_id": "O%02d" % (index + 1),
                    "earlier": earlier["window_id"],
                    "later": later["window_id"],
                    "start_sec": low, "end_sec": high})
    if len(out) != EXPECTED_OVERLAP_COUNT:
        raise ShadowError("겹침 개수가 %d가 아니다: %d"
                          % (EXPECTED_OVERLAP_COUNT, len(out)))
    return out


def overlap_by_id(overlap_id: str) -> dict:
    for row in overlaps():
        if row["overlap_id"] == overlap_id:
            return row
    raise ShadowError("모르는 겹침: %r" % overlap_id)


def shared_times(overlap: dict) -> tuple:
    """겹침 구간 안의 0.5fps 시각 12개 — 양쪽 창의 격자에 모두 있어야 한다."""
    earlier = set(frame_times(window_by_id(overlap["earlier"])))
    later = set(frame_times(window_by_id(overlap["later"])))
    shared = tuple(sorted(earlier & later))
    if len(shared) != SHARED_FRAMES_PER_OVERLAP:
        raise ShadowError("공유 프레임이 %d개가 아니다: %d"
                          % (SHARED_FRAMES_PER_OVERLAP, len(shared)))
    if any(time < overlap["start_sec"] or time >= overlap["end_sec"]
           for time in shared):
        raise ShadowError("공유 프레임이 겹침 구간 밖이다: %r" % (shared,))
    return shared


def bank_times() -> tuple:
    """reviewer audit용 frame bank — 0,2,…,598."""
    stamps = tuple(round(RANGE_START_SEC + STEP_SEC * i, 3)
                   for i in range(BANK_FRAME_COUNT))
    if stamps[-1] != 598.0:
        raise ShadowError("frame bank 마지막 시각이 598.0이 아니다")
    return stamps


def inference_config_change(requested: dict) -> dict:
    """SHORT_WINDOW_V1 S0 대비 inference 설정 변경이 없는지 확인한다.

    이 사건은 ablation이 아니라 architecture characterization이므로
    `single_change`라는 주장을 만들지 않는다 — inference 설정 변경이 NONE인지만 잰다.
    """
    differences = {}
    for key, value in FROZEN_FROM_SHORT_WINDOW.items():
        if key not in requested:
            continue
        if requested[key] != value:
            differences[key] = {"expected": value, "observed": requested[key]}
    return {
        "inference_config_change": "NONE" if not differences else "DETECTED",
        "differences": differences,
        "architecture_under_characterization":
            "deterministic 48s / 24s-overlap tiling of C01",
        "new_measurement_instrumentation":
            "overlap comparison + preregistered frame audit (7 overlaps)",
        "not_an_ablation": True,
    }


def assert_video_only(requested: dict) -> None:
    for key in FORBIDDEN_INPUTS:
        if requested.get(key):
            raise ShadowError("금지된 입력이 들어왔다: %s" % key)


def clip_event(event: dict, start: float, end: float):
    """겹침 범위로 자른 사본을 만든다. 원본을 수정하지 않는다."""
    low, high = float(event["start_sec"]), float(event["end_sec"])
    if low >= end or high <= start:
        return None
    return {
        "original_event_id": event.get("index"),
        "original_start": low, "original_end": high,
        "clipped_start": max(low, start), "clipped_end": min(high, end),
        "actor": event.get("actor"), "action": event.get("action"),
        "object_or_state": event.get("object_or_state"),
        "clipped": (low < start) or (high > end),
    }


def clip_sequence(collapsed, start: float, end: float) -> list:
    rows = []
    for event in collapsed:
        clipped = clip_event(event, start, end)
        if clipped is not None:
            rows.append(clipped)
    return rows


def blind_label(overlap_id: str, role: str, prereg_sha: str) -> str:
    """earlier·later를 Arm A/B로 가린다 — prereg SHA와 overlap id의 결정적 함수.

    사람이 결과를 보고 고르지 않는다. 실행 후 변경할 수 없다(같은 입력 → 같은 출력).
    """
    if role not in ("earlier", "later"):
        raise ShadowError("모르는 role: %r" % role)
    digest = hashlib.sha256(("%s|%s" % (prereg_sha, overlap_id))
                            .encode("utf-8"))
    flip = digest.digest()[0] & 1
    if role == "earlier":
        return "B" if flip else "A"
    return "A" if flip else "B"


def window_validity(record: dict, video_sha256: str) -> dict:
    """기술 검증 — V2의 arm_validity를 그대로 쓰고 창 고유 검사만 더한다."""
    import wvr_density_v2 as v2

    base = v2.arm_validity(record)
    reasons = list(base["reasons"])
    metrics = record.get("metrics") or {}
    if metrics.get("delivered_frame_count") != FRAMES_PER_WINDOW:
        reasons.append(FRAME_COUNT_MISMATCH)
    expected = list(frame_times(record["window"]))
    if [round(float(time), 3) for time in
            (record.get("frame_times") or [])] != expected:
        reasons.append(GRID_MISMATCH)
    if not record.get("raw_persisted"):
        reasons.append(RAW_NOT_PERSISTED)
    if record.get("video_sha256") != video_sha256:
        reasons.append(PROVENANCE_MISMATCH)
    return {"valid": not reasons, "reasons": reasons,
            "status": WINDOW_VALID if not reasons else WINDOW_INVALID,
            "language": base["language"]}


def technical_gate(window_statuses, overlap_identity_failures) -> dict:
    """기술 게이트만 계산한다. semantic 판정은 비워 둔다(reviewer 몫)."""
    invalid = [row for row in window_statuses if not row["valid"]]
    reasons = []
    if len(window_statuses) != EXPECTED_WINDOW_COUNT:
        reasons.append("WINDOW_COUNT_MISMATCH")
    if invalid:
        reasons.append("WINDOW_TECHNICAL_INVALID")
    if list(overlap_identity_failures):
        reasons.append(SHARED_FRAME_IDENTITY_FAILURE)
    return {
        "technical_verdict": TECHNICAL_OK if not reasons
        else TECHNICAL_INCONCLUSIVE,
        "reasons": reasons,
        "invalid_windows": [row["window_id"] for row in invalid],
        "overlap_identity_failures": list(overlap_identity_failures),
        "semantic_verdict": None,
        "semantic_verdict_by_executor": SEMANTIC_VERDICT_BY_EXECUTOR,
    }
