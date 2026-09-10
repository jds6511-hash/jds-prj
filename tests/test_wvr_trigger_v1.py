"""W00 trigger isolation 계약 (2026-09-10 · WVR-N01~N43).

```
설계   2×2 · A(P0M0) B(P0M1) C(P1M0) D(P1M1) · SHIFT_SEC +120.0
불변   24 픽셀 시각·해시 · prompt template · schema · token cap · 표집 ·
      duration·total_num_frames·fps·width/height·backend
조작   rendered prompt window 값 · VideoMetadata.frames_indices 둘뿐
게이트  INCONCLUSIVE → CONTROL_NOT_REPRODUCED → 2×2 패턴 (순서 고정)
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

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md")
PREREG = ROOT / PREREG_REL
RUNNER = ROOT / "scripts/wvr_trigger_run.py"
SUMMARY_TOOL = ROOT / "scripts/wvr_trigger_summary.py"
SELFCHECK_TOOL = ROOT / "scripts/wvr_trigger_selfcheck.py"
VALIDATOR = ROOT / "scripts/wvr_trigger_validate.py"
BATCH = ROOT / "scripts/wvr_trigger_batch.sh"
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


runner = _module(RUNNER, "wvr_trigger_run_mod")
summary_tool = _module(SUMMARY_TOOL, "wvr_trigger_summary_mod")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


PIXEL_HASHES = ["px%.0f" % time for time in tg.pixel_times()]


def _record(arm_id="A", cap=False, degenerate=False, raw=True, video="v",
            frames=None, status="OK", pixel_hashes=None, indices=None,
            metadata_overrides=None, rendered_hash=None,
            template_hash=None, unique=2):
    arm = tg.arm_by_id(arm_id)
    plan = tg.arm_plan(arm_id, RATE)
    rows = [
        {"index": 0, "start_sec": plan["prompt_window"][0],
         "end_sec": plan["prompt_window"][0] + 4.0, "actor": "person",
         "action": "holding", "object_or_state": "a bottle",
         "signature": ("person", "holding", "a bottle"),
         "source_indices": [0], "collapsed_count": 1},
        {"index": 1, "start_sec": plan["prompt_window"][0] + 4.0,
         "end_sec": plan["prompt_window"][0] + 8.0, "actor": "person",
         "action": "pouring", "object_or_state": "liquid into a bowl",
         "signature": ("person", "pouring", "liquid into a bowl"),
         "source_indices": [1], "collapsed_count": 1},
    ][:max(unique, 1)]
    metadata = {"total_num_frames": 60000, "fps": RATE, "width": 1920,
                "height": 1080, "duration": 2000.0, "video_backend": "pyav",
                "frames_indices": list(indices if indices is not None
                                       else plan["frames_indices"])}
    metadata.update(metadata_overrides or {})
    hashes = list(pixel_hashes if pixel_hashes is not None else PIXEL_HASHES)
    return {
        "event": tg.EVENT, "arm": arm,
        "pixel_times": list(tg.pixel_times()),
        "frame_hashes": hashes,
        "pixel_identity": tg.pixel_identity(hashes, PIXEL_HASHES),
        "raw_persisted": raw, "video_sha256": video, "arm_status": status,
        "prompt_template_hash": (template_hash if template_hash is not None
                                 else tg.prompt_template_hash()),
        "rendered_prompt_hash": (rendered_hash if rendered_hash is not None
                                 else plan["rendered_prompt_hash"]),
        "prompt_window": plan["prompt_window"],
        "metadata": metadata,
        "runtime_config_hash": "rt",
        "inference_config_change": {"inference_config_change": "NONE"},
        "frozen_artifacts_unchanged": {"unchanged": True},
        "requested": {"max_new_tokens": 4096},
        "metrics": {"delivered_frame_count":
                    tg.PIXEL_FRAME_COUNT if frames is None else frames,
                    "generated_token_count": 4096 if cap else 400,
                    "generation_cap_hit": cap},
        "parsed": {"status": "OK", "events": rows, "collapsed": rows,
                   "language": {"satisfied": True, "violations": []}},
        "representation": {
            "collapsed_event_count": len(rows),
            "unique_signature_count": len({tuple(row["signature"])
                                           for row in rows}),
            "degenerate": degenerate},
        "structure": {"raw_length": 500, "complete_object_count": len(rows),
                      "unique_signature_count": len(rows),
                      "zero_length_interval_count": 0,
                      "max_signature_repeat": 1, "json_parse_ok": True},
        "raw_path": "%s_%s_raw.txt" % (tg.ARTIFACT_TAG, arm_id),
        "raw_output_hash": "raw_%s" % arm_id,
    }


def _row(arm_id, valid=True, blockers=(), failures=()):
    return {"arm_id": arm_id, "valid": valid, "blockers": list(blockers),
            "output_failures": list(failures),
            "reasons": list(blockers) + list(failures)}


def _pattern(a, b, c, d):
    return [_row("A", a), _row("B", b), _row("C", c), _row("D", d)]


# ── WVR-N01~N10 설계 동결 ──────────────────────────────────────────
def test_wvr_n01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_n02_exactly_four_arms_in_a_two_by_two():
    assert tg.ARMS == (("A", "P0", "M0"), ("B", "P0", "M1"),
                       ("C", "P1", "M0"), ("D", "P1", "M1"))
    assert tg.ARM_IDS == ("A", "B", "C", "D")
    assert len(tg.arms()) == tg.EXPECTED_ARM_COUNT == 4


def test_wvr_n03_shift_is_exactly_one_hundred_twenty_seconds():
    assert tg.SHIFT_SEC == 120.0
    assert tg.prompt_window("P0") == (0.0, 48.0)
    assert tg.prompt_window("P1") == (120.0, 168.0)
    assert tg.metadata_times("M1")[0] == 120.0
    assert tg.metadata_times("M1")[-1] == 166.0


def test_wvr_n04_pixel_times_are_the_frozen_w00_grid():
    stamps = tg.pixel_times()
    assert stamps == sh.frame_times(sh.window_by_id("W00"))
    assert len(stamps) == tg.PIXEL_FRAME_COUNT == 24
    assert stamps[0] == 0.0 and stamps[-1] == 46.0
    assert tg.metadata_times("M0") == stamps


def test_wvr_n05_frames_indices_follow_the_frozen_rule():
    assert tg.frame_indices("M0", RATE)[:3] == (0, 60, 120)
    assert tg.frame_indices("M1", RATE)[:3] == (3600, 3660, 3720)
    shifted = tg.frame_indices("M1", RATE)
    original = tg.frame_indices("M0", RATE)
    assert [later - earlier for earlier, later in zip(original, shifted)] == \
        [int(round(tg.SHIFT_SEC * RATE))] * tg.PIXEL_FRAME_COUNT
    with pytest.raises(tg.TriggerError):
        tg.frame_indices("M0", 0)


def test_wvr_n06_prompt_template_is_untouched_and_only_numbers_change():
    assert tg.prompt_template_hash() == diag.prompt_hash()
    p0, p1 = tg.rendered_prompt("P0"), tg.rendered_prompt("P1")
    assert p0 != p1
    assert p0.replace("start_sec=0.0 end_sec=48.0",
                      "start_sec=120.0 end_sec=168.0") == p1, \
        "창 숫자값 외의 문구가 달라졌다"
    assert "%(window_start)" in diag.SAMPLING_DIAG_PROMPT_V2
    assert tg.PROMPT_TEXT_MUTATION_ALLOWED is False
    assert tg.SCHEMA_MUTATION_ALLOWED is False


def test_wvr_n07_arm_plans_pair_the_two_channels_correctly():
    plans = {arm_id: tg.arm_plan(arm_id, RATE) for arm_id in tg.ARM_IDS}
    assert plans["A"]["rendered_prompt_hash"] == \
        plans["B"]["rendered_prompt_hash"]
    assert plans["C"]["rendered_prompt_hash"] == \
        plans["D"]["rendered_prompt_hash"]
    assert plans["A"]["rendered_prompt_hash"] != \
        plans["C"]["rendered_prompt_hash"]
    assert plans["A"]["frames_indices"] == plans["C"]["frames_indices"]
    assert plans["B"]["frames_indices"] == plans["D"]["frames_indices"]
    assert plans["A"]["frames_indices"] != plans["B"]["frames_indices"]
    for plan in plans.values():
        assert plan["pixel_times"] == list(tg.pixel_times())
        assert plan["prompt_template_hash"] == diag.prompt_hash()


def test_wvr_n08_only_frames_indices_is_manipulated_in_metadata():
    assert tg.METADATA_MANIPULATED_FIELD == "frames_indices"
    assert set(tg.METADATA_FIXED_FIELDS) == {
        "total_num_frames", "fps", "width", "height", "duration",
        "video_backend"}
    assert "frames_indices" not in tg.METADATA_FIXED_FIELDS


def test_wvr_n09_inference_configuration_is_frozen():
    requested = runner.requested_config()
    assert requested["max_new_tokens"] == tokens.tokens_for(
        tokens.EVENT_V2) == 4096
    assert requested["repetition_penalty"] == 1.0
    assert requested["do_sample"] is False
    assert requested["sampling_fps"] == 0.5
    assert requested["frames"] == 24
    assert requested["prompt_hash"] == diag.prompt_hash()
    assert sh.inference_config_change(requested)[
        "inference_config_change"] == "NONE"


def test_wvr_n10_unknown_modes_are_rejected():
    for bad in ("P2", "p0", ""):
        with pytest.raises(tg.TriggerError):
            tg.prompt_window(bad)
    for bad in ("M2", "m0", ""):
        with pytest.raises(tg.TriggerError):
            tg.metadata_times(bad)
    with pytest.raises(tg.TriggerError):
        tg.arm_by_id("E")


# ── WVR-N11~N16 arm 기술 검증 ──────────────────────────────────────
def test_wvr_n11_a_clean_arm_is_valid():
    row = tg.arm_validity(_record(), "v")
    assert row["valid"] is True and row["status"] == "WINDOW_VALID"
    assert row["reasons"] == []


def test_wvr_n12_cap_hit_and_degeneracy_are_output_failures():
    cap = tg.arm_validity(_record(cap=True), "v")
    assert "TRUNCATED_AT_CAP" in cap["output_failures"]
    assert cap["blockers"] == []
    degen = tg.arm_validity(_record(degenerate=True), "v")
    assert sd.REPRESENTATION_DEGENERACY in degen["output_failures"]
    assert degen["blockers"] == []


def test_wvr_n13_pixel_identity_failure_is_a_blocker():
    tampered = list(PIXEL_HASHES)
    tampered[7] = "other"
    row = tg.arm_validity(_record(pixel_hashes=tampered), "v")
    assert tg.PIXEL_IDENTITY_FAILURE in row["blockers"]
    assert row["valid"] is False


def test_wvr_n14_frame_count_and_grid_and_raw_and_provenance_are_blockers():
    assert sh.FRAME_COUNT_MISMATCH in tg.arm_validity(
        _record(frames=23), "v")["blockers"]
    record = _record()
    record["pixel_times"] = [1.0] + record["pixel_times"][1:]
    assert sh.GRID_MISMATCH in tg.arm_validity(record, "v")["blockers"]
    assert sh.RAW_NOT_PERSISTED in tg.arm_validity(
        _record(raw=False), "v")["blockers"]
    assert sh.PROVENANCE_MISMATCH in tg.arm_validity(
        _record(video="other"), "v")["blockers"]


def test_wvr_n15_runtime_failure_is_a_blocker():
    record = _record(status=sd.RUNTIME_FAILURE, raw=False)
    record.pop("parsed")
    record.pop("representation")
    row = tg.arm_validity(record, "v")
    assert sd.RUNTIME_FAILURE in row["blockers"] and row["valid"] is False


def test_wvr_n16_pixel_identity_checks_order_and_length():
    assert tg.pixel_identity(PIXEL_HASHES, PIXEL_HASHES)["identical"] is True
    reordered = list(PIXEL_HASHES)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    row = tg.pixel_identity(reordered, PIXEL_HASHES)
    assert row["identical"] is False and row["mismatched_positions"] == [0, 1]
    short = tg.pixel_identity(PIXEL_HASHES[:-1], PIXEL_HASHES)
    assert short["identical"] is False and short["observed_count"] == 23
    assert tg.pixel_identity(PIXEL_HASHES, [])["identical"] is False


# ── WVR-N17~N24 verdict 어휘·우선순위 ──────────────────────────────
def test_wvr_n17_prompt_time_effect_pattern():
    row = tg.causal_pattern(_pattern(False, False, True, True))
    assert row["verdict"] == tg.PROMPT_TIME_EFFECT
    assert row["reason"] == "P0_INVALID_P1_VALID"
    assert row["allowed_claim"].startswith("이번 W00 pixel set에서 prompt")
    assert row["mechanism_claimed"] is False


def test_wvr_n18_metadata_time_effect_pattern():
    row = tg.causal_pattern(_pattern(False, True, False, True))
    assert row["verdict"] == tg.METADATA_TIME_EFFECT
    assert row["reason"] == "M0_INVALID_M1_VALID"
    assert "metadata" in row["allowed_claim"]


def test_wvr_n19_all_invalid_is_not_supported():
    row = tg.causal_pattern(_pattern(False, False, False, False))
    assert row["verdict"] == tg.NOT_SUPPORTED
    assert row["reason"] == "ALL_ARMS_INVALID"
    assert row["valid_arms"] == []
    assert row["allowed_claim"] is None


def test_wvr_n20_mixed_patterns_are_joint_or_interaction():
    for pattern in ((False, True, True, True), (False, True, True, False),
                    (False, False, False, True), (False, True, False, False)):
        row = tg.causal_pattern(_pattern(*pattern))
        assert row["verdict"] == tg.JOINT_EFFECT, pattern
        assert row["reason"] == "MIXED_PATTERN"
        assert row["allowed_claim"] is None


def test_wvr_n21_a_valid_control_ends_as_control_not_reproduced():
    for pattern in ((True, True, True, True), (True, False, False, False),
                    (True, False, True, False)):
        row = tg.causal_pattern(_pattern(*pattern))
        assert row["verdict"] == tg.CONTROL_NOT_REPRODUCED, pattern
        assert row["reason"] == "CONTROL_ARM_VALID"


def test_wvr_n22_blockers_outrank_every_pattern():
    row = tg.causal_pattern(_pattern(False, False, True, True),
                            blockers=[tg.PIXEL_IDENTITY_FAILURE])
    assert row["verdict"] == tg.INCONCLUSIVE
    assert row["reason"] == "MEASUREMENT_BLOCKED"
    assert tg.PIXEL_IDENTITY_FAILURE in row["blockers"]

    arm_blocked = tg.causal_pattern(
        [_row("A", False), _row("B", False, blockers=(sh.GRID_MISMATCH,)),
         _row("C", True), _row("D", True)])
    assert arm_blocked["verdict"] == tg.INCONCLUSIVE

    control_blocked = tg.causal_pattern(_pattern(True, True, True, True),
                                        blockers=[tg.IMPLEMENTATION_BLOCKED])
    assert control_blocked["verdict"] == tg.INCONCLUSIVE, \
        "INCONCLUSIVE가 CONTROL_NOT_REPRODUCED보다 우선한다"


def test_wvr_n23_a_missing_arm_blocks_the_measurement():
    row = tg.causal_pattern([_row("A", False), _row("B", False),
                             _row("C", True)])
    assert row["verdict"] == tg.INCONCLUSIVE
    assert tg.ARM_COUNT_MISMATCH in row["blockers"]


def test_wvr_n24_the_verdict_vocabulary_is_frozen():
    assert tg.VERDICTS == (
        "PROMPT_TIME_EFFECT_SUPPORTED", "METADATA_TIME_EFFECT_SUPPORTED",
        "JOINT_OR_INTERACTION_EFFECT_SUPPORTED",
        "ABSOLUTE_TIME_EFFECT_NOT_SUPPORTED", "CONTROL_NOT_REPRODUCED",
        "INCONCLUSIVE")
    for phrase in ("근본 원인을 규명했다", "Qwen 내부 메커니즘을 규명했다",
                   "start_sec=0 bug를 증명했다", "metadata가 모델을 망가뜨린다",
                   "prompt가 잘못됐다"):
        assert phrase in tg.FORBIDDEN_CONCLUSIONS
    assert "causal mechanism proof" in tg.EVENT_KIND


# ── WVR-N25~N29 조작 감사 ──────────────────────────────────────────
def _records(**overrides):
    return {arm_id: _record(arm_id, **overrides.get(arm_id, {}))
            for arm_id in tg.ARM_IDS}


def test_wvr_n25_manipulation_audit_passes_on_the_designed_arms():
    row = tg.manipulation_audit(_records())
    assert row["ok"] is True and row["reasons"] == []
    assert row["checks"]["A_indices_equal_C"] is True
    assert row["checks"]["A_indices_differ_B"] is True
    assert row["checks"]["prompt_A_differs_C"] is True
    assert all(row["checks"]["metadata_%s_identical" % name]
               for name in tg.METADATA_FIXED_FIELDS)


def test_wvr_n26_audit_catches_a_metadata_shift_that_did_not_apply():
    plans = tg.arm_plan("A", RATE)["frames_indices"]
    row = tg.manipulation_audit(_records(B={"indices": plans}))
    assert row["ok"] is False
    assert tg.METADATA_MANIPULATION_FAILURE in row["reasons"]
    assert row["checks"]["A_indices_differ_B"] is False
    swapped = tg.manipulation_audit(
        _records(C={"indices": list(tg.arm_plan("B", RATE)["frames_indices"])}))
    assert swapped["ok"] is False
    assert tg.METADATA_MANIPULATION_FAILURE in swapped["reasons"]
    assert swapped["checks"]["A_indices_equal_C"] is False


def test_wvr_n27_audit_catches_a_moved_fixed_metadata_field():
    row = tg.manipulation_audit(
        _records(D={"metadata_overrides": {"duration": 1880.0}}))
    assert row["ok"] is False
    assert tg.METADATA_MANIPULATION_FAILURE in row["reasons"]
    assert row["checks"]["metadata_duration_identical"] is False
    shifted = tg.manipulation_audit(
        _records(B={"metadata_overrides": {"total_num_frames": 1}}))
    assert shifted["checks"]["metadata_total_num_frames_identical"] is False


def test_wvr_n28_audit_catches_rendered_prompt_and_template_drift():
    row = tg.manipulation_audit(_records(B={"rendered_hash": "different"}))
    assert tg.RENDERED_PROMPT_MISMATCH in row["reasons"]
    template = tg.manipulation_audit(_records(C={"template_hash": "0" * 64}))
    assert tg.CONFIG_MISMATCH in template["reasons"]
    assert template["checks"]["prompt_template_frozen"] is False


def test_wvr_n29_pixel_agreement_requires_all_four_arms_identical():
    assert tg.pixel_agreement(_records())["identical"] is True
    tampered = list(PIXEL_HASHES)
    tampered[3] = "other"
    row = tg.pixel_agreement(_records(C={"pixel_hashes": tampered}))
    assert row["identical"] is False and row["differing_arms"] == ["C"]
    assert row["reason"] == tg.PIXEL_IDENTITY_FAILURE


# ── WVR-N30~N33 실행기 계약 ────────────────────────────────────────
def test_wvr_n30_the_runner_persists_raw_before_parsing():
    source = RUNNER.read_text(encoding="utf-8")
    assert source.index('raw_path.write_text(raw_output') < source.index(
        'v2.parse_events(raw_output')
    assert "for attempt" not in source and "while True" not in source
    assert 'max_new_tokens=plan["max_new_tokens"]' in source
    assert "do_sample_frames=contract.DO_SAMPLE_FRAMES" in source
    for patch_form in ("setattr(processor", "setattr(model",
                       "unittest.mock", "mock.patch", "types.MethodType"):
        assert patch_form not in source, "processor를 패치하고 있다: %s" % patch_form
    assert "tg.PROCESSOR_MONKEY_PATCH_ALLOWED" in source


def test_wvr_n31_the_runner_feeds_pixels_and_indices_from_separate_sources():
    source = RUNNER.read_text(encoding="utf-8")
    # 픽셀은 항상 고정 격자에서, indices는 arm plan에서 온다
    assert "probe.sample_frames(video,\n                                                                   stamps)" \
        in source or "probe.sample_frames(video, stamps)" in source
    assert 'frames_indices=list(metadata_used["frames_indices"])' in source
    assert 'videos=[frames]' in source
    assert 'raise RunError("픽셀이 원본 W00과 다르다' in source
    assert 'if not record["pixel_identity"]["identical"]:' in source,         "픽셀 identity 가드가 사라졌다"
    assert 'if arm["metadata_mode"] == "M0" and' in source,         "M0 index 대조 가드가 사라졌다"
    assert 'list(arm["frames_indices"]) != list(decoded_indices)' in source
    assert '"frames_indices": list(decoded_indices)}' not in source,         "metadata가 arm plan이 아니라 디코드 index를 쓰고 있다"


def _seed_runs(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    runs.mkdir()
    for name in tg.FROZEN_ARTIFACTS:
        source = RUNS / name
        if not source.is_file():
            pytest.skip("선행 산출물이 없다: %s" % name)
        shutil.copy2(source, runs / name)
    return runs


def test_wvr_n32_preflight_refuses_a_second_run_and_tampered_ancestors(
        tmp_path):
    runs = _seed_runs(tmp_path)
    plan = runner.preflight("A", runs, rate=RATE)
    assert plan["change"]["inference_config_change"] == "NONE"
    assert len(plan["reference_pixel_hashes"]) == tg.PIXEL_FRAME_COUNT
    assert plan["plan"]["frames_indices"][0] == 0
    plan["out_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight("A", runs)
    (runs / "subdiv_v1_C2.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight("B", runs)


def test_wvr_n33_preflight_refuses_open_flags(tmp_path, monkeypatch):
    runs = _seed_runs(tmp_path)
    for name in ("RETRY_ALLOWED", "RAW_SALVAGE_ALLOWED",
                 "TOKEN_CAP_INCREASE_APPROVED",
                 "PROMPT_TEXT_MUTATION_ALLOWED", "SCHEMA_MUTATION_ALLOWED",
                 "PROCESSOR_MONKEY_PATCH_ALLOWED"):
        monkeypatch.setattr(tg, name, True)
        with pytest.raises(runner.RunError):
            runner.preflight("C", runs)
        monkeypatch.setattr(tg, name, False)

    def _refuse(value):
        raise AssertionError("허용되지 않은 token cap: %r" % value)

    monkeypatch.setattr(runner.events, "assert_allowed", _refuse)
    with pytest.raises(AssertionError):
        runner.preflight("C", runs)


# ── WVR-N34~N37 요약·self-check 게이트 ─────────────────────────────
def _write_arms(runs: Path, selfcheck=True, **kwargs) -> None:
    for arm_id in tg.ARM_IDS:
        record = _record(arm_id, **kwargs.get(arm_id, {}))
        record["validity"] = tg.arm_validity(record, "v")
        (runs / ("%s_%s.json" % (tg.ARTIFACT_TAG, arm_id))).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")
    if selfcheck is not None:
        (runs / summary_tool.SELFCHECK_NAME).write_text(json.dumps(
            {"status": "SEPARABLE" if selfcheck else tg.IMPLEMENTATION_BLOCKED,
             "separable": bool(selfcheck), "checks": {},
             "transformers_version": "5.14.1"}), encoding="utf-8")


def test_wvr_n34_summary_classifies_the_designed_pattern(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_arms(runs, A={"cap": True}, B={"cap": True})
    summary = summary_tool.build(runs)
    verdict = summary["verdict"]
    assert verdict["verdict"] == tg.PROMPT_TIME_EFFECT
    assert verdict["pattern"] == {"A": "WINDOW_INVALID", "B": "WINDOW_INVALID",
                                  "C": "WINDOW_VALID", "D": "WINDOW_VALID"}
    assert summary["manipulation_audit"]["ok"] is True
    assert summary["pixel_agreement"]["identical"] is True
    assert summary["cross_arm_audit"]["role"] == "AUDIT_DIAGNOSTIC_ONLY"
    assert summary["arms"][0]["prompt_mode"] == "P0"


def test_wvr_n35_summary_blocks_without_a_passing_selfcheck(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_arms(runs, selfcheck=False, A={"cap": True}, B={"cap": True})
    summary = summary_tool.build(runs)
    assert summary["verdict"]["verdict"] == tg.INCONCLUSIVE
    assert tg.IMPLEMENTATION_BLOCKED in summary["verdict"]["blockers"]

    runs2 = tmp_path / "runs2"
    runs2.mkdir()
    _write_arms(runs2, selfcheck=None, A={"cap": True}, B={"cap": True})
    assert summary_tool.build(runs2)["verdict"]["verdict"] == tg.INCONCLUSIVE


def test_wvr_n36_summary_blocks_on_a_failed_manipulation(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_arms(runs, A={"cap": True}, B={"cap": True,
                                          "indices": list(
                                              tg.arm_plan("A", RATE)[
                                                  "frames_indices"])})
    summary = summary_tool.build(runs)
    assert summary["verdict"]["verdict"] == tg.INCONCLUSIVE
    assert tg.METADATA_MANIPULATION_FAILURE in summary["verdict"]["blockers"]


def test_wvr_n37_the_selfcheck_tool_is_a_hard_blocker_before_inference():
    source = SELFCHECK_TOOL.read_text(encoding="utf-8")
    assert "Qwen3VLForConditionalGeneration" not in source, \
        "self-check는 모델을 올리지 않는다"
    assert "pixel_values_videos" in source
    assert "IMPLEMENTATION_BLOCKED" in source
    assert '"pixel_values_identical_across_arms": len(pixel_values) == 1,'         in source, "self-check가 픽셀 동일성을 실제로 재지 않는다"
    batch = BATCH.read_text(encoding="utf-8")
    assert batch.index("wvr_trigger_validate.py") < batch.index(
        "wvr_trigger_selfcheck.py") < batch.index("wvr_trigger_run.py")
    assert "IMPLEMENTATION_BLOCKED — 추론하지 않는다" in batch
    assert "for arm in A B C D" in batch
    assert "재시도하지 않는다" in batch
    assert "for attempt" not in batch
    assert batch.count("for ") == 1


# ── WVR-N38~N40 경계 ──────────────────────────────────────────────
def test_wvr_n38_prior_artifacts_are_untouched():
    for name, expected in tg.FROZEN_ARTIFACTS.items():
        path = RUNS / name
        if not path.is_file():
            pytest.skip("선행 산출물이 없다: %s" % name)
        assert _sha256_file(path) == expected, "선행 산출물이 바뀌었다: %s" % name
    if SUBMISSION.is_file():
        assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert tg.PRIOR_STATE["WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1"] == \
        "CLOSED / RECOVERY_FAIL"
    assert tg.PRIOR_STATE["original_W00"].startswith("WINDOW_INVALID")
    row = tg.frozen_artifacts_unchanged(dict(tg.FROZEN_ARTIFACTS))
    assert row["unchanged"] is True
    changed = dict(tg.FROZEN_ARTIFACTS)
    changed["shadow_v1_W00_raw.txt"] = "0" * 64
    assert tg.frozen_artifacts_unchanged(changed)["unchanged"] is False
    partial = {key: value for key, value in tg.FROZEN_ARTIFACTS.items()
               if key != "subdiv_v1_C1.json"}
    assert tg.frozen_artifacts_unchanged(partial)["missing"] == \
        ["subdiv_v1_C1.json"]


def test_wvr_n39_every_expansion_flag_is_off():
    for name in ("RETRY_ALLOWED", "RAW_SALVAGE_ALLOWED",
                 "TOKEN_CAP_INCREASE_APPROVED",
                 "PROMPT_TEXT_MUTATION_ALLOWED", "SCHEMA_MUTATION_ALLOWED",
                 "VISUAL_CONTENT_MANIPULATION_ALLOWED",
                 "RECOVERY_ATTEMPT_ALLOWED", "PROCESSOR_MONKEY_PATCH_ALLOWED",
                 "ORIGINAL_W00_MAY_BE_REVALIDATED", "MAPPING_REVEAL_ALLOWED",
                 "SEMANTIC_VERDICT_BY_EXECUTOR",
                 "PRODUCTION_PROMOTION_ALLOWED"):
        assert getattr(tg, name) is False, "%s가 열려 있다" % name


def test_wvr_n40_the_validator_checks_the_two_by_two_design():
    source = VALIDATOR.read_text(encoding="utf-8")
    for name in ("prompt_A_equals_B", "prompt_C_equals_D",
                 "prompt_A_differs_C", "indices_A_equal_C",
                 "indices_B_equal_D", "indices_A_differ_B",
                 "frozen_artifacts_unchanged", "token_cap_frozen"):
        assert '"%s":' % name in source, "validator가 %s를 확인하지 않는다" % name
    assert VALIDATOR.is_file() and SUMMARY_TOOL.is_file()


# ── WVR-N41~N43 구조 단정 (상수가 흔들릴 때만 발화하는 검사) ────────
def test_wvr_n41_pixel_grid_assertions_fire_when_the_design_moves(
        monkeypatch):
    monkeypatch.setattr(tg, "PIXEL_FRAME_COUNT", 23)
    with pytest.raises(tg.TriggerError):
        tg.pixel_times()
    monkeypatch.setattr(tg, "PIXEL_FRAME_COUNT", 24)
    monkeypatch.setattr(tg, "SOURCE_WINDOW_ID", "W01")
    with pytest.raises(tg.TriggerError):
        tg.source_window()
    monkeypatch.setattr(tg, "SOURCE_WINDOW_ID", "W00")
    assert tg.source_window()["window_id"] == "W00"


def test_wvr_n42_summary_catches_pixel_drift_that_arms_report_as_clean(
        tmp_path):
    """arm record가 픽셀 동일이라고 주장해도 arm 간 해시가 다르면 막아야 한다."""
    runs = tmp_path / "runs"
    runs.mkdir()
    drifted = list(PIXEL_HASHES)
    drifted[5] = "other"
    for arm_id in tg.ARM_IDS:
        record = _record(arm_id, cap=(arm_id in ("A", "B")))
        if arm_id == "D":
            record["frame_hashes"] = drifted
        record["pixel_identity"] = {"identical": True, "forged_for_test": True}
        record["validity"] = tg.arm_validity(record, "v")
        (runs / ("%s_%s.json" % (tg.ARTIFACT_TAG, arm_id))).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")
    (runs / summary_tool.SELFCHECK_NAME).write_text(json.dumps(
        {"status": "SEPARABLE", "separable": True, "checks": {},
         "transformers_version": "5.14.1"}), encoding="utf-8")
    summary = summary_tool.build(runs)
    assert summary["pixel_agreement"]["identical"] is False
    assert summary["pixel_agreement"]["differing_arms"] == ["D"]
    assert summary["verdict"]["verdict"] == tg.INCONCLUSIVE
    assert tg.PIXEL_IDENTITY_FAILURE in summary["verdict"]["blockers"]


def test_wvr_n43_cross_arm_audit_is_diagnostic_only(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_arms(runs, A={"cap": True}, B={"cap": True})
    for arm_id, text in (("A", "raw-A"), ("B", "raw-A"), ("C", "raw-C"),
                         ("D", "raw-D")):
        (runs / ("%s_%s_raw.txt" % (tg.ARTIFACT_TAG, arm_id))).write_text(
            text, encoding="utf-8")
    audit = summary_tool.build(runs)["cross_arm_audit"]
    assert audit["role"] == "AUDIT_DIAGNOSTIC_ONLY"
    assert audit["pairs"]["A_vs_B"]["raw_identical"] is True
    assert audit["pairs"]["A_vs_C"]["raw_identical"] is False
    assert audit["pairs"]["A_vs_C"]["first_divergence_offset"] == 4
