"""[채택하면 실제로 무엇이 바뀌는가 — dev 전용, 채택 아님]

**왜 이 프로브가 따로 필요한가.** 캡션 스윕과 AI Hub 확증은 둘 다 **같은 배치에서
새로 생성한 서버 대조군**과 후보를 비교한다(후보 모델 검증 규약 4항 "동일 환경
대조군"). 그래야 모델 효과와 생성 환경 효과가 섞이지 않는다.

그런데 **실제로 배포되어 있는 인덱스는 노트북(RTX 3060)에서 생성한 캡션**이다.
후보(qwen3vl_4b, bf16 11.4GB 실측)는 6GB 노트북에서 못 돌리므로 채택하면
서버 생성분으로 통째로 교체된다. 즉 사용자가 체감하는 변화는

    서버 후보  −  노트북 현행

이고, 이건 스윕이 잰 값이 **아니다**. 2026-08-07에 같은 모델·양자화·프롬프트·
그리디인데도 노트북 생성분과 서버 생성분의 완전일치가 25.6%뿐이고 서버 재생성분의
dev MRR이 유의하게 낮다는 것을 이미 실측했다(Δ−0.0879 CI [−0.158, −0.023]).
그 환경 효과가 모델 효과와 **반대 방향**이라 상쇄될 수 있다.

**세 대비를 분해한다.**
  ① 모델 효과      서버 후보    − 서버 대조군    ← 스윕·확증이 재는 것
  ② 환경 효과      서버 대조군  − 노트북 현행    ← 8/7 실측의 재측정
  ③ 배포 변화      서버 후보    − 노트북 현행    ← 채택하면 실제로 일어나는 일
  ③ = ① + ② 이므로 ①이 양수여도 ②가 그만큼 음수면 ③은 0이다.

**주의 — 이건 가설검정이 아니다.** 채택 여부를 가르는 사전 등록 판정은 AI Hub
독립 확증이 이미 끝냈다(`aihub_model_confirm.py`). 여기서 구하는 것은 그 판정과
별개로, **채택 시 기대되는 실제 변화량**이다. p값을 채택 근거로 쓰지 마라.

**쌍 정렬 주의.** sweep의 rr_caption_only는 리스트이고 순서는 queries.jsonl의
dev 파일 순서다. 알파벳 정렬 키로 맞추면 쌍이 어긋나 평균은 맞고 CI·p만 틀린다
(실제로 한 번 틀렸다). 반드시 파일 순서로 맞춘다.

work/·results/ 불변, test 미접촉.
재현: python docs/probes/deploy_delta.py
"""
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402
from m5_search import VideoIndex                           # noqa: E402
from m6_evaluate import evaluate                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
SWEEP = OUT / "caption_sweep.json"
CONTROL = "qwen25_3b_4bit/P0"     # 서버에서 현행 설정으로 새로 생성한 대조군
CANDIDATE = "qwen3vl_4b/P1"       # dev 1단계 격자의 승자
B, PERM_N, SEED = 20_000, 200_000, 42


def boot_ci(d, seed=SEED):
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), size=(B, len(d)))].mean(1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def perm_p(d, seed=SEED):
    """쌍체 순열검정. 부트스트랩과 가정이 다른 별개 기계다."""
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    sg = rng.choice([-1.0, 1.0], size=(PERM_N, len(d)))
    return float((np.abs((sg * d).mean(1)) >= obs).mean())


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    ids = [q["query_id"] for q in dev]          # 파일 순서 — sweep 리스트와 같은 축

    base = {v: VideoIndex.load(cfg, v) for v in sorted({q["video_id"] for q in dev})}
    per_q = evaluate(dev, base, 0.0, cfg)["per_query"]
    lap_rr = {x["query_id"]: x["mrr"] for x in per_q}
    laptop = np.array([lap_rr[q] for q in ids])

    sweep = json.loads(SWEEP.read_text(encoding="utf-8"))["arms"]
    ctl = np.array(sweep[CONTROL]["rr_caption_only"])
    cand = np.array(sweep[CANDIDATE]["rr_caption_only"])
    if not (len(laptop) == len(ctl) == len(cand)):
        raise ValueError(f"길이 불일치: {len(laptop)} / {len(ctl)} / {len(cand)}")

    rep = {"note": "dev-only, 채택 아님. 채택 시 실제 변화량 추정. test 미접촉.",
           "caveat": "가설검정 아님 — 사전 등록 판정은 aihub_model_confirm.py가 끝냈다",
           "control": CONTROL, "candidate": CANDIDATE, "n": len(ids),
           "seed": SEED, "bootstrap_B": B, "perm_N": PERM_N,
           "mrr": {"laptop_incumbent": round(float(laptop.mean()), 4),
                   "server_control": round(float(ctl.mean()), 4),
                   "server_candidate": round(float(cand.mean()), 4)}}

    print(f"{'대비':44s} {'Δ':>9s}  {'CI95':>22s}  {'순열 p':>8s}")
    for key, label, d in (("model_effect", "① 모델 효과 (서버 후보 − 서버 대조군)", cand - ctl),
                          ("env_effect", "② 환경 효과 (서버 대조군 − 노트북 현행)", ctl - laptop),
                          ("deploy_delta", "③ 배포 변화 (서버 후보 − 노트북 현행)", cand - laptop)):
        m, lo, hi = boot_ci(d)
        p = perm_p(d)
        rep[key] = {"delta": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)],
                    "perm_p": round(p, 4)}
        print(f"{label:44s} {m:+9.4f}  [{lo:+7.4f}, {hi:+7.4f}]  {p:8.4f}")

    d3 = cand - laptop
    rep["per_query"] = {"candidate_better": int((d3 > 0).sum()),
                        "tie": int((d3 == 0).sum()),
                        "incumbent_better": int((d3 < 0).sum())}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "deploy_delta.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"평균 MRR — 노트북 현행 {laptop.mean():.4f} / 서버 대조군 {ctl.mean():.4f} "
          f"/ 서버 후보 {cand.mean():.4f}")
    print(f"질의 단위 — 후보 우세 {rep['per_query']['candidate_better']} / "
          f"동률 {rep['per_query']['tie']} / 현행 우세 {rep['per_query']['incumbent_better']}")
    print("->", p)


if __name__ == "__main__":
    main()
