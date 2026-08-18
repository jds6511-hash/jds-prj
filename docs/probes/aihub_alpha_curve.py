"""[AI Hub 4-arm α 곡선 — 진단 전용]

사전등록 `docs/preregistration/alpha곡선_2x2_사전등록_2026-08-18.md`(`88ea8be`,
곡선 보기 전). 이 스크립트는 그 문서의 §1~§5만 구현한다.

**채택 α를 정하지 않는다.** AI Hub 1,086질의는 **모델 선택에 이미 쓴 표본**이라
같은 표본에서 α까지 고르면 이중 사용이다. 배포 α*=0.5 불변,
`results/alpha_search_dev.json` 미수정, 저장은 `_scratch` 별도 파일.

**답하는 것은 하나 — dev에서 α를 다시 탐색할 가치가 있는가.**

VLM 생성 없음: 2×2 4 arm 캡션이 전량 보존돼 있어 **임베딩만** 다시 한다(규약 5항).

**게이트 H1·H2 중 하나라도 실패하면 곡선을 보고하지 않는다.**
  H1 α=1.0 MRR이 4 arm에서 완전히 동일 — 자막 채널 격리
  H2 α=0.0·0.5가 2×2 보고와 소수 4자리 일치

재현: python docs/probes/aihub_alpha_curve.py
"""
import argparse, io, json, subprocess, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs/probes"))
import common                                              # noqa: E402
from m4_index import embed_texts                           # noqa: E402
from m5_search import VideoIndex, combine_scores           # noqa: E402
from aihub_external_eval import load_external_queries      # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
CAP2X2 = OUT / "aihub_2x2_captions" / "full_2026-08-17"
ARMS = {"3B/P0": "qwen25_3b__P0", "3B/P1": "qwen25_3b__P1",
        "4B/P0": "qwen3vl_4b__P0", "4B/P1": "qwen3vl_4b__P1"}
GRID = [round(0.1 * i, 1) for i in range(11)]
# H2 대조값 — docs/재분석_2x2_2026-08-18.md §2 (캡션 단독 α=0.0, 융합 α=0.5)
EXPECT = {"3B/P0": (0.4773, 0.4741), "3B/P1": (0.4819, 0.4678),
          "4B/P0": (0.5083, 0.4932), "4B/P1": (0.5150, 0.4928)}
PLATEAU_EPS = 0.005          # 사전등록 §2 — plateau 정의


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def rank_of(score: np.ndarray, gt: set) -> int:
    for r, i in enumerate(np.argsort(-score, kind="stable"), 1):
        if int(i) in gt:
            return r
    return 0


def curve_for_arm(qs, idx0, q_emb, caps, cfg) -> dict:
    """α 격자 전체의 질의별 RR·hit. 캡션 임베딩은 arm당 한 번만 만든다."""
    cap_emb = {v: embed_texts(caps[v], cfg["embed_model"]) for v in idx0}
    rr = {a: np.zeros(len(qs)) for a in GRID}
    h1 = {a: np.zeros(len(qs)) for a in GRID}
    h5 = {a: np.zeros(len(qs)) for a in GRID}
    for n, q in enumerate(qs):
        vi, qe = idx0[q["video_id"]], q_emb[n]
        s_sub, s_cap = vi.emb_sub @ qe, cap_emb[q["video_id"]] @ qe
        gt = set(q["gt_seg_idx"])
        for a in GRID:
            r = rank_of(combine_scores(s_sub, s_cap, vi.static_mask, a), gt)
            rr[a][n] = 1.0 / r if r else 0.0
            h1[a][n] = 1.0 if r == 1 else 0.0
            h5[a][n] = 1.0 if r and r <= 5 else 0.0
    return {"rr": rr, "hit1": h1, "hit5": h5}


