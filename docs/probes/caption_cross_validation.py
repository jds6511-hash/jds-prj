"""[캡션 모델 결론의 교차검증 — dev 전용, 채택 아님, 결과 생성 전 커밋]

**왜 필요한가.** 스윕 1단계에서 qwen3vl_4b/P1이 대조군을 유의하게 이겼다
(ΔMRR +0.0917 CI [+0.0066, +0.1778]). 그런데 이 수치는 **한 번의 계산**이고,
하한이 +0.0066으로 0에 거의 붙어 있으며, 이 세션에서만도 계산 오류가 한 건
있었다(경합 부분집합을 기준 arm 성적으로 정의해 평균회귀를 만든 건). 채택은
test 재평가를 유발하므로 한 번 나온 수치로 밀면 안 된다.

**먼저 정직하게 — 아래 5개는 독립 증거가 아니다.** 전부 **같은 dev 96건**을
다시 자르는 것이라 표본이 공유된다. 검정하는 것은 "다른 데이터에서도 참인가"가
아니라 **"이 데이터 안에서 얼마나 안정적인가"** 다. 진짜 독립 증거는 파이프라인
밖 지표(AI Hub 사람 묘사 대비 chrF·cos)이고 그건 별도 프로브다.

  A. 영상 단위 leave-one-out — 효과가 한 영상에서만 나오는지
  B. 유형별 분해 — 캡션 개선이면 **장면형에 몰려야** 한다(기전 정합성)
  C. 대체 지표 — hit@1/@5/@10·중앙 랭크. MRR만 움직이면 지표 특이적이다
  D. 순열검정 — 부트스트랩과 **다른 추론 기계**. 쌍체 부호를 무작위로 뒤집어
     귀무분포를 만든다. 둘이 어긋나면 어느 쪽도 못 믿는다
  E. 시드 4종 — CI가 seed 42의 우연인지

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-09).**
  - **A에서 3영상 중 2영상 이상이 같은 부호**여야 한다. 한 영상이 전부를
    만들면 "영상 특이적"으로 보고하고 채택 근거로 쓰지 않는다.
  - **B에서 장면형 Δ가 자막형 Δ보다 커야** 한다. 반대면 기전이 안 맞으므로
    캡션 품질 개선이 아니라 다른 것을 재고 있는 것이다.
  - **C에서 hit@1과 hit@5가 MRR과 같은 부호**여야 한다.
  - **D의 순열 p < 0.05와 부트스트랩 CI 판정이 일치**해야 한다.
  - **E에서 4개 시드 전부 같은 판정**이어야 한다.
  - **5개 중 하나라도 어긋나면 "단일 지표 우위"로 격하**해 보고하고, 채택
    판단을 파이프라인 밖 지표로 넘긴다.

생성 비용 0(GPU 미사용) — 저장된 캡션을 재임베딩·재평가만 한다. 서버 스윕과
경합하지 않는다. work/·results/ 불변, test 미접촉.

재현: python docs/probes/caption_cross_validation.py
"""
import io, json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                          # noqa: E402
from m4_index import embed_texts                       # noqa: E402
from m5_search import VideoIndex                       # noqa: E402
from m6_evaluate import evaluate                       # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
CAPDIR = OUT / "caption_sweep_captions"
REF = "qwen25_3b_4bit__P0"
CANDS = ["qwen3vl_4b__P1", "qwen3vl_4b__P2", "qwen3vl_4b__P3",
         "varco_1_7b__P1", "qwen25_7b__P1"]
SEEDS = [42, 1, 7, 2026]
METRICS = ["mrr", "hit@1", "hit@5", "hit@10"]
PERM_N = 20000


def boot_ci(a, b, seed, B=20000):
    """쌍체 부트스트랩(질의 단위 재표집). 공유 인덱스로 상관을 보존한다."""
    n = len(a)
    ib = np.random.default_rng(seed).integers(0, n, size=(B, n))
    d = a[ib].mean(1) - b[ib].mean(1)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return float(a.mean() - b.mean()), float(lo), float(hi), bool(lo > 0 or hi < 0)


