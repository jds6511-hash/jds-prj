"""I1 detector development 탐색 — **candidate 고정용. 성능 판정 아니다.**

사전등록: `I1_detector_재설계_사전등록_2026-08-18.md` +
`I1_detector_보충1_development절차_2026-08-20.md`.

A116/B24는 **이미 소비된 development set**이다. 이 표본으로 후보를 고르므로 여기
나오는 수치는 **선택 근거**일 뿐이고 성능 주장이 아니다. 성능 판정은 fresh
validation set에서 한 번만 한다.

**추정량을 현행 estimator에서 그대로 가져올 수 없다.** 현행 `i1a_recall`은 적중을
전수로 취급한다(C1·C4·C5가 모집단 전수). 그러나 새 규칙은 표집 셀(C0 8,430중 24,
C2 800중 24)에서도 발동하므로 **TP도 셀 모집단 가중이 필요하다.**

**두 축을 분리한다.**

    foreign_script_present  CJK >= 1자. 관측만. 파라미터 없음
    language_drift          hard fail 후보. 격자에서 탐색

반복 규칙(구 반복·어절 반복)은 **이 탐색의 범위 밖이고 변경하지 않는다.**
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 보충1 §2에서 고정한 격자. **결과를 보고 확장하지 않는다.**
R_GRID = (2, 3, 4, 5, 6)
T_GRID = (0.02, 0.05, 0.10, 0.15, 0.20)
COMBINERS = ("R_only", "T_only", "R_or_T", "R_and_T")
# 보충1 §5. 결과에 따라 움직이지 않는다
PRECISION_FLOOR = 0.95
MAX_CANDIDATES = 2
# 보충1 §4. 이 목록 밖의 분류를 만들지 않는다
FP_CATEGORIES = ("scene_text", "normal_foreign_expression")
FP_UNSEPARABLE = ("normal_foreign_expression",)
POSITIVE = "drift"
EXCLUDED = "excluded_unclear"
# `docs/재분석_I1검증셋B_2026-08-18.md` 공표값. 대조군 재현 게이트의 기준이다
PUBLISHED_BASELINE = {"precision_sample": 0.9861, "recall_est": 0.0815}
# 단순한 규칙을 선호한다 — 동률 처리용 순위
_SIMPLICITY = {"R_only": 0, "T_only": 0, "R_or_T": 1, "R_and_T": 1}


class DevError(RuntimeError):
    pass


def grid():
    """60개 구성. 절대 개수 축은 없다 — 대조군으로만 등장한다."""
    for r in R_GRID:
        yield {"combiner": "R_only", "R": r, "T": None}
    for t in T_GRID:
        yield {"combiner": "T_only", "R": None, "T": t}
    for c in ("R_or_T", "R_and_T"):
        for r in R_GRID:
            for t in T_GRID:
                yield {"combiner": c, "R": r, "T": t}


def foreign_script_present(inst: dict) -> bool:
    """진단 축. 재캡셔닝 트리거가 아니다. 파라미터가 없다."""
    return inst["cjk_count"] >= 1


def fires(inst: dict, cfg: dict) -> bool:
    r_hit = cfg["R"] is not None and inst["longest_cjk_run"] >= cfg["R"]
    t_hit = cfg["T"] is not None and inst["cjk_ratio"] > cfg["T"]
    c = cfg["combiner"]
    if c == "R_only":
        return r_hit
    if c == "T_only":
        return t_hit
    if c == "R_or_T":
        return r_hit or t_hit
    if c == "R_and_T":
        return r_hit and t_hit
    raise DevError(f"선언되지 않은 결합: {c!r}")


def baseline_cjk_fires(inst: dict) -> bool:
    """현행 규칙의 **CJK 부분만**. 반복 성분을 가르는 데 쓴다."""
    return inst["cjk_count"] >= 3 or inst["cjk_ratio"] > 0.2


def repetition_component(inst: dict) -> bool:
    """현행 적중 중 **CJK로 설명되지 않는 부분** = 반복 규칙 발동.

    현행 detector가 `CJK 규칙 OR 반복 규칙`이므로 이 차집합이 반복 성분이다.
    C1(CJK 0인데 적중)이 여기서 나왔다. 반복 규칙은 변경하지 않으므로 후보에도
    그대로 남는다.
    """
    return bool(inst.get("i1a_hit")) and not baseline_cjk_fires(inst)


def baseline_fires(inst: dict) -> bool:
    """대조군 = **현행 detector 전체**. CJK 규칙만 쓰면 반복 적중이 사라진다."""
    if "i1a_hit" in inst:
        return bool(inst["i1a_hit"])
    return baseline_cjk_fires(inst)


def fires_total(inst: dict, cfg) -> bool:
    """배포 형태의 후보 = `language_drift(CJK) OR 반복`. 비교 대상을 맞춘다."""
    if cfg == "baseline":
        return baseline_fires(inst)
    return fires(inst, cfg) or repetition_component(inst)


def census_cells(pop: dict, sampled: dict) -> set:
    """표집 수가 모집단에 닿은 셀. 스케일링하지 않는다."""
    return {c for c, n in sampled.items() if n >= pop.get(c, 0)}


def _cell_stats(rows: list, cfg, pop: dict, census: set) -> dict:
    """셀별 가중 성분.

    **전수 셀은 스케일링하지 않는다.** `pop / analyzable`로 곱하면 관측하지 못한
    unclear를 관측률로 대입하는 것이 되고, 전수 셀에는 그럴 근거가 없다
    (실측: 대조군 recall이 0.0815에서 0.0919로 부풀었다).
    `cjk_count == 0` 셀은 표집 불확실성 자체가 없다.
    """
    out = {}
    for cell in sorted({r["cell"] for r in rows}):
        s = [r for r in rows if r["cell"] == cell]
        ok = [r for r in s if r["true"] != EXCLUDED]
        n = len(ok)
        derived = all(r["cjk_count"] == 0 for r in s)
        is_census = cell in census
        drift = sum(1 for r in ok if r["true"] == POSITIVE)
        tp = sum(1 for r in ok if r["true"] == POSITIVE and fires_total(r, cfg))
        fired = sum(1 for r in ok if fires_total(r, cfg))
        p = pop[cell]
        w = (lambda k: float(k)) if is_census else (
            lambda k: round(p * k / n, 1) if n else 0.0)
        out[cell] = {
            "population": p, "sampled": len(s), "analyzable": n,
            "is_census": is_census,
            "drift": drift, "tp": tp, "fired": fired,
            "est_drift": w(drift), "est_tp": w(tp), "est_fired": w(fired),
            "recall_est": (round(tp / drift, 4) if drift else None),
            "uncertainty": "none_by_derivation" if derived else (
                "none_census" if is_census else "sampling"),
        }
    return out


def evaluate(rows: list, cfg, pop: dict, census: set = frozenset()) -> dict:
    """한 구성의 descriptive 지표. **가중·비가중 precision을 둘 다 낸다.**

    비가중은 전수 셀(C4 78건)이 지배하고 가중은 C2(800)가 지배한다 — 하나만
    보면 오독한다(보충1 §3-2).
    """
    by_cell = _cell_stats(rows, cfg, pop, census)
    ok = [r for r in rows if r["true"] != EXCLUDED]
    fired = [r for r in ok if fires_total(r, cfg)]
    tp = [r for r in fired if r["true"] == POSITIVE]
    est_tp = sum(c["est_tp"] for c in by_cell.values())
    est_drift = sum(c["est_drift"] for c in by_cell.values())
    est_fired = sum(c["est_fired"] for c in by_cell.values())
    fp = Counter(r["true"] for r in fired if r["true"] != POSITIVE)
    return {
        "config": cfg,
        "n_analyzable": len(ok),
        "n_excluded_unclear": len(rows) - len(ok),
        "n_fired": len(fired), "n_tp": len(tp),
        "precision_sample": (round(len(tp) / len(fired), 4) if fired else None),
        "precision_weighted": (round(est_tp / est_fired, 4) if est_fired else None),
        "est_tp": est_tp, "est_drift_total": est_drift, "est_fired": est_fired,
        "recall_est": (round(est_tp / est_drift, 4) if est_drift else None),
        "fp_breakdown": {k: v for k, v in fp.items() if k in FP_CATEGORIES},
        # 선언 범주 밖의 FP도 남긴다 — 걸러 버리면 회계에서 사라진다.
        # C1(CJK 0인데 반복 규칙으로 적중)이 실제로 여기 들어온다
        "fp_outside_declared": {k: v for k, v in fp.items()
                                if k not in FP_CATEGORIES},
        "by_cell": by_cell,
    }


def select(results: list) -> list:
    """보충1 §5. 제약을 만족하는 것이 없으면 **빈 목록**이 정답이다."""
    ok = [r for r in results
          if (r.get("precision_weighted") or 0) >= PRECISION_FLOOR]
    ok.sort(key=lambda r: (-(r.get("recall_est") or 0),
                           _SIMPLICITY[r["config"]["combiner"]],
                           r["config"]["R"] if r["config"]["R"] is not None else 0,
                           -(r["config"]["T"] or 0)))
    return ok[:MAX_CANDIDATES]


def run(rows: list, pop: dict, census: set = frozenset(),
        published: dict = None) -> dict:
    """격자를 **1회** 계산한다. 반복 탐색은 종료 규칙이 금지한다(보충1 §6).

    `published`가 주어지면 **대조군 재현 게이트**를 적용한다 — 새 추정량이 공표된
    현행 수치를 재현하지 못하면 추정량이 틀린 것이고, 그 상태의 후보 순위는
    해석할 수 없다.
    """
    results = [evaluate(rows, cfg, pop, census) for cfg in grid()]
    base = evaluate(rows, "baseline", pop, census)
    base["config"] = "current: is_corrupted_caption (CJK rule OR repetition rule)"
    if published:
        bad = {k: {"recomputed": base.get(k), "published": v}
               for k, v in published.items() if base.get(k) != v}
        base["reproduction_check"] = {
            "published": dict(published),
            "recomputed": {k: base.get(k) for k in published},
            "match": not bad}
        if bad:
            raise DevError(
                f"대조군 재현 게이트 FAIL: {bad} — 새 추정량이 공표된 현행 수치를 "
                "재현하지 못한다. 허용 오차를 늘리거나 게이트를 끄지 마라. "
                "이 상태의 후보 순위는 해석할 수 없다")
    cands = select(results)
    diag = [r for r in rows if foreign_script_present(r)]
    return {
        "probe": "i1_detector_dev",
        "stage": "development_only",
        "prereg": ("docs/preregistration/I1_detector_보충1_development절차_"
                   "2026-08-20.md"),
        "n_instances": len(rows),
        "true_label_dist": dict(Counter(r["true"] for r in rows)),
        "foreign_script_present": {
            "definition": "cjk_count >= 1",
            "n_instances": len(diag),
            "note": "진단 축이다. 재캡셔닝 트리거가 아니다",
        },
        "grid_size": len(results),
        "grid_results": results,
        "baseline": base,
        "precision_floor": PRECISION_FLOOR,
        "candidates": cands,
        "candidate_cap": MAX_CANDIDATES,
        "fp_categories": list(FP_CATEGORIES),
        "fp_unseparable": {
            "categories": list(FP_UNSEPARABLE),
            "reason": ("A는 화면만 보고 B는 화면 대조만 한다 — 화면에 없는 정상 "
                       "외국어 표현은 현 라벨 체계로 분리할 수 없다. 추정하지 않는다"),
        },
        "structural_fact": ("cjk_count == 0이면 어떤 후보도 발동할 수 없다 — FP는 "
                            "CJK가 있는 인스턴스에서만 나온다"),
        "repetition_rules": ("구 반복·어절 반복 규칙은 이 탐색의 범위 밖이고 "
                             "변경하지 않았다. C1은 그 규칙에서 나왔다"),
        "limits": ("이 표본으로 후보를 골랐으므로 여기 수치는 **선택 근거**일 뿐이다. "
                   "성능 판정은 fresh validation set에서 현행과 동시에, 한 번만 한다. "
                   "development set 수치로 우열을 말하지 않는다"),
    }


def load_rows(kit=None, bkit=None) -> tuple:
    """A 매니페스트 · A/B 라벨에서 참 라벨을 붙인다. 도출 규칙은 재사용한다."""
    from i1_stage_b_analysis import load, true_label
    man, a, b, bman = load(kit, bkit)
    targets = set(bman["targets"])
    pop = man["population_by_cell"]
    rows = []
    for inst in man["instances"]:
        sid = inst["sample_id"]
        bl = b.get(sid) if sid in targets else None
        rows.append({**inst, "cell_population": pop[inst["cell"]],
                     "true": true_label(inst, a.get(sid, ""), bl)})
    return rows, pop, bman.get("a_labels_sha256")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows, pop, a_sha = load_rows()
    sampled = Counter(x["cell"] for x in rows)
    r = run(rows, pop, census_cells(pop, sampled), PUBLISHED_BASELINE)
    r["a_labels_sha256"] = a_sha
    r["census_cells"] = sorted(census_cells(pop, sampled))
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"saved: {a.out}")
    print(f"grid={r['grid_size']} candidates={len(r['candidates'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
