"""WVR_DISPLAY_SANITIZATION_AND_LOCAL_DEDUP_PATCH_V1 — 표시 계층만 검사한다."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))

import wvr_display_sanitize_v1 as ds  # noqa: E402


# ── visual mixed-script ────────────────────────────────────────────────

def test_clean_korean_visual_text_stays_original():
    out = ds.sanitize_visual_text("식재료를 준비하고 조리하는 활동", category="관찰 장면",
                                  broad_activity=["FOOD_PREPARATION"])
    assert out["display_decision"] == ds.ORIGINAL
    assert out["display_text"] == "식재료를 준비하고 조리하는 활동"


def test_english_acronym_is_not_stripped():
    out = ds.sanitize_visual_text("GPS 장치를 조작한다", category="관찰 장면",
                                  broad_activity=["WORK_OR_STUDY"])
    assert out["display_decision"] == ds.ORIGINAL


def test_digits_are_not_stripped():
    out = ds.sanitize_visual_text("그릇 3개를 식탁에 올린다", category="관찰 장면",
                                  broad_activity=["FOOD_PREPARATION"])
    assert out["display_decision"] == ds.ORIGINAL


def test_mixed_script_falls_back_to_verified_activity_label():
    out = ds.sanitize_visual_text("조리 도구에蛤蜊을 넣고 술을 부어 뚜껑으로 덮는다",
                                  category="관찰 장면", broad_activity=["FOOD_PREPARATION"])
    assert out["display_decision"] == ds.SAFE_VISUAL_DOWNGRADE
    assert out["display_text"] == "조리 활동"


def test_mixed_script_prefers_specific_clean_category_over_activity_label():
    out = ds.sanitize_visual_text("냄비에蛤蜊을 넣는다", category="라면 조리",
                                  broad_activity=["FOOD_PREPARATION"])
    assert out["display_decision"] == ds.SAFE_VISUAL_DOWNGRADE
    assert out["display_text"] == "라면 조리"


def test_mixed_script_without_any_clean_source_is_withheld():
    out = ds.sanitize_visual_text("조리 도구에蛤蜊을 넣는다", category="관찰 장면",
                                  broad_activity=["OTHER_VISIBLE_ACTIVITY"])
    assert out["display_decision"] == ds.VISUAL_TEXT_WITHHELD_MIXED_SCRIPT
    assert out["display_text"] is None


def test_original_text_is_always_preserved():
    raw = "조리 도구에蛤蜊을 넣는다"
    for activity in (["FOOD_PREPARATION"], ["OTHER_VISIBLE_ACTIVITY"]):
        assert ds.sanitize_visual_text(raw, "관찰 장면", activity)["original_text"] == raw


def test_downgrade_does_not_invent_new_nouns():
    out = ds.sanitize_visual_text("조리 도구에蛤蜊을 넣고 술을 부어 뚜껑으로 덮는다",
                                  category="관찰 장면", broad_activity=["FOOD_PREPARATION"])
    for noun in ("조개", "대합", "술", "뚜껑"):
        assert noun not in out["display_text"]


def test_activity_label_table_covers_only_known_enum():
    assert ds.activity_label("NOT_AN_ENUM_VALUE") is None
    assert ds.activity_label("FOOD_PREPARATION") == "조리"


# ── local repetition ───────────────────────────────────────────────────

def test_consecutive_token_run_collapses():
    out = ds.dedup_local("참기름 참기름 참기름 참기름 넣습니다")
    assert out["text"] == "참기름 넣습니다"
    assert out["removed"][0]["kind"] == "token"
    assert out["removed"][0]["repeats"] == 3


def test_consecutive_phrase_repetition_collapses():
    out = ds.dedup_local("재료를 넣고 재료를 넣고 섞는다")
    assert out["text"] == "재료를 넣고 섞는다"
    assert out["removed"][0]["kind"] == "phrase"


def test_consecutive_identical_sentence_collapses():
    out = ds.dedup_local("재료를 넣습니다. 재료를 넣습니다.")
    assert out["text"] == "재료를 넣습니다."
    assert out["removed"][0]["kind"] == "sentence"


def test_non_consecutive_identical_sentence_is_kept():
    text = "재료를 넣습니다. 불을 켭니다. 재료를 넣습니다."
    assert ds.dedup_local(text)["text"] == text


def test_near_duplicate_sentence_is_not_removed():
    text = ("오늘의 점심 메뉴는 얼큰한 해장국과 얼큰한 해장국을 준비했습니다. "
            "오늘의 점심 메뉴는 얼큰한 해장국을 준비했습니다.")
    out = ds.dedup_local(text)
    assert out["text"] == text
    assert out["removed"] == []


def test_decimal_number_is_not_treated_as_token_repetition():
    text = "현재 신청자의 비율은 전체의 2.2%이고, 하루 5명에서 10명 정도다."
    assert ds.dedup_local(text)["text"] == text


def test_clean_text_is_unchanged():
    text = "참가자들이 지게를 이용해 물건을 옮기는 봉사활동을 하고 있다."
    out = ds.dedup_local(text)
    assert out["text"] == text and out["removed"] == []


def test_empty_text_is_safe():
    assert ds.dedup_local("")["text"] == ""
    assert ds.dedup_local(None)["text"] == ""


def test_dedup_never_adds_characters():
    text = "참기름 참기름 넣고 재료를 넣고 재료를 넣고 볶는다"
    out = ds.dedup_local(text)
    assert set(out["text"].split()) <= set(text.split())
    assert len(out["text"]) < len(text)
