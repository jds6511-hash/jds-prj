"""dev 정밀도 3-arm — **실험별** validator hook.

`prec3_0818a` CANARY에서 launcher 공통 6항목이 전부 PASS인데 **연구적으로는 FAIL**인
상태가 나왔다: 세 arm이 실제로 요청한 정밀도로 돌았는지 산출물이 증언하지 못했다.
정밀도가 주 판정인 실험에서 그건 통과시킬 수 없다. 그 판정을 사람 눈에서
**hook으로 승격**한다.

**정체성의 source of truth는 provenance다. VRAM이 아니다.**
`server_incremental_peak_vram_gb`는 진단값이고 여기서 게이트로 쓰지 않는다 —
arm 간 측정 경계가 섞이면 이상값이 나오는데, 그것으로 실험을 죽이면 안 된다.

사전등록: `dev_precision_3arm_사전등록_2026-08-18.md` (+ `보충_CI해석`).
"""
import json
from pathlib import Path

# 사전등록 §1의 arm 선언 — 요청 정밀도까지 여기서 고정한다
DECLARED = {"qwen3vl_4b_q4/P0": True,      # requested_quantized
            "qwen3vl_4b/P0": False,
            "qwen25_3b_4bit/P0": True}
REQUIRED_PROV = ("requested_quantized", "effective_quantized",
                 "quantization_mismatch", "bnb_quant_type", "bnb_compute_dtype",
                 "bnb_double_quant", "model_id", "dtype", "attn_implementation")


def _report(run_dir: Path) -> dict:
    for p in sorted(Path(run_dir).glob("dev_precision_3arm_*.json")):
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def check(run_dir) -> tuple:
    """(ok, checks). launcher `validate`의 실험별 훅으로 붙는다."""
    rep = _report(run_dir)
    arms = rep.get("arms") or {}
    is_canary = bool(rep.get("limit"))
    expected_caps = rep.get("expected_captions")

    present = [k for k in DECLARED if k in arms]
    checks = {"all_arms_present": len(present) == len(DECLARED)}

    def _prov(k):
        return (arms.get(k) or {}).get("provenance") or {}

    checks["provenance_keys_present"] = all(
        all(f in _prov(k) for f in REQUIRED_PROV) for k in present) and bool(present)
    # 선언한 요청 정밀도 == 실제 요청값 == 실효 양자화
    checks["quantization_as_declared"] = all(
        _prov(k).get("requested_quantized") is req
        and _prov(k).get("effective_quantized") is req
        for k, req in DECLARED.items() if k in arms) and bool(present)
    checks["no_quantization_mismatch"] = all(
        _prov(k).get("quantization_mismatch") is False for k in present)
    checks["no_generation_failures"] = all(
        not (arms[k].get("generation_failures") or 0) for k in present)
    checks["vision_sanity_ok"] = all(
        (arms[k].get("vision_sanity") or {}).get("ok") is True for k in present)
    # **caption 완결성.** 하나라도 누락되면 그 arm은 invalid다 — 성공 subset 비교도,
    # 누락을 RR=0으로 바꾸는 것도 금지다. CANARY는 `--limit`로 도므로 면제한다.
    checks["captions_complete"] = (
        True if is_canary or not expected_caps
        else all(arms[k].get("n_captions") == expected_caps for k in present))
    return all(checks.values()), checks
