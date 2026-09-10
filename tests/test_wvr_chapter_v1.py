"""Semantic Chapter shadow 계약 (2026-09-10 · WVR-U01~U26).

```
입력   Conservative Event Map(PASS) 하나 · 새 VLM 추론 0회 · Track A 입력 없음
생성   chapter 후보 생성에만 text LLM 1회 (동결 프롬프트·런타임 · 재생성 금지)
계약   conflict 승자 선택 금지 · [0,24) 사실 생성 금지 · 격자 경계 복사 금지 ·
      계보 끊김 금지 · Overview 생성 금지 · executor는 판정을 쓰지 않는다
```
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_chapter_v1 as ch
import wvr_conservative_map_v1 as cmap

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md")
PREREG = ROOT / PREREG_REL
SELFCHECK = ROOT / "scripts/wvr_chapter_selfcheck.py"
RUNNER = ROOT / "scripts/wvr_chapter_run.py"
BUILDER = ROOT / "scripts/wvr_chapter_build.py"
VALIDATOR = ROOT / "scripts/wvr_chapter_validate.py"
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


selfcheck = _module(SELFCHECK, "wvr_chapter_selfcheck_mod")
builder = _module(BUILDER, "wvr_chapter_build_mod")
DOCUMENT = json.loads((RUNS / ch.SOURCE_MAP_NAME).read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _chapter(start, end, title="Food preparation", confidence="MIXED_EVIDENCE",
             reasons=("ACTIVITY_CHANGE",), summary="Observed actions recur; "
             "local observations disagree on some details."):
    return {"start_sec": start, "end_sec": end, "title": title,
            "summary": summary, "dominant_activities": ["preparation"],
            "confidence_class": confidence,
            "boundary_reason": list(reasons)}


def _payload(spans=((0.0, 110.0), (110.0, 300.0), (300.0, 430.0),
                    (430.0, 600.0))):
    return {"chapters": [_chapter(start, end) for start, end in spans]}


def _built(spans=None):
    payload = _payload(spans) if spans else _payload()
    chapters = ch.parse_chapters(payload)
    lineage = ch.derive_lineage(chapters, DOCUMENT)
    return chapters, lineage


# ── WVR-U01~U05 동결 ─────────────────────────────────────────────
def test_wvr_u01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_u02_every_prohibition_flag_is_closed():
    for name in ch.FLAGS:
        assert getattr(ch, name) is False, name
    assert ch.CHAPTER_LLM_ALLOWED is True          # 이 사건에서만 허용
    assert ch.RETRY_ALLOWED is False
    assert ch.GENERATION_ATTEMPTS == 1
    ch.assert_flags_closed()


def test_wvr_u03_the_vocabulary_and_bounds_are_frozen():
    assert ch.CONFIDENCE_CLASSES == ("STABLE_DOMINANT", "MIXED_EVIDENCE",
                                     "LIMITED_EVIDENCE")
    assert ch.BOUNDARY_REASONS == ("ACTIVITY_CHANGE", "SCENE_OR_TASK_CHANGE",
                                   "OBJECT_DOMAIN_CHANGE",
                                   "SUSTAINED_TRANSITION")
    assert (ch.MIN_CHAPTERS, ch.MAX_CHAPTERS) == (3, 10)
    assert ch.SHORT_CHAPTER_SEC == 20.0
    assert ch.UNRESOLVED_OPENING_POLICY == \
        "coverage_from_zero_with_unresolved_opening_metadata"
    assert ch.FINAL_VERDICTS == ("SEMANTIC_CHAPTER_SHADOW_PASS",
                                 "SEMANTIC_CHAPTER_SHADOW_HOLD",
                                 "SEMANTIC_CHAPTER_SHADOW_INCONCLUSIVE")


def test_wvr_u04_the_prompt_is_frozen_and_carries_no_expected_answer():
    assert ch.sha256_text(ch.CHAPTER_PROMPT_V1) == ch.PROMPT_TEMPLATE_SHA256
    prompt = ch.render_prompt(DOCUMENT)
    assert ch.sha256_text(prompt) == ch.RENDERED_PROMPT_SHA256
    for phrase in ("food", "eat", "sew", "gift", "wrap", "cook", "garment",
                   "cloth"):
        assert phrase not in ch.CHAPTER_PROMPT_V1.lower(),             "기대 답이 지시문에 들어갔다: %s" % phrase
    assert "STT" not in prompt and "caption" not in prompt
    assert "do not choose" in prompt and "no valid observation" in prompt
    for row in cmap.all_members(DOCUMENT):
        assert row["event_id"] not in prompt, "프롬프트에 event id가 들어갔다"


def test_wvr_u05_the_source_map_hash_is_frozen():
    assert _sha256_file(RUNS / ch.SOURCE_MAP_NAME) == ch.SOURCE_MAP_SHA256
    digest = ch.map_digest(DOCUMENT)
    for row in DOCUMENT["regions"]:
        assert "[REGION %s]" % row["region_id"] in digest
    assert digest.count("[CONFLICT ") == 10
    assert digest.count("[STITCHABLE ") == 12
    assert digest.count("[UNRESOLVED ") == 1


# ── WVR-U06~U09 파싱·스키마 ───────────────────────────────────────
def test_wvr_u06_a_well_formed_payload_parses_into_ordered_chapters():
    chapters = ch.parse_chapters(_payload())
    assert [row["chapter_id"] for row in chapters] == ["CH01", "CH02", "CH03",
                                                       "CH04"]
    assert chapters[0]["start_sec"] == 0.0
    assert chapters[-1]["end_sec"] == 600.0
    assert all(row["end_sec"] > row["start_sec"] for row in chapters)


def test_wvr_u07_schema_and_coverage_violations_are_refused():
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(_payload(((0.0, 300.0), (300.0, 600.0))))   # 2개
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters({"chapters": [
            _chapter(index * 50.0, (index + 1) * 50.0) for index in range(12)]})
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(_payload(((0.0, 200.0), (200.0, 200.0),
                                    (200.0, 600.0))))                 # end<=start
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(_payload(((0.0, 200.0), (250.0, 400.0),
                                    (400.0, 600.0))))                 # 구멍
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(_payload(((24.0, 200.0), (200.0, 400.0),
                                    (400.0, 600.0))))                 # 0에서 시작 안 함
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(_payload(((0.0, 200.0), (200.0, 400.0),
                                    (400.0, 576.0))))                 # 600에서 끝 안 남
    payload = _payload()
    payload["chapters"][1]["confidence_class"] = "0.87"
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(payload)
    payload = _payload()
    payload["chapters"][1]["boundary_reason"] = ["VIBES"]
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(payload)
    payload = _payload()
    payload["chapters"][2]["title"] = "  "
    with pytest.raises(ch.ChapterError):
        ch.parse_chapters(payload)


def test_wvr_u08_report_stage_fields_in_the_output_are_refused():
    for name in ("overview", "analysis", "conclusion", "report"):
        payload = _payload()
        payload[name] = "The video shows..."
        with pytest.raises(ch.ChapterError):
            ch.parse_chapters(payload)


def test_wvr_u09_declared_event_ids_must_exist():
    payload = _payload()
    payload["chapters"][0]["stable_source_events"] = ["W01_E001"]
    assert ch.assert_declared_ids(payload, DOCUMENT) == ["W01_E001"]
    payload["chapters"][1]["evidence_event_ids"] = ["W99_E999"]
    with pytest.raises(ch.ChapterError):
        ch.assert_declared_ids(payload, DOCUMENT)


# ── WVR-U10~U15 계보·안전 ────────────────────────────────────────
def test_wvr_u10_every_chapter_traces_back_to_the_map():
    chapters, lineage = _built()
    assert len(lineage) == len(chapters)
    known = {row["event_id"] for row in DOCUMENT["lineage"]}
    for rows in lineage:
        assert rows["source_regions"] and rows["source_nodes"]
        assert rows["source_event_count"] > 0
        assert set(rows["stable_source_events"]
                   + rows["conflict_source_events"]) <= known
        assert set(rows["source_windows"]) <= set(cmap.VALID_SOURCE_WINDOWS)
    assert lineage[0]["unresolved_intervals"] == [[0.0, 24.0]]
    covered = {node_id for rows in lineage for node_id in rows["conflict_blocks"]}
    assert covered == {row["node_id"]
                       for row in DOCUMENT["nodes"]["conflict_blocks"]}


def test_wvr_u11_a_chapter_with_no_source_events_is_refused(monkeypatch):
    monkeypatch.setattr(ch, "events_in_span", lambda document, start, end: [])
    chapters = ch.parse_chapters(_payload())
    with pytest.raises(ch.ChapterError):
        ch.derive_lineage(chapters, DOCUMENT)


def test_wvr_u12_dropping_one_conflict_observation_is_detected():
    chapters, lineage = _built()
    assert ch.conflict_safety(chapters, lineage, DOCUMENT)["violations"] == []
    tampered = json.loads(json.dumps(lineage))
    for rows in tampered:
        if rows["conflict_sources_preserved"]:
            rows["conflict_sources_preserved"] = \
                rows["conflict_sources_preserved"][:1]
            break
    assert ch.conflict_safety(chapters, tampered, DOCUMENT)["violations"]


def test_wvr_u13_a_winner_field_on_a_chapter_is_detected():
    chapters, lineage = _built()
    chapters[1]["preferred_source"] = "W08"
    assert ch.conflict_safety(chapters, lineage, DOCUMENT)["violations"]


def test_wvr_u14_the_unresolved_opening_must_stay_unresolved():
    chapters, lineage = _built()
    safety = ch.unresolved_safety(chapters, lineage, DOCUMENT)
    assert safety["violations"] == []
    assert safety["unresolved_intervals"] == [[0.0, 24.0]]
    assert safety["policy"] == ch.UNRESOLVED_OPENING_POLICY
    dropped = json.loads(json.dumps(lineage))
    for rows in dropped:
        rows["unresolved_intervals"] = []
    assert ch.unresolved_safety(chapters, dropped, DOCUMENT)["violations"]
    empty = json.loads(json.dumps(lineage))
    empty[0]["stable_source_events"] = []
    empty[0]["conflict_source_events"] = []
    assert ch.unresolved_safety(chapters, empty, DOCUMENT)["violations"]


def test_wvr_u15_boundary_evidence_is_derived_from_the_map():
    chapters, _ = _built()
    boundaries = ch.boundary_evidence(chapters, DOCUMENT)
    known = {row["event_id"] for row in DOCUMENT["lineage"]}
    assert len(boundaries) == len(chapters)
    assert boundaries[0]["is_video_start"] is True
    assert boundaries[0]["before_activity_evidence"] == []
    for row, chapter in zip(boundaries, chapters):
        assert row["boundary_sec"] == chapter["start_sec"]
        assert row["boundary_reason"] == chapter["boundary_reason"]
        assert set(row["before_source_event_ids"]
                   + row["after_source_event_ids"]) <= known
        assert isinstance(row["on_24s_grid"], bool)
    for row in boundaries[1:]:
        assert row["before_activity_evidence"] and row["after_activity_evidence"]


# ── WVR-U16~U19 격자·이상·packet ─────────────────────────────────
def test_wvr_u16_a_grid_copied_segmentation_is_flagged():
    off_grid = ch.grid_alignment(_built()[0])
    assert off_grid["all_internal_boundaries_on_grid"] is False
    assert off_grid["off_grid_count"] == 3
    chapters, lineage = _built(((0.0, 96.0), (96.0, 288.0), (288.0, 480.0),
                                (480.0, 600.0)))
    grid = ch.grid_alignment(chapters)
    assert grid["all_internal_boundaries_on_grid"] is True
    assert grid["on_24s_grid_count"] == 3
    kinds = [row["kind"] for row in ch.anomalies(chapters, lineage, DOCUMENT)]
    assert "ALL_BOUNDARIES_ON_24S_GRID" in kinds


def test_wvr_u17_short_chapters_and_stable_labels_over_conflict_are_flagged():
    payload = _payload(((0.0, 110.0), (110.0, 300.0), (300.0, 310.0),
                        (310.0, 600.0)))
    payload["chapters"][2]["boundary_reason"] = ["ACTIVITY_CHANGE"]
    chapters = ch.parse_chapters(payload)
    lineage = ch.derive_lineage(chapters, DOCUMENT)
    kinds = [row["kind"] for row in ch.anomalies(chapters, lineage, DOCUMENT)]
    assert "SHORT_CHAPTER_WITHOUT_STRONG_TRANSITION" in kinds
    payload = _payload()
    payload["chapters"][1]["confidence_class"] = "STABLE_DOMINANT"
    chapters = ch.parse_chapters(payload)
    lineage = ch.derive_lineage(chapters, DOCUMENT)
    kinds = [row["kind"] for row in ch.anomalies(chapters, lineage, DOCUMENT)]
    assert "STABLE_LABEL_OVER_CONFLICT_REGION" in kinds


def test_wvr_u18_the_packet_asks_and_never_answers():
    chapters, lineage = _built()
    boundaries = ch.boundary_evidence(chapters, DOCUMENT)
    rows = ch.anomalies(chapters, lineage, DOCUMENT)
    packet = ch.packet(DOCUMENT, chapters, lineage, boundaries, rows,
                       {"source_map_sha256": ch.SOURCE_MAP_SHA256,
                        "prompt_sha256": ch.RENDERED_PROMPT_SHA256})
    for question in ("Q1 WHOLE_VIDEO_STRUCTURE", "Q2 BOUNDARY_QUALITY",
                     "Q3 CONFLICT_SAFETY", "Q4 OVERVIEW_INPUT_USABILITY"):
        assert question in packet
    assert packet.count(ch.NOT_ADJUDICATED) >= 4
    stripped = packet.replace(ch.FINAL_VERDICT_VOCABULARY_LINE, "")
    for verdict in ch.FINAL_VERDICTS:
        assert verdict not in stripped
    for chapter in chapters:
        assert "## %s " % chapter["chapter_id"] in packet
    state = ch.executor_state(chapters, rows)
    assert state["verdict"] is None
    assert state["state"] == "EXECUTED / REVIEW_PENDING"
    assert state["overview_generated"] is False


def test_wvr_u19_the_selfcheck_passes_on_the_frozen_input():
    rows = selfcheck.checks(RUNS)["rows"]
    for name, value in rows.items():
        if name == "raw_not_yet_written":
            continue                        # 생성 이후에는 False가 정상이다
        assert value is True, name
    assert "raw_not_yet_written" in rows


# ── WVR-U20~U26 도구 게이트 · 경계 ───────────────────────────────
def test_wvr_u20_the_runner_refuses_to_regenerate(tmp_path, monkeypatch):
    runner = _module(RUNNER, "wvr_chapter_run_mod")
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / ch.SOURCE_MAP_NAME).write_bytes(
        (RUNS / ch.SOURCE_MAP_NAME).read_bytes())
    (runs / runner.RAW_NAME).write_text("already there", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.run(runs)                    # raw가 있으면 재생성 금지
    (runs / runner.RAW_NAME).unlink()
    monkeypatch.setattr(ch, "RETRY_ALLOWED", True)
    with pytest.raises(runner.RunError):
        runner.run(runs)
    monkeypatch.setattr(ch, "RETRY_ALLOWED", False)
    (runs / ch.SOURCE_MAP_NAME).write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError):
        runner.run(runs)                    # 해시 불일치면 실행하지 않는다


def test_wvr_u21_the_builder_refuses_broken_provenance(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / ch.SOURCE_MAP_NAME).write_bytes(
        (RUNS / ch.SOURCE_MAP_NAME).read_bytes())
    with pytest.raises(builder.BuildError):
        builder.build(runs)                 # raw 없음
    raw = json.dumps(_payload(), ensure_ascii=False)
    (runs / builder.RAW_NAME).write_text(raw, encoding="utf-8")
    (runs / builder.PROMPT_NAME).write_text(ch.render_prompt(DOCUMENT),
                                            encoding="utf-8")
    record = {"raw_sha256": ch.sha256_text(raw),
              "prompt_sha256": ch.RENDERED_PROMPT_SHA256,
              "source_map_sha256": ch.SOURCE_MAP_SHA256,
              "generation_attempts": 1, "retry_allowed": False,
              "raw_persisted_before_parse": True, "parsed_here": False,
              "new_vlm_inference_count": 0, "track_a_input_used": False,
              "effective_runtime": {"quantization_mismatch": False,
                                    "do_sample": False,
                                    "max_new_tokens": ch.LLM_MAX_NEW_TOKENS},
              "requested_runtime": {"model_id": ch.LLM_MODEL_ID,
                                    "load_4bit": False,
                                    "max_new_tokens": ch.LLM_MAX_NEW_TOKENS},
              "code_git_head": "x", "prereg_commit": "y",
              "elapsed_sec": 1.0, "vram": {}, "raw_chars": len(raw)}
    (runs / builder.RECORD_NAME).write_text(json.dumps(record),
                                            encoding="utf-8")
    built = builder.build(runs)
    assert built["summary"]["chapter_count"] == 4

    broken = dict(record, raw_sha256="0" * 64)
    (runs / builder.RECORD_NAME).write_text(json.dumps(broken),
                                            encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    broken = dict(record, generation_attempts=2)
    (runs / builder.RECORD_NAME).write_text(json.dumps(broken),
                                            encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    broken = dict(record, effective_runtime=dict(
        record["effective_runtime"], quantization_mismatch=True))
    (runs / builder.RECORD_NAME).write_text(json.dumps(broken),
                                            encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs)
    (runs / builder.RECORD_NAME).write_text(json.dumps(record),
                                            encoding="utf-8")
    for flag in ("OVERVIEW_GENERATION_ALLOWED", "REPORT_GENERATION_ALLOWED",
                 "ANALYSIS_GENERATION_ALLOWED", "CONFLICT_RESOLUTION_ALLOWED",
                 "SYNTHETIC_FILL_ALLOWED", "RETRY_ALLOWED",
                 "VERDICT_BY_EXECUTOR"):
        monkeypatch.setattr(ch, flag, True)
        with pytest.raises(builder.BuildError):
            builder.build(runs)
        monkeypatch.setattr(ch, flag, False)


def test_wvr_u22_the_builder_refuses_a_parse_failure(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / ch.SOURCE_MAP_NAME).write_bytes(
        (RUNS / ch.SOURCE_MAP_NAME).read_bytes())
    raw = "I cannot segment this video."
    (runs / builder.RAW_NAME).write_text(raw, encoding="utf-8")
    (runs / builder.RECORD_NAME).write_text(json.dumps(
        {"raw_sha256": ch.sha256_text(raw),
         "prompt_sha256": ch.RENDERED_PROMPT_SHA256,
         "source_map_sha256": ch.SOURCE_MAP_SHA256,
         "generation_attempts": 1, "retry_allowed": False,
         "raw_persisted_before_parse": True, "parsed_here": False,
         "effective_runtime": {"quantization_mismatch": False}}),
        encoding="utf-8")
    with pytest.raises(builder.BuildError) as error:
        builder.build(runs)
    assert "PARSE_FAILURE" in str(error.value)


def test_wvr_u23_the_validator_computes_its_checks_from_the_artifacts():
    source = VALIDATOR.read_text(encoding="utf-8")
    for expression in (
            'ch.sha256_text(raw) == record["raw_sha256"]',
            'chapters_doc["conflict_safety"]["violations"] == []',
            'chapters_doc["unresolved_safety"]["violations"] == []',
            '"all_internal_boundaries_on_grid"',
            'record["effective_runtime"]["do_sample"] is False'):
        assert expression in source, "validator 검사가 실제 계산이 아니다: %s" \
            % expression
    for verdict in ch.FINAL_VERDICTS:
        assert verdict not in source, "validator가 최종 판정을 계산한다"


def test_wvr_u24_no_report_stage_artifact_is_produced():
    assert ch.OVERVIEW_GENERATION_ALLOWED is False
    assert ch.ANALYSIS_GENERATION_ALLOWED is False
    assert ch.REPORT_GENERATION_ALLOWED is False
    for name in ("chapter_v1_overview.md", "chapter_v1_analysis.md",
                 "chapter_v1_conclusion.md", "chapter_v1_report.hwpx"):
        assert not (RUNS / name).exists(), name


def test_wvr_u25_the_frozen_boundaries_are_untouched():
    assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert not (RUNS / "m9_report_test.json").exists()
    assert _sha256_file(RUNS / "stitch_v1_verdicts.json") == \
        cmap.FROZEN_HASHES["stitch_v1_verdicts.json"]
    assert _sha256_file(RUNS / "event_map_v1_registry.json") == \
        cmap.FROZEN_HASHES["event_map_v1_registry.json"]
    assert ch.TRACK_A_INPUT_ALLOWED is False
    assert ch.NEW_VLM_INFERENCE_ALLOWED is False
    assert ch.PRODUCTION_PROMOTION_ALLOWED is False


def test_wvr_u26_the_generated_artifacts_pass_the_validator_when_present():
    if not (RUNS / builder.CHAPTERS_NAME).is_file():
        pytest.skip("chapter 생성 전이다")
    validator = _module(VALIDATOR, "wvr_chapter_validate_mod")
    rows = validator.checks(RUNS)
    failed = [name for name, value in rows.items() if not value]
    assert not failed, failed
