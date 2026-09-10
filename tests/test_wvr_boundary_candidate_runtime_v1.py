"""Runtime and artifact-boundary contract for boundary candidate V1."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import wvr_boundary_candidate_v1 as bc

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs/wvr_light_v1"
SUBMISSION = ROOT / "runs/quality_candidate/S7/report.hwpx"


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _module(ROOT / "scripts/wvr_bcand_build.py", "bcand_runtime_builder")
selfcheck = _module(ROOT / "scripts/wvr_bcand_selfcheck.py", "bcand_selfcheck")
runner = _module(ROOT / "scripts/wvr_bcand_run.py", "bcand_runner")
parser_mod = _module(ROOT / "scripts/wvr_bcand_parse.py", "bcand_parser")
validator = _module(ROOT / "scripts/wvr_bcand_validate.py", "bcand_validator")


def _prepared(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / bc.SOURCE_MAP_NAME).write_bytes((RUNS / bc.SOURCE_MAP_NAME).read_bytes())
    assert builder.main(["--runs", str(runs)]) == 0
    return runs


def _row(candidate_id):
    return {"candidate_id": candidate_id,
            "proposal": bc.NO_CHAPTER_TRANSITION,
            "before_activity": "broad work continues",
            "after_activity": "broad work continues",
            "rationale": "the broad task remains materially similar"}


def _raw_for_prompt(prompt):
    ids = list(dict.fromkeys(re.findall(r"C\d{3}", prompt)))
    return json.dumps({"candidates": [_row(value) for value in ids]})


def _factory(calls, runs):
    def factory(runtime):
        assert runtime == {
            "model_id": bc.LLM_MODEL_ID,
            "revision": bc.LLM_MODEL_REVISION,
            "dtype": bc.LLM_DTYPE,
            "attn_implementation": bc.LLM_ATTN_IMPLEMENTATION,
            "load_4bit": False,
            "do_sample": False,
            "max_new_tokens": bc.LLM_MAX_NEW_TOKENS,
        }

        def generate(prompt):
            assert any(path.read_text(encoding="utf-8") == prompt
                       for path in runs.glob("bcand_v1_prompt_B*.txt"))
            calls.append(prompt)
            return _raw_for_prompt(prompt)

        generate.provenance = {
            "effective_model_id": bc.LLM_MODEL_ID,
            "effective_model_revision": bc.LLM_MODEL_REVISION,
            "effective_dtype": "torch.bfloat16",
            "attn_implementation": "sdpa",
            "effective_quantized": False,
        }
        generate.runtime_metrics = lambda: {
            "cuda_available": True,
            "device_count": 1,
            "device_names": ["NVIDIA GeForce RTX 4090"],
            "max_memory_allocated_bytes": 1234,
            "max_memory_reserved_bytes": 2048,
        }
        return generate
    return factory


def test_preflight_rebuilds_the_frozen_blind_inputs(tmp_path):
    runs = _prepared(tmp_path)
    report = selfcheck.checks(runs, SUBMISSION)
    assert report["status"] == "PASS"
    assert all(report["checks"].values())
    assert report["candidate_count"] == 144
    assert report["batch_count"] == 18
    assert report["inference_count"] == 0


def test_runner_is_raw_only_and_records_executor_handoff(tmp_path):
    runs = _prepared(tmp_path)
    calls = []
    record = runner.run(runs, _factory(calls, runs))
    assert len(calls) == 18
    assert len(list(runs.glob("bcand_v1_raw_B*.txt"))) == 18
    assert not (runs / "bcand_v1_proposals.json").exists()
    assert record["raw_persisted_before_parse"] is True
    assert record["parsed_here"] is False
    assert record["generation_attempts_per_batch"] == 1
    assert record["previous_executor_agent"] == "Claude in VS Code"
    assert record["current_executor_agent"] == "Codex in VS Code"
    assert record["first_execution"] is True
    assert record["preexisting_raw_batches"] == []
    assert len(record["raw_sha256"]) == 18
    assert record["runtime_metrics"]["device_names"] \
        == ["NVIDIA GeForce RTX 4090"]
    assert record["runtime_metrics"]["max_memory_allocated_bytes"] == 1234


def test_runner_refuses_a_runtime_mismatch_before_generation(tmp_path):
    runs = _prepared(tmp_path)
    calls = []

    def wrong_factory(runtime):
        generate = _factory(calls, runs)(runtime)
        generate.provenance["effective_model_revision"] = "wrong-revision"
        return generate

    with pytest.raises(runner.RunError, match="RUNTIME_MISMATCH"):
        runner.run(runs, wrong_factory)
    assert calls == []
    assert not list(runs.glob("bcand_v1_raw_B*.txt"))


def test_runner_resumes_missing_batches_without_regenerating_raw(tmp_path):
    runs = _prepared(tmp_path)
    first_prompt = (runs / "bcand_v1_prompt_B01.txt").read_text(encoding="utf-8")
    original = _raw_for_prompt(first_prompt)
    (runs / "bcand_v1_raw_B01.txt").write_text(original, encoding="utf-8")
    calls = []
    record = runner.run(runs, _factory(calls, runs))
    assert len(calls) == 17
    assert (runs / "bcand_v1_raw_B01.txt").read_text(encoding="utf-8") == original
    assert record["preexisting_raw_batches"] == ["B01"]
    assert record["resumed_batches"] == ["B%02d" % index for index in range(2, 19)]
    with pytest.raises(runner.RunError, match="already complete"):
        runner.run(runs, _factory([], runs))


def test_parser_requires_all_raw_batches_and_never_reconstructs_them(tmp_path):
    runs = _prepared(tmp_path)
    (runs / "bcand_v1_raw_B01.txt").write_text(
        _raw_for_prompt((runs / "bcand_v1_prompt_B01.txt").read_text(
            encoding="utf-8")), encoding="utf-8")
    with pytest.raises(parser_mod.ParseError, match="RAW_NOT_PERSISTED"):
        parser_mod.parse(runs)
    assert len(list(runs.glob("bcand_v1_raw_B*.txt"))) == 1


def test_parser_builds_reviewer_material_without_mapping(tmp_path):
    runs = _prepared(tmp_path)
    runner.run(runs, _factory([], runs))
    result = parser_mod.parse(runs)
    assert len(result["proposals"]) == 144
    assert result["counts"][bc.NO_CHAPTER_TRANSITION] == 144
    assert result["packet_candidate_ids"] == []
    packet = (runs / "bcand_v1_packet.md").read_text(encoding="utf-8")
    assert "candidate_to_time" not in packet
    assert not re.search(r"\bW\d{2}\b|\bR\d{2}\b|\bCH\d{2}\b", packet)
    assert (runs / "bcand_v1_packet_ids.json").is_file()
    assert (runs / "bcand_v1_leakage_audit.json").is_file()


def test_parser_audits_the_entire_persisted_raw_output(tmp_path):
    runs = _prepared(tmp_path)

    def leaky_factory(runtime):
        generate = _factory([], runs)(runtime)
        clean_generate = generate

        def leaky_generate(prompt):
            return clean_generate(prompt) + "\nsource window W07"

        leaky_generate.provenance = generate.provenance
        leaky_generate.runtime_metrics = generate.runtime_metrics
        return leaky_generate

    runner.run(runs, leaky_factory)
    with pytest.raises(parser_mod.ParseError, match="GEOMETRY_LEAKAGE"):
        parser_mod.parse(runs)


def test_parser_rejects_conflict_winner_language_in_rationale(tmp_path):
    runs = _prepared(tmp_path)

    def winner_factory(runtime):
        generate = _factory([], runs)(runtime)

        def winner_generate(prompt):
            payload = json.loads(generate(prompt))
            payload["candidates"][0]["rationale"] = \
                "Observation Set A is the more reliable winner"
            return json.dumps(payload)

        winner_generate.provenance = generate.provenance
        winner_generate.runtime_metrics = generate.runtime_metrics
        return winner_generate

    runner.run(runs, winner_factory)
    with pytest.raises(parser_mod.ParseError,
                       match="CONFLICT_RESOLUTION_VIOLATION"):
        parser_mod.parse(runs)


def test_leakage_detection_does_not_treat_every_number_as_a_timestamp():
    events_doc = json.loads((RUNS / bc.SOURCE_MAP_NAME).read_text(encoding="utf-8"))
    events = bc.source_events(events_doc)
    candidates = bc.build_candidates(events, events_doc)
    assert bc.leakage_audit(["2 ingredients remain"], events, candidates)[
        "violations"] == []
    assert bc.leakage_audit(["at 48.0 sec"], events, candidates)["violations"] \
        == ["TIMESTAMP_LEAKAGE"]
    assert bc.leakage_audit(["48.0"], events, candidates)["violations"] \
        == ["TIMESTAMP_LEAKAGE"]


def test_validator_rejects_mapping_or_downstream_leakage(tmp_path):
    runs = _prepared(tmp_path)
    runner.run(runs, _factory([], runs))
    parser_mod.parse(runs)
    clean = validator.checks(runs, SUBMISSION)
    assert clean["status"] == "PASS"
    packet = runs / "bcand_v1_packet.md"
    packet.write_text(packet.read_text(encoding="utf-8")
                      + "candidate_to_time", encoding="utf-8")
    assert validator.checks(runs, SUBMISSION)["status"] == "FAIL"
    packet.write_text("SEMANTIC BOUNDARY CANDIDATE REVIEW\n", encoding="utf-8")
    (runs / "bcand_v1_overview.json").write_text("{}", encoding="utf-8")
    assert validator.checks(runs, SUBMISSION)["status"] == "FAIL"


def test_validator_rejects_recorded_runtime_drift(tmp_path):
    runs = _prepared(tmp_path)
    runner.run(runs, _factory([], runs))
    parser_mod.parse(runs)
    record_path = runs / "bcand_v1_record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["requested_runtime"]["revision"] = "wrong-revision"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    report = validator.checks(runs, SUBMISSION)
    assert report["status"] == "FAIL"
    assert report["checks"]["runtime_contract_exact"] is False
