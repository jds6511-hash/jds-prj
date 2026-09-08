"""PRESENTATION_SYNTHESIS_V1 계약 (2026-09-08 · PSY-001~016).

사전등록: `docs/finalization/PRESENTATION_SYNTHESIS_V1_ADDENDUM_2026-09-08.md`

```
episode summary  →  GroupSynthesizer   →  chapter (title + 1~2문장)
chapter          →  GlobalSynthesizer  →  overview 3~5 · analysis 3~6 · conclusion 1~2
```

GPU 없이 계약만 잰다. 모델 출력은 fixture 문자열로 넣는다.
"""
import json

import pytest

from v2_1_output_quality import FAIL, SUSPECT
from v2_1_presentation import PRESENTATION_GROUP_WINDOW_SEC, presentation_groups
from v2_1_presentation_input import PresentationEpisode, PresentationInput
from v2_1_presentation_synthesis import (
    ANALYSIS_RANGE,
    CONCLUSION_RANGE,
    GLOBAL_CONTRACT,
    GLOBAL_CONTRACT_VERSION,
    GLOBAL_SYNTHESIS_FAILURE,
    GROUP_CONTRACT,
    GROUP_CONTRACT_VERSION,
    GROUP_SENTENCE_RANGE,
    GROUP_SYNTHESIS_FAILURE,
    OVERVIEW_RANGE,
    VALID_SYNTHESIS,
    SynthesisError,
    build_global_prompt,
    build_group_prompt,
    global_prompt_hash,
    group_inputs,
    group_prompt_hash,
    parse_global,
    parse_group,
    validate_global,
    validate_group,
)

DRIFT = ("두 사람이 빵을 만드는 모습을 보여주고, 마지막으로 베이킹용품"
         "尤其是关于蛋糕，是否有售？价格在这里，请看样品。")


def _episode(index, summary, *, content_status="VALID_PARSE",
             grounding="NOT_APPLICABLE"):
    return PresentationEpisode(
        episode_id="EP%02d" % index, start_seg=(index - 1) * 12,
        end_seg=(index - 1) * 12 + 11, start_sec=(index - 1) * 60.0,
        end_sec=index * 60.0, source="stt", content_status=content_status,
        summary=summary, dialogue_note=None, grounding_status=grounding,
        anchor_cites=(), provenance=("m3_generate",))


def _presented():
    """H03 · H04를 실측과 같은 모양으로 만든다 — EP13 drift · EP17 parse 실패."""
    episodes = []
    for index in range(1, 21):
        if index == 13:
            episodes.append(_episode(index, DRIFT))
        elif index == 17:
            episodes.append(_episode(index, None,
                                     content_status="PARSE_CONTRACT_FAILURE"))
        else:
            episodes.append(_episode(index, "구간 %d에서 재료를 다룬다." % index))
    return PresentationInput(schema="aar_canonical_v2_1", video_id="PS",
                             run_id="run-psy", episodes=tuple(episodes))


@pytest.fixture
def world():
    presented = _presented()
    groups = presentation_groups(presented)
    return presented, groups, group_inputs(presented, groups)


def _group_payload(refs, sentences=1):
    return json.dumps({
        "title": "재료 준비",
        "summary_sentences": [
            {"text": "여러 재료를 차례로 준비한다.", "source_episode_refs": list(refs)}
        ][:sentences] + ([
            {"text": "이후 조리를 시작한다.", "source_episode_refs": [refs[-1]]}
        ] if sentences > 1 else []),
    }, ensure_ascii=False)


def _global_payload(highlights, overview=3, analysis=3, conclusion=1):
    def rows(count, text):
        return [{"text": "%s %d." % (text, index + 1),
                 "source_highlight_refs": [highlights[index % len(highlights)]]}
                for index in range(count)]
    return json.dumps({
        "overview_sentences": rows(overview, "전체 흐름은 이렇게 이어진다"),
        "analysis_points": rows(analysis, "중반 이후 활동이 바뀐다"),
        "conclusion_sentences": rows(conclusion, "마무리 정리"),
    }, ensure_ascii=False)


# ── PSY-001 · 002 정본·grouping 불변 ────────────────────────────────────
def test_psy_001_the_canonical_episodes_are_untouched(world):
    presented, _, inputs = world
    assert len(presented.episodes) == 20
    for episode in presented.episodes:
        assert episode.summary == _presented().episode(episode.episode_id).summary
    assert sum(len(item.episodes) for item in inputs) <= len(presented.episodes)


