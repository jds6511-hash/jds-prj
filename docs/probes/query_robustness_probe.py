"""[질의 표현 강건성 — dev 전용, 인덱스 불변, test 미접촉]

**왜.** 질의를 조금 바꿔도 같은 장면을 찾는지 한 번도 재본 적이 없다. 실제 사용자는
평가 질의와 똑같이 쓰지 않는다.

**무엇을 발견했나 (설계 근거).** dev 96건 중 **95건(99%)** 이, test 39건은 **전부**
`…하는 장면`으로 끝난다. 평가 집합 전체가 한 템플릿을 공유한다. 그러면 두 가지가
섞인다.

1. 시스템이 질의 **내용**으로 찾는가
2. 모든 질의에 공통으로 붙은 **접미 토큰**에 기대고 있는가

캡션도 장면 묘사라 `장면`은 양쪽에 흔한 단어다. 이 토큰이 변별에 기여하지 않는다면
빼도 성능이 유지돼야 하고, 유지되지 않는다면 **헤드라인 수치가 템플릿 덕을 보고
있다**는 뜻이다.

**변형은 전부 기계적이다 — 사람이 새로 쓰지 않는다.** 패러프레이즈를 직접 지으면
"쉬운 쪽으로 썼다"는 반론을 못 막는다. 문자열 치환만 한다.

| 변형 | 규칙 | 의도 |
|---|---|---|
| T1 drop | 끝의 `장면` 삭제 | 접미 토큰 의존도 |
| T2 부분 | 끝의 `장면` → `부분` | 같은 자리 다른 단어 |
| T3 순간 | 끝의 `장면` → `순간` | 위와 같음, 다른 어휘 |
| T4 구어 | 끝의 `장면` → `장면 찾아줘` | 실제 사용자 어투 |

정답 구간(gt)은 건드리지 않는다 — 같은 질의의 다른 표현이므로 GT가 바뀔 이유가 없다.

**한계.** 이 프로브는 접미 템플릿 하나만 흔든다. 문장 전체를 다시 쓴 패러프레이즈
강건성은 재지 못한다(그건 사람이 쓴 패러프레이즈 집합이 필요하다). 결과를 "질의
강건성 전반"으로 일반화하지 마라.

work/·results/ 불변, 재임베딩은 질의 쪽만, test 미접촉.
재현: python docs/probes/query_robustness_probe.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                            # noqa: E402
from m5_search import VideoIndex                         # noqa: E402
from m6_evaluate import evaluate                         # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
SEED = 42
B = 20_000

VARIANTS = {
    "T1_drop":  lambda t: t[: -len("장면")].rstrip() if t.endswith("장면") else t,
    "T2_부분":   lambda t: (t[: -len("장면")] + "부분") if t.endswith("장면") else t,
    "T3_순간":   lambda t: (t[: -len("장면")] + "순간") if t.endswith("장면") else t,
    "T4_구어":   lambda t: (t + " 찾아줘") if t.endswith("장면") else t,
}

# ── 사전 등록 (결과 보기 전 확정, 2026-08-14) ────────────────────────────────
PREREG = {
    "primary": "융합 α=0.5 MRR (dev 96) — 배포 설정 그대로",
    "secondary": "캡션 단독 α=0.0 · 자막 단독 α=1.0 (채널별로 어디가 흔들리는지)",
    "contrast": "변형 − 원본. 쌍체 부트스트랩 95% CI + 부호뒤집기 순열",
    "multiplicity": "변형 4개를 한 가족으로 BH-FDR q=0.05",
    "mde_note": "dev 96 검출 한계 ±0.086. 쌍체 비교라 실제 CI는 더 좁다",
    "decision_rule": {
        "전 변형 비유의": "접미 템플릿에 기대고 있지 않다. 강건성 근거로 보고",
        "일부 변형 유의 하락": ("그 변형이 무엇을 흔들었는지 규명하고 한계로 기록. "
                            "헤드라인 수치가 템플릿 덕을 봤을 가능성을 명시"),
        "유의 상승": "템플릿이 오히려 방해했다는 뜻 — 질의 정규화 검토",
    },
    "scope_limit": "접미 템플릿 하나만 흔든다. 질의 강건성 전반으로 일반화 금지",
    "gt_unchanged": "정답 구간은 그대로 — 같은 질의의 다른 표현이다",
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


def bh(pvals, q=0.05):
    """Benjamini-Hochberg. 반환: {key: pass 여부}"""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    passed, thresh = {k: False for k in pvals}, 0
    for i, (k, p) in enumerate(items, 1):
        if p <= i / m * q:
            thresh = i
    for i, (k, _) in enumerate(items, 1):
        passed[k] = i <= thresh
    return passed


def main():
    OUT.mkdir(exist_ok=True)
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}

    n_tpl = sum(1 for q in dev if q["text"].strip().endswith("장면"))
    print(f"dev {len(dev)}건 중 '장면'으로 끝나는 질의 {n_tpl}건 ({n_tpl/len(dev):.0%})")

    res = {"note": __doc__.strip().splitlines()[0], "prereg": PREREG,
           "n_dev": len(dev), "n_template_suffix": n_tpl,
           "alpha": 0.5, "variants": {}, "examples": {}, "contrasts": {}}

    alphas = ((0.5, "fused"), (0.0, "caption_only"), (1.0, "subtitle_only"))
    base_rr = {}
    for a, tag in alphas:
        ev = evaluate(dev, idx, a, cfg)
        base_rr[tag] = np.array([x["mrr"] for x in ev["per_query"]])
        res["variants"].setdefault("base", {})[tag] = {
            "mrr": round(float(base_rr[tag].mean()), 4),
            "hit@1": ev["metrics"]["hit@1"]}
    print(f"원본  fused {base_rr['fused'].mean():.4f}  "
          f"cap {base_rr['caption_only'].mean():.4f}  "
          f"sub {base_rr['subtitle_only'].mean():.4f}")

    pv = {}
    for name, fn in VARIANTS.items():
        mod = [{**q, "text": fn(q["text"])} for q in dev]
        changed = sum(1 for a, b in zip(dev, mod) if a["text"] != b["text"])
        res["examples"][name] = [{"before": dev[i]["text"], "after": mod[i]["text"]}
                                 for i in (0, 5)]
        row = {"n_changed": changed}
        for a, tag in alphas:
            ev = evaluate(mod, idx, a, cfg)
            rr = np.array([x["mrr"] for x in ev["per_query"]])
            d = rr - base_rr[tag]
            mean, lo, hi = boot_ci(d)
            p = perm_p(d)
            row[tag] = {"mrr": round(float(rr.mean()), 4),
                        "hit@1": ev["metrics"]["hit@1"],
                        "delta": round(mean, 4), "ci95": [round(lo, 4), round(hi, 4)],
                        "perm_p": round(p, 4)}
            if tag == "fused":
                pv[name] = p
        res["variants"][name] = row
        f = row["fused"]
        print(f"{name:10s} 변경 {changed:3d}건  fused {f['mrr']:.4f} "
              f"Δ{f['delta']:+.4f} CI[{f['ci95'][0]:+.4f}, {f['ci95'][1]:+.4f}] p={f['perm_p']:.4f}")

    passed = bh(pv)
    res["bh_fdr"] = {"q": 0.05, "family": list(pv), "passed": passed}
    hits = [k for k, v in passed.items() if v]
    if not hits:
        res["verdict"] = ("전 변형 비유의 — 접미 템플릿에 기대고 있지 않다. "
                          "다만 흔든 것은 접미 하나뿐이다(일반화 금지)")
    else:
        res["verdict"] = (f"유의 변형 {hits} — 규명 후 한계로 기록. "
                          "헤드라인 수치가 템플릿 덕을 봤을 가능성 검토")
    print("\n판정:", res["verdict"])

    p = OUT / "query_robustness.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("저장:", p)


if __name__ == "__main__":
    main()
