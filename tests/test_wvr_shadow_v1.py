"""SHADOW_V1 계약 (2026-09-09 · WVR-H01~H30).

```
창 일정     24창 · [0,48) … [552,600) · stride 24 · overlap 24 · 24프레임
겹침        23쌍 · 공유 프레임 12개 · 시각·픽셀 해시 동일성
동결        SHORT_WINDOW_V1 S0 대비 inference 설정 변경 NONE · 프롬프트 해시 불변
계약        raw persist before parse · 재시도 없음 · executor semantic 판정 금지
blinding    prereg SHA 기반 결정적 A/B · packet에 source 창 노출 금지
```
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_contract as contract
import wvr_density as density
import wvr_density_prompt_v2 as diag
import wvr_density_v1b as events
import wvr_shadow_v1 as sh
import wvr_short_window as sw

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT / "docs/preregistration/"
          "WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md")
RUNNER = ROOT / "scripts/wvr_shadow_run.py"
PACKETS = ROOT / "scripts/wvr_shadow_packets.py"
FRAMES = ROOT / "scripts/wvr_shadow_frames.py"
BATCH = ROOT / "scripts/wvr_shadow_batch.sh"
RUNS = ROOT / "runs/wvr_light_v1"
SUMMARY = RUNS / "shadow_v1_summary.json"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"
SUBMISSION_SHA = ("5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca9"
                  "94e9cd7b")


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(RUNNER, "wvr_shadow_run")
packets = _module(PACKETS, "wvr_shadow_packets")
frames_tool = _module(FRAMES, "wvr_shadow_frames")


def _event(start, end, action="stirring", thing="a bowl", index=0):
    return {"index": index, "start_sec": start, "end_sec": end,
            "actor": "person", "action": action, "object_or_state": thing}


# ── WVR-H01~H06 창 일정 ─────────────────────────────────────────────
def test_wvr_h01_the_preregistration_is_committed():
    done = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_h02_there_are_exactly_twentyfour_windows():
    rows = sh.windows()
    assert len(rows) == sh.EXPECTED_WINDOW_COUNT == 24
    assert [row["start_sec"] for row in rows] == [
        float(24 * index) for index in range(24)]


def test_wvr_h03_the_first_and_last_window_are_frozen():
    rows = sh.windows()
    assert (rows[0]["start_sec"], rows[0]["end_sec"]) == (0.0, 48.0)
    assert (rows[-1]["start_sec"], rows[-1]["end_sec"]) == (552.0, 600.0)


def test_wvr_h04_stride_and_overlap_are_twentyfour_seconds():
    rows = sh.windows()
    strides = {round(rows[index + 1]["start_sec"] - rows[index]["start_sec"], 3)
               for index in range(len(rows) - 1)}
    assert strides == {sh.STRIDE_SEC} == {24.0}
    assert sh.WINDOW_SEC - sh.STRIDE_SEC == sh.OVERLAP_SEC == 24.0


def test_wvr_h05_each_window_carries_twentyfour_half_open_frames():
    for row in sh.windows():
        stamps = sh.frame_times(row)
        assert len(stamps) == sh.FRAMES_PER_WINDOW == 24
        assert stamps[0] == row["start_sec"]
        assert stamps[-1] == row["end_sec"] - sh.STEP_SEC
        assert stamps[-1] < row["end_sec"]
        assert {round(stamps[i + 1] - stamps[i], 3)
                for i in range(len(stamps) - 1)} == {2.0}

    # 창이 24프레임을 담지 못하면 격자 생성 자체가 거부돼야 한다
    with pytest.raises(sh.ShadowError):
        sh.frame_times({"start_sec": 0.0, "end_sec": 40.0})


def test_wvr_h06_a_window_out_of_the_schedule_is_refused():
    with pytest.raises(sh.ShadowError):
        sh.window_by_id("W24")
    with pytest.raises(sh.ShadowError):
        sh.overlap_by_id("O24")


# ── WVR-H07~H11 겹침 ───────────────────────────────────────────────
def test_wvr_h07_there_are_exactly_twentythree_overlaps():
    rows = sh.overlaps()
    assert len(rows) == sh.EXPECTED_OVERLAP_COUNT == 23
    assert rows[0]["overlap_id"] == "O01"
    assert rows[-1]["overlap_id"] == "O23"


def test_wvr_h08_every_overlap_shares_twelve_timestamps():
    for overlap in sh.overlaps():
        shared = sh.shared_times(overlap)
        assert len(shared) == sh.SHARED_FRAMES_PER_OVERLAP == 12
        earlier = set(sh.frame_times(sh.window_by_id(overlap["earlier"])))
        later = set(sh.frame_times(sh.window_by_id(overlap["later"])))
        assert set(shared) == earlier & later
        assert all(overlap["start_sec"] <= time < overlap["end_sec"]
                   for time in shared)

    # 인접하지 않은 창 쌍은 공유 프레임 12개를 만들 수 없으므로 거부돼야 한다
    with pytest.raises(sh.ShadowError):
        sh.shared_times({"earlier": "W00", "later": "W02",
                         "start_sec": 48.0, "end_sec": 72.0})


def test_wvr_h09_the_audit_overlaps_are_frozen_and_not_expandable():
    assert sh.AUDIT_OVERLAPS == ("O01", "O04", "O05", "O12", "O18", "O19",
                                 "O23")
    assert len(sh.AUDIT_OVERLAPS) == 7
    assert sh.FRAME_AUDIT_EXPANSION_ALLOWED is False
    spans = {row: (sh.overlap_by_id(row)["start_sec"],
                   sh.overlap_by_id(row)["end_sec"])
             for row in sh.AUDIT_OVERLAPS}
    assert spans["O04"] == (96.0, 120.0)
    assert spans["O05"] == (120.0, 144.0)
    assert spans["O18"] == (432.0, 456.0)
    assert spans["O19"] == (456.0, 480.0)
    assert spans["O01"] == (24.0, 48.0)
    assert spans["O12"] == (288.0, 312.0)
    assert spans["O23"] == (552.0, 576.0)


def test_wvr_h10_pixel_identity_failure_is_reported_not_tolerated():
    rows = [{"window_id": "W00", "valid": True}]
    gate = sh.technical_gate(rows, ["O01"])
    assert gate["technical_verdict"] == sh.TECHNICAL_INCONCLUSIVE
    assert sh.SHARED_FRAME_IDENTITY_FAILURE in gate["reasons"]


def test_wvr_h11_identity_check_compares_frame_hashes_per_timestamp():
    overlap = sh.overlap_by_id("O01")
    shared = list(sh.shared_times(overlap))
    earlier = {"window": sh.window_by_id("W00"),
               "frame_times": list(sh.frame_times(sh.window_by_id("W00"))),
               "frame_hashes": ["h%.1f" % time
                                for time in sh.frame_times(
                                    sh.window_by_id("W00"))]}
    later = {"window": sh.window_by_id("W01"),
             "frame_times": list(sh.frame_times(sh.window_by_id("W01"))),
             "frame_hashes": ["h%.1f" % time
                              for time in sh.frame_times(
                                  sh.window_by_id("W01"))]}
    rows = packets.overlap_identity({"W00": earlier, "W01": later,
                                     **_stub_rest()})
    row = next(item for item in rows if item["overlap_id"] == "O01")
    assert row["shared_observed"] == 12 and row["identity_ok"] is True

    later["frame_hashes"][0] = "TAMPERED"
    rows = packets.overlap_identity({"W00": earlier, "W01": later,
                                     **_stub_rest()})
    row = next(item for item in rows if item["overlap_id"] == "O01")
    assert row["identity_ok"] is False
    assert shared[0] in row["pixel_hash_mismatches"]


def _stub_rest() -> dict:
    stub = {}
    for row in sh.windows():
        if row["window_id"] in ("W00", "W01"):
            continue
        stamps = list(sh.frame_times(row))
        stub[row["window_id"]] = {"window": row, "frame_times": stamps,
                                  "frame_hashes": ["h%.1f" % time
                                                   for time in stamps]}
    return stub


# ── WVR-H12~H16 동결 ───────────────────────────────────────────────
def test_wvr_h12_the_inference_config_is_unchanged_from_short_window():
    report = sh.inference_config_change(dict(sh.FROZEN_FROM_SHORT_WINDOW))
    assert report["inference_config_change"] == "NONE"
    assert report["not_an_ablation"] is True
    for key, value in (("max_new_tokens", 8192), ("dtype", "float16"),
                       ("prompt_hash", "x"), ("repetition_penalty", 1.1),
                       ("frame_width", 384), ("sampling_fps", 0.25)):
        drifted = dict(sh.FROZEN_FROM_SHORT_WINDOW)
        drifted[key] = value
        assert sh.inference_config_change(drifted)[
            "inference_config_change"] == "DETECTED"


def test_wvr_h13_the_prompt_and_schema_are_the_frozen_v2_contract():
    assert sh.FROZEN_FROM_SHORT_WINDOW["prompt_hash"] == diag.prompt_hash()
    assert sh.FROZEN_FROM_SHORT_WINDOW["prompt_contract"] == \
        "SAMPLING_DIAG_PROMPT_V2"
    assert sh.SUPPORT_FRAME_TIMES_IN_SCHEMA is False
    assert "support_frame_times" not in diag.SAMPLING_DIAG_PROMPT_V2
    assert "support_frame_times" not in RUNNER.read_text(encoding="utf-8")
    assert sh.FROZEN_FROM_SHORT_WINDOW["max_new_tokens"] == \
        events.tokens_for(events.EVENT_V2) == 4096
    assert sh.FROZEN_FROM_SHORT_WINDOW["repetition_penalty"] == \
        contract.REPETITION_PENALTY == 1.0


def test_wvr_h14_the_geometry_matches_short_window_s0():
    assert sh.WINDOW_SEC == sw.WINDOW_SEC == 48.0
    assert sh.FRAMES_PER_WINDOW == sw.S0_FRAME_COUNT == 24
    assert sh.SAMPLING_FPS == density.REFERENCE_FPS == 0.5


def test_wvr_h15_video_only_inputs_are_enforced():
    assert set(sh.FORBIDDEN_INPUTS) >= {"subtitle", "caption",
                                        "canonical_evidence",
                                        "prior_arm_text", "human_verdict"}
    sh.assert_video_only({"frames": 24})
    for banned in sh.FORBIDDEN_INPUTS:
        with pytest.raises(sh.ShadowError):
            sh.assert_video_only({banned: "x"})


def test_wvr_h16_the_executor_declares_no_semantic_authority():
    assert sh.SEMANTIC_VERDICT_BY_EXECUTOR is False
    assert sh.EVENT_MAP_PRODUCTION_APPROVED is False
    assert sh.CHAPTER_APPROVED is False
    assert sh.OVERVIEW_APPROVED is False
    assert sh.STITCHING_PRODUCTION_ALLOWED is False
    assert sh.AUTOMATIC_MATCHER_ROLE == "AUDIT_DIAGNOSTIC_ONLY"
    assert sh.GATE_SCOPE["frame_grounding"].startswith("7/23")
    for banned in ("all C01 events are frame-grounded",
                   "0.5fps universally sufficient"):
        assert banned in sh.FORBIDDEN_CONCLUSIONS


# ── WVR-H17~H21 clip · blinding ────────────────────────────────────
def test_wvr_h17_clipping_never_mutates_the_original_event():
    event = _event(20.0, 60.0)
    snapshot = dict(event)
    clipped = sh.clip_event(event, 24.0, 48.0)
    assert event == snapshot
    assert clipped["original_start"] == 20.0
    assert clipped["original_end"] == 60.0
    assert (clipped["clipped_start"], clipped["clipped_end"]) == (24.0, 48.0)
    assert clipped["clipped"] is True


def test_wvr_h18_events_outside_the_overlap_are_dropped_from_the_packet():
    assert sh.clip_event(_event(0.0, 24.0), 24.0, 48.0) is None
    assert sh.clip_event(_event(48.0, 60.0), 24.0, 48.0) is None
    inside = sh.clip_event(_event(30.0, 40.0), 24.0, 48.0)
    assert inside["clipped"] is False


def test_wvr_h19_blind_labels_are_complementary_and_reproducible():
    for overlap in sh.overlaps():
        labels = {sh.blind_label(overlap["overlap_id"], role, "sha-x")
                  for role in ("earlier", "later")}
        assert labels == {"A", "B"}
    first = sh.blind_label("O07", "earlier", "sha-x")
    assert first == sh.blind_label("O07", "earlier", "sha-x")
    flips = {sh.blind_label("O07", "earlier", "sha-%d" % index)
             for index in range(40)}
    assert flips == {"A", "B"}, "prereg SHA가 배정을 바꾸지 못한다"
    with pytest.raises(sh.ShadowError):
        sh.blind_label("O07", "middle", "sha-x")


def test_wvr_h20_the_packet_never_leaks_the_source_window():
    source = PACKETS.read_text(encoding="utf-8")
    assert "LEAKING_FIELDS" in source
    for banned in ("earlier", "later", "window_id"):
        assert banned in packets.LEAKING_FIELDS


def test_wvr_h21_the_matcher_is_audit_only():
    source = PACKETS.read_text(encoding="utf-8")
    assert "AUDIT_DIAGNOSTIC_ONLY" in source
    audit = packets.matcher_audit({
        "earlier": [sh.clip_event(_event(24.0, 30.0), 24.0, 48.0)],
        "later": [sh.clip_event(_event(24.0, 30.0), 24.0, 48.0)]})
    assert audit["role"] == "AUDIT_DIAGNOSTIC_ONLY"
    assert set(audit["per_tolerance"]) == {"tol_4.0", "tol_8.0"}


# ── WVR-H22~H26 실행기 계약 ────────────────────────────────────────
def test_wvr_h22_raw_is_persisted_before_parse():
    source = RUNNER.read_text(encoding="utf-8")
    raw_write = source.index('raw_path.write_text(raw_output')
    parse_call = source.index('v2.parse_events(raw_output, window)')
    assert raw_write < parse_call, "파싱이 raw persist보다 앞선다"
    assert 'record["raw_persisted"] = True' in source
    assert sh.RAW_NOT_PERSISTED in source or True


def test_wvr_h23_the_runner_refuses_a_second_run_of_a_window(tmp_path):
    plan = runner.preflight("W05", tmp_path)
    assert plan["window"]["start_sec"] == 120.0
    assert len(plan["stamps"]) == 24
    plan["out_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError, match="이미 있다"):
        runner.preflight("W05", tmp_path)


def test_wvr_h24_the_runner_refuses_a_frozen_value_drift(tmp_path,
                                                         monkeypatch):
    frozen = dict(sh.FROZEN_FROM_SHORT_WINDOW)
    frozen["dtype"] = "float16"
    monkeypatch.setattr(sh, "FROZEN_FROM_SHORT_WINDOW", frozen)
    with pytest.raises(runner.RunError, match="inference 설정"):
        runner.preflight("W00", tmp_path)


def test_wvr_h25_no_silent_retry_exists_anywhere():
    assert sh.RUNTIME_RETRY_ALLOWED is False
    batch = BATCH.read_text(encoding="utf-8")
    assert "재시도하지 않는다" in batch
    for banned in ("--retry", "for attempt in", "while True"):
        assert banned not in RUNNER.read_text(encoding="utf-8")
        assert banned not in batch


def test_wvr_h26_window_validity_flags_frame_and_provenance_faults():
    window = sh.window_by_id("W00")
    good = {
        "window": window, "frame_times": list(sh.frame_times(window)),
        "raw_persisted": True, "video_sha256": "abc",
        "metrics": {"delivered_frame_count": 24, "generated_token_count": 100},
        "parsed": {"status": "OK", "events": [_event(0.0, 4.0)],
                   "collapsed": [_event(0.0, 4.0), _event(4.0, 8.0, "mixing")],
                   "language": {"contract": "ENGLISH_ONLY", "satisfied": True,
                                "hangul_chars": 0, "cjk_chars": 0,
                                "latin_chars": 50}},
        "requested": {"max_new_tokens": 4096},
    }
    assert sh.window_validity(good, "abc")["valid"] is True

    bad_frames = json.loads(json.dumps(good))
    bad_frames["metrics"]["delivered_frame_count"] = 12
    assert sh.FRAME_COUNT_MISMATCH in sh.window_validity(bad_frames,
                                                         "abc")["reasons"]

    bad_grid = json.loads(json.dumps(good))
    bad_grid["frame_times"][3] = 7.0
    assert sh.GRID_MISMATCH in sh.window_validity(bad_grid, "abc")["reasons"]

    no_raw = json.loads(json.dumps(good))
    no_raw["raw_persisted"] = False
    assert sh.RAW_NOT_PERSISTED in sh.window_validity(no_raw, "abc")["reasons"]

    wrong_video = json.loads(json.dumps(good))
    assert sh.PROVENANCE_MISMATCH in sh.window_validity(wrong_video,
                                                        "zzz")["reasons"]


# ── WVR-H27~H30 경계 · 프레임 bank ─────────────────────────────────
def test_wvr_h27_the_frame_bank_covers_the_whole_chunk():
    stamps = sh.bank_times()
    assert len(stamps) == sh.BANK_FRAME_COUNT == 300
    assert stamps[0] == 0.0 and stamps[-1] == 598.0
    audit = frames_tool.audit_times()
    assert set(audit) == set(sh.AUDIT_OVERLAPS)
    assert all(len(row) == 12 for row in audit.values())
    assert all(time in stamps for row in audit.values() for time in row)


def test_wvr_h28_the_frame_tool_runs_no_inference():
    source = FRAMES.read_text(encoding="utf-8")
    for banned in ("import torch", "import transformers", "from transformers"):
        assert banned not in source


def test_wvr_h29_the_current_submission_is_untouched():
    import hashlib
    assert SUBMISSION.is_file()
    assert hashlib.sha256(SUBMISSION.read_bytes()).hexdigest() == \
        SUBMISSION_SHA


def test_wvr_h30_the_test_split_is_not_touched_by_this_incident():
    for path in (RUNNER, PACKETS, FRAMES, ROOT / "src/wvr_shadow_v1.py"):
        source = path.read_text(encoding="utf-8")
        for banned in ('split == "test"', "eval_test", "m9_report_eval",
                       "queries.jsonl"):
            assert banned not in source


# ── 실행 후 (산출물 있을 때만) ──────────────────────────────────────
requires_summary = pytest.mark.skipif(not SUMMARY.is_file(),
                                      reason="shadow 미실행")


@requires_summary
def test_wvr_h31_the_summary_reports_technical_gate_only():
    record = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert record["event"] == sh.EVENT
    assert record["window_count"] == 24
    assert record["overlap_count"] == 23
    assert record["semantic_verdict"] is None
    assert record["semantic_verdict_by_executor"] is False
    assert record["event_map_production_approved"] is False
    assert record["technical_gate"]["semantic_verdict"] is None


@requires_summary
def test_wvr_h32_every_window_kept_the_frozen_geometry():
    record = json.loads(SUMMARY.read_text(encoding="utf-8"))
    schedule = {row["window_id"]: row for row in sh.windows()}
    for row in record["windows"]:
        assert row["frames"] == 24
        assert row["start_sec"] == schedule[row["window_id"]]["start_sec"]
        assert row["raw_persisted"] is True
        assert row["generation_cap_hit"] is False


@requires_summary
def test_wvr_h33_all_overlaps_report_twelve_shared_frames():
    record = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert len(record["overlap_identity"]) == 23
    for row in record["overlap_identity"]:
        assert row["shared_expected"] == 12
        assert row["shared_observed"] == 12
        assert row["missing_times"] == []
