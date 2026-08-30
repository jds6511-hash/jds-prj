"""B-05 support/provenance 바인딩 — 사실만 만들고 판정은 하지 않는다.

티켓: Gate B / B-05

```
B-05   이 cite가 실제로 무엇을 가리키는가
B-06   그 결과로 이 claim을 통과시킬 수 있는가
```

핵심 invariant 하나.

> **조회 사실은 모두 보존하고, 판정은 하나도 하지 않는다.**

`usable_for_claims=false`인 참조를 여기서 지우면 B-06이 "인용이 없었다"와
"SUSPECT를 실제로 인용했다"를 구분하지 못한다. 그러면 `FAIL_INELIGIBLE_SUPPORT`가
다시 `FAIL_REFERENCE`와 섞인다 — OPEN-9가 막으려던 지점이다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_binding import (
    RESOLVED,
    UNKNOWN_SEGMENT,
    UNREADABLE,
    bind_cites,
)
from v2_1_content import merge_content
from v2_1_episode import build_episodes
from v2_1_fixtures import scenario
from v2_1_parse import SegmentRegistry, model_failure, parse_json_payload
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_scan import code_only
from v2_1_timeline import build_timeline

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_binding.py"


@pytest.fixture
def world(tmp_path):
    s = scenario("S1")
    store = RawStore(tmp_path / "raw", run_id="run-001", video_id="S1")
    judged = {}
    for source_type, channel in (("asr", s.asr), ("vlm", s.caption)):
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    timeline = build_timeline(s.segments, judged)
    episodes = build_episodes([(0, 5), (6, 11)], s.segments, timeline=timeline)
    return s, timeline, episodes, SegmentRegistry(s.segments)


def _bound(world, episode_index, payload):
    s, timeline, episodes, registry = world
    outcome = parse_json_payload(json.dumps(payload), registry)
    result = merge_content(episodes[episode_index], outcome)
    return bind_cites(result, timeline, registry)


def _cite(binding, value):
    return next(c for c in binding.cites if c.original_cite == value)


# ── 해석된 인용 ──────────────────────────────────────────────────────────
def test_a_usable_cite_is_bound_with_every_fact(world):
    binding = _bound(world, 1, {"summary": "요약", "stt_cites": [9]})
    cite = _cite(binding, 9)
    assert cite.resolution_status == RESOLVED
    assert cite.canonical_ref == cite.segment_id == 9
    assert cite.inside_episode is True
    assert cite.sanitation_status == "VALID"
    assert cite.usable_for_claims is True
    assert cite.source_type == "asr"


def test_a_suspect_cite_is_kept_not_dropped(world):
    """지우면 B-06이 '인용 없음'과 'SUSPECT 인용'을 구분하지 못한다."""
    binding = _bound(world, 0, {"summary": "요약", "stt_cites": [0]})
    cite = _cite(binding, 0)
    assert cite.resolution_status == RESOLVED
    assert cite.sanitation_status == "SUSPECT"
    assert cite.usable_for_claims is False
    assert len(binding.cites) == 1


def test_notation_is_normalized_before_lookup(world):
    binding = _bound(world, 1, {"summary": "요약", "stt_cites": ["seg#9"]})
    assert binding.cites[0].canonical_ref == 9


# ── 해석되지 않는 인용 ───────────────────────────────────────────────────
def test_nonexistent_segment_is_recorded_as_unknown(world):
    binding = _bound(world, 1, {"summary": "요약", "stt_cites": ["seg#999999"]})
    cite = binding.cites[0]
    assert cite.resolution_status == UNKNOWN_SEGMENT
    assert cite.canonical_ref == 999999
    assert cite.segment_id is None
    assert cite.inside_episode is None
    assert cite.usable_for_claims is None
    assert cite.sanitation_status is None


def test_unreadable_cite_is_recorded_not_discarded(world):
    binding = _bound(world, 1, {"summary": "요약", "stt_cites": ["없음"]})
    cite = binding.cites[0]
    assert cite.resolution_status == UNREADABLE
    assert cite.canonical_ref is None
    assert cite.original_cite == "없음"


def test_outside_episode_cite_is_a_fact_not_a_verdict(world):
    """B-05는 '밖에 있다'까지만 적는다. 통과 여부는 B-06이 정한다."""
    binding = _bound(world, 0, {"summary": "요약", "stt_cites": [9]})
    cite = _cite(binding, 9)
    assert cite.resolution_status == RESOLVED
    assert cite.inside_episode is False
    assert cite.usable_for_claims is True     # 자격은 있으나 이 구간이 아니다


def test_segment_without_speech_is_resolved_but_has_no_evidence(world):
    """구간은 있는데 그 채널에 근거가 없다 — 없는 구간과 다르다."""
    binding = _bound(world, 1, {"summary": "요약", "stt_cites": [11]})
    cite = _cite(binding, 11)
    assert cite.resolution_status == RESOLVED
    assert cite.segment_id == 11
    assert cite.inside_episode is True
    assert cite.sanitation_status is None
    assert cite.source_type is None


# ── 원본 보존 ────────────────────────────────────────────────────────────
def test_every_cite_survives_binding(world):
    payload = {"summary": "요약", "stt_cites": [6, 9, 11]}
    binding = _bound(world, 1, payload)
    assert [c.original_cite for c in binding.cites] == [6, 9, 11]


def test_original_notation_is_preserved(world):
    binding = _bound(world, 1, {"summary": "요약", "stt_cites": ["seg#9"]})
    assert binding.cites[0].original_cite == "seg#9"


def test_duplicate_cites_are_kept_as_given(world):
    """중복을 접으면 모델이 무엇을 냈는지 사후에 못 본다."""
    binding = _bound(world, 1, {"summary": "요약", "stt_cites": [9, 9]})
    assert len(binding.cites) == 2


# ── 코드가 파생하는 것 ───────────────────────────────────────────────────
def test_support_span_comes_from_the_episode(world):
    s, timeline, episodes, registry = world
    binding = _bound(world, 1, {"summary": "요약"})
    assert binding.support_span == episodes[1].support_span


def test_model_supplied_span_is_not_adopted(world):
    binding = _bound(world, 1, {"summary": "요약", "support_span":
                                {"start_seg": 0, "end_seg": 99}})
    assert binding.support_span == {"start_seg": 6, "end_seg": 11}


def test_provenance_lists_evidence_actually_in_the_span(world):
    s, timeline, episodes, registry = world
    binding = _bound(world, 1, {"summary": "요약"})
    for ref_id in binding.provenance:
        segment_id = int(ref_id.split(":")[1])
        assert episodes[1].start_seg <= segment_id <= episodes[1].end_seg


def test_provenance_keeps_ineligible_evidence_too(world):
    """무엇이 있었는지가 provenance다. 무엇을 근거로 삼았는지가 아니다."""
    binding = _bound(world, 0, {"summary": "요약"})
    statuses = {ref.sanitation_status for ref in binding.evidence}
    assert "SUSPECT" in statuses and "VALID" in statuses


def test_episode_id_is_carried_from_the_structure(world):
    assert _bound(world, 1, {"summary": "요약"}).episode_id == "EP02"


# ── 실패한 구간도 바인딩된다 ─────────────────────────────────────────────
def test_failed_content_still_binds_structure(world):
    s, timeline, episodes, registry = world
    result = merge_content(episodes[0], model_failure(RuntimeError("boom")))
    binding = bind_cites(result, timeline, registry)
    assert binding.episode_id == "EP01"
    assert binding.cites == ()
    assert binding.provenance


def test_content_without_cites_binds_an_empty_cite_list(world):
    assert _bound(world, 1, {"summary": "요약"}).cites == ()


# ── 판정하지 않는다 ──────────────────────────────────────────────────────
def test_b05_makes_no_verdict():
    code = code_only(SRC)
    for forbidden in ("PASS", "FAIL", "reject", "verdict", "named_entity",
                      "ocr_only", "unsupported"):
        assert forbidden not in code, "판정을 시작했다: " + forbidden


def test_b05_does_not_remove_anything(world):
    """자격 없는 인용도 목록에 남는다."""
    binding = _bound(world, 0, {"summary": "요약",
                                "stt_cites": [0, "seg#999999", "없음"]})
    assert len(binding.cites) == 3


def test_b05_does_not_touch_the_summary(world):
    binding = _bound(world, 0, {"summary": "요약", "stt_cites": ["없음"]})
    assert binding.summary == "요약"


def test_b05_does_not_call_a_model():
    code = code_only(SRC)
    for forbidden in ("transformers", "ollama", "torch", "make_llm"):
        assert forbidden not in code, "B-02 책임을 침범했다: " + forbidden


def test_b05_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
