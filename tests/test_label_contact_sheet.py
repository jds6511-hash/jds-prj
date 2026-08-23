"""라벨용 컨택트시트 — **프레임과 시각만 나간다.**

기존 도구는 신규 test 후보 3편이 하드코딩돼 있었다. P2는 35편이고 구간 격자가 사전등록
값이라, 여기서 고정하는 것은 두 가지다.

```
1  타일에 캡션·자막·모델·arm·점수·순위가 들어가지 않는다 (label_guard 경유)
2  프레임 누락·격자 불일치를 조용히 건너뛰지 않는다 (fail-closed)
```
"""
import ast
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import label_contact_sheet as L                                  # noqa: E402

SRC = (ROOT / "scripts" / "label_contact_sheet.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


def _work(tmp_path, n=8, with_caption=True, missing_frame=False):
    """캡션·자막이 **들어 있는** segments.json — 기확보 영상과 같은 상황이다."""
    w = tmp_path / "work" / "vid"
    (w / "frames").mkdir(parents=True)
    segs = []
    for i in range(n):
        rel = f"frames/seg_{i:04d}.jpg"
        if not (missing_frame and i == n - 1):
            Image.new("RGB", (64, 36), (i * 7 % 255, 40, 90)).save(w / rel)
        s = {"idx": i, "start": i * 5.0, "end": (i + 1) * 5.0, "rep_frame": rel,
             "is_static": False, "motion_score": 0.5}
        if with_caption:
            s["caption"] = f"비밀 캡션 {i}"
            s["subtitle"] = f"비밀 자막 {i}"
        segs.append(s)
    (w / "segments.json").write_text(
        json.dumps({"video_id": "vid", "n_segments": n, "fps": 30.0,
                    "segments": segs}, ensure_ascii=False), encoding="utf-8")
    return {"paths": {"work": str(tmp_path / "work")}}


@pytest.mark.parametrize("token", ["caption", "subtitle", "score", "rank",
                                   "arm", "mrr"])
def test_forbidden_information_never_reaches_the_tile(token):
    """그리는 코드에 그 필드 이름이 없어야 한다 — 관행이 아니라 코드로 막는다."""
    drawing = CODE.split("def main")[0]
    assert token not in drawing


def test_sheet_is_written_and_pages_split(tmp_path):
    cfg = _work(tmp_path, n=8)
    made = L.build("vid", cfg, out=tmp_path / "sheets")
    assert made and all(p.is_file() for p in made)
    assert Image.open(made[0]).size[0] > 0


def test_grid_mismatch_with_the_preregistered_count_fails_closed(tmp_path):
    cfg = _work(tmp_path, n=8)
    with pytest.raises(L.SheetError, match="n_segments"):
        L.build("vid", cfg, out=tmp_path / "sheets", expect_n=9)


def test_missing_frame_fails_closed_with_the_segment_named(tmp_path):
    cfg = _work(tmp_path, n=6, missing_frame=True)
    with pytest.raises(L.SheetError, match="rep_frame"):
        L.build("vid", cfg, out=tmp_path / "sheets")


def test_guard_rejects_a_leaking_loader(tmp_path, monkeypatch):
    """allowlist를 우회하면 시트를 만들지 않는다."""
    cfg = _work(tmp_path, n=4)
    import label_guard
    monkeypatch.setattr(label_guard, "strip_segments", lambda doc: doc)
    with pytest.raises(label_guard.GuardError, match="allowlist"):
        L.build("vid", cfg, out=tmp_path / "sheets")


def test_p2_targets_come_from_the_frozen_sample_not_a_hardcoded_list():
    vids = L.p2_targets()
    assert len(vids) == 35
    assert "jissi_farm" in vids and "-_mgcIUbbX4" in vids
    counts = L.p2_expected_segments()
    assert counts["pland_costco_hosting"] == 395
    assert sum(counts.values()) == 9115
