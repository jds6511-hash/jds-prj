"""[캡션 모델 후보의 독립 확증 — AI Hub 제3자 데이터. 결과 생성 전 커밋]

**왜 이게 필요한가 — dev 스윕만으로는 못 정한다.**
1단계 dev 스윕에서 qwen3vl_4b/P1이 대조군을 이겼다(ΔMRR +0.0917, 보정 전 유의).
교차검증 A~E(영상 LOO·유형 기전·대체 지표·순열·시드)도 전부 통과했다. 그런데
**다중비교를 보정하면 14개 비교 중 살아남는 arm이 0개다** — Bonferroni는 물론
훨씬 덜 보수적인 Benjamini-Hochberg FDR(q=0.05)로도 전부 탈락한다(순열 p 순위
4위, p=0.0419, BH 임계 0.0143). 즉 dev 결과는 **선별 신호**이지 확증이 아니다.

교차검증 A~E는 이걸 구제하지 못한다. 그것들은 **같은 dev 96건**을 다시 자르는
안정성 검정이라 다중성 문제를 건드리지 않는다.

**설계 — 선택과 확증을 분리한다.**
  선택: dev 96건, 사전 등록 격자 16 arm → 승자 qwen3vl_4b/P1 (완료)
  확증: AI Hub 194편·1,086질의에서 **단 하나의 비교** (이 프로브)
비교가 하나뿐이므로 **보정할 다중성이 없다.** 그리고 표본이 완전히 독립이다 —
영상 194편이 전부 다르고, 도메인도 다르며(드라마·여행·요리), 질의를 **제3자가**
썼다. dev n=96의 검출 한계가 ±0.086인데 여기는 n=1,086이라 ±0.03 수준이다.

**대조군을 새로 생성하는 이유(규약 4항).** `work_aihub`에 이미 현행 모델 캡션이
있지만(2026-08-07 생성), 그것이 이 서버·이 라이브러리에서 만들어졌다는 것을
파일만 보고 확신할 수 없다. 생성 환경 효과는 실측 −0.093으로 후보 효과와 같은
크기라 이 의심을 남기면 안 된다. **같은 배치에서 두 arm을 모두 새로 만든다.**

**사전 등록 (실행 전 확정, 2026-08-09).**
  - 주지표: **캡션 단독 α=0.0 MRR** (dev 1단계의 주지표와 동일).
  - 비교는 **qwen3vl_4b/P1 vs qwen25_3b_4bit/P0 하나뿐**. 다른 arm을 추가하지 않는다.
  - 판정: 쌍체 부트스트랩 95% CI가 0을 포함하지 않고 **부호가 dev와 같으면**
    "독립 표본에서 재현됨". CI가 0을 포함하면 **"재현 실패 — 채택 근거 없음"** 으로
    보고한다. 결과를 보고 지표나 표본을 바꾸지 않는다.
  - 보조: 융합 α(dev 확정값) MRR, hit@1/@5, 도메인별 분해. **판정에는 안 쓴다.**
  - 캡션 생성 실패로 제외되는 영상이 생기면 편수·사유를 결과에 남긴다(침묵 금지).

work_aihub 인덱스 불변(재임베딩은 메모리에서만), 본 test 미접촉.
재현: python docs/probes/aihub_model_confirm.py
"""
import argparse, io, json, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs/probes"))
import common                                              # noqa: E402
from m4_index import embed_texts                           # noqa: E402
from m5_search import VideoIndex                           # noqa: E402
from m6_evaluate import evaluate                           # noqa: E402
from caption_model_sweep import MODELS, PROMPTS, load_captioner   # noqa: E402
from aihub_external_eval import load_external_queries      # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
CAPDIR = OUT / "aihub_confirm_captions"
CONTROL = ("qwen25_3b_4bit", "P0")      # 현행 설정 그대로, 같은 배치에서 새로 생성
CANDIDATE = ("qwen3vl_4b", "P1")        # dev 1단계 사전 등록 격자의 승자


