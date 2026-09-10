"""Event Map coverage shadow 계약 (2026-09-10 · WVR-R01~R37).

```
입력   기존 SHADOW_V1 W01–W23 collapsed event (read-only · 새 추론 0회)
산출   registry · coverage map · CANDIDATE_EVENT_MAP · chapter candidate · flow packet
원칙   W00은 source 제외 · synthetic event 금지 · concat fallback 금지 ·
      unresolved 구간 보존 · chapter boundary는 event 내용에서만
게이트  reviewer 전용 (PASS/HOLD/INCONCLUSIVE) — executor는 계산하지 않는다
```
"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_density_v2 as v2
import wvr_event_map_v1 as em
import wvr_shadow_v1 as sh

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_EVENT_MAP_COVERAGE_SHADOW_V1_2026-09-10.md")
SOURCES_REL = ("docs/preregistration/"
               "WVR_EVENT_MAP_COVERAGE_SHADOW_V1_sources.json")
PREREG = ROOT / PREREG_REL
SOURCES = ROOT / SOURCES_REL
BUILDER = ROOT / "scripts/wvr_event_map_build.py"
VALIDATOR = ROOT / "scripts/wvr_event_map_validate.py"
RUNS = ROOT / "runs/wvr_light_v1"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"
SUBMISSION_SHA = ("5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca9"
                  "94e9cd7b")


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _module(BUILDER, "wvr_event_map_build_mod")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _event(event_id, window, start, end, actor="person", action="holding",
           obj="a bottle"):
    return {"event_id": event_id, "source_window": window,
            "collapsed_index": int(event_id[-3:]) - 1,
            "start_sec": start, "end_sec": end, "actor": actor,
            "action": action, "object_or_state": obj}


def _collapsed(start, end, actor="person", action="holding",
               obj="a bottle"):
    return {"start_sec": start, "end_sec": end, "actor": actor,
            "action": action, "object_or_state": obj,
            "signature": (actor, action, obj), "source_indices": [0],
            "collapsed_count": 1}


def _record(window_id, events, status=sh.WINDOW_VALID):
    window = sh.window_by_id(window_id)
    return {"event": sh.EVENT, "window": window,
            "validity": {"status": status, "valid": status
                         == sh.WINDOW_VALID, "reasons": []},
            "parsed": {"status": "OK", "events": events,
                       "collapsed": events},
            "representation": {"collapsed_event_count": len(events),
                               "unique_signature_count": len(events),
                               "degenerate": False},
            "raw_output_hash": "raw_%s" % window_id,
            "collapse_output_hash": "coll_%s" % window_id,
            "video_sha256": "vid", "code_git_head": "abc1234",
            "source_record_sha256": "rec_%s" % window_id}


def _records(**overrides):
    rows = {}
    for index, window_id in enumerate(em.VALID_SOURCE_WINDOWS):
        start = sh.window_by_id(window_id)["start_sec"]
        events = [_collapsed(start, start + 12.0,
                             action="action%02d" % index,
                             obj="object%02d" % index)]
        rows[window_id] = _record(window_id, events)
    for window_id, record in (overrides or {}).items():
        rows[window_id] = record
    return rows


# ── WVR-R01~R08 계약·어휘 동결 ─────────────────────────────────────
def test_wvr_r01_the_preregistration_and_source_manifest_are_committed():
    for path in (PREREG_REL, SOURCES_REL):
        done = subprocess.run(["git", "ls-files", "--error-unmatch", path],
                              cwd=str(ROOT), capture_output=True, text=True)
        assert done.returncode == 0, "커밋되지 않았다: %s" % path
    assert PREREG.is_file() and SOURCES.is_file()


def test_wvr_r02_only_w01_to_w23_are_valid_sources():
    assert em.VALID_SOURCE_WINDOWS[0] == "W01"
    assert em.VALID_SOURCE_WINDOWS[-1] == "W23"
    assert len(em.VALID_SOURCE_WINDOWS) == em.EXPECTED_VALID_SOURCE_COUNT == 23
    assert em.INVALID_SOURCE_WINDOWS == ("W00",)
    assert "W00" not in em.VALID_SOURCE_WINDOWS
    assert em.W00_AS_EVENT_SOURCE_ALLOWED is False
    assert em.W00_RERUN_ALLOWED is False


def test_wvr_r03_no_new_inference_and_no_generation_is_allowed():
    for name in ("NEW_INFERENCE_ALLOWED", "SYNTHETIC_EVENT_ALLOWED",
                 "CONCAT_FALLBACK_ALLOWED", "PROMPT_MUTATION_ALLOWED",
                 "BLIND_MAP_REVEAL_ALLOWED", "SEMANTIC_VERDICT_BY_EXECUTOR",
                 "CHAPTER_TITLE_GENERATION_ALLOWED",
                 "OVERVIEW_GENERATION_ALLOWED",
                 "SHADOW_V1_RETROACTIVE_PASS_ALLOWED",
                 "PRODUCTION_PROMOTION_ALLOWED"):
        assert getattr(em, name) is False, "%s가 열려 있다" % name


def test_wvr_r04_the_relation_and_coverage_vocabularies_are_frozen():
    assert em.RELATIONS == ("POSSIBLE_SAME_EVENT", "POSSIBLE_CONTINUATION",
                            "POSSIBLE_TRANSITION", "POSSIBLE_CONFLICT",
                            "UNRESOLVED")
    assert em.GROUPING_RELATIONS == ("POSSIBLE_SAME_EVENT",
                                     "POSSIBLE_CONTINUATION")
    assert em.COVERAGE_STATUSES == ("MULTI_WINDOW_OBSERVED",
                                    "SINGLE_WINDOW_OBSERVED",
                                    "INVALID_WINDOW_ONLY", "UNRESOLVED")
    assert em.REVIEWER_VERDICTS == ("EVENT_MAP_SHADOW_PASS",
                                    "EVENT_MAP_SHADOW_HOLD",
                                    "EVENT_MAP_SHADOW_INCONCLUSIVE")
    assert em.ARTIFACT_NAME == "CANDIDATE_EVENT_MAP"
    assert em.MIN_CHAPTER_SEC == 60.0 and em.SUSTAINED_LOOKBACK == 2


def test_wvr_r05_the_executor_never_computes_the_reviewer_verdict():
    rows = em.registry(_records())
    groups = em.group_events(rows, em.relation_candidates(rows))
    state = em.executor_state(rows, groups, em.coverage_map(rows))
    assert state["state"] == "EXECUTED / REVIEW_PENDING"
    assert state["semantic_verdict"] is None
    assert state["semantic_verdict_by_executor"] is False
    assert state["new_inference_count"] == 0
    assert state["allowed_max_conclusion"].startswith(
        "Existing valid C01 local-window observations")
    for phrase in ("Event extraction solved", "0.5fps sufficient",
                   "all events factual", "production ready"):
        assert phrase in em.FORBIDDEN_CONCLUSIONS
    assert em.COVERAGE_CAVEAT == "coverage percentage ≠ semantic correctness"


def test_wvr_r06_event_ids_are_deterministic():
    assert em.event_id("W01", 0) == "W01_E001"
    assert em.event_id("W23", 11) == "W23_E012"
    rows = em.registry(_records())
    assert rows[0]["event_id"] == "W01_E001"
    assert len({row["event_id"] for row in rows}) == len(rows)
    again = em.registry(_records())
    assert [row["event_id"] for row in rows] == [row["event_id"]
                                                 for row in again]


def test_wvr_r07_the_registry_refuses_invalid_or_missing_sources():
    records = _records()
    records.pop("W07")
    with pytest.raises(em.EventMapError):
        em.registry(records)
    broken = _records()
    broken["W07"] = _record("W07", [_collapsed(150.0, 160.0)],
                            status=sh.WINDOW_INVALID)
    with pytest.raises(em.EventMapError):
        em.registry(broken)


def test_wvr_r08_the_registry_preserves_event_text_and_lineage():
    records = _records()
    records["W01"] = _record("W01", [_collapsed(30.0, 40.0, actor="a person",
                                                action="pouring",
                                                obj="liquid into a bowl")])
    row = em.registry(records)[0]
    assert (row["actor"], row["action"], row["object_or_state"]) == (
        "a person", "pouring", "liquid into a bowl")
    assert row["source_window"] == "W01"
    assert row["source_raw_hash"] == "raw_W01"
    assert row["source_collapse_hash"] == "coll_W01"
    assert row["source_window_span"] == [24.0, 72.0]


# ── WVR-R09~R14 relation 규칙 ──────────────────────────────────────
def test_wvr_r09_identical_overlapping_events_are_possible_same_event():
    left = _event("W01_E001", "W01", 30.0, 40.0)
    right = _event("W02_E001", "W02", 35.0, 45.0)
    row = em.relation_label(left, right)
    assert row["relation"] == em.SAME_EVENT
    assert row["overlap_sec"] == 5.0
    assert row["role"] == "CANDIDATE_LABEL_NOT_FACTUAL_AUTHORITY"


def test_wvr_r10_disjoint_tokens_at_the_same_time_are_possible_conflict():
    left = _event("W01_E001", "W01", 30.0, 40.0, actor="a chef",
                  action="pouring", obj="liquid into a bowl")
    right = _event("W02_E001", "W02", 30.0, 40.0, actor="a worker",
                   action="stacking", obj="boxes")
    row = em.relation_label(left, right)
    assert row["relation"] == em.CONFLICT
    assert row["semantic_relation"] == v2.SEMANTICALLY_DIFFERENT


def test_wvr_r11_partial_token_overlap_stays_unresolved():
    left = _event("W01_E001", "W01", 30.0, 40.0, obj="a bottle of water")
    right = _event("W02_E001", "W02", 30.0, 40.0, obj="a bottle of oil")
    row = em.relation_label(left, right)
    assert row["relation"] == em.UNRESOLVED_RELATION
    assert row["shared_token_count"] >= 1


def test_wvr_r12_touching_events_are_continuation_or_transition():
    left = _event("W01_E001", "W01", 30.0, 40.0)
    same = _event("W02_E001", "W02", 40.0, 48.0)
    assert em.relation_label(left, same)["relation"] == em.CONTINUATION
    other = _event("W02_E002", "W02", 40.0, 48.0, action="stacking",
                   obj="boxes")
    assert em.relation_label(left, other)["relation"] == em.TRANSITION


def test_wvr_r13_events_with_a_positive_gap_get_no_relation_row():
    left = _event("W01_E001", "W01", 30.0, 40.0)
    right = _event("W02_E001", "W02", 42.0, 50.0)
    assert em.relation_label(left, right) == {}


def test_wvr_r14_relations_only_span_adjacent_valid_windows():
    pairs = em.adjacent_window_pairs()
    assert len(pairs) == 22
    assert pairs[0]["earlier"] == "W01" and pairs[0]["later"] == "W02"
    assert all(pair["shared_end_sec"] - pair["shared_start_sec"] == 24.0
               for pair in pairs)
    rows = em.registry(_records())
    relations = em.relation_candidates(rows)
    for relation in relations:
        assert any(pair["earlier"] == relation["earlier_window"]
                   and pair["later"] == relation["later_window"]
                   for pair in pairs)
    assert all("W00" not in (relation["earlier_window"],
                             relation["later_window"])
               for relation in relations)


# ── WVR-R15~R19 grouping · transition ─────────────────────────────
def test_wvr_r15_same_event_relations_group_without_concat():
    records = _records()
    records["W01"] = _record("W01", [_collapsed(30.0, 40.0)])
    records["W02"] = _record("W02", [_collapsed(35.0, 45.0)])
    rows = em.registry(records)
    relations = em.relation_candidates(rows)
    groups = em.group_events(rows, relations)
    merged = [group for group in groups if group["member_count"] > 1]
    assert merged, "겹치는 동일 event가 합쳐지지 않았다"
    assert merged[0]["members"] == ["W01_E001", "W02_E001"]
    assert merged[0]["start_sec"] == 30.0 and merged[0]["end_sec"] == 45.0
    assert merged[0]["source_windows"] == ["W01", "W02"]
    assert sum(group["member_count"] for group in groups) == len(rows)


def test_wvr_r16_conflicting_events_are_not_grouped():
    records = _records()
    records["W01"] = _record("W01", [_collapsed(30.0, 40.0, actor="a chef",
                                                action="pouring",
                                                obj="liquid into a bowl")])
    records["W02"] = _record("W02", [_collapsed(30.0, 40.0, actor="a worker",
                                                action="stacking",
                                                obj="boxes")])
    rows = em.registry(records)
    relations = em.relation_candidates(rows)
    groups = em.group_events(rows, relations)
    assert all(group["member_count"] == 1 for group in groups
               if set(group["members"]) <= {"W01_E001", "W02_E001"})
    assert any(row["relation"] == em.CONFLICT for row in relations)


def test_wvr_r17_groups_are_time_ordered_and_ids_deterministic():
    rows = em.registry(_records())
    relations = em.relation_candidates(rows)
    first = em.group_events(rows, relations)
    second = em.group_events(rows, relations)
    assert [group["group_id"] for group in first] == [
        group["group_id"] for group in second]
    assert first[0]["group_id"] == "G001"
    assert all(first[index]["start_sec"] <= first[index + 1]["start_sec"]
               for index in range(len(first) - 1))
    assert all(group["mixed_signature"] is False for group in first)


def test_wvr_r18_transitions_are_candidates_between_consecutive_groups():
    rows = em.registry(_records())
    groups = em.group_events(rows, em.relation_candidates(rows))
    transitions = em.group_transitions(groups)
    assert len(transitions) == len(groups) - 1
    assert all(row["role"] == "CANDIDATE_LABEL_NOT_FACTUAL_AUTHORITY"
               for row in transitions)
    assert all(row["from_group"] != row["to_group"] for row in transitions)


def test_wvr_r19_grouping_refuses_a_concat_fallback(monkeypatch):
    rows = em.registry(_records())
    monkeypatch.setattr(em, "CONCAT_FALLBACK_ALLOWED", True)
    with pytest.raises(em.EventMapError):
        em.group_events(rows, [])


# ── WVR-R20~R24 coverage ──────────────────────────────────────────
def test_wvr_r20_window_coverage_excludes_the_invalid_window():
    rows = em.registry(_records())
    coverage = em.coverage_map(rows)
    assert coverage["window_coverage_sec"] == 576.0
    assert coverage["window_coverage_pct"] == 96.0
    assert coverage["video_sec"] == 600.0


def test_wvr_r21_the_first_24_seconds_stay_unresolved():
    rows = em.registry(_records())
    coverage = em.coverage_map(rows)
    assert [0.0, 24.0] in coverage["unresolved_intervals"]
    assert [0.0, 24.0] in coverage["invalid_window_only_intervals"]
    assert coverage["status_seconds"]["INVALID_WINDOW_ONLY"] >= 24.0
    assert all(row[0] < 48.0 for row in
               coverage["invalid_window_only_intervals"]),         "INVALID_WINDOW_ONLY이 W00 구간 밖으로 나갔다"
    assert coverage["unresolved_sec"] > 0.0


def test_wvr_r22_event_and_redundant_coverage_are_deterministic_unions():
    rows = [_event("W01_E001", "W01", 24.0, 40.0),
            _event("W02_E001", "W02", 30.0, 50.0)]
    coverage = em.coverage_map(rows)
    assert coverage["event_coverage_sec"] == 26.0
    assert coverage["event_coverage_intervals"] == [[24.0, 50.0]]
    assert coverage["redundant_event_coverage_sec"] == 10.0
    assert coverage["unresolved_sec"] == 574.0
    assert em.union_length([(0.0, 10.0), (5.0, 12.0), (20.0, 22.0)]) == 14.0
    assert em.union_intervals([(0.0, 10.0), (5.0, 12.0), (20.0, 22.0)]) == [
        [0.0, 12.0], [20.0, 22.0]]
    assert em.complement_intervals([(0.0, 590.0)]) == [[590.0, 600.0]]
    assert em.complement_intervals([(10.0, 20.0)]) == [
        [0.0, 10.0], [20.0, 600.0]]
    assert em.complement_intervals([(0.0, 600.0)]) == []


def test_wvr_r23_segment_status_distinguishes_single_and_multi_window():
    rows = [_event("W01_E001", "W01", 24.0, 40.0),
            _event("W02_E001", "W02", 30.0, 50.0)]
    coverage = em.coverage_map(rows)
    statuses = {row["status"] for row in coverage["segments"]}
    assert em.MULTI_OBSERVED in statuses
    assert em.SINGLE_OBSERVED in statuses
    assert em.INVALID_ONLY in statuses
    assert em.UNRESOLVED_COVERAGE in statuses
    assert abs(sum(coverage["status_seconds"].values()) - 600.0) < 1e-6


def test_wvr_r24_coverage_reports_the_caveat_and_no_synthetic_events():
    coverage = em.coverage_map(em.registry(_records()))
    assert coverage["caveat"] == em.COVERAGE_CAVEAT
    assert coverage["synthetic_event_inserted"] is False


# ── WVR-R25~R28 chapter candidate ─────────────────────────────────
def _chapter_groups():
    """actor 유지 · 내용이 중간에 완전히 바뀌는 합성 group 열."""
    groups = []
    for index in range(12):
        start = 24.0 + index * 40.0
        if index < 5:
            action, obj = "pouring", "liquid bowl"
        else:
            action, obj = "stacking", "boxes shelf"
        groups.append({"group_id": "G%03d" % (index + 1),
                       "start_sec": start, "end_sec": start + 40.0,
                       "actor": "person", "action": action,
                       "object_or_state": obj,
                       "members": ["E%03d" % (index + 1)],
                       "member_count": 1, "source_windows": ["W%02d" % index],
                       "distinct_signature_count": 1,
                       "mixed_signature": False})
    return groups


def test_wvr_r25_chapter_boundaries_come_from_event_content():
    groups = _chapter_groups()
    signals = em.boundary_signals(groups)
    boundary = [row for row in signals if row["is_boundary_candidate"]]
    assert boundary, "내용이 완전히 바뀌었는데 boundary 후보가 없다"
    assert boundary[0]["group_id"] == "G006"
    assert boundary[0]["sustained_content_change"] is True
    assert boundary[0]["actor_changed"] is False
    rows = em.chapter_candidates(groups)
    assert rows["boundary_source"].startswith("event content")
    assert rows["window_grid_used_as_boundary"] is False
    assert [row["chapter_id"] for row in rows["chapters"]] == ["CH01", "CH02"]
    assert rows["chapters"][1]["start_sec"] == 224.0


def test_wvr_r26_an_actor_change_is_also_a_boundary_signal():
    groups = _chapter_groups()
    for group in groups[6:]:
        group["actor"] = "another person"
    signals = em.boundary_signals(groups)
    actor_rows = [row for row in signals if row["actor_changed"]]
    assert actor_rows and actor_rows[0]["group_id"] == "G007"
    assert actor_rows[0]["is_boundary_candidate"] is True


def test_wvr_r27_min_chapter_sec_suppresses_short_chapters():
    groups = _chapter_groups()
    for index, group in enumerate(groups):
        group["start_sec"] = 24.0 + index * 10.0
        group["end_sec"] = group["start_sec"] + 10.0
    rows = em.chapter_candidates(groups)
    assert rows["min_chapter_sec"] == 60.0
    assert rows["suppressed"], "60초 미만 boundary가 억제되지 않았다"
    assert all(row["reason"] == "MIN_CHAPTER_SEC" for row in rows["suppressed"])
    assert len(rows["chapters"]) == 1


def test_wvr_r28_chapters_partition_every_group_without_titles():
    groups = _chapter_groups()
    rows = em.chapter_candidates(groups)
    covered = [group_id for row in rows["chapters"]
               for group_id in row["group_ids"]]
    assert covered == [group["group_id"] for group in groups]
    assert all("title" not in row for row in rows["chapters"])
    assert all(row["semantic_boundary_confirmed"] is False
               for row in rows["chapters"])
    assert rows["semantic_verdict_by_executor"] is False


# ── WVR-R29~R32 산출물·경계 ───────────────────────────────────────
def test_wvr_r29_frame_stamps_are_traceability_only():
    stamps = em.frame_stamps(24.0, 30.0, [22.0, 24.0, 26.0, 28.0, 30.0])
    assert stamps == [24.0, 26.0, 28.0]
    assert em.frame_stamps(0.0, 24.0, []) == []


def test_wvr_r30_the_source_manifest_gate_detects_drift():
    rows = json.loads(SOURCES.read_text(encoding="utf-8"))["valid_sources"]
    assert em.source_manifest(rows)["unchanged"] is True
    tampered = dict(rows)
    first = sorted(tampered)[0]
    tampered[first] = "0" * 64
    assert em.source_manifest(tampered)["unchanged"] is False
    partial = {key: value for key, value in rows.items()
               if key != sorted(rows)[1]}
    assert em.source_manifest(partial)["unchanged"] is False


def test_wvr_r31_the_builder_refuses_drifted_sources(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    names = ["shadow_v1_W%02d%s" % (index, suffix)
             for index in range(24) for suffix in (".json", "_raw.txt")]
    for name in names + [em.FRAME_BANK_MANIFEST]:
        source = RUNS / name
        if not source.is_file():
            pytest.skip("source가 없다: %s" % name)
        shutil.copy2(source, runs / name)
    built = builder.build(runs)
    assert built["summary"]["executor_state"]["state"] == em.EXECUTOR_STATE
    assert built["registry"]["event_count"] > 0
    assert built["candidate_map"]["artifact_name"] == "CANDIDATE_EVENT_MAP"
    assert built["coverage"]["unresolved_intervals"] == [[0.0, 24.0]]
    assert built["registry"]["invalid_sources"]["W00"]["status"] == \
        "WINDOW_INVALID"
    assert "W00" not in built["registry"]["events_per_window"]
    (runs / "shadow_v1_W03_raw.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs)


def test_wvr_r32_boundaries_and_prior_state_are_untouched():
    assert em.PRIOR_STATE["WVR_EVENT_EXTRACTION_SHADOW_V1"] == \
        "CLOSED / INCONCLUSIVE"
    assert em.PRIOR_STATE["SUBDIVISION_family"] == "STOPPED / NOT SUFFICIENT"
    assert em.PRIOR_STATE["W00"].startswith("WINDOW_INVALID")
    assert em.PRIOR_STATE["WVR_W00_ZERO_DURATION_EXEMPLAR_ISOLATION_V1"
                          ].startswith("NOT EXECUTED")
    assert em.BOUNDARY_CONTRACT.startswith("local window boundary ≠")
    if SUBMISSION.is_file():
        assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    source = VALIDATOR.read_text(encoding="utf-8")
    for name in ("w00_not_an_event_source", "no_synthetic_event",
                 "unresolved_preserved", "deterministic_rebuild",
                 "chapter_boundaries_not_all_on_window_grid",
                 "no_new_inference"):
        assert '"%s":' % name in source, "validator가 %s를 빠뜨렸다" % name
    assert '"w00_not_an_event_source": all(\n            row["source_window"] in em.VALID_SOURCE_WINDOWS\n            for row in events),' in source, "validator의 W00 검사가 실제 계산이 아니다"
    assert '"chapter_boundaries_not_all_on_window_grid": bool(boundaries)\n        and not all(abs(value % WINDOW_GRID_SEC) < 1e-6\n                    for value in boundaries),' in source, "validator의 격자 검사가 실제 계산이 아니다"
    builder_source = BUILDER.read_text(encoding="utf-8")
    assert "generate(" not in builder_source, "생성 호출이 들어왔다"
    assert "AutoProcessor" not in builder_source
    assert "torch" not in builder_source


# ── WVR-R33~R37 남은 구멍 (정렬 · 총원 · 지속성 · builder 게이트) ────
def test_wvr_r33_groups_are_sorted_even_when_sources_are_out_of_order():
    """뒤 창이 앞 시각 event를 담고 있어도 group은 시간순이어야 한다."""
    records = _records()
    records["W01"] = _record("W01", [_collapsed(60.0, 66.0, action="late",
                                                obj="thing late")])
    records["W03"] = _record("W03", [_collapsed(26.0, 30.0, action="early",
                                                obj="thing early")])
    rows = em.registry(records)
    groups = em.group_events(rows, em.relation_candidates(rows))
    starts = [group["start_sec"] for group in groups]
    assert starts == sorted(starts), "group이 시간순으로 정렬되지 않았다"
    assert groups[0]["members"][0].startswith("W03"), \
        "가장 이른 event가 첫 group이 아니다"
    assert [group["group_id"] for group in groups] == [
        "G%03d" % (index + 1) for index in range(len(groups))]


def test_wvr_r34_a_lost_member_is_caught_by_the_total_check(monkeypatch):
    rows = em.registry(_records())
    relations = em.relation_candidates(rows)
    original = em.bucket_members

    def _drop(rows_in, find):
        buckets = original(rows_in, find)
        first = sorted(buckets)[0]
        buckets.pop(first)
        return buckets

    monkeypatch.setattr(em, "bucket_members", _drop)
    with pytest.raises(em.EventMapError):
        em.group_events(rows, relations)


def test_wvr_r35_a_returning_topic_is_not_a_sustained_change():
    """k-1과는 disjoint지만 k-2와 겹치면 지속된 변화가 아니다."""
    groups = []
    for index in range(6):
        start = 24.0 + index * 40.0
        action, obj = (("pouring", "liquid bowl") if index % 2 == 0
                       else ("stacking", "boxes shelf"))
        groups.append({"group_id": "G%03d" % (index + 1),
                       "start_sec": start, "end_sec": start + 40.0,
                       "actor": "person", "action": action,
                       "object_or_state": obj,
                       "members": ["E%03d" % (index + 1)],
                       "member_count": 1, "source_windows": ["W01"],
                       "distinct_signature_count": 1,
                       "mixed_signature": False})
    signals = em.boundary_signals(groups)
    alternating = [row for row in signals if row["group_id"] != "G002"]
    assert all(row["content_disjoint_prev"] for row in signals)
    assert all(row["sustained_content_change"] is False
               for row in alternating), \
        "번갈아 돌아오는 주제가 지속된 변화로 잡혔다"
    assert all(row["is_boundary_candidate"] is False for row in alternating)
    assert len(em.chapter_candidates(groups)["chapters"]) == 1


def test_wvr_r36_the_builder_gates_on_source_kind_and_flags(tmp_path,
                                                            monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    names = ["shadow_v1_W%02d%s" % (index, suffix)
             for index in range(24) for suffix in (".json", "_raw.txt")]
    for name in names + [em.FRAME_BANK_MANIFEST]:
        source = RUNS / name
        if not source.is_file():
            pytest.skip("source가 없다: %s" % name)
        shutil.copy2(source, runs / name)

    monkeypatch.setattr(em, "NEW_INFERENCE_ALLOWED", True)
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    monkeypatch.setattr(em, "NEW_INFERENCE_ALLOWED", False)
    monkeypatch.setattr(em, "SYNTHETIC_EVENT_ALLOWED", True)
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    monkeypatch.setattr(em, "SYNTHETIC_EVENT_ALLOWED", False)

    record_path = runs / "shadow_v1_W04.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["event"] = "SOME_OTHER_EVENT"
    record_path.write_text(json.dumps(record, ensure_ascii=False),
                           encoding="utf-8")
    monkeypatch.setattr(em, "source_manifest",
                        lambda observed: {"unchanged": True,
                                          "manifest_sha256": "patched",
                                          "observed_count": len(observed),
                                          "expected_count": 46,
                                          "expected_manifest_sha256": "x"})
    with pytest.raises(builder.BuildError):
        builder.build(runs)


def test_wvr_r37_the_builder_writes_no_generative_call():
    source = BUILDER.read_text(encoding="utf-8")
    for token in ("model.generate", "AutoProcessor", "import torch",
                  "openai", "anthropic"):
        assert token not in source, "생성 경로가 들어왔다: %s" % token
    assert "wvr_event_map_v1" in source
