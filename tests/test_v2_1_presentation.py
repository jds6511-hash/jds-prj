"""C-05 Presentation schema — 새 사건 서술을 만들지 않는다 (Gate C).

```
REF-001  형식 참조의 저자는 사용자다
REF-002  형식 참조는 GT가 아니다
REF-005  행 수를 목표로 삼지 않는다
REF-006  절 구성만 참고한다 — 문장·시간·개수는 가져오지 않는다
```

Highlight는 **묶고 재배치하는 자리**이지 서술을 만드는 자리가 아니다. summary는
canonical episode summary의 결정적 조합으로만 채운다.

`source_episode_ids`(무엇으로 구성됐는가)와 `summary_source_episode_ids`(무엇이
문장에 쓰였는가)를 **분리한다.** 섞으면 실패한 구간이 문장에 들어왔는지를 사후에
가릴 수 없다.
"""
import ast
import json
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_presentation import (
    FORMAT_REFERENCE,
    PRESENTATION_SCHEMA,
    SECTION_NAMES,
    SUMMARY_AVAILABLE,
    SUMMARY_NO_RELIABLE_CONTENT,
    SUMMARY_SEPARATOR,
    PresentationError,
    build_presentation,
    serialize_presentation,
    validate_presentation,
)
from v2_1_presentation_input import FORBIDDEN_UPSTREAM, presentation_input

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/v2_1_presentation.py"
FORMAT_DOC = ROOT / "docs/finalization/REPORT_FORMAT_REFERENCE_2026-08-30.md"

THREE = ((0, 3), (4, 7), (8, 11))
#: 근거를 갖춘 dialogue가 있어 grounding이 PASS로 남는 구성.
GROUNDED = ({"summary": "창고 문을 연다.",
             "dialogue_note": "다음 장소를 정한다.", "stt_cites": [1]},
            {"summary": "상자를 옮긴다.",
             "dialogue_note": "다음 장소를 정한다.", "stt_cites": [5]},
            {"summary": "불을 끄고 나간다.",
             "dialogue_note": "다음 장소를 정한다.", "stt_cites": [9]})
#: 앵커가 뒷받침되지 않아 grounding이 실패하는 구성.
UNSUPPORTED = {"summary": "제나가 42번 상자를 연다.",
               "dialogue_note": "42번이라고 말한다.", "stt_cites": [1]}


#: S1의 앞 8구간은 같은 문장이 반복돼 채널 전체가 SUSPECT가 된다(A-05).
#: 인용이 자격을 갖추려면 발화가 서로 달라야 하므로 구간마다 다른 문장을 넣는다.
DISTINCT_ASR = {i: "%d번째 구간의 발화다." % i for i in range(8)}


def _presented(tmp_path, payloads=GROUNDED):
    return presentation_input(
        run_pipeline(tmp_path, payloads, spans=THREE,
                     asr_overrides=DISTINCT_ASR).document
    )


def _build(presented, groups=(("EP01", "EP02"), ("EP03",)), labels=(None, None)):
    highlights = build_highlights(
        presented,
        [HighlightSpec(group, label=label) for group, label in zip(groups, labels)],
    )
    return build_presentation(presented, highlights)


def _replace(record, **changes):
    """frozen record 한 필드만 바꿔 위조본을 만든다."""
    fields = {f: getattr(record, f) for f in record.__dataclass_fields__}
    return record.__class__(**{**fields, **changes})


@pytest.fixture
def presented(tmp_path):
    return _presented(tmp_path)


# ── 확정된 표현 객체 ─────────────────────────────────────────────────────
def test_the_schema_carries_identity_time_and_lineage(presented):
    first = _build(presented)[0]
    assert first.highlight_id == "H01"
    assert first.start_sec == presented.episode("EP01").start_sec
    assert first.end_sec == presented.episode("EP02").end_sec
    assert first.source_episode_ids == ("EP01", "EP02")
    assert first.segment_refs


def test_a_label_is_carried_verbatim(presented):
    labelled = _build(presented, labels=("창고 정리", None))[0]
    assert labelled.label == "창고 정리"


def test_the_result_is_deterministic(presented):
    assert _build(presented) == _build(presented)


