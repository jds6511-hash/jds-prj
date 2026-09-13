"""V3 usability variant: deterministic, source-grounded highlights."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wvr_whole_video_report_v3 as v3


def entry(index, start, end, *activity):
    return {
        "entry_index": index,
        "start_sec": float(start),
        "end_sec": float(end),
        "broad_activity": list(activity),
        "source_chunk": "C01",
        "source_window": {"segment_id": f"S{index + 1:02}",
                          "start_sec": float(start), "end_sec": float(end)},
        "source_artifact_sha256": {"summary": "a" * 64},
    }


def test_adjacent_identical_activity_merges_without_expanding_boundary():
    # Catches merging a merely similar activity or losing source lineage.
    rows = [entry(0, 0, 10, "A"), entry(1, 10, 20, "A"),
            entry(2, 20, 30, "A", "B")]
    blocks = v3.build_blocks(rows, {"A", "B"}, 30.0)
    assert [(b["start_sec"], b["end_sec"], b["activities"],
             b["entry_indices"]) for b in blocks] == [
                 (0.0, 20.0, ["A"], [0, 1]),
                 (20.0, 30.0, ["A", "B"], [2]),
             ]
    assert blocks[0]["sources"][1]["source_window"]["segment_id"] == "S02"


def test_rejects_gap_and_unknown_activity():
    # Catches silently inventing time or admitting a noncanonical label.
    with pytest.raises(v3.V3Error, match="gap"):
        v3.build_blocks([entry(0, 0, 10, "A"), entry(1, 11, 20, "A")],
                        {"A"}, 20.0)
    with pytest.raises(v3.V3Error, match="unknown"):
        v3.build_blocks([entry(0, 0, 10, "X")], {"A"}, 10.0)


def test_six_strata_choose_max_overlap_and_preserve_final_phase():
    # Catches post-hoc selection, duplicate picks, and dropping the ending.
    rows = [entry(i, i * 30, (i + 1) * 30, chr(65 + i))
            for i in range(8)]
    blocks = v3.build_blocks(rows, {chr(65 + i) for i in range(8)}, 240.0)
    chosen = v3.select_highlights(blocks, [210.0, 240.0], 240.0)
    assert [b["start_sec"] for b in chosen] == [0.0, 30.0, 90.0,
                                                  120.0, 150.0, 210.0]
    assert chosen[-1]["activities"] == ["H"]


def test_report_preserves_v2_prose_and_hides_technical_codes():
    # Catches edits to PASS text or leaked beta/debug material in the body.
    baseline = {
        "short_overview": "첫 활동. 영상은 식사로 끝난다.",
        "detailed_overview": "첫 활동이 이어진다. 영상은 식사로 끝난다.",
        "analysis": "활동이 전환된다. 영상은 식사로 종료된다.",
        "conclusion": "활동이 이어진다. 영상은 식사로 끝난다.",
    }
    highlights = [{"highlight_id": "H01", "start_sec": 0.0,
                   "end_sec": 60.0, "activities": ["첫 활동"],
                   "description": "첫 활동이 이 구간에서 이어진다."},
                  {"highlight_id": "H02", "start_sec": 120.0,
                   "end_sec": 180.0, "activities": ["식사"],
                   "description": "식사가 이 구간에서 이어진다."}]
    body = v3.render_report(baseline, "첫 활동 뒤 식사가 이어진다.", highlights)
    for value in baseline.values():
        assert value in body
    assert "### 00:00–01:00" in body
    assert "### 02:00–03:00" in body
    assert "H01" not in body
    assert "OUTPUT_LANGUAGE_DRIFT" not in body
    assert "seg#" not in body
    assert "## 생성 및 근거 요약" in body
