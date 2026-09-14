from m3_generate import assign_subtitles

def _segs(n, dur=None):
    return [{"idx": i, "start": i * 5, "end": min(i * 5 + 5, dur or n * 5)}
            for i in range(n)]

def test_utterance_within_one_segment():
    segs = _segs(2)
    assign_subtitles([{"text": "안녕하세요", "t0": 1.0, "t1": 3.0}], segs)
    assert segs[0]["subtitle"] == "안녕하세요"
    assert segs[1]["subtitle"] == ""

def test_boundary_utterance_duplicated_both_sides():
    # 4~8초 발화: seg0(1s)·seg1(3s) 모두 걸침 → 양쪽 중복 포함 [DESIGN_SPEC 3-2, v2 8-1]
    segs = _segs(2)
    assign_subtitles([{"text": "경계 발화", "t0": 4.0, "t1": 8.0}], segs)
    assert "경계 발화" in segs[0]["subtitle"]
    assert "경계 발화" in segs[1]["subtitle"]

def test_multiple_utterances_ordered_and_joined():
    segs = _segs(1)
    assign_subtitles([{"text": "첫째", "t0": 0.5, "t1": 1.0},
                      {"text": "둘째", "t0": 2.0, "t1": 3.0}], segs)
    assert segs[0]["subtitle"] == "첫째 둘째"

def test_silent_segment_gets_empty_string():
    segs = _segs(3)
    assign_subtitles([], segs)
    assert all(s["subtitle"] == "" for s in segs)   # 무발화는 "" 정상 케이스
