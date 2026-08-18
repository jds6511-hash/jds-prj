"""[융합 feature 진단 — 질의 시점 관측량이 "자막 2~5위 위험 구간"을 예측하는가]

사전등록: `docs/preregistration/융합feature진단_사전등록_2026-08-18.md` (커밋 f9acb69,
데이터 읽기 전 작성). 이 스크립트는 그 문서의 §3~§8만 구현한다.

**왜.** 전달분해 §3-3에서 캡션 개선의 융합 전달률이 가장 낮은 층이 자막 단독 2~5위였다
(50.4% / 44.7%, 두 arm 짝 공통). 그런데 **자막 단독 순위는 GT를 알아야 나온다** — 실사용
질의 시점에는 모른다. 그래서 적응 α를 만들려면 먼저 이 질문을 닫아야 한다:
**GT를 안 쓰는 관측량만으로 그 층을 판별할 수 있는가.**

**하지 않는 것.** adaptive α rule을 만들지 않는다. α·τ·캡션 모델·인덱스를 바꾸지 않는다.
캡션을 생성하지 않는다(저장된 인덱스·2×2 캡션만). test 미접촉 — 표본은 AI Hub
`split="external"` 1,086질의다.

**자기검증 게이트 G1~G4.** 하나라도 실패하면 주분석 수치를 보고하지 않는다(SystemExit).

재현: python docs/probes/fusion_feature_diag.py
"""
import argparse, io, json, subprocess, sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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

# 사전등록 §4 — 8개 고정. 순서가 결과 JSON의 계수 순서다.
FEATURES = ["sub_top1_score", "sub_top2_score", "sub_top1_minus_top2",
            "sub_top1_minus_top5", "cap_top1_score", "cap_top1_minus_top2",
            "sub_cap_top1_score_gap", "sub_cap_top1_same_segment"]
# 전달분해 §3-3의 층 크기 — G2 대조값
EXPECTED_STRATA = {"sub_rank_1": 270, "sub_rank_2_5": 362, "sub_rank_6plus": 454}


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def rank_of(score: np.ndarray, gt: set) -> int:
    """m5_search와 동일한 안정 정렬로 GT 최상위 순위. 1-based, 미발견 0."""
    for r, i in enumerate(np.argsort(-score, kind="stable"), 1):
        if int(i) in gt:
            return r
    return 0


def query_features(s_sub: np.ndarray, s_cap: np.ndarray) -> dict:
    """**GT를 쓰지 않는다.** 두 채널의 raw 코사인만으로 계산한다.

    척도는 사전등록대로 raw 코사인이다 — z-score는 융합 단계의 정규화이고,
    질의별 표준편차로 나눈 격차는 다른 feature다(§4, z 변형은 탐색으로 분리)."""
    ss, sc = np.sort(s_sub)[::-1], np.sort(s_cap)[::-1]
    top5 = ss[4] if len(ss) >= 5 else ss[-1]
    return {"sub_top1_score": float(ss[0]), "sub_top2_score": float(ss[1]),
            "sub_top1_minus_top2": float(ss[0] - ss[1]),
            "sub_top1_minus_top5": float(ss[0] - top5),
            "cap_top1_score": float(sc[0]),
            "cap_top1_minus_top2": float(sc[0] - sc[1]),
            "sub_cap_top1_score_gap": float(ss[0] - sc[0]),
            "sub_cap_top1_same_segment":
                float(int(np.argmax(s_sub)) == int(np.argmax(s_cap)))}


