"""I1 human label 분석 — **라벨을 보기 전에** 계산 규칙을 고정한 코드.

사전등록: `docs/preregistration/I1검증셋_사전등록_2026-08-18.md` +
`I1검증셋_보충_B단계경계_2026-08-18.md`.

**두 추정량을 코드에서 분리한다.** 섞으면 8,430건짜리 셀을 24건처럼 세게 된다.

| 추정량 | 표집 | 계산 |
|---|---|---|
| **I1a 적중분 precision** | 82건 **전수**(C1+C3+C4+C5) | 표집오차 없음. 그대로 비율 |
| **I1a 음성 유병률** | C0 8,430중 24 · C2 800중 24 **표본** | **셀 가중 필수** |

**A 단계만으로 recall을 말하지 않는다.** A는 "화면에 글자가 있는가"만 답한다.
캡션의 외국어가 그 글자를 옮긴 것인지(`matches_screen`)는 B가 답한다. 그래서
A만 있는 시점의 값은 이름에 `_vs_frame_text_proxy`를 박고, `summarize`가
`recall` 키를 아예 만들지 않는다.

재현: python docs/probes/i1_label_analysis.py
"""
import argparse, csv, io, json, sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LABELS_DIR = ROOT / "label_kit" / "i1_frames"
OUT = Path(__file__).resolve().parent / "_scratch"
VALID = ("cjk_text_present", "korean_text_only", "no_text", "unclear")
# 화면에 해당 글자가 없는데 캡션에 CJK가 있으면 drift 후보다
NO_SCREEN_TEXT = ("korean_text_only", "no_text")


class AnalysisError(RuntimeError):
    pass


def join(manifest: dict, labels: dict) -> list:
    """표본 대장 × 프레임 라벨. 프레임 하나의 라벨이 그 프레임의 **모든 arm
    인스턴스**에 붙는다(프레임은 4 arm 공통이므로)."""
    pop = manifest.get("population_by_cell") or {}
    if not pop:
        raise AnalysisError("manifest에 population_by_cell이 없다 — 셀 가중을 "
                            "못 걸면 8,430건 셀을 24건처럼 세게 된다")
    rows, missing = [], []
    for inst in manifest["instances"]:
        lab = labels.get(inst["sample_id"])
        if not lab:
            missing.append(inst["sample_id"])
            continue
        if lab not in VALID:
            raise AnalysisError(f"{inst['sample_id']}: 알 수 없는 라벨 '{lab}'")
        # 셀 모집단을 **행에 붙인다** — 가중치를 인자로 두면 빼먹은 채
        # 호출해도 조용히 통과해 표본 비율이 모집단 비율로 둔갑한다
        rows.append({**inst, "label": lab, "cell_population": pop[inst["cell"]]})
    if missing:
        # 조용히 빼면 분모가 줄어 값이 부풀려진다
        raise AnalysisError(f"라벨 미기입 {len(set(missing))}건 (예: "
                            f"{sorted(set(missing))[:5]}) — 채운 뒤 다시 돌려라")
    return rows


def analyzable(rows: list) -> list:
    return [r for r in rows if r["label"] != "unclear"]


def unclear_rate(rows: list) -> float:
    return round(sum(1 for r in rows if r["label"] == "unclear") / max(len(rows), 1), 4)


def i1a_precision(rows: list) -> dict:
    """**전수 추정량.** I1a가 잡은 것 중 화면에 해당 글자가 없는 비율.

    `precision`이라고 단정하지 않는다 — 화면에 한자가 있어도 캡션의 외국어가
    그것과 무관할 수 있다(`drift_despite_text`). 그 판정은 B가 한다."""
    hits = [r for r in analyzable(rows) if r["i1a_hit"]]
    drift = sum(1 for r in hits if r["label"] in NO_SCREEN_TEXT)
    return {"n": len(hits), "drift_proxy": drift,
            "screen_text_present": len(hits) - drift,
            "precision_vs_frame_text_proxy":
                round(drift / len(hits), 4) if hits else None,
            "is_census": True,
            "note": "I1a 적중은 모집단 전수라 표집오차가 없다. 다만 B 판정 전이라 "
                    "화면 글자 유무를 대리값으로 쓴 값이다"}


def foreign_script_prevalence(rows: list) -> dict:
    """**표본 추정량.** I1a가 놓친 쪽에서 화면 글자가 없는데 CJK가 섞인 비율.

    셀별 추출률이 다르므로(C0 8,430중 24 · C2 800중 24) 모집단을 말하려면
    **셀 가중**이 필요하다. 표본 비율을 그대로 쓰면 C0을 C2와 같은 무게로 센다."""
    neg = [r for r in analyzable(rows) if not r["i1a_hit"]]
    if not neg:
        return {"n": 0, "unweighted": None, "weighted": None, "weights": {}}
    by_cell, weights = {}, {}
    for r in neg:
        by_cell.setdefault(r["cell"], []).append(
            1.0 if r["label"] == "cjk_text_present" else 0.0)
        weights[r["cell"]] = r["cell_population"]
    num = sum(weights[c] * float(np.mean(v)) for c, v in by_cell.items())
    return {"n": len(neg),
            "unweighted": round(float(np.mean([x for v in by_cell.values() for x in v])), 4),
            "weighted": round(num / sum(weights.values()), 4),
            "weights": weights,
            "by_cell": {c: {"n": len(v), "rate": round(float(np.mean(v)), 4)}
                        for c, v in by_cell.items()}}


