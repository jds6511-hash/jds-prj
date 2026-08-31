"""B-03 episode prompt builder + version/hash.

티켓: Gate B / B-03
규격: SPEC §13 — 모델에게 요구하는 것은 `summary` 하나

이 티켓은 **어느 모델에 보낼지와 무관하다.** 모델 호출·로딩·생성 파라미터는
B-02 소관이고 여기에 들어오면 안 된다.

근거 분리가 핵심이다.

```
claim_evidence          usable_for_claims == true
context_only_evidence   preserved == true AND usable_for_claims == false
```

같은 목록에 `usable=false` 플래그만 붙이면 모델이 옆문으로 인용한다. 블록 자체를
나눈다. 기본값은 context-only를 **아예 넣지 않는 것**이다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_episode import MODEL_FIELDS, build_episodes
from v2_1_fixtures import BOILERPLATE, EXCITED_SPEECH, scenario
from v2_1_prompt import (
    CONTRACT,
    PROMPT_VERSION,
    PromptError,
    build_episode_prompt,
    contract_hash,
    split_evidence,
)
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_scan import code_only
from v2_1_timeline import build_timeline

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_prompt.py"


@pytest.fixture
def stocked(tmp_path):
    """S1 채널을 raw store에 넣고 timeline·episode까지 세운다."""
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
    return store, timeline, episodes


# ── version / hash ───────────────────────────────────────────────────────
def test_prompt_version_is_declared():
    """v1 → v2: OPEN-10 자리표시자 제거로 계약이 바뀌었다."""
    assert PROMPT_VERSION == "episode_content_v2"


def test_hash_is_stable_across_calls():
    assert contract_hash() == contract_hash()
    assert re.fullmatch(r"[0-9a-f]{64}", contract_hash())


def test_hash_covers_the_contract_not_the_episode(stocked):
    """에피소드가 달라도 계약이 같으면 hash가 같다."""
    store, timeline, episodes = stocked
    first = build_episode_prompt(episodes[0], timeline, store)
    second = build_episode_prompt(episodes[1], timeline, store)
    assert first.prompt_hash == second.prompt_hash == contract_hash()
    assert first.text != second.text


def test_hash_input_is_exactly_the_contract():
    """모델·실행 시각·run id가 섞이면 "언제 프롬프트가 바뀌었나"를 못 쫓는다.

    소스에서 단어를 찾는 대신 해시 자체를 재현해 입력을 못 박는다.
    """
    import hashlib

    payload = json.dumps(CONTRACT, ensure_ascii=False, sort_keys=True)
    assert contract_hash() == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_hash_changes_when_the_contract_changes():
    changed = json.loads(json.dumps(CONTRACT))
    changed["output"]["required"] = ["summary", "title"]
    assert contract_hash(changed) != contract_hash()


def test_hash_is_order_independent():
    reordered = {k: CONTRACT[k] for k in reversed(list(CONTRACT))}
    assert contract_hash(reordered) == contract_hash()


def test_bundle_carries_version_and_hash(stocked):
    store, timeline, episodes = stocked
    bundle = build_episode_prompt(episodes[0], timeline, store)
    assert bundle.prompt_version == PROMPT_VERSION
    assert bundle.prompt_hash == contract_hash()


# ── LLM-002 출력 계약은 최소 ─────────────────────────────────────────────
def test_llm_002_required_output_is_summary_only():
    assert CONTRACT["output"]["required"] == ["summary"]
    assert CONTRACT["output"]["optional"] == ["dialogue_note", "stt_cites"]


def test_llm_002_contract_fields_match_the_episode_schema():
    declared = CONTRACT["output"]["required"] + CONTRACT["output"]["optional"]
    assert tuple(declared) == MODEL_FIELDS


def test_llm_002_prompt_does_not_ask_for_derived_fields(stocked):
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[0], timeline, store).text
    for banned in ("episode_id", "support_span", "anchor_cites", "start_sec",
                   "end_sec", "segment_ids", "title", "key_actions", "actors",
                   "importance", "uncertainty_note"):
        assert banned not in text, "모델에게 파생 필드를 요구한다: " + banned


# ── OPEN-10 자리표시자 복사 (2026-08-31 B-02b 실측) ──────────────────────
def test_open_10_no_copyable_literal_placeholder(stocked):
    """모델이 예시의 자리표시자를 그대로 베꼈다 — dialogue_note = "선택".

    복사할 문자열을 아예 두지 않는다. 키 이름과 설명만 남긴다.
    """
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[0], timeline, store).text
    assert not re.search(r'"(?:summary|dialogue_note)"\s*:\s*"[^"]+"', text)


def test_open_10_optional_fields_are_omitted_not_filled(stocked):
    """빈 값을 넣으라고 하면 빈 값 자체가 내용처럼 남는다."""
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[0], timeline, store).text
    assert "넣지 않는다" in text


def test_open_10_the_three_keys_are_still_named(stocked):
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[0], timeline, store).text
    for key in ("summary", "dialogue_note", "stt_cites"):
        assert key in text


def test_llm_002_prompt_states_the_output_shape(stocked):
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[0], timeline, store).text
    assert "summary" in text
    assert "dialogue_note" in text and "stt_cites" in text


# ── 근거 분리 ────────────────────────────────────────────────────────────
def test_claim_and_context_evidence_are_split_by_eligibility(stocked):
    store, timeline, episodes = stocked
    claim, context = split_evidence(episodes[0], timeline)
    assert claim and context
    assert all(ref.usable_for_claims for ref in claim)
    assert all(ref.preserved and not ref.usable_for_claims for ref in context)


def test_context_only_evidence_is_excluded_by_default(stocked):
    """가장 안전한 기본값은 보여주지 않는 것이다."""
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[0], timeline, store).text
    assert BOILERPLATE not in text


def test_context_only_can_be_included_but_stays_in_its_own_block(stocked):
    store, timeline, episodes = stocked
    bundle = build_episode_prompt(episodes[0], timeline, store,
                                  include_context_only=True)
    claim_block, context_block = _blocks(bundle.text)
    assert BOILERPLATE in context_block
    assert BOILERPLATE not in claim_block


def test_context_block_states_the_prohibition(stocked):
    store, timeline, episodes = stocked
    bundle = build_episode_prompt(episodes[0], timeline, store,
                                  include_context_only=True)
    _, context_block = _blocks(bundle.text)
    assert "근거로 쓸 수 없다" in context_block


def test_usable_speech_reaches_the_claim_block(stocked):
    store, timeline, episodes = stocked
    claim_block, _ = _blocks(
        build_episode_prompt(episodes[1], timeline, store).text
    )
    assert EXCITED_SPEECH in claim_block


def test_evidence_text_comes_from_the_raw_store(stocked):
    """텍스트 원본은 한 곳에만 있다 — timeline은 참조만 갖는다."""
    store, timeline, episodes = stocked
    store.load("asr", 8).raw_path.unlink()
    with pytest.raises(Exception):
        build_episode_prompt(episodes[1], timeline, store)


def test_cites_are_restricted_to_claim_evidence(stocked):
    store, timeline, episodes = stocked
    bundle = build_episode_prompt(episodes[1], timeline, store)
    assert "stt_cites" in bundle.text
    assert set(bundle.claim_cites) <= {r.segment_id for r in
                                       split_evidence(episodes[1], timeline)[0]}


def test_episode_without_usable_evidence_is_refused(stocked):
    """근거가 없으면 요약을 만들라고 시키지 않는다 — 환각의 입구다."""
    store, timeline, episodes = stocked
    s = scenario("S5")
    empty_store = RawStore(store.root.parent / "empty", run_id="r", video_id="S5")
    judged = {"asr": classify_channel(s.asr, "asr")}
    empty_timeline = build_timeline(s.segments, judged)
    empty_episodes = build_episodes([(0, 11)], s.segments, timeline=empty_timeline)
    with pytest.raises(PromptError, match="no usable evidence"):
        build_episode_prompt(empty_episodes[0], empty_timeline, empty_store)


# ── 결정성 ───────────────────────────────────────────────────────────────
def test_same_inputs_give_an_identical_prompt(stocked):
    store, timeline, episodes = stocked
    first = build_episode_prompt(episodes[0], timeline, store).text
    second = build_episode_prompt(episodes[0], timeline, store).text
    assert first == second


def test_evidence_is_ordered_by_segment(stocked):
    store, timeline, episodes = stocked
    claim_block, _ = _blocks(build_episode_prompt(episodes[1], timeline, store).text)
    cited = [int(n) for n in re.findall(r"seg#(\d+)", claim_block)]
    assert cited == sorted(cited)


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_b03_does_not_call_or_load_a_model():
    code = code_only(SRC)
    for forbidden in ("transformers", "ollama", "torch", "make_llm", "generate",
                      "temperature", "max_new_tokens"):
        assert forbidden not in code, "B-02 책임을 침범했다: " + forbidden


def test_b03_does_not_reimplement_gate_a():
    code = code_only(SRC)
    for forbidden in ("REPEAT_THRESHOLD", "classify", "window_spans",
                      "validate_partition"):
        assert forbidden not in code, "Gate A 기능을 다시 구현했다: " + forbidden


def _blocks(text):
    """claim 블록과 context 블록으로 가른다. 지시문 머리말은 뺀다."""
    head = text.split("[근거]", 1)[1]
    if "[참고]" in head:
        claim, context = head.split("[참고]", 1)
        return claim, "[참고]" + context
    return head, ""
