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

**2차 — 판정자 후보 비교 (2026-08-10 22:50, 1차 결과 본 뒤 추가).** 1차에서 현행
판정자가 coverage 양성 0.550으로 탈락했다. 그 탈락이 **판정자 탓인지 과제 탓인지**
가르지 않으면 "판정자를 바꾸면 된다"와 "지표를 내려야 한다" 중 어느 쪽인지 모른다.
용량 축(같은 패밀리 14B)과 패밀리 축(kanana 8B)을 같은 문항으로 돌린다.

  - 통과하는 판정자가 있으면 → 판정자 문제. 교체로 지표를 살린다
  - 셋 다 탈락하면 → **과제 자체가 판정 불가**. coverage를 공식 지표에서 내린다

임계값(0.75)·문항 수·문항 자체는 1차와 같다. **1차 결과를 보고 바꾼 것은 후보
목록뿐이고 판정 규칙은 그대로다.**

work/·results/ 불변, test 미접촉, 새 생성 없음.
재현: python docs/probes/judge_gate_probe.py [--n 60] [--judges all]
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

# 2차 — 판정자 후보군. 1차에서 현행(Qwen2.5-7B, 리포트와 같은 모델)이 coverage
# 양성 0.550으로 탈락했다. **탈락이 판정자 탓인지 지표 탓인지 가른다.**
#   용량 축   같은 패밀리 더 큰 모델이 통과하면 7B의 용량 문제다
#   패밀리 축 다른 패밀리가 통과하면 자기평가·패밀리 문제다
#   둘 다 탈락하면 **coverage 과제 자체가 판정 불가**이고 지표를 내려야 한다
# 4bit는 24GB에 안 들어가는 모델에만 쓰고 arm마다 기록한다(양자화 교란 명시).
JUDGES = {
    "Qwen/Qwen2.5-7B-Instruct":  {"q4": False, "axis": "현행(대조군)"},
    "Qwen/Qwen2.5-14B-Instruct": {"q4": True,  "axis": "용량(같은 패밀리)"},
    "kakaocorp/kanana-1.5-8b-instruct-2505": {"q4": False, "axis": "패밀리(한국어 특화)"},
}


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


