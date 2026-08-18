"""[dev 정밀도 3-arm — Δ_quant·Δ_deploy 판정. 결과 전 커밋]

사전등록: `docs/preregistration/dev_precision_3arm_사전등록_2026-08-18.md` +
`..._보충_CI해석_2026-08-18.md`.

**주 판정은 caption-only MRR이고 α가 개입하지 않는다.**

    Δ_quant  = MRR_caption(4B/P0/4bit) − MRR_caption(4B/P0/bf16)
    Δ_deploy = MRR_caption(4B/P0/4bit) − MRR_caption(3B/P0/4bit)

α·τ calibration은 **별도 섹션**이고 이 판정을 소급해서 바꾸지 않는다. 그렇지 않으면
"4bit에서 이득이 죽었는데 α를 새로 골라 살아난 점만 보고 채택"하는 선택 편향이 생긴다.

**cluster = 3이다.** dev는 영상 3편뿐이라 `paired video-cluster bootstrap CI`는
추론적으로 매우 거칠다. 계산은 하되 **불확실성 진단용으로만** 읽고, CI의 0 포함·배제를
**formal adoption gate로 쓰지 않는다**(보충 §1).

**코드가 판단을 대신하지 않는다.** quadrant는 부호 조합을 기술하는 문자열이고
`good`·`bad`·`equivalent`·`significant` 같은 평가어를 붙이지 않는다(보충 §2).

캡션 생성은 `caption_model_sweep.py`가 한다 — 여기서는 그 산출물만 읽는다.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

# 사전등록 §1의 arm — 결과를 보고 바꾸지 않는다
ARMS = {"quant_4bit": "qwen3vl_4b_q4/P0",
        "quant_bf16": "qwen3vl_4b/P0",
        "deploy_current": "qwen25_3b_4bit/P0"}
CI_METHOD = "paired_video_cluster_bootstrap_percentile"
CI_CAVEAT = ("cluster=3 — 불확실성 진단용이다. CI의 0 포함·배제를 formal adoption "
             "gate로 쓰지 않는다 (보충 §1)")
RR_KEY = "rr_caption_only"
MRR_KEY = "mrr_caption_only"


class AnalysisError(RuntimeError):
    pass


def quadrant(delta_quant: float, delta_deploy: float) -> str:
    """**기술적 라벨만.** 부호 조합을 서술하고 평가하지 않는다."""
    q = "quant_loss" if delta_quant < 0 else "no_quant_loss"
    d = "deploy_gain" if delta_deploy > 0 else "no_deploy_gain"
    return f"{q}_and_{d}"


def _pull(sweep: dict) -> tuple:
    """arm별 RR을 뽑고 **paired 대응이 성립하는지 fail-closed로** 확인한다.

    질의 순서가 한 칸 밀리면 Δ가 조용히 오염된다. 저장된 aggregate MRR과 per-query
    평균을 대조하는 것이 그 어긋남을 잡는 가장 싼 방법이다."""
    qs = sweep.get("queries")
    if not qs:
        raise AnalysisError("sweep 산출물에 `queries` 매니페스트가 없다 — "
                            "paired 대응을 확인할 수 없다")
    ids = [q["query_id"] for q in qs]
    if len(set(ids)) != len(ids):
        raise AnalysisError("질의 id가 중복이다 — paired 대응이 성립하지 않는다")
    arms = sweep.get("arms") or {}
    rr = {}
    for role, key in ARMS.items():
        if key not in arms:
            raise AnalysisError(f"arm이 없다: {key} — 세 arm이 모두 필요하다")
        a = arms[key]
        v = a.get(RR_KEY)
        if v is None:
            raise AnalysisError(f"{key}에 `{RR_KEY}`가 없다 — per-query RR 미저장")
        if len(v) != len(ids):
            raise AnalysisError(
                f"{key}의 RR 길이({len(v)})가 질의 수({len(ids)})와 다르다")
        stored = a.get(MRR_KEY)
        if stored is not None and abs(float(np.mean(v)) - stored) > 5e-4:
            raise AnalysisError(
                f"{key}의 저장된 MRR({stored})이 per-query 평균"
                f"({float(np.mean(v)):.4f})과 다르다 — 순서·집합이 어긋났다")
        rr[role] = np.asarray(v, dtype=float)
    return ids, [q["video_id"] for q in qs], rr


def _paired_ci(diff: np.ndarray, groups: list, n_boot: int, seed: int) -> list:
    """**영상 클러스터를 재표집**한다. 질의 단위 재표집은 영상 내 상관을 무시한다.

    paired다 — 같은 질의의 두 arm 차이를 하나의 관측으로 본다."""
    g = np.asarray(groups)
    uniq = np.unique(g)
    idx = {u: np.where(g == u)[0] for u in uniq}
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        sel = np.concatenate([idx[u] for u in pick])
        boots.append(float(diff[sel].mean()))
    return [round(float(np.percentile(boots, 2.5)), 4),
            round(float(np.percentile(boots, 97.5)), 4)]


def analyze(sweep: dict, n_boot: int = 2000, seed: int = 20260818) -> dict:
    ids, vids, rr = _pull(sweep)
    d_quant = rr["quant_4bit"] - rr["quant_bf16"]
    d_deploy = rr["quant_4bit"] - rr["deploy_current"]
    out = {
        "probe": "dev_precision_3arm",
        "prereg": "docs/preregistration/dev_precision_3arm_사전등록_2026-08-18.md",
        "primary": "캡션 단독 MRR (α 미개입)",
        "arms": dict(ARMS),
        "n_queries": len(ids), "n_clusters": int(len(set(vids))),
        "cluster_key": "video_id",
        "ci_method": CI_METHOD, "ci_interpretation": "diagnostic_only",
        "ci_caveat": CI_CAVEAT, "n_boot": n_boot, "seed": seed,
        "arm_mrr": {ARMS[r]: round(float(v.mean()), 4) for r, v in rr.items()},
        "delta_quant": {
            "definition": "MRR_caption(4B/P0/4bit) − MRR_caption(4B/P0/bf16)",
            "point": round(float(d_quant.mean()), 4),
            "ci": _paired_ci(d_quant, vids, n_boot, seed)},
        "delta_deploy": {
            "definition": "MRR_caption(4B/P0/4bit) − MRR_caption(3B/P0/4bit)",
            "point": round(float(d_deploy.mean()), 4),
            "ci": _paired_ci(d_deploy, vids, n_boot, seed + 1)},
    }
    out["quadrant"] = quadrant(out["delta_quant"]["point"],
                               out["delta_deploy"]["point"])
    # 서버 4090 측정값이다 — 6GB 적합성 수치로 오독되지 않게 키에 서버를 박는다
    vram = {k: a["server_peak_vram_gb"] for k, a in (sweep.get("arms") or {}).items()
            if "server_peak_vram_gb" in a}
    if vram:
        out["server_peak_vram_gb"] = vram
    # SECONDARY — 이 값들로 PRIMARY 판정을 뒤집지 않는다
    out["secondary"] = {
        "note": "calibration이다. PRIMARY의 정밀도 판정을 소급해서 바꾸지 않는다",
        "mrr_alpha_fixed": {k: (sweep["arms"][k] or {}).get("mrr_alpha_fixed")
                            for k in ARMS.values() if k in (sweep.get("arms") or {})},
        "alpha_star": {k: (sweep["arms"][k] or {}).get("alpha_star")
                       for k in ARMS.values() if k in (sweep.get("arms") or {})},
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", required=True, help="caption_model_sweep 산출 JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260818)
    a = ap.parse_args()
    r = analyze(json.loads(Path(a.sweep).read_text(encoding="utf-8")),
                n_boot=a.n_boot, seed=a.seed)
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"저장: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
