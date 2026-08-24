"""P2 PRIMARY 분석 — **판정식을 결과 보기 전에 코드로 고정한다.**

사전등록: `docs/preregistration/부호역전_확증_보충2_P2설계_2026-08-20.md`
(§2 estimand · §4-2 규모 규칙 · §5 exclusion · §6 기록 · §7 판정식 · §8 하지 않는 것).

```
PRIMARY   Δ_deploy = MRR_caption(4B q4 / P0) − MRR_caption(3B 4bit / P0)
          캡션 단독 α = 0.0. α는 개입하지 않는다
단위       paired video-cluster bootstrap, cluster = 영상
판정       CI가 0 배제·음수 → dev 방향 재현
          CI가 0 배제·양수 → AI Hub 방향 재현
          CI가 0 포함      → 이 규모로는 판정 불가 (규모를 적고 멈춘다)
          half-width > 0.04 → 판정 불가
          k < 16          → 판정용이 아니라 기술용
```

**이 모듈이 하지 않는 것.** 모델을 채택·기각하지 않는다(I1 detector 재설계 장벽이
남아 있다). α·τ를 재탐색해 부호를 구제하지 않는다. 층별 결과 중 유리한 층을 골라
판정하지 않는다 — 판정은 전체 Δ 하나로 한다. 유의성을 쫓아 추가 표집하지 않는다.

**제외는 사전 정의 목록으로만** 하고 개수와 사유를 산출물에 적는다. 조용히 분모에서
빼지 않고, 제외 후에는 같은 common support에서 다시 계산한다.

**부분 GT로 돌리지 않는다.** `require_frozen_gt`가 활성 설계 전량과 동결 해시를
요구한다(2026-08-24 amendment로 175건) — 일부만 보고 남은 질의의 문장·경계를
고치는 경로를 막는다.

실행은 GT 완성 후다. 지금은 구현과 테스트까지만이다.
"""
import argparse
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PRIMARY = ("Δ_deploy = MRR_caption(qwen3vl_4b_q4/P0) − "
           "MRR_caption(qwen25_3b_4bit/P0), 캡션 단독 α=0.0")
PRIMARY_ALPHA = 0.0
BASE_ARM, CANDIDATE_ARM = "3b", "4b"
CLUSTER_KEY = "video_id"
CI_METHOD = "paired_video_cluster_bootstrap_percentile"
HALF_WIDTH_TARGET = 0.04
MIN_CLUSTERS_FOR_VERDICT = 16
B, SEED = 2000, 20260820
EXCLUSION_REASONS = ("gold_count_exceeds_pool",
                     "gold_span_incompatible_with_rule",
                     "caption_missing")
REMAINING_BARRIER = ("부호를 확정해도 I1 detector 재설계 장벽이 남아 있다 "
                     "(I1_detector_재설계_사전등록_2026-08-18.md)")


class EvalError(RuntimeError):
    pass


def n_queries_required() -> int:
    """활성 설계에서 읽는다 — 규모를 이 파일에 상수로 박지 않는다.

    2026-08-24 amendment로 175가 됐다. 여러 모듈에 315를 박아 두면 amendment가
    한 군데만 반영되고 나머지가 조용히 거짓말을 한다.
    """
    import p2_active_design
    return p2_active_design.total_queries()


def require_frozen_gt(gt_meta: dict, require_count: int = None) -> dict:
    """GT가 완성·동결된 뒤에만 통과한다. **부분 GT 평가를 막는 문이다.**"""
    want = n_queries_required() if require_count is None else require_count
    n, sha = gt_meta.get("n"), gt_meta.get("sha256")
    if not sha:
        raise EvalError("GT 파일 동결 해시가 없다 — 동결 전에는 평가하지 않는다")
    if n != want:
        raise EvalError(
            f"GT가 {n}건이다 — {want}건 전량이 아니면 돌리지 않는다. "
            f"부분 GT 결과를 보면 남은 질의 작성에 영향을 준다")
    return {"ok": True, "n": n, "sha256": sha}


