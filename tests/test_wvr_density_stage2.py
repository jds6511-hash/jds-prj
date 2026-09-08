"""Stage 2 계약 — PAIRED_OUTPUT_SENSITIVITY (2026-09-08 · WVR-E01~E16).

```
매칭      시간 허용오차만으로 결정한다. 유사도 임계값은 없다
허용오차   (4.0, 8.0) 둘 다 보고 — 사후에 하나를 고르지 않는다
S1 ⊂ S0   같은 창의 KEEP 부분집합이어야 한다
판정      이 사건은 PASS/FAIL을 내지 않는다
```
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import wvr_density as density
import wvr_density_compare as compare
import wvr_density_prompt as diag

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/wvr_density_stage2.py"
STAGE1 = ROOT / "runs/wvr_light_v1/density_stage1.json"
WINDOW = {"start_sec": 300.0, "end_sec": 480.0}


def _runner():
    spec = importlib.util.spec_from_file_location("wvr_density_stage2", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wvr_density_stage2"] = module
    spec.loader.exec_module(module)
    return module


runner = _runner()


def _payload(rows):
    return json.dumps({"observed_events": rows}, ensure_ascii=False)


def _event(time_sec, text, entities=("사람",), activity="자르기"):
    return {"approx_time": time_sec, "event": text,
            "visible_entities": list(entities), "activity": activity}


# ── WVR-E01~E05 파싱 ──────────────────────────────────────────────────
def test_wvr_e01_a_valid_output_parses():
    parsed = compare.parse_events(_payload([_event(310.0, "재료를 꺼낸다")]),
                                  WINDOW)
    assert parsed["status"] == compare.PARSE_OK
    assert parsed["events"][0]["approx_time"] == 310.0
    assert parsed["events"][0]["inside_window"] is True
    assert parsed["violations"] == []


def test_wvr_e02_a_missing_json_is_a_parse_failure():
    for raw in ("", "설명만 있다", "```json 없음"):
        parsed = compare.parse_events(raw, WINDOW)
        assert parsed["status"] == compare.PARSE_FAILURE
        assert parsed["events"] == []


def test_wvr_e03_a_broken_json_is_not_repaired():
    parsed = compare.parse_events('{"observed_events": [', WINDOW)
    assert parsed["status"] == compare.PARSE_FAILURE
    assert parsed["reason"]


def test_wvr_e04_a_wrong_schema_is_a_contract_violation():
    assert compare.parse_events('{"observed_events": "x"}', WINDOW)["status"] \
        == compare.CONTRACT_VIOLATION
    assert compare.parse_events('{"events": []}', WINDOW)["status"] \
        == compare.CONTRACT_VIOLATION
    assert compare.parse_events(_payload([]), WINDOW)["status"] \
        == compare.CONTRACT_VIOLATION


def test_wvr_e05_an_out_of_window_time_is_recorded_not_dropped():
    parsed = compare.parse_events(
        _payload([_event(310.0, "안쪽"), _event(700.0, "창 밖")]), WINDOW)
    assert len(parsed["events"]) == 2                  # 조용히 버리지 않는다
    assert parsed["events"][1]["inside_window"] is False
    assert parsed["violations"][0]["approx_time"] == 700.0
    bad = compare.parse_events(
        _payload([{"approx_time": "310", "event": "문자 시각"}]), WINDOW)
    assert bad["violations"][0]["reason"].endswith("수가 아니다")


# ── WVR-E06~E10 매칭 ──────────────────────────────────────────────────
def test_wvr_e06_matching_is_decided_by_time_only():
    """유사도가 0이어도 허용오차 안이면 매칭된다 — 유사도 임계값은 없다."""
    reference = compare.parse_events(_payload([_event(310.0, "가나다")]),
                                     WINDOW)["events"]
    arm = compare.parse_events(_payload([_event(312.0, "전혀 다른 문장")]),
                               WINDOW)["events"]
    matched = compare.match(reference, arm, 4.0)
    assert matched["pairs"][0]["event_similarity"] == 0.0
    assert matched["only_reference"] == [] and matched["only_arm"] == []


def test_wvr_e07_the_tolerance_boundary_is_inclusive():
    reference = compare.parse_events(_payload([_event(310.0, "같음")]),
                                     WINDOW)["events"]
    arm = compare.parse_events(_payload([_event(314.0, "같음")]),
                               WINDOW)["events"]
    assert compare.match(reference, arm, 4.0)["pairs"]
    assert compare.match(reference, arm, 3.9)["pairs"] == []
    assert len(compare.match(reference, arm, 3.9)["only_reference"]) == 1


def test_wvr_e08_the_matching_is_one_to_one_and_deterministic():
    reference = compare.parse_events(
        _payload([_event(310.0, "가"), _event(311.0, "나")]), WINDOW)["events"]
    arm = compare.parse_events(_payload([_event(310.5, "가")]),
                               WINDOW)["events"]
    matched = compare.match(reference, arm, 8.0)
    assert len(matched["pairs"]) == 1
    assert matched["pairs"][0]["reference_index"] == 0        # 유사도로 가른다
    assert len(matched["only_reference"]) == 1
    assert compare.match(reference, arm, 8.0) == matched      # 결정적


def test_wvr_e09_an_unmatched_event_lands_in_the_right_bucket():
    reference = compare.parse_events(_payload([_event(310.0, "앞")]),
                                     WINDOW)["events"]
    arm = compare.parse_events(_payload([_event(400.0, "뒤")]),
                               WINDOW)["events"]
    matched = compare.match(reference, arm, 8.0)
    assert matched["pairs"] == []
    assert matched["only_reference"][0]["event"] == "앞"
    assert matched["only_arm"][0]["event"] == "뒤"


def test_wvr_e10_the_order_change_is_counted():
    pairs = [{"reference_index": 0, "arm_index": 1},
             {"reference_index": 1, "arm_index": 0}]
    assert compare.order_inversions(pairs) == 1
    assert compare.order_inversions([{"reference_index": 0, "arm_index": 0},
                                     {"reference_index": 1,
                                      "arm_index": 1}]) == 0


# ── WVR-E11 · E12 두 허용오차 ─────────────────────────────────────────
def test_wvr_e11_both_tolerances_are_reported():
    reference = compare.parse_events(
        _payload([_event(310.0, "가"), _event(400.0, "나")]), WINDOW)
    arm = compare.parse_events(
        _payload([_event(316.0, "가"), _event(401.0, "나")]), WINDOW)
    result = compare.compare(reference, arm)
    assert set(result["per_tolerance"]) == {"tol_4.0", "tol_8.0"}
    assert result["per_tolerance"]["tol_4.0"]["matched_count"] == 1
    assert result["per_tolerance"]["tol_8.0"]["matched_count"] == 2
    assert compare.TOLERANCES == (4.0, 8.0)


def test_wvr_e12_the_reference_arm_is_not_called_ground_truth():
    reference = compare.parse_events(_payload([_event(310.0, "가")]), WINDOW)
    result = compare.compare(reference, reference)
    assert "ground truth가 아니다" in result["note"]
    source = (ROOT / "src/wvr_density_compare.py").read_text(encoding="utf-8")
    assert "ground_truth" not in source
    assert result["event_count_delta"] == 0


# ── WVR-E13 entity·activity ──────────────────────────────────────────
def test_wvr_e13_entity_and_activity_changes_are_measured():
    reference = compare.parse_events(
        _payload([_event(310.0, "가", entities=("사람", "칼"),
                         activity="자르기")]), WINDOW)
    arm = compare.parse_events(
        _payload([_event(311.0, "가", entities=("사람",),
                         activity="담기")]), WINDOW)
    pair = compare.compare(reference, arm)["per_tolerance"]["tol_4.0"]["pairs"][0]
    assert pair["entity_jaccard"] == 0.5
    assert pair["activity_similarity"] < 1.0
    assert compare.jaccard(["가"], ["가"]) == 1.0
    assert compare.jaccard([], []) == 1.0
    assert compare.jaccard(["가"], []) == 0.0


# ── WVR-E14 arm 표집 ─────────────────────────────────────────────────
@pytest.mark.parametrize("label", density.SELECTION_LABELS)
def test_wvr_e14_the_arms_are_a_subset_pair(label):
    stage1 = json.loads(STAGE1.read_text(encoding="utf-8"))
    window = runner.window_for(label, stage1)
    s0 = runner.arm_timestamps(window, "S0")
    s1 = runner.arm_timestamps(window, "S1")
    assert len(s0) == 90 and len(s1) == 45
    assert set(s1) <= set(s0)
    assert s1[1] - s1[0] == 4.0 and s0[1] - s0[0] == 2.0
    assert window["end_sec"] - window["start_sec"] == 180.0


def test_an_unknown_window_or_arm_is_refused():
    stage1 = json.loads(STAGE1.read_text(encoding="utf-8"))
    with pytest.raises(runner.Stage2Error):
        runner.window_for("D9_best_looking", stage1)
    window = runner.window_for("D1_highest_change", stage1)
    with pytest.raises(runner.Stage2Error):
        runner.arm_timestamps(window, "S2")


def test_the_windows_come_from_the_stage1_selection():
    stage1 = json.loads(STAGE1.read_text(encoding="utf-8"))
    for label in density.SELECTION_LABELS:
        window = runner.window_for(label, stage1)
        assert window["window_id"] == stage1["selection"][label]["window_id"]
        assert window["stage1_score"] == stage1["selection"][label]["score"]


# ── WVR-E15 · E16 경계 ───────────────────────────────────────────────
def test_wvr_e15_the_diagnostic_prompt_is_used_not_the_production_one():
    source = RUNNER.read_text(encoding="utf-8")
    assert "diag.SAMPLING_DIAG_PROMPT_V1" in source
    assert "EVENT_PROMPT_V1" not in source
    assert diag.IS_PRODUCTION_CONTRACT is False
    assert runner.EVENT_EXTRACTION_APPROVED is False
    assert runner.SEMANTIC_VERDICT_ALLOWED is False


def test_wvr_e16_there_is_no_retry_or_offload_path():
    source = RUNNER.read_text(encoding="utf-8")
    for forbidden in ("retry", "fallback", "while True", "device_map=",
                      "load_in_8bit", "load_in_4bit", "PYTORCH_CUDA_ALLOC_CONF"):
        assert forbidden not in source
    assert "arm은 1회다" in source


# ── 비퇴화 전제조건 (다음 사건용 · 이번 실행을 재판정하지 않는다) ──────
def _record(*, generated=512, cap=1024, status=compare.PARSE_OK, events=1):
    return {"metrics": {"generated_token_count": generated},
            "requested": {"max_new_tokens": cap},
            "parsed": {"status": status,
                       "events": [{"index": 0}] * events}}


def test_a_capped_generation_is_degenerate():
    assert compare.truncated_at_cap(_record(generated=1024)) is True
    assert compare.truncated_at_cap(_record(generated=512)) is False
    assert compare.non_degenerate(_record(generated=1024)) is False


def test_an_unparsable_or_empty_output_is_degenerate():
    assert compare.non_degenerate(
        _record(status=compare.PARSE_FAILURE)) is False
    assert compare.non_degenerate(_record(events=0)) is False
    assert compare.non_degenerate(_record()) is True


@pytest.mark.parametrize("name", ["D1_S0", "D1_S1", "D2_S0", "D2_S1",
                                  "D3_S0", "D3_S1"])
def test_the_2026_09_09_run_is_recorded_as_degenerate(name):
    """이번 실행은 전부 cap에서 끊겼다. 그 사실이 산출물에 남아 있어야 한다."""
    path = ROOT / ("runs/wvr_light_v1/density_stage2_%s.json" % name)
    if not path.is_file():
        pytest.skip("Stage 2 미실행")
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["arm_status"] == compare.PARSE_FAILURE
    assert compare.truncated_at_cap(record) is True
    assert compare.non_degenerate(record) is False
    assert record["metrics"]["generated_token_count"] == 1024
