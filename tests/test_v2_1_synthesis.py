"""C-04 Global Synthesis — 새 사실을 만들지 않는다 (Gate C).

```
GLS-004 P0   자동 완전 검증을 주장하지 않는다
GLS-005 P0   source는 실재하는 canonical episode다
GLS-006 P0   grounding 실패 content를 사실처럼 종합하지 않는다
GLS-007 P1   믿을 내용이 없으면 억지 결론을 만들지 않는다
```

**LLM을 부르지 않는다.** 여기서 생성을 다시 열면 Gate B에서 만든 grounding 경계를
표현 단계에서 되돌리게 된다. 하는 일은 canonical에 남은 summary의 결정적 재배열·
구조화뿐이다.
"""
import ast
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import build_lineage
from v2_1_presentation_input import FORBIDDEN_UPSTREAM, presentation_input
from v2_1_synthesis import (
    ASSURANCE_PHRASES,
    LIMITATION,
    LIMITED,
    NO_RELIABLE_CONTENT,
    SUFFICIENT,
    GlobalSynthesis,
    SynthesisError,
    build_synthesis,
    validate_synthesis,
)

MODULE = Path(__file__).resolve().parents[1] / "src/v2_1_synthesis.py"

THREE = ((0, 3), (4, 7), (8, 11))
GOOD = ({"summary": "창고 문을 연다."},
        {"summary": "상자를 옮긴다."},
        {"summary": "불을 끄고 나간다."})
#: 앵커가 근거로 뒷받침되지 않아 grounding이 실패하는 내용.
UNSUPPORTED = ({"summary": "제나가 42번 상자를 연다.",
                "dialogue_note": "42번이라고 말한다.", "stt_cites": [1]},) * 3
#: EP03에 근거를 갖춘 dialogue가 살아남는 구성.
WITH_DIALOGUE = (GOOD[0], GOOD[1],
                 {"summary": "불을 끄고 나간다.",
                  "dialogue_note": "다음 장소를 정한다.", "stt_cites": [9]})


def _presented(tmp_path, payloads=GOOD):
    return presentation_input(
        run_pipeline(tmp_path, payloads, spans=THREE).document
    )


def _synthesis(presented, groups=(("EP01", "EP02"), ("EP03",))):
    highlights = build_highlights(
        presented, [HighlightSpec(group) for group in groups]
    )
    return build_synthesis(presented, build_lineage(presented, highlights))


@pytest.fixture
def presented(tmp_path):
    return _presented(tmp_path)


# ── GLS-001 · 002 · 003 결정적 baseline ──────────────────────────────────
def test_gls_001_overview_is_built_from_canonical_summaries(presented):
    synthesis = _synthesis(presented)
    assert synthesis.overview
    for episode in presented.episodes:
        assert episode.summary in synthesis.overview


def test_gls_002_analysis_is_structured_by_highlight(presented):
    synthesis = _synthesis(presented)
    assert len(synthesis.analysis) == 2
    assert synthesis.analysis[0].startswith("H01")
    assert "EP01" in synthesis.analysis[0] and "EP02" in synthesis.analysis[0]


def test_gls_003_conclusion_stays_inside_the_supported_range(presented):
    synthesis = _synthesis(presented)
    assert presented.episodes[0].summary in synthesis.conclusion
    assert presented.episodes[-1].summary in synthesis.conclusion


def test_the_result_is_deterministic(presented):
    assert _synthesis(presented) == _synthesis(presented)


def test_overview_follows_canonical_order_not_input_order(presented):
    forward = _synthesis(presented, (("EP01",), ("EP02",), ("EP03",)))
    backward = _synthesis(presented, (("EP03",), ("EP02",), ("EP01",)))
    assert forward.overview == backward.overview
    assert forward.source_episode_ids == ("EP01", "EP02", "EP03")
    assert backward.source_episode_ids == ("EP01", "EP02", "EP03")


# ── GLS-004 완전 검증을 주장하지 않는다 ──────────────────────────────────
def test_gls_004_limitation_is_always_stated(presented):
    synthesis = _synthesis(presented)
    assert synthesis.limitation == LIMITATION
    assert "not automatically verified" in synthesis.limitation


