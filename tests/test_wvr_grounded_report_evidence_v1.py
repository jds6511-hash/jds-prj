"""Frozen raw-grounding contract for WVR_GROUNDED_REPORT_EVIDENCE_V1."""
from collections import Counter
from pathlib import Path
import copy
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wvr_grounded_report_evidence_v1 as ge


REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "음식 준비 및 조리", "식사", "의류 작업 및 수선", "포장 작업",
    "외출 준비", "이동", "구매 또는 둘러보기", "정리 작업",
    "기타 명확한 주요 활동", "불명확",
}


def valid_raw(extra=""):
    body = {
        "BROAD_ACTIVITY": ["음식 준비 및 조리"],
        "OBSERVED_CHANGE": [],
        "CONTEXT_INFERENCE": [],
        "UNCERTAINTY": [],
    }
    return (json.dumps(body, ensure_ascii=False) + extra).encode("utf-8")


def fixture_source(tmp_path, window="S01", plan_windows=None):
    raw = tmp_path / f"video_overview_v2_segment_{window}_raw.txt"
    raw.write_bytes(valid_raw())
    return {
        "chunk": "C01",
        "window": window,
        "start_sec": 0.0,
        "end_sec": 48.0,
        "raw_path": raw.name,
        "raw_abs": str(raw),
        "plan_window_ids": sorted(plan_windows or {window}),
    }


def valid_observation():
    return {
        "observation_id": "GO0001",
        "start_sec": 0.0,
        "end_sec": 48.0,
        "broad_activity": ["음식 준비 및 조리"],
        "visual_facts": [{
            "text": "재료를 손으로 다루고 그릇에 옮긴다",
            "source_text": "재료를 손으로 다루고 그릇에 옮긴다",
            "confidence": "high",
            "source_span": [0.0, 48.0],
        }],
        "observed_change": [],
        "uncertainty": [],
        "source": {
            "chunk": "C01", "window": "S01", "raw_path": "raw.txt",
            "raw_sha256": "a" * 64,
        },
    }


def test_raw_universe_has_frozen_counts_and_manifest():
    rows = ge.raw_universe(REPO_ROOT)
    assert Counter(r["chunk"] for r in rows) == {
        "C01": 24, "C02": 24, "C03": 24, "C04": 24, "C05": 20,
    }
    assert len(rows) == 116
    assert ge.manifest_sha256(rows) == (
        "8c40bbe26b2e5e4e56800dbb5c87799e8d91c9df970bfac4a1e212c544cba485"
    )


def test_unknown_source_window_fails_closed(tmp_path):
    source = fixture_source(tmp_path, window="S99", plan_windows={"S01"})
    with pytest.raises(ge.GroundingError, match="unknown source window"):
        ge.audit_one(source, valid_raw(), ALLOWED)


def test_detail_outside_source_interval_fails_closed():
    observation = valid_observation()
    observation["visual_facts"][0]["source_span"] = [48.0, 72.0]
    with pytest.raises(ge.GroundingError, match="outside source interval"):
        ge.validate_observation(observation)


@pytest.mark.parametrize("field,text,reason", [
    ("BROAD_ACTIVITY", "음식 준비 및 조리", "broad_label_only"),
    ("OBSERVED_CHANGE", "식사 → 이동", "canonical_transition_only"),
    ("CONTEXT_INFERENCE", "병원에서 퇴원한 것으로 보임", "context_inference"),
    ("UNCERTAINTY", "재료를 다루는지 불명확함", "uncertainty_only"),
])
def test_four_contract_fields_never_become_visual_fact(field, text, reason):
    assert ge.classify_text(field, text)["rejection_reason"] == reason


@pytest.mark.parametrize("text", [
    "여행을 계획하며 물건을 포장한다",
    "기분이 좋아 음식을 먹는다",
    "직장 업무를 위해 옷을 손질한다",
])
def test_unsupported_context_phrase_is_rejected(text):
    assert ge.classify_text("RAW_EXTRA", text)["eligible"] is False


def test_explicit_visible_fact_is_retained_with_verbatim_source():
    text = "재료를 손으로 다루고 그릇에 옮긴다"
    got = ge.classify_text("RAW_EXTRA", text)
    assert got == {
        "eligible": True,
        "text": text,
        "source_text": text,
        "confidence": "high",
        "rejection_reason": None,
    }


