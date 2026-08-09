"""[캡션 길이를 맞추고 모델을 비교한다 — dev 전용, 채택 아님, 실측용]

**왜 필요한가.** 스윕 1단계에서 길이와 성능이 같이 움직인다(2026-08-09 실측):

| arm | 평균 길이 | 캡션단독 MRR |
|---|---|---|
| qwen25_3b_4bit/P0 | 127.1자 | 0.4609 |
| qwen25_3b_4bit/P3 | 106.8자 | 0.3898 |
| qwen25_7b/P1 | 81.5자 | 0.4566 |
| qwen25_7b/P0 | 64.9자 | 0.4334 |

7B는 절단율이 0.1~0.3%다 — **토큰 상한에 안 걸린다.** P0의 "한 문장으로 묘사하라"를
곧이곧대로 지켜 스스로 멈춘다. 반면 3B는 같은 지시에서 계속 쓴다(절단율 15%).
즉 지금 비교는 **모델의 시각 이해력**과 **길이 지시 순응도**가 섞여 있다.

이미 재 놓은 대조군이 이 혼입을 정량화한다 — 현행 캡션을 65자로 자르면 캡션단독
MRR이 0.5535 → 0.3985(Δ−0.1551, 유의)다(`caption_metric_sensitivity.json`).
**길이 자체가 0.15를 움직인다.** 모델 간 차이(0.03 수준)보다 5배 크다.

**설계 — 같은 길이에서 붙인다.** 저장된 각 arm의 캡션을 공통 길이로 잘라 재임베딩·
재평가한다. 생성 비용 0(GPU 미사용, 서버 스윕과 경합하지 않는다).

**사전 등록한 판정 규칙 (스윕 1단계 결과를 보기 전 확정 — 3B 4 arm과 7B의 P0·P1만
본 시점, 2026-08-09).**
  - 공통 길이에서 **순위가 뒤집히면**: 1단계의 "3B 우위"는 길이 산물이다. 후속으로
    길이를 열어 주는 프롬프트를 **전 모델 대칭**으로 추가해 2단계를 다시 잰다.
  - 공통 길이에서 **순위가 유지되면**: 3B가 같은 글자수로 더 나은 내용을 담은 것이고,
    길이는 설명이 아니다. 프롬프트 추가를 하지 않는다.
  - **어느 쪽이든 1단계 결론을 이 결과로 덮어쓰지 않는다.** 1단계는 사전 등록된
    격자이고 이건 사후 분석이다. 별도로 보고한다.

**이 분석의 한계 — 자른 캡션은 짧게 태어난 캡션과 다르다.** 문자 절단은 문장을
조각내지만 7B의 짧은 캡션은 완결된 문장이다. 그래서 절단은 **긴 모델에게 불리**하다.
이를 보정하려고 두 방식을 같이 낸다:
  cut   단순 문자 절단(하한)
  sent  절단 후 마지막 완결 문장까지만(`common.truncate_to_sentence`, 운영 함수)

work/·results/ 불변, test 미접촉.
재현: python docs/probes/caption_length_matched.py --caps <서버에서 받은 디렉터리>
"""
import argparse, io, json, statistics as st, sys
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
LENGTHS = [45, 65, 85, 100]          # 관측된 arm 평균 길이 구간을 덮는다


