"""WHOLE_VIDEO_REPORT_LIGHT_V1 실행 계약 (2026-09-08 · freeze).

사전등록: `docs/preregistration/WHOLE_VIDEO_REPORT_LIGHT_V1_2026-09-08.md`

```
chunk_length   600.0초        overlap  120.0초        stride 480.0초
chunk fps      0.5            sparse fps 0.05
frame 크기      512×288        (32의 배수 · 16:9 · bicubic)
dtype          bfloat16       quantization 없음      device cuda:0 고정
```

여기 있는 값은 **결과를 보기 전에 고정**됐다. OOM이 나면 chunk를 줄이지 않고
`CAPACITY_FAIL`로 기록하고 멈춘다 — 길이를 줄여 성공시키면 capacity 측정과
parameter tuning이 섞인다.
"""

# ── 모델 ────────────────────────────────────────────────────────────────
MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"
MODEL_REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
DTYPE = "bfloat16"
QUANTIZATION = None
DEVICE = "cuda:0"
ATTN_IMPLEMENTATION = "sdpa"

# device_map을 쓰지 않는다. accelerate가 CPU·디스크로 offload하면 24GB를
# 넘는 구성이 조용히 통과해 capacity 판정이 무의미해진다.
DEVICE_MAP = None

# ── 청킹 ────────────────────────────────────────────────────────────────
CHUNK_LENGTH_SEC = 600.0
CHUNK_OVERLAP_SEC = 120.0
CHUNK_STRIDE_SEC = CHUNK_LENGTH_SEC - CHUNK_OVERLAP_SEC     # 480.0

# ── 프레임 표집 ─────────────────────────────────────────────────────────
CHUNK_FPS = 0.5                 # 2.0초마다 1프레임 → 10분에 300프레임
SPARSE_FPS = 0.05               # 20.0초마다 1프레임
CHUNK_MAX_FRAMES = 300
SPARSE_MAX_FRAMES = 128
FRAME_WIDTH = 512               # 32 × 16
FRAME_HEIGHT = 288              # 32 × 9   (정확히 16:9)
FRAME_RESAMPLE = "bicubic"

# processor 실측값. 토큰 격자는 patch 16 × merge 2 = 32px, 시간축은 2프레임이다.
PATCH_SIZE = 16
MERGE_SIZE = 2
TEMPORAL_PATCH_SIZE = 2

# 프레임은 파이프라인이 뽑는다. processor가 다시 표집·리사이즈하지 않는다.
DO_SAMPLE_FRAMES = False
DO_RESIZE = False

# ── 생성 ────────────────────────────────────────────────────────────────
DO_SAMPLE = False
NUM_BEAMS = 1
MAX_NEW_TOKENS = 1024
REPETITION_PENALTY = 1.0

# ── 단계 상태 ───────────────────────────────────────────────────────────
STAGE_OK = "OK"
STAGE_PARSE_FAILURE = "PARSE_FAILURE"
STAGE_CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
STAGE_CAPACITY_FAIL = "CAPACITY_FAIL"
STAGE_RUNTIME_FAILURE = "RUNTIME_FAILURE"
STAGE_STATUSES = (STAGE_OK, STAGE_PARSE_FAILURE, STAGE_CONTRACT_VIOLATION,
                  STAGE_CAPACITY_FAIL, STAGE_RUNTIME_FAILURE)

# 실패는 실패로 기록한다. 아래 대체 경로는 존재하지 않는다.
NO_FALLBACK = ("concat", "retry", "chunk 축소", "다른 모델", "STT 대체")

# ── video-only 입력 정책 ────────────────────────────────────────────────
FORBIDDEN_INPUTS = (
    "raw_stt", "sanitized_stt", "stt_utterances", "stt_transcript",
    "episode_summary", "aar_canonical", "existing_report", "submission_hwpx",
    "human_report", "youtube_title", "youtube_description",
    "manual_annotation", "caption",
)


class ContractError(ValueError):
    """계약 위반. 조용히 넘기지 않는다."""


def assert_video_only_inputs(payload) -> None:
    """영상 이해 단계 입력에 금지 채널이 섞였는지 본다(키 이름 기준)."""
    keys = set(payload) if isinstance(payload, dict) else set(payload)
    for key in sorted(keys):
        lowered = str(key).lower()
        for banned in FORBIDDEN_INPUTS:
            if banned in lowered:
                raise ContractError("금지된 입력 채널: %s" % key)


def chunk_plan(duration_sec: float) -> tuple:
    """결정적 chunk 목록. 앞 chunk에 완전히 덮이는 꼬리 chunk는 만들지 않는다."""
    if duration_sec <= 0:
        raise ContractError("영상 길이가 0 이하다: %r" % duration_sec)
    plan, start, index = [], 0.0, 0
    while start < duration_sec:
        end = round(min(start + CHUNK_LENGTH_SEC, duration_sec), 3)
        if plan and end <= plan[-1]["end_sec"]:
            break                                    # 이미 덮인 꼬리
        index += 1
        plan.append({"chunk_id": "C%02d" % index, "start_sec": round(start, 3),
                     "end_sec": end})
        start += CHUNK_STRIDE_SEC
    return tuple(plan)


def overlap_pairs(plan) -> tuple:
    """인접 chunk의 겹치는 시간대. merge 단계의 입력 범위다."""
    pairs = []
    for left, right in zip(plan, plan[1:]):
        start, end = right["start_sec"], min(left["end_sec"], right["end_sec"])
        if end > start:
            pairs.append({"left": left["chunk_id"], "right": right["chunk_id"],
                          "overlap_start": round(start, 3),
                          "overlap_end": round(end, 3)})
    return tuple(pairs)


def frame_timestamps(start_sec: float, end_sec: float, fps: float,
                     max_frames: int) -> tuple:
    """표집 시각. 구간 시작에서 1/fps 간격으로 끝 이전까지."""
    if fps <= 0:
        raise ContractError("fps가 0 이하다: %r" % fps)
    if end_sec <= start_sec:
        raise ContractError("빈 구간이다: %r~%r" % (start_sec, end_sec))
    step = 1.0 / fps
    stamps, index = [], 0
    while True:
        stamp = start_sec + index * step
        if stamp >= end_sec - 1e-9:
            break
        stamps.append(round(stamp, 3))
        index += 1
    if len(stamps) > max_frames:
        raise ContractError("표집 프레임 %d개가 상한 %d개를 넘는다"
                            % (len(stamps), max_frames))
    return tuple(stamps)


def chunk_frames(chunk) -> tuple:
    return frame_timestamps(chunk["start_sec"], chunk["end_sec"], CHUNK_FPS,
                            CHUNK_MAX_FRAMES)


def sparse_frames(duration_sec: float) -> tuple:
    return frame_timestamps(0.0, duration_sec, SPARSE_FPS, SPARSE_MAX_FRAMES)
