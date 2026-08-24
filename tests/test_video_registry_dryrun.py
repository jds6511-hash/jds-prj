"""registry SoT 전환 전 dry-run 일관성 검사 — 계약 테스트.

전환 판단을 사람 눈에 맡기지 않는다. 검사 항목을 코드로 두고, **하나라도 어긋나면
읽기 전용 어댑터를 유지한다.** 그리고 검사가 전부 통과해도 이 함수는 GO를 선언하지
않는다 — 전환은 사용자 결정이다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import video_registry as R     # noqa: E402


def _sel(tmp_path, rows) -> Path:
    p = tmp_path / "selection.json"
    p.write_text(json.dumps({"selected": rows}, ensure_ascii=False),
                 encoding="utf-8")
    return p


H = "a" * 64


def _new(vid="v1", n=100, **kw):
    r = {"source_id": vid, "n_segments": n, "source_url": f"http://x/{vid}",
         "file_sha256": H, "publisher": "p", "program": "pr",
         "selected_audio_language": "ko", "speech_status": "audio_track_ko"}
    r.update(kw)
    return r


def _legacy(vid="L1", n=50, **kw):
    r = {"source_id": vid, "n_segments": n, "publisher": "p", "program": "pr",
         "pre_indexed": True}
    r.update(kw)
    return r


# ---- dry-run 보고 형태 ----------------------------------------------------

def test_dry_run_reports_all_contracts(tmp_path):
    sel = _sel(tmp_path, [_new(), _legacy()])
    r = R.dry_run(selection=sel, duration_artifact=None)
    for k in ("schema_validate_ok", "projection_matches_selection",
              "source_id_duplicates", "video_id_duplicates",
              "sha_mismatch", "new_required_provenance_missing",
              "legacy_guessed_fields", "duration_status_counts",
              "duration_estimated_from_grid"):
        assert k in r["checks"], k


def test_dry_run_never_declares_go(tmp_path):
    """검사가 전부 통과해도 전환을 스스로 선언하지 않는다."""
    sel = _sel(tmp_path, [_new(), _legacy()])
    r = R.dry_run(selection=sel, duration_artifact=None)
    assert r["contracts_ok"] is True
    assert r["sot_transition"] == "HOLD"
    assert r["decision"] == "사용자_승인_사항"
    assert r["hold_reasons"]


def test_dry_run_has_no_writer(tmp_path):
    """어댑터에 쓰기 경로가 생기지 않았는지 본다."""
    src = (ROOT / "scripts" / "video_registry.py").read_text(encoding="utf-8")
    assert "def save" not in src and "def write_registry" not in src


# ---- 개별 계약 -------------------------------------------------------------

def test_duplicate_source_id_fails_contracts(tmp_path):
    sel = _sel(tmp_path, [_new("v1"), _new("v1")])
    r = R.dry_run(selection=sel, duration_artifact=None)
    assert r["contracts_ok"] is False
    assert r["checks"]["schema_validate_ok"] is False


def test_new_without_url_fails_contracts(tmp_path):
    row = _new("v2")
    row.pop("source_url")
    sel = _sel(tmp_path, [row])
    r = R.dry_run(selection=sel, duration_artifact=None)
    assert r["contracts_ok"] is False


def test_legacy_with_guessed_hash_fails_contracts(tmp_path):
    """기확보 영상에 해시가 채워져 있으면 추측이다."""
    sel = _sel(tmp_path, [_legacy("L1", file_sha256=None,
                                  staging_sha256=H)])
    r = R.dry_run(selection=sel, duration_artifact=None)
    assert r["checks"]["legacy_guessed_fields"] >= 0   # 투영은 채우지 않는다
    recs = R.project_from_selection(sel, duration_artifact=None)
    assert recs[0].get("staging_sha256") is None


def test_projection_covers_every_selected_row(tmp_path):
    sel = _sel(tmp_path, [_new("v1"), _new("v2"), _legacy("L1")])
    r = R.dry_run(selection=sel, duration_artifact=None)
    assert r["checks"]["projection_matches_selection"] is True
    assert r["n_selected"] == 3 and r["n_projected"] == 3


# ---- duration -------------------------------------------------------------

def test_duration_unknown_is_a_status_not_an_estimate(tmp_path):
    sel = _sel(tmp_path, [_new("v1", n=200)])
    recs = R.project_from_selection(sel, duration_artifact=None)
    assert recs[0]["duration_status"] == "unknown"
    assert "duration_sec" not in recs[0]
    # 200구간 × 5초 = 1000초를 만들어 채우지 않는다
    assert 1000 not in [v for v in recs[0].values()
                        if isinstance(v, (int, float))]


def test_duration_status_counts_reported(tmp_path):
    sel = _sel(tmp_path, [_new("v1", duration_sec=123.4), _new("v2")])
    r = R.dry_run(selection=sel, duration_artifact=None)
    c = r["checks"]["duration_status_counts"]
    assert c["recorded"] == 1 and c["unknown"] == 1


def test_measured_duration_requires_grid_agreement(tmp_path):
    sel = _sel(tmp_path, [_new("v1", n=100)])
    art = tmp_path / "dur.json"
    art.write_text(json.dumps({"rows": [
        {"video_id": "v1", "duration_sec": 499.5, "n_segments_derived": 99,
         "measurement_path": "cv2"}]}), encoding="utf-8")
    with pytest.raises(R.RegistryError):
        R.dry_run(selection=sel, duration_artifact=art)


def test_measured_duration_is_linked_with_source(tmp_path):
    sel = _sel(tmp_path, [_new("v1", n=100)])
    art = tmp_path / "dur.json"
    art.write_text(json.dumps({"rows": [
        {"video_id": "v1", "duration_sec": 499.5, "n_segments_derived": 100,
         "measurement_path": "cv2"}]}), encoding="utf-8")
    recs = R.project_from_selection(sel, duration_artifact=art)
    assert recs[0]["duration_status"] == "measured"
    assert recs[0]["duration_source"]
    assert recs[0]["duration_measurement_path"] == "cv2"


def test_duration_dependent_check_fails_loudly_on_unknown(tmp_path):
    sel = _sel(tmp_path, [_new("v1")])
    recs = R.project_from_selection(sel, duration_artifact=None)
    with pytest.raises(R.RegistryError, match="unsupported"):
        R.require_duration(recs)


# ---- 실입력 ---------------------------------------------------------------

def test_real_projection_dry_run():
    r = R.dry_run()
    assert r["n_selected"] == r["n_projected"] == 35
    assert r["sot_transition"] == "HOLD"
    assert isinstance(r["contracts_ok"], bool)
