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


# ── 파서 강건성 (2026-08-29 canary v2 사고) ────────────────────────────
def test_맨_배열도_받는다():
    """모델이 네 청크 전부 맨 배열로 답해 경계가 0개가 됐던 사고."""
    assert H.parse_boundaries('["0", "26", "41", "58"]') == [0, 26, 41, 58]
    assert H.parse_boundaries("[55, 64, 91]") == [55, 64, 91]


def test_문자열_숫자도_받는다():
    assert H.parse_boundaries('{"atomic_start_segments":["110","116"]}') == [110, 116]


def test_숫자가_아니면_버린다():
    assert H.parse_boundaries('["a", "26", null, true]') == [26]


def test_앞뒤_설명이_붙어도_배열을_건진다():
    assert H.parse_boundaries('경계는 다음과 같다: [0, 30]\n끝') == [0, 30]


def test_객체가_있으면_객체를_우선한다():
    raw = '{"atomic_start_segments":[0,50],"note":[9,9,9]}'
    assert H.parse_boundaries(raw) == [0, 50]


# ── v4 title-only format repair ────────────────────────────────────────
def test_title_프롬프트는_서술만_준다():
    """구간을 다시 읽혀 새 사실을 끌어오지 않는다."""
    p = H.build_title_prompt("여성이 산길을 걷는다")
    assert "여성이 산길을 걷는다" in p
    assert "seg#" not in p and "자막" not in p


def test_title_파싱():
    assert H.parse_title('{"title": "산길 이동"}') == "산길 이동"
    assert H.parse_title('```json\n{"title":"숲속 산책"}\n```') == "숲속 산책"
    assert H.parse_title('"산길 이동"') == "산길 이동"


def test_title을_못_만들면_빈값이다():
    """fallback placeholder로 validator를 통과시키지 않는다."""
    assert H.parse_title("제목을 정할 수 없습니다") == ""
    assert H.parse_title("") == ""


def test_오염된_title은_거부된다():
    assert H.parse_title('{"title":"계단 위에는 계단 위에는 계단 위에는 "}') == ""


def _repair_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "titlerepair", ROOT / "scripts" / "m8_hier_title_repair.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["titlerepair"] = mod
    spec.loader.exec_module(mod)
    return mod


def _src():
    atoms = _atomics([0, 15, 30, 45])
    for a in atoms[1:3]:
        a["title"] = ""
    majors = H.build_major_spans(["E01", "E03"], ["산행", "하산"], atoms)
    return {"video_id": "v", "schema": H.SCHEMA, "run_kind": "v3",
            "n_segments": 60, "atomic_events": atoms,
            "major_events": majors, "overview": H.compose_overview(majors)}


def test_빈_title만_채운다():
    mod = _repair_mod()
    out, diag = mod.repair(_src(), lambda p: '{"title":"채운 제목"}')
    assert diag["n_targets"] == 2 and diag["filled"] == ["E02", "E03"]
    assert out["atomic_events"][0]["title"] == "산길 이동"     # 기존 유지
    assert out["atomic_events"][1]["title"] == "채운 제목"


def test_기존_title은_재생성하지_않는다():
    mod = _repair_mod()
    _, diag = mod.repair(_src(), lambda p: '{"title":"x"}')
    assert "E01" not in diag["filled"] and "E04" not in diag["filled"]


def test_하나라도_실패하면_무효다():
    mod = _repair_mod()
    with pytest.raises(H.HierInvalid) as e:
        mod.repair(_src(), lambda p: "제목 못 만들겠습니다")
    assert e.value.reason == "title_repair_failed"


def test_원본을_변형하지_않는다():
    mod = _repair_mod()
    src = _src()
    mod.repair(src, lambda p: '{"title":"x"}')
    assert src["atomic_events"][1]["title"] == ""


def test_구조가_바뀌면_무효다():
    mod = _repair_mod()
    src = _src()
    out, _ = mod.repair(src, lambda p: '{"title":"x"}')
    mod.assert_structure_unchanged(src, out)          # 정상 경로
    out["atomic_events"][0]["end_seg"] = 99
    with pytest.raises(H.HierInvalid) as e:
        mod.assert_structure_unchanged(src, out)
    assert e.value.reason == "frozen_field_changed"


