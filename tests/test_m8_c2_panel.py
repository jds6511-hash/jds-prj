"""M8 C2 판정 패널(N=8) 동결 검증.

이 테스트가 막는 것은 하나다 — **결과를 본 뒤 패널을 바꾸는 것.**

```
설계 상수     N=8 · 중앙값 · 0.70 · top-up 금지 — 코드에서 바뀌면 실패한다
표본 배제     소비 선언 2편 · test · E2E · P2/P3 · 노출 이력 1편이 패널에 없어야 한다
선정 재현     후보 풀 해시와 seed로 primary·reserve가 그대로 다시 나와야 한다
```

GPU·네트워크를 쓰지 않는다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import eligibility                                            # noqa: E402
import m8_c2_panel as P                                       # noqa: E402

MANIFEST = ROOT / "docs/finalization/m8_c2_panel_manifest_2026-08-27.json"
pytestmark = pytest.mark.skipif(not MANIFEST.exists(),
                                reason="패널 manifest가 아직 동결되지 않았다")


@pytest.fixture(scope="module")
def man():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 설계 상수

def test_fixed_n_is_eight(man):
    assert man["design"]["fixed_n"] == 8 == P.FIXED_N


def test_top_up_is_not_allowed(man):
    """8편 결과를 본 뒤 9~12편을 붙이는 경로를 열어두지 않는다."""
    assert man["design"]["top_up_allowed"] is False


def test_c2_statistic_and_threshold_unchanged(man):
    assert man["design"]["c2_statistic"] == "median"
    assert man["design"]["c2_threshold"] == 0.70 == P.C2_THRESHOLD


def test_reference_is_human_and_blind(man):
    assert man["design"]["reference_author"] == "human"
    assert man["design"]["reference_blinded_to_m8"] is True


# ---------------------------------------------------------------- 표본 배제

def test_consumed_pilot_videos_are_absent(man):
    for v in ("gwaktube_soviet_apartment", "kheritage_grave_excavation"):
        assert v not in man["final_panel"], v


def test_test_split_and_e2e_and_p2p3_are_absent(man):
    final = man["final_panel"]
    for v in eligibility.TEST_SPLIT_VIDEOS:
        assert v not in final, v
    for v in eligibility.e2e_only_videos():
        assert v not in final, v
    assert not [v for v in final if v.lower().startswith(eligibility.RESTRICTED_PREFIXES)]


def test_prior_exposure_video_is_absent(man):
    """`pland_costco_hosting`은 M8 산출물이 없지만 캡션·검색 결과를 상세 열람했다."""
    assert "pland_costco_hosting" not in man["final_panel"]
    codes = {e["video_id"]: e["reason_code"] for e in man["exclusions"]}
    assert codes["pland_costco_hosting"] == "PRIOR_EXPOSURE_RISK"


def test_final_panel_is_eight_unique(man):
    assert len(man["final_panel"]) == 8
    assert len(set(man["final_panel"])) == 8


# ---------------------------------------------------------------- 선정 재현

def test_seed_is_the_pre_selection_commit(man):
    assert man["seed"] == {"namespace": "M8-C2-N8-v1", "commit": "f035073",
                           "algorithm": "sha256"}


def test_selection_key_is_deterministic():
    a = P.selection_key("3I7oGwk6EaQ")
    assert a == P.selection_key(" 3I7oGwk6EaQ ")          # 공백만 제거한다
    assert a != P.selection_key("3i7ogwk6eaq")            # casefold하지 않는다


def test_candidate_pool_hash_is_stable(man):
    pool = man["candidate_pool"]["videos"]
    assert P.pool_sha256(pool) == man["candidate_pool"]["sha256"]
    assert P.pool_sha256(list(reversed(pool))) == man["candidate_pool"]["sha256"]


def test_primary_ordering_reproducible(man):
    primary, _ = P.pick(man["candidate_pool"]["videos"])
    assert [r["id"] for r in primary] == [r["id"] for r in man["selected_new"]]


def test_reserve_ordering_reproducible(man):
    _, reserve = P.pick(man["candidate_pool"]["videos"])
    assert [r["id"] for r in reserve] == [r["id"] for r in man["reserve_order"]]


def test_exactly_two_new_videos_selected(man):
    assert len(man["selected_new"]) == 2


def test_new_channels_are_distinct_from_each_other(man):
    ch = [r["channel_id"] for r in man["selected_new"]]
    assert len(set(ch)) == 2, ch


def test_new_channels_differ_from_known_existing_channels(man):
    known = set(man["channel_constraints"]["existing_known_channel_ids"].values())
    for r in man["selected_new"]:
        assert r["channel_id"] not in known, r["id"]


def test_unknown_existing_channels_are_declared_not_guessed(man):
    """출처를 남기지 않고 취득한 3편의 채널을 추측해 채우지 않는다."""
    unk = man["channel_constraints"]["existing_unknown_channel"]
    assert set(unk) == set(P.EXISTING_CHANNEL_UNKNOWN)


def test_replacement_reasons_are_allowlisted(man):
    for e in man.get("replacements", []):
        assert e["reason_code"] in P.REPLACEMENT_REASONS, e


def test_verify_reports_no_drift(man):
    assert P.verify(man) == []


def test_verify_catches_a_pool_edit(man):
    tampered = json.loads(json.dumps(man))
    tampered["candidate_pool"]["videos"].pop()
    assert any("candidate_pool_sha256" in d for d in P.verify(tampered))


def test_verify_catches_a_threshold_change(man):
    tampered = json.loads(json.dumps(man))
    tampered["design"]["c2_threshold"] = 0.60
    assert any("design" in d for d in P.verify(tampered))


def test_no_m8_outcome_was_observed(man):
    """패널을 정하는 동안 M8 결과를 보지 않았다는 것을 manifest가 주장한다."""
    b = man["boundaries"]
    assert b["m8_official_run"] is False
    assert b["event_recall_calculated"] is False
    assert b["m9_test_opened"] is False
    assert b["panel_chosen_from_outcome"] is False