def test_psy_002_the_group_membership_is_the_300_sec_grouping(world):
    presented, groups, inputs = world
    assert PRESENTATION_GROUP_WINDOW_SEC == 300
    assert [item.group_id for item in inputs] == [
        "H%02d" % (index + 1) for index in range(len(groups))]
    for item, group in zip(inputs, groups):
        assert item.member_episode_refs == tuple(group)


# ── PSY-003 제외 episode는 입력에 못 들어온다 ────────────────────────────
def test_psy_003_excluded_episodes_never_reach_the_synthesizer(world):
    _, _, inputs = world
    by_id = {item.group_id: item for item in inputs}
    third = by_id["H03"]
    assert third.eligible_episode_refs == ("EP11", "EP12", "EP14", "EP15")
    assert "EP13" not in third.eligible_episode_refs
    assert third.excluded == (("EP13", ("OUTPUT_LANGUAGE_DRIFT",)),)
    prompt = build_group_prompt(third)
    assert "EP13" not in prompt
    assert DRIFT[:12] not in prompt                      # 그 문장 자체도 안 들어간다

    fourth = by_id["H04"]
    assert fourth.eligible_episode_refs == ("EP16", "EP18", "EP19", "EP20")
    assert fourth.excluded == (("EP17", ("PARSE_CONTRACT_FAILURE",)),)


def test_the_prompt_carries_no_raw_evidence(world):
    _, _, inputs = world
    prompt = build_group_prompt(inputs[0])
    for forbidden in ("[근거]", "[참고]", "자막", "caption", "OCR"):
        assert forbidden not in prompt


# ── PSY-004 · 005 · 006 source refs 검증 ────────────────────────────────
def test_psy_004_a_nonexistent_ref_is_rejected(world):
    _, _, inputs = world
    first = inputs[0]
    payload = json.dumps({"title": "재료", "summary_sentences": [
        {"text": "재료를 준비한다.", "source_episode_refs": ["EP42"]}]},
        ensure_ascii=False)
    result = parse_group(payload, first)
    assert result.content_status == GROUP_SYNTHESIS_FAILURE
    assert any("EP42" in failure for failure in result.failures)


def test_psy_005_a_ref_from_another_group_is_rejected(world):
    _, _, inputs = world
    third = [item for item in inputs if item.group_id == "H03"][0]
    payload = json.dumps({"title": "재료", "summary_sentences": [
        {"text": "재료를 준비한다.", "source_episode_refs": ["EP01"]}]},
        ensure_ascii=False)
    result = parse_group(payload, third)
    assert result.content_status == GROUP_SYNTHESIS_FAILURE


def test_psy_006_an_ineligible_ref_is_rejected(world):
    _, _, inputs = world
    third = [item for item in inputs if item.group_id == "H03"][0]
    payload = json.dumps({"title": "재료", "summary_sentences": [
        {"text": "빵을 만든다.", "source_episode_refs": ["EP13"]}]},
        ensure_ascii=False)
    result = parse_group(payload, third)
    assert result.content_status == GROUP_SYNTHESIS_FAILURE
    assert any("EP13" in failure for failure in result.failures)


def test_empty_source_refs_are_rejected(world):
    _, _, inputs = world
    payload = json.dumps({"title": "재료", "summary_sentences": [
        {"text": "재료를 준비한다.", "source_episode_refs": []}]},
        ensure_ascii=False)
    assert parse_group(payload, inputs[0]).content_status == (
        GROUP_SYNTHESIS_FAILURE)


# ── PSY-007 형식 ────────────────────────────────────────────────────────
def test_psy_007_a_chapter_has_one_or_two_sentences(world):
    _, _, inputs = world
    first = inputs[0]
    for count in (1, 2):
        result = parse_group(_group_payload(first.eligible_episode_refs, count),
                             first)
        assert result.content_status == VALID_SYNTHESIS
        assert len(result.summary_sentences) == count
    assert GROUP_SENTENCE_RANGE == (1, 2)


