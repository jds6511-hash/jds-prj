"""Semantic boundary candidate proposal 계약 (2026-09-10 · WVR-B01~B30).

```
구조   Stage A(결정적 blinded packet · LLM 없음) → Stage B(후보별 label만 LLM)
계약   후보는 event 시작 시각 144개뿐 · packet에 시각·창·region·격자·event id 없음 ·
      candidate id는 순열(시간 순서 비노출) · conflict/stitchable 동일 형식 ·
      LLM은 timestamp·chapter를 만들 수 없다 · mapping은 판정 전 봉인 ·
      STRONG+AMBIGUOUS만 packet · WEAK 전량 appendix · executor 판정 금지
```
"""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_boundary_candidate_v1 as bc
import wvr_chapter_v1 as v1
import wvr_conservative_map_v1 as cmap

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1_2026-09-10.md")
PREREG = ROOT / PREREG_REL
SELFCHECK = ROOT / "scripts/wvr_bcand_selfcheck.py"
BUILDER = ROOT / "scripts/wvr_bcand_build.py"
RUNNER = ROOT / "scripts/wvr_bcand_run.py"
PARSER = ROOT / "scripts/wvr_bcand_parse.py"
VALIDATOR = ROOT / "scripts/wvr_bcand_validate.py"
VERDICTS = ROOT / "scripts/wvr_bcand_verdicts.py"
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


builder = _module(BUILDER, "wvr_bcand_build_mod")
verdicts_mod = _module(VERDICTS, "wvr_bcand_verdicts_mod")
DOCUMENT = json.loads((RUNS / bc.SOURCE_MAP_NAME).read_text(encoding="utf-8"))
EVENTS = bc.source_events(DOCUMENT)
CANDIDATES = bc.build_candidates(EVENTS, DOCUMENT)
BY_ID = {row["candidate_id"]: row for row in CANDIDATES}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fake_proposal(candidate_id, label=bc.NO_CHAPTER_TRANSITION):
    return {"candidate_id": candidate_id, "proposal": label,
            "before_activity": "one kind of work",
            "after_activity": "another kind of work",
            "rationale": "the listed lines differ in the kind of work"}


def _payload(ids, label=bc.NO_CHAPTER_TRANSITION):
    return {"candidates": [_fake_proposal(value, label) for value in ids]}


