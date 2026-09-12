"""WVR_CHUNK_OVERVIEW_V2 — C01에서 검증한 관찰 구조를 chunk 단위로 확장한다.

새 구조 연구가 아니다. **관찰 계약·프롬프트·스키마·모델·표집을 전부 V2에서
그대로 가져오고, 바뀌는 것은 시간 범위뿐이다.**

```
동결 유지   Qwen3-VL model/revision · visual observation prompt/schema
            window 48초 · stride 24초 · 0.5fps · 창당 24프레임
            broad visual summary contract
변하는 것   chunk 범위 [start, end)
```

chunk 계획은 `wvr_contract.chunk_plan(2424.186485)`이 내는 C01~C05 그대로다.
C01은 `runs/wvr_video_overview_preview_v2/`에 이미 있으므로 **재실행하지 않는다.**
"""
from __future__ import annotations

import wvr_contract as contract
import wvr_shadow_v1 as shadow
import wvr_video_overview_preview_v2 as ov

EVENT = "WVR_CHUNK_OVERVIEW_V2"
PREREG = ("docs/preregistration/"
          "WVR_CHUNK_OVERVIEW_V2_C02_C05_2026-09-13.md")

VIDEO_DURATION_SEC = 2424.186485
VIDEO_SHA256 = ov.VIDEO_SHA256

# 동결 기하 — shadow에서 가져온다. 여기서 새로 정하지 않는다.
WINDOW_SEC = shadow.WINDOW_SEC        # 48.0
STRIDE_SEC = shadow.STRIDE_SEC        # 24.0
FRAMES_PER_WINDOW = shadow.FRAMES_PER_WINDOW   # 24
SAMPLING_FPS = shadow.SAMPLING_FPS    # 0.5

# C01은 선행 사건 산출물을 쓴다. 이번 사건의 실행 대상은 C02~C05다.
EXECUTED_CHUNK_IDS = ("C02", "C03", "C04", "C05")
FROZEN_C01_RUNS = "runs/wvr_video_overview_preview_v2"

# 창 개수는 범위에서 결정된다. 결과를 보고 바꾸지 않으려고 여기 박는다.
EXPECTED_WINDOW_COUNT = {"C01": 24, "C02": 24, "C03": 24, "C04": 24, "C05": 20}


class ChunkOverviewError(RuntimeError):
    """chunk 확장 계약 위반. 조용히 넘어가지 않는다."""


def chunk_plan() -> list[dict]:
    """동결된 C01~C05. `wvr_contract.chunk_plan`이 유일한 출처다."""
    return contract.chunk_plan(VIDEO_DURATION_SEC)


def chunk_by_id(chunk_id: str) -> dict:
    for row in chunk_plan():
        if row["chunk_id"] == chunk_id:
            return row
    raise ChunkOverviewError("모르는 chunk: %r" % chunk_id)


def windows(chunk_id: str) -> list[dict]:
    """chunk 안의 48초 창 · 24초 stride. 창이 chunk 끝을 넘지 않는다.

    `shadow.windows()`와 같은 규칙이되 시작점이 chunk start다. chunk 끝에
    48초가 안 남으면 그 꼬리는 **창을 만들지 않는다** — 창 길이를 줄여
    다른 창과 비교 불가능한 관찰을 만들지 않기 위해서다. 덮이지 않은 꼬리
    길이는 `uncovered_tail_sec`으로 기록한다.
    """
    chunk = chunk_by_id(chunk_id)
    start_sec, end_sec = float(chunk["start_sec"]), float(chunk["end_sec"])
    rows, start, index = [], start_sec, 0
    while start + WINDOW_SEC <= end_sec + 1e-9:
        rows.append({"window_id": "W%02d" % index, "index": index,
                     "start_sec": round(start, 3),
                     "end_sec": round(start + WINDOW_SEC, 3)})
        index += 1
        start = round(start + STRIDE_SEC, 3)
    expected = EXPECTED_WINDOW_COUNT[chunk_id]
    if len(rows) != expected:
        raise ChunkOverviewError("%s 창 개수가 %d가 아니다: %d"
                                 % (chunk_id, expected, len(rows)))
    if rows[0]["start_sec"] != round(start_sec, 3):
        raise ChunkOverviewError("%s 첫 창이 chunk 시작에서 출발하지 않는다" % chunk_id)
    if rows[-1]["end_sec"] > end_sec + 1e-9:
        raise ChunkOverviewError("%s 마지막 창이 chunk 끝을 넘는다" % chunk_id)
    return rows


def uncovered_tail_sec(chunk_id: str) -> float:
    """창이 덮지 못한 chunk 꼬리(초). C05에서만 0이 아니다."""
    chunk = chunk_by_id(chunk_id)
    return round(float(chunk["end_sec"]) - windows(chunk_id)[-1]["end_sec"], 6)


def segments(chunk_id: str) -> list[dict]:
    """V2 runner가 받는 plan 형태. `ov.segments()`와 같은 구조다."""
    rows = []
    for index, window in enumerate(windows(chunk_id), start=1):
        rows.append({
            "segment_id": "S%02d" % index,
            "start_sec": float(window["start_sec"]),
            "end_sec": float(window["end_sec"]),
            "frame_times": [float(v) for v in shadow.frame_times(window)],
        })
    return rows


def plan_geometry(chunk_id: str) -> dict:
    """계측·gate용 요약. 판정하지 않는다."""
    rows = segments(chunk_id)
    chunk = chunk_by_id(chunk_id)
    return {
        "chunk_id": chunk_id,
        "chunk_start_sec": float(chunk["start_sec"]),
        "chunk_end_sec": float(chunk["end_sec"]),
        "window_count": len(rows),
        "window_sec": WINDOW_SEC,
        "stride_sec": STRIDE_SEC,
        "sampling_fps": SAMPLING_FPS,
        "frames_per_window": FRAMES_PER_WINDOW,
        "frame_count": sum(len(r["frame_times"]) for r in rows),
        "first_window": [rows[0]["start_sec"], rows[0]["end_sec"]],
        "last_window": [rows[-1]["start_sec"], rows[-1]["end_sec"]],
        "uncovered_tail_sec": uncovered_tail_sec(chunk_id),
    }
