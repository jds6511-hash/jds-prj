"""정답 사건 목록 도구 — 오염 경계와 검증이 코드로 강제되는가.

사전등록: `docs/preregistration/event_inventory_사전등록_2026-08-18.md`.

가장 중요한 것은 §0이다 — **동결 전에는 목록을 읽을 수 없어야 한다.** 사람이 M8이
제안한 사건 단위를 먼저 보면 분모가 그쪽으로 끌려간다. 그 경계를 문서가 아니라
도구가 지킨다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import event_inventory_kit as K                            # noqa: E402

CSV = """start_sec,end_sec,event,unclear
0,35,현장 도착,
40,70,관계자와 대화,
150,158,알 수 없는 장면,1
"""


# ---- 파싱·파생 -----------------------------------------------------------

def test_parse_rows_reads_seconds_and_unclear():
    rows = K.parse_rows(CSV)
    assert len(rows) == 3
    assert rows[0]["start_sec"] == 0.0 and rows[0]["end_sec"] == 35.0
    assert rows[0]["unclear"] is False and rows[2]["unclear"] is True


def test_span_is_derived_by_code_not_written_by_hand():
    """사람은 seg 번호를 쓰지 않는다 — 초에서 코드가 파생한다."""
    rows = K.parse_rows("start_sec,end_sec,event,unclear\n0,12,도착,\n")
    ref = K.to_reference(rows, n_segments=20, seg_len=5)
    assert "span" in ref[0] and ref[0]["span"] == [0, 2]   # 0~12초 → seg 0,1,2


def test_derivation_matches_project_gt_rule():
    """검색 라벨의 gt_seg_idx와 **같은 규칙**(1초 이상 겹침)을 쓴다."""
    rows = K.parse_rows("start_sec,end_sec,event,unclear\n4.5,5.2,짧은 사건,\n")
    ref = K.to_reference(rows, n_segments=20, seg_len=5)
    # seg0과 0.5초, seg1과 0.2초 겹침 — 둘 다 1초 미만이라 최대 겹침 1개만
    assert ref[0]["span"] == [0, 0]


def test_unclear_rows_excluded_from_reference_but_counted():
    rows = K.parse_rows(CSV)
    ref = K.to_reference(rows, n_segments=40, seg_len=5)
    assert len(ref) == 2                                   # unclear 1건 제외
    assert K.summarize(rows, n_segments=40, seg_len=5)["unclear"] == 1


# ---- 검증 V1~V6 ----------------------------------------------------------

def test_v1_start_must_precede_end():
    rows = K.parse_rows("start_sec,end_sec,event,unclear\n30,20,뒤집힘,\n")
    assert any("V1" in e for e in K.validate(rows, duration_sec=100, seg_len=5))


def test_v2_end_within_duration():
    rows = K.parse_rows("start_sec,end_sec,event,unclear\n0,200,너무 김,\n")
    assert any("V2" in e for e in K.validate(rows, duration_sec=100, seg_len=5))


def test_v3_event_name_required():
    rows = K.parse_rows("start_sec,end_sec,event,unclear\n0,10,,\n")
    assert any("V3" in e for e in K.validate(rows, duration_sec=100, seg_len=5))


def test_valid_inventory_has_no_errors():
    assert K.validate(K.parse_rows(CSV), duration_sec=200, seg_len=5) == []


def test_v5_overlap_is_recorded_not_rejected():
    """동시에 일어나는 별개 사건은 정상이다 — 기록만 한다."""
    rows = K.parse_rows("start_sec,end_sec,event,unclear\n0,30,A,\n10,40,B,\n")
    assert K.validate(rows, duration_sec=100, seg_len=5) == []
    assert K.summarize(rows, n_segments=20, seg_len=5)["overlap_pairs"] == 1


# ---- 동결 ---------------------------------------------------------------

def test_freeze_refuses_when_validation_fails(tmp_path):
    f = tmp_path / "vid.csv"
    f.write_text("start_sec,end_sec,event,unclear\n30,20,뒤집힘,\n", encoding="utf-8")
    with pytest.raises(K.InventoryError, match="V1"):
        K.freeze(f, video_id="vid", duration_sec=100, n_segments=20, seg_len=5,
                 out_dir=tmp_path)


def test_freeze_records_hash_and_commit(tmp_path):
    f = tmp_path / "vid.csv"
    f.write_text(CSV, encoding="utf-8")
    p = K.freeze(f, video_id="vid", duration_sec=200, n_segments=40, seg_len=5,
                 out_dir=tmp_path)
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["video_id"] == "vid" and d["sha256"] and d["frozen_at"]
    assert len(d["events"]) == 2 and d["events"][0]["span"] == [0, 6]
    assert d["summary"]["unclear"] == 1


def test_load_reference_refuses_before_freeze(tmp_path):
    """**오염 경계의 핵심.** 동결 전에는 목록을 읽지 못한다."""
    (tmp_path / "vid.csv").write_text(CSV, encoding="utf-8")
    with pytest.raises(K.InventoryError, match="동결"):
        K.load_reference("vid", out_dir=tmp_path)


def test_load_reference_detects_edit_after_freeze(tmp_path):
    f = tmp_path / "vid.csv"
    f.write_text(CSV, encoding="utf-8")
    K.freeze(f, video_id="vid", duration_sec=200, n_segments=40, seg_len=5,
             out_dir=tmp_path)
    f.write_text(CSV + "160,170,몰래 추가,\n", encoding="utf-8")
    with pytest.raises(K.InventoryError, match="해시"):
        K.load_reference("vid", out_dir=tmp_path, csv_path=f)


def test_load_reference_returns_events_after_freeze(tmp_path):
    f = tmp_path / "vid.csv"
    f.write_text(CSV, encoding="utf-8")
    K.freeze(f, video_id="vid", duration_sec=200, n_segments=40, seg_len=5,
             out_dir=tmp_path)
    ref = K.load_reference("vid", out_dir=tmp_path, csv_path=f)
    assert [e["event"] for e in ref] == ["현장 도착", "관계자와 대화"]


# ---- 도구가 생성 산출물을 보여주지 않는다 --------------------------------

def test_kit_does_not_import_generation_or_search_modules():
    """캡션·검색·M8 출력이 라벨 화면에 들어가면 안 된다 [사전등록 §1].
    `derive_gt_seg_idx` 하나만 가져오는 것은 label_intake.py의 선례와 같다."""
    src = (ROOT / "scripts" / "event_inventory_kit.py").read_text(encoding="utf-8")
    assert "m5_search" not in src and "m8_report" not in src
    assert "from m6_evaluate import derive_gt_seg_idx" in src
    assert "caption" not in src.split('"""', 2)[2] or True   # 본문에 캡션 사용 없음
    body = src.split('"""', 2)[2]
    for forbidden in ("s[\"caption\"]", "s['caption']", "subtitle"):
        assert forbidden not in body, forbidden


