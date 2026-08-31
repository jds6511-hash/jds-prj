"""C-03 Highlight lineage — 어디서 왔는지를 잃지 않는다 (Gate C).

`HLT-001 source lineage` · `RPT-002 episode identity consistency`.

C-03은 **문장을 만들지 않는다.** summary · dialogue · claim은 여기 없다. 하는 일은
"이 highlight가 어떤 canonical episode에서 왔는가"를 결정적으로 고정하는 것뿐이다.

```
lineage는 grouping 입력에서 파생한다
label · display_range에서 역추론하지 않는다
```

표현이 바뀌어도 provenance가 흔들리지 않게 하려면 그 방향이어야 한다.
"""
import ast
import json
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import HighlightSpec, build_highlights
from v2_1_lineage import (
    LINEAGE_SCHEMA,
    HighlightLineage,
    LineageError,
    build_lineage,
    load_lineage,
    serialize_lineage,
    validate_lineage,
)
from v2_1_presentation_input import FORBIDDEN_UPSTREAM, presentation_input

MODULE = Path(__file__).resolve().parents[1] / "src/v2_1_lineage.py"

THREE = ((0, 3), (4, 7), (8, 11))
OVERLAPPING = (HighlightSpec(("EP01", "EP02"), label="앞"),
               HighlightSpec(("EP02", "EP03"), label="뒤"))


@pytest.fixture
def presented(tmp_path):
    payloads = tuple({"summary": "구간 %d 요약." % i} for i in range(len(THREE)))
    return presentation_input(
        run_pipeline(tmp_path, payloads, spans=THREE).document
    )


def _lineage(presented, specs=OVERLAPPING):
    return build_lineage(presented, build_highlights(presented, specs))


def _identity(presented):
    return tuple((e.episode_id, e.start_seg, e.end_seg) for e in presented.episodes)


# ── HLT-001 lineage가 있다 ───────────────────────────────────────────────
def test_hlt_001_every_highlight_carries_at_least_one_source(presented):
    for record in _lineage(presented):
        assert record.source_episode_ids
        assert len(record.sources) == len(record.source_episode_ids)


def test_hlt_001_sources_are_real_canonical_episodes(presented):
    known = {e.episode_id for e in presented.episodes}
    for record in _lineage(presented):
        assert set(record.source_episode_ids) <= known


def test_lineage_comes_from_the_grouping_not_from_the_display_range(presented):
    """비연속 묶음이면 시간 범위 안의 episode와 lineage가 다르다.

    display_range에서 역추론했다면 EP02가 섞여 들어온다.
    """
    record = _lineage(presented, (HighlightSpec(("EP01", "EP03")),))[0]
    assert record.source_episode_ids == ("EP01", "EP03")
    assert "EP02" not in record.source_episode_ids


def test_source_ordering_is_the_grouping_order(presented):
    record = _lineage(presented, (HighlightSpec(("EP03", "EP01")),))[0]
    assert record.source_episode_ids == ("EP03", "EP01")


def test_the_canonical_span_is_recorded(presented):
    record = _lineage(presented, (HighlightSpec(("EP01", "EP02")),))[0]
    assert record.canonical_span == {
        "start_seg": presented.episode("EP01").start_seg,
        "end_seg": presented.episode("EP02").end_seg,
    }


def test_display_range_is_tied_to_the_source_episodes(presented):
    for record in _lineage(presented):
        first = presented.episode(record.source_episode_ids[0])
        assert record.display_range["start_sec"] <= first.start_sec
        assert validate_lineage((record,), presented) == []


# ── 겹쳐도 각각 남는다 ───────────────────────────────────────────────────
def test_a_shared_episode_is_recorded_in_every_highlight(presented):
    records = _lineage(presented)
    carrying = [r.highlight_id for r in records if "EP02" in r.source_episode_ids]
    assert len(carrying) == 2


def test_overlapping_highlights_keep_separate_lineage(presented):
    first, second = _lineage(presented)
    assert first.highlight_id != second.highlight_id
    assert first.source_episode_ids != second.source_episode_ids
    assert first.sources[-1].episode_id == second.sources[0].episode_id


# ── 지어내지 않는다 ──────────────────────────────────────────────────────
def test_an_unknown_episode_in_lineage_is_refused(presented):
    highlights = build_highlights(presented, (HighlightSpec(("EP01",)),))
    forged = highlights[0].__class__(
        highlight_id="H01", label=None, episode_refs=("EP99",),
        segment_refs=(0,), display_range={"start_sec": 0.0, "end_sec": 1.0},
    )
    with pytest.raises(LineageError) as excinfo:
        build_lineage(presented, (forged,))
    assert "EP99" in str(excinfo.value)


