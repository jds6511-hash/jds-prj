"""[임베더 비교 — AI Hub 절반에서 선택, 나머지 절반에서 확증 (결과 전 커밋)]

**왜 임베더인가.** dev 실패 52건의 분해에서 12%가 "캡션에 내용은 있는데 질의와
매칭이 안 된다"(변별 실패)였다. 그게 임베더가 겨냥하는 몫이다.

**왜 조건이 좋은가 — 생성 환경 교란이 없다.** 캡션 텍스트는 고정이고 임베딩만
바뀐다. 캡션 모델 교체를 막고 있는 −0.09짜리 환경 효과(`deploy_delta.py`)가 여기엔
적용되지 않는다. 비용도 거의 없다(VLM 생성 불필요, 모델당 텍스트 ~4,700건).

**왜 dev를 안 쓰는가.** 임베더의 상한이 낮다. 변별 실패 12% × 실패 비율 54% ≈ 전체
질의의 6.5%가 개선 여지이고 MRR로는 대략 0.03~0.05다. **dev 96의 검출 한계
±0.086보다 작아서 dev로는 고를 수가 없다.** AI Hub 1,086건을 영상 단위로 반으로
갈라 한쪽에서 고르고 다른 쪽에서 확증한다(각 ~543건). 선택과 확증이 분리되므로
지금까지 쓴 절차가 그대로 적용된다.

**절차.**
  1단계 `--stage select`  후보 전부를 **A 절반**에서 잰다. α는 모델마다 A에서
                          재탐색한다(규약 3항 — 현행 α*는 KURE 전용으로 튜닝된 값이라
                          후보에게 불리하다).
  2단계 `--stage confirm --model X`  **1단계 승자 하나만** B 절반에서 잰다.
                          B는 이 한 번만 쓴다. 여러 모델을 B에서 재면 확증이 아니다.

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-10).**
  - 주 지표: **융합 MRR**(모델별 A에서 재탐색한 α*). 임베더는 두 채널을 모두
    바꾸므로 융합이 배포 조건이다.
  - 채널 격리 병기 필수(규약 1항): 캡션 단독 α=0.0, 자막 단독 α=1.0을 같이 적는다.
  - 1단계 승자 = 현행 대비 Δ가 가장 크고 **BH-FDR(q=0.05)을 통과한** 모델.
    통과하는 모델이 없으면 **"선택 없음 — 현행 유지"** 로 끝내고 2단계를 돌리지 않는다.
  - 2단계 판정: 95% CI가 0을 배제하고 부호가 1단계와 같으면 **재현됨**, 아니면
    **재현 실패 — 채택 근거 없음**.
  - 결과를 보고 지표·임계값·후보를 바꾸지 않는다.

**동일 환경 대조군(규약 4항).** 현행 KURE-v1도 **같은 실행에서 다시 임베딩**한다.
저장된 인덱스와 직접 비교하지 않는다. 이 대조가 부수적으로 하나 더 알려준다 —
서버 재임베딩이 저장분과 같은 점수를 내면, 생성 환경 효과는 자기회귀 생성 고유의
문제이지 GPU 수치 전반의 문제가 아니라는 뜻이다.

**1차에서 뺀 것 — 제외가 아니라 연기다.** e5·KoE5·Qwen3-Embedding·arctic-embed는
질의/문서에 서로 다른 접두어가 필수인데, `m5_search.search`가 질의를 내부에서
임베딩하고 `expand_query` 변형까지 거치므로 접두어를 안전하게 끼우려면 검색 경로를
손봐야 한다. 접두어 없이 돌리면 그 모델들이 부당하게 진다(규약 3항 위반). 2차로 미룬다.

work_aihub 인덱스 불변(재임베딩은 메모리에서만), dev·test 미접촉.
재현:
  python docs/probes/embedder_sweep.py --stage select
  python docs/probes/embedder_sweep.py --stage confirm --model <id>
"""
import argparse
import io
import json
import sys
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
INCUMBENT = "nlpai-lab/KURE-v1"
# 접두어가 필요 없는 모델만. 사유는 docstring 참조.
CANDIDATES = [INCUMBENT, "BAAI/bge-m3", "dragonkue/BGE-m3-ko",
              "upskyy/bge-m3-korean", "Alibaba-NLP/gte-multilingual-base"]
SPLIT_SEED = 42
B = 20_000


