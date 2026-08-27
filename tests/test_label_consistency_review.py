"""consistency review 자료 생성기 — 순수 함수만 검증한다.

이 도구는 **판정하지 않는다.** 사람이 볼 후보를 모으는 게 전부라서, 테스트도
"후보를 놓치지 않는가"와 "정상을 후보로 올리지 않는가" 두 방향만 본다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import label_consistency_review as R                              # noqa: E402


def row(a, b, name="사건", unclear=False):
    return {"start_sec": float(a), "end_sec": float(b), "event": name,
            "unclear": unclear, "extra": []}


# ---------------------------------------------------------------- 길이 분포

def test_durations_and_stats():
    rows = [row(0, 10), row(20, 50), row(50, 55)]
    assert R.durations(rows) == [10.0, 30.0, 5.0]
    s = R.stats(R.durations(rows))
    assert (s["n"], s["min"], s["median"], s["max"]) == (3, 5.0, 10.0, 30.0)


def test_stats_empty_is_none_not_crash():
    """사건 0건인 영상이 섞여도 자료 생성 자체가 멈추면 안 된다."""
    assert R.stats([])["n"] == 0
    assert R.stats([])["median"] is None


# ---------------------------------------------------------------- 경계 관행

def test_adjacent_gaps_zero_and_positive():
    rows = [row(0, 10), row(10, 20), row(35, 40)]
    g = R.adjacent_gaps(rows)
    assert [x["gap"] for x in g] == [0.0, 15.0]
    assert R.zero_gap_ratio(rows) == pytest.approx(0.5)


def test_adjacent_gaps_negative_when_overlapping():
    """겹침은 사전등록에서 정상이다 — 음수 간격으로 **보여주되** 거부하지 않는다."""
    rows = [row(0, 30), row(20, 40)]
    assert R.adjacent_gaps(rows)[0]["gap"] == -10.0


def test_gaps_use_sorted_order_not_file_order():
    rows = [row(35, 40), row(0, 10)]
    assert [x["gap"] for x in R.adjacent_gaps(rows)] == [25.0]


# ---------------------------------------------------------------- 미커버 구간

def test_uncovered_ranges_merges_overlaps_before_complement():
    rows = [row(0, 30), row(20, 60)]
    assert R.uncovered_ranges(rows, 100.0, min_sec=10.0) == [(60.0, 100.0)]


def test_uncovered_ranges_filters_short_holes():
    rows = [row(0, 30), row(33, 100)]
    assert R.uncovered_ranges(rows, 100.0, min_sec=10.0) == []
    assert R.uncovered_ranges(rows, 100.0, min_sec=1.0) == [(30.0, 33.0)]


def test_uncovered_includes_unclear_rows_as_examined():
    """`unclear`는 주분석에서 빠지지만 **사람이 본 구간**이다 — 미커버로 띄우면
    "커버율을 맞추려 사건을 추가"하는 압력이 생긴다."""
    rows = [row(0, 50), row(50, 100, unclear=True)]
    assert R.uncovered_ranges(rows, 100.0, min_sec=1.0) == []


def test_coverage_ratio():
    assert R.coverage_ratio([row(0, 50)], 100.0) == pytest.approx(0.5)


# ---------------------------------------------------------------- 병합 규칙

def test_merge_candidate_same_name_within_window():
    """사전등록 §2: 같은 목적의 행위가 30초 이내면 하나로 본다."""
    rows = [row(0, 30, "포장작업"), row(45, 90, "포장작업")]
    c = R.merge_rule_candidates(rows, window=30.0)
    assert len(c) == 1 and c[0]["gap"] == 15.0


def test_merge_candidate_not_flagged_beyond_window():
    rows = [row(0, 30, "포장작업"), row(200, 260, "포장작업")]
    assert R.merge_rule_candidates(rows, window=30.0) == []


def test_merge_candidate_needs_same_name():
    rows = [row(0, 30, "포장작업"), row(35, 90, "퇴근")]
    assert R.merge_rule_candidates(rows, window=30.0) == []


# ---------------------------------------------------------------- 이름 형식

def test_name_form_flags_screen_description():
    """사전등록 §3: `event`는 **무슨 일인지**다. "…모습/장면"은 화면 서술이다."""
    f = R.name_form_candidates([row(0, 10, "등산하는 모습")])
    assert f and "화면서술" in f[0]["flags"]


def test_name_form_flags_multiple_events_in_one_line():
    f = R.name_form_candidates([row(0, 10, "포장작업 그리고 퇴근")])
    assert f and "복수사건" in f[0]["flags"]


def test_name_form_does_not_flag_ordinary_action_names():
    ok = ["호박순 정리", "자동차 운전", "강아지와 놀아주기", "퇴근", "식사"]
    assert R.name_form_candidates([row(0, 10, n) for n in ok]) == []


def test_name_form_flags_long_names():
    long = "가" * 26
    f = R.name_form_candidates([row(0, 10, long)])
    assert f and "긴이름" in f[0]["flags"]


# ---------------------------------------------------------------- 오염 경계

def test_module_does_not_import_search_or_eval():
    """CLAUDE.md 절대규칙 3 — 라벨 도구는 검색·평가 모듈을 import조차 하지 않는다."""
    src = (ROOT / "scripts" / "label_consistency_review.py").read_text(encoding="utf-8")
    for banned in ("m5_search", "m6_evaluate", "m8_", "m9_"):
        assert banned not in src


def test_report_flags_single_event_video():
    """1건 영상은 "쪼개라"가 아니라 "같은 정의를 적용했는지 확인"으로 띄운다."""
    md = R.render_video("vidA", [row(0, 863.8, "등산하는 모습")], 863.8, 173)
    assert "사건 1건" in md
