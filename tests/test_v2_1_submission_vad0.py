"""제출 profile에 STT_VAD0을 채택한 상태를 잠근다.

```
제출 arm        R1-VAD0 / episode_content_v3_summary_only + explicit VAD0
rollback        f874f643… (기존 제출본) 은 그대로 보존한다
repository      default 계약 v2 · VAD0 default off — 둘 다 바꾸지 않았다
의미            비퇴행 통과다. "VAD가 parse를 개선했다"가 아니다
```

수치는 손으로 적지 않는다. paired_metrics·Phase A manifest에서 읽었는지 대조한다.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from v2_1_prompt import CONTRACT, PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/finalization/V2_1_SUBMISSION_VAD0_PROMOTION_2026-09-07.md"
OLD_MANIFEST = ROOT / "runs/v3_paired/submission_manifest.json"
NEW_MANIFEST = ROOT / "runs/vad0_paired/submission_manifest_vad0.json"
PAIRED = ROOT / "runs/vad0_paired/paired_metrics.json"
VAD_MANIFEST = ROOT / "runs/stt_sanitation_v1/full_xekZO4n4QuE/manifest.json"
ROLLBACK_HWPX_SHA = ("f874f643112704120cd3b043c3667b71"
                     "ffd4f25105ca1fccf345b936d4e4a91d")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


submission = _load(ROOT / "scripts/v2_1_submission_manifest.py",
                   "submission_manifest_vad0_test")
shadow = _load(ROOT / "scripts/stt_vad0_shadow.py", "shadow_vad0_default_test")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


# ── 순수 helper: 수치가 artifact에서 오는지 ──────────────────────────────
def test_policy_label_comes_from_the_run_manifest():
    assert submission.policy_label({}) == "RAW_STT_ALL_VALID"
    assert submission.policy_label({"shadow_vad0": False}) == "RAW_STT_ALL_VALID"
    assert submission.policy_label(
        {"shadow_vad0": True, "rule": "r", "measurements_sha256": "a" * 64}
    ) == "STT_VAD0"


def test_a_vad0_run_without_measurement_provenance_is_refused():
    """어느 측정으로 abstain했는지 모르면 제출 provenance가 성립하지 않는다."""
    with pytest.raises(submission.SubmissionCheckError):
        submission.policy_label({"shadow_vad0": True, "rule": "r"})


def test_vad_provenance_is_copied_from_phase_a_not_retyped():
    provenance = submission.vad_provenance(_json(VAD_MANIFEST))
    assert provenance["vad_model"] == "silero_vad_v6.onnx"
    assert provenance["vad_model_sha256"] == (
        "4cbf549b8326f60f80f2536d9eefeb450a9abe83"
        "365a098031c89719f1be17d2")
    assert provenance["faster_whisper_version"] == "1.2.1"
    params = provenance["vad_params_resolved"]
    assert params["threshold"] == 0.5
    assert params["neg_threshold"] == 0.35
    assert params["min_silence_duration_ms"] == 2000
    assert params["speech_pad_ms"] == 400
    # null이 아니라 실효값이어야 한다 — implicit default를 제출본에 남기지 않는다.
    assert params["max_speech_duration_s"] == "inf"


def test_evidence_totals_come_from_the_paired_metrics():
    totals = submission.evidence_totals(_json(PAIRED))
    assert totals["original_claim_evidence"] == 777
    assert totals["selected_claim_evidence"] == 567


def test_a_manifest_from_another_run_cannot_borrow_the_paired_numbers():
    """"재실행 없이 승격"의 근거가 이 검사다 — 지문이 다르면 거부한다."""
    paired = _json(PAIRED)
    fingerprint = paired["arms"]["s1"]["fingerprint"]
    submission.assert_promoted_from_paired(paired, fingerprint)   # 같으면 통과
    other = dict(fingerprint, code_revision="deadbeef")
    with pytest.raises(submission.SubmissionCheckError):
        submission.assert_promoted_from_paired(paired, other)


def test_evidence_selection_that_grew_is_refused():
    """abstention은 one-way다. 근거가 늘면 다른 사건이다."""
    grown = {"episodes": [{"eligible_s0": 1, "eligible_s1": 2}]}
    with pytest.raises(submission.SubmissionCheckError):
        submission.evidence_totals(grown)


# ── 채택된 제출 manifest ────────────────────────────────────────────────
def test_the_submission_arm_declares_the_evidence_policy():
    manifest = _json(NEW_MANIFEST)
    assert manifest["submission_arm"] == "R1-VAD0"
    assert manifest["submission_contract"] == "episode_content_v3_summary_only"
    assert manifest["stt_evidence_policy"] == "STT_VAD0"


def test_the_manifest_records_the_promoted_numbers():
    manifest = _json(NEW_MANIFEST)
    assert manifest["episodes"] == 41
    assert manifest["presentation_eligible"] == 40
    assert manifest["parse_contract_failure"] == 1
    assert manifest["stt_evidence"]["original_claim_evidence"] == 777
    assert manifest["stt_evidence"]["selected_claim_evidence"] == 567


def test_the_manifest_points_at_the_paired_result_and_commit():
    manifest = _json(NEW_MANIFEST)
    paired = manifest["paired_result"]
    assert paired["metrics"].endswith("paired_metrics.json")
    assert paired["commit"] == "958276b06bcbf3983f00b9132edffba4185a8dcd"
    assert paired["presentation_eligible"] == {"s0": 39, "s1": 40}
    assert paired["parse_contract_failure"] == {"s0": 2, "s1": 1}


def test_the_promoted_artifact_is_the_paired_s1_file():
    """모델을 다시 돌리지 않았다 — S1 run 안의 그 파일이어야 한다."""
    manifest = _json(NEW_MANIFEST)
    assert "s1_shadow" in manifest["artifact"]["hwpx"].replace("\\", "/")
    assert manifest["artifact"]["hwpx_sha256"] != ROLLBACK_HWPX_SHA
    assert manifest["regenerated_by_rerun"] is False
    assert manifest["hangul"]["hancom_open"] is True
    assert manifest["hangul"]["pdf_export"] is True


def test_the_rollback_artifact_is_named_and_preserved():
    manifest = _json(NEW_MANIFEST)
    rollback = manifest["supersedes"]
    assert rollback["hwpx_sha256"] == ROLLBACK_HWPX_SHA
    assert rollback["manifest"].replace("\\", "/").endswith(
        "runs/v3_paired/submission_manifest.json")
    # 기존 제출본 manifest를 덮어쓰지 않았다.
    assert _json(OLD_MANIFEST)["artifact"]["hwpx_sha256"] == ROLLBACK_HWPX_SHA
    assert _json(OLD_MANIFEST)["presentation_eligible"] == 39


# ── 채택 범위: 제출본만이다 ──────────────────────────────────────────────
def test_repository_defaults_were_not_promoted():
    manifest = _json(NEW_MANIFEST)
    assert manifest["default_contract_unchanged"] is True
    assert manifest["vad0_default_off"] is True
    assert PROMPT_VERSION == "episode_content_v2"
    assert CONTRACT["output"]["optional"] == ["dialogue_note", "stt_cites"]
    assert shadow.SHADOW_VAD0_DEFAULT is False


def test_the_accepted_sanitation_core_has_no_vad_dependency():
    """VAD0는 sanitation core 밖의 별도 layer다 — core를 건드리지 않았다."""
    source = (ROOT / "src/v2_1_sanitation.py").read_text(encoding="utf-8")
    assert "vad" not in source.lower()


def test_the_shadow_rule_input_is_only_the_overlap_ratio():
    source = (ROOT / "scripts/stt_vad0_shadow.py").read_text(encoding="utf-8")
    for forbidden in ("no_speech_prob", "avg_logprob", "temperature",
                      "nearest_speech_gap", "latin_present"):
        assert forbidden not in source


# ── 문구 ────────────────────────────────────────────────────────────────
def test_the_document_states_the_adoption_scope():
    text = _doc()
    assert "submission profile adoption       APPROVED" in text
    assert "repository default                OFF / unchanged" in text
    assert "production-wide adoption          NOT ADOPTED" in text
    assert "semantic correctness              UNVERIFIED" in text


def test_the_allowed_claim_is_the_only_claim():
    text = _doc()
    assert ("A deterministic abstention layer reduced the use of "
            "low-speech-confidence STT as claim evidence") in text


def test_forbidden_claims_appear_only_as_prohibitions():
    text = _doc()
    for phrase in ("210 hallucinations removed", "semantic accuracy improved",
                   "VAD0 detects hallucination"):
        assert phrase in text                      # 금지 목록에 적혀 있어야 한다
        head, _, tail = text.partition("주장하지 않는 것")
        assert phrase not in head and phrase in tail


def test_the_parse_change_is_framed_as_non_regression():
    text = _doc()
    assert "비퇴행" in text
    assert "2 -> 1 변화를 일반화하지 않는다" in text
