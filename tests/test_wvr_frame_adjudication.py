"""FRAME_ADJUDICATION_V1 계약 (2026-09-09 · WVR-F01~F20).

```
추론 없음   torch·transformers를 import조차 하지 않는다
프레임      모델이 받은 것과 같은 512×288 · KEEP·DROP은 부모 창 격자로 결정
아님        GT 라벨 작성이 아니다 — dev·test 라벨·질의에 쓰지 않는다
판정        네 값 · 우선순위 동결(불충분 → DROP material → 생성 오류 → KEEP 충분)
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
import wvr_frame_adjudication as fa
import wvr_short_window as sw

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/preregistration/WVR_FRAME_ADJUDICATION_V1_2026-09-09.md"
BUILDER = ROOT / "scripts/wvr_frame_packet.py"
RUNS = ROOT / "runs/wvr_light_v1"
MANIFEST = RUNS / "frame_adjudication_manifest.json"
PACKET = RUNS / "frame_adjudication_packet.md"


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _module(BUILDER, "wvr_frame_packet")


# ── WVR-F01~F05 동결 ────────────────────────────────────────────────
def test_wvr_f01_the_preregistration_is_committed():
    done = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_FRAME_ADJUDICATION_V1_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_f02_the_three_questions_are_frozen():
    observed = tuple((row["question_id"], row["parent_window"],
                      row["start_sec"], row["end_sec"]) for row in fa.QUESTIONS)
    assert observed == (("Q1", "P2", 448.0, 464.0),
                        ("Q2", "P3", 104.0, 128.0),
                        ("Q3", "P3", 128.0, 144.0))


def test_wvr_f03_the_probe_declares_no_inference_and_no_label_use():
    assert fa.NEW_INFERENCE_ALLOWED is False
    assert fa.GT_LABEL_USE_ALLOWED is False
    assert fa.SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED is False
    assert fa.EVENT_EXTRACTION_APPROVED is False
    source = BUILDER.read_text(encoding="utf-8")
    for banned in ("import torch", "import transformers", "from transformers"):
        assert banned not in source


def test_wvr_f04_the_frame_geometry_matches_what_the_model_received():
    assert (fa.FRAME_WIDTH, fa.FRAME_HEIGHT) == (contract.FRAME_WIDTH,
                                                 contract.FRAME_HEIGHT) == \
        (512, 288)
    assert fa.STEP_SEC == 1.0 / density.REFERENCE_FPS == 2.0
    assert fa.KEEP_PERIOD_SEC == 4.0


def test_wvr_f05_the_scope_is_stated_and_narrow():
    assert "일반화하지 않는다" in fa.ALLOWED_SCOPE
    text = PREREG.read_text(encoding="utf-8")
    assert "dev·test 라벨" in text or "dev/test 라벨" in text


# ── WVR-F06~F12 프레임 파생 ─────────────────────────────────────────
def test_wvr_f06_frame_counts_match_the_preregistration():
    for question in fa.QUESTIONS:
        rows = fa.frame_rows(question)
        fa.assert_expected_counts(question["question_id"], rows)
    assert fa.EXPECTED_FRAME_COUNTS == {"Q1": {"KEEP": 4, "DROP": 4},
                                        "Q2": {"KEEP": 6, "DROP": 6},
                                        "Q3": {"KEEP": 4, "DROP": 4}}
    short = fa.frame_rows(fa.QUESTIONS[0])[:-1]
    with pytest.raises(fa.FrameAdjudicationError):
        fa.assert_expected_counts("Q1", short)


def test_wvr_f07_keep_and_drop_are_decided_by_the_parent_grid():
    rows = fa.frame_rows(fa.QUESTIONS[0])          # P2 448–464 (부모 416)
    assert fa.keep_times(rows) == (448.0, 452.0, 456.0, 460.0)
    assert fa.drop_times(rows) == (450.0, 454.0, 458.0, 462.0)

    # 질문 start가 KEEP 격자에 없을 때 — 부모 격자로 판정해야 한다
    offset = fa.frame_rows({"question_id": "QX", "parent_window": "P2",
                            "start_sec": 450.0, "end_sec": 458.0})
    assert fa.keep_times(offset) == (452.0, 456.0)
    assert fa.drop_times(offset) == (450.0, 454.0)


def test_wvr_f08_keep_frames_are_exactly_the_reduced_arm_inputs():
    for question in fa.QUESTIONS:
        rows = fa.frame_rows(question)
        fa.assert_keep_matches_s1(question, rows)
        parent = fa.parent_window(question)
        s1 = set(sw.arm_timestamps(parent, sw.ARM_S1))
        s0 = set(sw.arm_timestamps(parent, sw.ARM_S0))
        assert set(fa.keep_times(rows)) <= s1
        assert set(fa.drop_times(rows)) <= s0 - s1


def test_wvr_f09_a_mislabelled_frame_is_refused_in_both_directions():
    question = dict(fa.QUESTIONS[0])
    rows = fa.frame_rows(question)
    rows[1]["role"] = fa.KEEP                      # 450.0은 DROP이어야 한다
    with pytest.raises(fa.FrameAdjudicationError):
        fa.assert_keep_matches_s1(question, rows)

    swapped = fa.frame_rows(question)
    swapped[0]["role"] = fa.DROP                   # 448.0은 KEEP이어야 한다
    with pytest.raises(fa.FrameAdjudicationError):
        fa.assert_keep_matches_s1(question, swapped)


def test_wvr_f10_a_span_outside_the_parent_window_is_refused():
    with pytest.raises(fa.FrameAdjudicationError):
        fa.frame_rows({"question_id": "QX", "parent_window": "P2",
                       "start_sec": 400.0, "end_sec": 448.0})


def test_wvr_f11_frames_stay_inside_the_half_open_span():
    for question in fa.QUESTIONS:
        rows = fa.frame_rows(question)
        assert rows[0]["time_sec"] == question["start_sec"]
        assert rows[-1]["time_sec"] < question["end_sec"]
        assert rows[-1]["time_sec"] == question["end_sec"] - fa.STEP_SEC


def test_wvr_f12_the_tested_span_is_the_reviewer_named_total():
    total = sum(row["end_sec"] - row["start_sec"] for row in fa.QUESTIONS)
    assert total == 56.0


# ── WVR-F13~F17 판정 ───────────────────────────────────────────────
def test_wvr_f13_the_frame_verdict_vocabulary_is_exactly_four():
    assert fa.FRAME_VERDICTS == (
        "DROP_FRAMES_CARRY_MATERIAL_INFORMATION", "KEEP_FRAMES_SUFFICIENT",
        "GENERATION_ERROR_NOT_SAMPLING", "FRAMES_INSUFFICIENT")
    with pytest.raises(fa.FrameAdjudicationError):
        fa.question_verdict_valid("PASS")


def test_wvr_f14_insufficient_frames_outrank_everything():
    assert fa.probe_verdict([fa.FRAMES_INSUFFICIENT, fa.DROP_MATERIAL,
                             fa.GENERATION_ERROR]) == fa.PROBE_INCONCLUSIVE


def test_wvr_f15_drop_material_outranks_generation_error():
    assert fa.probe_verdict([fa.KEEP_SUFFICIENT, fa.DROP_MATERIAL,
                             fa.GENERATION_ERROR]) == fa.PROBE_SAMPLING_LOSS


def test_wvr_f16_generation_error_is_reachable_without_sampling_loss():
    assert fa.probe_verdict([fa.KEEP_SUFFICIENT, fa.GENERATION_ERROR,
                             fa.KEEP_SUFFICIENT]) == fa.PROBE_GENERATION_ERROR
    assert fa.probe_verdict([fa.KEEP_SUFFICIENT] * 3) == \
        fa.PROBE_KEEP_SUFFICIENT


def test_wvr_f17_all_three_questions_must_be_judged():
    with pytest.raises(fa.FrameAdjudicationError):
        fa.probe_verdict([fa.KEEP_SUFFICIENT, fa.KEEP_SUFFICIENT])
    assert fa.CLAIM_MATCHES == ("S0_CLAIM_MATCHES", "S1_CLAIM_MATCHES",
                                "BOTH_MATCH_PARTIALLY", "NEITHER_MATCHES")


# ── WVR-F18~F20 packet 조립 ────────────────────────────────────────
def test_wvr_f18_claims_come_verbatim_from_the_frozen_artifacts():
    claims = builder.claims_for(RUNS, fa.QUESTIONS[1])      # P3 104–128
    assert set(claims) == set(sw.ARMS)
    frozen = json.loads((RUNS / "short_window_P3_S1.json").read_text(
        encoding="utf-8"))["parsed"]["collapsed"]
    for row in claims[sw.ARM_S1]:
        assert row in frozen
    assert all(float(row["start_sec"]) < 128.0 and float(row["end_sec"]) > 104.0
               for rows in claims.values() for row in rows)


def test_wvr_f19_the_builder_checks_frame_size_and_count():
    from PIL import Image

    source = BUILDER.read_text(encoding="utf-8")
    assert "assert_keep_matches_s1" in source
    assert "assert_expected_counts" in source

    rows = fa.frame_rows(fa.QUESTIONS[0])
    good = [Image.new("RGB", (fa.FRAME_WIDTH, fa.FRAME_HEIGHT))
            for _ in rows]
    builder.check_frames(good, rows, "Q1")

    with pytest.raises(builder.PacketError, match="개수|맞지 않는다"):
        builder.check_frames(good[:-1], rows, "Q1")

    wrong = list(good)
    wrong[2] = Image.new("RGB", (384, 216))
    with pytest.raises(builder.PacketError, match="크기"):
        builder.check_frames(wrong, rows, "Q1")


requires_packet = pytest.mark.skipif(not MANIFEST.is_file(),
                                     reason="frame packet 미생성")


@requires_packet
def test_wvr_f20_the_manifest_records_every_frame_with_a_hash():
    record = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert record["event"] == fa.EVENT
    assert record["frame_size"] == [512, 288]
    assert record["new_inference_allowed"] is False
    assert record["gt_label_use_allowed"] is False
    assert len(record["questions"]) == 3
    for row in record["questions"]:
        expected = fa.EXPECTED_FRAME_COUNTS[row["question_id"]]
        assert row["counts"] == expected
        assert len(row["frames"]) == expected["KEEP"] + expected["DROP"]
        for frame in row["frames"]:
            assert len(frame["sha256"]) == 64
            assert (RUNS / builder.FRAME_DIR_NAME / frame["file"]).is_file()
        assert (RUNS / builder.FRAME_DIR_NAME / row["sheet"]).is_file()
