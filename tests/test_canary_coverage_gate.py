"""CANARY coverage를 FULL 승인 경로에 붙인 게이트 — 계약 테스트.

기존 `coverage()`는 검사 API였고 launcher에 연결되지 않았다. 여기서 붙이는 것은
**선언한 계획에만** 적용되는 fail-closed 게이트다. 선언이 없으면 요구하지 않되,
요구하지 않았다는 사실을 숨기지 않는다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import canary_coverage as C     # noqa: E402
import exp_launcher as L        # noqa: E402

CANARY_RESULT = "batch_run_canary.json"


def _corpus(tmp_path, rows) -> Path:
    p = tmp_path / "sample.json"
    p.write_text(json.dumps({"selected": rows}, ensure_ascii=False),
                 encoding="utf-8")
    return p


def _rows():
    return [
        {"source_id": "aaa", "n_segments": 100, "pre_indexed": False,
         "speech_status": C.AUDIO_KNOWN},
        {"source_id": "-bbb", "n_segments": 200, "pre_indexed": True,
         "speech_status": "unknown"},
        {"source_id": "ccc", "n_segments": 300, "pre_indexed": False,
         "speech_status": C.AUDIO_KNOWN},
    ]


CODECS = {"aaa": "native_h264", "-bbb": "transcoded_h264",
          "ccc": "native_h264"}


def _run_dir(tmp_path, canary_ids, extra=None) -> Path:
    d = tmp_path / "run"
    d.mkdir(exist_ok=True)
    body = {"video_ids": list(canary_ids), "n_videos": len(canary_ids)}
    body.update(extra or {})
    (d / CANARY_RESULT).write_text(json.dumps(body, ensure_ascii=False),
                                   encoding="utf-8")
    return d


def _plan(sample: Path, **kw):
    decl = {"sample": str(sample), "canary_result": CANARY_RESULT}
    decl.update(kw)
    return {"name": "t", C.COVERAGE_KEY: decl}


# ---- 선언 누락 처리는 test_canary_coverage_required.py에서 본다 --------------

def test_unknown_plan_without_declaration_is_blocked(tmp_path):
    """모르는 계획이 선언 없이 통과하지 않는다 (상세 갈래는 별 파일)."""
    with pytest.raises(C.CoverageError):
        C.gate_for_full({"name": "t"}, run_dir=tmp_path, root=ROOT)


# ---- 선언이 있으면 fail-closed ---------------------------------------------

def test_full_coverage_passes(tmp_path):
    sample = _corpus(tmp_path, _rows())
    # aaa(신규·최단·h264·audio known) + -bbb(기확보·변환·하이픈·audio unresolved)
    # + ccc(최장)
    d = _run_dir(tmp_path, ["aaa", "-bbb", "ccc"])
    r = C.gate_for_full(_plan(sample), run_dir=d, root=ROOT, codec_of=CODECS)
    assert r["required"] is True and r["ok"] is True
    assert r["coverage_kind"] == "marginal_per_axis"


def test_missing_class_blocks_full(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa"])           # 기확보·변환·하이픈·최장 미포함
    with pytest.raises(C.CoverageError):
        C.gate_for_full(_plan(sample), run_dir=d, root=ROOT, codec_of=CODECS)


def test_missing_sample_file_blocks_full(tmp_path):
    d = _run_dir(tmp_path, ["aaa"])
    with pytest.raises(C.CoverageError):
        C.gate_for_full(_plan(tmp_path / "nope.json"), run_dir=d, root=ROOT,
                        codec_of=CODECS)


def test_missing_canary_result_blocks_full(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = tmp_path / "empty"
    d.mkdir()
    with pytest.raises(C.CoverageError):
        C.gate_for_full(_plan(sample), run_dir=d, root=ROOT, codec_of=CODECS)


def test_canary_result_without_video_ids_blocks_full(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = tmp_path / "run"
    d.mkdir()
    (d / CANARY_RESULT).write_text(json.dumps({"n_videos": 2}),
                                   encoding="utf-8")
    with pytest.raises(C.CoverageError):
        C.gate_for_full(_plan(sample), run_dir=d, root=ROOT, codec_of=CODECS)


def test_empty_video_ids_blocks_full(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, [])
    with pytest.raises(C.CoverageError):
        C.gate_for_full(_plan(sample), run_dir=d, root=ROOT, codec_of=CODECS)


def test_required_combination_absent_from_full_is_refused(tmp_path):
    """FULL 입력에 없는 조합을 요구하는 config는 영원히 통과 못 한다 — 거부한다."""
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa", "-bbb", "ccc"])
    plan = _plan(sample, required_combinations=[
        ["codec:native_h264", "provenance:legacy"]])
    with pytest.raises(C.CoverageError, match="영원히"):
        C.gate_for_full(plan, run_dir=d, root=ROOT, codec_of=CODECS)


def test_required_combination_present_but_uncovered_blocks(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa", "ccc"])
    plan = _plan(sample, required_combinations=[
        ["codec:transcoded_h264", "id_shape:cli_sensitive"]])
    with pytest.raises(C.CoverageError):
        C.gate_for_full(plan, run_dir=d, root=ROOT, codec_of=CODECS)


def test_default_required_combinations_is_empty(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa", "-bbb", "ccc"])
    r = C.gate_for_full(_plan(sample), run_dir=d, root=ROOT, codec_of=CODECS)
    assert r["required_combinations"] == []


# ---- 모델 산출물을 읽지 않는다 ---------------------------------------------

def test_only_video_ids_read_from_canary_result(tmp_path):
    """CANARY 결과에 캡션·점수가 있어도 게이트는 video_ids만 본다."""
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa", "-bbb", "ccc"],
                 extra={"caption": "SENTINEL캡션", "mrr": 0.123,
                        "rank": [1, 2, 3], "score": 9.9})
    r = C.gate_for_full(_plan(sample), run_dir=d, root=ROOT, codec_of=CODECS)
    blob = json.dumps(r, ensure_ascii=False)
    assert "SENTINEL캡션" not in blob and "0.123" not in blob
    assert r["read_keys"] == ["video_ids"]


def test_gate_module_does_not_import_search_or_eval():
    import ast
    src = (ROOT / "scripts" / "canary_coverage.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m5_search", "m6_evaluate", "p2_retrieve", "p2_evaluate"}
                & mods)


# ---- launcher 연결 --------------------------------------------------------

def _launcher_plan(tmp_path, sample):
    p = dict(_plan(sample), command=["echo"], run_root="out",
             log_dir=str(tmp_path / "logs"), full_args=[], canary_args=[],
             protected_splits=["test"], expected_files=["o.json"])
    return p


def test_launcher_full_blocked_when_coverage_missing(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa"])
    plan = _launcher_plan(tmp_path, sample)
    with pytest.raises((L.LauncherError, C.CoverageError)):
        L.require_stage_approval(plan, "r1", {"canary_validated": True},
                                 stage="FULL", approve_full="r1",
                                 approve_test_open=None, root=ROOT,
                                 run_dir=d, codec_of=CODECS)


def test_launcher_full_passes_when_covered(tmp_path):
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa", "-bbb", "ccc"])
    plan = _launcher_plan(tmp_path, sample)
    L.require_stage_approval(plan, "r1", {"canary_validated": True},
                             stage="FULL", approve_full="r1",
                             approve_test_open=None, root=ROOT,
                             run_dir=d, codec_of=CODECS)


def test_launcher_canary_stage_not_gated(tmp_path):
    sample = _corpus(tmp_path, _rows())
    plan = _launcher_plan(tmp_path, sample)
    L.require_stage_approval(plan, "r1", {}, stage="CANARY",
                             approve_full=None, approve_test_open=None,
                             root=ROOT)


def test_declared_coverage_without_run_dir_is_refused(tmp_path):
    """선언했는데 run_dir을 못 주면 조용히 넘기지 않는다."""
    sample = _corpus(tmp_path, _rows())
    plan = _launcher_plan(tmp_path, sample)
    with pytest.raises((L.LauncherError, C.CoverageError)):
        L.require_stage_approval(plan, "r1", {"canary_validated": True},
                                 stage="FULL", approve_full="r1",
                                 approve_test_open=None, root=ROOT,
                                 run_dir=None, codec_of=CODECS)


def test_approval_checks_run_before_coverage(tmp_path):
    """오염 위험(승인 부재)이 배관 순서보다 먼저 보고돼야 한다."""
    sample = _corpus(tmp_path, _rows())
    d = _run_dir(tmp_path, ["aaa"])            # coverage도 실패할 상태
    plan = _launcher_plan(tmp_path, sample)
    with pytest.raises(L.LauncherError, match="승인"):
        L.require_stage_approval(plan, "r1", {"canary_validated": True},
                                 stage="FULL", approve_full=None,
                                 approve_test_open=None, root=ROOT,
                                 run_dir=d, codec_of=CODECS)


# ---- 완료된 P2 run에 소급 적용하지 않는다 -----------------------------------

def test_completed_p2_plan_is_not_retroactively_gated():
    """`p2_index_plan.json`에 선언을 넣으면 plan_hash가 바뀌어 완료된 run의 REPORT가
    막힌다(exp_launcher L432). 그래서 선언을 넣지 않는다."""
    plan = json.loads((ROOT / "docs" / "planning" / "p2_index_plan.json")
                      .read_text(encoding="utf-8"))
    assert C.COVERAGE_KEY not in plan
