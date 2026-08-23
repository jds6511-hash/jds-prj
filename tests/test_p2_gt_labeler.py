"""P2 GT 라벨러 — **손동작만 줄인다. GT 기준은 그대로다.**

여기서 고정하는 것 셋.

```
1  동결 필드 불변      query_id · video_id · query_type은 UI가 못 바꾼다
2  구조적 블라인드      캡션·자막·모델·arm·점수·순위·색인 경로를 **읽지 않는다**
                     (숨기는 게 아니라 접근 코드가 없다)
3  자동 확정 없음       타일 클릭은 seek 도움일 뿐 GT 경계를 정하지 않는다.
                     staging JSONL 자동 생성 없음. 평가 실행 경로 없음
```
"""
import ast
import csv
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_gt_labeler as L                                        # noqa: E402

SRC = (ROOT / "scripts" / "p2_gt_labeler.py").read_text(encoding="utf-8")
COLUMNS = ("query_id", "video_id", "query_type", "text", "gt_start", "gt_end",
           "note")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)
# HTML/JS는 코드 문자열 안에 있으므로 토큰 검사에서 빠지지 않게 원본도 함께 본다
UI_TEXT = SRC


def _csv(tmp_path, n=6, filled=0):
    p = tmp_path / "intake.csv"
    rows = []
    for i in range(n):
        vid = "v0" if i < n // 2 else "v1"
        r = {"query_id": f"p2_{vid}_q{i % 3 + 1:02d}", "video_id": vid,
             "query_type": ["복합형", "자막형", "장면형"][i % 3],
             "text": "", "gt_start": "", "gt_end": "", "note": ""}
        if i < filled:
            r.update({"text": f"질의 {i}", "gt_start": "10", "gt_end": "20"})
        rows.append(r)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        w.writerows(rows)
    return p


# --------------------------------------------------- 구조적 블라인드

@pytest.mark.parametrize("token", ["caption", "subtitle", "stt", "arm",
                                   "3b", "4b", "score", "rank", "mrr",
                                   "emb_", "work_p2", "segments.json",
                                   "eval", "staging"])
def test_forbidden_artifacts_are_not_reachable(token):
    assert token.lower() not in UI_TEXT.lower()


@pytest.mark.parametrize("mod", ["m5_search", "m6_evaluate", "frame_human_kit",
                                 "p2_evaluate"])
def test_forbidden_modules_are_not_imported(mod):
    assert mod not in CODE


def test_it_reads_only_the_declared_sources():
    """읽는 곳은 CSV · 선정표본 · 시트 · 원본 영상뿐이다."""
    assert set(L.READS) == {"intake_csv", "selection_manifest",
                            "contact_sheets", "source_video"}
    for p in (L.CSV_PATH, L.SHEETS, L.VIDEOS):
        assert "work_p2" not in str(p)


def test_runtime_needs_no_forbidden_file(tmp_path):
    """fixture에 캡션·색인이 아예 없어도 동작한다 — 필요하지 않다는 증거다."""
    app = L.App(csv_path=_csv(tmp_path), sheets=tmp_path / "sheets",
                videos=tmp_path / "videos", bounds={"v0": 100.0, "v1": 100.0})
    assert len(app.rows) == 6
    assert app.progress()["done"] == 0


# --------------------------------------------------- 동결 필드 불변

@pytest.mark.parametrize("field", ["query_id", "video_id", "query_type"])
def test_frozen_identity_cannot_be_edited(tmp_path, field):
    app = L.App(csv_path=_csv(tmp_path), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 100.0, "v1": 100.0})
    qid = app.rows[0]["query_id"]
    with pytest.raises(L.LabelerError, match=field):
        app.save({"query_id": qid, field: "바꿔치기", "text": "x",
                  "gt_start": 1, "gt_end": 2})


def test_unknown_query_id_is_refused(tmp_path):
    app = L.App(csv_path=_csv(tmp_path), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 100.0, "v1": 100.0})
    with pytest.raises(L.LabelerError, match="배정에 없다"):
        app.save({"query_id": "p2_x_q99", "text": "x", "gt_start": 1,
                  "gt_end": 2})


def test_only_the_human_columns_are_written(tmp_path):
    p = _csv(tmp_path)
    app = L.App(csv_path=p, sheets=tmp_path / "s", videos=tmp_path / "v",
                bounds={"v0": 100.0, "v1": 100.0})
    before = [dict(r) for r in app.rows]
    app.save({"query_id": before[2]["query_id"], "text": "질의",
              "gt_start": 12.5, "gt_end": 18.0, "note": "메모"})
    after = list(csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines()))
    assert [r["query_id"] for r in after] == [r["query_id"] for r in before]
    assert [r["query_type"] for r in after] == [r["query_type"] for r in before]
    assert after[2]["text"] == "질의" and after[2]["note"] == "메모"
    assert after[2]["gt_start"] == "12.5" and after[2]["gt_end"] == "18"
    assert list(csv.DictReader(io.StringIO(
        p.read_text(encoding="utf-8-sig"))).fieldnames) == list(COLUMNS)


# --------------------------------------------------- 입력 검증

def test_reversed_span_is_refused(tmp_path):
    app = L.App(csv_path=_csv(tmp_path), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 100.0, "v1": 100.0})
    with pytest.raises(L.LabelerError, match="gt_start < gt_end"):
        app.save({"query_id": app.rows[0]["query_id"], "text": "x",
                  "gt_start": 20, "gt_end": 20})


