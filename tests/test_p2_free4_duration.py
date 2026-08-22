"""기확보 4편 영상 길이 — **측정 결과를 canonical artifact로 승격한다.**

선정표본에 이 4편의 `duration_sec`이 없다. registry가 `n_segments * 5`로 추정해 채우면
실제보다 최대 한 구간만큼 느슨한 값이 사실처럼 남는다. 그래서 production과 같은 경로로
한 번 재서 출처와 함께 기록하고, 소비자는 그 artifact를 참조한다.

고정하는 것: 측정 경로가 m1과 같은지, 사전등록 구간 수와 맞는지, 없는 값을 만들지
않는지.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p2_free4_duration as F                                    # noqa: E402

SRC = (ROOT / "scripts" / "p2_free4_duration.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


def _fake_measure(monkeypatch):
    """영상마다 사전등록 격자와 맞는 길이를 돌려준다 — 상수를 쓰면 다른 편이 깨진다."""
    pre = {r["source_id"]: r["n_segments"] for r in F.load_selection()}
    monkeypatch.setattr(
        F, "_measure",
        lambda p: ((pre[Path(p).stem] - 1) * F.SEG_LEN + 2.0, 30.0, 1000))
    monkeypatch.setattr(F, "_sha256", lambda p: "a" * 64)


def test_targets_are_exactly_the_four_without_recorded_duration():
    sample = F.load_selection()
    missing = sorted(r["source_id"] for r in sample
                     if r.get("duration_sec") is None)
    assert sorted(F.targets()) == missing
    assert len(missing) == 4


def test_measurement_uses_the_same_path_as_m1():
    assert "CAP_PROP_FRAME_COUNT" in SRC and "CAP_PROP_FPS" in SRC
    assert "ffprobe" not in CODE, "ffprobe duration은 m1 격자와 어긋날 수 있다"


def test_rows_carry_provenance_and_the_grid_check(monkeypatch):
    _fake_measure(monkeypatch)
    rep = F.build()
    assert rep["n"] == 4
    row = rep["rows"][0]
    for k in ("video_id", "duration_sec", "fps", "frame_count", "file_sha256",
              "n_segments_preregistered", "n_segments_derived",
              "measurement_path", "tool"):
        assert k in row, k
    assert rep["source_ref"].endswith("P2_선정표본_2026-08-20.json")


def test_grid_mismatch_fails_closed(monkeypatch):
    monkeypatch.setattr(F, "_measure", lambda p: (10.0, 30.0, 300))
    monkeypatch.setattr(F, "_sha256", lambda p: "a" * 64)
    with pytest.raises(F.MeasureError, match="n_segments"):
        F.build()


def test_missing_file_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "VIDEOS", tmp_path)
    with pytest.raises(F.MeasureError, match="영상 파일이 없다"):
        F.build()


def test_artifact_matches_the_current_files():
    """커밋된 artifact가 지금 파일과 맞는지 — 값이 조용히 낡지 않게."""
    p = F.OUT
    if not p.is_file():
        pytest.skip("artifact가 아직 없다")
    rec = {r["video_id"]: r for r in
           json.loads(p.read_text(encoding="utf-8"))["rows"]}
    sample = {r["source_id"]: r for r in F.load_selection()}
    assert sorted(rec) == sorted(F.targets())
    for vid, row in rec.items():
        assert row["n_segments_derived"] == sample[vid]["n_segments"]
        assert row["duration_sec"] <= sample[vid]["n_segments"] * F.SEG_LEN