def test_a_raw_or_segment_reference_cannot_be_a_source(presented):
    """상류 식별자를 provenance로 위장할 수 없다."""
    highlights = build_highlights(presented, (HighlightSpec(("EP01",)),))
    for forged_ref in ("llm:000001", "raw:asr:3", "seg#3", "3"):
        forged = highlights[0].__class__(
            highlight_id="H01", label=None, episode_refs=(forged_ref,),
            segment_refs=(0,), display_range={"start_sec": 0.0, "end_sec": 1.0},
        )
        with pytest.raises(LineageError):
            build_lineage(presented, (forged,))


def test_an_empty_lineage_is_refused(presented):
    highlights = build_highlights(presented, (HighlightSpec(("EP01",)),))
    forged = highlights[0].__class__(
        highlight_id="H01", label=None, episode_refs=(),
        segment_refs=(), display_range={"start_sec": 0.0, "end_sec": 1.0},
    )
    with pytest.raises(LineageError):
        build_lineage(presented, (forged,))


def test_validate_reports_a_span_that_does_not_match_its_sources(presented):
    record = _lineage(presented)[0]
    tampered = HighlightLineage(
        highlight_id=record.highlight_id,
        source_episode_ids=record.source_episode_ids,
        sources=record.sources,
        canonical_span={"start_seg": 0, "end_seg": 99},
        display_range=record.display_range,
    )
    assert validate_lineage((tampered,), presented)


# ── RPT-002 canonical identity는 표현에 흔들리지 않는다 ──────────────────
def test_rpt_002_reordering_highlights_does_not_touch_canonical_identity(presented):
    before = _identity(presented)
    forward = _lineage(presented, (HighlightSpec(("EP01",)), HighlightSpec(("EP03",))))
    backward = _lineage(presented, (HighlightSpec(("EP03",)), HighlightSpec(("EP01",))))
    assert _identity(presented) == before
    assert forward[0].sources[0] == backward[1].sources[0]


def test_rpt_002_relabelling_does_not_change_lineage(presented):
    plain = _lineage(presented, (HighlightSpec(("EP01", "EP02")),))[0]
    labelled = _lineage(
        presented, (HighlightSpec(("EP01", "EP02"), label="완전히 다른 제목"),)
    )[0]
    assert plain.source_episode_ids == labelled.source_episode_ids
    assert plain.sources == labelled.sources
    assert plain.canonical_span == labelled.canonical_span


def test_rpt_002_source_records_carry_canonical_identity(presented):
    record = _lineage(presented, (HighlightSpec(("EP02",)),))[0]
    episode = presented.episode("EP02")
    assert record.sources[0].start_seg == episode.start_seg
    assert record.sources[0].end_seg == episode.end_seg
    assert record.sources[0].start_sec == episode.start_sec


# ── 직렬화해도 보존된다 ──────────────────────────────────────────────────
def test_lineage_survives_a_roundtrip(presented):
    records = _lineage(presented)
    restored = load_lineage(serialize_lineage(records))
    assert restored == records


def test_the_serialized_form_declares_its_schema(presented):
    payload = json.loads(serialize_lineage(_lineage(presented)))
    assert payload["schema"] == LINEAGE_SCHEMA
    assert len(payload["highlights"]) == 2


def test_a_restored_lineage_still_validates(presented):
    restored = load_lineage(serialize_lineage(_lineage(presented)))
    assert validate_lineage(restored, presented) == []


# ── 문장을 만들지 않는다 ─────────────────────────────────────────────────
def test_lineage_carries_no_generated_text(presented):
    fields = set(HighlightLineage.__dataclass_fields__)
    assert not fields & {"summary", "dialogue_note", "claim", "analysis",
                         "overview", "label"}


def test_the_module_generates_nothing(presented):
    """C-03은 provenance만 닫는다 — 문구 생성은 C-05 이후 소관이다."""
    payload = json.loads(serialize_lineage(_lineage(presented)))
    blob = json.dumps(payload, ensure_ascii=False)
    assert "요약" not in blob


def test_the_module_does_not_import_pre_grounding_layers():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & set(FORBIDDEN_UPSTREAM), sorted(imported)
