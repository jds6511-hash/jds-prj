"""Minimal body-quality contract for WVR_OVERVIEW_PREVIEW_V2."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import wvr_overview_preview_v2 as ov

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs/wvr_light_v1"


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(ROOT / "scripts/wvr_overview_preview_v2_run.py", "ovpreview_v2_runner")
builder = _module(ROOT / "scripts/wvr_overview_preview_v2_build.py", "ovpreview_v2_builder")
DOCUMENT = json.loads((RUNS / ov.SOURCE_MAP_NAME).read_text(encoding="utf-8"))
INPUT = ov.build_generation_input(DOCUMENT)


VALID_RAW = """SHORT OVERVIEW

관찰 가능한 구간에서는 음식을 준비하고 조리하는 활동이 이어진다.
이후 완성된 음식을 먹는 장면으로 흐름이 바뀐다.
그다음에는 천을 다루고 바느질하는 활동이 진행된다.
후반에는 선물을 포장하고 옷을 갈아입은 뒤 바깥으로 이동한다.

DETAILED OVERVIEW

관찰 가능한 앞부분에는 음식을 준비하고 조리하는 과정이 이어진다. 이후에는 완성된 음식을 먹는 활동으로 전환된다.

중후반에는 천을 다루고 바느질하는 활동이 진행된다. 후반에는 선물을 포장하고 옷을 갈아입은 뒤 바깥으로 이동하는 흐름이 나타난다.
"""


def _factory(calls, raw=VALID_RAW):
    def factory(runtime):
        assert runtime["max_new_tokens"] == 4096
        assert runtime["do_sample"] is False

        def generate(prompt):
            calls.append(prompt)
            return raw

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


def test_v2_uses_same_frozen_map_and_text_only_runtime():
    assert ov.SOURCE_MAP_SHA256 == \
        "0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c"
    assert INPUT["source_event_count"] == 160
    assert len(INPUT["regions"]) == 11
    assert INPUT["regions"][0] == {
        "region_id": "R01", "region_class": "UNRESOLVED",
        "status": "NO_OBSERVATION", "observations": []}
    assert ov.LLM_MODEL_ID == "Qwen/Qwen2.5-7B-Instruct"
    assert ov.LLM_MODEL_REVISION == "a09a35458c702b33eeacc393d103063234e8bc28"
    assert ov.LLM_DO_SAMPLE is False
    assert ov.LLM_MAX_NEW_TOKENS == 4096
    assert ov.NEW_VLM_INFERENCE_ALLOWED is False
    assert ov.TRACK_A_INPUT_ALLOWED is False


def test_prompt_requires_broad_phases_and_only_plain_body_output():
    prompt = ov.render_prompt(INPUT)
    assert ov.sha256_text(ov.PROMPT_TEMPLATE) == ov.PROMPT_TEMPLATE_SHA256
    for phrase in ("broad activity phase", "정확히 4문장", "정확히 2개 단락",
                   "event 수", "Observation Set A", "Observation Set B"):
        assert phrase in prompt
    for forbidden in ("claim_id", "source_event_ids", "support_type",
                      "claim trace", '"short_overview"'):
        assert forbidden.lower() not in ov.PROMPT_TEMPLATE.lower()


def test_parser_accepts_exact_four_sentences_and_two_paragraphs():
    result = ov.parse_and_validate(VALID_RAW)
    assert len(result["short_sentences"]) == 4
    assert len(result["detailed_paragraphs"]) == 2
    assert all(2 <= ov.sentence_count(row) <= 4
               for row in result["detailed_paragraphs"])


@pytest.mark.parametrize("raw, match", [
    (VALID_RAW.replace("그다음에는 천을 다루고 바느질하는 활동이 진행된다.\n", ""),
     "SHORT_COUNT"),
    (VALID_RAW.replace("\n\n중후반에는", "\n중후반에는"), "DETAILED_COUNT"),
    (VALID_RAW.replace("음식을 준비하고", "치약을 볶고", 1), "LOCAL_DETAIL"),
    (VALID_RAW + "\nclaim trace: OVC01", "OUTPUT_FORMAT"),
])
def test_parser_rejects_unstable_body_contract(raw, match):
    with pytest.raises(ov.PreviewError, match=match):
        ov.parse_and_validate(raw)


def test_runner_calls_once_saves_raw_then_builder_parses(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / ov.SOURCE_MAP_NAME).write_bytes((RUNS / ov.SOURCE_MAP_NAME).read_bytes())
    calls = []
    record = runner.run(runs, _factory(calls))
    assert len(calls) == 1
    assert record["inference_count"] == 1
    assert record["retry_count"] == 0
    assert record["raw_persisted_before_parse"] is True
    assert record["parsed_here"] is False
    assert (runs / ov.RAW_NAME).read_text(encoding="utf-8") == VALID_RAW
    assert not (runs / ov.RESULT_NAME).exists()
    with pytest.raises(runner.RunError, match="already exists"):
        runner.run(runs, _factory([]))
    result = builder.build(runs)
    assert len(result["short_sentences"]) == 4
    assert len(result["detailed_paragraphs"]) == 2
    assert (runs / ov.PACKET_NAME).read_text(encoding="utf-8").startswith(
        "SHORT OVERVIEW")
