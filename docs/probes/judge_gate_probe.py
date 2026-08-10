"""[M9 판정자 계측기 검정 — dev 전용, 채택 아님, 결과 전 커밋]

**왜 지금 하는가.** M9의 판정자는 리포트를 만든 모델과 **같은 모델**이다
(`judge_model == report_model`, `same_model_judge: true`). config 주석에 "다른 패밀리
1순위는 **서버 GPU 확정 대기**"라 적혀 있는데 서버는 2026-08-06에 확보됐으므로
그 잠정 조치는 이미 낡았다. 그런데 더 근본적인 문제는 **이 판정자가 판정을 할 수
있는지 자체가 한 번도 검정된 적이 없다는 것**이다.

이건 리포트 모델 비교를 하려고 필요한 게 아니다. **M9는 이미 test에서 두 번 돌았다.**
판정자가 grounded와 ungrounded를 못 가르면 그 두 번의 수치도 못 쓴다. 비교를
하든 안 하든 알아야 하는 사실이고, 새 생성이 전혀 필요 없다(8/6 리포트 396문장과
segments가 이미 있다).

같은 실수를 프레임 판정에서 이미 겪었다 — 생성형 판정자 2개가 하드 네거티브에서
"모르겠으면 2번"으로 쏠려 게이트 탈락했다. 양성 대조만 봤으면 0.977로 멀쩡해 보였다.

**설계 — 답을 아는 문항을 합성한다.** 새 생성 없이 기존 산출물만 재배열한다.

  groundedness
    양성  세그먼트 캡션을 **그대로** 문장으로 쓰고 그 세그먼트를 cite
          → 정의상 grounded. 이걸 못 맞히면 판정자가 망가진 것이다.
    음성  같은 문장에 **다른 영상의** 세그먼트를 cite
          → 정의상 ungrounded. 같은 영상 안에서 고르면 우연히 맞을 수 있어 쓰지 않는다.

  coverage
    양성  리포트에 실제로 인용된 세그먼트(`cites`에 등장) → covered여야 한다
    음성  **다른 영상의** 세그먼트 → covered가 아니어야 한다

**M9의 실제 프롬프트·파서를 그대로 쓴다**(`_grounded_prompt`, `judge_coverage`,
`_parse_verdict`). 검정용으로 따로 짜면 그 구현의 성능을 재게 되어 의미가 없다.

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-10).**
  - 두 과제 각각 **양성 정답률 ≥ 0.75 이고 음성 정답률 ≥ 0.75** 여야 통과.
  - 한쪽만 높은 것은 통과가 아니다. 양성만 높으면 "예"를 남발하는 것이고,
    음성만 높으면 "아니오"를 남발하는 것이다. **쏠림 지표(yes_rate)를 병기한다.**
  - 못 넘기면 그 과제의 M9 수치는 **해석 불가**로 보고한다. test에서 이미 산출된
    수치에도 이 한계를 명시한다(재평가와 무관하게 문서 정정 사항).
  - 결과를 보고 임계값을 바꾸지 않는다.

**한계.** 양성 대조가 "캡션 그대로 복사"라 쉬운 문항이다. 통과해도 **어려운 판정을
잘한다는 뜻은 아니고**, 실패하면 확실히 못 쓴다는 뜻이다. 즉 이 게이트는
**하한 검정**이다. 통과 시 그 사실을 결과에 적는다.

work/·results/ 불변, test 미접촉, 새 생성 없음.
재현: python docs/probes/judge_gate_probe.py [--n 60]
"""
import argparse
import io
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402
import m9_report_eval as m9                                # noqa: E402
from llm import make_llm                                   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
SEED = 42
GATE = 0.75


