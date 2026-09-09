"""WVR_W00_DEGENERACY_REPRO_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md`

```
질문   W00의 MODEL_OUTPUT_DEGENERACY가 동일 입력·동일 설정·fresh process에서 재현되는가
변경   없다 — prompt·schema·cap·penalty·표집·창 길이 전부 SHADOW_V1 W00과 동일
성격   retry가 아니라 사전등록된 관측 3건. 성공 run을 골라 쓰지 않는다
금지   원본 W00 소급 VALID 전환 · mapping reveal · semantic 판정 · recovery 실험 개시
```
"""
import wvr_shadow_v1 as sh
import wvr_w00_forensic as fx

EVENT = "WVR_W00_DEGENERACY_REPRO_V1"
ARTIFACT_TAG = "w00_repro"
TARGET_WINDOW_ID = "W00"
RUN_IDS = ("R1", "R2", "R3")
EXPECTED_RUN_COUNT = 3

# 원본 W00 산출물 (읽기 전용 · 무변경 확인용 · 사전등록에 기재)
ORIGINAL_RECORD = "shadow_v1_W00.json"
ORIGINAL_RAW = "shadow_v1_W00_raw.txt"
ORIGINAL_RECORD_SHA256 = (
    "c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e44daa074")
ORIGINAL_RAW_SHA256 = (
    "c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6")
ORIGINAL_RUNTIME_CONFIG_SHA256 = (
    "cb43ffd357d771ff2923f2d3e0dec0f48f85bba660171cfc3832a298f4fef5aa")

# forensic에서 관측된 두 signature (참고 기록 전용 — 판정 기준이 아니다)
REFERENCE_SIGNATURES = (
    ("a person", "pouring", "liquid from a bottle into a bowl"),
    ("a person", "holding", "a bottle"),
)

RETRY_ALLOWED = False
RECOVERY_EXPERIMENT_ALLOWED = False
SUBDIVISION_INFERENCE_ALLOWED = False        # 24초/12초 추론 금지
ORIGINAL_W00_MAY_BE_REVALIDATED = False
MAPPING_REVEAL_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False
PRODUCTION_SELECTION_ALLOWED = False         # 성공 run을 골라 쓰지 않는다

IDENTITY_FAILURE = "INPUT_IDENTITY_FAILURE"
IDENTITY_OK = "INPUT_IDENTITY_OK"
IDENTITY_FIELDS = ("video_sha256", "window", "frame_times", "frame_hashes",
                   "prompt_text", "prompt_hash", "model_revision",
                   "runtime_config_hash", "generation_config")

DEGENERACY = "MODEL_OUTPUT_DEGENERACY"
NO_DEGENERACY = "NO_DEGENERACY_DETECTED"

REPRODUCIBLE = "REPRODUCIBLE"
NOT_REPRODUCED = "NOT_REPRODUCED"
INTERMITTENT = "INTERMITTENT"
INCONCLUSIVE = "INCONCLUSIVE"
REPRO_VERDICTS = (REPRODUCIBLE, NOT_REPRODUCED, INTERMITTENT, INCONCLUSIVE)

EXACT_RAW = "EXACT_RAW_REPRODUCTION"
STRUCTURAL = "STRUCTURAL_DEGENERACY_REPRODUCTION"
OUTPUT_VARIATION = "OUTPUT_VARIATION"
DETERMINISM_AXES = (EXACT_RAW, STRUCTURAL, OUTPUT_VARIATION)

FORBIDDEN_CONCLUSIONS = (
    "원인이 48초 context다", "원인이 영상 내용이다", "prompt가 나쁘다",
    "4096이 부족하다", "문제가 해결됐다", "original W00이 false alarm이다",
    "single retry가 안전하다")


class ReproError(RuntimeError):
    """재현성 사건 계약 위반."""


def target_window() -> dict:
    return sh.window_by_id(TARGET_WINDOW_ID)


def frame_times() -> tuple:
    return sh.frame_times(target_window())


def expected_prompt() -> str:
    return fx.expected_prompt(target_window())


def identity_report(original: dict, observed: dict) -> dict:
    """원본 W00과 이번 run의 입력이 항목별로 같은지."""
    rows, mismatched = {}, []
    for field in IDENTITY_FIELDS:
        same = original.get(field) == observed.get(field)
        rows[field] = {"identical": same}
        if not same:
            rows[field]["original"] = _brief(original.get(field))
            rows[field]["observed"] = _brief(observed.get(field))
            mismatched.append(field)
    return {"fields": rows, "mismatched": mismatched,
            "status": IDENTITY_OK if not mismatched else IDENTITY_FAILURE,
            "identical": not mismatched}


def _brief(value):
    if isinstance(value, (list, tuple)):
        return {"count": len(value), "first": value[0] if value else None,
                "last": value[-1] if value else None}
    return value