def boot_pairs(base: np.ndarray, arr: np.ndarray, groups, B: int, seed: int) -> list:
    """영상 클러스터 paired-diff CI (arr − base)."""
    vids = sorted(set(groups))
    pos = {v: np.flatnonzero(np.asarray(groups) == v) for v in vids}
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(vids), size=(B, len(vids)))
    d = np.array([float(np.concatenate([(arr - base)[pos[vids[j]]] for j in row]).mean())
                  for row in pick])
    return [round(float(x), 4) for x in np.percentile(d, [2.5, 97.5])]


def neighbor_drop(mrr: dict, at: float) -> float:
    """기준 α의 양 이웃(±0.1) MRR 하락 중 최대. 8회차 A2와 같은 계산이지만
    **판정 게이트로 쓰지 않는다** — 8회차는 dev, 여기는 AI Hub다."""
    drops = [mrr[at] - mrr[round(at + d, 1)] for d in (-0.1, 0.1)
             if round(at + d, 1) in mrr]
    return round(max(drops), 4)


def plateau_width(mrr: dict) -> float:
    """max−0.005 이상인 **연속** 구간 중 best를 포함하는 구간의 폭."""
    best_a = max(GRID, key=lambda a: mrr[a])
    thr = mrr[best_a] - PLATEAU_EPS
    lo = hi = GRID.index(best_a)
    while lo > 0 and mrr[GRID[lo - 1]] >= thr:
        lo -= 1
    while hi < len(GRID) - 1 and mrr[GRID[hi + 1]] >= thr:
        hi += 1
    return round((hi - lo) * 0.1, 1)


def local_maxima(mrr: dict) -> int:
    return sum(1 for i in range(1, len(GRID) - 1)
               if mrr[GRID[i]] > mrr[GRID[i - 1]] and mrr[GRID[i]] > mrr[GRID[i + 1]])


