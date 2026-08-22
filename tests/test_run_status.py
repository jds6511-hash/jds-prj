"""실행 상태 마커 — **마커가 있다는 사실이 완료 근거가 아니다.**

2026-08-22 사고: 같은 run_id로 CANARY를 돌린 뒤 FULL을 시작했더니 CANARY가 남긴
`STAGE_m3_*`·`STAGE_m4_index_DONE`이 이미 있어서, FULL이 m2를 돌고 있는데 m4까지 끝난
것으로 읽혔다. 연구 결과는 오염되지 않았다(단계 소요는 배치 내부 시계에서 나오고,
마커는 건너뛰기 근거가 아니며, hook은 `*_full.json`을 우선한다). **관찰가능성 결함이다.**

그래서 새 마커는 mode·run_id·commit·stage·created_at·산출물 해시를 담고, 상태 판독기는
**현재 실행과 맞는 마커만** 완료로 센다. 이 모듈은 아직 launcher에 연결하지 않는다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_status as S                                           # noqa: E402

SRC = (ROOT / "scripts" / "run_status.py").read_text(encoding="utf-8")
STAGES = ("m1_segments", "m2_frames", "m3_base", "mirror_frames",
          "m3_captions", "m4_index")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


def _mark(d, stage, mode="FULL", run_id="r1", commit="c" * 40, **kw):
    return S.write_marker(d, stage=stage, mode=mode, run_id=run_id,
                          commit=commit, created_at="2026-01-01T00:00:00", **kw)


# ------------------------------------------------------------ 마커 스키마

def test_marker_name_is_namespaced_by_mode(tmp_path):
    p = _mark(tmp_path, "m2_frames", mode="CANARY")
    assert p.name == "CANARY_STAGE_m2_frames_DONE.json"
    assert _mark(tmp_path, "m2_frames").name == "FULL_STAGE_m2_frames_DONE.json"


def test_marker_records_mode_run_id_commit_and_time(tmp_path):
    p = _mark(tmp_path, "m1_segments", output_hash="a" * 64)
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["mode"] == "FULL" and d["run_id"] == "r1"
    assert d["commit"] == "c" * 40 and d["created_at"]
    assert d["stage"] == "m1_segments" and d["output_hash"] == "a" * 64


def test_unknown_mode_or_stage_is_refused(tmp_path):
    with pytest.raises(S.StatusError, match="mode"):
        _mark(tmp_path, "m1_segments", mode="SMOKE")
    with pytest.raises(S.StatusError, match="stage"):
        _mark(tmp_path, "m9_report")


# ------------------------------------------------- 완료 판정은 마커만으로 안 한다

def test_canary_marker_never_counts_as_full_completion(tmp_path):
    _mark(tmp_path, "m4_index", mode="CANARY")
    st = S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40)
    assert st["stages"]["m4_index"] == "pending"
    assert "CANARY" in st["ignored_markers"][0]


def test_marker_from_another_run_or_commit_is_ignored(tmp_path):
    _mark(tmp_path, "m1_segments", run_id="other")
    _mark(tmp_path, "m2_frames", commit="d" * 40)
    st = S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40)
    assert st["stages"]["m1_segments"] == "pending"
    assert st["stages"]["m2_frames"] == "pending"
    assert len(st["ignored_markers"]) == 2


def test_matching_markers_are_complete_and_next_stage_is_running(tmp_path):
    _mark(tmp_path, "m1_segments")
    _mark(tmp_path, "m2_frames")
    st = S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40,
                  process_alive=True)
    assert st["stages"]["m1_segments"] == "complete"
    assert st["stages"]["m2_frames"] == "complete"
    assert st["stages"]["m3_base"] == "running"
    assert st["stages"]["m4_index"] == "pending"


def test_without_a_live_process_the_next_stage_is_not_called_running(tmp_path):
    _mark(tmp_path, "m1_segments")
    st = S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40,
                  process_alive=False)
    assert st["stages"]["m2_frames"] == "pending"
    assert st["process_alive"] is False


def test_run_complete_requires_the_marker_file(tmp_path):
    for s in STAGES:
        _mark(tmp_path, s)
    st = S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40)
    assert all(v == "complete" for v in st["stages"].values())
    assert st["run_complete"] is False
    assert st["validator"] == "pending"
    (tmp_path / "RUN_COMPLETE.json").write_text("{}", encoding="utf-8")
    st2 = S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40)
    assert st2["run_complete"] is True and st2["validator"] == "passed"


def test_legacy_unnamespaced_markers_are_reported_but_not_trusted(tmp_path):
    """지금 돌고 있는 run이 남긴 옛 이름 마커도 완료로 세지 않는다."""
    (tmp_path / "STAGE_m4_index_DONE").write_text("{}", encoding="utf-8")
    st = S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40)
    assert st["stages"]["m4_index"] == "pending"
    assert st["legacy_markers"] == ["STAGE_m4_index_DONE"]


def test_status_is_read_only(tmp_path):
    _mark(tmp_path, "m1_segments")
    before = sorted(p.name for p in tmp_path.iterdir())
    S.status(tmp_path, run_id="r1", mode="FULL", commit="c" * 40)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_render_lists_every_stage_and_the_completion_flag(tmp_path):
    _mark(tmp_path, "m1_segments")
    text = S.render(S.status(tmp_path, run_id="r1", mode="FULL",
                             commit="c" * 40))
    for s in STAGES:
        assert s in text
    assert "RUN_COMPLETE: false" in text


# ------------------------------------------- 기존 계약을 약화시키지 않는다

def test_it_does_not_delete_or_rewrite_existing_markers():
    for token in ("unlink", "rmtree", "os.remove", "replace("):
        assert token not in CODE


def test_it_does_not_write_run_complete():
    assert "RUN_COMPLETE" in CODE          # 읽기는 한다
    assert "RUN_COMPLETE.json\").write" not in CODE
    assert "write_run_complete" not in CODE
