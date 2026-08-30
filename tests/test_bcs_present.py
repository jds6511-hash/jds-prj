"""BCS presentation layer — 정본(canonical)과 표현(presentation)의 분리.

결정: `docs/finalization/BCS_CORE_FREEZE_2026-08-29.md`

```
정본    runs/bcs/bcs_v0_reparsed/<vid>.json    검증을 통과한 사실
표현    블록 목록 → Markdown · HWPX             형식만 바꾼다
```

**표현 계층은 새 사실을 만들지 않는다.** LLM을 부르지 않고, 생성된 문장을
고쳐 쓰지 않으며, 실패해도 정본을 무효로 만들지 않는다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import bcs as B                                                     # noqa: E402
import bcs_present as P                                             # noqa: E402

SEGS = [{"idx": i, "caption": f"장면 {i}", "raw_stt": f"발화 {i}",
         "clean_stt": f"발화 {i}" if i < 20 else "",
         "stt_status": "USABLE" if i < 20 else "EMPTY"} for i in range(30)]


def _doc(**over):
    eps = B.episode_spans([0, 10, 20], 30)
    for e, s in zip(eps, ["산길을 오른다.", "휴식한다.", "하산한다."]):
        e.update({"summary": s, "dialogue_note": "", "stt_cites": [],
                  "dropped": None, "parse_mode": "json"})
    eps[1].update({"dialogue_note": "쉬어가기로 한다.", "stt_cites": [11, 12]})
    eps[2]["dropped"] = "no_stt_cite"
    d = {"video_id": "vid", "schema": B.SCHEMA, "n_segments": 30,
         "run_kind": "bcs_v0_reparsed", "commit": "abc1234",
         "stt_status_counts": {"USABLE": 20, "EMPTY": 10},
         "episodes": eps,
         "provenance": {"effective_model_id": "Qwen/Q", "do_sample": False,
                        "effective_model_revision": "a09a35458c70"}}
    d.update(over)
    return d


# ── 표현 계층은 사실을 만들지 않는다 ────────────────────────────────────
def test_LLM을_부르지_않는다():
    src = (ROOT / "src" / "bcs_present.py").read_text(encoding="utf-8")
    for bad in ("make_llm", "llm(", "build_content_prompt", "generate("):
        assert bad not in src, bad


def test_생성된_문장을_고쳐_쓰지_않는다():
    d = _doc()
    blocks = P.sections(d, SEGS, seg_len=5)
    body = " ".join(b.get("text", "") + " ".join(b.get("items", []))
                    for b in blocks)
    for e in d["episodes"]:
        assert e["summary"] in body
    assert "쉬어가기로 한다." in body


# ── 구조 ────────────────────────────────────────────────────────────────
def test_필수_절이_순서대로_있다():
    h = [b["text"] for b in P.sections(_doc(), SEGS, 5) if b["kind"] == "h1"]
    assert h == ["영상 개요", "주요 흐름", "구간별 기록",
                 "특이사항 및 확인 불가", "근거 및 생성 정보"]


def test_대화가_없으면_대화_절을_넣지_않는다():
    """3I7처럼 유효 발화가 없는 영상에서는 빈 절을 만들지 않는다."""
    d = _doc()
    for e in d["episodes"]:
        e.update({"dialogue_note": "", "stt_cites": [], "dropped": None})
    labels = [b["text"] for b in P.sections(d, SEGS, 5) if b["kind"] == "label"]
    assert "대화 요지" not in labels
    assert "주요 내용" in labels


def test_시각은_구간에서_결정적으로_계산된다():
    blocks = P.sections(_doc(), SEGS, seg_len=5)
    times = [b["text"] for b in blocks if b["kind"] == "h2"]
    assert times[0].startswith("EP01") and "00:00~00:50" in times[0]
    assert "00:50~01:40" in times[1]


# ── 특이사항 — 숨기지 않는다 ────────────────────────────────────────────
def test_버려진_대화_주장을_특이사항에_적는다():
    blocks = P.sections(_doc(), SEGS, 5)
    i = [n for n, b in enumerate(blocks)
         if b["kind"] == "h1" and b["text"] == "특이사항 및 확인 불가"][0]
    tail = " ".join(b.get("text", "") + " ".join(b.get("items", []))
                    for b in blocks[i:])
    assert "EP03" in tail and "no_stt_cite" in tail


def test_제거된_오염_STT_수를_적는다():
    d = _doc(stt_status_counts={"USABLE": 4, "EMPTY": 140,
                                "REPEATED_CONTAMINATION": 20,
                                "OVERLAY_OR_URL": 9})
    tail = " ".join(b.get("text", "") + " ".join(b.get("items", []))
                    for b in P.sections(d, SEGS, 5))
    assert "REPEATED_CONTAMINATION" in tail and "29" in tail


def test_M9_산출물이_아님을_명시한다():
    """POST_M9_DELIVERABLE_SPEC의 산출물과 혼동되면 안 된다 — M9는 HOLD다."""
    tail = " ".join(b.get("text", "") for b in P.sections(_doc(), SEGS, 5))
    assert "M9" in tail and "제품 prototype" in tail


# ── 근거 — 인용된 구간만 ────────────────────────────────────────────────
def test_인용된_구간의_STT만_부록에_넣는다():
    blocks = P.sections(_doc(), SEGS, 5)
    tail = " ".join(b.get("text", "") + " ".join(b.get("items", []))
                    for b in blocks)
    assert "발화 11" in tail and "발화 12" in tail
    assert "발화 5" not in tail          # 인용되지 않은 구간


# ── Markdown ────────────────────────────────────────────────────────────
def test_markdown은_블록을_그대로_옮긴다():
    md = P.to_markdown(P.sections(_doc(), SEGS, 5))
    assert md.count("# 영상 개요") == 1
    assert "## EP01" in md and "산길을 오른다." in md


def test_무효_정본은_표현하지_않는다():
    d = _doc()
    d["episodes"][0]["summary"] = ""
    with pytest.raises(B.ViewError):
        P.sections(d, SEGS, 5)


def test_실제_산출물로_동작한다():
    p = ROOT / "runs/bcs/bcs_v0_reparsed/wonyi_geoje.json"
    if not p.exists():
        pytest.skip("산출물 없음")
    d = json.loads(p.read_text(encoding="utf-8"))
    md = P.to_markdown(P.sections(d, None, 5))
    assert "# 영상 개요" in md and "EP32" in md


def test_버려진_주장의_근거는_부록에_넣지_않는다():
    """기각한 주장의 인용을 근거로 제시하면 안 된다 (EP15 사례)."""
    d = _doc()
    d["episodes"][2].update({"dialogue_note": "", "stt_cites": [5, 6],
                             "dropped": "cite_not_usable_stt"})
    tail = " ".join(b.get("text", "") + " ".join(b.get("items", []))
                    for b in P.sections(d, SEGS, 5))
    assert "발화 11" in tail          # 살아남은 EP02의 근거
    assert "seg#5 " not in tail and "seg#6 " not in tail


def test_생성_모델과_decoding을_적는다():
    tail = " ".join(" ".join(b.get("items", [])) for b in P.sections(_doc(), SEGS, 5))
    assert "Qwen/Q" in tail and "greedy" in tail and "a09a35458c70" in tail
