"""Boundary-Content Split prototype v0.

결정: `docs/finalization/BCS_PROTOTYPE_SPEC_2026-08-29.md`
근거: `docs/finalization/M8_HIER_BOUNDARY_ABLATION_RESULT_2026-08-29.md`

원칙 하나만 구현한다.

```
경계    caption만 본다 — STT는 사건을 쪼갤 권한이 없다
내용    caption + 사용 가능한 STT — STT는 의미를 더할 권한만 갖는다
```

채점하지 않는다 — GT·C1/C2/C3·Event Recall 없음. 라벨은 은퇴했다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import bcs as B                                                     # noqa: E402

SEGS = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
         "subtitle": f"발화 {i}", "caption": f"장면 {i}"} for i in range(0, 30)]


# ── 배제 항목 ───────────────────────────────────────────────────────────
def test_GT나_은퇴한_지표를_쓰지_않는다():
    src = (ROOT / "src" / "bcs.py").read_text(encoding="utf-8")
    for bad in ("reference_events", "event_recall", "temporal_iou",
                "compression", "judge_model", "load_reference", "gt_seg_idx"):
        assert bad not in src, bad


def test_경계_수_상한을_두지_않는다():
    """HOLD 항목 — degeneracy는 탐지만 하고 자동 보정하지 않는다."""
    src = (ROOT / "src" / "bcs.py").read_text(encoding="utf-8")
    for bad in ("MAX_BOUNDARIES", "boundary_cap", "truncate_boundaries"):
        assert bad not in src, bad


# ── STT sanitation — 결정적 판정만 ──────────────────────────────────────
def test_반복_오염은_임계_이상에서만_걸린다():
    """실측 여유: 실제 발화 최다 반복 5회 · 오염 9·20·22회 (패널 18편)."""
    assert B.REPEAT_THRESHOLD == 8
    counts = {"다음 영상에서 만나요.": 20, "아 행복해 보인다. 반팔을 입고": 5}
    assert B.stt_status("다음 영상에서 만나요.", counts) == "REPEATED_CONTAMINATION"
    assert B.stt_status("아 행복해 보인다. 반팔을 입고", counts) == "USABLE"


def test_방송국_URL류는_1회_출현이어도_걸린다():
    """jissi_farm seg#209는 같은 오염 문자열이 1회만 나온다 — 반복으로 못 잡는다."""
    t = "마포구청 인터넷 방송국 홈페이지"
    assert B.stt_status(t, {t: 1}) == "OVERLAY_OR_URL"


def test_크레딧_환각과_외국문자를_걸러낸다():
    assert B.stt_status("한글자막 by 아무개", {}) == "CREDIT"
    assert B.stt_status("나무가 满了 숲이 보인다 中文字幕", {}) == "FOREIGN_SCRIPT"


@pytest.mark.parametrize("t", [
    "나 잡았어!!! 나 잡았어!!! 나 잡았어!!!",
    "넣어라, 넣어라 넣어라 언니 넣어라, 넣어라",
    "리셋네 리셋네 원이님! 아이돌! 빨리 빨리 빨리!",
    "계피 계피, 계피 계피 하고 저기 멀리 있다 그러면 아 블루투스",
])
def test_흥분한_실제_발화의_반복을_오염으로_보지_않는다(t):
    """`is_corrupted_caption`의 반복 규칙은 VLM 캡션용이다. geoje dry-run에서
    실제 발화 11건을 지웠다 — STT에는 쓰지 않는다."""
    assert B.stt_status(t, {t: 1}) == "USABLE"


def test_빈_자막과_정상_발화():
    assert B.stt_status("", {}) == "EMPTY"
    assert B.stt_status("물고기 진짜 많다. 왔어.", {}) == "USABLE"


def test_실제_발화를_지우지_않는다():
    """오탐이 곧 발화 삭제다 — 5회 반복되는 긴 실제 발화는 살아야 한다."""
    t = "이 호수가 영국 왕실의 이름을 따서 지은 루이스야."
    assert B.stt_status(t, {t: 5}) == "USABLE"


def test_sanitize_는_원본을_보존한다():
    segs = [{"idx": i, "subtitle": "다음 영상에서 만나요.", "caption": "a"}
            for i in range(9)]
    out = B.sanitize_stt(segs)
    assert all(o["raw_stt"] == "다음 영상에서 만나요." for o in out)
    assert all(o["clean_stt"] == "" for o in out)
    assert all(o["stt_status"] == "REPEATED_CONTAMINATION" for o in out)


# ── 경계 pass는 caption만 본다 ──────────────────────────────────────────
def test_경계_프롬프트에_자막이_없다():
    p = B.build_boundary_prompt(SEGS[:5])
    assert "자막" not in p
    for i in range(5):
        assert f"발화 {i}" not in p and f"장면 {i}" in p


def test_경계_프롬프트는_실측한_조건과_동일하다():
    """ablation이 지지한 것은 그 프롬프트다. 새로 쓰지 않고 그대로 쓴다."""
    import m8_hier as H
    assert B.build_boundary_prompt(SEGS[:5]) == \
        H.build_atomic_boundary_prompt(SEGS[:5], caption_only=True)


# ── degeneracy: 탐지만, 보정 없음 ───────────────────────────────────────
def test_연속정수_run은_degenerate로_표시된다():
    b = list(range(254, 280))
    assert B.boundary_output_status(b) == "DEGENERATE"


