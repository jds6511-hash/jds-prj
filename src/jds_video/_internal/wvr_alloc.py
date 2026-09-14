"""WVR_CAPACITY_ALLOC_V1 판정 논리 (2026-09-08 · freeze).

사전등록: `docs/preregistration/WVR_CAPACITY_ALLOC_V1_2026-09-08.md`

```
treatment 변수   default allocator  vs  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
그 외 전부       C01과 동일 (모델·snapshot·dtype·attn·표집·해상도·프롬프트·생성)
A1 실행 조건     A0 == CAPACITY_FAIL일 때만
primary 비교     A0 vs A1  — historical C01과 A1을 직접 비교하지 않는다
```

GPU 없이 검증 가능한 순수 논리만 둔다. 실행은 `scripts/wvr_capacity_alloc.py`.
"""

ARM_A0 = "A0"
ARM_A1 = "A1"
ARMS = (ARM_A0, ARM_A1)

ALLOC_ENV = "PYTORCH_CUDA_ALLOC_CONF"
A1_ALLOC_VALUE = "expandable_segments:True"

# 실행 환경 comparability gate다. semantic threshold가 아니다.
COMPARABILITY_THRESHOLD_MIB = 128

COMPARABLE = "COMPARABLE"
COMPARISON_INVALID = "COMPARISON_INVALID"

ARM_PASS = "CAPACITY_PASS"
ARM_FAIL = "CAPACITY_FAIL"
ARM_DEFECT = "IMPLEMENTATION_DEFECT"

A1_NOT_RUN = "NOT_RUN_BY_PREREG_RULE"

# treatment가 실제로 적용됐는지 · workload가 정말 같았는지는 capacity 판정과 별개다.
TREATMENT_NOT_APPLIED = "TREATMENT_NOT_APPLIED"
WORKLOAD_MISMATCH = "WORKLOAD_MISMATCH"

# allocator 경고로 볼 문자열. 로그에 있으면 capacity 판정을 하지 않는다.
ALLOCATOR_WARNING_MARKERS = ("expandable_segments", "PYTORCH_CUDA_ALLOC_CONF",
                             "allocator")

# A0·A1에서 실측값까지 같아야 인과 비교가 성립한다(설정 일치만으로는 부족하다).
IDENTITY_METRICS = ("delivered_frame_count", "frame_size",
                    "frame_times_first_last", "video_token_count",
                    "input_token_count", "requested_timestamps")

EVENT_CAPACITY_PASS = "CAPACITY_PASS"
EVENT_CAPACITY_FAIL = "CAPACITY_FAIL"
EVENT_CONTROL_PASS = "CONTROL_PASS_CONFUND_FOUND"      # 사전등록 §19의 표기 그대로
EVENT_COMPARISON_INVALID = "COMPARISON_INVALID"
EVENT_DEFECT = "IMPLEMENTATION_DEFECT"
EVENT_VERDICTS = (EVENT_CAPACITY_PASS, EVENT_CAPACITY_FAIL, EVENT_CONTROL_PASS,
                  EVENT_COMPARISON_INVALID, EVENT_DEFECT)

SEMANTIC_RESULT = "NOT_EVALUATED"

# 이번 사건에서 손대지 않는 축. 이름만으로 실수를 잡기 위한 목록이다.
FROZEN_AXES = ("chunk_length", "fps", "frame_count", "resolution", "dtype",
               "quantization", "attn_implementation", "max_new_tokens",
               "prompt", "offload", "device_map")


class AllocError(RuntimeError):
    """사전등록 위반. 조용히 넘기지 않는다."""


def assert_fresh_process(cuda_initialized: bool) -> None:
    """CUDA context 초기화 뒤에는 allocator 환경변수의 의미가 불명확해진다."""
    if cuda_initialized:
        raise AllocError("CUDA가 이미 초기화됐다 — arm은 fresh process에서 돌린다")


def observed_allocator(env) -> str:
    return env.get(ALLOC_ENV, "")


def assert_allocator_env(arm: str, env) -> str:
    """A0은 expandable_segments가 없어야 하고, A1은 정확히 그 값이어야 한다."""
    if arm not in ARMS:
        raise AllocError("모르는 arm: %r" % arm)
    value = observed_allocator(env)
    if arm == ARM_A0:
        if "expandable_segments" in value:
            raise AllocError("A0(control)에 allocator 설정이 들어 있다: %r" % value)
        return value
    if value != A1_ALLOC_VALUE:
        raise AllocError("A1은 %s=%s 여야 한다 (관측: %r)"
                         % (ALLOC_ENV, A1_ALLOC_VALUE, value))
    return value


def treatment_applied(record) -> bool:
    """A1에서 expandable_segments가 실제로 segment에 반영됐는지."""
    observed = record.get("allocator_observed") or {}
    return bool(observed.get("expandable_segments_observed"))


def allocator_warnings(log_text: str) -> tuple:
    """로그에서 allocator 관련 경고 줄만 뽑는다."""
    lines = []
    for line in (log_text or "").splitlines():
        lowered = line.lower()
        if ("warn" in lowered or "error" in lowered) and any(
                marker.lower() in lowered for marker in ALLOCATOR_WARNING_MARKERS):
            lines.append(line.strip())
    return tuple(lines)


def completion_ok(record) -> bool:
    """PASS는 prefill 통과가 아니라 generate 정상 종료다."""
    metrics = record.get("metrics") or {}
    return (record.get("verdict") == "PASS"
            and metrics.get("oom") is False
            and metrics.get("generation_completed") is True
            and metrics.get("finish_reason") in ("EOS", "MAX_NEW_TOKENS")
            and (metrics.get("generated_token_count") or 0) > 0)


