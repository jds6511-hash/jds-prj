"""GT 작성 **전** 상태 동결 — 나중에 "그때 무엇을 보고 썼나"를 답할 수 있게.

라벨 작성 중에 시트가 바뀌거나 배정이 바뀌면 GT의 의미가 조용히 달라진다. 그래서
작성 전에 입력물의 해시를 찍어 둔다. 여기서 고정하는 것은 **무엇을 해시하는가**와
**빈 CSV가 정말 빈 상태인가**다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p2_gt_freeze as F                                         # noqa: E402


def _sheets(tmp_path, n=3):
    d = tmp_path / "sheets"
    d.mkdir()
    for i in range(n):
        (d / f"vid_p{i:02d}.jpg").write_bytes(b"jpeg" + bytes([i]))
    return d


def _csv(tmp_path, filled=False):
    p = tmp_path / "intake.csv"
    head = "query_id,video_id,query_type,text,gt_start,gt_end,note\n"
    row = "p2_v_q01,v,복합형," + ("질의,10,20," if filled else ",,,") + "\n"
    p.write_text(head + row, encoding="utf-8")
    return p


def test_freeze_records_hashes_of_every_input(tmp_path):
    r = F.freeze(csv_path=_csv(tmp_path), sheets_dir=_sheets(tmp_path))
    for k in ("intake_csv", "quota", "selection", "contact_sheets"):
        assert k in r["inputs"], k
    assert len(r["inputs"]["intake_csv"]["sha256"]) == 64
    assert r["inputs"]["contact_sheets"]["n_sheets"] == 3
    assert len(r["inputs"]["contact_sheets"]["manifest_sha256"]) == 64


def test_sheet_manifest_lists_per_file_hashes(tmp_path):
    r = F.freeze(csv_path=_csv(tmp_path), sheets_dir=_sheets(tmp_path))
    files = r["inputs"]["contact_sheets"]["files"]
    assert len(files) == 3
    assert all(len(v) == 64 for v in files.values())


def test_manifest_hash_changes_when_a_sheet_changes(tmp_path):
    d = _sheets(tmp_path)
    a = F.freeze(csv_path=_csv(tmp_path), sheets_dir=d)
    (d / "vid_p00.jpg").write_bytes(b"different")
    b = F.freeze(csv_path=_csv(tmp_path), sheets_dir=d)
    m = "manifest_sha256"
    assert a["inputs"]["contact_sheets"][m] != b["inputs"]["contact_sheets"][m]


def test_a_filled_csv_is_refused(tmp_path):
    """동결은 **작성 전** 상태를 찍는 것이다 — 이미 쓴 뒤면 기준이 못 된다."""
    with pytest.raises(F.FreezeError, match="이미 채워져"):
        F.freeze(csv_path=_csv(tmp_path, filled=True),
                 sheets_dir=_sheets(tmp_path))


def test_missing_sheets_dir_fails_closed(tmp_path):
    with pytest.raises(F.FreezeError, match="시트"):
        F.freeze(csv_path=_csv(tmp_path), sheets_dir=tmp_path / "none")


def test_provenance_of_the_sheet_source_is_recorded(tmp_path):
    r = F.freeze(csv_path=_csv(tmp_path), sheets_dir=_sheets(tmp_path))
    src = r["contact_sheet_source"]
    assert src["arm"] == "3b" and "config_p2_3b" in src["config"]
    assert "m2" in src["frames_note"]
    assert len(r["commit"]) == 40


def test_declares_what_is_not_frozen(tmp_path):
    """캡션·색인은 여기서 다루지 않는다 — 그 사실을 산출물에 적는다."""
    r = F.freeze(csv_path=_csv(tmp_path), sheets_dir=_sheets(tmp_path))
    assert "caption" in r["not_frozen_here"]


def test_real_inputs_freeze_and_match_the_expected_scale():
    if not F.CSV_PATH.is_file() or not F.SHEETS.is_dir():
        pytest.skip("실제 입력이 없다")
    r = F.freeze()
    assert r["inputs"]["contact_sheets"]["n_sheets"] == 172
    assert r["inputs"]["contact_sheets"]["n_videos"] == 35
    assert json.loads(F.QUOTA.read_text(encoding="utf-8"))["total_queries"] == 315
