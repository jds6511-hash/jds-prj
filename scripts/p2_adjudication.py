"""심사 provenance — **누가 무엇을 확정했는지만 남긴다.**

최종 `text` · `gt_start` · `gt_end`는 여기 저장하지 않는다. 그것은
`p2_label_intake.csv` 하나에만 있다. 이 파일은 audit metadata다.

```
label_origin   human_only | ai_first_human_adjudicated
draft_action   not_applicable | accepted | edited | rejected_manual
```

**PRIMARY 평가기에 넘기지 않는다.** label_origin으로 가중·선택·제외하지 않고,
label_origin별 성능을 사후에 갈라 보지 않는다. 그런 분석을 원하면 P2 결과 전에 따로
사전등록해야 한다 — 이번에는 만들지 않는다.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_label_intake as INTAKE                                   # noqa: E402

KIT = ROOT / "label_kit" / "p2_ai_assist"
AUDIT = KIT / "p2_adjudication_audit.csv"
AUDIT_COLUMNS = ("query_id", "label_origin", "draft_action", "recorded_at")
LABEL_ORIGIN = ("human_only", "ai_first_human_adjudicated")
DRAFT_ACTION = ("not_applicable", "accepted", "edited", "rejected_manual")
FORBIDDEN_COLUMNS = ("text", "gt_start", "gt_end", "note", "caption",
                     "subtitle", "rank", "score", "rr", "mrr", "arm")
NOT_FOR_EVALUATION = ("label_origin으로 가중·선택·제외하지 않는다",
                      "label_origin별 성능을 사후에 갈라 보지 않는다",
                      "그 분석은 P2 결과 전에 별도 사전등록이 필요하다")


class AdjudicationError(RuntimeError):
    pass


def _now() -> str:
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


def check_pair(label_origin: str, draft_action: str) -> None:
    """origin과 action의 짝이 말이 되는지 본다."""
    if label_origin not in LABEL_ORIGIN:
        raise AdjudicationError(f"label_origin {label_origin!r} 미허용 — "
                                f"{list(LABEL_ORIGIN)}")
    if draft_action not in DRAFT_ACTION:
        raise AdjudicationError(f"draft_action {draft_action!r} 미허용 — "
                                f"{list(DRAFT_ACTION)}")
    if label_origin == "human_only" and draft_action != "not_applicable":
        raise AdjudicationError("human_only인데 draft_action이 "
                                f"{draft_action!r}다 — 초안이 없던 행이다")
    if label_origin == "ai_first_human_adjudicated" \
            and draft_action == "not_applicable":
        raise AdjudicationError("ai_first_human_adjudicated인데 draft_action이 "
                                "not_applicable이다 — 사람이 행동을 명시해야 한다")


def load(path=AUDIT) -> list:
    path = Path(path)
    if not path.is_file():
        return []
    return list(csv.DictReader(path.read_text(encoding="utf-8-sig")
                              .splitlines()))


def _write(path: Path, rows: list) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(AUDIT_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)
    return path


def record(query_id: str, label_origin: str, draft_action: str, path=AUDIT,
           at: str = None, allocation: list = None) -> dict:
    """한 행의 심사 결과를 기록한다. 같은 query_id는 갱신한다."""
    check_pair(label_origin, draft_action)
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    if query_id not in {r["query_id"] for r in allocation}:
        raise AdjudicationError(f"{query_id}: 활성 설계에 없다")
    rows = [r for r in load(path) if r["query_id"] != query_id]
    row = {"query_id": query_id, "label_origin": label_origin,
           "draft_action": draft_action, "recorded_at": at or _now()}
    rows.append(row)
    order = {r["query_id"]: i for i, r in enumerate(allocation)}
    rows.sort(key=lambda r: order[r["query_id"]])
    _write(path, rows)
    return row


def seed_human_only(query_ids, path=AUDIT, at: str = None,
                    allocation: list = None) -> dict:
    """전환 동결이 기록한 human-only 분량을 audit에 심는다.

    **동결 파일의 query_id만 쓴다** — 라벨 내용은 그 파일에도 없다.
    """
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    known = {r["query_id"] for r in allocation}
    unknown = [q for q in query_ids if q not in known]
    if unknown:
        raise AdjudicationError(f"활성 설계에 없는 query_id {len(unknown)}건 "
                                f"(예: {unknown[:3]})")
    existing = {r["query_id"]: r for r in load(path)}
    at = at or _now()
    for q in query_ids:
        existing[q] = {"query_id": q, "label_origin": "human_only",
                       "draft_action": "not_applicable", "recorded_at": at}
    order = {r["query_id"]: i for i, r in enumerate(allocation)}
    rows = sorted(existing.values(), key=lambda r: order[r["query_id"]])
    _write(path, rows)
    return {"n_seeded": len(list(query_ids)), "n_rows": len(rows),
            "file": str(path)}


def validate(path=AUDIT, allocation: list = None) -> dict:
    """스키마와 짝을 전수 확인한다. 최종 라벨 값이 섞여 있으면 거부한다."""
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    rows = load(path)
    if rows:
        cols = set(rows[0])
        if cols != set(AUDIT_COLUMNS):
            raise AdjudicationError(f"열 구성이 다르다 {sorted(cols)} != "
                                    f"{list(AUDIT_COLUMNS)}")
        hit = sorted(c for c in FORBIDDEN_COLUMNS if c in cols)
        if hit:
            raise AdjudicationError(f"최종 라벨 값이 audit에 있다 {hit} — 최종 "
                                    "값은 작업 CSV 하나에만 둔다")
    known = {r["query_id"] for r in allocation}
    seen = set()
    counts = {o: 0 for o in LABEL_ORIGIN}
    actions = {a: 0 for a in DRAFT_ACTION}
    for r in rows:
        q = r["query_id"]
        if q in seen:
            raise AdjudicationError(f"{q}: audit 중복")
        seen.add(q)
        if q not in known:
            raise AdjudicationError(f"{q}: 활성 설계에 없다")
        check_pair(r["label_origin"], r["draft_action"])
        counts[r["label_origin"]] += 1
        actions[r["draft_action"]] += 1
    return {"n_rows": len(rows), "n_design": len(known),
            "by_label_origin": counts, "by_draft_action": actions,
            "missing": sorted(known - seen),
            "not_for_evaluation": list(NOT_FOR_EVALUATION)}


def main():
    ap = argparse.ArgumentParser(
        description="심사 provenance — 최종 라벨 값은 담지 않는다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--freeze", default=None)
    sub.add_parser("validate")
    a = ap.parse_args()
    if a.cmd == "seed":
        import p2_hybrid_freeze as HF
        src = Path(a.freeze) if a.freeze else HF.OUT
        ids = json.loads(src.read_text(encoding="utf-8"))["human_only"]["query_ids"]
        print(json.dumps(seed_human_only(ids), ensure_ascii=False, indent=2))
        return
    print(json.dumps(validate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