def workload_identity(a0_record, a1_record) -> tuple:
    """실측 workload가 다른 항목. 하나라도 다르면 인과 비교를 하지 않는다."""
    differing = list(workload_equal(a0_record, a1_record))
    left, right = a0_record["metrics"], a1_record["metrics"]
    differing.extend(key for key in IDENTITY_METRICS
                     if left.get(key) != right.get(key))
    if (a0_record.get("frame_indices_first_last")
            != a1_record.get("frame_indices_first_last")):
        differing.append("frame_indices_first_last")
    return tuple(sorted(set(differing)))


def assert_idle(snapshot) -> None:
    """다른 job이 GPU를 쓰고 있으면 baseline이 오염된다."""
    count = snapshot.get("compute_process_count")
    if count is None:
        raise AllocError("GPU compute process 수를 기록하지 못했다")
    if int(count) != 0:
        raise AllocError("GPU에 연산 프로세스가 %s개 있다" % count)


def assert_a1_allowed(a0_record) -> None:
    """A0가 통과했으면 A1을 돌리지 않는다(사전등록 §10 Case A)."""
    if a0_record is None:
        raise AllocError("A0 결과가 없다 — A1을 먼저 돌릴 수 없다")
    verdict = arm_verdict(a0_record)
    if verdict != ARM_FAIL:
        raise AllocError("A0가 %s다 — A1은 %s" % (verdict, A1_NOT_RUN))


def assert_once(exists: bool, arm: str) -> None:
    if exists:
        raise AllocError("%s 산출물이 이미 있다 — arm은 정확히 1회다" % arm)


def arm_verdict(record) -> str:
    """arm 하나의 판정. PASS는 generate 완주까지 확인한다."""
    verdict = record.get("verdict")
    if verdict == "PASS":
        return ARM_PASS if completion_ok(record) else ARM_DEFECT
    if verdict == "CAPACITY_FAIL":
        return ARM_FAIL
    return ARM_DEFECT


def a1_status(record, log_text: str = "") -> str:
    """A1이 capacity 판정 자격을 갖췄는지. 못 갖추면 그 사유가 상태다."""
    if not treatment_applied(record):
        return TREATMENT_NOT_APPLIED
    if allocator_warnings(log_text):
        return TREATMENT_NOT_APPLIED
    return arm_verdict(record)


def baseline_delta_mib(a0_record, a1_record) -> float:
    left = a0_record["metrics"]["baseline_vram_mib"]
    right = a1_record["metrics"]["baseline_vram_mib"]
    return round(abs(float(left) - float(right)), 1)


def comparability(delta_mib: float) -> str:
    return (COMPARABLE if delta_mib <= COMPARABILITY_THRESHOLD_MIB
            else COMPARISON_INVALID)


def event_verdict(a0_record, a1_record=None, log_text: str = "") -> str:
    """사건 전체 판정. 사전등록 §10·§11·§19의 규칙 그대로."""
    a0 = arm_verdict(a0_record)
    if a0 == ARM_DEFECT:
        return EVENT_DEFECT
    if a0 == ARM_PASS:
        if a1_record is not None:
            raise AllocError("A0가 통과했는데 A1 결과가 있다 — 사전등록 위반")
        return EVENT_CONTROL_PASS
    if a1_record is None:
        raise AllocError("A0가 실패했다 — A1 없이는 사건을 닫지 않는다")
    a1 = a1_status(a1_record, log_text)
    if a1 in (TREATMENT_NOT_APPLIED, ARM_DEFECT):
        return EVENT_DEFECT
    if workload_identity(a0_record, a1_record):
        return EVENT_COMPARISON_INVALID          # WORKLOAD_MISMATCH
    if a1 == ARM_FAIL:
        return EVENT_CAPACITY_FAIL
    delta = baseline_delta_mib(a0_record, a1_record)
    if comparability(delta) == COMPARISON_INVALID:
        return EVENT_COMPARISON_INVALID
    return EVENT_CAPACITY_PASS


def comparison_invalid_reason(a0_record, a1_record) -> str:
    """COMPARISON_INVALID의 사유를 구분해 남긴다. 없으면 빈 문자열."""
    if workload_identity(a0_record, a1_record):
        return WORKLOAD_MISMATCH
    if comparability(baseline_delta_mib(a0_record, a1_record))             == COMPARISON_INVALID:
        return "BASELINE_DELTA_ABOVE_GATE"
    return ""


def parse_oom(message: str) -> dict:
    """OOM 메시지에서 요청량·잔여량을 뽑는다. 없으면 None으로 남긴다."""
    import re

    request = re.search(r"Tried to allocate ([0-9.]+) ([KMG])iB", message or "")
    free = re.search(r"([0-9.]+) ([KMG])iB is free", message or "")
    scale = {"K": 1 / 1024, "M": 1.0, "G": 1024.0}

    def value(match):
        if not match:
            return None
        return round(float(match.group(1)) * scale[match.group(2)], 2)

    return {"oom_request_mib": value(request), "oom_free_mib": value(free)}


def workload_equal(a0_record, a1_record) -> tuple:
    """두 arm의 workload가 정말 같은지. 다른 키를 돌려준다(빈 tuple이면 동일)."""
    ignore = {"device_map"}                     # None 직렬화가 양쪽 동일하므로 무해
    left, right = a0_record["requested"], a1_record["requested"]
    differing = [key for key in sorted(set(left) | set(right))
                 if key not in ignore and left.get(key) != right.get(key)]
    for key in ("chunk", "prompt_contract", "prompt_hashes"):
        if a0_record.get(key) != a1_record.get(key):
            differing.append(key)
    return tuple(differing)
