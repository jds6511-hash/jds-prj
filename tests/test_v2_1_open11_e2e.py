"""C-09 OPEN-11 end-to-end 회귀 — 오염이 경계를 넘지 못한다 (Gate C).

닫는 문장은 **"producer가 이제 정상"이 아니다.**

> grounding이 제거한 정보는 canonical → presentation → renderer/fallback 어디에서도
> 부활하지 않는다. 동시에, 막는다는 이유로 정보 전체를 버리지도 않는다.

그래서 여기서는 프롬프트를 고치지도, 모델을 다시 돌리지도 않는다. **적대적 입력을
실제로 전 구간에 태워** 결과를 본다.

```
적대적 content → B-05 → B-06 → B-07 → C-01 → C-02/03 → C-04 → C-05
                                                        → C-06 → C-07 → C-08
```

검사는 **단계별**로 한다. 문서 전체 문자열 검색 하나로 끝내면 다른 절에 가려진다
(C-06에서 실제로 겪었다).
"""
from dataclasses import dataclass

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_presentation import build_presentation
from v2_1_presentation_input import presentation_input
from v2_1_render import render_markdown, render_preview
from v2_1_render_fallback import (
    PRESENTATION_FALLBACK_USED,
    render_with_fallback,
)
from v2_1_render_hwpx import hwpx_text, render_hwpx
from v2_1_render_probe import _blocks
from v2_1_run import Manifest
from v2_1_synthesis import build_synthesis

REPORT = Manifest(video_id="S1", run_id="run-open11", analysis_mode="report",
                  config_hash="c0ffee", code_git_head="deadbeef")

TWO = ((0, 5), (6, 11))

#: 2026-08-31 run 3에서 실제로 나온 형태 — 인용 목록이 발화 자리에 들어왔다.
CONFUSED_NOTE = "['seg#8', 'seg#10']"
#: run 2에서 나온 형태 — 프롬프트 예시의 자리표시자를 그대로 베꼈다(OPEN-10).
PLACEHOLDER_NOTE = "선택"


@dataclass(frozen=True)
class Chain:
    """전 구간 산출물. 단계별로 따로 볼 수 있게 전부 들고 있는다."""

    document: dict
    presented: object
    highlights: tuple
    lineage: tuple
    synthesis: object
    presentation: tuple
    markdown: str
    preview: str
    hwpx: str
    fallback: object


def _chain(tmp_path, payloads, *, name="S1", spans=TWO, groups=None,
           asr=None) -> Chain:
    pipeline = run_pipeline(tmp_path, payloads, name=name, spans=spans,
                            asr_overrides=asr)
    presented = presentation_input(pipeline.document)
    groups = groups or (tuple(e.episode_id for e in presented.episodes),)
    specs = [HighlightSpec(group) for group in groups]
    core = build_highlights(presented, specs)
    lineage = build_lineage(presented, core)
    synthesis = build_synthesis(presented, lineage)
    presentation = build_presentation(presented, core)

    def broken_hwpx(*_a, **_k):
        raise RuntimeError("hwpx unavailable")

    renderers = __import__("v2_1_render_fallback")._RENDERERS
    original = renderers["hwpx"]
    renderers["hwpx"] = broken_hwpx
    try:
        fallback = render_with_fallback(REPORT, presentation, synthesis)
    finally:
        renderers["hwpx"] = original

    return Chain(
        document=pipeline.document,
        presented=presented,
        highlights=core,
        lineage=lineage,
        synthesis=synthesis,
        presentation=presentation,
        markdown=render_markdown(REPORT, presentation, synthesis),
        preview=render_preview(REPORT, presentation, synthesis),
        hwpx=hwpx_text(render_hwpx(REPORT, presentation, synthesis)),
        fallback=fallback,
    )


def _stages(chain: Chain) -> dict:
    """오염이 없어야 하는 지점을 단계별로 모은다."""
    return {
        "canonical": " ".join(
            str(episode.get("summary")) + str(episode.get("dialogue_note"))
            for episode in chain.document["episodes"]
        ),
        "presentation_input": " ".join(
            "%s%s" % (e.summary, e.dialogue_note) for e in chain.presented.episodes
        ),
        "highlight_summary": " ".join(
            record.summary or "" for record in chain.presentation
        ),
        "synthesis": " ".join((chain.synthesis.overview, chain.synthesis.conclusion,
                               *chain.synthesis.analysis)),
        "markdown": chain.markdown,
        "preview": chain.preview,
        "hwpx": chain.hwpx,
        "fallback": str(chain.fallback.payload),
    }