def test_major가_바뀌면_무효다():
    mod = _repair_mod()
    src = _src()
    out, _ = mod.repair(src, lambda p: '{"title":"x"}')
    out["major_events"][0]["title"] = "다른 제목"
    with pytest.raises(H.HierInvalid) as e:
        mod.assert_structure_unchanged(src, out)
    assert e.value.reason == "major_changed"


def test_보수_후_문서가_검증을_통과한다():
    mod = _repair_mod()
    out, _ = mod.repair(_src(), lambda p: '{"title":"채운 제목"}')
    assert H.validate_document(out, "v") == []


# ── 사건 서술 경로 (한 문장) ────────────────────────────────────────────
def test_서술_프롬프트는_JSON을_요구하지_않는다():
    """형식 실패면을 없애는 게 이 경로의 요점이다."""
    p = H.build_narration_prompt(SEGS[:3])
    assert "한 문장" in p
    assert '{"' not in p and "title" not in p


def test_한_문장만_취한다():
    assert H.parse_narration("남성이 산길을 걷는다. 이후 표지판을 확인한다.") == \
        "남성이 산길을 걷는다."


def test_코드펜스와_따옴표를_벗긴다():
    assert H.parse_narration('```\n"두 사람이 버스에 탑승한다."\n```') == \
        "두 사람이 버스에 탑승한다."


def test_빈_서술은_빈값이다():
    assert H.parse_narration("   ") == "" and H.parse_narration(None) == ""


def test_오염된_서술은_거부된다():
    assert H.parse_narration("계단 위에는 계단 위에는 계단 위에는 ") == ""


def _narr_doc(narr="남성이 산길을 걸어 정상에 도착한다."):
    atoms = _atomics([0, 15, 30, 45])
    majors = H.build_major_spans(["E01", "E03"], ["산행", "하산"], atoms)
    return {"video_id": "v", "schema": H.NARRATION_SCHEMA, "n_segments": 60,
            "atomic_events": [{**{k: a[k] for k in
                                  ("event_id", "start_seg", "end_seg",
                                   "support_span", "anchor_cites")},
                               "narration": narr} for a in atoms],
            "major_events": majors, "overview": H.compose_overview(majors)}


def test_서술_문서는_title_없이_검증을_통과한다():
    assert H.validate_narration_document(_narr_doc(), "v") == []


def test_서술이_비면_무효다():
    assert "atomic_no_narration" in H.validate_narration_document(
        _narr_doc(""), "v")


def test_서술_문서도_구조_위반을_잡는다():
    import copy
    d = copy.deepcopy(_narr_doc())
    d["atomic_events"][1]["start_seg"] = 5
    assert "atomic_overlap" in H.validate_narration_document(d, "v")


def test_서술_문서를_렌더한다():
    md = _view().render(_narr_doc())
    assert "남성이 산길을 걸어 정상에 도착한다." in md and "M01 — 산행" in md


def test_narrate_러너는_구조를_만들지_않는다():
    src = (ROOT / "scripts" / "m8_hier_narrate.py").read_text(encoding="utf-8")
    for bad in ("build_atomic_spans", "build_major_spans", "parse_boundaries",
                "reference_events", "m8_metrics", "event_temporal_alignment"):
        assert bad not in src, bad
    assert '"structure_regenerated": False' in src


def test_narrate_러너는_실패해도_원본을_남긴다():
    """v4는 fail-closed 경로에서 원본을 버려 원인을 못 밝혔다."""
    src = (ROOT / "scripts" / "m8_hier_narrate.py").read_text(encoding="utf-8")
    assert '"raw": {"narration": raws}' in src


def test_하위_사건은_한_번만_렌더된다():
    """코드블록 목록과 불릿을 같이 내면 같은 문장을 두 번 읽게 된다."""
    md = _view().render(_narr_doc("남성이 산길을 걸어 정상에 도착한다."))
    assert md.count("남성이 산길을 걸어 정상에 도착한다.") == 4    # 사건 4개 × 1회
