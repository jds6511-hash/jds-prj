"""I1 B단계 시트 — **A를 오염시키지 않고 캡션만 새로 보여준다.**

사전등록: `I1검증셋_사전등록_2026-08-18.md` + `보충_B단계경계` + `보충2_B단계_C0생략`.

B에서 새로 보이는 것은 **캡션 문자열 하나**다. arm·I1 판정·셀·검색 순위·A 라벨이
화면에 들어가면 A가 막으려던 편향이 그대로 들어온다. 그걸 도구가 지킨다.
"""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import i1_stage_b_sheet as B                                # noqa: E402

MAN = {"instances": [
    {"sample_id": "S001", "cell": "C0", "i1a_hit": False, "cjk_count": 0,
     "arm": "qwen25_3b__P0", "caption": "숲에서 걷는다", "video_id": "v",
     "seg_idx": 3, "start": 15.0, "end": 20.0, "rep_frame": "f.jpg"},
    {"sample_id": "S002", "cell": "C2", "i1a_hit": False, "cjk_count": 2,
     "arm": "qwen3vl_4b__P1", "caption": "男 두 명이 앉아 있다", "video_id": "v",
     "seg_idx": 9, "start": 45.0, "end": 50.0, "rep_frame": "f.jpg"},
    {"sample_id": "S069", "cell": "C4", "i1a_hit": True, "cjk_count": 5,
     "arm": "qwen3vl_4b__P0", "caption": "간판에 中華料理店라고 적혀 있다",
     "video_id": "v", "seg_idx": 20, "start": 100.0, "end": 105.0,
     "rep_frame": "f.jpg"},
    {"sample_id": "S070", "cell": "C4", "i1a_hit": True, "cjk_count": 7,
     "arm": "qwen3vl_4b__P1", "caption": "다른 한자 캡션", "video_id": "v",
     "seg_idx": 21, "start": 105.0, "end": 110.0, "rep_frame": "f.jpg"},
]}
A_LABELS = {"S001": "no_text", "S002": "no_text", "S069": "cjk_text_present",
            "S070": "korean_text_only"}


def _kit(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps(MAN, ensure_ascii=False),
                                            encoding="utf-8")
    (tmp_path / "labels.csv").write_text(
        "sample_id,label\n" + "".join(f"{k},{v}\n" for k, v in A_LABELS.items()),
        encoding="utf-8")
    (tmp_path / "full").mkdir()
    for s in A_LABELS:
        (tmp_path / "full" / f"{s}.jpg").write_bytes(b"x")
    return tmp_path


# ---- 대상 집합 ------------------------------------------------------------

def test_targets_are_c2_plus_cjk_present_only(tmp_path):
    """보충2: C2 ∪ (가). **C0은 human label 대상이 아니다.**"""
    t = B.targets(*B.load(_kit(tmp_path)))
    assert [x["sample_id"] for x in t] == ["S002", "S069"]


def test_c0_is_excluded_from_labeling_but_recorded_as_derived(tmp_path):
    """`라벨 안 함`과 `분모에서 제외`는 다르다 — 파생값으로 남긴다."""
    man, lab = B.load(_kit(tmp_path))
    d = B.derived_negatives(man)
    assert [x["sample_id"] for x in d] == ["S001"]
    assert d[0]["true_cjk_drift"] is False
    assert d[0]["basis"] == "caption_cjk_count == 0"
    assert d[0]["human_labeled"] is False


def test_cjk_present_without_caption_cjk_is_not_a_target(tmp_path):
    """(가)는 **캡션에 CJK가 있는** `cjk_text_present`만이다."""
    man, lab = B.load(_kit(tmp_path))
    man["instances"][2]["cjk_count"] = 0
    assert "S069" not in [x["sample_id"] for x in B.targets(man, lab)]


def test_i1a_positive_without_cjk_present_label_is_not_a_target(tmp_path):
    """S070은 I1a 적중이지만 A가 `korean_text_only`다 — 도출 규칙이 이미 drift로
    결정하므로 B가 불필요하다."""
    assert "S070" not in [x["sample_id"] for x in B.targets(*B.load(_kit(tmp_path)))]


# ---- 시트가 숨기는 것 -----------------------------------------------------

def test_sheet_shows_caption_time_frame_only(tmp_path):
    k = _kit(tmp_path)
    out = tmp_path / "b"
    B.build(k, out)
    txt = (out / "sheet_b.md").read_text(encoding="utf-8")
    assert "男 두 명이 앉아 있다" in txt and "00:45" in txt and "S002" in txt
    for hidden in ("qwen3vl_4b", "qwen25_3b", "__P0", "__P1", "C2", "C4",
                   "i1a", "cjk_text_present", "korean_text_only"):
        assert hidden not in txt, hidden
    # A 라벨 `no_text`는 B 라벨 `drift_no_text`와 문자열이 겹친다 — 단독 출현만 막는다
    import re
    assert re.search(r"(?<!drift_)no_text", txt) is None


def test_sheet_does_not_ask_about_screen_text(tmp_path):
    """A가 답한 질문을 캡션을 본 상태에서 다시 묻지 않는다."""
    out = tmp_path / "b"
    B.build(_kit(tmp_path), out)
    txt = (out / "sheet_b.md").read_text(encoding="utf-8")
    assert "화면에 글자가 있" not in txt


def test_label_file_has_only_the_four_labels(tmp_path):
    out = tmp_path / "b"
    B.build(_kit(tmp_path), out)
    txt = (out / "sheet_b.md").read_text(encoding="utf-8")
    for lab in B.LABELS:
        assert lab in txt
    rows = list(csv.DictReader(
        (out / "labels_b.csv").read_text(encoding="utf-8").splitlines()))
    assert [r["sample_id"] for r in rows] == ["S002", "S069"]
    assert all(r["label_b"] == "" for r in rows)


def test_labels_are_exactly_prereg_four():
    assert B.LABELS == ("matches_screen", "drift_despite_text",
                        "drift_no_text", "unclear")


# ---- A 동결 --------------------------------------------------------------

def test_build_records_a_label_hash_for_freeze(tmp_path):
    """A 라벨 파일은 B 시작 시점에 동결한다 — 나중 대조용 해시를 남긴다."""
    k = _kit(tmp_path)
    out = tmp_path / "b"
    m = json.loads((B.build(k, out)).read_text(encoding="utf-8"))
    assert m["a_labels_sha256"] and m["n_targets"] == 2
    assert m["derived_negatives"] == 1
    assert m["prereg"]


def test_build_refuses_when_a_labels_incomplete(tmp_path):
    """A를 전부 끝내고 확정한 뒤 B를 시작한다."""
    k = _kit(tmp_path)
    (k / "labels.csv").write_text("sample_id,label\nS001,no_text\n", encoding="utf-8")
    with pytest.raises(B.SheetError, match="A 라벨"):
        B.build(k, tmp_path / "b")


def test_tool_does_not_import_search_or_eval():
    """라벨 도구는 `m5_search`·`m6_evaluate`를 import조차 하지 않는다."""
    src = (ROOT / "scripts" / "i1_stage_b_sheet.py").read_text(encoding="utf-8")
    assert "m5_search" not in src and "m6_evaluate" not in src
