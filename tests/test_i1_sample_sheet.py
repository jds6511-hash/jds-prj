"""I1 검증셋 층화 규칙 — 셀이 서로 겹치지 않고 현행 detector와 어긋나지 않는지.

사전등록 §2가 "셀은 서로 겹치지 않게" 정의한다고 못박았다. 셀 배정이 어긋나면
I1a precision/recall이 통째로 틀린다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                              # noqa: E402
from i1_sample_sheet import CJK, cell_of, longest_cjk_run  # noqa: E402

CASES = [
    ("한국어만 있는 정상 캡션입니다.", "C0"),
    ("", "C0"),
    ("한 남자가 中 글자가 적힌 옷을 입고 있습니다.", "C2"),          # CJK 1
    ("간판에 中国 이라고 적혀 있는 거리를 걷고 있습니다.", "C2"),      # CJK 2
    ("계단 위에는 中国人民 이라 적힌 표지가 서 있는 장면입니다.", "C4"),  # CJK 4
    ("女性が台所で料理をしている場面です。とても静かな時間。", "C5"),   # CJK 10+
]


def test_cell_assignment():
    for text, want in CASES:
        assert cell_of(text) == want, (text, cell_of(text), want)


def test_cells_agree_with_detector():
    """CJK 3자 이상이면 현행 detector가 반드시 잡는다(C4·C5는 전부 I1a 적중).
    CJK 0인데 적중이면 C1 — 비-CJK 원인이다."""
    for text, cell in CASES:
        hit = common.is_corrupted_caption(text)
        n = len(CJK.findall(text))
        if cell in ("C4", "C5"):
            assert hit and n >= 3
        if cell == "C0":
            assert not hit and n == 0
        if cell == "C2":
            assert not hit and 1 <= n <= 2


def test_repeat_caption_is_C1():
    """반복 생성은 CJK가 0이어도 적중한다 — 비-CJK 원인 셀."""
    text = "계단 위에는 계단 위에는 계단 위에는 계단 위에는"
    assert common.is_corrupted_caption(text)
    assert cell_of(text) == "C1"


def test_longest_cjk_run():
    assert longest_cjk_run("한글 中国 사이 人") == 2
    assert longest_cjk_run("한글만 있습니다") == 0
