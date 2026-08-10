"""[후보를 노트북에서 4bit로 생성해 현행과 직접 비교 — 결과 전 커밋]

**이 프로브만이 답하는 것.** 지금까지 잰 모델 효과는 전부 **서버 대 서버**였다.
실제 배포는 노트북 인덱스를 바꾸는 것이므로, 환경이 일치하는 비교가 한 번도 없었다.
후보가 4bit로 6GB에 올라간다는 것이 확인됐으므로(최대 3.27GB 실측) 이제 잴 수 있다.

    노트북 qwen3vl-4B-4bit/P1   vs   노트북 3B-4bit/P0 (현행 배포)

둘 다 노트북이므로 생성 환경이 상수다. `deploy_delta.py`의 ③(서버 후보 − 노트북 현행,
−0.0013)이 아니라 **환경 손실 없는 순수 모델 효과**를 본다.

**검출 한계를 미리 밝힌다 — 결과가 비유의여도 "효과 없음"이 아니다.**
서버에서 환경을 고정하고 잰 4bit 모델 효과는 **+0.0309 CI[−0.056, +0.117] p=0.487**로
이미 비유의였다(`caption_sweep.json`의 qwen3vl_4b_q4/P1 vs qwen25_3b_4bit/P0).
dev 96의 검출 한계는 ±0.086이므로 **+0.03짜리는 애초에 검출되지 않는다.**
따라서 이 프로브의 비유의 결과는 **"잴 수 없음"이지 "차이 없음"이 아니다**(절대규칙
판단기준: "비유의"를 "차이 없음"으로 쓰지 마라).

**그럼에도 돌리는 이유.** 서버에서 잰 +0.0309가 노트북에서도 같으리라는 보장이 없다.
환경 효과가 모델마다 동일하다는 근거가 없고, 3B에서 관측된 노트북 우위(+0.0926)가
qwen3vl에서도 같은 크기일지는 미측정이다. 환경 일치 측정은 이게 유일하다.

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-10).**
  - 주 지표: **캡션 단독 α=0.0 MRR**. 후보가 바꾸는 채널만 본다(규약 1항 채널 격리).
  - 쌍체 부트스트랩 CI가 0을 배제하면 **환경 일치 조건에서 우위 확인**,
    포함하면 **판정 불가(검출 한계 미달)** 로 적는다. "차이 없음"으로 쓰지 않는다.
  - 참고로 서버 4bit·bf16 값을 같이 적어 양자화 효과와 환경 효과를 분리해 보인다.
  - 결과를 보고 지표·임계값을 바꾸지 않는다.

**안전.** `work/`를 **읽기 전용**으로만 쓴다. 배포 인덱스의 `segments.json`을 절대
덮어쓰지 않는다. 생성 캡션은 `_scratch`에 전량 저장한다(규약 5항).
자막 임베딩은 저장된 것을 그대로 쓴다 — α=0.0에서는 랭킹에 관여하지 않고,
두 arm이 같은 것을 쓰므로 비교에 영향이 없다.

test 미접촉. dev 전용.
재현: python docs/probes/laptop_candidate_dev.py
"""
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs/probes"))
import common                                              # noqa: E402
from m4_index import embed_texts                           # noqa: E402
from m5_search import VideoIndex                           # noqa: E402
from m6_evaluate import evaluate                           # noqa: E402
from caption_model_sweep import PROMPTS                    # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
MODEL = "Qwen/Qwen3-VL-4B-Instruct"
PROMPT_KEY = "P1"
B, PERM_N, SEED = 20_000, 200_000, 42


def gen_captions(frames, cfg, prompt):
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, BitsAndBytesConfig, \
        Qwen3VLForConditionalGeneration

    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL, quantization_config=quant, device_map={"": 0}).eval()
    proc = AutoProcessor.from_pretrained(MODEL, min_pixels=256 * 28 * 28,
                                         max_pixels=cfg["vlm_max_pixels"])
    gk = dict(max_new_tokens=cfg.get("vlm_max_new_tokens", 128), do_sample=False)
    if cfg.get("vlm_rep_penalty", 1.0) != 1.0:
        gk["repetition_penalty"] = cfg["vlm_rep_penalty"]

    outs, t0 = [], time.time()
    try:
        for i, f in enumerate(frames):
            msgs = [{"role": "user", "content": [
                {"type": "image", "image": str(f)}, {"type": "text", "text": prompt}]}]
            text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            imgs, vids_ = process_vision_info(msgs)
            inp = proc(text=[text], images=imgs, videos=vids_, padding=True,
                       return_tensors="pt").to(model.device)
            with torch.inference_mode():
                gen = model.generate(**inp, **gk)
            outs.append(proc.batch_decode(gen[:, inp.input_ids.shape[1]:],
                                          skip_special_tokens=True)[0].strip())
            if i % 50 == 0:
                el = time.time() - t0
                print(f"  {i}/{len(frames)}  경과 {el/60:.1f}분", flush=True)
    finally:
        del model
        torch.cuda.empty_cache()
    return outs


