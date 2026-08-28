"""M8-v2 STEP 0.5 — rejected-candidate rescue reachability pilot.

지침 §20의 8개 항목을 그대로 옮긴다. 이 도구는 **생성하지 않는다** —
LLM 0 · GPU 0 · 새 라벨 0이고, 고치는 것은 `evidence` 길이 하나뿐이다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m8_report                                                    # noqa: E402
import m8v2_step05_rejected_rescue as R                             # noqa: E402

CHUNK = [{"idx": i} for i in range(0, 60)]
DESC = ("배가 부두에 닿자 사람들이 내려 짐을 옮기기 시작했고, 상인은 그물을 정리하며 "
        "오늘 잡은 것을 늘어놓았다. 아이들은 방파제 끝까지 뛰어갔다가 되돌아왔다.")


def _cand(ev, span=(0, 30), desc=DESC):
    return {"event": "사건", "span": list(span), "evidence_segments": list(ev),
            "description": desc}


# ── ① 정확히 4개면 대상이 아니다 ─────────────────────────────────────────
def test_evidence가_4개면_rescue_대상이_아니다():
    kept, rej = m8_report.validate_events([_cand([0, 1, 2, 3])], CHUNK)
    assert kept and not rej
    assert R.eligible({"reason": "no_segments"}) is False


def test_eligible은_too_many_evidence만이다():
    assert R.eligible({"reason": "too_many_evidence"}) is True
    for other in ("evidence_outside_span", "thin_description", "bad_span",
                  "duplicate_evidence", "foreign_language", "seg_out_of_range"):
        assert R.eligible({"reason": other}) is False


# ── ② 5개 + too_many_evidence 단독 → 4개 결정적 보존 ─────────────────────
def test_5개_후보는_생성_순서_앞_4개만_남는다():
    c = _cand([9, 3, 7, 1, 5])
    r = R.repair(c)
    assert r["evidence_segments"] == [9, 3, 7, 1]
    assert r["rescue"]["dropped"] == [5]
    assert r["rescue"]["rule"] == R.TRUNCATION_RULE


# ── ③ 같은 후보를 다시 돌리면 같은 결과 ──────────────────────────────────
def test_반복_실행은_같은_결과를_낸다():
    c = _cand([9, 3, 7, 1, 5])
    assert R.repair(c)["evidence_segments"] == R.repair(c)["evidence_segments"]


def test_repair는_evidence_외에는_아무것도_바꾸지_않는다():
    c = _cand([9, 3, 7, 1, 5], span=(2, 40), desc="서술 " * 40)
    r = R.repair(c)
    for k in ("event", "span", "description"):
        assert r[k] == c[k]
    assert c["evidence_segments"] == [9, 3, 7, 1, 5], "원본을 변형했다"


# ── ④ 다른 사유가 함께 있으면 rescue하지 않는다 ──────────────────────────
def test_다른_사유가_함께면_STILL_REJECTED로_남는다():
    """`validate_events`는 elif 체인이라 뒤 검사는 평가된 적이 없다. 그래서
    '고쳤다고 치고' 통과시키지 않고 **실제 validator를 다시 태운다**."""
    c = _cand([0, 1, 99, 2, 3], span=(0, 30))       # 99는 청크 밖 · 앞 4개에 든다
    st, reason, _ = R.revalidate(R.repair(c), CHUNK)
    assert st == "STILL_REJECTED" and reason == "seg_out_of_range"


def test_중복_evidence도_구제되지_않는다():
    c = _cand([1, 1, 2, 3, 4])
    st, reason, _ = R.revalidate(R.repair(c), CHUNK)
    assert st == "STILL_REJECTED" and reason == "duplicate_evidence"


# ── ⑤ 잘라도 여전히 무효면 거부 ─────────────────────────────────────────
def test_서술이_얇으면_잘라도_거부된다():
    c = _cand([0, 1, 2, 3, 4], desc="짧다")
    st, reason, _ = R.revalidate(R.repair(c), CHUNK)
    assert st == "STILL_REJECTED" and reason == "thin_description"


def test_유효해지면_VALID이고_사건이_나온다():
    c = _cand([0, 5, 10, 15, 20])
    st, reason, ev = R.revalidate(R.repair(c), CHUNK)
    assert st == "VALID" and reason is None
    assert ev["evidence_segments"] == sorted([0, 5, 10, 15])


# ── ⑥ baseline accepted event는 변하지 않는다 ───────────────────────────
def test_rescue는_ADD_ONLY다():
    b0 = [{"event": "a", "span": [0, 10], "evidence_segments": [0, 1],
           "description": "x"}]
    r1 = R.add_only(b0, [{"event": "b", "span": [20, 30],
                          "evidence_segments": [20], "description": "y"}])
    assert r1[:len(b0)] == b0 and len(r1) == 2
    assert b0 == [{"event": "a", "span": [0, 10], "evidence_segments": [0, 1],
                   "description": "x"}], "B0을 건드렸다"


def test_재병합하지_않는다():
    """`merge_events`를 다시 돌리면 B0 event의 span이 움직일 수 있다 — §8 위반."""
    src = (ROOT / "scripts" / "m8v2_step05_rejected_rescue.py").read_text(encoding="utf-8")
    assert "merge_events(" not in src


# ── ⑦ GT 매칭은 동결된 matcher를 그대로 쓴다 ────────────────────────────
def test_동결_matcher를_쓴다():
    import inspect
    assert "M.match_events" in inspect.getsource(R.newly_matched)


def test_newly_matched는_B0에서_미매칭이던_것만_센다():
    refs = [{"span": [0, 5]}, {"span": [40, 45]}]
    b0 = [{"span": [0, 5]}]
    r1 = b0 + [{"span": [40, 45]}]
    got = R.newly_matched(refs, b0, r1)
    assert got["newly_matched_idx"] == [1]
    assert got["b0_unmatched_idx"] == [1]


def test_새_임계나_수동_매핑을_만들지_않는다():
    src = (ROOT / "scripts" / "m8v2_step05_rejected_rescue.py").read_text(encoding="utf-8")
    for bad in ("iou_threshold", "manual_map", "IOU_THETA", "temporal_iou("):
        assert bad not in src


# ── ⑧ GT를 보고 evidence를 고르는 경로가 없다 ───────────────────────────
def test_repair는_GT를_인자로_받지_않는다():
    import inspect
    params = set(inspect.signature(R.repair).parameters)
    assert not (params & {"refs", "gt", "unmatched", "reference_events"})


def test_truncation_rule은_하나로_동결돼_있다():
    """여러 규칙을 시험하고 제일 좋은 것을 고르면 rule shopping이다."""
    assert R.TRUNCATION_RULE == "generation_order_first_4"
    assert R.MAX_EVIDENCE == m8_report.MAX_EVIDENCE_PER_EVENT == 4


# ── 경계 guard (§18) ────────────────────────────────────────────────────
def test_생성_경로를_참조하지_않는다():
    src = (ROOT / "scripts" / "m8v2_step05_rejected_rescue.py").read_text(encoding="utf-8")
    for bad in ("import llm", "make_llm", "generate_report", "consolidate",
                "torch", "cuda"):
        assert bad not in src, f"{bad}를 참조한다"


def test_경계_카운터가_산출물에_박힌다():
    b = R.BOUNDARY
    assert b["new_labels"] == 0 and b["llm_calls"] == 0
    assert b["generation_calls"] == 0 and b["gpu_required"] is False


def test_GO_기준은_상수로_동결돼_있다():
    assert R.GO_MIN_RECOVERED == 5 and R.GO_MIN_VIDEOS == 2
    assert R.GO_MAX_VIDEO_SHARE == 0.60


@pytest.mark.parametrize("m,go", [
    ({"newly_matched_gt": 5, "videos_recovered": 2, "max_video_share": 0.60}, True),
    ({"newly_matched_gt": 4, "videos_recovered": 3, "max_video_share": 0.30}, False),
    ({"newly_matched_gt": 6, "videos_recovered": 1, "max_video_share": 1.00}, False),
    ({"newly_matched_gt": 6, "videos_recovered": 2, "max_video_share": 0.67}, False),
])
def test_GO_판정(m, go):
    assert R.go_verdict(m)["go"] is go


def test_trigger는_T2_0_7로_고정된다():
    """§23 — STEP 0.5 결과를 보고 threshold를 바꾸지 않는다."""
    assert R.TRIGGER == {"family": "T2", "threshold": 0.7, "id": "T2@0.7"}
