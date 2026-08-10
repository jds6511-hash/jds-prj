"""[생성 환경 효과를 독립 표본에서 검증 — dev 밖에서 처음, 결과 전 커밋]

**지금 모든 판단의 밑에 깔린 전제.** 노트북(RTX 3060) 생성 캡션이 서버(RTX 4090)
생성분보다 dev 캡션단독 MRR이 **0.09 높다**(−0.0926 CI [−0.161, −0.025], p=0.0085).
이 전제 때문에 후보 모델 채택이 막혀 있다 — 후보로 갈아타면 인덱스가 서버 생성분이
되어 모델 이득 +0.0913을 환경 손실이 상쇄한다(`deploy_delta.py` ③ = −0.0013).

**그런데 근거가 dev 96건 하나뿐이다.** 서버에서 두 번 생성해 서로 98% 일치한 것은
"서버가 안정적"이라는 증거이지 "서버가 계통적으로 나쁘다"가 **다른 데이터에서도
성립한다**는 증거가 아니다. 환경은 둘뿐이고 각각 결정적 출력이 하나씩이므로,
0.09가 노트북이 우연히 뽑은 좋은 출력일 가능성을 dev만으로는 배제할 수 없다.

**AI Hub(n=1,086)에서 검증한다. 대조군은 이미 있다.** 확증 실행 때 서버에서 생성한
`qwen25_3b_4bit/P0` AI Hub 캡션이 저장돼 있다(`aihub_confirm_captions/`). 노트북에서
**같은 모델·같은 4bit·같은 프롬프트·같은 그리디**로 만들어 붙이면 쌍체 비교가 된다.
입력 동일성은 이미 확인됐다(프레임·전처리 비트 단위 일치, `env_gap_stage1.json`).

**두 결과 모두 결정적이다.**
  - AI Hub에서도 노트북이 **유의하게 높으면** → 환경 효과는 실재한다. "노트북에
    올라가는 모델만 후보"라는 제약이 확정되고, 8B 이상은 배포 시 손실을 안는다.
  - **차이가 없으면** → dev의 0.09는 96건짜리 우연이었다. 그러면 **전부 서버로
    통일**하고 후보를 bf16으로 채택하는 것이 맞으며, 8B·14B·32B가 전부 후보로 열린다.

n=1,086이므로 0.09는 확실히 검출된다(dev의 MDE ±0.086과 달리).

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-10).**
  - 주 지표: **캡션 단독 α=0.0 MRR**. AI Hub 확증과 동일한 지표를 쓴다(지표 변경 금지).
  - 쌍체 부트스트랩 95% CI가 0을 배제하고 **부호가 dev와 같으면**(노트북 우위)
    → "환경 효과 독립 표본에서 재현됨".
  - CI가 0을 포함하면 → "재현 실패 — dev의 0.09는 독립 표본에서 확인되지 않는다".
    이 경우 노트북 제약을 후보 선정 기준으로 쓰던 근거가 사라진다.
  - 부호가 dev와 반대이면서 유의하면 → "역전 — 별도 규명 필요"로 적는다.
  - 결과를 보고 지표·임계값을 바꾸지 않는다.

**주의.** 이건 **환경** 비교이지 모델 비교가 아니다. 두 arm이 같은 모델·설정이고
오직 생성 기계만 다르다. 따라서 AI Hub를 "확증 표본"으로 소모하는 것이 아니다 —
후보 채택 판정에는 쓰이지 않는다.

work_aihub 인덱스 불변(재임베딩은 메모리에서만), dev·test 미접촉.
재현: python docs/probes/aihub_env_check.py
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
from aihub_external_eval import load_external_queries      # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
SERVER_CAPS = OUT / "aihub_confirm_captions" / "qwen25_3b_4bit__P0.json"
LAPTOP_CAPS = OUT / "aihub_laptop_captions.json"
CFG = "config_aihub.yaml"
B, PERM_N, SEED = 20_000, 200_000, 42


def load_once(cfg):
    """모델을 한 번만 올린다. 영상마다 재적재하면 97회 × 15초를 버린다."""
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, BitsAndBytesConfig, \
        Qwen2_5_VLForConditionalGeneration
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        cfg["caption_model"], quantization_config=quant, device_map={"": 0}).eval()
    proc = AutoProcessor.from_pretrained(cfg["caption_model"], min_pixels=256 * 28 * 28,
                                         max_pixels=cfg["vlm_max_pixels"])
    gk = dict(max_new_tokens=cfg.get("vlm_max_new_tokens", 128), do_sample=False)
    if cfg.get("vlm_rep_penalty", 1.0) != 1.0:
        gk["repetition_penalty"] = cfg["vlm_rep_penalty"]

    def gen(frames):
        import torch
        outs, t0 = [], time.time()
        for i, f in enumerate(frames):
            msgs = [{"role": "user", "content": [
                {"type": "image", "image": str(f)},
                {"type": "text", "text": cfg["caption_prompt"]}]}]
            text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            imgs, vids_ = process_vision_info(msgs)
            inp = proc(text=[text], images=imgs, videos=vids_, padding=True,
                       return_tensors="pt").to(model.device)
            with torch.inference_mode():
                g = model.generate(**inp, **gk)
            outs.append(proc.batch_decode(g[:, inp.input_ids.shape[1]:],
                                          skip_special_tokens=True)[0].strip())
        return outs, (time.time() - t0) / max(len(frames), 1)

    def close():
        import torch
        del model
        torch.cuda.empty_cache()

    return gen, close


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", choices=["A", "B", "all"], default="A",
                    help="영상 절반만 쓴다. 기본 A — 노트북 생성이 프레임당 17초대라 "
                         "전량이면 12시간을 넘긴다. n≈562로도 MDE ±0.036이라 "
                         "재려는 0.09는 여유 있게 검출된다")
    ap.add_argument("--max-videos", type=int, default=None,
                    help="영상 수 상한. AI Hub 프레임이 dev보다 커서 프레임당 50초대라 "
                         "A 절반 97편이면 17시간이 걸린다. 표본을 줄여도 n≈280에서 "
                         "MDE ±0.050이라 재려는 0.09는 검출된다")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / CFG))
    prompt = cfg["caption_prompt"]
    qs_all = load_external_queries(ROOT / "data_aihub/queries/queries_aihub.jsonl")

    srv_all = json.loads(SERVER_CAPS.read_text(encoding="utf-8"))
    vids = sorted(srv_all)
    if a.side != "all":
        # 임베더·2단계와 **같은 분할·같은 시드**를 쓴다(embedder_sweep.load_side와 동일 규칙)
        perm = np.random.default_rng(42).permutation(len(vids))
        half = len(vids) // 2
        pick = {vids[i] for i in (perm[:half] if a.side == "A" else perm[half:])}
        vids = [v for v in vids if v in pick]
    if a.max_videos:
        done = set()
        if LAPTOP_CAPS.exists():
            done = set(json.loads(LAPTOP_CAPS.read_text(encoding="utf-8")))
        # 이미 만든 것을 먼저 채우고 나머지를 순서대로 — 생성분을 버리지 않는다
        vids = ([v for v in vids if v in done] +
                [v for v in vids if v not in done])[:a.max_videos]
        vids = sorted(vids)
    srv = {v: srv_all[v] for v in vids}
    print(f"[{a.side} 절반] 영상 {len(vids)}편", flush=True)
    idx0 = {v: VideoIndex.load(cfg, v) for v in vids}
    qs = [q for q in qs_all if q["video_id"] in idx0]
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}
    print(f"영상 {len(vids)} · 질의 {len(qs)} · 세그먼트 "
          f"{sum(len(idx0[v].segments) for v in vids)}", flush=True)

    # 부분 체크포인트에서 이어받는다. 파일이 있다고 생성을 통째로 건너뛰면
    # 중간에 끊겼을 때 불완전한 캡션으로 평가하거나 KeyError로 죽는다.
    lap = {}
    if LAPTOP_CAPS.exists():
        lap = json.loads(LAPTOP_CAPS.read_text(encoding="utf-8"))
        lap = {v: c for v, c in lap.items()
               if v in idx0 and len(c) == len(idx0[v].segments)}   # 길이 안 맞으면 버린다
        print(f"체크포인트 재사용 {len(lap)}/{len(vids)}편", flush=True)
    todo = [v for v in vids if v not in lap]
    if todo:
        print(f"생성 대상 {len(todo)}편 "
              f"({sum(len(idx0[v].segments) for v in todo)}장)", flush=True)
        gen, close = load_once(cfg)
        try:
            for n, v in enumerate(todo, 1):
                frames = [wdirs[v] / s["rep_frame"] for s in idx0[v].segments]
                lap[v], spf = gen(frames)
                print(f"  [{n}/{len(todo)}] {v} {len(frames)}장 "
                      f"{spf:.1f}초/장", flush=True)
                if n % 5 == 0 or n == len(todo):
                    LAPTOP_CAPS.write_text(json.dumps(lap, ensure_ascii=False),
                                           encoding="utf-8")
        finally:
            close()
        LAPTOP_CAPS.write_text(json.dumps(lap, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        print(f"저장 -> {LAPTOP_CAPS}", flush=True)
    missing = [v for v in vids if v not in lap]
    if missing:
        raise ValueError(f"캡션 미생성 {len(missing)}편 — 이어서 재실행하라")

    def score(caps):
        idx = {v: VideoIndex(segments=idx0[v].segments, emb_sub=idx0[v].emb_sub,
                             emb_cap=embed_texts(caps[v], cfg["embed_model"],
                                                 cfg["embed_batch_size"]),
                             static_mask=idx0[v].static_mask) for v in vids}
        r = evaluate(qs, idx, 0.0, cfg)
        return r["metrics"]["mrr"], np.array([x["mrr"] for x in r["per_query"]])

    m_s, rr_s = score(srv)
    m_l, rr_l = score(lap)
    d = rr_l - rr_s

    rng = np.random.default_rng(SEED)
    boot = d[rng.integers(0, len(d), size=(B, len(d)))].mean(1)
    sg = rng.choice([-1.0, 1.0], size=(PERM_N, len(d)))
    p = float((np.abs((sg * d).mean(1)) >= abs(d.mean())).mean())
    lo, hi = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))

    same = [1 for v in vids for a, b in zip(lap[v], srv[v]) if a == b]
    n_seg = sum(len(srv[v]) for v in vids)
    rep = {"note": "환경 비교. 모델 비교 아님 — 확증 표본을 소모하지 않는다. test 미접촉.",
           "model": cfg["caption_model"], "quant": "4bit nf4",
           "prereg": {"primary": "캡션 단독 α=0.0 MRR",
                      "rule": "CI가 0 배제하고 부호가 dev와 같으면 재현됨",
                      "dev_reference": "-0.0926 CI[-0.1608,-0.0252] p=0.0085 (서버-노트북)",
                      "declared_before_run": True},
           "side": a.side, "n_videos": len(vids), "n_queries": len(qs), "n_segments": n_seg,
           "exact_match_rate": round(len(same) / n_seg, 4),
           "mrr_server": round(float(m_s), 4), "mrr_laptop": round(float(m_l), 4),
           "delta_laptop_minus_server": round(float(d.mean()), 4),
           "ci95": [round(lo, 4), round(hi, 4)], "perm_p": round(p, 4)}
    if lo > 0:
        rep["verdict"] = ("환경 효과 독립 표본에서 재현됨 — 노트북 우위 실재. "
                          "노트북에 올라가는 모델만 후보로 유지한다")
    elif hi < 0:
        rep["verdict"] = "역전 — 서버가 유의하게 높다. 별도 규명 필요"
    else:
        rep["verdict"] = ("재현 실패 — dev의 0.09가 독립 표본에서 확인되지 않는다. "
                          "노트북 제약을 후보 선정 기준으로 쓸 근거가 사라진다")

    OUT.mkdir(parents=True, exist_ok=True)
    p_out = OUT / "aihub_env_check.json"
    p_out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"서버 {rep['mrr_server']:.4f} · 노트북 {rep['mrr_laptop']:.4f} · "
          f"완전일치 {rep['exact_match_rate']:.1%}")
    print(f"Δ(노트북−서버) {rep['delta_laptop_minus_server']:+.4f} "
          f"CI{rep['ci95']} p={rep['perm_p']}")
    print("판정:", rep["verdict"])
    print("->", p_out)


if __name__ == "__main__":
    main()