def load_dev(cfg):
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    vids = sorted({q["video_id"] for q in qs if q["split"] == "dev"})
    out = {}
    for v in vids:
        wdir = Path(common.work_dir(cfg, v))
        rp = wdir / "report.json"
        if not rp.exists():
            print(f"  [건너뜀] {v}: report.json 없음", flush=True)
            continue
        doc = common.load_segments(wdir / "segments.json",
                                   require=["subtitle", "caption"],
                                   seg_len=cfg["seg_len_sec"])
        out[v] = {"report": json.loads(rp.read_text(encoding="utf-8")),
                  "segs": doc["segments"]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="조건당 문항 수")
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    data = load_dev(cfg)
    if len(data) < 2:
        raise ValueError(f"영상이 {len(data)}편 — 다른 영상 음성 대조를 만들 수 없다")
    vids = sorted(data)
    rng = random.Random(SEED)

    judge = make_llm(cfg["judge_model"], max_new_tokens=512,
                     load_4bit=cfg.get("llm_4bit", False))

    rep = {"note": "M9 판정자 계측기 검정. dev only, 새 생성 없음, test 미접촉.",
           "judge_model": cfg["judge_model"],
           "same_model_judge": cfg.get("same_model_judge"),
           "report_model": cfg.get("report_model"),
           "prereg": {"gate": f"양성·음성 정답률 모두 ≥ {GATE}",
                      "negative_source": "다른 영상의 세그먼트",
                      "note": "양성이 캡션 복사라 쉬운 문항 — 하한 검정이다",
                      "declared_before_run": True},
           "seed": SEED, "n_per_cell": a.n}

    def other_seg(v):
        ov = rng.choice([x for x in vids if x != v])
        return rng.choice(data[ov]["segs"])

    # ── groundedness ──────────────────────────────────────────────────────
    pool = [(v, s) for v in vids for s in data[v]["segs"]
            if s["caption"] and not common.is_corrupted_caption(s["caption"])]
    rng.shuffle(pool)
    items = pool[:a.n]
    g_pos, g_neg = [], []
    for i, (v, s) in enumerate(items):
        sent = {"sent_id": f"gate{i}", "text": s["caption"], "cites": [s["idx"]]}
        g_pos.append(m9.judge_grounded(sent, [s], judge))          # 정답: True
        g_neg.append(m9.judge_grounded(sent, [other_seg(v)], judge))  # 정답: False
        if i % 20 == 0:
            print(f"  groundedness {i}/{len(items)}", flush=True)

    # ── coverage ──────────────────────────────────────────────────────────
    c_pos, c_neg = [], []
    per_v = max(1, a.n // len(vids))
    ci = 0
    for v in vids:
        rtext = "\n".join(s["text"] for s in data[v]["report"]["sentences"])
        cited = sorted({c for s in data[v]["report"]["sentences"] for c in s["cites"]})
        by_idx = {s["idx"]: s for s in data[v]["segs"]}
        picks = rng.sample(cited, min(per_v, len(cited)))
        for idx in picks:
            c_pos.append(m9.judge_coverage(rtext, by_idx[idx], judge)[0])   # 정답: True
            c_neg.append(m9.judge_coverage(rtext, other_seg(v), judge)[0])  # 정답: False
            ci += 1
            if ci % 10 == 0:
                print(f"  coverage {ci}", flush=True)

    def cell(name, pos, neg):
        pr = sum(pos) / len(pos)
        nr = 1 - sum(neg) / len(neg)                 # 음성 정답 = "아니다"라고 답한 비율
        yes = (sum(pos) + sum(neg)) / (len(pos) + len(neg))
        ok = pr >= GATE and nr >= GATE
        rep[name] = {"n": len(pos), "positive_correct": round(pr, 4),
                     "negative_correct": round(nr, 4), "yes_rate": round(yes, 4),
                     "passed": ok}
        print(f"[{name}] 양성 {pr:.3f} · 음성 {nr:.3f} · 예비율 {yes:.3f} "
              f"→ {'통과' if ok else '탈락'}")
        return ok

    print()
    ok_g = cell("groundedness", g_pos, g_neg)
    ok_c = cell("coverage", c_pos, c_neg)

    if ok_g and ok_c:
        rep["verdict"] = ("통과(하한) — 두 과제 모두 답을 아는 문항을 가른다. "
                          "다만 양성이 캡션 복사라 어려운 판정까지 보장하지 않는다")
    else:
        bad = [n for n, o in (("groundedness", ok_g), ("coverage", ok_c)) if not o]
        rep["verdict"] = (f"탈락 — {', '.join(bad)}는 답을 아는 문항도 못 가른다. "
                          "해당 지표는 해석 불가이며 test에서 산출된 기존 수치에도 "
                          "이 한계를 명시해야 한다")

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "judge_gate.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print("판정:", rep["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