def test_gls_004_no_assurance_wording_is_emitted(presented):
    synthesis = _synthesis(presented)
    blob = " ".join([synthesis.overview, synthesis.conclusion,
                     *synthesis.analysis, synthesis.limitation]).lower()
    for phrase in ASSURANCE_PHRASES:
        assert phrase.lower() not in blob


def test_gls_004_injected_assurance_wording_is_reported(presented):
    synthesis = _synthesis(presented)
    tampered = GlobalSynthesis(
        overview=synthesis.overview + " fully verified",
        analysis=synthesis.analysis,
        conclusion=synthesis.conclusion,
        source_episode_ids=synthesis.source_episode_ids,
        excluded_episode_ids=synthesis.excluded_episode_ids,
        synthesis_status=synthesis.synthesis_status,
        limitation=synthesis.limitation,
    )
    assert validate_synthesis(tampered, presented)


def test_gls_004_a_missing_limitation_is_reported(presented):
    synthesis = _synthesis(presented)
    tampered = GlobalSynthesis(
        overview=synthesis.overview, analysis=synthesis.analysis,
        conclusion=synthesis.conclusion,
        source_episode_ids=synthesis.source_episode_ids,
        excluded_episode_ids=synthesis.excluded_episode_ids,
        synthesis_status=synthesis.synthesis_status, limitation="",
    )
    assert validate_synthesis(tampered, presented)


# ── GLS-005 source는 실재한다 ────────────────────────────────────────────
def test_gls_005_sources_resolve_to_canonical_episodes(presented):
    synthesis = _synthesis(presented)
    known = {e.episode_id for e in presented.episodes}
    assert set(synthesis.source_episode_ids) <= known
    assert validate_synthesis(synthesis, presented) == []


def test_gls_005_an_unknown_source_is_reported(presented):
    synthesis = _synthesis(presented)
    tampered = GlobalSynthesis(
        overview=synthesis.overview, analysis=synthesis.analysis,
        conclusion=synthesis.conclusion,
        source_episode_ids=synthesis.source_episode_ids + ("EP99",),
        excluded_episode_ids=synthesis.excluded_episode_ids,
        synthesis_status=synthesis.synthesis_status,
        limitation=synthesis.limitation,
    )
    assert any("EP99" in failure for failure in validate_synthesis(tampered,
                                                                   presented))


def test_gls_005_text_without_any_source_is_reported(presented):
    synthesis = _synthesis(presented)
    tampered = GlobalSynthesis(
        overview=synthesis.overview, analysis=synthesis.analysis,
        conclusion=synthesis.conclusion, source_episode_ids=(),
        excluded_episode_ids=synthesis.excluded_episode_ids,
        synthesis_status=synthesis.synthesis_status,
        limitation=synthesis.limitation,
    )
    assert any("text without any source" in failure
               for failure in validate_synthesis(tampered, presented))


# ── GLS-006 실패한 내용은 종합되지 않는다 ────────────────────────────────
def test_gls_006_failed_episodes_are_excluded(tmp_path):
    presented = _presented(tmp_path, UNSUPPORTED)
    failed = [e for e in presented.episodes if e.grounding_status.startswith("FAIL")]
    assert failed, "실패 사례가 없으면 이 검사는 무의미하다"
    synthesis = _synthesis(presented)
    for episode in failed:
        assert episode.episode_id not in synthesis.source_episode_ids
        assert episode.episode_id in synthesis.excluded_episode_ids
        assert episode.summary not in synthesis.overview


def test_gls_006_a_mixed_video_keeps_only_the_usable_part(tmp_path):
    presented = _presented(tmp_path, (GOOD[0], UNSUPPORTED[0], GOOD[2]))
    synthesis = _synthesis(presented)
    usable = [e for e in presented.episodes
              if not e.grounding_status.startswith("FAIL")]
    assert synthesis.source_episode_ids == tuple(e.episode_id for e in usable)
    assert synthesis.synthesis_status == LIMITED


