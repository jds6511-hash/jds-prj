"""영상 provenance registry — **schema·검증·읽기 어댑터까지만.**

지금 돌고 있는 P2 FULL의 provenance 구조를 교체하지 않는다. 여기서 고정하는 것은
canonical schema와 fail-closed 규칙, 그리고 **기존 manifest와 어긋나지 않는가**다.

writer/source-of-truth 전환은 FULL 종료 후 별도 판단이다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import video_registry as R                                       # noqa: E402

SRC = (ROOT / "scripts" / "video_registry.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)

NEW = {"video_id": "abc", "source_id": "abc", "acquisition_class": "downloaded",
       "source_url": "https://example.invalid/watch?v=abc",
       "publisher": "ebs", "program": "ebs_docuprime",
       "acquisition_tool": "yt-dlp 2026.08.19",
       "staging_sha256": "a" * 64, "production_sha256": "a" * 64,
       "codec": "h264", "resolution": "1920x1080", "duration_sec": 1802.27,
       "n_segments": 361, "audio_language": "ko",
       "provenance_reference": "docs/P2_선정표본_2026-08-20.json"}
LEGACY = {"video_id": "old", "source_id": "old",
          "acquisition_class": "pre_existing", "legacy_exempt": True,
          "legacy_exempt_reason": "취득 시점에 출처 ID·해시를 기록하지 않았다",
          "codec": "h264", "resolution": "1920x1080", "n_segments": 183,
          "provenance_reference": "docs/P2_선정표본_2026-08-20.json"}


# ------------------------------------------------------- 판정에 쓰지 않는다

@pytest.mark.parametrize("token", ["mrr", "recall", "precision", "adoption",
                                   "eligible", "caption"])
def test_registry_does_not_decide_metrics_or_eligibility(token):
    assert token not in CODE


# ------------------------------------------------------- 신규 fail-closed

@pytest.mark.parametrize("field", ["source_id", "source_url",
                                   "production_sha256"])
def test_new_video_missing_identity_fails_closed(field):
    rec = {k: v for k, v in NEW.items() if k != field}
    with pytest.raises(R.RegistryError, match=field):
        R.validate([rec])


def test_valid_records_pass():
    assert R.validate([NEW, LEGACY])["ok"] is True


def test_duplicate_source_id_fails_closed():
    with pytest.raises(R.RegistryError, match="중복"):
        R.validate([NEW, {**NEW, "video_id": "abc2"}])


def test_duplicate_video_id_fails_closed():
    with pytest.raises(R.RegistryError, match="중복"):
        R.validate([NEW, {**NEW, "source_id": "abc2"}])


def test_hash_shape_is_checked():
    with pytest.raises(R.RegistryError, match="sha256"):
        R.validate([{**NEW, "production_sha256": "short"}])


def test_staging_and_production_hash_mismatch_is_flagged_not_silent():
    """복사로 승격했으니 같아야 한다. 다르면 사유가 있어야 통과한다."""
    with pytest.raises(R.RegistryError, match="해시가 다르다"):
        R.validate([{**NEW, "production_sha256": "b" * 64}])
    ok = R.validate([{**NEW, "production_sha256": "b" * 64,
                      "production_differs_reason": "AV1 → H.264 변환"}])
    assert ok["ok"] is True


# ------------------------------------------------------- legacy 규칙

def test_legacy_exempt_needs_an_explicit_reason():
    rec = {k: v for k, v in LEGACY.items() if k != "legacy_exempt_reason"}
    with pytest.raises(R.RegistryError, match="사유"):
        R.validate([rec])


def test_legacy_unknown_fields_must_stay_absent_not_guessed():
    with pytest.raises(R.RegistryError, match="추측"):
        R.validate([{**LEGACY, "source_url": "https://example.invalid/guess"}])


def test_legacy_exempt_cannot_be_claimed_by_a_new_acquisition():
    with pytest.raises(R.RegistryError, match="pre_existing"):
        R.validate([{**NEW, "legacy_exempt": True,
                     "legacy_exempt_reason": "편의"}])


# ------------------------------------------------------- 읽기 어댑터

def test_reader_is_read_only(tmp_path):
    p = tmp_path / "videos.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                           for r in (NEW, LEGACY)) + "\n", encoding="utf-8")
    before = p.read_bytes()
    recs = R.load(p)
    assert {r["video_id"] for r in recs} == {"abc", "old"}
    assert p.read_bytes() == before
    assert not hasattr(R, "write") and not hasattr(R, "save")


def test_identity_fields_are_declared_immutable():
    assert R.IDENTITY_FIELDS == ("video_id", "source_id", "source_url",
                                 "staging_sha256", "production_sha256")


def test_downstream_edit_of_identity_is_refused():
    before = dict(NEW)
    after = {**NEW, "source_url": "https://example.invalid/other"}
    with pytest.raises(R.RegistryError, match="identity"):
        R.assert_identity_unchanged([before], [after])
    assert R.assert_identity_unchanged([before], [dict(NEW)]) is True


def test_identity_check_refuses_a_dropped_record():
    with pytest.raises(R.RegistryError, match="사라졌다"):
        R.assert_identity_unchanged([NEW, LEGACY], [NEW])


# ------------------------------------------------------- 기존 manifest 대조

def test_projection_from_the_existing_selection_manifest_is_consistent():
    """기존 선정표본을 registry 스키마로 투영해도 검증을 통과해야 한다."""
    recs = R.project_from_selection()
    assert len(recs) == 35
    assert R.validate(recs)["ok"] is True
    legacy = [r for r in recs if r.get("legacy_exempt")]
    assert len(legacy) == 4
    assert all("legacy_exempt_reason" in r for r in legacy)


def test_projection_does_not_invent_missing_values():
    recs = {r["source_id"]: r for r in R.project_from_selection()}
    for vid in ("baekmansonghee_jirisan", "jissi_farm", "pland_costco_hosting",
                "softyeon_ceramics"):
        assert "source_url" not in recs[vid]
        assert "production_sha256" not in recs[vid]
