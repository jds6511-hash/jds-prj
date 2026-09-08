"""합성 계층 렌더 (2026-09-08 · PSY-017~027).

```
chapter title + 1~2문장          → 주요 사건 및 내용
global overview 3~5              → 개요
global analysis 3~6              → 핵심 내용 분석
global conclusion 1~2            → 결론
```

기존 concat 경로는 그대로 통과해야 한다 — 두 경로가 공존한다.
"""
import json
import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import unescape

import pytest

from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_presentation import (
    SECTION_NAMES,
    build_presentation,
    presentation_groups,
)
from v2_1_presentation_input import PresentationEpisode, PresentationInput
from v2_1_presentation_synthesis import group_inputs, parse_global, parse_group
from v2_1_render import LABELS, render_markdown, semantic_view
from v2_1_render_hwpx import render_hwpx
from v2_1_run import Manifest
from v2_1_synthesis import build_synthesis

REPORT = Manifest(video_id="PS", run_id="run-psy", analysis_mode="report",
                  config_hash="c0ffee", code_git_head="deadbeef")
DRIFT = ("두 사람이 빵을 만드는 모습을 보여주고, 마지막으로 베이킹용품"
         "尤其是关于蛋糕，是否有售？价格在这里，请看样品。")


def _episode(index, summary, *, content_status="VALID_PARSE"):
    return PresentationEpisode(
        episode_id="EP%02d" % index, start_seg=(index - 1) * 12,
        end_seg=(index - 1) * 12 + 11, start_sec=(index - 1) * 60.0,
        end_sec=index * 60.0, source="stt", content_status=content_status,
        summary=summary, dialogue_note=None,
        grounding_status="NOT_APPLICABLE", anchor_cites=(),
        provenance=("m3_generate",))


def _chapter(item):
    payload = json.dumps({
        "title": "%s 장 제목" % item.group_id,
        "summary_sentences": [
            {"text": "%s에서 재료를 준비하고 조리를 이어간다." % item.group_id,
             "source_episode_refs": list(item.eligible_episode_refs)}]},
        ensure_ascii=False)
    return parse_group(payload, item)


@pytest.fixture
def world():
    episodes = []
    for index in range(1, 16):
        episodes.append(_episode(
            index, DRIFT if index == 13 else "구간 %d에서 재료를 다룬다." % index))
    presented = PresentationInput(schema="aar_canonical_v2_1", video_id="PS",
                                  run_id="run-psy", episodes=tuple(episodes))
    groups = presentation_groups(presented)
    highlights = build_highlights(presented, [HighlightSpec(g) for g in groups])
    records = build_presentation(presented, highlights)
    legacy = build_synthesis(presented, build_lineage(presented, highlights))

    inputs = group_inputs(presented, groups)
    chapters = [_chapter(item) for item in inputs]
    ids = [chapter.group_id for chapter in chapters]
    global_result = parse_global(json.dumps({
        "overview_sentences": [
            {"text": "전체적으로 재료 준비가 이어진다.",
             "source_highlight_refs": [ids[0]]},
            {"text": "중반에는 조리가 중심이 된다.",
             "source_highlight_refs": [ids[1]]},
            {"text": "후반에는 마무리가 이어진다.",
             "source_highlight_refs": [ids[-1]]}],
        "analysis_points": [
            {"text": "초반 흐름은 준비다.", "source_highlight_refs": [ids[0]]},
            {"text": "중반 흐름은 조리다.", "source_highlight_refs": [ids[1]]},
            {"text": "후반 흐름은 정리다.", "source_highlight_refs": [ids[-1]]}],
        "conclusion_sentences": [
            {"text": "준비에서 정리까지 이어지는 흐름이다.",
             "source_highlight_refs": [ids[0], ids[-1]]}]},
        ensure_ascii=False), chapters)
    return presented, records, legacy, chapters, global_result, inputs


def _hwpx_text(payload: bytes) -> str:
    with zipfile.ZipFile(BytesIO(payload)) as package:
        section = package.read("Contents/section0.xml").decode("utf-8")
    return "\n".join(unescape(text) for text in
                     re.findall(r"<hp:t>(.*?)</hp:t>", section, re.S))


# ── PSY-017 chapter title ───────────────────────────────────────────────
def test_psy_017_the_chapter_title_and_sentence_are_rendered(world):
    _, records, legacy, chapters, global_result, _ = world
    markdown = render_markdown(REPORT, records, legacy, chapters=chapters,
                               global_synthesis=global_result)
    hwpx = _hwpx_text(render_hwpx(REPORT, records, legacy, chapters=chapters,
                                  global_synthesis=global_result))
    for text in (markdown, hwpx):
        assert chapters[0].title in text
        assert chapters[0].summary_sentences[0].text in text


