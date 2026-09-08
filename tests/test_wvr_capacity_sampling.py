"""WVR_CAPACITY_SAMPLING_V1 계약 (2026-09-08 · WVR-S01~S16).

```
유일한 변경   fps 0.5 → 0.25 (150프레임 · 0,4,…,596)
allocator     default로 복귀 (A1 treatment를 물려받지 않는다)
해상도         512×288 동결 — 384×216은 32 격자를 만족하지 않는다
PASS 후에도   event extraction 금지 · semantic 판정 금지
```
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_alloc as alloc
import wvr_contract as contract
import wvr_sampling as sampling

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/preregistration/WVR_CAPACITY_SAMPLING_V1_2026-09-08.md"
RUNNER = ROOT / "scripts/wvr_capacity_sampling.py"
A0_PATH = ROOT / "runs/wvr_light_v1/capacity_alloc_A0.json"
B_PATH = ROOT / "runs/wvr_light_v1/capacity_sampling_B.json"
REPORT = ROOT / "docs/probes/WVR_CAPACITY_SAMPLING_V1_2026-09-08.md"
CHUNK = {"chunk_id": "C01", "start_sec": 0.0, "end_sec": 600.0}


def _runner():
    spec = importlib.util.spec_from_file_location("wvr_capacity_sampling",
                                                  RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wvr_capacity_sampling"] = module
    spec.loader.exec_module(module)
    return module


runner = _runner()
DOC = PREREG.read_text(encoding="utf-8")


def _control():
    return json.loads(A0_PATH.read_text(encoding="utf-8"))


def _arm(control=None, *, verdict="PASS", frames=150, fps=0.25,
         input_tokens=12663):
    """B arm 산출물 모양의 표본. control에서 파생해 단일 변경만 넣는다."""
    import copy

    record = copy.deepcopy(control or _control())
    record["verdict"] = verdict
    record["requested"]["chunk_fps"] = fps
    metrics = record["metrics"]
    metrics.update({
        "delivered_frame_count": frames, "requested_timestamps": frames,
        "frame_times_first_last": [0.0, 596.0],
        "video_token_count": frames // 2 * 144,
        "input_token_count": input_tokens,
        "oom": verdict == "CAPACITY_FAIL",
        "generation_completed": verdict == "PASS",
        "finish_reason": "EOS" if verdict == "PASS" else None,
        "generated_token_count": 640 if verdict == "PASS" else None,
    })
    return record


# ── WVR-S01 사전등록 ───────────────────────────────────────────────────
def test_wvr_s01_the_preregistration_is_committed():
    assert PREREG.is_file()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_CAPACITY_SAMPLING_V1_2026-09-08.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert tracked.returncode == 0, "사전등록이 커밋되지 않았다"


# ── WVR-S02 표집 ──────────────────────────────────────────────────────
def test_wvr_s02_the_sampling_is_the_preregistered_one():
    assert sampling.SAMPLING_FPS == 0.25
    assert sampling.SAMPLING_MAX_FRAMES == 150
    stamps = sampling.sampling_frames(CHUNK)
    assert len(stamps) == 150
    assert (stamps[0], stamps[1], stamps[-1]) == (0.0, 4.0, 596.0)
    assert contract.CHUNK_FPS == 0.5          # C01 동결값은 그대로다


def test_the_expected_counts_are_labelled_as_calculations():
    assert sampling.EXPECTED_FRAMES == 150
    assert sampling.EXPECTED_VIDEO_TOKENS == 10800
    assert "사전 계산 (판정 아님)" in DOC
    assert "이 계산을 결과로 쓰지 않는다" in DOC


# ── WVR-S03 해상도 동결 ───────────────────────────────────────────────
def test_wvr_s03_the_resolution_is_frozen():
    assert (sampling.FRAME_WIDTH, sampling.FRAME_HEIGHT) == (512, 288)
    cell = contract.PATCH_SIZE * contract.MERGE_SIZE
    assert sampling.FRAME_WIDTH % cell == 0
    assert sampling.FRAME_HEIGHT % cell == 0
    record = _arm()
    record["requested"]["frame_size"] = [384, 216]
    with pytest.raises(sampling.SamplingError):
        sampling.assert_resolution_frozen(record)
    assert sampling.assert_resolution_frozen(_arm()) is None


def test_the_invalid_resolution_is_corrected_in_the_documents():
    assert "216 / 32 = 6.75" in DOC
    probe_doc = (ROOT / "docs/probes/WVR_LIGHT_V1_CAPACITY_C01_2026-09-08.md"
                 ).read_text(encoding="utf-8")
    assert "384×216은 잘못이다" in probe_doc
    assert 216 % (contract.PATCH_SIZE * contract.MERGE_SIZE) != 0


# ── WVR-S04 allocator 복귀 ────────────────────────────────────────────
def test_wvr_s04_an_expandable_allocator_is_refused():
    assert sampling.assert_default_allocator({}) == ""
    with pytest.raises(sampling.SamplingError):
        sampling.assert_default_allocator(
            {"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})


# ── WVR-S05 · S06 parent control ──────────────────────────────────────
def test_wvr_s05_s06_the_control_must_exist_and_have_failed():
    source = RUNNER.read_text(encoding="utf-8")
    assert "capacity_alloc_A0.json" in source
    assert "parent control(A0) 산출물이 없다" in source
    assert "parent control이 CAPACITY_FAIL이 아니다" in source
    assert alloc.arm_verdict(_control()) == alloc.ARM_FAIL


# ── WVR-S07 단일 변경 ─────────────────────────────────────────────────
def test_wvr_s07_only_the_sampling_may_differ():
    control = _control()
    assert sampling.single_change(control, _arm(control)) == ()


@pytest.mark.parametrize("path,value", [
    (("requested", "dtype"), "float16"),
    (("requested", "attn_implementation"), "flash_attention_2"),
    (("requested", "quantization"), "8bit"),
    (("requested", "max_new_tokens"), 256),
    (("requested", "frame_size"), [384, 224]),
    (("requested", "do_resize"), True),
])
def test_a_second_change_is_a_violation(path, value):
    control = _control()
    arm = _arm(control)
    arm[path[0]][path[1]] = value
    assert "%s.%s" % path in sampling.single_change(control, arm)


def test_a_changed_prompt_or_chunk_is_a_violation():
    control = _control()
    arm = _arm(control)
    arm["chunk"] = {"chunk_id": "C02", "start_sec": 480.0, "end_sec": 1080.0}
    assert "chunk" in sampling.single_change(control, arm)
    other = _arm(control)
    other["prompt_hashes"] = {"EVENT_PROMPT_V1": "0" * 64}
    assert "prompt_hashes" in sampling.single_change(control, other)


# ── WVR-S08 표집이 실제로 줄었는지 ────────────────────────────────────
def test_wvr_s08_an_unchanged_sampling_is_not_an_experiment():
    control = _control()
    assert sampling.sampling_changed(control, _arm(control)) is True
    assert sampling.sampling_changed(control, _arm(control, frames=300)) is False
    assert sampling.sampling_changed(control,
                                     _arm(control, fps=0.5)) is False


def test_the_token_reduction_is_reported_from_measurements():
    control = _control()
    reduction = sampling.token_reduction(control, _arm(control))
    assert reduction["video_tokens"] == [21600, 10800]
    assert reduction["video_token_delta"] == -10800
    assert reduction["input_token_delta"] == 12663 - 23463


# ── WVR-S09 완주 정의 ─────────────────────────────────────────────────
def test_wvr_s09_a_pass_requires_a_completed_generation():
    control = _control()
    arm = _arm(control)
    assert alloc.arm_verdict(arm) == alloc.ARM_PASS
    arm["metrics"]["generation_completed"] = False
    assert alloc.arm_verdict(arm) == alloc.ARM_DEFECT


# ── WVR-S10 · S11 실행 계약 ───────────────────────────────────────────
def test_wvr_s10_s11_the_arm_runs_once_on_an_idle_gpu():
    with pytest.raises(alloc.AllocError):
        alloc.assert_once(True, sampling.ARM_B)
    with pytest.raises(alloc.AllocError):
        alloc.assert_idle({"compute_process_count": 2})
    source = RUNNER.read_text(encoding="utf-8")
    assert "assert_once" in source and "assert_idle" in source
    for forbidden in ("retry", "fallback", "while True", "device_map=",
                      "load_in_8bit", "load_in_4bit"):
        assert forbidden not in source


# ── WVR-S12 · S13 다음 단계로 넘어가지 않는다 ─────────────────────────
def test_wvr_s12_s13_the_next_stages_stay_closed():
    assert runner.EVENT_EXTRACTION_APPROVED is False
    assert runner.SEMANTIC_EVALUATION_ENABLED is False
    assert "EVENT_EXTRACTION_APPROVED = False" in DOC
    assert "capacity와 의미 밀도는 다른 질문이다" in DOC
    assert '"0.25 fps가 충분하다"' in DOC


# ── WVR-S14 기존 자산 ─────────────────────────────────────────────────
@pytest.mark.parametrize("path", [
    "runs/wvr_light_v1/capacity_C01.json",
    "runs/wvr_light_v1/capacity_alloc_A0.json",
    "runs/wvr_light_v1/capacity_alloc_A1.json",
    "runs/quality_candidate/report_quality.hwpx",
])
def test_wvr_s14_the_earlier_artifacts_are_unchanged(path):
    done = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path],
                          cwd=str(ROOT))
    assert done.returncode == 0, "%s이 변경됐다" % path


# ── 조건부: 실행 후 ───────────────────────────────────────────────────
@pytest.mark.skipif(not B_PATH.is_file(), reason="B 미실행")
def test_the_artifact_records_the_single_change():
    record = json.loads(B_PATH.read_text(encoding="utf-8"))
    assert record["arm"] == "B"
    assert record["requested"]["chunk_fps"] == 0.25
    assert record["requested"]["frame_size"] == [512, 288]
    assert record["allocator_env_observed"] == ""
    assert record["allocator_observed"]["expandable_segments_observed"] is False
    assert record["single_change_violations"] == []
    assert record["sampling_changed"] is True
    assert record["metrics"]["delivered_frame_count"] == 150
    assert record["parent_control"]["verdict"] == "CAPACITY_FAIL"


@pytest.mark.skipif(not B_PATH.is_file(), reason="B 미실행")
@pytest.mark.parametrize("field", [
    "baseline_vram_mib", "post_load_vram_mib", "peak_vram_allocated_mib",
    "peak_vram_reserved_mib", "device_peak_used_mib", "input_token_count",
    "video_token_count",
])
def test_wvr_s15_the_report_quotes_the_json(field):
    record = json.loads(B_PATH.read_text(encoding="utf-8"))
    assert REPORT.is_file(), "보고서가 없다"
    assert format(record["metrics"][field], ",") in REPORT.read_text(
        encoding="utf-8")


@pytest.mark.skipif(not B_PATH.is_file(), reason="B 미실행")
def test_wvr_s16_the_calculation_is_not_presented_as_a_measurement():
    record = json.loads(B_PATH.read_text(encoding="utf-8"))
    assert record["expected_video_tokens"] == 10800          # 계산값 표기
    assert "expected_video_tokens" in record
    text = REPORT.read_text(encoding="utf-8")
    assert "계산" in text
