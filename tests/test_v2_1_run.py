"""A-02 run layout + manifest.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-02
선행: RPT-008(`analysis_mode != report` → render 거부) · RAW-006(run 분리)

```
manifest.json   video_id · run_id · analysis_mode · config_hash · code_git_head
디렉터리         media · raw · evidence · structure · canonical · presentation · rendered
```

manifest는 **provenance를 기록하는 자리**다. parse·sanitation 상태를 여기서 다시
정의하지 않는다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_scan import code_only
from v2_1_run import (
    ANALYSIS_MODES,
    RUN_DIRS,
    Manifest,
    RenderRefused,
    RunError,
    create_run,
    current_git_head,
    hash_config,
    load_manifest,
    require_report_mode,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/v2_1_run.py"


def _create(root, **kw):
    kw.setdefault("video_id", "wonyi_geoje")
    kw.setdefault("run_id", "run-001")
    kw.setdefault("analysis_mode", "report")
    kw.setdefault("config_hash", "abc123")
    kw.setdefault("code_git_head", "feef865")
    return create_run(root, **kw)


# ── 레이아웃 ─────────────────────────────────────────────────────────────
def test_all_seven_directories_are_created(tmp_path):
    run = _create(tmp_path)
    assert sorted(RUN_DIRS) == sorted(
        p.name for p in run.path.iterdir() if p.is_dir()
    )


def test_directory_names_are_the_declared_ones():
    assert RUN_DIRS == ("media", "raw", "evidence", "structure", "canonical",
                        "presentation", "rendered")


def test_dir_returns_the_subdirectory(tmp_path):
    run = _create(tmp_path)
    assert run.dir("raw") == run.path / "raw"
    assert run.dir("raw").is_dir()


def test_unknown_directory_is_refused(tmp_path):
    with pytest.raises(RunError, match="unknown run directory"):
        _create(tmp_path).dir("scratch")


def test_runs_live_under_video_then_run_id(tmp_path):
    run = _create(tmp_path)
    assert run.path == tmp_path / "wonyi_geoje" / "run-001"


# ── manifest ─────────────────────────────────────────────────────────────
def test_manifest_records_the_five_fields(tmp_path):
    run = _create(tmp_path)
    written = json.loads((run.path / "manifest.json").read_text(encoding="utf-8"))
    assert written == {
        "video_id": "wonyi_geoje",
        "run_id": "run-001",
        "analysis_mode": "report",
        "config_hash": "abc123",
        "code_git_head": "feef865",
    }


def test_manifest_round_trips(tmp_path):
    run = _create(tmp_path)
    assert load_manifest(run.path) == run.manifest


def test_manifest_is_immutable(tmp_path):
    with pytest.raises(Exception):
        _create(tmp_path).manifest.analysis_mode = "preview"


@pytest.mark.parametrize("field", ["video_id", "run_id", "config_hash",
                                   "code_git_head"])
def test_blank_provenance_field_is_refused(tmp_path, field):
    with pytest.raises(RunError, match=field):
        _create(tmp_path, **{field: "  "})


def test_manifest_does_not_carry_analysis_state():
    """provenance 자리다 — 판정 상태를 여기서 다시 정의하지 않는다."""
    code = code_only(SRC)
    for forbidden in ("usable_for_claims", "SUSPECT", "PARSE_", "sanitation",
                      "boundary_positions"):
        assert forbidden not in code, "판정 상태가 manifest로 새어 들어왔다: " + forbidden


# ── analysis_mode ────────────────────────────────────────────────────────
def test_the_three_declared_modes():
    assert ANALYSIS_MODES == ("preview", "report", "hybrid")


def test_unknown_mode_is_refused(tmp_path):
    with pytest.raises(RunError, match="analysis_mode"):
        _create(tmp_path, analysis_mode="draft")


@pytest.mark.parametrize("mode", ["preview", "hybrid"])
def test_rpt_008_non_report_mode_refuses_rendering(tmp_path, mode):
    run = _create(tmp_path, analysis_mode=mode)
    with pytest.raises(RenderRefused, match="analysis_mode"):
        require_report_mode(run.manifest)


def test_rpt_008_report_mode_passes(tmp_path):
    assert require_report_mode(_create(tmp_path).manifest) is None


def test_rpt_008_refusal_does_not_coerce_the_mode(tmp_path):
    """report로 자동 보정하면 미리보기 산출물이 정식 근거가 된다."""
    run = _create(tmp_path, analysis_mode="preview")
    with pytest.raises(RenderRefused):
        require_report_mode(run.manifest)
    assert load_manifest(run.path).analysis_mode == "preview"


def test_rpt_008_interlock_has_no_fallback_path():
    code = code_only(SRC)
    for forbidden in ("fallback", "except RenderRefused", 'mode = "report"'):
        assert forbidden not in code, "보정 경로가 있다: " + forbidden


# ── RAW-006 run 분리 ─────────────────────────────────────────────────────
def test_raw_006_two_runs_of_one_video_do_not_share_a_directory(tmp_path):
    first = _create(tmp_path, run_id="run-001")
    second = _create(tmp_path, run_id="run-002")
    assert first.path != second.path
    assert first.dir("raw") != second.dir("raw")


def test_raw_006_reusing_a_run_id_is_refused(tmp_path):
    _create(tmp_path)
    with pytest.raises(RunError, match="already exists"):
        _create(tmp_path)


def test_raw_006_an_existing_run_keeps_its_artifacts(tmp_path):
    run = _create(tmp_path)
    (run.dir("raw") / "keep.txt").write_text("payload", encoding="utf-8")
    with pytest.raises(RunError):
        _create(tmp_path)
    assert (run.dir("raw") / "keep.txt").read_text(encoding="utf-8") == "payload"


def test_different_videos_are_separated(tmp_path):
    a = _create(tmp_path, video_id="wonyi_geoje")
    b = _create(tmp_path, video_id="m8c2_3I7oGwk6EaQ")
    assert a.path.parent != b.path.parent


# ── provenance helper ────────────────────────────────────────────────────
def test_config_hash_is_stable_and_order_independent():
    a = hash_config({"boundary": {"provider": "fixed_window_v1"}, "ocr": False})
    b = hash_config({"ocr": False, "boundary": {"provider": "fixed_window_v1"}})
    assert a == b == hash_config({"ocr": False,
                                  "boundary": {"provider": "fixed_window_v1"}})


def test_config_hash_changes_with_content():
    assert hash_config({"a": 1}) != hash_config({"a": 2})


def test_current_git_head_reads_the_repository():
    head = current_git_head(ROOT)
    assert re.fullmatch(r"[0-9a-f]{40}", head)


def test_current_git_head_without_a_repository(tmp_path):
    with pytest.raises(RunError, match="no git"):
        current_git_head(tmp_path)


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_a02_does_not_write_pipeline_artifacts():
    """run 뼈대만 만든다 — 내용은 각 단계가 쓴다."""
    code = code_only(SRC)
    for forbidden in ("window_spans", "classify", "build_timeline", "RawStore"):
        assert forbidden not in code, "다른 티켓 책임을 침범했다: " + forbidden


def test_a02_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
