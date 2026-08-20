"""`derive_gt_seg_idx`를 중립 모듈로 옮긴 것이 동작을 바꾸지 않았는지 검증한다.

**새 규칙을 만드는 변경이 아니다.** CLAUDE.md 절대규칙 3의 문언("라벨용 도구는
`m5_search`·`m6_evaluate`를 import조차 하지 마라")과 코드 구조를 일치시키는
refactor다. 이전에는 `label_intake`가 `m6_evaluate`에서 이 함수 하나를 가져와서
**절대 규칙에 특례가 존재**했다.

막는 것 넷.
1. 이동이 값을 바꾸는 것 (경계·최대겹침 분기 포함)
2. `wl_q03` 초집합 허용 동작이 달라지는 것
3. 라벨 도구가 다시 `m6_evaluate`·`m5_search`를 import하는 것
4. 두 모듈에 서로 다른 구현이 공존하는 것 (복사 후 표류)
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                    # noqa: E402
import m6_evaluate as M6                                         # noqa: E402


def test_function_lives_in_the_neutral_module():
    assert hasattr(common, "derive_gt_seg_idx")


def test_m6_reexports_the_same_object_not_a_copy():
    """복사하면 한쪽만 고쳐져 표류한다 — 같은 객체여야 한다."""
    assert M6.derive_gt_seg_idx is common.derive_gt_seg_idx


def test_only_one_definition_exists_in_the_tree():
    hits = []
    for p in list((ROOT / "src").glob("*.py")) + \
            list((ROOT / "scripts").glob("*.py")):
        if "def derive_gt_seg_idx" in p.read_text(encoding="utf-8"):
            hits.append(p.name)
    assert hits == ["common.py"], hits


# ---- 값이 바뀌지 않았다 --------------------------------------------------

def test_documented_cases_unchanged():
    d = common.derive_gt_seg_idx
    assert d(3.0, 7.0, n_segments=3, seg_len=5) == [0, 1]
    assert d(4.8, 5.4, n_segments=3, seg_len=5) == [1]
    assert d(33.0, 38.5, n_segments=10, seg_len=5) == [6, 7]


def test_one_second_threshold_is_inclusive():
    d = common.derive_gt_seg_idx
    assert d(4.0, 6.0, n_segments=3, seg_len=5) == [0, 1]      # 각 정확히 1.0s
    # 각 0.5s로 1초 미달 → 최대겹침 1개. **동률이면 낮은 인덱스**(max가 첫 원소를
    # 준다). 이동 전과 같은 동작이며 여기서 고정한다
    assert d(4.5, 5.5, n_segments=3, seg_len=5) == [0]


def test_never_returns_empty():
    d = common.derive_gt_seg_idx
    for a, b in ((0.0, 0.0), (7.2, 7.3), (99.0, 99.1)):
        assert len(d(a, b, n_segments=20, seg_len=5)) >= 1


def test_grid_is_identical_to_the_reference_implementation():
    """이동 전 구현을 그대로 재현해 전 격자 대조한다."""
    def reference(gt_start, gt_end, n_segments, seg_len):
        overlaps = []
        for i in range(n_segments):
            s, e = i * seg_len, (i + 1) * seg_len
            overlaps.append((i, max(0.0, min(e, gt_end) - max(s, gt_start))))
        idx = [i for i, ov in overlaps if ov >= 1.0]
        return idx if idx else [max(overlaps, key=lambda t: t[1])[0]]

    for start in range(0, 60):
        for span in (0.4, 1.0, 2.5, 5.0, 12.0):
            a = start * 0.7
            got = common.derive_gt_seg_idx(a, a + span, 30, 5)
            assert got == reference(a, a + span, 30, 5), (a, span)


# ---- wl_q03 초집합 허용이 그대로다 ----------------------------------------

def test_wl_q03_superset_behaviour_unchanged():
    """`gt_seg_idx`가 파생 결과의 초집합인 유일한 예외 — 동작이 변하면 안 된다."""
    p = ROOT / "data" / "queries" / "queries.jsonl"
    if not p.exists():
        pytest.skip("queries.jsonl 없음")
    q = next((json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
              if l.strip() and json.loads(l)["query_id"] == "wl_q03"), None)
    if q is None:
        pytest.skip("wl_q03 없음")
    derived = common.derive_gt_seg_idx(q["gt_start"], q["gt_end"], 400, 5)
    assert derived == [132, 133, 134]
    # 라벨의 312는 파생 결과에 없는 초집합 원소다 — 누락이 아니라 추가 포함이다
    assert set(derived) <= set(q["gt_seg_idx"])
    assert 312 in q["gt_seg_idx"]


# ---- 라벨 도구가 규칙 문언과 일치한다 -------------------------------------

@pytest.mark.parametrize("tool", ["label_intake", "label_contact_sheet",
                                  "label_guard", "event_inventory_kit"])
def test_label_tools_import_neither_m5_nor_m6(tool):
    body = (ROOT / "scripts" / f"{tool}.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("m5_search", "m6_evaluate", "frame_human_kit"):
        assert bad not in body, (tool, bad)


def test_label_intake_derives_from_common():
    src = (ROOT / "scripts" / "label_intake.py").read_text(encoding="utf-8")
    assert "common.derive_gt_seg_idx" in src or \
        "from common import derive_gt_seg_idx" in src
