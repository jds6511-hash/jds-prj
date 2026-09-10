"""Semantic Chapter boundary repair 계약 (2026-09-10 · WVR-V01~V24).

```
구조   Stage A(결정적 경계 추출 · LLM 없음) → 경계 동결 → Stage B(제목·요약만 LLM)
계약   후보는 event 시작 시각만 · region·격자 주입 금지 · jitter 금지 ·
      conflict 안 경계는 두 관측 공통 근거 필요 · LLM은 경계·evidence class 불가 ·
      conflict 노출 필수 · single-source는 STABLE 불가 · [0,24) 보존
```
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_chapter_repair_v1 as cr
import wvr_chapter_v1 as v1
import wvr_conservative_map_v1 as cmap

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md")
PREREG = ROOT / PREREG_REL
STAGEA = ROOT / "scripts/wvr_crepair_stagea.py"
RUNNER = ROOT / "scripts/wvr_crepair_run.py"
BUILDER = ROOT / "scripts/wvr_crepair_build.py"
VALIDATOR = ROOT / "scripts/wvr_crepair_validate.py"
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


stagea = _module(STAGEA, "wvr_crepair_stagea_mod")
DOCUMENT = json.loads((RUNS / cr.SOURCE_MAP_NAME).read_text(encoding="utf-8"))
EVENTS = cr.source_events(DOCUMENT)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _event(event_id, window, start, end, action, obj):
    return {"event_id": event_id, "source_window": window,
            "start_sec": start, "end_sec": end, "actor": "person",
            "action": action, "object_or_state": obj}


def _support(conflict=0, single=0.0, multi=0.0, unresolved=0.0, events=1):
    return {"chapter_id": "CH01",
            "conflict_blocks": ["CB%03d" % (index + 1)
                                for index in range(conflict)],
            "single_source_seconds": single, "multi_window_seconds": multi,
            "unresolved_seconds": unresolved, "conflict_seconds": 0.0,
            "unresolved_intervals": [[0.0, 24.0]] if unresolved else [],
            "source_event_ids": ["W01_E001"] * events,
            "source_event_count": events, "source_regions": ["R02"],
            "source_windows": ["W01"], "conflict_sources_preserved": [],
            "region_seconds": {}}


def _tmp_runs(tmp_path, extra=()):
    runs = tmp_path / "runs"
    runs.mkdir()
    for name in (cr.SOURCE_MAP_NAME, cr.V1_CHAPTERS_NAME) + tuple(extra):
        (runs / name).write_bytes((RUNS / name).read_bytes())
    return runs


# ── WVR-V01~V04 동결·입력 ───────────────────────────────────────
def test_wvr_v01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_v02_every_prohibition_flag_is_closed_and_rules_are_derived():
    for name in cr.FLAGS:
        assert getattr(cr, name) is False, name
    assert cr.CHAPTER_LLM_ALLOWED is True
    cr.assert_flags_closed()
    assert cr.MIN_SEPARATION_SEC == round(
        (cr.VIDEO_END_SEC - cr.VIDEO_START_SEC) / cr.MAX_CHAPTERS, 3)
    assert cr.DETECT_WINDOW_SEC == 30.0 and cr.SUSTAIN_WINDOW_SEC == 60.0
    assert (cr.MIN_CHAPTERS, cr.MAX_CHAPTERS) == (3, 10)
    assert cr.EVIDENCE_PRIORITY == (cr.MIXED_EVIDENCE, cr.LIMITED_EVIDENCE,
                                    cr.STABLE_DOMINANT)
    assert cr.FINAL_VERDICTS == ("SEMANTIC_CHAPTER_REPAIR_PASS",
                                 "SEMANTIC_CHAPTER_REPAIR_HOLD",
                                 "SEMANTIC_CHAPTER_REPAIR_INCONCLUSIVE")


def test_wvr_v03_the_input_is_the_same_frozen_conservative_map():
    assert cr.SOURCE_MAP_SHA256 == v1.SOURCE_MAP_SHA256
    assert _sha256_file(RUNS / cr.SOURCE_MAP_NAME) == cr.SOURCE_MAP_SHA256
    assert len(EVENTS) == cmap.EXPECTED_SOURCE_EVENT_COUNT == 160
    assert all(row["source_window"] in cmap.VALID_SOURCE_WINDOWS
               for row in EVENTS)
    assert cr.NEW_VLM_INFERENCE_ALLOWED is False
    assert cr.TRACK_A_INPUT_ALLOWED is False
    assert cr.EVENT_MAP_REBUILD_ALLOWED is False
    assert cr.LOCAL_EVENT_REEXTRACTION_ALLOWED is False


def test_wvr_v04_candidate_times_are_event_starts_and_never_geometry():
    times = cr.candidate_times(EVENTS)
    starts = {round(row["start_sec"], 3) for row in EVENTS}
    assert times and set(times) <= starts
    region_edges = {edge for region in DOCUMENT["regions"]
                    for edge in (region["start_sec"], region["end_sec"])}
    injected = region_edges - starts
    assert not (injected & set(times)), "region 경계가 후보로 들어갔다"
    assert all(cr.VIDEO_START_SEC < value < cr.VIDEO_END_SEC
               for value in times)
    # jitter 금지: 후보는 event 시각과 정확히 같다
    assert all(value in starts for value in times)


# ── WVR-V05~V09 Stage A 규칙 ────────────────────────────────────
def test_wvr_v05_reasons_come_from_token_domain_disjointness():
    before = [_event("A1", "W01", 0.0, 10.0, "chopping", "onion")]
    after = [_event("A2", "W01", 10.0, 20.0, "sewing", "fabric")]
    rows = cr._reasons(before, after, before, after)
    assert cr.ACTIVITY_DOMAIN_CHANGE in rows
    assert cr.OBJECT_DOMAIN_CHANGE in rows
    assert cr.SCENE_OR_TASK_CHANGE in rows
    assert cr.SUSTAINED_ACTIVITY_CHANGE in rows
    shared = [_event("A3", "W01", 10.0, 20.0, "chopping", "carrot")]
    rows = cr._reasons(before, shared, before, shared)
    assert cr.ACTIVITY_DOMAIN_CHANGE not in rows      # action 토큰 공유
    assert cr.OBJECT_DOMAIN_CHANGE in rows
    assert cr.SCENE_OR_TASK_CHANGE not in rows
    same = [_event("A4", "W01", 10.0, 20.0, "chopping", "onion")]
    assert cr._reasons(before, same, before, same) == []


def test_wvr_v06_a_boundary_only_one_conflict_source_supports_is_excluded():
    """conflict block 안에서 한쪽 관측만 전환을 보이면 후보가 아니다 (§7).

    실제 map에서는 이 경로가 발동하지 않았다(accepted 후보가 모두 conflict 밖).
    그래서 합성 시나리오로 규칙 자체를 검사한다.
    """
    document = {"nodes": {"conflict_blocks": [{
        "node_id": "CB001", "start_sec": 0.0, "end_sec": 60.0,
        "observation_set_1": {"source": "W01"},
        "observation_set_2": {"source": "W02"}}]}}
    events = [
        _event("W01_E001", "W01", 10.0, 30.0, "chopping", "onion"),
        _event("W01_E002", "W01", 30.0, 50.0, "sewing", "fabric"),
        _event("W02_E001", "W02", 10.0, 30.0, "peeling", "potato"),
    ]
    row = cr.evaluate_candidate(events, document, 30.0)
    assert row["in_conflict_block"] is True
    assert row["reason"], "합쳐서 보면 전환 근거가 있다"
    assert row["conflict_source_reasons"]["W02"] == []
    assert row["excluded"] == cr.UNSUPPORTED_BY_CONFLICT

    # 양쪽이 같은 근거를 보이면 후보로 남는다
    events.append(_event("W02_E002", "W02", 30.0, 50.0, "stitching", "thread"))
    row = cr.evaluate_candidate(events, document, 30.0)
    assert row["excluded"] is None
    assert set(row["conflict_source_reasons"]["W01"])         & set(row["conflict_source_reasons"]["W02"])

    # 실제 map: conflict 안에서 공통 근거가 없는 후보는 하나도 통과하지 않았다
    rows = [item for item in cr.candidates(EVENTS, DOCUMENT)
            if item["in_conflict_block"] and item["conflict_source_reasons"]
            and not set.intersection(*[set(value) for value
                                       in item["conflict_source_reasons"]
                                       .values()])]
    assert all(item["excluded"] == cr.UNSUPPORTED_BY_CONFLICT for item in rows)


def test_wvr_v07_selection_keeps_separation_and_ignores_geometry():
    def row(time, reasons, breadth):
        return {"boundary_sec": time, "reason": list(reasons),
                "breadth": breadth, "excluded": None}
    rows = [row(70.0, ["OBJECT_DOMAIN_CHANGE"], 3),
            row(100.0, ["OBJECT_DOMAIN_CHANGE", "ACTIVITY_DOMAIN_CHANGE"], 9),
            row(200.0, ["OBJECT_DOMAIN_CHANGE"], 1),
            row(240.0, ["OBJECT_DOMAIN_CHANGE"], 8),
            row(560.0, ["OBJECT_DOMAIN_CHANGE"], 5)]
    selected = cr.select_boundaries(rows)
    times = [item["boundary_sec"] for item in selected]
    assert times == [100.0, 200.0], times      # 근거 많은 100, 60초 간격 유지
    assert all(right - left >= cr.MIN_SEPARATION_SEC
               for left, right in zip(times, times[1:]))
    assert 560.0 not in times                  # 540 초과 → 밴드 밖
    assert cr.select_boundaries([row(30.0, ["OBJECT_DOMAIN_CHANGE"], 5)]) == []


def test_wvr_v08_chapter_count_out_of_bounds_is_a_blocker():
    def row(time):
        return {"boundary_sec": time, "reason": ["OBJECT_DOMAIN_CHANGE"],
                "breadth": 1, "excluded": None}
    with pytest.raises(cr.RepairError) as error:
        cr.chapters_from_boundaries([row(300.0)])
    assert "INSUFFICIENT_BOUNDARY_EVIDENCE" in str(error.value)
    chapters = cr.chapters_from_boundaries([row(120.0), row(300.0)])
    assert [item["chapter_id"] for item in chapters] == ["CH01", "CH02",
                                                         "CH03"]
    assert chapters[0]["start_sec"] == 0.0 and chapters[-1]["end_sec"] == 600.0


def test_wvr_v09_stage_a_on_the_frozen_map_records_its_blocker(tmp_path):
    runs = _tmp_runs(tmp_path)
    built = stagea.stage_a(runs)
    written = stagea.write_artifacts(runs, built)
    assert stagea.CANDIDATES_NAME in written
    candidates = json.loads((runs / stagea.CANDIDATES_NAME)
                            .read_text(encoding="utf-8"))
    if built["blocker"]:
        assert stagea.BOUNDARIES_NAME not in written
        assert not (runs / stagea.BOUNDARIES_NAME).exists()
        assert "INSUFFICIENT_BOUNDARY_EVIDENCE" in candidates["blocker"]
        assert candidates["stage_b_executed"] is False
        assert candidates["rule_relaxed"] is False
    else:
        assert (runs / stagea.BOUNDARIES_NAME).is_file()
    assert candidates["accepted_count"] <= candidates["candidate_count"]
    assert candidates["provenance"]["stage_a_rule"]["llm_used"] is False


# ── WVR-V10~V13 evidence class · 감사 ──────────────────────────
def test_wvr_v10_evidence_class_is_deterministic_and_conflict_wins():
    assert cr.evidence_class(_support(conflict=1, multi=100.0))[
        "evidence_class"] == cr.MIXED_EVIDENCE
    assert cr.evidence_class(_support(conflict=2, single=90.0))[
        "evidence_class"] == cr.MIXED_EVIDENCE
    assert cr.evidence_class(_support(single=40.0, multi=10.0))[
        "evidence_class"] == cr.LIMITED_EVIDENCE
    assert cr.evidence_class(_support(multi=90.0, unresolved=24.0))[
        "evidence_class"] == cr.LIMITED_EVIDENCE
    assert cr.evidence_class(_support(multi=90.0, single=10.0))[
        "evidence_class"] == cr.STABLE_DOMINANT
    assert all(row["assigned_by"] == "executor" for row in
               (cr.evidence_class(_support(multi=90.0, single=10.0)),
                cr.evidence_class(_support(conflict=1))))


def test_wvr_v11_a_single_source_only_chapter_can_never_be_stable():
    support = _support(single=24.0, multi=0.0)
    assert cr.evidence_class(support)["evidence_class"] == cr.LIMITED_EVIDENCE
    chapters = [{"chapter_id": "CH01", "start_sec": 0.0, "end_sec": 24.0}]
    forced = [{"evidence_class": cr.STABLE_DOMINANT, "reason": [],
               "assigned_by": "executor", "priority": []}]
    audit = cr.evidence_audit(chapters, [support], forced)
    assert audit["violations"], "single-source STABLE_DOMINANT가 통과했다"


def test_wvr_v12_a_conflict_chapter_labelled_stable_is_a_violation():
    support = _support(conflict=1, multi=50.0)
    chapters = [{"chapter_id": "CH01", "start_sec": 0.0, "end_sec": 50.0}]
    for label in (cr.STABLE_DOMINANT, cr.LIMITED_EVIDENCE):
        audit = cr.evidence_audit(chapters, [support],
                                  [{"evidence_class": label, "reason": [],
                                    "assigned_by": "executor",
                                    "priority": []}])
        assert audit["violations"], label
    audit = cr.evidence_audit(chapters, [support],
                              [cr.evidence_class(support)])
    assert audit["violations"] == []
    assert audit["class_counts"][cr.MIXED_EVIDENCE] == 1


def test_wvr_v13_evidence_class_assigned_by_an_llm_is_rejected(monkeypatch):
    monkeypatch.setattr(cr, "LLM_MAY_SET_EVIDENCE_CLASS_ALLOWED", True)
    with pytest.raises(cr.RepairError):
        cr.evidence_class(_support(multi=90.0))
    monkeypatch.setattr(cr, "LLM_MAY_SET_EVIDENCE_CLASS_ALLOWED", False)
    chapters = [{"chapter_id": "CH01", "start_sec": 0.0, "end_sec": 60.0}]
    audit = cr.evidence_audit(
        chapters, [_support(multi=60.0)],
        [{"evidence_class": cr.STABLE_DOMINANT, "reason": [],
          "assigned_by": "generator", "priority": []}])
    assert audit["violations"]


# ── WVR-V14~V17 conflict 노출 · unresolved ─────────────────────
def test_wvr_v14_conflict_chapters_always_disclose_uncertainty():
    chapter = {"chapter_id": "CH02", "start_sec": 48.0, "end_sec": 96.0}
    support = _support(conflict=2, multi=48.0)
    spoken = cr.disclosure_audit(
        chapter, support,
        "Food handling. Local observations disagree on some objects.")
    assert spoken["disclosure_required"] is True
    assert spoken["disclosed_by_generator"] is True
    assert spoken["conflict_disclosed"] is True
    silent = cr.disclosure_audit(chapter, support,
                                 "Food handling proceeds steadily.")
    assert silent["disclosure_required"] is True
    assert silent["disclosed_by_generator"] is False
    assert silent["machine_disclosure"] == cr.MACHINE_DISCLOSURE
    assert silent["conflict_disclosed"] is True      # 은폐는 불가능하다
    rows = cr.anomalies([chapter], [support],
                        [cr.evidence_class(support)], [silent],
                        cr.grid_audit([], DOCUMENT))
    assert any(row["kind"] == "CONFLICT_NOT_DISCLOSED_BY_GENERATOR"
               for row in rows)
    clean = cr.disclosure_audit(chapter, _support(multi=48.0), "Plain text.")
    assert clean["disclosure_required"] is False
    assert clean["conflict_disclosed"] is True


def test_wvr_v15_the_unresolved_opening_is_preserved():
    chapters = [{"chapter_id": "CH01", "start_sec": 0.0, "end_sec": 120.0}]
    support = _support(unresolved=24.0, multi=96.0)
    audit = cr.unresolved_audit(chapters, [support], DOCUMENT)
    assert audit["violations"] == []
    assert audit["unresolved_intervals"] == [[0.0, 24.0]]
    dropped = dict(support, unresolved_intervals=[])
    assert cr.unresolved_audit(chapters, [dropped], DOCUMENT)["violations"]
    empty = dict(support, source_event_ids=[])
    assert cr.unresolved_audit(chapters, [empty], DOCUMENT)["violations"]


def test_wvr_v16_the_grid_audit_records_but_never_selects():
    def row(time):
        return {"boundary_sec": time, "reason": ["OBJECT_DOMAIN_CHANGE"],
                "breadth": 1, "excluded": None}
    audit = cr.grid_audit([row(96.0), row(103.0)], DOCUMENT)
    assert audit["internal_boundary_count"] == 2
    assert audit["on_24s_grid_count"] == 1
    assert audit["on_48s_grid_count"] == 1
    assert audit["equals_region_boundary_count"] == 1
    assert audit["grid_used_for_selection"] is False
    assert audit["jitter_applied"] is False
    assert all(item["used_for_selection"] is False
               for item in audit["boundaries"])
    grid_only = cr.grid_audit([row(96.0), row(192.0)], DOCUMENT)
    kinds = [item["kind"] for item in cr.anomalies(
        [{"chapter_id": "CH01", "start_sec": 0.0, "end_sec": 600.0}],
        [_support(multi=600.0)], [cr.evidence_class(_support(multi=600.0))],
        [], grid_only)]
    assert "ALL_BOUNDARIES_ON_24S_GRID" in kinds
    assert "ALL_BOUNDARIES_EQUAL_REGION_BOUNDARIES" in kinds


def test_wvr_v17_chapter_support_traces_back_to_the_map():
    chapter = {"chapter_id": "CH01", "start_sec": 0.0, "end_sec": 120.0}
    support = cr.chapter_support(chapter, DOCUMENT, EVENTS)
    known = {row["event_id"] for row in EVENTS}
    assert set(support["source_event_ids"]) <= known
    assert support["source_event_count"] > 0
    assert support["unresolved_intervals"] == [[0.0, 24.0]]
    assert support["conflict_blocks"]
    assert set(support["conflict_sources_preserved"]) <= set(
        cmap.VALID_SOURCE_WINDOWS)
    empty = {"chapter_id": "CHX", "start_sec": 0.0, "end_sec": 1.0}
    with pytest.raises(cr.RepairError):
        cr.chapter_support(empty, DOCUMENT, EVENTS)


# ── WVR-V18~V21 Stage B 계약 (경계 불변) ────────────────────────
def test_wvr_v18_the_llm_cannot_touch_the_frozen_boundaries():
    chapters = cr.chapters_from_boundaries([
        {"boundary_sec": 120.0}, {"boundary_sec": 300.0}])
    good = {"chapters": {row["chapter_id"]: {
        "title": "Bench work", "summary": "Observations recur.",
        "dominant_activities": ["handling"]} for row in chapters}}
    parsed = cr.parse_titles(good, chapters)
    assert sorted(parsed) == ["CH01", "CH02", "CH03"]
    assert set(parsed["CH01"]) == {"title", "summary", "dominant_activities"}

    listed = {"chapters": [dict(value, chapter_id=key)
                           for key, value in good["chapters"].items()]}
    with pytest.raises(cr.RepairError):
        cr.parse_titles(listed, chapters)          # 배열 = 경계 재정의
    for field in ("start_sec", "end_sec", "boundary_sec", "time"):
        payload = json.loads(json.dumps(good))
        payload["chapters"]["CH02"][field] = 111.0
        with pytest.raises(cr.RepairError) as error:
            cr.parse_titles(payload, chapters)
        assert "LLM_CHANGED_BOUNDARIES" in str(error.value)
    for field in ("confidence_class", "evidence_class", "confidence"):
        payload = json.loads(json.dumps(good))
        payload["chapters"]["CH02"][field] = cr.STABLE_DOMINANT
        with pytest.raises(cr.RepairError) as error:
            cr.parse_titles(payload, chapters)
        assert "EVIDENCE_CLASS_VIOLATION" in str(error.value)
    payload = json.loads(json.dumps(good))
    payload["chapters"]["CH04"] = payload["chapters"]["CH01"]
    with pytest.raises(cr.RepairError):
        cr.parse_titles(payload, chapters)
    payload = json.loads(json.dumps(good))
    del payload["chapters"]["CH03"]
    with pytest.raises(cr.RepairError):
        cr.parse_titles(payload, chapters)
    for name in ("overview", "analysis", "conclusion", "boundaries",
                 "chapter_count"):
        payload = json.loads(json.dumps(good))
        payload[name] = "x"
        with pytest.raises(cr.RepairError):
            cr.parse_titles(payload, chapters)
    with pytest.raises(cr.RepairError):
        cr.extract_json("no json here")


def test_wvr_v19_the_runner_refuses_retry_and_missing_frozen_boundaries(
        tmp_path, monkeypatch):
    runner = _module(RUNNER, "wvr_crepair_run_mod")
    runs = _tmp_runs(tmp_path)
    with pytest.raises(runner.RunError) as error:
        runner.run(runs)
    assert "BOUNDARY_SET_NOT_FROZEN" in str(error.value)
    (runs / runner.RAW_NAME).write_text("already", encoding="utf-8")
    with pytest.raises(runner.RunError) as error:
        runner.run(runs)
    assert "재생성 금지" in str(error.value)
    monkeypatch.setattr(cr, "RETRY_ALLOWED", True)
    with pytest.raises(runner.RunError):
        runner.run(runs)
    monkeypatch.setattr(cr, "RETRY_ALLOWED", False)


def test_wvr_v20_the_build_runs_end_to_end_on_frozen_boundaries(
        tmp_path, monkeypatch):
    runner = _module(RUNNER, "wvr_crepair_run_mod2")
    builder = _module(BUILDER, "wvr_crepair_build_mod")
    starts = sorted({row["start_sec"] for row in EVENTS
                     if 100.0 <= row["start_sec"] <= 500.0})
    picked = [starts[0], starts[len(starts) // 2], starts[-1]]
    frozen_rows = [cr.evaluate_candidate(EVENTS, DOCUMENT, value)
                   for value in picked]
    for row in frozen_rows:
        row["excluded"] = None
        row["reason"] = row["reason"] or ["OBJECT_DOMAIN_CHANGE"]
    monkeypatch.setattr(cr, "select_boundaries", lambda rows: frozen_rows)

    runs = _tmp_runs(tmp_path)
    built = stagea.stage_a(runs)
    assert built["blocker"] is None
    stagea.write_artifacts(runs, built)
    chapters = built["boundaries"]["chapters"]
    supports = built["boundaries"]["chapter_support"]
    document = built["document"]
    prompt = cr.render_prompt(chapters, supports, document, EVENTS)
    raw = json.dumps({"chapters": {
        row["chapter_id"]: {
            "title": "Bench work",
            "summary": ("Observations recur; local observations disagree on "
                        "some objects."),
            "dominant_activities": ["handling", "placing"]}
        for row in chapters}}, ensure_ascii=False)
    (runs / runner.PROMPT_NAME).write_text(prompt, encoding="utf-8")
    (runs / runner.RAW_NAME).write_text(raw, encoding="utf-8")
    record = {
        "raw_sha256": cr.sha256_text(raw),
        "prompt_sha256": cr.sha256_text(prompt),
        "prompt_template_sha256": cr.sha256_text(cr.REPAIR_PROMPT_V1),
        "source_map_sha256": cr.SOURCE_MAP_SHA256,
        "boundaries_sha256": runner.sha256_file(
            runs / stagea.BOUNDARIES_NAME),
        "generation_attempts": 1, "retry_allowed": False,
        "raw_persisted_before_parse": True, "parsed_here": False,
        "new_vlm_inference_count": 0, "track_a_input_used": False,
        "llm_role": "title/summary/dominant_activities only",
        "llm_may_change_boundaries": False,
        "llm_may_set_evidence_class": False,
        "effective_runtime": {"quantization_mismatch": False,
                              "do_sample": False,
                              "max_new_tokens": cr.LLM_MAX_NEW_TOKENS},
        "requested_runtime": {"model_id": cr.LLM_MODEL_ID,
                              "load_4bit": False,
                              "max_new_tokens": cr.LLM_MAX_NEW_TOKENS},
        "code_git_head": "x", "prereg_commit": "y",
        "elapsed_sec": 1.0, "vram": {}, "raw_chars": len(raw)}
    (runs / runner.RECORD_NAME).write_text(json.dumps(record),
                                           encoding="utf-8")

    result = builder.build(runs)
    doc = result["chapters_doc"]
    assert len(doc["chapters"]) == len(chapters)
    assert [row["start_sec"] for row in doc["chapters"][1:]] == picked
    assert all(row["assigned_by"] == "executor" for row in doc["evidence"])
    assert doc["evidence_audit"]["violations"] == []
    assert doc["unresolved_audit"]["violations"] == []
    assert doc["executor_state"]["verdict"] is None
    for question in ("Q1 STRUCTURE", "Q2 BOUNDARY_SEMANTICS",
                     "Q3 GEOMETRY_INDEPENDENCE", "Q4 CONFLICT_SAFETY",
                     "Q5 EVIDENCE_CALIBRATION", "Q6 OVERVIEW_READY"):
        assert question in result["packet"]
    assert result["packet"].count(cr.NOT_ADJUDICATED) >= 6
    assert result["comparison"]["v1"]["chapter_count"] == 8
    assert result["comparison"]["v2"]["evidence_assigned_by"] \
        == "executor (deterministic)"

    broken = dict(record, raw_sha256="0" * 64)
    (runs / runner.RECORD_NAME).write_text(json.dumps(broken),
                                           encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    broken = dict(record, boundaries_sha256="0" * 64)
    (runs / runner.RECORD_NAME).write_text(json.dumps(broken),
                                           encoding="utf-8")
    with pytest.raises(builder.BuildError) as error:
        builder.build(runs)
    assert "BOUNDARY_SET_NOT_FROZEN" in str(error.value)
    broken = dict(record, generation_attempts=2)
    (runs / runner.RECORD_NAME).write_text(json.dumps(broken),
                                           encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    (runs / runner.RECORD_NAME).write_text(json.dumps(record),
                                           encoding="utf-8")
    for flag in ("OVERVIEW_GENERATION_ALLOWED", "REPORT_GENERATION_ALLOWED",
                 "ANALYSIS_GENERATION_ALLOWED", "RETRY_ALLOWED",
                 "LLM_MAY_CHANGE_BOUNDARIES_ALLOWED",
                 "LLM_MAY_SET_EVIDENCE_CLASS_ALLOWED",
                 "BOUNDARY_JITTER_ALLOWED", "SYNTHETIC_FILL_ALLOWED"):
        monkeypatch.setattr(cr, flag, True)
        with pytest.raises(builder.BuildError):
            builder.build(runs)
        monkeypatch.setattr(cr, flag, False)


def test_wvr_v21_the_validator_computes_its_checks_from_the_artifacts():
    source = VALIDATOR.read_text(encoding="utf-8")
    for expression in (
            'round(row["boundary_sec"], 3) in event_starts for row in rows',
            '["jitter_applied"] is False',
            'row["evidence_class"] != cr.STABLE_DOMINANT',
            'row["conflict_disclosed"] for row in disclosures',
            'cr.sha256_text(raw) == record["raw_sha256"]'):
        assert expression in source, "validator 검사가 실제 계산이 아니다: %s" \
            % expression
    for verdict in cr.FINAL_VERDICTS:
        assert verdict not in source, "validator가 최종 판정을 계산한다"


# ── WVR-V22~V24 경계 보존 ──────────────────────────────────────
def test_wvr_v22_v1_artifacts_and_the_map_are_untouched():
    assert _sha256_file(RUNS / cr.SOURCE_MAP_NAME) == cr.SOURCE_MAP_SHA256
    v1_doc = json.loads((RUNS / cr.V1_CHAPTERS_NAME)
                        .read_text(encoding="utf-8"))
    assert len(v1_doc["chapters"]) == 8
    assert v1_doc["executor_state"]["verdict"] is None
    assert _sha256_file(RUNS / "stitch_v1_verdicts.json") == \
        cmap.FROZEN_HASHES["stitch_v1_verdicts.json"]


def test_wvr_v23_no_report_stage_artifact_exists():
    for name in ("chapter_repair_v1_overview.md",
                 "chapter_repair_v1_analysis.md",
                 "chapter_repair_v1_conclusion.md",
                 "chapter_repair_v1_report.hwpx"):
        assert not (RUNS / name).exists(), name
    assert cr.OVERVIEW_GENERATION_ALLOWED is False
    assert cr.ANALYSIS_GENERATION_ALLOWED is False
    assert cr.REPORT_GENERATION_ALLOWED is False


def test_wvr_v24_the_frozen_boundaries_of_the_project_are_untouched():
    assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert not (RUNS / "m9_report_test.json").exists()
    assert cr.PRODUCTION_PROMOTION_ALLOWED is False
    assert cr.VERDICT_BY_EXECUTOR is False


# ── WVR-V25~V27 mutation에서 나온 구멍 차단 ──────────────────────
def test_wvr_v25_open_injection_or_jitter_flags_stop_the_extractor(monkeypatch):
    for flag in ("GRID_BOUNDARY_AS_CANDIDATE_ALLOWED",
                 "REGION_BOUNDARY_AS_CANDIDATE_ALLOWED",
                 "BOUNDARY_JITTER_ALLOWED"):
        monkeypatch.setattr(cr, flag, True)
        with pytest.raises(cr.RepairError):
            cr.candidate_times(EVENTS)
        monkeypatch.setattr(cr, flag, False)
    chapters = cr.chapters_from_boundaries([{"boundary_sec": 120.0},
                                            {"boundary_sec": 300.0}])
    payload = {"chapters": {row["chapter_id"]: {
        "title": "Bench work", "summary": "Observations recur.",
        "dominant_activities": ["handling"]} for row in chapters}}
    monkeypatch.setattr(cr, "LLM_MAY_CHANGE_BOUNDARIES_ALLOWED", True)
    with pytest.raises(cr.RepairError):
        cr.parse_titles(payload, chapters)
    monkeypatch.setattr(cr, "LLM_MAY_CHANGE_BOUNDARIES_ALLOWED", False)
    assert sorted(cr.parse_titles(payload, chapters)) == ["CH01", "CH02",
                                                          "CH03"]


def test_wvr_v26_conflict_disclosure_is_computed_not_asserted(monkeypatch):
    chapter = {"chapter_id": "CH02", "start_sec": 48.0, "end_sec": 96.0}
    support = _support(conflict=1, multi=48.0)
    monkeypatch.setattr(cr, "MACHINE_DISCLOSURE", "")
    silent = cr.disclosure_audit(chapter, support, "Steady bench work.")
    assert silent["disclosure_required"] is True
    assert silent["conflict_disclosed"] is False, \
        "노출 수단이 하나도 없는데 통과했다"
    spoken = cr.disclosure_audit(chapter, support,
                                 "Observations disagree here.")
    assert spoken["conflict_disclosed"] is True


def test_wvr_v27_the_cursor_advances_to_the_earliest_remaining_candidate():
    def row(time, reasons=("OBJECT_DOMAIN_CHANGE",), breadth=1):
        return {"boundary_sec": time, "reason": list(reasons),
                "breadth": breadth, "excluded": None}
    rows = [row(70.0), row(300.0), row(480.0)]      # 480 = 24*20 (격자 위)
    times = [item["boundary_sec"] for item in cr.select_boundaries(rows)]
    assert times == [70.0, 300.0, 480.0], times
    # 격자 후보를 먼저 보는 순서라면 300이 건너뛰어진다 — 그것을 금지한다
    assert 300.0 in times, "격자 우선 순서가 후보를 건너뛰었다"
