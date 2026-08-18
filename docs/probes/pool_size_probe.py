"""P1 — 후보 풀 크기 × 모델 상호작용. **기전 진단이지 확증이 아니다.**

사전등록: `docs/preregistration/부호역전_확증_사전등록_2026-08-18.md`
보충: `docs/preregistration/부호역전_확증_보충1_P1설계_2026-08-18.md`

    D_small = MRR_cap(4B, 후보 12) − MRR_cap(3B, 후보 12)
    D_large = MRR_cap(4B, 전체)    − MRR_cap(3B, 전체)
    I_pool  = D_large − D_small          사전 예측: I_pool < 0

**dev·AI Hub는 둘 다 소진된 표본이다.** 예측과 맞아도 상한은 "plausible contributor"다
(보충1 §1-2). 이 모듈은 `cause`·`verdict` 키를 내지 않는다.

**후보 선택은 점수를 볼 수 없다.** `select_candidates`는 arm·캡션·임베딩·유사도·rank를
인자로 받지 않는다 — 받으면 후보를 성능 보고 고르는 경로가 열린다.

**임베딩을 다시 계산한다.** 저장된 것은 캡션 텍스트뿐이라 다른 방법이 없다(보충1 §3).
그래서 전체 풀 MRR이 저장값과 소수 4자리까지 같은지 **재현 게이트**로 검증하고,
어긋나면 중단한다. 캡션 텍스트는 건드리지 않고 VLM도 쓰지 않는다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

RULE_VERSION = 1
# 조작 이름이 조작 내용과 일치해야 한다. 연속 창은 풀 크기 **+ locality**를 바꾸므로
# `pool_size_only`라고 부르지 않는다 (보충1 §2).
RULES = ("P1a_pool_size_random_negatives", "P1a_local_window_12")
PRIMARY_RULE = "P1a_pool_size_random_negatives"
SMALL_POOL = 12
# 보충1 §4에서 미리 고정한 격자. 결과를 보고 점을 추가하지 않는다
DEV_GRID = (12, 24, 48, 96)
AIHUB_GRID = (12, 24, 48, 96, 192, 384, 768, 2328)


class ProbeError(RuntimeError):
    pass


def parity_audit(sweep: dict, keys: list) -> dict:
    """parity 어휘를 재사용한다 — 기록 없음은 `unknown_not_recorded`이고 PASS도
    FAIL도 아니다. 두 번째 구현을 만들면 한쪽이 그 상태를 잃는다."""
    from sign_reversal_diag import parity_audit as _pa
    return _pa(sweep, keys)


def _h(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()


def select_candidates(query_id: str, video_id: str, seg_ids: list, gold: list,
                      pool_size: int, run_tag: str,
                      rule: str = PRIMARY_RULE) -> list:
    """후보 집합. **점수·arm·캡션을 인자로 받지 않는다.**

    인자를 늘리지 마라 — arm이나 유사도가 들어오면 후보 선택이 성능에 의존하게
    되고, 그 시점에 조작이 아니라 선별이 된다.
    """
    if rule not in RULES:
        raise ProbeError(f"선언되지 않은 규칙: {rule!r} — {RULES}만 쓴다")
    gold = sorted(set(gold))
    if not gold:
        raise ProbeError(f"{query_id}: gold가 비었다")
    if not set(gold) <= set(seg_ids):
        raise ProbeError(f"{query_id}: gold가 universe 밖이다")
    if len(gold) > pool_size:
        # fail-closed. 사람이 판단해 자를 여지를 두지 않는다
        raise ProbeError(f"{query_id}: gold {len(gold)}개 > 풀 {pool_size}개")
    if pool_size >= len(seg_ids):
        return list(seg_ids)

    if rule == "P1a_pool_size_random_negatives":
        neg = [s for s in seg_ids if s not in set(gold)]
        neg.sort(key=lambda s: _h(run_tag, query_id, video_id, s))
        return sorted(gold + neg[:pool_size - len(gold)], key=seg_ids.index)

    # P1a_local_window_12 — gold를 포함하는 연속 창. AI Hub의 실제 구조를 모사한다
    pos = [seg_ids.index(g) for g in gold]
    lo, hi = min(pos), max(pos)
    if hi - lo + 1 > pool_size:
        raise ProbeError(f"{query_id}: gold 범위가 창 {pool_size}보다 넓다")
    starts = [s for s in range(max(0, hi - pool_size + 1),
                               min(lo, len(seg_ids) - pool_size) + 1)]
    if not starts:
        starts = [max(0, min(lo, len(seg_ids) - pool_size))]
    start = min(starts, key=lambda s: _h(run_tag, query_id, video_id, s))
    return list(seg_ids[start:start + pool_size])


def restricted_rr(order: list, gold: list, candidates: list) -> float:
    """후보를 제한한 뒤의 RR. 전체 순위를 걸러서 계산한다.

    z-score는 단조변환이므로 부분집합 안의 상대 순서가 전체 순위와 같다. 그래서
    점수를 다시 계산하지 않아도 정확하다.
    """
    allowed, g = set(candidates), set(gold)
    rank = 0
    for s in order:
        if s not in allowed:
            continue
        rank += 1
        if s in g:
            return 1.0 / rank
    return 0.0


def caption_sha(caps: dict) -> str:
    return hashlib.sha256(json.dumps(caps, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()


def score_order(cap_emb: np.ndarray, q_emb: np.ndarray, seg_ids: list) -> list:
    """캡션 단독(α=0) 순위. static_threshold=0이라 치환이 없고 z-score는 단조라서
    랭킹은 raw 코사인 순서와 같다. 질의 변형은 production과 같이 max 풀링한다."""
    s = np.max(cap_emb @ q_emb.T, axis=1) if q_emb.ndim == 2 else cap_emb @ q_emb
    return [seg_ids[i] for i in np.argsort(-s, kind="stable")]


def analyze(orders: dict, queries: list, universe: dict, gold: dict,
            arms: dict, run_tag: str, grid=DEV_GRID, rule: str = PRIMARY_RULE,
            stored_mrr: dict = None) -> dict:
    """`orders[arm][query_id]` = 전체 순위(세그먼트 ID 목록).

    `arms` = {"cand": arm_key, "cur": arm_key}. `stored_mrr`가 주어지면 전체 풀
    재현 게이트를 적용한다.
    """
    for role in ("cand", "cur"):
        if arms.get(role) not in orders:
            raise ProbeError(f"arm이 없다: {role}={arms.get(role)!r}")
    qids = [q["query_id"] for q in queries]
    if len(set(qids)) != len(qids):
        raise ProbeError("query_id 중복")

    # 계약 2 — 같은 질의의 모든 arm이 동일한 후보 ID 목록을 받는다.
    # arm별로 따로 뽑으면 조작이 arm에 의존하게 된다
    cands = {}
    for q in queries:
        segs = universe[q["video_id"]]
        cands[q["query_id"]] = {
            k: select_candidates(q["query_id"], q["video_id"], segs,
                                 gold[q["query_id"]], k, run_tag, rule)
            for k in grid}

    rr = {}
    for role in ("cand", "cur"):
        a = arms[role]
        rr[role] = {"full": np.array([
            restricted_rr(orders[a][q["query_id"]], gold[q["query_id"]],
                          universe[q["video_id"]]) for q in queries])}
        for k in grid:
            rr[role][k] = np.array([
                restricted_rr(orders[a][q["query_id"]], gold[q["query_id"]],
                              cands[q["query_id"]][k]) for q in queries])

    out = {"probe": "pool_size_probe",
           "prereg": "docs/preregistration/부호역전_확증_보충1_P1설계_2026-08-18.md",
           "purpose": ("mechanism diagnostic — pool-size sensitivity가 plausible "
                       "contributor인지 본다. 원인 확정이 아니다"),
           "candidate_rule": rule, "candidate_rule_version": RULE_VERSION,
           "run_tag": run_tag, "arms": dict(arms),
           "n_queries": len(queries), "grid": list(grid),
           "mrr": {role: {str(k): round(float(v.mean()), 4)
                          for k, v in rr[role].items()} for role in rr}}

    # 재현 게이트 — 완화(임베딩 재계산)를 검증 가능하게 만드는 장치다
    if stored_mrr:
        rep = {}
        for role in ("cand", "cur"):
            got = round(float(rr[role]["full"].mean()), 4)
            want = stored_mrr.get(arms[role])
            rep[arms[role]] = {"recomputed": got, "stored": want,
                               "match": want is not None and got == round(want, 4)}
        out["reproduction_check"] = rep
        bad = [k for k, v in rep.items() if not v["match"]]
        if bad:
            raise ProbeError(
                f"재현 게이트 FAIL: {bad} — 전체 풀 MRR이 저장값과 다르다. "
                "허용 오차를 늘려 살리지 마라(보충1 §3-2). 임베딩 경로가 원 실행과 "
                "다르다는 뜻이고 그 상태의 조작 결과는 해석할 수 없다")

    d_small = float((rr["cand"][SMALL_POOL] - rr["cur"][SMALL_POOL]).mean())
    d_large = float((rr["cand"]["full"] - rr["cur"]["full"]).mean())
    out["primary"] = {
        "definition": "I_pool = D_large − D_small (캡션 단독, α 미개입)",
        "d_small": round(d_small, 4), "d_large": round(d_large, 4),
        "i_pool": round(d_large - d_small, 4),
        "predicted_direction": "i_pool < 0",
        "matches_prediction": bool(d_large - d_small < 0),
        "small_pool_size": SMALL_POOL}
    out["by_pool_size"] = {
        str(k): round(float((rr["cand"][k] - rr["cur"][k]).mean()), 4) for k in grid}
    out["by_pool_size"]["full"] = round(d_large, 4)
    out["limits"] = ("두 표본은 이미 소진됐다. 상한은 plausible contributor이며 "
                     "원인 확정도 채택 판정도 아니다. magnitude threshold를 결과 "
                     "보고 만들지 않는다")
    return out


# ---- 산출물 적재 --------------------------------------------------------

def load_dev(sweep_path, caption_dir, cfg_path=None) -> tuple:
    """dev — 저장 캡션을 다시 임베딩해 전체 순위를 만든다. VLM은 쓰지 않는다."""
    import common
    from m4_index import embed_texts
    from m5_search import expand_query

    cfg = common.load_config(cfg_path or ROOT / "config.yaml")
    sweep = json.loads(Path(sweep_path).read_text(encoding="utf-8"))
    qs = [q for q in (json.loads(l) for l in
                      (ROOT / "data" / "queries" / "queries.jsonl")
                      .read_text(encoding="utf-8").splitlines() if l.strip())
          if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in qs})
    universe = {}
    for v in vids:
        doc = json.loads((ROOT / "work" / v / "segments.json")
                         .read_text(encoding="utf-8"))
        universe[v] = [f"{v}#{i}" for i in range(len(doc["segments"]))]
    gold = {q["query_id"]: [f"{q['video_id']}#{i}" for i in q["gt_seg_idx"]]
            for q in qs}

    qemb = {}
    for q in qs:
        variants = expand_query(q["text"], cfg)
        qemb[q["query_id"]] = embed_texts(
            variants if len(variants) > 1 else [q["text"]], cfg["embed_model"])

    orders, shas = {}, {}
    for arm in sweep["arms"]:
        p = Path(caption_dir) / f"{arm.replace('/', '__')}.json"
        if not p.exists():
            continue
        caps = json.loads(p.read_text(encoding="utf-8"))
        shas[arm] = caption_sha(caps)
        emb = {v: embed_texts(caps[v], cfg["embed_model"]) for v in vids}
        orders[arm] = {q["query_id"]: score_order(emb[q["video_id"]],
                                                  qemb[q["query_id"]],
                                                  universe[q["video_id"]])
                       for q in qs}
    stored = {a: v.get("mrr_caption_only") for a, v in sweep["arms"].items()}
    return orders, qs, universe, gold, stored, shas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", required=True)
    ap.add_argument("--caption-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cand", default="qwen3vl_4b_q4/P0")
    ap.add_argument("--cur", default="qwen25_3b_4bit/P0")
    ap.add_argument("--rule", default=PRIMARY_RULE, choices=RULES)
    ap.add_argument("--run-tag", required=True)
    a = ap.parse_args()
    orders, qs, universe, gold, stored, shas = load_dev(a.sweep, a.caption_dir)
    r = analyze(orders, qs, universe, gold, {"cand": a.cand, "cur": a.cur},
                a.run_tag, DEV_GRID, a.rule, stored)
    r["caption_sha256"] = shas
    r["source_sweep"] = str(a.sweep)
    sweep = json.loads(Path(a.sweep).read_text(encoding="utf-8"))
    r["parity_audit"] = parity_audit(sweep, [a.cand, a.cur])
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    # 콘솔은 cp949다 — ASCII만 쓴다
    print(f"saved: {a.out}")
    p = r["primary"]
    print(f"D_small={p['d_small']} D_large={p['d_large']} I_pool={p['i_pool']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
