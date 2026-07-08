import json
from m8_report import build_map_prompt, build_reduce_prompt, parse_citations, generate_report, save_report

def _segs(n):
    return [{"idx": i, "start": i * 5, "end": i * 5 + 5,
             "subtitle": f"자막{i}", "caption": f"캡션{i}"} for i in range(n)]

def test_map_prompt_contains_rules_and_segments():
    p = build_map_prompt(_segs(2))
    assert "[seg#N]" in p and "[seg#0]" in p and "[seg#1]" in p
    assert "추측" in p                                 # 규칙 2 [13-1]
    assert "자막0" in p and "캡션1" in p

def test_reduce_prompt_forbids_new_facts():
    p = build_reduce_prompt(["부분1", "부분2"])
    assert "새로운 사실" in p and "부분1" in p         # [13-2]

def test_parse_citations():
    text = "- 화자가 재료를 준비한다 [seg#6, seg#7]\n- 근거 없는 문장\n- 요리를 시작한다 [seg#9]"
    sents = parse_citations(text)
    assert [s["cites"] for s in sents] == [[6, 7], [], [9]]
    assert sents[0]["sent_id"] == 0
    assert sents[1]["cites"] == []                     # 저장은 하되 자동 ungrounded [15-1]

def test_generate_report_single_call_when_small():
    calls = []
    def llm(prompt):
        calls.append(prompt)
        return "- 사건 [seg#0]"
    rep = generate_report(_segs(3), llm, chunk_size=60, overlap=5)
    assert len(calls) == 1                             # n<=chunk_size → 단일 호출
    assert rep["sentences"][0]["cites"] == [0]
    assert rep["raw_output"] == "- 사건 [seg#0]"      # raw 보존

def test_generate_report_map_reduce_and_subset_check():
    def llm(prompt):
        if "부분 리포트" in prompt:                    # reduce 호출
            return "- 통합 사건 [seg#1]\n- 유령 인용 [seg#99]"
        return "- 부분 사건 [seg#1]"                   # map 호출
    rep = generate_report(_segs(10), llm, chunk_size=4, overlap=1)
    cites = [s["cites"] for s in rep["sentences"]]
    assert [1] in cites
    # reduce의 [seg#99]는 map 인용 집합에 없음 → 걸러짐 [13-2 안전장치]
    assert [99] not in cites

def test_save_report_preserves_raw_output_on_range_violation(tmp_path):
    # map 단계 환각(reduce⊆map 검사를 통과하는 out-of-range 인용)이 있어도
    # report.json은 먼저 저장되고, assert는 그 뒤에 실패해야 한다. [final-review Finding 1]
    out = tmp_path / "report.json"
    rep = {"sentences": [{"sent_id": 0, "text": "유령 인용 [seg#999]", "cites": [999]}],
           "raw_output": "- 유령 인용 [seg#999]", "map_raw_outputs": []}
    cfg = {"report_model": "stub-model", "map_chunk_size": 60}
    try:
        save_report(out, "v1", cfg, rep, n=3)
        assert False, "범위 위반인데 AssertionError가 발생하지 않음"
    except AssertionError:
        pass
    assert out.exists()                                 # report.json 소실되지 않음
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["raw_output"] == "- 유령 인용 [seg#999]"  # raw_output 보존