def test_정상_간격은_ok다():
    assert B.boundary_output_status([220, 227, 229, 238, 249]) == "OK"


def test_degenerate여도_경계를_버리거나_자르지_않는다():
    b = list(range(10, 30))
    kept = B.episode_spans(b, 60)
    assert len(kept) == 21          # 코드가 항상 넣는 0 + 모델 경계 20개
    assert kept[0]["start_seg"] == 0 and kept[-1]["end_seg"] == 59


# ── span 구성은 코드 · 겹침·구멍 불가 ───────────────────────────────────
def test_episode는_전체를_빈틈없이_덮는다():
    eps = B.episode_spans([0, 10, 25], 30)
    assert [(e["start_seg"], e["end_seg"]) for e in eps] == \
        [(0, 9), (10, 24), (25, 29)]
    assert all(e["episode_id"] == f"EP{i:02d}" for i, e in enumerate(eps, 1))


def test_episode에_support_span과_anchor가_붙는다():
    e = B.episode_spans([0, 10], 30)[1]
    assert e["support_span"] == {"start_seg": 10, "end_seg": 29}
    assert e["anchor_cites"] == [10, 19, 29]


# ── 내용 pass: STT는 의미만 더한다 ──────────────────────────────────────
def test_내용_프롬프트는_사용가능한_STT만_넣는다():
    segs = [{"idx": 0, "caption": "해변", "clean_stt": "낚시 안 할래",
             "stt_status": "USABLE"},
            {"idx": 1, "caption": "바다", "clean_stt": "",
             "stt_status": "REPEATED_CONTAMINATION",
             "raw_stt": "다음 영상에서 만나요."}]
    p = B.build_content_prompt(segs)
    assert "낚시 안 할래" in p
    assert "다음 영상에서 만나요" not in p


def test_요약은_JSON이_아니어도_받는다():
    """v3·v4는 형식 하나로 무효가 났다. 표기는 받아들이되 구조는 코드가 갖는다."""
    assert B.parse_content("두 여성이 해변에서 대화한다.")["summary"] == \
        "두 여성이 해변에서 대화한다."
    d = B.parse_content('{"summary": "산길을 오른다.", '
                        '"dialogue_note": "쉬기로 한다.", "stt_cites": [3]}')
    assert d["summary"] == "산길을 오른다."
    assert d["dialogue_note"] == "쉬기로 한다."
    assert d["stt_cites"] == [3]


# ── citation 검증 — 이 층에 이빨을 준다 ─────────────────────────────────
def _segs_with(usable_idx):
    return [{"idx": i, "caption": "c",
             "clean_stt": "말" if i in usable_idx else "",
             "stt_status": "USABLE" if i in usable_idx else "EMPTY"}
            for i in range(30)]


def test_STT_claim은_사용가능한_구간을_인용해야_남는다():
    ep = {"start_seg": 0, "end_seg": 29}
    c = {"summary": "s", "dialogue_note": "결정했다", "stt_cites": [5]}
    out = B.verify_content(c, ep, _segs_with({5}))
    assert out["dialogue_note"] == "결정했다"
    assert out["stt_cites"] == [5]
    assert out["dropped"] is None


@pytest.mark.parametrize("cites,why", [
    ([], "no_stt_cite"),
    ([7], "cite_not_usable_stt"),
    ([99], "cite_outside_span"),
])
def test_근거가_없거나_오염이면_dialogue_note를_버린다(cites, why):
    ep = {"start_seg": 0, "end_seg": 29}
    c = {"summary": "s", "dialogue_note": "결정했다", "stt_cites": cites}
    out = B.verify_content(c, ep, _segs_with({5}))
    assert out["dialogue_note"] == ""
    assert out["dropped"] == why


def test_요약은_STT_인용을_요구하지_않는다():
    """summary는 caption만으로도 성립한다 — 3I7 같은 caption-dominant 사례."""
    ep = {"start_seg": 0, "end_seg": 29}
    out = B.verify_content({"summary": "걷는다", "dialogue_note": "",
                            "stt_cites": []}, ep, _segs_with(set()))
    assert out["summary"] == "걷는다"
    assert out["dropped"] is None


# ── 검증·렌더 ───────────────────────────────────────────────────────────
def _doc(summaries):
    eps = B.episode_spans([0, 10, 20], 30)
    for e, s in zip(eps, summaries):
        e.update({"summary": s, "dialogue_note": "", "stt_cites": [],
                  "dropped": None})
    return {"video_id": "v", "schema": B.SCHEMA, "n_segments": 30,
            "episodes": eps}


def test_요약이_비면_문서가_무효다():
    assert B.validate(_doc(["a", "b", "c"]), "v") == []
    assert "episode_no_summary" in B.validate(_doc(["a", "", "c"]), "v")


def test_렌더는_요약_없는_문서를_거부한다():
    with pytest.raises(B.ViewError):
        B.render(_doc(["a", "", "c"]), seg_len=5)


def test_렌더는_구간을_한_번씩만_적는다():
    md = B.render(_doc(["a", "b", "c"]), seg_len=5)
    assert md.count("EP01") == 1 and md.count("EP02") == 1
    assert "00:00" in md and "근거" in md
