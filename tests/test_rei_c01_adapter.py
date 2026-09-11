"""WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1 adapter 테스트.

사전등록 §3~§5 동결 규칙과 §8 static gate의 negative check를 강제한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rei_c01_adapter as ad  # noqa: E402

WVR_DIR = ROOT / "runs" / "wvr_video_overview_preview_v2"
M3_PATH = ROOT / "work_full" / "full_xekZO4n4QuE" / "segments.json"


def _fake_summaries(n=ad.EXPECTED_WINDOW_COUNT):
    return [{"segment_id": "S%02d" % (i + 1),
             "BROAD_ACTIVITY": ["활동%d" % i],
             "OBSERVED_CHANGE": [],
             "CONTEXT_INFERENCE": [],
             "UNCERTAINTY": []} for i in range(n)]


def _fake_plan(n=ad.EXPECTED_WINDOW_COUNT):
    return [{"segment_id": "S%02d" % (i + 1),
             "start_sec": i * ad.STRIDE_SEC,
             "end_sec": min(i * ad.STRIDE_SEC + ad.WINDOW_SEC, ad.RANGE_END_SEC)}
            for i in range(n)]


def _fake_m3(n=120, seg=5.0):
    return [{"idx": i, "start": i * seg, "end": (i + 1) * seg,
             "subtitle": ("말%d" % i) if i % 2 == 0 else "",
             "caption": "c%d" % i} for i in range(n)]


# ── §3 기하 ────────────────────────────────────────────────────────
def test_rei_a01_overlap_view_geometry_is_frozen():
    got = [ad.interval(i, ad.OVERLAP_VIEW) for i in range(24)]
    assert got[0] == (0.0, 48.0)
    assert got[1] == (24.0, 72.0)
    assert got[23] == (552.0, 600.0)
    assert all(s == i * 24.0 for i, (s, _) in enumerate(got))


def test_rei_a02_nonoverlap_view_geometry_is_frozen():
    got = [ad.interval(i, ad.NONOVERLAP_VIEW) for i in range(24)]
    assert got[0] == (0.0, 24.0)
    assert got[22] == (528.0, 552.0)
    assert got[23] == (552.0, 600.0)   # 마지막만 stride를 넘어 600까지 덮는다


def test_rei_a03_both_views_satisfy_engine_alpha_start_invariant():
    for view in ad.VIEWS:
        for i in range(24):
            start, _ = ad.interval(i, view)
            assert start == i * ad.STRIDE_SEC


def test_rei_a04_nonoverlap_view_has_zero_duplicate_coverage():
    rows = [{"start": s, "end": e}
            for s, e in (ad.interval(i, ad.NONOVERLAP_VIEW) for i in range(24))]
    assert ad.duplicate_coverage_sec(rows) == 0.0
    assert ad.temporal_coverage_sec(rows) == 600.0


def test_rei_a05_overlap_view_duplicates_are_material_and_measured():
    rows = [{"start": s, "end": e}
            for s, e in (ad.interval(i, ad.OVERLAP_VIEW) for i in range(24))]
    assert ad.duplicate_coverage_sec(rows) > 0
    assert ad.temporal_coverage_sec(rows) == 600.0


def test_rei_a06_unknown_view_is_rejected():
    with pytest.raises(ad.AdapterError):
        ad.interval(0, "BEST_VIEW")


# ── §4 caption ─────────────────────────────────────────────────────
def test_rei_a07_caption_uses_broad_fields_only():
    cap = ad.build_caption({"BROAD_ACTIVITY": ["음식 준비 및 조리", "식사"],
                            "OBSERVED_CHANGE": ["조리 → 식사"],
                            "CONTEXT_INFERENCE": ["넣으면 안 되는 추론"],
                            "UNCERTAINTY": ["넣으면 안 되는 불확실성"]})
    assert "음식 준비 및 조리 · 식사" in cap
    assert "조리 → 식사" in cap
    assert "넣으면 안 되는 추론" not in cap
    assert "넣으면 안 되는 불확실성" not in cap


def test_rei_a08_caption_empty_marker_when_no_broad_content():
    assert ad.build_caption({"BROAD_ACTIVITY": [], "OBSERVED_CHANGE": [],
                             "CONTEXT_INFERENCE": [], "UNCERTAINTY": []}) \
        == ad.EMPTY_CAPTION


def test_rei_a09_caption_source_schema_mismatch_is_red():
    with pytest.raises(ad.AdapterError):
        ad.build_caption({"BROAD_ACTIVITY": ["x"], "OBSERVED_CHANGE": []})


# ── §5 subtitle ────────────────────────────────────────────────────
def test_rei_a10_subtitle_includes_positive_overlap_only():
    m3 = [{"idx": 0, "start": 0.0, "end": 24.0, "subtitle": "a"},
          {"idx": 1, "start": 24.0, "end": 29.0, "subtitle": "b"},   # 접점 아님, 포함
          {"idx": 2, "start": 20.0, "end": 25.0, "subtitle": "c"}]
    picked = ad.aggregate_subtitle(m3, 24.0, 48.0)
    idxs = [s["idx"] for s in picked]
    assert 0 not in idxs      # [0,24) 는 접점만 닿는다 → 제외
    assert idxs == [2, 1]     # start 오름차순: 20.0 < 24.0


def test_rei_a11_subtitle_join_is_single_space_and_drops_empty():
    m3 = [{"idx": 0, "start": 0.0, "end": 5.0, "subtitle": " 가 "},
          {"idx": 1, "start": 5.0, "end": 10.0, "subtitle": ""},
          {"idx": 2, "start": 10.0, "end": 15.0, "subtitle": "나"}]
    assert ad.subtitle_text(ad.aggregate_subtitle(m3, 0.0, 24.0)) == "가 나"


def test_rei_a12_subtitle_aggregation_is_deterministic():
    m3 = _fake_m3()
    first = ad.subtitle_text(ad.aggregate_subtitle(m3, 24.0, 72.0))
    second = ad.subtitle_text(ad.aggregate_subtitle(list(reversed(m3)), 24.0, 72.0))
    assert first == second


# ── build_view 계약 ────────────────────────────────────────────────
def test_rei_a13_build_view_emits_required_fields_for_every_segment():
    for view in ad.VIEWS:
        out = ad.build_view(_fake_summaries(), _fake_plan(), _fake_m3(), view)
        segs = out["doc"]["segments"]
        assert len(segs) == 24
        for s in segs:
            assert "subtitle" in s and "caption" in s
            assert s["end"] > s["start"]


def test_rei_a14_build_view_lineage_is_complete():
    out = ad.build_view(_fake_summaries(), _fake_plan(), _fake_m3(), ad.OVERLAP_VIEW)
    assert len(out["lineage"]) == 24
    for row in out["lineage"]:
        assert set(row) == {"adapter_idx", "wvr_window", "broad_visual_summary",
                            "adapter_segment", "subtitle_source_m3_idx"}
        assert row["wvr_window"]["segment_id"].startswith("S")


def test_rei_a15_build_view_is_deterministic():
    args = (_fake_summaries(), _fake_plan(), _fake_m3(), ad.NONOVERLAP_VIEW)
    a = json.dumps(ad.build_view(*args), ensure_ascii=False, sort_keys=True)
    b = json.dumps(ad.build_view(*args), ensure_ascii=False, sort_keys=True)
    assert a == b


def test_rei_a16_window_count_mismatch_is_red():
    with pytest.raises(ad.AdapterError):
        ad.build_view(_fake_summaries(23), _fake_plan(23), _fake_m3(), ad.OVERLAP_VIEW)


def test_rei_a17_window_start_off_frozen_grid_is_red():
    plan = _fake_plan()
    plan[3]["start_sec"] = 100.0          # 동결 격자 이탈
    with pytest.raises(ad.AdapterError):
        ad.build_view(_fake_summaries(), plan, _fake_m3(), ad.OVERLAP_VIEW)


def test_rei_a18_provenance_records_zero_new_inference():
    out = ad.build_view(_fake_summaries(), _fake_plan(), _fake_m3(), ad.OVERLAP_VIEW)
    assert out["doc"]["provenance"]["new_inference_count"] == 0
    assert out["doc"]["provenance"]["event"] == ad.EVENT


# ── §2 frozen source ───────────────────────────────────────────────
@pytest.mark.skipif(not WVR_DIR.exists() or not M3_PATH.exists(),
                    reason="frozen source 미존재")
def test_rei_a19_frozen_source_hashes_match_prereg():
    loaded = ad.load_sources(WVR_DIR, M3_PATH)
    assert loaded["source_sha256"] == ad.FROZEN_SHA256
    assert len(loaded["summaries"]) == ad.EXPECTED_WINDOW_COUNT


@pytest.mark.skipif(not M3_PATH.exists(), reason="baseline 입력 미존재")
def test_rei_a20_m3_source_is_submission_baseline_input_and_readonly():
    """이 파일 해시는 제출 manifest의 input.segments_sha256과 같아야 한다."""
    manifest = ROOT / "runs" / "v3_paired" / "submission_manifest.json"
    if not manifest.exists():
        pytest.skip("submission manifest 미존재")
    with open(manifest, encoding="utf-8") as f:
        declared = json.load(f)["input"]["segments_sha256"]
    assert ad.sha256_file(M3_PATH) == declared == \
        ad.FROZEN_SHA256["work_full_segments.json"]
