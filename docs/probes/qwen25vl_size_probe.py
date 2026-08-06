"""[Qwen2.5-VL 7B vs 3B 캡션 dev 비교 — 채택 아님, 실측용]

앞선 캡션 비교(qwen3vl/varco)의 결함을 고친 설계다. 그 둘은 **현행 전용으로 튜닝된
설정을 후보에게 그대로 씌웠다** — Phase 2 STT의 straw-man 기준선 사고와 같은 구조다.
증거: Qwen3-VL에서 **자막형 MRR이 0.7858→0.6161로 떨어졌다.** 자막 채널은 arm 간
완전히 동일한데도 그렇다. α=0.5 융합이 캡션 채널의 노이즈를 자막 결과까지 끌어내린
것이고, 즉 그 수치는 "캡션이 나쁘다"가 아니라 "현행 α에 안 맞는다"를 잰 것이다.

이 프로브가 고치는 것 2가지:
  1. **α를 arm마다 재탐색**한다(dev 그리드). 고정 α=0.5 결과도 병기해 차이를 보인다.
  2. **양자화와 모델 크기를 분리**한다. 현행은 3B-**4bit**인데 후보를 7B-**bf16**으로
     재면 두 요인이 섞인다. 3B-bf16 arm을 넣어 각각을 분리한다.

arm 3종 (전부 dev 3영상 655프레임, 기존 rep_frame 재사용):
  cur_3b_4bit  현행 그대로 — segments.json의 캡션을 그대로 쓴다(재생성 없음)
  3b_bf16      같은 모델, 양자화만 해제      → cur 대비 = **양자화 효과**
  7b_bf16      같은 계열 7B, bf16            → 3b_bf16 대비 = **모델 크기 효과**
                                              cur 대비 = **시스템 효과(실제 교체분)**

프롬프트·max_new_tokens·rep_penalty·max_pixels는 arm 무관하게 config 값을 쓴다 —
같은 계열이라 이 설정이 후보에게 불리하게 작용할 이유가 없다(Qwen3-VL·VARCO는
계열이 달라 이 가정이 성립하지 않았다).

work/·results/ 불변, test 미접촉. 재임베딩은 메모리에서만.
재현: python docs/probes/qwen25vl_size_probe.py [--arms 3b_bf16,7b_bf16]
"""
import argparse, gc, json, statistics as st, sys
from pathlib import Path
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                          # noqa: E402
from m3_generate import load_vlm, caption_frame        # noqa: E402
from m4_index import embed_texts                       # noqa: E402
from m5_search import VideoIndex                       # noqa: E402
from m6_evaluate import evaluate, grid_search_alpha    # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
ARMS = {
    "3b_bf16": ("Qwen/Qwen2.5-VL-3B-Instruct", False),
    "7b_bf16": ("Qwen/Qwen2.5-VL-7B-Instruct", False),
}


def rr_vec(res):
    return np.array([r["mrr"] for r in res["per_query"]])


