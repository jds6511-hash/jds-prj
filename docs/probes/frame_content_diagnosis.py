"""[실패 질의의 정답 프레임에 내용이 있는가 — dev 전용, 채택 아님, 결과 전 커밋]

**왜 필요한가 — 투자할 곳을 정한다.** dev 실패 52건 중 88%가 "정답 세그먼트의
캡션에 질의 내용이 없다"였다. 그런데 원인이 둘로 갈린다:

  (가) 프레임에는 있는데 **캡션이 안 썼다** → 모델·프롬프트 문제(지금 하는 실험이 맞다)
  (나) **프레임 자체에 없다** → M2 대표 프레임 선택·해상도 문제(모델을 바꿔도 소용없다)

이걸 안 가르면 캡션 모델에 계속 GPU를 쓰면서 정작 병목은 M2일 수 있다.

**설계 — VLM에게 프레임을 주고 예/아니오로 묻는다.** 그런데 그냥 물으면 못 쓴다:
모델이 "예"를 남발하면 전부 (가)로 보이고, "아니오"를 남발하면 전부 (나)로 보인다.
**대조군 두 개를 반드시 같이 잰다.**

  A  실패 질의 × **정답 프레임**      ← 관심 조건
  B  실패 질의 × **같은 영상의 무작위 비정답 프레임**  ← 음성 대조군
  C  성공 질의 × 정답 프레임          ← 양성 대조군
  D  성공 질의 × 무작위 비정답 프레임  ← 음성 대조군

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-09).**
  - **먼저 계측기부터 본다.** C − D 가 **0.3 이상** 벌어지지 않으면 이 진단은
    프레임 내용을 구분하지 못하는 것이므로 **"판정 불가"로 보고하고 끝낸다.**
    (모델이 질문에 예/아니오를 아무렇게나 답하는 상태)
  - 계측기가 통과했을 때만 A를 읽는다:
    * **A − B ≥ 0.3** 이고 A가 C의 70% 이상 → **(가) 프레임에는 있다.**
      캡션 모델·프롬프트가 병목. 지금 실험 방향이 맞다.
    * **A − B < 0.3** → **(나) 프레임에 없다.** M2 프레임 선택·max_pixels로
      우선순위를 옮긴다.
    * 그 사이면 "혼재"로 보고하고 두 갈래 모두 열어 둔다.
  - 결과를 보고 임계값이나 조건을 바꾸지 않는다.

**한계.** 판정에 쓰는 VLM이 로컬 6GB 제약으로 현행 3B-4bit다. 더 큰 모델이면
"보인다"가 늘 수 있다. 즉 **(가)를 과소평가하는 방향의 편향**이고, 그래서 (나)로
판정될 때는 그 편향을 병기해야 한다. 반대로 (가)로 나오면 보수적으로 안전하다.

work/·results/ 불변, test 미접촉.
재현: python docs/probes/frame_content_diagnosis.py
"""
import io, json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs/probes"))
import common                                              # noqa: E402
from m5_search import VideoIndex                           # noqa: E402
from m6_evaluate import evaluate                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
SEED = 42
ASK = ('다음 설명이 이 사진의 내용과 맞습니까?\n"{q}"\n'
       '"예" 또는 "아니오" 한 단어로만 답하시오.')


