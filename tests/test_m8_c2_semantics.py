"""C2 판정 집계가 사전등록과 같은지 — **구현 정합성 검사, 새 방법론 아님.**

라벨링을 시작하기 전에 한 번 잠근다. 판정 시점에 즉석으로 `mean`을 쓰거나 다른
quantile 규칙을 쓰면 사전등록과 어긋나고, 그 어긋남은 수치를 본 뒤에는 고치기 어렵다.

동결 근거
```
M8_구조변경_사전등록_2026-08-16.md §2-3   C1 catastrophic 0편 · C2 Event Recall
                                        **중앙값** ≥ 0.70 · C3 Compression ≤ 2.0
                                        판정 표본 8~12편
M8_event지표_보충_2026-08-18.md          IoU θ 세 개 전부 보고 · 1:1 매칭
```
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import m8_metrics as M                                          # noqa: E402

PREREG = ROOT / "docs/preregistration/M8_구조변경_사전등록_2026-08-16.md"


# ------------------------------------------------------------ 사전등록 문언

def test_prereg_still_says_median_and_070():
    """문서가 바뀌면 이 테스트가 먼저 깨진다 — 임계·통계량은 동결이다."""
    t = PREREG.read_text(encoding="utf-8")
    assert "Event Recall 중앙값 ≥ **0.70**" in t
    assert "평균이 아니라 중앙값" in t
    assert "Catastrophic failure **0편**" in t
    assert "Compression ≤ **2.0**" in t


def test_prereg_sample_size_is_eight_to_twelve():
    t = PREREG.read_text(encoding="utf-8")
    assert re.search(r"8~12편", t)


# ------------------------------------------------------------ C2 집계 의미

def test_c2_uses_median_not_mean():
    """평균과 중앙값이 갈리는 입력에서 중앙값 쪽을 골라야 한다."""
    v = [0.10, 0.20, 0.75, 0.80]        # 평균 0.4625 · 중앙값 0.475
    assert M.c2_statistic(v) == 0.475


def test_median_for_n8_is_mean_of_4th_and_5th():
    v = [0.10, 0.20, 0.30, 0.40, 0.60, 0.70, 0.80, 0.90]
    assert M.c2_statistic(v) == pytest.approx((0.40 + 0.60) / 2)


def test_c2_statistic_ignores_input_order():
    a = [0.9, 0.1, 0.5, 0.3, 0.7, 0.2, 0.8, 0.4]
    assert M.c2_statistic(a) == M.c2_statistic(sorted(a))


def test_c2_statistic_is_none_when_nothing_measurable():
    """"중앙값 0.0"과 "측정 불가"는 다른 상태다."""
    assert M.c2_statistic([]) is None
    assert M.c2_statistic([None, None]) is None


def test_c2_verdict_threshold_is_frozen_at_070():
    assert M.c2_verdict([0.70] * 8)["threshold"] == 0.70
    assert M.c2_verdict([0.70] * 8)["passed"] is True          # 경계값은 통과다(≥)
    assert M.c2_verdict([0.69] * 8)["passed"] is False


def test_c2_verdict_reports_statistic_name_and_n():
    out = M.c2_verdict([0.5, 0.6, 0.7, 0.8, 0.9, 0.4, 0.3, 0.2])
    assert out["statistic"] == "median" and out["n_videos"] == 8


def test_c2_verdict_passed_is_none_when_unmeasurable():
    assert M.c2_verdict([])["passed"] is None


# ------------------------------------------------------------ 매칭·θ 의미

def test_iou_thetas_include_03_and_are_all_reported():
    assert 0.3 in M.IOU_THETAS
    out = M.temporal_event_recall([{"span": [0, 4]}], [{"span": [0, 4]}])
    assert set(out) == {f"temporal_event_recall@IoU>={t}" for t in M.IOU_THETAS}


def test_event_matching_is_one_to_one_not_overlap_coverage():
    """거대한 span 하나가 정답 사건 둘을 덮어 recall을 부풀리면 안 된다."""
    refs = [{"span": [0, 4]}, {"span": [10, 14]}]
    gens = [{"span": [0, 14]}]                       # 통째로 덮는 사건 하나
    out = M.temporal_event_recall(refs, gens)
    assert out["temporal_event_recall@IoU>=0.3"] < 1.0


def test_zero_overlap_pairs_are_not_matched():
    refs = [{"span": [0, 4]}]
    gens = [{"span": [50, 54]}]
    assert M.temporal_event_recall(refs, gens)["temporal_event_recall@IoU>=0.3"] == 0.0


def test_recall_is_none_when_reference_is_absent():
    out = M.temporal_event_recall([], [{"span": [0, 4]}])
    assert all(v is None for v in out.values())


def test_iou_counts_both_endpoints():
    """양 끝 포함 규약 — off-by-one이면 θ 경계에서 판정이 조용히 뒤집힌다."""
    assert M.temporal_iou([0, 4], [0, 4]) == 1.0
    assert M.temporal_iou([0, 4], [5, 9]) == 0.0
    assert M.temporal_iou([0, 9], [0, 4]) == pytest.approx(5 / 10)
