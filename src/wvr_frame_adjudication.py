"""WVR_..._FRAME_ADJUDICATION_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_FRAME_ADJUDICATION_V1_2026-09-09.md`

```
목적    SHORT_WINDOW_V1의 material divergence 구간에서, S0에만 있는 DROP 프레임이
        report-material 정보를 실제로 제공했는지 프레임 실물로 판정한다
추론    없다. 모델을 부르지 않는다. 프레임 추출만 한다
프레임  모델이 실제로 받은 것과 같은 512×288 (probe.sample_frames 경로 동일)
아님    GT 라벨 작성이 아니다. 이 판정은 dev·test 라벨·질의에 쓰지 않는다
```
"""
import wvr_contract as contract
import wvr_density as density
import wvr_short_window as sw

EVENT = "WVR_SAMPLING_SEMANTIC_DENSITY_FRAME_ADJUDICATION_V1"
ARTIFACT_TAG = "frame_adjudication"

NEW_INFERENCE_ALLOWED = False
GT_LABEL_USE_ALLOWED = False
SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED = False
EVENT_EXTRACTION_APPROVED = False

FRAME_WIDTH = contract.FRAME_WIDTH
FRAME_HEIGHT = contract.FRAME_HEIGHT
STEP_SEC = 1.0 / density.REFERENCE_FPS          # 2.0 — S0 격자
KEEP_PERIOD_SEC = STEP_SEC * density.KEEP_STRIDE  # 4.0 — S1(KEEP) 격자

KEEP = "KEEP"        # S0·S1 공통 프레임
DROP = "DROP"        # S0에만 있는 프레임

# 리뷰어가 지목한 질문 3개 (원문 기준 · 동결)
QUESTIONS = (
    {"question_id": "Q1", "parent_window": "P2",
     "start_sec": 448.0, "end_sec": 464.0,
     "question": ("garment/pajama sequence가 계속되는가, 아니면 food-on-plate "
                  "장면으로 전환되는가?")},
    {"question_id": "Q2", "parent_window": "P3",
     "start_sec": 104.0, "end_sec": 128.0,
     "question": "potato peeling인가, potato ricer/pressing/mixing인가?"},
    {"question_id": "Q3", "parent_window": "P3",
     "start_sec": 128.0, "end_sec": 144.0,
     "question": "forming potato balls인가, gloves/mixing sequence인가?"},
)

# 질문별 프레임 수 (결과를 보기 전에 기록)
EXPECTED_FRAME_COUNTS = {"Q1": {KEEP: 4, DROP: 4},
                         "Q2": {KEEP: 6, DROP: 6},
                         "Q3": {KEEP: 4, DROP: 4}}

# 프레임 판정 어휘 (넷)
DROP_MATERIAL = "DROP_FRAMES_CARRY_MATERIAL_INFORMATION"
KEEP_SUFFICIENT = "KEEP_FRAMES_SUFFICIENT"
GENERATION_ERROR = "GENERATION_ERROR_NOT_SAMPLING"
FRAMES_INSUFFICIENT = "FRAMES_INSUFFICIENT"
FRAME_VERDICTS = (DROP_MATERIAL, KEEP_SUFFICIENT, GENERATION_ERROR,
                  FRAMES_INSUFFICIENT)

# 어느 arm의 주장이 프레임과 맞는지 (별도 축 · 사건 판정에 직접 쓰지 않는다)
S0_MATCHES = "S0_CLAIM_MATCHES"
S1_MATCHES = "S1_CLAIM_MATCHES"
BOTH_PARTIAL = "BOTH_MATCH_PARTIALLY"
NEITHER_MATCHES = "NEITHER_MATCHES"
CLAIM_MATCHES = (S0_MATCHES, S1_MATCHES, BOTH_PARTIAL, NEITHER_MATCHES)

PROBE_SAMPLING_LOSS = "SAMPLING_LOSS_CONFIRMED"
PROBE_GENERATION_ERROR = "GENERATION_ERROR_DOMINANT"
PROBE_KEEP_SUFFICIENT = "KEEP_SUFFICIENT_ON_TESTED_WINDOWS"
PROBE_INCONCLUSIVE = "INCONCLUSIVE"

