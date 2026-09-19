import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import wvr_report_hwpx as R  # noqa: E402


MD = """# 일상 및 식사·조리 활동 영상 보고서

□ 개요

영상은 음식 준비와 조리로 시작해 외출·이동을 거친 뒤, 다시 조리로 이어진다.

□ 세부내용

| 구분 | 시간 | 내용 | 비고 |
|---|---|---|---|
| 식사 준비 | 00:24 ~ 00:32 | 빵과 토마토를 준비한다. | 관찰 구간 |
| 조리 | 11:36 ~ 11:44 | 음식을 조리하고 접시에 담는다. | 관찰 구간 |
| 식사 준비 | 20:00 ~ 20:08 | 식사를 준비하며 음식을 접시에 올린다. | 관찰 구간 |
| 조리 | 37:40, 37:49 ~ 37:54 | 식재료를 준비하고 조리한다. | 복수 시점 관찰 |
"""


def test_parse_extracts_title_overview_rows():
    doc = R.parse_report(MD)
    assert doc["title"] == "일상 및 식사·조리 활동 영상 보고서"
    assert doc["overview"].startswith("영상은 음식 준비와 조리로 시작해")
    assert len(doc["rows"]) == 4
    assert doc["rows"][0] == {
        "category": "식사 준비",
        "time": "00:24 ~ 00:32",
        "content": "빵과 토마토를 준비한다.",
        "note": "관찰 구간",
    }
    assert doc["rows"][3]["time"] == "37:40, 37:49 ~ 37:54"


def test_parse_rejects_report_without_table():
    with pytest.raises(ValueError, match="세부내용"):
        R.parse_report("# 제목\n\n□ 개요\n\n본문만 있다.\n")


def test_parse_rejects_unexpected_columns():
    bad = MD.replace("| 구분 | 시간 | 내용 | 비고 |", "| 구분 | 시간 | 내용 |")
    with pytest.raises(ValueError, match="열"):
        R.parse_report(bad)


def test_counts_are_derived_only_from_rows():
    doc = R.parse_report(MD)
    counts = R.category_counts(doc["rows"])
    assert counts == [("식사 준비", 2), ("조리", 2)]
    assert sum(c for _, c in counts) == len(doc["rows"])


def test_build_html_preserves_every_cell_verbatim():
    doc = R.parse_report(MD)
    html = R.build_html(doc, video_id="69E1sdSMaO4")
    for row in doc["rows"]:
        for key in ("category", "time", "content", "note"):
            assert row[key] in html
    assert doc["overview"] in html
    assert doc["title"] in html


def test_build_html_adds_no_sentence_of_its_own():
    doc = R.parse_report(MD)
    html = R.build_html(doc, video_id="69E1sdSMaO4")
    text = R.html_to_text(html)
    # 표현 계층이 넣는 고정 문구를 제외하면 원문에 없는 문장이 있어서는 안 된다
    for sentence in R.FIXED_PHRASES:
        text = text.replace(sentence, "")
    for label in ("보고 개요", "대상 영상", "생성 방식", "관찰 구간", "구분별 건수", "영상 개요",
                  "세부 관찰 내용", "연 번", "구 분", "시 간", "내 용", "비 고",
                  "69E1sdSMaO4", "건", "약", "분"):
        text = text.replace(label, "")
    leftovers = [t for t in text.split() if any(ch.isalpha() for ch in t)]
    source = MD + doc["title"] + doc["overview"]
    for token in leftovers:
        assert token in source, token


def test_build_html_escapes_markup_characters():
    md = MD.replace("빵과 토마토를 준비한다.", "빵 & 토마토 <준비>한다.")
    doc = R.parse_report(md)
    html = R.build_html(doc, video_id="x")
    assert "빵 &amp; 토마토 &lt;준비&gt;한다." in html
    assert "<준비>" not in html