def _rows(arm: dict, name: str) -> dict:
    if arm.get("alpha") != PRIMARY_ALPHA:
        raise EvalError(f"{name}: alpha가 {arm.get('alpha')}다 — PRIMARY는 "
                        f"캡션 단독 alpha={PRIMARY_ALPHA}이고 재탐색하지 않는다")
    out = {}
    for r in arm["per_query"]:
        qid = r["query_id"]
        if qid in out:
            raise EvalError(f"{name}: query_id 중복 {qid}")
        rr = r["rr"]
        if not 0.0 <= rr <= 1.0:
            raise EvalError(f"{name}: {qid}의 rr가 범위를 벗어난다 ({rr})")
        out[qid] = {"rr": rr, CLUSTER_KEY: r[CLUSTER_KEY]}
    return out


def _cluster_bootstrap(diffs: dict, clusters: dict) -> tuple:
    """영상 단위로 재표집한다. 질의 단위가 아니다 — 같은 영상 질의는 상관된다."""
    by_cluster = {}
    for qid, d in diffs.items():
        by_cluster.setdefault(clusters[qid], []).append(d)
    keys = sorted(by_cluster)
    rng = random.Random(SEED)
    means = []
    for _ in range(B):
        picked = [by_cluster[keys[rng.randrange(len(keys))]] for _ in keys]
        flat = [d for grp in picked for d in grp]
        means.append(sum(flat) / len(flat))
    means.sort()
    lo = means[int(0.025 * B)]
    hi = means[min(B - 1, int(0.975 * B))]
    return round(lo, 4), round(hi, 4), len(keys)


def _verdict(ci: tuple, half_width: float, n_clusters: int) -> tuple:
    if n_clusters < MIN_CLUSTERS_FOR_VERDICT:
        return ("기술용_판정하지_않음",
                f"cluster {n_clusters} < {MIN_CLUSTERS_FOR_VERDICT} — 사전등록 "
                f"§4-2(5)에 따라 판정용이 아니라 기술용이다")
    if half_width > HALF_WIDTH_TARGET:
        return ("판정_불가",
                f"achieved half-width {half_width:.4f} > {HALF_WIDTH_TARGET} — "
                f"이 규모로는 판정 불가다. 규모를 적고 멈춘다. 유의성을 쫓아 "
                f"추가 표집하지 않는다")
    if ci[0] <= 0 <= ci[1]:
        return ("판정_불가",
                "CI가 0을 포함한다 — 이 규모로는 판정 불가다. "
                "**'차이 없음'으로 쓰지 않는다**")
    if ci[1] < 0:
        return ("dev_방향_재현", "CI가 0을 배제하고 음수다 — dev 방향이 재현됐다")
    return ("aihub_방향_재현", "CI가 0을 배제하고 양수다 — AI Hub 방향이 재현됐다")


