"""WVR_WHOLE_VIDEO_REPORT_V1 계약 테스트.

24초 격자 정규화가 내용을 바꾸지 않는지, machine check가 규칙 위반을 잡는지
확인한다. 모델을 올리지 않는다.
"""
from __future__ import annotations

import json
import sys
import weakref
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_overview_synthesis_v2 as sv  # noqa: E402
import wvr_whole_video_report_v1 as wr  # noqa: E402
import wvr_whole_video_report_v1_run as run  # noqa: E402

TIMELINE = (ROOT / "runs" / "wvr_whole_video_merge_v1" /
            "whole_video_activity_timeline.json")
FLOW = ROOT / "runs" / "wvr_overview_synthesis_v2" / "canonical_flow.json"
OVERVIEW = ROOT / "runs" / "wvr_overview_synthesis_v2" / "overview_result.json"
M3 = ROOT / "work_full" / "full_xekZO4n4QuE" / "segments.json"

needs_branch = pytest.mark.skipif(
    not (TIMELINE.is_file() and FLOW.is_file() and OVERVIEW.is_file()),
    reason="Overview branch 미존재")


def _timeline():
    return json.loads(TIMELINE.read_text(encoding="utf-8"))


def _fake_timeline(spans):
    return {"entries": [{"entry_index": i, "start_sec": s, "end_sec": e,
                         "broad_activity": ["식사"], "source_chunk": "C01",
                         "source_window": {"segment_id": "S01",
                                           "start_sec": s, "end_sec": e}}
                        for i, (s, e) in enumerate(spans)]}


# ── §4-1 격자 정규화 ───────────────────────────────────────────────
def test_wvr_wr_01_twenty_four_second_entries_pass_through():
    spans = [(i * 24.0, i * 24.0 + 24.0) for i in range(101)]
    rows = wr.split_entries(_fake_timeline(spans))
    assert len(rows) == 101
    assert all(r["source_entry_part_count"] == 1 for r in rows)
    assert rows[-1]["end"] == 2424.0


def test_wvr_wr_02_forty_eight_second_entry_splits_into_two():
    spans = [(i * 24.0, i * 24.0 + 24.0) for i in range(100)]
    spans[-1] = (2376.0, 2424.0)          # 마지막만 48초
    rows = wr.split_entries(_fake_timeline(spans))
    assert len(rows) == 101
    assert rows[-2]["source_entry_index"] == rows[-1]["source_entry_index"] == 99
    assert rows[-2]["broad_activity"] == rows[-1]["broad_activity"]


def test_wvr_wr_03_unexpected_span_is_red():
    with pytest.raises(wr.ReportError):
        wr.split_entries(_fake_timeline([(0.0, 30.0)]))


@needs_branch
def test_wvr_wr_04_real_timeline_yields_the_frozen_segment_count():
    rows = wr.split_entries(_timeline())
    assert len(rows) == wr.EXPECTED_SEGMENT_COUNT == 101
    assert rows[-1]["end"] == wr.TOTAL_COVERAGE_SEC == 2424.0


@needs_branch
def test_wvr_wr_05_grid_invariant_holds_for_every_segment():
    for row in wr.split_entries(_timeline()):
        assert row["start"] == row["idx"] * wr.SEG_LEN_SEC


@needs_branch
def test_wvr_wr_06_exactly_five_entries_are_split():
    rows = wr.split_entries(_timeline())
    split = {r["source_entry_index"] for r in rows
             if r["source_entry_part_count"] == 2}
    assert split == {23, 42, 61, 80, 95}


@needs_branch
@pytest.mark.skipif(not M3.is_file(), reason="M3 STT 미존재")
def test_wvr_wr_06b_split_entry_stat_counts_sources_not_pieces():
    m3 = json.loads(M3.read_text(encoding="utf-8"))["segments"]
    stats = wr.build_segments(_timeline(), m3)["stats"]
    assert stats["split_entry_count"] == 5


@needs_branch
def test_wvr_wr_07_split_pieces_keep_the_source_activity_verbatim():
    timeline = _timeline()
    by_index = {e["entry_index"]: e for e in timeline["entries"]}
    for row in wr.split_entries(timeline):
        assert row["broad_activity"] == list(
            by_index[row["source_entry_index"]]["broad_activity"])


# ── §4-2 caption ───────────────────────────────────────────────────
def test_wvr_wr_08_caption_joins_labels_verbatim():
    assert wr.build_caption(["식사", "이동"]) == "식사 · 이동"


def test_wvr_wr_09_empty_activity_gets_the_empty_marker():
    assert wr.build_caption([]) == wr.EMPTY_CAPTION


# ── §4-3 subtitle ──────────────────────────────────────────────────
@needs_branch
@pytest.mark.skipif(not M3.is_file(), reason="M3 STT 미존재")
def test_wvr_wr_10_segments_carry_subtitle_and_caption_for_every_row():
    m3 = json.loads(M3.read_text(encoding="utf-8"))["segments"]
    built = wr.build_segments(_timeline(), m3)
    segments = built["doc"]["segments"]
    assert len(segments) == 101
    assert all("subtitle" in s and "caption" in s for s in segments)
    assert built["stats"]["duplicate_coverage_sec"] == 0.0
    assert built["stats"]["temporal_coverage_sec"] == 2424.0


