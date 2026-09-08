"""WVR_CAPACITY_ALLOC_V1 계약 (2026-09-08 · WVR-A01~A36).

```
treatment      allocator 하나만 다르다
A1 실행        A0 == CAPACITY_FAIL일 때만
PASS 정의      prefill 통과가 아니라 generate 완주
인과 비교      실측 workload 동일 + baseline delta <= 128 MiB
```

GPU 없이 잰다 — 판정 논리는 `src/wvr_alloc.py`에 순수 함수로 있다.
"""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_alloc as alloc
import wvr_contract as contract
import wvr_prompts as prompts

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/preregistration/WVR_CAPACITY_ALLOC_V1_2026-09-08.md"
RUNNER = ROOT / "scripts/wvr_capacity_alloc.py"
PROBE = ROOT / "scripts/wvr_capacity_probe.py"
C01 = ROOT / "runs/wvr_light_v1/capacity_C01.json"
A0_PATH = ROOT / "runs/wvr_light_v1/capacity_alloc_A0.json"
A1_PATH = ROOT / "runs/wvr_light_v1/capacity_alloc_A1.json"
SUBMISSION = ROOT / "runs/quality_candidate/report_quality.hwpx"


def _runner():
    spec = importlib.util.spec_from_file_location("wvr_capacity_alloc", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wvr_capacity_alloc"] = module
    spec.loader.exec_module(module)
    return module


runner = _runner()
DOC = PREREG.read_text(encoding="utf-8")


def _record(*, verdict="PASS", baseline=40.0, expandable=False, tokens=23463):
    """probe 산출물 모양의 최소 표본."""
    return {
        "verdict": verdict,
        "requested": {
            "model_id": contract.MODEL_ID,
            "model_revision": contract.MODEL_REVISION,
            "dtype": "bfloat16", "quantization": None, "device": "cuda:0",
            "device_map": None, "attn_implementation": "sdpa",
            "chunk_fps": 0.5, "frame_size": [512, 288],
            "do_sample_frames": False, "do_resize": False,
            "do_sample": False, "num_beams": 1, "max_new_tokens": 1024,
            "repetition_penalty": 1.0,
        },
        "chunk": {"chunk_id": "C01", "start_sec": 0.0, "end_sec": 600.0},
        "prompt_contract": "EVENT_PROMPT_V1",
        "prompt_hashes": prompts.contract_hashes(),
        "frame_indices_first_last": [0, 17940],
        "allocator_observed": {"backend": "native",
                               "expandable_segments_observed": expandable,
                               "segment_count": 4},
        "metrics": {
            "baseline_vram_mib": baseline, "delivered_frame_count": 300,
            "requested_timestamps": 300, "frame_size": [512, 288],
            "frame_times_first_last": [0.0, 598.0],
            "video_token_count": 21600, "input_token_count": tokens,
            "oom": verdict == "CAPACITY_FAIL",
            "generation_completed": verdict == "PASS",
            "finish_reason": "EOS" if verdict == "PASS" else None,
            "generated_token_count": 512 if verdict == "PASS" else None,
        },
    }


# ── WVR-A01 · A02 사전등록 우선 ─────────────────────────────────────────
def test_wvr_a01_the_preregistration_exists_and_is_tracked():
    assert PREREG.is_file()
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch",
                              str(PREREG.relative_to(ROOT)).replace("\\", "/")],
                             cwd=str(ROOT), capture_output=True, text=True)
    assert tracked.returncode == 0, "사전등록이 커밋되지 않았다"


@pytest.mark.skipif(not A0_PATH.is_file(), reason="A0 미실행")
def test_wvr_a02_the_preregistration_commit_precedes_the_run():
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%cI", "--",
         "docs/preregistration/WVR_CAPACITY_ALLOC_V1_2026-09-08.md"],
        cwd=str(ROOT), capture_output=True, text=True, check=True).stdout.strip()
    record = json.loads(A0_PATH.read_text(encoding="utf-8"))
    assert commit and commit < record["gpu_idle_before"]["timestamp"]


