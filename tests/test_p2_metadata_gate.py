"""P2 후보 metadata gate — **길이만 본다.** 캡션·점수를 보지 않는다.

막는 것 셋.
1. 길이를 추측해서 통과시키는 것 — 미확인은 `duration_pending`으로 남는다
2. 사용 불가 영상이 조용히 사라지는 것
3. 게이트가 캡션·검색 점수·모델명을 입력으로 받는 것
"""
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p2_metadata_gate as G                                   # noqa: E402


# ---- 경계는 seg_len에서 파생된다 -----------------------------------------

def test_bounds_derive_from_seg_len_and_target_segments():
    assert G.SEG_LEN == 5
    assert G.TARGET_SEGMENTS == (150, 400)
    assert G.MIN_SEC == 750 and G.MAX_SEC == 2000


def test_eligibility_is_inclusive_at_both_bounds():
    assert G.eligible(750) is True
    assert G.eligible(2000) is True
    assert G.eligible(749) is False
    assert G.eligible(2001) is False


def test_segment_estimate_uses_ceiling():
    assert G.est_segments(750) == 150
    assert G.est_segments(751) == 151                 # 5초 경계를 넘으면 한 칸 늘어난다
    assert G.est_segments(2000) == 400


def test_unknown_duration_is_pending_not_eligible():
    """색인에서 추측하지 않는다 — 모르면 pending이다."""
    r = G.classify({"id": "x", "duration": None})
    assert r["availability"] == "duration_pending"
    assert r["eligible"] is None                      # False가 아니다
    assert r["est_segments"] is None


def test_unavailable_video_is_recorded_not_dropped():
    r = G.classify({"id": "x", "duration": None, "error": "Private video"})
    assert r["availability"] == "unavailable"
    assert r["error"]
    assert r["eligible"] is None


# ---- 게이트가 성능을 볼 수 없다 -------------------------------------------

def test_classify_cannot_see_captions_or_scores():
    params = set(inspect.signature(G.classify).parameters)
    assert params == {"meta"}
    body = (ROOT / "scripts" / "p2_metadata_gate.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("caption", "mrr", "rr_", "qwen", "3b", "4b", "score", "rank"):
        assert bad not in body.lower(), bad


def test_no_title_based_filtering():
    """제목을 보고 거르지 않는다 — 기록만 한다."""
    a = G.classify({"id": "x", "duration": 1000, "title": "4B가 잘할 것 같은 영상"})
    b = G.classify({"id": "y", "duration": 1000, "title": "aaa"})
    assert a["eligible"] == b["eligible"] is True


# ---- 집계 --------------------------------------------------------------

def test_summary_counts_by_family_and_eligibility():
    rows = [{"family": "f1", "eligible": True}, {"family": "f1", "eligible": False},
            {"family": "f2", "eligible": True}, {"family": "f2", "eligible": None}]
    s = G.summarize(rows)
    assert s["eligible_total"] == 2
    assert s["by_family"]["f1"] == {"eligible": 1, "ineligible": 1, "pending": 0}
    assert s["by_family"]["f2"] == {"eligible": 1, "ineligible": 0, "pending": 1}
    assert s["pending_total"] == 1


def test_summary_reports_family_concentration():
    """한 프로그램이 표본을 지배하면 그 자체가 표본 선택 축이다."""
    rows = [{"family": "f1", "eligible": True}] * 9 + [
        {"family": "f2", "eligible": True}]
    s = G.summarize(rows)
    assert s["max_family_share"] == pytest.approx(0.9)
    assert s["concentration_note"]


def test_summary_separates_talking_head_family():
    rows = [{"family": "lecture_dialog", "eligible": True},
            {"family": "ebs_docuprime", "eligible": True}]
    s = G.summarize(rows)
    assert s["by_family"]["lecture_dialog"]["eligible"] == 1
    assert "lecture_dialog" in s["out_of_scope_pending_decision"]


def test_dedup_basis_is_recorded_as_unverifiable():
    """기존 11편에 출처 ID가 없다 — ID 대조가 불가능하다는 사실을 남긴다."""
    s = G.summarize([{"family": "f", "eligible": True}])
    d = s["dedup_vs_existing"]
    assert d["method"] == "program_family_disjointness"
    assert d["id_level_verified"] is False


def test_cli_output_is_ascii_safe():
    src = (ROOT / "scripts" / "p2_metadata_gate.py").read_text(encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line


def test_summary_reports_broadcaster_concentration_not_only_program():
    """프로그램별 점유율만 보면 방송사 집중을 놓친다.

    실측: 프로그램 최대 점유 0.2564인데 EBS 방송사 점유는 0.9091이었다.
    """
    rows = ([{"family": f"ebs_p{i}", "eligible": True} for i in range(9)]
            + [{"family": "kbs_docu", "eligible": True}])
    s = G.summarize(rows)
    assert s["max_family_share"] < 0.2
    assert s["max_source_share"] == pytest.approx(0.9)
    assert s["by_source"]["ebs"] == 9


def test_source_is_derived_from_family_prefix():
    assert G.source_of("ebs_docuprime") == "ebs"
    assert G.source_of("kbs_docu") == "kbs"
    assert G.source_of("lecture_dialog") == "lecture"
