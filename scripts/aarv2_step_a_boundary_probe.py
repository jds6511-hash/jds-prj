"""AAR-v2 STEP A — Boundary Detectability Probe.

사전등록: `docs/finalization/AARV2_STEP_A_PREREG_2026-08-28.md` (실행 전 동결).

질문 하나만 답한다.

    이미 존재하는 subtitle/caption embedding의 인접 구간 변화량이, GT 사건 경계
    위치에 대해 **균등 시간 분할보다** 유용한 정보를 담고 있는가.

AAR-v2 아키텍처를 구현하지 않는다 — 전제 하나만 잰다. 새 라벨 0 · LLM 0 ·
새 embedding 0 · GPU 0 · M8-v1 판정 불변 · M9/official test 무접촉.

사용:
    python scripts/aarv2_step_a_boundary_probe.py
"""
import argparse
import hashlib
import io
import json
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
from m8_gates import panel_videos, reference_events                 # noqa: E402

PREREG = "docs/finalization/AARV2_STEP_A_PREREG_2026-08-28.md"
RUNDIR = ROOT / "runs/aarv2_step_a"

# 사전등록 §3·§5·§7·§11 — 실행 전 동결. 결과를 보고 고치지 않는다.
PRIMARY = "mean(percentile_norm(d_sub), percentile_norm(d_cap))"
K_SECONDS_PER_BOUNDARY = 60
TOLERANCE_SEC = 10.0
SECONDARY_TOLERANCES = (5.0, 15.0)
GO_MIN_DELTA = 0.15
GO_MIN_BETTER = 5
GO_MAX_WORSE = 2

BOUNDARY = {"new_labels": 0, "llm_calls": 0, "generation_calls": 0,
            "new_embeddings": 0, "gpu_required": False,
            "model_training": 0, "fresh_data": False,
            "m8v1_verdict_changed": False, "round3": False,
            "m9_touched": False, "official_test_touched": False,
            "aarv2_architecture_implemented": False, "pushed": False}


class StepAError(RuntimeError):
    """전제가 안 맞으면 조용히 진행하지 않는다."""


# ── GT 경계 ──────────────────────────────────────────────────────────────
def gt_boundaries(events: list, seg_len_sec: int) -> list:
    """사건 사이 전이 시각. 사건 자체가 아니라 **경계**를 평가한다.

    구간 `i`는 `[i*sl, (i+1)*sl)`초다. 인접(delta=1)이면 공유 경계, 사이가 비면
    공백의 중점을 쓴다. 영상 시작·끝은 대상이 아니다(사건 사이에서만 나온다).
    """
    ev = sorted(events, key=lambda e: (e["span"][0], e["span"][1]))
    out = []
    for a, b in zip(ev, ev[1:]):
        lo = (a["span"][1] + 1) * seg_len_sec       # 앞 사건이 끝나는 시각
        hi = b["span"][0] * seg_len_sec             # 뒤 사건이 시작하는 시각
        out.append(lo if hi <= lo else (lo + hi) / 2)
    return sorted(set(out))


# ── change signal ────────────────────────────────────────────────────────
def adjacent_distance(emb: np.ndarray) -> np.ndarray:
    """인접 구간 코사인 거리. m4가 L2 정규화해 저장하지만 여기서도 나눈다."""
    a, b = emb[:-1], emb[1:]
    na = np.linalg.norm(a, axis=1)
    nb = np.linalg.norm(b, axis=1)
    denom = np.where((na * nb) == 0, 1.0, na * nb)
    return 1.0 - (a * b).sum(axis=1) / denom


def valid_mask(texts: list) -> np.ndarray:
    """transition이 유효하려면 **양쪽 다** 비공백이어야 한다.

    빈 subtitle은 sentinel이 아니라 공백 문자열의 임베딩이다(preflight audit).
    그 거리를 신호로 쓰면 무발화 구간이 경계처럼 보인다.
    """
    ok = np.array([bool((t or "").strip()) for t in texts])
    return ok[:-1] & ok[1:]


