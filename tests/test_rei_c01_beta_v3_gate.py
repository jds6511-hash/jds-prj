"""WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1 gate 테스트.

사전등록 §2 동결 해시 · §3 invocation · §5 static gate를 코드가 실제로 강제하는지
확인한다. 모델을 올리지 않는다.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PREREG = (ROOT / "docs" / "preregistration" /
          "WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md")
RUN_SCRIPT = ROOT / "scripts" / "rei_c01_beta_v3_run.sh"


def _load_gate():
    spec = importlib.util.spec_from_file_location(
        "rei_c01_beta_v3_gate", ROOT / "scripts" / "rei_c01_beta_v3_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load_gate()


# ── §2 동결 해시가 문서와 코드에서 같다 ────────────────────────────
def test_rei_v3_01_frozen_hashes_match_the_preregistration():
    text = PREREG.read_text(encoding="utf-8")
    for value in gate.FROZEN_SHA256.values():
        assert value in text, value


def test_rei_v3_02_frozen_input_is_the_nonoverlap_cell_of_the_prior_event():
    assert gate.SRC_SEGMENTS == ROOT / "runs" / "rei_c01" / "b_beta" / "segments.json"


@pytest.mark.skipif(not (ROOT / "runs" / "rei_c01" / "b_beta" /
                         "segments.json").exists(), reason="선행 산출물 미존재")
def test_rei_v3_03_the_frozen_input_still_hashes_to_the_recorded_value():
    assert gate.sha(gate.SRC_SEGMENTS) == gate.FROZEN_SHA256["segments.json"]


# ── §5 T4 커버리지 계산 ────────────────────────────────────────────
def test_rei_v3_04_coverage_is_zero_duplicate_for_the_nonoverlap_grid():
    rows = [{"start": i * 24.0,
             "end": (600.0 if i == 23 else i * 24.0 + 24.0)} for i in range(24)]
    assert gate.coverage(rows) == (600.0, 0.0)


def test_rei_v3_05_coverage_reports_duplication_when_windows_overlap():
    rows = [{"start": i * 24.0, "end": min(i * 24.0 + 48.0, 600.0)}
            for i in range(24)]
    cov, dup = gate.coverage(rows)
    assert cov == 600.0 and dup > 0


# ── §5 T7 engine source가 prompt·grounding까지 덮는다 ──────────────
def test_rei_v3_06_engine_source_watchlist_covers_prompt_and_grounding():
    assert "src/v2_1_prompt.py" in gate.ENGINE_SOURCES
    assert "src/v2_1_grounding.py" in gate.ENGINE_SOURCES


# ── §5 T8 contract 해석 ────────────────────────────────────────────
def test_rei_v3_07_v3_contract_is_summary_only():
    import v2_1_prompt as vp
    contract = vp.resolve_contract("v3")
    assert contract["version"] == vp.PROMPT_VERSION_V3
    assert list(contract["output"]["required"]) == ["summary"]
    assert list(contract["output"]["optional"]) == []


def test_rei_v3_08_unknown_contract_name_does_not_fall_back_to_v2():
    import v2_1_prompt as vp
    with pytest.raises(vp.PromptError):
        vp.resolve_contract("v2.5")


# ── §3 invocation이 실행 스크립트에 그대로 박혀 있다 ───────────────
def _run_script_code() -> str:
    """주석을 뺀 실행 코드만 본다 — 주석에서 인자를 '쓰지 않는다'고 설명한다."""
    return "\n".join(line for line in RUN_SCRIPT.read_text(encoding="utf-8")
                     .splitlines() if not line.lstrip().startswith("#"))


@pytest.mark.skipif(not RUN_SCRIPT.exists(), reason="실행 스크립트 미작성")
def test_rei_v3_09_run_script_freezes_contract_v3_and_no_retry():
    code = _run_script_code()
    assert "--contract v3" in code
    # 동결되지 않은 인자를 넣지 않는다
    assert "--max-new-tokens" not in code
    assert "--window-sec" not in code
    assert "--shadow-vad0" not in code


@pytest.mark.skipif(not RUN_SCRIPT.exists(), reason="실행 스크립트 미작성")
def test_rei_v3_10_run_script_runs_only_the_nonoverlap_cell():
    code = _run_script_code()
    assert "rei_c01_overlap" not in code, "OVERLAP_VIEW는 이번 사건에 없다"
    assert "rei_c01_nonoverlap" in code


# ── 산출물 경로가 선행 사건과 섞이지 않는다 ────────────────────────
def test_rei_v3_11_outputs_are_isolated_from_the_prior_event():
    assert gate.RUN_ROOT.name == "rei_c01_beta_v3"
    assert "rei_c01_beta_v3" in str(gate.CELL_DIR)
    assert gate.RUN_ROOT != ROOT / "runs" / "rei_c01"


# ── gate 산출물이 있으면 형식을 확인한다 ───────────────────────────
@pytest.mark.skipif(not (ROOT / "runs" / "rei_c01_beta_v3" /
                         "static_gate.json").exists(), reason="gate 미실행")
def test_rei_v3_12_static_gate_record_declares_zero_new_inference():
    rec = json.loads((ROOT / "runs" / "rei_c01_beta_v3" / "static_gate.json")
                     .read_text(encoding="utf-8"))
    assert rec["new_inference_count"] == 0
    assert rec["event"] == gate.EVENT
    assert re.fullmatch(r"[0-9a-f]{40}", rec["code_git_head"])