# ── 사전등록·플래그 ───────────────────────────────────────────────
def test_wvr_b01_the_preregistration_is_committed():
    done = subprocess.run(["git", "log", "-1", "--format=%H", "--", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.stdout.strip(), "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()
    assert bc.PREREG == PREREG_REL


def test_wvr_b02_every_prohibition_flag_is_closed():
    for name in bc.FLAGS:
        assert getattr(bc, name) is False, name
    assert bc.PROPOSER_LLM_ALLOWED is True
    bc.assert_flags_closed()
    for name in ("CHAPTER_GENERATION_ALLOWED", "OVERVIEW_GENERATION_ALLOWED",
                 "TRACK_A_INPUT_ALLOWED", "NEW_VLM_INFERENCE_ALLOWED",
                 "MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED",
                 "TIMESTAMP_IN_PACKET_ALLOWED", "RETRY_ALLOWED",
                 "VERDICT_BY_EXECUTOR"):
        assert name in bc.FLAGS


def test_wvr_b03_the_input_is_the_same_frozen_conservative_map():
    assert bc.SOURCE_MAP_NAME == v1.SOURCE_MAP_NAME
    assert bc.SOURCE_MAP_SHA256 == v1.SOURCE_MAP_SHA256
    assert len(EVENTS) == bc.EXPECTED_SOURCE_EVENT_COUNT == 160
    assert all(row["source_window"] not in cmap.INVALID_SOURCE_WINDOWS
               for row in EVENTS)


# ── candidate universe ─────────────────────────────────────────
def test_wvr_b04_candidate_times_are_event_starts_only():
    times = bc.candidate_times(EVENTS)
    assert len(times) == bc.EXPECTED_CANDIDATE_COUNT == 144
    starts = {round(row["start_sec"], 3) for row in EVENTS}
    assert set(times) <= starts
    assert bc.VIDEO_START_SEC not in times
    assert bc.VIDEO_END_SEC not in times
    assert times == sorted(set(times))


def test_wvr_b05_candidate_ids_are_a_deterministic_permutation():
    first = bc.blind_ids(bc.candidate_times(EVENTS))
    second = bc.blind_ids(bc.candidate_times(EVENTS))
    assert [row["candidate_id"] for row in first] \
        == [row["candidate_id"] for row in second]
    assert [row["boundary_sec"] for row in first] \
        == [row["boundary_sec"] for row in second]
    assert [row["candidate_id"] for row in first] \
        == ["C%03d" % (index + 1) for index in range(len(first))]
    ordered = [row["boundary_sec"] for row in
               sorted(first, key=lambda row: row["candidate_id"])]
    assert ordered != sorted(ordered), "id 순서가 시간 순서를 노출한다"


def test_wvr_b06_the_context_window_is_frozen_and_off_grid():
    assert bc.CONTEXT_WINDOW_SEC == 30.0
    assert bc.CONTEXT_WINDOW_SEC % cmap.CELL_SEC != 0
    row = BY_ID["C001"]
    time = row["boundary_sec"]
    expected_before = {event["event_id"] for event in bc.events_between(
        EVENTS, max(bc.VIDEO_START_SEC, time - 30.0), time)}
    expected_after = {event["event_id"] for event in bc.events_between(
        EVENTS, time, min(bc.VIDEO_END_SEC, time + 30.0))}
    assert set(row["before_event_ids"]) == expected_before
    assert set(row["after_event_ids"]) == expected_after


def test_wvr_b07_observation_sets_follow_the_frozen_side_rule():
    seen = {"empty": 0, "single": 0, "multi": 0}
    for row in CANDIDATES:
        for side in (row["before"], row["after"]):
            count = len(side["windows"])
            if count == 0:
                assert side["sets"] == []
                assert side["empty"] is True
                seen["empty"] += 1
            elif count == 1:
                assert len(side["sets"]) == 1
                assert side["sets"][0]["label"] == ""
                seen["single"] += 1
            else:
                assert len(side["sets"]) == count
                assert [entry["label"] for entry in side["sets"]] \
                    == list("ABCD"[:count])
                seen["multi"] += 1
    assert seen["empty"] == 1 and seen["single"] and seen["multi"]


def test_wvr_b08_set_labels_hide_the_window_order():
    assert bc.set_labels("C001", ["W02"]) == {}
    labels = bc.set_labels("C001", ["W02", "W03"])
    assert sorted(labels.values()) == ["A", "B"]
    assert bc.set_labels("C001", ["W03", "W02"]) == labels
    assert bc.set_labels("C002", ["W02", "W03"]) is not None
    flipped = [row for row in CANDIDATES
               for side in (row["before"], row["after"])
               if len(side["windows"]) > 1
               and side["sets"][0]["source_window"] != min(side["windows"])]
    assert flipped, "라벨이 항상 창 id 순서와 같다 — 순서가 노출된다"


def test_wvr_b09_conflict_and_stitchable_sides_look_identical():
    conflict = [row for row in CANDIDATES if row["in_conflict_block"]]
    stitchable = [row for row in CANDIDATES if not row["in_conflict_block"]]
    assert conflict and stitchable
    for group in (conflict, stitchable):
        text = "\n".join(bc.render_block(row) for row in group)
        assert "CONFLICT" not in text
        assert "STITCHABLE" not in text
        assert "SINGLE" not in text.upper().replace("SINGLE_SOURCE", "")
    marks = {"Observation Set" in bc.render_block(row) for row in conflict}
    assert True in marks
    assert True in {"Observation Set" in bc.render_block(row)
                    for row in stitchable}


# ── blinding ───────────────────────────────────────────────────
def test_wvr_b10_a_rendered_block_carries_no_digit_but_its_own_id():
    for row in CANDIDATES[:20] + CANDIDATES[-20:]:
        text = bc.render_block(row)
        assert row["candidate_id"] in text
        stripped = re.sub(r"C\d{3}", "", text)
        assert not re.search(r"\d", stripped), text
        assert "%.1f" % row["boundary_sec"] not in text
        assert "%d" % int(row["boundary_sec"]) not in text


def test_wvr_b11_a_rendered_block_carries_no_geometry_or_event_id():
    text = "\n".join(bc.render_block(row) for row in CANDIDATES)
    for event in EVENTS:
        assert event["event_id"] not in text
        assert event["source_window"] not in text
    assert not re.search(r"\bW\d{2}\b|\bR\d{2}\b|\bCH\d{2}\b", text)
    for metadata in ("source_window", "source_window_id", "window_id",
                     "region_id", "region_class", "region_boundary",
                     "chapter_id", "prior_chapter", "grid_24s", "grid_48s",
                     "earlier_window", "later_window", "24-second grid",
                     "48-second grid"):
        assert metadata not in text
    assert "train window showing cityscape" in text
    assert "walking through train window" in text
    for row in EVENTS[:40]:
        assert row["action"] in text


def test_wvr_b12_the_leakage_audit_catches_injected_geometry():
    clean = bc.leakage_audit([bc.render_block(row) for row in CANDIDATES],
                             EVENTS, CANDIDATES)
    assert clean["violations"] == []
    assert clean["candidate_id_order_differs_from_time_order"] is True
    for poison in ("the boundary is at 400.0 sec", "source window W07",
                   "window_id: W07", "region R05", "region_id: R05",
                   "prior chapter CH03", EVENTS[0]["event_id"]):
        dirty = bc.leakage_audit([poison], EVENTS, CANDIDATES)
        assert dirty["violations"], poison
    natural = bc.leakage_audit(["train window showing cityscape",
                                "blending ingredients in a blender"],
                               EVENTS, CANDIDATES)
    assert natural["violations"] == []


# ── 배치·프롬프트 ─────────────────────────────────────────────────
def test_wvr_b13_batches_are_deterministic_and_cover_every_candidate():
    rows = bc.batches(CANDIDATES)
    assert len(rows) == bc.EXPECTED_BATCH_COUNT == 18
    assert all(len(row["candidate_ids"]) == bc.BATCH_SIZE for row in rows)
    flat = [value for row in rows for value in row["candidate_ids"]]
    assert flat == [row["candidate_id"] for row in CANDIDATES]
    assert len(set(flat)) == bc.EXPECTED_CANDIDATE_COUNT
    assert [row["batch_id"] for row in rows] \
        == ["B%02d" % (index + 1) for index in range(18)]
    assert bc.batches(CANDIDATES) == rows


def test_wvr_b14_the_prompt_is_frozen_and_neutral():
    assert bc.sha256_text(bc.PROPOSER_PROMPT_V1) == bc.PROMPT_TEMPLATE_SHA256
    guidance_banned = ("food preparation", "eating", "sewing",
                       "gift wrapping", "clothing", "400 sec",
                       "v1 chapter sequence")
    assert tuple(bc.FORBIDDEN_PROMPT_STRINGS) == guidance_banned
    guidance = bc.PROPOSER_PROMPT_V1.lower()
    for phrase in guidance_banned:
        assert phrase not in guidance, phrase
    batch = bc.batches(CANDIDATES)[0]
    prompt = bc.render_prompt([BY_ID[value]
                               for value in batch["candidate_ids"]])
    for value in batch["candidate_ids"]:
        assert value in prompt
    for label in bc.PROPOSALS:
        assert label in prompt
    # Errata 2 §30: activity terms in frozen source observations are allowed,
    # but every actor/action/object_or_state line must remain verbatim.
    expected_lines = []
    for value in batch["candidate_ids"]:
        boundary = BY_ID[value]["boundary_sec"]
        for low, high in ((max(bc.VIDEO_START_SEC,
                               boundary - bc.CONTEXT_WINDOW_SEC), boundary),
                          (boundary, min(bc.VIDEO_END_SEC,
                                         boundary + bc.CONTEXT_WINDOW_SEC))):
            for event in EVENTS:
                overlap = max(0.0, min(high, event["end_sec"])
                              - max(low, event["start_sec"]))
                if overlap > 0:
                    expected_lines.append("%s | %s | %s" % (
                        event["actor"], event["action"],
                        event["object_or_state"]))
    for line in set(expected_lines):
        assert prompt.count(line) >= expected_lines.count(line), line
    assert any(phrase in prompt.lower() for phrase in
               ("food", "eat", "sew", "gift", "wrap", "cook", "cloth"))
    assert bc.leakage_audit([prompt], EVENTS, CANDIDATES)["violations"] == []


def test_wvr_b15_the_prompt_never_asks_for_chapters_or_times():
    prompt = bc.render_prompt([BY_ID["C001"]])
    structured_time_fields = ("start_sec", "end_sec", "boundary_sec",
                              "timestamp", "time_sec")
    assert tuple(bc.TIME_FIELDS) == structured_time_fields
    for field in structured_time_fields:
        assert field not in prompt
    for word in ("title", "summary", "dominant_activities", "overview"):
        assert word not in prompt.lower()
    assert "blender" in prompt.lower()
    for poison in ('{"start_sec": 48}', '{"end_sec": 72}',
                   '{"boundary_sec": 48}', '{"timestamp": 48.0}',
                   '{"time": 48}', "move the boundary start time"):
        assert bc.leakage_audit([poison], EVENTS, CANDIDATES)["violations"], poison
    assert bc.CHAPTER_GENERATION_ALLOWED is False


# ── 파싱 ──────────────────────────────────────────────────────
def test_wvr_b16_a_valid_batch_output_parses():
    ids = bc.batches(CANDIDATES)[0]["candidate_ids"]
    raw = "```json\n%s\n```" % json.dumps(
        _payload(ids, bc.STRONG_TRANSITION_CANDIDATE))
    rows = bc.parse_batch(bc.extract_json(raw), ids)
    assert sorted(rows) == sorted(ids)
    assert all(row["proposal"] == bc.STRONG_TRANSITION_CANDIDATE
               for row in rows.values())
    assert all(row["rationale"] for row in rows.values())


def test_wvr_b17_an_unknown_label_is_a_vocabulary_violation():
    ids = ["C001", "C002"]
    payload = _payload(ids)
    payload["candidates"][0]["proposal"] = "PROBABLY_A_BOUNDARY"
    with pytest.raises(bc.CandidateError, match="VOCABULARY_VIOLATION"):
        bc.parse_batch(payload, ids)


def test_wvr_b18_missing_and_invented_candidate_ids_are_blockers():
    ids = ["C001", "C002"]
    with pytest.raises(bc.CandidateError, match="CANDIDATE_SET_MISMATCH"):
        bc.parse_batch(_payload(["C001"]), ids)
    with pytest.raises(bc.CandidateError, match="CANDIDATE_SET_MISMATCH"):
        bc.parse_batch(_payload(["C001", "C002", "C900"]), ids)
    duplicated = _payload(["C001", "C001"])
    with pytest.raises(bc.CandidateError, match="CANDIDATE_SET_MISMATCH"):
        bc.parse_batch(duplicated, ids)


def test_wvr_b19_a_generated_timestamp_or_chapter_is_a_schema_violation():
    ids = ["C001"]
    for field in ("start_sec", "boundary_sec", "time"):
        payload = _payload(ids)
        payload["candidates"][0][field] = 400.0
        with pytest.raises(bc.CandidateError, match="SCHEMA_VIOLATION"):
            bc.parse_batch(payload, ids)
    for field in ("chapters", "chapter_count", "overview", "boundaries"):
        payload = _payload(ids)
        payload[field] = ["anything"]
        with pytest.raises(bc.CandidateError, match="SCHEMA_VIOLATION"):
            bc.parse_batch(payload, ids)
    for field in ("title", "summary", "preferred_source", "winner"):
        payload = _payload(ids)
        payload["candidates"][0][field] = "x"
        with pytest.raises(bc.CandidateError, match="SCHEMA_VIOLATION"):
            bc.parse_batch(payload, ids)


def test_wvr_b20_a_missing_json_object_is_a_parse_failure():
    with pytest.raises(bc.CandidateError, match="PARSE_FAILURE"):
        bc.extract_json("no json here")
    with pytest.raises(bc.CandidateError, match="PARSE_FAILURE"):
        bc.extract_json("{broken")


# ── reduction · density ───────────────────────────────────────
def test_wvr_b21_the_packet_keeps_strong_and_ambiguous_only():
    proposals = {}
    for index, row in enumerate(CANDIDATES):
        label = bc.PROPOSALS[index % len(bc.PROPOSALS)]
        proposals[row["candidate_id"]] = _fake_proposal(row["candidate_id"],
                                                        label)
    packet_ids = bc.packet_ids(proposals)
    appendix = bc.appendix_ids(proposals)
    assert packet_ids == sorted(
        value for value, row in proposals.items()
        if row["proposal"] in (bc.STRONG_TRANSITION_CANDIDATE, bc.AMBIGUOUS))
    assert appendix == sorted(
        value for value, row in proposals.items()
        if row["proposal"] == bc.WEAK_TRANSITION_CANDIDATE)
    assert not set(packet_ids) & set(appendix)
    counts = bc.proposal_counts(proposals)
    assert sum(counts.values()) == len(CANDIDATES)
    assert counts[bc.NO_CHAPTER_TRANSITION]


def test_wvr_b22_the_density_guard_reports_but_never_relaxes():
    few = {"C001": _fake_proposal("C001", bc.STRONG_TRANSITION_CANDIDATE)}
    note = bc.density_note(bc.proposal_counts(few))
    assert note["blocker"] == "INSUFFICIENT_SEMANTIC_CANDIDATES"
    assert note["strong_count"] == 1
    many = {"C%03d" % index:
            _fake_proposal("C%03d" % index, bc.STRONG_TRANSITION_CANDIDATE)
            for index in range(1, 40)}
    note = bc.density_note(bc.proposal_counts(many))
    assert note["blocker"] is None
    assert note["threshold_applied"] is False
    assert note["truncated"] is False


# ── packet · seal ─────────────────────────────────────────────
def test_wvr_b23_the_reviewer_packet_has_no_timestamp_or_verdict():
    proposals = {row["candidate_id"]:
                 _fake_proposal(row["candidate_id"],
                                bc.STRONG_TRANSITION_CANDIDATE
                                if index % 3 == 0 else bc.AMBIGUOUS
                                if index % 3 == 1
                                else bc.WEAK_TRANSITION_CANDIDATE)
                 for index, row in enumerate(CANDIDATES)}
    text = bc.reviewer_packet(CANDIDATES, proposals, {"source_map_sha256": "x"})
    audit = bc.leakage_audit([text], EVENTS, CANDIDATES)
    assert audit["violations"] == []
    assert bc.NOT_ADJUDICATED in text
    for label in bc.REVIEWER_VERDICTS:
        assert label in text
    assert bc.WEAK_TRANSITION_CANDIDATE not in text
    appendix = bc.weak_appendix(CANDIDATES, proposals)
    assert bc.leakage_audit([appendix], EVENTS, CANDIDATES)["violations"] == []
    for value in bc.appendix_ids(proposals):
        assert value in appendix


def test_wvr_b24_the_blind_map_is_a_separate_sealed_artifact():
    document = bc.blind_map_document(CANDIDATES)
    assert document["sealed"] is True
    assert document["reveal_before_verdicts_allowed"] is False
    assert len(document["candidate_to_time"]) == bc.EXPECTED_CANDIDATE_COUNT
    proposals = {row["candidate_id"]:
                 _fake_proposal(row["candidate_id"],
                                bc.STRONG_TRANSITION_CANDIDATE)
                 for row in CANDIDATES}
    text = bc.reviewer_packet(CANDIDATES, proposals,
                              {"source_map_sha256": "x"})
    assert "candidate_to_time" not in text
    assert "observation_set_to_window" not in text


def test_wvr_b25_the_reveal_gate_needs_every_packet_verdict():
    ids = ["C001", "C002"]
    partial = {"C001": {"verdict": "CHAPTER_BOUNDARY"}}
    summary = bc.verdict_summary(partial, ids)
    assert summary["reveal_allowed"] is False
    assert summary["missing"] == ["C002"]
    full = dict(partial)
    full["C002"] = {"verdict": "NOT_CHAPTER_BOUNDARY"}
    summary = bc.verdict_summary(full, ids)
    assert summary["reveal_allowed"] is True
    assert summary["counts"]["CHAPTER_BOUNDARY"] == 1
    with pytest.raises(bc.CandidateError, match="VOCABULARY_VIOLATION"):
        bc.verdict_summary({"C001": {"verdict": "MAYBE"},
                            "C002": {"verdict": "UNRESOLVED"}}, ids)


def test_wvr_b26_the_verdict_script_refuses_a_premature_reveal(tmp_path):
    runs = tmp_path
    (runs / "bcand_v1_packet_ids.json").write_text(
        json.dumps({"packet_candidate_ids": ["C001", "C002"]}),
        encoding="utf-8")
    (runs / "bcand_v1_blind_map.json").write_text(
        json.dumps({"candidate_to_time": {"C001": 100.0, "C002": 200.0}}),
        encoding="utf-8")
    with pytest.raises(verdicts_mod.VerdictError, match="reveal"):
        verdicts_mod.reveal(runs)
    verdicts_mod.record(runs, {"verdicts": [
        {"candidate_id": "C001", "verdict": "CHAPTER_BOUNDARY"},
        {"candidate_id": "C002", "verdict": "UNRESOLVED"}]})
    mapping = verdicts_mod.reveal(runs)
    assert mapping["C001"] == 100.0
    recorded = json.loads((runs / "bcand_v1_verdicts.json").read_text(
        encoding="utf-8"))
    assert recorded["recorded_by"] == "reviewer"
    assert recorded["final_verdict"] is None
    assert recorded["final_verdict_by_executor"] is False


def test_wvr_b27_executor_state_carries_no_verdict():
    proposals = {row["candidate_id"]:
                 _fake_proposal(row["candidate_id"]) for row in CANDIDATES}
    state = bc.executor_state(proposals, bc.packet_ids(proposals),
                              bc.density_note(bc.proposal_counts(proposals)),
                              {"violations": []})
    assert state["state"] == "EXECUTED / REVIEW_PENDING"
    assert state["verdict"] is None
    assert state["verdict_by_executor"] is False
    assert state["chapter_generated"] is False
    assert state["overview_generated"] is False
    assert state["mapping_revealed"] is False
    assert state["new_vlm_inference_count"] == 0
    assert state["final_verdict_vocabulary"] == \
        bc.FINAL_VERDICT_VOCABULARY_LINE


# ── 스크립트·경계 ──────────────────────────────────────────────
def test_wvr_b28_the_builder_writes_blinded_artifacts_only(tmp_path):
    runs = tmp_path
    (runs / bc.SOURCE_MAP_NAME).write_bytes(
        (RUNS / bc.SOURCE_MAP_NAME).read_bytes())
    written = builder.main(["--runs", str(runs)])
    assert written == 0
    names = sorted(path.name for path in runs.iterdir())
    assert "bcand_v1_candidates.json" in names
    assert "bcand_v1_blind_map.json" in names
    assert "bcand_v1_batches.json" in names
    assert sum(1 for name in names if name.startswith("bcand_v1_prompt_")) \
        == bc.EXPECTED_BATCH_COUNT
    prompts = [path.read_text(encoding="utf-8")
               for path in runs.glob("bcand_v1_prompt_*.txt")]
    audit = bc.leakage_audit(prompts, EVENTS, CANDIDATES)
    assert audit["violations"] == []
    for path in runs.glob("bcand_v1_prompt_*.txt"):
        assert "\r" not in path.read_text(encoding="utf-8", newline="")


def test_wvr_b29_the_frozen_prior_artifacts_are_untouched():
    assert _sha256_file(RUNS / bc.SOURCE_MAP_NAME) == bc.SOURCE_MAP_SHA256
    assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    for name in ("chapter_v1_chapters.json", "chapter_v1_raw.txt",
                 "chapter_repair_v1_candidates.json",
                 "stitch_v1_verdicts.json"):
        assert (RUNS / name).is_file(), name
    assert not (RUNS / "chapter_repair_v1_boundaries.json").is_file()
    for name in ("bcand_v1_chapters.json", "bcand_v1_overview.json",
                 "bcand_v1_report.json"):
        assert not (RUNS / name).is_file(), name


def test_wvr_b30_open_leakage_flags_stop_the_construction(monkeypatch):
    monkeypatch.setattr(bc, "TIMESTAMP_IN_PACKET_ALLOWED", True)
    with pytest.raises(bc.CandidateError):
        bc.render_block(BY_ID["C001"])
    monkeypatch.setattr(bc, "TIMESTAMP_IN_PACKET_ALLOWED", False)
    monkeypatch.setattr(bc, "GEOMETRY_IN_PACKET_ALLOWED", True)
    with pytest.raises(bc.CandidateError):
        bc.render_block(BY_ID["C001"])
    monkeypatch.setattr(bc, "GEOMETRY_IN_PACKET_ALLOWED", False)
    monkeypatch.setattr(bc, "PRIOR_CHAPTER_INPUT_ALLOWED", True)
    with pytest.raises(bc.CandidateError):
        bc.build_candidates(EVENTS, DOCUMENT)