# ── WVR-A03~A15 frozen workload ────────────────────────────────────────
def test_wvr_a03_the_snapshot_is_the_c01_one():
    assert contract.MODEL_REVISION == "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
    assert contract.MODEL_REVISION in DOC


def test_wvr_a04_a05_a06_a07_dtype_attention_quantization_offload():
    assert contract.DTYPE == "bfloat16"
    assert contract.ATTN_IMPLEMENTATION == "sdpa"
    assert contract.QUANTIZATION is None
    assert contract.DEVICE_MAP is None
    source = RUNNER.read_text(encoding="utf-8")
    for forbidden in ("device_map=", "offload_folder", "load_in_8bit",
                      "load_in_4bit", "BitsAndBytes"):
        assert forbidden not in source


def test_wvr_a08_a09_a10_a11_chunk_fps_frames_resolution():
    chunk = runner.probe.approved_chunk(2424.186485)
    assert chunk["end_sec"] - chunk["start_sec"] == 600.0
    assert contract.CHUNK_FPS == 0.5
    assert len(contract.chunk_frames(chunk)) == 300
    assert (contract.FRAME_WIDTH, contract.FRAME_HEIGHT) == (512, 288)


def test_wvr_a12_a13_timestamps_and_video_metadata():
    stamps = contract.chunk_frames(runner.probe.approved_chunk(2424.186485))
    assert (stamps[0], stamps[-1]) == (0.0, 598.0)
    assert "video_metadata" in PROBE.read_text(encoding="utf-8")


def test_wvr_a14_a15_prompt_and_generation_config():
    assert prompts.contract_hash("EVENT_PROMPT_V1").startswith("a3c087d715b1dd49")
    assert contract.MAX_NEW_TOKENS == 1024
    assert contract.DO_SAMPLE is False and contract.NUM_BEAMS == 1
    assert contract.REPETITION_PENALTY == 1.0


