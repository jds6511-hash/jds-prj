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


# ---------------------------------------------- C1 · C3 (사전등록 문언만 보고 구현)
# 파일럿 산출물을 보면서 의미를 조정하지 않았다. 사전등록 §2-2·§2-3이 유일한 근거다.

def test_compression_is_sentences_over_reference_events():
    assert M.compression(6, 3) == 2.0
    assert M.compression(5, 4) == 1.25


def test_compression_is_none_when_no_reference_events():
    """정답 사건 0개는 0.0도 inf도 아니라 측정 불가다."""
    assert M.compression(10, 0) is None


def test_c1_counts_videos_not_sentences():
    """사전등록이 "발생 **영상 수**"로 정의했다."""
    out = M.c1_verdict([False, True, False, True])
    assert out["n_catastrophic_videos"] == 2 and out["n_videos"] == 4
    assert out["passed"] is False
    assert M.c1_verdict([False] * 8)["passed"] is True


def test_c1_kinds_are_the_three_preregistered_ones():
    assert M.CATASTROPHIC_KINDS == ("language_drift", "early_stop", "repetition_loop")
    t = PREREG.read_text(encoding="utf-8")
    assert "다른 언어 이탈·조기 종료·반복 루프" in t


def test_c3_refuses_to_pick_an_aggregation_silently():
    """사전등록에 C3 집계 통계량이 없다 — 짐작해 넣으면 코드가 규칙을 새로 만든다."""
    with pytest.raises(M.GateSpecError, match="사전등록에 없다"):
        M.c3_verdict([1.0, 2.5, 1.2])


def test_c3_threshold_is_frozen_at_20():
    assert M.c3_verdict([1.9] * 8, statistic="median")["passed"] is True
    assert M.c3_verdict([2.0] * 8, statistic="median")["passed"] is True     # 경계는 통과(≤)
    assert M.c3_verdict([2.1] * 8, statistic="median")["passed"] is False
    assert M.c3_verdict([1.0], statistic="median")["threshold"] == 2.0


def test_c3_aggregation_choice_changes_the_verdict():
    """어느 통계량을 고르느냐가 판정을 바꾼다 — 그래서 결과 열람 전에 정해야 한다."""
    v = [1.0, 1.2, 1.4, 9.0]
    assert M.c3_verdict(v, statistic="median")["passed"] is True
    assert M.c3_verdict(v, statistic="max")["passed"] is False


def test_c3_is_unmeasurable_when_all_none():
    out = M.c3_verdict([None, None], statistic="median")
    assert out["value"] is None and out["passed"] is None
