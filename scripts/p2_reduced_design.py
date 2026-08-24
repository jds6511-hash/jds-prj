"""P2 축소 설계 — **어떤 기존 질의를 남길지 결정론적으로 고른다.**

이 모듈은 설계를 고르지 않는다. 140 / 175 / 315 중 선택은 사용자 승인 사항이고,
여기서는 각 설계의 keep-mask를 만들고 제약을 재검증할 뿐이다.

```
입력       동결 배정표(query_id · video_id · query_type)와 seed뿐이다
금지 입력   text · gt_start · gt_end · note · 작성 완료 여부 · 사람이 느낀 난이도 ·
           모델 산출물 일체
불변       35 video cluster 유지 · 새 질의 생성 없음 · query_id 재번호 없음
제약       영상당 정확히 m행 · 모든 영상에 세 유형 >= 1 · global quota 정확히 일치
```

**노동량을 줄이는 축은 cluster 수가 아니라 cluster당 질의 수다.** 영상은 35편
그대로 두고 영상당 9 → 5 → 4로만 줄인다.

Hamilton 기준은 배정표가 선언한 `dev_proportions`(34:24:38)다. achieved 315
(111/79/125)를 기준으로 다시 계산하면 140이 49/35/56으로 갈리므로 기준을 고정한다.

extra 배정은 greedy가 아니라 **제약 흐름**으로 푼다. 어떤 영상이 특정 유형을 1건만
가지고 있으면 그 유형의 extra를 그 영상에 놓을 수 없어서, 순서대로 채우는 방식은
막판에 quota를 못 맞추고 조용히 어긋난다. 흐름이 포화되지 않으면 fail-closed다.
"""
import argparse
import hashlib
import json
import sys
from math import floor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_label_intake as INTAKE                                  # noqa: E402

QUOTA = ROOT / "docs" / "P2_질의쿼터_2026-08-20.json"
SEED = 20260820
N_VIDEOS = 35
DESIGNS = {140: 4, 175: 5, 315: 9}
DESIGNS_FULL = 315
TYPES = ("복합형", "자막형", "장면형")
SELECTION_INPUTS = ("query_id", "video_id", "query_type",
                    "frozen_allocation_order", "seed")
FORBIDDEN_INPUTS = ("text", "gt_start", "gt_end", "note", "caption", "subtitle",
                    "rank", "score", "written_already", "perceived_difficulty",
                    "retrieval_result", "index", "embedding")


class DesignError(Exception):
    pass


def _quota_doc() -> dict:
    return json.loads(QUOTA.read_text(encoding="utf-8"))


def base_proportions() -> dict:
    """Hamilton 기준 비율. 배정표가 선언한 dev 유형 분포다."""
    q = _quota_doc()
    ko = INTAKE.TYPE_KO
    return {ko[k]: v for k, v in q["dev_proportions"].items()}


def _tie_order() -> list:
    return [INTAKE.TYPE_KO[k] for k in _quota_doc()["tie_order"]]


def hamilton(total: int, base: dict, tie_order: list) -> dict:
    """largest remainder. 동률은 배정표가 선언한 tie_order로 깬다."""
    s = sum(base.values())
    exact = {k: base[k] * total / s for k in base}
    out = {k: floor(v) for k, v in exact.items()}
    rem = total - sum(out.values())
    order = sorted(base, key=lambda k: (-(exact[k] - floor(exact[k])),
                                        tie_order.index(k)))
    for k in order[:rem]:
        out[k] += 1
    return out


def quota_for(total: int) -> dict:
    return hamilton(total, base_proportions(), _tie_order())


def type_totals(allocation: list) -> dict:
    out = {t: 0 for t in TYPES}
    for r in allocation:
        out[r["query_type"]] += 1
    return out


def expected_quota(total: int, allocation: list) -> dict:
    """축소 설계는 Hamilton, 현행 설계는 배정표의 achieved 값이다.

    현행 315를 Hamilton으로 다시 계산해 대조하면 배정표를 재배정하는 셈이 된다.
    실 배정표에서는 둘이 같지만(111/79/125), 같다는 것을 근거로 삼지 않는다.
    """
    return type_totals(allocation) if total == DESIGNS_FULL else quota_for(total)


def frozen_allocation() -> list:
    """동결 배정표 315행. 사람 입력 칸을 읽지 않는다."""
    return INTAKE.load_allocation()


