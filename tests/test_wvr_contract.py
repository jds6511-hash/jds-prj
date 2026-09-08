"""WHOLE_VIDEO_REPORT_LIGHT_V1 계약 동결 (2026-09-08 · WVR-C01~C24).

```
사전등록 문서의 표 == 코드의 값        (한쪽만 고치면 실패한다)
chunk·표집은 결정적                    (같은 길이 → 같은 계획)
OOM만 CAPACITY_FAIL                    나머지는 IMPLEMENTATION_DEFECT
```

GPU 없이 잰다 — torch·av는 함수 안에서만 import되므로 이 파일은 그것들을
불러오지 않는다.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import wvr_contract as contract
import wvr_prompts as prompts

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/preregistration/WHOLE_VIDEO_REPORT_LIGHT_V1_2026-09-08.md"
SCRIPT = ROOT / "scripts/wvr_capacity_probe.py"
DURATION = 2424.186485

FROZEN_PLAN = (
    ("C01", 0.0, 600.0), ("C02", 480.0, 1080.0), ("C03", 960.0, 1560.0),
    ("C04", 1440.0, 2040.0), ("C05", 1920.0, 2424.186),
)


def _probe():
    spec = importlib.util.spec_from_file_location("wvr_capacity_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wvr_capacity_probe"] = module
    spec.loader.exec_module(module)
    return module


probe = _probe()
DOC = PREREG.read_text(encoding="utf-8")


# ── WVR-C01~C04 계약 8종 ────────────────────────────────────────────────
def test_wvr_c01_there_are_exactly_eight_contracts():
    assert prompts.CONTRACT_COUNT == 8
    assert len(prompts.CONTRACTS) == 8
    assert "계약은 **8개**다" in DOC


@pytest.mark.parametrize("name", sorted(prompts.CONTRACTS))
def test_wvr_c02_the_document_table_matches_the_module(name):
    """문서의 hash 표와 본문이 어긋나면 실패한다 — 한쪽만 고칠 수 없다."""
    row = re.search(r"^%s\s+([0-9a-f]{64})$" % name, DOC, re.M)
    assert row, "사전등록 문서에 %s 행이 없다" % name
    assert row.group(1) == prompts.contract_hash(name)


TEXT_ONLY = ("EVENT_MERGE_PROMPT_V1", "CHAPTER_PROMPT_V1",
             "HIGHLIGHT_PROMPT_V1", "OVERVIEW_PROMPT_V1",
             "ANALYSIS_PROMPT_V1", "CONCLUSION_PROMPT_V1")


@pytest.mark.parametrize("name", TEXT_ONLY)
def test_wvr_c03_the_downstream_contracts_get_no_frames(name):
    body = prompts.CONTRACTS[name]
    assert "주어지지 않는다" in body


@pytest.mark.parametrize("name", ("SPARSE_GLOBAL_PROMPT_V1",
                                  "EVENT_PROMPT_V1"))
def test_the_two_video_contracts_read_frames(name):
    body = prompts.CONTRACTS[name]
    assert "프레임" in body
    assert "주어지지 않는다" not in body


@pytest.mark.parametrize("name", sorted(prompts.CONTRACTS))
def test_wvr_c04_every_contract_carries_the_common_rules(name):
    body = prompts.CONTRACTS[name]
    assert prompts.COMMON_RULES in body
    assert "한국어로만 쓴다" in body
    assert "소리·대사·자막은 입력에 없으므로 말하지 않는다" in body


# ── WVR-C05~C09 청킹 ───────────────────────────────────────────────────
def test_wvr_c05_the_chunk_plan_is_the_frozen_table():
    plan = contract.chunk_plan(DURATION)
    assert tuple((c["chunk_id"], c["start_sec"], c["end_sec"]) for c in plan) \
        == FROZEN_PLAN


@pytest.mark.parametrize("chunk_id,start,end", FROZEN_PLAN)
def test_the_document_states_the_same_chunk_rows(chunk_id, start, end):
    row = re.search(r"^%s\s+([0-9.]+)\s+–\s+([0-9.]+)" % chunk_id, DOC, re.M)
    assert row, "사전등록 문서에 %s 행이 없다" % chunk_id
    assert float(row.group(1)) == start
    assert float(row.group(2)) == end


def test_wvr_c06_no_tail_chunk_is_fully_covered_by_its_predecessor():
    plan = contract.chunk_plan(DURATION)
    for left, right in zip(plan, plan[1:]):
        assert right["end_sec"] > left["end_sec"]


def test_wvr_c07_the_window_constants_are_the_preregistered_ones():
    assert contract.CHUNK_LENGTH_SEC == 600.0
    assert contract.CHUNK_OVERLAP_SEC == 120.0
    assert contract.CHUNK_STRIDE_SEC == 480.0


def test_wvr_c08_every_overlap_is_the_preregistered_two_minutes():
    pairs = contract.overlap_pairs(contract.chunk_plan(DURATION))
    assert len(pairs) == 4
    for pair in pairs:
        assert pair["overlap_end"] - pair["overlap_start"] == 120.0


def test_wvr_c09_a_zero_length_video_is_refused():
    with pytest.raises(contract.ContractError):
        contract.chunk_plan(0.0)


# ── WVR-C10~C14 표집 ───────────────────────────────────────────────────
def test_wvr_c10_the_first_chunk_yields_three_hundred_stamps():
    stamps = contract.chunk_frames(contract.chunk_plan(DURATION)[0])
    assert len(stamps) == 300
    assert stamps[0] == 0.0 and stamps[-1] == 598.0
    assert stamps[1] - stamps[0] == 2.0


def test_wvr_c11_the_sparse_pass_yields_the_documented_count():
    stamps = contract.sparse_frames(DURATION)
    assert len(stamps) == 122
    assert stamps[1] - stamps[0] == 20.0
    assert stamps[-1] < DURATION
    assert "122프레임" in DOC


def test_wvr_c12_exceeding_the_frame_cap_raises_instead_of_truncating():
    with pytest.raises(contract.ContractError):
        contract.frame_timestamps(0.0, 600.0, contract.CHUNK_FPS, 299)


def test_wvr_c13_the_frame_size_fits_the_processor_grid():
    cell = contract.PATCH_SIZE * contract.MERGE_SIZE          # 32 픽셀
    assert contract.FRAME_WIDTH % cell == 0
    assert contract.FRAME_HEIGHT % cell == 0
    assert contract.FRAME_WIDTH * 9 == contract.FRAME_HEIGHT * 16   # 16:9
    assert (contract.FRAME_WIDTH, contract.FRAME_HEIGHT) == (512, 288)


def test_wvr_c14_the_processor_may_not_resample_or_resize_again():
    assert contract.DO_SAMPLE_FRAMES is False
    assert contract.DO_RESIZE is False


# ── WVR-C15~C17 video-only 입력 ────────────────────────────────────────
@pytest.mark.parametrize("banned", [
    "raw_stt", "sanitized_stt", "stt_utterances", "stt_transcript",
    "episode_summary", "aar_canonical", "existing_report", "submission_hwpx",
    "human_report", "youtube_title", "youtube_description",
    "manual_annotation", "caption",
])
def test_wvr_c15_a_forbidden_channel_is_refused(banned):
    with pytest.raises(contract.ContractError):
        contract.assert_video_only_inputs({"frames": [], banned: "x"})


def test_wvr_c16_a_prefixed_or_suffixed_forbidden_key_is_still_refused():
    with pytest.raises(contract.ContractError):
        contract.assert_video_only_inputs({"prior_episode_summary_v2": 1})
    with pytest.raises(contract.ContractError):
        contract.assert_video_only_inputs(["CAPTION_TEXT"])


def test_wvr_c17_a_video_only_payload_passes():
    assert contract.assert_video_only_inputs(
        {"frames": [], "chunk": {}, "video_metadata": {}}) is None


# ── WVR-C18~C22 probe 규율 ─────────────────────────────────────────────
def test_wvr_c18_only_the_first_chunk_is_approved():
    assert probe.APPROVED_CHUNK_ID == "C01"
    assert probe.FULL_PIPELINE_APPROVED is False
    assert probe.approved_chunk(DURATION)["end_sec"] == 600.0


def test_wvr_c19_only_an_oom_is_a_capacity_verdict():
    class FakeOOM(Exception):
        pass

    assert probe.classify_error(FakeOOM(), (FakeOOM,)) == "CAPACITY_FAIL"
    assert probe.classify_error(ValueError(), (FakeOOM,)) \
        == "IMPLEMENTATION_DEFECT"
    assert probe.classify_error(FakeOOM(), (None,)) == "IMPLEMENTATION_DEFECT"


def test_wvr_c20_the_probe_never_shrinks_the_chunk_to_succeed():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("retry", "fallback", "while True", "CHUNK_LENGTH_SEC ="):
        assert forbidden not in source
    # 자기 주석에 걸리지 않게 구체적 호출 인자만 본다
    assert "device_map=" not in source
    assert "offload_folder" not in source
    assert "offload_state_dict" not in source
    assert "max_memory=" not in source


def test_wvr_c21_a_failed_run_is_still_written_with_every_metric(tmp_path):
    out = tmp_path / "deep" / "capacity_C01.json"
    probe.write_record({"verdict": "IMPLEMENTATION_DEFECT"}, out)
    record = json.loads(out.read_text(encoding="utf-8"))
    for name in probe.REQUIRED_METRICS:
        assert name in record["metrics"]


def test_wvr_c22_the_probe_uses_the_frozen_event_contract(tmp_path):
    chunk = probe.approved_chunk(DURATION)
    text = probe.build_prompt(chunk)
    assert "start_sec=0.0 end_sec=600.0" in text
    assert prompts.COMMON_RULES in text
    assert probe.SEMANTIC_RESULT == "NOT_EVALUATED"


# ── WVR-C23·C24 실패 정책 ──────────────────────────────────────────────
def test_wvr_c23_the_stage_statuses_name_capacity_failure():
    assert contract.STAGE_CAPACITY_FAIL in contract.STAGE_STATUSES
    assert contract.STAGE_PARSE_FAILURE in contract.STAGE_STATUSES
    assert contract.STAGE_CONTRACT_VIOLATION in contract.STAGE_STATUSES


def test_wvr_c24_the_document_forbids_the_shrink_retry():
    assert "동일 사건에서 8분·5분으로 자동 재시도 금지" in DOC
    assert "SUBMISSION_PROMOTION             HOLD" in DOC
    assert "OFFICIAL TEST                    UNOPENED" in DOC
