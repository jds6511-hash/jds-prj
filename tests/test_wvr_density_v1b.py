"""V1B 계약 — max_new_tokens 4096만 바뀐다 (2026-09-09 · WVR-F01~F14).

```
arm validity   파싱 성공 + event ≥ 1 + 절단 없음
언어 계약       validity와 분리해 기록한다
pair           한쪽이라도 invalid면 NON_EVALUABLE
사건 판정       세 pair 전부 evaluable일 때만 MEASURED
```
"""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_contract as contract
import wvr_density as density
import wvr_density_compare as compare
import wvr_density_prompt as diag
import wvr_density_v1b as events

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT / "docs/preregistration/"
          "WVR_SAMPLING_SEMANTIC_DENSITY_V1B_2026-09-09.md")
RUNNER = ROOT / "scripts/wvr_density_stage2.py"
RUNS = ROOT / "runs/wvr_light_v1"
REPORT = ROOT / "docs/probes/WVR_DENSITY_STAGE2B_2026-09-09.md"
WINDOW = {"start_sec": 300.0, "end_sec": 480.0}


def _runner():
    spec = importlib.util.spec_from_file_location("wvr_density_stage2", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wvr_density_stage2"] = module
    spec.loader.exec_module(module)
    return module


runner = _runner()
DOC = PREREG.read_text(encoding="utf-8")


def _record(*, generated=800, cap=4096, events_count=3, korean=True):
    rows = [{"approx_time": 300.0 + index * 10,
             "event": "재료를 다룬다" if korean else "A hand holds a bag",
             "visible_entities": ["사람"] if korean else ["hand", "bag"],
             "activity": "자르기" if korean else "holding"}
            for index in range(events_count)]
    raw = json.dumps({"observed_events": rows}, ensure_ascii=False)
    parsed = compare.parse_events(raw, WINDOW)
    return {"raw_output": raw, "parsed": parsed,
            "metrics": {"generated_token_count": generated},
            "requested": {"max_new_tokens": cap}}


# ── WVR-F01~F04 사건 분리 ──────────────────────────────────────────────
def test_wvr_f01_the_preregistration_is_committed():
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1B_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert tracked.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_f02_only_the_token_cap_changes():
    assert events.tokens_for("V1B") == 4096
    assert events.tokens_for("V1") == 1024 == contract.MAX_NEW_TOKENS
    assert "max_new_tokens   1024 → 4096" in DOC


def test_wvr_f03_an_unregistered_cap_is_refused():
    assert events.ALLOWED_MAX_NEW_TOKENS == (1024, 4096)
    for value in (512, 2048, 8192):
        with pytest.raises(events.EventError):
            events.assert_allowed(value)
    assert events.assert_allowed(4096) is None
    with pytest.raises(events.EventError):
        events.tokens_for("V2")


def test_wvr_f04_the_artifacts_do_not_share_a_name():
    assert events.tag_for("V1") == "density_stage2"
    assert events.tag_for("V1B") == "density_stage2b"
    assert events.tag_for("V1") != events.tag_for("V1B")
    source = RUNNER.read_text(encoding="utf-8")
    assert "events.tag_for(event)" in source


# ── WVR-F05 · F06 arm validity ────────────────────────────────────────
def test_wvr_f05_validity_is_parse_and_events_and_no_truncation():
    assert compare.arm_validity(_record())["valid"] is True
    truncated = compare.arm_validity(_record(generated=4096))
    assert truncated["valid"] is False
    assert "TRUNCATED_AT_CAP" in truncated["reasons"]
    empty = _record(events_count=0)
    assert compare.arm_validity(empty)["valid"] is False
    broken = {"raw_output": "설명만", "parsed": compare.parse_events("설명만",
                                                                 WINDOW),
              "metrics": {"generated_token_count": 100},
              "requested": {"max_new_tokens": 4096}}
    assert "PARSE_FAILURE" in compare.arm_validity(broken)["reasons"]


def test_wvr_f06_a_language_violation_is_recorded_apart_from_validity():
    english = _record(korean=False)
    verdict = compare.arm_validity(english)
    assert verdict["language_contract_failure"] is True
    assert verdict["valid"] is True                  # validity와 분리된다
    assert "TRUNCATED_AT_CAP" not in verdict["reasons"]
    korean = compare.arm_validity(_record())
    assert korean["language_contract_failure"] is False
    assert "별도 contract failure로 반드시 기록" in DOC


# ── WVR-F07~F09 pair·사건 판정 ────────────────────────────────────────
def test_wvr_f07_one_bad_arm_kills_the_pair():
    good, bad = _record(), _record(generated=4096)
    assert compare.pair_evaluability(good, good)["status"] \
        == compare.PAIR_EVALUABLE
    for pair in ((good, bad), (bad, good)):
        result = compare.pair_evaluability(*pair)
        assert result["status"] == compare.PAIR_NON_EVALUABLE
        assert result["reasons"]


def test_wvr_f08_all_three_pairs_are_required():
    evaluable = compare.PAIR_EVALUABLE
    assert compare.event_verdict([evaluable] * 3) == compare.EVENT_MEASURED
    assert compare.event_verdict([evaluable] * 2) == compare.EVENT_INCONCLUSIVE
    assert compare.event_verdict([evaluable, evaluable,
                                  compare.PAIR_NON_EVALUABLE]) \
        == compare.EVENT_INCONCLUSIVE
    assert compare.event_verdict([]) == compare.EVENT_INCONCLUSIVE


def test_wvr_f09_a_missing_pair_leaves_the_event_inconclusive():
    assert "하나라도 NON_EVALUABLE" in DOC
    assert "event extraction은 HOLD" in DOC
    assert compare.EVENT_INCONCLUSIVE == "INCONCLUSIVE"


# ── WVR-F10~F12 동결 ─────────────────────────────────────────────────
def test_wvr_f10_escalation_is_not_approved():
    assert events.ESCALATION_APPROVED is False
    assert "즉석에서 8192로 올리지 않는다" in DOC


def test_wvr_f11_the_prompt_is_unchanged():
    assert diag.prompt_hash() == (
        "7899dc460957fff6eef49ffb50ab15fb527436ec5008ee618772a232ce4350a4")
    assert diag.prompt_hash() in DOC
    assert diag.IS_PRODUCTION_CONTRACT is False


def test_wvr_f12_the_windows_and_sampling_are_unchanged():
    stage1 = json.loads((RUNS / "density_stage1.json").read_text(
        encoding="utf-8"))
    assert [stage1["selection"][label]["window_id"]
            for label in density.SELECTION_LABELS] == ["W11", "W02", "W05"]
    window = runner.window_for("D1_highest_change", stage1)
    assert len(runner.arm_timestamps(window, "S0")) == 90
    assert len(runner.arm_timestamps(window, "S1")) == 45
    assert (contract.FRAME_WIDTH, contract.FRAME_HEIGHT) == (512, 288)
    assert density.MATCH_TOLERANCE_SEC == (4.0, 8.0)


# ── WVR-F13 V1 산출물 무변경 ─────────────────────────────────────────
@pytest.mark.parametrize("name", ["D1_S0", "D1_S1", "D2_S0", "D2_S1",
                                  "D3_S0", "D3_S1"])
def test_wvr_f13_the_v1_artifacts_are_untouched(name):
    path = "runs/wvr_light_v1/density_stage2_%s.json" % name
    done = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path],
                          cwd=str(ROOT))
    assert done.returncode == 0, "%s이 변경됐다" % path


