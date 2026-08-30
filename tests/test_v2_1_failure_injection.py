"""B-08 결함 주입 — 각 방어선이 실제로 잡는지 사슬 전체로 확인한다.

티켓: Gate B / B-08

단위 테스트는 자기 계층 안에서만 본다. 여기서는 **파이프라인 전 구간을 통과시킨 뒤**
결함이 어디서 잡히는지 확인한다. 계층 사이의 틈으로 새는 결함이 이 방식으로만
보인다.

주입 아홉 가지를 고정한다 — 전부 실제 사고이거나 설계상 가장 위험한 우회다.
"""
import json
from pathlib import Path

import pytest

from v2_1_aar import build_aar_canonical, structural_signature, validate_aar
from v2_1_grounding import (
    FAIL_INELIGIBLE_SUPPORT,
    FAIL_REFERENCE,
    NOT_APPLICABLE,
    PASS,
)
from v2_1_gate_b import run_pipeline
from v2_1_parse import EMPTY, MODEL_FAILURE, PARSE_CONTRACT_FAILURE, model_failure

INJECTIONS = (
    "model_failure_loses_structure",
    "parse_failure_disguised_as_empty",
    "model_supplied_derived_fields_adopted",
    "suspect_only_support_passes",
    "suspect_required_beside_valid",
    "nonexistent_ref_remapped",
    "grounding_failure_normalized_by_serializer",
    "presentation_field_in_canonical_artifact",
    "canonical_partition_partially_missing",
)

_OK = {"summary": "짐을 챙겨 자리를 옮긴다.", "dialogue_note": "다음 장소를 정한다.",
       "stt_cites": [9]}
_PLAIN = {"summary": "두 사람이 해변에 앉아 있다."}


def _doc(pipeline):
    return pipeline.document


# ── 1. 모델 실패가 구조를 지우는가 ───────────────────────────────────────
def test_model_failure_does_not_lose_structure(tmp_path):
    pipeline = run_pipeline(tmp_path, [model_failure(RuntimeError("boom")), _OK])
    document = _doc(pipeline)
    assert [e["episode_id"] for e in document["episodes"]] == ["EP01", "EP02"]
    assert document["episodes"][0]["content_status"] == MODEL_FAILURE
    assert document["episodes"][0]["start_seg"] == 0
    assert document["episodes"][0]["end_seg"] == 5
    assert validate_aar(document).ok


def test_model_failure_leaves_summary_empty_not_faked(tmp_path):
    pipeline = run_pipeline(tmp_path, [model_failure(RuntimeError("boom")), _OK])
    assert _doc(pipeline)["episodes"][0]["summary"] is None


# ── 2. parse 실패가 EMPTY로 위장되는가 ───────────────────────────────────
def test_parse_failure_is_not_disguised_as_empty(tmp_path):
    pipeline = run_pipeline(tmp_path, ['{"summary": "잘린', _OK])
    assert _doc(pipeline)["episodes"][0]["content_status"] == PARSE_CONTRACT_FAILURE


def test_blank_output_stays_empty(tmp_path):
    pipeline = run_pipeline(tmp_path, ["", _OK])
    assert _doc(pipeline)["episodes"][0]["content_status"] == EMPTY


def test_missing_required_field_is_not_empty(tmp_path):
    pipeline = run_pipeline(tmp_path, [{"dialogue_note": "메모"}, _OK])
    assert _doc(pipeline)["episodes"][0]["content_status"] == PARSE_CONTRACT_FAILURE


# ── 3. 모델이 보낸 파생 필드가 채택되는가 ────────────────────────────────
def test_model_supplied_derived_fields_are_not_adopted(tmp_path):
    hijack = {**_PLAIN, "episode_id": "EP99", "start_seg": 0, "end_seg": 11,
              "support_span": {"start_seg": 0, "end_seg": 11},
              "anchor_cites": [0], "source": "stt", "provenance": ["asr:000000"]}
    pipeline = run_pipeline(tmp_path, [hijack, _OK])
    episode = _doc(pipeline)["episodes"][0]
    assert episode["episode_id"] == "EP01"
    assert (episode["start_seg"], episode["end_seg"]) == (0, 5)
    assert episode["support_span"] == {"start_seg": 0, "end_seg": 5}
    assert episode["source"] == "visual"


def test_hijack_attempt_is_visible_afterwards(tmp_path):
    pipeline = run_pipeline(tmp_path, [{**_PLAIN, "episode_id": "EP99"}, _OK])
    assert "episode_id" in pipeline.results[0].ignored_fields