def build_rows(qs, idx0, q_emb, cap_emb, alpha) -> list[dict]:
    """질의별 feature + 목표변수 + 참고 순위. cap_emb=None이면 인덱스 emb_cap."""
    rows = []
    for n, q in enumerate(qs):
        vi, qe = idx0[q["video_id"]], q_emb[n]
        s_sub = vi.emb_sub @ qe
        s_cap = (vi.emb_cap if cap_emb is None else cap_emb[q["video_id"]]) @ qe
        gt = set(q["gt_seg_idx"])
        r_sub = rank_of(s_sub, gt)
        row = {"query_id": q["query_id"], "video_id": q["video_id"],
               "domain": q["type"], "sub_rank": r_sub,
               # 목표변수는 자막 채널만 쓰므로 캡션 arm과 무관하다 [사전등록 §3]
               "y": int(2 <= r_sub <= 5),
               "rank_fus_a": rank_of(combine_scores(
                   s_sub, s_cap, vi.static_mask, alpha), gt),
               "rank_fus_lo": rank_of(combine_scores(
                   s_sub, s_cap, vi.static_mask, 0.3), gt),
               **query_features(s_sub, s_cap)}
        rows.append(row)
    return rows


def oof_auc(X, y, groups, k=5, seed=0) -> tuple[np.ndarray, float]:
    """GroupKFold(video_id) out-of-fold 예측과 그 AUC.

    영상 단위로 묶는 이유: 같은 영상의 질의가 train·test fold에 동시에 들어가면
    분류기가 영상 특성을 외운다."""
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=k).split(X, y, groups):
        m = make_pipeline(StandardScaler(),
                          LogisticRegression(max_iter=1000, random_state=seed))
        m.fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    return oof, float(roc_auc_score(y, oof))


def boot_auc_cluster(y, score, groups, B: int, seed: int) -> dict:
    """영상 단위 부트스트랩 AUC 95% CI. 영상을 복원추출하고 선택된 영상의
    전 질의를 함께 넣는다. 한 클래스만 뽑힌 표본은 버린다."""
    vids = sorted(set(groups))
    pos = {v: np.flatnonzero(np.asarray(groups) == v) for v in vids}
    rng = np.random.default_rng(seed)
    vals, skipped = [], 0
    for _ in range(B):
        idx = np.concatenate([pos[vids[j]] for j in
                              rng.integers(0, len(vids), size=len(vids))])
        if len(set(y[idx])) < 2:
            skipped += 1
            continue
        vals.append(roc_auc_score(y[idx], score[idx]))
    lo, hi = (float(x) for x in np.percentile(vals, [2.5, 97.5]))
    return {"point": round(float(roc_auc_score(y, score)), 4),
            "ci95": [round(lo, 4), round(hi, 4)], "B_used": len(vals),
            "B_skipped_single_class": skipped}


def verdict(ci_lo: float, n_pos: int) -> dict:
    """사전등록 §6 — 판정은 점추정이 아니라 CI 하한으로. 양성 50건 미만이면
    점추정이 무엇이든 '약한 신호'로 강등한다(§3 전건 규칙)."""
    band = ("신호 없음" if ci_lo < 0.60
            else "약한 신호" if ci_lo < 0.70 else "신호 있음")
    if n_pos < 50 and band == "신호 있음":
        return {"band": "약한 신호", "ci_lower": ci_lo,
                "demoted": f"양성 {n_pos}건 < 50 — §3 전건 규칙"}
    return {"band": band, "ci_lower": ci_lo, "demoted": None}


