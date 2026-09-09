"""C0 재귀 분해 계약 (2026-09-09 · WVR-M01~M44).

```
child      D0 [0,12) · D1 [6,18) · D2 [12,24) · 각 6프레임 · 0.5fps 격자
coverage   parent C0 [0,24) gap 0 · 겹침 2개 각 공유 프레임 3
게이트      INCONCLUSIVE(측정 불가) → FAIL(모델 출력 실패) → PASS(3/3 VALID)
계약       raw-before-parse · retry 없음 · C1·C2 재실행 금지 · 6초 자동 재귀 금지 ·
          선행 산출물(C0·C1·C2·W00) 무변경 · packet은 PASS일 때만
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
import wvr_recursive_v1 as rc
import wvr_shadow_v1 as sh
import wvr_subdivision_v1 as sd

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1_2026-09-09.md")
PREREG = ROOT / PREREG_REL
RUNNER = ROOT / "scripts/wvr_recur_run.py"
SUMMARY_TOOL = ROOT / "scripts/wvr_recur_summary.py"
FRAMES_TOOL = ROOT / "scripts/wvr_recur_frames.py"
VALIDATOR = ROOT / "scripts/wvr_recur_validate.py"
BATCH = ROOT / "scripts/wvr_recur_batch.sh"
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


runner = _module(RUNNER, "wvr_recur_run_mod")
summary_tool = _module(SUMMARY_TOOL, "wvr_recur_summary_mod")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _record(child_id="D0", frames=None, cap=False, degenerate=False,
            raw=True, video="v", status="OK"):
    child = rc.child_by_id(child_id)
    stamps = list(rc.frame_times(child))
    rows = [
        {"index": 0, "start_sec": child["start_sec"],
         "end_sec": child["start_sec"] + 3.0, "actor": "person",
         "action": "holding", "object_or_state": "a bottle",
         "signature": ("person", "holding", "a bottle"),
         "source_indices": [0], "collapsed_count": 1},
        {"index": 1, "start_sec": child["start_sec"] + 3.0,
         "end_sec": child["start_sec"] + 6.0, "actor": "person",
         "action": "pouring", "object_or_state": "liquid into a bowl",
         "signature": ("person", "pouring", "liquid into a bowl"),
         "source_indices": [1], "collapsed_count": 1},
    ]
    unique = {tuple(row["signature"]) for row in rows}
    return {
        "event": rc.EVENT, "child": child,
        "frame_times": stamps if frames is None else stamps[:frames],
        "frame_hashes": ["px%.0f" % time for time in stamps],
        "raw_persisted": raw, "video_sha256": video, "arm_status": status,
        "prompt_hash": diag.prompt_hash(), "runtime_config_hash": "rt",
        "frozen_artifacts_unchanged": {"unchanged": True},
        "lineage": {"checked": 6, "mismatches": [], "identity_ok": True},
        "inference_config_change": {"inference_config_change": "NONE",
                                    "geometry_as_declared": True},
        "requested": {"max_new_tokens": 4096},
        "metrics": {"delivered_frame_count":
                    rc.FRAMES_PER_CHILD if frames is None else frames,
                    "generated_token_count": 4096 if cap else 300,
                    "generation_cap_hit": cap},
        "parsed": {"status": "OK", "events": rows, "collapsed": rows,
                   "language": {"satisfied": True, "violations": []}},
        "representation": {"collapsed_event_count": len(rows),
                           "unique_signature_count": len(unique),
                           "degenerate": degenerate},
        "structure": {"raw_length": 400, "complete_object_count": len(rows),
                      "unique_signature_count": len(unique),
                      "zero_length_interval_count": 0,
                      "max_signature_repeat": 1, "json_parse_ok": True},
    }


def _row(child_id="D0", valid=True, blockers=(), failures=()):
    return {"child_id": child_id, "valid": valid,
            "blockers": list(blockers), "output_failures": list(failures),
            "reasons": list(blockers) + list(failures)}


def _identity(ok=True):
    return [{"overlap_id": row["overlap_id"], "identity_ok": ok}
            for row in rc.overlaps()]


# ── WVR-M01~M09 일정·동결 ──────────────────────────────────────────
def test_wvr_m01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_m02_exactly_three_children_with_frozen_spans():
    rows = rc.children()
    assert len(rows) == 3
    assert tuple((row["child_id"], row["start_sec"], row["end_sec"])
                 for row in rows) == (("D0", 0.0, 12.0), ("D1", 6.0, 18.0),
                                      ("D2", 12.0, 24.0))
    assert rc.CHILD_IDS == ("D0", "D1", "D2")


def test_wvr_m03_six_frames_on_the_exact_half_fps_grid():
    assert rc.frame_times(rc.child_by_id("D0")) == (0.0, 2.0, 4.0, 6.0, 8.0,
                                                    10.0)
    assert rc.frame_times(rc.child_by_id("D1")) == (6.0, 8.0, 10.0, 12.0,
                                                    14.0, 16.0)
    assert rc.frame_times(rc.child_by_id("D2")) == (12.0, 14.0, 16.0, 18.0,
                                                    20.0, 22.0)
    for row in rc.children():
        stamps = rc.frame_times(row)
        assert len(stamps) == rc.FRAMES_PER_CHILD == 6
        assert stamps[-1] < row["end_sec"]


def test_wvr_m04_parent_c0_coverage_has_no_gap():
    row = rc.assert_coverage()
    assert row["covered"] is True and row["gaps"] == []
    assert row["parent"] == [0.0, 24.0] and row["union"] == [0.0, 24.0]


def test_wvr_m05_two_overlaps_with_frozen_spans():
    rows = rc.overlaps()
    assert len(rows) == 2
    assert tuple((row["overlap_id"], row["earlier"], row["later"],
                  row["start_sec"], row["end_sec"]) for row in rows) == (
        ("RR-O1", "D0", "D1", 6.0, 12.0),
        ("RR-O2", "D1", "D2", 12.0, 18.0))


def test_wvr_m06_each_overlap_shares_exactly_three_frames():
    assert rc.shared_times(rc.overlap_by_id("RR-O1")) == (6.0, 8.0, 10.0)
    assert rc.shared_times(rc.overlap_by_id("RR-O2")) == (12.0, 14.0, 16.0)
    for row in rc.overlaps():
        assert len(rc.shared_times(row)) == rc.SHARED_FRAMES_PER_OVERLAP == 3


def test_wvr_m07_child_frames_lie_on_the_parent_and_grandparent_grid():
    parent = set(sd.frame_times(rc.parent_child()))
    grandparent = set(sh.frame_times(rc.grandparent_window()))
    for row in rc.children():
        stamps = set(rc.frame_times(row))
        assert stamps <= parent, "C0 계보 대조가 불가능해진다"
        assert stamps <= grandparent, "W00 계보 대조가 불가능해진다"


def test_wvr_m08_inference_configuration_is_frozen_to_c0():
    assert rc.FROZEN_FROM_C0 == sd.FROZEN_FROM_W00
    assert rc.FROZEN_FROM_C0["prompt_hash"] == diag.prompt_hash()
    assert rc.FROZEN_FROM_C0["max_new_tokens"] == tokens.tokens_for(
        tokens.EVENT_V2) == 4096
    assert rc.FROZEN_FROM_C0["repetition_penalty"] == 1.0
    assert rc.FROZEN_FROM_C0["do_sample"] is False
    assert rc.FROZEN_FROM_C0["sampling_fps"] == rc.SAMPLING_FPS == 0.5
    assert "window_sec" not in rc.FROZEN_FROM_C0
    assert "frames_per_window" not in rc.FROZEN_FROM_C0
    assert rc.DECLARED_GEOMETRY == {"window_sec": 12.0,
                                    "frames_per_window": 6}


def test_wvr_m09_parent_and_grandparent_spans_are_the_failing_windows():
    assert (rc.parent_child()["child_id"], rc.parent_child()["start_sec"],
            rc.parent_child()["end_sec"]) == ("C0", 0.0, 24.0)
    assert (rc.grandparent_window()["window_id"],
            rc.grandparent_window()["start_sec"],
            rc.grandparent_window()["end_sec"]) == ("W00", 0.0, 48.0)
    assert rc.SUBDIVISION_DEPTH == 2


# ── WVR-M10~M11 설정 변경 감지 ─────────────────────────────────────
def test_wvr_m10_config_change_is_none_only_for_the_declared_geometry():
    requested = dict(rc.FROZEN_FROM_C0)
    requested.update(rc.DECLARED_GEOMETRY)
    change = rc.inference_config_change(requested)
    assert change["inference_config_change"] == "NONE"
    assert change["geometry_as_declared"] is True
    assert change["deeper_subdivision_allowed"] is False

    tampered = dict(requested)
    tampered["repetition_penalty"] = 1.1
    detected = rc.inference_config_change(tampered)
    assert detected["inference_config_change"] == "DETECTED"
    assert "repetition_penalty" in detected["differences"]


def test_wvr_m11_twenty_four_second_geometry_is_not_the_declared_change():
    requested = dict(rc.FROZEN_FROM_C0)
    requested.update({"window_sec": 24.0, "frames_per_window": 12})
    change = rc.inference_config_change(requested)
    assert change["inference_config_change"] == "NONE"
    assert change["geometry_as_declared"] is False


# ── WVR-M12~M19 child 기술 검증 ────────────────────────────────────
def test_wvr_m12_a_clean_child_is_valid():
    row = rc.child_validity(_record(), "v")
    assert row["valid"] is True and row["status"] == "WINDOW_VALID"
    assert row["reasons"] == []
    assert row["blockers"] == [] and row["output_failures"] == []


def test_wvr_m13_generation_cap_hit_is_an_output_failure():
    row = rc.child_validity(_record(cap=True), "v")
    assert row["valid"] is False and row["status"] == "WINDOW_INVALID"
    assert "TRUNCATED_AT_CAP" in row["output_failures"]
    assert row["blockers"] == []


def test_wvr_m14_frame_count_mismatch_is_a_blocker():
    row = rc.child_validity(_record(frames=5), "v")
    assert sh.FRAME_COUNT_MISMATCH in row["blockers"]
    assert sh.FRAME_COUNT_MISMATCH not in row["output_failures"]


def test_wvr_m15_grid_mismatch_is_a_blocker():
    record = _record()
    record["frame_times"] = [1.0] + record["frame_times"][1:]
    assert sh.GRID_MISMATCH in rc.child_validity(record, "v")["blockers"]


def test_wvr_m16_missing_raw_is_a_blocker():
    assert sh.RAW_NOT_PERSISTED in rc.child_validity(
        _record(raw=False), "v")["blockers"]


def test_wvr_m17_video_provenance_mismatch_is_a_blocker():
    assert sh.PROVENANCE_MISMATCH in rc.child_validity(
        _record(video="other"), "v")["blockers"]


def test_wvr_m18_representation_degeneracy_is_an_output_failure():
    row = rc.child_validity(_record(degenerate=True), "v")
    assert rc.REPRESENTATION_DEGENERACY in row["output_failures"]
    assert row["blockers"] == []


def test_wvr_m19_runtime_failure_is_a_blocker():
    record = _record(status=rc.RUNTIME_FAILURE, raw=False)
    record.pop("parsed")
    record.pop("representation")
    row = rc.child_validity(record, "v")
    assert rc.RUNTIME_FAILURE in row["blockers"] and row["valid"] is False


# ── WVR-M20~M26 recovery 게이트 ───────────────────────────────────
def test_wvr_m20_three_valid_children_pass():
    gate = rc.recovery_verdict([_row("D0"), _row("D1"), _row("D2")],
                               _identity())
    assert gate["recovery_verdict"] == rc.RECOVERY_PASS == \
        "RECURSIVE_SUBDIVISION_TECHNICAL_PASS"
    assert gate["reason"] == "ALL_CHILDREN_VALID"
    assert gate["valid_child_count"] == 3 and gate["blockers"] == []


def test_wvr_m21_one_output_failure_is_recovery_fail():
    gate = rc.recovery_verdict(
        [_row("D0"), _row("D1", valid=False, failures=("PARSE_FAILURE",)),
         _row("D2")], _identity())
    assert gate["recovery_verdict"] == rc.RECOVERY_FAIL == \
        "RECURSIVE_SUBDIVISION_RECOVERY_FAIL"
    assert gate["invalid_children"] == ["D1"]
    assert gate["packet_generation_allowed"] is False


def test_wvr_m22_a_blocker_outranks_an_output_failure():
    gate = rc.recovery_verdict(
        [_row("D0", valid=False, blockers=(rc.LINEAGE_PIXEL_MISMATCH,)),
         _row("D1", valid=False, failures=("TRUNCATED_AT_CAP",)), _row("D2")],
        _identity())
    assert gate["recovery_verdict"] == rc.INCONCLUSIVE
    assert gate["reason"] == "MEASUREMENT_BLOCKED"
    assert rc.LINEAGE_PIXEL_MISMATCH in gate["blockers"]


def test_wvr_m23_a_missing_child_blocks_the_measurement():
    gate = rc.recovery_verdict([_row("D0"), _row("D1")], _identity())
    assert gate["recovery_verdict"] == rc.INCONCLUSIVE
    assert rc.CHILD_COUNT_MISMATCH in gate["blockers"]


def test_wvr_m24_shared_frame_identity_failure_blocks_the_measurement():
    gate = rc.recovery_verdict([_row("D0"), _row("D1"), _row("D2")],
                               _identity(ok=False))
    assert gate["recovery_verdict"] == rc.INCONCLUSIVE
    assert sh.SHARED_FRAME_IDENTITY_FAILURE in gate["blockers"]


def test_wvr_m25_pass_stops_at_semantic_review_pending():
    gate = rc.recovery_verdict([_row("D0"), _row("D1"), _row("D2")],
                               _identity())
    assert gate["packet_generation_allowed"] is True
    assert gate["event_status"] == ("RECURSIVE_SUBDIVISION_TECHNICAL_PASS + "
                                    "SEMANTIC_REVIEW_PENDING")
    assert gate["deeper_subdivision_allowed"] is False
    assert "6초" in gate["stop_rule"]
    failed = rc.recovery_verdict(
        [_row("D0", valid=False, failures=("NO_EVENT",)), _row("D1"),
         _row("D2")], _identity())
    assert failed["event_status"] == rc.RECOVERY_FAIL


def test_wvr_m26_the_executor_never_fills_a_semantic_verdict():
    for identity in (_identity(), _identity(ok=False)):
        gate = rc.recovery_verdict([_row("D0"), _row("D1"), _row("D2")],
                                   identity)
        assert gate["semantic_verdict"] is None
        assert gate["semantic_verdict_by_executor"] is False
    assert rc.SEMANTIC_VERDICT_BY_EXECUTOR is False
    assert rc.ALLOWED_MAX_CONCLUSION.startswith(
        "The known failing C0 [0,24) window was technically recoverable")
    for phrase in ("12초 semantic stability proven", "12초 production approved",
                   "hierarchical fallback production approved",
                   "0.5fps sufficient", "Event extraction solved",
                   "0초 boundary가 원인이다", "모든 더 짧은 window가 실패한다"):
        assert phrase in rc.FORBIDDEN_CONCLUSIONS


# ── WVR-M27~M31 blinding · identity · 계보 · 깊이 비교 ────────────
def test_wvr_m27_blinding_is_deterministic_and_complementary():
    sha = "4c0f24a0f6bf3a7821d0fdc1776b499b64e32346"
    for overlap_id in ("RR-O1", "RR-O2"):
        earlier = rc.blind_label(overlap_id, "earlier", sha)
        later = rc.blind_label(overlap_id, "later", sha)
        assert {earlier, later} == {"A", "B"}
        assert rc.blind_label(overlap_id, "earlier", sha) == earlier
        assigned = {rc.blind_label(overlap_id, "earlier", "salt%d" % index)
                    for index in range(40)}
        assert assigned == {"A", "B"}, "earlier가 한쪽 라벨에 고정돼 있다"
    with pytest.raises(rc.RecursiveError):
        rc.blind_label("RR-O1", "middle", sha)
    with pytest.raises(rc.RecursiveError):
        rc.blind_label("RR-O1", "earlier", "")


def test_wvr_m28_shared_frame_identity_catches_mismatch_and_absence():
    good = {row["child_id"]: {time: "px%.0f" % time
                              for time in rc.frame_times(row)}
            for row in rc.children()}
    rows = rc.shared_frame_identity(good)
    assert [row["identity_ok"] for row in rows] == [True, True]
    assert [row["shared_observed"] for row in rows] == [3, 3]

    tampered = {key: dict(value) for key, value in good.items()}
    tampered["D1"][8.0] = "different"
    rows = rc.shared_frame_identity(tampered)
    assert rows[0]["identity_ok"] is False
    assert rows[0]["pixel_hash_mismatches"] == [8.0]

    dropped = {key: dict(value) for key, value in good.items()}
    dropped["D2"].pop(14.0)
    rows = rc.shared_frame_identity(dropped)
    assert rows[1]["identity_ok"] is False
    assert rows[1]["missing_times"] == [14.0]
    assert rows[1]["shared_observed"] == 2


def test_wvr_m29_lineage_report_needs_a_reference_and_flags_mismatch():
    table = {"D0": {0.0: "a", 2.0: "b"}}
    assert rc.lineage_report(table, {0.0: "a", 2.0: "b"})["identity_ok"] \
        is True
    bad = rc.lineage_report(table, {0.0: "a", 2.0: "zz"})
    assert bad["identity_ok"] is False
    assert bad["mismatches"][0]["time_sec"] == 2.0
    empty = rc.lineage_report(table, {})
    assert empty["checked"] == 0 and empty["identity_ok"] is False


def test_wvr_m30_frozen_artifacts_detect_change_and_absence():
    good = dict(rc.FROZEN_ARTIFACTS)
    assert rc.frozen_artifacts_unchanged(good)["unchanged"] is True
    changed = dict(good)
    changed["subdiv_v1_C1.json"] = "0" * 64
    row = rc.frozen_artifacts_unchanged(changed)
    assert row["unchanged"] is False
    assert row["changed"] == ["subdiv_v1_C1.json"]
    partial = {key: value for key, value in good.items()
               if key != "subdiv_v1_C2_raw.txt"}
    row = rc.frozen_artifacts_unchanged(partial)
    assert row["unchanged"] is False
    assert row["missing"] == ["subdiv_v1_C2_raw.txt"]
    assert row["c1_c2_rerun_allowed"] is False
    assert row["may_be_revalidated"] is False


def test_wvr_m31_depth_comparison_records_zero_start_without_a_cause_claim():
    rows = [{"child_id": "D0", "start_sec": 0.0},
            {"child_id": "D1", "start_sec": 6.0},
            {"child_id": "D2", "start_sec": 12.0}]
    row = rc.depth_comparison({"label": "W00 [0,48)"}, {"label": "C0 [0,24)"},
                              rows)
    assert row["zero_start_children"] == ["D0"]
    assert row["start_sec_zero_is_not_claimed_as_cause"] is True
    assert row["semantic_superiority_claimed"] is False
    assert row["context_relation"]["executor_judgment"] is False
    assert "equivalent truth로 취급하지 않는다" in \
        row["context_relation"]["equivalence"]


# ── WVR-M32~M35 실행기 계약 ───────────────────────────────────────
def test_wvr_m32_the_runner_persists_raw_before_parsing():
    source = RUNNER.read_text(encoding="utf-8")
    assert source.index('raw_path.write_text(raw_output') < source.index(
        'v2.parse_events(raw_output')
    assert "for attempt" not in source and "while True" not in source
    assert 'max_new_tokens=plan["max_new_tokens"]' in source


def _seed_runs(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    runs.mkdir()
    for name in rc.FROZEN_ARTIFACTS:
        source = RUNS / name
        if not source.is_file():
            pytest.skip("선행 산출물이 없다: %s" % name)
        shutil.copy2(source, runs / name)
    bank = RUNS / runner.BANK_MANIFEST
    if bank.is_file():
        shutil.copy2(bank, runs / runner.BANK_MANIFEST)
    return runs


def test_wvr_m33_preflight_refuses_a_second_run_of_the_same_child(tmp_path):
    runs = _seed_runs(tmp_path)
    plan = runner.preflight("D0", runs)
    assert plan["change"]["inference_config_change"] == "NONE"
    assert plan["change"]["geometry_as_declared"] is True
    assert plan["reference_missing_times"] == []
    assert plan["frozen_artifacts"]["unchanged"] is True
    plan["out_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight("D0", runs)


def test_wvr_m34_preflight_refuses_tampered_ancestors_and_open_flags(
        tmp_path, monkeypatch):
    runs = _seed_runs(tmp_path)
    for name in ("RETRY_ALLOWED", "TOKEN_CAP_INCREASE_APPROVED",
                 "DEEPER_SUBDIVISION_ALLOWED", "C1_C2_RERUN_ALLOWED"):
        monkeypatch.setattr(rc, name, True)
        with pytest.raises(runner.RunError):
            runner.preflight("D1", runs)
        monkeypatch.setattr(rc, name, False)
    (runs / "subdiv_v1_C1_raw.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.preflight("D1", runs)


def test_wvr_m35_preflight_enforces_geometry_and_the_token_cap(tmp_path,
                                                               monkeypatch):
    runs = _seed_runs(tmp_path)
    monkeypatch.setattr(rc, "DECLARED_GEOMETRY",
                        {"window_sec": 24.0, "frames_per_window": 12})
    with pytest.raises(runner.RunError):
        runner.preflight("D2", runs)
    monkeypatch.setattr(rc, "DECLARED_GEOMETRY",
                        {"window_sec": rc.CHILD_SEC,
                         "frames_per_window": rc.FRAMES_PER_CHILD})

    def _refuse(value):
        raise AssertionError("허용되지 않은 token cap: %r" % value)

    monkeypatch.setattr(runner.events, "assert_allowed", _refuse)
    with pytest.raises(AssertionError):
        runner.preflight("D2", runs)


# ── WVR-M36~M38 요약·packet 게이트 ────────────────────────────────
def _write_children(runs: Path, **kwargs) -> None:
    for child_id in rc.CHILD_IDS:
        record = _record(child_id, **kwargs.get(child_id, {}))
        record["validity"] = rc.child_validity(record, "v")
        (runs / ("%s_%s.json" % (rc.ARTIFACT_TAG, child_id))).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")


def test_wvr_m36_the_packet_is_built_only_on_a_pass(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_children(runs)
    built = summary_tool.build(runs, "4c0f24a0")
    gate = built["summary"]["recovery_gate"]
    assert gate["recovery_verdict"] == rc.RECOVERY_PASS
    assert built["summary"]["packet_generated"] is True
    assert "### Arm A" in built["packet"] and "### Arm B" in built["packet"]
    assert "RR-O1" in built["packet"] and "RR-O2" in built["packet"]
    for overlap_id in ("RR-O1", "RR-O2"):
        row = built["mapping"]["mapping"][overlap_id]
        assert {row["A"], row["B"]} == {
            rc.overlap_by_id(overlap_id)["earlier"],
            rc.overlap_by_id(overlap_id)["later"]}
    for leaked in ("D0", "D1", "D2"):
        assert leaked not in built["packet"]
    assert built["summary"]["coverage"]["covered"] is True
    assert gate["semantic_verdict"] is None


def test_wvr_m37_a_failing_child_suppresses_the_packet(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_children(runs, D0={"cap": True})
    built = summary_tool.build(runs, "4c0f24a0")
    gate = built["summary"]["recovery_gate"]
    assert gate["recovery_verdict"] == rc.RECOVERY_FAIL
    assert gate["invalid_children"] == ["D0"]
    assert "packet" not in built and "mapping" not in built
    assert built["summary"]["packet_generated"] is False


def test_wvr_m38_the_summary_derives_structure_from_the_persisted_raw(
        tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    raw = ('{"events": [{"start_sec": 0.0, "end_sec": 0.0, "actor": "person",'
           ' "action": "pouring", "object_or_state": "a bowl"},'
           '{"start_sec": 0.0, "end_sec": 0.0, "actor": "person",'
           ' "action": "pouring", "object_or_state": "a bowl"}')
    for child_id in rc.CHILD_IDS:
        record = _record(child_id)
        record["structure"] = None
        record["raw_path"] = "%s_%s_raw.txt" % (rc.ARTIFACT_TAG, child_id)
        record["validity"] = rc.child_validity(record, "v")
        (runs / record["raw_path"]).write_text(raw, encoding="utf-8")
        (runs / ("%s_%s.json" % (rc.ARTIFACT_TAG, child_id))).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")
    built = summary_tool.build(runs, "4c0f24a0")
    row = built["summary"]["children"][0]
    assert row["structure_source"] == "raw_file_post_hoc"
    assert row["completed_object_count"] == 2
    assert row["zero_duration_count"] == 2
    assert row["positive_duration_count"] == 0
    assert row["json_complete"] is False


def test_wvr_m39_the_frame_packet_gate_requires_a_pass(tmp_path):
    frames_tool = _module(FRAMES_TOOL, "wvr_recur_frames_mod")
    runs = tmp_path / "runs"
    runs.mkdir()
    for verdict in (rc.RECOVERY_FAIL, rc.INCONCLUSIVE):
        (runs / frames_tool.SUMMARY_NAME).write_text(json.dumps(
            {"recovery_gate": {"recovery_verdict": verdict}}),
            encoding="utf-8")
        with pytest.raises(frames_tool.FrameError):
            frames_tool.gate(runs)
    (runs / frames_tool.SUMMARY_NAME).write_text(json.dumps(
        {"recovery_gate": {"recovery_verdict": rc.RECOVERY_PASS}}),
        encoding="utf-8")
    assert frames_tool.gate(runs)["recovery_gate"]["recovery_verdict"] == \
        rc.RECOVERY_PASS
    assert rc.audit_times() == {"RR-O1": [6.0, 8.0, 10.0],
                                "RR-O2": [12.0, 14.0, 16.0]}
    assert rc.FRAME_AUDIT_EXPANSION_ALLOWED is False


# ── WVR-M40~M43 기하 단정 · 경계 ──────────────────────────────────
def test_wvr_m40_geometry_assertions_fire_when_the_structure_breaks():
    with pytest.raises(rc.RecursiveError):
        rc.frame_times({"child_id": "X", "start_sec": 0.0, "end_sec": 6.0})
    rows = [{"child_id": "D0", "start_sec": 0.0, "end_sec": 12.0},
            {"child_id": "D2", "start_sec": 14.0, "end_sec": 24.0}]
    assert rc.coverage(rows)["gaps"] == [[12.0, 14.0]]
    with pytest.raises(rc.RecursiveError):
        rc.assert_coverage(rows)
    with pytest.raises(rc.RecursiveError):
        rc.shared_times({"overlap_id": "X", "earlier": "D0", "later": "D2",
                         "start_sec": 0.0, "end_sec": 24.0})


def test_wvr_m41_prior_results_and_artifacts_are_untouched():
    for name, expected in rc.FROZEN_ARTIFACTS.items():
        path = RUNS / name
        if not path.is_file():
            pytest.skip("선행 산출물이 없다: %s" % name)
        assert _sha256_file(path) == expected, "선행 산출물이 바뀌었다: %s" % name
    if SUBMISSION.is_file():
        assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert rc.PRIOR_STATE["WVR_W00_SUBDIVISION_RECOVERY_V1"] == \
        "CLOSED / SUBDIVISION_RECOVERY_FAIL"
    assert rc.PRIOR_STATE["WVR_W00_DEGENERACY_REPRO_V1"] == \
        "CLOSED / REPRODUCIBLE"
    assert rc.PRIOR_STATE["C0"].startswith("WINDOW_INVALID")
    assert rc.PRIOR_STATE["C1"].startswith("WINDOW_VALID")
    assert rc.PRIOR_STATE["C2"].startswith("WINDOW_VALID")


def test_wvr_m42_every_expansion_flag_is_off():
    for name in ("RETRY_ALLOWED", "RAW_SALVAGE_ALLOWED",
                 "TOKEN_CAP_INCREASE_APPROVED", "DEEPER_SUBDIVISION_ALLOWED",
                 "C1_C2_RERUN_ALLOWED", "PARENT_MAY_BE_REVALIDATED",
                 "SHADOW_V1_RETROACTIVE_REPAIR_ALLOWED",
                 "MAPPING_REVEAL_ALLOWED", "SEMANTIC_VERDICT_BY_EXECUTOR",
                 "PRODUCTION_PROMOTION_ALLOWED",
                 "FALLBACK_POLICY_ADOPTION_ALLOWED",
                 "EVENT_MAP_PRODUCTION_APPROVED",
                 "FRAME_AUDIT_EXPANSION_ALLOWED"):
        assert getattr(rc, name) is False, "%s가 열려 있다" % name


def test_wvr_m43_the_batch_runs_the_validator_and_never_retries():
    source = BATCH.read_text(encoding="utf-8")
    assert "wvr_recur_validate.py" in source
    assert source.index("wvr_recur_validate.py") < source.index(
        "wvr_recur_run.py")
    assert "for child in D0 D1 D2" in source
    assert "재시도하지 않는다" in source
    assert "for attempt" not in source
    assert source.count("for ") == 1, "child 루프 외의 반복이 들어왔다"
    assert VALIDATOR.is_file() and SUMMARY_TOOL.is_file()
    assert rc.RECOVERY_VERDICTS == ("RECURSIVE_SUBDIVISION_TECHNICAL_PASS",
                                    "RECURSIVE_SUBDIVISION_RECOVERY_FAIL",
                                    "INCONCLUSIVE")


def test_wvr_m44_parent_span_is_asserted_against_the_frozen_range(
        monkeypatch):
    """parent 범위 단정은 상수가 흔들릴 때만 발화한다 — 그 경로를 직접 확인한다."""
    monkeypatch.setattr(rc, "PARENT_END_SEC", 30.0)
    with pytest.raises(rc.RecursiveError):
        rc.parent_child()
    monkeypatch.setattr(rc, "PARENT_END_SEC", 24.0)
    monkeypatch.setattr(rc, "PARENT_START_SEC", 6.0)
    with pytest.raises(rc.RecursiveError):
        rc.parent_child()
    monkeypatch.setattr(rc, "PARENT_START_SEC", 0.0)
    assert rc.parent_child()["child_id"] == "C0"
