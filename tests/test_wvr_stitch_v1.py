"""Overlap event stitching shadow 계약 (2026-09-10 · WVR-S01~S33).

```
대상   valid-valid adjacency 22개 (O02…O23) · 각 24초 · 공유 프레임 12장
단위   overlap-local event sequence (event 한 줄 매칭이 아니다)
어휘   relation 5개 · 상위 판정 3개 — executor는 채우지 않는다
계약   새 추론 0회 · 임계 금지 · packet/pairs/audit에 창·event id 미노출 ·
      mapping은 22개 판정 전까지 봉인
```
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_density_v2 as v2
import wvr_event_map_v1 as em
import wvr_shadow_v1 as sh
import wvr_stitch_v1 as st

ROOT = Path(__file__).resolve().parents[1]
PREREG_REL = ("docs/preregistration/"
              "WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md")
PREREG = ROOT / PREREG_REL
BUILDER = ROOT / "scripts/wvr_stitch_build.py"
VERDICT_TOOL = ROOT / "scripts/wvr_stitch_verdicts.py"
VALIDATOR = ROOT / "scripts/wvr_stitch_validate.py"
RUNS = ROOT / "runs/wvr_light_v1"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"
SUBMISSION_SHA = ("5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca9"
                  "94e9cd7b")
PREREG_SHA = "41081254f9004d8bb4d9cfdd5b3bfaf5ee820165"


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _module(BUILDER, "wvr_stitch_build_mod")
verdict_tool = _module(VERDICT_TOOL, "wvr_stitch_verdicts_mod")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _event(event_id, window, start, end, actor="person", action="holding",
           obj="a bottle"):
    return {"event_id": event_id, "source_window": window,
            "start_sec": start, "end_sec": end, "actor": actor,
            "action": action, "object_or_state": obj}


def _full_verdicts(relation=st.CONTINUATION, top=st.STITCHABLE):
    return {"verdicts": [{"overlap_id": row["overlap_id"],
                          "relation": relation, "top_verdict": top}
                         for row in st.overlaps()]}


# ── WVR-S01~S07 대상·어휘 동결 ─────────────────────────────────────
def test_wvr_s01_the_preregistration_is_committed():
    done = subprocess.run(["git", "ls-files", "--error-unmatch", PREREG_REL],
                          cwd=str(ROOT), capture_output=True, text=True)
    assert done.returncode == 0, "사전등록이 커밋되지 않았다"
    assert PREREG.is_file()


def test_wvr_s02_exactly_22_valid_valid_overlaps():
    rows = st.overlaps()
    assert len(rows) == st.EXPECTED_OVERLAP_COUNT == 22
    assert [row["overlap_id"] for row in rows] == [
        "O%02d" % index for index in range(2, 24)]
    assert all("W00" not in (row["earlier"], row["later"]) for row in rows)
    assert st.EXCLUDED_OVERLAPS == ("O01",)
    assert all(round(row["end_sec"] - row["start_sec"], 6) == 24.0
               for row in rows)


def test_wvr_s03_each_overlap_shares_twelve_frames():
    for row in st.overlaps():
        shared = st.shared_times(row)
        assert len(shared) == st.SHARED_FRAMES_PER_OVERLAP == 12
        assert all(row["start_sec"] <= time < row["end_sec"]
                   for time in shared)


def test_wvr_s04_the_comparison_unit_is_the_sequence():
    assert st.COMPARISON_UNIT == "overlap_local_event_sequence"
    assert "report-material contradiction" in st.JUDGMENT_BASIS


def test_wvr_s05_the_reviewer_vocabularies_are_frozen():
    assert st.RELATION_VERDICTS == ("SAME_EVENT", "CONTINUATION",
                                    "TRANSITION", "CONFLICT", "UNRESOLVED")
    assert st.TOP_VERDICTS == ("STITCHABLE", "MATERIAL_CONFLICT",
                               "UNRESOLVED")
    assert st.FINAL_VERDICTS == ("STITCHING_SHADOW_PASS",
                                 "STITCHING_SHADOW_HOLD",
                                 "STITCHING_SHADOW_INCONCLUSIVE")
    assert st.NOT_ADJUDICATED == "NOT_ADJUDICATED"
    assert st.EXECUTOR_STATE == "EXECUTED / REVIEW_PENDING"


def test_wvr_s06_every_expansion_flag_is_off():
    for name in ("NEW_INFERENCE_ALLOWED", "NEW_LLM_CALL_ALLOWED",
                 "EVENT_TEXT_MUTATION_ALLOWED", "EVENT_MAP_REBUILD_ALLOWED",
                 "ADJUDICATED_MAP_BUILD_ALLOWED", "SEMANTIC_CHAPTER_ALLOWED",
                 "OVERVIEW_GENERATION_ALLOWED",
                 "SIMILARITY_THRESHOLD_ALLOWED", "VERDICT_BY_EXECUTOR",
                 "MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED",
                 "W00_RERUN_ALLOWED", "PRODUCTION_PROMOTION_ALLOWED"):
        assert getattr(st, name) is False, "%s가 열려 있다" % name


def test_wvr_s07_prior_verdict_is_recorded():
    assert st.PRIOR_STATE["WVR_EVENT_MAP_COVERAGE_SHADOW_V1"] == \
        "CLOSED / EVENT_MAP_SHADOW_HOLD"
    answers = st.PRIOR_STATE["reviewer_answers"]
    assert answers["Q1_FLOW_RECOVERABLE"] == "COARSELY YES"
    assert answers["Q2_GAP_MATERIALITY"] == "NOT PRIMARY BLOCKER"
    assert answers["Q3_EVENT_MAP_USABLE"] == "NO"
    assert "stitching" in st.PRIOR_STATE["bottleneck"]
    for phrase in ("Event Map이 검증됐다", "stitching이 해결됐다",
                   "0.5fps sufficient", "Semantic Chapter로 바로 간다"):
        assert phrase in st.FORBIDDEN_CONCLUSIONS


# ── WVR-S08~S12 clip · blinding ───────────────────────────────────
def test_wvr_s08_clip_preserves_the_original_interval():
    overlap = st.overlap_by_id("O02")
    rows = st.clip_sequence([_event("W01_E001", "W01", 40.0, 60.0)], overlap)
    assert len(rows) == 1
    row = rows[0]
    assert row["original_start"] == 40.0 and row["original_end"] == 60.0
    assert row["clipped_start"] == 48.0 and row["clipped_end"] == 60.0
    assert row["clipped"] is True
    assert row["actor"] == "person"


def test_wvr_s09_clip_drops_events_outside_the_overlap():
    overlap = st.overlap_by_id("O02")
    rows = st.clip_sequence([_event("W01_E001", "W01", 24.0, 40.0),
                             _event("W01_E002", "W01", 72.0, 80.0),
                             _event("W01_E003", "W01", 50.0, 55.0)], overlap)
    assert [row["event_id"] for row in rows] == ["W01_E003"]
    assert rows[0]["clipped"] is False


def test_wvr_s10_clip_is_time_ordered_and_refuses_text_mutation(monkeypatch):
    overlap = st.overlap_by_id("O02")
    rows = st.clip_sequence([_event("W01_E002", "W01", 60.0, 66.0),
                             _event("W01_E001", "W01", 50.0, 55.0)], overlap)
    assert [row["event_id"] for row in rows] == ["W01_E001", "W01_E002"]
    monkeypatch.setattr(st, "EVENT_TEXT_MUTATION_ALLOWED", True)
    with pytest.raises(st.StitchError):
        st.clip_sequence([], overlap)


def test_wvr_s11_blinding_is_deterministic_and_complementary():
    for overlap_id in ("O02", "O13", "O23"):
        earlier = st.blind_label(overlap_id, "earlier", PREREG_SHA)
        later = st.blind_label(overlap_id, "later", PREREG_SHA)
        assert {earlier, later} == {"A", "B"}
        assert st.blind_label(overlap_id, "earlier", PREREG_SHA) == earlier
        assigned = {st.blind_label(overlap_id, "earlier", "salt%d" % index)
                    for index in range(40)}
        assert assigned == {"A", "B"}, "earlier가 한쪽 라벨에 고정돼 있다"
    with pytest.raises(st.StitchError):
        st.blind_label("O02", "middle", PREREG_SHA)
    with pytest.raises(st.StitchError):
        st.blind_label("O02", "earlier", "")


def test_wvr_s12_blinding_varies_across_overlaps():
    labels = {overlap_id: st.blind_label(overlap_id, "earlier", PREREG_SHA)
              for overlap_id in [row["overlap_id"] for row in st.overlaps()]}
    assert set(labels.values()) == {"A", "B"}, \
        "모든 overlap이 같은 배정이면 blinding이 의미가 없다"


# ── WVR-S13~S16 audit (임계 없음 · blind) ─────────────────────────
def test_wvr_s13_audit_counts_frozen_relations_without_thresholds():
    arm_a = [_event("W01_E001", "W01", 50.0, 55.0, action="pouring",
                    obj="liquid into a bowl")]
    arm_b = [_event("W02_E001", "W02", 50.0, 55.0, action="pouring",
                    obj="liquid into a bowl"),
             _event("W02_E002", "W02", 55.0, 60.0, actor="a worker",
                    action="stacking", obj="boxes")]
    rows = [st.clip_sequence(arm, st.overlap_by_id("O02"))
            for arm in (arm_a, arm_b)]
    audit = st.pair_audit(rows[0], rows[1])
    assert audit["role"] == "AUDIT_DIAGNOSTIC_ONLY"
    assert audit["threshold_used"] is False
    assert audit["arm_a_event_count"] == 1 and audit["arm_b_event_count"] == 2
    assert audit["exact_signature_pair_count"] == 1
    assert audit["pairwise_relation_counts"][v2.SEMANTICALLY_EQUIVALENT] == 1
    assert audit["pairwise_relation_counts"][v2.SEMANTICALLY_DIFFERENT] == 1
    assert audit["shared_token_count"] == 4
    assert audit["arm_a_only_token_count"] == 0
    assert audit["arm_b_only_token_count"] == 3


def test_wvr_s14_audit_keys_never_name_earlier_or_later():
    audit = st.pair_audit([], [])
    assert not any(key.startswith(("earlier_", "later_")) for key in audit), \
        "audit 키가 창 순서를 드러낸다"
    assert "arm_a_event_count" in audit and "arm_b_event_count" in audit
    assert audit["arm_a_span"] is None and audit["arm_b_span"] is None


def test_wvr_s15_audit_refuses_a_similarity_threshold(monkeypatch):
    monkeypatch.setattr(st, "SIMILARITY_THRESHOLD_ALLOWED", True)
    with pytest.raises(st.StitchError):
        st.pair_audit([], [])


def test_wvr_s16_sequence_tokens_union_the_whole_arm():
    rows = [_event("W01_E001", "W01", 50.0, 52.0, action="chopping",
                   obj="onion"),
            _event("W01_E002", "W01", 52.0, 54.0, action="peeling",
                   obj="carrot")]
    tokens = st.sequence_tokens(rows)
    assert {"chopping", "peeling", "onion", "carrot"} <= tokens


# ── WVR-S17~S21 verdict 기록 · reveal 게이트 ──────────────────────
def test_wvr_s17_the_executor_records_no_verdict_by_default():
    state = st.parse_verdicts(None)
    assert state["adjudicated_count"] == 0
    assert state["expected_count"] == 22
    assert state["complete"] is False
    assert all(row["relation"] == st.NOT_ADJUDICATED
               and row["top_verdict"] == st.NOT_ADJUDICATED
               and row["adjudicated"] is False
               for row in state["verdicts"])
    assert state["final_verdict"] is None
    assert state["final_verdict_by_executor"] is False


def test_wvr_s18_only_the_frozen_vocabulary_is_accepted():
    good = st.parse_verdicts({"verdicts": [
        {"overlap_id": "O02", "relation": "CONTINUATION",
         "top_verdict": "STITCHABLE", "note": "같은 흐름"}]})
    assert good["adjudicated_count"] == 1
    assert good["relation_counts"]["CONTINUATION"] == 1
    assert good["top_verdict_counts"]["STITCHABLE"] == 1
    for bad in ({"overlap_id": "O02", "relation": "PROBABLY_SAME",
                 "top_verdict": "STITCHABLE"},
                {"overlap_id": "O02", "relation": "CONTINUATION",
                 "top_verdict": "LOOKS_FINE"},
                {"overlap_id": "O99", "relation": "CONTINUATION",
                 "top_verdict": "STITCHABLE"},
                {"overlap_id": "O01", "relation": "CONTINUATION",
                 "top_verdict": "STITCHABLE"}):
        with pytest.raises(st.StitchError):
            st.parse_verdicts({"verdicts": [bad]})


def test_wvr_s19_the_executor_may_not_fill_verdicts(monkeypatch):
    monkeypatch.setattr(st, "VERDICT_BY_EXECUTOR", True)
    with pytest.raises(st.StitchError):
        st.parse_verdicts(None)


def test_wvr_s20_mapping_reveal_needs_every_overlap_adjudicated():
    empty = st.parse_verdicts(None)
    assert st.reveal_allowed(empty)["allowed"] is False
    assert st.reveal_allowed(empty)["reason"] == "VERDICTS_INCOMPLETE"
    partial = st.parse_verdicts({"verdicts": [
        {"overlap_id": "O02", "relation": "SAME_EVENT",
         "top_verdict": "STITCHABLE"}]})
    assert st.reveal_allowed(partial)["allowed"] is False
    full = st.parse_verdicts(_full_verdicts())
    assert full["complete"] is True
    assert full["adjudicated_count"] == 22
    assert st.reveal_allowed(full)["allowed"] is True


def test_wvr_s21_the_verdict_tool_refuses_an_early_reveal(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    with pytest.raises(verdict_tool.VerdictError):
        verdict_tool.reveal(runs)
    state = verdict_tool.record(runs, _full_verdicts(st.CONFLICT,
                                                     st.MATERIAL_CONFLICT))
    assert state["complete"] is True
    assert state["relation_counts"]["CONFLICT"] == 22
    assert state["top_verdict_counts"]["MATERIAL_CONFLICT"] == 22
    assert state["final_verdict"] is None
    (runs / verdict_tool.VERDICTS_NAME).write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(verdict_tool.VerdictError):
        verdict_tool.reveal(runs)          # mapping 파일이 아직 없다


# ── WVR-S22~S27 산출물 (blind · 계보 · 결정성) ────────────────────
def test_wvr_s22_the_builder_refuses_bad_registry_and_open_flags(tmp_path,
                                                                 monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    with pytest.raises(builder.BuildError):
        builder.build(runs, PREREG_SHA)
    source = RUNS / builder.REGISTRY_NAME
    if not source.is_file():
        pytest.skip("registry가 없다")
    registry = json.loads(source.read_text(encoding="utf-8"))
    (runs / builder.REGISTRY_NAME).write_text(
        json.dumps({**registry, "event": "OTHER"}, ensure_ascii=False),
        encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs, PREREG_SHA)
    (runs / builder.REGISTRY_NAME).write_text(
        json.dumps({**registry, "new_inference_count": 1},
                   ensure_ascii=False), encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs, PREREG_SHA)
    drifted = {**registry,
               "source_manifest": {**registry["source_manifest"],
                                   "unchanged": False}}
    (runs / builder.REGISTRY_NAME).write_text(
        json.dumps(drifted, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(builder.BuildError):
        builder.build(runs, PREREG_SHA)
    (runs / builder.REGISTRY_NAME).write_text(
        json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    for name in ("NEW_INFERENCE_ALLOWED", "NEW_LLM_CALL_ALLOWED",
                 "EVENT_MAP_REBUILD_ALLOWED",
                 "ADJUDICATED_MAP_BUILD_ALLOWED"):
        monkeypatch.setattr(st, name, True)
        with pytest.raises(builder.BuildError):
            builder.build(runs, PREREG_SHA)
        monkeypatch.setattr(st, name, False)


def _built(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    source = RUNS / builder.REGISTRY_NAME
    if not source.is_file():
        pytest.skip("registry가 없다")
    (runs / builder.REGISTRY_NAME).write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8")
    return runs, builder.build(runs, PREREG_SHA)


def test_wvr_s23_the_packet_and_pairs_hide_window_and_event_ids(tmp_path):
    _, built = _built(tmp_path)
    packet = built["packet"]
    assert packet.count("### Arm A") == 22 and packet.count("### Arm B") == 22
    for index in range(24):
        assert ("W%02d" % index) not in packet
    rows = [row for pair in built["pairs"]["pairs"]
            for arm in pair["arms"].values() for row in arm]
    assert rows, "arm event가 없다"
    for row in rows:
        assert "source_window" not in row and "event_id" not in row
        assert row["local_id"].startswith(("O", "o"))
    assert "local_id_map" in built["mapping"]["mapping"]["O02"]
    assert built["mapping"]["mapping"]["O02"]["local_id_map"]


def test_wvr_s24_pairs_keep_the_original_intervals_inside_the_overlap(
        tmp_path):
    _, built = _built(tmp_path)
    for pair in built["pairs"]["pairs"]:
        assert pair["shared_frame_count"] == 12
        assert set(pair["arms"]) == {"A", "B"}
        assert pair["comparison_unit"] == "overlap_local_event_sequence"
        for arm in pair["arms"].values():
            for row in arm:
                assert pair["start_sec"] <= row["clipped_start"]
                assert row["clipped_end"] <= pair["end_sec"]
                assert row["original_start"] <= row["clipped_start"]
                assert row["original_end"] >= row["clipped_end"]


def test_wvr_s25_the_build_is_deterministic_and_records_lineage(tmp_path):
    runs, built = _built(tmp_path)
    again = builder.build(runs, PREREG_SHA)
    assert json.dumps(built["pairs"], sort_keys=True) == json.dumps(
        again["pairs"], sort_keys=True)
    assert built["packet"] == again["packet"]
    summary = built["summary"]
    assert summary["new_inference_count"] == 0
    assert summary["new_llm_call_count"] == 0
    assert summary["source_manifest_sha256"] == \
        em.VALID_SOURCE_MANIFEST_SHA256
    assert summary["registry_sha256"]
    assert summary["executor_state"]["state"] == st.EXECUTOR_STATE
    assert summary["executor_state"]["verdict"] is None
    assert summary["mapping_sealed"] is True


def test_wvr_s26_a_different_salt_changes_the_blind_assignment(tmp_path):
    runs, built = _built(tmp_path)
    other = builder.build(runs, "some-other-salt")
    assert built["mapping"]["mapping"] != other["mapping"]["mapping"], \
        "salt가 달라도 배정이 같다면 blinding이 salt와 무관하다"


def test_wvr_s27_the_audit_is_blind_and_threshold_free(tmp_path):
    _, built = _built(tmp_path)
    audit = built["audit"]
    assert audit["role"] == "AUDIT_DIAGNOSTIC_ONLY"
    assert audit["threshold_used"] is False
    assert len(audit["overlaps"]) == 22
    counts = {pair["overlap_id"]: pair["arm_event_counts"]
              for pair in built["pairs"]["pairs"]}
    for row in audit["overlaps"]:
        assert not any(key.startswith(("earlier_", "later_")) for key in row)
        assert row["threshold_used"] is False
        assert len(row["shared_frame_times"]) == 12
        assert row["arm_a_event_count"] == counts[row["overlap_id"]]["A"], \
            "audit이 Arm A가 아닌 창 순서로 계산됐다"
        assert row["arm_b_event_count"] == counts[row["overlap_id"]]["B"]


# ── WVR-S28~S30 경계 ─────────────────────────────────────────────
def test_wvr_s28_prior_artifacts_and_boundaries_are_untouched():
    registry = RUNS / builder.REGISTRY_NAME
    if registry.is_file():
        rows = json.loads(registry.read_text(encoding="utf-8"))
        assert rows["source_manifest"]["unchanged"] is True
        assert rows["event_count"] == 160
    for name in ("shadow_v1_W00.json", "shadow_v1_W00_raw.txt"):
        path = RUNS / name
        if path.is_file():
            assert _sha256_file(path) in (
                em.PRIOR_STATE and (
                    "c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e"
                    "44daa074",
                    "c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b"
                    "2b36b7e6"))
    if SUBMISSION.is_file():
        assert _sha256_file(SUBMISSION) == SUBMISSION_SHA
    assert sh.EXPECTED_OVERLAP_COUNT == 23, "SHADOW 겹침 정의는 그대로다"


def test_wvr_s29_the_validator_checks_the_blinding_and_verdict_gates():
    source = VALIDATOR.read_text(encoding="utf-8")
    for name in ("overlap_count_22", "o01_and_w00_excluded",
                 "pairs_carry_no_window_or_event_ids", "audit_is_blind",
                 "audit_has_no_threshold", "executor_filled_no_verdict",
                 "reveal_refused_now", "deterministic_rebuild",
                 "event_map_rebuild_blocked", "packet_hides_window_ids"):
        assert '"%s":' % name in source, "validator가 %s를 빠뜨렸다" % name
    assert 'not any(key.startswith(("earlier_", "later_"))' in source
    assert '"pairs_carry_no_window_or_event_ids": all(\n            set(row) == {"local_id", "original_start", "original_end",\n                         "clipped_start", "clipped_end", "clipped", "actor",\n                         "action", "object_or_state"}\n            for row in all_rows),' in source, "validator의 blind 검사가 실제 계산이 아니다"
    assert '"reveal_refused_now":\n            st.reveal_allowed(verdicts)["allowed"] is False,' in source, "validator의 reveal 검사가 실제 계산이 아니다"


def test_wvr_s30_no_generative_call_in_any_tool():
    for path in (BUILDER, VERDICT_TOOL, VALIDATOR):
        source = path.read_text(encoding="utf-8")
        for token in ("model.generate", "AutoProcessor", "import torch",
                      "openai", "anthropic"):
            assert token not in source, "%s에 생성 경로가 있다: %s" % (path.name,
                                                                 token)


# ── WVR-S31~S33 구조 단정 · 도구 게이트 ──────────────────────────
def test_wvr_s31_schedule_guards_fire_when_the_design_moves(monkeypatch):
    """O01 배제·개수·겹침 길이 세 가드를 각각 분리해 확인한다."""
    monkeypatch.setattr(st, "EXCLUDED_OVERLAPS", ())
    rows = st.overlaps()
    assert len(rows) == 22, "W00 필터가 O01을 빼지 못했다"
    assert all(row["overlap_id"] != "O01" for row in rows)
    monkeypatch.setattr(st, "EXCLUDED_OVERLAPS", ("O01",))

    monkeypatch.setattr(st, "EXPECTED_OVERLAP_COUNT", 23)
    with pytest.raises(st.StitchError):
        st.overlaps()                      # 개수 가드
    monkeypatch.setattr(st, "EXPECTED_OVERLAP_COUNT", 22)

    monkeypatch.setattr(st, "OVERLAP_SEC", 12.0)
    with pytest.raises(st.StitchError):
        st.overlaps()                      # 겹침 길이 가드
    monkeypatch.setattr(st, "OVERLAP_SEC", 24.0)
    assert len(st.overlaps()) == 22


def test_wvr_s32_the_verdict_tool_gates_reveal_and_executor_input(tmp_path,
                                                                  monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / verdict_tool.MAPPING_NAME).write_text(json.dumps(
        {"mapping": {row["overlap_id"]: {"A": "W01", "B": "W02",
                                         "start_sec": row["start_sec"],
                                         "end_sec": row["end_sec"]}
                     for row in st.overlaps()}}), encoding="utf-8")
    partial = verdict_tool.record(runs, {"verdicts": [
        {"overlap_id": "O02", "relation": "SAME_EVENT",
         "top_verdict": "STITCHABLE"}]})
    (runs / verdict_tool.VERDICTS_NAME).write_text(
        json.dumps(partial, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(verdict_tool.VerdictError):
        verdict_tool.reveal(runs)          # mapping은 있지만 판정이 불완전하다

    full = verdict_tool.record(runs, _full_verdicts())
    (runs / verdict_tool.VERDICTS_NAME).write_text(
        json.dumps(full, ensure_ascii=False), encoding="utf-8")
    revealed = verdict_tool.reveal(runs)
    assert len(revealed["rows"]) == 22
    assert all(row["A"] and row["B"] for row in revealed["rows"])

    monkeypatch.setattr(st, "parse_verdicts",
                        lambda payload: {"verdicts": [], "complete": False,
                                         "adjudicated_count": 0,
                                         "expected_count": 22,
                                         "relation_counts": {},
                                         "top_verdict_counts": {},
                                         "final_verdict": None,
                                         "final_verdict_by_executor": False})
    monkeypatch.setattr(st, "VERDICT_BY_EXECUTOR", True)
    with pytest.raises(verdict_tool.VerdictError):
        verdict_tool.record(runs, _full_verdicts())


def test_wvr_s33_the_current_state_starts_empty(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    state = verdict_tool.current(runs)
    assert state["adjudicated_count"] == 0
    assert state["complete"] is False
    assert state["recorded_by"] == "reviewer"
    assert all(row["relation"] == "NOT_ADJUDICATED"
               for row in state["verdicts"])