def audit_fixture(index, activity, *, fact=True):
    raw_hash = f"{index:064x}"[-64:]
    facts = []
    if fact:
        facts = [{
            "text": f"재료를 손으로 다룬다 {index}",
            "source_text": f"재료를 손으로 다룬다 {index}",
            "confidence": "high",
            "source_span": [float(index * 10), float(index * 10 + 10)],
        }]
    return {
        "chunk": "C01", "window": f"S{index + 1:02}",
        "start_sec": float(index * 10), "end_sec": float(index * 10 + 10),
        "raw_path": f"raw-{index}.txt", "raw_sha256": raw_hash,
        "BROAD_ACTIVITY": [activity], "eligible_visual_facts": facts,
        "observation": {
            "observation_id": f"GO{index + 1:04}",
            "start_sec": float(index * 10),
            "end_sec": float(index * 10 + 10),
            "broad_activity": [activity], "visual_facts": facts,
            "observed_change": [], "uncertainty": [],
            "source": {"chunk": "C01", "window": f"S{index + 1:02}",
                       "raw_path": f"raw-{index}.txt", "raw_sha256": raw_hash},
        },
    }


def gate_timeline():
    return {"entries": [
        {"start_sec": 0.0, "end_sec": 100.0, "broad_activity": ["A"]},
        {"start_sec": 100.0, "end_sec": 180.0, "broad_activity": ["B"]},
        {"start_sec": 180.0, "end_sec": 190.0, "broad_activity": ["C"]},
    ]}


def qualifying_audits():
    return [audit_fixture(i, activity) for i, activity in enumerate(
        ["A", "A", "B", "B", "C"])]


def test_exact_branch_a_thresholds_are_conjunctive():
    result = ge.evaluate_sufficiency(qualifying_audits(), gate_timeline())
    assert result["branch"] == "A"
    assert result["all_thresholds_pass"] is True

    assert ge.evaluate_sufficiency(qualifying_audits()[:4], gate_timeline())[
        "branch"] == "SOURCE_INSUFFICIENT"
    only_two = [audit_fixture(i, activity) for i, activity in enumerate(
        ["A", "A", "B", "B", "A"])]
    assert ge.evaluate_sufficiency(only_two, gate_timeline())[
        "branch"] == "SOURCE_INSUFFICIENT"
    no_non_dominant = [audit_fixture(i, activity) for i, activity in enumerate(
        ["A", "A", "B", "B", "B"])]
    assert ge.evaluate_sufficiency(no_non_dominant, gate_timeline())[
        "branch"] == "SOURCE_INSUFFICIENT"


def test_source_insufficient_writes_only_audit_record_and_result(tmp_path):
    record = {"raw_files_inspected": 116, "inference": ge.ZERO_INFERENCE.copy()}
    decision = {
        "branch": "SOURCE_INSUFFICIENT",
        "metrics": {
            "usable_detail_windows": 0,
            "distinct_activities_with_detail": 0,
            "non_dominant_activities_with_detail": 0,
            "lineage_complete_candidates": 0,
        },
        "all_thresholds_pass": False,
    }
    result = ge.write_source_insufficient_outputs(tmp_path, [], record, decision)
    assert result["status"] == (
        "CLOSED / GROUNDING_DETAIL_SOURCE_INSUFFICIENT"
    )
    assert result["new_visual_inference_required"] == "UNKNOWN"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "execution_record.json", "raw_detail_audit.json", "result.json",
    ]
    assert result["inference"] == {
        "visual": 0, "stt": 0, "beta_v3_regeneration": 0,
        "text_generation": 0, "retry": 0,
    }


def test_source_hash_drift_fails_closed(tmp_path):
    protected = tmp_path / "protected.txt"
    protected.write_text("frozen", encoding="utf-8")
    before = ge.snapshot_sources(tmp_path, ["protected.txt"])
    protected.write_text("changed", encoding="utf-8")
    after = ge.snapshot_sources(tmp_path, ["protected.txt"])
    with pytest.raises(ge.GroundingError, match="source hash drift"):
        ge.assert_unchanged(before, after)


def valid_detail():
    return valid_observation()


def valid_candidate(candidate_id="C001", start=0.0, end=24.0,
                    activities=None, zone="early", fact_text=None,
                    final=False):
    activities = list(activities or ["음식 준비 및 조리"])
    fact_text = fact_text or f"재료를 손으로 다룬다 {candidate_id}"
    return {
        "candidate_id": candidate_id,
        "start_sec": float(start), "end_sec": float(end),
        "duration_sec": float(end - start),
        "activities": activities, "temporal_zone": zone,
        "visual_facts": [{
            "text": fact_text, "source_text": fact_text,
            "confidence": "high", "source_span": [float(start), float(end)],
        }],
        "unique_visual_fact_count": 1,
        "activity_coverage_seconds": {activity: 30.0 for activity in activities},
        "timeline_entry_ids": [1], "grounded_observation_ids": ["GO0001"],
        "sources": [{"chunk": "C01", "window": "S01",
                     "raw_path": "raw.txt", "raw_sha256": "a" * 64}],
        "is_final_phase": final,
    }


def test_detail_without_lineage_is_rejected():
    detail = valid_detail()
    del detail["source"]
    with pytest.raises(ge.GroundingError, match="source lineage"):
        ge.validate_detail(detail)


