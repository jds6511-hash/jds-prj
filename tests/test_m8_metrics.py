"""M8 event 지표 — **정답 목록도 M8 출력도 없는 지금** 계산 규칙을 고정한다.

사전등록: `docs/preregistration/M8_event지표_보충_2026-08-18.md` §2·§3.
나중에 정하면 목록과 지표를 서로 맞춰 튜닝할 수 있다. 그래서 먼저 박는다.

핵심은 **1:1 매칭**이다. "조금이라도 겹치면 covered"로 두면 거대한 span 하나가
여러 정답 사건을 먹어 recall이 부풀려진다 — `segment coverage`를 주지표에서
내린 것과 같은 종류의 결함이다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from m8_metrics import (event_temporal_alignment, iou_recall, match_events,  # noqa: E402
                        structural_summary, temporal_iou, timeline_span_coverage)


def _ev(a, b, **kw):
    return {"span": [a, b], **kw}


# ---- temporal IoU --------------------------------------------------------

def test_iou_identical_is_one():
    assert temporal_iou([0, 9], [0, 9]) == 1.0


def test_iou_disjoint_is_zero():
    assert temporal_iou([0, 4], [5, 9]) == 0.0


def test_iou_span_is_inclusive_of_both_ends():
    """span [0,4]는 5구간이다 — 끝 포함. off-by-one이면 IoU가 조용히 어긋난다."""
    assert temporal_iou([0, 4], [0, 4]) == 1.0
    assert temporal_iou([0, 4], [2, 6]) == 3 / 7      # 교집합 2..4=3, 합집합 0..6=7


def test_iou_touching_but_not_overlapping_is_zero():
    assert temporal_iou([0, 4], [5, 5]) == 0.0


# ---- 1:1 매칭 ------------------------------------------------------------

def test_one_giant_event_cannot_cover_two_references():
    """부풀리기 방어의 핵심 — 이 테스트가 지표의 존재 이유다."""
    refs = [_ev(0, 9), _ev(20, 29)]
    gens = [_ev(0, 29)]                                # 둘 다 걸치는 거대 span
    m = match_events(refs, gens)
    assert sum(1 for v in m.values() if v is not None) == 1   # 하나만 대응된다


def test_matching_is_optimal_not_greedy():
    """탐욕적으로 고르면 첫 정답이 더 나은 짝을 가져가 전체 합이 나빠진다."""
    refs = [_ev(0, 9), _ev(10, 19)]
    gens = [_ev(10, 19), _ev(0, 9)]
    m = match_events(refs, gens)
    assert m[0] == 1 and m[1] == 0                     # 교차로 완전 매칭


def test_unmatched_reference_maps_to_none():
    refs = [_ev(0, 9), _ev(50, 59)]
    gens = [_ev(0, 9)]
    m = match_events(refs, gens)
    assert m[1] is None


def test_zero_overlap_pair_is_not_matched():
    """겹침이 0이면 매칭하지 않는다 — 짝을 억지로 만들면 alignment가 오염된다."""
    refs = [_ev(0, 9)]
    gens = [_ev(50, 59)]
    assert match_events(refs, gens)[0] is None


# ---- 주지표: macro 평균 --------------------------------------------------

def test_alignment_is_macro_mean_unmatched_counts_zero():
    refs = [_ev(0, 9), _ev(20, 29)]
    gens = [_ev(0, 9)]                                 # 두 번째는 못 맞춘다
    assert event_temporal_alignment(refs, gens) == 0.5   # (1.0 + 0.0) / 2


def test_alignment_macro_not_weighted_by_length():
    """긴 사건이 결과를 지배하면 안 된다 — 사건 하나가 한 표다."""
    refs = [_ev(0, 99), _ev(200, 201)]
    gens = [_ev(0, 99)]
    assert event_temporal_alignment(refs, gens) == 0.5


def test_alignment_none_when_no_references():
    """정답이 0개면 0.0이 아니라 **측정 불가**다 (M9 coverage_rate와 같은 원칙)."""
    assert event_temporal_alignment([], [_ev(0, 9)]) is None


# ---- 부지표: 임계 recall --------------------------------------------------

def test_iou_recall_reports_all_three_thetas():
    refs = [_ev(0, 9), _ev(20, 29)]
    gens = [_ev(0, 9), _ev(20, 24)]                    # 두 번째 IoU = 5/10 = 0.5
    r = iou_recall(refs, gens)
    assert set(r) == {"0.3", "0.5", "0.7"}
    assert r["0.3"] == 1.0 and r["0.5"] == 1.0 and r["0.7"] == 0.5


# ---- timeline span coverage (진단) ---------------------------------------

def test_timeline_span_coverage_uses_union_not_sum():
    """겹치는 span을 더하면 1을 넘는다. 합집합이어야 한다."""
    events = [_ev(0, 9), _ev(5, 14)]
    assert timeline_span_coverage(events, n_segments=20) == 0.75   # 0..14 = 15/20


def test_timeline_span_coverage_none_without_segments():
    assert timeline_span_coverage([_ev(0, 9)], n_segments=0) is None


# ---- 구조 진단 -----------------------------------------------------------

REPORT = {
    "events": [{"event": "도착", "span": [0, 4], "evidence_segments": [0, 1],
                "description": "가"* 40},
               {"event": "작업", "span": [3, 9], "evidence_segments": [3, 4, 5],
                "description": "나" * 90}],
    "rejected": [{"reason": "thin_description"}, {"reason": "bad_span"},
                 {"reason": "thin_description"}],
    "chunk_retries": [{"chunk": 0, "recovered": True}],
}


def test_structural_summary_counts_and_reasons():
    s = structural_summary(REPORT, n_segments=20)
    assert s["valid_events"] == 2 and s["rejected_events"] == 3
    assert s["rejection_reasons"]["thin_description"] == 2
    assert s["rejection_reasons"]["bad_span"] == 1


def test_structural_summary_distributions():
    s = structural_summary(REPORT, n_segments=20)
    assert s["span_len_dist"] == [5, 7]                # 끝 포함
    assert s["evidence_per_event_dist"] == [2, 3]
    assert s["chars_per_evidence"] == [20.0, 30.0]


def test_structural_summary_reports_overlap_between_events():
    """사건 span이 겹치면 같은 시간을 두 번 서술한 것 — 진단으로 남긴다."""
    s = structural_summary(REPORT, n_segments=20)
    assert s["event_span_overlap_pairs"] == 1          # [0,4] 와 [3,9]가 겹친다


def test_structural_summary_includes_timeline_span_coverage():
    s = structural_summary(REPORT, n_segments=20)
    assert s["timeline_span_coverage"] == 0.5          # 0..9 = 10/20
