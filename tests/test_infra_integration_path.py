"""인프라 3건 통합 경로 — synthetic dry-run.

coverage 게이트 → 단계 마커 → 상태 판독 → registry 조회가 **한 경로로 이어지는지**만
본다. GPU도 모델도 쓰지 않고, 실제 P2 산출물을 건드리지 않는다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import canary_coverage as C     # noqa: E402
import exp_launcher as L        # noqa: E402
import p2_index_batch as B      # noqa: E402
import run_status as S          # noqa: E402
import video_registry as R      # noqa: E402

RID, COMMIT = "synth1", "1234567"
CODECS = {"aaa": "native_h264", "-bbb": "transcoded_h264",
          "ccc": "native_h264"}
H = "b" * 64


def _rows():
    return [
        {"source_id": "aaa", "n_segments": 100, "pre_indexed": False,
         "speech_status": C.AUDIO_KNOWN, "source_url": "http://x/aaa",
         "file_sha256": H, "duration_sec": 499.0},
        {"source_id": "-bbb", "n_segments": 200, "pre_indexed": True,
         "speech_status": "unknown"},
        {"source_id": "ccc", "n_segments": 300, "pre_indexed": False,
         "speech_status": C.AUDIO_KNOWN, "source_url": "http://x/ccc",
         "file_sha256": H, "duration_sec": 1499.0},
    ]


@pytest.fixture
def world(tmp_path):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"selected": _rows()}, ensure_ascii=False),
                      encoding="utf-8")
    d = tmp_path / "run" / RID
    d.mkdir(parents=True)
    (d / "batch_run_canary.json").write_text(
        json.dumps({"video_ids": ["aaa", "-bbb", "ccc"]}), encoding="utf-8")
    plan = {"name": "synth", "command": ["echo"], "canary_args": [],
            "full_args": [], "run_root": "run", "log_dir": str(tmp_path),
            "protected_splits": ["test"], "expected_files": ["o.json"],
            C.COVERAGE_KEY: {"sample": str(sample),
                             "canary_result": "batch_run_canary.json"}}
    return {"plan": plan, "run_dir": d, "sample": sample}


def test_full_path_coverage_marker_status_registry(world):
    # 1. coverage 게이트
    cov = L.require_stage_approval(
        world["plan"], RID, {"canary_validated": True}, stage="FULL",
        approve_full=RID, approve_test_open=None, root=ROOT,
        run_dir=world["run_dir"], codec_of=CODECS)
    assert cov["required"] is True and cov["ok"] is True

    # 2. 단계 마커 (배치가 쓰는 경로)
    for st in S.STAGES:
        B.stage_marker(world["run_dir"], st, mode="FULL", run_id=RID,
                       commit=COMMIT, elapsed_sec=1.0,
                       created_at="2026-08-24T00:00:00")

    # 3. 상태 판독 — 마커가 다 있어도 완료가 아니다
    st = S.status(world["run_dir"], run_id=RID, mode="FULL", commit=COMMIT)
    assert all(v == "complete" for v in st["stages"].values())
    assert st["run_complete"] is False

    # 4. registry 조회 — 읽기 전용, 전환은 HOLD
    reg = R.dry_run(selection=world["sample"], duration_artifact=None)
    assert reg["contracts_ok"] is True
    assert reg["sot_transition"] == "HOLD"
    assert reg["adapter_mode"] == "read_only"


def test_coverage_failure_stops_before_markers(world):
    (world["run_dir"] / "batch_run_canary.json").write_text(
        json.dumps({"video_ids": ["aaa"]}), encoding="utf-8")
    with pytest.raises((L.LauncherError, C.CoverageError)):
        L.require_stage_approval(
            world["plan"], RID, {"canary_validated": True}, stage="FULL",
            approve_full=RID, approve_test_open=None, root=ROOT,
            run_dir=world["run_dir"], codec_of=CODECS)
    assert not list(world["run_dir"].glob("*_DONE.json"))


def test_no_module_in_path_touches_model_outcome():
    """네 모듈 중 어느 것도 검색·평가 모듈을 import하지 않는다."""
    forbidden = {"m5_search", "m6_evaluate", "p2_retrieve", "p2_evaluate",
                 "m8_report", "m9_report_eval"}
    for name in ("canary_coverage", "run_status", "video_registry",
                 "exp_launcher"):
        src = (ROOT / "scripts" / f"{name}.py").read_text(encoding="utf-8")
        mods = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert not (forbidden & mods), f"{name}: {forbidden & mods}"


def test_run_complete_writer_is_still_only_finalize():
    """RUN_COMPLETE를 쓰는 경로가 늘어나지 않았다."""
    writers = []
    for p in sorted((ROOT / "scripts").glob("*.py")):
        src = p.read_text(encoding="utf-8")
        if "RUN_COMPLETE" in src and "write_text" in src:
            for line in src.splitlines():
                if "RUN_COMPLETE" in line and "m = " in line:
                    writers.append(p.name)
    assert set(writers) <= {"exp_launcher.py"}


def test_p2_completed_run_artifacts_are_not_referenced_for_rewrite():
    """완료 마커 migration 경로를 만들지 않았다."""
    for name in ("run_status.py", "p2_index_batch.py", "make_handoff.py"):
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        for bad in ("unlink()", "os.remove", "shutil.move", "rename("):
            assert bad not in src or "STAGE" not in src, f"{name}: {bad}"