def gen_or_load(mkey, pkey, vids, segs, wdirs, cfg, max_new=None):
    """arm 캡션을 만든다. 이미 저장돼 있고 세그먼트 수가 맞으면 재사용(재개용)."""
    f = CAPDIR / f"{mkey}__{pkey}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        if all(v in d and len(d[v]) == len(segs[v]) for v in vids):
            print(f"[{mkey}/{pkey}] 저장된 캡션 재사용", flush=True)
            return d
    cap, close = load_captioner(MODELS[mkey], cfg, max_new)
    t0 = time.time()
    try:
        caps = {}
        for n, v in enumerate(vids, 1):
            caps[v] = [cap(wdirs[v] / s["rep_frame"], PROMPTS[pkey]) for s in segs[v]]
            if n % 20 == 0:
                print(f"  {mkey}/{pkey} {n}/{len(vids)}편 "
                      f"({(time.time()-t0)/60:.1f}분)", flush=True)
    finally:
        close()
    CAPDIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(caps, ensure_ascii=False), encoding="utf-8")
    print(f"[{mkey}/{pkey}] 생성 완료 ({(time.time()-t0)/60:.1f}분) -> {f}", flush=True)
    return caps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    ap.add_argument("--alpha", type=float, default=None,
                    help="융합 보조지표용. 미지정 시 results/alpha_search_dev.json의 alpha_star")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    alpha = a.alpha
    if alpha is None:
        p = ROOT / "results/alpha_search_dev.json"
        alpha = json.loads(p.read_text(encoding="utf-8"))["alpha_star"] if p.exists() else 0.5

    qs_all = load_external_queries(ROOT / a.queries)
    idx0, missing = {}, []
    for v in sorted({q["video_id"] for q in qs_all}):
        try:
            idx0[v] = VideoIndex.load(cfg, v)
        except Exception as e:
            missing.append({"video_id": v, "error": f"{type(e).__name__}: {e}"})
    assert idx0, "인덱스가 하나도 없다"
    qs = [q for q in qs_all if q["video_id"] in idx0]
    vids = sorted(idx0)
    segs = {v: idx0[v].segments for v in vids}
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}
    n_frames = sum(len(segs[v]) for v in vids)
    print(f"영상 {len(vids)}편 · 세그먼트 {n_frames} · 질의 {len(qs)}건 "
          f"(제외 {len(missing)}편)", flush=True)

    rep = {"note": "채택 아님. dev에서 고른 후보의 독립 확증. work_aihub 불변, test 미접촉.",
           "prereg": {
               "primary": "캡션 단독 α=0.0 MRR",
               "comparison": f"{CANDIDATE[0]}/{CANDIDATE[1]} vs {CONTROL[0]}/{CONTROL[1]} 단 하나",
               "rule": ("95% CI가 0을 포함하지 않고 부호가 dev와 같으면 재현됨. "
                        "0을 포함하면 재현 실패 — 채택 근거 없음."),
               "why_single": "비교가 하나뿐이라 보정할 다중성이 없다(선택은 dev에서 끝났다)",
               "declared_before_run": True},
           "n_videos": len(vids), "n_queries": len(qs), "n_frames": n_frames,
           "excluded_videos": missing, "alpha_fused": alpha,
           "seed": cfg["seed"], "bootstrap_B": cfg["bootstrap_B"], "arms": {}}

    vec = {}
    for mkey, pkey in (CONTROL, CANDIDATE):
        caps = gen_or_load(mkey, pkey, vids, segs, wdirs, cfg)
        idx = {v: VideoIndex(segments=segs[v], emb_sub=idx0[v].emb_sub,
                             emb_cap=embed_texts(caps[v], cfg["embed_model"]),
                             static_mask=idx0[v].static_mask) for v in vids}
        blk = {"len_mean": round(float(np.mean([len(t) for v in vids for t in caps[v]])), 1),
               "corrupted": sum(1 for v in vids for t in caps[v]
                                if common.is_corrupted_caption(t))}
        for al, name in ((0.0, "caption_only"), (alpha, "fused")):
            r = evaluate(qs, idx, al, cfg)
            blk[f"mrr_{name}"] = r["metrics"]["mrr"]
            blk[f"hit@1_{name}"] = r["metrics"]["hit@1"]
            blk[f"hit@5_{name}"] = r["metrics"]["hit@5"]
            blk[f"by_type_{name}"] = {t: m["mrr"]
                                      for t, m in r["metrics"]["by_type"].items()}
            vec[(f"{mkey}/{pkey}", name)] = np.array([x["mrr"] for x in r["per_query"]])
            vec[(f"{mkey}/{pkey}", f"hit@1_{name}")] = np.array(
                [float(x["hit@1"]) for x in r["per_query"]])
        rep["arms"][f"{mkey}/{pkey}"] = blk
        print(f"[{mkey}/{pkey}] 길이 {blk['len_mean']} 오염 {blk['corrupted']} "
              f"캡션단독 {blk['mrr_caption_only']:.4f} 융합 {blk['mrr_fused']:.4f}",
              flush=True)

    ctl, cnd = f"{CONTROL[0]}/{CONTROL[1]}", f"{CANDIDATE[0]}/{CANDIDATE[1]}"
    n, B = len(qs), cfg["bootstrap_B"]
    ib = np.random.default_rng(cfg["seed"]).integers(0, n, size=(B, n))
    rep["contrasts"] = {}
    for key in ("caption_only", "fused", "hit@1_caption_only"):
        b, k = vec[(ctl, key)], vec[(cnd, key)]
        d = k[ib].mean(1) - b[ib].mean(1)
        lo, hi = np.percentile(d, [2.5, 97.5])
        rep["contrasts"][key] = {"delta": round(float(k.mean() - b.mean()), 4),
                                 "ci95": [round(float(lo), 4), round(float(hi), 4)],
                                 "significant": bool(lo > 0 or hi < 0)}

    pri = rep["contrasts"]["caption_only"]
    rep["verdict"] = ("독립 표본에서 재현됨 — 채택 검토 가능"
                      if pri["significant"] and pri["delta"] > 0 else
                      "재현 실패 — 채택 근거 없음"
                      if not pri["significant"] else
                      "부호 반전 — 채택 근거 없음")

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "aihub_model_confirm.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"주지표 ΔMRR {pri['delta']:+.4f} CI{pri['ci95']}")
    print("판정:", rep["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
