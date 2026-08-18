"""실효 양자화 provenance + 실험별 validator hook. **PRIMARY의 arm 정체성을 증명한다.**

`prec3_0818a` CANARY에서 launcher 공통 6항목이 전부 PASS인데 **연구적으로는 FAIL**인
상태가 나왔다 — 세 arm이 실제로 요청한 정밀도로 돌았는지 산출물이 증언하지 못했다.
`Δ_quant`·`Δ_deploy`가 무엇 사이의 차이인지 알 수 없으면 주 판정이 무의미하다.

**VRAM은 source of truth가 아니다.** q4/bf16 정체성 판정은 provenance로 한다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "hooks"))
import m3_generate                                          # noqa: E402
import dev_precision_3arm_hook as H                         # noqa: E402


class _Q:
    bnb_4bit_quant_type = "nf4"
    bnb_4bit_compute_dtype = "torch.bfloat16"
    bnb_4bit_use_double_quant = True


class _Conf:
    _name_or_path = "Qwen/Qwen2.5-VL-3B-Instruct"
    _commit_hash = "abc"
    _attn_implementation = "sdpa"

    def __init__(self, quant):
        if quant:
            self.quantization_config = _Q()


class _Model:
    dtype = "torch.bfloat16"

    def __init__(self, quant):
        self.config = _Conf(quant)


# ---- provenance: 요청과 실효를 **별도 축**으로 -----------------------------

def test_requested_and_effective_are_separate_axes():
    """4bit 모델도 계산 dtype은 bf16이다 — dtype 하나로 q4를 판정하면 안 된다."""
    p = m3_generate.caption_provenance({"vlm_4bit": True}, _Model(True), "x", "t")
    assert p["requested_quantized"] is True
    assert p["effective_quantized"] is True
    assert p["quantization_mismatch"] is False
    assert p["bnb_quant_type"] == "nf4"
    assert p["bnb_double_quant"] is True
    assert "bfloat16" in p["bnb_compute_dtype"]


def test_mismatch_is_detected_when_flag_ignored():
    """`vlm_4bit`가 무시된 채 돌았던 전례 — 불일치 자체가 신호다."""
    p = m3_generate.caption_provenance({"vlm_4bit": True}, _Model(False), "x", "t")
    assert p["effective_quantized"] is False
    assert p["quantization_mismatch"] is True


def test_bf16_arm_reports_not_quantized():
    p = m3_generate.caption_provenance({"vlm_4bit": False}, _Model(False), "x", "t")
    assert p["requested_quantized"] is False and p["effective_quantized"] is False
    assert p["quantization_mismatch"] is False
    assert p["bnb_quant_type"] is None


def test_legacy_keys_are_preserved():
    """기존 소비자를 깨지 않는다."""
    p = m3_generate.caption_provenance({"vlm_4bit": True}, _Model(True), "x", "t")
    for k in ("entrypoint", "model_id", "dtype", "quantized", "attn_implementation",
              "prompt_sha256", "git_head", "config_vlm_4bit"):
        assert k in p, k


# ---- 실험별 validator hook -------------------------------------------------

def _arm(req, eff, mismatch=None, failures=0, n_captions=655, sanity=True):
    return {"n_captions": n_captions,
            "generation_failures": failures,
            "vision_sanity": {"ok": sanity},
            "provenance": {
                "requested_quantized": req, "effective_quantized": eff,
                "quantization_mismatch": (req != eff if mismatch is None else mismatch),
                "bnb_quant_type": "nf4" if eff else None,
                "bnb_compute_dtype": "torch.bfloat16" if eff else None,
                "bnb_double_quant": True if eff else None,
                "model_id": "m", "dtype": "torch.bfloat16",
                "attn_implementation": "sdpa"}}


def _rep(**over):
    arms = {"qwen3vl_4b_q4/P0": _arm(True, True),
            "qwen3vl_4b/P0": _arm(False, False),
            "qwen25_3b_4bit/P0": _arm(True, True)}
    arms.update(over)
    return {"queries": [{"query_id": f"q{i}", "video_id": "v"} for i in range(96)],
            "arms": arms, "expected_captions": 655}


def _run(tmp_path, rep, name="dev_precision_3arm_canary.json"):
    (tmp_path / name).write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_hook_passes_when_all_arms_match_declaration(tmp_path):
    ok, checks = H.check(_run(tmp_path, _rep()))
    assert ok, checks
    assert checks["quantization_as_declared"] is True


def test_hook_fails_when_q4_arm_loaded_unquantized(tmp_path):
    r = _rep(**{"qwen25_3b_4bit/P0": _arm(True, False)})
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["quantization_as_declared"] is False


def test_hook_fails_when_bf16_arm_loaded_quantized(tmp_path):
    r = _rep(**{"qwen3vl_4b/P0": _arm(False, True)})
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["quantization_as_declared"] is False


def test_hook_fails_on_mismatch_flag_even_if_axes_look_right(tmp_path):
    r = _rep(**{"qwen3vl_4b_q4/P0": _arm(True, True, mismatch=True)})
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["no_quantization_mismatch"] is False


def test_hook_fails_on_missing_provenance_key(tmp_path):
    r = _rep()
    del r["arms"]["qwen3vl_4b/P0"]["provenance"]["bnb_quant_type"]
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["provenance_keys_present"] is False


def test_hook_fails_on_generation_failure(tmp_path):
    """실패 건수가 있으면 그 arm은 invalid — PRIMARY를 산출하지 않는다."""
    r = _rep(**{"qwen3vl_4b_q4/P0": _arm(True, True, failures=3)})
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["no_generation_failures"] is False


def test_hook_fails_on_incomplete_captions(tmp_path):
    """caption 하나라도 누락되면 arm invalid. 성공 subset 비교도, RR=0 대체도 금지."""
    r = _rep(**{"qwen3vl_4b/P0": _arm(False, False, n_captions=654)})
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["captions_complete"] is False


def test_hook_fails_on_vision_sanity_collapse(tmp_path):
    r = _rep(**{"qwen3vl_4b/P0": _arm(False, False, sanity=False)})
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["vision_sanity_ok"] is False


def test_hook_fails_on_missing_arm(tmp_path):
    r = _rep()
    del r["arms"]["qwen25_3b_4bit/P0"]
    ok, checks = H.check(_run(tmp_path, r))
    assert not ok and checks["all_arms_present"] is False


def test_hook_skips_caption_completeness_on_canary(tmp_path):
    """CANARY는 `--limit`로 도므로 655 완결을 요구하지 않는다 — 대신 정체성만 본다."""
    r = _rep(**{"qwen3vl_4b/P0": _arm(False, False, n_captions=24)})
    r["limit"] = 8
    ok, checks = H.check(_run(tmp_path, r))
    assert ok, checks
    assert checks["captions_complete"] is True


def test_vram_is_diagnostic_not_a_gate(tmp_path):
    """정체성 판정은 provenance가 한다 — VRAM 이상값으로 FAIL을 만들지 않는다."""
    r = _rep()
    r["arms"]["qwen25_3b_4bit/P0"]["server_incremental_peak_vram_gb"] = -1.0
    ok, checks = H.check(_run(tmp_path, r))
    assert ok
    assert not any("vram" in k for k in checks)
