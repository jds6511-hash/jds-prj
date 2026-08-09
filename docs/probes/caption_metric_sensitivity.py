"""[캡션 평가 계측기의 민감도 — 양성 대조군. dev 전용, 채택 아님]

**왜 필요한가.** 캡션 모델 비교가 "전부 비유의"로 끝났을 때 해석이 두 갈래다.
  (a) 모델들이 실제로 비슷하다
  (b) **계측기가 둔해서 차이를 못 잡는다**
둘을 구분하지 못하면 어떤 결론도 못 낸다. 그리고 결과를 본 뒤에 지표를 바꾸면
그건 측정이 아니라 조작이다. 그래서 **모델 결과를 보기 전에** 계측기부터 검정한다.

**설계 — 답을 아는 열화를 주입한다.** 현행 캡션을 일정 비율로 **같은 영상 안 다른
세그먼트 캡션과 바꿔치기**한다. 바꾼 캡션은 문법도 어휘도 자연스럽지만 **그 세그먼트의
내용이 아니다.** 즉 "캡션 품질이 정확히 이만큼 나빠졌다"를 아는 상태를 만든다.

여기서 나오는 것이 **계측기가 검출할 수 있는 최소 열화율**이다. 예를 들어 10% 오염을
못 잡으면, 모델 간의 미세한 차이는 당연히 못 잡는다 — 그때 "비유의"는 "모델이 같다"가
아니라 "이 저울로는 못 잰다"이고, 판단 근거를 파이프라인 밖 지표로 넘겨야 한다.

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-09).**
  - 계측기가 **10% 오염을 유의하게 검출**하면: 모델 간 비유의는 신뢰할 수 있다
    ("모델 차이가 오염 10% 미만 수준"). 캡션 모델 유지 결론이 성립한다.
  - 10%는 못 잡고 **20~40%만** 잡으면: 계측기가 둔하다. 모델 비교의 비유의는
    정보가 없고, AI Hub 사람 묘사 대비 지표로 판단을 넘긴다.
  - **40%도 못 잡으면**: dev 검색 지표는 캡션 품질 계측기로 부적격. 그 사실 자체를
    보고하고 이 실험군 전체를 파이프라인 밖 지표로 대체한다.

셔플(100% 오염)이 무너지지 않으면 그건 **평가 자체가 캡션을 안 보고 있다는 뜻**이라
그 시점에서 실험을 중단하고 원인을 찾는다.

생성 비용 0 — 이미 있는 캡션을 섞기만 한다. work/·results/ 불변, test 미접촉.
재현: python docs/probes/caption_metric_sensitivity.py
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
FRACTIONS = [0.0, 0.05, 0.10, 0.20, 0.40, 1.0]
# 두 번째 양성 대조군 — 전 캡션을 이 길이로 자른다. 바꿔치기(정합성 파괴)와 달리
# **세부 정보만** 줄어드는 열화라 "덜 자세한 모델"에 더 가깝다. 7B가 실제로
# 현행의 절반 길이(64.7자 vs 130.5자)를 내므로 그 조건을 흉내낸 것이기도 하다.
TRUNC_LENS = [100, 65, 45]
SEED = 42


def corrupt(texts: list[str], frac: float, rng) -> list[str]:
    """frac 비율의 캡션을 **같은 영상 안 다른 세그먼트 캡션**으로 바꾼다.

    무작위 문자열이 아니라 실제 캡션을 쓰는 이유: 문법·어휘·길이 분포를 유지한 채
    **정합성만** 깨야 "캡션 품질 저하"를 흉내낸 것이 된다. 빈 문자열이나 잡음을 넣으면
    임베딩이 이상해져서 실제 모델 차이와 다른 종류의 신호를 만든다.
    """
    n = len(texts)
    k = int(round(n * frac))
    if k == 0:
        return list(texts)
    idx = rng.choice(n, k, replace=False)
    src = rng.choice(n, k, replace=True)          # 같은 영상 내 다른 세그먼트
    out = list(texts)
    for i, s in zip(idx, src):
        if s == i:
            s = (s + 1) % n
        out[i] = texts[s]
    return out


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}
    texts = {v: [s.get("caption") or "" for s in base[v].segments] for v in vids}

    rep = {"note": "dev-only, 채택 아님. 계측기 민감도 검정(양성 대조군). test 미접촉.",
           "prereg": {
               "rule": ("10% 오염 검출 시 모델 비유의 신뢰 가능 / 20~40%만 검출 시 "
                        "AI Hub 참조 지표로 판단 이관 / 40%도 미검출 시 dev 검색 지표를 "
                        "캡션 품질 계측기로 부적격 처리"),
               "declared_before_model_results": True},
           "fractions": FRACTIONS, "by_fraction": {}}

    vecs = {}
    for f in FRACTIONS:
        rng = np.random.default_rng(SEED)
        idx = {v: VideoIndex(segments=base[v].segments, emb_sub=base[v].emb_sub,
                             emb_cap=embed_texts(corrupt(texts[v], f, rng),
                                                 cfg["embed_model"]),
                             static_mask=base[v].static_mask) for v in vids}
        blk = {}
        for alpha, name in ((0.0, "caption_only"), (0.5, "fused")):
            r = evaluate(dev, idx, alpha, cfg)
            blk[f"mrr_{name}"] = r["metrics"]["mrr"]
            vecs[(f, name)] = np.array([x["mrr"] for x in r["per_query"]])
        rep["by_fraction"][str(f)] = blk
        print(f"[오염 {f:>5.0%}] 캡션단독 {blk['mrr_caption_only']:.4f} | "
              f"융합 {blk['mrr_fused']:.4f}", flush=True)

    for L in TRUNC_LENS:
        idx = {v: VideoIndex(segments=base[v].segments, emb_sub=base[v].emb_sub,
                             emb_cap=embed_texts([t[:L] for t in texts[v]],
                                                 cfg["embed_model"]),
                             static_mask=base[v].static_mask) for v in vids}
        blk = {}
        for alpha, name in ((0.0, "caption_only"), (0.5, "fused")):
            r = evaluate(dev, idx, alpha, cfg)
            blk[f"mrr_{name}"] = r["metrics"]["mrr"]
            vecs[(f"trunc{L}", name)] = np.array([x["mrr"] for x in r["per_query"]])
        rep["by_fraction"][f"trunc{L}"] = blk
        print(f"[{L}자 절단] 캡션단독 {blk['mrr_caption_only']:.4f} | "
              f"융합 {blk['mrr_fused']:.4f}", flush=True)

    n, B = len(dev), cfg["bootstrap_B"]
    ib = np.random.default_rng(SEED).integers(0, n, size=(B, n))
    rep["contrasts"] = {}
    detected = {}
    for f in FRACTIONS[1:] + [f"trunc{L}" for L in TRUNC_LENS]:
        for name in ("caption_only", "fused"):
            b, k = vecs[(0.0, name)], vecs[(f, name)]
            d = k[ib].mean(1) - b[ib].mean(1)
            lo, hi = np.percentile(d, [2.5, 97.5])
            sig = bool(lo > 0 or hi < 0)
            rep["contrasts"][f"corrupt{f}_vs_clean/{name}"] = {
                "delta": round(float(k.mean() - b.mean()), 4),
                "ci95": [round(float(lo), 4), round(float(hi), 4)], "significant": sig}
            if sig and isinstance(f, float) and name not in detected:
                detected[name] = f
    rep["min_detectable_corruption"] = detected
    rep["verdict"] = {
        name: ("신뢰 가능 — 10% 이하 열화를 검출" if detected.get(name, 9) <= 0.10 else
               "둔함 — 파이프라인 밖 지표로 판단 이관" if detected.get(name, 9) <= 0.40 else
               "부적격 — 40% 열화도 검출 못 함")
        for name in ("caption_only", "fused")}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "caption_metric_sensitivity.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print("검출 가능한 최소 오염률:", detected)
    print("판정:", json.dumps(rep["verdict"], ensure_ascii=False))
    print("->", p)


if __name__ == "__main__":
    main()
