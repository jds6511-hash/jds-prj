"""SHORT_WINDOW_V1 계약 (2026-09-09 · WVR-S01~S28).

```
유일 변경   context 180초 → 48초. V2 동결값이 하나라도 달라지면 RED
창 파생     미해결 충돌 → gap ≤ 8초 cluster → 중심 48초 → 4초 grid floor
            사람이 창을 고를 여지가 없다
판정        자동 matcher는 audit diagnostic. primary는 blinded 사람 판정
blinding    packet에 density를 노출하는 필드가 들어가면 RED
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
import wvr_short_window as sw

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md"
RUNNER = ROOT / "scripts/wvr_short_window_run.py"
PACKET = ROOT / "scripts/wvr_short_window_packet.py"
RUNS = ROOT / "runs/wvr_light_v1"
RESOLUTION = RUNS / "wvr_evidence_resolution_v1.json"
EVIDENCE = RUNS / sw.SOURCE_ARTIFACT


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


packet = _module(PACKET, "wvr_short_window_packet")
runner = _module(RUNNER, "wvr_short_window_run")


def _conflict(pair, span, resolution="NEITHER_RESOLVED",
              source=("REVIEWER_NAMED",)):
    return {"source": list(source), "resolution": resolution,
            "evidence_window": list(span)}


def _resolution(rows):
    pairs = {}
    for pair, span, *rest in rows:
        kind = rest[0] if rest else "NEITHER_RESOLVED"
        source = rest[1] if len(rest) > 1 else ("REVIEWER_NAMED",)
        pairs.setdefault(pair, {"conflicts": []})["conflicts"].append(
            _conflict(pair, span, kind, source))
    return {"pairs": pairs}


FROZEN_ROWS = [("D1", (380.0, 390.0)), ("D1", (420.0, 450.0)),
               ("D1", (450.0, 460.0)), ("D2", (104.0, 112.0)),
               ("D2", (112.0, 120.0)), ("D2", (128.0, 136.0)),
               ("D2", (136.0, 144.0)), ("D2", (144.0, 152.0))]


# ── WVR-S01~S05 동결 ────────────────────────────────────────────────
def test_wvr_s01_the_preregistration_is_committed():
    done = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_s02_only_the_context_length_changed():
    assert sw.WINDOW_SEC == 48.0
    assert density.WINDOW_SEC == 180.0
    assert sw.FROZEN_FROM_V2["prompt_hash"] == diag.prompt_hash()
    assert sw.FROZEN_FROM_V2["max_new_tokens"] == events.tokens_for(
        events.EVENT_V2) == 4096
    assert sw.FROZEN_FROM_V2["output_language"] == "en"
    assert sw.FROZEN_FROM_V2["repetition_penalty"] == \
        contract.REPETITION_PENALTY == 1.0
    assert sw.FROZEN_FROM_V2["model_revision"] == contract.MODEL_REVISION
    assert sw.FROZEN_FROM_V2["quantization"] is None


def test_wvr_s03_single_change_detects_a_frozen_value_drift():
    good = dict(sw.FROZEN_FROM_V2)
    assert sw.single_change(good)["single_change"] is True
    for key, value in (("max_new_tokens", 8192), ("dtype", "float16"),
                       ("repetition_penalty", 1.1), ("prompt_hash", "x"),
                       ("frame_width", 384), ("do_sample", True)):
        drifted = dict(sw.FROZEN_FROM_V2)
        drifted[key] = value
        report = sw.single_change(drifted)
        assert report["single_change"] is False
        assert key in report["differences"]


def test_wvr_s04_the_probe_claims_nothing_beyond_its_scope():
    assert sw.SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED is False
    assert sw.EVENT_EXTRACTION_APPROVED is False
    assert sw.FRAME_ADJUDICATION_APPROVED is False
    assert sw.AUTOMATIC_MATCHER_ROLE == "AUDIT_DIAGNOSTIC_ONLY"
    assert "universally" in sw.FORBIDDEN_CONCLUSION
    assert PREREG.read_text(encoding="utf-8").count(
        sw.FORBIDDEN_CONCLUSION) >= 1


def test_wvr_s05_the_inference_budget_is_six():
    assert sw.TOTAL_INFERENCES == len(sw.EXPECTED_WINDOWS) * len(sw.ARMS) == 6


# ── WVR-S06~S12 창 파생 ─────────────────────────────────────────────
def test_wvr_s06_only_unresolved_reviewer_conflicts_are_inputs():
    rows = FROZEN_ROWS + [("D1", (300.0, 310.0), "ARM_ONLY_SUPPORTED"),
                          ("D3", (200.0, 208.0), "NEITHER_RESOLVED",
                           ("DETERMINISTIC_DOUBLY_DISJOINT",))]
    picked = sw.unresolved_conflicts(_resolution(rows))
    assert set(picked) == {"D1", "D2"}
    assert (300.0, 310.0) not in picked["D1"]
    assert "D3" not in picked


def test_wvr_s07_clustering_merges_only_within_the_gap():
    assert sw.CONFLICT_GAP_SEC == 8.0
    assert sw.cluster([(0.0, 10.0), (18.0, 20.0)]) == [(0.0, 20.0)]
    assert sw.cluster([(0.0, 10.0), (18.1, 20.0)]) == [(0.0, 10.0),
                                                       (18.1, 20.0)]


def test_wvr_s08_the_frozen_clusters_are_reproduced():
    clusters = sw.derive_clusters(_resolution(FROZEN_ROWS))
    observed = tuple((row["cluster_id"], row["pair"], row["start_sec"],
                      row["end_sec"]) for row in clusters)
    assert observed == sw.EXPECTED_CLUSTERS
    assert max(row["length_sec"] for row in clusters) == sw.WINDOW_SEC


def test_wvr_s09_the_frozen_windows_are_reproduced():
    windows = sw.derive_windows(_resolution(FROZEN_ROWS))
    observed = tuple((row["window_id"], row["cluster_id"], row["start_sec"],
                      row["end_sec"]) for row in windows)
    assert observed == sw.EXPECTED_WINDOWS
    sw.assert_expected(windows)


def test_wvr_s10_every_window_is_grid_aligned_and_covers_its_cluster():
    for row in sw.derive_windows(_resolution(FROZEN_ROWS)):
        assert row["start_sec"] % sw.GRID_SEC == 0.0
        assert row["end_sec"] - row["start_sec"] == sw.WINDOW_SEC
        assert row["start_sec"] <= row["cluster"][0]
        assert row["end_sec"] >= row["cluster"][1]


def test_wvr_s11_a_cluster_longer_than_the_window_is_an_error():
    with pytest.raises(sw.ShortWindowError, match="창보다 길다"):
        sw.window_for_cluster({"cluster_id": "CX", "start_sec": 0.0,
                               "end_sec": 60.0})


def test_wvr_s12_a_derived_window_that_differs_from_the_prereg_is_refused():
    shifted = sw.derive_windows(_resolution(
        [("D1", (388.0, 398.0))] + FROZEN_ROWS[1:]))
    with pytest.raises(sw.ShortWindowError):
        sw.assert_expected(shifted)


# ── WVR-S13~S17 프레임 ──────────────────────────────────────────────
def test_wvr_s13_frame_counts_are_twentyfour_and_twelve():
    window = {"start_sec": 104.0, "end_sec": 152.0}
    assert len(sw.arm_timestamps(window, sw.ARM_S0)) == 24
    assert len(sw.arm_timestamps(window, sw.ARM_S1)) == 12


def test_wvr_s14_the_reduced_arm_is_an_exact_subset():
    for row in sw.derive_windows(_resolution(FROZEN_ROWS)):
        reference = sw.arm_timestamps(row, sw.ARM_S0)
        keep = sw.arm_timestamps(row, sw.ARM_S1)
        assert set(keep) <= set(reference)
        density.assert_contained(reference, keep)
        assert keep == reference[::2]


def test_wvr_s15_frames_stay_inside_the_half_open_window():
    for row in sw.derive_windows(_resolution(FROZEN_ROWS)):
        for arm in sw.ARMS:
            stamps = sw.arm_timestamps(row, arm)
            assert stamps[0] == row["start_sec"]
            assert stamps[-1] < row["end_sec"]


def test_wvr_s16_the_sampling_rates_come_from_the_v2_contract():
    assert sw.FROZEN_FROM_V2["reference_fps"] == density.REFERENCE_FPS == 0.5
    assert sw.FROZEN_FROM_V2["density_fps"] == density.DENSITY_FPS == 0.25
    assert sw.FROZEN_FROM_V2["keep_stride"] == density.KEEP_STRIDE == 2


def test_wvr_s17_an_unknown_arm_is_refused():
    with pytest.raises(sw.ShortWindowError):
        sw.arm_timestamps({"start_sec": 0.0, "end_sec": 48.0}, "S2")


# ── WVR-S18~S22 판정 ───────────────────────────────────────────────
def test_wvr_s18_the_verdict_vocabulary_is_exactly_four():
    assert sw.VERDICTS == ("STABLE", "GRANULARITY_SHIFT",
                           "MATERIAL_DIVERGENCE", "UNRESOLVED")
    assert sw.PASSING_VERDICTS == ("STABLE", "GRANULARITY_SHIFT")
    assert sw.window_pass("STABLE") and sw.window_pass("GRANULARITY_SHIFT")
    assert not sw.window_pass("MATERIAL_DIVERGENCE")
    assert not sw.window_pass("UNRESOLVED")
    with pytest.raises(sw.ShortWindowError):
        sw.window_pass("PASS")


def test_wvr_s19_material_divergence_anywhere_is_a_hold():
    assert sw.probe_verdict(["STABLE", "MATERIAL_DIVERGENCE",
                             "GRANULARITY_SHIFT"]) == sw.PROBE_HOLD


def test_wvr_s20_unresolved_anywhere_is_inconclusive():
    assert sw.probe_verdict(["STABLE", "UNRESOLVED", "STABLE"]) == \
        sw.PROBE_INCONCLUSIVE


def test_wvr_s21_a_technical_failure_outranks_the_content_verdicts():
    assert sw.probe_verdict(["STABLE", "STABLE", "STABLE"],
                            [{"window_id": "P1", "label": "A",
                              "reasons": ["TRUNCATED_AT_CAP"]}]) == \
        sw.PROBE_INCONCLUSIVE
    assert sw.probe_verdict(["STABLE", "MATERIAL_DIVERGENCE", "STABLE"],
                            [{"window_id": "P1", "label": "A",
                              "reasons": ["LANGUAGE_CONTRACT_FAILURE"]}]) == \
        sw.PROBE_INCONCLUSIVE


def test_wvr_s22_all_three_windows_must_be_judged():
    assert sw.probe_verdict(["STABLE", "STABLE", "GRANULARITY_SHIFT"]) == \
        sw.PROBE_PASS
    with pytest.raises(sw.ShortWindowError):
        sw.probe_verdict(["STABLE", "STABLE"])
    with pytest.raises(sw.ShortWindowError):
        sw.probe_verdict(["STABLE", "STABLE", "PASS"])


# ── WVR-S23~S28 blinding · 실행기 ──────────────────────────────────
def test_wvr_s23_blind_labels_are_complementary_and_salt_dependent():
    labels = {sw.blind_label("P1", arm, "salt-x") for arm in sw.ARMS}
    assert labels == {"A", "B"}
    flips = {sw.blind_label("P1", sw.ARM_S0, "salt-%d" % index)
             for index in range(40)}
    assert flips == {"A", "B"}, "salt가 배정을 바꾸지 못한다"


def test_wvr_s24_the_packet_never_carries_density_revealing_fields():
    source = PACKET.read_text(encoding="utf-8")
    assert "LEAKING_FIELDS" in source
    for banned in ("delivered_frame_count", "input_token_count",
                   "generated_token_count"):
        assert banned in packet.LEAKING_FIELDS
    built = _built_packet()
    text = built["packet"]
    for banned in ("S0", "S1", "0.5fps 24", "24프레임", "12프레임",
                   "delivered_frame_count", "input_token_count"):
        assert banned not in text, "packet이 density를 노출한다: %s" % banned
    assert "Arm A" in text and "Arm B" in text
    assert built["blind_map"]["salt"] not in text


def test_wvr_s25_the_blind_map_is_written_apart_from_the_packet():
    assert packet.BLIND_MAP_NAME != packet.PACKET_NAME
    built = _built_packet()
    for window_id, mapping in built["blind_map"]["mapping"].items():
        assert set(mapping) == {"A", "B"}
        assert set(mapping.values()) == set(sw.ARMS)
    assert built["audit"]["role"] == sw.AUTOMATIC_MATCHER_ROLE


def _runner_dir(tmp_path):
    (tmp_path / sw.SOURCE_ARTIFACT).write_text(
        EVIDENCE.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_wvr_s26_the_runner_refuses_a_frozen_value_drift(tmp_path,
                                                         monkeypatch):
    out_dir = _runner_dir(tmp_path)
    plan = runner.preflight("P1", sw.ARM_S0, out_dir)
    assert len(plan["stamps"]) == 24
    assert plan["max_new_tokens"] == 4096
    assert plan["prompt"] == diag.SAMPLING_DIAG_PROMPT_V2 % {
        "window_start": 360.0, "window_end": 408.0}

    frozen = dict(sw.FROZEN_FROM_V2)
    frozen["dtype"] = "float16"
    monkeypatch.setattr(sw, "FROZEN_FROM_V2", frozen)
    with pytest.raises(runner.RunError, match="동결값"):
        runner.preflight("P1", sw.ARM_S0, out_dir)


def test_wvr_s27_the_runner_writes_one_artifact_per_arm(tmp_path):
    out_dir = _runner_dir(tmp_path)
    plan = runner.preflight("P2", sw.ARM_S1, out_dir)
    assert plan["out_path"].name == "short_window_P2_S1.json"
    plan["out_path"].write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError, match="이미 있다"):
        runner.preflight("P2", sw.ARM_S1, out_dir)


def test_wvr_s28_windows_derive_from_the_committed_evidence_artifact():
    assert EVIDENCE.is_file(), "evidence resolution 산출물이 필요하다"
    resolution = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    windows = sw.derive_windows(resolution)
    sw.assert_expected(windows)
    assert [row["source_pair"] for row in windows] == ["D1", "D1", "D2"]


# ── 실행 후 (산출물 있을 때만) ──────────────────────────────────────
def _artifacts():
    return [RUNS / ("%s_%s_%s.json" % (sw.ARTIFACT_TAG, row[0], arm))
            for row in sw.EXPECTED_WINDOWS for arm in sw.ARMS]


def _built_packet():
    if not all(path.is_file() for path in _artifacts()):
        pytest.skip("short-window 산출물 미생성")
    return packet.build(RUNS, "test-salt")


requires_runs = pytest.mark.skipif(
    not all(path.is_file() for path in _artifacts()),
    reason="short-window 미실행")


@requires_runs
def test_wvr_s29_every_arm_records_the_single_change_and_frame_count():
    expected = {sw.ARM_S0: 24, sw.ARM_S1: 12}
    for row in sw.EXPECTED_WINDOWS:
        for arm in sw.ARMS:
            record = packet.load_arm(RUNS, row[0], arm)
            assert record["single_change"]["single_change"] is True
            assert record["context_length_sec"] == sw.WINDOW_SEC
            assert record["metrics"]["delivered_frame_count"] == expected[arm]
            assert record["prompt_hash"] == diag.prompt_hash()


@requires_runs
def test_wvr_s30_the_packet_lists_three_windows_and_six_arms():
    built = _built_packet()
    text = built["packet"]
    for row in sw.EXPECTED_WINDOWS:
        assert "## %s" % row[0] in text
    assert text.count("### Arm A") == 3
    assert text.count("### Arm B") == 3