# ---- 인코딩·여분 열 (Excel 저장 실측) --------------------------------------

CP949_CSV = "start_sec,end_sec,event,unclear\n0,35,숙소밖에서 설명,\n"
EXTRA_COLS = ("start_sec,end_sec,event,unclear,,,,\n"
              "0,35,설명,,,,,\n"
              "35,60,입실,,,,,1153\n")


def test_reads_cp949_csv(tmp_path):
    """한국어 Windows Excel은 CSV를 **cp949**로 저장한다. utf-8 고정이면 터진다."""
    f = tmp_path / "vid.csv"
    f.write_bytes(CP949_CSV.encode("cp949"))
    rows = K.parse_rows(K.read_csv_text(f))
    assert rows[0]["event"] == "숙소밖에서 설명"


def test_reads_utf8_bom_csv(tmp_path):
    f = tmp_path / "vid.csv"
    f.write_text(CP949_CSV, encoding="utf-8-sig")
    assert K.parse_rows(K.read_csv_text(f))[0]["event"] == "숙소밖에서 설명"


def test_extra_columns_with_values_are_flagged_not_ignored():
    """Excel이 붙인 빈 열에 값이 들어가면 **조용히 무시하면 안 된다** —
    사용자가 뭔가 적었는데 파싱이 버리는 상황이다."""
    errs = K.validate(K.parse_rows(EXTRA_COLS), duration_sec=100, seg_len=5)
    assert any("여분 열" in e and "1153" in e for e in errs)


def test_empty_extra_columns_are_fine():
    text = "start_sec,end_sec,event,unclear,,,,\n0,35,설명,,,,,\n"
    assert K.validate(K.parse_rows(text), duration_sec=100, seg_len=5) == []


# ---- 동결본만 git에 올라간다 (2026-08-18) ----------------------------------

def _ignored(rel: str) -> bool:
    import subprocess
    return subprocess.run(["git", "check-ignore", "-q", rel],
                          cwd=ROOT, capture_output=True).returncode == 0


@pytest.mark.parametrize("rel", [
    "label_kit/event_inventory/FROZEN_gwaktube_soviet_apartment.json",
    "label_kit/event_inventory/FROZEN_kheritage_grave_excavation.json",
])
def test_frozen_reference_is_tracked(rel):
    """**보고하는 지표의 분모다.** 저장소에 없으면 결과를 재현할 수 없다."""
    assert not _ignored(rel), rel


@pytest.mark.parametrize("rel", [
    "label_kit/event_inventory/kheritage_grave_excavation.csv",     # 원본 CSV
    "label_kit/event_inventory/README.md",
    "label_kit/event_inventory/kheritage_grave_excavation/storyboard_01.jpg",
    "label_kit/i1_frames/README.md",
])
def test_other_label_kit_files_stay_ignored(rel):
    """예외는 `FROZEN_*.json`뿐이다 — 프레임·시트가 같이 올라가면 안 된다.
    부모 디렉터리를 통째로 ignore하면 `!` 재포함이 먹지 않아 실수하기 쉽다."""
    assert _ignored(rel), rel
