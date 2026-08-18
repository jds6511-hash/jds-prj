"""[I1 B단계 분석 — A × B 도출 규칙으로 참 라벨을 만들고 precision·recall을 낸다]

사전등록: `I1검증셋_사전등록_2026-08-18.md` · `보충_B단계경계_2026-08-18.md` ·
`보충2_B단계_C0생략_2026-08-18.md`.

**B가 끝나기 전에는 `precision`·`recall`이라는 말을 쓰지 않는다**(보충 §고정하는 경계).
이 모듈은 B 라벨이 완결됐을 때만 그 키를 만든다.

## 도출 규칙 (사전등록 §도출 규칙 그대로)

    캡션 CJK 있음 · A cjk_text_present · B matches_screen       → scene text (적중이면 오탐)
    캡션 CJK 있음 · A cjk_text_present · B drift_despite_text   → drift
    캡션 CJK 있음 · A korean_text_only·no_text                  → drift (B 불요)
    캡션 CJK 없음                                               → CJK drift 아님
    A unclear 또는 B unclear                                    → 제외, 수를 보고

## recall의 분모

I1a 적중은 **모집단 전수**(C1·C4·C5)라 표집오차가 없다. 미탐 성분은 **표집된 I1a
음성**에서만 추정되므로 셀 모집단으로 가중한다. C2 모집단 800 중 24만 봤기 때문에
**미탐률 CI가 넓다** — 폭을 반드시 병기한다(사전등록 §남는 한계).

C0은 human label을 생략했다(보충2). **분모에서 빼는 것이 아니라** 캡션 CJK가 0이라
도출 규칙상 drift가 될 수 없는 셀로 다룬다.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "label_kit" / "i1_frames"
BKIT = ROOT / "label_kit" / "i1_stage_b"
OUT = Path(__file__).resolve().parent / "_scratch"
NO_SCREEN = ("no_text", "korean_text_only")
B_LABELS = ("matches_screen", "drift_despite_text", "drift_no_text", "unclear")


class AnalysisError(RuntimeError):
    pass


def _csv(path) -> list:
    return list(csv.DictReader(Path(path).read_text(encoding="utf-8-sig").splitlines()))


def load(kit=None, bkit=None) -> tuple:
    kit, bkit = Path(kit or KIT), Path(bkit or BKIT)
    man = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    a = {r["sample_id"]: (r.get("label") or "").strip() for r in _csv(kit / "labels.csv")}
    b = {r["sample_id"]: (r.get("label_b") or "").strip()
         for r in _csv(bkit / "labels_b.csv")}
    bman = json.loads((bkit / "manifest_b.json").read_text(encoding="utf-8"))
    return man, a, b, bman


def true_label(inst: dict, a: str, b: str | None) -> str:
    """사전등록 도출 규칙. **여기서 규칙을 새로 만들지 않는다.**"""
    # **순서 주의.** 보충2는 `caption_cjk_count == 0`이면 파생값으로 false라고
    # 못박았다 — A가 unclear여도 그렇다. 그래서 이 검사가 unclear보다 먼저다.
    # (사전등록 표는 두 행의 우선순위를 명시하지 않아 여기서 해소한다. 규칙을
    #  바꾸는 것이 아니라 보충2의 명시적 파생 규칙을 따르는 것이다.)
    if inst["cjk_count"] == 0:
        return "not_cjk_drift"
    if a == "unclear" or b == "unclear":
        return "excluded_unclear"
    if a == "cjk_text_present":
        if b is None:
            raise AnalysisError(
                f"{inst['sample_id']}: A가 cjk_text_present인데 B 라벨이 없다 — "
                f"이 인스턴스는 B 없이 참 라벨을 정할 수 없다")
        return {"matches_screen": "scene_text",
                "drift_despite_text": "drift"}[b]
    if a in NO_SCREEN:
        return "drift"
    raise AnalysisError(f"{inst['sample_id']}: 알 수 없는 A 라벨 {a!r}")


def _wilson(k: int, n: int, z: float = 1.96) -> list:
    """Wilson 구간. 비율이 0·1에 붙어도 폭이 생긴다 — 여기서 20/20이 나온다."""
    if not n:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return [round(max(0.0, (c - r) / d), 4), round(min(1.0, (c + r) / d), 4)]


def analyze(man: dict, a: dict, b: dict, bman: dict) -> dict:
    targets = set(bman["targets"])
    missing = [s for s in targets if b.get(s) not in B_LABELS]
    if missing:
        raise AnalysisError(
            f"B 라벨이 완결되지 않았다({len(missing)}건, 예: {missing[:3]}) — "
            f"완결 전에는 precision·recall을 산출하지 않는다")

    # 셀 모집단은 **join 시점에 붙인다** — 가중치를 빼먹을 수 없게 하려는
    # `i1_label_analysis`의 설계를 그대로 따른다.
    pop = man["population_by_cell"]
    rows = []
    for inst in man["instances"]:
        sid = inst["sample_id"]
        bl = b.get(sid) if sid in targets else None
        rows.append({**inst, "cell_population": pop[inst["cell"]],
                     "a": a.get(sid, ""), "b": bl,
                     "true": true_label(inst, a.get(sid, ""), bl)})
    hits = [r for r in rows if r["i1a_hit"]]
    hits_ok = [r for r in hits if r["true"] != "excluded_unclear"]
    n_drift_hit = sum(1 for r in hits_ok if r["true"] == "drift")
    n_scene_hit = sum(1 for r in hits_ok if r["true"] == "scene_text")

    # 미탐 성분 — 표집된 I1a 음성. 셀별로 비율을 내고 모집단으로 가중한다.
    miss = {}
    for cell in sorted({r["cell"] for r in rows if not r["i1a_hit"]}):
        s = [r for r in rows if not r["i1a_hit"] and r["cell"] == cell]
        ok = [r for r in s if r["true"] != "excluded_unclear"]
        k = sum(1 for r in ok if r["true"] == "drift")
        labeled = [r for r in s if r["b"] is not None]
        # **파생 셀에는 표집 불확실성이 없다.** 셀이 `cjk_count == 0`으로 정의돼
        # 있으면 drift가 표본에서 0으로 나온 것이 아니라 도출 규칙상 될 수 없다.
        # Wilson CI를 붙이면 모집단(8430)이 곱해져 허구의 상한이 생기고 recall
        # 하한을 그것이 지배한다 — 2026-08-18 실측에서 1553.6이 나왔다.
        derived = not labeled and all(r["cjk_count"] == 0 for r in s)
        ci = [0.0, 0.0] if derived else _wilson(k, len(ok))
        miss[cell] = {
            "population": pop[cell], "sampled": len(s),
            "human_labeled": len(labeled),
            "analyzable": len(ok), "drift": k, "unclear": len(s) - len(ok),
            "drift_rate": (round(k / len(ok), 4) if ok else None),
            "drift_rate_ci": ci,
            "basis": ("human_label" if labeled else
                      "derived: caption_cjk_count == 0 (보충2)"),
            "uncertainty": "none_by_derivation" if derived else "sampling",
            "est_drift_population": (round(pop[cell] * k / len(ok), 1) if ok else None),
            "est_drift_population_ci": [
                round(pop[cell] * x, 1) if x is not None else None for x in ci],
        }

    det = n_drift_hit                                  # 적중은 전수라 그대로
    est_missed = sum(m["est_drift_population"] or 0 for m in miss.values())
    lo = sum((m["est_drift_population_ci"][0] or 0) for m in miss.values())
    hi = sum((m["est_drift_population_ci"][1] or 0) for m in miss.values())
    return {
        "probe": "i1_stage_b_analysis",
        "stage": "A_and_B",
        "prereg": bman.get("prereg"),
        "a_labels_sha256": bman.get("a_labels_sha256"),
        "n_instances": len(rows),
        "true_label_dist": dict(Counter(r["true"] for r in rows)),
        "b_label_dist": dict(Counter(v for v in b.values())),
        "i1a_precision": {
            "n_hits_census": len(hits),
            "n_analyzable": len(hits_ok),
            "n_excluded_unclear": len(hits) - len(hits_ok),
            "n_drift": n_drift_hit, "n_scene_text": n_scene_hit,
            "precision": (round(n_drift_hit / len(hits_ok), 4) if hits_ok else None),
            "precision_ci": _wilson(n_drift_hit, len(hits_ok)),
            "is_census": True,
            "note": ("적중 중 A가 cjk_text_present인 것이 0건이라 matches_screen이 "
                     "나올 여지가 없었다 — precision이 B와 무관하게 결정됐다"),
        },
        "miss_zone_by_cell": miss,
        "i1a_recall": {
            "detected_drift": det,
            "est_missed_drift": round(est_missed, 1),
            "recall": (round(det / (det + est_missed), 4) if det + est_missed else None),
            "recall_ci_from_miss_ci": [
                round(det / (det + hi), 4) if det + hi else None,
                round(det / (det + lo), 4) if det + lo else None],
            "limits": ("분모의 미탐 성분은 **표집된 I1a 음성**에서만 추정된다. "
                       "C2는 모집단 800 중 24만 봤다 — CI 폭을 그대로 읽어라. "
                       "표본은 프레임 클러스터라 실제 불확실성은 이 Wilson 구간보다 "
                       "넓을 수 있다(사전등록 §남는 한계)."),
        },
        "scope": ("**CJK drift에 한정한다.** C0을 B에서 직접 보지 않았으므로 비-CJK "
                  "외국어 drift나 일반 캡션 오염으로 확장하지 않는다(보충2)."),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT / "i1_stage_b_analysis.json"))
    a = ap.parse_args()
    r = analyze(*load())
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"저장: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
