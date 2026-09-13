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
