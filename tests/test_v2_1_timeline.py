"""A-06 evidence timeline — 옮기는 계층이지 판정하는 계층이 아니다.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-06

```
segment_id · start_sec · end_sec · asr_refs[] · caption_refs[] · ocr_refs[]
텍스트를 복제하지 않는다 — 참조로 간다
모든 ref는 실재 artifact로 resolve된다
missing evidence ≠ failure · segment 밖 timestamp 금지
sanitation 상태와 usable_for_claims를 downstream이 읽을 수 있게 보존
```

**eligibility를 다시 계산하지 않는다.** A-05가 정한 것을 그대로 옮긴다 — 여기서
재계산하면 정책이 두 벌이 되고 둘이 갈라진다.
"""
import re
from pathlib import Path

import pytest

from v2_1_fixtures import EXCITED_SPEECH, scenario
from v2_1_raw_store import EVIDENCE_MODALITIES, RawStore
from v2_1_sanitation import SUSPECT, VALID, classify_channel
from v2_1_timeline import (
    TimelineError,
    build_timeline,
    refs_for,
    validate_timeline,
)

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_timeline.py"


@pytest.fixture
def store(tmp_path):
    return RawStore(tmp_path / "raw", run_id="run-001", video_id="S1")


def _stock(store, scenario_name="S1"):
    """fixture 채널을 raw store에 넣고 sanitation 판정을 돌려준다."""
    s = scenario(scenario_name)
    judged = {}
    for source_type, channel in (("asr", s.asr), ("vlm", s.caption), ("ocr", s.ocr)):
        if not channel:
            continue
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    return s, judged


