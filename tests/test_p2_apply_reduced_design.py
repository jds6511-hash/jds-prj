"""활성 설계 적용 — **원본 315를 덮어써서 역사를 없애지 않는다.**

```
보존   원본 315행 CSV를 archive로 복사한다 (삭제·수정 없음)
파생   동결 keep-mask에서 175행 작업 CSV를 기계적으로 만든다
audit  drop된 140행은 지우지 않고 audit CSV로 남긴다. 작성분은 작성분으로 표시
불변   query_id 재번호 없음 · 새 질의 없음 · 사람 입력 칸 그대로 복사
```
"""
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_apply_reduced_design as AP                               # noqa: E402
import p2_label_intake as I                                        # noqa: E402


def _write(path, rows, cols=None):
    cols = cols or list(I.COLUMNS)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path


def _original(tmp_path, filled_ids=()):
    rows = []
    for r in I.load_allocation():
        row = {**r, "text": "", "gt_start": "", "gt_end": "", "note": ""}
        if r["query_id"] in filled_ids:
            row.update({"text": f"{r['query_id']} 질의", "gt_start": "10",
                        "gt_end": "20", "note": "메모"})
        rows.append(row)
    return _write(tmp_path / "p2_label_intake.csv", rows)


def _read(p):
    return list(csv.DictReader(Path(p).read_text(encoding="utf-8-sig")
                               .splitlines()))


def _first_video_ids():
    alloc = I.load_allocation()
    first = alloc[0]["video_id"]
    return [r["query_id"] for r in alloc if r["video_id"] == first]


# ------------------------------------------------------------- 정상 경로

def test_it_writes_the_reduced_working_file_and_keeps_the_original(tmp_path):
    src = _original(tmp_path, filled_ids=_first_video_ids())
    r = AP.apply(src, out_dir=tmp_path)
    assert Path(r["archive"]).is_file()
    assert len(_read(r["archive"])) == 315
    assert len(_read(r["working"])) == I.active_total() == 175
    assert len(_read(r["audit"])) == 315 - 175


def test_the_archive_is_a_byte_copy_of_the_original(tmp_path):
    src = _original(tmp_path, filled_ids=_first_video_ids())
    before = Path(src).read_bytes()
    r = AP.apply(src, out_dir=tmp_path)
    assert Path(r["archive"]).read_bytes() == before


def test_retained_human_labels_are_carried_over_verbatim(tmp_path):
    ids = _first_video_ids()
    src = _original(tmp_path, filled_ids=ids)
    r = AP.apply(src, out_dir=tmp_path)
    kept = {row["query_id"]: row for row in _read(r["working"])}
    carried = [q for q in ids if q in kept]
    assert carried, "첫 영상의 유지분이 있어야 한다"
    for q in carried:
        assert kept[q]["text"] == f"{q} 질의"
        assert kept[q]["gt_start"] == "10" and kept[q]["gt_end"] == "20"
        assert kept[q]["note"] == "메모"


def test_dropped_written_rows_are_archived_not_deleted(tmp_path):
    ids = _first_video_ids()
    src = _original(tmp_path, filled_ids=ids)
    r = AP.apply(src, out_dir=tmp_path)
    audit = {row["query_id"]: row for row in _read(r["audit"])}
    dropped_written = [q for q in ids if q in audit]
    assert dropped_written, "첫 영상의 drop분이 있어야 한다"
    for q in dropped_written:
        assert audit[q]["text"] == f"{q} 질의"
        assert audit[q]["status"] == AP.STATUS_WRITTEN
    assert r["dropped_written"] == len(dropped_written)


def test_blank_dropped_rows_are_marked_differently(tmp_path):
    src = _original(tmp_path, filled_ids=_first_video_ids())
    r = AP.apply(src, out_dir=tmp_path)
    audit = _read(r["audit"])
    kinds = {row["status"] for row in audit}
    assert kinds == {AP.STATUS_WRITTEN, AP.STATUS_BLANK}


def test_working_rows_are_exactly_the_frozen_mask(tmp_path):
    src = _original(tmp_path)
    r = AP.apply(src, out_dir=tmp_path)
    import p2_active_design as A
    assert [row["query_id"] for row in _read(r["working"])] == \
        A.kept_query_ids()


def test_query_ids_are_not_renumbered(tmp_path):
    src = _original(tmp_path)
    r = AP.apply(src, out_dir=tmp_path)
    # 적용 후 src는 축소본이다 — 원본 집합은 archive에서 읽는다
    orig = {row["query_id"] for row in _read(r["archive"])}
    working = {row["query_id"] for row in _read(r["working"])}
    dropped = {row["query_id"] for row in _read(r["audit"])}
    assert working <= orig and dropped <= orig
    assert working | dropped == orig and not (working & dropped)


def test_frozen_columns_are_untouched(tmp_path):
    src = _original(tmp_path)
    r = AP.apply(src, out_dir=tmp_path)
    by_id = {row["query_id"]: row for row in _read(src)}
    for row in _read(r["working"]):
        o = by_id[row["query_id"]]
        assert row["video_id"] == o["video_id"]
        assert row["query_type"] == o["query_type"]
    assert list(_read(r["working"])[0].keys()) == list(I.COLUMNS)


def test_it_is_deterministic(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = AP.apply(_original(tmp_path / "a"), out_dir=tmp_path / "a")
    b = AP.apply(_original(tmp_path / "b"), out_dir=tmp_path / "b")
    assert [r["query_id"] for r in _read(a["working"])] == \
           [r["query_id"] for r in _read(b["working"])]


# ------------------------------------------------------------- fail-closed

def test_it_refuses_to_overwrite_an_existing_archive(tmp_path):
    src = _original(tmp_path)
    AP.apply(src, out_dir=tmp_path)
    with pytest.raises(AP.ApplyError, match="archive"):
        AP.apply(src, out_dir=tmp_path)


def test_it_refuses_a_source_that_is_not_the_full_allocation(tmp_path):
    rows = _read(_original(tmp_path))[:-1]
    src = _write(tmp_path / "short.csv", rows)
    with pytest.raises(AP.ApplyError, match="315"):
        AP.apply(src, out_dir=tmp_path)


def test_it_refuses_a_source_with_an_unknown_query_id(tmp_path):
    rows = _read(_original(tmp_path))
    rows[0]["query_id"] = "p2_zz_q99"
    src = _write(tmp_path / "bad.csv", rows)
    with pytest.raises(AP.ApplyError, match="p2_zz_q99"):
        AP.apply(src, out_dir=tmp_path)


def test_it_refuses_a_source_with_a_changed_query_type(tmp_path):
    rows = _read(_original(tmp_path))
    rows[0]["query_type"] = "행동형"
    src = _write(tmp_path / "bad.csv", rows)
    with pytest.raises(AP.ApplyError, match="query_type"):
        AP.apply(src, out_dir=tmp_path)


def test_dry_run_writes_nothing(tmp_path):
    src = _original(tmp_path)
    r = AP.apply(src, out_dir=tmp_path, dry_run=True)
    assert r["dry_run"] is True
    assert not (tmp_path / AP.ARCHIVE_NAME).exists()
    assert not (tmp_path / AP.AUDIT_NAME).exists()
    assert len(_read(src)) == 315


# ------------------------------------------------------------- 경계

def test_it_reports_counts_without_showing_label_content(tmp_path):
    src = _original(tmp_path, filled_ids=_first_video_ids())
    r = AP.apply(src, out_dir=tmp_path)
    for value in r.values():
        assert "질의" not in str(value) or str(value).endswith(".csv")
