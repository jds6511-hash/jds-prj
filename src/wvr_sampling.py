"""WVR_CAPACITY_SAMPLING_V1 계약 (2026-09-08 · freeze).

사전등록: `docs/preregistration/WVR_CAPACITY_SAMPLING_V1_2026-09-08.md`

```
유일한 변경   fps 0.5 → 0.25 (300 → 150프레임 · 시각 0,4,8,…,596)
parent control  A0 (default allocator · 0.5 fps · CAPACITY_FAIL) — 재실행하지 않는다
allocator      default로 되돌린다 — expandable과 sampling을 같이 바꾸면 원인이 섞인다
해상도         512×288 동결 (축소하지 않는다)
```

`wvr_contract`의 `CHUNK_FPS`는 C01·A0/A1의 동결값이므로 **건드리지 않는다.**
B arm 값은 여기 따로 둔다.
"""
import wvr_contract as contract

ARM_B = "B"

SAMPLING_FPS = 0.25                 # 4.0초마다 1프레임
SAMPLING_MAX_FRAMES = 150

# 해상도는 이 사건에서 바꾸지 않는다. 앞서 후보로 적었던 384×216은 잘못이다 —
# 216 / 32 = 6.75로 processor의 32픽셀 격자를 만족하지 않는다(2026-09-08 정정).
FRAME_WIDTH = contract.FRAME_WIDTH
FRAME_HEIGHT = contract.FRAME_HEIGHT

# 계산값이다. 실측은 probe가 기록한다.
EXPECTED_FRAMES = 150
EXPECTED_VIDEO_TOKENS = 10800       # 150 / temporal 2 × 144

# A0 대비 달라져도 되는 항목. 이 밖의 차이는 단일 변경 위반이다.
ALLOWED_REQUEST_DIFFERENCES = ("chunk_fps",)
ALLOWED_METRIC_DIFFERENCES = (
    "requested_timestamps", "delivered_frame_count", "frame_times_first_last",
    "video_token_count", "input_token_count", "baseline_vram_mib",
    "baseline_vram_free_mib", "post_load_vram_mib", "peak_vram_allocated_mib",
    "peak_vram_reserved_mib", "device_peak_used_mib",
    "reserved_minus_allocated_mib", "load_wall_sec", "video_process_wall_sec",
    "infer_wall_sec", "total_wall_sec", "oom", "oom_request_mib",
    "oom_free_mib", "generation_completed", "finish_reason",
    "generated_token_count", "output_token_count", "offloaded_params",
    "frame_size",
)


class SamplingError(RuntimeError):
    """사전등록 위반. 조용히 넘기지 않는다."""


def sampling_frames(chunk) -> tuple:
    """B arm 표집 시각. 구간·해상도·모델은 그대로다."""
    return contract.frame_timestamps(chunk["start_sec"], chunk["end_sec"],
                                     SAMPLING_FPS, SAMPLING_MAX_FRAMES)


def assert_default_allocator(env) -> str:
    """allocator는 default다 — A1의 treatment를 물려받지 않는다."""
    value = env.get("PYTORCH_CUDA_ALLOC_CONF", "")
    if "expandable_segments" in value:
        raise SamplingError("B arm은 default allocator다 (관측: %r)" % value)
    return value


def assert_resolution_frozen(record) -> None:
    size = record["requested"]["frame_size"]
    if tuple(size) != (FRAME_WIDTH, FRAME_HEIGHT):
        raise SamplingError("해상도가 바뀌었다: %r" % (size,))


def single_change(control_record, arm_record) -> tuple:
    """허용 목록 밖에서 달라진 항목. 빈 tuple이어야 단일 변경이다."""
    differing = []
    left, right = control_record["requested"], arm_record["requested"]
    for key in sorted(set(left) | set(right)):
        if key in ALLOWED_REQUEST_DIFFERENCES:
            continue
        if left.get(key) != right.get(key):
            differing.append("requested.%s" % key)
    for key in ("chunk", "prompt_contract", "prompt_hashes"):
        if control_record.get(key) != arm_record.get(key):
            differing.append(key)
    lmetrics, rmetrics = control_record["metrics"], arm_record["metrics"]
    for key in sorted(set(lmetrics) | set(rmetrics)):
        if key in ALLOWED_METRIC_DIFFERENCES:
            continue
        if lmetrics.get(key) != rmetrics.get(key):
            differing.append("metrics.%s" % key)
    return tuple(differing)


def sampling_changed(control_record, arm_record) -> bool:
    """표집이 실제로 줄었는지 — 안 줄었으면 실험이 성립하지 않는다."""
    return (arm_record["metrics"]["delivered_frame_count"]
            < control_record["metrics"]["delivered_frame_count"]
            and arm_record["requested"]["chunk_fps"] == SAMPLING_FPS)


def token_reduction(control_record, arm_record) -> dict:
    """실측 토큰 감소. 계산값이 아니라 processor 출력이다."""
    left, right = control_record["metrics"], arm_record["metrics"]
    return {
        "video_tokens": [left["video_token_count"], right["video_token_count"]],
        "input_tokens": [left["input_token_count"], right["input_token_count"]],
        "video_token_delta": right["video_token_count"]
        - left["video_token_count"],
        "input_token_delta": right["input_token_count"]
        - left["input_token_count"],
    }