# ── EVT-001 segment alignment ────────────────────────────────────────────
def test_evt_001_refs_land_on_their_own_segment(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    assert [e.segment_id for e in timeline] == s.segment_ids
    for entry in timeline:
        for ref in refs_for(entry):
            assert ref.segment_id == entry.segment_id


def test_evt_001_entry_times_come_from_the_canonical_segment(store):
    s, judged = _stock(store)
    by_id = {seg.segment_id: seg for seg in s.segments}
    for entry in build_timeline(s.segments, judged):
        assert entry.start_sec == by_id[entry.segment_id].start_sec
        assert entry.end_sec == by_id[entry.segment_id].end_sec


def test_evidence_text_is_not_copied_into_the_timeline(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    blob = repr(timeline)
    assert EXCITED_SPEECH not in blob
    assert "해변" not in blob


def test_refs_resolve_back_to_the_raw_artifact(store):
    s, judged = _stock(store)
    entry = build_timeline(s.segments, judged)[8]
    ref = [r for r in refs_for(entry) if r.source_type == "asr"][0]
    assert store.load(ref.source_type, ref.segment_id).read_text() == EXCITED_SPEECH


# ── EVT-002 missing modality ─────────────────────────────────────────────
def test_evt_002_missing_modality_is_empty_refs_not_a_failure(store):
    s, judged = _stock(store, "S3")          # caption만 있다
    timeline = build_timeline(s.segments, judged)
    assert all(e.asr_refs == [] for e in timeline)
    assert all(e.caption_refs for e in timeline)
    assert validate_timeline(timeline, s.segments, store).ok


def test_evt_002_structure_survives_a_completely_empty_video(store):
    s, judged = _stock(store, "S5")
    timeline = build_timeline(s.segments, judged)
    assert len(timeline) == len(s.segments)
    assert all(not refs_for(e) for e in timeline)


def test_empty_and_parse_failed_evidence_produce_no_ref(store):
    """참조할 것이 없다 — 빈 근거를 ref로 만들면 downstream이 실재로 오해한다."""
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    assert timeline[11].asr_refs == []       # S1 seg#11은 빈 발화


# ── EVT-003 invalid ref ──────────────────────────────────────────────────
def test_evt_003_unresolvable_ref_fails_validation(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    store.load("asr", 0).raw_path.unlink()
    result = validate_timeline(timeline, s.segments, store)
    assert not result.ok
    assert "UNRESOLVED_REF" in {f.code for f in result.failures}


def test_evt_003_ref_to_a_segment_outside_the_video_fails(store):
    s, judged = _stock(store)
    judged["asr"][99] = judged["asr"][0]
    with pytest.raises(TimelineError, match="unknown segment"):
        build_timeline(s.segments, judged)


# ── EVT-004 out-of-range timestamp ───────────────────────────────────────
def test_evt_004_timestamp_outside_its_segment_is_rejected(store):
    s, judged = _stock(store)
    with pytest.raises(TimelineError, match="outside"):
        build_timeline(s.segments, judged, timestamps={("asr", 0): 42.0})


def test_evt_004_timestamp_inside_its_segment_is_kept(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged, timestamps={("asr", 0): 2.5})
    ref = [r for r in refs_for(timeline[0]) if r.source_type == "asr"][0]
    assert ref.at_sec == 2.5


def test_evt_004_timestamp_at_the_segment_end_is_outside(store):
    """구간은 반열림 `[start, end)`이다."""
    s, judged = _stock(store)
    with pytest.raises(TimelineError, match="outside"):
        build_timeline(s.segments, judged, timestamps={("asr", 0): 5.0})


# ── EVT-005·006 sparse / rich ────────────────────────────────────────────
def test_evt_005_sparse_evidence_builds(store):
    s, judged = _stock(store, "S3")
    assert len(build_timeline(s.segments, judged)) == 12


def test_evt_006_rich_asr_is_carried(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    assert sum(len(e.asr_refs) for e in timeline) == 11   # 12구간 중 1건이 빈 발화


# ── EVT-007 sanitation 상태 보존 ─────────────────────────────────────────
def test_evt_007_status_and_eligibility_are_carried_verbatim(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    for entry in timeline:
        for ref in refs_for(entry):
            source = judged[ref.source_type][ref.segment_id]
            assert ref.status == source.status
            assert ref.usable_for_claims == source.usable_for_claims
            assert ref.preserved == source.preserved


def test_evt_007_suspect_stays_and_stays_unusable(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    suspect = [r for e in timeline for r in refs_for(e) if r.status == SUSPECT]
    assert len(suspect) == 8
    assert all(r.usable_for_claims is False for r in suspect)


def test_evt_007_valid_evidence_stays_usable(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    usable = [r for e in timeline for r in refs_for(e) if r.usable_for_claims]
    assert usable and all(r.status == VALID for r in usable)


def test_evt_007_valid_but_unusable_ocr_survives_as_such(store):
    """상태가 VALID인데 usable이 아닌 경우가 pass-through와 재계산을 가른다."""
    s, judged = _stock(store, "S8")
    timeline = build_timeline(s.segments, judged)
    ocr = [r for e in timeline for r in refs_for(e) if r.source_type == "ocr"]
    assert ocr and all(r.status == VALID for r in ocr)
    assert all(r.usable_for_claims is False for r in ocr)


def test_a06_does_not_recompute_eligibility():
    """정책이 두 벌이 되면 갈라진다 — A-05가 정한 것을 옮기기만 한다."""
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("REPEAT_THRESHOLD", "is_subtitle_credit", "classify(",
                      "occurrence_counts"):
        assert forbidden not in src, "판정을 다시 하고 있다: " + forbidden


# ── EVT-008 llm은 evidence modality가 아니다 ─────────────────────────────
def test_evt_008_llm_source_type_is_refused_by_the_timeline(store):
    s, judged = _stock(store)
    judged["llm"] = judged["asr"]
    with pytest.raises(TimelineError, match="llm"):
        build_timeline(s.segments, judged)


def test_evt_008_timeline_only_accepts_evidence_modalities(store):
    s, judged = _stock(store)
    timeline = build_timeline(s.segments, judged)
    seen = {r.source_type for e in timeline for r in refs_for(e)}
    assert seen <= set(EVIDENCE_MODALITIES)
    assert "llm" not in seen


def test_evt_008_unknown_source_type_is_refused(store):
    s, judged = _stock(store)
    judged["subtitle"] = judged["asr"]
    with pytest.raises(TimelineError, match="subtitle"):
        build_timeline(s.segments, judged)


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_a06_does_not_build_episodes_or_validate_partitions():
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("episode", "window", "partition", "boundary"):
        assert forbidden not in src.lower(), "다른 티켓 책임을 침범했다: " + forbidden


def test_a06_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
