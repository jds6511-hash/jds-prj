import math
from m1_preprocess import make_segments

def test_make_segments_basic():
    segs = make_segments(14.0)
    assert len(segs) == math.ceil(14.0 / 5) == 3
    assert [s["start"] for s in segs] == [0, 5, 10]
    assert segs[-1]["end"] == 14.0                    # end = min(start+5, duration)
    assert segs[0]["end"] == 5

def test_make_segments_exact_multiple():
    segs = make_segments(15.0)
    assert len(segs) == 3 and segs[-1]["end"] == 15.0

def test_make_segments_idx_contiguous():
    segs = make_segments(632.4)
    assert len(segs) == 127                            # ceil(632.4/5)
    assert all(s["idx"] == i and s["start"] == i * 5 for i, s in enumerate(segs))
    assert abs(segs[-1]["end"] - 632.4) < 1e-9
