"""B-04 content 병합 + failure isolation.

티켓: Gate B / B-04
규격: SPEC §16 실패 의미론 — dialogue 하나가 실패했다고 Episode를 버리지 않는다

셋을 분리한다.

```
episode structure   canonical episode 자체 — 언제나 유지
content state       MODEL_FAILURE · PARSE_CONTRACT_FAILURE · EMPTY · VALID_PARSE
content payload     summary
```

모델이 죽어도 `episode_id` · 시간 · segment 소속 · 순서는 살아 있어야 한다.
반대로 `summary=""` 같은 값으로 실패를 정상 내용처럼 위장해서도 안 된다.

**grounding은 여기서 하지 않는다.** 근거 자격·named entity 검증은 B-05·B-06이다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_content import (
    EpisodeResult,
    merge_all,
    merge_content,
)
from v2_1_episode import build_episodes
from v2_1_fixtures import CANONICAL_PARTITION, scenario
from v2_1_parse import (
    EMPTY,
    MODEL_FAILURE,
    PARSE_CONTRACT_FAILURE,
    VALID_PARSE,
    SegmentRegistry,
    model_failure,
    parse_json_payload,
)
from v2_1_scan import code_only

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_content.py"


@pytest.fixture
def segments():
    return scenario("S1").segments


@pytest.fixture
def episodes(segments):
    return build_episodes(CANONICAL_PARTITION, segments)


@pytest.fixture
def registry(segments):
    return SegmentRegistry(segments)


def _parsed(registry, payload):
    return parse_json_payload(json.dumps(payload), registry)


# ── LLM-009 구조는 어떤 실패에도 살아남는다 ─────────────────────────────
def _structure(result):
    e = result.episode
    return (e.episode_id, e.start_seg, e.end_seg, e.start_sec, e.end_sec,
            tuple(e.anchor_cites), e.support_span["start_seg"], e.source)


def test_llm_009_model_failure_keeps_the_episode_structure(episodes):
    episode = episodes[0]
    result = merge_content(episode, model_failure(RuntimeError("CUDA out of memory")))
    assert result.content_status == MODEL_FAILURE
    assert result.content is None
    assert _structure(result) == _structure(EpisodeResult(episode, VALID_PARSE, None))


def test_llm_009_parse_failure_keeps_the_episode_structure(episodes, registry):
    result = merge_content(episodes[1], parse_json_payload('{"summary":', registry))
    assert result.content_status == PARSE_CONTRACT_FAILURE
    assert result.content is None
    assert result.episode.episode_id == "EP02"
    assert result.episode.anchor_cites == episodes[1].anchor_cites


def test_llm_009_every_episode_survives_a_partial_outage(episodes, registry):
    outcomes = [
        model_failure(RuntimeError("boom")),
        _parsed(registry, {"summary": "해변에서 소스를 넣는다."}),
        parse_json_payload("", registry),
    ]
    results = merge_all(episodes, outcomes)
    assert [r.episode.episode_id for r in results] == ["EP01", "EP02", "EP03"]
    assert [r.content_status for r in results] == [MODEL_FAILURE, VALID_PARSE, EMPTY]


def test_llm_009_ordering_is_preserved(episodes, registry):
    outcomes = [_parsed(registry, {"summary": "요약 %d" % i}) for i in range(3)]
    results = merge_all(episodes, outcomes)
    assert [r.episode.start_seg for r in results] == [0, 4, 8]


def test_llm_009_count_mismatch_is_refused(episodes, registry):
    with pytest.raises(ValueError, match="one outcome per episode"):
        merge_all(episodes, [_parsed(registry, {"summary": "하나뿐"})])


# ── 실패를 내용으로 위장하지 않는다 ──────────────────────────────────────
def test_failure_never_produces_an_empty_summary(episodes, registry):
    for outcome in (model_failure(RuntimeError("x")),
                    parse_json_payload('{"a":', registry),
                    parse_json_payload("", registry)):
        result = merge_content(episodes[0], outcome)
        assert result.content is None
        assert result.content_status != VALID_PARSE


def test_missing_summary_is_a_contract_failure_not_empty(episodes, registry):
    """구조는 왔는데 약속한 필드가 없다 — 빈 출력과 다르다."""
    result = merge_content(episodes[0], _parsed(registry, {"dialogue_note": "메모"}))
    assert result.content_status == PARSE_CONTRACT_FAILURE
    assert result.reason == "missing_summary"
    assert result.content is None


def test_blank_summary_is_a_contract_failure(episodes, registry):
    result = merge_content(episodes[0],
                           _parsed(registry, {"summary": "   ", "dialogue_note": "메모"}))
    assert result.content_status == PARSE_CONTRACT_FAILURE
    assert result.reason == "missing_summary"


def test_failure_reason_is_kept(episodes, registry):
    result = merge_content(episodes[0], model_failure(TimeoutError("no response")))
    assert result.error_type == "TimeoutError"
    assert "no response" in result.error


def test_there_is_no_placeholder_text():
    code = code_only(SRC)
    for forbidden in ("생성 실패", "요약 없음", "N/A", "(없음)", "unknown"):
        assert forbidden not in code, "실패를 문구로 메웠다: " + forbidden


# ── 정상 병합 ────────────────────────────────────────────────────────────
def test_valid_payload_becomes_content(episodes, registry):
    result = merge_content(
        episodes[2],
        _parsed(registry, {"summary": "두 사람이 해변에서 짐을 챙긴다.",
                           "dialogue_note": "다음 장소를 정한다.",
                           "stt_cites": [8, "seg#9"]}),
    )
    assert result.content_status == VALID_PARSE
    assert result.content.summary == "두 사람이 해변에서 짐을 챙긴다."
    assert result.content.dialogue_note == "다음 장소를 정한다."
    assert result.content.stt_cites == (8, 9)


def test_cite_notation_is_normalized_and_sorted(episodes, registry):
    result = merge_content(
        episodes[2],
        _parsed(registry, {"summary": "요약", "stt_cites": ["seg#11", 8, "8"]}),
    )
    assert result.content.stt_cites == (8, 11)


def test_unreadable_cites_are_dropped_not_invented(episodes, registry):
    result = merge_content(
        episodes[2],
        _parsed(registry, {"summary": "요약", "stt_cites": ["없음", None, 9]}),
    )
    assert result.content.stt_cites == (9,)


def test_absent_optional_fields_stay_absent(episodes, registry):
    result = merge_content(episodes[0], _parsed(registry, {"summary": "요약"}))
    assert result.content.dialogue_note is None
    assert result.content.stt_cites == ()


# ── 모델이 파생 필드를 덮지 못한다 ───────────────────────────────────────
def test_model_supplied_derived_fields_are_ignored(episodes, registry):
    hijack = {
        "summary": "요약",
        "episode_id": "EP99",
        "start_seg": 0,
        "end_seg": 11,
        "support_span": {"start_seg": 0, "end_seg": 11},
        "anchor_cites": [0, 1, 2],
        "source": "stt",
    }
    result = merge_content(episodes[1], _parsed(registry, hijack))
    assert _structure(result) == _structure(EpisodeResult(episodes[1], VALID_PARSE, None))
    assert result.episode.episode_id == "EP02"


def test_hijack_attempt_is_recorded_not_silently_dropped(episodes, registry):
    result = merge_content(
        episodes[1],
        _parsed(registry, {"summary": "요약", "episode_id": "EP99", "source": "stt"}),
    )
    assert set(result.ignored_fields) == {"episode_id", "source"}


def test_clean_output_records_no_ignored_fields(episodes, registry):
    result = merge_content(episodes[0], _parsed(registry, {"summary": "요약"}))
    assert result.ignored_fields == ()


def test_unknown_extra_fields_are_not_treated_as_hijacks(episodes, registry):
    """SCH-006 — 모르는 필드는 파생 필드가 아니다."""
    result = merge_content(
        episodes[0], _parsed(registry, {"summary": "요약", "camera_move": "pan"})
    )
    assert result.ignored_fields == ()
    assert result.content_status == VALID_PARSE


# ── 계층 경계 ────────────────────────────────────────────────────────────
def test_b04_does_not_do_grounding():
    """근거 자격·named entity 검증은 B-05·B-06 소관이다."""
    code = code_only(SRC)
    for forbidden in ("usable_for_claims", "FAIL_", "GRD", "named_entity",
                      "eligible_support", "timeline"):
        assert forbidden not in code, "grounding을 시작했다: " + forbidden


def test_b04_does_not_call_a_model():
    code = code_only(SRC)
    for forbidden in ("transformers", "ollama", "torch", "make_llm"):
        assert forbidden not in code, "B-02 책임을 침범했다: " + forbidden


def test_b04_reuses_the_parse_vocabulary():
    """A-04와 다른 어휘를 만들지 않는다."""
    import v2_1_content
    import v2_1_parse

    assert v2_1_content.CONTENT_STATUSES == v2_1_parse.PARSE_STATUSES


def test_b04_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
