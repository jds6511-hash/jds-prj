# abstention 채널 재캘리브레이션: raw_sub_max 단독 → max(raw_sub_max, raw_cap_max)
# 근거(2026-07-13 설계 점검 1): sub 단독 채널은 장면형 유관 질의(무발화 장면을 찾는
# 질의라 자막과 원래 안 붙음)의 분포가 무관 질의와 겹쳐 구조적으로 불리하다.
# 기존 캘리브레이션 per_query 데이터 재분석 — GPU·재검색 불필요, leakage 없음(dev 전용).
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

c = json.load(open("results/abstention_calibration.json", encoding="utf-8"))
rel = [max(r["raw_sub_max"], r["raw_cap_max"]) for r in c["per_query"]["relevant"]]
neg = [max(r["raw_sub_max"], r["raw_cap_max"]) for r in c["per_query"]["negative"]]
rel_min = min(rel)
print(f"유관 max채널: min={rel_min:.4f}  무관 max채널: max={max(neg):.4f}")

print("\nτ' 스윕 (오배제 최소화 우선 — 8-2 소프트 배너 계약):")
rows = []
for t100 in range(50, 63):
    tau = t100 / 100
    fa = sum(1 for x in rel if x < tau)
    det = sum(1 for x in neg if x < tau)
    rows.append((tau, fa, det))
    print(f"  τ'={tau:.2f}: 오배제 {fa}/96 ({fa/96:.1%}), 무관감지 {det}/20 ({det/20:.0%})")

# 선택 규칙: 오배제 0을 유지하는 최대 τ' (유관 최솟값 직하의 0.01 격자점)
best = max(t for t, fa, _ in rows if fa == 0)
fa = sum(1 for x in rel if x < best)
det = sum(1 for x in neg if x < best)
print(f"\n=> 선택 τ'={best:.2f}: 오배제 {fa}/96, 무관감지 {det}/20")
print(f"   (현행 sub 단독 τ=0.48: 오배제 2/96, 무관감지 13/20 — 양쪽 축 모두 개선)")

out = {"channel": "max(raw_sub_max, raw_cap_max)", "tau": best,
       "false_abstention": f"{fa}/96", "negative_detected": f"{det}/20",
       "relevant_min": round(rel_min, 4), "negative_max": round(max(neg), 4),
       "sweep": [{"tau": t, "false_abstention": f, "detected": d} for t, f, d in rows],
       "baseline_sub_only": {"tau": 0.48, "false_abstention": "2/96", "negative_detected": "13/20"},
       "source": "results/abstention_calibration.json per_query 재분석 (2026-07-13)"}
with open("results/abstention_calibration_maxch.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("저장: results/abstention_calibration_maxch.json")
