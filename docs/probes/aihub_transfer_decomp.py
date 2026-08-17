"""[AI Hub 1,086 — per_query 복원 + video-cluster bootstrap + 융합 전달 분해]

**왜 필요한가 (2026-08-17 자체 감사 §3, docs/감사_2026-08-17.md).**
aihub_model_confirm.py는 per_query를 메모리에서만 쓰고 저장하지 않았다. 그래서
두 가지를 사후에 확인할 수 없었다.

  (1) **CI 재표집 단위.** 보고된 CI는 전부 질의 단위다. AI Hub는 194영상에
      1,086질의가 중첩돼 있어 같은 영상의 질의가 상관되면 CI가 실제보다 좁다.
      **영상을 재표집 단위로 하는 video-cluster bootstrap이 필요하다.**
  (2) **융합 전달 실패의 구조.** caption-only는 개선인데 융합은 약해지는 이유를
      "희석"이라 불렀지만 그건 현상 기술이다. 질의별로 갈라 봐야 한다.

VLM 재생성은 하지 않는다 — arm별 캡션이 _scratch/aihub_confirm_captions/에
전량 보존돼 있다(규약 5항). **임베딩만 다시 한다.**

**자기검증 게이트 (결과 해석 전에 통과해야 함).**
같은 arm 짝을 질의 단위로 재집계했을 때 저장된 사전등록 결과
(_scratch/aihub_model_confirm.json: caption_only +0.0342, fused +0.0233)를
소수 4자리까지 재현해야 한다. 재현 실패면 이 스크립트의 재구성이 틀린 것이므로
아래 어떤 수치도 보고하지 않는다. --require-reproduce 로 강제(기본 on).

**측정하는 것.**
  per_query: 세 α(0.0 캡션단독 / α* 융합 / 1.0 자막단독)에서 GT 순위·RR·hit@1
  margin:    각 채널 z-정규화 점수에서  max(GT) − max(비GT)
             = "GT를 1위로 만드는 데 남은 여유". 순위보다 연속적이라 개선의
             크기를 본다. 융합에 들어가는 값 그대로(static 치환 이후) 계산한다.
  버킷:      caption-only 순위가 오른 질의를 융합 순위 변화로 3분할
             (개선 전달 / 무변화 / 역전) — 자문 지적의 직접 검정
  자막 강도:  AI Hub 질의에는 자막형·장면형 유형 라벨이 없다(도메인 라벨만).
             그래서 **자막 단독 순위**를 유형 프록시로 쓴다(1위면 자막이 이미
             충분한 질의). 이건 유형 라벨의 대체물이지 같은 것이 아니다.

**하지 않는 것.** 채택 판정을 바꾸지 않는다. work_aihub 인덱스 불변(재임베딩은
메모리에서만). test 미접촉. 사전등록 주지표를 바꾸지 않는다 — cluster CI는
**보고된 CI의 유효성 점검**이지 새 주지표가 아니다.

**남는 한계 (이 스크립트로 해소되지 않음).** 두 arm은 3B/P0 과 4B/P1 이라
모델 효과와 프롬프트 효과가 분리되지 않는다. 여기서 나오는 것은 전부
configuration effect다. 분리에는 3B/P1 arm이 필요하다.

재현: python docs/probes/aihub_transfer_decomp.py
"""
import argparse, io, json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs/probes"))
import common                                              # noqa: E402
from m4_index import embed_texts                           # noqa: E402
from m5_search import VideoIndex, combine_scores, zscore    # noqa: E402
from aihub_external_eval import load_external_queries      # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
CAPDIR = OUT / "aihub_confirm_captions"
# 사전등록 결과와 대조할 기준 파일 — arm 키가 캡션 파일명과 일치해야 한다
REPRO = {"aihub_model_confirm.json": ("qwen25_3b_4bit/P0", "qwen3vl_4b/P1"),
         "aihub_confirm_bf16matched.json": ("qwen25_3b/P0", "qwen3vl_4b/P1")}


