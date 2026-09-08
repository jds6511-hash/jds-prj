"""WVR_SAMPLING_SEMANTIC_DENSITY_V1 계약 (2026-09-08 · WVR-D01~D15).

```
Stage 1   화면 변화 측정 — 의미 판정 아님 · 모델 없음
부분집합   0.25fps ⊂ 0.5fps 를 코드로 잠근다
창 선택    Stage 1 점수만 · 동률은 이른 창
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
import wvr_density_prompt as diag

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT
          / "docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md")
STAGE1 = ROOT / "scripts/wvr_density_stage1.py"
B_PATH = ROOT / "runs/wvr_light_v1/capacity_sampling_B.json"
RESULT = ROOT / "runs/wvr_light_v1/density_stage1.json"
REPORT = ROOT / "docs/probes/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md"


def _stage1():
    spec = importlib.util.spec_from_file_location("wvr_density_stage1", STAGE1)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wvr_density_stage1"] = module
    spec.loader.exec_module(module)
    return module


stage1 = _stage1()
DOC = PREREG.read_text(encoding="utf-8")


# ── WVR-D01 사전등록 ───────────────────────────────────────────────────
def test_wvr_d01_the_preregistration_is_committed():
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert tracked.returncode == 0, "사전등록이 커밋되지 않았다"


# ── WVR-D02~D04 부분집합 ──────────────────────────────────────────────
def test_wvr_d02_keep_and_drop_partition_the_reference():
    reference = density.reference_timestamps()
    keep, drop = density.keep_drop(reference)
    assert len(reference) == 300
    assert len(keep) == 150 and len(drop) == 150
    assert set(keep) | set(drop) == set(reference)
    assert not set(keep) & set(drop)
    assert (keep[0], keep[1], keep[-1]) == (0.0, 4.0, 596.0)
    assert (drop[0], drop[1], drop[-1]) == (2.0, 6.0, 598.0)


def test_wvr_d03_the_keep_set_is_what_the_b_arm_actually_used():
    keep, _ = density.keep_drop()
    record = json.loads(B_PATH.read_text(encoding="utf-8"))
    assert record["metrics"]["delivered_frame_count"] == len(keep)
    assert record["metrics"]["frame_times_first_last"] == [keep[0], keep[-1]]
    assert record["requested"]["chunk_fps"] == density.DENSITY_FPS


def test_wvr_d04_a_timestamp_outside_the_reference_is_refused():
    keep, _ = density.keep_drop()
    assert density.assert_subset(keep, keep) is None
    with pytest.raises(density.DensityError):
        density.assert_subset(keep, list(keep[:-1]) + [1.0])
    with pytest.raises(density.DensityError):
        density.assert_subset(keep, keep[:10])


# ── WVR-D05 novelty ──────────────────────────────────────────────────
def test_wvr_d05_novelty_is_the_minimum_of_both_neighbours():
    assert density.novelty(10.0, 2.0) == 2.0
    assert density.novelty(2.0, 10.0) == 2.0
    assert density.novelty(None, 7.5) == 7.5
    with pytest.raises(density.DensityError):
        density.novelty(None, None)


def test_the_neighbours_are_the_surrounding_keep_frames():
    keep, drop = density.keep_drop()
    assert density.neighbours(2.0, keep) == (0.0, 4.0)
    assert density.neighbours(598.0, keep) == (596.0, None)


def test_the_change_metrics_are_deterministic():
    left = bytes([0, 0, 0, 0])
    right = bytes([10, 10, 10, 10])
    assert density.luma_diff(left, left) == 0.0
    assert density.luma_diff(left, right) == 10.0
    assert density.histogram_distance(density.histogram(left),
                                      density.histogram(left)) == 0.0
    assert density.histogram_distance(density.histogram(left),
                                      density.histogram(right)) == 1.0
    with pytest.raises(density.DensityError):
        density.luma_diff(left, bytes([1]))


# ── WVR-D06 · D07 창 ─────────────────────────────────────────────────
def test_wvr_d06_the_windows_are_the_preregistered_ones():
    windows = density.windows()
    assert len(windows) == 15
    assert density.WINDOW_SEC == 180.0 and density.WINDOW_STRIDE_SEC == 30.0
    assert windows[0]["start_sec"] == 0.0 and windows[-1]["start_sec"] == 420.0
    keep, drop = density.keep_drop()
    for window in windows:
        counts = density.window_frames(window, keep, drop)
        assert len(counts["reference"]) == 90
        assert len(counts["keep"]) == 45
        assert len(counts["drop"]) == 45


def test_wvr_d07_the_selection_uses_the_score_only():
    scored = [{"window_id": "W01", "start_sec": 0.0, "score": 5.0},
              {"window_id": "W02", "start_sec": 30.0, "score": 9.0},
              {"window_id": "W03", "start_sec": 60.0, "score": 1.0}]
    chosen = density.select_windows(scored)
    assert chosen["D1_highest_change"]["window_id"] == "W02"
    assert chosen["D3_lowest_change"]["window_id"] == "W03"
    assert chosen["D2_median_change"]["window_id"] == "W01"


def test_a_tie_picks_the_earlier_window():
    scored = [{"window_id": "W02", "start_sec": 30.0, "score": 9.0},
              {"window_id": "W01", "start_sec": 0.0, "score": 9.0},
              {"window_id": "W03", "start_sec": 60.0, "score": 1.0}]
    chosen = density.select_windows(scored)
    assert chosen["D1_highest_change"]["window_id"] == "W02"   # 최대는 늦은 창
    assert chosen["D2_median_change"]["window_id"] == "W01"     # 동률은 이른 창


def test_the_window_score_only_counts_frames_inside():
    window = {"window_id": "W01", "start_sec": 0.0, "end_sec": 180.0}
    assert density.window_score(window, [(0.0, 1.0), (179.9, 2.0),
                                         (180.0, 100.0)]) == 3.0


# ── WVR-D08 임계값 없음 ──────────────────────────────────────────────
def test_wvr_d08_the_distribution_has_no_threshold_verdict():
    values = [float(index) for index in range(101)]
    report = density.distribution(values)
    assert set(report) == {"count", "min", "median", "p75", "p90", "p95",
                           "max", "mean"}
    assert report["median"] == 50.0 and report["p95"] == 95.0
    # 자기 문서 문구에 걸리지 않게 코드 구성만 본다
    source = (ROOT / "src/wvr_density.py").read_text(encoding="utf-8")
    for forbidden in ("THRESHOLD =", "def is_significant", "def has_change",
                      "SEMANTIC_SUFFICIENCY ="):
        assert forbidden not in source


# ── WVR-D09 · D10 Stage 경계 ─────────────────────────────────────────
def test_wvr_d09_stage1_never_touches_a_model():
    source = STAGE1.read_text(encoding="utf-8")
    for forbidden in ("Qwen3VLForConditionalGeneration", "AutoProcessor",
                      "generate(", "torch.cuda", "cuda:0"):
        assert forbidden not in source
    assert "probe.sample_frames" in source        # 같은 프레임을 쓴다


def test_wvr_d10_stage2_and_the_report_path_stay_closed():
    assert stage1.STAGE2_APPROVED is False
    assert stage1.EVENT_EXTRACTION_APPROVED is False
    assert "별도 승인 필요" in DOC


# ── WVR-D11 진단 프롬프트 ────────────────────────────────────────────
def test_wvr_d11_the_diagnostic_prompt_is_not_a_production_contract():
    assert diag.IS_PRODUCTION_CONTRACT is False
    assert diag.prompt_hash() in DOC
    import wvr_prompts as production
    assert diag.DIAG_CONTRACT_NAME not in production.CONTRACTS
    assert production.CONTRACT_COUNT == 8
    assert "보고서를 쓰지 않는다" in diag.SAMPLING_DIAG_PROMPT_V1


def test_the_diagnostic_prompt_keeps_the_language_and_evidence_rules():
    body = diag.SAMPLING_DIAG_PROMPT_V1
    assert "한국어로만 쓴다" in body
    assert "소리·대사·자막은 입력에 없으므로 말하지 않는다" in body
    assert "억지로 항목을 채우지 않는다" in body


# ── WVR-D12 · D13 어휘 ───────────────────────────────────────────────
def test_wvr_d12_two_match_tolerances_are_frozen():
    assert density.MATCH_TOLERANCE_SEC == (4.0, 8.0)
    assert "MATCH_TOLERANCE_SEC = (4.0, 8.0)" in DOC


def test_wvr_d13_the_reference_is_not_called_truth():
    assert density.STAGE1 == "VISUAL_TEMPORAL_COVERAGE"
    assert density.STAGE2 == "PAIRED_OUTPUT_SENSITIVITY"
    assert "0.5fps는 영상의 truth가 아니다" in DOC
    assert "SEMANTIC_SUFFICIENCY라고 부르지 않는다" in DOC
    assert "ground truth로 부르지 않는다" in DOC


# ── WVR-D14 기존 자산 ────────────────────────────────────────────────
@pytest.mark.parametrize("path", [
    "runs/wvr_light_v1/capacity_C01.json",
    "runs/wvr_light_v1/capacity_alloc_A0.json",
    "runs/wvr_light_v1/capacity_alloc_A1.json",
    "runs/wvr_light_v1/capacity_sampling_B.json",
    "runs/quality_candidate/report_quality.hwpx",
])
def test_wvr_d14_the_earlier_artifacts_are_unchanged(path):
    done = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path],
                          cwd=str(ROOT))
    assert done.returncode == 0, "%s이 변경됐다" % path


# ── 조건부: Stage 1 실행 후 ──────────────────────────────────────────
@pytest.mark.skipif(not RESULT.is_file(), reason="Stage 1 미실행")
def test_the_stage1_artifact_records_the_subset_relation():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    sampling = record["sampling"]
    assert record["stage"] == "VISUAL_TEMPORAL_COVERAGE"
    assert sampling["reference_frames"] == 300
    assert sampling["keep_frames"] == 150 and sampling["drop_frames"] == 150
    assert sampling["keep_first_last"] == [0.0, 596.0]
    assert sampling["frame_size"] == [contract.FRAME_WIDTH,
                                      contract.FRAME_HEIGHT]
    assert len(record["rows"]) == 150
    assert len(record["windows"]) == 15
    assert record["stage2_approved"] is False


@pytest.mark.skipif(not RESULT.is_file(), reason="Stage 1 미실행")
def test_the_selected_windows_match_the_recorded_scores():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    recomputed = density.select_windows(record["windows"])
    for label in density.SELECTION_LABELS:
        assert record["selection"][label]["window_id"] \
            == recomputed[label]["window_id"]


@pytest.mark.skipif(not RESULT.is_file() or not REPORT.is_file(),
                    reason="Stage 1 또는 보고서 미실행")
@pytest.mark.parametrize("field", ["median", "p90", "p95", "max"])
def test_wvr_d15_the_report_quotes_the_json(field):
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    value = record["distribution"]["luma_novelty"][field]
    assert str(value) in REPORT.read_text(encoding="utf-8")