def test_a_chapter_that_reprints_every_episode_is_rejected(world):
    """5 episode → 5문장은 압축이 아니다."""
    _, _, inputs = world
    first = inputs[0]
    payload = json.dumps({"title": "재료", "summary_sentences": [
        {"text": "구간 %s를 설명한다." % ref, "source_episode_refs": [ref]}
        for ref in first.eligible_episode_refs]}, ensure_ascii=False)
    result = parse_group(payload, first)
    assert result.content_status == GROUP_SYNTHESIS_FAILURE


def test_a_missing_title_is_rejected(world):
    _, _, inputs = world
    payload = json.dumps({"summary_sentences": [
        {"text": "재료를 준비한다.",
         "source_episode_refs": [inputs[0].eligible_episode_refs[0]]}]},
        ensure_ascii=False)
    assert parse_group(payload, inputs[0]).content_status == (
        GROUP_SYNTHESIS_FAILURE)


# ── PSY-008 · 009 실패 처리 ─────────────────────────────────────────────
def test_psy_008_a_failed_group_never_falls_back_to_concat(world):
    _, _, inputs = world
    result = parse_group("이건 JSON이 아니다", inputs[0])
    assert result.content_status == GROUP_SYNTHESIS_FAILURE
    assert result.summary_sentences == ()
    assert result.title is None
    joined = " / ".join(inputs[0].summaries)
    assert joined not in json.dumps(result.as_dict(), ensure_ascii=False)


def test_psy_009_the_raw_model_output_is_preserved(world):
    _, _, inputs = world
    raw = "이건 JSON이 아니다"
    result = parse_group(raw, inputs[0])
    assert result.raw_model_output == raw
    good = _group_payload(inputs[0].eligible_episode_refs)
    assert parse_group(good, inputs[0]).raw_model_output == good


# ── PSY-010 · 011 global 입력 계층 ──────────────────────────────────────
def test_psy_010_the_global_prompt_carries_chapters_only(world):
    _, _, inputs = world
    chapters = [parse_group(_group_payload(item.eligible_episode_refs), item)
                for item in inputs]
    prompt = build_global_prompt(chapters)
    for chapter in chapters:
        assert chapter.title in prompt
    for episode in _presented().episodes:
        if episode.summary:
            assert episode.summary not in prompt


def test_psy_011_the_global_layer_refuses_episode_summaries(world):
    _, _, inputs = world
    with pytest.raises(SynthesisError):
        build_global_prompt(list(inputs))          # chapter가 아니라 episode 입력
    with pytest.raises(SynthesisError):
        build_global_prompt([])


def test_the_global_prompt_skips_failed_chapters(world):
    _, _, inputs = world
    chapters = [parse_group(_group_payload(item.eligible_episode_refs), item)
                for item in inputs]
    chapters[1] = parse_group("망가진 출력", inputs[1])
    prompt = build_global_prompt(chapters)
    assert chapters[1].group_id not in prompt


# ── PSY-012 · 013 global 형식·참조 ──────────────────────────────────────
def test_psy_012_the_overview_has_three_to_five_sentences(world):
    _, _, inputs = world
    chapters = [parse_group(_group_payload(item.eligible_episode_refs), item)
                for item in inputs]
    ids = [chapter.group_id for chapter in chapters]
    assert OVERVIEW_RANGE == (3, 5)
    for count in (3, 4, 5):
        result = parse_global(_global_payload(ids, overview=count), chapters)
        assert result.content_status == VALID_SYNTHESIS
        assert len(result.overview_sentences) == count
    for count in (2, 6):
        result = parse_global(_global_payload(ids, overview=count), chapters)
        assert result.content_status == GLOBAL_SYNTHESIS_FAILURE


def test_the_analysis_and_conclusion_ranges_are_frozen(world):
    _, _, inputs = world
    chapters = [parse_group(_group_payload(item.eligible_episode_refs), item)
                for item in inputs]
    ids = [chapter.group_id for chapter in chapters]
    assert ANALYSIS_RANGE == (3, 6) and CONCLUSION_RANGE == (1, 2)
    assert parse_global(_global_payload(ids, analysis=2), chapters
                        ).content_status == GLOBAL_SYNTHESIS_FAILURE
    assert parse_global(_global_payload(ids, conclusion=3), chapters
                        ).content_status == GLOBAL_SYNTHESIS_FAILURE