def stats(d):
    rng = np.random.default_rng(SEED)
    m = d[rng.integers(0, len(d), size=(B, len(d)))].mean(1)
    sg = rng.choice([-1.0, 1.0], size=(PERM_N, len(d)))
    p = float((np.abs((sg * d).mean(1)) >= abs(d.mean())).mean())
    return (round(float(d.mean()), 4),
            [round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)],
            round(p, 4))


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    prompt = PROMPTS[PROMPT_KEY]
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})

    base = {v: VideoIndex.load(cfg, v) for v in vids}     # 읽기 전용
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}

    cap_path = OUT / "laptop_candidate_captions.json"
    if cap_path.exists():
        caps = json.loads(cap_path.read_text(encoding="utf-8"))
        print(f"저장된 캡션 재사용: {sum(len(v) for v in caps.values())}건", flush=True)
    else:
        caps = {}
        for v in vids:
            frames = [wdirs[v] / s["rep_frame"] for s in base[v].segments]
            print(f"[{v}] {len(frames)}장 생성", flush=True)
            caps[v] = gen_captions(frames, cfg, prompt)
        OUT.mkdir(parents=True, exist_ok=True)
        cap_path.write_text(json.dumps(caps, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"캡션 저장 -> {cap_path}", flush=True)

    # 현행(배포 인덱스) — 저장된 임베딩 그대로
    inc = evaluate(dev, base, 0.0, cfg)["per_query"]
    rr_inc = np.array([x["mrr"] for x in inc])

    # 후보 — 캡션만 교체, 자막 임베딩은 동일(α=0.0에서 랭킹 무관)
    cand_idx = {v: VideoIndex(segments=base[v].segments, emb_sub=base[v].emb_sub,
                              emb_cap=embed_texts(caps[v], cfg["embed_model"],
                                                  cfg["embed_batch_size"]),
                              static_mask=base[v].static_mask) for v in vids}
    cnd = evaluate(dev, cand_idx, 0.0, cfg)["per_query"]
    rr_cnd = np.array([x["mrr"] for x in cnd])
    assert [x["query_id"] for x in inc] == [x["query_id"] for x in cnd], "질의 정렬 불일치"

    flat = [t for v in vids for t in caps[v]]
    delta, ci, p = stats(rr_cnd - rr_inc)
    rep = {"note": "dev only, 채택 아님. work/ 읽기 전용, test 미접촉.",
           "model": MODEL, "quant": "4bit nf4", "prompt_key": PROMPT_KEY,
           "prereg": {"primary": "캡션 단독 α=0.0 MRR",
                      "mde_note": "dev 96 검출 한계 ±0.086 — 비유의는 '잴 수 없음'이지 "
                                  "'차이 없음'이 아니다",
                      "server_reference": "서버 4bit 모델 효과 +0.0309 CI[-0.056,+0.117]",
                      "declared_before_run": True},
           "n_queries": len(dev), "n_captions": len(flat),
           "len_mean": round(float(np.mean([len(t) for t in flat])), 1),
           "corrupted": sum(1 for t in flat if common.is_corrupted_caption(t)),
           "mrr_incumbent": round(float(rr_inc.mean()), 4),
           "mrr_candidate": round(float(rr_cnd.mean()), 4),
           "delta": delta, "ci95": ci, "perm_p": p}
    rep["verdict"] = ("환경 일치 조건에서 우위 확인" if (ci[0] > 0 or ci[1] < 0)
                      else "판정 불가 — CI가 0을 포함한다(검출 한계 미달). "
                           "'차이 없음'이 아니다")

    p_out = OUT / "laptop_candidate_dev.json"
    p_out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"현행(노트북 3B-4bit)  {rep['mrr_incumbent']:.4f}")
    print(f"후보(노트북 qwen3vl-4bit) {rep['mrr_candidate']:.4f}  "
          f"길이 {rep['len_mean']} 오염 {rep['corrupted']}")
    print(f"Δ {delta:+.4f}  CI95 {ci}  순열 p={p}")
    print("판정:", rep["verdict"])
    print("->", p_out)


if __name__ == "__main__":
    main()
