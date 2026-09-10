"""Conservative Event Map shadow 계약 (2026-09-10 · WVR-T01~T33).

```
목적   리뷰어 STITCHABLE는 상위 group으로, MATERIAL_CONFLICT는 alternative
      observation으로 보존하는 whole-video 표현을 만든다
계약   새 추론 0회 · conflict 해결 금지 · 승자 선택 금지 · event 유실 0 ·
      [0,24) synthetic fill 금지 · W00 사용 금지 · narrative 생성 금지 ·
      executor는 PASS/HOLD를 계산하지 않는다
```
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_conservative_map_v1 as cm
import wvr_shadow_v1 as sh
import wvr_stitch_v1 as st

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1_2026-09-10.md")
PREREG = ROOT / PREREG_REL
BUILDER = ROOT / "scripts/wvr_cmap_build.py"
VALIDATOR = ROOT / "scripts/wvr_cmap_validate.py"
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


builder = _module(BUILDER, "wvr_cmap_build_mod")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(name):
    return json.loads((RUNS / name).read_text(encoding="utf-8"))


REGISTRY = _load("event_map_v1_registry.json")
VERDICTS = _load("stitch_v1_verdicts.json")
MAPPING = _load("stitch_v1_blind_map.json")
BANK = _load("shadow_frame_bank.json")
BANK_TIMES = tuple(row["time_sec"] for row in BANK["frames"])
EVENTS = REGISTRY["events"]


def _built():
    return cm.build_document(EVENTS, VERDICTS, BANK_TIMES,
                             provenance=cm.provenance_stub())


# ── WVR-T01~T06 대상·어휘·사전등록 동결 ─────────────────────────────
def test_wvr_t01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_t02_every_prohibition_flag_is_closed():
    assert cm.CONFLICT_RESOLUTION_ALLOWED is False
    assert cm.PREFERRED_SOURCE_ALLOWED is False
    assert cm.NEW_INFERENCE_ALLOWED is False
    assert cm.NEW_LLM_CALL_ALLOWED is False
    assert cm.TRACK_A_EVIDENCE_ALLOWED is False
    assert cm.SYNTHETIC_FILL_ALLOWED is False
    assert cm.EVENT_DELETION_ALLOWED is False
    assert cm.EVENT_TEXT_MUTATION_ALLOWED is False
    assert cm.NARRATIVE_GENERATION_ALLOWED is False
    assert cm.CHAPTER_ALLOWED is False
    assert cm.VERDICT_BY_EXECUTOR is False


def test_wvr_t03_the_node_vocabulary_is_frozen():
    assert cm.NODE_TYPES == ("CONSENSUS_EVENT", "CONTINUATION_GROUP",
                             "TRANSITION", "CONFLICT_BLOCK",
                             "SINGLE_SOURCE_EVENT", "UNRESOLVED_GAP")
    assert cm.GROUP_TYPES == ("STITCH_GROUP", "CONFLICT_REGION")
    assert cm.RELATION_TO_NODE_TYPE == {
        "SAME_EVENT": "CONSENSUS_EVENT",
        "CONTINUATION": "CONTINUATION_GROUP",
        "TRANSITION": "TRANSITION"}
    assert cm.FINAL_VERDICTS == ("CONSERVATIVE_EVENT_MAP_PASS",
                                 "CONSERVATIVE_EVENT_MAP_HOLD",
                                 "CONSERVATIVE_EVENT_MAP_INCONCLUSIVE")


def test_wvr_t04_the_verdict_index_demands_a_complete_frozen_verdict_file():
    index = cm.verdict_index(VERDICTS)
    assert len(index) == 22
    assert sum(1 for row in index.values()
               if row["top_verdict"] == "MATERIAL_CONFLICT") == 10
    assert sum(1 for row in index.values()
               if row["top_verdict"] == "STITCHABLE") == 12
    with pytest.raises(cm.MapError):
        cm.verdict_index({"verdicts": [], "complete": False})
    broken = json.loads(json.dumps(VERDICTS))
    broken["verdicts"][0]["top_verdict"] = "PROBABLY_FINE"
    with pytest.raises(cm.MapError):
        cm.verdict_index(broken)


def test_wvr_t05_w00_is_never_a_valid_source():
    assert cm.INVALID_SOURCE_WINDOWS == ("W00",)
    assert "W00" not in cm.VALID_SOURCE_WINDOWS
    assert all(event["source_window"] in cm.VALID_SOURCE_WINDOWS
               for event in EVENTS)


def test_wvr_t06_the_source_hashes_are_frozen_in_the_module():
    assert cm.FROZEN_HASHES["event_map_v1_registry.json"] == _sha256_file(
        RUNS / "event_map_v1_registry.json")
    assert cm.FROZEN_HASHES["stitch_v1_verdicts.json"] == _sha256_file(
        RUNS / "stitch_v1_verdicts.json")
    assert cm.FROZEN_HASHES["stitch_v1_blind_map.json"] == _sha256_file(
        RUNS / "stitch_v1_blind_map.json")
    assert cm.FROZEN_HASHES["shadow_frame_bank.json"] == _sha256_file(
        RUNS / "shadow_frame_bank.json")


# ── WVR-T07~T12 region 유도 ────────────────────────────────────────
def test_wvr_t07_regions_tile_the_whole_video_on_the_24_sec_grid():
    regions = cm.regions(VERDICTS)
    assert len(regions) == 11
    assert regions[0]["start_sec"] == 0.0
    assert regions[-1]["end_sec"] == 600.0
    for left, right in zip(regions, regions[1:]):
        assert left["end_sec"] == right["start_sec"], "region이 끊겼다"
    assert sum(row["end_sec"] - row["start_sec"] for row in regions) == 600.0
    assert all(row["start_sec"] % 24 == 0 and row["end_sec"] % 24 == 0
               for row in regions)


def test_wvr_t08_the_region_schedule_matches_the_frozen_expectation():
    derived = [(row["region_id"], row["start_sec"], row["end_sec"],
                row["node_class"], tuple(row["overlap_ids"]))
               for row in cm.regions(VERDICTS)]
    assert derived == [tuple(row) for row in cm.EXPECTED_REGION_SCHEDULE]


def test_wvr_t09_every_overlap_is_assigned_to_exactly_one_region():
    seen = [overlap_id for row in cm.regions(VERDICTS)
            for overlap_id in row["overlap_ids"]]
    assert sorted(seen) == sorted(row["overlap_id"] for row in st.overlaps())
    assert len(seen) == len(set(seen)) == 22


def test_wvr_t10_a_changed_verdict_file_breaks_the_region_guard():
    flipped = json.loads(json.dumps(VERDICTS))
    for row in flipped["verdicts"]:
        if row["overlap_id"] == "O02":
            row["relation"], row["top_verdict"] = "SAME_EVENT", "STITCHABLE"
    with pytest.raises(cm.MapError):
        cm.regions(flipped)


def test_wvr_t11_the_unresolved_gap_is_preserved_and_never_filled():
    regions = cm.regions(VERDICTS)
    gap = [row for row in regions if row["node_class"] == cm.UNRESOLVED]
    assert [(row["start_sec"], row["end_sec"]) for row in gap] == [(0.0, 24.0)]
    assert gap[0]["source_windows"] == []
    document = _built()
    node = document["nodes"]["unresolved_gaps"][0]
    assert node["node_type"] == "UNRESOLVED_GAP"
    assert node["events"] == [] and node["filled"] is False
    assert node["invalid_source_windows"] == ["W00"]
    assert node["resolution"] == "NONE"


def test_wvr_t12_region_durations_are_derived_not_asserted():
    coverage = cm.coverage(cm.regions(VERDICTS))
    assert coverage["conflict_duration_sec"] == 240.0
    assert coverage["stitchable_duration_sec"] == 288.0
    assert coverage["single_source_duration_sec"] == 48.0
    assert coverage["unresolved_duration_sec"] == 24.0
    assert coverage["total_sec"] == 600.0
    assert coverage["semantic_truth_percentage"] is None


# ── WVR-T13~T19 node 구성 ─────────────────────────────────────────
def test_wvr_t13_stitchable_overlaps_become_typed_stitch_groups():
    groups = _built()["nodes"]["stitch_groups"]
    assert len(groups) == 12
    counts = {name: sum(1 for row in groups if row["node_type"] == name)
              for name in ("CONSENSUS_EVENT", "CONTINUATION_GROUP",
                           "TRANSITION")}
    assert counts == {"CONSENSUS_EVENT": 6, "CONTINUATION_GROUP": 5,
                      "TRANSITION": 1}
    for row in groups:
        assert row["reviewer_status"] == "STITCHABLE"
        assert row["description_generated"] is False
        assert "description" not in row
        assert len(row["sources"]) == 2
        assert row["ordered_members"], "group이 비었다"
        starts = [member["clipped_start"] for member in row["ordered_members"]]
        assert starts == sorted(starts), "member 시간순이 깨졌다"


def test_wvr_t14_conflict_overlaps_keep_both_observation_sets():
    blocks = _built()["nodes"]["conflict_blocks"]
    assert len(blocks) == 10
    for row in blocks:
        assert row["node_type"] == "CONFLICT_BLOCK"
        assert row["reviewer_relation"] == "CONFLICT"
        assert row["reviewer_status"] == "MATERIAL_CONFLICT"
        assert row["resolution"] == "NONE"
        assert row["preferred_source"] is None
        one, two = row["observation_set_1"], row["observation_set_2"]
        assert one["source"] != two["source"]
        assert one["events"] and two["events"], "한쪽 관측이 비었다"
        assert one["event_count"] == len(one["events"])
        assert "선호" in row["ordering_basis"]


def test_wvr_t15_adjacent_conflict_blocks_form_conflict_regions():
    document = _built()
    conflict_regions = document["nodes"]["conflict_regions"]
    assert len(conflict_regions) == 4
    assert [(row["start_sec"], row["end_sec"]) for row in conflict_regions] \
        == [(48.0, 96.0), (192.0, 264.0), (312.0, 384.0), (480.0, 528.0)]
    assert [row["member_overlaps"] for row in conflict_regions] == [
        ["O02", "O03"], ["O08", "O09", "O10"], ["O13", "O14", "O15"],
        ["O20", "O21"]]
    blocks = {row["node_id"] for row in document["nodes"]["conflict_blocks"]}
    for row in conflict_regions:
        assert set(row["member_blocks"]) <= blocks
        assert row["resolution"] == "NONE"


def test_wvr_t16_single_source_regions_carry_exactly_one_window():
    nodes = _built()["nodes"]["single_source"]
    assert len(nodes) == 2
    assert [(row["start_sec"], row["end_sec"]) for row in nodes] == [
        (24.0, 48.0), (576.0, 600.0)]
    assert [row["source_window"] for row in nodes] == ["W01", "W23"]
    for row in nodes:
        assert row["node_type"] == "SINGLE_SOURCE_EVENT"
        assert row["events"]
        assert {member["source_window"] for member in row["events"]} == {
            row["source_window"]}


def test_wvr_t17_node_ids_are_deterministic_and_time_ordered():
    document = _built()
    assert [row["node_id"] for row in document["nodes"]["conflict_blocks"]] \
        == ["CB%03d" % index for index in range(1, 11)]
    assert [row["node_id"] for row in document["nodes"]["stitch_groups"]] \
        == ["SG%03d" % index for index in range(1, 13)]
    assert [row["node_id"] for row in document["nodes"]["conflict_regions"]] \
        == ["CR01", "CR02", "CR03", "CR04"]
    assert [row["region_id"] for row in document["regions"]] \
        == ["R%02d" % index for index in range(1, 12)]
    for group in ("conflict_blocks", "stitch_groups"):
        rows = document["nodes"][group]
        assert [row["start_sec"] for row in rows] == sorted(
            row["start_sec"] for row in rows)


def test_wvr_t18_every_overlap_interval_hangs_on_a_node_no_silent_concat():
    document = _built()
    attached = {row["overlap_id"]
                for row in document["nodes"]["stitch_groups"]}
    attached |= {row["overlap_id"]
                 for row in document["nodes"]["conflict_blocks"]}
    assert attached == {row["overlap_id"] for row in st.overlaps()}
    assert document["silent_concat"] is False
    for region in document["regions"]:
        if region["node_class"] in (cm.CONFLICT, cm.STITCHABLE):
            assert region["node_ids"], "overlap region에 node가 없다"


def test_wvr_t19_frame_stamps_stay_inside_their_node_and_on_the_grid():
    document = _built()
    rows = (document["nodes"]["stitch_groups"]
            + document["nodes"]["conflict_blocks"])
    for row in rows:
        assert len(row["frame_stamps"]) == sh.SHARED_FRAMES_PER_OVERLAP
        assert all(row["start_sec"] <= stamp < row["end_sec"]
                   for stamp in row["frame_stamps"])
        assert all(stamp in BANK_TIMES for stamp in row["frame_stamps"])


# ── WVR-T20~T25 lineage · 유실 0 ──────────────────────────────────
def test_wvr_t20_all_160_source_events_are_accounted_for():
    document = _built()
    lineage = document["lineage"]
    assert len(lineage) == len(EVENTS) == 160
    assert {row["event_id"] for row in lineage} == {
        event["event_id"] for event in EVENTS}
    assert document["lineage_summary"]["events_missing"] == 0
    assert document["lineage_summary"]["events_represented"] == 160
    for row in lineage:
        assert row["primary_region"], "primary region이 없다"
        assert row["node_memberships"], "어떤 node에도 속하지 않았다"
        assert row["lineage_type"] in cm.LINEAGE_TYPES


def test_wvr_t21_a_dropped_source_event_is_detected():
    trimmed = [event for event in EVENTS
               if event["event_id"] != "W07_E003"]
    with pytest.raises(cm.MapError):
        cm.build_document(trimmed, VERDICTS, BANK_TIMES,
                          provenance=cm.provenance_stub())


def test_wvr_t22_straddling_events_record_every_region_they_touch():
    lineage = {row["event_id"]: row for row in _built()["lineage"]}
    straddling = [row for row in lineage.values() if row["also_in_regions"]]
    assert len(straddling) >= 1
    assert lineage["W01_E008"]["primary_region"] == "R02"
    assert lineage["W01_E008"]["also_in_regions"] == ["R03"]
    assert lineage["W01_E008"]["lineage_type"] == "single_source_event"
    # 같은 event가 conflict block 관측으로도 남아 있어야 한다 (삭제 금지)
    assert any(node.startswith("CB")
               for node in lineage["W01_E008"]["node_memberships"])


def test_wvr_t23_the_primary_region_is_the_largest_overlap_earlier_on_ties():
    assert cm.primary_region(
        {"start_sec": 46.0, "end_sec": 49.0},
        cm.regions(VERDICTS))["region_id"] == "R02"
    assert cm.primary_region(
        {"start_sec": 44.0, "end_sec": 52.0},
        cm.regions(VERDICTS))["region_id"] == "R02"       # 4:4 동률 → 이른 쪽
    assert cm.primary_region(
        {"start_sec": 46.0, "end_sec": 60.0},
        cm.regions(VERDICTS))["region_id"] == "R03"


def test_wvr_t24_event_text_and_order_are_preserved_verbatim():
    document = _built()
    source = {event["event_id"]: event for event in EVENTS}
    seen = set()
    for row in cm.all_members(document):
        origin = source[row["event_id"]]
        for field in ("actor", "action", "object_or_state"):
            assert row[field] == origin[field], "event 텍스트가 바뀌었다"
        assert row["original_start"] == origin["start_sec"]
        assert row["original_end"] == origin["end_sec"]
        seen.add(row["event_id"])
    assert seen == set(source)
    for window in cm.VALID_SOURCE_WINDOWS:
        order = [row["event_id"] for row in document["lineage"]
                 if row["source_window"] == window]
        assert order == sorted(order), "창 안의 event 순서가 바뀌었다"


def test_wvr_t25_no_event_is_invented_and_no_invalid_source_leaks_in():
    document = _built()
    assert document["summary_counts"]["invalid_source_dependency_count"] == 0
    assert document["provenance"]["new_inference_count"] == 0
    assert document["provenance"]["new_llm_call_count"] == 0
    poisoned = list(EVENTS) + [{
        "event_id": "W00_E001", "source_window": "W00",
        "source_window_span": [0.0, 48.0], "start_sec": 4.0, "end_sec": 8.0,
        "actor": "person", "action": "standing", "object_or_state": "kitchen",
        "collapsed_index": 0}]
    with pytest.raises(cm.MapError):
        cm.build_document(poisoned, VERDICTS, BANK_TIMES,
                          provenance=cm.provenance_stub())


# ── WVR-T26~T30 conflict 무해결 · 결정성 · packet ──────────────────
def test_wvr_t26_no_conflict_is_resolved_and_no_arm_is_preferred():
    document = _built()
    assert document["summary_counts"]["false_resolution_count"] == 0
    text = json.dumps(document, ensure_ascii=False).lower()
    for word in cm.FORBIDDEN_FIELD_NAMES:
        assert '"%s"' % word not in text, "금지 필드가 들어갔다: %s" % word
    assert cm.false_resolutions(document) == []


def test_wvr_t27_forcing_a_conflict_into_a_stitch_group_is_red():
    document = _built()
    block = document["nodes"]["conflict_blocks"][0]
    document["nodes"]["stitch_groups"].append({
        "node_id": "SG999", "node_type": "CONSENSUS_EVENT",
        "overlap_id": block["overlap_id"], "relation": "SAME_EVENT",
        "reviewer_status": "STITCHABLE", "sources": ["W01", "W02"],
        "start_sec": block["start_sec"], "end_sec": block["end_sec"],
        "ordered_members": [], "description_generated": False,
        "frame_stamps": []})
    assert cm.false_resolutions(document), "conflict 오병합이 감지되지 않았다"


def test_wvr_t28_dropping_one_observation_set_is_red():
    document = _built()
    document["nodes"]["conflict_blocks"][2]["observation_set_2"]["events"] = []
    document["nodes"]["conflict_blocks"][2]["observation_set_2"][
        "event_count"] = 0
    assert cm.false_resolutions(document)
    document = _built()
    document["nodes"]["conflict_blocks"][1]["preferred_source"] = "W08"
    assert cm.false_resolutions(document)


def test_wvr_t29_the_document_is_canonically_stable_across_rebuilds():
    first = cm.canonical(_built())
    second = cm.canonical(_built())
    assert first == second
    assert '"indent"' not in first
    assert json.loads(first)["schema"] == "wvr_conservative_event_map_v1"


def test_wvr_t30_the_chapter_input_packet_asks_and_never_answers():
    document = _built()
    packet = cm.chapter_input_packet(document)
    for question in ("Q1 STRUCTURAL_USABILITY", "Q2 CONFLICT_LOCALIZATION",
                     "Q3 NO_FALSE_RESOLUTION", "Q4 CHAPTER_INPUT_USABILITY"):
        assert question in packet
    for verdict in cm.FINAL_VERDICTS:
        assert verdict not in packet.replace(
            "CONSERVATIVE_EVENT_MAP_PASS / HOLD / INCONCLUSIVE", "")
    assert "NOT_ADJUDICATED" in packet
    assert cm.executor_state(document)["verdict"] is None
    assert cm.executor_state(document)["state"] == "EXECUTED / REVIEW_PENDING"


# ── WVR-T31~T33 도구 게이트 · 경계 ─────────────────────────────────
def test_wvr_t31_the_builder_refuses_drifted_sources_and_open_flags(
        tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    for name in ("event_map_v1_registry.json", "stitch_v1_verdicts.json",
                 "stitch_v1_blind_map.json", "shadow_frame_bank.json"):
        (runs / name).write_bytes((RUNS / name).read_bytes())
    built = builder.build(runs)
    assert built["summary"]["events_missing"] == 0

    drifted = json.loads((runs / "stitch_v1_verdicts.json")
                         .read_text(encoding="utf-8"))
    drifted["verdicts"][0]["note"] = "tampered"
    (runs / "stitch_v1_verdicts.json").write_text(
        json.dumps(drifted, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    (runs / "stitch_v1_verdicts.json").write_bytes(
        (RUNS / "stitch_v1_verdicts.json").read_bytes())

    for flag in ("CONFLICT_RESOLUTION_ALLOWED", "PREFERRED_SOURCE_ALLOWED",
                 "NEW_INFERENCE_ALLOWED", "NEW_LLM_CALL_ALLOWED",
                 "TRACK_A_EVIDENCE_ALLOWED", "SYNTHETIC_FILL_ALLOWED",
                 "EVENT_DELETION_ALLOWED", "NARRATIVE_GENERATION_ALLOWED",
                 "CHAPTER_ALLOWED", "VERDICT_BY_EXECUTOR"):
        monkeypatch.setattr(cm, flag, True)
        with pytest.raises(builder.BuildError):
            builder.build(runs)
        monkeypatch.setattr(cm, flag, False)


def test_wvr_t32_the_validator_computes_its_checks_from_the_artifacts():
    source = VALIDATOR.read_text(encoding="utf-8")
    for expression in (
            'cm.false_resolutions(document) == []',
            'document["lineage_summary"]["events_missing"] == 0',
            'derived == [tuple(row) for row in cm.EXPECTED_REGION_SCHEDULE]',
            'row["preferred_source"] is None',
            'row["resolution"] == "NONE"'):
        assert expression in source, "validator 검사가 실제 계산이 아니다: %s" \
            % expression
    assert "CONSERVATIVE_EVENT_MAP_PASS" not in source, \
        "validator가 최종 판정을 계산한다"


def test_wvr_t33_the_frozen_boundaries_are_untouched():
    assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert not (ROOT / "runs/wvr_light_v1/m9_report_test.json").exists()
    verdicts_now = _sha256_file(RUNS / "stitch_v1_verdicts.json")
    assert verdicts_now == cm.FROZEN_HASHES["stitch_v1_verdicts.json"]
    assert cm.TRACK_A_EVIDENCE_ALLOWED is False
    assert cm.PRODUCTION_PROMOTION_ALLOWED is False
