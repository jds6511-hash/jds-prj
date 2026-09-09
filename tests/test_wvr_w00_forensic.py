"""W00 forensic 계약 (2026-09-09 · WVR-J01~J14).

```
추론 없음   torch·transformers를 import조차 하지 않는다
분류        4값 · 진리표 동결 (A=입력 이상 · B=출력 축퇴)
raw         salvage 금지 — 구조 관찰만
C4 지표      임계 동결(16.0 · 2.0) · 분류에 들어가지 않는다
경계        기존 artifact·mapping·제출본 미접촉
```
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_density_prompt_v2 as diag
import wvr_shadow_v1 as sh
import wvr_w00_forensic as fx

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT / "docs/preregistration/"
          "WVR_W00_DEGENERACY_FORENSIC_V1_2026-09-09.md")
RUNNER = ROOT / "scripts/wvr_w00_forensic_run.py"
RUNS = ROOT / "runs/wvr_light_v1"
RESULT = RUNS / "w00_forensic_v1.json"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"
SUBMISSION_SHA = ("5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca9"
                  "94e9cd7b")


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(RUNNER, "wvr_w00_forensic_runner")


def _obj(action="pouring", thing="liquid into a bowl", start=0.0, end=0.0):
    return ('{"start_sec": %.1f, "end_sec": %.1f, "actor": "a person", '
            '"action": "%s", "object_or_state": "%s"}' % (start, end, action,
                                                          thing))


# ── WVR-J01~J05 동결 ────────────────────────────────────────────────
def test_wvr_j01_the_preregistration_is_committed():
    done = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_W00_DEGENERACY_FORENSIC_V1_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_j02_no_inference_stack_is_used():
    for path in (RUNNER, ROOT / "src/wvr_w00_forensic.py"):
        source = path.read_text(encoding="utf-8")
        for banned in ("import torch", "import transformers",
                       "from transformers"):
            assert banned not in source
    assert fx.NEW_INFERENCE_ALLOWED is False
    assert fx.RERUN_ALLOWED is False
    assert fx.TOKEN_CAP_INCREASE_APPROVED is False
    assert fx.MAPPING_REVEAL_ALLOWED is False
    assert fx.SEMANTIC_VERDICT_BY_EXECUTOR is False


def test_wvr_j03_the_classification_vocabulary_is_exactly_four():
    assert fx.CLASSIFICATIONS == ("INPUT_PIPELINE_DEFECT",
                                  "MODEL_OUTPUT_DEGENERACY", "MIXED",
                                  "UNRESOLVED")


def test_wvr_j04_the_truth_table_is_frozen():
    assert fx.classify(True, False) == fx.INPUT_PIPELINE_DEFECT
    assert fx.classify(False, True) == fx.MODEL_OUTPUT_DEGENERACY
    assert fx.classify(True, True) == fx.MIXED
    assert fx.classify(False, False) == fx.UNRESOLVED


def test_wvr_j05_the_visual_thresholds_are_frozen():
    assert fx.BLACK_LUMA_THRESHOLD == 16.0
    assert fx.NEAR_STATIC_DIFF_THRESHOLD == 2.0
    assert fx.VISUAL_METRICS_IN_CLASSIFICATION is False
    text = PREREG.read_text(encoding="utf-8")
    assert "16.0" in text and "2.0" in text


# ── WVR-J06~J08 입력 ───────────────────────────────────────────────
def test_wvr_j06_existing_artifacts_are_only_read():
    source = RUNNER.read_text(encoding="utf-8") + \
        (ROOT / "src/wvr_w00_forensic.py").read_text(encoding="utf-8")
    for banned in ("unlink", "rmtree", "os.remove", "shutil"):
        assert banned not in source, "기존 산출물을 지우는 호출이 있다"
    assert "shadow_v1" in source
    # 쓰기는 결과 파일 하나뿐이어야 한다
    assert source.count("write_text") == 1
    assert "RESULT_NAME" in source


def test_wvr_j07_raw_salvage_is_forbidden(monkeypatch):
    assert fx.RAW_SALVAGE_ALLOWED is False
    monkeypatch.setattr(fx, "RAW_SALVAGE_ALLOWED", True)
    with pytest.raises(fx.ForensicError):
        fx.raw_structure("{}")


def test_wvr_j08_prompts_are_reconstructed_from_the_template():
    window = sh.window_by_id("W00")
    assert fx.expected_prompt(window) == diag.SAMPLING_DIAG_PROMPT_V2 % {
        "window_start": 0.0, "window_end": 48.0}
    diff = fx.prompt_diff(fx.expected_prompt(window),
                          fx.expected_prompt(sh.window_by_id("W01")))
    assert diff["differing_line_count"] == 1
    assert "start_sec=" in diff["lines"][0]["target"]


# ── WVR-J09~J11 구조 분석 ──────────────────────────────────────────
def test_wvr_j09_repetition_metrics_are_computed_correctly():
    raw = '{"events": [%s, %s, %s]}' % (_obj(), _obj(), _obj("holding",
                                                             "a bottle"))
    structure = fx.raw_structure(raw)
    assert structure["complete_object_count"] == 3
    assert structure["unique_signature_count"] == 2
    assert structure["max_signature_repeat"] == 2
    assert structure["first_repeat"]["object_index"] == 1
    assert structure["first_repeat"]["first_seen_index"] == 0
    assert structure["json_parse_ok"] is True


def test_wvr_j10_zero_length_intervals_are_counted():
    raw = '{"events": [%s, %s, %s]}' % (
        _obj(start=0.0, end=0.0), _obj("holding", "a bottle", 4.0, 4.0),
        _obj("mixing", "a bowl", 2.0, 6.0))
    structure = fx.raw_structure(raw)
    assert structure["complete_object_count"] == 3
    assert structure["zero_length_interval_count"] == 2


def test_wvr_j11_unterminated_json_is_detected():
    raw = '{"events": [%s, {"start_sec": ' % _obj()
    structure = fx.raw_structure(raw)
    assert structure["json_parse_ok"] is False
    assert structure["ends_mid_object"] is True
    assert fx.parser_responsibility(structure)["attributed_to"] == \
        "MODEL_OUTPUT"
    complete = fx.raw_structure('{"events": [%s]}' % _obj())
    assert fx.parser_responsibility(complete)["attributed_to"] == \
        "PARSER_CANDIDATE"


# ── WVR-J12~J14 지표·경계 ─────────────────────────────────────────
def test_wvr_j12_grid_linearity_flags_a_broken_grid():
    window = sh.window_by_id("W00")
    stamps = list(sh.frame_times(window))
    good = {"window": window, "frame_times": stamps, "decoded_fps": 30.0,
            "frame_indices": [int(round(time * 30.0)) for time in stamps]}
    assert fx.grid_linearity(good)["linear"] is True
    bad_time = {**good, "frame_times": [7.0] + stamps[1:]}
    assert fx.grid_linearity(bad_time)["times_match_schedule"] is False
    bad_index = {**good, "frame_indices": [9999] + good["frame_indices"][1:]}
    assert fx.grid_linearity(bad_index)["index_linear"] is False


def test_wvr_j13_visual_metrics_never_enter_the_classification():
    source = (ROOT / "src/wvr_w00_forensic.py").read_text(encoding="utf-8")
    body = source[source.index("def input_anomaly"):source.index("def classify")]
    for banned in ("mean_luma", "black_frame_ratio", "near_static",
                   "mean_adjacent_diff"):
        assert banned not in body, "시각 지표가 분류 축에 들어갔다"
    classify_body = source[source.index("def classify"):
                           source.index("def parser_responsibility")]
    assert "luma" not in classify_body


def test_wvr_j14_mapping_and_submission_stay_untouched():
    source = RUNNER.read_text(encoding="utf-8")
    for banned in ("blind_map", "overlap_packet", "report.hwpx",
                   "quality_candidate"):
        assert banned not in source, "봉인 대상 파일을 건드린다: %s" % banned
    assert fx.MAPPING_REVEAL_ALLOWED is False
    assert SUBMISSION.is_file()
    assert hashlib.sha256(SUBMISSION.read_bytes()).hexdigest() == \
        SUBMISSION_SHA


# ── 실행 후 (산출물 있을 때만) ─────────────────────────────────────
requires_result = pytest.mark.skipif(not RESULT.is_file(),
                                     reason="forensic 미실행")


@requires_result
def test_wvr_j15_the_result_declares_its_limits():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    assert record["event"] == fx.EVENT
    assert record["new_inference_allowed"] is False
    assert record["rerun_allowed"] is False
    assert record["mapping_reveal_allowed"] is False
    assert record["classification"] in fx.CLASSIFICATIONS
    assert record["c4_visual"]["used_in_classification"] is False
    assert record["c5_determinism"]["determinism_measured"] is False


@requires_result
def test_wvr_j16_the_classification_follows_the_frozen_table():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    assert record["classification"] == fx.classify(
        record["axis_input_anomaly"]["found"],
        record["axis_output_degeneracy"]["confirmed"])
