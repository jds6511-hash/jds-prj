from m5_search import Result
from m7_demo import format_output

def test_format_output_contract():
    ranked = [Result(6, 0.9, 30, 35), Result(7, 0.8, 35, 40), Result(2, 0.7, 10, 15.5)]
    segments = {2: {"subtitle": "셋"}, 6: {"subtitle": "여섯"}, 7: {"subtitle": "일곱"}}
    segs = [dict(idx=i, subtitle=segments.get(i, {}).get("subtitle", "")) for i in range(8)]
    out = format_output(ranked, segs, k=3)
    assert out["jump_to"] == 30                       # int
    assert out["subtitle"] == "여섯"
    assert out["windows"] == [[30, 35], [35, 40], [10, 15]]   # 정수 초 [v2 6장]
    assert all(isinstance(v, int) for w in out["windows"] for v in w)