def test_gls_006_dialogue_is_never_a_synthesis_source(tmp_path):
    """dialogue를 아예 쓰지 않는다 — 제거된 dialogue가 들어올 경로 자체가 없다.

    통과한 dialogue조차 쓰지 않는다. 쓰기 시작하면 "어떤 dialogue는 되고 어떤
    것은 안 되는가"가 표현 계층의 판단이 되고, 그 판단은 여기 있으면 안 된다.
    """
    presented = _presented(tmp_path, WITH_DIALOGUE)
    spoken = [e for e in presented.episodes if e.dialogue_note]
    assert spoken, "dialogue가 살아남은 사례가 없으면 이 검사는 무의미하다"
    synthesis = _synthesis(presented)
    for episode in spoken:
        assert episode.dialogue_note not in synthesis.overview
        assert episode.dialogue_note not in synthesis.conclusion
        assert all(episode.dialogue_note not in line for line in synthesis.analysis)


def test_gls_006_an_excluded_episode_named_as_source_is_reported(tmp_path):
    presented = _presented(tmp_path, (GOOD[0], UNSUPPORTED[0], GOOD[2]))
    synthesis = _synthesis(presented)
    failed = next(e for e in presented.episodes
                  if e.grounding_status.startswith("FAIL"))
    tampered = GlobalSynthesis(
        overview=synthesis.overview, analysis=synthesis.analysis,
        conclusion=synthesis.conclusion,
        source_episode_ids=synthesis.source_episode_ids + (failed.episode_id,),
        excluded_episode_ids=synthesis.excluded_episode_ids,
        synthesis_status=synthesis.synthesis_status,
        limitation=synthesis.limitation,
    )
    assert validate_synthesis(tampered, presented)


# ── GLS-007 없으면 만들지 않는다 ─────────────────────────────────────────
def test_gls_007_all_sources_usable_is_sufficient(presented):
    assert _synthesis(presented).synthesis_status == SUFFICIENT


def test_gls_007_no_reliable_content_produces_no_concrete_conclusion(tmp_path):
    presented = _presented(tmp_path, UNSUPPORTED)
    synthesis = _synthesis(presented)
    if synthesis.source_episode_ids:
        pytest.skip("이 fixture에서 전건 실패가 재현되지 않았다")
    assert synthesis.synthesis_status == NO_RELIABLE_CONTENT
    assert synthesis.analysis == ()
    for episode in presented.episodes:
        assert episode.summary not in synthesis.conclusion
    # 자기 검증기를 통과해야 한다 — 구체 결론을 지어내면 여기서 걸린다.
    assert validate_synthesis(synthesis, presented) == []


def test_gls_007_a_concrete_conclusion_without_sources_is_reported(presented):
    synthesis = _synthesis(presented)
    tampered = GlobalSynthesis(
        overview="", analysis=(), conclusion="영상에서는 정리가 이루어졌다.",
        source_episode_ids=(), excluded_episode_ids=(),
        synthesis_status=NO_RELIABLE_CONTENT, limitation=LIMITATION,
    )
    assert validate_synthesis(tampered, presented)


# ── 입력 계약 ────────────────────────────────────────────────────────────
def test_only_a_presentation_input_is_accepted(tmp_path):
    document = run_pipeline(tmp_path, GOOD, spans=THREE).document
    with pytest.raises(SynthesisError):
        build_synthesis(document, ())


def test_lineage_is_required_for_analysis(presented):
    """analysis는 lineage 위에서만 만든다 — 출처 없는 절은 만들지 않는다."""
    synthesis = build_synthesis(presented, ())
    assert synthesis.analysis == ()
    assert synthesis.overview


# ── 생성기를 부르지 않는다 ───────────────────────────────────────────────
def test_the_module_calls_no_model():
    """LLM 도입은 별도 티켓·별도 contract다. Gate C 안에 몰래 넣지 않는다."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    assert not names & {"transformers", "ollama", "generator", "prompt", "model",
                        "invoke", "v2_1_llm_adapter", "v2_1_prompt"}


def test_the_module_does_not_import_pre_grounding_layers():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & set(FORBIDDEN_UPSTREAM), sorted(imported)
