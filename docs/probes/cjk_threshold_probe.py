"""[오염 필터 임계 실험 — dev 전용, 인덱스 불변, test 미접촉]

**왜.** `common.is_corrupted_caption`은 한자·가나가 **3글자 이상**이어야 오염으로
본다. 2글자는 통과한다. 그 통과분 하나(panibottle seg 88 "靠垫")가 M8 리포트를
두 번 조기 종료시켜 영상 커버를 32.4%로 떨어뜨린 것이 2026-08-14에 규명됐다.
전 인덱스 2,568건 중 **183건(7.13%)** 이 같은 상태다.

임계를 낮추면 검색 성능이 어떻게 되나? 튜터 결정(2026-08-14): **낮춰보고 기존과
비교한다.**

**측정하는 것과 못 하는 것을 먼저 가른다.**

임계를 낮춘다는 것은 원칙상 그 캡션을 **재생성**한다는 뜻이다(운영 규약: 오염
캡션은 `--recaption-corrupted`로 재생성, 수동 편집 금지). 재생성에는 VLM이 필요하다.

이 프로브는 그중 **제거(strip)만** 잰다 — `common.strip_residual_cjk`로 한자·가나를
지운 캡션으로 재임베딩해 dev 96 검색 성능을 비교한다. 재생성은 GPU 확보 후 별도.

- **제거**가 성능을 해치지 않으면: 리포트 입력 시점 제거(이미 적용, 3c8a0ba)가
  안전한 선택이고, 인덱스까지 바꿀 근거는 약하다
- **제거가 성능을 올리면**: 인덱스 쪽도 손댈 근거가 생기고, 그때 재생성과 비교한다
- **제거가 성능을 내리면**: 한자 2글자가 검색에 기여하고 있다는 뜻이므로
  임계를 낮추면 안 된다

*제거는 재생성의 하한도 상한도 아니다. 재생성이 더 나을 수도, 더 나쁠 수도 있다.
이 프로브 결과로 재생성 효과를 추정하지 마라.*

**설계.** 인덱스는 건드리지 않는다 — 캡션을 메모리에서 변형하고 그 자리에서
재임베딩해 평가한다(embedder_sweep과 같은 방식). work/·results/ 불변.

재현: python docs/probes/cjk_threshold_probe.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                            # noqa: E402
from m4_index import embed_texts                         # noqa: E402
from m5_search import VideoIndex                         # noqa: E402
from m6_evaluate import evaluate                         # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
CJK = re.compile(r"[一-鿿぀-ヿ]")
SEED = 42
B = 20_000

# ── 사전 등록 (결과 보기 전 확정, 2026-08-14) ────────────────────────────────
PREREG = {
    "primary": "캡션 단독 α=0.0 MRR (dev 96)",
    "secondary": "융합 α=0.5 MRR (dev 96)",
    "contrast": "strip(제거) − base(현행). 쌍체 부트스트랩 95% CI + 부호뒤집기 순열",
    "mde_note": ("dev 96의 검출 한계는 ±0.086이다. 이보다 작은 차이는 '효과 있음'으로 "
                 "읽지 않는다 [튜터결정 2026-08-14 §2 R2]."),
    "decision_rule": {
        "제거가 유의하게 낫다": "인덱스 쪽 임계 인하를 검토하고, 재생성과 비교한다",
        "비유의": ("임계를 낮출 근거 없음. 리포트 입력 시점 제거(3c8a0ba)만 유지하고 "
                   "인덱스는 그대로 둔다 — 인덱스를 바꾸면 재평가 절차가 따라온다"),
        "제거가 유의하게 나쁘다": "임계를 낮추지 않는다. 한자 2글자가 검색에 기여한다",
    },
    "scope_limit": "제거만 측정한다. 재생성 효과는 이 결과로 추정하지 않는다",
    "declared_before_run": True,
}


def boot_ci(d, seed=SEED):
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), size=(B, len(d)))].mean(1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def perm_p(d, seed=SEED, n=200_000):
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    flips = rng.choice([-1.0, 1.0], size=(n, len(d)))
    return float((np.abs((flips * d).mean(1)) >= obs - 1e-12).mean())


def main():
    OUT.mkdir(exist_ok=True)
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}

    # 대상 집계 — 필터를 통과하는 CJK 혼입이 dev에 몇 건인가
    affected = {}
    for v in vids:
        hits = [i for i, s in enumerate(base[v].segments)
                if CJK.search(s.get("caption") or "")
                and not common.is_corrupted_caption(s.get("caption") or "")]
        affected[v] = hits
    n_aff = sum(len(h) for h in affected.values())
    n_seg = sum(len(base[v].segments) for v in vids)
    print(f"dev {len(vids)}편 {n_seg}구간 중 필터 통과 CJK 혼입 {n_aff}건 "
          f"({n_aff / n_seg:.2%})")
    if n_aff == 0:
        raise SystemExit("dev에 대상이 없다 — 비교할 것이 없음")

    # strip arm: 캡션에서 CJK만 제거하고 그 자리에서 재임베딩(인덱스 불변)
    stripped = {}
    for v in vids:
        texts = [common.strip_residual_cjk(s.get("caption") or "")
                 for s in base[v].segments]
        stripped[v] = texts
    changed = sum(1 for v in vids for a, b in
                  zip([s.get("caption") or "" for s in base[v].segments], stripped[v])
                  if a != b)
    print(f"실제로 문자열이 바뀐 세그먼트 {changed}건")

    arm = {}
    for v in vids:
        idx = VideoIndex.load(cfg, v)
        idx.emb_cap = embed_texts(stripped[v], cfg["embed_model"],
                                  cfg.get("embed_batch_size", 32))
        for s, t in zip(idx.segments, stripped[v]):
            s["caption"] = t
        arm[v] = idx

    res = {"note": __doc__.strip().splitlines()[0], "prereg": PREREG,
           "n_dev_queries": len(dev), "n_segments": n_seg,
           "n_filter_passing_cjk": n_aff, "n_changed": changed,
           "affected_by_video": {v: len(h) for v, h in affected.items()},
           "arms": {}, "contrasts": {}}

    for alpha, tag in ((0.0, "caption_only"), (0.5, "fused")):
        ev_b = evaluate(dev, base, alpha, cfg)
        ev_s = evaluate(dev, arm, alpha, cfg)
        rr_b = np.array([x["mrr"] for x in ev_b["per_query"]])
        rr_s = np.array([x["mrr"] for x in ev_s["per_query"]])
        d = rr_s - rr_b
        mean, lo, hi = boot_ci(d)
        res["arms"][tag] = {"base_mrr": round(float(rr_b.mean()), 4),
                            "strip_mrr": round(float(rr_s.mean()), 4),
                            "base_hit@1": ev_b["metrics"]["hit@1"],
                            "strip_hit@1": ev_s["metrics"]["hit@1"]}
        res["contrasts"][tag] = {"delta": round(mean, 4),
                                 "ci95": [round(lo, 4), round(hi, 4)],
                                 "perm_p": round(perm_p(d), 4),
                                 "significant": bool(lo > 0 or hi < 0)}
        print(f"[{tag}] base {rr_b.mean():.4f} → strip {rr_s.mean():.4f}  "
              f"Δ{mean:+.4f} CI[{lo:+.4f}, {hi:+.4f}]")

    c = res["contrasts"]["caption_only"]
    if c["significant"]:
        res["verdict"] = ("제거가 유의하게 낫다 — 인덱스 임계 인하 검토 대상"
                          if c["delta"] > 0 else
                          "제거가 유의하게 나쁘다 — 임계를 낮추지 않는다")
    else:
        res["verdict"] = ("비유의 — 임계를 낮출 근거 없음. 리포트 입력 시점 제거만 "
                          "유지하고 인덱스는 건드리지 않는다")
    print("\n판정:", res["verdict"])

    p = OUT / "cjk_threshold_probe.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("저장:", p)


if __name__ == "__main__":
    main()
