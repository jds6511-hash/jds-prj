"""라벨링 blind 유지 장치 — 컨택트시트 대상 목록과 유출 검사.

두 가지를 잠근다.

```
① 패널 목록은 **동결 manifest에서만** 온다 — 손으로 적으면 판정 표본이 갈린다
② 유출 검사는 캡션·자막 **원문 값**을 대조한다 — 필드 이름만 보면 값이 다른 이름으로
   실려 들어온 경우를 놓친다
```
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import label_blindness_check as B                              # noqa: E402
import label_contact_sheet as CS                               # noqa: E402
import label_guard                                             # noqa: E402

MANIFEST = ROOT / "docs/finalization/m8_c2_panel_manifest_2026-08-27.json"


# ------------------------------------------------------- 대상 목록의 출처

@pytest.mark.skipif(not MANIFEST.exists(), reason="패널 manifest 미동결")
def test_panel_targets_come_from_the_frozen_manifest():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert CS.m8_c2_panel_targets() == man["final_panel"]
    assert len(CS.m8_c2_panel_targets()) == 8


def test_panel_targets_reject_a_tampered_manifest(tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"final_panel": ["a", "b"], "design": {"fixed_n": 8}}),
                   encoding="utf-8")
    with pytest.raises(CS.SheetError, match="고유"):
        CS.m8_c2_panel_targets(bad)


def test_panel_targets_reject_duplicates(tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"final_panel": ["a"] * 8, "design": {"fixed_n": 8}}),
                   encoding="utf-8")
    with pytest.raises(CS.SheetError):
        CS.m8_c2_panel_targets(bad)


def test_contact_sheet_reads_segments_through_the_guard():
    """시트 생성 경로가 allowlist를 지나야 캡션·자막이 애초에 로드되지 않는다."""
    src = (ROOT / "scripts/label_contact_sheet.py").read_text(encoding="utf-8")
    assert "label_guard" in src
    assert label_guard.ALLOWED_SEG_FIELDS == ("idx", "start", "end", "rep_frame")


# ------------------------------------------------------- 유출 검사의 성질

def _kit(tmp_path, name: str, text: str) -> Path:
    d = tmp_path / "contact_sheets"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


def test_scan_passes_on_clean_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "ROOT", tmp_path)
    _kit(tmp_path, "sheet_index.json", json.dumps({"video_id": "v", "seg_idx": 3,
                                                   "start": 15, "end": 20}))
    res = B.scan(tmp_path, videos=[])
    assert res["verdict"] == "PASS"


def test_scan_catches_a_caption_value_even_under_a_harmless_field_name(tmp_path, monkeypatch):
    """필드 이름을 `note`로 바꿔 캡션을 실어도 값 대조에서 걸려야 한다."""
    monkeypatch.setattr(B, "ROOT", tmp_path)
    caption = "화면에는 한 남성이 문을 열고 들어와 있는 모습이 보입니다"
    _kit(tmp_path, "sheet_index.json", json.dumps({"note": caption}, ensure_ascii=False))
    seg = tmp_path / "work" / "v" / "segments.json"
    seg.parent.mkdir(parents=True)
    seg.write_text(json.dumps({"video_id": "v", "n_segments": 1, "segments": [
        {"idx": 0, "start": 0, "end": 5, "caption": caption, "subtitle": ""}]},
        ensure_ascii=False), encoding="utf-8")
    res = B.scan(tmp_path, videos=["v"])
    assert res["verdict"] == "FAIL"
    assert res["caption_or_subtitle_value_hits"]


def test_scan_catches_forbidden_field_names_in_data_files(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "ROOT", tmp_path)
    _kit(tmp_path, "sheet_index.json", json.dumps({"rank": 1, "score": 0.9}))
    res = B.scan(tmp_path, videos=[])
    assert res["verdict"] == "FAIL"
    assert {h["token"] for h in res["body_token_hits"]} >= {"rank", "score"}


def test_query_type_name_is_not_a_leak(tmp_path, monkeypatch):
    """`자막형`은 질의 유형명이다 — 이것으로 FAIL이 나면 검사가 쓸모없어진다."""
    monkeypatch.setattr(B, "ROOT", tmp_path)
    _kit(tmp_path, "types.json", json.dumps({"type": "자막형"}, ensure_ascii=False))
    assert B.scan(tmp_path, videos=[])["verdict"] == "PASS"


def test_bare_subtitle_word_in_a_data_file_is_a_leak(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "ROOT", tmp_path)
    _kit(tmp_path, "d.json", json.dumps({"자막": "무언가"}, ensure_ascii=False))
    assert B.scan(tmp_path, videos=[])["verdict"] == "FAIL"


def test_guide_markdown_may_state_the_prohibition(tmp_path, monkeypatch):
    """규칙 문서는 "캡션을 보지 마라"를 적어야 한다 — 토큰 검사에서 뺀다."""
    monkeypatch.setattr(B, "ROOT", tmp_path)
    _kit(tmp_path, "가이드.md", "캡션과 자막을 보지 마라. score·rank도 보지 마라.")
    assert B.scan(tmp_path, videos=[])["verdict"] == "PASS"


def test_other_tasks_artifacts_are_reported_separately(tmp_path, monkeypatch):
    """`i1_frames/`처럼 캡션이 라벨 대상이던 과제는 판정에 섞지 않고 따로 적는다."""
    monkeypatch.setattr(B, "ROOT", tmp_path)
    caption = "화면에는 한 여성이 스마트폰을 들고 있는 모습이 보입니다"
    other = tmp_path / "i1_frames"
    other.mkdir(parents=True)
    (other / "manifest.json").write_text(json.dumps({"caption": caption},
                                                    ensure_ascii=False), encoding="utf-8")
    seg = tmp_path / "work" / "v" / "segments.json"
    seg.parent.mkdir(parents=True)
    seg.write_text(json.dumps({"video_id": "v", "n_segments": 1, "segments": [
        {"idx": 0, "start": 0, "end": 5, "caption": caption, "subtitle": ""}]},
        ensure_ascii=False), encoding="utf-8")
    res = B.scan(tmp_path, videos=["v"])
    assert res["verdict"] == "PASS"                 # strict 범위가 아니다
    assert res["out_of_scope_value_hits"]           # 그래도 기록은 남는다


@pytest.mark.skipif(not (ROOT / "label_kit/blindness_check.json").exists(),
                    reason="검사 산출물 없음")
def test_recorded_run_passed():
    res = json.loads((ROOT / "label_kit/blindness_check.json").read_text(encoding="utf-8"))
    assert res["verdict"] == "PASS"
    assert res["n_videos_checked"] == 8 and res["n_snippets"] > 1000
