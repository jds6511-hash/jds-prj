"""M8 hierarchical prototype v2 — boundary selection 계약.

규격: `docs/finalization/M8_HIER_PROTOTYPE_SPEC_2026-08-29.md` + structural repair.

v1은 LLM에게 사건 목록·그룹을 자유 생성시켜 실패했다(1구간 사건 29건 · 겹침 ·
주제 기반 재그룹 → non_contiguous). v2에서 검사하는 것은 **자유도가 실제로
제거됐는가**다.

채점하지 않는다 — C1/C2/C3·Event Recall·GT 대조 없음. judge 없음. fallback 없음.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import m8_hier as H                                                 # noqa: E402

SEGS = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
         "subtitle": "", "caption": f"장면 {i}"} for i in range(0, 60)]


def _atomics(bounds, n=60, title="산길 이동", desc="산길을 따라 이동한다."):
    return [H.with_evidence({**a, "title": title, "description": desc})
            for a in H.build_atomic_spans(bounds, n)]


# ── 배제 항목 ───────────────────────────────────────────────────────────
def test_새_VLM이나_수식_지표를_쓰지_않는다():
    src = (ROOT / "src" / "m8_hier.py").read_text(encoding="utf-8")
    for bad in ("SentenceTransformer", "shot_detect", "importance_score",
                "boundary_score", "torch"):
        assert bad not in src, bad


def test_GT나_공식결과를_생성입력으로_쓰지_않는다():
    src = (ROOT / "src" / "m8_hier.py").read_text(encoding="utf-8")
    for bad in ("reference_events", "m8_metrics", "load_reference",
                "event_temporal_alignment", "c1_verdict", "compression("):
        assert bad not in src, bad


def test_fallback을_만들지_않는다():
    """v1은 grouping이 깨지면 singleton Major 47개를 만들고 PASS로 렌더했다."""
    src = (ROOT / "src" / "m8_hier.py").read_text(encoding="utf-8")
    assert "_fallback" not in src and "fallback을 만들지 않는다" in src


def test_채점하지_않는다():
    names = {n for n in dir(H) if not n.startswith("_")}
    for bad in ("score", "recall", "verdict", "acceptance", "judge"):
        assert not any(bad in n.lower() for n in names), bad


# ── Atomic: 경계만 고른다 ───────────────────────────────────────────────
def test_경계_사이가_사건이_된다():
    got = H.build_atomic_spans([0, 20, 45], 60)
    assert [(a["start_seg"], a["end_seg"]) for a in got] == \
        [(0, 19), (20, 44), (45, 59)]
    assert [a["event_id"] for a in got] == ["E01", "E02", "E03"]


def test_겹침이_원리적으로_불가능하다():
    got = H.build_atomic_spans([0, 7, 8, 30], 60)
    for a, b in zip(got, got[1:]):
        assert a["end_seg"] < b["start_seg"]


def test_타임라인에_구멍이_없다():
    got = H.build_atomic_spans([12, 30], 60)
    assert got[0]["start_seg"] == 0 and got[-1]["end_seg"] == 59
    covered = [i for a in got for i in range(a["start_seg"], a["end_seg"] + 1)]
    assert covered == list(range(60))


def test_영상_시작은_코드가_항상_포함한다():
    """앞부분이 어느 사건에도 안 들어가면 타임라인에 구멍이 생긴다."""
    assert H.build_atomic_spans([12], 60)[0]["start_seg"] == 0


def test_중복_경계는_하나로():
    assert len(H.build_atomic_spans([0, 20, 20, 20], 60)) == 2


def test_범위_밖_경계는_무효():
    with pytest.raises(H.HierInvalid) as e:
        H.build_atomic_spans([0, 99], 60)
    assert e.value.reason == "boundary_out_of_range"


def test_경계_파싱():
    assert H.parse_boundaries('{"atomic_start_segments":[9,3,3,0]}') == [0, 3, 9]
    assert H.parse_boundaries("JSON 아님") == []


def test_LLM은_span을_직접_쓰지_않는다():
    """v1은 모델이 start/end를 자유 생성해 겹침이 생겼다. v2는 시작점만 고른다."""
    p = H.build_atomic_boundary_prompt(SEGS[:5])
    assert "atomic_start_segments" in p
    assert "end_seg" not in p
    assert p.count("start_seg") == p.count("atomic_start_segments")


# ── 근거: 범위 보존 · 표시 앵커만 축약 ──────────────────────────────────
@pytest.mark.parametrize("s,e,want", [
    (10, 10, [10]), (10, 11, [10, 11]), (10, 12, [10, 11, 12]),
    (110, 169, [110, 139, 169]), (0, 25, [0, 12, 25]),
])
def test_앵커는_first_middle_last(s, e, want):
    assert H.anchors(s, e) == want


def test_앵커는_최대_3개다():
    """v1은 상한을 없앴다가 60개 인용으로 돌아갔다."""
    assert len(H.anchors(0, 172)) <= H.MAX_ANCHORS == 3


def test_support_span은_근거_범위를_그대로_보존한다():
    ev = H.with_evidence({"event_id": "E01", "start_seg": 110, "end_seg": 169})
    assert ev["support_span"] == {"start_seg": 110, "end_seg": 169}
    assert ev["anchor_cites"] == [110, 139, 169]


# ── 제목·서술은 시간 구조를 못 바꾼다 ──────────────────────────────────
def test_서술_프롬프트는_해당_span만_준다():
    p = H.build_describe_prompt(SEGS[10:15])
    assert "seg#10" in p and "seg#14" in p and "seg#20" not in p


def test_서술_파싱_실패는_빈값이고_구조를_바꾸지_않는다():
    assert H.parse_describe("깨진 출력") == {"title": "", "description": ""}


def test_오염된_서술은_빈값으로_떨어진다():
    got = H.parse_describe('{"title":"산길","description":"계단 위에는 계단 '
                           '위에는 계단 위에는 "}')
    assert got == {"title": "", "description": ""}


# ── Major: 경계만 고른다 ────────────────────────────────────────────────
ATOMS = _atomics([0, 15, 30, 45])


def test_major_경계_사이가_묶인다():
    got = H.build_major_spans(["E01", "E03"], ["산행 시작", "하산"], ATOMS)
    assert [m["subevents"] for m in got] == [["E01", "E02"], ["E03", "E04"]]
    assert got[0]["start_seg"] == 0 and got[0]["end_seg"] == 29
    assert [m["major_event_id"] for m in got] == ["M01", "M02"]


def test_모든_atomic이_정확히_한번_들어간다():
    got = H.build_major_spans(["E01", "E02", "E04"], ["a", "b", "c"], ATOMS)
    used = [s for m in got for s in m["subevents"]]
    assert used == ["E01", "E02", "E03", "E04"]


def test_major_span과_앵커는_코드가_정한다():
    got = H.build_major_spans(["E01"], ["전체"], ATOMS)
    assert got[0]["start_seg"] == 0 and got[0]["end_seg"] == 59
    assert got[0]["anchor_cites"] == H.anchors(0, 59)


@pytest.mark.parametrize("ids,titles,reason", [
    ([], [], "no_major_start"),
    (["E01"], [], "title_count_mismatch"),
    (["E01", "E99"], ["a", "b"], "unknown_atomic"),
    (["E01", "E01"], ["a", "b"], "duplicate_major_start"),
    (["E03", "E01"], ["a", "b"], "major_start_not_sorted"),
    (["E02"], ["a"], "first_atomic_not_included"),
    (["E01"], ["  "], "empty_major_title"),
])
def test_major_경계_위반은_무효다(ids, titles, reason):
    with pytest.raises(H.HierInvalid) as e:
        H.build_major_spans(ids, titles, ATOMS)
    assert e.value.reason == reason


def test_major_파싱():
    ids, titles = H.parse_major_starts(
        '{"major_start_atomic_ids":["E01","E12"],"titles":["a","b"]}')
    assert ids == ["E01", "E12"] and titles == ["a", "b"]


def test_major_프롬프트는_개수를_지시하지_않는다():
    p = H.build_major_boundary_prompt(ATOMS)
    for bad in ("최대 ", "개 이하", "개까지", "정답", "GT"):
        assert bad not in p


def test_major_프롬프트는_서술을_주지_않는다():
    p = H.build_major_boundary_prompt(ATOMS)
    assert "산길 이동" in p and "산길을 따라 이동한다." not in p


# ── 개요는 결정적 ───────────────────────────────────────────────────────
def test_개요는_LLM을_쓰지_않는다():
    """v1의 LLM 개요는 supports에 major를 전부 나열해 검증을 통과했다."""
    import inspect
    assert len(inspect.signature(H.compose_overview).parameters) == 1
    ov = H.compose_overview(
        H.build_major_spans(["E01", "E03"], ["산행", "하산"], ATOMS))
    assert ov["source"] == "deterministic"
    assert "산행" in ov["overview"] and "하산" in ov["overview"]


# ── 문서 검증 ───────────────────────────────────────────────────────────
def _doc():
    majors = H.build_major_spans(["E01", "E03"], ["산행 진행", "하산"], ATOMS)
    return {"video_id": "v", "schema": H.SCHEMA, "n_segments": 60,
            "atomic_events": [dict(a) for a in ATOMS],
            "major_events": [dict(m) for m in majors],
            "overview": H.compose_overview(majors)}


def test_유효한_문서는_통과한다():
    assert H.validate_document(_doc(), "v") == []


@pytest.mark.parametrize("mut,code", [
    (lambda d: d["atomic_events"][1].update({"start_seg": 5}), "atomic_overlap"),
    (lambda d: d["atomic_events"][0].update({"title": ""}), "atomic_empty_field"),
    (lambda d: d["atomic_events"][0].update({"anchor_cites": []}),
     "no_anchor_cites"),
    (lambda d: d["atomic_events"][0].update({"anchor_cites": [0, 1, 2, 3]}),
     "too_many_anchors"),
    (lambda d: d["atomic_events"][0].update({"anchor_cites": [0, 1, 2]}),
     "anchor_not_deterministic"),
    (lambda d: d["atomic_events"][0]["support_span"].update({"end_seg": 3}),
     "support_span_mismatch"),
    (lambda d: d["major_events"][0].update({"subevents": ["E01", "E03"]}),
     "major_not_contiguous"),
    (lambda d: d["major_events"][0].update({"start_seg": 2}),
     "major_span_mismatch"),
    (lambda d: d["major_events"].pop(), "atomic_not_partitioned"),
    (lambda d: d["atomic_events"].pop(), "timeline_gap_at_end"),
])
def test_구조_위반을_잡는다(mut, code):
    import copy
    d = copy.deepcopy(_doc())
    mut(d)
    assert code in H.validate_document(d, "v"), H.validate_document(d, "v")


def test_video_id_불일치를_잡는다():
    assert "video_id_mismatch" in H.validate_document(_doc(), "다른영상")


# ── 러너·렌더러 경계 ────────────────────────────────────────────────────
def test_러너는_공식_경로에_쓰지_않는다():
    src = (ROOT / "scripts" / "m8_hier_prototype.py").read_text(encoding="utf-8")
    assert 'assert "report.json" not in p.name' in src
    assert "save_report" not in src


def test_러너는_GT나_판정을_부르지_않는다():
    src = (ROOT / "scripts" / "m8_hier_prototype.py").read_text(encoding="utf-8")
    for bad in ("reference_events", "m8_metrics", "m8_gates", "m8_c1",
                "panel_verdict", "event_temporal_alignment"):
        assert bad not in src, bad


def test_러너는_무효면_CANARY_INVALID로_끝낸다():
    src = (ROOT / "scripts" / "m8_hier_prototype.py").read_text(encoding="utf-8")
    assert "CANARY_INVALID" in src and "HierInvalid" in src


def test_청크_경계는_생성기와_같다():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "runner", ROOT / "scripts" / "m8_hier_prototype.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runner"] = mod
    spec.loader.exec_module(mod)
    segs = [{"idx": i} for i in range(183)]
    got = [(c[0]["idx"], c[-1]["idx"]) for c in mod.chunks(segs, 60, 5)]
    assert got == [(0, 59), (55, 114), (110, 169), (165, 182)]


def _view():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hierview", ROOT / "scripts" / "m8_hier_view.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hierview"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_렌더는_계층과_앵커를_보여준다():
    md = _view().render(_doc())
    assert "M01 — 산행 진행" in md and "E01" in md
    assert "[seg#0]" in md and "채점하지 않음" in md


def test_검증_실패_문서는_렌더하지_않는다():
    import copy
    mod = _view()
    d = copy.deepcopy(_doc())
    d["atomic_events"][0]["anchor_cites"] = [999]
    with pytest.raises(mod.ViewError):
        mod.render(d)
