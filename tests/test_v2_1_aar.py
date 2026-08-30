"""B-07 aar_canonical 스키마 + 직렬화.

티켓: Gate B / B-07
규격: SPEC §1 — `aar_canonical.json`까지가 정본이다

```
AAR-001  presentation 없이 단독으로 유효
AAR-002  canonical partition 전체 포함
AAR-003  provenance 존재
AAR-004  grounding 상태 존재
AAR-005  presentation이 canonical을 바꾸지 못한다
AAR-006  재실행 구조 동일 (run id·시각 때문에 byte equality를 요구하지 않는다)
AAR-007  직렬화 왕복에서 의미 보존 (P1)
```

직렬화기는 **재판정하지 않는다.** grounding 실패를 누락하거나 PASS처럼 정규화하면
그 자체가 GRD-009 위반이다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_aar import (
    SCHEMA,
    AarInvalid,
    build_aar_canonical,
    load_aar,
    serialize_aar,
    structural_signature,
    validate_aar,
)
from v2_1_binding import bind_cites
from v2_1_content import merge_content
from v2_1_episode import build_episodes
from v2_1_fixtures import scenario
from v2_1_grounding import (
    FAIL_INELIGIBLE_SUPPORT,
    NOT_APPLICABLE,
    PASS,
    apply_grounding,
    validate_grounding,
)
from v2_1_parse import SegmentRegistry, model_failure, parse_json_payload
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_scan import code_only
from v2_1_timeline import build_timeline

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_aar.py"

_PAYLOADS = [
    {"summary": "두 사람이 해변에 자리를 잡는다.", "dialogue_note": "메모",
     "stt_cites": [0]},                                   # SUSPECT만 → FAIL
    {"summary": "짐을 챙겨 자리를 옮긴다.", "dialogue_note": "다음 장소를 정한다.",
     "stt_cites": [9]},                                   # PASS
]


def _world(tmp_path, payloads=None, spans=((0, 5), (6, 11))):
    s = scenario("S1")
    store = RawStore(tmp_path / "raw", run_id="run-001", video_id="S1")
    judged = {}
    for source_type, channel in (("asr", s.asr), ("vlm", s.caption)):
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    timeline = build_timeline(s.segments, judged)
    episodes = build_episodes(list(spans), s.segments, timeline=timeline)
    registry = SegmentRegistry(s.segments)

    grounded = []
    for episode, payload in zip(episodes, payloads or _PAYLOADS):
        outcome = (payload if not isinstance(payload, dict)
                   else parse_json_payload(json.dumps(payload), registry))
        binding = bind_cites(merge_content(episode, outcome), timeline, registry)
        grounded.append(apply_grounding(binding, validate_grounding(binding, store)))
    return s, timeline, grounded


@pytest.fixture
def doc(tmp_path):
    s, timeline, grounded = _world(tmp_path)
    return build_aar_canonical(video_id="S1", run_id="run-001",
                               segments=s.segments, grounded=grounded,
                               timeline=timeline)


# ── AAR-001 단독 유효 ────────────────────────────────────────────────────
def test_aar_001_document_is_valid_on_its_own(doc):
    assert doc["schema"] == SCHEMA
    assert validate_aar(doc).ok


def test_aar_001_no_presentation_section_is_required(doc):
    for absent in ("highlights", "report_highlights", "synthesis", "rendered"):
        assert absent not in doc


def test_aar_001_missing_schema_is_refused(doc):
    broken = {k: v for k, v in doc.items() if k != "schema"}
    assert not validate_aar(broken).ok


def test_aar_001_serializes_to_json(doc):
    assert json.loads(serialize_aar(doc))["schema"] == SCHEMA


# ── AAR-002 전체 partition ───────────────────────────────────────────────
def test_aar_002_every_episode_is_present(doc):
    assert [e["episode_id"] for e in doc["episodes"]] == ["EP01", "EP02"]


def test_aar_002_partition_covers_every_segment(doc):
    owned = [seg for e in doc["episodes"]
             for seg in range(e["start_seg"], e["end_seg"] + 1)]
    assert sorted(owned) == list(range(12))


def test_aar_002_a_missing_episode_is_refused(doc):
    broken = {**doc, "episodes": doc["episodes"][:1]}
    result = validate_aar(broken)
    assert not result.ok
    assert any("partition" in f for f in result.failures)


def test_aar_002_reuses_the_gate_a_partition_validator():
    """겹침·빈틈 판정을 여기서 다시 구현하지 않는다."""
    code = code_only(SRC)
    assert "validate_partition" in code


def test_aar_002_empty_document_is_refused(doc):
    assert not validate_aar({**doc, "episodes": []}).ok


# ── AAR-003 provenance ───────────────────────────────────────────────────
def test_aar_003_every_episode_carries_provenance(doc):
    for episode in doc["episodes"]:
        assert episode["provenance"]
        assert episode["support_span"] and episode["anchor_cites"]


def test_aar_003_provenance_refs_are_traceable(doc):
    for episode in doc["episodes"]:
        for ref in episode["provenance"]:
            source_type, segment_id = ref.split(":")
            assert source_type in ("asr", "vlm", "ocr")
            assert episode["start_seg"] <= int(segment_id) <= episode["end_seg"]


def test_aar_003_missing_provenance_is_refused(doc):
    broken = json.loads(json.dumps(doc))
    broken["episodes"][0].pop("provenance")
    assert not validate_aar(broken).ok


# ── AAR-004 grounding 상태 ───────────────────────────────────────────────
def test_aar_004_grounding_status_is_present_on_every_episode(doc):
    assert [e["grounding_status"] for e in doc["episodes"]] == [
        FAIL_INELIGIBLE_SUPPORT, PASS
    ]


def test_aar_004_failure_reasons_are_serialized(doc):
    failed = doc["episodes"][0]
    assert failed["grounding_reasons"]
    assert {"code", "detail"} <= set(failed["grounding_reasons"][0])


def test_aar_004_failure_is_not_normalized_to_pass(doc):
    """실패를 통과처럼 적으면 그 자체가 GRD-009 위반이다."""
    assert doc["episodes"][0]["grounding_status"] != PASS
    assert doc["episodes"][0]["dialogue_note"] is None
    assert doc["episodes"][0]["summary"]


def test_aar_004_unknown_grounding_status_is_refused(doc):
    broken = json.loads(json.dumps(doc))
    broken["episodes"][0]["grounding_status"] = "OK"
    assert not validate_aar(broken).ok


def test_aar_004_content_status_is_kept(tmp_path):
    s, timeline, grounded = _world(
        tmp_path, payloads=[model_failure(RuntimeError("boom")), _PAYLOADS[1]]
    )
    doc = build_aar_canonical(video_id="S1", run_id="run-001",
                              segments=s.segments, grounded=grounded,
                              timeline=timeline)
    assert doc["episodes"][0]["content_status"] == "MODEL_FAILURE"
    assert doc["episodes"][0]["summary"] is None
    assert validate_aar(doc).ok


# ── AAR-005 presentation은 canonical을 바꾸지 못한다 ─────────────────────
def test_aar_005_presentation_keys_inside_an_episode_are_refused(doc):
    broken = json.loads(json.dumps(doc))
    broken["episodes"][0]["highlight_group"] = ["EP01", "EP02"]
    result = validate_aar(broken)
    assert not result.ok
    assert any("presentation" in f for f in result.failures)


def test_aar_005_a_presentation_section_does_not_belong_here(doc):
    assert not validate_aar({**doc, "highlights": [{"id": "H01"}]}).ok


def test_aar_005_episode_list_is_the_fixed_point(doc):
    """표현 계층이 무엇을 묶든 이 목록은 그대로다."""
    before = structural_signature(doc)
    presentation = {"highlights": [{"id": "H01", "episodes": ["EP01", "EP02"]}]}
    assert structural_signature(doc) == before
    assert "highlights" not in doc
    assert presentation["highlights"][0]["episodes"] == ["EP01", "EP02"]


# ── AAR-006 재실행 구조 동일 ─────────────────────────────────────────────
def test_aar_006_structure_is_identical_across_runs(tmp_path):
    first = _world(tmp_path / "a")
    second = _world(tmp_path / "b")
    doc_a = build_aar_canonical(video_id="S1", run_id="run-001",
                                segments=first[0].segments, grounded=first[2],
                                timeline=first[1])
    doc_b = build_aar_canonical(video_id="S1", run_id="run-777",
                                segments=second[0].segments, grounded=second[2],
                                timeline=second[1])
    assert structural_signature(doc_a) == structural_signature(doc_b)


def test_aar_006_run_id_does_not_enter_the_signature(doc):
    other = {**doc, "run_id": "run-999"}
    assert structural_signature(doc) == structural_signature(other)


def test_aar_006_byte_equality_is_not_required(doc):
    other = {**doc, "run_id": "run-999"}
    assert serialize_aar(doc) != serialize_aar(other)
    assert structural_signature(doc) == structural_signature(other)


def test_aar_006_signature_changes_when_boundaries_change(doc):
    moved = json.loads(json.dumps(doc))
    moved["episodes"][0]["end_seg"] = 6
    moved["episodes"][1]["start_seg"] = 7
    assert structural_signature(moved) != structural_signature(doc)


def test_aar_006_signature_ignores_content(doc):
    reworded = json.loads(json.dumps(doc))
    reworded["episodes"][1]["summary"] = "다른 문장으로 바꿨다."
    assert structural_signature(reworded) == structural_signature(doc)


# ── AAR-007 왕복 (P1) ────────────────────────────────────────────────────
def test_aar_007_roundtrip_preserves_meaning(doc):
    assert load_aar(serialize_aar(doc)) == doc


def test_aar_007_roundtrip_keeps_failure_reasons(doc):
    restored = load_aar(serialize_aar(doc))
    assert restored["episodes"][0]["grounding_reasons"] == \
        doc["episodes"][0]["grounding_reasons"]


def test_aar_007_serialization_is_deterministic(doc):
    assert serialize_aar(doc) == serialize_aar(doc)


def test_aar_007_load_refuses_a_foreign_document():
    with pytest.raises(AarInvalid):
        load_aar(json.dumps({"schema": "something_else", "episodes": []}))


# ── quality notes (SPEC §15) ─────────────────────────────────────────────
def test_quality_notes_are_deterministic_counts(doc):
    notes = doc["quality_notes"]
    assert notes["usable_stt_count"] + notes["excluded_stt_count"] == 11
    assert notes["rejected_claims"] == 1
    assert notes["ocr_available"] is False


def test_quality_notes_are_not_a_model_claim():
    code = code_only(SRC)
    for forbidden in ("uncertainty_note", "confidence", "probably"):
        assert forbidden not in code, "모델의 자기 신고를 넣었다: " + forbidden


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_b07_does_not_rejudge_grounding():
    code = code_only(SRC)
    for forbidden in ("validate_grounding", "anchors_in", "usable_for_claims ="):
        assert forbidden not in code, "판정을 다시 했다: " + forbidden


def test_b07_does_not_call_a_model():
    code = code_only(SRC)
    for forbidden in ("transformers", "ollama", "torch", "make_llm"):
        assert forbidden not in code, "B-02 책임을 침범했다: " + forbidden


def test_b07_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
