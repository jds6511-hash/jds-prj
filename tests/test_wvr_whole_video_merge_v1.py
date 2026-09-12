"""WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1 merge 계약 테스트.

사전등록 §3 중복 제거 규칙과 §8 gate를 코드가 실제로 강제하는지 확인한다.
모델을 올리지 않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_chunk_overview_v2 as cv  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402
import wvr_whole_video_merge_v1 as wm  # noqa: E402

SOURCES_PRESENT = all(
    (wm.chunk_dir(ROOT, c) / "video_overview_v2_segment_summaries.json").is_file()
    for c in wm.CHUNK_IDS)
needs_sources = pytest.mark.skipif(not SOURCES_PRESENT,
                                   reason="frozen C01~C05 산출물 미존재")


# ── §3-2 chunk 소유 규칙은 내용이 아니라 index로 정해진다 ───────────
def test_wvr_wm_01_ownership_is_lowest_chunk_index_and_contiguous():
    owned = wm.ownership()
    assert owned == {"C01": (0.0, 600.0), "C02": (600.0, 1080.0),
                     "C03": (1080.0, 1560.0), "C04": (1560.0, 2040.0),
                     "C05": (2040.0, 2424.0)}


def test_wvr_wm_02_ownership_stops_at_the_observed_end_not_the_video_end():
    assert wm.ownership()["C05"][1] == wm.OBSERVED_END_SEC == 2424.0
    assert wm.VIDEO_DURATION_SEC > wm.OBSERVED_END_SEC


def test_wvr_wm_03_terminal_remainder_is_recorded_not_synthesised():
    start, end = wm.TERMINAL_REMAINDER
    assert (start, end) == (2424.0, 2424.186485)
    assert round(end - start, 6) == 0.186485


# ── §3-1 window NONOVERLAP 정규화 ──────────────────────────────────
def test_wvr_wm_04_nonoverlap_spans_use_stride_except_the_last_window():
    spans = wm.nonoverlap_spans("C02")
    assert spans[0] == (480.0, 504.0)
    assert spans[-2] == (1008.0, 1032.0)
    assert spans[-1] == (1032.0, 1080.0)      # 마지막 창만 관찰 끝까지


def test_wvr_wm_05_nonoverlap_spans_have_zero_duplication_within_a_chunk():
    for chunk_id in wm.CHUNK_IDS:
        spans = wm.nonoverlap_spans(chunk_id)
        for a, b in zip(spans, spans[1:]):
            assert a[1] == b[0]


def test_wvr_wm_06_ownership_boundaries_fall_on_window_boundaries():
    """경계가 창 경계와 어긋나면 구간을 잘라야 한다 — 그런 일이 없어야 한다."""
    owned = wm.ownership()
    for chunk_id in wm.CHUNK_IDS:
        edges = {s for span in wm.nonoverlap_spans(chunk_id) for s in span}
        start, end = owned[chunk_id]
        assert start in edges or start == 0.0
        assert end in edges


# ── §1 frozen source ───────────────────────────────────────────────
@needs_sources
def test_wvr_wm_07_frozen_source_hashes_match_the_preregistration():
    for chunk_id in wm.CHUNK_IDS:
        loaded = wm.load_chunk(ROOT, chunk_id)
        assert loaded["sha256"] == wm.FROZEN_SHA256[chunk_id]


@needs_sources
def test_wvr_wm_08_chunk_plan_in_the_artifact_matches_the_frozen_geometry():
    for chunk_id in wm.CHUNK_IDS:
        assert wm.load_chunk(ROOT, chunk_id)["plan"] == cv.segments(chunk_id)


# ── §8 gate 조건을 build_timeline이 스스로 강제한다 ────────────────
@needs_sources
def test_wvr_wm_09_timeline_covers_zero_to_observed_end_without_gaps():
    timeline = wm.build_timeline(ROOT)
    assert timeline["temporal_coverage_sec"] == 2424.0
    assert timeline["duplicate_coverage_after_sec"] == 0.0
    assert timeline["entries"][0]["start_sec"] == 0.0
    assert timeline["entries"][-1]["end_sec"] == 2424.0


@needs_sources
def test_wvr_wm_10_entries_are_contiguous_and_non_overlapping():
    entries = wm.build_timeline(ROOT)["entries"]
    for a, b in zip(entries, entries[1:]):
        assert a["end_sec"] == b["start_sec"]
        assert b["entry_index"] == a["entry_index"] + 1


@needs_sources
def test_wvr_wm_11_every_entry_carries_full_lineage():
    timeline = wm.build_timeline(ROOT)
    for entry in timeline["entries"]:
        assert entry["source_chunk"] in wm.CHUNK_IDS
        assert entry["source_window"]["segment_id"].startswith("S")
        assert set(entry["source_artifact_sha256"]) == \
            set(wm.FROZEN_SHA256[entry["source_chunk"]])
        window = entry["source_window"]
        assert window["start_sec"] <= entry["start_sec"]
        assert entry["end_sec"] <= window["end_sec"]
    assert len(timeline["lineage"]) == timeline["entry_count"]


@needs_sources
def test_wvr_wm_12_merge_is_deterministic():
    first = json.dumps(wm.build_timeline(ROOT), ensure_ascii=False, sort_keys=True)
    second = json.dumps(wm.build_timeline(ROOT), ensure_ascii=False, sort_keys=True)
    assert first == second


@needs_sources
def test_wvr_wm_13_duplicate_exposure_before_normalisation_is_material():
    timeline = wm.build_timeline(ROOT)
    assert timeline["duplicate_coverage_before_sec"] > 0
    assert timeline["new_visual_inference"] == 0
    assert timeline["new_stt_inference"] == 0


@needs_sources
def test_wvr_wm_14_labels_are_copied_verbatim_from_the_source():
    timeline = wm.build_timeline(ROOT)
    by_chunk: dict[str, list] = {}
    for chunk_id in wm.CHUNK_IDS:
        by_chunk[chunk_id] = {s["segment_id"]: s["BROAD_ACTIVITY"]
                              for s in wm.load_chunk(ROOT, chunk_id)["summaries"]}
    for entry in timeline["entries"]:
        source = by_chunk[entry["source_chunk"]][
            entry["source_window"]["segment_id"]]
        assert entry["broad_activity"] == list(source)


# ── §5·§6 synthesis 입력 ───────────────────────────────────────────
@needs_sources
def test_wvr_wm_15_synthesis_uses_the_v2_prompt_unchanged():
    timeline = wm.build_timeline(ROOT)
    prompt, compressed = wm.synthesis_prompt(timeline)
    assert "SHORT OVERVIEW" in prompt and "DETAILED OVERVIEW" in prompt
    assert prompt == ov.synthesis_prompt(compressed)


@needs_sources
def test_wvr_wm_16_synthesis_input_carries_no_invented_context():
    timeline = wm.build_timeline(ROOT)
    rows = wm.synthesis_summaries(timeline)
    assert all(r["OBSERVED_CHANGE"] == [] for r in rows)
    assert all(set(r) == {"segment_id", "BROAD_ACTIVITY", "OBSERVED_CHANGE"}
               for r in rows)


@needs_sources
def test_wvr_wm_17_markdown_view_lists_every_entry():
    timeline = wm.build_timeline(ROOT)
    text = wm.timeline_markdown(timeline)
    assert text.count("\n| ") >= timeline["entry_count"]
    assert "terminal remainder" in text


# ── negative check ─────────────────────────────────────────────────
def test_wvr_wm_18_source_hash_mismatch_is_red(tmp_path):
    (tmp_path / wm.C01_RUNS).mkdir(parents=True)
    for name in wm.FROZEN_SHA256["C01"]:
        (tmp_path / wm.C01_RUNS / name).write_text("[]", encoding="utf-8")
    with pytest.raises(wm.MergeError):
        wm.load_chunk(tmp_path, "C01")


def test_wvr_wm_19_validate_rejects_a_gap():
    with pytest.raises(wm.MergeError):
        wm._validate([{"entry_index": 0, "start_sec": 0.0, "end_sec": 24.0},
                      {"entry_index": 1, "start_sec": 48.0, "end_sec": 72.0}])


def test_wvr_wm_20_validate_rejects_an_overlap():
    with pytest.raises(wm.MergeError):
        wm._validate([{"entry_index": 0, "start_sec": 0.0, "end_sec": 24.0},
                      {"entry_index": 1, "start_sec": 12.0, "end_sec": 36.0}])