# ── 조건부: V1B 실행 후 ──────────────────────────────────────────────
def _v1b_paths():
    return sorted(RUNS.glob("density_stage2b_*.json"))


@pytest.mark.skipif(not _v1b_paths(), reason="V1B 미실행")
def test_the_v1b_artifacts_carry_the_new_cap():
    paths = _v1b_paths()
    assert len(paths) == 6
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["event"] == "V1B"
        assert record["requested"]["max_new_tokens"] == 4096
        assert record["requested"]["frame_size"] == [512, 288]
        assert record["prompt_hash"] == diag.prompt_hash()
        assert record["allocator_observed"][
            "expandable_segments_observed"] is False


@pytest.mark.skipif(not _v1b_paths(), reason="V1B 미실행")
def test_the_pair_gate_is_recorded_for_every_window():
    summary = RUNS / "density_stage2b_summary.json"
    assert summary.is_file(), "요약 산출물이 없다"
    record = json.loads(summary.read_text(encoding="utf-8"))
    assert set(record["pairs"]) == {"D1", "D2", "D3"}
    statuses = [record["pairs"][name]["evaluability"]["status"]
                for name in ("D1", "D2", "D3")]
    assert record["event_verdict"] == compare.event_verdict(statuses)


@pytest.mark.skipif(not (RUNS / "density_stage2b_summary.json").is_file()
                    or not REPORT.is_file(), reason="V1B 또는 보고서 미실행")
def test_wvr_f14_the_report_agrees_with_the_summary():
    record = json.loads((RUNS / "density_stage2b_summary.json").read_text(
        encoding="utf-8"))
    text = REPORT.read_text(encoding="utf-8")
    assert record["event_verdict"] in text
    for name in ("D1", "D2", "D3"):
        assert record["pairs"][name]["evaluability"]["status"] in text
