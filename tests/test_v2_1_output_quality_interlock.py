"""quality FAIL이 표현에서만 빠지고 정본·원문은 그대로인지 (2026-09-08).

```
FAIL     presentation eligibility 제외 + 사유 기록
SUSPECT  통과 (diagnostic이 자동 삭제가 되면 계약이 모순된다)
canonical · raw model output · sanitation core   무변경
```
"""
import importlib.util
import json
import sys
from pathlib import Path

from v2_1_output_quality import (FAIL, PASS, SUSPECT, QUALITY_POLICY_VERSION,
                                 REASON_BROKEN_MIXED_SCRIPT,
                                 REASON_LANGUAGE_DRIFT, evaluate_summary)
from v2_1_presentation_input import (PresentationEpisode, exclusion_reasons,
                                     summary_eligible_for_presentation)
from v2_1_prompt import PROMPT_VERSION
from v2_1_sanitation import STATUSES

ROOT = Path(__file__).resolve().parents[1]
DRIFT = ("두 사람이 빵을 만드는 모습을 보여주고, 마지막으로 베이킹용품"
         "尤其是关于蛋糕，是否有售？价格在这里，请看样品。")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _episode(summary, *, episode_id="EP01", content_status="VALID_PARSE",
             grounding="NOT_APPLICABLE"):
    return PresentationEpisode(
        episode_id=episode_id, start_seg=0, end_seg=3, start_sec=0.0,
        end_sec=60.0, source="stt", content_status=content_status,
        summary=summary, dialogue_note=None, grounding_status=grounding,
        anchor_cites=(), provenance=("m3_generate",))


# ── interlock ────────────────────────────────────────────────────────────
def test_a_language_drift_summary_is_not_eligible():
    assert not summary_eligible_for_presentation(_episode(DRIFT))


def test_a_normal_korean_summary_stays_eligible():
    assert summary_eligible_for_presentation(
        _episode("여성이 시장에서 재료를 고른다."))


def test_a_suspect_summary_stays_eligible():
    """diagnostic이 자동 제외가 되면 Q2 · Q3 계약과 모순된다."""
    episode = _episode("주인공이 카레우don과 밀가루를 처리한다.")
    assert evaluate_summary(episode.summary).status == SUSPECT
    assert summary_eligible_for_presentation(episode)


def test_the_interlock_is_fail_only_not_pass_only():
    source = (ROOT / "src/v2_1_presentation_input.py").read_text(encoding="utf-8")
    assert "!= FAIL" in source or "not blocks_presentation" in source
    assert "== PASS" not in source


# ── 사유 ─────────────────────────────────────────────────────────────────
def test_the_reason_is_a_deterministic_code_not_prose():
    assert exclusion_reasons(_episode(DRIFT)) == (REASON_LANGUAGE_DRIFT,)
    assert exclusion_reasons(
        _episode(None, content_status="PARSE_CONTRACT_FAILURE")) == (
        "PARSE_CONTRACT_FAILURE",)
    assert exclusion_reasons(
        _episode("여성이 재료를 고른다.", grounding="FAIL_UNSUPPORTED")) == (
        "GROUNDING_FAIL_UNSUPPORTED",)
    assert exclusion_reasons(_episode("여성이 재료를 고른다.")) == ()


def test_a_suspect_summary_has_no_exclusion_reason():
    assert exclusion_reasons(
        _episode("주인공이 카레우don을 처리한다.")) == ()


# ── 정본 · 원문 무변경 ───────────────────────────────────────────────────
def test_quality_failure_does_not_change_the_canonical_episode():
    episode = _episode(DRIFT)
    before = json.dumps(episode.__getstate__() if hasattr(episode, "__getstate__")
                        else {"summary": episode.summary}, ensure_ascii=False)
    summary_eligible_for_presentation(episode)
    exclusion_reasons(episode)
    after = json.dumps(episode.__getstate__() if hasattr(episode, "__getstate__")
                       else {"summary": episode.summary}, ensure_ascii=False)
    assert before == after
    assert episode.summary == DRIFT          # raw model output 보존


def test_the_quality_layer_never_calls_a_model():
    for name in ("src/v2_1_output_quality.py", "src/v2_1_presentation_input.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        for forbidden in ("v2_1_llm_adapter", "generate(", "AutoModel",
                          "retry", "translate"):
            assert forbidden not in source


def test_the_quality_layer_does_not_rewrite_text():
    source = (ROOT / "src/v2_1_output_quality.py").read_text(encoding="utf-8")
    for forbidden in (".replace(", ".sub(", "strip() ="):
        assert forbidden not in source


# ── 채택 범위 밖은 그대로 ────────────────────────────────────────────────
def test_the_default_contract_and_vad0_default_are_unchanged():
    assert PROMPT_VERSION == "episode_content_v2"
    shadow = _load(ROOT / "scripts/stt_vad0_shadow.py", "shadow_quality_test")
    assert shadow.SHADOW_VAD0_DEFAULT is False


def test_the_sanitation_core_semantics_are_unchanged():
    assert STATUSES == ("VALID", "SUSPECT", "REJECTED", "EMPTY", "PARSE_FAILED")
    source = (ROOT / "src/v2_1_sanitation.py").read_text(encoding="utf-8")
    assert "vad" not in source.lower()
    assert "output_quality" not in source


def test_the_policy_version_is_recorded():
    assert QUALITY_POLICY_VERSION == "output_quality_v1"
    assert evaluate_summary("여성이 재료를 고른다.").diagnostics["policy"] == (
        QUALITY_POLICY_VERSION)
    assert evaluate_summary("여성이 재료를 고른다.").status == PASS
    assert FAIL == "FAIL"
