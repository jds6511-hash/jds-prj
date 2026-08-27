"""C1·C2·C3 관문 집행 — 규격 `docs/finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md`.

여기서 지키는 것은 셋이다.

```
분모는 FROZEN에서만 온다        draft CSV가 우회로 들어오면 동결이 무의미하다
C3 집계는 MAX로 동결됐다        median/mean과 값이 갈리는 fixture로 확인
C2 판정 지표는 아직 안 정해졌다   코드가 거부한다 — 판정 시점에 고르면 결과가 고른다
```
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import event_inventory_kit as K                                    # noqa: E402
import m8_gates as G                                               # noqa: E402
import m8_metrics as M                                             # noqa: E402

CSV = ("start_sec,end_sec,event,unclear\n"
       "0,30,현장 도착,\n40,70,관계자와 대화,\n75,140,작업,\n")


def frozen(tmp_path, vid="vid"):
    p = tmp_path / f"{vid}.csv"
    p.write_text(CSV, encoding="utf-8")
    K.freeze(p, video_id=vid, duration_sec=200, n_segments=40, seg_len=5,
             out_dir=tmp_path)
    return p


def report(n_sentences, spans=None):
    spans = spans or [[0, 6]] * n_sentences
    return {"sentences": [{"sent_id": i, "text": f"문장{i}", "cites": [spans[i][0]],
                           "event": f"E{i}", "span": spans[i]}
                          for i in range(n_sentences)],
            "events": [{"event": f"E{i}", "span": spans[i],
                        "evidence_segments": [spans[i][0]], "description": "가나다"}
                       for i in range(n_sentences)],
            "rejected": [], "map_raw_outputs": ["[]"], "chunk_retries": [],
            "truncated_tail": None}


# ---------------------------------------------------------------- 분모 경계

def test_reference_comes_from_frozen_artifact(tmp_path):
    csv = frozen(tmp_path)
    refs = G.reference_events("vid", out_dir=tmp_path, csv_path=csv)
    assert len(refs) == 3 and all("span" in r for r in refs)


def test_reference_refuses_before_freeze(tmp_path):
    (tmp_path / "vid.csv").write_text(CSV, encoding="utf-8")
    with pytest.raises(K.InventoryError, match="동결"):
        G.reference_events("vid", out_dir=tmp_path, csv_path=tmp_path / "vid.csv")


def test_reference_refuses_after_draft_mutation(tmp_path):
    """**핵심.** 동결 뒤 CSV를 고치면 관문이 fail-closed 한다."""
    csv = frozen(tmp_path)
    csv.write_text(CSV + "150,180,추가 사건,\n", encoding="utf-8")
    with pytest.raises(K.InventoryError, match="해시 불일치"):
        G.reference_events("vid", out_dir=tmp_path, csv_path=csv)


def test_module_never_reads_draft_csv_directly():
    src = (ROOT / "scripts" / "m8_gates.py").read_text(encoding="utf-8")
    assert "parse_rows" not in src and ".draft.json" not in src
    assert "load_reference" in src


# ---------------------------------------------------------------- C3

def test_video_compression_is_sentences_over_reference_events(tmp_path):
    csv = frozen(tmp_path)
    refs = G.reference_events("vid", out_dir=tmp_path, csv_path=csv)
    assert G.video_compression(report(6), refs) == 2.0        # 6 / 3
    assert G.video_compression(report(3), refs) == 1.0


def test_c3_statistic_is_frozen_to_max():
    assert G.C3_STATISTIC == "max"


def test_c3_max_differs_from_median_and_mean():
    """한 편만 넘는 fixture — MAX만 FAIL로 잡는다."""
    v = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0]
    assert M.c3_verdict(v, statistic="median")["passed"] is True
    assert M.c3_verdict(v, statistic="mean")["passed"] is True
    assert M.c3_verdict(v, statistic=G.C3_STATISTIC)["passed"] is False


def test_c3_boundary_exactly_two_passes():
    assert M.c3_verdict([2.0] * 8, statistic=G.C3_STATISTIC)["passed"] is True
    assert M.c3_verdict([2.0] * 7 + [2.0001], statistic=G.C3_STATISTIC)["passed"] \
        is False


def test_c3_input_order_does_not_change_verdict():
    v = [1.0, 3.0, 1.5]
    a = M.c3_verdict(v, statistic=G.C3_STATISTIC)
    b = M.c3_verdict(list(reversed(v)), statistic=G.C3_STATISTIC)
    assert a["value"] == b["value"] and a["passed"] == b["passed"]


# ---------------------------------------------------------------- C2 미결

def test_c2_metric_choice_is_refused_by_default():
    """C2 판정에 쓸 per-video 지표가 사전등록에 확정돼 있지 않다.

    원 사전등록은 "Event Recall 중앙값"이라 적었고, 보충이 주지표를
    `event_temporal_alignment`(연속값)로 두면서 θ 기반 recall은 **세 값을 모두
    보고하고 하나를 고르지 않는다**고 했다. 그래서 코드가 고르지 않는다.
    """
    rows = [{"video_id": "v", "c2_candidates": {"event_temporal_alignment": 0.8}}]
    with pytest.raises(M.GateSpecError, match="C2"):
        G.panel_verdict(rows)


def test_c2_metric_must_be_one_of_the_reported_candidates():
    rows = [{"video_id": "v", "c2_candidates": {"event_temporal_alignment": 0.8}}]
    with pytest.raises(M.GateSpecError):
        G.panel_verdict(rows, c2_metric="made_up_metric")


def test_c2_metric_explicit_choice_is_honored():
    rows = [{"video_id": f"v{i}", "c1_status": "ABSENT", "compression": 1.0,
             "c2_candidates": {"event_temporal_alignment": 0.8}} for i in range(8)]
    out = G.panel_verdict(rows, c2_metric="event_temporal_alignment")
    assert out["C2"]["value"] == 0.8 and out["C2"]["passed"] is True
    assert out["c2_metric"] == "event_temporal_alignment"


# ---------------------------------------------------------------- 패널 판정

def rows_ok(n=8, **over):
    out = []
    for i in range(n):
        r = {"video_id": f"v{i}", "c1_status": "ABSENT", "compression": 1.0,
             "c2_candidates": {"event_temporal_alignment": 0.8}}
        r.update(over)
        out.append(r)
    return out


def test_panel_all_pass():
    out = G.panel_verdict(rows_ok(), c2_metric="event_temporal_alignment")
    assert [out[k]["passed"] for k in ("C1", "C2", "C3")] == [True, True, True]
    assert out["all_passed"] is True


def test_panel_c1_unclear_blocks_overall_pass():
    rows = rows_ok()
    rows[3]["c1_status"] = "UNCLEAR"
    out = G.panel_verdict(rows, c2_metric="event_temporal_alignment")
    assert out["C1"]["passed"] is None and out["all_passed"] is None


def test_panel_c1_present_fails_even_with_unclear():
    rows = rows_ok()
    rows[0]["c1_status"] = "PRESENT"
    rows[1]["c1_status"] = "UNCLEAR"
    out = G.panel_verdict(rows, c2_metric="event_temporal_alignment")
    assert out["C1"]["passed"] is False and out["all_passed"] is False


def test_panel_reports_diagnostics_separately_from_c3():
    """Redundancy·overmerge·spurious는 C3에 합치지 않는다 — 규격 §2-3."""
    out = G.panel_verdict(rows_ok(), c2_metric="event_temporal_alignment")
    assert "C3" in out and "diagnostics_note" in out
    assert "redundancy" not in out["C3"]


# ---------------------------------------------------------------- 산출물 부재

def test_video_row_refuses_missing_report(tmp_path):
    csv = frozen(tmp_path)
    with pytest.raises(G.GateRunError, match="report.json"):
        G.video_row("vid", tmp_path / "없는곳", n_segments=40,
                    out_dir=tmp_path, csv_path=csv)


def test_video_row_collects_c1_and_compression(tmp_path):
    csv = frozen(tmp_path)
    wdir = tmp_path / "work"
    wdir.mkdir()
    (wdir / "report.json").write_text(json.dumps(report(6), ensure_ascii=False),
                                      encoding="utf-8")
    row = G.video_row("vid", wdir, n_segments=40, out_dir=tmp_path, csv_path=csv)
    assert row["compression"] == 2.0
    assert row["c1_status"] in ("PRESENT", "ABSENT", "UNCLEAR")
    assert "event_temporal_alignment" in row["c2_candidates"]
    assert row["n_reference_events"] == 3 and row["n_sentences"] == 6