def cut(t: str, n: int, mode: str) -> str:
    c = t[:n]
    return common.truncate_to_sentence(c) if mode == "sent" else c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--caps", default="docs/probes/_scratch/caption_sweep_captions",
                    help="arm별 캡션 JSON 디렉터리(mkey__pkey.json)")
    ap.add_argument("--min-captions", type=int, default=100,
                    help="이보다 적으면 파일럿 잔재로 보고 건너뛴다")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}

    caps_dir = ROOT / a.caps
    arms = {}
    for f in sorted(caps_dir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if any(v not in d or len(d[v]) != len(base[v].segments) for v in vids):
            print(f"건너뜀(세그먼트 수 불일치): {f.name}", flush=True)
            continue
        if sum(len(d[v]) for v in vids) < a.min_captions:
            continue
        arms[f.stem.replace("__", "/")] = d
    # 현행(노트북 생성분)도 같은 격자에 넣는다. 환경이 달라 arm 간 대비의
    # 기준선으로 쓰지 않지만, 길이-성능 곡선의 형태 비교에는 쓸 수 있다.
    arms["cur_laptop"] = {v: [s.get("caption") or "" for s in base[v].segments]
                          for v in vids}
    assert arms, f"캡션 파일이 없다: {caps_dir}"

    def mrr_of(texts):
        idx = {v: VideoIndex(segments=base[v].segments, emb_sub=base[v].emb_sub,
                             emb_cap=embed_texts(texts[v], cfg["embed_model"]),
                             static_mask=base[v].static_mask) for v in vids}
        r = evaluate(dev, idx, 0.0, cfg)
        return r["metrics"]["mrr"], np.array([x["mrr"] for x in r["per_query"]])

    rep = {"note": "dev-only, 채택 아님. 사후 분석 — 1단계 결론을 덮어쓰지 않는다.",
           "prereg": {
               "rule": ("공통 길이에서 순위가 뒤집히면 1단계 우위는 길이 산물 → "
                        "길이를 여는 프롬프트를 전 모델 대칭으로 추가해 2단계 재측정. "
                        "유지되면 프롬프트 추가 없음."),
               "declared_before_full_stage1": True,
               "seen_at_declaration": ["qwen25_3b_4bit/P0..P3", "qwen25_7b/P0", "qwen25_7b/P1"]},
           "caveat": ("문자 절단은 완결 문장으로 짧게 생성한 것과 다르다 — 긴 모델에게 "
                      "불리하다. cut(하한)과 sent(완결 문장까지)를 같이 낸다."),
           "lengths": LENGTHS, "arms": {}}

    vecs = {}
    for name, texts in arms.items():
        blk = {"len_mean": round(st.mean([len(t) for v in vids for t in texts[v]]), 1)}
        m, rr = mrr_of(texts)
        blk["mrr_natural"] = m
        vecs[(name, "natural")] = rr
        for L in LENGTHS:
            for mode in ("cut", "sent"):
                t2 = {v: [cut(t, L, mode) for t in texts[v]] for v in vids}
                m2, rr2 = mrr_of(t2)
                blk[f"mrr_{mode}{L}"] = m2
                blk[f"len_{mode}{L}"] = round(
                    st.mean([len(t) for v in vids for t in t2[v]]), 1)
                vecs[(name, f"{mode}{L}")] = rr2
        rep["arms"][name] = blk
        print(f"[{name:22s}] 원본 {blk['len_mean']:5.1f}자 {blk['mrr_natural']:.4f} | "
              + " ".join(f"{L}자 {blk[f'mrr_cut{L}']:.4f}" for L in LENGTHS), flush=True)

    # 같은 길이에서의 쌍체 대비 — 공유 부트스트랩 인덱스(질의 단위)
    n, B = len(dev), cfg["bootstrap_B"]
    ib = np.random.default_rng(cfg["seed"]).integers(0, n, size=(B, n))
    names = [x for x in rep["arms"] if x != "cur_laptop"]
    ref = "qwen25_3b_4bit/P0" if "qwen25_3b_4bit/P0" in names else names[0]
    rep["reference_arm"] = ref
    rep["contrasts"] = {}
    for name in names:
        if name == ref:
            continue
        for key in ["natural"] + [f"{m}{L}" for L in LENGTHS for m in ("cut", "sent")]:
            b, k = vecs[(ref, key)], vecs[(name, key)]
            d = k[ib].mean(1) - b[ib].mean(1)
            lo, hi = np.percentile(d, [2.5, 97.5])
            rep["contrasts"][f"{name}_vs_{ref}/{key}"] = {
                "delta": round(float(k.mean() - b.mean()), 4),
                "ci95": [round(float(lo), 4), round(float(hi), 4)],
                "significant": bool(lo > 0 or hi < 0)}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "caption_length_matched.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"기준 arm: {ref}")
    for k, v in rep["contrasts"].items():
        if v["significant"]:
            print(f"  ** {k}: {v['delta']:+.4f} CI{v['ci95']}")
    print("->", p)


if __name__ == "__main__":
    main()
