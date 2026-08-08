"""[캡션 품질을 파이프라인 밖에서 잰다 — AI Hub 사람 묘사 대비. 채택 아님, 실측용]

**왜 필요한가.** dev MRR로 캡션 모델을 비교하면 세 가지가 한꺼번에 섞인다:
① 캡션 품질, ② KURE-v1이 그 품질 차이를 벡터로 옮기는 능력, ③ 5초 세그먼트 변별이라는
과제 성격. 그래서 "후보가 나쁘다"와 "우리 파이프라인이 차이를 못 잡는다"가 구분되지
않는다. 실제로 Qwen2.5-VL 7B가 3B를 못 이겼을 때 이 구분을 못 했다.

**이 프로브는 ①만 잰다.** AI Hub `003.비디오 장면 설명문 생성 데이터`에는 **사람이 쓴
한국어 장면 묘사**가 시간 구간과 함께 있다. 그 구간에 속하는 세그먼트의 대표 프레임을
각 모델로 캡션해 사람 묘사와 직접 대조한다. 우리 검색 지표를 전혀 거치지 않는다.

**지표 2종을 나란히 본다 — 갈리면 그게 병목의 증거다.**
  chrF   문자 n-gram F-score. **임베딩을 거치지 않는다.**
  cos    KURE-v1 코사인. 우리 파이프라인이 실제로 쓰는 표현 공간.
chrF는 오르는데 cos가 안 오르면 "캡션은 좋아졌는데 임베더가 그 차이를 못 옮긴다"이고,
그때 손봐야 할 것은 캡션 모델이 아니라 **임베딩 모델**이다.

**사전 등록 (실행 전 확정, 2026-08-08).**
- 표본: 사람 묘사가 **정확히 1개** 덮는 세그먼트만(중의성 제거), 도메인 층화, seed 42,
  총 300개. 결과를 보고 표본을 바꾸지 않는다.
- 모델별로 **dev 스윕에서 고른 최고 프롬프트 1개**만 돌린다(24 arm 전부는 불필요).
- 현행 모델은 `work_aihub`에 이미 있는 캡션을 재사용한다 — **같은 서버에서 생성된**
  산출분이라 환경 교란이 없다.
- chrF와 cos의 순위가 어긋나면 **어긋났다는 사실 자체를 결과로 보고**한다.

재현: python docs/probes/aihub_caption_reference.py --config config_aihub.yaml \
        --arms qwen25_7b:P0,varco_1_7b:P2,...
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                          # noqa: E402
from m4_index import embed_texts                       # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
SEED = 42
N_SAMPLE = 300
CHRF_N, CHRF_BETA = 6, 2.0


def _ngrams(s: str, n: int) -> Counter:
    s = "".join(s.split())          # 공백 제거 — 한국어 띄어쓰기 변동을 벌하지 않는다
    return Counter(s[i:i + n] for i in range(len(s) - n + 1))


def chrf(ref: str, hyp: str, nmax: int = CHRF_N, beta: float = CHRF_BETA) -> float:
    """문자 n-gram F-score(chrF). 임베딩·형태소 분석기에 의존하지 않는다.

    n=1..nmax의 정밀도·재현율을 각각 평균한 뒤 F_beta를 낸다(표준 chrF 정의).
    beta=2는 재현율을 더 본다 — 캡션이 사람 묘사의 내용을 얼마나 담았는지가 관심사다.
    """
    ps, rs = [], []
    for n in range(1, nmax + 1):
        r, h = _ngrams(ref, n), _ngrams(hyp, n)
        if not r or not h:
            continue
        overlap = sum((r & h).values())
        ps.append(overlap / sum(h.values()))
        rs.append(overlap / sum(r.values()))
    if not ps:
        return 0.0
    p, r = float(np.mean(ps)), float(np.mean(rs))
    if p + r == 0:
        return 0.0
    b2 = beta ** 2
    return (1 + b2) * p * r / (b2 * p + r)


def build_sample(cfg, queries_path: Path, split: str = "selection") -> list[dict]:
    """사람 묘사가 정확히 1개 덮는 세그먼트만, 도메인 층화 표집.

    **selection / evaluation을 서로 겹치지 않게 나눈다.** 프롬프트를 고른 표본에서
    최종 수치를 내면 선택 편향이 붙는다. 고르기는 selection에서, 보고는 evaluation에서.
    """
    qs = [json.loads(l) for l in queries_path.read_text(encoding="utf-8").splitlines()
          if l.strip()]
    cover: dict[tuple, list] = {}
    for q in qs:
        for si in q["gt_seg_idx"]:
            cover.setdefault((q["video_id"], si), []).append(q)
    cands = []
    for (vid, si), qq in cover.items():
        if len(qq) != 1:
            continue                      # 중의성 제거: 묘사가 겹치는 세그먼트는 뺀다
        sp = Path(common.work_dir(cfg, vid)) / "segments.json"
        if not sp.exists():
            continue
        doc = json.loads(sp.read_text(encoding="utf-8"))
        if si >= len(doc["segments"]):
            continue
        s = doc["segments"][si]
        if not s.get("rep_frame"):
            continue
        cands.append({"video_id": vid, "seg_idx": si, "domain": qq[0]["type"],
                      "ref": qq[0]["text"].strip(),
                      "frame": str(Path(common.work_dir(cfg, vid)) / s["rep_frame"]),
                      "cur_caption": s.get("caption") or ""})
    rng = np.random.default_rng(SEED)
    bydom: dict[str, list] = {}
    for c in sorted(cands, key=lambda x: (x["video_id"], x["seg_idx"])):
        bydom.setdefault(c["domain"], []).append(c)
    per = max(1, N_SAMPLE // max(len(bydom), 1))
    sel, ev = [], []
    for d in sorted(bydom):
        pool = bydom[d]
        take = min(per * 2, len(pool))                 # selection + evaluation
        pick = rng.choice(len(pool), take, replace=False)
        half = take // 2
        sel += [pool[i] for i in pick[:half]]
        ev += [pool[i] for i in pick[half:half * 2]]
    return (sel if split == "selection" else ev)[:N_SAMPLE]


def score(refs: list[str], hyps: list[str], embed_model: str) -> dict:
    ch = [chrf(r, h) for r, h in zip(refs, hyps)]
    er, eh = embed_texts(refs, embed_model), embed_texts(hyps, embed_model)
    er = er / (np.linalg.norm(er, axis=1, keepdims=True) + 1e-9)
    eh = eh / (np.linalg.norm(eh, axis=1, keepdims=True) + 1e-9)
    cos = np.sum(er * eh, axis=1)
    return {"chrf": np.array(ch), "cos": cos}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    ap.add_argument("--split", default="selection", choices=("selection", "evaluation"),
                    help="selection에서 프롬프트를 고르고 evaluation에서 최종 수치를 낸다(서로 배타)")
    ap.add_argument("--arms", default="",
                    help="쉼표 구분 'modelkey:PROMPT'. 비우면 현행 재사용분만 채점")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    sample = build_sample(cfg, ROOT / a.queries, a.split)
    assert sample, "표본이 비었다 — work_aihub 인덱스와 질의 파일을 확인하라"
    refs = [s["ref"] for s in sample]
    print(f"표본 {len(sample)}개 / 도메인 {sorted({s['domain'] for s in sample})}", flush=True)

    rep = {"note": "채택 아님. 캡션 품질을 검색 지표 밖에서 잰다(AI Hub 제3자 사람 묘사).",
           "power": ("검정력 실측(2026-08-08): dev 검색 MRR n=96은 MDE ±0.086(평균 대비 "
                     "15.6%)이라 웬만한 차이를 못 잡는다. ±0.03을 잡으려면 질의 795건이 "
                     "필요하다. 이 지표는 n=300에서 cos MDE ±0.0112(2.0%), chrF ±0.0036"
                     "(6.7%)로 **훨씬 민감하다** — 그래서 모델 선택의 주지표로 쓴다."),
           "n_sample": len(sample), "split": a.split, "seed": SEED,
           "prereg": {"sample": "사람 묘사가 정확히 1개 덮는 세그먼트, 도메인 층화",
                      "metrics": ["chrf(임베더 무관)", "cos(KURE-v1)"],
                      "disagreement_rule": "chrf와 cos 순위가 어긋나면 그 사실을 결과로 보고",
                      "declared_before_run": True},
           "arms": {}}

    def add(name, hyps, note=""):
        sc = score(refs, hyps, cfg["embed_model"])
        rep["arms"][name] = {
            "note": note,
            "chrf_mean": round(float(sc["chrf"].mean()), 4),
            "cos_mean": round(float(sc["cos"].mean()), 4),
            "len_mean": round(float(np.mean([len(h) for h in hyps])), 1),
            "chrf": sc["chrf"].tolist(), "cos": sc["cos"].tolist()}
        print(f"[{name}] chrF {rep['arms'][name]['chrf_mean']:.4f} "
              f"cos {rep['arms'][name]['cos_mean']:.4f}", flush=True)

    add("cur_prod", [s["cur_caption"] for s in sample],
        "work_aihub 기존 캡션(현행 모델·P0, 같은 서버 생성분)")

    if a.arms:
        sys.path.insert(0, str(ROOT / "docs/probes"))
        from caption_model_sweep import MODELS, PROMPTS, load_captioner   # noqa: E402
        main_cfg = common.load_config(str(ROOT / "config.yaml"))
        for spec_s in [x for x in a.arms.split(",") if x]:
            mkey, pkey = spec_s.split(":")
            cap, close = load_captioner(MODELS[mkey], main_cfg)
            try:
                hyps = []
                for i, s in enumerate(sample):
                    hyps.append(cap(Path(s["frame"]), PROMPTS[pkey]))
                    if i % 50 == 0:
                        print(f"  {mkey}/{pkey} {i}/{len(sample)}", flush=True)
                add(f"{mkey}/{pkey}", hyps)
            finally:
                close()

    # 쌍체 부트스트랩 — 같은 표본에 대한 대비라 쌍체가 맞다.
    names = list(rep["arms"])
    rng = np.random.default_rng(SEED)
    ib = rng.integers(0, len(sample), size=(cfg["bootstrap_B"], len(sample)))
    rep["contrasts"] = {}
    for n in names[1:]:
        c = {}
        for m in ("chrf", "cos"):
            b = np.array(rep["arms"]["cur_prod"][m])
            k = np.array(rep["arms"][n][m])
            d = k[ib].mean(1) - b[ib].mean(1)
            lo, hi = np.percentile(d, [2.5, 97.5])
            c[m] = {"delta": round(float(k.mean() - b.mean()), 4),
                    "ci95": [round(float(lo), 4), round(float(hi), 4)],
                    "significant": bool(lo > 0 or hi < 0)}
        c["agree"] = (c["chrf"]["delta"] > 0) == (c["cos"]["delta"] > 0)
        rep["contrasts"][f"{n}_vs_cur_prod"] = c

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"aihub_caption_reference_{a.split}.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("->", p)


if __name__ == "__main__":
    main()