@needs_branch
@pytest.mark.skipif(not M3.is_file(), reason="M3 STT 미존재")
def test_wvr_wr_11_build_is_deterministic():
    m3 = json.loads(M3.read_text(encoding="utf-8"))["segments"]
    a = json.dumps(wr.build_segments(_timeline(), m3), ensure_ascii=False,
                   sort_keys=True)
    b = json.dumps(wr.build_segments(_timeline(), m3), ensure_ascii=False,
                   sort_keys=True)
    assert a == b


@needs_branch
@pytest.mark.skipif(not M3.is_file(), reason="M3 STT 미존재")
def test_wvr_wr_12_provenance_declares_zero_new_inference():
    m3 = json.loads(M3.read_text(encoding="utf-8"))["segments"]
    doc = wr.build_segments(_timeline(), m3)["doc"]
    assert doc["provenance"]["new_inference_count"] == 0
    assert doc["provenance"]["m3_segments_sha256"] == wr.M3_SEGMENTS_SHA256


# ── §2·§3 프롬프트 ─────────────────────────────────────────────────
@needs_branch
def test_wvr_wr_13_analysis_prompt_forbids_intent_and_exposes_final_phase():
    flow = json.loads(FLOW.read_text(encoding="utf-8"))
    overview = json.loads(OVERVIEW.read_text(encoding="utf-8"))
    prompt = wr.analysis_prompt(flow, overview["detailed_overview"])
    assert "의도" in prompt and "감정" in prompt and "생활 습관" in prompt
    assert "final_phase_activities" in prompt
    assert "새로운 사건" in prompt


@needs_branch
def test_wvr_wr_14_analysis_prompt_never_leaks_timestamps():
    flow = json.loads(FLOW.read_text(encoding="utf-8"))
    overview = json.loads(OVERVIEW.read_text(encoding="utf-8"))
    payload = wr.analysis_prompt(flow, overview["detailed_overview"])
    payload = payload.split("CANONICAL_FLOW:", 1)[1]
    assert "start_sec" not in payload
    assert "2424" not in payload


def test_wvr_wr_15_conclusion_prompt_carries_all_three_inputs():
    prompt = wr.conclusion_prompt("짧다.", "자세하다.", "분석이다.")
    assert "짧다." in prompt and "자세하다." in prompt and "분석이다." in prompt
    assert "새로운 근거를 추가하지 마십시오" in prompt


# ── §8 machine check ───────────────────────────────────────────────
def _flow(final):
    return {"final_phase_activities": list(final)}


def _overview(detailed, short):
    return {"detailed_overview": detailed, "short_overview": short}


def test_wvr_wr_16_clean_texts_pass_every_check():
    overview = _overview("식사와 이동이 이어진다. 영상은 식사로 끝난다.",
                         "식사가 이어진다. 영상은 식사로 끝난다.")
    analysis = "식사와 이동이 번갈아 나타난다. 영상은 식사로 끝난다."
    conclusion = "식사와 이동이 이어진다. 영상은 식사로 끝난다."
    checks = wr.machine_checks(_flow(["식사"]), overview, analysis, conclusion)
    assert checks["all_pass"], checks


def test_wvr_wr_17_analysis_final_phase_mismatch_is_caught():
    overview = _overview("식사가 이어진다. 영상은 식사로 끝난다.",
                         "영상은 식사로 끝난다.")
    analysis = "식사가 나타난다. 영상은 이동으로 끝난다."
    checks = wr.machine_checks(_flow(["식사"]), overview, analysis,
                               "영상은 식사로 끝난다.")
    assert not checks["analysis_final_phase_matches_canonical"]["pass"]


def test_wvr_wr_18_conclusion_introducing_new_evidence_is_caught():
    overview = _overview("식사가 이어진다. 영상은 식사로 끝난다.",
                         "영상은 식사로 끝난다.")
    analysis = "식사가 나타난다. 영상은 식사로 끝난다."
    conclusion = "식사와 포장 작업이 이어진다. 영상은 식사로 끝난다."
    checks = wr.machine_checks(_flow(["식사"]), overview, analysis, conclusion)
    assert not checks["conclusion_activity_subset_of_overview_and_analysis"]["pass"]
    assert checks["conclusion_activity_subset_of_overview_and_analysis"][
        "conclusion_only"] == ["포장 작업"]


def test_wvr_wr_19_context_inference_in_analysis_is_caught():
    overview = _overview("식사가 이어진다. 영상은 식사로 끝난다.",
                         "영상은 식사로 끝난다.")
    analysis = "외출 준비는 직장 일정 때문으로 보인다. 영상은 식사로 끝난다."
    checks = wr.machine_checks(_flow(["식사"]), overview, analysis,
                               "영상은 식사로 끝난다.")
    assert not checks["analysis_context_terms"]["pass"]


