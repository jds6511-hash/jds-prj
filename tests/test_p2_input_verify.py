"""FULL 직전 입력 검증. **잘린 파일이 통과하지 못하는지**를 막는 층.

cv2는 부분 다운로드된 mp4를 열고 duration까지 돌려준다(2026-08-20 staging 실측).
그래서 "열린다"가 아니라 **해시**로 판정한다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_input_verify as V                                       # noqa: E402
import provenance as PV                                           # noqa: E402


def _mk(d, vid, body=b"bytes"):
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{vid}.mp4"
    f.write_bytes(body)
    return PV.sha256_file(f)


def test_match_and_legacy_are_counted_separately(tmp_path):
    h = _mk(tmp_path, "NEW")
    _mk(tmp_path, "OLD", b"legacy-bytes")
    sel = [{"source_id": "NEW", "file_sha256": h, "pre_indexed": False},
           {"source_id": "OLD", "file_sha256": None, "pre_indexed": True}]
    r = V.verify(sel, tmp_path)
    assert r["ok"] is True
    assert r["matched"] == 1 and r["legacy_recorded"] == 1
    old = [x for x in r["rows"] if x["video_id"] == "OLD"][0]
    assert old["sha256"] and old["status"] == "legacy_recorded"


def test_truncated_file_is_caught(tmp_path):
    h = _mk(tmp_path, "NEW", b"full-bytes")
    (tmp_path / "NEW.mp4").write_bytes(b"trunc")        # 전송 중 잘렸다
    sel = [{"source_id": "NEW", "file_sha256": h, "pre_indexed": False}]
    r = V.verify(sel, tmp_path)
    assert r["ok"] is False and r["mismatched"] == 1
    assert any("검증한 바이트가 아니다" in p for p in r["problems"])


def test_missing_file_is_caught(tmp_path):
    sel = [{"source_id": "GONE", "file_sha256": "a" * 64, "pre_indexed": False}]
    r = V.verify(sel, tmp_path)
    assert r["ok"] is False and r["missing"] == 1


def test_real_selected_list_shape():
    sel = json.loads((ROOT / "docs" / "P2_선정표본_2026-08-20.json")
                     .read_text(encoding="utf-8"))["selected"]
    assert len(sel) == 35
    assert sum(1 for r in sel if r.get("pre_indexed")) == 4
