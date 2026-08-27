"""C1 파국 판정 — 규격은 `docs/finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md` §1.

세 유형 · 3-state · **병합 전 원본에서 반복 판정.** 새 임계(비한글 비율·유사도)를
만들지 않는다는 것도 테스트가 지킨다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import m8_c1 as C                                                  # noqa: E402
import m8_metrics as M                                             # noqa: E402
import m8_report                                                   # noqa: E402


def ev(name, desc, span=(0, 5)):
    return {"event": name, "span": list(span), "evidence_segments": [span[0]],
            "description": desc}


def raw(events):
    return json.dumps(events, ensure_ascii=False)


def rep_of(raw_chunks, sentences=None, **kw):
    """구조 경로(`generate_report_structured`)가 내는 형태의 최소 리포트."""
    d = {"map_raw_outputs": list(raw_chunks), "chunk_retries": [],
         "sentences": sentences if sentences is not None else [{"sent_id": 0}],
         "events": [], "rejected": [], "truncated_tail": None, "raw_output": ""}
    d.update(kw)
    return d


# ---------------------------------------------------------------- 3-state

def test_status_enum_is_exactly_three():
    assert C.STATUSES == ("PRESENT", "ABSENT", "UNCLEAR")
    assert C.C1_KINDS == ("language_drift", "early_stop", "repetition_loop")


def test_finding_shape_is_status_plus_evidence():
    f = C.inspect_video(rep_of([raw([ev("등산", "산을 오른다")])]))
    assert set(f) == set(C.C1_KINDS)
    for k in C.C1_KINDS:
        assert set(f[k]) == {"status", "evidence"}
        assert f[k]["status"] in C.STATUSES


def test_unknown_status_is_refused():
    with pytest.raises(C.C1SpecError):
        C.video_status({"language_drift": {"status": "MAYBE", "evidence": []},
                        "early_stop": {"status": "ABSENT", "evidence": []},
                        "repetition_loop": {"status": "ABSENT", "evidence": []}})


def test_missing_kind_is_refused():
    """유형이 빠진 채 판정하면 그 유형은 조용히 ABSENT가 된다."""
    with pytest.raises(C.C1SpecError):
        C.video_status({"early_stop": {"status": "ABSENT", "evidence": []}})


# ---------------------------------------------------------------- 반복 루프

def test_repetition_three_consecutive_identical_is_present():
    e = ev("포장", "상자를 포장한다")
    f = C.inspect_video(rep_of([raw([e, e, e])]))
    assert f["repetition_loop"]["status"] == "PRESENT"
    assert f["repetition_loop"]["evidence"]


def test_repetition_two_consecutive_is_not_catastrophic():
    e = ev("포장", "상자를 포장한다")
    f = C.inspect_video(rep_of([raw([e, e])]))
    assert f["repetition_loop"]["status"] == "ABSENT"


def test_repetition_survives_merge_erasure():
    """**핵심.** `_merge_events`가 합쳐 없애도 C1은 원본에서 잡는다.

    병합 후 산출물에서 세면 파이프라인이 지워 준 파국을 PASS로 읽는다.
    """
    e = ev("등산", "산을 오른다", (0, 5))
    merged = m8_report.merge_events([dict(e), dict(e), dict(e)])
    assert len(merged) == 1                          # 병합이 실제로 지운다
    rep = rep_of([raw([e, e, e])], sentences=m8_report.events_to_sentences(merged),
                 events=merged)
    assert C.inspect_video(rep)["repetition_loop"]["status"] == "PRESENT"


def test_repetition_normalizes_whitespace_only():
    """정규화는 공백까지다. **의미 유사도 임계를 만들지 않는다.**"""
    a = ev("포장", "상자를  포장한다")
    b = ev("포장", "상자를 포장한다 ")
    f = C.inspect_video(rep_of([raw([a, b, a])]))
    assert f["repetition_loop"]["status"] == "PRESENT"


def test_repetition_does_not_flag_paraphrase():
    f = C.inspect_video(rep_of([raw([
        ev("포장", "상자를 포장한다"),
        ev("포장", "상자를 싸고 있다"),
        ev("포장", "포장 작업을 계속한다")])]))
    assert f["repetition_loop"]["status"] == "ABSENT"


def test_repetition_run_may_cross_chunk_boundary():
    e = ev("포장", "상자를 포장한다")
    f = C.inspect_video(rep_of([raw([e, e]), raw([e])]))
    assert f["repetition_loop"]["status"] == "PRESENT"


def test_repetition_unclear_when_no_raw_output_kept():
    """원본이 없으면 **판정 불가**다. 없는 것을 ABSENT로 쓰면 안 된다."""
    f = C.inspect_video(rep_of([]))
    assert f["repetition_loop"]["status"] == "UNCLEAR"


# ---------------------------------------------------------------- 조기 종료

def test_early_stop_from_truncated_tail():
    f = C.inspect_video(rep_of([raw([ev("A", "가")])], truncated_tail="잘린 꼬리"))
    assert f["early_stop"]["status"] == "PRESENT"


def test_early_stop_from_unrecovered_chunk():
    """청크 재생성이 실패했으면 그 구간 출력이 만들어지지 않았다."""
    f = C.inspect_video(rep_of([raw([ev("A", "가")])],
                               chunk_retries=[{"chunk": 0, "recovered": False}]))
    assert f["early_stop"]["status"] == "PRESENT"


def test_early_stop_from_empty_sentences():
    f = C.inspect_video(rep_of([raw([ev("A", "가")])], sentences=[]))
    assert f["early_stop"]["status"] == "PRESENT"


def test_early_stop_absent_on_complete_run():
    f = C.inspect_video(rep_of([raw([ev("A", "가나다")])],
                               chunk_retries=[{"chunk": 0, "recovered": True}]))
    assert f["early_stop"]["status"] == "ABSENT"


# ---------------------------------------------------------------- 언어 이탈

def test_language_drift_absent_when_every_unit_has_hangul():
    """고유명사·짧은 인용·화면 문자·단일 외래어는 drift가 아니다 —
    **한글이 있는 문장 안에** 있으므로 후보로도 올라오지 않는다."""
    f = C.inspect_video(rep_of([raw([
        ev("도착", "Banff 국립공원 입구에 도착한다"),
        ev("간판", '간판에 "OPEN"이라고 적혀 있다'),
        ev("주문", "카페에서 아메리카노를 주문한다")])]))
    assert f["language_drift"]["status"] == "ABSENT"
    assert f["language_drift"]["evidence"] == []


def test_language_drift_candidate_is_unclear_not_present():
    """한글이 아예 없는 완결 단위는 **후보**다. 사람이 판정한다 —
    화면 문자를 그대로 옮긴 것일 수도 있다."""
    f = C.inspect_video(rep_of([raw([
        ev("A", "The man climbs the mountain slowly."),
        ev("B", "산을 오른다")])]))
    assert f["language_drift"]["status"] == "UNCLEAR"
    assert f["language_drift"]["evidence"]


def test_language_drift_human_adjudication_overrides_candidate():
    rep = rep_of([raw([ev("A", "The man climbs the mountain.")])])
    assert C.inspect_video(rep, language_drift="PRESENT")["language_drift"]["status"] \
        == "PRESENT"
    assert C.inspect_video(rep, language_drift="ABSENT")["language_drift"]["status"] \
        == "ABSENT"


def test_language_drift_human_value_is_validated():
    with pytest.raises(C.C1SpecError):
        C.inspect_video(rep_of([]), language_drift="NO")


def test_language_drift_uses_no_ratio_threshold():
    """비한글 **비율** 임계를 만들지 않았다는 것을 소스로 확인한다."""
    src = (ROOT / "src" / "m8_c1.py").read_text(encoding="utf-8")
    for banned in ("0.1", "0.2", "ratio", "similarity", "cosine", "embed"):
        assert banned not in src


# ---------------------------------------------------------------- 영상 판정

def test_video_status_present_wins_over_unclear():
    f = {"language_drift": {"status": "UNCLEAR", "evidence": []},
         "early_stop": {"status": "PRESENT", "evidence": []},
         "repetition_loop": {"status": "ABSENT", "evidence": []}}
    assert C.video_status(f) == "PRESENT"


def test_video_status_unclear_when_any_unclear():
    f = {k: {"status": "ABSENT", "evidence": []} for k in C.C1_KINDS}
    f["language_drift"]["status"] = "UNCLEAR"
    assert C.video_status(f) == "UNCLEAR"


def test_video_status_absent_only_when_all_absent():
    f = {k: {"status": "ABSENT", "evidence": []} for k in C.C1_KINDS}
    assert C.video_status(f) == "ABSENT"


# ---------------------------------------------------------------- 관문 집계

def test_c1_verdict_passes_only_on_all_absent():
    out = M.c1_verdict(["ABSENT"] * 8)
    assert out["passed"] is True and out["n_videos"] == 8
    assert out["n_catastrophic_videos"] == 0


def test_c1_verdict_counts_videos_not_sentences():
    out = M.c1_verdict(["ABSENT", "PRESENT", "ABSENT", "PRESENT"])
    assert out["n_catastrophic_videos"] == 2 and out["n_videos"] == 4
    assert out["passed"] is False


def test_c1_verdict_refuses_pass_on_unclear():
    """**UNCLEAR는 PASS로 떨어지지 않는다.** 판정 불가는 통과가 아니다."""
    out = M.c1_verdict(["ABSENT"] * 7 + ["UNCLEAR"])
    assert out["passed"] is None
    assert out["n_unclear_videos"] == 1


def test_c1_verdict_present_beats_unclear_for_fail():
    """UNCLEAR가 섞여도 PRESENT가 하나 있으면 이미 FAIL이다."""
    out = M.c1_verdict(["PRESENT", "UNCLEAR"] + ["ABSENT"] * 6)
    assert out["passed"] is False


def test_c1_verdict_rejects_unknown_status():
    with pytest.raises(M.GateSpecError):
        M.c1_verdict(["ABSENT", "MAYBE"])


def test_c1_verdict_accepts_findings_dicts():
    f = {k: {"status": "ABSENT", "evidence": []} for k in C.C1_KINDS}
    assert M.c1_verdict([f] * 8)["passed"] is True


def test_c1_threshold_stays_zero():
    assert M.c1_verdict(["ABSENT"] * 8)["threshold"] == 0
    assert M.c1_verdict(["PRESENT"] + ["ABSENT"] * 7)["passed"] is False
