"""AAR 추적 렌더러 — report.json의 각 문장을 timestamp·근거까지 잇는다.

LLM을 쓰지 않는다. 이미 생성된 `report.json`을 읽어 **주장 → 세그먼트 → 시각 → 근거**를
연결하고, 잇지 못하는 인용은 fail-closed로 드러낸다. 새 서술을 만들지 않는다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import aar_view as A                                                # noqa: E402


def _segs(n=6, seg_len=5):
    return {"n_segments": n, "segments": [
        {"idx": i, "start": i * seg_len, "end": (i + 1) * seg_len,
         "subtitle": f"발화{i}", "caption": f"화면{i}",
         "motion_score": 0.5} for i in range(n)]}


def _report(cites=((0, 1), (3,)), video_id="v"):
    return {"video_id": video_id, "schema_version": 2,
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "sentences": [{"sent_id": i, "text": f"사건 {i} 서술",
                           "cites": list(c)} for i, c in enumerate(cites)],
            "raw_output": "…"}


def _write(tmp_path, report=None, segs=None):
    (tmp_path / "report.json").write_text(
        json.dumps(report or _report(), ensure_ascii=False), encoding="utf-8")
    (tmp_path / "segments.json").write_text(
        json.dumps(segs or _segs(), ensure_ascii=False), encoding="utf-8")
    return tmp_path / "report.json", tmp_path / "segments.json"


# ---- 추적 ------------------------------------------------------------------

def test_each_sentence_resolves_to_timestamps(tmp_path):
    rp, sp = _write(tmp_path)
    doc = A.build(rp, sp)
    s0 = doc["sentences"][0]
    assert s0["cites"] == [0, 1]
    assert s0["spans"] == [{"idx": 0, "start": 0, "end": 5},
                           {"idx": 1, "start": 5, "end": 10}]
    assert s0["seek_to"] == 0
    assert s0["time_range"] == {"start": 0, "end": 10}


def test_evidence_comes_from_the_index_only(tmp_path):
    rp, sp = _write(tmp_path)
    ev = A.build(rp, sp)["sentences"][0]["evidence"]
    assert ev[0] == {"idx": 0, "subtitle": "발화0", "caption": "화면0"}


def test_no_new_narration_is_generated(tmp_path):
    """렌더러는 문장을 만들지 않는다 — report의 text를 그대로 옮긴다."""
    rp, sp = _write(tmp_path)
    doc = A.build(rp, sp)
    assert [s["text"] for s in doc["sentences"]] == ["사건 0 서술", "사건 1 서술"]


def test_sentences_are_ordered_by_first_cited_time(tmp_path):
    rp, sp = _write(tmp_path, report=_report(cites=((4,), (1,))))
    doc = A.build(rp, sp)
    assert [s["sent_id"] for s in doc["timeline"]] == [1, 0]


# ---- fail-closed -----------------------------------------------------------

def test_out_of_range_citation_is_refused(tmp_path):
    rp, sp = _write(tmp_path, report=_report(cites=((99,),)))
    with pytest.raises(A.TraceError) as e:
        A.build(rp, sp)
    assert "99" in str(e.value)


def test_sentence_without_citation_is_refused(tmp_path):
    rp, sp = _write(tmp_path, report=_report(cites=((),)))
    with pytest.raises(A.TraceError):
        A.build(rp, sp)


def test_video_id_mismatch_is_refused(tmp_path):
    rp, sp = _write(tmp_path, report=_report(video_id="other"))
    with pytest.raises(A.TraceError) as e:
        A.build(rp, sp, video_id="v")
    assert "video_id" in str(e.value)


def test_missing_report_is_refused(tmp_path):
    with pytest.raises(A.TraceError):
        A.build(tmp_path / "nope.json", tmp_path / "also_nope.json")


def test_unknown_schema_version_is_refused(tmp_path):
    r = _report()
    r["schema_version"] = 99
    rp, sp = _write(tmp_path, report=r)
    with pytest.raises(A.TraceError) as e:
        A.build(rp, sp)
    assert "schema_version" in str(e.value)


# ---- 통계·경계 -------------------------------------------------------------

def test_coverage_is_descriptive_only(tmp_path):
    rp, sp = _write(tmp_path)
    doc = A.build(rp, sp)
    assert doc["cited_segments"] == 3 and doc["n_segments"] == 6
    assert doc["cited_fraction"] == 0.5
    assert "평가 지표가 아니다" in doc["coverage_note"]


def test_document_declares_no_m9_and_no_test(tmp_path):
    rp, sp = _write(tmp_path)
    doc = A.build(rp, sp)
    assert doc["m9_evaluated"] is False
    assert doc["test_split_used"] is False


def test_markdown_render_has_one_block_per_sentence(tmp_path):
    rp, sp = _write(tmp_path)
    md = A.to_markdown(A.build(rp, sp))
    assert md.count("### ") == 2
    assert "00:00~00:10" in md
    assert "발화0" in md and "화면0" in md


def test_module_does_not_import_llm_or_evaluation():
    import ast
    src = (ROOT / "scripts" / "aar_view.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"llm", "m8_report", "m9_report_eval", "torch",
                 "transformers"} & mods)


# ---- 사전 생성 artifact 정합 (발표 fallback) -------------------------------

def test_segment_count_mismatch_is_refused(tmp_path):
    """리포트 생성 후 인덱스가 바뀌면 인용 번호의 의미가 달라진다."""
    r = _report()
    r["provenance"] = {"n_segments": 99}
    rp, sp = _write(tmp_path, report=r)
    with pytest.raises(A.TraceError) as e:
        A.build(rp, sp)
    assert "n_segments" in str(e.value)


def test_matching_segment_count_passes(tmp_path):
    r = _report()
    r["provenance"] = {"n_segments": 6}
    rp, sp = _write(tmp_path, report=r)
    assert A.build(rp, sp)["index_consistency"]["n_segments_checked"] is True


def test_provenance_without_counts_is_reported_not_fatal(tmp_path):
    rp, sp = _write(tmp_path)
    doc = A.build(rp, sp)
    assert doc["index_consistency"]["n_segments_checked"] is False
    assert doc["index_consistency"]["note"]


def test_check_precomputed_reports_instead_of_raising(tmp_path):
    rp, sp = _write(tmp_path, report=_report(cites=((99,),)))
    st = A.check_precomputed(rp, sp)
    assert st["ok"] is False and "99" in st["reason"]


def test_check_precomputed_ok_path(tmp_path):
    rp, sp = _write(tmp_path)
    st = A.check_precomputed(rp, sp)
    assert st["ok"] is True and st["n_sentences"] == 2
    assert st["reason"] is None


def test_check_precomputed_missing_file(tmp_path):
    st = A.check_precomputed(tmp_path / "no.json", tmp_path / "no2.json")
    assert st["ok"] is False and "없다" in st["reason"]


def test_run_kind_is_labeled_as_demo_not_research(tmp_path):
    """M8 research evaluation과 이름을 분리한다."""
    rp, sp = _write(tmp_path)
    doc = A.build(rp, sp)
    assert doc["run_kind"] == "aar_demo_render"
    assert doc["m8_research_evaluation"] is False
