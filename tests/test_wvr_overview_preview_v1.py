"""Minimal safety contract for WVR_OVERVIEW_PREVIEW_V1."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import wvr_overview_preview_v1 as ov

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs/wvr_light_v1"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(ROOT / "scripts/wvr_overview_preview_run.py", "ovpreview_runner")
builder = _module(ROOT / "scripts/wvr_overview_preview_build.py", "ovpreview_builder")
DOCUMENT = json.loads((RUNS / ov.SOURCE_MAP_NAME).read_text(encoding="utf-8"))
INPUT = ov.build_generation_input(DOCUMENT)


def _events(region):
    if region["region_class"] == "STITCHABLE":
        return [event for group in region["groups"] for event in group["events"]]
    if region["region_class"] == "SINGLE_SOURCE":
        return region["observations"]
    return []


def _valid_payload(source=INPUT):
    stitch = next(row for row in source["regions"]
                  if row["region_class"] == "STITCHABLE")
    conflict = next(row for row in source["regions"]
                    if row["region_class"] == "CONFLICT")
    block = conflict["blocks"][0]
    stitch_event = _events(stitch)[0]["event_id"]
    arm_a = block["observation_sets"]["A"][0]["event_id"]
    arm_b = block["observation_sets"]["B"][0]["event_id"]
    return {
        "short_overview": [
            {"sentence_id": "S01", "text": "관찰 가능한 구간에서는 주요 활동이 이어진다.",
             "claim_ids": ["OVC01"]},
            {"sentence_id": "S02", "text": "중간에는 세부 관찰이 엇갈리는 활동도 나타난다.",
             "claim_ids": ["OVC02"]},
            {"sentence_id": "S03", "text": "이후에도 큰 활동 흐름이 계속된다.",
             "claim_ids": ["OVC01"]},
        ],
        "detailed_overview": [
            {"paragraph_id": "D01",
             "text": "관찰된 범위에서 활동이 순서대로 이어지며, 일부 구간은 세부 관찰이 달라 넓은 수준으로만 설명할 수 있다.",
             "claim_ids": ["OVC01", "OVC02"]},
        ],
        "claim_trace": [
            {"claim_id": "OVC01", "claim": "주요 활동이 이어진다.",
             "support_type": "STITCHABLE",
             "source_event_ids": [stitch_event],
             "source_regions": [stitch["region_id"]]},
            {"claim_id": "OVC02", "claim": "세부 관찰이 엇갈린다.",
             "support_type": "CONFLICT_COMMON_DENOMINATOR",
             "source_event_ids": [arm_a, arm_b],
             "source_regions": [conflict["region_id"]]},
        ],
    }


def test_preview_input_is_the_frozen_map_without_track_a_or_w00():
    assert ov.SOURCE_MAP_SHA256 == \
        "0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c"
    assert INPUT["source_event_count"] == 160
    assert len(INPUT["regions"]) == 11
    assert [row["region_id"] for row in INPUT["regions"]] \
        == ["R%02d" % index for index in range(1, 12)]
    text = json.dumps(INPUT, ensure_ascii=False)
    for forbidden in ("W00", "source_window", "preferred_source",
                      "winner", "track_a", "caption", "stt"):
        assert forbidden.lower() not in text.lower()


def test_unresolved_opening_has_no_observation_and_conflicts_keep_two_arms():
    opening = INPUT["regions"][0]
    assert opening == {"region_id": "R01", "region_class": "UNRESOLVED",
                       "status": "NO_OBSERVATION", "observations": []}
    conflicts = [row for row in INPUT["regions"]
                 if row["region_class"] == "CONFLICT"]
    assert conflicts
    for region in conflicts:
        assert region["blocks"]
        for block in region["blocks"]:
            assert set(block["observation_sets"]) == {"A", "B"}
            assert all(block["observation_sets"].values())


def test_prompt_and_runtime_are_frozen_for_one_korean_generation():
    prompt = ov.render_prompt(INPUT)
    assert ov.sha256_text(ov.PROMPT_TEMPLATE) == ov.PROMPT_TEMPLATE_SHA256
    assert "한국어" in prompt
    assert "3~5" in prompt and "1~3" in prompt
    assert ov.LLM_MODEL_ID == "Qwen/Qwen2.5-7B-Instruct"
    assert ov.LLM_MODEL_REVISION == "a09a35458c702b33eeacc393d103063234e8bc28"
    assert ov.LLM_MAX_NEW_TOKENS == 4096
    assert ov.LLM_DO_SAMPLE is False


def test_valid_overview_and_claim_trace_parse():
    parsed = ov.parse_and_validate(json.dumps(_valid_payload()), INPUT)
    assert len(parsed["short_overview"]) == 3
    assert len(parsed["detailed_overview"]) == 1
    assert len(parsed["claim_trace"]) == 2


def test_every_overview_unit_needs_a_valid_claim_trace():
    payload = _valid_payload()
    payload["short_overview"][0]["claim_ids"] = ["OVC99"]
    with pytest.raises(ov.PreviewError, match="CLAIM_TRACE"):
        ov.parse_and_validate(json.dumps(payload), INPUT)


def test_claim_sources_must_be_valid_and_cannot_use_unresolved_r01():
    payload = _valid_payload()
    payload["claim_trace"][0]["source_event_ids"] = ["invented-event"]
    with pytest.raises(ov.PreviewError, match="CLAIM_SOURCE"):
        ov.parse_and_validate(json.dumps(payload), INPUT)
    payload = _valid_payload()
    payload["claim_trace"][0]["source_regions"] = ["R01"]
    with pytest.raises(ov.PreviewError, match="UNRESOLVED"):
        ov.parse_and_validate(json.dumps(payload), INPUT)


def test_conflict_claim_must_cite_both_opaque_observation_arms():
    payload = _valid_payload()
    payload["claim_trace"][1]["source_event_ids"] = \
        payload["claim_trace"][1]["source_event_ids"][:1]
    with pytest.raises(ov.PreviewError, match="CONFLICT_COMMON_DENOMINATOR"):
        ov.parse_and_validate(json.dumps(payload), INPUT)


def test_overview_rejects_analysis_conclusion_and_opening_invention():
    for poison in ("영상의 의도를 분석한다.", "결론적으로 좋은 결과다.",
                   "영상은 시작부터 음식을 준비한다."):
        payload = _valid_payload()
        payload["short_overview"][0]["text"] = poison
        with pytest.raises(ov.PreviewError, match="ROLE_OR_OPENING"):
            ov.parse_and_validate(json.dumps(payload), INPUT)


def _factory(calls):
    def factory(runtime):
        assert runtime["max_new_tokens"] == 4096

        def generate(prompt):
            calls.append(prompt)
            return json.dumps(_valid_payload(), ensure_ascii=False)

        generate.provenance = {
            "effective_model_id": ov.LLM_MODEL_ID,
            "effective_model_revision": ov.LLM_MODEL_REVISION,
            "effective_dtype": "torch.bfloat16",
            "attn_implementation": "sdpa",
            "effective_quantized": False,
        }
        generate.runtime_metrics = lambda: {
            "cuda_available": True, "device_count": 1,
            "device_names": ["NVIDIA GeForce RTX 4090"],
            "max_memory_allocated_bytes": 100,
            "max_memory_reserved_bytes": 200,
        }
        return generate
    return factory


def test_runner_persists_prompt_and_raw_before_separate_parse(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / ov.SOURCE_MAP_NAME).write_bytes((RUNS / ov.SOURCE_MAP_NAME).read_bytes())
    calls = []
    record = runner.run(runs, _factory(calls))
    assert len(calls) == 1
    assert record["inference_count"] == 1
    assert record["raw_persisted_before_parse"] is True
    assert record["parsed_here"] is False
    assert (runs / ov.PROMPT_NAME).is_file()
    assert (runs / ov.RAW_NAME).is_file()
    assert not (runs / ov.RESULT_NAME).exists()
    with pytest.raises(runner.RunError, match="already exists"):
        runner.run(runs, _factory([]))
    result = builder.build(runs)
    assert result["short_overview"][0]["text"]
    assert (runs / ov.RESULT_NAME).is_file()
    assert (runs / ov.PACKET_NAME).is_file()


def test_submission_is_unchanged_and_preview_opens_no_other_generation():
    assert ov.sha256_file(SUBMISSION) == ov.SUBMISSION_SHA256
    assert ov.NEW_VLM_INFERENCE_ALLOWED is False
    assert ov.TRACK_A_INPUT_ALLOWED is False
    assert ov.ANALYSIS_ALLOWED is False
    assert ov.CONCLUSION_ALLOWED is False
    assert ov.HWPX_ALLOWED is False
