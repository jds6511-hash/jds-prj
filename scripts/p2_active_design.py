"""P2 활성 설계 — **표본 규모의 단일 출처.**

`315`를 여러 모듈에 상수로 박아 두면 amendment가 한 군데만 반영되고 나머지가
조용히 거짓말을 한다. 그래서 활성 설계를 하나의 tracked 산출물로 두고
intake · retrieval · evaluation이 전부 여기서 읽는다.

```
승인       2026-08-24 amendment — 35영상 × 5 = 175 (fixed N)
동결 mask   docs/P2_keepmask_175_2026-08-24.json (sha256 대조)
불변       PRIMARY · alpha · 후보 풀 · cluster bootstrap · exclusion · half-width 0.04
금지       결과를 본 뒤 175 → 315 증량 (별도 사전등록 사건이다)
```

읽을 때마다 전부 재검산한다 — mask 해시, 영상당 행 수, global quota, 세 유형 존재,
동결 배정표 315의 부분집합인지. 하나라도 어긋나면 fail-closed다.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_reduced_design as RD                                     # noqa: E402

ACTIVE = ROOT / "docs" / "P2_활성설계_2026-08-24.json"
REQUIRED_FLAGS = ("fixed_n", "no_outcome_based_top_up")


class ActiveDesignError(Exception):
    pass


def _mask_of(doc: dict, base: Path) -> dict:
    p = base / doc["keep_mask"] if not Path(doc["keep_mask"]).is_absolute() \
        else Path(doc["keep_mask"])
    if not p.is_file():
        raise ActiveDesignError(f"동결 mask가 없다: {p}")
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    if got != doc["keep_mask_sha256"]:
        raise ActiveDesignError(f"mask sha256 불일치 — 기대 "
                                f"{doc['keep_mask_sha256'][:12]}… 실제 "
                                f"{got[:12]}…")
    return json.loads(p.read_text(encoding="utf-8"))


def load(path=ACTIVE, allocation: list = None) -> dict:
    """활성 설계를 읽고 전부 재검산한다. 캐시하지 않는다."""
    path = Path(path)
    if not path.is_file():
        raise ActiveDesignError(f"활성 설계 파일이 없다: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    for flag in REQUIRED_FLAGS:
        if doc.get(flag) is not True:
            raise ActiveDesignError(f"{flag}가 참이 아니다 — 표본 규모를 결과에 "
                                    "맞춰 늘리는 설계는 받지 않는다")
    mask = _mask_of(doc, ROOT)
    allocation = allocation if allocation is not None else RD.frozen_allocation()
    if len(allocation) != doc["frozen_allocation_total"]:
        raise ActiveDesignError(f"동결 배정표 {len(allocation)}행 != "
                                f"{doc['frozen_allocation_total']}행")
    for key in ("total_queries", "queries_per_video", "n_videos"):
        want = {"total_queries": mask["total"],
                "queries_per_video": mask["queries_per_video"],
                "n_videos": mask["n_videos"]}[key]
        if doc[key] != want:
            raise ActiveDesignError(f"{key} 불일치 — 설계 {doc[key]} · mask {want}")
    if doc["quota"] != mask["quota"]:
        raise ActiveDesignError(f"quota 불일치 — 설계 {doc['quota']} · "
                                f"mask {mask['quota']}")

    kept = list(mask["kept_query_ids"])
    if len(set(kept)) != len(kept):
        raise ActiveDesignError("mask에 중복 query_id가 있다")
    if len(kept) != doc["total_queries"]:
        raise ActiveDesignError(f"mask {len(kept)}건 != 설계 "
                                f"{doc['total_queries']}건")
    by_id = {r["query_id"]: r for r in allocation}
    unknown = [q for q in kept if q not in by_id]
    if unknown:
        raise ActiveDesignError(f"동결 배정표에 없는 query_id {len(unknown)}건 "
                                f"(예: {unknown[:3]}) — 새 질의를 만들 수 없다")
    rows, types = {}, {}
    for q in kept:
        r = by_id[q]
        rows[r["video_id"]] = rows.get(r["video_id"], 0) + 1
        types.setdefault(r["video_id"], set()).add(r["query_type"])
    if len(rows) != doc["n_videos"]:
        raise ActiveDesignError(f"영상 {len(rows)}편 != {doc['n_videos']}편 — "
                                "cluster를 줄이는 설계가 아니다")
    bad = {v: n for v, n in rows.items() if n != doc["queries_per_video"]}
    if bad:
        raise ActiveDesignError(f"영상당 행 수가 다르다 {bad} — 목표 "
                                f"{doc['queries_per_video']}")
    thin = {v: sorted(t) for v, t in types.items() if len(t) < len(RD.TYPES)}
    if thin:
        raise ActiveDesignError(f"세 유형이 다 없는 영상이 있다 {thin}")
    got_quota = {t: 0 for t in RD.TYPES}
    for q in kept:
        got_quota[by_id[q]["query_type"]] += 1
    if got_quota != doc["quota"]:
        raise ActiveDesignError(f"유형 합 {got_quota} != quota {doc['quota']}")
    return dict(doc, kept_query_ids=kept,
                dropped_query_ids=list(mask["dropped_query_ids"]))


def total_queries(path=ACTIVE) -> int:
    return load(path)["total_queries"]


def kept_query_ids(path=ACTIVE) -> list:
    return load(path)["kept_query_ids"]
