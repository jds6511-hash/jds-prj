"""[자막 품질 → 검색 성능 환산 — 양성 대조군. dev 전용, 채택 아님]

**왜 필요한가.** STT 설정 변경(빔5→그리디)의 이득은 **ΔCER −0.0093**(KconfSpeech 실측,
유의)이다. 그런데 우리가 정말 알아야 할 것은 CER이 아니라 **검색 성능**이고, 둘 사이의
환산 관계를 모른다. dev에서 재전사해 확인하려면 GPU를 쓰는데, **그 전에 "그만한 CER
변화가 검색 지표로 검출 가능한 크기인가"를 먼저 알 수 있다.**

**설계 — 자막에 알려진 크기의 문자 오류를 주입한다.** 현행 자막을 기준(reference)으로
두고 문자 단위 치환·삭제를 비율별로 넣어 **CER을 인위적으로 올린다.** 그 상태의
자막 단독(α=1.0) MRR을 재면 **ΔCER 대비 ΔMRR 기울기**가 나온다.

기울기를 알면 답이 나온다:
  기대 ΔMRR ≈ 기울기 × 0.0093
이 값이 dev 검출 한계(자막 단독 MDE)보다 훨씬 작으면 **dev 재전사로는 검증이 불가능**
하고, 그때 빔 설정 판단은 CER 근거만으로 해야 한다. 그걸 모르고 GPU를 쓰면 "차이
없음"이라는 정보 없는 결과에 시간을 쓴다.

**주의 — 이 환산은 상한이 아니라 근사다.** 주입 오류는 무작위로 흩어지지만 실제 ASR
오류는 특정 어휘(고유명사·전문용어)에 몰린다. 질의가 그런 단어를 담고 있으면 같은
CER이라도 검색에 더 큰 영향을 준다. 즉 **실제 효과가 이 추정보다 클 수 있다.**
반대로 오류가 질의와 무관한 곳에 몰리면 더 작다. 방향을 단정하지 말고 자릿수만 본다.

생성 비용 0 — 저장된 자막을 변형만 한다. work/·results/ 불변, test 미접촉.
재현: python docs/probes/stt_metric_sensitivity.py
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
# 주입 오류율. 빔 효과(0.0093)를 포함하도록 아래쪽을 촘촘히 잡는다.
RATES = [0.0, 0.01, 0.02, 0.05, 0.10, 0.20]
SEED = 42
HANGUL0, HANGUL1 = 0xAC00, 0xD7A3


def inject(text: str, rate: float, rng) -> str:
    """문자 단위 오류 주입. ASR 오류 구성을 대략 흉내낸다 — 치환 2 : 삭제 1.

    치환은 무작위 한글 음절로 한다(자모 혼동을 정교하게 흉내내지 않는다 — 목적이
    '오류율 대비 검색 영향'의 자릿수 파악이라 오류 종류의 사실성은 부차적이다).
    """
    if rate <= 0 or not text:
        return text
    out = []
    for ch in text:
        r = rng.random()
        if r < rate * (2 / 3):
            out.append(chr(rng.integers(HANGUL0, HANGUL1 + 1)))
        elif r < rate:
            continue                                   # 삭제
        else:
            out.append(ch)
    return "".join(out)


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}
    subs = {v: [(s.get("subtitle") or "") for s in base[v].segments] for v in vids}

    rep = {"note": "dev-only, 채택 아님. 자막 품질→검색 환산 계수. test 미접촉.",
           "why": ("빔5→그리디의 이득 ΔCER -0.0093이 검색 지표로 검출 가능한 크기인지를 "
                   "GPU 재전사 전에 판단한다."),
           "rates": RATES, "seed": SEED, "by_rate": {}}
    vecs = {}
    for rate in RATES:
        rng = np.random.default_rng(SEED)
        noisy, d, n = {}, 0, 0
        for v in vids:
            noisy[v] = [inject(t, rate, rng) for t in subs[v]]
            for a, b in zip(subs[v], noisy[v]):
                d += edit_distance(a, b)
                n += len(a)
        cer = d / max(n, 1)
        idx = {v: VideoIndex(segments=base[v].segments,
                             emb_sub=embed_texts(noisy[v], cfg["embed_model"]),
                             emb_cap=base[v].emb_cap,
                             static_mask=base[v].static_mask) for v in vids}
        blk = {"induced_cer": round(cer, 4)}
        for alpha, name in ((1.0, "subtitle_only"), (0.5, "fused")):
            r = evaluate(dev, idx, alpha, cfg)
            blk[f"mrr_{name}"] = r["metrics"]["mrr"]
            vecs[(rate, name)] = np.array([x["mrr"] for x in r["per_query"]])
        rep["by_rate"][str(rate)] = blk
        print(f"[주입 {rate:>5.0%}] 유발 CER {cer:.4f} | 자막단독 {blk['mrr_subtitle_only']:.4f} "
              f"| 융합 {blk['mrr_fused']:.4f}", flush=True)

    n_q, B = len(dev), cfg["bootstrap_B"]
    ib = np.random.default_rng(SEED).integers(0, n_q, size=(B, n_q))
    rep["contrasts"] = {}
    for rate in RATES[1:]:
        for name in ("subtitle_only", "fused"):
            b, k = vecs[(0.0, name)], vecs[(rate, name)]
            dd = k[ib].mean(1) - b[ib].mean(1)
            lo, hi = np.percentile(dd, [2.5, 97.5])
            rep["contrasts"][f"rate{rate}/{name}"] = {
                "delta": round(float(k.mean() - b.mean()), 4),
                "ci95": [round(float(lo), 4), round(float(hi), 4)],
                "significant": bool(lo > 0 or hi < 0)}

    # 환산 계수: 유발 CER 대비 자막단독 MRR 기울기(원점 통과 최소제곱)
    x = np.array([rep["by_rate"][str(r)]["induced_cer"] for r in RATES])
    y = np.array([rep["by_rate"][str(r)]["mrr_subtitle_only"] for r in RATES])
    y0 = y[0] - y
    slope = float(np.dot(x, y0) / np.dot(x, x)) if np.dot(x, x) > 0 else float("nan")
    # 자막단독 검출 한계
    v0 = vecs[(0.0, "subtitle_only")]
    mde = float(1.96 * v0[ib].mean(1).std())
    rep["conversion"] = {
        "slope_dMRR_per_dCER": round(slope, 3),
        "beam_gain_dCER": 0.0093,
        "expected_dMRR": round(slope * 0.0093, 4),
        "subtitle_only_MDE95": round(mde, 4),
        "detectable": bool(slope * 0.0093 > mde),
        "verdict": ("검출 가능 — dev 재전사로 검증할 가치가 있다"
                    if slope * 0.0093 > mde else
                    "검출 불가 — dev 재전사로는 확인되지 않는다. 빔 판단은 CER 근거로만 한다")}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "stt_metric_sensitivity.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"환산 계수 ΔMRR/ΔCER = {slope:.3f}")
    print(f"빔 이득 ΔCER 0.0093 → 기대 ΔMRR {slope*0.0093:+.4f} "
          f"(자막단독 검출 한계 ±{mde:.4f})")
    print("판정:", rep["conversion"]["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
