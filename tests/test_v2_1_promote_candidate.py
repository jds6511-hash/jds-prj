"""quality candidate 승격 — 새 submission arm manifest (2026-09-08 · TRACK A).

```
OLD  4e10aaab…  submission-vad0-2026-09-07   rollback 유지
NEW  57320758…  quality candidate            새 submission arm
```

수치를 손으로 적지 않는다. 두 artifact(candidate manifest · 직전 submission
manifest)에서 파생하고, 어긋나면 거부한다.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/v2_1_promote_candidate.py"
CANDIDATE = ROOT / "runs/quality_candidate/candidate_manifest.json"
PREVIOUS = ROOT / "runs/vad0_paired/submission_manifest_vad0.json"
PROMOTED = ROOT / "runs/quality_candidate/submission_manifest_quality.json"

OLD_HWPX = "4e10aaaba1d8a6e510c4749efc4a6e1bf5a5dbb5dba963403a84379bcd92ff90"
OLDEST_HWPX = "f874f643112704120cd3b043c3667b71ffd4f25105ca1fccf345b936d4e4a91d"


def _load():
    spec = importlib.util.spec_from_file_location("promote_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["promote_candidate"] = module
    spec.loader.exec_module(module)
    return module


promote = _load()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ── 합성 규칙 ────────────────────────────────────────────────────────────
def test_the_arm_records_all_three_policy_layers():
    manifest = promote.compose(_json(CANDIDATE), _json(PREVIOUS))
    assert manifest["submission_contract"] == "episode_content_v3_summary_only"
    assert manifest["stt_evidence_policy"] == "STT_VAD0"
    assert manifest["output_quality_policy"] == "output_quality_v1"
    assert manifest["presentation_group_window_sec"] == 300


def test_the_numbers_come_from_the_candidate_artifact():
    candidate = _json(CANDIDATE)
    manifest = promote.compose(candidate, _json(PREVIOUS))
    assert manifest["artifact"]["hwpx_sha256"] == candidate["artifact"]["hwpx_sha256"]
    assert manifest["canonical_partition_hash"] == candidate[
        "canonical_partition_hash"]
    assert manifest["presentation_eligible"] == candidate["presentation_eligible"]
    assert manifest["llm_rerun"] is False


def test_the_excluded_episodes_are_listed_with_their_codes():
    manifest = promote.compose(_json(CANDIDATE), _json(PREVIOUS))
    assert manifest["excluded_summary_episodes"] == [
        {"episode_id": "EP13", "reasons": ["OUTPUT_LANGUAGE_DRIFT"]},
        {"episode_id": "EP17", "reasons": ["PARSE_CONTRACT_FAILURE"]},
    ]


def test_the_upstream_provenance_is_carried_not_retyped():
    previous = _json(PREVIOUS)
    manifest = promote.compose(_json(CANDIDATE), previous)
    assert manifest["fingerprint"] == previous["fingerprint"]
    assert manifest["model_provenance"] == previous["model_provenance"]
    assert manifest["input"] == previous["input"]
    assert manifest["vad"] == previous["vad"]
    assert manifest["measurements_sha256"] == previous["measurements_sha256"]
    assert manifest["stt_evidence"] == previous["stt_evidence"]


def test_the_previous_submission_is_named_as_rollback():
    manifest = promote.compose(_json(CANDIDATE), _json(PREVIOUS))
    assert manifest["supersedes"]["hwpx_sha256"] == OLD_HWPX
    assert manifest["supersedes"]["submission_arm"] == "R1-VAD0"
    assert "rollback" in manifest["supersedes"]["role"]


def test_a_candidate_from_another_source_run_is_refused():
    """제출본은 그 paired arm의 정본에서 나온 것이어야 한다."""
    candidate = _json(CANDIDATE)
    candidate["source_run_fingerprint"] = dict(
        candidate["source_run_fingerprint"], code_revision="deadbeef")
    with pytest.raises(promote.PromotionError):
        promote.compose(candidate, _json(PREVIOUS))


def test_a_candidate_that_claims_an_llm_rerun_is_refused():
    candidate = dict(_json(CANDIDATE), llm_rerun=True)
    with pytest.raises(promote.PromotionError):
        promote.compose(candidate, _json(PREVIOUS))


def test_the_script_never_generates():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("v2_1_llm_adapter", "AutoModel", "torch", "build_episode_prompt"):
        assert forbidden not in source


# ── rollback 보존 ────────────────────────────────────────────────────────
def test_the_rollback_check_reads_the_real_files():
    verdict = promote.rollback_intact()
    assert verdict["submission_vad0_2026_09_07"] == OLD_HWPX
    assert verdict["submission_ready_2026_09_03"] == OLDEST_HWPX
    assert verdict["intact"] is True


def test_the_rollback_check_fails_on_a_changed_hash(tmp_path, monkeypatch):
    changed = tmp_path / "report.hwpx"
    changed.write_bytes(b"not the submitted document")
    monkeypatch.setitem(promote.ROLLBACK, "submission_vad0_2026_09_07",
                        (changed, OLD_HWPX))
    verdict = promote.rollback_intact()
    assert verdict["intact"] is False


# ── 산출된 manifest (승격 실행 후) ───────────────────────────────────────
def test_the_promoted_manifest_exists_and_passes_the_live_checks():
    manifest = _json(PROMOTED)
    assert manifest["submission_arm"] == "R1-VAD0-QUALITY"
    assert manifest["structural_validator"] == "PASS"
    assert manifest["hangul"]["hancom_open"] is True
    assert manifest["hangul"]["pdf_export"] is True
    assert manifest["artifact"]["hwpx_sha256"] == _json(CANDIDATE)[
        "artifact"]["hwpx_sha256"]
    assert manifest["rollback_intact"]["intact"] is True


def test_the_promoted_manifest_keeps_the_repository_defaults():
    manifest = _json(PROMOTED)
    assert manifest["default_contract_unchanged"] is True
    assert manifest["vad0_default_off"] is True
    from v2_1_prompt import PROMPT_VERSION
    assert PROMPT_VERSION == "episode_content_v2"


def test_the_promoted_manifest_states_what_is_not_claimed():
    manifest = _json(PROMOTED)
    blob = " ".join(manifest["not_claimed"]).lower()
    assert "hallucination" in blob
    assert "semantic" in blob
    for forbidden in ("semantic accuracy improved",
                      "210 hallucinations removed"):
        assert forbidden not in json.dumps(manifest, ensure_ascii=False)
