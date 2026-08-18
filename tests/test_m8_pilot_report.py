"""M8 pilot 보고 지표 — **결과를 열기 전에** 고정한다.

M8 FULL 산출물(`m8pilot_0818d`)을 아직 열지 않은 상태에서 커밋한다. 분모와 분석
함수가 결과보다 먼저 이력에 있어야 "보고 나서 정한 것"이 아니라고 말할 수 있다.

핵심은 **적격성을 positive로 정의**하는 것이다. `_10_000`은 배관 진단 중 M8 사건
수가 로그에 노출돼(작업현황 §5-4) 독립 reference로 쓸 수 없다. 이런 영상의
reference 지표를 `0`으로 내면 "GT가 있었는데 하나도 못 맞췄다"는 **전혀 다른 뜻**이
된다. `None`이어야 한다.

사건 시간 표현: reference는 사람이 쓴 **초**, M8은 **구간 번호(span)**. 비교는
span에서 하고, reference span은 초에서 `derive_gt_seg_idx`로 매번 재계산한다
(동결본의 `span`을 authoritative로 쓰지 않는다 — 초가 원본이다).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import m8_pilot_report as R                                 # noqa: E402

POLICY = {"policies": [{
    "run_id": "r1", "plan_name": "m8_dev_pilot",
    "requires_frozen_inventory": ["vidA", "vidB"],
    "excluded_from_reference": ["vidX"]}]}


def _frozen(d: Path, vid: str, events, n_segments=40, seg_len=5):
    """동결본을 흉내낸다 — 초만 authoritative, span은 넣지 않는다."""
    (d / f"FROZEN_{vid}.json").write_text(json.dumps(
        {"video_id": vid, "sha256": "x", "frozen_at": "t",
         "seg_len": seg_len, "n_segments": n_segments,
         "events": [{"start_sec": s, "end_sec": e, "event": n} for s, e, n in events]},
        ensure_ascii=False), encoding="utf-8")


def _rep(*spans):
    return {"events": [{"event": f"e{i}", "span": list(s),
                        "evidence_segments": [s[0]], "description": "x" * 20}
                       for i, s in enumerate(spans)]}


@pytest.fixture
def env(tmp_path):
    inv, pol = tmp_path / "inv", tmp_path / "report_access.json"
    inv.mkdir()
    pol.write_text(json.dumps(POLICY), encoding="utf-8")
    _frozen(inv, "vidA", [(0, 30, "a1"), (40, 70, "a2")])   # span [0,5], [8,13]
    _frozen(inv, "vidB", [(0, 50, "b1")])                   # span [0,9]
    return {"inventory_dir": inv, "policy_path": pol}


# ---- reference span은 초에서 재계산한다 -----------------------------------

def test_reference_span_is_derived_from_seconds(env):
    refs = R.reference_events("vidA", **env)
    assert [r["span"] for r in refs] == [[0, 5], [8, 13]]


# ---- 적격성: positive로 정의한다 ------------------------------------------

def test_eligible_requires_frozen_and_not_excluded(env):
    assert R.reference_eligible("vidA", "r1", **env) is True
    assert R.reference_eligible("vidB", "r1", **env) is True
    assert R.reference_eligible("vidX", "r1", **env) is False   # 제외 등록
    assert R.reference_eligible("vidZ", "r1", **env) is False   # 동결 없음


def test_excluded_video_gets_none_not_zero(env):
    """`0`은 '맞춘 게 없다'는 뜻이다 — 여기서는 '해당 없음'이어야 한다."""
    m = R.video_metrics("vidX", _rep([0, 5], [7, 11]), 40, "r1", **env)
    assert m["reference_eligible"] is False
    assert m["reference_status"] == "not_applicable"
    assert m["event_temporal_alignment"] is None
    for k, v in m["temporal_event_recall"].items():
        assert v is None, k


def test_video_without_frozen_reference_also_none(env):
    m = R.video_metrics("vidZ", _rep([0, 2]), 40, "r1", **env)
    assert m["event_temporal_alignment"] is None
    assert m["temporal_event_recall"]["temporal_event_recall@IoU>=0.5"] is None
    assert m["reference_status"] == "no_frozen_reference"


def test_structural_diagnostics_computed_even_when_excluded(env):
    """생성 쪽 구조 진단은 reference가 없어도 낸다 — 그게 분리의 요점이다."""
    m = R.video_metrics("vidX", _rep([0, 5], [20, 25]), 40, "r1", **env)
    assert m["structural"]["valid_events"] == 2
    assert m["structural"]["timeline_span_coverage"] is not None


# ---- 지표 정의 ------------------------------------------------------------

def test_unmatched_reference_counts_as_zero_in_alignment(env):
    """정렬은 reference 전체의 macro mean이다 — 못 맞춘 건 0으로 들어간다."""
    m = R.video_metrics("vidA", _rep([0, 5]), 40, "r1", **env)   # a2 미매칭
    assert m["event_temporal_alignment"] == pytest.approx(0.5, abs=1e-9)


def test_one_huge_span_cannot_cover_two_references(env):
    """1:1 매칭이다. 거대한 span 하나가 reference 둘을 동시에 덮지 못한다."""
    m = R.video_metrics("vidA", _rep([0, 13]), 40, "r1", **env)
    assert m["n_matched"] == 1
    assert m["temporal_event_recall"]["temporal_event_recall@IoU>=0.3"] <= 0.5


def test_zero_overlap_pairs_are_not_matched(env):
    m = R.video_metrics("vidA", _rep([30, 35]), 60, "r1", **env)
    assert m["n_matched"] == 0
    assert m["event_temporal_alignment"] == 0.0


def test_thresholds_are_fixed_at_3_5_7(env):
    m = R.video_metrics("vidA", _rep([0, 5]), 40, "r1", **env)
    assert sorted(m["temporal_event_recall"]) == [
        "temporal_event_recall@IoU>=0.3",
        "temporal_event_recall@IoU>=0.5",
        "temporal_event_recall@IoU>=0.7"]


# ---- 집계 ----------------------------------------------------------------

def _three(env):
    return {v: R.video_metrics(v, r, 40, "r1", **env) for v, r in {
        "vidA": _rep([0, 5]), "vidB": _rep([0, 9]), "vidX": _rep([0, 5])}.items()}


def test_aggregate_uses_only_eligible_videos(env):
    agg = R.aggregate(_three(env))
    assert agg["n_reference_videos"] == 2
    assert sorted(agg["reference_videos"]) == ["vidA", "vidB"]
    assert agg["n_reference_events"] == 3                     # 2 + 1
    assert agg["excluded_videos"] == ["vidX"]


def test_aggregate_weights_every_reference_event_equally(env):
    """**영상 균등이 아니라 reference event 균등이다.** 두 방식은 사건 수가 많은
    영상의 가중치가 다르다 — 정의가 'reference별 matched IoU의 macro mean'이므로
    모든 reference event를 동일 가중한다. 영상 균등 평균은 산출하지 않는다."""
    agg = R.aggregate(_three(env))
    # 사건 균등: (1.0 + 0.0 + 1.0)/3 = 0.6667.  영상 균등이면 (0.5 + 1.0)/2 = 0.75.
    assert agg["event_temporal_alignment"] == pytest.approx(2 / 3, abs=1e-4)
    assert "event_temporal_alignment_by_video_mean" not in agg


def test_aggregate_recall_is_also_event_weighted(env):
    agg = R.aggregate(_three(env))
    assert agg["temporal_event_recall"][
        "temporal_event_recall@IoU>=0.7"] == pytest.approx(2 / 3, abs=1e-4)


def test_aggregate_reports_no_ci(env):
    """영상 2편이다 — CI를 내지 않는다(작업현황 §5-3)."""
    agg = R.aggregate(_three(env))
    assert agg["ci"] is None and agg["ci_reason"]
    assert not any(k.endswith("_ci") for k in agg)


def test_timeline_coverage_is_separate_from_reference_metrics(env):
    """생성 span만으로 계산하는 **진단** 지표다. reference 지표와 섞지 않는다."""
    agg = R.aggregate({"vidX": R.video_metrics("vidX", _rep([0, 5]), 40, "r1", **env)})
    assert agg["n_reference_videos"] == 0
    assert agg["event_temporal_alignment"] is None
    assert agg["structural"]["n_videos"] == 1                 # 구조 쪽은 살아 있다


def test_real_policy_declares_the_two_reference_videos():
    """실제 정책 파일이 이 사이클의 분모를 선언하고 있는가."""
    pol = json.loads((ROOT / "planning" / "report_access.json")
                     .read_text(encoding="utf-8"))["policies"][0]
    assert pol["run_id"] == "m8pilot_0818d"
    assert set(pol["requires_frozen_inventory"]) == {
        "gwaktube_soviet_apartment", "kheritage_grave_excavation"}
    assert pol["excluded_from_reference"] == [
        "_10_000_Every_Day_You_Survive_In_The_Wilderness"]