# ── summary는 조합일 뿐이다 ──────────────────────────────────────────────
def test_summary_is_a_deterministic_composition(presented):
    first = _build(presented)[0]
    assert first.summary == SUMMARY_SEPARATOR.join(
        (presented.episode("EP01").summary, presented.episode("EP02").summary)
    )
    assert first.summary_status == SUMMARY_AVAILABLE


def test_summary_follows_canonical_order_not_grouping_order(presented):
    forward = _build(presented, (("EP01", "EP02"),))[0]
    backward = _build(presented, (("EP02", "EP01"),))[0]
    assert forward.summary == backward.summary
    assert backward.summary_source_episode_ids == ("EP01", "EP02")


def test_no_connective_is_invented(presented):
    """원문 summary에 없던 관계어를 끼워 넣지 않는다."""
    joined = " ".join(record.summary or "" for record in _build(presented))
    sources = " ".join(e.summary for e in presented.episodes)
    for connective in ("이후", "때문에", "따라서", "함께", "이를 통해"):
        if connective not in sources:
            assert connective not in joined


def test_duplicate_summaries_are_not_collapsed(tmp_path):
    """중복 제거를 시작하면 표현 계층이 의미 동일성을 판정하게 된다."""
    same = {"summary": "문을 연다.",
            "dialogue_note": "다음 장소를 정한다.", "stt_cites": [1]}
    presented = _presented(tmp_path, (same,
                                      dict(same, stt_cites=[5]),
                                      dict(same, stt_cites=[9])))
    record = _build(presented, (("EP01", "EP02"),))[0]
    assert record.summary.count("문을 연다.") == 2


# ── lineage와 summary lineage를 가른다 ───────────────────────────────────
def test_a_failed_episode_stays_in_lineage_but_not_in_the_summary(tmp_path):
    presented = _presented(tmp_path, (GROUNDED[0], UNSUPPORTED, GROUNDED[2]))
    failed = next(e for e in presented.episodes
                  if e.grounding_status != "PASS")
    record = _build(presented, (("EP01", "EP02", "EP03"),))[0]
    assert failed.episode_id in record.source_episode_ids
    assert failed.episode_id not in record.summary_source_episode_ids
    assert failed.episode_id in record.excluded_summary_episode_ids
    assert failed.summary not in record.summary


def test_the_excluded_list_is_not_dropped(tmp_path):
    presented = _presented(tmp_path, (GROUNDED[0], UNSUPPORTED, GROUNDED[2]))
    record = _build(presented, (("EP01", "EP02", "EP03"),))[0]
    assert set(record.source_episode_ids) == (
        set(record.summary_source_episode_ids)
        | set(record.excluded_summary_episode_ids)
    )


def test_no_usable_source_produces_no_placeholder_sentence(tmp_path):
    presented = _presented(tmp_path, (UNSUPPORTED,) * 3)
    record = _build(presented, (("EP01", "EP02"),))[0]
    assert record.summary is None
    assert record.summary_status == SUMMARY_NO_RELIABLE_CONTENT
    assert record.summary_source_episode_ids == ()
    assert record.source_episode_ids == ("EP01", "EP02")


# ── 검증기 ───────────────────────────────────────────────────────────────
def test_a_clean_presentation_validates(presented):
    assert validate_presentation(_build(presented), presented) == []


def test_a_summary_that_is_not_a_composition_is_reported(presented):
    record = _build(presented)[0]
    tampered = _replace(record, summary=record.summary + " 그래서 두 사람은 만족했다.")
    assert validate_presentation((tampered,), presented)


def test_an_ineligible_summary_source_is_reported(tmp_path):
    presented = _presented(tmp_path, (GROUNDED[0], UNSUPPORTED, GROUNDED[2]))
    record = _build(presented, (("EP01", "EP02", "EP03"),))[0]
    failed = next(e for e in presented.episodes if e.grounding_status != "PASS")
    tampered = _replace(
        record,
        summary_source_episode_ids=record.summary_source_episode_ids
        + (failed.episode_id,),
    )
    assert validate_presentation((tampered,), presented)