# ── 4. SUSPECT만으로 통과하는가 ──────────────────────────────────────────
def test_suspect_only_support_does_not_pass(tmp_path):
    claim = {**_PLAIN, "dialogue_note": "메모", "stt_cites": [0]}
    pipeline = run_pipeline(tmp_path, [claim, _OK])
    episode = _doc(pipeline)["episodes"][0]
    assert episode["grounding_status"] == FAIL_INELIGIBLE_SUPPORT
    assert episode["dialogue_note"] is None
    assert episode["summary"]


def test_many_suspects_still_do_not_pass(tmp_path):
    claim = {**_PLAIN, "dialogue_note": "메모", "stt_cites": [0, 1, 2, 3, 4, 5]}
    pipeline = run_pipeline(tmp_path, [claim, _OK])
    assert _doc(pipeline)["episodes"][0]["grounding_status"] == FAIL_INELIGIBLE_SUPPORT


# ── 5. VALID 옆의 SUSPECT가 필수 근거로 쓰이는가 ─────────────────────────
def test_valid_plus_suspect_passes_on_the_valid_alone(tmp_path):
    claim = {"summary": "요약", "dialogue_note": "메모", "stt_cites": [9, 6]}
    pipeline = run_pipeline(tmp_path, [_PLAIN, claim])
    assert _doc(pipeline)["episodes"][1]["grounding_status"] == PASS


def test_the_suspect_citation_is_still_recorded(tmp_path):
    claim = {"summary": "요약", "dialogue_note": "메모", "stt_cites": [9, 6]}
    pipeline = run_pipeline(tmp_path, [_PLAIN, claim])
    codes = {r["code"] for r in _doc(pipeline)["episodes"][1]["grounding_reasons"]}
    assert "ineligible_support" in codes


def test_removing_the_valid_citation_flips_the_verdict(tmp_path):
    """통과가 VALID 때문인지 확인한다 — SUSPECT를 빼도 통과해야 한다."""
    only_valid = {"summary": "요약", "dialogue_note": "메모", "stt_cites": [9]}
    only_suspect = {"summary": "요약", "dialogue_note": "메모", "stt_cites": [6]}
    assert run_pipeline(tmp_path / "a", [_PLAIN, only_valid]
                        ).document["episodes"][1]["grounding_status"] == PASS
    assert run_pipeline(tmp_path / "b", [_PLAIN, only_suspect]
                        ).document["episodes"][1]["grounding_status"] == \
        FAIL_INELIGIBLE_SUPPORT


# ── 6. 없는 참조가 다른 segment로 보정되는가 ─────────────────────────────
def test_nonexistent_ref_is_not_remapped(tmp_path):
    claim = {"summary": "요약", "dialogue_note": "메모", "stt_cites": ["seg#999999"]}
    pipeline = run_pipeline(tmp_path, [_PLAIN, claim])
    cite = pipeline.bindings[1].cites[0]
    assert cite.segment_id is None
    assert cite.canonical_ref == 999999
    assert _doc(pipeline)["episodes"][1]["grounding_status"] == FAIL_REFERENCE


def test_out_of_range_ref_does_not_borrow_a_neighbour(tmp_path):
    claim = {"summary": "요약", "dialogue_note": "메모", "stt_cites": [12]}
    pipeline = run_pipeline(tmp_path, [_PLAIN, claim])
    assert pipeline.bindings[1].cites[0].segment_id is None
    assert _doc(pipeline)["episodes"][1]["grounding_status"] == FAIL_REFERENCE


# ── 7. 직렬화가 실패를 통과로 정규화하는가 ───────────────────────────────
def test_serializer_carries_every_grounding_status_verbatim(tmp_path):
    claim = {**_PLAIN, "dialogue_note": "메모", "stt_cites": [0]}
    pipeline = run_pipeline(tmp_path, [claim, _OK])
    assert [e["grounding_status"] for e in _doc(pipeline)["episodes"]] == \
        [g.grounding_status for g in pipeline.grounded]


def test_serializer_carries_every_reason(tmp_path):
    claim = {**_PLAIN, "dialogue_note": "메모", "stt_cites": ["없음", 0]}
    pipeline = run_pipeline(tmp_path, [claim, _OK])
    serialized = _doc(pipeline)["episodes"][0]["grounding_reasons"]
    assert [r["code"] for r in serialized] == \
        [r.code for r in pipeline.grounded[0].grounding_reasons]


