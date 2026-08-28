"""M8 hierarchical prototype — Observation → Atomic → Major → AAR.

규격: `docs/finalization/M8_HIER_PROTOTYPE_SPEC_2026-08-29.md`.

이 프로토타입은 **채점하지 않는다.** C1/C2/C3·Event Recall·GT 비교가 없다.
검사하는 것은 구조적 무결성뿐이고 전부 결정적이다 — judge 없음.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import m8_hier as H                                                 # noqa: E402

CHUNK = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
          "subtitle": "", "caption": f"장면 {i}"} for i in range(0, 60)]


def _atomic(eid, s, e, cites, title="산길을 걸음", desc="산길을 따라 이동한다."):
    return {"event_id": eid, "title": title, "description": desc,
            "start_seg": s, "end_seg": e, "cites": list(cites)}


# ── Observation은 새로 만들지 않는다 ────────────────────────────────────
def test_새_VLM을_돌리지_않는다():
    src = (ROOT / "src" / "m8_hier.py").read_text(encoding="utf-8")
    for bad in ("SentenceTransformer", "caption_frame", "shot_detect",
                "importance_score", "boundary_score"):
        assert bad not in src, f"{bad}를 참조한다 — 규격에서 배제한 항목이다"


def test_GT나_공식결과를_생성입력으로_쓰지_않는다():
    """GT는 prototype 산출물을 맞추기 위한 정답지가 아니다."""
    src = (ROOT / "src" / "m8_hier.py").read_text(encoding="utf-8")
    for bad in ("reference_events", "m8_metrics", "load_reference",
                "event_temporal_alignment", "c1_verdict", "compression("):
        assert bad not in src, f"{bad}를 참조한다"


def test_채점하지_않는다():
    names = {n for n in dir(H) if not n.startswith("_")}
    for bad in ("score", "recall", "verdict", "acceptance", "judge"):
        assert not any(bad in n.lower() for n in names), bad


# ── Atomic 파싱·검증 ────────────────────────────────────────────────────
def test_atomic_파싱은_필수필드를_요구한다():
    raw = ('[{"title":"산길을 걸음","description":"산길을 따라 이동한다.",'
           '"start_seg":3,"end_seg":8,"cites":[3,5,8]}]')
    got = H.parse_atomic(raw)
    assert len(got) == 1 and got[0]["start_seg"] == 3 and got[0]["cites"] == [3, 5, 8]


def test_atomic_파싱은_깨진_JSON에서_빈_리스트를_낸다():
    assert H.parse_atomic("설명만 있고 JSON이 없다") == []


def test_cite가_span_밖이면_거부():
    kept, rej = H.validate_atomic([_atomic("E01", 3, 8, [3, 9])], CHUNK)
    assert not kept and rej[0]["reason"] == "cite_outside_span"


def test_cite가_없으면_거부():
    kept, rej = H.validate_atomic([_atomic("E01", 3, 8, [])], CHUNK)
    assert not kept and rej[0]["reason"] == "no_cites"


def test_존재하지_않는_구간을_인용하면_거부():
    kept, rej = H.validate_atomic([_atomic("E01", 3, 999, [3])], CHUNK)
    assert not kept and rej[0]["reason"] == "span_out_of_range"


def test_역순_span은_거부():
    kept, rej = H.validate_atomic([_atomic("E01", 8, 3, [5])], CHUNK)
    assert not kept and rej[0]["reason"] == "bad_span"


def test_제목이나_서술이_비면_거부():
    kept, rej = H.validate_atomic([_atomic("E01", 3, 8, [5], title="")], CHUNK)
    assert not kept and rej[0]["reason"] == "empty_field"


def test_evidence_개수_상한을_두지_않는다():
    """`too_many_evidence`로 좋은 후보를 버렸던 함정을 반복하지 않는다."""
    kept, _ = H.validate_atomic([_atomic("E01", 0, 59, list(range(0, 40)))], CHUNK)
    assert kept and len(kept[0]["cites"]) == 40


def test_유효하면_통과한다():
    kept, rej = H.validate_atomic([_atomic("E01", 3, 8, [3, 5, 8])], CHUNK)
    assert len(kept) == 1 and not rej


# ── id 부여·중복 제거 ───────────────────────────────────────────────────
def test_id는_시간순으로_결정적으로_부여된다():
    got = H.assign_ids([_atomic(None, 10, 12, [10]), _atomic(None, 3, 5, [3])])
    assert [e["event_id"] for e in got] == ["E01", "E02"]
    assert [e["start_seg"] for e in got] == [3, 10]


def test_청크_겹침에서_생긴_중복은_제거된다():
    """청크가 5구간 겹치므로 같은 사건이 두 번 나올 수 있다."""
    dup = [_atomic(None, 3, 8, [3, 5]), _atomic(None, 3, 8, [3, 5])]
    got, n = H.dedupe_atomic(dup)
    assert len(got) == 1 and n == 1


def test_제목이_다르면_중복이_아니다():
    a = [_atomic(None, 3, 8, [3], title="걷는다"),
         _atomic(None, 3, 8, [3], title="쉰다")]
    got, n = H.dedupe_atomic(a)
    assert len(got) == 2 and n == 0


# ── Major grouping ─────────────────────────────────────────────────────
ATOMS = [_atomic("E01", 0, 9, [0]), _atomic("E02", 10, 19, [10]),
         _atomic("E03", 20, 29, [20]), _atomic("E04", 30, 39, [30])]


def test_연속_분할이면_통과():
    groups = [{"major_event_id": "M01", "title": "산행 진행",
               "atomic_event_ids": ["E01", "E02", "E03"]},
              {"major_event_id": "M02", "title": "하산",
               "atomic_event_ids": ["E04"]}]
    majors, diag = H.compose_major(groups, ATOMS)
    assert diag["ok"] and len(majors) == 2
    assert majors[0]["start_seg"] == 0 and majors[0]["end_seg"] == 29


def test_span과_cites는_코드가_정한다():
    """LLM이 시간 범위와 근거를 자유 생성하지 못하게 한다."""
    groups = [{"major_event_id": "M01", "title": "x",
               "atomic_event_ids": ["E01", "E02", "E03", "E04"],
               "start_seg": 999, "end_seg": 1, "cites": [777]}]
    majors, _ = H.compose_major(groups, ATOMS)
    assert majors[0]["start_seg"] == 0 and majors[0]["end_seg"] == 39
    assert majors[0]["cites"] == [0, 10, 20, 30]


def test_cites는_멤버_합집합이며_상한이_없다():
    atoms = [_atomic("E01", 0, 9, list(range(0, 9))),
             _atomic("E02", 10, 19, list(range(10, 19)))]
    groups = [{"major_event_id": "M01", "title": "x",
               "atomic_event_ids": ["E01", "E02"]}]
    majors, _ = H.compose_major(groups, atoms)
    assert majors[0]["cites"] == sorted(set(range(0, 9)) | set(range(10, 19)))


@pytest.mark.parametrize("groups,reason", [
    ([{"major_event_id": "M01", "title": "x",
       "atomic_event_ids": ["E01", "E03"]},
      {"major_event_id": "M02", "title": "y",
       "atomic_event_ids": ["E02", "E04"]}], "non_contiguous"),
    ([{"major_event_id": "M01", "title": "x",
       "atomic_event_ids": ["E01", "E02"]}], "missing_atomic"),
    ([{"major_event_id": "M01", "title": "x",
       "atomic_event_ids": ["E01", "E02", "E03", "E04"]},
      {"major_event_id": "M02", "title": "y",
       "atomic_event_ids": ["E01"]}], "duplicate_membership"),
    ([{"major_event_id": "M01", "title": "x",
       "atomic_event_ids": ["E01", "E02", "E03", "E04", "E99"]}], "unknown_atomic"),
    ([{"major_event_id": "M01", "title": "",
       "atomic_event_ids": ["E01", "E02", "E03", "E04"]}], "empty_title"),
    ([{"major_event_id": "M01", "title": "x", "atomic_event_ids": []},
      {"major_event_id": "M02", "title": "y",
       "atomic_event_ids": ["E01", "E02", "E03", "E04"]}], "empty_group"),
])
def test_grouping_위반은_fail_closed(groups, reason):
    majors, diag = H.compose_major(groups, ATOMS)
    assert diag["ok"] is False and diag["reason"] == reason
    assert [m["subevents"] for m in majors] == [["E01"], ["E02"],
                                               ["E03"], ["E04"]]


def test_fail_closed면_Atomic_하나당_Major_하나가_된다():
    majors, diag = H.compose_major([], ATOMS)
    assert diag["ok"] is False and len(majors) == len(ATOMS)
    assert majors[0]["title"] == ATOMS[0]["title"]


def test_major_id는_결정적으로_다시_부여된다():
    groups = [{"major_event_id": "zzz", "title": "x",
               "atomic_event_ids": ["E01", "E02"]},
              {"major_event_id": "aaa", "title": "y",
               "atomic_event_ids": ["E03", "E04"]}]
    majors, _ = H.compose_major(groups, ATOMS)
    assert [m["major_event_id"] for m in majors] == ["M01", "M02"]


# ── 개요 ────────────────────────────────────────────────────────────────
def _doc():
    groups = [{"major_event_id": "M01", "title": "산행 진행",
               "atomic_event_ids": ["E01", "E02", "E03"]},
              {"major_event_id": "M02", "title": "하산",
               "atomic_event_ids": ["E04"]}]
    majors, _ = H.compose_major(groups, ATOMS)
    return {"video_id": "v", "schema": H.SCHEMA, "n_segments": 60,
            "atomic_events": ATOMS, "major_events": majors}


def test_개요는_supports가_유효해야_채택된다():
    ov = H.compose_overview(
        '{"overview":"산행을 한다.","flow":"이동 후 하산.","notes":"없음",'
        '"supports":["M01","M02"]}', _doc()["major_events"])
    assert ov["source"] == "llm" and ov["supports"] == ["M01", "M02"]


def test_모르는_major를_인용하면_결정적_개요로_떨어진다():
    ov = H.compose_overview(
        '{"overview":"x","flow":"y","notes":"z","supports":["M99"]}',
        _doc()["major_events"])
    assert ov["source"] == "deterministic"
    assert "산행 진행" in ov["overview"] and "하산" in ov["overview"]


def test_개요_JSON이_깨져도_결정적으로_떨어진다():
    ov = H.compose_overview("모델이 산문만 썼다", _doc()["major_events"])
    assert ov["source"] == "deterministic"


# ── 문서 전체 검증 (규격 §5의 10개) ─────────────────────────────────────
def test_유효한_문서는_통과한다():
    assert H.validate_document(_doc(), "v") == []


@pytest.mark.parametrize("mut,code", [
    (lambda d: d["atomic_events"][0].update({"cites": [999]}), "cite_not_exist"),
    (lambda d: d["atomic_events"][0].update({"cites": [50]}), "cite_outside_atomic"),
    (lambda d: d["atomic_events"][0].update({"cites": []}), "atomic_no_cite"),
    (lambda d: d["major_events"][0].update({"subevents": []}), "major_no_subevent"),
    (lambda d: d["major_events"][0].update({"subevents": ["E99"]}),
     "major_unknown_atomic"),
    (lambda d: d["major_events"][0].update({"start_seg": 5}), "major_span_mismatch"),
    (lambda d: d["major_events"][0].update({"cites": [59]}), "major_cite_invented"),
    (lambda d: d["atomic_events"].append(ATOMS[0]), "atomic_id_duplicate"),
    (lambda d: d["major_events"][1].update({"subevents": ["E01"]}),
     "atomic_assigned_twice"),
])
def test_구조_위반을_전부_잡는다(mut, code):
    import copy
    d = copy.deepcopy(_doc())
    mut(d)
    assert code in H.validate_document(d, "v"), H.validate_document(d, "v")


def test_video_id_불일치를_잡는다():
    assert "video_id_mismatch" in H.validate_document(_doc(), "다른영상")


def test_major가_시간순_연속이_아니면_잡는다():
    import copy
    d = copy.deepcopy(_doc())
    d["major_events"][0], d["major_events"][1] = \
        d["major_events"][1], d["major_events"][0]
    assert "major_not_ordered" in H.validate_document(d, "v")


# ── 프롬프트 경계 ───────────────────────────────────────────────────────
def test_atomic_프롬프트는_구간만_준다():
    p = H.build_atomic_prompt(CHUNK[:3])
    assert "seg#0" in p and "장면 0" in p
    for bad in ("정답", "GT", "reference", "68"):
        assert bad not in p


def test_major_프롬프트는_id와_시각과_제목만_준다():
    p = H.build_major_prompt(ATOMS)
    assert "E01" in p and "산길을 걸음" in p
    assert "산길을 따라 이동한다." not in p, "description을 넣으면 재생성 유인이 생긴다"


def test_major_프롬프트는_개수를_지시하지_않는다():
    """고정 event-count cap을 만들지 않는다."""
    p = H.build_major_prompt(ATOMS)
    for bad in ("최대 ", "개 이하", "개까지"):
        assert bad not in p


def test_overview_프롬프트는_major만_준다():
    p = H.build_overview_prompt(_doc()["major_events"])
    assert "M01" in p and "산행 진행" in p
    assert "E01" not in p


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


def _renderable():
    groups = [{"major_event_id": "M01", "title": "산행 진행",
               "atomic_event_ids": ["E01", "E02", "E03"]},
              {"major_event_id": "M02", "title": "하산",
               "atomic_event_ids": ["E04"]}]
    majors, _ = H.compose_major(groups, ATOMS)
    return {"video_id": "v", "schema": H.SCHEMA, "run_kind": "t",
            "n_segments": 60, "atomic_events": ATOMS, "major_events": majors,
            "overview": {"source": "llm", "overview": "산행을 한다.",
                         "flow": "이동 후 하산.", "notes": "없음",
                         "supports": ["M01", "M02"]}}


def test_렌더는_계층과_시각을_보여준다():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hierview", ROOT / "scripts" / "m8_hier_view.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hierview"] = mod
    spec.loader.exec_module(mod)
    md = mod.render(_renderable())
    assert "M01 — 산행 진행" in md and "00:00:00" in md
    assert "E01" in md and "[seg#0]" in md
    assert "채점하지 않음" in md


def test_검증_실패_문서는_렌더하지_않는다():
    import copy
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hierview2", ROOT / "scripts" / "m8_hier_view.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hierview2"] = mod
    spec.loader.exec_module(mod)
    d = copy.deepcopy(_renderable())
    d["atomic_events"][0]["cites"] = [999]
    with pytest.raises(mod.ViewError):
        mod.render(d)