def run_gate(judge, data, vids, n, rep):
    """판정자 하나로 두 과제의 게이트를 돌린다. rep에 셀 결과를 채우고 통과 여부 반환.

    **rng를 판정자마다 새로 만든다** — 같은 문항을 줘야 판정자끼리 비교가 된다.
    """
    rng = random.Random(SEED)

    def other_seg(v):
        ov = rng.choice([x for x in vids if x != v])
        return rng.choice(data[ov]["segs"])

    # ── groundedness ──────────────────────────────────────────────────────
    pool = [(v, s) for v in vids for s in data[v]["segs"]
            if s["caption"] and not common.is_corrupted_caption(s["caption"])]
    rng.shuffle(pool)
    items = pool[:n]
    g_pos, g_neg = [], []
    for i, (v, s) in enumerate(items):
        sent = {"sent_id": f"gate{i}", "text": s["caption"], "cites": [s["idx"]]}
        g_pos.append(m9.judge_grounded(sent, [s], judge))          # 정답: True
        g_neg.append(m9.judge_grounded(sent, [other_seg(v)], judge))  # 정답: False
        if i % 20 == 0:
            print(f"  groundedness {i}/{len(items)}", flush=True)

    # ── coverage ──────────────────────────────────────────────────────────
    c_pos, c_neg = [], []
    per_v = max(1, n // len(vids))
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
                     "passed": ok,
                     # 원자료 보존(규약 5항) — 나중에 다른 각도로 볼 때 재실행 불필요
                     "raw": {"positive": [bool(x) for x in pos],
                             "negative": [bool(x) for x in neg]}}
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
        bad = [t for t, o in (("groundedness", ok_g), ("coverage", ok_c)) if not o]
        rep["verdict"] = (f"탈락 — {', '.join(bad)}는 답을 아는 문항도 못 가른다. "
                          "해당 지표는 해석 불가이며 test에서 산출된 기존 수치에도 "
                          "이 한계를 명시해야 한다")
    return ok_g, ok_c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="조건당 문항 수")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--judges", default="",
                    help="판정자 후보 비교(쉼표 구분 또는 'all'). 비우면 config 판정자 1개")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    data = load_dev(cfg)
    if len(data) < 2:
        raise ValueError(f"영상이 {len(data)}편 — 다른 영상 음성 대조를 만들 수 없다")
    vids = sorted(data)

    multi = bool(a.judges)
    if not multi:
        mids = [cfg["judge_model"]]
    elif a.judges == "all":
        mids = list(JUDGES)
    else:
        mids = [m.strip() for m in a.judges.split(",") if m.strip()]

    prereg = {"gate": f"양성·음성 정답률 모두 ≥ {GATE}",
              "negative_source": "다른 영상의 세그먼트",
              "note": "양성이 캡션 복사라 쉬운 문항 — 하한 검정이다",
              "declared_before_run": True}
    if multi:
        prereg["why_multi"] = (
            "1차에서 현행 판정자가 coverage 양성 0.550으로 탈락했다. 용량 축(같은 "
            "패밀리 14B)과 패밀리 축(kanana 8B)을 둘 다 통과 못 하면 coverage는 "
            "판정자가 아니라 **과제 자체가 판정 불가**라는 뜻이다")
        prereg["same_items"] = "판정자마다 rng를 SEED로 새로 만들어 동일 문항을 준다"
        prereg["quant_note"] = "24GB에 안 들어가는 모델만 4bit — arm마다 기록"

    top = {"note": "M9 판정자 계측기 검정. dev only, 새 생성 없음, test 미접촉.",
           "report_model": cfg.get("report_model"),
           "incumbent_judge": cfg["judge_model"],
           "prereg": prereg, "seed": SEED, "n_per_cell": a.n, "judges": {}}

    # 판정자마다 프로세스를 나눠 돌린 결과를 누적한다. `make_llm`이 모델을 캐시에
    # 물고 안 놓기 때문에 한 프로세스에서 둘 이상 올리면 뒤가 VRAM 부족으로 죽는다
    # (2026-08-11 실측 — 7B가 남아 있어 14B 4bit가 CPU로 밀렸다).
    p_out = OUT / ("judge_gate_models.json" if multi else "judge_gate.json")
    if multi and p_out.exists():
        top["judges"] = json.loads(p_out.read_text(encoding="utf-8")).get("judges", {})

    for mid in mids:
        spec = JUDGES.get(mid, {"q4": cfg.get("llm_4bit", False), "axis": "config"})
        print(f"\n=== {mid} ({spec['axis']}, {'4bit' if spec['q4'] else 'bf16'}) ===",
              flush=True)
        rep = {"judge_model": mid, "axis": spec["axis"], "load_4bit": spec["q4"],
               "same_model_judge": mid == cfg.get("report_model")}
        try:
            judge = make_llm(mid, max_new_tokens=512, load_4bit=spec["q4"])
            run_gate(judge, data, vids, a.n, rep)
        except Exception as e:
            rep["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            rep["verdict"] = "실행 실패 — 판정 없음"
            print(f"  실패 — {type(e).__name__}: {str(e)[:160]}", flush=True)
        top["judges"][mid] = rep
        OUT.mkdir(parents=True, exist_ok=True)
        p_out.write_text(
            json.dumps(top if multi else {**top, **rep}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    if multi:
        okc = [m for m, r in top["judges"].items() if r.get("coverage", {}).get("passed")]
        top["verdict"] = (
            f"coverage 통과 판정자: {okc} — 판정자 교체로 지표를 살릴 수 있다"
            if okc else
            "coverage를 통과한 판정자가 없다 — 판정자가 아니라 **과제 자체가 판정 "
            "불가**다. M9 coverage는 공식 지표에서 내리고 test 기존 수치에도 한계를 명시")
        (OUT / "judge_gate_models.json").write_text(
            json.dumps(top, ensure_ascii=False, indent=2), encoding="utf-8")
        print()
        print("판정:", top["verdict"])


if __name__ == "__main__":
    main()