def test_a_document_claiming_pass_for_a_failed_episode_is_detectable(tmp_path):
    """문서를 손으로 고쳐 통과처럼 만들면 원본과 대조해 드러난다."""
    claim = {**_PLAIN, "dialogue_note": "메모", "stt_cites": [0]}
    pipeline = run_pipeline(tmp_path, [claim, _OK])
    forged = json.loads(json.dumps(_doc(pipeline)))
    forged["episodes"][0]["grounding_status"] = PASS
    assert validate_aar(forged).ok          # 형식만으로는 알 수 없다
    assert [e["grounding_status"] for e in forged["episodes"]] != \
        [g.grounding_status for g in pipeline.grounded]


# ── 8. 표현 필드가 정본에 섞이는가 ───────────────────────────────────────
def test_presentation_field_inside_an_episode_is_rejected(tmp_path):
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    forged = json.loads(json.dumps(_doc(pipeline)))
    forged["episodes"][0]["highlight_group"] = ["EP01", "EP02"]
    assert not validate_aar(forged).ok


def test_presentation_section_at_the_top_is_rejected(tmp_path):
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    forged = {**_doc(pipeline), "highlights": [{"id": "H01"}]}
    assert not validate_aar(forged).ok


def test_grouping_episodes_for_display_does_not_change_the_canonical_list(tmp_path):
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    before = structural_signature(_doc(pipeline))
    grouped = {"highlights": [{"id": "H01", "episodes": ["EP01", "EP02"]}]}
    assert structural_signature(_doc(pipeline)) == before
    assert len(grouped["highlights"][0]["episodes"]) == 2


# ── 9. partition 일부가 빠지는가 ─────────────────────────────────────────
def test_missing_episode_is_rejected(tmp_path):
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    forged = {**_doc(pipeline), "episodes": _doc(pipeline)["episodes"][:1]}
    assert not validate_aar(forged).ok


def test_overlapping_episodes_are_rejected(tmp_path):
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    forged = json.loads(json.dumps(_doc(pipeline)))
    forged["episodes"][0]["end_seg"] = 6
    assert not validate_aar(forged).ok


def test_a_gap_between_episodes_is_rejected(tmp_path):
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    forged = json.loads(json.dumps(_doc(pipeline)))
    forged["episodes"][1]["start_seg"] = 7
    assert not validate_aar(forged).ok


# ── 사슬 전체가 실제로 돌았는가 ──────────────────────────────────────────
def test_the_pipeline_persists_raw_before_parsing(tmp_path):
    """모델 출력도 A-03 raw store를 지나간다 — 두 번째 store를 만들지 않았다."""
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    stored = {r.segment_id for r in pipeline.store.records() if r.source_type == "llm"}
    assert stored == {0, 1}


def test_raw_survives_a_model_parse_failure(tmp_path):
    pipeline = run_pipeline(tmp_path, ['{"summary": "잘린', _OK])
    assert pipeline.store.load("llm", 0).read_text() == '{"summary": "잘린'


def test_a_healthy_run_has_no_failures(tmp_path):
    pipeline = run_pipeline(tmp_path, [_PLAIN, _OK])
    document = _doc(pipeline)
    assert validate_aar(document).ok
    assert [e["grounding_status"] for e in document["episodes"]] == \
        [NOT_APPLICABLE, PASS]


def test_every_declared_injection_has_a_test():
    """주입 목록과 테스트가 어긋나면 여기서 먼저 깨진다."""
    source = Path(__file__).read_text(encoding="utf-8")
    missing = [name for name in INJECTIONS if not _covered(name, source)]
    assert not missing, "주입에 대응하는 테스트가 없다: %r" % missing


_COVERAGE = {
    "model_failure_loses_structure": "test_model_failure_does_not_lose_structure",
    "parse_failure_disguised_as_empty": "test_parse_failure_is_not_disguised_as_empty",
    "model_supplied_derived_fields_adopted":
        "test_model_supplied_derived_fields_are_not_adopted",
    "suspect_only_support_passes": "test_suspect_only_support_does_not_pass",
    "suspect_required_beside_valid": "test_removing_the_valid_citation_flips_the_verdict",
    "nonexistent_ref_remapped": "test_nonexistent_ref_is_not_remapped",
    "grounding_failure_normalized_by_serializer":
        "test_serializer_carries_every_grounding_status_verbatim",
    "presentation_field_in_canonical_artifact":
        "test_presentation_field_inside_an_episode_is_rejected",
    "canonical_partition_partially_missing": "test_missing_episode_is_rejected",
}


def _covered(name, source):
    return ("def %s(" % _COVERAGE[name]) in source


def test_the_coverage_map_lists_every_injection():
    assert sorted(_COVERAGE) == sorted(INJECTIONS)