def load_arm_captions(arm: str, vids, segs) -> dict:
    """저장된 arm 캡션 로드. 생성은 하지 않는다 — 없으면 실패시킨다."""
    mkey, pkey = arm.split("/", 1)
    f = CAPDIR / f"{mkey}__{pkey}.json"
    if not f.is_file():
        raise FileNotFoundError(
            f"{f} 없음 — 이 arm의 캡션이 로컬에 보존돼 있지 않다. "
            f"서버 _scratch/aihub_confirm_captions/ 에서 가져와야 한다.")
    d = json.loads(f.read_text(encoding="utf-8"))
    bad = [v for v in vids if v not in d or len(d[v]) != len(segs[v])]
    assert not bad, f"{f}: 세그먼트 수 불일치 영상 {len(bad)}편 (예: {bad[:3]})"
    return d


def margin(sn: np.ndarray, gt: set) -> float:
    """max(GT) − max(비GT). 양수면 GT가 1위. 비GT가 없으면 정의 불가(None)."""
    g = [sn[i] for i in range(len(sn)) if i in gt]
    o = [sn[i] for i in range(len(sn)) if i not in gt]
    if not g or not o:
        return None
    return float(max(g) - max(o))


def rank_of(score: np.ndarray, gt: set) -> int:
    """m5_search와 동일한 정렬(안정 정렬 · -score)로 GT 최상위 순위. 1-based."""
    for r, i in enumerate(np.argsort(-score, kind="stable"), 1):
        if int(i) in gt:
            return r
    return 0


def per_query_rows(qs, idx0, caps, q_emb, alpha, cfg) -> list[dict]:
    """질의별 세 α의 순위·RR·hit@1 + 채널 margin. 채널 점수는 융합에 들어가는
    값 그대로(z-정규화 + static 치환 이후)."""
    cap_emb = {v: embed_texts(caps[v], cfg["embed_model"]) for v in idx0}
    rows = []
    for n, q in enumerate(qs):
        v = q["video_id"]
        vi, qe = idx0[v], q_emb[n]
        s_sub, s_cap = vi.emb_sub @ qe, cap_emb[v] @ qe
        gt = set(q["gt_seg_idx"])
        sub_n = zscore(s_sub)
        cap_n = zscore(s_cap).copy()
        cap_n[vi.static_mask] = sub_n[vi.static_mask]   # combine_scores와 동일 [8-4]
        row = {"query_id": q["query_id"], "video_id": v, "domain": q["type"],
               "n_seg": len(vi.segments),
               "margin_cap": margin(cap_n, gt), "margin_sub": margin(sub_n, gt)}
        for al, name in ((0.0, "cap"), (alpha, "fus"), (1.0, "sub")):
            sc = combine_scores(s_sub, s_cap, vi.static_mask, al)
            r = rank_of(sc, gt)
            row[f"rank_{name}"] = r
            row[f"rr_{name}"] = 1.0 / r if r else 0.0
            row[f"hit1_{name}"] = 1.0 if r == 1 else 0.0
        row["margin_fus"] = margin(
            combine_scores(s_sub, s_cap, vi.static_mask, alpha), gt)
        rows.append(row)
    return rows


def boot_query(b: np.ndarray, k: np.ndarray, B: int, seed: int) -> dict:
    """질의 단위 쌍체 부트스트랩 — 기존 보고와 같은 방식(재현 검증용)."""
    n = len(b)
    ib = np.random.default_rng(seed).integers(0, n, size=(B, n))
    d = k[ib].mean(1) - b[ib].mean(1)
    lo, hi = (float(x) for x in np.percentile(d, [2.5, 97.5]))
    return {"unit": "query", "n_unit": n, "delta": round(float(k.mean() - b.mean()), 4),
            "ci95": [round(lo, 4), round(hi, 4)], "excludes_zero": bool(lo > 0 or hi < 0)}


def boot_cluster(b, k, groups, B: int, seed: int, macro: bool = False) -> dict:
    """영상 단위 쌍체 부트스트랩. 영상을 복원추출하고 선택된 영상의 전 질의를
    함께 넣는다. macro=False면 질의가중(원래 estimand 유지), True면 영상 평균의
    평균(video-macro MRR)."""
    vids = sorted(set(groups))
    pos = {v: np.flatnonzero(np.asarray(groups) == v) for v in vids}
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(vids), size=(B, len(vids)))

    def stat(arr, chosen):
        if macro:
            return float(np.mean([arr[pos[vids[j]]].mean() for j in chosen]))
        return float(np.concatenate([arr[pos[vids[j]]] for j in chosen]).mean())

    d = np.array([stat(k, row) - stat(b, row) for row in pick])
    lo, hi = (float(x) for x in np.percentile(d, [2.5, 97.5]))
    if macro:
        pt = (float(np.mean([k[p].mean() for p in pos.values()]))
              - float(np.mean([b[p].mean() for p in pos.values()])))
    else:
        pt = float(k.mean() - b.mean())
    return {"unit": "video-macro" if macro else "video-cluster",
            "n_unit": len(vids), "delta": round(pt, 4),
            "ci95": [round(lo, 4), round(hi, 4)], "excludes_zero": bool(lo > 0 or hi < 0)}


