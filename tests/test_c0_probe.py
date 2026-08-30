"""C0 관찰 스크립트 — 관찰 전용임을 코드로 고정한다."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import c0_boundary_signal_probe as C                                # noqa: E402


def test_임계나_채택_판단을_하지_않는다():
    src = (ROOT / "scripts" / "c0_boundary_signal_probe.py").read_text(
        encoding="utf-8")
    for bad in ("threshold =", "cutoff =", "min_gap", "smooth(",
                "reference_events", "gt_seg_idx", "make_llm"):
        assert bad not in src, bad
    # 하지 않는 것을 산출물에 명시한다
    for must in ("provider_adoption", "smoothing_tuning", "optimal_cutoff"):
        assert must in src, must


def test_인접거리는_코사인이고_첫_구간은_0이다():
    e = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    d = C.adjacent_distance(e)
    assert d[0] == 0.0
    assert abs(d[1] - 0.0) < 1e-9
    assert abs(d[2] - 1.0) < 1e-9


def test_국소최대는_cutoff없이_모양으로만_뽑는다():
    d = np.array([0.0, 0.1, 0.9, 0.1, 0.2, 0.05, 0.3])
    p = C.local_peaks(d, 1, 6, radius=2)
    assert 2 in p and 6 in p
    assert 3 not in p and 5 not in p


def test_백분위는_첫_구간을_분포에서_뺀다():
    d = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    assert C.percentile_rank(d, 4) == 0.75      # 4개 중 3개가 더 작다
    assert C.percentile_rank(d, 1) == 0.0