# ── Case A — grounding FAIL에서 제거된 dialogue ──────────────────────────
CASE_A = ({"summary": "창고 문을 연다."},
          {"summary": "상자를 옮긴다.", "dialogue_note": CONFUSED_NOTE,
           "stt_cites": [9]})


@pytest.fixture(scope="module")
def case_a(tmp_path_factory):
    return _chain(tmp_path_factory.mktemp("a"), CASE_A)


def test_case_a_grounding_actually_failed(case_a):
    """오염이 통과해 버리면 이 회귀 자체가 무의미하다."""
    affected = case_a.document["episodes"][1]
    assert affected["grounding_status"].startswith("FAIL")


def test_case_a_the_confused_note_is_gone_at_every_stage(case_a):
    for stage, text in _stages(case_a).items():
        assert CONFUSED_NOTE not in text, stage
        assert "seg#8" not in text, stage


def test_case_a_the_episode_itself_survives(case_a):
    """containment이지 episode 제거가 아니다."""
    assert len(case_a.presented.episodes) == 2
    affected = case_a.presented.episode("EP02")
    assert affected.summary == "상자를 옮긴다."
    assert affected.dialogue_note is None


def test_case_a_the_summary_still_reaches_the_documents(case_a):
    for text in (case_a.markdown, case_a.hwpx, case_a.preview):
        assert "창고 문을 연다." in text


def test_case_a_the_failure_is_visible_not_hidden(case_a):
    """실패를 통과처럼 정규화하지 않는다 — 사유가 정본에 남는다."""
    affected = case_a.document["episodes"][1]
    assert affected["grounding_reasons"]
    assert affected["episode_id"] in case_a.presentation[0].source_episode_ids


def test_case_a_the_fallback_output_is_clean(case_a):
    assert case_a.fallback.status == PRESENTATION_FALLBACK_USED
    assert CONFUSED_NOTE not in case_a.fallback.payload


# ── Case B — 발화 근거가 아예 없는 구간의 자리표시자 ─────────────────────
CASE_B = ({"summary": "창고 문을 연다.", "dialogue_note": PLACEHOLDER_NOTE},
          {"summary": "정리하고 나간다."})


@pytest.fixture(scope="module")
def case_b(tmp_path_factory):
    return _chain(tmp_path_factory.mktemp("b"), CASE_B, name="S3")


def test_case_b_the_scenario_has_no_speech(case_b):
    from v2_1_fixtures import scenario

    assert not scenario("S3").asr


def test_case_b_a_dialogue_without_support_does_not_pass(case_b):
    """발화 근거가 없으면 dialogue claim은 통과할 수 없다."""
    affected = case_b.document["episodes"][0]
    assert affected["grounding_status"] != "PASS"
    assert affected["dialogue_note"] is None


def test_case_b_the_placeholder_never_appears_downstream(case_b):
    for stage, text in _stages(case_b).items():
        assert PLACEHOLDER_NOTE not in text, stage


def test_case_b_canonical_keeps_the_summary(case_b):
    """containment는 삭제가 아니다 — 정본에는 요약이 그대로 남는다."""
    assert case_b.presented.episode("EP01").summary == "창고 문을 연다."
    assert case_b.document["episodes"][0]["summary"] == "창고 문을 연다."


def test_case_b_a_failed_episode_costs_its_summary_in_presentation(case_b):
    """**관측 사실**: dialogue 오염으로 FAIL이 되면 그 구간의 요약도 표현에서 빠진다.

    OPEN-12 자격이 `{PASS, NOT_APPLICABLE}` allowlist이기 때문이다. 즉 producer가
    발화를 지어내면 **멀쩡한 요약까지 문서에서 사라진다.** 이것을 여기서 바꾸지
    않고 사실로 고정한다 — 자격 정책 변경은 별도 판단이다.
    """
    assert case_b.document["episodes"][0]["grounding_status"].startswith("FAIL")
    assert case_b.presentation[0].summary_source_episode_ids == ("EP02",)
    assert "EP01" in case_b.presentation[0].excluded_summary_episode_ids
    assert "창고 문을 연다." not in case_b.markdown