def analyze(base: dict, candidate: dict, exclude: dict = None,
            arm_failures: dict = None, query_types: dict = None,
            pool_sizes: dict = None) -> dict:
    """Δ와 CI, 그리고 판정 문구까지. **채택 판단은 하지 않는다.**"""
    failures = {k: v for k, v in (arm_failures or {}).items() if v}
    if failures:
        raise EvalError(
            f"완주하지 못한 arm이 있다 {failures} — 성공 부분집합 비교도, RR=0 "
            f"대입도 하지 않는다(§6). PRIMARY를 계산하지 않는다")

    a = _rows(base, BASE_ARM)
    c = _rows(candidate, CANDIDATE_ARM)
    if set(a) != set(c):
        only_a, only_c = sorted(set(a) - set(c)), sorted(set(c) - set(a))
        raise EvalError(f"두 arm의 공통 지지가 다르다 — {BASE_ARM}만 {len(only_a)}건 "
                        f"{only_a[:3]} · {CANDIDATE_ARM}만 {len(only_c)}건 "
                        f"{only_c[:3]}")

    exclusions = []
    for qid, reason in sorted((exclude or {}).items()):
        if reason not in EXCLUSION_REASONS:
            raise EvalError(
                f"{qid}: '{reason}'은 사전 정의 exclusion 사유가 아니다 — "
                f"{list(EXCLUSION_REASONS)} 밖의 사유로 제외하지 않는다")
        if qid not in a:
            raise EvalError(f"{qid}: 제외 대상이 결과에 없다")
        exclusions.append({"query_id": qid, "reason": reason})
        del a[qid], c[qid]

    if not a:
        raise EvalError("분석할 질의가 없다")
    diffs = {q: c[q]["rr"] - a[q]["rr"] for q in a}
    clusters = {q: a[q][CLUSTER_KEY] for q in a}
    delta = sum(diffs.values()) / len(diffs)
    lo, hi, k = _cluster_bootstrap(diffs, clusters)
    half = (hi - lo) / 2
    verdict, text = _verdict((lo, hi), half, k)

    by_video = {}
    for q, d in diffs.items():
        by_video.setdefault(clusters[q], []).append(d)
    by_type = {}
    for q, d in diffs.items():
        t = (query_types or {}).get(q)
        if t:
            by_type.setdefault(t, []).append(d)

    return {
        "probe": "p2_evaluate",
        "primary": PRIMARY,
        "alpha": PRIMARY_ALPHA,
        "prereg": ("docs/preregistration/부호역전_확증_보충2_P2설계_"
                   "2026-08-20.md"),
        "n_queries_analyzed": len(diffs),
        "n_excluded": len(exclusions),
        "exclusions": exclusions,
        "common_support_recomputed": True,
        "mrr": {BASE_ARM: round(statistics.fmean(v["rr"] for v in a.values()), 6),
                CANDIDATE_ARM: round(
                    statistics.fmean(v["rr"] for v in c.values()), 6)},
        "delta_point": round(delta, 6),
        "ci": [lo, hi],
        "half_width": round(half, 4),
        "half_width_target": HALF_WIDTH_TARGET,
        "ci_method": CI_METHOD,
        "cluster_key": CLUSTER_KEY,
        "n_clusters": k,
        "bootstrap": {"B": B, "seed": SEED},
        "verdict": verdict,
        "verdict_text": text,
        "verdict_basis": "overall_delta_only",
        "by_video": {v: round(statistics.fmean(ds), 6)
                     for v, ds in sorted(by_video.items())},
        "by_type": {t: round(statistics.fmean(ds), 6)
                    for t, ds in sorted(by_type.items())},
        "by_type_note": ("부수 보고다. 층별 결과 중 유리한 층을 골라 판정하지 "
                         "않는다 — 판정은 전체 Δ 하나로 한다"),
        "pool_sizes": dict(pool_sizes or {}),
        "pool_size_note": ("연속 변수로 그대로 기록한다. Δ와의 관계는 기술값이고 "
                           "판정에 쓰지 않는다"),
        "adoption": "이_분석에서_하지_않는다",
        "remaining_barrier": REMAINING_BARRIER,
        "not_done_here": ("α·τ 재탐색으로 부호를 구제하지 않는다 · 추가 표집하지 "
                          "않는다 · '비유의'를 '차이 없음'으로 쓰지 않는다 · "
                          "P1의 I_pool을 adoption gate로 쓰지 않는다"),
        "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                 capture_output=True,
                                 encoding="utf-8").stdout.strip(),
    }


def main():
    ap = argparse.ArgumentParser(
        description="P2 PRIMARY 분석. GT 완성·동결 후에만 실행한다")
    ap.add_argument("--base", required=True, help=f"{BASE_ARM} arm 결과 JSON")
    ap.add_argument("--candidate", required=True,
                    help=f"{CANDIDATE_ARM} arm 결과 JSON")
    ap.add_argument("--gt-freeze", required=True,
                    help="GT 동결 기록 JSON (n·sha256)")
    ap.add_argument("--exclude", help="query_id=reason 쉼표 목록 (사전 정의 사유만)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    gt = json.loads(Path(a.gt_freeze).read_text(encoding="utf-8"))
    require_frozen_gt(gt)
    exclude = dict(kv.split("=", 1) for kv in a.exclude.split(",")) \
        if a.exclude else None
    r = analyze(json.loads(Path(a.base).read_text(encoding="utf-8")),
                json.loads(Path(a.candidate).read_text(encoding="utf-8")),
                exclude=exclude)
    r["gt_freeze"] = {"n": gt["n"], "sha256": gt["sha256"]}
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"saved: {a.out}")
    print(f"  Δ = {r['delta_point']:+.4f}  CI {r['ci']}  "
          f"half-width {r['half_width']:.4f}  k={r['n_clusters']}")
    print(f"  판정: {r['verdict']} — {r['verdict_text']}")
    print(f"  채택: {r['adoption']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
