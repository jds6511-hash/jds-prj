"""최종 상태 CLOSED — 제출 arm·범위·한계를 문서와 코드가 같이 말하는지 본다.

닫힌 상태는 흔들리면 안 된다. manifest·tag·코드 기본값과 문서가 어긋나면 실패한다.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from v2_1_prompt import PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/finalization/V2_1_FINAL_STATUS_2026-09-07.md"
MANIFEST = ROOT / "runs/vad0_paired/submission_manifest_vad0.json"
CURRENT_SHA = ("4e10aaaba1d8a6e510c4749efc4a6e1bf"
               "5a5dbb5dba963403a84379bcd92ff90")
ROLLBACK_SHA = ("f874f643112704120cd3b043c3667b71"
                "ffd4f25105ca1fccf345b936d4e4a91d")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


shadow = _load(ROOT / "scripts/stt_vad0_shadow.py", "shadow_final_status_test")


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_the_adoption_is_closed():
    assert "STT_VAD0 SUBMISSION-PROFILE ADOPTION   CLOSED" in _doc()


def test_the_locked_block_names_the_arm_and_policy():
    text = _doc()
    for line in ("SUBMISSION_READY               YES",
                 "SUBMISSION ARM                 R1-VAD0",
                 "PROMPT CONTRACT                episode_content_v3_summary_only",
                 "STT EVIDENCE POLICY            STT_VAD0",
                 "presentation                   40 / 41 eligible",
                 "parse-contract failure         1 / 41",
                 "repository default             episode_content_v2",
                 "VAD0 default                   OFF",
                 "official test                  UNOPENED",
                 "M9                             HOLD"):
        assert line in text


def test_both_artifacts_are_named_by_hash():
    text = _doc()
    assert CURRENT_SHA in text and ROLLBACK_SHA in text
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["artifact"]["hwpx_sha256"] == CURRENT_SHA
    assert manifest["supersedes"]["hwpx_sha256"] == ROLLBACK_SHA


def test_the_document_agrees_with_the_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["submission_arm"] == "R1-VAD0"
    assert manifest["stt_evidence_policy"] == "STT_VAD0"
    assert manifest["presentation_eligible"] == 40
    assert manifest["parse_contract_failure"] == 1
    assert manifest["regenerated_by_rerun"] is False


def test_the_tag_exists_and_points_at_the_promotion_commit():
    """제출 상태가 주소를 가져야 rollback도 성립한다."""
    tags = subprocess.run(["git", "-C", str(ROOT), "tag"],
                          capture_output=True, text=True, check=True).stdout
    assert "submission-vad0-2026-09-07" in tags
    assert "submission-ready-2026-09-03" in tags        # rollback point 보존
    assert "submission-vad0-2026-09-07" in _doc()


def test_the_defaults_stay_off():
    assert PROMPT_VERSION == "episode_content_v2"
    assert shadow.SHADOW_VAD0_DEFAULT is False
    text = _doc()
    assert "production-wide adoption               NO" in text
    assert "SHADOW_VAD0_DEFAULT                    False" in text
    assert "threshold tuning                       NO" in text


def test_the_limits_are_recorded_with_the_claim():
    text = _doc()
    assert ("A deterministic abstention layer reduced the use of "
            "low-speech-confidence STT as claim evidence") in text
    assert "21 / 41 episode에서 ASR 근거가 전량 빠졌다" in text
    assert "zero-overlap은 실제 무발화 GT가 아니다" in text
    assert "parse 2 -> 1 변화를 일반화하지 않는다" in text


def test_forbidden_claims_stay_in_the_prohibition_section():
    text = _doc()
    head, marker, tail = text.partition("주장하지 않는 것")
    assert marker
    for phrase in ("VAD0가 Whisper hallucination을 검출했다",
                   "210건을 제거했다", "semantic accuracy가 향상됐다"):
        assert phrase not in head and phrase in tail