def transfer_buckets(ctl, cnd) -> dict:
    """caption-only 순위 변화 × 융합 순위 변화 교차 분류.
    미발견(rank=0)은 최악으로 취급해 n_seg+1로 환산한다."""
    def rk(r, key):
        return r[key] if r[key] else r["n_seg"] + 1

    cells, rows = {}, []
    for b, k in zip(ctl, cnd):
        dc = rk(b, "rank_cap") - rk(k, "rank_cap")     # >0 = 후보가 개선
        df = rk(b, "rank_fus") - rk(k, "rank_fus")
        cap = "cap_up" if dc > 0 else "cap_down" if dc < 0 else "cap_same"
        fus = "fus_up" if df > 0 else "fus_down" if df < 0 else "fus_same"
        cells[(cap, fus)] = cells.get((cap, fus), 0) + 1
        rows.append((b, k, cap, fus, dc, df))

    def blk(sel):
        s = [(b, k) for b, k, c, f, _, _ in rows if sel(c, f)]
        if not s:
            return {"n": 0}
        return {"n": len(s),
                "sub_rank1_share": round(np.mean([b["rank_sub"] == 1 for b, _ in s]), 3),
                "mean_margin_sub_ctl": round(float(np.mean([b["margin_sub"] for b, _ in s
                                                            if b["margin_sub"] is not None])), 4),
                "mean_dmargin_cap": round(float(np.mean([k["margin_cap"] - b["margin_cap"]
                                                         for b, k in s])), 4),
                "mean_dmargin_fus": round(float(np.mean([k["margin_fus"] - b["margin_fus"]
                                                         for b, k in s])), 4),
                "domains": {d: sum(1 for b, _ in s if b["domain"] == d)
                            for d in sorted({b["domain"] for b, _ in s})}}

    dcap = np.array([rk(b, "rank_cap") - rk(k, "rank_cap") for b, k, *_ in rows], float)
    dfus = np.array([rk(b, "rank_fus") - rk(k, "rank_fus") for b, k, *_ in rows], float)
    dmc = np.array([k["margin_cap"] - b["margin_cap"] for b, k, *_ in rows])
    dmf = np.array([k["margin_fus"] - b["margin_fus"] for b, k, *_ in rows])
    return {
        "crosstab": {f"{c}|{f}": n for (c, f), n in sorted(cells.items())},
        "cap_up_fus_same": blk(lambda c, f: c == "cap_up" and f == "fus_same"),
        "cap_up_fus_up": blk(lambda c, f: c == "cap_up" and f == "fus_up"),
        "cap_up_fus_down": blk(lambda c, f: c == "cap_up" and f == "fus_down"),
        "cap_same_or_down": blk(lambda c, f: c != "cap_up"),
        "corr_rank_delta": round(float(np.corrcoef(dcap, dfus)[0, 1]), 3),
        "corr_margin_delta": round(float(np.corrcoef(dmc, dmf)[0, 1]), 3),
        "mean_dmargin_cap_all": round(float(dmc.mean()), 4),
        "mean_dmargin_fus_all": round(float(dmf.mean()), 4),
    }


