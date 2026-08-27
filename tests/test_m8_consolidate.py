"""ROUND 2 consolidation — **새 사건을 발명하지 않는다.**

규격: `docs/finalization/M8_REDESIGN_R2_GATE_2026-08-28.md` §2-2·§2-3 (실행 전 동결).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import m8_consolidate as C                                         # noqa: E402
import m8_report as R                                              # noqa: E402


def cand(a, b, name="사건", desc="사람이 무언가를 한다 가나다라마바사", ev=None):
    return {"event": name, "span": [a, b], "description": desc,
            "evidence_segments": ev if ev is not None else [a]}


def grouper(groups):
    """ID 그룹만 내는 가짜 consolidation 모델."""
    return lambda prompt, **kw: json.dumps({"groups": groups}, ensure_ascii=False)


# ---------------------------------------------------------------- ID 계약

def test_candidate_ids_are_stable_and_ordered():
    ids = C.candidate_ids([cand(0, 4), cand(5, 9)])
    assert ids == ["E01", "E02"]


def test_parse_groups_accepts_exact_partition():
    g = C.parse_groups(json.dumps({"groups": [["E01", "E02"], ["E03"]]}),
                       ["E01", "E02", "E03"])
    assert g == [["E01", "E02"], ["E03"]]


def test_parse_groups_refuses_missing_id():
    with pytest.raises(C.ConsolidateError, match="누락"):
        C.parse_groups(json.dumps({"groups": [["E01"]]}), ["E01", "E02"])


def test_parse_groups_refuses_duplicate_id():
    with pytest.raises(C.ConsolidateError, match="중복"):
        C.parse_groups(json.dumps({"groups": [["E01"], ["E01", "E02"]]}),
                       ["E01", "E02"])


def test_parse_groups_refuses_unknown_id():
    with pytest.raises(C.ConsolidateError, match="미지"):
        C.parse_groups(json.dumps({"groups": [["E01", "E99"]]}), ["E01"])


def test_parse_groups_refuses_unparseable():
    with pytest.raises(C.ConsolidateError):
        C.parse_groups("설명만 있고 JSON이 없다", ["E01"])


# ---------------------------------------------------------------- 합성 규칙

def test_compose_span_stays_inside_members():
    e = C.compose_group([cand(10, 20, "걷기"), cand(21, 30, "설명")])
    assert e["span"] == [10, 30]


def test_compose_title_is_longest_span_member():
    e = C.compose_group([cand(0, 2, "짧은것"), cand(3, 40, "주된활동"),
                         cand(41, 43, "다른것")])
    assert e["event"] == "주된활동"


def test_compose_title_tie_breaks_to_earliest():
    e = C.compose_group([cand(0, 4, "앞"), cand(5, 9, "뒤")])
    assert e["event"] == "앞"


def test_compose_description_joins_and_dedups_exact_repeats():
    d = "같은 서술이 반복된다 가나다라마바사아자차"
    e = C.compose_group([cand(0, 4, "가", d), cand(5, 9, "나", d),
                         cand(10, 14, "다", "다른 서술 카타파하 가나다라마바사")])
    assert e["description"].count(d) == 1
    assert "다른 서술" in e["description"]


def test_compose_evidence_one_representative_per_member():
    e = C.compose_group([cand(0, 4, ev=[0, 1]), cand(5, 9, ev=[5, 6])])
    assert e["evidence_segments"] == [0, 5]


def test_compose_evidence_capped_at_frozen_max_and_spread():
    """멤버가 많아도 대표 근거는 최대 4개다 — 사전등록 규칙 1."""
    members = [cand(i * 5, i * 5 + 4, ev=[i * 5]) for i in range(9)]
    e = C.compose_group(members)
    ev = e["evidence_segments"]
    assert len(ev) == R.MAX_EVIDENCE_PER_EVENT
    assert ev[0] == 0 and ev[-1] == 40          # 양 끝을 포함해 고르게
    assert ev == sorted(ev)


def test_compose_evidence_never_invents_segments():
    members = [cand(0, 4, ev=[2]), cand(5, 9, ev=[7])]
    e = C.compose_group(members)
    assert set(e["evidence_segments"]) <= {2, 7}


def test_compose_evidence_inside_span():
    e = C.compose_group([cand(10, 14, ev=[12]), cand(15, 19, ev=[16])])
    assert all(e["span"][0] <= c <= e["span"][1]
               for c in e["evidence_segments"])


# ---------------------------------------------------------------- 통합 동작

def test_consolidate_merges_fragments_of_one_activity():
    cands = [cand(0, 9, "등산로를 걸음"), cand(10, 19, "코스를 설명함"),
             cand(20, 29, "풍경을 봄"), cand(30, 39, "다시 걸음")]
    out, diag = C.consolidate(cands, grouper([["E01", "E02", "E03", "E04"]]))
    assert len(out) == 1 and out[0]["span"] == [0, 39]
    assert diag["input_candidates"] == 4 and diag["output_events"] == 1
    assert diag["groups"] == 1 and diag["merged_groups"] == 1


def test_consolidate_keeps_singletons_untouched():
    cands = [cand(0, 4, "가"), cand(50, 54, "나")]
    out, diag = C.consolidate(cands, grouper([["E01"], ["E02"]]))
    assert [e["event"] for e in out] == ["가", "나"]
    assert diag["singletons"] == 2 and diag["merged_groups"] == 0


def test_consolidate_falls_back_to_singletons_on_invalid_grouping():
    """fail-closed — 잘못된 그룹이면 **적용하지 않고** 원본을 그대로 둔다."""
    cands = [cand(0, 4), cand(5, 9)]
    out, diag = C.consolidate(cands, grouper([["E01"]]))     # E02 누락
    assert len(out) == 2 and diag["invalid_grouping"] == 1
    assert diag["applied"] is False


def test_consolidate_never_increases_event_count():
    cands = [cand(0, 4), cand(5, 9), cand(10, 14)]
    out, _ = C.consolidate(cands, grouper([["E01", "E02"], ["E03"]]))
    assert len(out) <= len(cands)


def test_consolidate_no_op_on_empty_input():
    out, diag = C.consolidate([], grouper([]))
    assert out == [] and diag["input_candidates"] == 0


def test_consolidate_does_not_call_model_for_single_candidate():
    calls = []

    def llm(prompt, **kw):
        calls.append(prompt)
        return json.dumps({"groups": [["E01"]]})
    out, diag = C.consolidate([cand(0, 4)], llm)
    assert len(out) == 1 and calls == []
    assert diag["applied"] is False


# ---------------------------------------------------------------- 금지 사항

def test_module_has_no_similarity_threshold():
    src = (ROOT / "src" / "m8_consolidate.py").read_text(encoding="utf-8")
    for banned in ("cosine", "similarity", "embed", "threshold", "0.7", "0.8"):
        assert banned not in src


def test_prompt_gives_ids_and_asks_for_groups_only():
    p = C.build_consolidation_prompt([cand(0, 4, "가"), cand(5, 9, "나")],
                                     ["E01", "E02"])
    assert "E01" in p and "E02" in p and "groups" in p
    assert "새 사건" in p or "새로운 사건" in p          # 금지를 명시한다


def test_group_ordering_is_deterministic():
    cands = [cand(20, 24), cand(0, 4), cand(10, 14)]
    a, _ = C.consolidate(cands, grouper([["E02"], ["E03"], ["E01"]]))
    b, _ = C.consolidate(cands, grouper([["E01"], ["E03"], ["E02"]]))
    assert [e["span"] for e in a] == [e["span"] for e in b]


# ---------------------------------------------------------------- 생성 계약 V3

def test_v3_adds_duplicate_suppression_and_keeps_v2_contract():
    t = R.EVENT_RULES_V3
    assert "반복" in t and "종료" in t
    assert "짧" in t and ("과분할" in t or "쪼개" in t)
    assert "한국어" in t


def test_v3_is_not_the_default():
    p = R.build_event_prompt([{"idx": 0, "start": 0, "end": 5,
                               "subtitle": "가", "caption": "나"}])
    assert R.EVENT_RULES_V3 not in p


def test_structured_run_consolidates_before_validation():
    """수렴이 **검증 앞**에서 일어나 사건 수가 줄어든다."""
    segs = [{"idx": i, "start": i * 5.0, "end": i * 5.0 + 5,
             "subtitle": f"발화{i}", "caption": f"화면{i}"} for i in range(20)]
    # 단독으로도 하한을 넘고, 서로 달라야 병합 시 완전중복 제거에 걸리지 않는다
    desc = "사람이 무언가를 이어서 한다 가나다라마바"

    def gen(prompt, **kw):
        if "groups" in prompt:                       # consolidation 호출
            return json.dumps({"groups": [["E01", "E02", "E03", "E04"]]})
        return json.dumps([{"event": f"조각{i}", "span": [i * 5, i * 5 + 4],
                            "evidence_segments": [i * 5],
                            "description": f"{desc} {i}"} for i in range(4)],
                          ensure_ascii=False)

    a = R.generate_report_structured(segs, gen, 20, 5)
    b = R.generate_report_structured(segs, gen, 20, 5, consolidate_llm=gen)
    assert len(a["events"]) == 4                     # 수렴 없으면 조각 4개
    assert len(b["events"]) == 1                     # 켜면 하나로
    assert b["events"][0]["span"] == [0, 19]
    assert b["consolidation"]["merged_groups"] == 1
    assert "consolidation" not in a


def test_thin_description_is_not_fixed_by_merging():
    """**중요한 한계.** `thin_description` 하한은 근거 수에 비례한다
    (15자 x 근거). 멤버마다 근거가 하나씩 붙으면 병합해도 비례가 유지돼
    그 거부가 줄지 않는다. 근거가 상한(4)에 걸리는 큰 그룹에서만 유리해진다.
    """
    short = "짧은 서술 열두자"                          # 12자 — 단독이면 거부
    two = C.compose_group([cand(0, 4, "가", short, [0]),
                           cand(5, 9, "나", short + "다", [5])])
    assert len(two["evidence_segments"]) == 2
    assert len(two["description"]) < R.MIN_CHARS_PER_EVIDENCE * 2

    big = C.compose_group([cand(i * 5, i * 5 + 4, f"조각{i}", short + str(i), [i * 5])
                           for i in range(8)])
    assert len(big["evidence_segments"]) == R.MAX_EVIDENCE_PER_EVENT
    assert len(big["description"]) >= R.MIN_CHARS_PER_EVIDENCE * len(
        big["evidence_segments"])