def _dist(rows: list) -> dict:
    return {"n": len(rows), "labels": dict(Counter(r["label"] for r in rows))}


def by_arm(rows: list) -> dict:
    out = {}
    for r in rows:
        out.setdefault(r["arm"], []).append(r)
    return {k: _dist(v) for k, v in sorted(out.items())}


def by_cjk_stratum(rows: list) -> dict:
    """검출기 임계(CJK 절대 3자)가 어디서 갈리는지 보려면 이 층화가 필요하다."""
    def bucket(n):
        return "0" if n == 0 else "1-2" if n <= 2 else "3-9" if n <= 9 else "10+"
    out = {b: [] for b in ("0", "1-2", "3-9", "10+")}
    for r in rows:
        out[bucket(r["cjk_count"])].append(r)
    return {k: _dist(v) for k, v in out.items()}


def cluster_ci(values, groups, B: int = 2000, seed: int = 42) -> dict:
    """**영상 클러스터** 부트스트랩. 같은 영상의 프레임은 상관되므로 표본 단위로
    재표집하면 CI가 실제보다 좁아진다."""
    v = np.asarray(values, dtype=float)
    g = np.asarray(groups)
    vids = sorted(set(groups))
    pos = {x: np.flatnonzero(g == x) for x in vids}
    rng = np.random.default_rng(seed)
    stat = [float(np.concatenate([v[pos[vids[j]]] for j in
                                  rng.integers(0, len(vids), size=len(vids))]).mean())
            for _ in range(B)]
    lo, hi = (float(x) for x in np.percentile(stat, [2.5, 97.5]))
    return {"point": round(float(v.mean()), 4), "ci95": [round(lo, 4), round(hi, 4)],
            "n_videos": len(vids), "unit": "video-cluster"}


def stage_b_pending(rows: list) -> dict:
    """보충 사전등록의 (가)·(나) — B 판정이 **필수**인 집합.

    (가) 화면에 글자가 있고 캡션에도 CJK가 있는 인스턴스: 캡션의 외국어가 그
        글자를 옮긴 것인지(`matches_screen`) 아닌지(`drift_despite_text`)를
        갈라야 precision이 성립한다.
    (나) I1a 음성 표본: 여기서 발견되는 drift가 recall 분모의 미탐 성분이다."""
    a = sorted({r["sample_id"] for r in analyzable(rows)
                if r["label"] == "cjk_text_present" and r["cjk_count"] > 0})
    b = sorted({r["sample_id"] for r in analyzable(rows) if not r["i1a_hit"]})
    return {"a_cjk_present_with_caption_cjk": a, "b_i1a_negative_sample": b,
            "note": "이 둘이 끝나기 전에는 precision·recall이라는 말을 쓰지 않는다"}


def summarize(rows: list, manifest: dict) -> dict:
    """**`recall` 키를 만들지 않는다.** A 단계만으로는 정의되지 않는다."""
    ana = analyzable(rows)
    return {
        "stage": "A_only",
        "n_instances": len(rows), "n_analyzable": len(ana),
        "unclear_rate": unclear_rate(rows),
        "i1a_hits_census": i1a_precision(rows),
        "i1a_negative_sampled": foreign_script_prevalence(rows),
        "by_arm": by_arm(ana), "by_cjk_stratum": by_cjk_stratum(ana),
        "screen_text_rate_ci": cluster_ci(
            [1.0 if r["label"] == "cjk_text_present" else 0.0 for r in ana],
            [r["video_id"] for r in ana]) if ana else None,
        "stage_b_pending": stage_b_pending(rows),
        "limits": ["A 단계만이다 — precision·recall은 B 판정 후에만 말한다",
                   "구간 5초에 대표 프레임 1장이라 다른 시점의 글자를 놓친다 "
                   "(drift 과대추정 방향)",
                   "C2 모집단 800 중 24만 봤다 — 미탐률 CI가 넓다"],
    }


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(LABELS_DIR / "manifest.json"))
    ap.add_argument("--labels", default=str(LABELS_DIR / "labels.csv"))
    ap.add_argument("--out", default="i1_label_analysis.json")
    a = ap.parse_args()
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    labels = {r["sample_id"]: (r["label"] or "").strip()
              for r in csv.DictReader(io.StringIO(
                  Path(a.labels).read_text(encoding="utf-8")))
              if (r.get("label") or "").strip()}
    rep = summarize(join(man, labels), man)
    OUT.mkdir(exist_ok=True)
    (OUT / a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(json.dumps({k: rep[k] for k in
                      ("stage", "n_analyzable", "unclear_rate",
                       "i1a_hits_census", "i1a_negative_sampled")},
                     ensure_ascii=False, indent=2))
    print(f"저장: docs/probes/_scratch/{a.out}")


if __name__ == "__main__":
    try:
        main()
    except AnalysisError as e:
        print(f"차단: {e}", file=sys.stderr)
        sys.exit(2)