def icc1(ctl, cnd, key: str) -> dict:
    """쌍체 차이의 영상내 상관 ICC(1)과 설계효과. 클러스터 보정이 필요한지를
    부트스트랩 결과와 독립적으로 판정한다 — 설계효과 ≤1이면 질의 단위 CI가
    좁은 것이 아니다(오히려 보수적)."""
    g = {}
    for b, k in zip(ctl, cnd):
        g.setdefault(b["video_id"], []).append(k[key] - b[key])
    grp = [np.array(v) for v in g.values() if len(v) > 1]
    allv = np.concatenate(grp)
    n, K, gm = len(allv), len(grp), allv.mean()
    msb = sum(len(x) * (x.mean() - gm) ** 2 for x in grp) / (K - 1)
    msw = sum(((x - x.mean()) ** 2).sum() for x in grp) / (n - K)
    m = float(np.mean([len(x) for x in grp]))
    icc = (msb - msw) / (msb + (m - 1) * msw)
    return {"icc1": round(float(icc), 4), "mean_cluster_size": round(m, 2),
            "design_effect": round(1 + (m - 1) * float(icc), 3),
            "cluster_adjustment_needed": bool(1 + (m - 1) * float(icc) > 1.0)}


def saturation_adjusted(ctl, cnd) -> dict:
    """arm 대칭 포화 제거 후 전달률. 포화 = 양쪽 모두 융합 rank 1(두 arm을 구분할
    수 없는 질의) — m6_evaluate의 contested 정의와 같다. 기준값만으로 조건화하면
    Δfus가 상향 편향되므로 대칭 조건을 쓴다."""
    def strat(b):
        if b["rank_sub"] == 1:
            return "sub_rank1"
        return "sub_rank2_5" if 2 <= b["rank_sub"] <= 5 else "sub_rank6plus_or_miss"

    out = {}
    for s in ("ALL", "sub_rank1", "sub_rank2_5", "sub_rank6plus_or_miss"):
        p = [(b, k) for b, k in zip(ctl, cnd) if s == "ALL" or strat(b) == s]
        con = [(b, k) for b, k in p
               if not (b["rank_fus"] == 1 and k["rank_fus"] == 1)]
        dc = float(np.mean([k["rr_cap"] - b["rr_cap"] for b, k in con]))
        df = float(np.mean([k["rr_fus"] - b["rr_fus"] for b, k in con]))
        out[s] = {"n": len(p), "n_saturated": len(p) - len(con), "n_contested": len(con),
                  "d_mrr_cap": round(dc, 4), "d_mrr_fus": round(df, 4),
                  "transfer_pct": round(df / dc * 100, 1) if dc else None}
    return out


def by_group(ctl, cnd) -> dict:
    """도메인·질의수 구간별로 영상평균 Δ와 질의가중 Δ를 나란히 본다.
    video-macro 추정이 질의가중보다 작은 이유를 귀속하기 위한 분해."""
    g = {}
    for b, k in zip(ctl, cnd):
        g.setdefault(b["video_id"], []).append((k["rr_cap"] - b["rr_cap"], b["domain"]))
    vids = sorted(g)
    dv = np.array([np.mean([x[0] for x in g[v]]) for v in vids])
    nq = np.array([len(g[v]) for v in vids])
    dom = {v: g[v][0][1] for v in vids}

    def blk(mask):
        if not mask.any():
            return {"n_videos": 0}
        return {"n_videos": int(mask.sum()), "n_queries": int(nq[mask].sum()),
                "d_video_macro": round(float(dv[mask].mean()), 4),
                "d_query_weighted": round(float((dv[mask] * nq[mask]).sum()
                                                / nq[mask].sum()), 4)}

    return {
        "videos_improved": int((dv > 0).sum()), "videos_worse": int((dv < 0).sum()),
        "videos_tied": int((dv == 0).sum()),
        "corr_nqueries_delta": round(float(np.corrcoef(nq, dv)[0, 1]), 3),
        "by_domain": {d: blk(np.array([dom[v] == d for v in vids]))
                      for d in sorted(set(dom.values()))},
        "by_nqueries": {f"{lo}-{hi}": blk((nq >= lo) & (nq <= hi))
                        for lo, hi in ((2, 3), (4, 5), (6, 8), (9, 14))},
    }