def percentile_norm(d: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """영상 안에서 채널별 percentile rank. 무효 구간은 NaN으로 남긴다.

    스케일 차이에 둔감하고 하이퍼파라미터가 없다. 동점은 평균 순위.
    """
    out = np.full(len(d), np.nan)
    if not mask.any():
        return out
    r = rankdata(d[mask], method="average") / int(mask.sum())
    out[mask] = r
    return out


def primary_score(norm_sub: np.ndarray, norm_cap: np.ndarray) -> np.ndarray:
    """유효한 채널만 평균한다. 둘 다 무효면 NaN(후보 불가)."""
    stack = np.vstack([norm_sub, norm_cap])
    with warnings.catch_warnings():          # 둘 다 무효인 열은 NaN이 정상값이다
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(stack, axis=0)


# ── 예측 · baseline ──────────────────────────────────────────────────────
def budget_k(n_segments: int, seg_len_sec: int) -> int:
    """duration만으로 정한다. 정답 개수를 보고 예산을 정하면 그 자체가 누설이다."""
    return max(1, int(round(n_segments * seg_len_sec / K_SECONDS_PER_BOUNDARY)))


def top_k(score: np.ndarray, k: int) -> list:
    """점수 내림차순, 동점은 인덱스 오름차순. NaN은 후보가 아니다. NMS 없음."""
    idx = [i for i in range(len(score)) if not np.isnan(score[i])]
    return sorted(idx, key=lambda i: (-float(score[i]), i))[:k]


def uniform_boundaries(duration_sec: float, k: int) -> list:
    """영상 내부에 등간격 K개. 시작·끝 제외. 구간 경계로 snap하지 않는다."""
    return [duration_sec * i / (k + 1) for i in range(1, k + 1)]


# ── matching ─────────────────────────────────────────────────────────────
def match_boundaries(gt: list, pred: list, tol: float) -> dict:
    """1:1. 최대 cardinality를 먼저 취하고 그 안에서 총 거리를 최소화한다.

    예측 하나가 GT 여럿을 동시에 맞힌 것으로 세면 recall이 부풀려진다 —
    GT 최소 길이가 2구간(10초)이라 τ=±10초에서 실제로 생길 수 있다.
    """
    if not gt or not pred:
        return {"n_matched": 0, "pairs": [], "n_gt": len(gt), "n_pred": len(pred)}
    d = np.abs(np.array(gt)[:, None] - np.array(pred)[None, :])
    big = tol * min(len(gt), len(pred)) + 1.0
    cost = np.where(d <= tol, d, big)
    rows, cols = linear_sum_assignment(cost)
    pairs = [(int(i), int(j), float(d[i, j]))
             for i, j in zip(rows, cols) if d[i, j] <= tol]
    return {"n_matched": len(pairs), "pairs": sorted(pairs),
            "n_gt": len(gt), "n_pred": len(pred)}


def go_verdict(m: dict) -> dict:
    failed = []
    if m["delta"] < GO_MIN_DELTA:
        failed.append("A_delta>=0.15")
    if m["n_better_or_equal"] < GO_MIN_BETTER:
        failed.append("B_better>=5")
    if m["n_worse"] > GO_MAX_WORSE:
        failed.append("C_worse<=2")
    return {"go": not failed, "failed": failed}


# ── 실행 ─────────────────────────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _short_side(events: list, b: float, seg_len_sec: int) -> str:
    """경계 양쪽 사건 중 **짧은 쪽** 길이로 분류(사전등록 §12)."""
    lens = [(e["span"][1] - e["span"][0] + 1) * seg_len_sec for e in events
            if e["span"][0] * seg_len_sec <= b <= (e["span"][1] + 1) * seg_len_sec]
    if not lens:
        return "unknown"
    s = min(lens)
    return "short" if s <= 40 else ("medium" if s <= 180 else "long")


def run(cfg: dict) -> dict:
    sl = cfg["seg_len_sec"]
    rows, scores_out, preds_out, unis_out, matches_out = [], [], [], [], []
    for v in panel_videos():
        w = Path(common.work_dir(cfg, v))
        doc = json.loads((w / "segments.json").read_text(encoding="utf-8"))
        segs = doc["segments"]
        es, ec = np.load(w / "emb_sub.npy"), np.load(w / "emb_cap.npy")
        if not (len(segs) == len(es) == len(ec)):
            raise StepAError(f"{v}: 길이 불일치 seg={len(segs)} sub={len(es)} "
                             f"cap={len(ec)}")
        if es.shape[1] != 1024 or ec.shape[1] != 1024:
            raise StepAError(f"{v}: 임베딩 차원이 1024가 아니다")
        if any(segs[i]["start"] > segs[i + 1]["start"] for i in range(len(segs) - 1)):
            raise StepAError(f"{v}: 타임스탬프가 단조가 아니다")

        refs = reference_events(v)
        gt = gt_boundaries(refs, sl)
        n, dur = len(segs), len(segs) * sl
        k = budget_k(n, sl)

        m_sub = valid_mask([s.get("subtitle") for s in segs])
        m_cap = valid_mask([s.get("caption") for s in segs])
        ns = percentile_norm(adjacent_distance(es), m_sub)
        nc = percentile_norm(adjacent_distance(ec), m_cap)
        score = primary_score(ns, nc)

        def times(sel):
            return [(t + 1) * sl for t in sel]

        pred = times(top_k(score, k))
        uni = uniform_boundaries(float(dur), k)
        pm = match_boundaries(gt, pred, TOLERANCE_SEC)
        um = match_boundaries(gt, uni, TOLERANCE_SEC)
        sec = {"subtitle_only": match_boundaries(gt, times(top_k(ns, k)),
                                                 TOLERANCE_SEC)["n_matched"],
               "caption_only": match_boundaries(gt, times(top_k(nc, k)),
                                                TOLERANCE_SEC)["n_matched"]}
        tolsens = {f"tau_{int(t)}s": match_boundaries(gt, pred, t)["n_matched"]
                   for t in SECONDARY_TOLERANCES}
        hit_gt = {i for i, _, _ in pm["pairs"]}
        dur_diag = {}
        for i, b in enumerate(gt):
            g = _short_side(refs, b, sl)
            c = dur_diag.setdefault(g, {"n": 0, "hit": 0})
            c["n"] += 1
            c["hit"] += int(i in hit_gt)

        rows.append({
            "video_id": v, "n_segments": n, "duration_sec": dur, "K": k,
            "n_gt_events": len(refs), "n_gt_boundaries": len(gt),
            "eligible": bool(gt),
            "n_invalid_sub_transitions": int((~m_sub).sum()),
            "n_invalid_cap_transitions": int((~m_cap).sum()),
            "embedding_hits": pm["n_matched"],
            "embedding_recall": round(pm["n_matched"] / len(gt), 4) if gt else None,
            "uniform_hits": um["n_matched"],
            "uniform_recall": round(um["n_matched"] / len(gt), 4) if gt else None,
            "delta": (round((pm["n_matched"] - um["n_matched"]) / len(gt), 4)
                      if gt else None),
            "secondary": sec, "tolerance_sensitivity": tolsens,
            "duration_diagnostic": dur_diag})
        scores_out.append({"video_id": v, "primary_score": [
            None if np.isnan(x) else round(float(x), 6) for x in score]})
        preds_out.append({"video_id": v, "K": k, "boundaries_sec": pred})
        unis_out.append({"video_id": v, "K": k, "boundaries_sec": uni})
        matches_out.append({"video_id": v, "gt_boundaries_sec": gt,
                            "embedding": pm, "uniform": um})
    return {"per_video": rows, "scores": scores_out, "predicted": preds_out,
            "uniform": unis_out, "matching": matches_out}


def summarize(rows: list) -> dict:
    el = [r for r in rows if r["eligible"]]
    tot = sum(r["n_gt_boundaries"] for r in el)
    eh = sum(r["embedding_hits"] for r in el)
    uh = sum(r["uniform_hits"] for r in el)
    er, ur = (eh / tot if tot else 0.0), (uh / tot if tot else 0.0)
    return {"n_videos": len(rows), "n_eligible_videos": len(el),
            "excluded_videos": [r["video_id"] for r in rows if not r["eligible"]],
            "gt_boundaries": tot,
            "embedding_matched": eh, "embedding_recall": round(er, 4),
            "uniform_matched": uh, "uniform_recall": round(ur, 4),
            "delta": round(er - ur, 4),
            "n_better_or_equal": sum(1 for r in el
                                     if r["embedding_hits"] >= r["uniform_hits"]),
            "n_worse": sum(1 for r in el
                           if r["embedding_hits"] < r["uniform_hits"]),
            "secondary_subtitle_only": sum(r["secondary"]["subtitle_only"]
                                           for r in el),
            "secondary_caption_only": sum(r["secondary"]["caption_only"]
                                          for r in el)}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default=str(RUNDIR))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    res = run(cfg)
    m = summarize(res["per_video"])
    verdict = go_verdict(m)
    prov = {"source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                text=True).stdout.strip(),
            "prereg": PREREG,
            "prereg_sha256": _sha(ROOT / PREREG),
            "panel": panel_videos(),
            "primary": PRIMARY, "k_rule": "max(1, round(duration_sec / 60))",
            "tolerance_sec": TOLERANCE_SEC, "matching": "1:1 Hungarian, max-cardinality",
            "uniform_baseline": "duration * i / (K+1), i=1..K",
            "go_threshold": {"delta>=": GO_MIN_DELTA, "better>=": GO_MIN_BETTER,
                             "worse<=": GO_MAX_WORSE},
            "boundary": BOUNDARY}

    common.atomic_write_json(out / "gt_boundaries.json",
                             {"provenance": prov, "per_video": [
                                 {"video_id": r["video_id"],
                                  "gt_boundaries_sec": r["gt_boundaries_sec"]}
                                 for r in res["matching"]]})
    common.atomic_write_json(out / "change_scores.json",
                             {"provenance": prov, "per_video": res["scores"]})
    common.atomic_write_json(out / "predicted_boundaries.json",
                             {"provenance": prov, "per_video": res["predicted"]})
    common.atomic_write_json(out / "uniform_boundaries.json",
                             {"provenance": prov, "per_video": res["uniform"]})
    common.atomic_write_json(out / "matching_results.json",
                             {"provenance": prov, "per_video": res["matching"]})
    common.atomic_write_json(out / "summary.json",
                             {"provenance": prov, "metrics": m, **verdict})
    common.atomic_write_json(out / "manifest.json", {
        "record": "AAR-v2 STEP A — boundary detectability probe",
        "date": "2026-08-28", "provenance": prov, "metrics": m, **verdict,
        "per_video": res["per_video"],
        "interpretation": (
            "GO는 기존 embedding의 국소 변화 신호가 균등 분할보다 GT 경계 위치에 "
            "대해 더 유용한 정보를 담았다는 뜻이다. AAR-v2 성공·event proposal "
            "성공·hierarchy 성공·보고서 품질 개선·M8-v1 실패 해소·fresh 일반화를 "
            "뜻하지 않는다."),
        "not_evaluated": ["C1", "C3", "event proposal", "hierarchy", "merge",
                          "LLM 사건 서술", "evidence attachment",
                          "report assembly", "report synthesis"]})

    print(f"적격 {m['n_eligible_videos']}/{m['n_videos']}편 "
          f"(제외 {m['excluded_videos']}) · GT 경계 {m['gt_boundaries']}")
    print(f"{'video':24s} {'dur':>5s} {'K':>3s} {'GTb':>4s} "
          f"{'emb':>4s} {'rec':>6s} {'uni':>4s} {'rec':>6s} {'Δ':>7s}")
    for r in res["per_video"]:
        if not r["eligible"]:
            print(f"{r['video_id']:24s} {r['duration_sec']:5d} {r['K']:3d} "
                  f"{0:4d}    — 경계 없음 · 제외")
            continue
        print(f"{r['video_id']:24s} {r['duration_sec']:5d} {r['K']:3d} "
              f"{r['n_gt_boundaries']:4d} {r['embedding_hits']:4d} "
              f"{r['embedding_recall']:6.3f} {r['uniform_hits']:4d} "
              f"{r['uniform_recall']:6.3f} {r['delta']:+7.3f}")
    print(f"\npooled  embedding {m['embedding_matched']}/{m['gt_boundaries']} = "
          f"{m['embedding_recall']:.4f} · uniform {m['uniform_matched']}/"
          f"{m['gt_boundaries']} = {m['uniform_recall']:.4f} · "
          f"Δ {m['delta']:+.4f}")
    print(f"영상별  embedding >= uniform {m['n_better_or_equal']} · "
          f"worse {m['n_worse']}")
    print(f"secondary (판정 미사용)  subtitle-only {m['secondary_subtitle_only']} · "
          f"caption-only {m['secondary_caption_only']}")
    print(f"\nSTEP A: {'GO' if verdict['go'] else 'NO-GO'}"
          + (f" — 미충족 {', '.join(verdict['failed'])}" if verdict["failed"] else ""))
    print(f"산출물: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
