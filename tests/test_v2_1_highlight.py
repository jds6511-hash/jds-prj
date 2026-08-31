"""C-02 Highlight Builder core — 정본은 건드리지 않고 묶기만 한다 (Gate C).

```
Canonical Episode   overlap 0 · gap 0 · exactly once · 시간순
Highlight           중첩 허용 · 같은 episode 다중 참여 허용 · 개수 자유
```

**두 구조는 다른 규칙을 따른다.** highlight의 중첩을 canonical partition 검증기로
재면 v2.1 설계가 무너진다 — 그래서 여기서 A-09를 부르지 않는다.

`HLT-004`(목표 개수 없음)는 소스에서 숫자를 찾는 것으로 막지 않는다. **입력 구성이
달라지면 개수가 실제로 달라지는지**를 기능으로 확인하고, 소스 스캔은 보조로만 둔다.
"""
import ast
from pathlib import Path

import pytest

from v2_1_gate_b import run_pipeline
from v2_1_highlight import (
    Highlight,
    HighlightError,
    HighlightSpec,
    build_highlights,
)
from v2_1_presentation_input import FORBIDDEN_UPSTREAM, presentation_input

MODULE = Path(__file__).resolve().parents[1] / "src/v2_1_highlight.py"

THREE = ((0, 3), (4, 7), (8, 11))
FOUR = ((0, 2), (3, 5), (6, 8), (9, 11))


def _presented(tmp_path, spans=THREE):
    payloads = tuple({"summary": "구간 %d 요약." % i} for i in range(len(spans)))
    return presentation_input(
        run_pipeline(tmp_path, payloads, spans=spans).document
    )


def _signature(presented):
    """정본이 정말 그대로인지 볼 때 쓰는 지문."""
    return tuple(
        (e.episode_id, e.start_seg, e.end_seg, e.start_sec, e.end_sec)
        for e in presented.episodes
    )


@pytest.fixture
def presented(tmp_path):
    return _presented(tmp_path)


# ── 묶는다 ───────────────────────────────────────────────────────────────
def test_a_single_episode_becomes_a_highlight(presented):
    highlights = build_highlights(presented, [HighlightSpec(("EP01",))])
    assert len(highlights) == 1
    assert highlights[0].episode_refs == ("EP01",)


def test_hlt_005_several_episodes_merge_into_one_highlight(presented):
    highlights = build_highlights(presented, [HighlightSpec(("EP01", "EP02"))])
    assert highlights[0].episode_refs == ("EP01", "EP02")
    first, second = presented.episode("EP01"), presented.episode("EP02")
    assert highlights[0].display_range == {"start_sec": first.start_sec,
                                           "end_sec": second.end_sec}


def test_hlt_006_the_same_episode_may_join_two_highlights(presented):
    highlights = build_highlights(presented, [HighlightSpec(("EP01", "EP02")),
                                              HighlightSpec(("EP02", "EP03"))])
    joined = [h.highlight_id for h in highlights if "EP02" in h.episode_refs]
    assert len(joined) == 2


def test_hlt_002_highlights_may_overlap_in_time(presented):
    """canonical은 overlap 0이지만 highlight는 겹쳐도 된다."""
    first, second = build_highlights(
        presented, [HighlightSpec(("EP01", "EP02")), HighlightSpec(("EP02", "EP03"))]
    )
    assert first.display_range["end_sec"] > second.display_range["start_sec"]


def test_highlight_ids_are_code_derived_and_ordered(presented):
    highlights = build_highlights(presented, [HighlightSpec(("EP03",)),
                                              HighlightSpec(("EP01",))])
    assert [h.highlight_id for h in highlights] == ["H01", "H02"]


def test_segment_refs_are_the_union_of_member_spans(presented):
    highlight = build_highlights(presented, [HighlightSpec(("EP01", "EP02"))])[0]
    expected = list(range(presented.episode("EP01").start_seg,
                          presented.episode("EP02").end_seg + 1))
    assert list(highlight.segment_refs) == expected


def test_a_gap_between_members_is_not_claimed_as_segments(presented):
    """연속하지 않은 묶음의 사이 구간은 highlight의 것이 아니다."""
    highlight = build_highlights(presented, [HighlightSpec(("EP01", "EP03"))])[0]
    middle = presented.episode("EP02")
    assert not set(highlight.segment_refs) & set(
        range(middle.start_seg, middle.end_seg + 1)
    )