ALLOWED_SCOPE = ("영상 1편의 48초 창 2개에서 뽑은 3개 구간(합계 56초)에 대한 판정이다. "
                 "다른 영상·다른 구간·전체 파이프라인으로 일반화하지 않는다.")


class FrameAdjudicationError(RuntimeError):
    """frame adjudication 계약 위반."""


def parent_window(question: dict) -> dict:
    for row in sw.EXPECTED_WINDOWS:
        if row[0] == question["parent_window"]:
            return {"window_id": row[0], "cluster_id": row[1],
                    "start_sec": row[2], "end_sec": row[3]}
    raise FrameAdjudicationError("모르는 부모 창: %r" % question["parent_window"])


def assert_inside_parent(question: dict) -> None:
    parent = parent_window(question)
    if question["start_sec"] < parent["start_sec"] or \
            question["end_sec"] > parent["end_sec"]:
        raise FrameAdjudicationError("질문 구간이 부모 창을 벗어난다: %s"
                                     % question["question_id"])


def frame_rows(question: dict) -> list:
    """S0 격자(2초) 프레임을 뽑고 KEEP·DROP을 **부모 창 기준**으로 표시한다."""
    assert_inside_parent(question)
    parent = parent_window(question)
    rows, time = [], float(question["start_sec"])
    while time < float(question["end_sec"]) - 1e-9:
        offset = round(time - parent["start_sec"], 6)
        role = KEEP if abs(offset % KEEP_PERIOD_SEC) < 1e-9 else DROP
        rows.append({"time_sec": round(time, 3), "role": role,
                     "parent_offset_sec": offset})
        time = round(time + STEP_SEC, 3)
    return rows


def counts(rows) -> dict:
    return {KEEP: sum(1 for row in rows if row["role"] == KEEP),
            DROP: sum(1 for row in rows if row["role"] == DROP)}


def assert_expected_counts(question_id: str, rows) -> None:
    observed = counts(rows)
    expected = EXPECTED_FRAME_COUNTS[question_id]
    if observed != expected:
        raise FrameAdjudicationError("%s 프레임 구성이 사전등록과 다르다: %r"
                                     % (question_id, observed))


def keep_times(rows) -> tuple:
    return tuple(row["time_sec"] for row in rows if row["role"] == KEEP)


def drop_times(rows) -> tuple:
    return tuple(row["time_sec"] for row in rows if row["role"] == DROP)


def assert_keep_matches_s1(question: dict, rows) -> None:
    """KEEP 프레임이 실제 S1 입력 시각의 부분집합인지 확인한다."""
    parent = parent_window(question)
    s1 = set(sw.arm_timestamps(parent, sw.ARM_S1))
    missing = [time for time in keep_times(rows) if time not in s1]
    if missing:
        raise FrameAdjudicationError("KEEP이 S1 입력에 없다: %r" % missing)
    s0 = set(sw.arm_timestamps(parent, sw.ARM_S0))
    stray = [row["time_sec"] for row in rows if row["time_sec"] not in s0]
    if stray:
        raise FrameAdjudicationError("S0 입력에 없는 프레임이다: %r" % stray)
    overlap = [time for time in drop_times(rows) if time in s1]
    if overlap:
        raise FrameAdjudicationError("DROP이 S1 입력에 있다: %r" % overlap)


def question_verdict_valid(verdict: str) -> bool:
    if verdict not in FRAME_VERDICTS:
        raise FrameAdjudicationError("모르는 프레임 판정값: %r" % verdict)
    return True


def probe_verdict(verdicts) -> str:
    """① 불충분 → ② DROP material → ③ 생성 오류 → ④ KEEP 충분."""
    values = list(verdicts)
    if len(values) != len(QUESTIONS):
        raise FrameAdjudicationError("질문 %d개의 판정이 필요하다"
                                     % len(QUESTIONS))
    for value in values:
        question_verdict_valid(value)
    if FRAMES_INSUFFICIENT in values:
        return PROBE_INCONCLUSIVE
    if DROP_MATERIAL in values:
        return PROBE_SAMPLING_LOSS
    if GENERATION_ERROR in values:
        return PROBE_GENERATION_ERROR
    return PROBE_KEEP_SUFFICIENT