# ------------------------------------------------------------- 결정론적 순서

def _order_key(seed: int, key: str) -> str:
    return hashlib.blake2b(f"{seed}|{key}".encode("utf-8"),
                           digest_size=8).hexdigest()


# ------------------------------------------------------------- 제약 흐름

def _maxflow(cap: list, s: int, t: int) -> tuple:
    """Edmonds-Karp. 노드 순서를 고정해 두었으므로 결과가 결정론적이다."""
    n = len(cap)
    flow = [[0] * n for _ in range(n)]
    total = 0
    while True:
        prev = [-1] * n
        prev[s] = s
        queue = [s]
        while queue:
            u = queue.pop(0)
            for v in range(n):
                if prev[v] == -1 and cap[u][v] - flow[u][v] > 0:
                    prev[v] = u
                    queue.append(v)
        if prev[t] == -1:
            break
        path, v = [], t
        while v != s:
            path.append((prev[v], v))
            v = prev[v]
        add = min(cap[u][v] - flow[u][v] for u, v in path)
        for u, v in path:
            flow[u][v] += add
            flow[v][u] -= add
        total += add
    return total, flow


def _assign_extras(counts: dict, extra_quota: dict, need: int, seed: int) -> dict:
    """영상별 extra 배정. 포화되지 않으면 조용히 넘기지 않고 실패한다."""
    if need == 0:
        return {vid: {t: 0 for t in TYPES} for vid in counts}
    vids = sorted(counts, key=lambda v: (_order_key(seed, v), v))
    k = len(vids)
    n = k + len(TYPES) + 2
    src, snk = 0, n - 1
    cap = [[0] * n for _ in range(n)]
    for i, vid in enumerate(vids, start=1):
        cap[src][i] = need
        for j, t in enumerate(TYPES):
            cap[i][k + 1 + j] = max(0, counts[vid][t] - 1)
    for j, t in enumerate(TYPES):
        cap[k + 1 + j][snk] = extra_quota[t]
    got, flow = _maxflow(cap, src, snk)
    want = need * k
    if got != want:
        short = {t: extra_quota[t] - sum(flow[i][k + 1 + j]
                                         for i in range(1, k + 1))
                 for j, t in enumerate(TYPES)}
        raise DesignError(f"extra {want}건 중 {got}건만 배치됐다 — 제약을 "
                          f"만족하는 배정을 배치할 수 없다. 유형별 잔여 {short}")
    return {vid: {t: flow[i][k + 1 + j] for j, t in enumerate(TYPES)}
            for i, vid in enumerate(vids, start=1)}


# ------------------------------------------------------------- keep-mask

def _counts(allocation: list) -> dict:
    out = {}
    for r in allocation:
        out.setdefault(r["video_id"], {t: 0 for t in TYPES})
        if r["query_type"] not in TYPES:
            raise DesignError(f"{r['query_id']}: 미허용 유형 {r['query_type']!r}")
        out[r["video_id"]][r["query_type"]] += 1
    return out


