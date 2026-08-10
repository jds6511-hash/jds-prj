"""[사람 맹검 키트 채점 — dev 전용, 답 보기 전 작성·커밋]

`frame_human_kit.py`가 만든 76문항의 응답을 사전 등록 규칙대로 채점한다.
규칙은 키트 생성 시점(2026-08-10)에 이미 커밋됐고 여기서 바꾸지 않는다.

**왜 사람에게 왔는가.** 판정 v2가 두 조건 모두 **판정 불가**로 끝났다. 관문을
통과한 판정자가 CLIP 하나뿐이었고(생성형 2개는 하드 네거티브에서 "모르겠으면 2번"
으로 쏠려 탈락), 사전 등록 규칙이 "통과 판정자 2개 미만이면 사람 확인으로 넘긴다"다.

**무엇을 가르는가.** dev 실패 52건이
  (가) 프레임에는 있는데 캡션이 안 썼다  → 캡션 모델·프롬프트가 병목
  (나) 프레임 자체에 없다              → M2 대표 프레임 선택·max_pixels가 병목
중 어느 쪽인지. 로컬 v1은 "혼재"(보정 A/C 0.634)로 끝났고 그 판정자는 캡션을 만든
3B라 순환성이 있었다.

**조건.**
  A  실패 질의 × (정답 프레임 vs 같은 영상 무작위)  52문항  ← 관심 조건
  C  성공 질의 × (정답 프레임 vs 같은 영상 무작위)  12문항  ← 양성 대조
  N  다른 영상 질의 × (이 영상 프레임 2장)         12문항  ← 하드 네거티브(정답 없음)

**사전 등록한 판정 규칙 (키트 생성 시 확정).**
  - **사람 관문**: C 정답률 ≥ 0.75 이고 N 쏠림 0.35~0.65. 못 넘기면 그 응답은 전량 제외.
  - **집계**: A 정답률을 C로 보정한 값(A/C)이 ≥ 0.6이면 (가), ≤ 0.4면 (나), 사이는 혼재.
  - `0`(둘 다 아님) 응답 비율 병기 필수.
  - 결과를 보고 임계값·조건을 바꾸지 않는다.

**미규정 구간의 해석 (답 보기 전 명시, 2026-08-10).** N 쏠림은 1·2 중 하나를 골라야
하는 모델 기준으로 등록됐는데 사람은 `0`을 쓸 수 있다. N을 전부 `0`으로 답하면 쏠림이
정의되지 않는다 — 이는 **위치 편향이 없다는 뜻이므로 통과**로 본다. 쏠림은 `0`이 아닌
응답에 대해서만 계산하고, 그런 응답이 4건 미만이면 판정에 쓰지 않는다(표본 부족).

**A에서 `0`은 결측이 아니다.** 실패 질의에서 "둘 다 아니다"는 **정답 프레임에 내용이
없다**는 뜻이므로 (나)의 증거다. 오답과 함께 "못 찾음"으로 집계한다.

work/·results/ 불변, test 미접촉. GPU 불필요.
재현: python docs/probes/frame_human_score.py [--kit <경로>]
"""
import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
KIT = OUT / "frame_human_kit_full"
GATE_C, NEG_LO, NEG_HI, MIN_NONZERO = 0.75, 0.35, 0.65, 4
AGG_HI, AGG_LO = 0.6, 0.4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", type=Path, default=KIT)
    a = ap.parse_args()

    keymap = json.loads((a.kit / "_keymap.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((a.kit / "answers_blind.csv")
                               .open(encoding="utf-8-sig")))

    ans, bad = {}, []
    for r in rows:
        v = (r.get("정답") or "").strip()
        if v not in ("0", "1", "2"):
            bad.append({"item_id": r["item_id"], "raw": v})
            continue
        ans[r["item_id"]] = int(v)

    missing = [k for k in keymap if k not in ans]
    cells = {c: {"correct": 0, "zero": 0, "n": 0, "picked_one": 0, "nonzero": 0}
             for c in "ACN"}
    for iid, meta in keymap.items():
        if iid not in ans:
            continue
        c = cells[meta["condition"]]
        v = ans[iid]
        c["n"] += 1
        if v == 0:
            c["zero"] += 1
        else:
            c["nonzero"] += 1
            c["picked_one"] += (v == 1)
        # 정답: A·C는 gt_position, N은 0
        if v == meta["gt_position"]:
            c["correct"] += 1

    def rate(c, k):
        return (c[k] / c["n"]) if c["n"] else None

    rep = {"note": "사람 맹검 채점. dev only, test 미접촉.",
           "kit": str(a.kit), "n_answered": len(ans),
           "n_unanswered": len(missing), "invalid_entries": bad,
           "prereg": {"gate": f"C 정답률 ≥{GATE_C}, N 쏠림 {NEG_LO}~{NEG_HI}",
                      "aggregate": f"A/C ≥{AGG_HI} (가) / ≤{AGG_LO} (나) / 사이 혼재",
                      "n_zero_note": "A의 0은 결측이 아니라 (나)의 증거",
                      "declared_before_answers": True}}

    for c in "ACN":
        d = cells[c]
        rep[c] = {"n": d["n"], "correct_rate": round(rate(d, "correct"), 4) if d["n"] else None,
                  "zero_rate": round(rate(d, "zero"), 4) if d["n"] else None,
                  "n_nonzero": d["nonzero"],
                  "one_share_among_nonzero": (round(d["picked_one"] / d["nonzero"], 4)
                                              if d["nonzero"] else None)}

    A, C, N = rep["A"], rep["C"], rep["N"]
    gate_c = C["correct_rate"] is not None and C["correct_rate"] >= GATE_C
    share = N["one_share_among_nonzero"]
    if N["n_nonzero"] < MIN_NONZERO:
        gate_n, gate_n_why = True, f"N 비영 응답 {N['n_nonzero']}건 — 위치 편향 없음으로 통과"
    else:
        gate_n = NEG_LO <= share <= NEG_HI
        gate_n_why = f"N 비영 응답 중 '1' 비율 {share}"
    rep["gate"] = {"C_passed": gate_c, "N_passed": gate_n, "N_note": gate_n_why,
                   "passed": bool(gate_c and gate_n)}

    if not rep["gate"]["passed"]:
        rep["verdict"] = ("관문 탈락 — 이 응답은 쓰지 않는다 "
                          f"(C {C['correct_rate']}, {gate_n_why})")
    else:
        ratio = A["correct_rate"] / C["correct_rate"] if C["correct_rate"] else None
        rep["corrected_ratio"] = round(ratio, 4) if ratio is not None else None
        if ratio is None:
            rep["verdict"] = "산출 불가 — C 정답률이 0이다"
        elif ratio >= AGG_HI:
            rep["verdict"] = ("(가) 프레임에는 있는데 캡션이 안 썼다 — "
                              "캡션 모델·프롬프트가 병목")
        elif ratio <= AGG_LO:
            rep["verdict"] = ("(나) 프레임 자체에 없다 — M2 대표 프레임 선택·max_pixels가 "
                              "병목. 캡션 모델 교체로는 해결되지 않는다")
        else:
            rep["verdict"] = "혼재 — 두 갈래를 모두 연다"

    # 참고: 모델 판정(v1)과의 대조. 판정이 아니라 기술 통계다.
    v1 = OUT / "frame_content_diagnosis.json"
    if v1.exists():
        d = json.loads(v1.read_text(encoding="utf-8"))
        rep["model_v1_reference"] = {
            "A_yes_rate": d.get("A_failed_gt", {}).get("yes_rate"),
            "C_yes_rate": d.get("C_success_gt", {}).get("yes_rate"),
            "A_over_C": d.get("contrasts", {}).get("A_over_C"),
            "verdict": d.get("verdict")}

    p = OUT / "frame_human_score.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"응답 {len(ans)}/{len(keymap)}건" + (f" · 미응답 {len(missing)}" if missing else "")
          + (f" · 형식오류 {len(bad)}" if bad else ""))
    for c in "ACN":
        r = rep[c]
        print(f"  {c}  n={r['n']:3d}  정답률 {r['correct_rate']}  "
              f"0응답 {r['zero_rate']}  비영중'1' {r['one_share_among_nonzero']}")
    print()
    print(f"관문: C {'통과' if gate_c else '탈락'} · N {'통과' if gate_n else '탈락'} "
          f"({gate_n_why})")
    if rep["gate"]["passed"]:
        print(f"보정 A/C = {rep.get('corrected_ratio')}")
    print("판정:", rep["verdict"])
    print("->", p)


if __name__ == "__main__":
    main()
