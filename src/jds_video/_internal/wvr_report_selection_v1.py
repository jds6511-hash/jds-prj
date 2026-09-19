"""Report selection — 보여줄 행만 고른다. event·경계·관계·chapter는 건드리지 않는다.

```
할 수 있는 것   같은 chapter 안에서 사실상 같은 말을 반복하는 행을 화면에서 접는다
할 수 없는 것   event 생성 · 경계 분할/병합 · 관계 변경 · chapter membership 변경
```

접은 행도 evidence는 그대로 남는다(`suppressed_rows`에 id와 사유를 적는다).
**display suppression ≠ evidence 삭제.**
"""
from __future__ import annotations

import numpy as np

DUPLICATE_IN_CHAPTER = "DUPLICATE_IN_CHAPTER"
REPORT_GRANULARITY_LIMITATION = "REPORT_GRANULARITY_LIMITATION"

DUPLICATE_SIM = 0.92           # 이 이상이면 사실상 같은 문장으로 본다
LONG_ROW_SEC = 600.0           # 한 행이 이보다 길면 정보가 뭉개졌을 수 있다고 표시만 한다


def _unit(vector):
    array = np.asarray(vector, dtype=np.float32)
    return array / (float(np.linalg.norm(array)) or 1.0)


def select_rows_for_report(rows, encode, duplicate_sim=DUPLICATE_SIM,
                           long_row_sec=LONG_ROW_SEC):
    """행 목록 → (보여줄 행, 접은 행). 행을 새로 만들지 않는다."""
    ordered = sorted(rows, key=lambda r: (r["start"], r["end"], r["row_id"]))
    if not ordered:
        return [], []
    vectors = [_unit(v) for v in encode([r.get("summary", "") for r in ordered])]

    kept, suppressed = [], []
    kept_index = []
    for index, row in enumerate(ordered):
        duplicate_of, best = None, 0.0
        for position in kept_index:
            if ordered[position].get("chapter_id") != row.get("chapter_id"):
                continue          # chapter가 다르면 같은 문장이라도 다른 맥락이다
            similarity = float(np.dot(vectors[index], vectors[position]))
            if similarity > best:
                duplicate_of, best = ordered[position]["row_id"], similarity
        if duplicate_of and best >= duplicate_sim:
            entry = dict(row)
            entry["reason"] = DUPLICATE_IN_CHAPTER
            entry["duplicate_of"] = duplicate_of
            entry["similarity"] = round(best, 4)
            suppressed.append(entry)
            continue
        entry = dict(row)
        entry["granularity_flag"] = (REPORT_GRANULARITY_LIMITATION
                                     if (row["end"] - row["start"]) > long_row_sec else None)
        kept.append(entry)
        kept_index.append(index)
    return kept, suppressed


def selection_summary(kept, suppressed):
    return {
        "kept_rows": len(kept),
        "suppressed_rows": len(suppressed),
        "suppressed_reasons": {DUPLICATE_IN_CHAPTER:
                               sum(1 for r in suppressed
                                   if r["reason"] == DUPLICATE_IN_CHAPTER)},
        "granularity_limited_rows": [r["row_id"] for r in kept
                                     if r.get("granularity_flag")],
    }
