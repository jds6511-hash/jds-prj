"""M8 실패 분해 — 진단이 공식 판정을 건드리지 않는다는 것을 검증한다."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m8_failure_analysis as F                                    # noqa: E402
import m8_metrics as M                                             # noqa: E402

OFFICIAL = ROOT / "docs" / "finalization" / "m8_official_result_2026-08-27.json"


def ref(a, b, name="GT"):
    return {"event": name, "span": [a, b]}


def gen(a, b, name="생성", ev=None):
    return {"event": name, "span": [a, b], "description": "가나다",
            "evidence_segments": ev if ev is not None else [a]}


# ---------------------------------------------------------------- 불변 경계

def test_official_verdict_is_copied_not_recomputed():
    src = (ROOT / "scripts" / "m8_failure_analysis.py").read_text(encoding="utf-8")
    for banned in ("c1_verdict", "c2_verdict", "c3_verdict", "c2_statistic",
                   "panel_verdict"):
        assert banned not in src, f"진단이 관문을 다시 계산한다: {banned}"


def test_official_artifact_is_not_written():
    src = (ROOT / "scripts" / "m8_failure_analysis.py").read_text(encoding="utf-8")
    assert "m8_official_result" in src            # 읽기는 한다
    assert "write_text" in src                   # 자기 산출물만 쓴다
    assert 'OFFICIAL.write_text' not in src and "atomic_write_json(OFFICIAL" not in src


def test_reference_comes_from_frozen_only():
    src = (ROOT / "scripts" / "m8_failure_analysis.py").read_text(encoding="utf-8")
    assert "load_reference" in src and "parse_rows" not in src


# ---------------------------------------------------------------- 사건 단위

def test_unmatched_gt_counts_as_iou_zero():
    """동결 정의 유지 — 미매칭은 0이고 평균에서 빼지 않는다."""
    rows = F.event_rows("v", [ref(0, 4), ref(100, 104)], [gen(0, 4)])
    assert [r["matched"] for r in rows] == [True, False]
    assert [r["matched_iou"] for r in rows] == [1.0, 0.0]
    assert rows[1]["alignment_type"] == "missed_event"
    assert rows[1]["bucket"] == "UNMATCHED"


def test_overmerge_when_one_generated_covers_two_gt():
    rows = F.event_rows("v", [ref(0, 4), ref(6, 10)], [gen(0, 10)])
    assert any(r["alignment_type"] == "overmerge" for r in rows)


def test_boundary_too_wide_vs_shift():
    wide = F.event_rows("v", [ref(10, 14)], [gen(0, 40)])[0]
    assert wide["alignment_type"] in ("boundary_too_wide", "overmerge")
    shift = F.event_rows("v", [ref(10, 20)], [gen(16, 26)])[0]
    assert shift["alignment_type"] == "boundary_shift"


def test_reasonable_match_at_high_iou():
    r = F.event_rows("v", [ref(0, 9)], [gen(0, 9)])[0]
    assert r["alignment_type"] == "reasonable_match" and r["bucket"] == "HIGH"


def test_alignment_types_stay_inside_frozen_taxonomy():
    rows = F.event_rows("v", [ref(0, 4), ref(6, 10), ref(50, 60)],
                        [gen(0, 10), gen(52, 54)])
    for r in rows:
        assert r["alignment_type"] in M.EVENT_ALIGNMENT_TYPES


# ---------------------------------------------------------------- 생성 단위

def test_generated_unmatched_is_spurious():
    rows = F.generated_rows("v", [ref(0, 4)], [gen(0, 4), gen(80, 84)])
    assert [r["matched"] for r in rows] == [True, False]
    assert rows[1]["type"] == "spurious_event"


# ---------------------------------------------------------------- 거부 연결

def test_rejection_maps_to_unmatched_gt_without_counterfactual():
    refs = [ref(0, 4), ref(20, 24)]
    rep = {"rejected": [{"chunk": 0, "reason": "bad_span", "span": [20, 24],
                         "event": "거부된 후보"}]}
    ev = F.event_rows("v", refs, [gen(0, 4)])
    rows = F.rejection_rows("v", refs, rep, ev)
    assert rows[0]["overlapping_gt"] == [1]
    assert rows[0]["overlapping_unmatched_gt"] == [1]


def test_rejection_analysis_does_not_revive_candidates():
    src = (ROOT / "scripts" / "m8_failure_analysis.py").read_text(encoding="utf-8")
    assert "counterfactual" in src              # 금지된다고 적혀 있다
    assert "PASS했다" not in src


# ---------------------------------------------------------------- 청크·C1

def test_chunk_rows_reparse_premerge_raw():
    rep = {"map_raw_outputs": [json.dumps([{"event": "a", "span": [0, 2],
                                            "evidence_segments": [0],
                                            "description": "가나다"}]), "[]"],
           "chunk_retries": [{"chunk": 1, "recovered": False}]}
    rows = F.chunk_rows("v", rep)
    assert [r["raw_events"] for r in rows] == [1, 0]
    assert rows[1]["zero_event_chunk"] and rows[1]["regeneration_attempted"]
    assert rows[1]["regeneration_recovered"] is False


def test_c1_semantic_mid_stream_vs_tail():
    ch = [{"chunk": i} for i in range(4)]
    mid = F.c1_semantic("v", {"chunk_retries": [{"chunk": 1, "recovered": False}],
                              "sentences": [{}], "map_raw_outputs": ["[]"] * 4}, ch)
    assert mid["post_hoc_kind"] == "MID_STREAM_EMPTY_CHUNK"
    tail = F.c1_semantic("v", {"chunk_retries": [{"chunk": 3, "recovered": False}],
                               "sentences": [{}], "map_raw_outputs": ["[]"] * 4}, ch)
    assert tail["post_hoc_kind"] == "TAIL_TERMINATION"


def test_c1_semantic_never_rewrites_official_status():
    ch = [{"chunk": 0}]
    out = F.c1_semantic("v", {"chunk_retries": [{"chunk": 0, "recovered": False}],
                              "sentences": [{}], "map_raw_outputs": ["[]"]}, ch)
    assert out["official_early_stop"] == "PRESENT"      # 공식 값을 그대로 옮긴다
    assert "passed" not in out and "verdict" not in out


# ---------------------------------------------------------------- Redundancy

def test_redundancy_is_reported_as_ambiguous():
    ev = F.event_rows("v", [ref(0, 9)], [gen(0, 4), gen(5, 9)])
    d = F.redundancy_diagnostic(ev)
    assert d["status"] == "DEFINITION_AMBIGUOUS"
    assert d["gt_events_with_multiple_overlapping_generated"] == 1
    assert "Redundancy" in d["note"]


def test_redundancy_never_named_as_the_metric_value():
    src = (ROOT / "scripts" / "m8_failure_analysis.py").read_text(encoding="utf-8")
    assert '"redundancy_value"' not in src and "redundancy_ratio" not in src


# ---------------------------------------------------------------- 재현성

def test_input_ordering_does_not_change_counts():
    refs = [ref(0, 4), ref(20, 24), ref(40, 44)]
    gens = [gen(0, 4), gen(41, 45)]
    a = F.event_rows("v", refs, gens)
    b = F.event_rows("v", list(refs), list(reversed(gens)))
    assert sum(r["matched"] for r in a) == sum(r["matched"] for r in b)
    assert sorted(r["matched_iou"] for r in a) == sorted(r["matched_iou"] for r in b)


def test_iou_distribution_keeps_unmatched_zeros():
    ev = F.event_rows("v", [ref(0, 4), ref(90, 94)], [gen(0, 4)])
    d = F.iou_distribution(ev)
    assert d["n"] == 2 and d["min"] == 0.0 and d["max"] == 1.0
    assert d["buckets"]["UNMATCHED"] == 1


def test_failure_mode_is_labelled_diagnostic_not_acceptance():
    v = {"n_sentences": 6, "n_reference_events": 12, "compression": 0.5,
         "alignment": 0.217, "rejections": 1}
    out = F.failure_mode(v)
    assert "UNDER_GENERATION_DOMINANT" in out["failure_modes"] and out["evidence"]


# ---------------------------------------------------------------- 산출물

@pytest.mark.skipif(not OFFICIAL.is_file(), reason="공식 결과가 없다")
def test_json_artifact_has_required_fields():
    p = ROOT / "docs" / "finalization" / "m8_failure_analysis_2026-08-27.json"
    if not p.is_file():
        pytest.skip("진단 산출물이 아직 없다")
    d = json.loads(p.read_text(encoding="utf-8"))
    for k in ("official_result", "per_video", "event_level", "generated_level",
              "rejection_analysis", "c1_semantic_diagnostic",
              "failure_mode_summary", "confirmation_consequence", "m9_status"):
        assert k in d
    assert d["official_result"]["acceptance"] == "FAIL"
    assert d["official_result"]["changed_by_this_analysis"] is False
    assert d["m9_status"] == "HOLD"
    assert len(d["event_level"]) == 68
