"""evidence resolution 계약 (2026-09-09 · WVR-E01~E30).

```
새 추론 없음        torch·transformers를 import조차 하지 않는다
evidence            5초 segment의 caption·subtitle만. episode summary는 evidence 아님
없음 ≠ 반증          지지 부재는 절대 CONTRADICTS가 되지 않는다
사전                evidence를 읽기 전에 동결. hash가 바뀌면 RED
```
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_density as density
import wvr_evidence_lexicon as lex
import wvr_evidence_v1 as ev

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT / "docs/preregistration/"
          "WVR_EVIDENCE_RESOLUTION_V1_2026-09-09.md")
RESOLVER = ROOT / "scripts/wvr_evidence_resolve.py"
RESULT = ROOT / "runs/wvr_light_v1/evidence_resolution_v1.json"
LEXICON_HASH = "450f5dac163ba236e1af090e1cabdac49f1282e74d8fd3bc6491b79add486b1b"


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


resolver = _module(RESOLVER, "wvr_evidence_resolve")


def _event(start, end, action="eating", thing="a breaded food item",
           actor="a person"):
    return {"start_sec": start, "end_sec": end, "actor": actor,
            "action": action, "object_or_state": thing}


def _seg(idx, start, caption="", subtitle=""):
    return {"idx": idx, "start": start, "end": start + 5.0,
            "caption": caption, "subtitle": subtitle}


# ── WVR-E01~E04 동결 ────────────────────────────────────────────────
def test_wvr_e01_the_preregistration_is_committed():
    done = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_EVIDENCE_RESOLUTION_V1_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_e02_the_lexicon_hash_is_frozen():
    assert lex.lexicon_hash() == LEXICON_HASH
    assert LEXICON_HASH in PREREG.read_text(encoding="utf-8")


def test_wvr_e03_colliding_surface_terms_are_dropped_from_both_sets():
    assert "볼" in lex.COLLISION_DROPPED
    assert "볼" not in lex.OBJECT_TERMS["bowl"]
    assert "볼" not in lex.OBJECT_TERMS["balls"]


def test_wvr_e04_the_probe_declares_no_inference_and_no_promotion():
    assert ev.NEW_INFERENCE_ALLOWED is False
    assert ev.SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED is False
    assert ev.PROMOTION_ALLOWED is False
    assert ev.EVENT_EXTRACTION_APPROVED is False


# ── WVR-E05~E09 후보 선정 ───────────────────────────────────────────
def test_wvr_e05_both_tolerances_stay_reported():
    assert ev.TOLERANCES == density.MATCH_TOLERANCE_SEC == (4.0, 8.0)
    assert ev.PRIMARY_TOLERANCE == 4.0


def test_wvr_e06_doubly_disjoint_requires_both_dimensions():
    eating = _event(312.0, 480.0, "eating", "a breaded food item")
    sewing = _event(420.0, 450.0, "sewing", "pajama pants")
    assert ev.doubly_disjoint(eating, sewing)
    coat_a = _event(140.0, 145.0, "coating", "potato balls")
    coat_b = _event(146.0, 154.0, "coating", "potato mixture")
    assert not ev.doubly_disjoint(coat_a, coat_b)
    share_object = _event(140.0, 145.0, "placing", "potato balls")
    assert not ev.doubly_disjoint(share_object, coat_b)


def test_wvr_e07_candidates_need_temporal_compatibility():
    reference = [_event(300.0, 310.0, "eating", "rice")]
    far = [_event(400.0, 410.0, "sewing", "pajama pants")]
    assert ev.candidate_pairs(reference, far, 4.0) == []
    near = [_event(310.0, 320.0, "sewing", "pajama pants")]
    assert len(ev.candidate_pairs(reference, near, 4.0)) == 1


def test_wvr_e08_token_overlapping_pairs_are_not_conflict_candidates():
    reference = [_event(300.0, 310.0, "coating", "potato balls")]
    arm = [_event(300.0, 310.0, "coating", "potato mixture")]
    assert ev.candidate_pairs(reference, arm, 4.0) == []


def test_wvr_e09_evidence_window_is_the_overlap_not_the_hull():
    reference = _event(312.0, 480.0, "eating", "a breaded food item")
    arm = _event(420.0, 450.0, "sewing", "pajama pants")
    assert ev.evidence_window(reference, arm) == (420.0, 450.0)
    gap_arm = _event(482.0, 486.0, "sewing", "pajama pants")
    assert ev.evidence_window(reference, gap_arm) == (312.0, 486.0)


# ── WVR-E10~E12 evidence 수집 ───────────────────────────────────────
def test_wvr_e10_evidence_segments_use_half_open_intersection():
    segments = [_seg(0, 415.0), _seg(1, 420.0), _seg(2, 445.0), _seg(3, 450.0)]
    picked = [row["idx"] for row in ev.evidence_segments(segments, 420.0,
                                                         450.0)]
    assert picked == [1, 2]


def test_wvr_e11_pre_freeze_viewed_segments_are_disclosed():
    assert ev.PRE_FREEZE_VIEWED_SEG_IDX == (60, 61, 62, 63)
    rows = ev.evidence_segments([_seg(60, 300.0), _seg(70, 350.0)], 290.0,
                                400.0)
    flags = {row["idx"]: row["pre_freeze_viewed"] for row in rows}
    assert flags == {60: True, 70: False}


def test_wvr_e12_episode_summary_is_never_read_as_evidence():
    assert "summary" in ev.NON_EVIDENCE_FIELDS
    source = RESOLVER.read_text(encoding="utf-8")
    for banned in ('episode["summary"]', 'episode.get("summary")',
                   '"summary"]'):
        assert banned not in source, "episode summary를 evidence로 썼다"
    rows = ev.evidence_segments(
        [dict(_seg(1, 10.0, "감자를 씻는다"), summary="요약문")], 10.0, 15.0)
    assert "summary" not in rows[0]


# ── WVR-E13~E16 claim 지지 ─────────────────────────────────────────
def test_wvr_e13_support_requires_both_dimensions_in_one_segment():
    terms = ev.claim_terms(_event(0.0, 5.0, "chopping", "onion"))
    split = [_seg(0, 0.0, "양파가 보인다"), _seg(1, 5.0, "칼로 썰고 있다")]
    support = ev.claim_support(terms, split)
    assert support["supported"] is False
    assert len(support["partial"]) == 2
    together = [_seg(0, 0.0, "양파를 칼로 썰고 있다")]
    assert ev.claim_support(terms, together)["supported"] is True


def test_wvr_e14_shared_surface_term_support_is_flagged_not_hidden():
    terms = ev.claim_terms(_event(420.0, 450.0, "sewing",
                                  "pajama pants with a sewing machine"))
    support = ev.claim_support(terms, [_seg(0, 420.0, "재봉틀이 놓여 있다")])
    assert support["supported"] is True
    assert support["independent_support"] is False
    assert support["shared_term_only_hits"] == 1
    assert support["hits"][0]["shared_terms"]


def test_wvr_e15_absence_of_evidence_is_never_a_contradiction():
    terms = ev.claim_terms(_event(0.0, 5.0, "sewing", "pajama pants"))
    empty = ev.claim_support(terms, [_seg(0, 0.0, "화면에 창문이 보인다")])
    verdict = ev.claim_verdict(empty, empty)
    assert verdict["verdict"] == ev.EVIDENCE_UNRESOLVED


def test_wvr_e16_contradiction_requires_positive_support_of_the_rival():
    mine = ev.claim_terms(_event(0.0, 5.0, "sewing", "pajama pants"))
    rival = ev.claim_terms(_event(0.0, 5.0, "eating", "rice"))
    segments = [_seg(0, 0.0, "밥을 먹고 있다")]
    my_support = ev.claim_support(mine, segments)
    rival_support = ev.claim_support(rival, segments)
    assert rival_support["supported"] is True
    assert ev.claim_verdict(my_support, rival_support)["verdict"] == \
        ev.EVIDENCE_CONTRADICTS
    assert ev.claim_verdict(rival_support, my_support)["verdict"] == \
        ev.EVIDENCE_SUPPORTS


def test_wvr_e17_an_uncovered_claim_can_never_be_contradicted():
    uncovered = ev.claim_terms(_event(0.0, 5.0, "zzz", "qqq"))
    assert uncovered["covered"] is False
    rival = ev.claim_terms(_event(0.0, 5.0, "eating", "rice"))
    segments = [_seg(0, 0.0, "밥을 먹고 있다")]
    verdict = ev.claim_verdict(ev.claim_support(uncovered, segments),
                               ev.claim_support(rival, segments))
    assert verdict["verdict"] == ev.EVIDENCE_UNRESOLVED
    assert ev.LEXICON_UNCOVERED in verdict["reasons"]


# ── WVR-E18~E21 판정 ───────────────────────────────────────────────
def test_wvr_e18_pair_resolution_has_four_disjoint_labels():
    S, U = ev.EVIDENCE_SUPPORTS, ev.EVIDENCE_UNRESOLVED
    assert ev.pair_resolution(S, S) == ev.BOTH_SUPPORTED
    assert ev.pair_resolution(S, U) == ev.REFERENCE_ONLY
    assert ev.pair_resolution(U, S) == ev.ARM_ONLY
    assert ev.pair_resolution(U, U) == ev.NEITHER_RESOLVED
    assert ev.pair_resolution(ev.EVIDENCE_CONTRADICTS, U) == \
        ev.NEITHER_RESOLVED


def test_wvr_e19_branch_mapping_is_frozen_before_results():
    assert ev.event_verdict(0, 3) == ev.BRANCH_A
    assert ev.event_verdict(3, 0) == ev.BRANCH_B
    assert ev.event_verdict(2, 2) == ev.BRANCH_C
    assert ev.event_verdict(0, 0) == ev.BRANCH_C


def test_wvr_e20_reviewer_named_conflicts_are_frozen_verbatim():
    assert len(ev.REVIEWER_NAMED_CONFLICTS) == 8
    assert ("D1", (312.0, 480.0), (420.0, 450.0)) in \
        ev.REVIEWER_NAMED_CONFLICTS
    assert ("D2", (96.0, 210.0), (104.0, 112.0)) in \
        ev.REVIEWER_NAMED_CONFLICTS
    assert {row[0] for row in ev.REVIEWER_NAMED_CONFLICTS} == {"D1", "D2"}


def test_wvr_e21_selector_incompleteness_is_recorded_not_silent():
    reference = [_event(312.0, 480.0, "eating", "a breaded food item")]
    arm = [_event(420.0, 450.0, "sewing", "pajama pants")]
    found = ev.candidate_pairs(reference, arm, 4.0)
    cover = ev.reviewer_coverage(found, "D1")
    assert cover["named_count"] == 4
    assert cover["status"] == ev.SELECTOR_INCOMPLETE
    assert len(cover["missing"]) == 3
    assert {"reference": [312.0, 480.0], "arm": [420.0, 450.0]} in \
        cover["found"]


# ── WVR-E22~E26 실행기 계약 ────────────────────────────────────────
def test_wvr_e22_the_resolver_never_loads_an_inference_stack():
    source = RESOLVER.read_text(encoding="utf-8")
    for banned in ("import torch", "import transformers",
                   "from transformers"):
        assert banned not in source
    assert "torch" not in sys.modules
    sys.modules["torch"] = object()
    try:
        with pytest.raises(resolver.ResolveError):
            resolver.assert_no_inference()
    finally:
        del sys.modules["torch"]


def test_wvr_e23_invalid_v2_arms_are_refused_as_input(tmp_path):
    record = {"event": "V2", "arm_status": "ARM_INVALID",
              "parsed": {"collapsed": []}}
    (tmp_path / "density_v2_D1_S0.json").write_text(
        json.dumps(record), encoding="utf-8")
    with pytest.raises(resolver.ResolveError):
        resolver.load_v2(tmp_path, "D1", "S0")


def test_wvr_e24_input_identity_is_verified_by_hash(tmp_path):
    fake = tmp_path / "segments.json"
    fake.write_text(json.dumps({"segments": []}), encoding="utf-8")
    with pytest.raises(resolver.ResolveError):
        resolver.resolve(tmp_path, fake, fake, fake)

    # 두 해시 가드를 하나씩 분리해 확인한다 (한쪽만 남아도 통과하면 안 된다)
    digest = resolver.sha256(fake)
    for attribute in ("EXPECTED_VIDEO_SHA256", "EXPECTED_SEGMENTS_SHA256"):
        original = getattr(ev, attribute)
        setattr(ev, attribute, digest)
        try:
            with pytest.raises(resolver.ResolveError):
                resolver.resolve(tmp_path, fake, fake, fake)
        finally:
            setattr(ev, attribute, original)


def test_wvr_e25_reviewer_named_pairs_are_unioned_not_replaced():
    reference = [_event(312.0, 480.0, "eating", "a breaded food item")]
    arm = [_event(380.0, 390.0, "cooking", "chicken with a torch"),
           _event(420.0, 450.0, "sewing", "pajama pants"),
           _event(450.0, 460.0, "chopping", "tomato with a knife"),
           _event(470.0, 480.0, "cooking", "tomato and egg in a pan")]
    found = ev.candidate_pairs(reference, [arm[1]], 4.0)
    merged = resolver.add_reviewer_named(found, "D1", reference, arm)
    assert len(merged) == 4
    sewing = [row for row in merged
              if float(row["arm"]["start_sec"]) == 420.0][0]
    assert set(sewing["source"]) == {ev.SOURCE_DETERMINISTIC,
                                     ev.SOURCE_REVIEWER}
    others = [row for row in merged if row is not sewing]
    assert all(row["source"] == [ev.SOURCE_REVIEWER] for row in others)


def test_wvr_e26_a_reviewer_span_absent_from_frozen_output_is_an_error():
    reference = [_event(312.0, 480.0, "eating", "a breaded food item")]
    arm = [_event(420.0, 450.0, "sewing", "pajama pants")]
    with pytest.raises(resolver.ResolveError):
        resolver.add_reviewer_named([], "D2", reference, arm)


# ── WVR-E27~E30 실행 후 (산출물 있을 때만) ──────────────────────────
requires_result = pytest.mark.skipif(not RESULT.is_file(),
                                     reason="evidence resolution 미실행")


@requires_result
def test_wvr_e27_the_result_declares_its_limits():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    assert record["schema"] == "wvr_evidence_resolution_v1"
    assert record["event"] == ev.EVENT
    assert record["new_inference_allowed"] is False
    assert record["semantic_sufficiency_claim_allowed"] is False
    assert record["promotion_allowed"] is False
    assert record["lexicon"]["hash"] == LEXICON_HASH


@requires_result
def test_wvr_e28_every_contradiction_names_a_supported_rival():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    for pair in record["pairs"].values():
        for row in pair["conflicts"]:
            if row["reference_verdict"] == ev.EVIDENCE_CONTRADICTS:
                assert row["arm_support"]["hits"]
            if row["arm_verdict"] == ev.EVIDENCE_CONTRADICTS:
                assert row["reference_support"]["hits"]


@requires_result
def test_wvr_e29_resolution_labels_and_totals_are_consistent():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    labels = {ev.REFERENCE_ONLY, ev.ARM_ONLY, ev.BOTH_SUPPORTED,
              ev.NEITHER_RESOLVED}
    totals = dict.fromkeys(labels, 0)
    for pair in record["pairs"].values():
        assert pair["conflict_count"] == len(pair["conflicts"])
        for row in pair["conflicts"]:
            assert row["resolution"] in labels
            totals[row["resolution"]] += 1
    assert totals == record["resolution_totals"]
    assert record["event_verdict"] == ev.event_verdict(
        totals[ev.REFERENCE_ONLY], totals[ev.ARM_ONLY])


@requires_result
def test_wvr_e30_input_provenance_is_the_adopted_submission_layer():
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    assert record["inputs"]["segments_sha256"] == ev.EXPECTED_SEGMENTS_SHA256
    assert record["inputs"]["video_sha256"] == ev.EXPECTED_VIDEO_SHA256
    assert record["inputs"]["canonical"].endswith(
        "runs/vad0_paired/s1_shadow/S5/aar_canonical.json")
    assert record["inputs"]["canonical_boundary"]["provider_config"][
        "window_sec"] == 60.0