def test_a_label_is_carried_verbatim_and_optional(presented):
    labelled, plain = build_highlights(
        presented, [HighlightSpec(("EP01",), label="창고를 연다"),
                    HighlightSpec(("EP02",))]
    )
    assert labelled.label == "창고를 연다"
    assert plain.label is None


# ── 정본은 그대로다 ──────────────────────────────────────────────────────
def test_hlt_003_canonical_structure_is_unchanged(presented):
    before = _signature(presented)
    build_highlights(presented, [HighlightSpec(("EP01", "EP02")),
                                 HighlightSpec(("EP02", "EP03"))])
    assert _signature(presented) == before


def test_hlt_007_episode_boundaries_cannot_be_written(presented):
    highlight = build_highlights(presented, [HighlightSpec(("EP01",))])[0]
    episode = presented.episode("EP01")
    with pytest.raises(Exception):
        episode.start_sec = 0.0
    with pytest.raises(Exception):
        highlight.display_range = {}


def test_the_episode_list_itself_is_not_reordered_or_trimmed(presented):
    before = [e.episode_id for e in presented.episodes]
    build_highlights(presented, [HighlightSpec(("EP03",))])
    assert [e.episode_id for e in presented.episodes] == before


# ── 지어내지 않는다 ──────────────────────────────────────────────────────
def test_an_unknown_episode_is_refused(presented):
    with pytest.raises(HighlightError) as excinfo:
        build_highlights(presented, [HighlightSpec(("EP99",))])
    assert "EP99" in str(excinfo.value)


def test_an_empty_group_is_refused(presented):
    with pytest.raises(HighlightError):
        build_highlights(presented, [HighlightSpec(())])


def test_a_repeated_episode_inside_one_group_is_refused(presented):
    """같은 highlight 안에서의 중복은 표현이 아니라 실수다."""
    with pytest.raises(HighlightError):
        build_highlights(presented, [HighlightSpec(("EP01", "EP01"))])


def test_only_a_presentation_input_is_accepted(tmp_path):
    """C-01을 통과하지 않은 것은 여기서도 못 들어온다."""
    document = run_pipeline(tmp_path, ({"summary": "가"}, {"summary": "나"})).document
    with pytest.raises(HighlightError):
        build_highlights(document, [HighlightSpec(("EP01",))])
    with pytest.raises(HighlightError):
        build_highlights(document["episodes"], [HighlightSpec(("EP01",))])


# ── 개수를 강제하지 않는다 (HLT-004) ─────────────────────────────────────
def test_hlt_004_highlight_count_follows_the_input(tmp_path):
    """episode 구성이 달라지면 highlight 개수도 자연히 달라진다."""
    counts = []
    for spans in (THREE, FOUR):
        presented = _presented(tmp_path / str(len(spans)), spans=spans)
        specs = [HighlightSpec((e.episode_id,)) for e in presented.episodes]
        counts.append(len(build_highlights(presented, specs)))
    assert counts == [len(THREE), len(FOUR)]


def test_hlt_004_one_highlight_over_everything_is_allowed(presented):
    all_ids = tuple(e.episode_id for e in presented.episodes)
    assert len(build_highlights(presented, [HighlightSpec(all_ids)])) == 1


def test_hlt_004_no_group_at_all_is_allowed(presented):
    assert build_highlights(presented, []) == ()


def test_hlt_004_many_highlights_are_not_capped(presented):
    """상한을 두면 여기서 걸린다 — 형식 참조의 9행이 상한이 아니다."""
    specs = [HighlightSpec(("EP01",)) for _ in range(12)]
    assert len(build_highlights(presented, specs)) == 12


def test_hlt_004_source_declares_no_target_count(presented):
    """보조 가드다 — 위의 기능 테스트가 본 검사다."""
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    assert not names & {"target_count", "target", "expected_count", "row_count"}


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


def test_the_builder_does_not_render(presented):
    """C-02는 조합까지다 — 서식은 C-05 이후 소관이다."""
    highlight = build_highlights(presented, [HighlightSpec(("EP01",))])[0]
    assert set(Highlight.__dataclass_fields__) == {
        "highlight_id", "label", "episode_refs", "segment_refs", "display_range",
    }
    assert isinstance(highlight.display_range, dict)