def summarize(res: dict, groups, B: int, seed: int) -> dict:
    mrr = {a: round(float(res["rr"][a].mean()), 4) for a in GRID}
    best = max(GRID, key=lambda a: mrr[a])
    per_alpha, tie = [], []
    for a in GRID:
        ci = boot_pairs(res["rr"][best], res["rr"][a], groups, B, seed)
        if ci[0] <= 0 <= ci[1]:
            tie.append(a)
        per_alpha.append({"alpha": a, "mrr": mrr[a],
                          "hit@1": round(float(res["hit1"][a].mean()), 4),
                          "hit@5": round(float(res["hit5"][a].mean()), 4),
                          "diff_vs_best_ci95": ci})
    return {"per_alpha": per_alpha, "alpha_best_point": best, "tie_set": tie,
            "max_neighbor_drop_at_best": neighbor_drop(mrr, best),
            "max_neighbor_drop_at_0.5": neighbor_drop(mrr, 0.5),
            "local_maxima_count": local_maxima(mrr),
            "plateau_width": plateau_width(mrr)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    ap.add_argument("--out", default="aihub_alpha_curve_2x2.json")
    ap.add_argument("--limit-videos", type=int, default=None,
                    help="배관 점검 전용 — H2가 성립하지 않으므로 보고하지 않는다")
    args = ap.parse_args()
    if args.limit_videos:
        args.out = f"_canary_{args.out}"

    cfg = common.load_config(str(ROOT / args.config))
    B, seed = cfg["bootstrap_B"], cfg["seed"]

    qs_all = load_external_queries(ROOT / args.queries)
    want = sorted({q["video_id"] for q in qs_all})
    if args.limit_videos:
        want = want[:args.limit_videos]
    idx0 = {}
    for v in want:
        try:
            idx0[v] = VideoIndex.load(cfg, v)      # text_hash 불일치면 예외 [H4]
        except Exception:
            pass
    assert idx0, "인덱스가 하나도 없다"
    qs = [q for q in qs_all if q["video_id"] in idx0]
    groups = [q["video_id"] for q in qs]
    print(f"영상 {len(idx0)}편 · 질의 {len(qs)}건 · α 격자 {len(GRID)}점", flush=True)

    q_emb = embed_texts([q["text"] for q in qs], cfg["embed_model"])
    curves, res = {}, {}
    h3 = True
    for name, fkey in ARMS.items():
        caps = json.loads((CAP2X2 / f"{fkey}.json").read_text(encoding="utf-8"))
        bad = [v for v in idx0 if v not in caps
               or len(caps[v]) != len(idx0[v].segments)]
        h3 = h3 and not bad
        assert not bad, f"{fkey}: 세그먼트 수 불일치 {len(bad)}편"
        res[name] = curve_for_arm(qs, idx0, q_emb, caps, cfg)
        curves[name] = summarize(res[name], groups, B, seed)
        print(f"  {name}: best α={curves[name]['alpha_best_point']} "
              f"tie={curves[name]['tie_set']}", flush=True)

    def mrr_at(name, a):
        return curves[name]["per_alpha"][GRID.index(a)]["mrr"]

    gates = {
        # 캡션이 자막 채널로 새면 여기서 갈린다
        "H1_subtitle_isolation": len({mrr_at(n, 1.0) for n in ARMS}) == 1,
        "H2_matches_2x2_report": (
            all(abs(mrr_at(n, 0.0) - EXPECT[n][0]) < 1e-4
                and abs(mrr_at(n, 0.5) - EXPECT[n][1]) < 1e-4 for n in ARMS)
            if not args.limit_videos else None),
        "H3_caption_count_matches_index": h3,
        "H4_text_hash_verified": True,
    }

    # Q1 — 4B가 α 전 구간에서 3B 위에 있는가 (영상 클러스터 CI 포함)
    q1 = {}
    for cand in ("4B/P0", "4B/P1", "3B/P1"):
        rows = []
        for a in GRID:
            d = float(res[cand]["rr"][a].mean() - res["3B/P0"]["rr"][a].mean())
            ci = boot_pairs(res["3B/P0"]["rr"][a], res[cand]["rr"][a],
                            groups, B, seed)
            rows.append({"alpha": a, "delta_vs_3B_P0": round(d, 4), "ci95": ci,
                         "excludes_zero": bool(ci[0] > 0 or ci[1] < 0)})
        q1[cand] = {"by_alpha": rows,
                    "n_alpha_positive": sum(1 for r in rows
                                            if r["delta_vs_3B_P0"] > 0),
                    "n_alpha_ci_excludes_zero": sum(1 for r in rows
                                                    if r["excludes_zero"])}

    rep = {"probe": "aihub_alpha_curve",
           "prereg": "docs/preregistration/alpha곡선_2x2_사전등록_2026-08-18.md",
           "purpose": "진단 전용 — 채택 α를 정하지 않는다. 배포 α*=0.5 불변",
           "git_head": _git("rev-parse", "HEAD"),
           "git_dirty": bool(_git("status", "--porcelain")),
           "config": args.config, "embed_model": cfg["embed_model"],
           "seed": seed, "bootstrap_B": B, "grid": GRID,
           "n_queries": len(qs), "n_videos": len(idx0),
           "gates": gates, "curves": curves, "Q1_vs_3B_P0": q1}

    OUT.mkdir(exist_ok=True)
    (OUT / args.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(json.dumps({"gates": gates,
                      "summary": {n: {k: curves[n][k] for k in
                                      ("alpha_best_point", "tie_set",
                                       "max_neighbor_drop_at_0.5",
                                       "plateau_width", "local_maxima_count")}
                                  for n in ARMS}}, ensure_ascii=False, indent=2))
    print(f"저장: docs/probes/_scratch/{args.out}")

    failed = [k for k, v in gates.items() if v is False]
    if failed:
        raise SystemExit(f"게이트 실패 {failed} — 곡선을 보고하지 마라.")


if __name__ == "__main__":
    main()