def test_case_b_the_eligible_neighbour_still_reaches_the_documents(case_b):
    """오염된 구간 때문에 문서 전체가 비지는 않는다."""
    for text in (case_b.markdown, case_b.hwpx, case_b.preview):
        assert PLACEHOLDER_NOTE not in text
        assert "정리하고 나간다." in text


# ── Case C — 자막 없는 영상의 지어낸 인용 ────────────────────────────────
CASE_C = ({"summary": "창고 문을 연다.", "stt_cites": [1, 2, 3]},
          {"summary": "정리하고 나간다.", "stt_cites": [7, 8]})


@pytest.fixture(scope="module")
def case_c(tmp_path_factory):
    return _chain(tmp_path_factory.mktemp("c"), CASE_C, name="S3")


def test_case_c_the_model_cites_exist_in_the_content(case_c):
    """실제로 지어낸 인용이 들어왔는지 먼저 확인한다."""
    assert not __import__("v2_1_fixtures").scenario("S3").asr
    assert case_c.document["episodes"][0]["content_status"] == "VALID_PARSE"


def test_case_c_model_cites_do_not_become_presentation_provenance(case_c):
    """presentation lineage는 canonical episode에서 온다 — 모델 인용에서 오지 않는다."""
    known = {e.episode_id for e in case_c.presented.episodes}
    for record in case_c.presentation:
        assert set(record.source_episode_ids) <= known
        assert set(record.summary_source_episode_ids) <= known
        assert set(record.excluded_summary_episode_ids) <= known


def test_case_c_lineage_records_only_canonical_sources(case_c):
    known = {e.episode_id for e in case_c.presented.episodes}
    for record in case_c.lineage:
        assert set(record.source_episode_ids) <= known
        assert all(source.episode_id in known for source in record.sources)


def test_case_c_no_segment_reference_leaks_into_the_documents(case_c):
    """`seg#…` 표기가 문서에 provenance인 척 실리지 않는다."""
    for stage, text in _stages(case_c).items():
        assert "seg#" not in text, stage


def test_case_c_the_synthesis_sources_are_episode_ids(case_c):
    known = {e.episode_id for e in case_c.presented.episodes}
    assert set(case_c.synthesis.source_episode_ids) <= known


# ── 과잉 containment도 실패다 ────────────────────────────────────────────
def test_no_episode_is_deleted_by_containment(case_a, case_b, case_c):
    for chain in (case_a, case_b, case_c):
        assert len(chain.document["episodes"]) == len(chain.presented.episodes)
        assert len(chain.presented.episodes) == 2


def test_every_highlight_block_survives_in_both_renderers(case_a):
    ids = {record.highlight_id for record in case_a.presentation}
    assert set(_blocks(case_a.markdown)) == ids
    assert set(_blocks(case_a.hwpx)) == ids


def test_eligible_summaries_are_not_dropped(case_b):
    assert case_b.synthesis.source_episode_ids
    assert case_b.synthesis.overview


