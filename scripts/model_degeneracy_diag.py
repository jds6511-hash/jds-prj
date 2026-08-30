"""경계 열거 degeneracy 모델 대조 진단. **NON-ADOPTIVE diagnostic이다.**

사전등록: `docs/finalization/MODEL_DEGENERACY_DIAG_PREREG_2026-08-29.md`

```
BCS v0 core / HWPX path   FROZEN — 이 스크립트는 그것들을 바꾸지 않는다
```

geoje chunk3(110~169) · chunk5(220~279) × full / caption-only.
**Qwen 두 조건은 저장된 raw를 재사용**하고 비교 모델만 4회 호출한다.

공정성: task semantics 동일 · serialization은 각 모델의 native chat template.
파서 실패를 모델 실패와 분리한다(`PARSE_CONTRACT_FAILURE`).

사용:
    python scripts/model_degeneracy_diag.py --config config_server.yaml \
        --model LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct --commit <sha>
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
import m8_hier as H                                                 # noqa: E402

CHUNKS = {"chunk3": (110, 169), "chunk5": (220, 279)}


def compat_shims() -> list:
    """**순수 kwarg 별칭이다. 계산을 바꾸지 않는다.**

    transformers 5.x는 `create_causal_mask`의 인자를 `inputs_embeds`로 개명했고
    EXAONE-3.5의 vendored `modeling_exaone.py`는 옛 이름 `input_embeds`로 부른다
    (transformers 5.14.1 · 네이티브 지원은 exaone4/4.5뿐).

    HF 캐시의 파일을 고치면 git 밖에서 실행본이 달라진다(2026-08-17 사고 3건).
    대신 여기서 별칭만 붙인다. **모델을 로드하기 전에 불러야 한다** — vendored
    모듈이 import 시점에 함수를 이름으로 가져가기 때문이다.
    """
    import inspect
    import transformers.masking_utils as mu
    orig = mu.create_causal_mask
    if "input_embeds" in inspect.signature(orig).parameters:
        return []

    def shim(*args, **kw):
        if "input_embeds" in kw and "inputs_embeds" not in kw:
            kw["inputs_embeds"] = kw.pop("input_embeds")
        return orig(*args, **kw)

    shim.__wrapped__ = orig
    mu.create_causal_mask = shim
    return ["create_causal_mask: input_embeds -> inputs_embeds (별칭만)"]


QWEN_FULL = ROOT / "runs/m8_hier/m8_hier_prototype_geoje/wonyi_geoje.json"
QWEN_CAP = ROOT / "runs/m8_hier/m8_hier_boundary_ablation/wonyi_geoje.json"
OUT = ROOT / "runs/model_diag/geoje_boundary_degeneracy.json"


# ── 지표 — 사전등록 §4 정의 그대로 ──────────────────────────────────────
def longest_step_run(b: list, step: int) -> int:
    """간격이 `step`으로 일정한 최장 부분열의 **원소 수**."""
    b, best, run = sorted(set(b)), 0, 1
    for i in range(1, len(b)):
        run = run + 1 if b[i] - b[i - 1] == step else 1
        best = max(best, run)
    return best if len(b) > 1 else len(b)


def longest_arithmetic_run(b: list, min_step: int = 2) -> tuple:
    best, step_of = 1, 0
    for s in set(b[i + 1] - b[i] for i in range(len(b) - 1)) if len(b) > 1 else []:
        if s >= min_step:
            n = longest_step_run(b, s)
            if n > best:
                best, step_of = n, s
    return best, step_of


def parse_status(raw: str, got: list, has_list: bool) -> str:
    if not has_list:
        return "PARSE_CONTRACT_FAILURE"
    return "EMPTY_LIST" if not got else "PARSE_OK"


def _has_list(raw: str) -> bool:
    """파서가 목록 자체를 찾았는가 — 표기 실패와 빈 목록을 가른다."""
    d = H._obj(raw)
    if isinstance(d, dict) and isinstance(d.get("atomic_start_segments"), list):
        return True
    return bool(re.search(r"\[[^\[\]]*\]", raw or "", re.S))


def measure(raw: str, lo: int, hi: int, prompt: str, tok=None) -> dict:
    parsed = H.parse_boundaries(raw)
    got = [b for b in parsed if lo <= b <= hi]
    arun, astep = longest_arithmetic_run(got)
    m = {"prompt_chars": len(prompt),
         "output_chars": len(raw or ""),
         "boundary_count": len(got),
         "out_of_range": sorted(set(parsed) - set(got)),
         "consecutive_run_max": longest_step_run(got, 1),
         "arithmetic_run_max": arun, "arithmetic_run_step": astep,
         "parse_status": parse_status(raw, got, _has_list(raw)),
         "boundaries": got, "steps": [got[i + 1] - got[i]
                                      for i in range(len(got) - 1)]}
    if tok is not None:
        text = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                       tokenize=False, add_generation_prompt=True)
        m["input_tokens"] = len(tok(text).input_ids)
        m["output_tokens"] = len(tok(raw or "", add_special_tokens=False).input_ids)
    return m


def overlap(a: list, b: list) -> dict:
    A, B = set(a), set(b)
    u = len(A | B)
    return {"shared": len(A & B), "a_only": len(A - B), "b_only": len(B - A),
            "jaccard": round(len(A & B) / u, 4) if u else None}


# ── Qwen 저장분 — 재실행하지 않는다 ─────────────────────────────────────
def qwen_raw() -> dict:
    """저장된 산출물에서 chunk3·chunk5의 원본 출력을 꺼낸다."""
    full = json.loads(QWEN_FULL.read_text(encoding="utf-8"))
    cap = json.loads(QWEN_CAP.read_text(encoding="utf-8"))
    fr = full["raw"]["atomic_boundaries"]          # 청크 순서 = 생성 순서
    order = ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5", "chunk6"]
    if len(fr) != len(order):
        raise SystemExit(f"full raw 청크 수 {len(fr)}")
    out = {"full": {}, "caption_only": {}}
    for name, r in zip(order, fr):
        if name in CHUNKS:
            out["full"][name] = r
    by_lo = {r["lo"]: r["raw"] for r in cap["raw"]}
    for name, (lo, _) in CHUNKS.items():
        if lo not in by_lo:
            raise SystemExit(f"caption-only raw에 lo={lo} 없음")
        out["caption_only"][name] = by_lo[lo]
    return out


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--video-id", default="wonyi_geoje")
    ap.add_argument("--model", required=True)
    ap.add_argument("--commit", default=None)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))

    segs = common.load_segments(
        Path(common.work_dir(cfg, a.video_id)) / "segments.json",
        require=["subtitle", "caption"], seg_len=cfg["seg_len_sec"])["segments"]
    by_idx = {s["idx"]: s for s in segs}
    prompts = {}
    for name, (lo, hi) in CHUNKS.items():
        ch = [by_idx[i] for i in range(lo, hi + 1)]
        prompts[name] = {
            "full": H.build_atomic_boundary_prompt(ch),
            "caption_only": H.build_atomic_boundary_prompt(ch, caption_only=True)}

    shims = compat_shims()          # **모델 로드 전에** 붙인다
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    mx = cfg.get("report_max_new_tokens", 2048)

    def load(name):
        tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
        mdl = AutoModelForCausalLM.from_pretrained(
            name, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
        return tok, mdl

    def gen(tok, mdl, prompt):
        text = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                       tokenize=False, add_generation_prompt=True)
        inputs = tok([text], return_tensors="pt").to(mdl.device)
        with torch.inference_mode():
            o = mdl.generate(**inputs, max_new_tokens=mx, do_sample=False)
        return tok.decode(o[0][inputs.input_ids.shape[1]:],
                          skip_special_tokens=True).strip()

    res = {"video_id": a.video_id, "commit": a.commit,
           "prereg": "docs/finalization/"
                     "MODEL_DEGENERACY_DIAG_PREREG_2026-08-29.md",
           "chunks": {k: list(v) for k, v in CHUNKS.items()},
           "max_new_tokens": mx, "do_sample": False, "arms": {}, "raw": {}}
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def flush():
        common.atomic_write_json(out_path, res)

    # ── 비교 모델 — **호출 직후 raw 먼저 저장** ─────────────────────────
    tok_b, mdl_b = load(a.model)
    res["comparison_model"] = {
        "requested": a.model,
        "effective_model_id": getattr(mdl_b.config, "_name_or_path", None),
        "effective_revision": getattr(mdl_b.config, "_commit_hash", None),
        "dtype": str(mdl_b.dtype), "tokenizer": type(tok_b).__name__,
        "chat_template": bool(tok_b.chat_template),
        "compat_shims": shims}
    flush()
    for cond in ("full", "caption_only"):
        for name, (lo, hi) in CHUNKS.items():
            p = prompts[name][cond]
            raw = gen(tok_b, mdl_b, p)
            res["raw"][f"comparison/{cond}/{name}"] = raw
            flush()
            res["arms"][f"comparison/{cond}/{name}"] = measure(raw, lo, hi, p,
                                                               tok_b)
            flush()
    del mdl_b
    torch.cuda.empty_cache()

    # ── 현재 모델 — 저장된 raw 재사용. 토크나이저만 올린다 ──────────────
    qr = qwen_raw()
    tok_a = AutoTokenizer.from_pretrained(cfg["report_model"])
    res["current_model"] = {"model": cfg["report_model"],
                            "tokenizer": type(tok_a).__name__,
                            "source": "저장된 raw 재사용 — 재실행하지 않았다",
                            "full_from": str(QWEN_FULL).replace("\\", "/"),
                            "caption_only_from": str(QWEN_CAP).replace("\\", "/")}
    for cond in ("full", "caption_only"):
        for name, (lo, hi) in CHUNKS.items():
            raw = qr[cond][name]
            res["raw"][f"current/{cond}/{name}"] = raw
            res["arms"][f"current/{cond}/{name}"] = measure(
                raw, lo, hi, prompts[name][cond], tok_a)
    flush()

    # ── 위치 안정성 ─────────────────────────────────────────────────────
    B = lambda k: res["arms"][k]["boundaries"]                       # noqa: E731
    res["stability"] = {}
    for m in ("current", "comparison"):
        for name in CHUNKS:
            res["stability"][f"{m}/{name}/full_vs_caption"] = overlap(
                B(f"{m}/full/{name}"), B(f"{m}/caption_only/{name}"))
    for cond in ("full", "caption_only"):
        for name in CHUNKS:
            res["stability"][f"cross_model/{cond}/{name}"] = overlap(
                B(f"current/{cond}/{name}"), B(f"comparison/{cond}/{name}"))
    flush()

    print(f"산출물: {out_path}")
    hdr = f"{'arm':<34}{'chars':>7}{'in_tok':>8}{'out_tok':>8}{'bnd':>5}" \
          f"{'run1':>6}{'arith':>7}  parse"
    print(hdr)
    for k in sorted(res["arms"]):
        m = res["arms"][k]
        print(f"{k:<34}{m['prompt_chars']:>7}{m.get('input_tokens', 0):>8}"
              f"{m.get('output_tokens', 0):>8}{m['boundary_count']:>5}"
              f"{m['consecutive_run_max']:>6}"
              f"{m['arithmetic_run_max']}/{m['arithmetic_run_step']:<5}"
              f"  {m['parse_status']}")
    print("\n위치 안정성")
    for k, v in res["stability"].items():
        print(f"  {k:<38} shared {v['shared']:>3}  jaccard {v['jaccard']}")
    print("\nNON-ADOPTIVE diagnostic — BCS·모델·프롬프트를 바꾸지 않는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
