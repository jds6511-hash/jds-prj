"""[AI Hub 2단계 — dev 상위 모델을 검정력 있는 표본에서 비교 (결과 전 커밋)]

**왜 dev로는 안 되는가.** dev 96의 검출 한계는 **±0.086**이다. 캡션 스윕에서 21 arm을
돌렸을 때 BH-FDR을 통과한 arm이 **0개**였다. arm을 늘릴수록 임계가 더 빡빡해지므로
dev에서 모델을 고르는 것은 대부분 노이즈 최대값을 고르는 일이다. **dev는 선별
전용이고, 유의성 주장을 하지 않는다.**

**AI Hub A 절반에서 비교한다.** 97영상·562질의로 dev의 6배다. B 절반은 최종 확증용
으로 남긴다(임베더 스윕과 같은 분할·같은 시드, `embedder_sweep.py`).

**선택 규칙을 사람이 개입하지 않고 스크립트가 적용한다** — 새벽에 무인으로 돌기
때문이다. 결과를 보고 고르는 경로를 아예 없앤다.

**사전 등록한 규칙 (결과 보기 전 확정, 2026-08-10).**
  - 선별 지표 = **dev 캡션 단독 α=0.0 MRR**. AI Hub 확증·환경 검증과 같은 지표를
    쓴다(지표 변경 금지, 규약 1항 채널 격리와도 일치).
  - **모델별 최고 prompt를 뽑고, 그 중 상위 K개 모델**(기본 K=3)을 A 절반에 올린다.
    현행(`qwen25_3b_4bit`)과 빈 캡션으로 제외된 모델(`kanana_3b`)은 후보에서 뺀다.
  - 대조군은 **저장된 서버 생성 현행 캡션**(`aihub_confirm_captions`)을 A 절반으로
    잘라 쓴다. 같은 기계·같은 설정이고, **서버 두 배치가 서로 98.0% 일치**한다는 것을
    오늘 실측했으므로 배치 간 재생성이 불필요하다(규약 4항의 취지는 충족).
  - 비교는 **쌍체 부트스트랩 + 순열검정**, 다중성은 **BH-FDR q=0.05**.
  - 통과 모델이 없으면 "선택 없음 — 현행 유지"로 끝내고 B 절반을 쓰지 않는다.
  - 결과를 보고 지표·K·임계값을 바꾸지 않는다.

**시간이 모자라면 순위대로 채운다.** arm 하나가 1,164 프레임이라 40~175분 걸린다.
중간에 끊겨도 완료된 arm은 JSON에 남고, 다음 실행이 캐시된 캡션을 재사용한다.

work_aihub 인덱스 불변(재임베딩은 메모리에서만), dev·test 미접촉.
재현: python docs/probes/aihub_stage2.py [--top-k 3]
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
from aihub_model_confirm import gen_or_load                # noqa: E402
from embedder_sweep import bh_reject, load_side            # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
SWEEP = OUT / "caption_sweep.json"
CONTROL_CAPS = OUT / "aihub_confirm_captions" / "qwen25_3b_4bit__P0.json"
EXCLUDE = {"qwen25_3b_4bit", "kanana_3b", "cur_laptop"}
SEL_METRIC = "mrr_caption_only"
B, PERM_N, SEED = 20_000, 200_000, 42


def pick_top(k):
    """dev 스윕에서 모델별 최고 prompt를 뽑고 상위 k개 모델을 고른다."""
    arms = json.loads(SWEEP.read_text(encoding="utf-8"))["arms"]
    best = {}
    for key, v in arms.items():
        m, _, p = key.partition("/")
        if m in EXCLUDE or not p or SEL_METRIC not in v:
            continue
        if m not in best or v[SEL_METRIC] > best[m][1]:
            best[m] = (p, v[SEL_METRIC])
    ranked = sorted(best.items(), key=lambda kv: -kv[1][1])
    return [(m, p, s) for m, (p, s) in ranked[:k]], ranked


def stat(d):
    rng = np.random.default_rng(SEED)
    m = d[rng.integers(0, len(d), size=(B, len(d)))].mean(1)
    sg = rng.choice([-1.0, 1.0], size=(PERM_N, len(d)))
    return (float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)),
            float((np.abs((sg * d).mean(1)) >= abs(d.mean())).mean()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    idx0, qs, missing = load_side(cfg, a.queries, "A")
    vids = sorted(idx0)
    segs = {v: idx0[v].segments for v in vids}
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}
    print(f"[A 절반] 영상 {len(vids)} · 질의 {len(qs)} · 세그먼트 "
          f"{sum(len(segs[v]) for v in vids)}", flush=True)

    top, ranked = pick_top(a.top_k)
    print("dev 순위(모델별 최고 prompt):", flush=True)
    for m, (p, s) in ranked:
        mark = " <=선택" if any(m == t[0] for t in top) else ""
        print(f"  {m:20s} {p:8s} {s:.4f}{mark}", flush=True)

    ctl = json.loads(CONTROL_CAPS.read_text(encoding="utf-8"))
    missing_ctl = [v for v in vids if v not in ctl]
    if missing_ctl:
        raise ValueError(f"대조군 캡션 없음 {len(missing_ctl)}편 — 먼저 확증 실행 필요")

    def score(caps):
        idx = {v: VideoIndex(segments=segs[v], emb_sub=idx0[v].emb_sub,
                             emb_cap=embed_texts(caps[v], cfg["embed_model"],
                                                 cfg["embed_batch_size"]),
                             static_mask=idx0[v].static_mask) for v in vids}
        r = evaluate(qs, idx, 0.0, cfg)
        return r["metrics"], np.array([x["mrr"] for x in r["per_query"]])

    rep = {"note": "AI Hub A 절반 비교. B는 확증용으로 남긴다. dev·test 미접촉.",
           "prereg": {"select_metric": f"dev {SEL_METRIC}",
                      "select_rule": f"모델별 최고 prompt, 상위 {a.top_k}개",
                      "control": "저장된 서버 생성 현행 캡션(서버 배치 간 98.0% 일치 실측)",
                      "multiplicity": "BH-FDR q=0.05",
                      "declared_before_run": True},
           "dev_ranking": [{"model": m, "prompt": p, "dev_mrr": s} for m, (p, s) in ranked],
           "selected": [{"model": m, "prompt": p, "dev_mrr": s} for m, p, s in top],
           "n_videos": len(vids), "n_queries": len(qs), "arms": {}}

    m0, rr0 = score({v: ctl[v] for v in vids})
    rep["arms"]["qwen25_3b_4bit/P0 (대조군)"] = {"mrr_caption_only": m0["mrr"],
                                               "hit@1": m0["hit@1"]}
    print(f"[대조군] 캡션단독 {m0['mrr']:.4f}", flush=True)

    contrasts, pv, names = {}, [], []
    for mkey, pkey, dev_s in top:
        maxnew = 256 if "@256" in pkey else None
        pbase = pkey.split("@")[0]
        try:
            caps = gen_or_load(mkey, pbase, vids, segs, wdirs, cfg, max_new=maxnew)
            met, rr = score(caps)
        except Exception as e:
            rep["arms"][f"{mkey}/{pkey}"] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
            print(f"[{mkey}/{pkey}] 실패 — {type(e).__name__}: {str(e)[:160]}", flush=True)
            continue
        rep["arms"][f"{mkey}/{pkey}"] = {"mrr_caption_only": met["mrr"],
                                         "hit@1": met["hit@1"], "dev_mrr": dev_s}
        d = rr - rr0
        mean, lo, hi, p = stat(d)
        contrasts[f"{mkey}/{pkey}"] = {"delta": round(mean, 4),
                                       "ci95": [round(lo, 4), round(hi, 4)],
                                       "perm_p": round(p, 4)}
        pv.append(p)
        names.append(f"{mkey}/{pkey}")
        print(f"[{mkey}/{pkey}] 캡션단독 {met['mrr']:.4f}  Δ{mean:+.4f} "
              f"CI[{lo:+.4f},{hi:+.4f}] p={p:.4f}", flush=True)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "aihub_stage2.json").write_text(
            json.dumps({**rep, "contrasts": contrasts}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    if pv:
        keep = bh_reject(np.array(pv))
        for n, k in zip(names, keep):
            contrasts[n]["bh_pass"] = bool(k)
    rep["contrasts"] = contrasts
    passed = [n for n in names if contrasts[n].get("bh_pass")]
    if passed:
        win = max(passed, key=lambda n: contrasts[n]["delta"])
        rep["verdict"] = (f"2단계 통과: {win} (Δ{contrasts[win]['delta']:+.4f}). "
                          "B 절반에서 확증하라")
    else:
        rep["verdict"] = "선택 없음 — BH-FDR 통과 모델이 없다. 현행 유지, B 절반 미사용"

    p_out = OUT / "aihub_stage2.json"
    p_out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print("판정:", rep["verdict"])
    print("->", p_out)


if __name__ == "__main__":
    main()
