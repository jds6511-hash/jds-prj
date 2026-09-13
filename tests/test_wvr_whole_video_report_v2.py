"""사용자-facing 보고서 V2: 동결 개요와 보조 구간 제외 계약."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_whole_video_report_v2 as report  # noqa: E402


def _flow():
    return {
        "phases": [
            {"phase_index": 0, "activities": ["음식 준비 및 조리"],
             "entry_count": 2},
            {"phase_index": 1, "activities": ["식사"], "entry_count": 1},
        ],
        "repeated_activities": ["음식 준비 및 조리"],
        "final_phase_activities": ["식사"],
        "phase_count": 2,
        "transition_count": 1,
    }


def _timeline():
    return {
        "entries": [
            {"broad_activity": ["음식 준비 및 조리"], "start_sec": 0.0,
             "end_sec": 24.0, "source_chunk": "C01"},
            {"broad_activity": ["식사"], "start_sec": 24.0,
             "end_sec": 48.0, "source_chunk": "C01"},
        ],
        "video_duration_sec": 48.2,
        "temporal_coverage_sec": 48.0,
        "terminal_remainder_sec": 0.2,
        "entry_count": 2,
    }


def _overview():
    return {
        "short_overview": "음식 준비 및 조리가 이어진다.  \n영상은 식사로 끝난다.",
        "detailed_overview": "음식 준비 및 조리가 이어진 뒤 식사가 나타난다. 영상은 식사로 끝난다.",
    }


def test_analysis_prompt_receives_only_frozen_structural_sources():
    prompt = report.analysis_prompt(_flow(), _overview(), _timeline())
    assert "음식 준비 및 조리" in prompt
    assert _overview()["detailed_overview"] in prompt
    assert "식사" in prompt
    assert "구조적 패턴" in prompt
    assert "0.0" not in prompt and "48.2" not in prompt
    assert "C01" not in prompt
    assert "H01" not in prompt


def test_conclusion_prompt_receives_overview_and_revised_analysis_only():
    analysis = "음식 준비 및 조리가 반복되고 마지막은 식사다."
    prompt = report.conclusion_prompt(_overview(), analysis)
    assert _overview()["short_overview"] in prompt
    assert _overview()["detailed_overview"] in prompt
    assert analysis in prompt
    assert "CANONICAL_FLOW" not in prompt
    assert "새 evidence" in prompt


def test_user_report_keeps_overview_and_excludes_beta_narratives():
    beta = {
        "episodes": 41, "eligible": 36, "excluded": 5,
        "quality_exclusions": {
            "EP10": "OUTPUT_LANGUAGE_DRIFT",
            "EP21": "OUTPUT_LANGUAGE_DRIFT",
            "EP23": "OUTPUT_LANGUAGE_CONTRACT_FAILURE + OUTPUT_LANGUAGE_DRIFT",
            "EP28": "PARSE_CONTRACT_FAILURE",
            "EP30": "PARSE_CONTRACT_FAILURE",
        },
    }
    text = report.final_report_markdown(
        _overview(), "구조적 분석. 영상은 식사로 끝난다.",
        "짧은 종합. 영상은 식사로 끝난다.", _timeline(), beta)
    assert "## 개요\n\n" + _overview()["short_overview"] in text
    assert "## 상세 개요\n\n" + _overview()["detailed_overview"] in text
    assert "## 분석\n\n구조적 분석." in text
    assert "## 결론\n\n짧은 종합." in text
    assert "eligible 36/41" in text
    assert "EP23 OUTPUT_LANGUAGE_CONTRACT_FAILURE + OUTPUT_LANGUAGE_DRIFT" in text
    assert "## β/v3 보조 구간 요약" not in text
    assert "H01" not in text and "H09" not in text
    assert "seg#" not in text
    assert text.count("\n## ") == 5


def test_user_report_rejects_identifier_in_new_prose():
    beta = {"episodes": 2, "eligible": 2, "excluded": 0,
            "quality_exclusions": {}}
    with pytest.raises(report.ReportV2Error, match="identifier"):
        report.final_report_markdown(
            _overview(), "seg#82가 보인다. 영상은 식사로 끝난다.",
            "영상은 식사로 끝난다.", _timeline(), beta)


def test_machine_checks_reject_context_and_wrong_final_phase():
    analysis = "직장 일정 때문에 음식 준비 및 조리가 반복된다. 영상은 이동으로 끝난다."
    conclusion = "음식 준비 및 조리가 나타난다. 영상은 이동으로 끝난다."
    checks = report.machine_checks(_flow(), _overview(), analysis, conclusion)
    assert not checks["analysis_context"]
    assert not checks["analysis_final"]
    assert not checks["conclusion_final"]
    assert not checks["all_pass"]
