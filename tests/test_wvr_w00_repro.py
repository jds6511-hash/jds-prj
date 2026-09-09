"""W00 재현성 계약 (2026-09-09 · WVR-K01~K16).

```
run 3개    R1·R2·R3 · 창은 W00 [0,48) · 24 timestamps 고정
identity   픽셀 해시·프롬프트·revision·runtime config 대조 · 불일치는 실패로 남긴다
계약       raw-before-parse · hidden retry 없음 · run 1회 · 원본 W00 무변경
게이트      재현성 4값 · determinism 축 분리
```
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_contract as contract
import wvr_density_prompt_v2 as diag
import wvr_density_v1b as events
import wvr_shadow_v1 as sh
import wvr_w00_repro as rp

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT / "docs/preregistration/"
          "WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md")
RUNNER = ROOT / "scripts/wvr_w00_repro_run.py"
SUMMARY_TOOL = ROOT / "scripts/wvr_w00_repro_summary.py"
BATCH = ROOT / "scripts/wvr_w00_repro_batch.sh"
RUNS = ROOT / "runs/wvr_light_v1"
SUMMARY = RUNS / "w00_repro_summary.json"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"
SUBMISSION_SHA = ("5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca9"
                  "94e9cd7b")


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(RUNNER, "wvr_w00_repro_run_mod")
summary_tool = _module(SUMMARY_TOOL, "wvr_w00_repro_summary_mod")


def _row(run_id, degeneracy=rp.DEGENERACY, valid=False,
         identity=rp.IDENTITY_OK, status="PARSE_FAILURE", raw=True,
         tokens=4096, raw_hash="h"):
    return {"run_id": run_id, "degeneracy": degeneracy,
            "technical_valid": valid, "identity_status": identity,
            "technical_status": status, "raw_persisted": raw,
            "generated_tokens": tokens, "raw_output_hash": raw_hash,
            "json_complete": not valid, "zero_progress": not valid}


# ── WVR-K01~K06 동결 ────────────────────────────────────────────────
def test_wvr_k01_the_preregistration_is_committed():
    done = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_k02_exactly_three_preregistered_runs():
    assert rp.RUN_IDS == ("R1", "R2", "R3")
    assert rp.EXPECTED_RUN_COUNT == 3
    batch = BATCH.read_text(encoding="utf-8")
    assert "for run in R1 R2 R3" in batch


def test_wvr_k03_the_window_is_w00_zero_to_fortyeight():
    window = rp.target_window()
    assert window["window_id"] == "W00"
    assert (window["start_sec"], window["end_sec"]) == (0.0, 48.0)


def test_wvr_k04_the_same_twentyfour_timestamps_are_used():
    stamps = rp.frame_times()
    assert len(stamps) == 24
    assert stamps == sh.frame_times(sh.window_by_id("W00"))
    assert stamps[0] == 0.0 and stamps[-1] == 46.0


def test_wvr_k05_prompt_and_model_revision_are_frozen():
    assert rp.expected_prompt() == diag.SAMPLING_DIAG_PROMPT_V2 % {
        "window_start": 0.0, "window_end": 48.0}
    assert diag.prompt_hash() == (
        "37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273")
    assert contract.MODEL_REVISION == (
        "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b")
    assert "support_frame_times" not in RUNNER.read_text(encoding="utf-8")


def test_wvr_k06_generation_settings_are_unchanged():
    config = runner.generation_config()
    assert config == {"do_sample": False, "num_beams": 1,
                      "max_new_tokens": 4096, "repetition_penalty": 1.0}
    assert events.tokens_for(events.EVENT_V2) == 4096
    assert rp.SUBDIVISION_INFERENCE_ALLOWED is False
    assert rp.RECOVERY_EXPERIMENT_ALLOWED is False


# ── WVR-K07~K09 identity ───────────────────────────────────────────
def test_wvr_k07_identity_compares_every_frozen_field():
    assert set(rp.IDENTITY_FIELDS) == {
        "video_sha256", "window", "frame_times", "frame_hashes",
        "prompt_text", "prompt_hash", "model_revision",
        "runtime_config_hash", "generation_config"}
    original = {field: field for field in rp.IDENTITY_FIELDS}
    assert rp.identity_report(original, dict(original))["status"] == \
        rp.IDENTITY_OK


def test_wvr_k08_a_single_pixel_hash_difference_fails_identity():
    original = {field: field for field in rp.IDENTITY_FIELDS}
    original["frame_hashes"] = ["h%d" % index for index in range(24)]
    observed = dict(original)
    observed["frame_hashes"] = ["h%d" % index for index in range(24)]
    observed["frame_hashes"][7] = "TAMPERED"
    report = rp.identity_report(original, observed)
    assert report["status"] == rp.IDENTITY_FAILURE
    assert report["mismatched"] == ["frame_hashes"]


def test_wvr_k09_identity_failure_blocks_the_measurement():
    rows = [_row("R1"), _row("R2", identity=rp.IDENTITY_FAILURE),
            _row("R3")]
    verdict = rp.repro_verdict(rows)
    assert verdict["verdict"] == rp.INCONCLUSIVE
    assert verdict["reason"] == "MEASUREMENT_BLOCKED"
    assert verdict["blocked_runs"] == ["R2"]


# ── WVR-K10~K12 실행 계약 ──────────────────────────────────────────
def test_wvr_k10_raw_is_persisted_before_parse():
    source = RUNNER.read_text(encoding="utf-8")
    raw_write = source.index("raw_path.write_text(raw_output")
    parse_call = source.index("v2.parse_events(raw_output, window)")
    assert raw_write < parse_call
    assert 'record["raw_persisted"] = True' in source


def test_wvr_k11_no_hidden_retry_exists():
    assert rp.RETRY_ALLOWED is False
    assert rp.PRODUCTION_SELECTION_ALLOWED is False
    for path in (RUNNER, BATCH, SUMMARY_TOOL):
        source = path.read_text(encoding="utf-8")
        for banned in ("while True", "for attempt", "--retry", "retry(" ):
            assert banned not in source, "%s 에 retry 흔적이 있다" % path.name
    assert "재시도하지 않는다" in BATCH.read_text(encoding="utf-8")


def test_wvr_k12_each_run_is_written_once(tmp_path):
    for name in (rp.ORIGINAL_RECORD, rp.ORIGINAL_RAW):
        (tmp_path / name).write_bytes((RUNS / name).read_bytes())
    plan = runner.preflight("R1", tmp_path, ROOT / "data/videos/full_xekZO4n4QuE.mp4")
    assert plan["runtime_config_hash"] == rp.ORIGINAL_RUNTIME_CONFIG_SHA256
    plan["out_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError, match="이미 있다"):
        runner.preflight("R1", tmp_path,
                         ROOT / "data/videos/full_xekZO4n4QuE.mp4")


def test_wvr_k12b_a_runtime_config_hash_mismatch_blocks_the_run(tmp_path,
                                                                monkeypatch):
    for name in (rp.ORIGINAL_RECORD, rp.ORIGINAL_RAW):
        (tmp_path / name).write_bytes((RUNS / name).read_bytes())
    monkeypatch.setattr(rp, "ORIGINAL_RUNTIME_CONFIG_SHA256", "0" * 64)
    with pytest.raises(runner.RunError, match="runtime config"):
        runner.preflight("R2", tmp_path,
                         ROOT / "data/videos/full_xekZO4n4QuE.mp4")


# ── WVR-K13~K14 게이트 ─────────────────────────────────────────────
def test_wvr_k13_the_reproducibility_truth_table_is_frozen():
    assert rp.REPRO_VERDICTS == ("REPRODUCIBLE", "NOT_REPRODUCED",
                                 "INTERMITTENT", "INCONCLUSIVE")
    three = [_row("R1"), _row("R2"), _row("R3")]
    assert rp.repro_verdict(three)["verdict"] == rp.REPRODUCIBLE

    valid = [_row(run, degeneracy=rp.NO_DEGENERACY, valid=True, status="OK")
             for run in rp.RUN_IDS]
    assert rp.repro_verdict(valid)["verdict"] == rp.NOT_REPRODUCED

    mixed = [_row("R1"),
             _row("R2", degeneracy=rp.NO_DEGENERACY, valid=True, status="OK"),
             _row("R3", degeneracy=rp.NO_DEGENERACY, valid=True, status="OK")]
    assert rp.repro_verdict(mixed)["verdict"] == rp.INTERMITTENT

    two_of_three = [_row("R1"), _row("R2"),
                    _row("R3", degeneracy=rp.NO_DEGENERACY, valid=True,
                         status="OK")]
    assert rp.repro_verdict(two_of_three)["verdict"] == rp.INTERMITTENT

    other = [_row(run, degeneracy=rp.NO_DEGENERACY, valid=False,
                  status="PARSE_FAILURE") for run in rp.RUN_IDS]
    assert rp.repro_verdict(other)["verdict"] == rp.INCONCLUSIVE

    with pytest.raises(rp.ReproError):
        rp.repro_verdict([_row("R1"), _row("R2")])


def test_wvr_k14_the_determinism_axis_is_separate():
    assert rp.DETERMINISM_AXES == ("EXACT_RAW_REPRODUCTION",
                                   "STRUCTURAL_DEGENERACY_REPRODUCTION",
                                   "OUTPUT_VARIATION")
    same = [_row(run, raw_hash="same") for run in rp.RUN_IDS]
    assert rp.determinism_axis(["same"] * 3, same)["axis"] == rp.EXACT_RAW
    differing = [_row("R1", raw_hash="a"), _row("R2", raw_hash="b"),
                 _row("R3", raw_hash="c")]
    assert rp.determinism_axis(["a", "b", "c"], differing)["axis"] == \
        rp.STRUCTURAL
    mixed = [_row("R1", raw_hash="a"),
             _row("R2", degeneracy=rp.NO_DEGENERACY, valid=True, status="OK",
                  raw_hash="b"),
             _row("R3", raw_hash="c")]
    assert rp.determinism_axis(["a", "b", "c"], mixed)["axis"] == \
        rp.OUTPUT_VARIATION


# ── WVR-K15~K16 경계 ──────────────────────────────────────────────
def test_wvr_k15_the_original_w00_and_blind_artifacts_stay_untouched():
    assert rp.ORIGINAL_W00_MAY_BE_REVALIDATED is False
    record_sha = hashlib.sha256(
        (RUNS / rp.ORIGINAL_RECORD).read_bytes()).hexdigest()
    raw_sha = hashlib.sha256(
        (RUNS / rp.ORIGINAL_RAW).read_bytes()).hexdigest()
    report = rp.original_unchanged(record_sha, raw_sha)
    assert report["unchanged"] is True
    assert report["original_status_retained"] == "WINDOW_INVALID"
    tampered = rp.original_unchanged("0" * 64, raw_sha)
    assert tampered["unchanged"] is False
    assert tampered["checks"]["record"] is False
    for path in (RUNNER, SUMMARY_TOOL):
        source = path.read_text(encoding="utf-8")
        for banned in ("blind_map", "overlap_packet", "shadow_v1_W01"):
            assert banned not in source
    assert rp.MAPPING_REVEAL_ALLOWED is False


def test_wvr_k16_submission_and_test_split_stay_untouched():
    assert hashlib.sha256(SUBMISSION.read_bytes()).hexdigest() == \
        SUBMISSION_SHA
    for path in (RUNNER, SUMMARY_TOOL, ROOT / "src/wvr_w00_repro.py"):
        source = path.read_text(encoding="utf-8")
        for banned in ('split == "test"', "eval_test", "m9_report_eval",
                       "queries.jsonl", "report.hwpx"):
            assert banned not in source


# ── 실행 후 ────────────────────────────────────────────────────────
requires_summary = pytest.mark.skipif(not SUMMARY.is_file(),
                                      reason="재현성 미실행")


@requires_summary
def test_wvr_k17_the_summary_declares_its_limits():
    record = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert record["event"] == rp.EVENT
    assert record["run_count"] == 3
    assert record["retry_allowed"] is False
    assert record["production_selection_allowed"] is False
    assert record["subdivision_inference_allowed"] is False
    assert record["mapping_reveal_allowed"] is False
    assert record["original_w00"]["unchanged"] is True
    assert record["reproducibility"]["verdict"] in rp.REPRO_VERDICTS
    assert record["determinism_axis"]["axis"] in rp.DETERMINISM_AXES


@requires_summary
def test_wvr_k18_every_run_used_identical_input():
    record = json.loads(SUMMARY.read_text(encoding="utf-8"))
    for run_id, identity in record["identity"].items():
        assert identity.get("status") == rp.IDENTITY_OK, run_id
    for row in record["runs"]:
        assert row["raw_persisted"] is True