def yes(ans: str) -> bool:
    """앞부분만 본다 — 모델이 뒤에 사족을 붙여도 판정이 흔들리지 않게."""
    a = (ans or "").strip().replace(" ", "")[:6]
    if a.startswith("아니") or a.startswith("아뇨") or a.lower().startswith("no"):
        return False
    return a.startswith("예") or a.startswith("네") or a.lower().startswith("yes")


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}

    # 실패/성공 = 현행 캡션 단독(α=0.0)에서 1위를 못 잡았는가. 경합 부분집합과 같은 정의.
    per_q = evaluate(dev, base, 0.0, cfg)["per_query"]
    rank1 = {r["query_id"]: (r["rank"] == 1) for r in per_q}
    failed = [q for q in dev if not rank1[q["query_id"]]]
    succ = [q for q in dev if rank1[q["query_id"]]]
    print(f"실패 {len(failed)} / 성공 {len(succ)} (dev {len(dev)})", flush=True)

    rng = np.random.default_rng(SEED)

    def frames_for(q):
        """(정답 프레임, 같은 영상의 무작위 비정답 프레임)"""
        v = q["video_id"]
        segs = base[v].segments
        gt = set(q["gt_seg_idx"])
        gi = q["gt_seg_idx"][0]
        pool = [i for i in range(len(segs)) if i not in gt]
        ri = int(rng.choice(pool))
        return (wdirs[v] / segs[gi]["rep_frame"], wdirs[v] / segs[ri]["rep_frame"], ri)

    from caption_model_sweep import MODELS, load_captioner   # noqa: E402
    # 판정 모델: 로컬 제약으로 현행 3B-4bit. 한계는 docstring 참조.
    cap, close = load_captioner(MODELS["qwen25_3b_4bit"], cfg, max_new=8)

    rep = {"note": "dev-only, 채택 아님. 투자처 판정용. test 미접촉.",
           "judge_model": MODELS["qwen25_3b_4bit"]["id"],
           "prereg": {
               "instrument_gate": "C-D >= 0.3 아니면 판정 불가로 끝낸다",
               "rule": ("A-B >= 0.3 이고 A >= 0.7*C 이면 (가) 프레임에 있다 → 캡션 모델·프롬프트. "
                        "A-B < 0.3 이면 (나) 프레임에 없다 → M2·해상도. 그 사이는 혼재."),
               "bias_note": "판정 모델이 작아 (가)를 과소평가하는 방향",
               "declared_before_run": True},
           "seed": SEED, "n_failed": len(failed), "n_success": len(succ)}

    try:
        cells = {}
        for name, qlist, use_gt in (("A_failed_gt", failed, True),
                                    ("B_failed_random", failed, False),
                                    ("C_success_gt", succ, True),
                                    ("D_success_random", succ, False)):
            hits, detail = [], []
            for i, q in enumerate(qlist):
                gt_f, rd_f, ri = frames_for(q)
                f = gt_f if use_gt else rd_f
                ans = cap(f, ASK.format(q=q["text"]))
                hits.append(yes(ans))
                detail.append({"query_id": q["query_id"], "yes": yes(ans),
                               "raw": (ans or "")[:20]})
                if i % 20 == 0:
                    print(f"  {name} {i}/{len(qlist)}", flush=True)
            cells[name] = float(np.mean(hits))
            rep[name] = {"yes_rate": round(cells[name], 4), "n": len(qlist),
                         "detail": detail}
            print(f"[{name}] 예 비율 {cells[name]:.3f} (n={len(qlist)})", flush=True)
    finally:
        close()

    A, B, C, D = cells["A_failed_gt"], cells["B_failed_random"], \
        cells["C_success_gt"], cells["D_success_random"]
    rep["contrasts"] = {"A_minus_B": round(A - B, 4), "C_minus_D": round(C - D, 4),
                        "A_over_C": round(A / C, 4) if C > 0 else None}

    if (C - D) < 0.3:
        rep["verdict"] = ("판정 불가 — 이 진단이 프레임 내용을 구분하지 못한다 "
                          f"(양성 대조 C-D={C-D:.3f} < 0.3)")
    elif (A - B) >= 0.3 and C > 0 and A >= 0.7 * C:
        rep["verdict"] = ("(가) 프레임에는 있는데 캡션이 안 썼다 — "
                          "캡션 모델·프롬프트가 병목. 현재 실험 방향이 맞다")
    elif (A - B) < 0.3:
        rep["verdict"] = ("(나) 프레임 자체에 없다 — M2 대표 프레임 선택·max_pixels로 "
                          "우선순위를 옮긴다. 모델 교체로는 해결되지 않는다")
    else:
        rep["verdict"] = "혼재 — 두 갈래를 모두 연다"

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "frame_content_diagnosis.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"A(실패×정답) {A:.3f} | B(실패×무작위) {B:.3f} | "
          f"C(성공×정답) {C:.3f} | D(성공×무작위) {D:.3f}")
    print(f"A-B {A-B:+.3f} · C-D {C-D:+.3f}")
    print("판정:", rep["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
