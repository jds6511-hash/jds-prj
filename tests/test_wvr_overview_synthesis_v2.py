"""WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2 계약 테스트.

CANONICAL_FLOW가 결정적인지, machine check가 reviewer가 지적한 실패를 실제로
잡는지 확인한다. 모델을 올리지 않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_overview_synthesis_v2 as sv  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402

TIMELINE = (ROOT / "runs" / "wvr_whole_video_merge_v1" /
            "whole_video_activity_timeline.json")
needs_timeline = pytest.mark.skipif(not TIMELINE.is_file(),
                                    reason="frozen timeline 미존재")


def _timeline():
    return json.loads(TIMELINE.read_text(encoding="utf-8"))


def _fake_timeline(label_rows):
    return {"entries": [{"entry_index": i, "start_sec": i * 24.0,
                         "end_sec": (i + 1) * 24.0, "broad_activity": list(row)}
                        for i, row in enumerate(label_rows)],
            "temporal_coverage_sec": len(label_rows) * 24.0}


# ── CANONICAL_FLOW ─────────────────────────────────────────────────
def test_wvr_sv2_01_consecutive_identical_activities_collapse_into_one_phase():
    flow = sv.canonical_flow(_fake_timeline([["식사"], ["식사"], ["이동"]]))
    assert flow["phase_count"] == 2
    assert flow["phases"][0]["entry_count"] == 2
    assert flow["phases"][0]["start_sec"] == 0.0
    assert flow["phases"][0]["end_sec"] == 48.0


def test_wvr_sv2_02_final_phase_comes_from_the_last_entries_only():
    flow = sv.canonical_flow(_fake_timeline(
        [["음식 준비 및 조리"]] * 10 + [["식사"]]))
    assert flow["final_phase_activities"] == ["식사"]
    assert flow["final_phase_span"] == [240.0, 264.0]


def test_wvr_sv2_03_repetition_is_counted_not_asserted():
    flow = sv.canonical_flow(_fake_timeline([["식사"], ["이동"], ["식사"]]))
    assert flow["repeated_activities"] == ["식사"]
    assert flow["non_repeated_activities"] == ["이동"]


def test_wvr_sv2_04_canonical_flow_does_no_inference():
    flow = sv.canonical_flow(_fake_timeline([["식사"], ["이동"]]))
    assert flow["inference_count"] == 0


def test_wvr_sv2_05_canonical_flow_is_deterministic():
    timeline = _fake_timeline([["식사"], ["이동"], ["식사"], ["식사"]])
    a = json.dumps(sv.canonical_flow(timeline), ensure_ascii=False, sort_keys=True)
    b = json.dumps(sv.canonical_flow(timeline), ensure_ascii=False, sort_keys=True)
    assert a == b


def test_wvr_sv2_06_empty_timeline_is_red():
    with pytest.raises(sv.SynthesisV2Error):
        sv.canonical_flow({"entries": [], "temporal_coverage_sec": 0.0})


@needs_timeline
def test_wvr_sv2_07_real_timeline_final_phase_is_the_last_entries():
    timeline = _timeline()
    flow = sv.canonical_flow(timeline)
    last = timeline["entries"][-1]
    assert flow["final_phase_span"][1] == last["end_sec"] == 2424.0
    assert set(flow["final_phase_activities"]) <= set(ov.ACTIVITY_LABELS)


@needs_timeline
def test_wvr_sv2_08_phases_cover_the_timeline_without_gaps():
    flow = sv.canonical_flow(_timeline())
    phases = flow["phases"]
    assert phases[0]["start_sec"] == 0.0
    assert phases[-1]["end_sec"] == 2424.0
    for a, b in zip(phases, phases[1:]):
        assert a["end_sec"] == b["start_sec"]
    assert sum(p["entry_count"] for p in phases) == 96


# ── 프롬프트 ───────────────────────────────────────────────────────
@needs_timeline
def test_wvr_sv2_09_detailed_prompt_carries_the_final_phase_explicitly():
    flow = sv.canonical_flow(_timeline())
    prompt = sv.detailed_prompt(flow)
    assert "final_phase_activities" in prompt
    assert "마지막 문장" in prompt
    for term in ("빈번하게", "주기적으로", "핵심적인"):
        assert term in prompt          # 금지어로 명시돼 있어야 한다


@needs_timeline
def test_wvr_sv2_10_detailed_prompt_never_leaks_timestamps():
    flow = sv.canonical_flow(_timeline())
    payload_start = sv.detailed_prompt(flow).split("CANONICAL_FLOW:", 1)[1]
    assert "start_sec" not in payload_start
    assert "2424" not in payload_start


def test_wvr_sv2_11_short_prompt_embeds_the_detailed_body():
    body = "음식 준비 및 조리가 이어진다. 마지막은 식사다."
    prompt = sv.short_prompt(body)
    assert body in prompt
    assert "없는 활동" in prompt


# ── 본문 정리 ──────────────────────────────────────────────────────
def test_wvr_sv2_12_clean_body_strips_fences_and_headings():
    raw = "```\nDETAILED OVERVIEW\n식사가 이어진다.\n```"
    assert sv.clean_body(raw, what="detailed") == "식사가 이어진다."


def test_wvr_sv2_13_empty_output_is_red():
    with pytest.raises(sv.SynthesisV2Error):
        sv.clean_body("   ", what="short")


# ── machine check가 reviewer 지적을 실제로 잡는다 ──────────────────
def _flow_with_final(labels):
    return {"final_phase_activities": list(labels), "repeated_activities": []}


def test_wvr_sv2_14_final_phase_mismatch_is_caught():
    """V1에서 실제로 났던 실패다 — SHORT 종료부가 DETAILED와 달랐다."""
    detailed = "음식 준비 및 조리가 이어진다. 마지막으로 식사가 나타난다."
    short = "여러 활동이 이어진다. 마지막으로 정리 작업과 외출 준비가 나타난다."
    checks = sv.machine_checks(_flow_with_final(["식사"]), detailed, short)
    assert not checks["final_phase_short_equals_detailed"]["pass"]
    assert not checks["all_pass"]


def test_wvr_sv2_15_short_introducing_a_new_activity_is_caught():
    detailed = "식사가 이어진다. 마지막으로 식사가 나타난다."
    short = "식사와 이동이 이어진다. 마지막으로 식사가 나타난다."
    checks = sv.machine_checks(_flow_with_final(["식사"]), detailed, short)
    assert not checks["short_activity_subset_of_detailed"]["pass"]
    assert checks["short_activity_subset_of_detailed"]["short_only"] == ["이동"]


def test_wvr_sv2_16_overclaim_vocabulary_is_caught():
    """V1에서 실제로 났던 표현이다."""
    detailed = "이동과 구매가 빈번하게 삽입되어 일상적인 흐름을 이룬다. 마지막은 식사다."
    short = "식사로 끝난다."
    checks = sv.machine_checks(_flow_with_final(["식사"]), detailed, short)
    assert not checks["overclaim_terms"]["pass"]
    assert "빈번" in checks["overclaim_terms"]["detailed"]
    assert "일상적" in checks["overclaim_terms"]["detailed"]


def test_wvr_sv2_17_canonical_final_phase_mismatch_is_caught():
    detailed = "여러 활동이 이어진다. 마지막으로 이동이 나타난다."
    short = "마지막으로 이동이 나타난다."
    checks = sv.machine_checks(_flow_with_final(["식사"]), detailed, short)
    assert not checks["final_phase_matches_canonical"]["pass"]


def test_wvr_sv2_18_identifier_exposure_is_caught():
    detailed = "S01 구간에서 식사가 나타난다. 마지막으로 식사가 나타난다."
    short = "마지막으로 식사가 나타난다."
    checks = sv.machine_checks(_flow_with_final(["식사"]), detailed, short)
    assert not checks["identifier_exposure"]["pass"]


def test_wvr_sv2_19_context_inference_vocabulary_is_caught():
    detailed = "외출 준비 후 병원 일정을 위해 이동한다. 마지막으로 식사가 나타난다."
    short = "마지막으로 식사가 나타난다."
    checks = sv.machine_checks(_flow_with_final(["식사"]), detailed, short)
    assert not checks["context_terms"]["pass"]


def test_wvr_sv2_20_a_clean_pair_passes_every_check():
    detailed = ("음식 준비 및 조리가 먼저 나타나고 구매 또는 둘러보기로 바뀐다. "
                "이동과 포장 작업이 이어진 뒤 음식 준비 및 조리가 다시 나타난다. "
                "마지막으로 식사가 나타난다.")
    short = ("음식 준비 및 조리와 구매 또는 둘러보기가 이어지고 이동과 포장 작업이 나타난다. "
             "마지막으로 식사가 나타난다.")
    checks = sv.machine_checks(_flow_with_final(["식사"]), detailed, short)
    assert checks["all_pass"], checks


def test_wvr_sv2_21_sentence_split_uses_the_last_sentence_only():
    text = "식사가 나타난다. 이동이 나타난다. 마지막으로 정리 작업이 나타난다."
    assert sv.final_phase_labels(text) == {"정리 작업"}