def test_span_past_the_video_is_refused(tmp_path):
    app = L.App(csv_path=_csv(tmp_path), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 30.0, "v1": 100.0})
    with pytest.raises(L.LabelerError, match="영상 길이"):
        app.save({"query_id": app.rows[0]["query_id"], "text": "x",
                  "gt_start": 10, "gt_end": 40})


def test_empty_text_is_refused_on_save(tmp_path):
    app = L.App(csv_path=_csv(tmp_path), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 100.0, "v1": 100.0})
    with pytest.raises(L.LabelerError, match="text"):
        app.save({"query_id": app.rows[0]["query_id"], "text": "  ",
                  "gt_start": 1, "gt_end": 2})


def test_draft_keeps_partial_work_without_pretending_it_is_done(tmp_path):
    """작성 중 이탈해도 잃지 않는다 — 단 완료로 세지 않는다."""
    p = _csv(tmp_path)
    app = L.App(csv_path=p, sheets=tmp_path / "s", videos=tmp_path / "v",
                bounds={"v0": 100.0, "v1": 100.0})
    app.draft({"query_id": app.rows[0]["query_id"], "text": "쓰다 만 질의",
               "gt_start": 5})
    reopened = L.App(csv_path=p, sheets=tmp_path / "s", videos=tmp_path / "v",
                     bounds={"v0": 100.0, "v1": 100.0})
    assert reopened.rows[0]["text"] == "쓰다 만 질의"
    assert reopened.rows[0]["gt_start"] == "5"
    assert reopened.progress()["done"] == 0


# --------------------------------------------------- 진행·이어하기

def test_progress_counts_only_complete_rows(tmp_path):
    app = L.App(csv_path=_csv(tmp_path, filled=2), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 100.0, "v1": 100.0})
    pr = app.progress()
    assert pr["done"] == 2 and pr["total"] == 6
    assert pr["by_video"]["v0"] == 2


def test_resume_returns_the_first_incomplete_row(tmp_path):
    app = L.App(csv_path=_csv(tmp_path, filled=2), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 100.0, "v1": 100.0})
    assert app.resume_index() == 2


def test_resume_is_zero_when_nothing_is_written(tmp_path):
    app = L.App(csv_path=_csv(tmp_path), sheets=tmp_path / "s",
                videos=tmp_path / "v", bounds={"v0": 100.0, "v1": 100.0})
    assert app.resume_index() == 0


def test_frozen_row_order_is_preserved(tmp_path):
    p = _csv(tmp_path)
    order = [r["query_id"] for r in csv.DictReader(
        p.read_text(encoding="utf-8-sig").splitlines())]
    app = L.App(csv_path=p, sheets=tmp_path / "s", videos=tmp_path / "v",
                bounds={"v0": 100.0, "v1": 100.0})
    app.save({"query_id": order[-1], "text": "x", "gt_start": 1, "gt_end": 2})
    after = [r["query_id"] for r in csv.DictReader(
        p.read_text(encoding="utf-8-sig").splitlines())]
    assert after == order


# --------------------------------------------------- 타일 → seek

def test_tile_click_maps_to_a_segment_start_only():
    """타일 클릭은 seek 도움이다 — 반환값에 gt_start·gt_end가 없다."""
    r = L.tile_at(page=3, x_frac=0.0, y_frac=0.0, n_segments=200)
    assert r == {"seg_idx": 120, "seek_sec": 600.0}
    assert "gt_start" not in r and "gt_end" not in r


def test_tile_click_uses_the_grid_of_the_sheet_generator():
    # 두 번째 열·두 번째 행 → 첫 페이지의 7 + 1 = idx 7
    r = L.tile_at(page=1, x_frac=0.30, y_frac=0.15, n_segments=60)
    assert r["seg_idx"] == 7 and r["seek_sec"] == 35.0


def test_tile_click_outside_the_last_page_is_refused():
    with pytest.raises(L.LabelerError, match="세그먼트"):
        L.tile_at(page=4, x_frac=0.9, y_frac=0.9, n_segments=185)


def test_grid_constants_match_the_sheet_generator():
    """타일 → 시각 매핑은 시트 생성기·config와 같은 격자를 써야 맞다."""
    import common
    import label_contact_sheet as LCS
    assert (L.COLS, L.PER_SHEET) == (LCS.COLS, LCS.PER_SHEET)
    assert L.SEG_LEN == common.load_config(ROOT / "config.yaml")["seg_len_sec"]


def test_sheet_pages_come_from_the_frozen_segment_count():
    assert L.n_pages(152) == 3 and L.n_pages(395) == 7
    assert L.n_pages(60) == 1


# --------------------------------------------------- 자동화 금지

def test_no_build_or_evaluation_entry_point():
    for token in ("p2_label_intake.build", "subprocess", "jsonl"):
        assert token not in CODE


def test_no_text_generation_helper():
    for token in ("suggest", "autocomplete", "generate_text", "llm"):
        assert token.lower() not in UI_TEXT.lower()


def test_final_validator_is_still_the_intake_build():
    assert "p2_label_intake.py build" in SRC          # 안내 문구로만 등장한다


# --------------------------------------------------- 영상 서비스 (Range)

@pytest.mark.parametrize("header,size,want", [
    ("bytes=0-99", 1000, (0, 99)),
    ("bytes=100-", 1000, (100, 999)),
    ("bytes=-200", 1000, (800, 999)),
])
def test_range_header_is_parsed_for_seeking(header, size, want):
    assert L.parse_range(header, size) == want


def test_bad_range_falls_back_to_the_whole_file():
    assert L.parse_range("bytes=abc", 1000) is None
    assert L.parse_range(None, 1000) is None
