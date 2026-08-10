"""[생성 환경 격차 2단계 — 커널을 바꾸면 붙는가 (결과 전 커밋)]

**1단계에서 확정된 것.** 노트북과 서버의 **입력은 비트 단위로 동일하다** —
프레임 파일·토큰화·리사이즈 격자·픽셀 텐서 198장 전부 일치(`env_gap_stage1.json`).
torch·transformers·pillow·torchvision 버전이 다른데도 전처리 산출물은 같았다.
따라서 원인은 **수치 연산**이다.

**같은 환경 안에서는 결정적이라는 것도 확인됐다.** 서버에서 따로 두 번 생성한
캡션이 서로 98.0% 일치하고, 노트북과는 두 번 모두 정확히 25.6%였다. 실행 간
무작위성이 아니라 **환경에 고정된 계통 차이**다.

**이 스크립트가 묻는 것.** 그 계통 차이가 **attention 커널 선택** 때문인가.
그렇다면 서버에서 커널을 바꾸는 것만으로 노트북 출력에 붙어야 한다.

  조건 1  `sdpa`          — 현행 기본값(서버 생성분이 이걸로 만들어졌다)
  조건 2  `eager`         — 융합 커널 없이 순수 파이토치 경로
  조건 3  `sdpa` + math   — SDPA 백엔드를 math로 고정. flash/mem-efficient 커널을
                            끄면 리덕션 순서가 아키텍처 의존성을 덜 탄다

**기준선은 배포된 인덱스의 캡션이다** — `work/<video>/segments.json`에 들어 있는
노트북 생성분. 별도 재생성 없이 그대로 쓴다.

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-10).**
  - 어떤 조건이 노트북과의 완전일치율을 **기본값 대비 +20%p 이상** 끌어올리면
    → **원인 확정: attention 커널.** 그 설정으로 맞춰 재생성하면 환경 손실이 사라지고
    후보 모델의 +0.09가 실현된다.
  - 모든 조건이 기본값의 ±10%p 안에 머물면 → **커널이 아니다.** 남는 것은 GPU
    아키텍처(Ampere sm_86 vs Ada sm_89)와 라이브러리 버전이고, 아키텍처면 **못 고친다.**
  - 그 사이면 **부분 기여**로 보고하고 일치율 순서를 병기한다.
  - 결과를 보고 임계값·조건을 바꾸지 않는다.

**못 고친다는 결론도 쓸모가 있다.** 그때는 노트북 생성분이 높은 것이 재현 불가능한
1회성 산출물이라는 뜻이므로, 올바른 비교는 서버 대 서버가 되고 후보 채택
(+0.0913, `deploy_delta.py` ①)이 정당해진다. 다만 서버 두 실행이 서로 98% 일치한
사실은 "노트북이 운 좋은 뽑기"라는 해석에 불리하므로, 그 경우 **왜 서버가 계통적으로
낮은가**를 별도로 답해야 한다.

**한계.** 프레임 표본만 생성하므로 MRR은 재지 않는다. 이 프로브가 답하는 것은
"붙는가"뿐이고, 붙는 조건이 나오면 전량 재생성 후 MRR을 따로 재야 한다.

work/·results/ 불변, test 미접촉.
재현: python docs/probes/env_gap_kernel.py [--n 120]
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
N_FRAMES = 120
GATE_FIX, GATE_SAME = 0.20, 0.10
CONDS = [("sdpa", None), ("eager", None), ("sdpa", "math")]


def pick(cfg, n):
    """dev 앞쪽 세그먼트를 결정적으로 고른다 — 1단계와 같은 규칙."""
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    vids = sorted({q["video_id"] for q in qs if q["split"] == "dev"})
    per = max(1, n // len(vids))
    out = []
    for v in vids:
        wdir = Path(common.work_dir(cfg, v))
        segs = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
        segs = segs["segments"] if isinstance(segs, dict) else segs
        for s in segs[:per]:
            out.append({"video_id": v, "frame": wdir / s["rep_frame"],
                        "ref": s.get("caption", "")})
    return out


def run_condition(attn, backend, items, cfg):
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, BitsAndBytesConfig, \
        Qwen2_5_VLForConditionalGeneration

    kwargs = dict(device_map={"": 0}, attn_implementation=attn)
    if cfg.get("vlm_4bit"):
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    else:
        kwargs["dtype"] = torch.bfloat16
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        cfg["caption_model"], **kwargs).eval()
    proc = AutoProcessor.from_pretrained(
        cfg["caption_model"], min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])
    prompt = cfg["caption_prompt"]

    gen_kwargs = dict(max_new_tokens=cfg.get("vlm_max_new_tokens", 128), do_sample=False)
    if cfg.get("vlm_rep_penalty", 1.0) != 1.0:
        gen_kwargs["repetition_penalty"] = cfg["vlm_rep_penalty"]

    outs = []
    try:
        for i, it in enumerate(items):
            msgs = [{"role": "user", "content": [
                {"type": "image", "image": str(it["frame"])},
                {"type": "text", "text": prompt}]}]
            text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            imgs, vids_ = process_vision_info(msgs)
            inp = proc(text=[text], images=imgs, videos=vids_, padding=True,
                       return_tensors="pt").to(model.device)
            with torch.inference_mode():
                if backend == "math":
                    with torch.nn.attention.sdpa_kernel(
                            torch.nn.attention.SDPBackend.MATH):
                        gen = model.generate(**inp, **gen_kwargs)
                else:
                    gen = model.generate(**inp, **gen_kwargs)
            outs.append(proc.batch_decode(gen[:, inp.input_ids.shape[1]:],
                                          skip_special_tokens=True)[0].strip())
            if i % 40 == 0:
                print(f"    {i}/{len(items)}", flush=True)
    finally:
        del model
        torch.cuda.empty_cache()
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_FRAMES)
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    items = pick(cfg, a.n)
    print(f"프레임 {len(items)}장 · 기준선 = 배포 인덱스(노트북 생성분)", flush=True)

    rep = {"note": "생성 환경 격차 2단계 — 커널 요인. dev only, test 미접촉.",
           "prereg": {"fix_gate": f"기본값 대비 +{GATE_FIX:.0%}p 이상이면 커널이 원인",
                      "same_gate": f"모든 조건이 ±{GATE_SAME:.0%}p 안이면 커널 아님",
                      "baseline": "work/<video>/segments.json 의 노트북 생성 캡션",
                      "declared_before_run": True},
           "n_frames": len(items), "caption_model": cfg["caption_model"],
           "vlm_4bit": cfg.get("vlm_4bit"), "conditions": {}}

    ref = [it["ref"] for it in items]
    for attn, backend in CONDS:
        key = attn if backend is None else f"{attn}+{backend}"
        print(f"[{key}] 생성 시작", flush=True)
        try:
            outs = run_condition(attn, backend, items, cfg)
        except Exception as e:
            rep["conditions"][key] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[{key}] 실패 — {type(e).__name__}: {e}", flush=True)
            continue
        match = sum(1 for a_, b_ in zip(outs, ref) if a_ == b_)
        rep["conditions"][key] = {"exact_match": round(match / len(ref), 4),
                                  "n_match": match, "captions": outs}
        print(f"[{key}] 노트북과 완전일치 {match}/{len(ref)} = {match/len(ref):.1%}",
              flush=True)

    ok = {k: v["exact_match"] for k, v in rep["conditions"].items() if "exact_match" in v}
    if not ok:
        rep["verdict"] = "판정 불가 — 모든 조건이 실패했다"
    else:
        base = ok.get("sdpa")
        if base is None:
            rep["verdict"] = "판정 불가 — 기본값(sdpa) 조건이 실패했다"
        else:
            best = max(ok, key=ok.get)
            gain = ok[best] - base
            rep["baseline_sdpa"] = base
            rep["best_condition"] = best
            rep["gain_over_baseline"] = round(gain, 4)
            if gain >= GATE_FIX:
                rep["verdict"] = (f"원인 확정 — attention 커널. {best}로 바꾸면 "
                                  f"완전일치가 {base:.1%} → {ok[best]:.1%}로 오른다. "
                                  "이 설정으로 전량 재생성 후 MRR을 재라")
            elif all(abs(v - base) <= GATE_SAME for v in ok.values()):
                rep["verdict"] = ("커널이 아니다 — 어떤 커널을 써도 붙지 않는다. "
                                  "남는 것은 GPU 아키텍처(sm_86 vs sm_89)와 "
                                  "라이브러리 버전이며, 아키텍처면 고칠 수 없다")
            else:
                rep["verdict"] = (f"부분 기여 — 최고 {best} {ok[best]:.1%} "
                                  f"(기본값 {base:.1%}, 차이 {gain:+.1%}p)")

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "env_gap_kernel.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    for k, v in ok.items():
        print(f"  {k:14s} {v:.1%}")
    print("판정:", rep["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