def boot_ci(d, seed=SPLIT_SEED):
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), size=(B, len(d)))].mean(1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def perm_p(d, seed=SPLIT_SEED, N=200_000):
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    sg = rng.choice([-1.0, 1.0], size=(N, len(d)))
    return float((np.abs((sg * d).mean(1)) >= obs).mean())


def bh_reject(pvals, q=0.05):
    """Benjamini-Hochberg. 반환: 각 p의 기각 여부(원래 순서)."""
    order = np.argsort(pvals)
    m = len(pvals)
    keep = np.zeros(m, dtype=bool)
    thr = 0
    for rank, i in enumerate(order, 1):
        if pvals[i] <= rank / m * q:
            thr = rank
    for rank, i in enumerate(order, 1):
        if rank <= thr:
            keep[i] = True
    return keep


def load_side(cfg, queries_path, side, split_seed=SPLIT_SEED):
    """AI Hub를 영상 단위로 반 가른다. side in {'A','B'}."""
    qs_all = load_external_queries(ROOT / queries_path)
    idx0, missing = {}, []
    for v in sorted({q["video_id"] for q in qs_all}):
        try:
            idx0[v] = VideoIndex.load(cfg, v)
        except Exception as e:
            missing.append({"video_id": v, "error": f"{type(e).__name__}: {e}"})
    vids = sorted(idx0)
    perm = np.random.default_rng(split_seed).permutation(len(vids))
    half = len(vids) // 2
    pick = {vids[i] for i in (perm[:half] if side == "A" else perm[half:])}
    qs = [q for q in qs_all if q["video_id"] in pick]
    return {v: idx0[v] for v in sorted(pick)}, qs, missing


def measure(model_id, idx0, qs, cfg, alpha_grid):
    """모델 하나로 두 채널을 다시 임베딩하고 α를 재탐색한다."""
    c = dict(cfg)
    c["embed_model"] = model_id
    idx = {}
    for v, ix in idx0.items():
        subs = [s["subtitle"] for s in ix.segments]
        caps = [s["caption"] for s in ix.segments]
        idx[v] = VideoIndex(segments=ix.segments,
                            emb_sub=embed_texts(subs, model_id, cfg["embed_batch_size"]),
                            emb_cap=embed_texts(caps, model_id, cfg["embed_batch_size"]),
                            static_mask=ix.static_mask)
    curve = {}
    for al in alpha_grid:
        curve[al] = evaluate(qs, idx, al, c)["metrics"]["mrr"]
    a_star = max(curve, key=lambda k: (curve[k], k))      # 동률 시 자막 우선(큰 α)
    out = {"alpha_star": a_star, "alpha_curve": {str(k): v for k, v in curve.items()}}
    for al, name in ((0.0, "caption_only"), (1.0, "subtitle_only"), (a_star, "fused")):
        r = evaluate(qs, idx, al, c)
        out[f"mrr_{name}"] = r["metrics"]["mrr"]
        out[f"hit@1_{name}"] = r["metrics"]["hit@1"]
        out[f"rr_{name}"] = [x["mrr"] for x in r["per_query"]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["select", "confirm"], required=True)
    ap.add_argument("--model", help="confirm 단계에서 확증할 모델 하나")
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    side = "A" if a.stage == "select" else "B"
    idx0, qs, missing = load_side(cfg, a.queries, side)
    print(f"[{side} 절반] 영상 {len(idx0)}편 · 질의 {len(qs)}건 (인덱스 없음 {len(missing)}편)",
          flush=True)

    prereg = {"primary": "융합 MRR(모델별 α* A에서 재탐색)",
              "channel_isolation": "캡션 단독 α=0.0 · 자막 단독 α=1.0 병기",
              "select_rule": "현행 대비 Δ 최대이면서 BH-FDR q=0.05 통과. 없으면 현행 유지",
              "confirm_rule": "95% CI가 0 배제하고 부호가 1단계와 같으면 재현됨",
              "deferred": "접두어 필요 모델(e5·KoE5·Qwen3-Emb·arctic)은 2차",
              "declared_before_run": True}
    rep = {"note": "채택 아님. work_aihub 불변, dev·test 미접촉.", "stage": a.stage,
           "side": side, "split_seed": SPLIT_SEED, "prereg": prereg,
           "incumbent": INCUMBENT, "n_videos": len(idx0), "n_queries": len(qs),
           "arms": {}}

    models = CANDIDATES if a.stage == "select" else [INCUMBENT, a.model]
    if a.stage == "confirm" and not a.model:
        ap.error("--model 이 필요하다")

    for mid in models:
        try:
            rep["arms"][mid] = measure(mid, idx0, qs, cfg, cfg["alpha_grid"])
            m = rep["arms"][mid]
            print(f"[{mid}] α*={m['alpha_star']} 융합 {m['mrr_fused']:.4f} "
                  f"캡션 {m['mrr_caption_only']:.4f} 자막 {m['mrr_subtitle_only']:.4f}",
                  flush=True)
        except Exception as e:
            rep["arms"][mid] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[{mid}] 실패 — {type(e).__name__}: {e}", flush=True)

    base = rep["arms"].get(INCUMBENT, {})
    if "rr_fused" not in base:
        raise ValueError("현행 대조군이 실패했다 — 비교 불가")
    b = np.array(base["rr_fused"])
    contrasts, pvals, names = {}, [], []
    for mid, m in rep["arms"].items():
        if mid == INCUMBENT or "rr_fused" not in m:
            continue
        d = np.array(m["rr_fused"]) - b
        mean, lo, hi = boot_ci(d)
        p = perm_p(d)
        contrasts[mid] = {"delta": round(mean, 4), "ci95": [round(lo, 4), round(hi, 4)],
                          "perm_p": round(p, 4)}
        pvals.append(p)
        names.append(mid)
    if pvals:
        keep = bh_reject(np.array(pvals))
        for n, k in zip(names, keep):
            contrasts[n]["bh_pass"] = bool(k)
    rep["contrasts"] = contrasts

    if a.stage == "select":
        passed = [n for n in names if contrasts[n].get("bh_pass")]
        if passed:
            win = max(passed, key=lambda n: contrasts[n]["delta"])
            rep["verdict"] = f"1단계 승자: {win} (Δ{contrasts[win]['delta']:+.4f}). B에서 확증하라"
        else:
            rep["verdict"] = "선택 없음 — BH-FDR 통과 모델이 없다. 현행 유지, 2단계 불필요"
    else:
        c = contrasts.get(a.model, {})
        ok = c and (c["ci95"][0] > 0 or c["ci95"][1] < 0)
        rep["verdict"] = ("독립 절반에서 재현됨 — 채택 검토 가능" if ok
                          else "재현 실패 — 채택 근거 없음")

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"embedder_sweep_{a.stage}.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    for n, c in contrasts.items():
        print(f"  {n:38s} Δ{c['delta']:+.4f} CI[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
              f"p={c['perm_p']:.4f} BH={'통과' if c.get('bh_pass') else '탈락'}")
    print()
    print("판정:", rep["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