def perm_p(a, b, seed=42, N=PERM_N):
    """쌍체 순열검정. 귀무가설 아래서는 각 질의의 (후보-기준) 부호가 대칭이므로
    부호를 무작위로 뒤집어 귀무분포를 만든다. 부트스트랩과 가정이 다른 별개
    기계라, 둘이 같은 결론을 내야 수치를 믿을 수 있다."""
    d = a - b
    obs = abs(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(N, len(d)))
    null = (signs * d).mean(1)
    return float((np.abs(null) >= obs).mean())


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}

    def load(stem):
        p = CAPDIR / f"{stem}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        if any(v not in d or len(d[v]) != len(base[v].segments) for v in vids):
            return None
        return d

    def per_query(texts):
        idx = {v: VideoIndex(segments=base[v].segments, emb_sub=base[v].emb_sub,
                             emb_cap=embed_texts(texts[v], cfg["embed_model"]),
                             static_mask=base[v].static_mask) for v in vids}
        return evaluate(dev, idx, 0.0, cfg)["per_query"]

    ref_caps = load(REF)
    assert ref_caps, f"기준 arm 캡션이 없다: {REF}"
    rows = {REF: per_query(ref_caps)}
    for c in CANDS:
        caps = load(c)
        if caps is None:
            print(f"건너뜀(캡션 없음/불일치): {c}", flush=True)
            continue
        rows[c] = per_query(caps)
    print(f"평가 완료 arm {len(rows)}개 (질의 {len(dev)})", flush=True)

    def vec(arm, metric):
        return np.array([float(r[metric]) for r in rows[arm]])

    rep = {"note": "dev-only, 채택 아님. 같은 표본을 다시 자르는 안정성 검정이지 "
                   "독립 증거가 아니다. 독립 증거는 AI Hub 참조 지표(별도 프로브).",
           "prereg": {
               "rules": ["A: 3영상 중 2영상 이상 같은 부호",
                         "B: 장면형 Δ > 자막형 Δ",
                         "C: hit@1·hit@5가 MRR과 같은 부호",
                         "D: 순열 p<0.05와 부트스트랩 판정 일치",
                         "E: 시드 4종 전부 같은 판정",
                         "하나라도 어긋나면 '단일 지표 우위'로 격하"],
               "declared_before_run": True},
           "reference": REF, "seeds": SEEDS, "arms": {}}

    qvid = [q["video_id"] for q in dev]
    qtyp = [q["type"] for q in dev]

    for arm in rows:
        if arm == REF:
            continue
        a_mrr, b_mrr = vec(arm, "mrr"), vec(REF, "mrr")
        blk = {"n": len(dev)}

        # ── C. 대체 지표 ──
        blk["metrics"] = {}
        for m in METRICS:
            d, lo, hi, sig = boot_ci(vec(arm, m), vec(REF, m), 42)
            blk["metrics"][m] = {"delta": round(d, 4),
                                 "ci95": [round(lo, 4), round(hi, 4)],
                                 "significant": sig}
        blk["median_rank"] = {
            "ref": float(np.median([r["rank"] for r in rows[REF]])),
            "arm": float(np.median([r["rank"] for r in rows[arm]]))}

        # ── A. 영상 단위 ──
        blk["by_video"], blk["leave_one_out"] = {}, {}
        for v in vids:
            inv = np.array([x == v for x in qvid])
            d, lo, hi, sig = boot_ci(a_mrr[inv], b_mrr[inv], 42)
            blk["by_video"][v] = {"n": int(inv.sum()), "delta": round(d, 4),
                                  "ci95": [round(lo, 4), round(hi, 4)],
                                  "significant": sig}
            d2, lo2, hi2, sig2 = boot_ci(a_mrr[~inv], b_mrr[~inv], 42)
            blk["leave_one_out"][f"without_{v}"] = {
                "n": int((~inv).sum()), "delta": round(d2, 4),
                "ci95": [round(lo2, 4), round(hi2, 4)], "significant": sig2}

        # ── B. 유형별 ──
        blk["by_type"] = {}
        for t in sorted(set(qtyp)):
            m = np.array([x == t for x in qtyp])
            d, lo, hi, sig = boot_ci(a_mrr[m], b_mrr[m], 42)
            blk["by_type"][t] = {"n": int(m.sum()), "delta": round(d, 4),
                                 "ci95": [round(lo, 4), round(hi, 4)],
                                 "significant": sig}

        # ── D. 순열검정 ──
        p = perm_p(a_mrr, b_mrr)
        blk["permutation"] = {"p": round(p, 5), "significant": bool(p < 0.05)}

        # ── E. 시드 4종 ──
        blk["seeds"] = {}
        for s in SEEDS:
            d, lo, hi, sig = boot_ci(a_mrr, b_mrr, s)
            blk["seeds"][str(s)] = {"ci95": [round(lo, 4), round(hi, 4)],
                                    "significant": sig}

        # ── 사전 등록 규칙 채점 ──
        sgn = np.sign(blk["metrics"]["mrr"]["delta"])
        same_video = sum(1 for v in vids
                         if np.sign(blk["by_video"][v]["delta"]) == sgn)
        scene = blk["by_type"].get("장면형", {}).get("delta", 0.0)
        subt = blk["by_type"].get("자막형", {}).get("delta", 0.0)
        checks = {
            "A_videos_same_sign": {"pass": bool(same_video >= 2),
                                   "detail": f"{same_video}/{len(vids)}"},
            "B_scene_gt_subtitle": {"pass": bool(scene > subt),
                                    "detail": f"장면형 {scene:+.4f} vs 자막형 {subt:+.4f}"},
            "C_hit_agrees_mrr": {
                "pass": bool(np.sign(blk["metrics"]["hit@1"]["delta"]) == sgn
                             and np.sign(blk["metrics"]["hit@5"]["delta"]) == sgn),
                "detail": f"hit@1 {blk['metrics']['hit@1']['delta']:+.4f} "
                          f"hit@5 {blk['metrics']['hit@5']['delta']:+.4f}"},
            "D_perm_agrees_boot": {
                "pass": bool(blk["permutation"]["significant"]
                             == blk["metrics"]["mrr"]["significant"]),
                "detail": f"perm p={p:.4f} vs boot {blk['metrics']['mrr']['significant']}"},
            "E_seeds_agree": {
                "pass": bool(len({v["significant"] for v in blk["seeds"].values()}) == 1),
                "detail": str({k: v["significant"] for k, v in blk["seeds"].items()})}}
        blk["checks"] = checks
        blk["verdict"] = ("교차검증 통과 — 안정적" if all(c["pass"] for c in checks.values())
                          else "격하: 단일 지표 우위 — 파이프라인 밖 지표로 판단 이관")
        rep["arms"][arm.replace("__", "/")] = blk

        print(f"\n[{arm.replace('__', '/')}] ΔMRR {blk['metrics']['mrr']['delta']:+.4f} "
              f"CI{blk['metrics']['mrr']['ci95']}", flush=True)
        for k, c in checks.items():
            print(f"   {'OK ' if c['pass'] else 'NG '} {k}: {c['detail']}", flush=True)
        print(f"   => {blk['verdict']}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "caption_cross_validation.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n->", p)


if __name__ == "__main__":
    main()