def keep_mask(total: int, allocation: list = None, seed: int = SEED) -> dict:
    """어떤 query_id를 남길지 결정론적으로 고른다. 새 질의를 만들지 않는다."""
    if total not in DESIGNS:
        raise DesignError(f"설계 후보가 아니다: {total} — {sorted(DESIGNS)}")
    m = DESIGNS[total]
    allocation = allocation if allocation is not None else frozen_allocation()
    counts = _counts(allocation)
    if len(counts) != N_VIDEOS:
        raise DesignError(f"영상 수 {len(counts)} != {N_VIDEOS} — cluster를 "
                          "줄이는 설계가 아니다")
    for vid in sorted(counts):
        rows = sum(counts[vid].values())
        if rows != DESIGNS[DESIGNS_FULL]:
            raise DesignError(f"{vid}: 배정 {rows}행 != "
                              f"{DESIGNS[DESIGNS_FULL]}행")
        missing = [t for t in TYPES if counts[vid][t] < 1]
        if missing:
            raise DesignError(f"{vid}: 배정에 {missing}이 없다 — 모든 영상에 "
                              "세 유형이 있어야 축소가 가능하다")
    quota = expected_quota(total, allocation)
    extra_quota = {t: quota[t] - N_VIDEOS for t in TYPES}
    bad = {t: v for t, v in extra_quota.items() if v < 0}
    if bad:
        raise DesignError(f"유형별 quota가 영상 수보다 적다 {bad} — 영상마다 "
                          "최소 1건을 둘 수 없다")
    if total == DESIGNS_FULL:
        # 현행 설계는 축소가 아니다 — 배정표 그대로이므로 mask는 항등이고
        # quota도 Hamilton 재계산 대상이 아니라 배정표의 achieved 값이다.
        extras = {vid: {t: counts[vid][t] - 1 for t in TYPES} for vid in counts}
    else:
        extras = _assign_extras(counts, extra_quota, m - 3, seed)

    by_video, kept = {}, []
    for vid in sorted(counts):
        by_video[vid] = {}
        for t in TYPES:
            take = 1 + extras[vid][t]
            cands = sorted((r["query_id"] for r in allocation
                            if r["video_id"] == vid and r["query_type"] == t),
                           key=lambda q: (_order_key(seed, q), q))
            if take > len(cands):
                raise DesignError(f"{vid}/{t}: {take}건이 필요한데 배정은 "
                                  f"{len(cands)}건이다")
            by_video[vid][t] = take
            kept.extend(cands[:take])
    kept_set = set(kept)
    order = [r["query_id"] for r in
             sorted(allocation, key=lambda r: (r["video_id"], r["query_id"]))]
    return {"design": f"p2_{total}", "total": total, "queries_per_video": m,
            "seed": seed, "n_videos": len(counts), "quota": quota,
            "extra_quota": extra_quota,
            "kept_query_ids": [q for q in order if q in kept_set],
            "dropped_query_ids": [q for q in order if q not in kept_set],
            "by_video": by_video,
            "selection_inputs": list(SELECTION_INPUTS),
            "forbidden_inputs": list(FORBIDDEN_INPUTS),
            "decision": "사용자_승인_사항"}


def verify_mask(mask: dict, allocation: list = None) -> dict:
    """mask를 다시 검산한다. 만든 코드와 같은 경로를 쓰지 않는다."""
    allocation = allocation if allocation is not None else frozen_allocation()
    total, m = mask["total"], mask["queries_per_video"]
    kept = set(mask["kept_query_ids"])
    dropped = set(mask["dropped_query_ids"])
    ids = {r["query_id"] for r in allocation}
    rows_by_video, got_totals, types_per_video = {}, {t: 0 for t in TYPES}, {}
    for r in allocation:
        if r["query_id"] in kept:
            rows_by_video[r["video_id"]] = rows_by_video.get(r["video_id"], 0) + 1
            got_totals[r["query_type"]] += 1
            types_per_video.setdefault(r["video_id"], set()).add(r["query_type"])
    want = expected_quota(total, allocation)
    checks = {
        "count_matches_design": len(kept) == total,
        "per_video_rows_exact": bool(rows_by_video) and
                                set(rows_by_video.values()) == {m},
        "clusters_preserved": len(rows_by_video) == N_VIDEOS,
        "all_types_present_per_video": all(v == set(TYPES)
                                           for v in types_per_video.values()),
        "global_quota_exact": got_totals == want,
        "declared_quota_matches": mask["quota"] == want,
        "no_new_query_id": kept <= ids,
        "partition_is_complete": (kept | dropped) == ids and not (kept & dropped),
    }
    return {"ok": all(checks.values()), "checks": checks,
            "type_totals": got_totals, "expected_quota": want,
            "n_kept": len(kept)}


def main():
    ap = argparse.ArgumentParser(
        description="P2 축소 설계 keep-mask 생성 — 설계 선택은 하지 않는다")
    ap.add_argument("--total", type=int, required=True, choices=sorted(DESIGNS))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    alloc = frozen_allocation()
    mask = keep_mask(a.total, allocation=alloc, seed=a.seed)
    check = verify_mask(mask, allocation=alloc)
    if not check["ok"]:
        raise DesignError(f"검산 실패: {check['checks']}")
    mask["verification"] = check
    Path(a.out).write_text(json.dumps(mask, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"{mask['design']}: keep {len(mask['kept_query_ids'])} / "
          f"drop {len(mask['dropped_query_ids'])} -> {a.out}")


if __name__ == "__main__":
    main()