def consecutive_repeats(signatures) -> int:
    """가장 긴 연속 동일 signature 길이."""
    best, current = 0, 0
    previous = None
    for signature in signatures:
        current = current + 1 if signature == previous else 1
        previous = signature
        best = max(best, current)
    return best


def structure_audit(raw: str, metrics: dict) -> dict:
    """forensic의 raw 구조 분석 + 이번 사건이 요구한 항목."""
    base = fx.raw_structure(raw)
    signatures = []
    for match in fx.OBJECT_RE.finditer(raw):
        signatures.append((match.group(3), match.group(4), match.group(5)))
    positive = base["complete_object_count"] - \
        base["zero_length_interval_count"]
    reference_hits = {
        "S%d" % (index + 1): signatures.count(signature)
        for index, signature in enumerate(REFERENCE_SIGNATURES)}
    return {
        **base,
        "generated_tokens": metrics.get("generated_token_count"),
        "finish_reason": metrics.get("finish_reason"),
        "positive_duration_interval_count": positive,
        "max_consecutive_signature_repeat": consecutive_repeats(signatures),
        "reference_signature_hits": reference_hits,
        "reference_note": ("문구가 다르면 degeneracy가 아니라고 판단하지 않는다 — "
                           "무진행 반복·zero-length 지배·미완결 구조로 본다"),
    }


def run_degeneracy(structure: dict) -> dict:
    """forensic 축 B를 그대로 적용한다."""
    axis = fx.output_degeneracy(structure)
    return {"classification": DEGENERACY if axis["confirmed"]
            else NO_DEGENERACY, "reasons": axis["reasons"],
            "zero_progress": (structure["zero_length_interval_count"] ==
                              structure["complete_object_count"]
                              and structure["complete_object_count"] > 0)}


def repro_verdict(rows) -> dict:
    """사전등록 §9 게이트. 비율 임계를 새로 만들지 않는다."""
    values = list(rows)
    if len(values) != EXPECTED_RUN_COUNT:
        raise ReproError("run %d개의 관측이 필요하다: %d"
                         % (EXPECTED_RUN_COUNT, len(values)))
    blockers = [row for row in values
                if row.get("identity_status") != IDENTITY_OK
                or row.get("technical_status") == "RUNTIME_FAILURE"
                or not row.get("raw_persisted")]
    degenerate = [row for row in values
                  if row.get("degeneracy") == DEGENERACY]
    valid = [row for row in values if row.get("technical_valid")]
    if blockers:
        return {"verdict": INCONCLUSIVE,
                "reason": "MEASUREMENT_BLOCKED",
                "blocked_runs": [row.get("run_id") for row in blockers],
                "degenerate_count": len(degenerate)}
    if len(degenerate) == EXPECTED_RUN_COUNT:
        return {"verdict": REPRODUCIBLE, "reason": "ALL_RUNS_DEGENERATE",
                "degenerate_count": len(degenerate)}
    if len(valid) == EXPECTED_RUN_COUNT:
        return {"verdict": NOT_REPRODUCED, "reason": "ALL_RUNS_VALID",
                "degenerate_count": 0}
    if degenerate:
        return {"verdict": INTERMITTENT, "reason": "PARTIAL_DEGENERACY",
                "degenerate_count": len(degenerate)}
    return {"verdict": INCONCLUSIVE,
            "reason": "NO_DEGENERACY_BUT_NOT_ALL_VALID",
            "degenerate_count": 0}


def determinism_axis(raw_hashes, rows) -> dict:
    """primary verdict를 바꾸지 않는 별도 축."""
    identical = len(set(raw_hashes)) == 1 and len(raw_hashes) == \
        EXPECTED_RUN_COUNT
    all_degenerate = all(row.get("degeneracy") == DEGENERACY for row in rows)
    mixed = any(row.get("technical_valid") for row in rows) and \
        any(row.get("degeneracy") == DEGENERACY for row in rows)
    if identical and all_degenerate:
        axis = EXACT_RAW
    elif all_degenerate:
        axis = STRUCTURAL
    elif mixed:
        axis = OUTPUT_VARIATION
    else:
        axis = OUTPUT_VARIATION
    return {"axis": axis, "raw_hashes_identical": identical,
            "distinct_raw_hashes": len(set(raw_hashes)),
            "note": "이 축은 primary verdict를 바꾸지 않는다"}


def original_unchanged(record_sha: str, raw_sha: str) -> dict:
    rows = {"record": record_sha == ORIGINAL_RECORD_SHA256,
            "raw": raw_sha == ORIGINAL_RAW_SHA256}
    return {"unchanged": all(rows.values()), "checks": rows,
            "expected": {"record": ORIGINAL_RECORD_SHA256,
                         "raw": ORIGINAL_RAW_SHA256},
            "observed": {"record": record_sha, "raw": raw_sha},
            "original_status_retained": "WINDOW_INVALID",
            "may_be_revalidated": ORIGINAL_W00_MAY_BE_REVALIDATED}