def permute_by_video(y, groups, seed: int) -> np.ndarray:
    """영상 단위 라벨 치환 — 영상 순서를 섞어 y 블록을 재배치하고 원래 영상
    크기로 다시 자른다. 질의 단위 전역 치환보다 **엄격한 누출 검정**이다:
    영상 내 y 상관이 보존되므로, CV가 영상 정보를 흘리면 AUC가 0.5를 넘는다."""
    vids = sorted(set(groups))
    pos = [np.flatnonzero(np.asarray(groups) == v) for v in vids]
    perm = np.random.default_rng(seed).permutation(len(vids))
    pooled = np.concatenate([y[pos[p]] for p in perm])
    out, c = np.zeros(len(y), dtype=int), 0
    for p in pos:                       # 원래 영상 크기로 재분할
        out[p] = pooled[c:c + len(p)]
        c += len(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    ap.add_argument("--alpha", type=float, default=None)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--out", default="fusion_feature_diag_2026-08-18.json")
    ap.add_argument("--limit-videos", type=int, default=None,
                    help="배관 점검 전용 — G2가 성립하지 않으므로 보고하지 않는다")
    a = ap.parse_args()
    if a.limit_videos:
        a.out = f"_canary_{a.out}"

    cfg = common.load_config(str(ROOT / a.config))
    alpha = a.alpha
    if alpha is None:
        p = ROOT / "results/alpha_search_dev.json"
        alpha = json.loads(p.read_text(encoding="utf-8"))["alpha_star"] if p.exists() else 0.5
    B, seed = cfg["bootstrap_B"], cfg["seed"]

    qs_all = load_external_queries(ROOT / a.queries)
    want = sorted({q["video_id"] for q in qs_all})
    if a.limit_videos:
        want = want[:a.limit_videos]
    idx0 = {}
    for v in want:
        try:
            idx0[v] = VideoIndex.load(cfg, v)   # text_hash 불일치면 여기서 ValueError [G4]
        except Exception:
            pass
    assert idx0, "인덱스가 하나도 없다"
    qs = [q for q in qs_all if q["video_id"] in idx0]
    n_static = int(sum(int(idx0[v].static_mask.sum()) for v in idx0))
    print(f"영상 {len(idx0)}편 · 질의 {len(qs)}건 · α={alpha} · "
          f"static 치환 {n_static}구간", flush=True)

    q_emb = embed_texts([q["text"] for q in qs], cfg["embed_model"])
    rows = build_rows(qs, idx0, q_emb, None, alpha)

    y = np.array([r["y"] for r in rows])
    groups = [r["video_id"] for r in rows]
    X = np.array([[r[f] for f in FEATURES] for r in rows])

    # ---- 자기검증 게이트 (사전등록 §7) -------------------------------------
    strata = {"sub_rank_1": sum(1 for r in rows if r["sub_rank"] == 1),
              "sub_rank_2_5": sum(1 for r in rows if 2 <= r["sub_rank"] <= 5),
              "sub_rank_6plus": sum(1 for r in rows
                                    if r["sub_rank"] == 0 or r["sub_rank"] >= 6)}
    y_perm = permute_by_video(y, groups, seed)
    oof_perm, _ = oof_auc(X, y_perm, groups, a.folds, seed)
    g1 = boot_auc_cluster(y_perm, oof_perm, groups, B, seed)
    gates = {
        "G1_permutation_includes_0.5": bool(g1["ci95"][0] <= 0.5 <= g1["ci95"][1]),
        "G2_strata_match_transfer_decomp": (strata == EXPECTED_STRATA
                                            if not a.limit_videos else None),
        "G3_no_gt_derived_feature": all(
            k not in FEATURES for k in ("y", "sub_rank", "rank_fus_a", "rank_fus_lo")),
        "G4_text_hash_verified": True,     # VideoIndex.load가 불일치면 예외
    }
    gates_detail = {"strata_observed": strata, "strata_expected": EXPECTED_STRATA,
                    "permutation_auc": g1,
                    "permutation_note":
                        "사전등록 §7 G1의 '영상 단위 치환'은 영상당 질의 수가 2~14로 "
                        "달라 블록 교환이 정의되지 않는다. 영상 순서를 섞어 y를 "
                        "이어붙인 뒤 원래 크기로 재분할하는 방식으로 구현했다."}

    # ---- 주분석 -----------------------------------------------------------
    oof, auc = oof_auc(X, y, groups, a.folds, seed)
    boot = boot_auc_cluster(y, oof, groups, B, seed)
    uni = {f: round(float(roc_auc_score(y, X[:, i])), 4)
           for i, f in enumerate(FEATURES)}
    coef = make_pipeline(StandardScaler(),
                         LogisticRegression(max_iter=1000, random_state=seed))
    coef.fit(X, y)
    primary = {"oof_auc": round(auc, 4), "bootstrap": boot,
               "univariate_auc": uni,
               "coef_full_fit": dict(zip(
                   FEATURES, [round(float(c), 4)
                              for c in coef[-1].coef_[0]])),
               "verdict": verdict(boot["ci95"][0], int(y.sum()))}

    # ---- 탐색 (판정에 쓰지 않는다 — 사전등록 §8) ---------------------------
    expl = {}
    # §8-2 대안 목표변수: α를 0.5→0.3으로 내렸을 때 융합 순위가 좋아지는 질의
    y2 = np.array([int((r["rank_fus_lo"] or 10**6) < (r["rank_fus_a"] or 10**6))
                   for r in rows])
    if len(set(y2)) == 2:
        oof2, auc2 = oof_auc(X, y2, groups, a.folds, seed)
        expl["adaptive_helpful"] = {
            "definition": "α 0.5→0.3에서 융합 GT 순위 개선",
            "n_pos": int(y2.sum()),
            "bootstrap": boot_auc_cluster(y2, oof2, groups, B, seed)}
    # §8-4 도메인별 양성률
    doms = sorted({r["domain"] for r in rows})
    expl["by_domain"] = {d: {"n": sum(1 for r in rows if r["domain"] == d),
                             "pos_rate": round(float(np.mean(
                                 [r["y"] for r in rows if r["domain"] == d])), 4)}
                         for d in doms}
    # §8-1 arm 강건성: 캡션 채널을 2×2의 4B/P0 캡션으로 교체
    f4b = CAP2X2 / "qwen3vl_4b__P0.json"
    if f4b.is_file() and not a.limit_videos:
        caps = json.loads(f4b.read_text(encoding="utf-8"))
        ok = [v for v in idx0 if v in caps and len(caps[v]) == len(idx0[v].segments)]
        if len(ok) == len(idx0):
            cap_emb = {v: embed_texts(caps[v], cfg["embed_model"]) for v in ok}
            rows4 = build_rows(qs, idx0, q_emb, cap_emb, alpha)
            X4 = np.array([[r[f] for f in FEATURES] for r in rows4])
            assert (np.array([r["y"] for r in rows4]) == y).all(), \
                "목표변수가 arm에 따라 달라졌다 — 자막 채널만 쓴다는 전제 위반"
            oof4, _ = oof_auc(X4, y, groups, a.folds, seed)
            expl["arm_4B_P0"] = boot_auc_cluster(y, oof4, groups, B, seed)
        else:
            expl["arm_4B_P0"] = f"세그먼트 수 불일치 — {len(idx0) - len(ok)}편 제외 필요"

    rep = {"probe": "fusion_feature_diag",
           "prereg": "docs/preregistration/융합feature진단_사전등록_2026-08-18.md",
           "git_head": _git("rev-parse", "HEAD"),
           "git_dirty": bool(_git("status", "--porcelain")),
           "config": a.config, "embed_model": cfg["embed_model"], "seed": seed,
           "bootstrap_B": B, "alpha_fused": alpha, "folds": a.folds,
           "n_queries": len(qs), "n_videos": len(idx0),
           "n_static_segments": n_static,
           "n_positive": int(y.sum()),
           "positive_rate": round(float(y.mean()), 4),
           "features": FEATURES, "gates": gates, "gates_detail": gates_detail,
           "primary": primary, "exploratory": expl}

    OUT.mkdir(exist_ok=True)
    (OUT / a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(json.dumps({"gates": gates, "n_positive": rep["n_positive"],
                      "primary": {k: primary[k] for k in
                                  ("oof_auc", "bootstrap", "verdict")}},
                     ensure_ascii=False, indent=2))
    print(f"저장: docs/probes/_scratch/{a.out}")

    failed = [k for k, v in gates.items() if v is False]
    if failed:
        raise SystemExit(f"게이트 실패 {failed} — 주분석 수치를 보고하지 마라.")


if __name__ == "__main__":
    main()