def test_psy_013_global_refs_must_be_valid_highlight_refs(world):
    _, _, inputs = world
    chapters = [parse_group(_group_payload(item.eligible_episode_refs), item)
                for item in inputs]
    payload = json.loads(_global_payload([chapter.group_id
                                          for chapter in chapters]))
    payload["overview_sentences"][0]["source_highlight_refs"] = ["EP01"]
    result = parse_global(json.dumps(payload, ensure_ascii=False), chapters)
    assert result.content_status == GLOBAL_SYNTHESIS_FAILURE
    assert any("EP01" in failure for failure in result.failures)


def test_global_refs_to_a_failed_chapter_are_rejected(world):
    _, _, inputs = world
    chapters = [parse_group(_group_payload(item.eligible_episode_refs), item)
                for item in inputs]
    chapters[0] = parse_group("망가진 출력", inputs[0])
    payload = _global_payload([chapter.group_id for chapter in chapters[1:]])
    body = json.loads(payload)
    body["overview_sentences"][0]["source_highlight_refs"] = [chapters[0].group_id]
    result = parse_global(json.dumps(body, ensure_ascii=False), chapters)
    assert result.content_status == GLOBAL_SYNTHESIS_FAILURE


# ── PSY-014 output quality ──────────────────────────────────────────────
def test_psy_014_a_quality_failing_chapter_is_not_presented(world):
    _, _, inputs = world
    first = inputs[0]
    payload = json.dumps({"title": "베이킹", "summary_sentences": [
        {"text": DRIFT, "source_episode_refs": [first.eligible_episode_refs[0]]}]},
        ensure_ascii=False)
    result = parse_group(payload, first)
    assert result.quality_status == FAIL
    assert result.presentable is False
    assert "OUTPUT_LANGUAGE_DRIFT" in result.quality_reasons


def test_a_suspect_chapter_is_still_presented(world):
    """SUSPECT는 diagnostic이다 — 자동 제외로 승격하지 않는다."""
    _, _, inputs = world
    first = inputs[0]
    payload = json.dumps({"title": "재료", "summary_sentences": [
        {"text": "주인공이 카레우don을 처리한다.",
         "source_episode_refs": [first.eligible_episode_refs[0]]}]},
        ensure_ascii=False)
    result = parse_group(payload, first)
    assert result.quality_status == SUSPECT
    assert result.presentable is True


def test_the_title_is_judged_by_the_same_gate(world):
    _, _, inputs = world
    first = inputs[0]
    payload = json.dumps({"title": DRIFT, "summary_sentences": [
        {"text": "재료를 준비한다.",
         "source_episode_refs": [first.eligible_episode_refs[0]]}]},
        ensure_ascii=False)
    assert parse_group(payload, first).quality_status == FAIL


# ── 계약 지문 ───────────────────────────────────────────────────────────
def test_the_two_contracts_are_new_and_hashed():
    assert GROUP_CONTRACT_VERSION == "presentation_group_synthesis_v1"
    assert GLOBAL_CONTRACT_VERSION == "presentation_global_synthesis_v1"
    assert GROUP_CONTRACT["version"] == GROUP_CONTRACT_VERSION
    assert GLOBAL_CONTRACT["version"] == GLOBAL_CONTRACT_VERSION
    assert group_prompt_hash() != global_prompt_hash()
    assert len(group_prompt_hash()) == 64


def test_the_episode_contracts_are_untouched():
    """v2 계약 해시는 **실행 기록에서 가져와** 대조한다 — 손으로 적지 않는다."""
    import json
    from pathlib import Path

    from v2_1_prompt import CONTRACT, PROMPT_VERSION, contract_hash
    recorded = json.loads(
        (Path(__file__).resolve().parents[1]
         / "runs/v3_paired/r0_v2/run_manifest.json").read_text(encoding="utf-8")
    )["fingerprint"]["prompt_hash"]
    assert PROMPT_VERSION == "episode_content_v2"
    assert contract_hash(CONTRACT) == recorded


def test_validators_are_reusable_on_their_own(world):
    _, _, inputs = world
    first = inputs[0]
    result = parse_group(_group_payload(first.eligible_episode_refs), first)
    assert validate_group(result, first) == []
    chapters = [parse_group(_group_payload(item.eligible_episode_refs), item)
                for item in inputs]
    global_result = parse_global(
        _global_payload([chapter.group_id for chapter in chapters]), chapters)
    assert validate_global(global_result, chapters) == []