def by_sub_strength(ctl, cnd) -> dict:
    """자막 단독 순위를 유형 프록시로 쓴 층별 ΔMRR. 자막이 이미 GT를 1위로
    두는 질의에서는 캡션 개선이 최종 순위를 바꿀 여지가 작다는 가설의 검정."""
    out = {}
    for name, sel in (("sub_rank1", lambda b: b["rank_sub"] == 1),
                      ("sub_rank2_5", lambda b: 2 <= b["rank_sub"] <= 5),
                      ("sub_rank6plus_or_miss",
                       lambda b: b["rank_sub"] == 0 or b["rank_sub"] > 5)):
        s = [(b, k) for b, k in zip(ctl, cnd) if sel(b)]
        if not s:
            out[name] = {"n": 0}
            continue
        out[name] = {"n": len(s),
                     "d_mrr_cap": round(float(np.mean([k["rr_cap"] - b["rr_cap"]
                                                       for b, k in s])), 4),
                     "d_mrr_fus": round(float(np.mean([k["rr_fus"] - b["rr_fus"]
                                                       for b, k in s])), 4)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    ap.add_argument("--control", default="qwen25_3b_4bit/P0")
    ap.add_argument("--candidate", default="qwen3vl_4b/P1")
    ap.add_argument("--alpha", type=float, default=None)
    ap.add_argument("--out", default="aihub_transfer_decomp.json")
    ap.add_argument("--allow-no-reproduce", action="store_true",
                    help="대조 기준 파일이 없는 arm 짝을 재현 검증 없이 실행(권장 안 함)")
    ap.add_argument("--limit-videos", type=int, default=None,
                    help="배관 점검(canary) 전용 — 앞 N편만. 재현 검증이 성립하지 않으므로 "
                         "--allow-no-reproduce 필요. 이 결과는 보고하지 않는다")
    a = ap.parse_args()
    if a.limit_videos:
        a.out = f"_canary_{a.out}"

    cfg = common.load_config(str(ROOT / a.config))
    alpha = a.alpha
    if alpha is None:
        p = ROOT / "results/alpha_search_dev.json"
        alpha = json.loads(p.read_text(encoding="utf-8"))["alpha_star"] if p.exists() else 0.5

    qs_all = load_external_queries(ROOT / a.queries)
    want = sorted({q["video_id"] for q in qs_all})
    if a.limit_videos:
        want = want[:a.limit_videos]
    idx0 = {}
    for v in want:
        try:
            idx0[v] = VideoIndex.load(cfg, v)
        except Exception:
            pass
    assert idx0, "인덱스가 하나도 없다"
    qs = [q for q in qs_all if q["video_id"] in idx0]
    segs = {v: idx0[v].segments for v in idx0}
    print(f"영상 {len(idx0)}편 · 세그먼트 {sum(len(s) for s in segs.values())} · "
          f"질의 {len(qs)}건 · α={alpha}", flush=True)

    caps = {arm: load_arm_captions(arm, list(idx0), segs)
            for arm in (a.control, a.candidate)}
    q_emb = embed_texts([q["text"] for q in qs], cfg["embed_model"])
    pq = {}
    for arm in (a.control, a.candidate):
        pq[arm] = per_query_rows(qs, idx0, caps[arm], q_emb, alpha, cfg)
        m = {k: round(float(np.mean([r[f"rr_{k}"] for r in pq[arm]])), 4)
             for k in ("cap", "fus", "sub")}
        print(f"[{arm}] MRR 캡션단독 {m['cap']} 융합 {m['fus']} 자막단독 {m['sub']}",
              flush=True)

    ctl, cnd = pq[a.control], pq[a.candidate]
    pair = (a.control, a.candidate)
    rep = {
        "note": ("per_query 복원 + 재표집 단위 점검 + 융합 전달 분해. 채택 판정 변경 아님. "
                 "work_aihub 불변, test 미접촉."),
        "purpose": "감사_2026-08-17 §3 미결 2건(CI 재표집 단위 · 융합 전달 구조) 해소",
        "confound_not_resolved": (f"{a.control} vs {a.candidate} — 모델과 프롬프트가 함께 "
                                  f"바뀐다. 여기 수치는 전부 configuration effect다."),
        "arms": {"control": a.control, "candidate": a.candidate},
        "n_videos": len(idx0), "n_queries": len(qs), "alpha_fused": alpha,
        "seed": cfg["seed"], "bootstrap_B": cfg["bootstrap_B"],
        "embed_model": cfg["embed_model"],
        "mrr": {arm: {k: round(float(np.mean([r[f"rr_{k}"] for r in pq[arm]])), 4)
                      for k in ("cap", "fus", "sub")} for arm in pair},
    }

    # ① 재현 검증 게이트 — 통과 못 하면 아래 수치를 쓰지 않는다
    ref = next((f for f, p in REPRO.items() if p == pair), None)
    if a.limit_videos:       # 부분 표본이라 전수 기준과 일치할 수 없다
        ref = None
    rep["reproduce"] = {"reference": ref}
    if ref and (OUT / ref).is_file():
        st = json.loads((OUT / ref).read_text(encoding="utf-8"))["contrasts"]
        got = {"caption_only": round(float(np.mean([k["rr_cap"] - b["rr_cap"]
                                                   for b, k in zip(ctl, cnd)])), 4),
               "fused": round(float(np.mean([k["rr_fus"] - b["rr_fus"]
                                             for b, k in zip(ctl, cnd)])), 4)}
        exp = {k: st[k]["delta"] for k in got}
        ok = all(abs(got[k] - exp[k]) <= 1e-4 for k in got)
        rep["reproduce"].update({"expected": exp, "recomputed": got, "match": ok})
        print(f"재현 검증: 기대 {exp} / 재계산 {got} -> {'PASS' if ok else 'FAIL'}")
        assert ok, ("사전등록 결과를 재현하지 못했다 — 재구성이 틀렸다. "
                    "아래 수치를 보고하지 않는다.")
    else:
        rep["reproduce"]["match"] = None
        msg = f"대조 기준 파일 없음 (arm 짝 {pair}) — 재현 검증 불가"
        print("경고:", msg)
        assert a.allow_no_reproduce, msg + " (--allow-no-reproduce 로만 진행)"

    # ② 재표집 단위별 CI
    groups = [r["video_id"] for r in ctl]
    B, seed = cfg["bootstrap_B"], cfg["seed"]
    rep["contrasts"] = {}
    for key, name in (("rr_cap", "caption_only"), ("rr_fus", "fused"),
                      ("hit1_cap", "hit@1_caption_only")):
        b = np.array([r[key] for r in ctl]); k = np.array([r[key] for r in cnd])
        rep["contrasts"][name] = {
            "query": boot_query(b, k, B, seed),
            "video_cluster": boot_cluster(b, k, groups, B, seed),
            "video_macro": boot_cluster(b, k, groups, B, seed, macro=True)}
        for u in ("query", "video_cluster", "video_macro"):
            c = rep["contrasts"][name][u]
            print(f"  {name:20s} {u:14s} Δ{c['delta']:+.4f} CI{c['ci95']} "
                  f"{'0배제' if c['excludes_zero'] else '0포함'}")

    # ②-b 클러스터 보정 필요성을 부트스트랩과 독립으로 판정
    rep["icc"] = {n: icc1(ctl, cnd, k)
                  for k, n in (("rr_cap", "caption_only"), ("rr_fus", "fused"))}
    for n, v in rep["icc"].items():
        print(f"  ICC {n:14s} {v['icc1']:+.4f} 설계효과 {v['design_effect']:.3f} "
              f"{'보정 필요' if v['cluster_adjustment_needed'] else '보정 불필요'}")

    # ③ 융합 전달 분해
    rep["transfer"] = transfer_buckets(ctl, cnd)
    rep["by_sub_strength"] = by_sub_strength(ctl, cnd)
    rep["saturation_adjusted"] = saturation_adjusted(ctl, cnd)
    rep["by_group"] = by_group(ctl, cnd)
    rep["exploratory_note"] = ("saturation_adjusted·by_group·by_sub_strength는 "
                              "사전등록되지 않은 사후 분해다. 가설 생성용으로만 쓰고 "
                              "확증으로 세지 않는다.")
    rep["per_query"] = {"control": ctl, "candidate": cnd}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / a.out
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    t = rep["transfer"]
    print("\n전달 분해:", json.dumps(t["crosstab"], ensure_ascii=False))
    print(f"  cap↑fus= {t['cap_up_fus_same']['n']} / cap↑fus↑ {t['cap_up_fus_up']['n']}"
          f" / cap↑fus↓ {t['cap_up_fus_down']['n']}")
    print(f"  Δmargin 상관 {t['corr_margin_delta']} · Δrank 상관 {t['corr_rank_delta']}")
    print("->", p)


if __name__ == "__main__":
    main()
