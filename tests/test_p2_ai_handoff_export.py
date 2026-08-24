"""AI 초안용 handoff — **정체성 필드와 원본 프레임 경로만 나간다.**

```
payload    query_id · video_id · query_type · 시트 파일명
적격       활성 행 · 전환 동결 완료분 아님 · 동결 유형 장면형 — 이 셋만으로 판정
금지       사람이 쓴 값 · 모델 identity · 검색 결과 · 순위/점수 · 파이프라인 자막
allowlist  스키마 밖 키가 나오면 거부 (blacklist만 쓰지 않는다)
```
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_ai_handoff_export as H                                   # noqa: E402

SCENE = H.SCENE
TYPES = ("복합형", "자막형", "장면형")


def _alloc(n_videos=3, per_type=2) -> list:
    rows = []
    for i in range(n_videos):
        vid = f"v{i:02d}"
        n = 0
        for t in TYPES:
            for _ in range(per_type):
                n += 1
                rows.append({"query_id": f"p2_{vid}_q{n:02d}", "video_id": vid,
                             "query_type": t})
    return rows


def _sheets(tmp_path, videos, pages=2) -> Path:
    d = Path(tmp_path) / "sheets"
    d.mkdir(parents=True, exist_ok=True)
    for v in videos:
        for p in range(1, pages + 1):
            (d / f"{v}_p{p:02d}.jpg").write_bytes(b"\xff\xd8jpg" + v.encode())
    return d


def _freeze(tmp_path, done_ids) -> Path:
    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    p = Path(tmp_path) / "freeze.json"
    p.write_text(json.dumps({"human_only": {"query_ids": list(done_ids)}}),
                 encoding="utf-8")
    return p


def _intake(tmp_path, allocation, filled_ids=()) -> Path:
    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    p = Path(tmp_path) / "intake.csv"
    cols = ("query_id", "video_id", "query_type", "text", "gt_start", "gt_end",
            "note")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cols))
        w.writeheader()
        for r in allocation:
            row = {**r, "text": "", "gt_start": "", "gt_end": "", "note": ""}
            if r["query_id"] in filled_ids:
                row.update({"text": "비밀 질의", "gt_start": "10",
                            "gt_end": "20", "note": "비밀 메모"})
            w.writerow(row)
    return p


def _env(tmp_path, done=(), filled=(), pages=2):
    alloc = _alloc()
    vids = sorted({r["video_id"] for r in alloc})
    return {"allocation": alloc, "freeze_path": _freeze(tmp_path, done),
            "intake": _intake(tmp_path, alloc, filled),
            "sheets_dir": _sheets(tmp_path, vids, pages)}


# ------------------------------------------------------------- 적격 판정

def test_only_scene_rows_are_eligible(tmp_path):
    e = _env(tmp_path)
    got = H.protocol_eligible(e["freeze_path"], e["allocation"])
    assert all(r["query_type"] == SCENE for r in got)
    assert len(got) == 6                                   # 3영상 x 장면형 2


def test_transition_completed_rows_are_excluded(tmp_path):
    e = _env(tmp_path, done=("p2_v00_q05",))
    got = H.protocol_eligible(e["freeze_path"], e["allocation"])
    assert "p2_v00_q05" not in [r["query_id"] for r in got]
    assert len(got) == 5


def test_eligibility_ignores_current_label_content(tmp_path):
    """지금 사람이 더 썼어도 protocol 적격 기준은 동결 시점이다."""
    a = _env(tmp_path, done=(), filled=("p2_v00_q05", "p2_v00_q06"))
    b = _env(tmp_path / "b", done=())
    assert [r["query_id"] for r in
            H.protocol_eligible(a["freeze_path"], a["allocation"])] == \
           [r["query_id"] for r in
            H.protocol_eligible(b["freeze_path"], b["allocation"])]


def test_already_written_scene_rows_are_not_sent(tmp_path):
    e = _env(tmp_path, filled=("p2_v00_q05",))
    p = H.build_payload(**e)
    assert p["protocol_eligible_scene_rows"] == 6
    assert p["currently_blank_scene_rows"] == 5
    assert p["already_written_scene_rows"] == 1
    assert "p2_v00_q05" not in [r["query_id"] for r in p["rows"]]


def test_a_missing_freeze_file_is_refused(tmp_path):
    with pytest.raises(H.HandoffError, match="전환 동결"):
        H.protocol_eligible(tmp_path / "nope.json", _alloc())


def test_a_row_missing_from_the_intake_is_refused(tmp_path):
    e = _env(tmp_path)
    with pytest.raises(H.HandoffError, match="작업 CSV에 없다"):
        H.currently_blank(["p2_zz_q99"], e["intake"])


# ------------------------------------------------------------- 산출물

def test_prepare_writes_the_minimal_package(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    r = H.prepare(out, **e)
    for name in (H.CSV_NAME, H.MANIFEST_NAME, H.PROMPT_NAME, H.README_NAME):
        assert (out / name).is_file()
    assert len(list((out / H.BY_VIDEO).glob("*.json"))) == 3
    assert r["row_count"] == 6 and r["video_count"] == 3
    assert r["prompt_sha256"] == H.EXPECTED_PROMPT_SHA256


def test_the_csv_has_exactly_three_columns(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    rows = list(csv.DictReader((out / H.CSV_NAME)
                              .read_text(encoding="utf-8-sig").splitlines()))
    assert list(rows[0]) == ["query_id", "video_id", "query_type"]
    assert all(r["query_type"] == SCENE for r in rows)


def test_the_csv_carries_no_human_value(tmp_path):
    e = _env(tmp_path, filled=("p2_v00_q05",))
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    body = (out / H.CSV_NAME).read_text(encoding="utf-8")
    assert "비밀 질의" not in body and "비밀 메모" not in body
    assert "gt_start" not in body


def test_by_video_objects_use_the_allowlist(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    for p in (out / H.BY_VIDEO).glob("*.json"):
        v = json.loads(p.read_text(encoding="utf-8"))
        assert set(v) == H.VIDEO_KEYS
        for q in v["queries"]:
            assert set(q) == H.QUERY_KEYS


def test_every_video_gets_all_of_its_sheets(tmp_path):
    e = _env(tmp_path, pages=3)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    m = json.loads((out / H.MANIFEST_NAME).read_text(encoding="utf-8"))
    for v in m["videos"]:
        assert len(v["contact_sheets"]) == 3
        assert v["contact_sheets"][0].endswith("_p01.jpg")


def test_the_prompt_is_copied_verbatim(tmp_path):
    import p2_ai_draft as AID
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    got = (out / H.PROMPT_NAME).read_text(encoding="utf-8")
    assert got == AID.PROMPT_TEMPLATE
    assert hashlib.sha256(got.encode("utf-8")).hexdigest() == \
        H.EXPECTED_PROMPT_SHA256


def test_the_readme_says_what_not_to_upload(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    txt = (out / H.README_NAME).read_text(encoding="utf-8")
    assert "초안" in txt and "정답이 아니다" in txt
    assert "프롬프트 수정" in txt


def test_output_is_deterministic_under_row_reordering(tmp_path):
    e = _env(tmp_path)
    a = H.build_payload(**e)
    e2 = dict(e, allocation=list(reversed(e["allocation"])))
    b = H.build_payload(**e2)
    assert sorted(r["query_id"] for r in a["rows"]) == \
           sorted(r["query_id"] for r in b["rows"])
    assert {v["video_id"] for v in a["videos"]} == \
           {v["video_id"] for v in b["videos"]}


def test_a_video_without_sheets_is_refused(tmp_path):
    e = _env(tmp_path)
    for p in Path(e["sheets_dir"]).glob("v01_*.jpg"):
        p.unlink()
    with pytest.raises(H.HandoffError, match="컨택트시트가 없다"):
        H.build_payload(**e)


def test_prepare_does_not_touch_the_source_sheets(tmp_path):
    e = _env(tmp_path)
    before = {p.name: p.read_bytes() for p in Path(e["sheets_dir"]).iterdir()}
    H.prepare(tmp_path / "handoff", **e)
    after = {p.name: p.read_bytes() for p in Path(e["sheets_dir"]).iterdir()}
    assert before == after


def test_prepare_does_not_touch_the_working_intake(tmp_path):
    e = _env(tmp_path, filled=("p2_v00_q05",))
    before = Path(e["intake"]).read_bytes()
    H.prepare(tmp_path / "handoff", **e)
    assert Path(e["intake"]).read_bytes() == before


# ------------------------------------------------------------- verify

def test_verify_passes_on_a_fresh_package(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is True, r["problems"]
    assert r["prompt_sha256"]["match"] is True
    assert r["n_rows"] == 6 and r["n_videos"] == 3


def test_verify_refuses_a_tampered_prompt(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    (out / H.PROMPT_NAME).write_text("더 좋아 보이는 프롬프트", encoding="utf-8")
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False and r["checks"]["prompt_sha256_matches"] is False


def test_verify_refuses_an_extra_csv_column(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    rows = list(csv.DictReader((out / H.CSV_NAME)
                              .read_text(encoding="utf-8-sig").splitlines()))
    with open(out / H.CSV_NAME, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(H.CSV_COLUMNS) + ["gt_start"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "gt_start": "10"})
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False
    assert r["checks"]["csv_columns_allowlisted"] is False


def test_verify_refuses_an_extra_json_key(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    m = json.loads((out / H.MANIFEST_NAME).read_text(encoding="utf-8"))
    m["videos"][0]["queries"][0]["caption_model"] = "some/model"
    (out / H.MANIFEST_NAME).write_text(json.dumps(m, ensure_ascii=False),
                                       encoding="utf-8")
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False and r["checks"]["json_keys_allowlisted"] is False


def test_verify_refuses_a_forbidden_token_in_the_payload(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    m = json.loads((out / H.MANIFEST_NAME).read_text(encoding="utf-8"))
    m["videos"][0]["contact_sheets"].append("v00_rank_score.jpg")
    (out / H.MANIFEST_NAME).write_text(json.dumps(m, ensure_ascii=False),
                                       encoding="utf-8")
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False


def test_verify_refuses_a_row_outside_the_active_design(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    rows = list(csv.DictReader((out / H.CSV_NAME)
                              .read_text(encoding="utf-8-sig").splitlines()))
    rows[0]["query_id"] = "p2_zz_q99"
    with open(out / H.CSV_NAME, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(H.CSV_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False and r["checks"]["subset_of_active_design"] is False


def test_verify_refuses_a_duplicate_query(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    rows = list(csv.DictReader((out / H.CSV_NAME)
                              .read_text(encoding="utf-8-sig").splitlines()))
    rows[1] = dict(rows[0])
    with open(out / H.CSV_NAME, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(H.CSV_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False and r["checks"]["query_ids_unique"] is False


def test_verify_refuses_a_missing_sheet(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    next(Path(e["sheets_dir"]).glob("v00_p02.jpg")).unlink()
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False


def test_verify_refuses_a_page_count_mismatch(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    m = json.loads((out / H.MANIFEST_NAME).read_text(encoding="utf-8"))
    m["videos"][0]["contact_sheets"] = m["videos"][0]["contact_sheets"][:1]
    (out / H.MANIFEST_NAME).write_text(json.dumps(m, ensure_ascii=False),
                                       encoding="utf-8")
    r = H.verify(out, allocation=e["allocation"], freeze_path=e["freeze_path"],
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False and r["checks"]["page_counts_match_source"] is False


def test_verify_refuses_a_transition_completed_row(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    rows = list(csv.DictReader((out / H.CSV_NAME)
                              .read_text(encoding="utf-8-sig").splitlines()))
    later = _freeze(tmp_path / "later", [rows[0]["query_id"]])
    r = H.verify(out, allocation=e["allocation"], freeze_path=later,
                 sheets_dir=e["sheets_dir"])
    assert r["ok"] is False
    assert r["checks"]["transition_completed_excluded"] is False


def test_verify_needs_the_package_to_exist(tmp_path):
    with pytest.raises(H.HandoffError, match="prepare"):
        H.verify(tmp_path / "nothing")


def test_export_sheets_copies_without_touching_the_source(tmp_path):
    e = _env(tmp_path)
    out = tmp_path / "handoff"
    H.prepare(out, **e)
    before = {p.name: p.read_bytes() for p in Path(e["sheets_dir"]).iterdir()}
    got = H.export_sheets(out, sheets_dir=e["sheets_dir"])
    assert got["copied"] == 6
    after = {p.name: p.read_bytes() for p in Path(e["sheets_dir"]).iterdir()}
    assert before == after
