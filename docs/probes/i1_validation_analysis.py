"""I1 detector validation — **한 번만 평가한다.** 라벨 도착 전에 커밋됐다.

사전등록: `I1_detector_보충2_validation표집_2026-08-20.md` +
`보충3_표집확정_2026-08-20.md`. freeze: `docs/I1_detector_candidate_freeze_2026-08-20.md`.

세 규칙을 같은 표본에서 함께 잰다 — 현행 · primary · fallback. 반복 규칙은 셋 모두
동일하고 변경하지 않았으므로 이 비교는 **CJK 축의 비교**다.

**fresh 성분과 carried-over 성분을 섞어 부르지 않는다.** C1·C4·C5는 잔여 모집단이
0이라(보충3 §1) development census를 이어받는다. 그 셀들은 **이번에 재검증되지
않았다.** 그래서 산출을 두 블록으로 나눈다.

    fresh_strata_only          C0 · C2 — 이번 표본으로만 계산
    combined_with_carried_over C1·C4·C5를 더한 값. **플래그와 목록을 붙인다**

**튜닝 손잡이가 없다.** 임계·격자를 인자로 받지 않는다. 결과가 기대와 달라도 `R=1`을
추가하거나 임계를 재조정하지 않는다(보충1 §6 종료 규칙).
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import i1_detector_dev as D                                    # noqa: E402

KIT = ROOT / "label_kit" / "i1_validation"
META = ROOT / "label_kit" / "i1_validation_meta"
RULES = {"baseline": "baseline",
         "primary": D.FROZEN_PRIMARY,
         "fallback": D.FROZEN_FALLBACK}
FRESH_STRATA = ("C0", "C2")
CARRIED_OVER_STRATA = ("C1", "C4", "C5")
A_LABELS = ("no_text", "korean_text_only", "cjk_text_present", "unclear")
NO_SCREEN = ("no_text", "korean_text_only")
POSITIVE, EXCLUDED = "drift", "excluded_unclear"


class AnalysisError(RuntimeError):
    pass


def _wilson(k: int, n: int, z: float = 1.96) -> list:
    if not n:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return [round(max(0.0, (c - r) / d), 4), round(min(1.0, (c + r) / d), 4)]


def true_label(inst: dict, a: str, b) -> str:
    """도출 규칙은 development과 **같은 것**을 쓴다. 새로 만들지 않는다."""
    if inst["cjk_count"] == 0:
        return "not_cjk_drift"
    if a == "unclear" or b == "unclear":
        return EXCLUDED
    if a == "cjk_text_present":
        if b is None:
            raise AnalysisError(
                f"{inst['sample_id']}: A가 cjk_text_present인데 B 라벨이 없다")
        return {"matches_screen": "scene_text",
                "drift_despite_text": POSITIVE,
                "drift_no_text": POSITIVE}[b]
    if a in NO_SCREEN:
        return POSITIVE
    raise AnalysisError(f"{inst['sample_id']}: 알 수 없는 A 라벨 {a!r}")


def _metrics(rows: list, name: str, pop: dict) -> dict:
    cfg = RULES[name]
    by_cell = {}
    for cell in sorted({r["cell"] for r in rows}):
        s = [r for r in rows if r["cell"] == cell]
        ok = [r for r in s if r["true"] != EXCLUDED]
        n = len(ok)
        drift = sum(1 for r in ok if r["true"] == POSITIVE)
        tp = sum(1 for r in ok if r["true"] == POSITIVE and D.fires_total(r, cfg))
        fired = sum(1 for r in ok if D.fires_total(r, cfg))
        p = pop.get(cell, 0)
        w = (lambda k: round(p * k / n, 1)) if n else (lambda k: 0.0)
        by_cell[cell] = {
            "population": p, "sampled": len(s), "analyzable": n,
            "drift": drift, "tp": tp, "fired": fired,
            "est_drift": w(drift), "est_tp": w(tp), "est_fired": w(fired),
            "recall_est": (round(tp / drift, 4) if drift else None),
            "recall_ci_wilson": _wilson(tp, drift) if drift else [None, None],
        }
    ok = [r for r in rows if r["true"] != EXCLUDED]
    fired = [r for r in ok if D.fires_total(r, cfg)]
    tp = [r for r in fired if r["true"] == POSITIVE]
    est_tp = sum(c["est_tp"] for c in by_cell.values())
    est_drift = sum(c["est_drift"] for c in by_cell.values())
    est_fired = sum(c["est_fired"] for c in by_cell.values())
    fp = Counter(r["true"] for r in fired if r["true"] != POSITIVE)
    return {
        "rule": cfg,
        "n_analyzable": len(ok),
        "n_excluded_unclear": len(rows) - len(ok),
        "n_fired": len(fired), "n_tp": len(tp),
        "precision_sample": (round(len(tp) / len(fired), 4) if fired else None),
        "precision_ci_wilson": _wilson(len(tp), len(fired)),
        "precision_weighted": (round(est_tp / est_fired, 4) if est_fired else None),
        "est_tp": est_tp, "est_drift_total": est_drift, "est_fired": est_fired,
        "recall_est": (round(est_tp / est_drift, 4) if est_drift else None),
        "fp_breakdown": {k: v for k, v in fp.items() if k in D.FP_CATEGORIES},
        "fp_outside_declared": {k: v for k, v in fp.items()
                                if k not in D.FP_CATEGORIES},
        "by_cell": by_cell,
    }


def _combine(fresh: dict, carried: dict, name: str) -> dict:
    """carried-over census를 더한다. **전수라 스케일링하지 않는다.**"""
    est_tp = fresh["est_tp"] + sum(c["tp"][name] for c in carried.values())
    est_drift = fresh["est_drift_total"] + sum(c["drift"] for c in carried.values())
    est_fired = fresh["est_fired"] + sum(c["tp"][name] for c in carried.values())
    return {"est_tp": est_tp, "est_drift_total": est_drift,
            "est_fired": est_fired,
            "recall_est": (round(est_tp / est_drift, 4) if est_drift else None),
            "precision_weighted": (round(est_tp / est_fired, 4)
                                   if est_fired else None)}


def analyze(rows: list, a_labels: dict, b_labels: dict, pop: dict,
            carried: dict = None, published_carried_tp: dict = None) -> dict:
    """`rows`는 매니페스트 인스턴스. `pop`은 **fresh 층의 잔여 모집단**이다."""
    need_a = [r for r in rows if r["cjk_count"] > 0]
    missing_a = [r["sample_id"] for r in need_a
                 if a_labels.get(r["sample_id"], "") not in A_LABELS]
    if missing_a:
        raise AnalysisError(
            f"A 라벨이 덜 찼다({len(missing_a)}건, 예: {missing_a[:3]}) — "
            "완결 전에는 지표를 산출하지 않는다")
    marked = []
    for r in rows:
        sid = r["sample_id"]
        a = a_labels.get(sid, "")
        b = b_labels.get(sid) if a == "cjk_text_present" else None
        if a == "cjk_text_present" and b is None:
            raise AnalysisError(
                f"{sid}: B 라벨이 없다 — cjk_text_present는 B 없이 참 라벨을 "
                "정할 수 없다")
        marked.append({**r, "a": a, "b": b, "true": true_label(r, a, b)})

    fresh = {name: _metrics(marked, name, pop) for name in RULES}
    for m in fresh.values():
        m["contains_carried_over"] = False

    out = {
        "probe": "i1_validation_analysis",
        "stage": "validation_one_shot",
        "prereg": ("docs/preregistration/I1_detector_보충2_validation표집_"
                   "2026-08-20.md + 보충3_표집확정_2026-08-20.md"),
        "freeze_doc": "docs/I1_detector_candidate_freeze_2026-08-20.md",
        "n_instances": len(marked),
        "true_label_dist": dict(Counter(r["true"] for r in marked)),
        "fresh_strata": list(FRESH_STRATA),
        "carried_over_strata": list(CARRIED_OVER_STRATA),
        "fresh_strata_only": {**fresh, "contains_carried_over": False},
        "ci_interpretation": "descriptive_only",
        # primary와 fallback의 development 차이는 C4 인스턴스 1건이었고 C4 잔여가
        # 0이다. **그 1건을 다시 꺼내 두 후보를 가르지 않는다** — 후보 선정에 쓰인
        # 바로 그 인스턴스이기 때문이다.
        "primary_vs_fallback": {
            "separable_on_fresh_data": False,
            "reason": ("두 후보의 차이가 나타난 층은 잔여 모집단이 0이다 — 새 "
                       "표본에서 가를 수 없다"),
            "resolution": "simple_rule_preference",
            "resolved_to": "fallback (R_only, R=2)",
        },
        "limits": ("Wilson 구간은 descriptive다. 표본이 프레임 클러스터이고 같은 "
                   "영상·콘텐츠 구조가 남아 있으므로 실제 불확실성은 이 구간보다 "
                   "넓을 수 있다. 폭이 좁아졌다고 정밀도가 충분하다고 선언하지 "
                   "않는다"),
    }
    if carried:
        if published_carried_tp:
            got = {k: sum(c["tp"][k] for c in carried.values())
                   for k in published_carried_tp}
            match = all(got[k] == v for k, v in published_carried_tp.items())
            out["reproduction_check"] = {"published": dict(published_carried_tp),
                                         "recomputed": got, "match": match}
            if not match:
                raise AnalysisError(
                    f"carried-over 재현 게이트 FAIL: {got} vs "
                    f"{published_carried_tp} — 이어받은 census가 development "
                    "공표값과 다르다. candidate 결과를 열지 않는다")
        out["combined_with_carried_over"] = {
            **{name: _combine(fresh[name], carried, name) for name in RULES},
            "contains_carried_over": True,
            "carried_over_strata": sorted(carried),
            "note": ("이 블록은 development census를 이어받은 성분을 포함한다. "
                     "그 층들은 이번에 **재검증되지 않았다** — 전체가 fresh한 "
                     "추정값이 아니다"),
        }
    return out


def _csv(path) -> list:
    return list(csv.DictReader(Path(path).read_text(encoding="utf-8-sig")
                               .splitlines()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--carried", help="carried-over census JSON (optional)")
    a = ap.parse_args()
    man = json.loads((META / "manifest_v.json").read_text(encoding="utf-8"))
    al = {r["sample_id"]: (r.get("label") or "").strip()
          for r in _csv(KIT / "labels_v.csv")}
    bp = KIT / "labels_vb.csv"
    bl = ({r["sample_id"]: (r.get("label_b") or "").strip() for r in _csv(bp)}
          if bp.exists() else {})
    carried = (json.loads(Path(a.carried).read_text(encoding="utf-8"))
               if a.carried else None)
    r = analyze(man["instances"], al, bl, man["remaining_population"], carried)
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"saved: {a.out}")
    for name in RULES:
        m = r["fresh_strata_only"][name]
        print(f"  {name}: fired={m['n_fired']} tp={m['n_tp']} "
              f"p_s={m['precision_sample']} recall={m['recall_est']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
