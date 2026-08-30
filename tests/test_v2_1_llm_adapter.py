"""B-02a LLM adapter contract — 모델 없이 호출 경계만 시험한다.

티켓: Gate B / B-02a

```
invoke → raw persist → parse → merge
```

fake generator는 **모델의 의미 품질을 흉내내지 않는다.** 호출 경계에서 무엇이
어떻게 분류되는지만 본다. 실제 모델 실행은 B-02b(서버)다.

```
generator 예외        MODEL_FAILURE      raw 없음
깨진 raw              PARSE_CONTRACT_FAILURE   raw 보존
빈 출력               EMPTY              raw 보존
정상 summary          VALID_PARSE        raw 보존
```
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_episode import build_episodes
from v2_1_fixtures import scenario
from v2_1_llm_adapter import (
    GenerationConfig,
    invoke_episode,
)
from v2_1_parse import (
    EMPTY,
    MODEL_FAILURE,
    PARSE_CONTRACT_FAILURE,
    VALID_PARSE,
    SegmentRegistry,
)
from v2_1_prompt import PROMPT_VERSION, build_episode_prompt, contract_hash
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_scan import code_only
from v2_1_timeline import build_timeline

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_llm_adapter.py"

CONFIG = GenerationConfig(model_id="Qwen/Qwen2.5-7B-Instruct")
GOOD = json.dumps({"summary": "짐을 챙겨 자리를 옮긴다.",
                   "dialogue_note": "다음 장소를 정한다.",
                   "stt_cites": [9]}, ensure_ascii=False)


@pytest.fixture
def world(tmp_path):
    s = scenario("S1")
    store = RawStore(tmp_path / "raw", run_id="run-001", video_id="S1")
    judged = {}
    for source_type, channel in (("asr", s.asr), ("vlm", s.caption)):
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    timeline = build_timeline(s.segments, judged)
    episodes = build_episodes([(0, 5), (6, 11)], s.segments, timeline=timeline)
    registry = SegmentRegistry(s.segments)
    bundle = build_episode_prompt(episodes[1], timeline, store)
    return store, registry, episodes[1], bundle


def _invoke(world, generate, config=CONFIG):
    store, registry, episode, bundle = world
    return invoke_episode(generate, episode, bundle, store, registry, config=config)


# ── 상태 분류 ────────────────────────────────────────────────────────────
def test_valid_output_becomes_content(world):
    invocation = _invoke(world, lambda prompt: GOOD)
    assert invocation.result.content_status == VALID_PARSE
    assert invocation.result.content.summary == "짐을 챙겨 자리를 옮긴다."


def test_generator_exception_is_model_failure(world):
    def broken(prompt):
        raise RuntimeError("CUDA out of memory")

    invocation = _invoke(world, broken)
    assert invocation.result.content_status == MODEL_FAILURE
    assert "CUDA" in invocation.result.error
    assert invocation.result.error_type == "RuntimeError"


def test_malformed_output_is_a_parse_contract_failure(world):
    invocation = _invoke(world, lambda prompt: '{"summary": "잘린')
    assert invocation.result.content_status == PARSE_CONTRACT_FAILURE


def test_empty_output_is_empty_not_a_failure(world):
    invocation = _invoke(world, lambda prompt: "   ")
    assert invocation.result.content_status == EMPTY


def test_model_failure_is_not_a_parse_failure(world):
    def broken(prompt):
        raise TimeoutError("no response")

    assert _invoke(world, broken).result.content_status != PARSE_CONTRACT_FAILURE


@pytest.mark.parametrize("kind", ["raises", "malformed", "blank"])
def test_structure_survives_every_failure(world, kind):
    """호출마다 새 world를 쓴다 — 같은 구간에 두 번 저장하는 것은 계약 위반이다."""
    generate = {
        "raises": lambda p: (_ for _ in ()).throw(RuntimeError("x")),
        "malformed": lambda p: '{"a":',
        "blank": lambda p: "",
    }[kind]
    invocation = _invoke(world, generate)
    assert invocation.result.episode.episode_id == "EP02"
    assert invocation.result.episode.support_span == {"start_seg": 6, "end_seg": 11}
    assert invocation.result.content is None


# ── raw-before-parse ─────────────────────────────────────────────────────
def test_raw_is_stored_before_parsing(world):
    store, registry, episode, bundle = world
    seen = {}

    def generate(prompt):
        return GOOD

    invocation = _invoke(world, generate)
    assert store.load("llm", 6).read_text() == GOOD
    assert invocation.raw_ref == "llm:000006"


def test_raw_survives_a_parse_failure(world):
    store, registry, episode, bundle = world
    _invoke(world, lambda prompt: '{"summary": "잘린')
    assert store.load("llm", 6).read_text() == '{"summary": "잘린'


def test_raw_is_byte_exact(world):
    store, registry, episode, bundle = world
    payload = '  {"summary": "요약"}\r\n '
    _invoke(world, lambda prompt: payload)
    assert store.load("llm", 6).read_bytes() == payload.encode("utf-8")


def test_a_generator_exception_leaves_no_raw(world):
    """호출 자체가 실패하면 저장할 raw가 없다 — 빈 파일을 만들지 않는다."""
    store, registry, episode, bundle = world

    def broken(prompt):
        raise RuntimeError("boom")

    invocation = _invoke(world, broken)
    assert invocation.raw_ref is None
    assert not [r for r in store.records() if r.source_type == "llm"]


def test_invoke_precedes_parse_in_source():
    body = SRC.read_text(encoding="utf-8").split("def invoke_episode", 1)[1]
    assert body.index("generate(") < body.index("store_then_parse")


def test_no_second_raw_store_is_created():
    code = code_only(SRC)
    assert "RawStore(" not in code, "두 번째 raw store를 만들었다"


def test_llm_raw_uses_the_declared_source_type():
    code = code_only(SRC)
    assert '"llm"' in code


# ── 프롬프트 provenance ──────────────────────────────────────────────────
def test_prompt_version_and_hash_are_recorded(world):
    invocation = _invoke(world, lambda prompt: GOOD)
    assert invocation.prompt_version == PROMPT_VERSION
    assert invocation.prompt_hash == contract_hash()


def test_the_prompt_text_is_what_the_generator_receives(world):
    store, registry, episode, bundle = world
    seen = {}

    def generate(prompt):
        seen["prompt"] = prompt
        return GOOD

    _invoke(world, generate)
    assert seen["prompt"] == bundle.text


def test_provenance_is_recorded_in_the_raw_metadata(world):
    store, registry, episode, bundle = world
    _invoke(world, lambda prompt: GOOD)
    record = store.load("llm", 6)
    assert record.producer == "Qwen/Qwen2.5-7B-Instruct"
    assert "do_sample=False" in record.producer_version


# ── generation config를 가장하지 않는다 ──────────────────────────────────
def test_decoding_is_declared_not_implied():
    """SPEC §22의 temperature=0을 transformers에서 그대로 주장하지 않는다."""
    assert CONFIG.do_sample is False
    assert "temperature" not in CONFIG.as_dict()


def test_config_signature_is_stable_and_explicit():
    assert CONFIG.signature() == GenerationConfig(
        model_id="Qwen/Qwen2.5-7B-Instruct").signature()
    assert "do_sample=False" in CONFIG.signature()
    assert "max_new_tokens=" in CONFIG.signature()


def test_sampling_config_changes_the_signature():
    sampled = GenerationConfig(model_id="Qwen/Qwen2.5-7B-Instruct", do_sample=True)
    assert sampled.signature() != CONFIG.signature()


def test_model_id_is_required():
    with pytest.raises(ValueError, match="model_id"):
        GenerationConfig(model_id="  ")


def test_invocation_records_the_model_id(world):
    assert _invoke(world, lambda p: GOOD).model_id == "Qwen/Qwen2.5-7B-Instruct"


# ── 파생 필드 채택 금지 ──────────────────────────────────────────────────
def test_model_supplied_derived_fields_are_not_adopted(world):
    hijack = json.dumps({"summary": "요약", "episode_id": "EP99",
                         "support_span": {"start_seg": 0, "end_seg": 11},
                         "source": "stt"}, ensure_ascii=False)
    invocation = _invoke(world, lambda prompt: hijack)
    assert invocation.result.episode.episode_id == "EP02"
    assert invocation.result.episode.support_span == {"start_seg": 6, "end_seg": 11}
    assert invocation.result.episode.anchor_cites == [6, 8, 11]
    assert "episode_id" in invocation.result.ignored_fields


# ── B-02a는 모델을 올리지 않는다 ─────────────────────────────────────────
def test_b02a_does_not_load_a_model():
    code = code_only(SRC)
    for forbidden in ("transformers", "torch", "AutoModel", "from_pretrained",
                      "cuda", "make_llm"):
        assert forbidden not in code, "B-02b 책임을 침범했다: " + forbidden


def test_b02a_does_not_build_prompts_or_ground():
    code = code_only(SRC)
    for forbidden in ("build_episode_prompt", "validate_grounding", "anchors_in"):
        assert forbidden not in code, "다른 계층을 끌어왔다: " + forbidden


def test_b02a_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
