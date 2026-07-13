# 구조 개선 후보 실증: 유형별 α 라우팅 — 규칙 분류기의 실현 이득 측정 (dev 96, GPU 0)
# oracle(+, 완벽 분류 가정)과 단일 α 사이에서 현실 분류기가 얼마를 건지는지 계산.
# 기존 alpha_search_dev.json(z-score) per_query_rr 재분석 — 검색 재실행 없음.
# 한계: 규칙이 dev 표본 관찰 후 설계됨(과적합 위험) — 정식 채택 전 별도 검증 필요.
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

d = json.load(open("results/alpha_search_dev.json", encoding="utf-8"))
qs = [json.loads(l) for l in open("data/queries/queries_dev_only.jsonl", encoding="utf-8")]
pa = {e["alpha"]: e["per_query_rr"] for e in d["per_alpha"]}
alphas = sorted(pa)

# 유형별 α-MRR 곡선(z-score 기준) → 유형별 최적 α
from collections import defaultdict
curves = defaultdict(dict)
for a in alphas:
    by = defaultdict(list)
    for rr, q in zip(pa[a], qs):
        by[q["type"]].append(rr)
    for t, v in by.items():
        curves[t][a] = sum(v) / len(v)
opt = {t: max(c, key=c.get) for t, c in curves.items()}
print("유형별 최적 α (z-score):", opt)

SPEECH = re.compile(r"라고|라는 (자막|말|제안|설명)|자막|말하|이야기|소개하|부탁하|당부|설명하|묻는|대답|외치")
VISUAL_WITH = re.compile(r"함께.*(보이|뜨|나오)|보이는.*자막|자막.*(함께|위에)")

def classify(text: str) -> str:
    """발화 표지 없음→장면형, 발화+화면 결합 표지→복합형, 발화만→자막형."""
    if not SPEECH.search(text):
        return "장면형"
    if VISUAL_WITH.search(text) or ("함께" in text):
        return "복합형"
    return "자막형"

pred = [classify(q["text"]) for q in qs]
gold = [q["type"] for q in qs]
acc = sum(p == g for p, g in zip(pred, gold)) / len(gold)
conf = defaultdict(int)
for p, g in zip(pred, gold):
    conf[(g, p)] += 1
print(f"\n분류 정확도: {acc:.1%}")
print("혼동(정답→예측):", {f"{g}→{p}": n for (g, p), n in sorted(conf.items()) if g != p})

# 라우팅 mrr: 예측 유형의 최적 α 사용 vs 비교 기준들
routed = [pa[opt[p]][i] for i, p in enumerate(pred)]
oracle = [pa[opt[g]][i] for i, g in enumerate(gold)]
star = pa[0.5]; point = pa[0.4]
import numpy as np
rng = np.random.default_rng(42)
def ci(diff):
    diff = np.array(diff)
    bs = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
    return np.percentile(bs, [2.5, 97.5])
print(f"\n단일 α*=0.5      mrr={sum(star)/96:.4f}")
print(f"단일 점최적 α=0.4  mrr={sum(point)/96:.4f}")
lo, hi = ci([r - p for r, p in zip(routed, point)])
print(f"규칙 라우팅       mrr={sum(routed)/96:.4f}  Δvs점최적 CI[{lo:+.4f},{hi:+.4f}]")
print(f"oracle 라우팅     mrr={sum(oracle)/96:.4f}  (상한)")