def test_wvr_wr_20_overclaim_in_conclusion_is_caught():
    overview = _overview("식사가 이어진다. 영상은 식사로 끝난다.",
                         "영상은 식사로 끝난다.")
    analysis = "식사가 나타난다. 영상은 식사로 끝난다."
    conclusion = "식사가 주기적으로 나타난다. 영상은 식사로 끝난다."
    checks = wr.machine_checks(_flow(["식사"]), overview, analysis, conclusion)
    assert not checks["conclusion_overclaim_terms"]["pass"]


# ── 최종 보고서 조립 ───────────────────────────────────────────────
def test_wvr_wr_21_final_report_has_every_section():
    overview = _overview("자세한 개요다.", "짧은 개요다.")
    text = wr.final_report_markdown(overview, "분석이다.", "결론이다.",
                                    {"segment_count": 101})
    for heading in ("## 개요", "## 상세 개요", "## 분석", "## 결론",
                    "## 근거 및 생성 정보"):
        assert heading in text
    assert "짧은 개요다." in text and "결론이다." in text


def test_wvr_wr_22_report_module_reuses_the_frozen_check_vocabulary():
    assert wr.machine_checks.__module__ == "wvr_whole_video_report_v1"
    assert sv.OVERCLAIM_TERMS and sv.CONTEXT_TERMS


# ── 승인된 Overview + β/v3 보조 구간 최종 조립 ─────────────────────
def test_wvr_wr_23_extracts_only_beta_support_section():
    engine_report = """# engine report

## 개요

엔진이 만든 별도 개요

## 주요 사건 및 내용

### H01
- 요약: 보조 요약

## 핵심 내용 분석

엔진이 만든 별도 분석
"""
    support = wr.extract_beta_support(engine_report)
    assert "### H01" in support and "보조 요약" in support
    assert "엔진이 만든 별도 개요" not in support
    assert "엔진이 만든 별도 분석" not in support


def test_wvr_wr_24_final_report_keeps_frozen_overview_verbatim():
    overview = _overview("동결 상세 개요", "동결 짧은 개요")
    report = wr.final_report_markdown(
        overview, "새 분석", "새 결론", {"segment_count": 101},
        beta_support="### H01\n- 요약: 보조 요약")
    assert "## 개요\n\n동결 짧은 개요" in report
    assert "## 상세 개요\n\n동결 상세 개요" in report
    assert "## 분석\n\n새 분석" in report
    assert "## 결론\n\n새 결론" in report
    assert "## β/v3 보조 구간 요약\n\n### H01" in report


def test_wvr_wr_25_report_lines_preserve_every_nonempty_body_line():
    markdown = "# 보고서\n\n## 개요\n\n동결 개요\n\n## 결론\n\n결론"
    lines = wr.report_lines(markdown)
    assert lines == ["# 보고서", "", "## 개요", "", "동결 개요", "",
                     "## 결론", "", "결론"]


def test_wvr_wr_26_beta_metrics_expose_exclusions_and_fallbacks():
    canonical = {"episodes": [
        {"episode_id": "EP01", "content_status": "VALID_PARSE"},
        {"episode_id": "EP02", "content_status": "PARSE_CONTRACT_FAILURE"},
    ]}
    presentation = {"highlights": [
        {"highlight_id": "H01", "summary_status": "AVAILABLE",
         "excluded_summary_episode_ids": []},
        {"highlight_id": "H02", "summary_status": "NO_RELIABLE_CONTENT",
         "excluded_summary_episode_ids": ["EP02"]},
    ]}
    manifest = {"distributions": {
        "counters": {"llm_calls": 2, "prompt_refusals": 0,
                     "llm_failures": 0, "retries": 0},
        "presentation": {"episodes": 2, "eligible": 1,
                         "excluded_by_dialogue_grounding": 0}}}
    metrics = wr.beta_metrics(canonical, presentation, manifest)
    assert metrics["eligible"] == 1
    assert metrics["excluded"] == 1
    assert metrics["quality_exclusions"] == {"EP02": "PARSE_CONTRACT_FAILURE"}
    assert metrics["fallback"] == {"prompt_refusals": 0, "llm_failures": 0,
                                   "retries": 0}


def test_wvr_wr_27_release_runtime_drops_model_and_processor_references():
    class Payload:
        pass

    class Runtime:
        pass

    runtime = Runtime()
    runtime.model = Payload()
    runtime.processor = Payload()
    model_ref = weakref.ref(runtime.model)
    processor_ref = weakref.ref(runtime.processor)
    run.release_runtime(runtime)
    assert not hasattr(runtime, "model")
    assert not hasattr(runtime, "processor")
    assert model_ref() is None and processor_ref() is None


def test_wvr_wr_28_frozen_text_hash_ignores_only_crlf(tmp_path):
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    changed = tmp_path / "changed.json"
    lf.write_bytes(b'{\n  "value": 1\n}\n')
    crlf.write_bytes(b'{\r\n  "value": 1\r\n}\r\n')
    changed.write_bytes(b'{\n  "value": 2\n}\n')
    assert wr.frozen_text_sha(lf) == wr.frozen_text_sha(crlf)
    assert wr.frozen_text_sha(lf) != wr.frozen_text_sha(changed)