# ── 구조 가드와 행동 증거를 함께 묶는다 ──────────────────────────────────
def test_the_presentation_layer_cannot_reach_upstream_objects():
    """C-01의 architecture guard를 여기서 다시 묶어 확인한다.

    구조(닿을 수 없다)와 행동(적대적 입력도 되살아나지 않는다) 둘 다 있어야
    OPEN-11 closure가 선다.
    """
    import ast
    from pathlib import Path

    from v2_1_presentation_input import FORBIDDEN_UPSTREAM

    root = Path(__file__).resolve().parents[1] / "src"
    modules = ("v2_1_presentation_input", "v2_1_highlight", "v2_1_lineage",
               "v2_1_synthesis", "v2_1_presentation", "v2_1_render",
               "v2_1_render_hwpx", "v2_1_render_fallback")
    for name in modules:
        tree = ast.parse((root / ("%s.py" % name)).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not imported & set(FORBIDDEN_UPSTREAM), name


def test_the_regression_used_no_model_and_no_prompt_change():
    """C-09는 생성 실험이 아니다 — 저장된 fixture만 쓴다.

    문자열이 아니라 **import 문**을 본다. 금지 목록을 문자열로 훑으면 그 목록
    자체에 걸린다(A-10 · A-02 · C-06에서 겪었다).
    """
    import ast
    from pathlib import Path

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & {"transformers", "torch", "v2_1_llm_adapter",
                           "v2_1_prompt"}


# ── Case D — 통과한 dialogue조차 표현으로 넘어가지 않는다 ────────────────
#: S1의 앞 8구간은 같은 문장이라 채널이 SUSPECT다. 인용이 자격을 갖추도록 구간마다
#: 다른 발화를 넣는다 — 그래야 grounding PASS 사례를 만들 수 있다.
DISTINCT_ASR = {i: "%d번째 구간의 발화다." % i for i in range(12)}
LIVE_DIALOGUE = "다음 장소를 정한다."
CASE_D = ({"summary": "창고 문을 연다."},
          {"summary": "상자를 옮긴다.", "dialogue_note": LIVE_DIALOGUE,
           "stt_cites": [9]})


@pytest.fixture(scope="module")
def case_d(tmp_path_factory):
    return _chain(tmp_path_factory.mktemp("d"), CASE_D, asr=DISTINCT_ASR)


def test_case_d_the_dialogue_actually_passed(case_d):
    affected = case_d.document["episodes"][1]
    assert affected["grounding_status"] == "PASS"
    assert affected["dialogue_note"] == LIVE_DIALOGUE


def test_case_d_passing_dialogue_still_never_becomes_presentation_content(case_d):
    """C-04·C-05는 dialogue를 아예 쓰지 않는다 — 통과한 것도 쓰지 않는다.

    "어떤 dialogue는 되고 어떤 것은 안 되는가"를 표현 계층이 판단하기 시작하면
    그 판단이 곧 우회 경로가 된다.
    """
    assert LIVE_DIALOGUE in case_d.presented.episode("EP02").dialogue_note
    for stage in ("highlight_summary", "synthesis", "markdown", "preview",
                  "hwpx", "fallback"):
        assert LIVE_DIALOGUE not in _stages(case_d)[stage], stage


# ── 정본을 손으로 고쳐 들어오는 우회 ─────────────────────────────────────
def test_a_tampered_canonical_document_is_refused_at_the_entrance(case_a):
    """앞 계층 버그나 수작업으로 dialogue가 되살아난 문서는 표현으로 못 넘어간다."""
    from copy import deepcopy

    from v2_1_presentation_input import PresentationInputError

    tampered = deepcopy(case_a.document)
    affected = tampered["episodes"][1]
    assert affected["grounding_status"].startswith("FAIL")
    affected["dialogue_note"] = CONFUSED_NOTE
    with pytest.raises(PresentationInputError):
        presentation_input(tampered)


# ── Case E — 전 구간이 오염돼 내용이 하나도 남지 않는 문서 ───────────────
CASE_E = ({"summary": "제나가 42번 상자를 연다.",
           "dialogue_note": CONFUSED_NOTE, "stt_cites": [9]},) * 2


@pytest.fixture(scope="module")
def case_e(tmp_path_factory):
    return _chain(tmp_path_factory.mktemp("e"), CASE_E)


def test_case_e_nothing_is_eligible(case_e):
    assert all(e.grounding_status.startswith("FAIL")
               for e in case_e.presented.episodes)
    assert case_e.presentation[0].summary is None


def test_case_e_the_empty_document_is_not_filled_in(case_e):
    """비었다는 이유로 renderer·fallback이 내용을 만들어 채우지 않는다."""
    for text in (case_e.markdown, case_e.hwpx, str(case_e.fallback.payload)):
        assert "NO_RELIABLE_CONTENT" in text
        assert "상자를 옮긴다." not in text
        assert "42번" not in text


def test_case_e_the_structure_and_provenance_survive(case_e):
    """내용이 없어도 구간과 출처는 남는다 — 그것이 degradation의 정의다."""
    assert len(case_e.presented.episodes) == 2
    for text in (case_e.markdown, case_e.hwpx):
        assert "EP01" in text and "EP02" in text
