"""W00 subdivision recovery 계약 (2026-09-09 · WVR-L01~L43).

```
child      C0 [0,24) · C1 [12,36) · C2 [24,48) · 각 12프레임 · 0.5fps 격자
coverage   parent [0,48) gap 0 · 겹침 2개 각 공유 프레임 6
게이트      INCONCLUSIVE(측정 불가) → FAIL(모델 출력 실패) → PASS(3/3 VALID)
계약       raw-before-parse · retry 없음 · 원본 W00 무변경 · packet은 PASS일 때만
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
import wvr_w00_repro as rp

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md")
PREREG = ROOT / PREREG_REL
RUNNER = ROOT / "scripts/wvr_subdiv_run.py"
SUMMARY_TOOL = ROOT / "scripts/wvr_subdiv_summary.py"
FRAMES_TOOL = ROOT / "scripts/wvr_subdiv_frames.py"
VALIDATOR = ROOT / "scripts/wvr_subdiv_validate.py"
BATCH = ROOT / "scripts/wvr_subdiv_batch.sh"
RUNS = ROOT / "runs/wvr_light_v1"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"
SUBMISSION_SHA = ("5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca9"
                  "94e9cd7b")


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(RUNNER, "wvr_subdiv_run_mod")
summary_tool = _module(SUMMARY_TOOL, "wvr_subdiv_summary_mod")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _record(child_id="C0", frames=None, cap=False, degenerate=False,
            raw=True, video="v", status="OK", events_rows=None):
    child = sd.child_by_id(child_id)
    stamps = list(sd.frame_times(child))
    rows = events_rows if events_rows is not None else [
        {"index": 0, "start_sec": child["start_sec"],
         "end_sec": child["start_sec"] + 6.0, "actor": "a person",
         "action": "pouring", "object_or_state": "liquid into a bowl",
         "signature": ("a person", "pouring", "liquid into a bowl"),
         "source_indices": [0], "collapsed_count": 1},
        {"index": 1, "start_sec": child["start_sec"] + 6.0,
         "end_sec": child["start_sec"] + 12.0, "actor": "a person",
         "action": "stirring", "object_or_state": "a bowl",
         "signature": ("a person", "stirring", "a bowl"),
         "source_indices": [1], "collapsed_count": 1},
    ]
    unique = {tuple(row["signature"]) for row in rows}
    return {
        "event": sd.EVENT, "child": child,
        "frame_times": stamps if frames is None else stamps[:frames],
        "frame_hashes": ["px%.0f" % time for time in stamps],
        "raw_persisted": raw, "video_sha256": video,
        "arm_status": status,
        "prompt_hash": diag.prompt_hash(),
        "runtime_config_hash": "rt",
        "original_w00_unchanged": {"unchanged": True},
        "lineage": {"checked": 12, "mismatches": [], "identity_ok": True},
        "inference_config_change": {"inference_config_change": "NONE",
                                    "geometry_as_declared": True},
        "requested": {"max_new_tokens": 4096},
        "metrics": {"delivered_frame_count":
                    sd.FRAMES_PER_CHILD if frames is None else frames,
                    "generated_token_count": 4096 if cap else 900,
                    "generation_cap_hit": cap},
        "parsed": {"status": "OK", "events": rows, "collapsed": rows,
                   "language": {"satisfied": True, "violations": []}},
        "representation": {"collapsed_event_count": len(rows),
                           "unique_signature_count": len(unique),
                           "degenerate": degenerate},
        "structure": {"raw_length": 800, "complete_object_count": len(rows),
                      "unique_signature_count": len(unique),
                      "zero_length_interval_count": 0,
                      "max_signature_repeat": 1, "json_parse_ok": True},
    }


def _row(child_id="C0", valid=True, blockers=(), failures=()):
    return {"child_id": child_id, "valid": valid,
            "blockers": list(blockers), "output_failures": list(failures),
            "reasons": list(blockers) + list(failures)}


def _identity(ok=True):
    return [{"overlap_id": row["overlap_id"], "identity_ok": ok}
            for row in sd.overlaps()]


# ── WVR-L01~L08 일정·동결 ───────────────────────────────────────────
def test_wvr_l01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_l02_exactly_three_children_with_frozen_spans():
    rows = sd.children()
    assert len(rows) == 3
    assert tuple((row["child_id"], row["start_sec"], row["end_sec"])
                 for row in rows) == (("C0", 0.0, 24.0), ("C1", 12.0, 36.0),
                                      ("C2", 24.0, 48.0))
    assert sd.CHILD_IDS == ("C0", "C1", "C2")


def test_wvr_l03_twelve_frames_on_the_exact_half_fps_grid():
    assert sd.frame_times(sd.child_by_id("C0")) == (
        0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0)
    assert sd.frame_times(sd.child_by_id("C1")) == (
        12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0,
        34.0)
    assert sd.frame_times(sd.child_by_id("C2")) == (
        24.0, 26.0, 28.0, 30.0, 32.0, 34.0, 36.0, 38.0, 40.0, 42.0, 44.0,
        46.0)
    for row in sd.children():
        stamps = sd.frame_times(row)
        assert len(stamps) == sd.FRAMES_PER_CHILD == 12
        assert stamps[-1] < row["end_sec"]


def test_wvr_l04_parent_coverage_has_no_gap():
    row = sd.assert_coverage()
    assert row["covered"] is True
    assert row["gaps"] == []
    assert row["parent"] == [0.0, 48.0]
    assert row["union"] == [0.0, 48.0]


def test_wvr_l05_two_overlaps_with_frozen_spans():
    rows = sd.overlaps()
    assert len(rows) == 2
    assert tuple((row["overlap_id"], row["earlier"], row["later"],
                  row["start_sec"], row["end_sec"]) for row in rows) == (
        ("R-O1", "C0", "C1", 12.0, 24.0),
        ("R-O2", "C1", "C2", 24.0, 36.0))


def test_wvr_l06_each_overlap_shares_exactly_six_frames():
    assert sd.shared_times(sd.overlap_by_id("R-O1")) == (
        12.0, 14.0, 16.0, 18.0, 20.0, 22.0)
    assert sd.shared_times(sd.overlap_by_id("R-O2")) == (
        24.0, 26.0, 28.0, 30.0, 32.0, 34.0)
    for row in sd.overlaps():
        assert len(sd.shared_times(row)) == sd.SHARED_FRAMES_PER_OVERLAP == 6


def test_wvr_l07_child_frames_lie_on_the_parent_w00_grid():
    parent = set(sh.frame_times(sd.parent_window()))
    for row in sd.children():
        assert set(sd.frame_times(row)) <= parent, "계보 대조가 불가능해진다"


def test_wvr_l08_inference_configuration_is_frozen_to_w00():
    assert sd.FROZEN_FROM_W00["prompt_hash"] == diag.prompt_hash()
    assert sd.FROZEN_FROM_W00["max_new_tokens"] == tokens.tokens_for(
        tokens.EVENT_V2) == 4096
    assert sd.FROZEN_FROM_W00["repetition_penalty"] == 1.0
    assert sd.FROZEN_FROM_W00["do_sample"] is False
    assert sd.FROZEN_FROM_W00["sampling_fps"] == sd.SAMPLING_FPS == 0.5
    assert "window_sec" not in sd.FROZEN_FROM_W00
    assert "frames_per_window" not in sd.FROZEN_FROM_W00
    for key in ("model_revision", "dtype", "attn_implementation",
                "frame_width", "frame_height", "prompt_contract"):
        assert sd.FROZEN_FROM_W00[key] == sh.FROZEN_FROM_SHORT_WINDOW[key]


# ── WVR-L09~L10 설정 변경 감지 ──────────────────────────────────────
def test_wvr_l09_config_change_is_none_only_for_the_declared_geometry():
    requested = dict(sd.FROZEN_FROM_W00)
    requested.update(sd.DECLARED_GEOMETRY)
    change = sd.inference_config_change(requested)
    assert change["inference_config_change"] == "NONE"
    assert change["geometry_as_declared"] is True

    tampered = dict(requested)
    tampered["max_new_tokens"] = 8192
    detected = sd.inference_config_change(tampered)
    assert detected["inference_config_change"] == "DETECTED"
    assert "max_new_tokens" in detected["differences"]


def test_wvr_l10_forty_eight_second_geometry_is_not_the_declared_change():
    requested = dict(sd.FROZEN_FROM_W00)
    requested.update({"window_sec": 48.0, "frames_per_window": 24})
    change = sd.inference_config_change(requested)
    assert change["inference_config_change"] == "NONE"
    assert change["geometry_as_declared"] is False


# ── WVR-L11~L18 child 기술 검증 ────────────────────────────────────
def test_wvr_l11_a_clean_child_is_valid():
    row = sd.child_validity(_record(), "v")
    assert row["valid"] is True
    assert row["status"] == sd.CHILD_VALID == "WINDOW_VALID"
    assert row["reasons"] == []
    assert row["blockers"] == [] and row["output_failures"] == []


def test_wvr_l12_generation_cap_hit_is_an_output_failure():
    row = sd.child_validity(_record(cap=True), "v")
    assert row["valid"] is False
    assert row["status"] == sd.CHILD_INVALID
    assert "TRUNCATED_AT_CAP" in row["output_failures"]
    assert row["blockers"] == []


def test_wvr_l13_frame_count_mismatch_is_a_blocker():
    row = sd.child_validity(_record(frames=11), "v")
    assert sh.FRAME_COUNT_MISMATCH in row["blockers"]
    assert sh.FRAME_COUNT_MISMATCH not in row["output_failures"]
    assert row["valid"] is False


def test_wvr_l14_grid_mismatch_is_a_blocker():
    record = _record()
    record["frame_times"] = [1.0] + record["frame_times"][1:]
    row = sd.child_validity(record, "v")
    assert sh.GRID_MISMATCH in row["blockers"]


def test_wvr_l15_missing_raw_is_a_blocker():
    row = sd.child_validity(_record(raw=False), "v")
    assert sh.RAW_NOT_PERSISTED in row["blockers"]


def test_wvr_l16_video_provenance_mismatch_is_a_blocker():
    row = sd.child_validity(_record(video="other"), "v")
    assert sh.PROVENANCE_MISMATCH in row["blockers"]


def test_wvr_l17_representation_degeneracy_is_an_output_failure():
    row = sd.child_validity(_record(degenerate=True), "v")
    assert sd.REPRESENTATION_DEGENERACY in row["output_failures"]
    assert row["blockers"] == []


def test_wvr_l18_runtime_failure_is_a_blocker():
    record = _record(status=sd.RUNTIME_FAILURE, raw=False)
    record.pop("parsed")
    record.pop("representation")
    row = sd.child_validity(record, "v")
    assert sd.RUNTIME_FAILURE in row["blockers"]
    assert row["valid"] is False


# ── WVR-L19~L25 recovery 게이트 ────────────────────────────────────
def test_wvr_l19_three_valid_children_pass():
    gate = sd.recovery_verdict([_row("C0"), _row("C1"), _row("C2")],
                               _identity())
    assert gate["recovery_verdict"] == sd.RECOVERY_PASS
    assert gate["reason"] == "ALL_CHILDREN_VALID"
    assert gate["valid_child_count"] == 3
    assert gate["blockers"] == []


def test_wvr_l20_one_output_failure_is_recovery_fail():
    gate = sd.recovery_verdict(
        [_row("C0"), _row("C1", valid=False, failures=("TRUNCATED_AT_CAP",)),
         _row("C2")], _identity())
    assert gate["recovery_verdict"] == sd.RECOVERY_FAIL
    assert gate["reason"] == "CHILD_TECHNICAL_INVALID"
    assert gate["invalid_children"] == ["C1"]
    assert gate["packet_generation_allowed"] is False


def test_wvr_l21_a_blocker_outranks_an_output_failure():
    gate = sd.recovery_verdict(
        [_row("C0", valid=False, blockers=(sh.GRID_MISMATCH,)),
         _row("C1", valid=False, failures=("PARSE_FAILURE",)), _row("C2")],
        _identity())
    assert gate["recovery_verdict"] == sd.INCONCLUSIVE
    assert gate["reason"] == "MEASUREMENT_BLOCKED"
    assert sh.GRID_MISMATCH in gate["blockers"]


def test_wvr_l22_a_missing_child_blocks_the_measurement():
    gate = sd.recovery_verdict([_row("C0"), _row("C1")], _identity())
    assert gate["recovery_verdict"] == sd.INCONCLUSIVE
    assert sd.CHILD_COUNT_MISMATCH in gate["blockers"]


def test_wvr_l23_shared_frame_identity_failure_blocks_the_measurement():
    gate = sd.recovery_verdict([_row("C0"), _row("C1"), _row("C2")],
                               _identity(ok=False))
    assert gate["recovery_verdict"] == sd.INCONCLUSIVE
    assert sh.SHARED_FRAME_IDENTITY_FAILURE in gate["blockers"]


def test_wvr_l24_pass_stops_at_semantic_review_pending():
    gate = sd.recovery_verdict([_row("C0"), _row("C1"), _row("C2")],
                               _identity())
    assert gate["packet_generation_allowed"] is True
    assert gate["event_status"] == ("SUBDIVISION_TECHNICAL_RECOVERY_PASS + "
                                    "SEMANTIC_REVIEW_PENDING")
    failed = sd.recovery_verdict(
        [_row("C0", valid=False, failures=("PARSE_FAILURE",)), _row("C1"),
         _row("C2")], _identity())
    assert failed["event_status"] == sd.RECOVERY_FAIL


def test_wvr_l25_the_executor_never_fills_a_semantic_verdict():
    for identity in (_identity(), _identity(ok=False)):
        gate = sd.recovery_verdict([_row("C0"), _row("C1"), _row("C2")],
                                   identity)
        assert gate["semantic_verdict"] is None
        assert gate["semantic_verdict_by_executor"] is False
    assert sd.SEMANTIC_VERDICT_BY_EXECUTOR is False
    assert sd.ALLOWED_MAX_CONCLUSION.startswith(
        "The deterministic W00 degeneracy observed at 48 seconds was not")
    for phrase in ("24초 semantic stability proven", "24초 production approved",
                   "0.5fps sufficient", "Event extraction solved",
                   "48초가 degeneracy의 원인이다", "24초 전체 architecture 불가능"):
        assert phrase in sd.FORBIDDEN_CONCLUSIONS


# ── WVR-L26~L29 blinding · identity · 계보 ─────────────────────────
def test_wvr_l26_blinding_is_deterministic_and_complementary():
    sha = "e593914d69826c378ce59c3476b036396ac3a723"
    for overlap_id in ("R-O1", "R-O2"):
        earlier = sd.blind_label(overlap_id, "earlier", sha)
        later = sd.blind_label(overlap_id, "later", sha)
        assert {earlier, later} == {"A", "B"}
        assert sd.blind_label(overlap_id, "earlier", sha) == earlier
        assert sd.blind_label(overlap_id, "earlier", "other") in ("A", "B")
    for overlap_id in ("R-O1", "R-O2"):
        assigned = {sd.blind_label(overlap_id, "earlier", "salt%d" % index)
                    for index in range(40)}
        assert assigned == {"A", "B"}, "earlier가 한쪽 라벨에 고정돼 있다"
    with pytest.raises(sd.SubdivisionError):
        sd.blind_label("R-O1", "middle", sha)
    with pytest.raises(sd.SubdivisionError):
        sd.blind_label("R-O1", "earlier", "")


def test_wvr_l27_shared_frame_identity_catches_mismatch_and_absence():
    good = {"C0": {time: "px%.0f" % time
                   for time in sd.frame_times(sd.child_by_id("C0"))},
            "C1": {time: "px%.0f" % time
                   for time in sd.frame_times(sd.child_by_id("C1"))},
            "C2": {time: "px%.0f" % time
                   for time in sd.frame_times(sd.child_by_id("C2"))}}
    rows = sd.shared_frame_identity(good)
    assert [row["identity_ok"] for row in rows] == [True, True]
    assert [row["shared_observed"] for row in rows] == [6, 6]

    tampered = {key: dict(value) for key, value in good.items()}
    tampered["C1"][16.0] = "different"
    rows = sd.shared_frame_identity(tampered)
    assert rows[0]["identity_ok"] is False
    assert rows[0]["pixel_hash_mismatches"] == [16.0]

    dropped = {key: dict(value) for key, value in good.items()}
    dropped["C2"].pop(28.0)
    rows = sd.shared_frame_identity(dropped)
    assert rows[1]["identity_ok"] is False
    assert rows[1]["missing_times"] == [28.0]
    assert rows[1]["shared_observed"] == 5


def test_wvr_l28_lineage_report_needs_a_reference_and_flags_mismatch():
    table = {"C0": {0.0: "a", 2.0: "b"}}
    assert sd.lineage_report(table, {0.0: "a", 2.0: "b"})["identity_ok"] \
        is True
    bad = sd.lineage_report(table, {0.0: "a", 2.0: "zz"})
    assert bad["identity_ok"] is False
    assert bad["mismatches"][0]["time_sec"] == 2.0
    empty = sd.lineage_report(table, {})
    assert empty["checked"] == 0 and empty["identity_ok"] is False
    assert len(empty["uncovered"]) == 2


def test_wvr_l29_original_w00_hashes_are_the_frozen_repro_hashes():
    assert sd.ORIGINAL_RECORD_SHA256 == rp.ORIGINAL_RECORD_SHA256
    assert sd.ORIGINAL_RAW_SHA256 == rp.ORIGINAL_RAW_SHA256
    row = sd.original_unchanged(sd.ORIGINAL_RECORD_SHA256,
                                sd.ORIGINAL_RAW_SHA256)
    assert row["unchanged"] is True
    assert row["may_be_revalidated"] is False
    assert row["original_status_retained"] == "WINDOW_INVALID"
    assert sd.original_unchanged("0" * 64,
                                 sd.ORIGINAL_RAW_SHA256)["unchanged"] is False
    assert sd.ORIGINAL_W00_MAY_BE_REVALIDATED is False
    assert sd.SHADOW_V1_RETROACTIVE_REPAIR_ALLOWED is False


# ── WVR-L30~L32 실행기 계약 ────────────────────────────────────────
def test_wvr_l30_the_runner_persists_raw_before_parsing():
    source = RUNNER.read_text(encoding="utf-8")
    persist = source.index('raw_path.write_text(raw_output')
    parse = source.index('v2.parse_events(raw_output')
    assert persist < parse, "raw를 파싱보다 먼저 저장해야 한다"
    assert "for attempt" not in source and "while True" not in source
    assert "max_new_tokens=plan[\"max_new_tokens\"]" in source


def _seed_runs(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    runs.mkdir()
    for name in (sd.ORIGINAL_RECORD, sd.ORIGINAL_RAW):
        source = RUNS / name
        if not source.is_file():
            pytest.skip("원본 W00 산출물이 없다: %s" % name)
        shutil.copy2(source, runs / name)
    bank = RUNS / runner.BANK_MANIFEST
    if bank.is_file():
        shutil.copy2(bank, runs / runner.BANK_MANIFEST)
    return runs


def test_wvr_l31_preflight_refuses_a_second_run_of_the_same_child(tmp_path):
    runs = _seed_runs(tmp_path)
    plan = runner.preflight("C0", runs)
    assert plan["change"]["inference_config_change"] == "NONE"
    assert plan["change"]["geometry_as_declared"] is True
    assert plan["reference_missing_times"] == []
    plan["out_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight("C0", runs)


def test_wvr_l32_preflight_refuses_tampered_originals_and_retry(tmp_path,
                                                                monkeypatch):
    runs = _seed_runs(tmp_path)
    monkeypatch.setattr(sd, "RETRY_ALLOWED", True)
    with pytest.raises(runner.RunError):
        runner.preflight("C1", runs)
    monkeypatch.setattr(sd, "RETRY_ALLOWED", False)
    monkeypatch.setattr(sd, "TOKEN_CAP_INCREASE_APPROVED", True)
    with pytest.raises(runner.RunError):
        runner.preflight("C1", runs)
    monkeypatch.setattr(sd, "TOKEN_CAP_INCREASE_APPROVED", False)
    (runs / sd.ORIGINAL_RAW).write_text("tampered", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight("C1", runs)


# ── WVR-L33~L34 요약·packet 게이트 ─────────────────────────────────
def _write_children(runs: Path, **kwargs) -> None:
    for child_id in sd.CHILD_IDS:
        record = _record(child_id, **kwargs.get(child_id, {}))
        record["validity"] = sd.child_validity(record, "v")
        (runs / ("%s_%s.json" % (sd.ARTIFACT_TAG, child_id))).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")


def test_wvr_l33_the_packet_is_built_only_on_a_pass(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_children(runs)
    built = summary_tool.build(runs, "e593914d")
    gate = built["summary"]["recovery_gate"]
    assert gate["recovery_verdict"] == sd.RECOVERY_PASS
    assert built["summary"]["packet_generated"] is True
    assert "### Arm A" in built["packet"] and "### Arm B" in built["packet"]
    assert "R-O1" in built["packet"] and "R-O2" in built["packet"]
    for overlap_id in ("R-O1", "R-O2"):
        row = built["mapping"]["mapping"][overlap_id]
        assert {row["A"], row["B"]} == {
            sd.overlap_by_id(overlap_id)["earlier"],
            sd.overlap_by_id(overlap_id)["later"]}
    for leaked in ("C0", "C1", "C2"):
        assert leaked not in built["packet"]
    assert built["summary"]["coverage"]["covered"] is True
    assert built["summary"]["recovery_gate"]["semantic_verdict"] is None


def test_wvr_l34_a_failing_child_suppresses_the_packet(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_children(runs, C1={"cap": True})
    built = summary_tool.build(runs, "e593914d")
    gate = built["summary"]["recovery_gate"]
    assert gate["recovery_verdict"] == sd.RECOVERY_FAIL
    assert gate["invalid_children"] == ["C1"]
    assert "packet" not in built and "mapping" not in built
    assert built["summary"]["packet_generated"] is False


def test_wvr_l35_the_frame_packet_gate_requires_a_pass(tmp_path):
    frames_tool = _module(FRAMES_TOOL, "wvr_subdiv_frames_mod")
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / frames_tool.SUMMARY_NAME).write_text(json.dumps(
        {"recovery_gate": {"recovery_verdict": sd.RECOVERY_FAIL}}),
        encoding="utf-8")
    with pytest.raises(frames_tool.FrameError):
        frames_tool.gate(runs)
    (runs / frames_tool.SUMMARY_NAME).write_text(json.dumps(
        {"recovery_gate": {"recovery_verdict": sd.RECOVERY_PASS}}),
        encoding="utf-8")
    assert frames_tool.gate(runs)["recovery_gate"]["recovery_verdict"] == \
        sd.RECOVERY_PASS
    assert sd.audit_times() == {"R-O1": [12.0, 14.0, 16.0, 18.0, 20.0, 22.0],
                                "R-O2": [24.0, 26.0, 28.0, 30.0, 32.0, 34.0]}
    assert sd.FRAME_AUDIT_EXPANSION_ALLOWED is False


# ── WVR-L36~L38 경계 ──────────────────────────────────────────────
def test_wvr_l36_prior_events_and_originals_are_untouched():
    for name, expected in ((sd.ORIGINAL_RECORD, sd.ORIGINAL_RECORD_SHA256),
                           (sd.ORIGINAL_RAW, sd.ORIGINAL_RAW_SHA256)):
        path = RUNS / name
        if not path.is_file():
            pytest.skip("원본 W00 산출물이 없다: %s" % name)
        assert _sha256_file(path) == expected, "원본 W00이 바뀌었다: %s" % name
    if SUBMISSION.is_file():
        assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert sd.PRIOR_STATE["WVR_EVENT_EXTRACTION_SHADOW_V1"] == \
        "CLOSED / INCONCLUSIVE"
    assert sd.PRIOR_STATE["WVR_W00_DEGENERACY_REPRO_V1"] == \
        "CLOSED / REPRODUCIBLE"
    assert sd.PRIOR_STATE["original_W00"].startswith("WINDOW_INVALID")


def test_wvr_l37_every_expansion_flag_is_off():
    for name in ("RETRY_ALLOWED", "RAW_SALVAGE_ALLOWED",
                 "TOKEN_CAP_INCREASE_APPROVED",
                 "ORIGINAL_W00_MAY_BE_REVALIDATED",
                 "SHADOW_V1_RETROACTIVE_REPAIR_ALLOWED",
                 "MAPPING_REVEAL_ALLOWED", "SEMANTIC_VERDICT_BY_EXECUTOR",
                 "PRODUCTION_PROMOTION_ALLOWED",
                 "EVENT_MAP_PRODUCTION_APPROVED",
                 "STITCHING_PRODUCTION_ALLOWED",
                 "FULL_C01_RESUBDIVISION_ALLOWED",
                 "FRAME_AUDIT_EXPANSION_ALLOWED",
                 "BRANCH_EXECUTION_ALLOWED"):
        assert getattr(sd, name) is False, "%s가 열려 있다" % name
    assert set(sd.BRANCHES) == {"PASS + semantic overlap stable",
                                "PASS + semantic divergence",
                                "RECOVERY FAIL", "INCONCLUSIVE"}


def test_wvr_l38_the_batch_runs_the_validator_and_never_retries():
    source = BATCH.read_text(encoding="utf-8")
    assert "wvr_subdiv_validate.py" in source
    assert source.index("wvr_subdiv_validate.py") < source.index(
        "wvr_subdiv_run.py")
    assert "for child in C0 C1 C2" in source
    assert "재시도하지 않는다" in source
    assert "for attempt" not in source
    assert source.count("for ") == 1, "child 루프 외의 반복이 들어왔다"
    assert VALIDATOR.is_file() and SUMMARY_TOOL.is_file()
    assert sd.RECOVERY_VERDICTS == (
        "SUBDIVISION_TECHNICAL_RECOVERY_PASS", "SUBDIVISION_RECOVERY_FAIL",
        "INCONCLUSIVE")


# ── WVR-L39~L42 기하 단정 (구조가 깨졌을 때만 발화하는 검사) ────────
def test_wvr_l39_frames_may_not_leave_their_child_window():
    with pytest.raises(sd.SubdivisionError):
        sd.frame_times({"child_id": "X", "start_sec": 0.0, "end_sec": 10.0})
    assert sd.frame_times({"child_id": "X", "start_sec": 100.0,
                           "end_sec": 124.0})[-1] == 122.0


def test_wvr_l40_coverage_reports_a_gap_when_children_do_not_touch():
    rows = [{"child_id": "C0", "start_sec": 0.0, "end_sec": 24.0},
            {"child_id": "C2", "start_sec": 26.0, "end_sec": 48.0}]
    row = sd.coverage(rows)
    assert row["covered"] is False
    assert row["gaps"] == [[24.0, 26.0]]
    short = sd.coverage([{"child_id": "C0", "start_sec": 0.0,
                          "end_sec": 24.0}])
    assert short["covered"] is False and short["gaps"] == [[24.0, 48.0]]


def test_wvr_l41_assert_coverage_raises_on_a_gap():
    rows = [{"child_id": "C0", "start_sec": 0.0, "end_sec": 24.0},
            {"child_id": "C2", "start_sec": 26.0, "end_sec": 48.0}]
    with pytest.raises(sd.SubdivisionError):
        sd.assert_coverage(rows)
    assert sd.assert_coverage()["covered"] is True


def test_wvr_l42_non_adjacent_children_share_no_frames():
    with pytest.raises(sd.SubdivisionError):
        sd.shared_times({"overlap_id": "X", "earlier": "C0", "later": "C2",
                         "start_sec": 0.0, "end_sec": 48.0})
    with pytest.raises(sd.SubdivisionError):
        sd.shared_times({"overlap_id": "X", "earlier": "C0", "later": "C1",
                         "start_sec": 30.0, "end_sec": 36.0})


def test_wvr_l43_preflight_enforces_geometry_and_the_token_cap(tmp_path,
                                                               monkeypatch):
    runs = _seed_runs(tmp_path)
    monkeypatch.setattr(sd, "DECLARED_GEOMETRY",
                        {"window_sec": 48.0, "frames_per_window": 24})
    with pytest.raises(runner.RunError):
        runner.preflight("C2", runs)
    monkeypatch.setattr(sd, "DECLARED_GEOMETRY",
                        {"window_sec": sd.CHILD_SEC,
                         "frames_per_window": sd.FRAMES_PER_CHILD})

    def _refuse(value):
        raise AssertionError("허용되지 않은 token cap: %r" % value)

    monkeypatch.setattr(runner.events, "assert_allowed", _refuse)
    with pytest.raises(AssertionError):
        runner.preflight("C2", runs)


def test_wvr_l44_the_summary_derives_structure_from_the_persisted_raw(tmp_path):
    """record의 구조 필드가 비어도 raw 원문에서 사후 계산한다(추론 재실행 없이)."""
    runs = tmp_path / "runs"
    runs.mkdir()
    raw = ('{"events": [{"start_sec": 0.0, "end_sec": 0.0, "actor": "a person",'
           ' "action": "pouring", "object_or_state": "a bowl"},'
           '{"start_sec": 0.0, "end_sec": 0.0, "actor": "a person",'
           ' "action": "pouring", "object_or_state": "a bowl"}')
    for child_id in sd.CHILD_IDS:
        record = _record(child_id)
        record["structure"] = None
        record["raw_path"] = "%s_%s_raw.txt" % (sd.ARTIFACT_TAG, child_id)
        record["validity"] = sd.child_validity(record, "v")
        (runs / record["raw_path"]).write_text(raw, encoding="utf-8")
        (runs / ("%s_%s.json" % (sd.ARTIFACT_TAG, child_id))).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")
    built = summary_tool.build(runs, "e593914d")
    row = built["summary"]["children"][0]
    assert row["structure_source"] == "raw_file_post_hoc"
    assert row["completed_object_count"] == 2
    assert row["zero_duration_count"] == 2
    assert row["positive_duration_count"] == 0
    assert row["json_complete"] is False

    record = json.loads((runs / "subdiv_v1_C0.json").read_text(
        encoding="utf-8"))
    record["raw_persisted"] = False
    (runs / "subdiv_v1_C0.json").write_text(json.dumps(record,
                                                       ensure_ascii=False),
                                            encoding="utf-8")
    again = summary_tool.build(runs, "e593914d")
    assert again["summary"]["children"][0]["structure_source"] == "UNAVAILABLE"