def test_activity_outside_allowed_or_source_set_is_rejected():
    candidate = valid_candidate(activities=["자동차 운전"])
    with pytest.raises(ge.GroundingError, match="unknown activity"):
        ge.validate_candidate(candidate, ALLOWED)


def test_duplicate_id_and_nonmonotonic_time_are_rejected():
    rows = [
        valid_candidate("H01", 20, 30),
        valid_candidate("H01", 0, 10),
    ]
    with pytest.raises(ge.GroundingError):
        ge.validate_highlights(rows, ALLOWED)


def selection_fixture():
    return [
        valid_candidate("C001", 0, 25, activities=["음식 준비 및 조리"],
                        zone="early", fact_text="재료를 손으로 다룬다 하나"),
        valid_candidate("C002", 30, 55, activities=["음식 준비 및 조리"],
                        zone="early", fact_text="재료를 그릇에 담는다 둘"),
        valid_candidate("C003", 60, 85, activities=["음식 준비 및 조리"],
                        zone="early", fact_text="음식을 용기에 넣는다 셋"),
        valid_candidate("C004", 100, 125, activities=["의류 작업 및 수선"],
                        zone="middle", fact_text="옷을 손으로 수선한다"),
        valid_candidate("C005", 135, 160, activities=["포장 작업"],
                        zone="middle", fact_text="물건을 종이로 포장한다"),
        valid_candidate("C006", 200, 225, activities=["구매 또는 둘러보기"],
                        zone="late", fact_text="사람이 걸으며 이동한다"),
        valid_candidate("C007", 235, 260, activities=["정리 작업"],
                        zone="late", fact_text="물건을 손으로 정리한다"),
        valid_candidate("C008", 270, 300, activities=["식사"],
                        zone="late", fact_text="사람이 음식을 먹는다",
                        final=True),
    ]


def test_selector_caps_identical_signature_and_keeps_zones_and_final():
    got = ge.select_highlights(
        selection_fixture(), [270.0, 300.0],
        dominant={"음식 준비 및 조리", "구매 또는 둘러보기"},
    )
    assert 5 <= len(got) <= 8
    assert max(Counter(tuple(x["activities"]) for x in got).values()) <= 2
    assert {x["temporal_zone"] for x in got} == {"early", "middle", "late"}
    assert [got[-1]["start_sec"], got[-1]["end_sec"]] == [270.0, 300.0]
    assert sum(bool(set(x["activities"]) - {
        "음식 준비 및 조리", "구매 또는 둘러보기"
    }) for x in got) >= 2


def test_same_label_and_nonadjacent_highlights_never_claim_transition():
    same = ge.render_highlight(valid_candidate(
        "H01", 0, 24, activities=["식사"], fact_text="사람이 음식을 먹는다"))
    assert "전환" not in same
    pair = ge.render_pair(
        valid_candidate("H01", 0, 24, activities=["식사"]),
        valid_candidate("H02", 48, 72, activities=["이동"]),
    )
    assert "전환" not in pair


def test_compound_label_uses_separator_not_broken_particle():
    text = ge.render_highlight(valid_candidate(
        "H01", 0, 24,
        activities=["구매 또는 둘러보기", "음식 준비 및 조리"],
    ))
    assert "구매 또는 둘러보기 · 음식 준비 및 조리 활동이 함께 나타난다" in text
    assert "둘러보기와" not in text
    assert "둘러보기과" not in text


def test_adjacent_different_pair_may_claim_transition():
    pair = ge.render_pair(
        valid_candidate("H01", 0, 24, activities=["식사"]),
        valid_candidate("H02", 24, 48, activities=["이동"]),
    )
    assert "전환" in pair


def test_branch_a_writer_emits_only_preregistered_data_artifacts(tmp_path):
    candidates = selection_fixture()
    highlights = ge.select_highlights(
        candidates, [270.0, 300.0],
        dominant={"음식 준비 및 조리", "구매 또는 둘러보기"},
    )
    observation = valid_observation()
    observation["observation_id"] = "GO0001"
    result = ge.write_branch_a_outputs(
        tmp_path, audits=[], execution_record={"raw_files_inspected": 116},
        decision={"branch": "A", "metrics": {}, "all_thresholds_pass": True},
        observations=[observation], detail_store={"details": []},
        candidates=candidates, highlights=highlights,
        comparison={"v3": {}, "grounded_v1": {}},
    )
    assert result["status"] == "EXECUTED / REVIEW_PENDING"
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([
        "raw_detail_audit.json", "execution_record.json", "result.json",
        "grounded_observations.json", "grounded_detail_store.json",
        "grounded_detail_lineage.json", "highlight_candidates.json",
        "highlights.json", "highlight_lineage.json", "comparison_v3.json",
    ])
    assert not any(p.suffix in {".md", ".hwpx"} for p in tmp_path.iterdir())