def gen_captions(cfg, arm, vids, idx_cur):
    """arm 설정으로 dev 전 프레임 캡션 재생성. 모델은 arm당 1회만 로드."""
    model_name, use_4bit = ARMS[arm]
    acfg = {**cfg, "caption_model": model_name, "vlm_4bit": use_4bit}
    print(f"[{arm}] {model_name} 로딩...", flush=True)
    model, processor = load_vlm(acfg)
    caps = {}
    for v in vids:
        wdir = common.work_dir(cfg, v)
        out = []
        for i, s in enumerate(idx_cur[v].segments):
            out.append(caption_frame(Path(wdir) / s["rep_frame"],
                                     cfg["caption_prompt"], model, processor, acfg))
            if i % 50 == 0:
                print(f"  {v[:20]} {i}", flush=True)
        caps[v] = out
        print(f"[{arm}] {v[:24]} {len(out)}개", flush=True)
    del model, processor
    gc.collect()
    torch.cuda.empty_cache()
    return caps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="3b_bf16,7b_bf16")
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]

    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})

    idx = {"cur_3b_4bit": {v: VideoIndex.load(cfg, v) for v in vids}}
    texts = {"cur_3b_4bit": {v: [s.get("caption") or ""
                                 for s in idx["cur_3b_4bit"][v].segments] for v in vids}}
    for arm in arms:
        caps = gen_captions(cfg, arm, vids, idx["cur_3b_4bit"])
        texts[arm] = caps
        idx[arm] = {v: VideoIndex(
            segments=idx["cur_3b_4bit"][v].segments,
            emb_sub=idx["cur_3b_4bit"][v].emb_sub,
            emb_cap=embed_texts(caps[v], cfg["embed_model"]),
            static_mask=idx["cur_3b_4bit"][v].static_mask) for v in vids}

    keys = ["cur_3b_4bit"] + arms
    rep = {"note": "dev-only, 채택 아님. work/·results/ 불변, test 미접촉.",
           "arms": {k: {"model": ARMS.get(k, (cfg["caption_model"], True))[0],
                        "4bit": ARMS.get(k, (None, True))[1]} for k in keys},
           "seed": cfg["seed"], "alpha_fixed": 0.5, "by_arm": {}, "contrasts": {}}

    # 캡션 특성 — 길이는 검색 성능의 교란(짧으면 매칭 표면이 준다). 실측해 병기.
    for k in keys:
        L = [len(t) for v in vids for t in texts[k][v]]
        corr = sum(1 for v in vids for t in texts[k][v] if common.is_corrupted_caption(t))
        rep["by_arm"][k] = {"n_captions": len(L), "len_mean": round(st.mean(L), 1),
                            "len_median": st.median(L),
                            "corrupted": corr, "corrupt_rate": round(corr / len(L), 4)}

    # 지표 2종: (a) 고정 α=0.5, (b) arm별 α 재탐색 — 앞선 비교가 (a)만 봤다.
    vecs_fixed, vecs_star = {}, {}
    for k in keys:
        r = evaluate(dev, idx[k], 0.5, cfg)
        rep["by_arm"][k]["mrr_alpha_fixed"] = r["metrics"]["mrr"]
        rep["by_arm"][k]["by_type_alpha_fixed"] = {
            t: m["mrr"] for t, m in r["metrics"]["by_type"].items()}
        vecs_fixed[k] = rr_vec(r)

        gs = grid_search_alpha(dev, idx[k], cfg)
        astar = gs["dev_search"]["alpha_star"] if "dev_search" in gs else gs["alpha_star"]
        r2 = evaluate(dev, idx[k], astar, cfg)
        rep["by_arm"][k]["alpha_star"] = astar
        rep["by_arm"][k]["mrr_alpha_star"] = r2["metrics"]["mrr"]
        vecs_star[k] = rr_vec(r2)
        print(f"[{k}] α고정 {r['metrics']['mrr']:.4f} | α*={astar} {r2['metrics']['mrr']:.4f}",
              flush=True)

    n, B = len(dev), cfg["bootstrap_B"]
    rng = np.random.default_rng(cfg["seed"])
    ib = rng.integers(0, n, size=(B, n))

    def ci(base, cand, vecs):
        d = vecs[cand][ib].mean(1) - vecs[base][ib].mean(1)
        lo, hi = np.percentile(d, [2.5, 97.5])
        return {"delta": round(float(vecs[cand].mean() - vecs[base].mean()), 4),
                "ci95": [round(float(lo), 4), round(float(hi), 4)],
                "significant": bool(lo > 0 or hi < 0)}

    pairs = {"quantization(3b_bf16 vs cur)": ("cur_3b_4bit", "3b_bf16"),
             "model_size(7b vs 3b_bf16)": ("3b_bf16", "7b_bf16"),
             "system(7b_bf16 vs cur)": ("cur_3b_4bit", "7b_bf16")}
    for label, (b, c) in pairs.items():
        if b in vecs_fixed and c in vecs_fixed:
            rep["contrasts"][label] = {"alpha_fixed": ci(b, c, vecs_fixed),
                                       "alpha_star": ci(b, c, vecs_star)}

    rep["samples"] = [{"video_id": v, "seg_idx": i,
                       **{k: texts[k][v][i] for k in keys}}
                      for v in vids for i in (0, 1, 2)]
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "qwen25vl_size_probe.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {p}")


if __name__ == "__main__":
    main()
