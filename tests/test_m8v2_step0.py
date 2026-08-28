"""M8-v2 STEP 0 — trigger reachability pilot.

규격: `docs/finalization/M8V2_STEP0_SPEC_2026-08-28.md` (실행 전 동결).

여기서 지키는 것은 셋이다.
  ① 이 도구는 **생성하지 않는다** — LLM을 부르지 않고 GPU를 쓰지 않는다.
  ② trigger feature는 **GT를 쓰지 않는다** — fresh data에서 같은 규칙을 적용해야 한다.
  ③ GO 기준·threshold grid·선택 규칙은 **결과를 보기 전에 고정**돼 있다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m8v2_step0_reachability as S                                 # noqa: E402


# ── 청크 경계 재현 ────────────────────────────────────────────────────────
def test_chunk_spans_생성기_루프와_같은_경계를_낸다():
    """`generate_report_structured`의 while 루프와 같아야 한다 — 어긋나면 feature가
    조용히 다른 구간에서 계산된다."""
    assert S.chunk_spans(183, 60, 5) == [(0, 59), (55, 114), (110, 169), (165, 182)]


def test_chunk_spans_마지막_청크는_남은_구간까지만():
    assert S.chunk_spans(316, 60, 5)[-1] == (275, 315)
    assert len(S.chunk_spans(316, 60, 5)) == 6


def test_chunk_spans_단일_청크():
    assert S.chunk_spans(30, 60, 5) == [(0, 29)]


# ── feature — GT 없이 baseline 산출물만 ──────────────────────────────────
def _rep(events, raws, rejected=None):
    return {"events": events, "map_raw_outputs": raws,
            "rejected": rejected or []}


def test_accepted_span_coverage는_합집합_기준():
    """겹치는 span을 단순 합산하면 1을 넘는다."""
    rep = _rep([{"span": [0, 29]}, {"span": [20, 39]}], ["[]"])
    f = S.chunk_features(rep, [(0, 59)], seg_len_sec=5)[0]
    assert f["accepted_span_coverage"] == pytest.approx(40 / 60, abs=1e-4)


def test_coverage는_청크_밖_사건을_세지_않는다():
    rep = _rep([{"span": [100, 120]}], ["[]"])
    f = S.chunk_features(rep, [(0, 59)], seg_len_sec=5)[0]
    assert f["accepted_span_coverage"] == 0.0


def test_max_uncovered_gap은_최장_연속_미커버_구간이다():
    """두 공백이 있으면 합이 아니라 **최장**이다."""
    rep = _rep([{"span": [0, 9]}, {"span": [20, 24]}], ["[]"])
    f = S.chunk_features(rep, [(0, 59)], seg_len_sec=5)[0]
    # 미커버: 10~19(10구간), 25~59(35구간) → 최장 35구간 × 5초
    assert f["max_uncovered_gap_sec"] == 175


def test_전부_커버되면_gap은_0():
    rep = _rep([{"span": [0, 59]}], ["[]"])
    assert S.chunk_features(rep, [(0, 59)], seg_len_sec=5)[0]["max_uncovered_gap_sec"] == 0


def test_raw_candidates는_검증_전_파싱_개수다():
    raw = '[{"event":"a","span":[0,1],"evidence_segments":[0]},' \
          ' {"event":"b","span":[2,3],"evidence_segments":[2]}]'
    f = S.chunk_features(_rep([], [raw]), [(0, 59)], seg_len_sec=5)[0]
    assert f["raw_candidates"] == 2


def test_rejection_부하는_청크별로_귀속된다():
    rep = _rep([], ["[]", "[]"],
               rejected=[{"chunk": 1, "reason": "x"}, {"chunk": 1, "reason": "y"}])
    fs = S.chunk_features(rep, [(0, 59), (55, 114)], seg_len_sec=5)
    assert [f["rejected"] for f in fs] == [0, 2]


def test_rejection_ratio는_raw가_0이면_0이다():
    """0으로 나누지 않는다 — 빈 청크를 '거부 부하 최대'로 오분류하면 T5가 T1이 된다."""
    rep = _rep([], ["not json"], rejected=[])
    assert S.chunk_features(rep, [(0, 59)], seg_len_sec=5)[0]["rejection_ratio"] == 0.0


def test_feature는_GT를_인자로_받지_않는다():
    """서명에 GT가 들어오면 fresh data에서 못 쓰는 trigger가 된다."""
    import inspect
    params = set(inspect.signature(S.chunk_features).parameters)
    assert not (params & {"refs", "gt", "reference_events", "unmatched"})


# ── trigger ──────────────────────────────────────────────────────────────
def test_threshold_grid는_38개다():
    ids = [c["id"] for c in S.candidates()]
    assert len(ids) == 38
    assert len(set(ids)) == 38


def test_grid는_다섯_계열을_전부_포함한다():
    fams = {c["family"] for c in S.candidates()}
    assert fams == {"T2", "T3", "T4", "T5a", "T5b"}


def test_T1은_후보가_아니다():
    """zero-event rescue는 도달 상한 1/22로 structural NO-GO다."""
    assert "T1" not in {c["family"] for c in S.candidates()}


@pytest.mark.parametrize("fam,thr,feat,want", [
    ("T2", 0.5, {"accepted_span_coverage": 0.4}, True),
    ("T2", 0.5, {"accepted_span_coverage": 0.5}, False),      # 경계 미포함
    ("T3", 3, {"raw_density_per60": 2.0}, True),
    ("T3", 3, {"raw_density_per60": 3.0}, False),
    ("T4", 60, {"max_uncovered_gap_sec": 90}, True),
    ("T4", 60, {"max_uncovered_gap_sec": 60}, False),
    ("T5a", 0.3, {"rejection_ratio": 0.3}, True),             # 경계 포함
    ("T5a", 0.3, {"rejection_ratio": 0.2}, False),
    ("T5b", 2.0, {"rejections_per_10min": 2.0}, True),
    ("T5b", 2.0, {"rejections_per_10min": 1.9}, False),
])
def test_trigger_발화_규칙(fam, thr, feat, want):
    assert S.fires(feat, {"family": fam, "threshold": thr}) is want


def test_OR_결합은_제공하지_않는다():
    """단일 trigger로 안 되면 그 자체가 신호다 — 합쳐서 넘기는 API를 두지 않는다."""
    assert not [n for n in dir(S) if "combine" in n.lower() or "union_trigger" in n.lower()]


# ── reachability ─────────────────────────────────────────────────────────
def test_unmatched_GT는_발화_청크와_겹치면_reachable():
    per_video = [{"video_id": "v", "n_segments": 120,
                  "chunks": [{"span": (0, 59), "flag": False},
                             {"span": (55, 119), "flag": True}],
                  "unmatched": [[10, 12], [100, 110]]}]
    m = S.evaluate(per_video)
    assert m["reachable_unmatched_gt"] == 1
    assert m["reachable_videos"] == 1
    assert m["triggered_chunks"] == 1


def test_한_구간이라도_겹치면_reachable이다():
    """경계에 걸친 GT를 놓치지 않는다 — 양 끝 포함."""
    per_video = [{"video_id": "v", "n_segments": 120,
                  "chunks": [{"span": (55, 119), "flag": True}],
                  "unmatched": [[50, 55]]}]
    assert S.evaluate(per_video)["reachable_unmatched_gt"] == 1


def test_wasted_trigger는_unmatched가_없는_발화_청크다():
    per_video = [{"video_id": "v", "n_segments": 120,
                  "chunks": [{"span": (0, 59), "flag": True},
                             {"span": (55, 119), "flag": True}],
                  "unmatched": [[100, 110]]}]
    m = S.evaluate(per_video)
    assert m["triggered_chunks"] == 2 and m["wasted_triggers"] == 1


def test_max_video_share():
    per_video = [{"video_id": "a", "n_segments": 60,
                  "chunks": [{"span": (0, 59), "flag": True}],
                  "unmatched": [[1, 2], [3, 4], [5, 6]]},
                 {"video_id": "b", "n_segments": 60,
                  "chunks": [{"span": (0, 59), "flag": True}],
                  "unmatched": [[1, 2]]}]
    assert S.evaluate(per_video)["max_video_share"] == pytest.approx(0.75)


def test_reachable은_상한이라고_산출물에_적힌다():
    """'닿는다'와 '회수한다'는 다르다. 그 구분이 빠지면 상한이 성능으로 읽힌다."""
    assert "상한" in S.UPPER_BOUND_NOTE and "회수" in S.UPPER_BOUND_NOTE


# ── GO 판정 ──────────────────────────────────────────────────────────────
_OK = {"reachable_unmatched_gt": 6, "reachable_videos": 3,
       "triggered_chunks": 9, "max_video_share": 0.5}


def test_네_조건을_모두_만족하면_GO():
    assert S.go_verdict(_OK)["go"] is True


@pytest.mark.parametrize("key,bad", [
    ("reachable_unmatched_gt", 4),      # ① 5 미만
    ("reachable_videos", 1),            # ② 2편 미만
    ("triggered_chunks", 13),           # ③ 12 초과
    ("max_video_share", 0.61),          # ④ 60% 초과
])
def test_하나라도_어기면_NO_GO(key, bad):
    v = S.go_verdict({**_OK, key: bad})
    assert v["go"] is False and key in v["failed"]


def test_경계값은_통과다():
    v = S.go_verdict({"reachable_unmatched_gt": 5, "reachable_videos": 2,
                      "triggered_chunks": 12, "max_video_share": 0.60})
    assert v["go"] is True


def test_GO_기준은_상수로_동결돼_있다():
    assert S.GO_MIN_REACHABLE == 5 and S.GO_MIN_VIDEOS == 2
    assert S.GO_MAX_TRIGGERED == 12 and S.GO_MAX_VIDEO_SHARE == 0.60


# ── 선택 규칙 ────────────────────────────────────────────────────────────
def _c(cid, fam, burden, vids):
    return {"id": cid, "family": fam, "triggered_chunks": burden,
            "reachable_videos": vids, "go": True}


def test_선택은_burden_최소가_1순위():
    best = S.select_best([_c("T2@0.5", "T2", 10, 5), _c("T4@60", "T4", 7, 2)])
    assert best["id"] == "T4@60"


def test_동률이면_영상_수가_많은_것():
    best = S.select_best([_c("T2@0.5", "T2", 7, 2), _c("T4@60", "T4", 7, 4)])
    assert best["id"] == "T4@60"


def test_그다음은_규칙이_단순한_것():
    best = S.select_best([_c("T4@60", "T4", 7, 3), _c("T3@2", "T3", 7, 3)])
    assert best["id"] == "T3@2"


def test_단순성_순서는_동결돼_있다():
    assert S.SIMPLICITY_RANK == {"T3": 1, "T5a": 2, "T5b": 3, "T2": 4, "T4": 5}


def test_GO가_없으면_선택도_없다():
    assert S.select_best([]) is None


def test_최종_후보는_최대_1개():
    got = S.select_best([_c("a", "T3", 5, 3), _c("b", "T2", 5, 3)])
    assert isinstance(got, dict)


# ── 경계 준수 ────────────────────────────────────────────────────────────
def test_생성_모듈을_import하지_않는다():
    """LLM을 부르는 순간 pilot이 아니라 ROUND 3가 된다."""
    src = (ROOT / "scripts" / "m8v2_step0_reachability.py").read_text(encoding="utf-8")
    for bad in ("import llm", "make_llm", "generate_report", "consolidate"):
        assert bad not in src, f"{bad}를 참조한다 — 이 도구는 생성하지 않는다"


def test_판정_함수를_import하지_않는다():
    """C1/C2/C3 verdict를 부르면 pilot 숫자가 판정처럼 읽힌다."""
    src = (ROOT / "scripts" / "m8v2_step0_reachability.py").read_text(encoding="utf-8")
    for bad in ("c1_verdict", "c2_verdict", "c3_verdict", "panel_verdict"):
        assert bad not in src


def test_outcome_informed_고지가_있다():
    assert "outcome-informed" in S.OUTCOME_INFORMED_NOTE
    assert "fresh" in S.OUTCOME_INFORMED_NOTE


def test_선택된_trigger의_공백_원인을_가른다():
    """`생성이 없었다`와 `생성됐다가 거부됐다`는 필요한 개입이 다르다.
    안 가르면 재생성으로 못 고치는 것을 재생성으로 고치려 든다."""
    panel = [{"video_id": "v", "features": [
        {"span": (0, 59), "accepted_span_coverage": 0.1,
         "raw_candidates": 4, "rejected": 4},
        {"span": (55, 114), "accepted_span_coverage": 0.1,
         "raw_candidates": 0, "rejected": 0},
        {"span": (110, 169), "accepted_span_coverage": 1.0,
         "raw_candidates": 3, "rejected": 0}]}]
    d = S.selected_diagnostic(panel, {"family": "T2", "threshold": 0.7,
                                      "id": "T2@0.7"})
    assert d["fired_chunks"] == 2
    assert d["rejection_share"] == 1.0            # 발화 청크 안에서는 4/4
    assert d["panel_rejection_share"] == pytest.approx(4 / 7, abs=1e-4)
    assert d["chunks_with_no_generation"] == 1
    assert d["chunks_where_all_candidates_rejected"] == 1


def test_전체_sweep을_저장한다는_계약():
    """통과한 것만 남기면 sweep 은폐다."""
    import inspect
    assert "frontier" in inspect.getsource(S.build_manifest)
