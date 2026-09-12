"""WVR_CHUNK_OVERVIEW_V2 (C02~C05) 계약 테스트.

이번 사건은 **새 구조 연구가 아니라 C01 구조의 범위 확장**이다. 따라서 테스트의
중심은 "C01과 같은 관찰 계약인가"이지 "새 기하가 좋은가"가 아니다.
모델을 올리지 않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_chunk_overview_v2 as cv  # noqa: E402
import wvr_shadow_v1 as shadow  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402

FROZEN_C01_PLAN = (ROOT / "runs" / "wvr_video_overview_preview_v2" /
                   "video_overview_v2_segments.json")


# ── 동결 유지: 기하 상수를 이 모듈이 새로 정하지 않는다 ─────────────
def test_wvr_cov_01_geometry_constants_come_from_the_frozen_shadow_contract():
    assert cv.WINDOW_SEC == shadow.WINDOW_SEC == 48.0
    assert cv.STRIDE_SEC == shadow.STRIDE_SEC == 24.0
    assert cv.FRAMES_PER_WINDOW == shadow.FRAMES_PER_WINDOW == 24
    assert cv.SAMPLING_FPS == shadow.SAMPLING_FPS == 0.5


def test_wvr_cov_02_video_identity_is_the_frozen_source():
    assert cv.VIDEO_SHA256 == ov.VIDEO_SHA256
    assert cv.VIDEO_DURATION_SEC == 2424.186485


# ── chunk plan은 wvr_contract가 유일한 출처다 ──────────────────────
def test_wvr_cov_03_chunk_plan_is_the_frozen_c01_to_c05():
    rows = cv.chunk_plan()
    assert [r["chunk_id"] for r in rows] == ["C01", "C02", "C03", "C04", "C05"]
    assert [r["start_sec"] for r in rows] == [0.0, 480.0, 960.0, 1440.0, 1920.0]
    assert rows[-1]["end_sec"] == pytest.approx(2424.186, abs=1e-3)


def test_wvr_cov_04_unknown_chunk_is_rejected():
    with pytest.raises(cv.ChunkOverviewError):
        cv.chunk_by_id("C06")


# ── 핵심: C01 창 일정을 그대로 재현한다 ────────────────────────────
@pytest.mark.skipif(not FROZEN_C01_PLAN.exists(), reason="frozen C01 plan 미존재")
def test_wvr_cov_05_builder_reproduces_the_frozen_c01_plan_exactly():
    frozen = json.loads(FROZEN_C01_PLAN.read_text(encoding="utf-8"))
    assert cv.segments("C01") == frozen


# ── 창 기하 ────────────────────────────────────────────────────────
def test_wvr_cov_06_window_counts_are_frozen_per_chunk():
    for chunk_id, expected in cv.EXPECTED_WINDOW_COUNT.items():
        assert len(cv.windows(chunk_id)) == expected


def test_wvr_cov_07_every_window_is_48_seconds_on_a_24_second_grid():
    for chunk_id in cv.EXPECTED_WINDOW_COUNT:
        rows = cv.windows(chunk_id)
        base = rows[0]["start_sec"]
        for i, row in enumerate(rows):
            assert row["start_sec"] == pytest.approx(base + i * 24.0)
            assert row["end_sec"] - row["start_sec"] == pytest.approx(48.0)


def test_wvr_cov_08_no_window_crosses_its_chunk_end():
    for chunk_id in cv.EXPECTED_WINDOW_COUNT:
        end = cv.chunk_by_id(chunk_id)["end_sec"]
        assert cv.windows(chunk_id)[-1]["end_sec"] <= end + 1e-9


def test_wvr_cov_09_only_c05_has_an_uncovered_tail_and_it_is_under_one_frame_step():
    tails = {c: cv.uncovered_tail_sec(c) for c in cv.EXPECTED_WINDOW_COUNT}
    assert [tails[c] for c in ("C01", "C02", "C03", "C04")] == [0.0, 0.0, 0.0, 0.0]
    assert 0 < tails["C05"] < 1.0 / cv.SAMPLING_FPS   # 프레임 한 칸보다 짧다


def test_wvr_cov_10_frame_times_are_24_per_window_and_stay_inside_it():
    for chunk_id in cv.EXPECTED_WINDOW_COUNT:
        for row in cv.segments(chunk_id):
            times = row["frame_times"]
            assert len(times) == 24
            assert times[0] == row["start_sec"]
            assert times[-1] < row["end_sec"]
            steps = {round(b - a, 6) for a, b in zip(times, times[1:])}
            assert steps == {2.0}


def test_wvr_cov_11_segment_ids_are_contiguous_from_s01():
    for chunk_id in cv.EXPECTED_WINDOW_COUNT:
        rows = cv.segments(chunk_id)
        assert [r["segment_id"] for r in rows] == \
            ["S%02d" % i for i in range(1, len(rows) + 1)]


# ── C01은 이번 사건의 실행 대상이 아니다 ───────────────────────────
def test_wvr_cov_12_c01_is_not_re_executed_in_this_event():
    assert cv.EXECUTED_CHUNK_IDS == ("C02", "C03", "C04", "C05")
    assert "C01" not in cv.EXECUTED_CHUNK_IDS


# ── chunk 간 겹침이 동결 계획대로 120초다 ──────────────────────────
def test_wvr_cov_13_adjacent_chunks_overlap_by_120_seconds():
    rows = cv.chunk_plan()
    for a, b in zip(rows, rows[1:]):
        assert a["end_sec"] - b["start_sec"] == pytest.approx(120.0)


# ── runner가 외부 plan을 받아들인다 (C01 기본 동작은 불변) ─────────
def test_wvr_cov_14_runner_accepts_an_injected_plan_and_defaults_to_c01():
    import inspect

    import wvr_video_overview_preview_v2_run as v2run
    sig = inspect.signature(v2run.run)
    assert "plan" in sig.parameters, "runner가 plan 주입을 받지 않는다"
    assert sig.parameters["plan"].default is None, \
        "plan 기본값이 None이 아니면 C01 기본 동작이 바뀐다"


def test_wvr_cov_15_plan_geometry_records_what_a_gate_needs():
    geo = cv.plan_geometry("C05")
    assert geo["window_count"] == 20
    assert geo["frame_count"] == 20 * 24
    assert geo["uncovered_tail_sec"] > 0
    assert geo["first_window"] == [1920.0, 1968.0]
    assert geo["last_window"] == [2376.0, 2424.0]
