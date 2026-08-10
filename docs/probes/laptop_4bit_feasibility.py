"""[후보 모델을 노트북에서 4bit로 돌릴 수 있는가 — 타당성 확인, 채택 아님]

**왜 이걸 보는가.** 후보 Qwen3-VL-4B-Instruct의 `4b`는 **파라미터 40억**이지 4bit가
아니다. 지금까지 전부 bf16으로 11.4GB를 써서 6GB 노트북에 안 올라갔고, 그래서 채택
시 인덱스 전체를 서버 생성분으로 바꿔야 했다. 그 교체가 생성 환경 손실 −0.0926을
불러 모델 이득 +0.0913을 상쇄한다(`deploy_delta.py`).

**4bit로 노트북에 올라가면 그 문제 자체가 사라진다.** 환경이 안 바뀌므로 손실이
발생하지 않고, 커널 프로브 결과와 무관하게 채택 경로가 열린다.

근거 둘. 2026-08-07 실측에서 **양자화 효과는 Δ+0.0024로 비유의**였다(3B-bf16 vs
3B-4bit). 그리고 현행 3B-4bit가 서버에서 5.3GB로 돌아간다.

위험. 4B는 3B보다 크고, 노트북 여유 VRAM은 화면 출력분을 빼면 5.4GB 안팎이다.
`vlm_max_pixels`를 낮추면 올라갈 수도 있지만 **그건 별개의 변경**이라 여기서는
현행 값(602112)을 유지한 채로만 판정한다.

**이건 가설검정이 아니라 타당성 확인이다.** 재는 것은 세 가지뿐이다.
  1. 적재되는가 (OOM 없이)
  2. 최대 VRAM 사용량
  3. 프레임당 생성 시간 → dev 전량(655장) 소요 추정

**판정.**
  - OOM 없이 생성되면 → **가능**. 다음 단계는 dev 전량 생성 후 노트북 현행과 직접 비교.
    그 비교는 환경이 같으므로 `deploy_delta.py`의 ③이 아니라 ①에 해당한다.
  - OOM이면 → **불가**. max_pixels 하향은 별도 변경이므로 따로 판단한다.

work/·results/ 불변, test 미접촉. 캡션을 저장하지 않는다(타당성만 본다).
재현: python docs/probes/laptop_4bit_feasibility.py [--n 10]
"""
import argparse
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
MODEL = "Qwen/Qwen3-VL-4B-Instruct"
DEV_FRAMES_TOTAL = 655          # dev 3편 세그먼트 수(소요 추정용)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()

    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, BitsAndBytesConfig

    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    v = sorted({q["video_id"] for q in qs if q["split"] == "dev"})[0]
    wdir = Path(common.work_dir(cfg, v))
    segs = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
    segs = segs["segments"] if isinstance(segs, dict) else segs
    frames = [wdir / s["rep_frame"] for s in segs[:a.n]]

    torch.cuda.reset_peak_memory_stats()
    free0, total = torch.cuda.mem_get_info()
    print(f"GPU {torch.cuda.get_device_name(0)} · 전체 {total/1e9:.2f}GB · "
          f"시작 여유 {free0/1e9:.2f}GB", flush=True)

    rep = {"note": "타당성 확인. 채택 아님, 캡션 미저장, test 미접촉.",
           "model": a.model, "vlm_max_pixels": cfg["vlm_max_pixels"],
           "vlm_max_new_tokens": cfg.get("vlm_max_new_tokens", 128),
           "gpu": torch.cuda.get_device_name(0),
           "vram_total_gb": round(total / 1e9, 2),
           "vram_free_at_start_gb": round(free0 / 1e9, 2),
           "n_frames": len(frames)}

    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    try:
        from transformers import Qwen3VLForConditionalGeneration as Cls
        t0 = time.time()
        model = Cls.from_pretrained(a.model, quantization_config=quant,
                                    device_map={"": 0}).eval()
        rep["load_sec"] = round(time.time() - t0, 1)
        rep["vram_after_load_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        print(f"적재 완료 {rep['load_sec']}초 · 가중치 {rep['vram_after_load_gb']}GB",
              flush=True)
    except torch.cuda.OutOfMemoryError as e:
        rep["verdict"] = f"불가 — 적재 단계 OOM: {str(e)[:200]}"
        _save(rep)
        return
    except Exception as e:
        rep["verdict"] = f"실패 — {type(e).__name__}: {str(e)[:300]}"
        _save(rep)
        return

    proc = AutoProcessor.from_pretrained(a.model, min_pixels=256 * 28 * 28,
                                         max_pixels=cfg["vlm_max_pixels"])
    gen_kwargs = dict(max_new_tokens=cfg.get("vlm_max_new_tokens", 128), do_sample=False)
    if cfg.get("vlm_rep_penalty", 1.0) != 1.0:
        gen_kwargs["repetition_penalty"] = cfg["vlm_rep_penalty"]

    times, samples = [], []
    try:
        for i, f in enumerate(frames):
            msgs = [{"role": "user", "content": [
                {"type": "image", "image": str(f)},
                {"type": "text", "text": cfg["caption_prompt"]}]}]
            text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            imgs, vids_ = process_vision_info(msgs)
            inp = proc(text=[text], images=imgs, videos=vids_, padding=True,
                       return_tensors="pt").to(model.device)
            t0 = time.time()
            with torch.inference_mode():
                gen = model.generate(**inp, **gen_kwargs)
            times.append(time.time() - t0)
            out = proc.batch_decode(gen[:, inp.input_ids.shape[1]:],
                                    skip_special_tokens=True)[0].strip()
            if i < 3:
                samples.append(out[:120])
            print(f"  {i+1}/{len(frames)} {times[-1]:.1f}초", flush=True)
    except torch.cuda.OutOfMemoryError as e:
        rep["vram_peak_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        rep["n_completed"] = len(times)
        rep["verdict"] = (f"불가 — 생성 중 OOM({len(times)}장 후). "
                          f"최대 {rep['vram_peak_gb']}GB: {str(e)[:150]}")
        _save(rep)
        return

    per = sum(times) / len(times)
    rep["vram_peak_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
    rep["sec_per_frame"] = round(per, 2)
    rep["est_dev_hours"] = round(per * DEV_FRAMES_TOTAL / 3600, 2)
    rep["samples"] = samples
    rep["verdict"] = (f"가능 — 최대 {rep['vram_peak_gb']}GB, 프레임당 {per:.1f}초. "
                      f"dev 전량({DEV_FRAMES_TOTAL}장) 추정 {rep['est_dev_hours']}시간")
    _save(rep)


def _save(rep):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "laptop_4bit_feasibility.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print("판정:", rep["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