# ── WVR-A16 · A17 allocator ────────────────────────────────────────────
def test_wvr_a16_the_control_refuses_an_allocator_setting():
    assert alloc.assert_allocator_env("A0", {}) == ""
    with pytest.raises(alloc.AllocError):
        alloc.assert_allocator_env(
            "A0", {"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})


@pytest.mark.parametrize("value", ["", "expandable_segments:False",
                                   "max_split_size_mb:128",
                                   "expandable_segments:true"])
def test_wvr_a17_the_treatment_requires_the_exact_value(value):
    with pytest.raises(alloc.AllocError):
        alloc.assert_allocator_env("A1", {"PYTORCH_CUDA_ALLOC_CONF": value})
    assert alloc.assert_allocator_env(
        "A1", {"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}) \
        == "expandable_segments:True"


# ── WVR-A18~A21 실행 횟수·순서·프로세스 ────────────────────────────────
def test_wvr_a18_a20_each_arm_runs_at_most_once():
    with pytest.raises(alloc.AllocError):
        alloc.assert_once(True, "A0")
    with pytest.raises(alloc.AllocError):
        alloc.assert_once(True, "A1")
    assert alloc.assert_once(False, "A1") is None


def test_wvr_a19_the_treatment_cannot_run_when_the_control_passes():
    with pytest.raises(alloc.AllocError):
        alloc.assert_a1_allowed(_record(verdict="PASS"))
    with pytest.raises(alloc.AllocError):
        alloc.assert_a1_allowed(None)
    assert alloc.assert_a1_allowed(_record(verdict="CAPACITY_FAIL")) is None


def test_wvr_a21_an_initialised_cuda_context_is_refused():
    with pytest.raises(alloc.AllocError):
        alloc.assert_fresh_process(True)
    assert alloc.assert_fresh_process(False) is None
    source = RUNNER.read_text(encoding="utf-8")
    assert "os.environ[" not in source          # allocator를 안에서 설정하지 않는다
    assert "putenv" not in source


# ── WVR-A22 · A23 idle·baseline ───────────────────────────────────────
def test_wvr_a22_a_busy_gpu_blocks_the_run():
    with pytest.raises(alloc.AllocError):
        alloc.assert_idle({"compute_process_count": 1})
    with pytest.raises(alloc.AllocError):
        alloc.assert_idle({})
    assert alloc.assert_idle({"compute_process_count": 0}) is None


def test_wvr_a23_the_baseline_is_part_of_the_required_metrics():
    for name in ("baseline_vram_mib", "baseline_vram_free_mib"):
        assert name in runner.probe.REQUIRED_METRICS


# ── WVR-A24 · A25 comparability ───────────────────────────────────────
def test_wvr_a24_the_baseline_delta_is_computed():
    a0, a1 = _record(baseline=40.0), _record(baseline=52.5)
    assert alloc.baseline_delta_mib(a0, a1) == 12.5


def test_wvr_a25_a_large_delta_invalidates_the_causal_comparison():
    assert alloc.comparability(128) == alloc.COMPARABLE
    assert alloc.comparability(128.1) == alloc.COMPARISON_INVALID
    a0 = _record(verdict="CAPACITY_FAIL", baseline=40.0)
    a1 = _record(verdict="PASS", baseline=400.0, expandable=True)
    assert alloc.event_verdict(a0, a1) == alloc.EVENT_COMPARISON_INVALID
    assert alloc.comparison_invalid_reason(a0, a1) == "BASELINE_DELTA_ABOVE_GATE"


def test_the_gate_is_documented_as_an_operational_tolerance():
    assert alloc.COMPARABILITY_THRESHOLD_MIB == 128
    assert "operational tolerance" in DOC
    assert "과학적으로 도출한 임계값이 아니다" in DOC


# ── WVR-A26 semantic ──────────────────────────────────────────────────
def test_wvr_a26_semantic_evaluation_stays_disabled():
    assert runner.SEMANTIC_EVALUATION_ENABLED is False
    assert alloc.SEMANTIC_RESULT == "NOT_EVALUATED"
    assert runner.probe.SEMANTIC_RESULT == "NOT_EVALUATED"


# ── WVR-A27 지표 완비 ─────────────────────────────────────────────────
@pytest.mark.parametrize("name", [
    "baseline_vram_mib", "baseline_vram_free_mib", "post_load_vram_mib",
    "peak_vram_allocated_mib", "peak_vram_reserved_mib", "device_peak_used_mib",
    "delivered_frame_count", "frame_size", "input_token_count",
    "video_token_count", "load_wall_sec", "video_process_wall_sec",
    "infer_wall_sec", "total_wall_sec", "oom", "generated_token_count",
    "finish_reason",
])
def test_wvr_a27_the_capacity_metrics_are_required(name):
    assert name in runner.probe.REQUIRED_METRICS


# ── WVR-A28 · A29 JSON normative ──────────────────────────────────────
def test_wvr_a28_the_json_is_the_normative_source():
    assert "normative source는 JSON이다" in DOC


@pytest.mark.skipif(not A0_PATH.is_file(), reason="A0 미실행")
def test_wvr_a29_the_report_agrees_with_the_json():
    report = ROOT / "docs/probes/WVR_CAPACITY_ALLOC_V1_2026-09-08.md"
    assert report.is_file(), "보고서가 없다"
    text = report.read_text(encoding="utf-8")
    record = json.loads(A0_PATH.read_text(encoding="utf-8"))
    for field in ("baseline_vram_mib", "post_load_vram_mib",
                  "peak_vram_allocated_mib", "input_token_count"):
        assert format(record["metrics"][field], ",") in text


# ── WVR-A30 · A31 기존 자산 ───────────────────────────────────────────
@pytest.mark.parametrize("path", ["runs/wvr_light_v1/capacity_C01.json",
                                  "runs/quality_candidate/report_quality.hwpx"])
def test_wvr_a30_a31_the_historical_artifacts_are_unchanged(path):
    done = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path],
                          cwd=str(ROOT))
    assert done.returncode == 0, "%s이 변경됐다" % path


# ── WVR-A32 treatment 적용 검증 ───────────────────────────────────────
def test_wvr_a32_an_unapplied_treatment_is_not_a_capacity_verdict():
    a0 = _record(verdict="CAPACITY_FAIL")
    a1 = _record(verdict="PASS", expandable=False)          # 적용 안 됨
    assert alloc.a1_status(a1) == alloc.TREATMENT_NOT_APPLIED
    assert alloc.event_verdict(a0, a1) == alloc.EVENT_DEFECT


def test_an_allocator_warning_also_blocks_the_capacity_verdict():
    a0 = _record(verdict="CAPACITY_FAIL")
    a1 = _record(verdict="PASS", expandable=True)
    log = "UserWarning: expandable_segments not supported on this platform"
    assert alloc.allocator_warnings(log)
    assert alloc.a1_status(a1, log) == alloc.TREATMENT_NOT_APPLIED
    assert alloc.event_verdict(a0, a1, log) == alloc.EVENT_DEFECT
    assert alloc.a1_status(a1, "") == alloc.ARM_PASS


# ── WVR-A33 workload identity ─────────────────────────────────────────
def test_wvr_a33_a_measured_workload_difference_blocks_the_comparison():
    a0 = _record(verdict="CAPACITY_FAIL", tokens=23463)
    a1 = _record(verdict="PASS", expandable=True, tokens=23319)
    assert "input_token_count" in alloc.workload_identity(a0, a1)
    assert alloc.comparison_invalid_reason(a0, a1) == alloc.WORKLOAD_MISMATCH
    assert alloc.event_verdict(a0, a1) == alloc.EVENT_COMPARISON_INVALID


def test_an_identical_pair_has_no_workload_difference():
    a0 = _record(verdict="CAPACITY_FAIL")
    a1 = _record(verdict="PASS", expandable=True)
    assert alloc.workload_identity(a0, a1) == ()
    assert alloc.event_verdict(a0, a1) == alloc.EVENT_CAPACITY_PASS


@pytest.mark.parametrize("field,value", [
    ("delivered_frame_count", 299), ("frame_size", [384, 216]),
    ("frame_times_first_last", [0.0, 596.0]), ("video_token_count", 10800),
    ("requested_timestamps", 150),
])
def test_each_identity_metric_is_checked(field, value):
    a0 = _record(verdict="CAPACITY_FAIL")
    a1 = _record(verdict="PASS", expandable=True)
    a1["metrics"][field] = value
    assert field in alloc.workload_identity(a0, a1)


def test_a_changed_frame_index_is_caught():
    a0 = _record(verdict="CAPACITY_FAIL")
    a1 = _record(verdict="PASS", expandable=True)
    a1["frame_indices_first_last"] = [0, 17880]
    assert "frame_indices_first_last" in alloc.workload_identity(a0, a1)


# ── WVR-A34 완주 정의 ─────────────────────────────────────────────────
def test_wvr_a34_a_prefill_only_pass_is_not_a_capacity_pass():
    record = _record(verdict="PASS")
    record["metrics"]["generation_completed"] = False
    assert alloc.completion_ok(record) is False
    assert alloc.arm_verdict(record) == alloc.ARM_DEFECT


@pytest.mark.parametrize("field,value", [
    ("generated_token_count", 0), ("finish_reason", None),
    ("generation_completed", None), ("oom", True),
])
def test_each_completion_condition_is_required(field, value):
    record = _record(verdict="PASS")
    record["metrics"][field] = value
    assert alloc.completion_ok(record) is False


def test_a_completed_generation_passes():
    record = _record(verdict="PASS")
    assert alloc.completion_ok(record) is True
    assert alloc.arm_verdict(record) == alloc.ARM_PASS


# ── WVR-A35 · A36 계측 ────────────────────────────────────────────────
def test_wvr_a35_the_fragmentation_statistics_are_collected():
    source = PROBE.read_text(encoding="utf-8")
    for key in ("inactive_split_bytes.all.peak", "num_alloc_retries",
                "num_ooms", "memory_summary"):
        assert key in source


def test_wvr_a36_the_preflight_records_the_execution_context():
    source = RUNNER.read_text(encoding="utf-8")
    for key in ("video_sha256", "model_snapshot", "git_head", "tree_clean",
                "command", "environment"):
        assert key in source
    assert "PYTORCH_CUDA_ALLOC_CONF" in source


# ── 사건 판정 어휘 ────────────────────────────────────────────────────
def test_the_control_pass_closes_the_event_without_the_treatment():
    a0 = _record(verdict="PASS")
    assert alloc.event_verdict(a0) == alloc.EVENT_CONTROL_PASS
    with pytest.raises(alloc.AllocError):
        alloc.event_verdict(a0, _record(verdict="PASS", expandable=True))


def test_a_failed_control_cannot_close_the_event_alone():
    with pytest.raises(alloc.AllocError):
        alloc.event_verdict(_record(verdict="CAPACITY_FAIL"))


def test_both_failing_arms_are_a_capacity_fail():
    a0 = _record(verdict="CAPACITY_FAIL")
    a1 = _record(verdict="CAPACITY_FAIL", expandable=True)
    assert alloc.event_verdict(a0, a1) == alloc.EVENT_CAPACITY_FAIL


def test_the_event_verdict_vocabulary_is_closed():
    assert set(alloc.EVENT_VERDICTS) == {
        "CAPACITY_PASS", "CAPACITY_FAIL", "CONTROL_PASS_CONFUND_FOUND",
        "COMPARISON_INVALID", "IMPLEMENTATION_DEFECT"}
    for name in alloc.EVENT_VERDICTS:
        assert name in DOC


def test_the_oom_message_is_parsed_into_numbers():
    parsed = alloc.parse_oom("CUDA out of memory. Tried to allocate 550.00 MiB. "
                             "GPU 0 has a total capacity of 23.52 GiB of which "
                             "108.75 MiB is free.")
    assert parsed == {"oom_request_mib": 550.0, "oom_free_mib": 108.75}
    assert alloc.parse_oom("") == {"oom_request_mib": None, "oom_free_mib": None}


def test_a_gigabyte_sized_request_is_scaled():
    parsed = alloc.parse_oom("Tried to allocate 1.50 GiB. 2.00 GiB is free.")
    assert parsed == {"oom_request_mib": 1536.0, "oom_free_mib": 2048.0}


# ── 조건부: 실행 후 산출물 ────────────────────────────────────────────
@pytest.mark.skipif(not A0_PATH.is_file(), reason="A0 미실행")
def test_the_control_artifact_carries_the_frozen_request():
    record = json.loads(A0_PATH.read_text(encoding="utf-8"))
    assert record["arm"] == "A0"
    assert record["allocator_env_observed"] == ""
    assert "expandable_segments" not in json.dumps(
        record["preflight"]["environment"])
    assert record["requested"]["attn_implementation"] == "sdpa"
    assert record["gpu_idle_before"]["compute_process_count"] == 0


@pytest.mark.skipif(not A1_PATH.is_file(), reason="A1 미실행 (사전등록 규칙)")
def test_the_treatment_artifact_carries_the_applied_allocator():
    record = json.loads(A1_PATH.read_text(encoding="utf-8"))
    assert record["arm"] == "A1"
    assert record["allocator_env_observed"] == "expandable_segments:True"
    assert record["allocator_observed"]["expandable_segments_observed"] is True
    assert record["comparability_gate_mib"] == 128


@pytest.mark.skipif(A1_PATH.is_file() or not A0_PATH.is_file(),
                    reason="A1이 실행된 경우엔 해당 없음")
def test_a_passing_control_leaves_the_treatment_unrun():
    record = json.loads(A0_PATH.read_text(encoding="utf-8"))
    if record["arm_verdict"] == alloc.ARM_PASS:
        assert record["a1_status"] == alloc.A1_NOT_RUN
        assert record["event_verdict"] == alloc.EVENT_CONTROL_PASS