def test_a_summary_without_any_source_is_reported(presented):
    """lineage 일관성은 맞춰 둔 채로 문장만 출처를 잃게 만든다.

    그래야 다른 검사에 가려지지 않고 이 검사 하나가 답한다.
    """
    record = _build(presented)[0]
    tampered = _replace(record, summary_source_episode_ids=(),
                        excluded_summary_episode_ids=record.source_episode_ids)
    assert any("without any source" in failure
               for failure in validate_presentation((tampered,), presented))


def test_an_unknown_episode_is_refused(presented):
    highlights = build_highlights(presented, (HighlightSpec(("EP01",)),))
    forged = highlights[0].__class__(
        highlight_id="H01", label=None, episode_refs=("EP99",),
        segment_refs=(0,), display_range={"start_sec": 0.0, "end_sec": 1.0},
    )
    with pytest.raises(PresentationError):
        build_presentation(presented, (forged,))


def test_only_a_presentation_input_is_accepted(tmp_path):
    document = run_pipeline(tmp_path, GROUNDED, spans=THREE).document
    with pytest.raises(PresentationError):
        build_presentation(document, ())


# ── REF-001 · 002 형식 참조의 신분 ───────────────────────────────────────
def test_ref_001_the_format_reference_names_its_author(presented):
    assert FORMAT_REFERENCE["author"] == "user"
    assert FORMAT_REFERENCE["role"] == "format_reference"


def test_ref_002_the_format_reference_is_not_ground_truth(presented):
    assert FORMAT_REFERENCE["is_ground_truth"] is False
    payload = json.loads(serialize_presentation(_build(presented)))
    assert payload["format_reference"]["is_ground_truth"] is False


def test_ref_002_a_ground_truth_claim_is_reported(presented):
    assert validate_presentation(
        _build(presented), presented,
        format_reference={**FORMAT_REFERENCE, "is_ground_truth": True},
    )


# ── REF-005 행 수는 목표가 아니다 ────────────────────────────────────────
def test_ref_005_any_number_of_highlights_serializes_the_same_way(presented):
    for count in (1, 3, 12):
        specs = [HighlightSpec(("EP01",)) for _ in range(count)]
        payload = json.loads(serialize_presentation(
            build_presentation(presented, build_highlights(presented, specs))
        ))
        assert payload["schema"] == PRESENTATION_SCHEMA
        assert len(payload["highlights"]) == count


def test_ref_005_no_row_count_is_read_from_the_format_reference():
    """형식 참조에서 개수를 읽어 highlight 수를 맞추는 경로가 없어야 한다."""
    assert not {"rows", "row_count", "target_rows", "n_rows"} & set(FORMAT_REFERENCE)
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    assert not names & {"row_count", "target_count", "target_rows", "expected_rows"}


# ── REF-006 절 구성만 가져온다 ───────────────────────────────────────────
def test_ref_006_only_section_names_come_from_the_reference():
    assert SECTION_NAMES == ("개요", "주요 사건 및 내용", "핵심 내용 분석",
                             "결론", "근거 및 생성 정보")


def test_ref_006_no_sentence_from_the_human_report_reaches_the_output(presented):
    """사람이 쓴 보고서의 문장·고유명이 생성물에 들어오면 안 된다."""
    reference = FORMAT_DOC.read_text(encoding="utf-8")
    blob = serialize_presentation(_build(presented)) + MODULE.read_text(
        encoding="utf-8")
    for phrase in ("연습생 시절", "쪽샘", "신라 공주", "댄스 챌린지"):
        assert phrase in reference, "참조 문서가 바뀌었다 — 검사를 갱신해야 한다"
        assert phrase not in blob


def test_ref_006_no_time_range_from_the_human_report_is_used(presented):
    for record in _build(presented):
        assert record.start_sec <= record.end_sec
        assert record.end_sec <= max(e.end_sec for e in presented.episodes)


# ── 상류로 손을 뻗지 않는다 ──────────────────────────────────────────────
def test_the_module_does_not_import_pre_grounding_layers():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & set(FORBIDDEN_UPSTREAM), sorted(imported)


def test_the_module_calls_no_model():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    assert not names & {"transformers", "ollama", "generator", "prompt", "model",
                        "invoke", "v2_1_llm_adapter", "v2_1_prompt"}