def test_the_concat_summary_is_not_rendered_when_a_chapter_exists(world):
    _, records, legacy, chapters, global_result, _ = world
    markdown = render_markdown(REPORT, records, legacy, chapters=chapters,
                               global_synthesis=global_result)
    assert " / " not in markdown                     # slash concat 패턴이 없다
    assert records[0].summary is not None            # 정본 표현 객체는 그대로다


# ── PSY-018 · 019 형식 ──────────────────────────────────────────────────
def test_psy_018_the_analysis_has_three_to_six_points(world):
    _, records, legacy, chapters, global_result, _ = world
    view = semantic_view(records, legacy, chapters=chapters,
                         global_synthesis=global_result)
    assert 3 <= len(view["analysis"]) <= 6


def test_psy_019_the_conclusion_is_one_or_two_sentences(world):
    _, records, legacy, chapters, global_result, _ = world
    view = semantic_view(records, legacy, chapters=chapters,
                         global_synthesis=global_result)
    assert 1 <= view["conclusion"].count("다.") <= 2


# ── PSY-020 중복 금지 ───────────────────────────────────────────────────
def test_psy_020_the_analysis_does_not_reprint_the_chapter_summaries(world):
    _, records, legacy, chapters, global_result, _ = world
    view = semantic_view(records, legacy, chapters=chapters,
                         global_synthesis=global_result)
    for chapter in chapters:
        for sentence in chapter.summary_sentences:
            assert all(sentence.text not in point for point in view["analysis"])


def test_the_overview_is_not_the_episode_concat(world):
    presented, records, legacy, chapters, global_result, _ = world
    view = semantic_view(records, legacy, chapters=chapters,
                         global_synthesis=global_result)
    assert 3 <= len(view["overview_sentences"]) <= 5
    for episode in presented.episodes:
        if episode.summary and episode.summary != DRIFT:
            assert episode.summary not in view["overview"]


# ── PSY-021 출처 계층 ───────────────────────────────────────────────────
def test_psy_021_the_overview_provenance_is_the_group_layer(world):
    _, records, legacy, chapters, global_result, _ = world
    view = semantic_view(records, legacy, chapters=chapters,
                         global_synthesis=global_result)
    allowed = {chapter.group_id for chapter in chapters}
    for sentence in view["overview_sentences"]:
        assert set(sentence["source_refs"]) <= allowed
        assert not any(ref.startswith("EP") for ref in sentence["source_refs"])


# ── PSY-022 제외 표기 유지 ──────────────────────────────────────────────
def test_psy_022_the_excluded_episode_is_still_reported(world):
    _, records, legacy, chapters, global_result, _ = world
    markdown = render_markdown(REPORT, records, legacy, chapters=chapters,
                               global_synthesis=global_result)
    assert "%s: EP13 (OUTPUT_LANGUAGE_DRIFT)" % LABELS["excluded"] in markdown
    assert DRIFT not in markdown


# ── PSY-024 두 출력이 같은 의미 계층을 쓴다 ─────────────────────────────
def test_psy_024_both_renderers_share_the_semantic_view(world):
    _, records, legacy, chapters, global_result, _ = world
    markdown = render_markdown(REPORT, records, legacy, chapters=chapters,
                               global_synthesis=global_result)
    hwpx = _hwpx_text(render_hwpx(REPORT, records, legacy, chapters=chapters,
                                  global_synthesis=global_result))
    view = semantic_view(records, legacy, chapters=chapters,
                         global_synthesis=global_result)
    for text in (markdown, hwpx):
        assert view["conclusion"] in text
        for sentence in view["overview_sentences"]:
            assert sentence["text"] in text
        for point in view["analysis"]:
            assert point in text


def test_the_five_sections_are_still_there(world):
    _, records, legacy, chapters, global_result, _ = world
    markdown = render_markdown(REPORT, records, legacy, chapters=chapters,
                               global_synthesis=global_result)
    for section in SECTION_NAMES:
        assert section in markdown


# ── 기존 경로 불변 ──────────────────────────────────────────────────────
def test_the_legacy_concat_path_is_unchanged(world):
    """합성 인자를 주지 않으면 예전 출력과 같은 경로다."""
    _, records, legacy, _, _, _ = world
    markdown = render_markdown(REPORT, records, legacy)
    assert " / " in markdown                         # 예전 concat 그대로
    assert legacy.overview in markdown
    assert legacy.conclusion in markdown


def test_a_failed_chapter_is_shown_as_a_failure_not_a_concat(world):
    _, records, legacy, chapters, global_result, inputs = world
    broken = list(chapters)
    broken[0] = parse_group("망가진 출력", inputs[0])
    markdown = render_markdown(REPORT, records, legacy, chapters=broken,
                               global_synthesis=global_result)
    assert "GROUP_SYNTHESIS_FAILURE" in markdown
    assert " / " not in markdown
