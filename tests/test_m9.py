import pytest
from m9_report_eval import eval_report, check_judge_config, judge_grounded

def _segs(n):
    return [{"idx": i, "start": i * 5, "end": i * 5 + 5,
             "subtitle": f"자막{i}", "caption": f"캡션{i}"} for i in range(n)]

def _report(sent_specs):
    return {"video_id": "v", "sentences": [
        {"sent_id": i, "text": t, "cites": c} for i, (t, c) in enumerate(sent_specs)]}

def test_uncited_sentence_auto_ungrounded_without_judge_call():
    calls = []
    judge = lambda prompt: (calls.append(prompt) or '{"match": true}')
    rep = _report([("근거 없는 문장", [])])
    out = eval_report(rep, _segs(3), gt_seg_indices=[0], judge=judge)
    assert out["per_sentence"][0]["grounded"] is False   # 자동 ungrounded [15-1]
    # cites=[] 문장은 judge 호출을 유발하지 않으므로 coverage 1회만 호출됨
    # [m8m9-prompt-critique B-8: 무의미 assert 단순화]
    assert len(calls) == 1

def test_rates_computed():
    # coverage 호출은 "언급했는지"로 식별, 세그먼트 헤더(idx)로만 판정
    # [m8m9-prompt-critique A-1: fake judge가 리포트 본문의 "seg#0"에 반응해
    #  seg1도 covered 처리되던 결함을 수정]
    def judge(prompt):
        if "언급했는지" in prompt:                       # coverage 호출
            return '{"match": true}' if "(idx 0)" in prompt else '{"match": false}'
        return '{"match": true}'                          # groundedness 호출
    rep = _report([("사건 [seg#0]", [0]), ("무근거", [])])
    out = eval_report(rep, _segs(3), gt_seg_indices=[0, 1], judge=judge)
    assert out["groundedness_rate"] == 0.5               # 2문장 중 1개 grounded
    assert out["coverage_rate"] == 0.5                   # gt 2개 중 1개 커버

def test_judge_grounded_conservative_on_parse_failure():
    judge = lambda prompt: "잘 모르겠습니다"              # JSON 아님 → 보수 판정 false
    ok = judge_grounded({"text": "문장", "cites": [0]}, _segs(1), judge)
    assert ok is False                                    # [v2 17-4]

def test_verdict_accepts_quoted_value():
    # [m8m9-prompt-critique B-5] {"match": "true"} 처럼 값이 따옴표로 감싸인 변형 허용
    judge = lambda prompt: '{"match": "true"}'
    ok = judge_grounded({"text": "문장", "cites": [0]}, _segs(1), judge)
    assert ok is True

def test_judge_parse_ok_flag_recorded():
    # [m8m9-prompt-critique B-6] judge 파싱 실패를 결과에 기록 (truncation 편향 진단용)
    rep = _report([("근거 있음 [seg#0]", [0])])
    ok_judge = lambda prompt: '{"match": true}'
    out_ok = eval_report(rep, _segs(3), gt_seg_indices=[0], judge=ok_judge)
    assert out_ok["per_sentence"][0]["judge_parse_ok"] is True

    fail_judge = lambda prompt: "잘 모르겠습니다"
    out_fail = eval_report(rep, _segs(3), gt_seg_indices=[0], judge=fail_judge)
    assert out_fail["per_sentence"][0]["judge_parse_ok"] is False

def test_same_model_judge_guard():
    cfg = {"report_model": "Qwen/Qwen2.5-7B-Instruct",
           "judge_model": "Qwen/Qwen2.5-7B-Instruct", "same_model_judge": False}
    with pytest.raises(ValueError, match="same_model_judge"):
        check_judge_config(cfg)
    cfg["same_model_judge"] = True
    check_judge_config(cfg)                               # 명시하면 통과
    cfg2 = {"report_model": "Qwen/Qwen2.5-7B-Instruct", "judge_model": None,
            "same_model_judge": False}
    with pytest.raises(ValueError, match="judge_model"):
        check_judge_config(cfg2)
