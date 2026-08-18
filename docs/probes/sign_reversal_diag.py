"""[`4B − 3B` 부호 역전 조사 — heterogeneity localization. SECONDARY 열람 전 커밋]

사전등록: `docs/preregistration/부호역전_조사_사전등록_2026-08-18.md`.

캡션 단독(α 미개입) `4B/P0 − 3B/P0`:

    AI Hub 1,086질의   +0.0310
    dev 96질의·3영상   −0.0903

**질문은 "어느 쪽이 맞나"가 아니다.** 기존 두 표본만으로 참 효과의 부호를 확정할 수
없다 — AI Hub는 이미 선택에 사용됐고 dev는 영상 3편이다. 이 조사의 역할은
**부호가 어디에서 뒤집히는지 국소화하고 새 표본 확증 설계를 만드는 것**이다.

**α·τ가 들어오지 않는다.** 어떤 분석에서도 caption-only PRIMARY의 부호를 구제하지
않는다(사전등록 §3). 그래서 이 모듈은 α 관련 키를 읽지 않는다.

**코드가 원인을 단정하지 않는다.** `cause`·`verdict` 같은 키를 내지 않고, 오염·길이
연관은 `exploratory`로 격리한다.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CAND = "qwen3vl_4b_q4/P0"          # 배포 후보 (4bit)
CUR = "qwen25_3b_4bit/P0"          # 현행 배포
BF16 = "qwen3vl_4b/P0"             # 참고 대비만
RR = "rr_caption_only"
MRR = "mrr_caption_only"
# 층은 **파일에 이미 있는 값**만 쓴다. 결과를 보고 새 strata를 만들지 않는다.
ALLOWED_STRATA = ("type",)
# 두 실험의 비교 가능성을 기계적으로 대조할 항목
PARITY_FIELDS = ("prompt_sha256", "effective_quantized", "effective_model_revision",
                 "attn_implementation", "dtype", "config_vlm_max_pixels",
                 "config_vlm_max_new_tokens", "config_vlm_rep_penalty")
# arm마다 다른 것이 정상인 항목 — 불일치를 결함으로 세지 않는다
PARITY_EXPECTED_TO_DIFFER = ("effective_model_revision", "effective_quantized")


class DiagError(RuntimeError):
    pass


def _rr(sweep: dict, key: str, n: int) -> np.ndarray:
    arms = sweep.get("arms") or {}
    if key not in arms:
        raise DiagError(f"arm이 없다: {key}")
    v = (arms[key] or {}).get(RR)
    if v is None:
        raise DiagError(f"{key}에 `{RR}`가 없다")
    if len(v) != n:
        raise DiagError(f"{key}의 RR 길이({len(v)})가 질의 수({n})와 다르다")
    return np.asarray(v, dtype=float)


def _dist(d: np.ndarray) -> dict:
    return {"n": int(d.size), "mean": round(float(d.mean()), 4),
            "median": round(float(np.median(d)), 4),
            "min": round(float(d.min()), 4), "max": round(float(d.max()), 4),
            "n_positive": int((d > 0).sum()), "n_negative": int((d < 0).sum()),
            "n_zero": int((d == 0).sum()),
            "sum_positive": round(float(d[d > 0].sum()), 4),
            "sum_negative": round(float(d[d < 0].sum()), 4)}


def _parity(sweep: dict, keys: list) -> dict:
    arms = sweep["arms"]
    out = {}
    for f in PARITY_FIELDS:
        vals = {k: (arms[k].get("provenance") or {}).get(f) for k in keys}
        if all(v is None for v in vals.values()):
            continue
        out[f] = {"values": vals,
                  "match": len(set(map(str, vals.values()))) == 1,
                  "expected_to_differ": f in PARITY_EXPECTED_TO_DIFFER}
    return out


def analyze(sweep: dict, queries: list, stratum_key: str = "type") -> dict:
    if stratum_key not in ALLOWED_STRATA:
        raise DiagError(
            f"허용되지 않은 strata: {stratum_key!r} — 층은 queries 파일의 "
            f"{ALLOWED_STRATA} 값만 쓴다. 결과를 보고 새 층을 만들지 않는다")
    n = len(queries)
    cand, cur = _rr(sweep, CAND, n), _rr(sweep, CUR, n)
    d = cand - cur
    vids = [q["video_id"] for q in queries]
    strat = [q.get(stratum_key) for q in queries]

    by_video = {}
    for v in sorted(set(vids)):
        m = np.array([x == v for x in vids])
        by_video[v] = {"n": int(m.sum()),
                       "mean_delta": round(float(d[m].mean()), 4),
                       "mrr_cand": round(float(cand[m].mean()), 4),
                       "mrr_cur": round(float(cur[m].mean()), 4),
                       **{k: val for k, val in _dist(d[m]).items()
                          if k in ("n_positive", "n_negative", "n_zero")}}

    overall = float(d.mean())
    lovo = {}
    for v in sorted(set(vids)):
        m = np.array([x != v for x in vids])
        mu = float(d[m].mean()) if m.any() else None
        lovo[v] = {"excluded_video": v, "n": int(m.sum()),
                   "mean_delta": round(mu, 4) if mu is not None else None,
                   # 부호가 뒤집히면 그 영상이 전체를 지배한다는 신호다
                   "sign_flips_vs_overall": (
                       bool(mu is not None and overall != 0 and
                            np.sign(mu) != np.sign(overall)))}

    by_type = {}
    for s in sorted({x for x in strat if x is not None}):
        m = np.array([x == s for x in strat])
        by_type[s] = {"n": int(m.sum()),
                      "mean_delta": round(float(d[m].mean()), 4),
                      "n_positive": int((d[m] > 0).sum()),
                      "n_negative": int((d[m] < 0).sum())}

    arms = sweep["arms"]
    keys = [CAND, CUR]
    out = {
        "probe": "sign_reversal_diag",
        "prereg": "docs/preregistration/부호역전_조사_사전등록_2026-08-18.md",
        "purpose": ("heterogeneity localization + fresh-sample confirmation plan — "
                    "원인 확정이 아니다"),
        "contrast": f"{CAND} − {CUR} (캡션 단독, α 미개입)",
        "arm_mrr": {k: arms[k].get(MRR) for k in keys},
        "parity_audit": _parity(sweep, keys),
        "paired_delta": _dist(d),
        "by_video": by_video,
        "leave_one_video_out": lovo,
        "by_query_type": by_type,
        "strata_source": f"queries.jsonl:{stratum_key}",
        # **exploratory 격리.** 4B 오염이 많았다는 이유로 retrieval 하락의 원인이라고
        # 미리 정하지 않는다(사전등록 §2-(5)).
        "exploratory": {
            "label": "exploratory_not_a_cause_claim",
            "corrupted_by_arm": {k: arms[k].get("corrupted") for k in keys},
            "len_mean_by_arm": {k: arms[k].get("len_mean") for k in keys},
            "note": ("연관을 보고 인과로 쓰지 마라. 오염 수는 arm 수준 집계이고 "
                     "질의 수준 Δ와 직접 연결되지 않는다"),
        },
        "limits": ("두 표본만으로 참 효과의 부호를 **확정**할 수 없다. AI Hub는 이미 "
                   "선택에 사용됐고(장벽 1번) dev는 영상 3편·96질의다. 새 표본 확증이 "
                   "별도로 필요하다."),
    }
    if BF16 in arms:
        db = _rr(sweep, BF16, n) - cur
        out["paired_delta_bf16_reference"] = {
            **_dist(db),
            "note": ("참고 대비만. 배포 경로는 4bit이므로 주 대비는 "
                     f"{CAND} − {CUR}이다"),
        }
    return out


def load_queries(path=None) -> list:
    p = Path(path or ROOT / "data" / "queries" / "queries.jsonl")
    qs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [q for q in qs if q["split"] == "dev"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sweep = json.loads(Path(a.sweep).read_text(encoding="utf-8"))
    qs = sweep.get("queries") or load_queries()
    # sweep의 매니페스트에 type이 없으면 원본 질의에서 붙인다 (층은 파일 값 그대로)
    if qs and "type" not in qs[0]:
        src = {q["query_id"]: q for q in load_queries()}
        qs = [{**q, "type": src[q["query_id"]]["type"]} for q in qs]
    r = analyze(sweep, qs)
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"저장: {a.out}")
    print(f"부호 분포 +{r['paired_delta']['n_positive']} "
          f"−{r['paired_delta']['n_negative']} 0:{r['paired_delta']['n_zero']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
