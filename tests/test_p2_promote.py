"""staging → P2 입력 승격. **검증한 바이트가 그대로 M1에 들어가는지**를 막는 층.

승격은 되돌리기 쉬운 작업처럼 보이지만, 여기서 다른 파일이 들어가면 그 뒤 20시간
GPU가 전부 무의미해진다. 그래서 세 값을 대조한다 — 선정 목록 · staging manifest ·
**실제 파일**.

막는 것 일곱.
1. 선정 목록에 없는 영상이 섞여 들어가는 것
2. staging manifest와 선정 목록의 sha256이 다른데 통과하는 것
3. 실제 파일 해시가 둘과 다른데 통과하는 것
4. 목적지에 **다른** 파일이 이미 있는데 덮어쓰는 것
5. 복사 후 목적지 해시를 확인하지 않는 것
6. staging 원본을 지우는 것 (P2 종료까지 보존)
7. 기확보 4편을 신규처럼 다시 넣는 것
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_promote as P                                            # noqa: E402
import provenance as PV                                           # noqa: E402


def _mk(tmp_path, body=b"video-bytes", name="AAA.mp4"):
    stage = tmp_path / "staging" / "videos"
    stage.mkdir(parents=True)
    f = stage / name
    f.write_bytes(body)
    return f, PV.sha256_file(f)


def _fixture(tmp_path, digest, name="AAA.mp4", sid="AAA"):
    sel = {"selected": [
        {"source_id": sid, "local_filename": name, "file_sha256": digest,
         "pre_indexed": False, "n_segments": 200},
        {"source_id": "old_vid", "local_filename": None, "file_sha256": None,
         "pre_indexed": True, "n_segments": 183}]}
    man = {"videos": [{"source_id": sid, "local_filename": name,
                       "file_sha256": digest}]}
    return sel, man


def test_happy_path_copies_and_reverifies(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    dest = tmp_path / "data" / "videos"
    (dest.parent).mkdir(parents=True)
    dest.mkdir()
    (dest / "old_vid.mp4").write_bytes(b"legacy")
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    assert r["ok"] is True
    assert r["copied"] == 1 and r["skipped"] == 0
    assert (dest / "AAA.mp4").read_bytes() == b"video-bytes"
    row = [x for x in r["rows"] if x["video_id"] == "AAA"][0]
    assert row["dest_sha256"] == h          # **복사 후 재계산값이다**
    assert row["status"] == "copied"
    assert f.exists(), "staging 원본을 지우면 안 된다"


def test_sha_disagreement_between_sources_is_fail_closed(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    man["videos"][0]["file_sha256"] = "d" * 64      # manifest만 다르다
    dest = tmp_path / "data" / "videos"
    dest.mkdir(parents=True)
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    assert r["ok"] is False
    assert any("manifest" in p for p in r["problems"])
    assert not (dest / "AAA.mp4").exists(), "불일치면 복사하지 않는다"


def test_actual_file_hash_mismatch_is_fail_closed(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    f.write_bytes(b"tampered")                      # 파일이 바뀌었다
    dest = tmp_path / "data" / "videos"
    dest.mkdir(parents=True)
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    assert r["ok"] is False
    assert any("staging 해시" in p or "실제" in p for p in r["problems"])
    assert not (dest / "AAA.mp4").exists()


def test_existing_identical_file_is_skipped_not_recopied(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    dest = tmp_path / "data" / "videos"
    dest.mkdir(parents=True)
    (dest / "AAA.mp4").write_bytes(b"video-bytes")
    (dest / "old_vid.mp4").write_bytes(b"legacy")
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    assert r["ok"] is True and r["skipped"] == 1 and r["copied"] == 0
    assert [x for x in r["rows"] if x["video_id"] == "AAA"][0]["status"] \
        == "already_present"


def test_existing_different_file_is_never_overwritten(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    dest = tmp_path / "data" / "videos"
    dest.mkdir(parents=True)
    (dest / "AAA.mp4").write_bytes(b"SOMETHING-ELSE")
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    assert r["ok"] is False
    assert (dest / "AAA.mp4").read_bytes() == b"SOMETHING-ELSE"
    assert any("덮어쓰지" in p for p in r["problems"])


def test_pre_indexed_videos_are_checked_not_copied(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    dest = tmp_path / "data" / "videos"
    dest.mkdir(parents=True)
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    old = [x for x in r["rows"] if x["video_id"] == "old_vid"][0]
    assert old["status"] == "pre_indexed_missing"
    assert r["ok"] is False, "기확보분이 입력 경로에 없으면 그대로 진행하면 안 된다"


def test_video_absent_from_manifest_is_fail_closed(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    man["videos"] = []
    dest = tmp_path / "data" / "videos"
    dest.mkdir(parents=True)
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    assert r["ok"] is False
    assert any("manifest에 없다" in p for p in r["problems"])


def test_missing_staging_file_is_reported(tmp_path):
    f, h = _mk(tmp_path)
    sel, man = _fixture(tmp_path, h)
    f.unlink()
    dest = tmp_path / "data" / "videos"
    dest.mkdir(parents=True)
    r = P.promote(sel["selected"], man, tmp_path / "staging", dest)
    assert r["ok"] is False
    assert any("staging에 파일이 없다" in p for p in r["problems"])


def test_report_records_counts_for_the_real_sample():
    """실제 선정 목록으로 형태만 확인한다 — 파일 복사는 하지 않는다."""
    sel = json.loads((ROOT / "docs" / "P2_선정표본_2026-08-20.json")
                     .read_text(encoding="utf-8"))["selected"]
    assert len(sel) == 35
    assert sum(1 for r in sel if not r.get("pre_indexed")) == 31
    assert all(r["local_filename"].endswith(".mp4")
               for r in sel if not r.get("pre_indexed"))
