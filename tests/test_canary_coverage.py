"""CANARY 입력 커버리지 — **"몇 편"이 아니라 "어떤 종류"를 밟았는가.**

2026-08-21 사고 3건이 전부 입력 종류에서 났다. CANARY가 신규 avc1 1편만 돌려서
기확보·AV1·하이픈 id를 밟지 않았고, 두 건은 FULL 31편째에서야 드러났다.

여기서 고정하는 것은 축 목록이 아니라 **없는 범주를 만들지 않는다**는 것과
**성능·캡션·검색 결과를 커버리지 입력으로 쓰지 않는다**는 것이다.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import canary_coverage as C                                      # noqa: E402

SRC = (ROOT / "scripts" / "canary_coverage.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)

CORPUS = [
    {"source_id": "aaa", "n_segments": 100, "speech_status": "audio_track_ko"},
    {"source_id": "-bbb", "n_segments": 300, "speech_status": "unresolved"},
    {"source_id": "ccc", "n_segments": 200, "pre_indexed": True,
     "speech_status": "audio_track_ko"},
]
CODECS = {"aaa": "native_h264", "-bbb": "native_h264", "ccc": "transcoded_h264"}


def _inv(corpus=None, codecs=None):
    return C.inventory(corpus or CORPUS, codecs or CODECS)


# ------------------------------------------------------- 입력으로 쓰면 안 되는 것

@pytest.mark.parametrize("token", ["caption", "subtitle", "mrr", "recall",
                                   "score", "rank", "segments.json"])
def test_performance_and_model_output_are_not_coverage_inputs(token):
    assert token not in CODE


# ------------------------------------------------------------------- 분류

def test_every_axis_is_observed_not_invented():
    """어떤 클래스도 소속 영상이 0이면 안 된다 — 없는 범주를 만들지 않는다."""
    inv = _inv()
    members = {}
    for vid, classes in inv.items():
        for c in classes:
            members.setdefault(c, []).append(vid)
    assert members and all(members.values())


def test_classes_cover_the_five_required_axes():
    inv = _inv()
    axes = {c.split(":", 1)[0] for cs in inv.values() for c in cs}
    assert axes == set(C.AXES)


def test_cli_sensitive_id_is_its_own_class():
    inv = _inv()
    assert "id_shape:cli_sensitive" in inv["-bbb"]
    assert "id_shape:plain" in inv["aaa"]


def test_legacy_and_new_are_separated():
    inv = _inv()
    assert "provenance:legacy" in inv["ccc"]
    assert "provenance:new" in inv["aaa"]


def test_duration_extremes_are_corpus_relative():
    inv = _inv()
    assert "duration:shortest" in inv["aaa"] and "duration:longest" in inv["-bbb"]
    assert not [c for c in inv["ccc"] if c.startswith("duration:")]


def test_audio_language_known_vs_unresolved():
    inv = _inv()
    assert "audio:known" in inv["aaa"] and "audio:unresolved" in inv["-bbb"]


def test_unknown_codec_fails_closed():
    with pytest.raises(C.CoverageError, match="codec"):
        C.inventory(CORPUS, {"aaa": "native_h264"})


# ------------------------------------------------------------------- 커버리지

def test_missing_classes_are_reported():
    inv = _inv()
    r = C.coverage([v["source_id"] for v in CORPUS], ["aaa"], inv)
    assert r["ok"] is False
    assert "provenance:legacy" in r["missing"]
    assert "codec:transcoded_h264" in r["missing"]
    assert set(r["covered"]) <= set(r["full_classes"])


def test_full_coverage_is_ok():
    inv = _inv()
    ids = [v["source_id"] for v in CORPUS]
    r = C.coverage(ids, ids, inv)
    assert r["ok"] is True and r["missing"] == []


def test_canary_video_outside_full_is_refused():
    """FULL 입력에 없는 영상으로 커버리지를 채우면 밟은 게 아니다."""
    with pytest.raises(C.CoverageError, match="FULL 입력에 없다"):
        C.coverage(["aaa"], ["ccc"], _inv())


def test_video_outside_the_inventory_is_refused():
    with pytest.raises(C.CoverageError, match="inventory에 없는"):
        C.coverage(["aaa", "zzz"], ["aaa"], _inv())


def test_require_coverage_is_fail_closed():
    inv = _inv()
    with pytest.raises(C.CoverageError, match="미포함"):
        C.require_coverage([v["source_id"] for v in CORPUS], ["aaa"], inv)
    ids = [v["source_id"] for v in CORPUS]
    assert C.require_coverage(ids, ids, inv)["ok"] is True


# ------------------------------------------------------------- 대표 표본 선정

def test_representative_set_covers_every_class_and_is_deterministic():
    inv = _inv()
    a = C.select_representatives(inv)
    b = C.select_representatives(inv)
    assert a == b
    assert C.coverage([v["source_id"] for v in CORPUS], a, inv)["ok"] is True


def test_representative_selection_prefers_small_inputs_on_ties():
    """동률이면 구간이 적은 쪽 — CANARY는 배관 확인이라 짧을수록 좋다."""
    corpus = CORPUS + [{"source_id": "ddd", "n_segments": 50,
                        "speech_status": "audio_track_ko"}]
    codecs = {**CODECS, "ddd": "native_h264"}
    inv = C.inventory(corpus, codecs)
    picked = C.select_representatives(inv)
    assert "ddd" in picked and "aaa" not in picked


def test_selection_does_not_read_the_corpus_order():
    inv_a = C.inventory(CORPUS, CODECS)
    inv_b = C.inventory(list(reversed(CORPUS)), CODECS)
    assert C.select_representatives(inv_a) == C.select_representatives(inv_b)
