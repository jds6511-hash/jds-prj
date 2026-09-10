"""visual content isolation 계약 (2026-09-10 · WVR-P01~P33).

```
설계   arm E = W05 [120,168) 픽셀 + Trigger A 시간 인코딩(T0) · 새 inference 1회
불변   prompt 문구·zero-duration 예시·schema·token cap·penalty·표집·metadata 6필드
확인   기존 세 칸(Trigger A INVALID · Trigger D VALID · SHADOW W05 VALID) 해시 무변경
게이트  INCONCLUSIVE → E INVALID면 시간 configuration · E VALID면 content×time interaction
```
"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_density_prompt_v2 as diag
import wvr_density_v1b as tokens
import wvr_shadow_v1 as sh
import wvr_subdivision_v1 as sd
import wvr_trigger_v1 as tg
import wvr_visual_v1 as vc

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md")
PREREG = ROOT / PREREG_REL
RUNNER = ROOT / "scripts/wvr_visual_run.py"
SUMMARY_TOOL = ROOT / "scripts/wvr_visual_summary.py"
SELFCHECK_TOOL = ROOT / "scripts/wvr_visual_selfcheck.py"
VALIDATOR = ROOT / "scripts/wvr_visual_validate.py"
BATCH = ROOT / "scripts/wvr_visual_batch.sh"
RUNS = ROOT / "runs/wvr_light_v1"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"
SUBMISSION_SHA = ("5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca9"
                  "94e9cd7b")
RATE = 30.0


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(RUNNER, "wvr_visual_run_mod")
summary_tool = _module(SUMMARY_TOOL, "wvr_visual_summary_mod")

PIXEL_HASHES = ["w05px%.0f" % time for time in vc.pixel_times()]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _time_reference(indices=None, prompt_hash=None, window=None):
    plan = vc.arm_plan(RATE)
    metadata = {"total_num_frames": 72724, "fps": RATE, "width": 1920,
                "height": 1080, "duration": 2424.186485,
                "video_backend": "pyav",
                "frames_indices": list(indices if indices is not None
                                       else plan["frames_indices"])}
    return {"rendered_prompt_hash": (prompt_hash if prompt_hash is not None
                                     else plan["rendered_prompt_hash"]),
            "prompt_window": (window if window is not None
                              else plan["prompt_window"]),
            "prompt_template_hash": tg.prompt_template_hash(),
            "metadata": metadata}


def _record(cap=False, degenerate=False, raw=True, video="v", frames=None,
            status="OK", pixel_hashes=None, indices=None,
            metadata_overrides=None, time_reference=None, unique=2):
    plan = vc.arm_plan(RATE)
    rows = [
        {"index": 0, "start_sec": 0.0, "end_sec": 4.0, "actor": "person",
         "action": "holding", "object_or_state": "a bag of rice",
         "signature": ("person", "holding", "a bag of rice"),
         "source_indices": [0], "collapsed_count": 1},
        {"index": 1, "start_sec": 4.0, "end_sec": 8.0, "actor": "person",
         "action": "pouring", "object_or_state": "powder into a pan",
         "signature": ("person", "pouring", "powder into a pan"),
         "source_indices": [1], "collapsed_count": 1},
    ][:max(unique, 1)]
    metadata = dict(_time_reference()["metadata"])
    metadata["frames_indices"] = list(indices if indices is not None
                                      else plan["frames_indices"])
    metadata.update(metadata_overrides or {})
    hashes = list(pixel_hashes if pixel_hashes is not None else PIXEL_HASHES)
    record = {
        "event": vc.EVENT,
        "arm": {"arm_id": vc.ARM_ID, "cell": vc.CELL_X1T0["cell"],
                "pixel_source": vc.PIXEL_SOURCE_WINDOW_ID,
                "time_encoding": vc.TIME_ENCODING,
                "prompt_mode": vc.PROMPT_MODE,
                "metadata_mode": vc.METADATA_MODE},
        "pixel_times": list(vc.pixel_times()),
        "frame_hashes": hashes,
        "pixel_identity": vc.pixel_identity(hashes, PIXEL_HASHES),
        "raw_persisted": raw, "video_sha256": video, "arm_status": status,
        "prompt_template_hash": tg.prompt_template_hash(),
        "rendered_prompt_hash": plan["rendered_prompt_hash"],
        "prompt_window": plan["prompt_window"],
        "metadata": metadata,
        "runtime_config_hash": "rt",
        "inference_config_change": {"inference_config_change": "NONE"},
        "frozen_cells_unchanged": {"unchanged": True},
        "requested": {"max_new_tokens": 4096},
        "metrics": {"delivered_frame_count":
                    vc.PIXEL_FRAME_COUNT if frames is None else frames,
                    "generated_token_count": 4096 if cap else 400,
                    "generation_cap_hit": cap},
        "parsed": {"status": "OK", "events": rows, "collapsed": rows,
                   "language": {"satisfied": True, "violations": []}},
        "representation": {
            "collapsed_event_count": len(rows),
            "unique_signature_count": len({tuple(row["signature"])
                                           for row in rows}),
            "degenerate": degenerate},
        "structure": {"raw_length": 600, "complete_object_count": len(rows),
                      "unique_signature_count": len(rows),
                      "zero_length_interval_count": 0,
                      "max_signature_repeat": 1, "json_parse_ok": True},
        "raw_path": "%s_%s_raw.txt" % (vc.ARTIFACT_TAG, vc.ARM_ID),
        "raw_output_hash": "raw_E",
    }
    record["time_encoding_identity"] = vc.time_encoding_identity(
        record, time_reference if time_reference is not None
        else _time_reference())
    return record


def _row(valid=True, blockers=(), failures=()):
    return {"arm_id": vc.ARM_ID, "valid": valid,
            "status": sh.WINDOW_VALID if valid else sh.WINDOW_INVALID,
            "blockers": list(blockers), "output_failures": list(failures),
            "reasons": list(blockers) + list(failures)}


# ── WVR-P01~P09 설계 동결 ──────────────────────────────────────────
def test_wvr_p01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_p02_exactly_one_new_inference():
    assert vc.ARM_ID == "E"
    assert vc.EXPECTED_ARM_COUNT == 1
    assert vc.RERUN_OF_FROZEN_CELLS_ALLOWED is False


def test_wvr_p03_pixels_come_from_the_w05_window():
    assert vc.PIXEL_SOURCE_WINDOW_ID == "W05"
    window = vc.pixel_source_window()
    assert (window["start_sec"], window["end_sec"]) == (120.0, 168.0)
    stamps = vc.pixel_times()
    assert stamps == sh.frame_times(sh.window_by_id("W05"))
    assert stamps[0] == 120.0 and stamps[-1] == 166.0
    assert len(stamps) == vc.PIXEL_FRAME_COUNT == 24


def test_wvr_p04_time_encoding_is_trigger_arm_a():
    encoding = vc.time_encoding()
    assert encoding["time_encoding"] == "T0"
    assert encoding["prompt_mode"] == "P0"
    assert encoding["metadata_mode"] == "M0"
    assert encoding["prompt_window"] == [0.0, 48.0]
    assert encoding["rendered_prompt_hash"] == tg.rendered_prompt_hash("P0")
    assert encoding["prompt_template_hash"] == diag.prompt_hash()
    assert vc.frame_indices(RATE) == tg.frame_indices("M0", RATE)
    assert vc.frame_indices(RATE)[:3] == (0, 60, 120)


def test_wvr_p05_the_arm_pairs_w05_pixels_with_t0_time():
    plan = vc.arm_plan(RATE)
    assert plan["pixel_times"][0] == 120.0 and plan["pixel_times"][-1] == 166.0
    assert plan["prompt_window"] == [0.0, 48.0]
    assert plan["frames_indices"][0] == 0 and plan["frames_indices"][-1] == 1380
    assert plan["cell"] == "X1T0"
    assert "start_sec=0.0 end_sec=48.0" in plan["rendered_prompt"]
    assert plan["rendered_prompt"] == tg.rendered_prompt("P0")


def test_wvr_p06_the_three_frozen_cells_are_recorded_with_their_status():
    assert vc.CELL_X0T0["status"] == sh.WINDOW_INVALID
    assert vc.CELL_X0T1["status"] == sh.WINDOW_VALID
    assert vc.CELL_X1T1["status"] == sh.WINDOW_VALID
    assert vc.CELL_X0T0["source"] == "trigger_v1_A"
    assert vc.CELL_X0T1["source"] == "trigger_v1_D"
    assert vc.CELL_X1T1["source"] == "shadow_v1_W05"
    assert len(vc.FROZEN_CELLS) == 3


def test_wvr_p07_the_prompt_and_schema_stay_frozen():
    assert vc.PROMPT_TEXT_MUTATION_ALLOWED is False
    assert vc.ZERO_DURATION_EXAMPLE_MUTATION_ALLOWED is False
    assert vc.SCHEMA_MUTATION_ALLOWED is False
    assert '{"start_sec": 0.0, "end_sec": 0.0' in \
        diag.SAMPLING_DIAG_PROMPT_V2, "zero-duration 예시가 바뀌었다"
    assert tg.prompt_template_hash() == diag.prompt_hash()
    assert tokens.tokens_for(tokens.EVENT_V2) == 4096


def test_wvr_p08_the_verdict_vocabulary_is_frozen():
    assert vc.VERDICTS == ("ABSOLUTE_TIME_CONFIGURATION_EFFECT_SUPPORTED",
                           "VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED",
                           "INCONCLUSIVE")
    for phrase in ("0초 버그의 내부 원인을 증명했다", "Qwen 내부 메커니즘을 규명했다",
                   "두 채널을 +120초로 옮기면 무조건 해결된다",
                   "recovery 방법을 찾았다",
                   "다른 창·다른 영상·다른 shift에서도 같다"):
        assert phrase in vc.FORBIDDEN_CONCLUSIONS
    assert vc.MEASUREMENT_SCOPE == "pixel set 2개 · time encoding 2개 · shift 1개(+120초)"


def test_wvr_p09_pixel_source_assertions_fire_when_the_design_moves(
        monkeypatch):
    monkeypatch.setattr(vc, "PIXEL_SOURCE_WINDOW_ID", "W00")
    with pytest.raises(vc.VisualError):
        vc.pixel_source_window()
    monkeypatch.setattr(vc, "PIXEL_SOURCE_WINDOW_ID", "W05")
    monkeypatch.setattr(vc, "PIXEL_FRAME_COUNT", 23)
    with pytest.raises(vc.VisualError):
        vc.pixel_times()


# ── WVR-P10~P16 기술 검증 ──────────────────────────────────────────
def test_wvr_p10_a_clean_arm_is_valid():
    row = vc.arm_validity(_record(), "v")
    assert row["valid"] is True and row["status"] == "WINDOW_VALID"
    assert row["reasons"] == []


def test_wvr_p11_cap_hit_and_degeneracy_are_output_failures():
    cap = vc.arm_validity(_record(cap=True), "v")
    assert "TRUNCATED_AT_CAP" in cap["output_failures"]
    assert cap["blockers"] == []
    degen = vc.arm_validity(_record(degenerate=True), "v")
    assert sd.REPRESENTATION_DEGENERACY in degen["output_failures"]


def test_wvr_p12_pixel_identity_failure_is_a_blocker():
    tampered = list(PIXEL_HASHES)
    tampered[9] = "other"
    row = vc.arm_validity(_record(pixel_hashes=tampered), "v")
    assert vc.PIXEL_IDENTITY_FAILURE in row["blockers"]
    assert row["valid"] is False


def test_wvr_p13_time_encoding_mismatch_is_a_blocker():
    row = vc.arm_validity(
        _record(indices=list(tg.frame_indices("M1", RATE))), "v")
    assert vc.TIME_ENCODING_MISMATCH in row["blockers"]
    shifted = vc.arm_validity(
        _record(time_reference=_time_reference(prompt_hash="other")), "v")
    assert vc.TIME_ENCODING_MISMATCH in shifted["blockers"]


def test_wvr_p14_fixed_metadata_drift_is_a_blocker():
    row = vc.arm_validity(
        _record(metadata_overrides={"duration": 1880.0}), "v")
    assert vc.TIME_ENCODING_MISMATCH in row["blockers"]
    assert row["valid"] is False
    detail = _record(metadata_overrides={"total_num_frames": 5})
    assert "metadata_total_num_frames" in \
        detail["time_encoding_identity"]["mismatched"]


def test_wvr_p15_structural_blockers_are_kept():
    assert sh.FRAME_COUNT_MISMATCH in vc.arm_validity(
        _record(frames=23), "v")["blockers"]
    record = _record()
    record["pixel_times"] = [1.0] + record["pixel_times"][1:]
    assert sh.GRID_MISMATCH in vc.arm_validity(record, "v")["blockers"]
    assert sh.RAW_NOT_PERSISTED in vc.arm_validity(
        _record(raw=False), "v")["blockers"]
    assert sh.PROVENANCE_MISMATCH in vc.arm_validity(
        _record(video="other"), "v")["blockers"]


def test_wvr_p16_runtime_failure_is_a_blocker():
    record = _record(status=sd.RUNTIME_FAILURE, raw=False)
    record.pop("parsed")
    record.pop("representation")
    row = vc.arm_validity(record, "v")
    assert sd.RUNTIME_FAILURE in row["blockers"] and row["valid"] is False


# ── WVR-P17~P21 verdict ────────────────────────────────────────────
def test_wvr_p17_an_invalid_e_supports_the_time_configuration_effect():
    row = vc.verdict(_row(valid=False, failures=("TRUNCATED_AT_CAP",)))
    assert row["verdict"] == vc.TIME_CONFIG_EFFECT
    assert row["reason"] == "E_INVALID"
    assert row["allowed_claim"].startswith("이번 두 pixel set 범위에서")
    assert row["table"]["X1T0"]["status"] == sh.WINDOW_INVALID
    assert row["table"]["X0T0"]["status"] == sh.WINDOW_INVALID
    assert row["table"]["X0T1"]["status"] == sh.WINDOW_VALID
    assert row["table"]["X1T1"]["status"] == sh.WINDOW_VALID


def test_wvr_p18_a_valid_e_supports_the_content_time_interaction():
    row = vc.verdict(_row(valid=True))
    assert row["verdict"] == vc.CONTENT_TIME_INTERACTION
    assert row["reason"] == "E_VALID"
    assert "결합될 때만" in row["allowed_claim"]
    assert row["table"]["X1T0"]["status"] == sh.WINDOW_VALID


def test_wvr_p19_blockers_outrank_both_readings():
    row = vc.verdict(_row(valid=False), blockers=[vc.PIXEL_IDENTITY_FAILURE])
    assert row["verdict"] == vc.INCONCLUSIVE
    assert row["reason"] == "MEASUREMENT_BLOCKED"
    assert row["allowed_claim"] is None
    arm_blocked = vc.verdict(_row(valid=False,
                                  blockers=(vc.TIME_ENCODING_MISMATCH,)))
    assert arm_blocked["verdict"] == vc.INCONCLUSIVE
    valid_blocked = vc.verdict(_row(valid=True),
                               blockers=[vc.FROZEN_CELL_CHANGED])
    assert valid_blocked["verdict"] == vc.INCONCLUSIVE


def test_wvr_p20_the_verdict_never_claims_a_mechanism():
    for row in (vc.verdict(_row(valid=True)), vc.verdict(_row(valid=False))):
        assert row["mechanism_claimed"] is False
        assert row["new_inference_count"] == 1
        assert row["measurement_scope"] == vc.MEASUREMENT_SCOPE
        assert row["table"]["rerun_of_frozen_cells"] is False


def test_wvr_p21_frozen_cells_detect_change_and_absence():
    assert vc.frozen_cells_unchanged(dict(vc.FROZEN_ARTIFACTS))["unchanged"] \
        is True
    changed = dict(vc.FROZEN_ARTIFACTS)
    changed["trigger_v1_D_raw.txt"] = "0" * 64
    row = vc.frozen_cells_unchanged(changed)
    assert row["unchanged"] is False
    assert row["changed"] == ["trigger_v1_D_raw.txt"]
    partial = {key: value for key, value in vc.FROZEN_ARTIFACTS.items()
               if key != "shadow_v1_W05.json"}
    assert vc.frozen_cells_unchanged(partial)["missing"] == \
        ["shadow_v1_W05.json"]
    assert vc.frozen_cells_unchanged(partial)["rerun_allowed"] is False


# ── WVR-P22~P25 실행기 계약 ────────────────────────────────────────
def test_wvr_p22_the_runner_persists_raw_before_parsing():
    source = RUNNER.read_text(encoding="utf-8")
    assert source.index('raw_path.write_text(raw_output') < source.index(
        'v2.parse_events(raw_output')
    assert "for attempt" not in source and "while True" not in source
    assert 'max_new_tokens=plan["max_new_tokens"]' in source
    assert 'if not record["pixel_identity"]["identical"]:' in source
    assert 'if not record["time_encoding_identity"]["identical"]:' in source
    assert "trigger_runner.requested_config()" in source, \
        "설정 표를 trigger와 다른 경로에서 만들고 있다"


def _seed_runs(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    runs.mkdir()
    for name in vc.FROZEN_ARTIFACTS:
        source = RUNS / name
        if not source.is_file():
            pytest.skip("선행 산출물이 없다: %s" % name)
        shutil.copy2(source, runs / name)
    return runs


def test_wvr_p23_preflight_accepts_the_design_and_refuses_a_second_run(
        tmp_path):
    runs = _seed_runs(tmp_path)
    plan = runner.preflight(runs, rate=RATE)
    assert plan["change"]["inference_config_change"] == "NONE"
    assert len(plan["pixel_reference"]) == vc.PIXEL_FRAME_COUNT
    assert plan["time_reference"]["rendered_prompt_hash"] == \
        tg.rendered_prompt_hash("P0")
    assert plan["plan"]["pixel_times"][0] == 120.0
    assert plan["plan"]["frames_indices"][0] == 0
    plan["out_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight(runs)


def test_wvr_p24_preflight_refuses_changed_frozen_cells(tmp_path):
    runs = _seed_runs(tmp_path)
    (runs / "shadow_v1_W05_raw.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight(runs)


def test_wvr_p25_preflight_refuses_open_flags(tmp_path, monkeypatch):
    runs = _seed_runs(tmp_path)
    for name in ("RETRY_ALLOWED", "RAW_SALVAGE_ALLOWED",
                 "TOKEN_CAP_INCREASE_APPROVED",
                 "PROMPT_TEXT_MUTATION_ALLOWED",
                 "ZERO_DURATION_EXAMPLE_MUTATION_ALLOWED",
                 "SCHEMA_MUTATION_ALLOWED", "SUBDIVISION_RESTART_ALLOWED",
                 "ADDITIONAL_SHIFT_ALLOWED",
                 "PROCESSOR_MONKEY_PATCH_ALLOWED",
                 "RERUN_OF_FROZEN_CELLS_ALLOWED"):
        monkeypatch.setattr(vc, name, True)
        with pytest.raises(runner.RunError):
            runner.preflight(runs)
        monkeypatch.setattr(vc, name, False)

    def _refuse(value):
        raise AssertionError("허용되지 않은 token cap: %r" % value)

    monkeypatch.setattr(runner.events, "assert_allowed", _refuse)
    with pytest.raises(AssertionError):
        runner.preflight(runs)


# ── WVR-P26~P28 요약 게이트 ────────────────────────────────────────
def _write_arm(runs: Path, selfcheck=True, **kwargs) -> None:
    record = _record(**kwargs)
    record["validity"] = vc.arm_validity(record, "v")
    (runs / ("%s_%s.json" % (vc.ARTIFACT_TAG, vc.ARM_ID))).write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8")
    if selfcheck is not None:
        (runs / summary_tool.SELFCHECK_NAME).write_text(json.dumps(
            {"ok": bool(selfcheck), "checks": {},
             "status": "OK" if selfcheck else "IMPLEMENTATION_BLOCKED"}),
            encoding="utf-8")


def _seed_reference_records(runs: Path) -> None:
    for name in vc.FROZEN_ARTIFACTS:
        source = RUNS / name
        if not source.is_file():
            pytest.skip("선행 산출물이 없다: %s" % name)
        shutil.copy2(source, runs / name)


def test_wvr_p26_summary_reads_the_three_frozen_cells(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _seed_reference_records(runs)
    _write_arm(runs, cap=True)
    summary = summary_tool.build(runs)
    assert summary["verdict"]["verdict"] == vc.TIME_CONFIG_EFFECT
    cells = summary["reference_cells"]
    assert cells["X0T0"]["status"] == sh.WINDOW_INVALID
    assert cells["X0T1"]["status"] == sh.WINDOW_VALID
    assert cells["X1T1"]["status"] == sh.WINDOW_VALID
    assert cells["X0T0"]["generated_tokens"] == 4096
    assert summary["new_inference_count"] == 1
    assert summary["cross_comparison"]["role"] == "AUDIT_DIAGNOSTIC_ONLY"


def test_wvr_p27_summary_blocks_without_a_passing_selfcheck(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _seed_reference_records(runs)
    _write_arm(runs, selfcheck=False)
    assert summary_tool.build(runs)["verdict"]["verdict"] == vc.INCONCLUSIVE
    runs2 = tmp_path / "runs2"
    runs2.mkdir()
    _seed_reference_records(runs2)
    _write_arm(runs2, selfcheck=None)
    assert summary_tool.build(runs2)["verdict"]["verdict"] == vc.INCONCLUSIVE


def test_wvr_p28_summary_blocks_when_a_frozen_cell_moved(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _seed_reference_records(runs)
    _write_arm(runs)
    (runs / "trigger_v1_A.json").write_text("{}", encoding="utf-8")
    summary = summary_tool.build(runs)
    assert summary["verdict"]["verdict"] == vc.INCONCLUSIVE
    assert vc.FROZEN_CELL_CHANGED in summary["verdict"]["blockers"]


# ── WVR-P29~P30 경계 ──────────────────────────────────────────────
def test_wvr_p29_prior_artifacts_and_boundaries_are_untouched():
    for name, expected in vc.FROZEN_ARTIFACTS.items():
        path = RUNS / name
        if not path.is_file():
            pytest.skip("선행 산출물이 없다: %s" % name)
        assert _sha256_file(path) == expected, "선행 산출물이 바뀌었다: %s" % name
    if SUBMISSION.is_file():
        assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert vc.PRIOR_STATE["WVR_W00_TRIGGER_ISOLATION_V1"] == \
        "CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED"
    assert vc.PRIOR_STATE["recursive_subdivision_hypothesis"] == \
        "STOPPED / NOT SUFFICIENT"
    for name in ("RETRY_ALLOWED", "RAW_SALVAGE_ALLOWED",
                 "TOKEN_CAP_INCREASE_APPROVED",
                 "PROMPT_TEXT_MUTATION_ALLOWED",
                 "ZERO_DURATION_EXAMPLE_MUTATION_ALLOWED",
                 "SCHEMA_MUTATION_ALLOWED", "SUBDIVISION_RESTART_ALLOWED",
                 "ADDITIONAL_SHIFT_ALLOWED",
                 "PROCESSOR_MONKEY_PATCH_ALLOWED", "MAPPING_REVEAL_ALLOWED",
                 "SEMANTIC_VERDICT_BY_EXECUTOR",
                 "PRODUCTION_PROMOTION_ALLOWED", "MECHANISM_CLAIM_ALLOWED",
                 "RERUN_OF_FROZEN_CELLS_ALLOWED"):
        assert getattr(vc, name) is False, "%s가 열려 있다" % name


def test_wvr_p30_the_batch_gates_on_the_selfcheck_and_runs_one_arm():
    batch = BATCH.read_text(encoding="utf-8")
    assert batch.index("wvr_visual_validate.py") < batch.index(
        "wvr_visual_selfcheck.py") < batch.index("wvr_visual_run.py")
    assert "SELFCHECK 실패 — 추론하지 않는다" in batch
    assert "재시도하지 않는다" in batch
    assert "for " not in batch, "arm 루프가 들어왔다 — E는 1회다"
    selfcheck = SELFCHECK_TOOL.read_text(encoding="utf-8")
    assert "Qwen3VLForConditionalGeneration" not in selfcheck, \
        "self-check는 모델을 올리지 않는다"
    assert '"pixels_match_w05": identity["identical"],' in selfcheck
    assert '"pixel_values_differ_from_trigger_A": bool(trigger_pixels)\n        and pixel_values != trigger_pixels,' in selfcheck, \
        "self-check가 픽셀 차이를 실제로 재지 않는다"
    assert '"markers_are_T0": bool(markers) and markers[0] == "1.0"\n        and markers[-1] == "45.0",' in selfcheck, \
        "self-check가 마커를 실제로 재지 않는다"
    validator = VALIDATOR.read_text(encoding="utf-8")
    for name in ("pixels_are_w05_grid", "prompt_window_is_T0",
                 "rendered_prompt_matches_trigger_A",
                 "indices_match_trigger_A", "frozen_cells_unchanged",
                 "rerun_of_frozen_cells_blocked",
                 "zero_duration_example_frozen"):
        assert '"%s":' % name in validator, "validator가 %s를 빠뜨렸다" % name


# ── WVR-P31~P33 구조 단정 · 요약 blocker 격리 ──────────────────────
def test_wvr_p31_pixel_time_assertion_fires_when_the_grid_moves(monkeypatch):
    monkeypatch.setattr(vc.sh, "frame_times",
                        lambda window: tuple(float(index * 2)
                                             for index in range(24)))
    with pytest.raises(vc.VisualError):
        vc.pixel_times()


def test_wvr_p32_summary_blocks_when_a_frozen_cell_status_moved(tmp_path,
                                                                monkeypatch):
    """파일 해시는 맞지만 기록된 판정이 다르면 막아야 한다."""
    runs = tmp_path / "runs"
    runs.mkdir()
    _seed_reference_records(runs)
    _write_arm(runs, cap=True)
    path = runs / "trigger_v1_A.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["validity"]["status"] = sh.WINDOW_VALID
    record["validity"]["valid"] = True
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(vc, "FROZEN_ARTIFACTS",
                        {**vc.FROZEN_ARTIFACTS,
                         "trigger_v1_A.json": _sha256_file(path)})
    summary = summary_tool.build(runs)
    assert summary["frozen_cells"]["unchanged"] is True, "해시는 맞춰 둔 상태다"
    assert summary["verdict"]["verdict"] == vc.INCONCLUSIVE
    assert vc.FROZEN_CELL_CHANGED in summary["verdict"]["blockers"]


def test_wvr_p33_summary_blocks_on_pixel_drift_the_arm_reports_as_clean(
        tmp_path):
    """arm record가 스스로 깨끗하다고 적어도 요약이 픽셀·시간 identity를 다시 본다."""
    runs = tmp_path / "runs"
    runs.mkdir()
    _seed_reference_records(runs)
    record = _record()
    record["pixel_identity"] = {"identical": False, "forged_for_test": True}
    record["validity"] = {"valid": True, "status": sh.WINDOW_VALID,
                          "reasons": [], "blockers": [],
                          "output_failures": [],
                          "language": {"satisfied": True}}
    (runs / ("%s_%s.json" % (vc.ARTIFACT_TAG, vc.ARM_ID))).write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8")
    (runs / summary_tool.SELFCHECK_NAME).write_text(
        json.dumps({"ok": True, "checks": {}}), encoding="utf-8")
    summary = summary_tool.build(runs)
    assert summary["verdict"]["verdict"] == vc.INCONCLUSIVE
    assert vc.PIXEL_IDENTITY_FAILURE in summary["verdict"]["blockers"]

    record["pixel_identity"] = {"identical": True}
    record["time_encoding_identity"] = {"identical": False}
    (runs / ("%s_%s.json" % (vc.ARTIFACT_TAG, vc.ARM_ID))).write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8")
    summary = summary_tool.build(runs)
    assert vc.TIME_ENCODING_MISMATCH in summary["verdict"]["blockers"]
