"""AAR-v2 STEP A — boundary detectability probe.

사전등록: `docs/finalization/AARV2_STEP_A_PREREG_2026-08-28.md` (실행 전 동결).
지침 §22의 12개 항목 + 경계 guard.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import aarv2_step_a_boundary_probe as A                             # noqa: E402


# ── ① 코사인 거리 ────────────────────────────────────────────────────────
def test_코사인_거리():
    e = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    d = A.adjacent_distance(e)
    assert d[0] == pytest.approx(0.0, abs=1e-6)
    assert d[1] == pytest.approx(1.0, abs=1e-6)
    assert len(d) == 2, "transition 수는 구간 수 - 1"


# ── ② 빈 subtitle 처리는 결정적 ─────────────────────────────────────────
def test_양쪽_중_하나라도_공백이면_invalid():
    """공백 subtitle 임베딩은 sentinel이 아니라 공백 문자열의 임베딩이다 —
    그 거리는 의미가 없다."""
    assert A.valid_mask(["가", "", " ", "나"]).tolist() == [False, False, False]
    assert A.valid_mask(["가", "나", "다"]).tolist() == [True, True]


def test_캡션은_비공백이면_전부_유효():
    assert A.valid_mask(["a", "b", "c", "d"]).tolist() == [True, True, True]


# ── ③ 정규화는 결정적 ───────────────────────────────────────────────────
def test_percentile_정규화는_순위_기반이다():
    d = np.array([0.1, 0.9, 0.5])
    n = A.percentile_norm(d, np.array([True, True, True]))
    assert n.tolist() == pytest.approx([1 / 3, 1.0, 2 / 3])


def test_동점은_평균_순위():
    n = A.percentile_norm(np.array([0.5, 0.5]), np.array([True, True]))
    assert n.tolist() == pytest.approx([0.75, 0.75])


def test_무효_구간은_NaN으로_남는다():
    n = A.percentile_norm(np.array([0.1, 9.9, 0.5]), np.array([True, False, True]))
    assert np.isnan(n[1]) and n[0] == pytest.approx(0.5) and n[2] == pytest.approx(1.0)


def test_정규화는_반복해도_같다():
    d = np.array([0.3, 0.1, 0.2, 0.9])
    m = np.ones(4, bool)
    assert A.percentile_norm(d, m).tolist() == A.percentile_norm(d, m).tolist()


def test_primary_score는_유효한_채널만_평균한다():
    s = A.primary_score(np.array([0.2, np.nan, np.nan]),
                        np.array([0.6, 0.4, np.nan]))
    assert s[0] == pytest.approx(0.4)      # 둘 다 유효 → 평균
    assert s[1] == pytest.approx(0.4)      # sub 무효 → cap 단독
    assert np.isnan(s[2])                  # 둘 다 무효 → 후보 불가


# ── ④ K는 duration 규칙 ─────────────────────────────────────────────────
@pytest.mark.parametrize("n_seg,k", [(12, 1), (173, 14), (327, 27), (345, 29), (1, 1)])
def test_K는_duration에서만_나온다(n_seg, k):
    assert A.budget_k(n_seg, seg_len_sec=5) == k


def test_K는_GT를_인자로_받지_않는다():
    import inspect
    p = set(inspect.signature(A.budget_k).parameters)
    assert not (p & {"refs", "gt", "n_gt", "n_boundaries", "reference_events"})


# ── ⑤ top-K 선택은 결정적 ───────────────────────────────────────────────
def test_top_K는_점수_내림차순_동점은_인덱스_오름차순():
    s = np.array([0.5, 0.9, 0.5, 0.1])
    assert A.top_k(s, 3) == [1, 0, 2]


def test_NaN은_선택되지_않는다():
    s = np.array([0.5, np.nan, 0.2])
    assert A.top_k(s, 3) == [0, 2]


def test_NMS를_쓰지_않는다():
    """NMS radius는 하이퍼파라미터를 하나 더 만든다 — STEP B로 미룬다."""
    src = (ROOT / "scripts" / "aarv2_step_a_boundary_probe.py").read_text(encoding="utf-8")
    assert "def nms" not in src and "non_max" not in src


# ── ⑥ 균등 baseline 배치 ────────────────────────────────────────────────
def test_균등_baseline은_내부에_등간격():
    assert A.uniform_boundaries(400.0, 3) == pytest.approx([100.0, 200.0, 300.0])
    assert A.uniform_boundaries(60.0, 1) == pytest.approx([30.0])


def test_균등_baseline은_시작과_끝을_제외한다():
    b = A.uniform_boundaries(100.0, 4)
    assert min(b) > 0 and max(b) < 100.0


# ── ⑦ ±10초 매칭 ────────────────────────────────────────────────────────
def test_tolerance_안이면_hit():
    m = A.match_boundaries([100.0], [108.0], tol=10.0)
    assert m["n_matched"] == 1


def test_tolerance_밖이면_miss():
    assert A.match_boundaries([100.0], [111.0], tol=10.0)["n_matched"] == 0


def test_경계값은_hit이다():
    assert A.match_boundaries([100.0], [110.0], tol=10.0)["n_matched"] == 1


# ── ⑧⑨ 1:1 — 한쪽이 둘을 먹지 못한다 ────────────────────────────────────
def test_예측_하나가_GT_둘을_맞히지_못한다():
    """GT 최소 길이 2구간(10초) — τ=±10초에서 실제로 생길 수 있다."""
    m = A.match_boundaries([100.0, 108.0], [104.0], tol=10.0)
    assert m["n_matched"] == 1


def test_GT_하나가_예측_둘에_매칭되지_않는다():
    m = A.match_boundaries([100.0], [96.0, 104.0], tol=10.0)
    assert m["n_matched"] == 1


def test_최대_cardinality를_먼저_취한다():
    """총 거리만 줄이려 들면 짝을 덜 맺는 해가 이길 수 있다."""
    m = A.match_boundaries([100.0, 109.0], [100.0, 108.0], tol=10.0)
    assert m["n_matched"] == 2


# ── ⑩ 동점 결정성 ───────────────────────────────────────────────────────
def test_동점_매칭도_결정적():
    a = A.match_boundaries([100.0], [95.0, 105.0], tol=10.0)
    b = A.match_boundaries([100.0], [95.0, 105.0], tol=10.0)
    assert a["pairs"] == b["pairs"] and a["n_matched"] == 1


# ── ⑪ GT 수로 K를 정하지 않는다 (소스 수준) ─────────────────────────────
def test_K_계산_경로에_GT가_흐르지_않는다():
    import inspect
    src = inspect.getsource(A.budget_k)
    for bad in ("refs", "boundar", "gt"):
        assert bad not in src


# ── ⑫ secondary는 판정을 바꾸지 않는다 ──────────────────────────────────
def test_go_verdict는_secondary를_보지_않는다():
    import inspect
    src = inspect.getsource(A.go_verdict)
    for bad in ("subtitle_only", "caption_only", "secondary"):
        assert bad not in src


def test_GO는_세_조건_전부():
    ok = {"delta": 0.20, "n_better_or_equal": 6, "n_worse": 1}
    assert A.go_verdict(ok)["go"] is True


@pytest.mark.parametrize("key,bad,tag", [
    ("delta", 0.14, "A_delta>=0.15"),
    ("n_better_or_equal", 4, "B_better>=5"),
    ("n_worse", 3, "C_worse<=2"),
])
def test_하나라도_어기면_NO_GO(key, bad, tag):
    v = A.go_verdict({**{"delta": 0.20, "n_better_or_equal": 6, "n_worse": 1},
                      key: bad})
    assert v["go"] is False and tag in v["failed"]


def test_경계값은_통과():
    assert A.go_verdict({"delta": 0.15, "n_better_or_equal": 5,
                         "n_worse": 2})["go"] is True


def test_동결_상수():
    assert A.TOLERANCE_SEC == 10.0 and A.K_SECONDS_PER_BOUNDARY == 60
    assert A.GO_MIN_DELTA == 0.15 and A.GO_MIN_BETTER == 5 and A.GO_MAX_WORSE == 2
    assert A.PRIMARY == "mean(percentile_norm(d_sub), percentile_norm(d_cap))"


# ── GT 경계 구성 ────────────────────────────────────────────────────────
def test_contiguous면_공유_경계():
    ev = [{"span": [0, 52]}, {"span": [53, 70]}]
    assert A.gt_boundaries(ev, seg_len_sec=5) == [265.0]


def test_gap이면_중점():
    ev = [{"span": [0, 9]}, {"span": [20, 30]}]     # 공백 10~19
    assert A.gt_boundaries(ev, seg_len_sec=5) == [75.0]      # (50 + 100) / 2


def test_사건이_하나면_경계가_없다():
    assert A.gt_boundaries([{"span": [0, 172]}], seg_len_sec=5) == []


def test_중복_경계는_dedup된다():
    ev = [{"span": [0, 9]}, {"span": [10, 19]}, {"span": [10, 25]}]
    b = A.gt_boundaries(ev, seg_len_sec=5)
    assert b == sorted(set(b))


# ── 경계 guard ──────────────────────────────────────────────────────────
def test_생성_경로를_참조하지_않는다():
    src = (ROOT / "scripts" / "aarv2_step_a_boundary_probe.py").read_text(encoding="utf-8")
    for bad in ("import llm", "make_llm", "generate_report", "SentenceTransformer",
                "torch", "cuda", "embed_texts"):
        assert bad not in src, f"{bad}를 참조한다 — STEP A는 새 embedding을 만들지 않는다"


def test_아키텍처를_구현하지_않는다():
    """STEP A는 전제만 잰다 — proposal·merge·서술·조립을 만들지 않는다."""
    names = {n for n in dir(A) if not n.startswith("_")}
    for bad in ("propose_events", "merge_events", "describe_event",
                "assemble_report", "synthesize"):
        assert bad not in names


def test_경계_카운터():
    b = A.BOUNDARY
    assert b["new_labels"] == 0 and b["llm_calls"] == 0
    assert b["gpu_required"] is False and b["new_embeddings"] == 0
    assert b["aarv2_architecture_implemented"] is False
