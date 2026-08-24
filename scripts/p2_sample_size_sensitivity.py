"""P2 표본 규모 민감도 — **과거 자료로 진단만 한다. 판정하지 않는다.**

질문: 35 video cluster를 유지한 채 영상당 질의 수 m을 9 → 5 → 4로 줄이면
paired video-cluster CI의 half-width가 얼마나 넓어질 수 있는가.

```
쓰는 자료   AI Hub 2x2 캡션 단독 per-query RR (194영상 · 1,086질의)
            arm: qwen25_3b/P0 vs qwen3vl_4b/P0
안 쓰는 것  P2 retrieval · P2 arm 산출물 · P2 캡션 · p2_evaluate
불변        half-width 목표 0.04 · PRIMARY · alpha · cluster bootstrap · exclusion
판정        하지 않는다 — 140/175/315 선택은 사용자 승인 사항이다
```

**과거 자료는 P2 정밀도를 보장하지 않는다.** 후보 풀(12 vs 약 260)·도메인·생성
정밀도(bf16 vs 4bit)가 다르다. 그래서 절대값보다 **m에 따른 상대 변화**가 읽을
값이고, 그 사실을 산출물의 `limitations`에 싣는다.

두 갈래로 본다.

```
투사    불균형 일원 랜덤효과 분해로 σ²_between · σ²_within을 얻고
        Var(mean) = (σ²_b + σ²_w/m)/k 로 k=35 · m=4/5/9을 투사한다
경험    영상 안에서 m건으로 thinning한 뒤 k개 영상을 뽑아 cluster bootstrap을
        반복해 half-width 분포를 낸다. 적격 영상이 k보다 적으면 "추정 불가"다
```

경험 갈래에는 **선택 편향**이 있다 — 질의가 m건 이상인 영상만 쓰므로 질의가 많은
영상 쪽으로 치우친다. 그 사실을 행마다 적는다.

balanced 설계에서는 영상 평균의 재표집 평균과 질의 pooled 평균이 같으므로
`p2_evaluate._cluster_bootstrap`(영상 재표집 후 질의 pooled)과 일치한다.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

AIHUB = ROOT / "docs" / "probes" / "_scratch" / \
    "aihub_caption_2x2_full_2026-08-17.json"
DEV_DIAG = ROOT / "docs" / "probes" / "_scratch" / "sign_reversal_diag.json"
BASE_KEY = "qwen25_3b/P0"
CAND_KEY = "qwen3vl_4b/P0"
CHANNEL_FIELD = "rr_cap"
M_GRID = (4, 5, 9)
K_TARGET = 35
SEED = 20260820
Z95 = 1.959963984540054
HALF_WIDTH_TARGET = 0.04
REPLICATES = 400
BOOT = 600


class SensitivityError(Exception):
    pass


# ------------------------------------------------------------- 자료 적재

def paired_deltas(source=AIHUB, base_key: str = BASE_KEY,
                  cand_key: str = CAND_KEY) -> list:
    """질의별 캡션 단독 RR 차이. 같은 질의 순서로 짝지어져 있어야 한다."""
    doc = json.loads(Path(source).read_text(encoding="utf-8"))
    pq = doc.get("per_query") or {}
    for key in (base_key, cand_key):
        if key not in pq:
            raise SensitivityError(f"{key} arm이 자료에 없다")
    a, b = pq[base_key], pq[cand_key]
    if len(a) != len(b):
        raise SensitivityError(f"두 arm 길이가 다르다 {len(a)} vs {len(b)}")
    out = []
    for ra, rb in zip(a, b):
        if ra["query_id"] != rb["query_id"] or ra["video_id"] != rb["video_id"]:
            raise SensitivityError(f"짝이 맞지 않는다: {ra['query_id']} vs "
                                   f"{rb['query_id']}")
        out.append({"query_id": ra["query_id"], "video_id": ra["video_id"],
                    "delta": float(rb[CHANNEL_FIELD]) - float(ra[CHANNEL_FIELD])})
    return out


def _grouped(deltas: list) -> dict:
    out = {}
    for r in deltas:
        out.setdefault(r["video_id"], []).append(r["delta"])
    return {k: np.asarray(v, dtype=float) for k, v in sorted(out.items())}


# ------------------------------------------------------------- 분산 분해

def decompose(deltas: list) -> dict:
    """불균형 일원 랜덤효과 적률 추정. σ²_between이 음수면 0으로 절단한다."""
    groups = _grouped(deltas)
    k = len(groups)
    if k < 2:
        raise SensitivityError(f"cluster {k}개로는 between 분산을 나눌 수 없다")
    n_j = np.array([len(v) for v in groups.values()], dtype=float)
    n = float(n_j.sum())
    if n <= k:
        raise SensitivityError(f"질의 {int(n)}건 · cluster {k}개 — within "
                               "자유도가 없다")
    means = np.array([v.mean() for v in groups.values()])
    grand = float(sum(v.sum() for v in groups.values()) / n)
    ssw = float(sum(((v - v.mean()) ** 2).sum() for v in groups.values()))
    ssb = float((n_j * (means - grand) ** 2).sum())
    s2w = ssw / (n - k)
    n0 = (n - float((n_j ** 2).sum()) / n) / (k - 1)
    s2b = max(0.0, (ssb / (k - 1) - s2w) / n0)
    total = s2b + s2w
    return {"n": int(n), "k": k, "grand_mean_delta": round(grand, 6),
            "sigma2_within": s2w, "sigma2_between": s2b, "n0": n0,
            "icc": (s2b / total) if total > 0 else 0.0,
            "queries_per_cluster_observed": {"min": int(n_j.min()),
                                             "median": float(np.median(n_j)),
                                             "max": int(n_j.max())}}


def projected_half_width(sigma2_between: float, sigma2_within: float,
                         k: int, m: int) -> float:
    """balanced k x m 설계의 정규근사 half-width."""
    return Z95 * float(np.sqrt((sigma2_between + sigma2_within / m) / k))


def half_width_ratios(sigma2_between: float, sigma2_within: float,
                      k: int, grid=M_GRID, reference: int = 9) -> dict:
    ref = projected_half_width(sigma2_between, sigma2_within, k, reference)
    return {m: projected_half_width(sigma2_between, sigma2_within, k, m) / ref
            for m in grid}


ICC_SCENARIOS = (0.0, 0.03, 0.10, 0.25)


def icc_scenarios(total_variance: float, k: int, grid=M_GRID,
                  scenarios=ICC_SCENARIOS, reference: int = 9) -> list:
    """ICC를 가정값으로 훑는다 — 미지수에 답이 얼마나 의존하는지 보이기 위해서다.

    AI Hub에서 관측된 ICC는 0이었다. 그러나 dev 3편의 영상별 mean_delta는
    −0.0418 / −0.0276 / −0.2112로 흩어져 있어 장편에서는 between 분산이 0이
    아닐 가능성이 있다(cluster 3 · 자유도 2라 **추정이 아니다**).

    ICC가 커지면 m을 줄이는 손해가 작아진다. 그래서 ICC=0 행은
    **이 일원 랜덤효과 분산 모형 안에서 m=4·m=5의 m=9 대비 상대 손실의 상한**이다.
    P2의 실제 자료생성 구조 전체에 대한 보편적 상한이 아니다 — 이 모형이 담지
    못하는 구조(질의 유형별 이질 분산, 영상×유형 상호작용, 후보 풀 크기 의존성
    등)가 있으면 그 상한은 성립하지 않는다.

    두 표본의 분산 성분을 섞어 하나의 점추정을 만들지는 않는다.
    """
    out = []
    for icc in scenarios:
        s2b = total_variance * icc
        s2w = total_variance * (1.0 - icc)
        ref = projected_half_width(s2b, s2w, k, reference)
        out.append({"assumed_icc": icc,
                    "half_width": {m: round(projected_half_width(s2b, s2w, k, m),
                                            4) for m in sorted(grid)},
                    "relative_to_m9": {m: round(projected_half_width(
                        s2b, s2w, k, m) / ref, 3) for m in sorted(grid)}})
    return out


# ------------------------------------------------------------- 경험적 재표집

def empirical_half_widths(deltas: list, m: int, k: int = K_TARGET,
                          seed: int = SEED, replicates: int = REPLICATES,
                          boot: int = BOOT) -> dict:
    """영상 안에서 m건으로 줄인 뒤 k영상 cluster bootstrap을 반복한다."""
    groups = _grouped(deltas)
    eligible = [v for v, arr in groups.items() if len(arr) >= m]
    out = {"m": m, "k": k, "total_clusters": len(groups),
           "eligible_clusters": len(eligible), "replicates": replicates,
           "boot": boot,
           "selection_note": (f"질의 {m}건 이상인 영상만 쓴다 — 질의가 많은 영상 "
                              "쪽으로 선택 편향이 있다"),
           "unit": "paired_video_cluster_bootstrap_percentile"}
    if len(eligible) < k:
        out.update({"usable": False, "median": None, "p75": None, "p90": None,
                    "reason": f"질의 {m}건 이상인 영상이 {len(eligible)}편으로 "
                              f"cluster 목표 {k}편에 미달 — 추정 불가"})
        return out
    rng = np.random.default_rng(seed)
    pool = [np.asarray(groups[v], dtype=float) for v in eligible]
    widths = []
    for _ in range(replicates):
        pick = rng.choice(len(pool), size=k, replace=False)
        means = np.array([rng.choice(pool[i], size=m, replace=False).mean()
                          for i in pick])
        idx = rng.integers(0, k, size=(boot, k))
        draws = np.sort(means[idx].mean(axis=1))
        lo = draws[int(0.025 * boot)]
        hi = draws[min(boot - 1, int(0.975 * boot))]
        widths.append((hi - lo) / 2.0)
    w = np.sort(np.asarray(widths))
    out.update({"usable": True, "reason": None,
                "median": float(np.percentile(w, 50)),
                "p75": float(np.percentile(w, 75)),
                "p90": float(np.percentile(w, 90))})
    return out


# ------------------------------------------------------------- dev 사용 가능성

def dev_usability(source=DEV_DIAG) -> dict:
    """dev 96질의는 이 분석에 쓸 수 없다 — 근거를 파일에서 직접 확인한다."""
    doc = json.loads(Path(source).read_text(encoding="utf-8"))
    by_video = doc.get("by_video") or {}
    has_per_query = any(isinstance(v, dict) and "deltas" in v
                        for v in by_video.values())
    return {"usable": False, "clusters": len(by_video),
            "stored_fields": sorted({f for v in by_video.values()
                                     if isinstance(v, dict) for f in v}),
            "per_query_stored": has_per_query,
            "reason": ("질의 단위(per-query) 짝지은 RR이 저장돼 있지 않고 영상별 "
                       "집계만 있다. 또 cluster가 3개라 between 분산의 자유도가 "
                       "2다 — thinning도 분해도 불가")}


# ------------------------------------------------------------- 보고

LIMITATIONS = [
    "AI Hub 후보 풀은 영상당 12구간이고 P2는 장편(영상당 약 260구간)이다 — "
    "RR 분포의 스케일이 달라 절대 half-width를 P2에 그대로 옮길 수 없다",
    "AI Hub 2x2 arm은 bf16이고 P2 PRIMARY는 양 arm 4bit다 — 생성 정밀도가 다르다",
    "AI Hub 1,086질의는 모델 확증에 이미 사용된 재사용 표본이다 — fresh evidence가 "
    "아니고, 여기서는 분산 구조 진단에만 쓴다",
    "dev와 AI Hub는 도메인·후보 풀·cluster 구조가 달라 하나의 모집단으로 pool하지 "
    "않는다. dev는 per-query 미저장 + cluster 3으로 이 분석에 사용 불가다",
    "경험 갈래는 질의 m건 이상인 영상만 쓰므로 질의가 많은 영상 쪽 선택 편향이 있다",
    "투사 갈래는 정규근사이고 balanced 설계를 가정한다 — bootstrap percentile CI와 "
    "정확히 같지 않다",
    "이 분석은 P2의 실제 half-width를 예측하지 않는다. m에 따른 상대 변화의 크기를 "
    "가늠하는 진단이다",
]


def report(source=AIHUB, k: int = K_TARGET, grid=M_GRID, seed: int = SEED,
           replicates: int = REPLICATES, boot: int = BOOT) -> dict:
    deltas = paired_deltas(source)
    dec = decompose(deltas)
    ratios = half_width_ratios(dec["sigma2_between"], dec["sigma2_within"], k,
                               grid=grid)
    rows = []
    for m in sorted(grid):
        emp = empirical_half_widths(deltas, m=m, k=k, seed=seed,
                                    replicates=replicates, boot=boot)
        rows.append({
            "design": f"p2_{k * m}", "queries_per_video": m,
            "total_queries": k * m, "clusters": k,
            "projected_half_width": round(projected_half_width(
                dec["sigma2_between"], dec["sigma2_within"], k, m), 4),
            "relative_to_m9": round(ratios[m], 3),
            "empirical_usable": emp["usable"],
            "empirical_median_half_width": (round(emp["median"], 4)
                                            if emp["usable"] else None),
            "empirical_p75": round(emp["p75"], 4) if emp["usable"] else None,
            "empirical_p90": round(emp["p90"], 4) if emp["usable"] else None,
            "empirical_eligible_clusters": emp["eligible_clusters"],
            "empirical_reason": emp["reason"],
            "selection_note": emp["selection_note"],
            "historical_source": str(Path(source).name),
        })
    return {"probe": "p2_sample_size_sensitivity",
            "question": ("35 video cluster 유지 · 영상당 질의 수 m에 따른 paired "
                         "video-cluster CI half-width의 상대 변화"),
            "arms": {"base": BASE_KEY, "candidate": CAND_KEY,
                     "channel": CHANNEL_FIELD},
            "variance_decomposition": {
                "n": dec["n"], "k": dec["k"],
                "sigma2_between": round(dec["sigma2_between"], 6),
                "sigma2_within": round(dec["sigma2_within"], 6),
                "icc": round(dec["icc"], 4), "n0": round(dec["n0"], 3),
                "queries_per_cluster_observed":
                    dec["queries_per_cluster_observed"]},
            "rows": rows,
            "icc_scenarios": icc_scenarios(
                dec["sigma2_between"] + dec["sigma2_within"], k, grid=grid),
            "icc_scenarios_note": ("관측 ICC는 0이었다. ICC가 크면 m 축소의 손해가 "
                                   "작아지므로 ICC=0 행은 **이 일원 랜덤효과 분산 "
                                   "모형 안에서** m=4·m=5의 m=9 대비 상대 손실의 "
                                   "상한이다. P2 자료생성 구조 전체에 대한 보편적 "
                                   "상한이 아니다. 가정값 훑기이고 추정이 아니다"),
            "dev_usability": dev_usability(),
            "half_width_target": HALF_WIDTH_TARGET,
            "half_width_target_note": ("사전등록 규칙이다. 이 분석으로 완화하지 "
                                       "않는다"),
            "sign_is_not_a_decision_input": True,
            "sign_note": ("설계 선택 근거는 정밀도·비용 trade-off다. 과거 표본의 "
                          "Δ 부호가 어느 설계에서 더 유리하게 보이는지는 근거가 "
                          "아니다"),
            "limitations": LIMITATIONS,
            "decision": "사용자_승인_사항",
            "seed": seed}


def main():
    ap = argparse.ArgumentParser(
        description="P2 표본 규모 민감도 진단 — 설계를 고르지 않는다")
    ap.add_argument("--source", default=str(AIHUB))
    ap.add_argument("--k", type=int, default=K_TARGET)
    ap.add_argument("--replicates", type=int, default=REPLICATES)
    ap.add_argument("--boot", type=int, default=BOOT)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rep = report(source=a.source, k=a.k, replicates=a.replicates, boot=a.boot)
    Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    for row in rep["rows"]:
        print(f"{row['design']}  m={row['queries_per_video']}  "
              f"proj={row['projected_half_width']}  "
              f"rel={row['relative_to_m9']}  "
              f"emp={row['empirical_median_half_width']}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
