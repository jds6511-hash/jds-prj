"""Gate B P1 — LLM-006 · 007 · 010 의 **contract 수준** 확인.

여기서 확인하는 것은 하나뿐이다.

> 그 입력을 모델에게 **올바르게 전달할 수 있는가.**

아직 B-02(실제 adapter)가 없으므로 호출 후 `summary`가 raw store → parse → merge를
거쳐 정상적으로 돌아오는지는 확인할 수 없다. 그래서 이 파일이 green이어도 상태는
`CONTRACT PASS / B-02 integration pending`이지 `PASS`가 아니다.

```
LLM-006  no ASR case        ASR이 없다는 것만으로 insufficient가 되지 않는다
LLM-007  no caption case    caption이 없다는 것만으로 insufficient가 되지 않는다
LLM-010  rich dialogue      자격 있는 발화가 실제로 [근거] 블록에 들어간다
```

B-02가 생기면 같은 S1·S3·S4 fixture를 adapter integration test에 다시 태우고
그때 `PASS`로 승격한다.
"""
import pytest

from v2_1_episode import build_episodes
from v2_1_fixtures import EXCITED_SPEECH, scenario
from v2_1_prompt import PromptError, build_episode_prompt, split_evidence
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_timeline import build_timeline


def _world(tmp_path, name, spans):
    s = scenario(name)
    store = RawStore(tmp_path / name, run_id="run-001", video_id=name)
    judged = {}
    for source_type, channel in (("asr", s.asr), ("vlm", s.caption), ("ocr", s.ocr)):
        if not channel:
            continue
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    timeline = build_timeline(s.segments, judged)
    return store, timeline, build_episodes(list(spans), s.segments, timeline=timeline)


# ── LLM-006 no ASR case ──────────────────────────────────────────────────
def test_llm_006_caption_only_episode_still_has_claim_evidence(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S3", [(0, 11)])
    claim, _ = split_evidence(episodes[0], timeline)
    assert claim and all(ref.source_type == "vlm" for ref in claim)


def test_llm_006_caption_only_episode_builds_a_prompt(tmp_path):
    """ASR 부재 자체는 insufficient가 아니다."""
    store, timeline, episodes = _world(tmp_path, "S3", [(0, 11)])
    bundle = build_episode_prompt(episodes[0], timeline, store)
    assert "화면" in bundle.text
    assert bundle.claim_cites


def test_llm_006_caption_only_episode_source_is_visual(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S3", [(0, 11)])
    assert episodes[0].source == "visual"


# ── LLM-007 no caption case ──────────────────────────────────────────────
def test_llm_007_asr_only_episode_still_has_claim_evidence(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S4", [(0, 11)])
    claim, _ = split_evidence(episodes[0], timeline)
    assert claim and all(ref.source_type == "asr" for ref in claim)


def test_llm_007_asr_only_episode_builds_a_prompt(tmp_path):
    """caption 부재 자체는 insufficient가 아니다."""
    store, timeline, episodes = _world(tmp_path, "S4", [(0, 11)])
    bundle = build_episode_prompt(episodes[0], timeline, store)
    assert "발화" in bundle.text
    assert bundle.claim_cites


def test_llm_007_asr_only_episode_source_is_stt(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S4", [(0, 11)])
    assert episodes[0].source == "stt"


# ── 근거가 아예 없을 때는 요구하지 않는다 (LLM-008과의 경계) ─────────────
def test_an_episode_with_no_usable_evidence_is_still_refused(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S5", [(0, 11)])
    with pytest.raises(PromptError, match="no usable evidence"):
        build_episode_prompt(episodes[0], timeline, store)


# ── LLM-010 rich dialogue ────────────────────────────────────────────────
def test_llm_010_eligible_speech_reaches_the_evidence_block(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S1", [(6, 11)])
    bundle = build_episode_prompt(episodes[0], timeline, store)
    block = bundle.text.split("[근거]", 1)[1]
    assert EXCITED_SPEECH in block
    assert "여기 소스를 넣으면 돼." in block


def test_llm_010_ineligible_speech_does_not_reach_it(tmp_path):
    """풍부하다고 다 넣지 않는다 — 자격 없는 발화는 기본적으로 빠진다.

    S1 seg#0~5의 발화는 전부 boilerplate(SUSPECT)다. 캡션이 있어 프롬프트는
    만들어지지만 그 발화는 [근거] 블록에 들어가지 않는다.
    """
    from v2_1_fixtures import BOILERPLATE

    store, timeline, episodes = _world(tmp_path, "S1", [(0, 5)])
    bundle = build_episode_prompt(episodes[0], timeline, store)
    assert BOILERPLATE not in bundle.text
    assert all(ref.source_type == "vlm"
               for ref in split_evidence(episodes[0], timeline)[0])


def test_llm_010_speech_and_caption_are_labelled_separately(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S1", [(6, 11)])
    block = build_episode_prompt(episodes[0], timeline, store).text.split(
        "[근거]", 1)[1]
    assert "발화:" in block and "화면:" in block


def test_llm_010_cites_are_restricted_to_eligible_speech(tmp_path):
    store, timeline, episodes = _world(tmp_path, "S1", [(6, 11)])
    bundle = build_episode_prompt(episodes[0], timeline, store)
    claim, _ = split_evidence(episodes[0], timeline)
    assert set(bundle.claim_cites) == {ref.segment_id for ref in claim}


# ── 상태 표기 ────────────────────────────────────────────────────────────
def test_these_are_contract_level_not_integration(tmp_path):
    """이 파일은 모델을 부르지 않는다 — 그래서 PASS가 아니라 CONTRACT PASS다."""
    source = __doc__ or ""
    assert "CONTRACT PASS / B-02 integration pending" in source
