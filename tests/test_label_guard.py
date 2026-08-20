"""라벨 도구가 캡션·자막에 닿지 않는지 **강제**한다.

기존 도구는 관행으로 지켰다 — `segments.json`을 통째로 읽고 `rep_frame`·시각만
썼다. P2에서 기확보 FREE 4편에는 캡션이 **이미 존재**하므로 관행만으로는 부족하다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import label_guard as G                                          # noqa: E402

DOC = {"video_id": "v", "duration_sec": 100.0, "fps": 30.0, "n_segments": 2,
       "segments": [
           {"idx": 0, "start": 0, "end": 5, "rep_frame": "frames/seg_0000.jpg",
            "is_static": False, "motion_score": 0.13,
            "subtitle": "자막 문장", "caption": "캡션 문장"},
           {"idx": 1, "start": 5, "end": 10, "rep_frame": "frames/seg_0001.jpg",
            "subtitle": "", "caption": "또 다른 캡션"}]}


def test_allowlist_is_frames_and_times_only():
    assert G.ALLOWED_SEG_FIELDS == ("idx", "start", "end", "rep_frame")
    for f in ("caption", "subtitle", "score", "rank"):
        assert f in G.FORBIDDEN_FIELDS


def test_strip_drops_caption_and_subtitle():
    out = G.strip_segments(DOC)
    flat = json.dumps(out, ensure_ascii=False)
    for bad in ("캡션 문장", "또 다른 캡션", "자막 문장", "caption", "subtitle"):
        assert bad not in flat, bad
    assert [s["rep_frame"] for s in out["segments"]] == \
        ["frames/seg_0000.jpg", "frames/seg_0001.jpg"]
    assert out["n_segments"] == 2


def test_strip_does_not_mutate_the_original():
    doc = json.loads(json.dumps(DOC, ensure_ascii=False))
    G.strip_segments(doc)
    assert doc["segments"][0]["caption"] == "캡션 문장"


def test_unknown_new_fields_do_not_pass_through():
    """allowlist다 — 나중에 필드가 추가돼도 자동으로 들어오지 않는다."""
    doc = json.loads(json.dumps(DOC, ensure_ascii=False))
    doc["segments"][0]["retrieval_rank"] = 1
    doc["segments"][0]["future_field"] = "x"
    out = G.strip_segments(doc)
    assert set(out["segments"][0]) <= set(G.ALLOWED_SEG_FIELDS)


def test_loader_refuses_when_allowlist_leaks(monkeypatch, tmp_path):
    p = tmp_path / "segments.json"
    p.write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(G, "strip_segments", lambda d: d)   # 고의 누출
    with pytest.raises(G.GuardError, match="allowlist"):
        G.load_segments_for_labeling(p)


# ---- 실제 FREE 4편 -------------------------------------------------------

FREE = ("baekmansonghee_jirisan", "jissi_farm", "softyeon_ceramics",
        "pland_costco_hosting")


@pytest.mark.parametrize("vid", FREE)
def test_real_free_video_captions_are_dropped(vid):
    """P2 표본에 들어간 기확보 4편 — 캡션이 실재한다."""
    p = ROOT / "work" / vid / "segments.json"
    if not p.exists():
        pytest.skip(f"{vid} 미인덱싱")
    raw = json.loads(p.read_text(encoding="utf-8"))
    caps = [s.get("caption", "") for s in raw["segments"]]
    assert any(caps), f"{vid}에 캡션이 없다 — 이 테스트의 전제가 깨졌다"
    out = G.load_segments_for_labeling(p)
    flat = json.dumps(out, ensure_ascii=False)
    for c in [x for x in caps if x][:20]:
        assert c not in flat
    assert out["n_segments"] == raw["n_segments"]


# ---- 도구가 가드를 실제로 쓴다 --------------------------------------------

@pytest.mark.parametrize("tool", ["label_contact_sheet", "label_intake"])
def test_label_tools_use_the_guard(tool):
    src = (ROOT / "scripts" / f"{tool}.py").read_text(encoding="utf-8")
    assert "label_guard" in src, f"{tool}이 가드를 쓰지 않는다"
    body = src.split('"""', 2)[2]
    assert 'segments.json").read_text' not in body, \
        f"{tool}이 segments.json을 직접 읽는다"


@pytest.mark.parametrize("tool", ["label_contact_sheet", "label_intake",
                                  "label_guard"])
def test_label_tools_never_import_search_or_eval(tool):
    body = (ROOT / "scripts" / f"{tool}.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("m5_search", "frame_human_kit", "m8_report"):
        assert bad not in body, (tool, bad)
    # `m6_evaluate`는 **순수 파생 함수 하나만** 허용한다 — 시각 -> 세그먼트 번호.
    # CLAUDE.md 절대규칙 3이 label_intake를 허용 도구로 명시하면서 그 역할을
    # `gt_seg_idx 자동 파생`으로 지정한다. 그 외 심볼은 금지다
    for line in body.splitlines():
        if "m6_evaluate" in line:
            assert line.strip().startswith(
                "from m6_evaluate import derive_gt_seg_idx"), line
    for bad in ("m6_evaluate.search", "from m6_evaluate import evaluate"):
        assert bad not in body, (tool, bad)
    for line in body.splitlines():
        assert line.strip() != "import m6_evaluate", (tool, line)
