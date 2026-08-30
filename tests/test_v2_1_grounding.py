"""B-06 grounding validator — 사실을 판정으로 바꾼다.

티켓: Gate B / B-06
규격: SPEC §15 — 실패하면 **dialogue만 제거하고 summary는 유지**한다

```
B-05   이 cite가 무엇을 가리키는가        (사실)
B-06   이 claim을 통과시킬 수 있는가      (판정)
```

불변식.

```
grounding FAIL
  → canonical episode 구조 유지
  → summary 유지
  → dialogue만 정책대로 제거
  → grounding_status는 FAIL로 보존 · PASS처럼 숨기지 않는다
```

`GRD-004`(unsupported concrete event)는 P1이다. 의미 함의는 문자열·참조·자격으로
결정되지 않는다. 여기서 억지 규칙으로 흉내내지 않는다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_binding import bind_cites
from v2_1_content import merge_content
from v2_1_episode import build_episodes
from v2_1_fixtures import scenario
from v2_1_grounding import (
    FAIL_INELIGIBLE_SUPPORT,
    FAIL_NO_SUPPORT,
    FAIL_OUTSIDE_EPISODE,
    FAIL_REFERENCE,
    FAIL_UNSUPPORTED,
    GROUNDING_STATUSES,
    NOT_APPLICABLE,
    PASS,
    apply_grounding,
    validate_grounding,
)
from v2_1_parse import SegmentRegistry, parse_json_payload
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_scan import code_only
from v2_1_timeline import build_timeline

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_grounding.py"


def _world(tmp_path, name="S1", spans=((0, 5), (6, 11)), asr_overrides=None):
    s = scenario(name)
    store = RawStore(tmp_path / name, run_id="run-001", video_id=name)
    judged = {}
    asr = dict(s.asr)
    asr.update(asr_overrides or {})
    for source_type, channel in (("asr", asr), ("vlm", s.caption), ("ocr", s.ocr)):
        if not channel:
            continue
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    timeline = build_timeline(s.segments, judged)
    episodes = build_episodes(list(spans), s.segments, timeline=timeline)
    return s, store, timeline, episodes, SegmentRegistry(s.segments)


@pytest.fixture
def world(tmp_path):
    return _world(tmp_path)


def _judge(world, index, payload):
    s, store, timeline, episodes, registry = world
    outcome = parse_json_payload(json.dumps(payload), registry)
    binding = bind_cites(merge_content(episodes[index], outcome), timeline, registry)
    return binding, validate_grounding(binding, store)


def _codes(result):
    return {r.code for r in result.reasons}


# ── GRD-001 정상 인용 ────────────────────────────────────────────────────
def test_grd_001_valid_refs_pass(world):
    _, result = _judge(world, 1, {"summary": "요약",
                                  "dialogue_note": "다음 장소를 정한다.",
                                  "stt_cites": [9]})
    assert result.status == PASS
    assert result.reasons == ()
    assert result.dialogue_retained is True


def test_grd_001_summary_only_episode_is_not_applicable(world):
    _, result = _judge(world, 1, {"summary": "요약"})
    assert result.status == NOT_APPLICABLE
    assert result.dialogue_retained is True


def test_status_vocabulary_is_closed():
    assert set(GROUNDING_STATUSES) == {
        PASS, NOT_APPLICABLE, FAIL_REFERENCE, FAIL_OUTSIDE_EPISODE,
        FAIL_INELIGIBLE_SUPPORT, FAIL_NO_SUPPORT, FAIL_UNSUPPORTED,
    }


# ── GRD-002 존재하지 않는 참조 ───────────────────────────────────────────
def test_grd_002_nonexistent_ref_is_a_reference_failure(world):
    _, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": ["seg#999999"]})
    assert result.status == FAIL_REFERENCE
    assert "unknown_segment" in _codes(result)


def test_grd_002_unreadable_ref_is_a_reference_failure(world):
    _, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": ["없음"]})
    assert result.status == FAIL_REFERENCE
    assert "unreadable_cite" in _codes(result)


def test_grd_002_existing_segment_without_evidence_is_distinguished(world):
    """구간은 있는데 그 채널에 근거가 없다 — 없는 구간과 다른 사유다."""
    _, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [11]})
    assert result.status == FAIL_REFERENCE
    assert "no_evidence_at_segment" in _codes(result)
    assert "unknown_segment" not in _codes(result)


def test_grd_002_no_resolution_is_attempted_for_missing_segments(world):
    """없는 참조를 다른 구간으로 옮겨 검사를 이어가지 않는다."""
    binding, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모",
                                        "stt_cites": ["seg#999999"]})
    assert binding.cites[0].segment_id is None
    assert all(r.cite is None or r.cite == "seg#999999" for r in result.reasons)


# ── GRD-003 구간 밖 참조 ─────────────────────────────────────────────────
def test_grd_003_outside_episode_ref_fails(world):
    _, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [9]})
    assert result.status == FAIL_OUTSIDE_EPISODE
    assert "outside_episode" in _codes(result)


def test_grd_003_outside_is_not_reported_as_a_missing_reference(world):
    _, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [9]})
    assert result.status != FAIL_REFERENCE


# ── GRD-010 근거 없는 claim ──────────────────────────────────────────────
def test_grd_010_dialogue_without_any_cite_fails(world):
    _, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모"})
    assert result.status == FAIL_NO_SUPPORT
    assert "no_support_ref" in _codes(result)


def test_grd_010_is_not_confused_with_ineligible_support(world):
    _, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모"})
    assert result.status != FAIL_INELIGIBLE_SUPPORT


# ── GRD-011 · GRD-012 자격 ───────────────────────────────────────────────
def test_grd_011_suspect_only_support_is_ineligible(world):
    """보존과 승격은 다르다 — SUSPECT만으로는 claim이 서지 않는다."""
    _, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [0]})
    assert result.status == FAIL_INELIGIBLE_SUPPORT
    assert "ineligible_support" in _codes(result)


def test_grd_011_is_not_a_reference_failure(world):
    _, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [0]})
    assert result.status != FAIL_REFERENCE


def test_grd_012_valid_plus_suspect_passes_on_the_valid_one(world):
    s, store, timeline, episodes, registry = world
    _, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [9, 6]})
    assert result.status == PASS


def test_grd_012_suspect_beside_valid_does_not_auto_pass(world):
    """VALID가 하나도 없으면 SUSPECT를 몇 개 붙여도 통과하지 않는다."""
    _, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [0, 1, 2, 3]})
    assert result.status == FAIL_INELIGIBLE_SUPPORT


def test_grd_012_ineligible_cite_is_still_recorded_when_valid_exists(world):
    """통과시키더라도 SUSPECT를 인용했다는 사실은 남긴다."""
    _, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": [9, 6]})
    assert result.status == PASS
    assert "ineligible_support" in _codes(result)


def test_grd_012_eligibility_comes_from_sanitation_not_from_the_model(world):
    binding, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                        "stt_cites": [0]})
    assert binding.cites[0].sanitation_status == "SUSPECT"
    assert binding.cites[0].usable_for_claims is False


# ── GRD-006 OCR 단독 ─────────────────────────────────────────────────────
def test_grd_006_ocr_only_evidence_cannot_support_a_claim(tmp_path):
    world = _world(tmp_path, "S8", spans=((0, 11),))
    _, result = _judge(world, 0, {"summary": "화면에 일정이 보인다.",
                                  "dialogue_note": "09:30 출발이라고 한다.",
                                  "stt_cites": [4]})
    assert result.status == FAIL_REFERENCE
    assert "no_evidence_at_segment" in _codes(result)


def test_grd_006_ocr_evidence_is_never_usable(tmp_path):
    world = _world(tmp_path, "S8", spans=((0, 11),))
    binding, _ = _judge(world, 0, {"summary": "요약"})
    ocr = [e for e in binding.evidence if e.source_type == "ocr"]
    assert ocr and not any(e.usable_for_claims for e in ocr)


# ── GRD-005 named entity 문자열 앵커 ─────────────────────────────────────
def test_grd_005_unsupported_number_in_the_claim_fails(world):
    _, result = _judge(world, 1, {"summary": "요약",
                                  "dialogue_note": "3시에 만나기로 했다.",
                                  "stt_cites": [9]})
    assert result.status == FAIL_UNSUPPORTED
    assert "unsupported_anchor" in _codes(result)


def test_grd_005_supported_anchor_passes(tmp_path):
    """앵커가 인용된 근거 안에 실제로 있으면 통과한다."""
    world = _world(tmp_path, asr_overrides={9: "여기 소스를 3번 넣으면 돼."})
    _, result = _judge(world, 1, {"summary": "요약",
                                  "dialogue_note": "소스를 3번 넣는다고 한다.",
                                  "stt_cites": [9]})
    assert result.status == PASS


def test_grd_005_claim_without_anchors_is_not_flagged(world):
    _, result = _judge(world, 1, {"summary": "요약",
                                  "dialogue_note": "다음 장소를 정한다.",
                                  "stt_cites": [9]})
    assert result.status == PASS


def test_grd_005_anchor_check_only_covers_decidable_strings():
    """한국어 고유명사 일반은 결정 불가다 — GRD-004(P1)로 남긴다."""
    import v2_1_grounding

    assert v2_1_grounding.ANCHOR_KINDS == ("digits", "quoted", "latin")


def test_grd_004_is_not_implemented_as_p0():
    code = code_only(SRC)
    for forbidden in ("entailment", "nli", "semantic_support"):
        assert forbidden not in code.lower(), "의미 함의를 흉내냈다: " + forbidden


# ── short-circuit 하지 않는다 ────────────────────────────────────────────
def test_all_deterministic_violations_are_recorded(world):
    _, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "3시에 만난다.",
                                  "stt_cites": ["seg#999999", 9, 0]})
    assert {"unknown_segment", "outside_episode", "ineligible_support"} <= _codes(result)
    assert len(result.reasons) >= 3


def test_status_precedence_is_deterministic(world):
    first = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                              "stt_cites": ["seg#999999", 0]})[1]
    second = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                               "stt_cites": [0, "seg#999999"]})[1]
    assert first.status == second.status == FAIL_REFERENCE


def test_each_reason_names_its_cite(world):
    _, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                  "stt_cites": ["seg#999999", 0]})
    for reason in result.reasons:
        assert reason.code
        assert reason.detail


# ── GRD-008 · GRD-009 상태 보존 ──────────────────────────────────────────
def test_grd_008_status_is_attached_to_the_binding(world):
    binding, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                        "stt_cites": [0]})
    grounded = apply_grounding(binding, result)
    assert grounded.grounding_status == FAIL_INELIGIBLE_SUPPORT
    assert grounded.grounding_reasons


def test_grd_009_failure_removes_dialogue_but_keeps_summary(world):
    binding, result = _judge(world, 0, {"summary": "해변에 앉아 있다.",
                                        "dialogue_note": "메모", "stt_cites": [0]})
    grounded = apply_grounding(binding, result)
    assert grounded.summary == "해변에 앉아 있다."
    assert grounded.dialogue_note is None
    assert result.dialogue_retained is False


def test_grd_009_failure_keeps_the_episode_structure(world):
    binding, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                        "stt_cites": [0]})
    grounded = apply_grounding(binding, result)
    assert grounded.episode_id == binding.episode_id
    assert grounded.support_span == binding.support_span
    assert grounded.anchor_cites == binding.anchor_cites
    assert grounded.provenance == binding.provenance


def test_grd_009_failure_is_not_reported_as_pass(world):
    binding, result = _judge(world, 0, {"summary": "요약", "dialogue_note": "메모",
                                        "stt_cites": [0]})
    grounded = apply_grounding(binding, result)
    assert grounded.grounding_status != PASS
    assert grounded.grounding_status in GROUNDING_STATUSES


def test_pass_keeps_the_dialogue(world):
    binding, result = _judge(world, 1, {"summary": "요약", "dialogue_note": "메모",
                                        "stt_cites": [9]})
    grounded = apply_grounding(binding, result)
    assert grounded.dialogue_note == "메모"


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_b06_does_not_rewrite_facts():
    code = code_only(SRC)
    for forbidden in ("normalize_segment_ref", "bind_cites", "build_episodes",
                      "window_spans", "classify_channel"):
        assert forbidden not in code, "앞 계층을 다시 돌렸다: " + forbidden


def test_b06_does_not_touch_the_summary_text(world):
    binding, result = _judge(world, 0, {"summary": "원문 그대로", "dialogue_note": "메모",
                                        "stt_cites": [0]})
    assert apply_grounding(binding, result).summary == "원문 그대로"


def test_b06_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
