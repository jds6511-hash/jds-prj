"""P2 영상별 질의 유형 쿼터 — 315질의를 35편에 결정적으로 배정한다.

근거: `docs/P2_승인1_규모확정_2026-08-20.md` §4 · 사전등록
`부호역전_확증_보충4_P2표집틀검증` §3. 선정 표본: `docs/P2_선정표본_2026-08-20.json`.

승인 ① §4-3이 고정한 절차 그대로다.

    1  모든 영상에 mixed 1 + subtitle 1 + scene 1                (3 × k)
    2  남은 quota(6 × k)의 유형 라벨 목록을 만든다
    3  seed 20260820으로 결정적 순열한다
    4  seed-order 영상에 앞에서부터 6개씩 배정한다

**승인 ①에 없던 세부 하나를 여기서 정한다** — `seed-order 영상`의 정의다.
같은 RNG를 두 곳에서 쓰면 순서가 결과를 바꾸므로 소비 순서까지 고정한다.

    RNG        random.Random(20260820) 하나
    소비 순서  ① 영상 순열  ② 유형 라벨 순열
    영상 초기 정렬  (program, source_id) 오름차순 — 선정 산출물과 같은 순서

**결과와 무관한 정적 규칙이다.** 캡션·검색 점수·제목을 보지 않는다.

`achieved_k`가 35보다 작아지면 **111/79/125의 뒤를 잘라 쓰지 않는다.** 새 총량
`9 × achieved_k`에 Hamilton을 처음부터 다시 적용하고 이 알고리즘도 처음부터
다시 돌린다(보충4 §3-1).
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEED = 20260820
QUERIES_PER_VIDEO = 9
TYPES = ("mixed", "subtitle", "scene")
# dev 96질의의 동결 분포 — 복합 34 · 자막 24 · 장면 38
DEV_COUNTS = {"mixed": 34, "subtitle": 24, "scene": 38}
# remainder 동률 시 사전 고정 순서 (보충4 §3-3)
TIE_ORDER = ("mixed", "scene", "subtitle")
BASE_PER_TYPE = 1
VIDEO_SORT = "(program, source_id) ascending"


def hamilton_types(total: int) -> dict:
    """largest remainder. **동률은 `TIE_ORDER`로만 푼다.**"""
    pool = sum(DEV_COUNTS.values())
    exact = {t: DEV_COUNTS[t] * total / pool for t in TYPES}
    q = {t: int(exact[t]) for t in TYPES}
    left = total - sum(q.values())
    order = sorted(TYPES, key=lambda t: (-(exact[t] - int(exact[t])),
                                         TIE_ORDER.index(t)))
    for t in order[:left]:
        q[t] += 1
    return q


def allocate(video_ids: list, seed: int = SEED,
             per_video: int = QUERIES_PER_VIDEO) -> dict:
    """영상별 유형 쿼터. 행 합은 `per_video`, 열 합은 global quota다."""
    k = len(video_ids)
    total = per_video * k
    glob = hamilton_types(total)
    base = {t: BASE_PER_TYPE * k for t in TYPES}
    rest = {t: glob[t] - base[t] for t in TYPES}
    if any(v < 0 for v in rest.values()):
        raise ValueError(f"기본 배정이 global quota를 넘는다: {glob} vs {base}")

    rng = random.Random(seed)
    order = list(video_ids)
    rng.shuffle(order)                      # ① 영상 순열
    pool = [t for t in TYPES for _ in range(rest[t])]
    rng.shuffle(pool)                       # ② 유형 라벨 순열

    extra_each = per_video - BASE_PER_TYPE * len(TYPES)
    if len(pool) != extra_each * k:
        raise ValueError(f"잔여 라벨 수가 맞지 않는다: {len(pool)} vs "
                         f"{extra_each * k}")
    quota = {v: {t: BASE_PER_TYPE for t in TYPES} for v in video_ids}
    for i, v in enumerate(order):
        for t in pool[i * extra_each:(i + 1) * extra_each]:
            quota[v][t] += 1
    return {
        "seed": seed, "per_video": per_video, "n_videos": k,
        "total_queries": total,
        "global_target_quota": glob,
        "dev_proportions": dict(DEV_COUNTS),
        "rounding": "largest_remainder_hamilton",
        "tie_order": list(TIE_ORDER),
        "video_sort_before_shuffle": VIDEO_SORT,
        "rng_consumption_order": ["video_permutation", "type_label_pool"],
        "base_per_type": BASE_PER_TYPE,
        "extra_per_video": extra_each,
        "seed_order": order,
        "per_video_quota": quota,
        "achieved_type_quota": {t: sum(q[t] for q in quota.values())
                                for t in TYPES},
        "deviation": {},
        "note": ("target과 achieved가 다르면 '달성'이라고 쓰지 않고 deviation으로 "
                 "보고한다. type_unavailable swap·종단 조항은 보충4 §3-3"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", default="docs/P2_선정표본_2026-08-20.json")
    ap.add_argument("--out", default="docs/P2_질의쿼터_2026-08-20.json")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    sel = json.loads(Path(ROOT / a.selected).read_text(encoding="utf-8"))
    vids = [r["source_id"] for r in sorted(
        sel["selected"], key=lambda r: (r["program"], r["source_id"]))]
    r = allocate(vids, seed=a.seed)
    r["selected_source"] = a.selected
    r["program_of"] = {x["source_id"]: x["program"] for x in sel["selected"]}
    Path(ROOT / a.out).write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"videos: {r['n_videos']}  total: {r['total_queries']}")
    print(f"global target: {r['global_target_quota']}")
    print(f"achieved: {r['achieved_type_quota']}")
    rows = sorted(set(sum(q.values()) for q in r["per_video_quota"].values()))
    print(f"row sums: {rows}")
    print(f"saved: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
