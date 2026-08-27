"""ROUND 2 consolidation — 고재현율 후보를 major event로 다시 수렴시킨다.

규격 `docs/finalization/M8_REDESIGN_R2_GATE_2026-08-28.md` §2-2·§2-3 (실행 전 동결).

ROUND 1에서 짧은 사건 recall은 살았지만(미매칭 GT 22→10) 생성이 93→219로 터졌고
그중 161건이 미매칭이었다. 정리 단계가 없었기 때문이다.

```
고재현율 추출 → **이 모듈** → 기존 validate_events · merge_events · report.json
```

**새 사건을 발명하지 않는다.** 모델에게 후보 내용을 다시 쓰게 하지 않고
**기존 후보 ID의 그룹만** 내게 한다. 최종 사건은 그 그룹에서 코드가 조립한다.

```
허용   같은 주요 활동의 내부 단계를 한 그룹으로 · 명백한 중복을 한 그룹으로
금지   새 사건 · 추가 분할 · 비인접 임의 병합 · 증거 밖 span 확장 ·
      유사도 임계 신설
```

**fail-closed.** 그룹이 입력 후보의 정확한 분할이 아니면 그 청크의 consolidation을
적용하지 않고 원본을 그대로 둔다.
"""
import json
import re

import m8_report


class ConsolidateError(RuntimeError):
    """그룹이 입력 후보의 분할이 아닐 때. **조용히 고치지 않는다.**"""


def candidate_ids(candidates: list) -> list:
    return [f"E{i + 1:02d}" for i in range(len(candidates))]


def build_consolidation_prompt(candidates: list, ids: list) -> str:
    """후보 목록을 보여주고 **그룹만** 받는다. 서술을 다시 쓰게 하지 않는다."""
    lines = []
    for i, c in zip(ids, candidates):
        span = c.get("span") or []
        lines.append(f'{i} 구간 {span} · {c.get("event", "")} · '
                     f'{(c.get("description") or "")[:120]}')
    return (
        "아래는 같은 영상 구간에서 뽑은 사건 후보들입니다.\n"
        "하나의 지속 활동이 세부 설명·풍경·안내 때문에 여러 후보로 쪼개진 경우,\n"
        "그 후보들을 **한 그룹**으로 묶으세요. 서로 다른 활동은 각각 따로 두세요.\n\n"
        "출력은 **JSON 하나만** 쓸 것. 형식:\n"
        '{"groups": [["E01","E02"], ["E03"]]}\n\n'
        "규칙:\n"
        "1. 모든 후보 ID가 정확히 한 번씩 나와야 한다.\n"
        "2. **새 사건을 만들지 말 것.** 있는 ID만 묶는다.\n"
        "3. 후보를 더 쪼개지 말 것.\n"
        "4. 시간적으로 떨어진 후보를 억지로 묶지 말 것.\n"
        "5. 설명·머리말·맺음말을 쓰지 말 것.\n\n"
        "후보:\n" + "\n".join(lines))


def parse_groups(raw: str, ids: list) -> list:
    """입력 ID의 **정확한 분할**만 통과시킨다."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        raise ConsolidateError("JSON을 못 건졌다")
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError) as e:
        raise ConsolidateError(f"JSON 파싱 실패: {e}") from e
    groups = data.get("groups")
    if not isinstance(groups, list) or not all(isinstance(g, list) for g in groups):
        raise ConsolidateError("groups가 배열의 배열이 아니다")
    flat = [x for g in groups for x in g]
    unknown = [x for x in flat if x not in ids]
    if unknown:
        raise ConsolidateError(f"미지 ID: {unknown[:5]}")
    if len(flat) != len(set(flat)):
        raise ConsolidateError("중복 ID가 있다")
    missing = [i for i in ids if i not in set(flat)]
    if missing:
        raise ConsolidateError(f"누락 ID: {missing[:5]}")
    return [list(g) for g in groups if g]


def _spread(values: list, k: int) -> list:
    """양 끝을 포함해 고르게 `k`개를 고른다. 앞에서 잘라내지 않는다."""
    if len(values) <= k:
        return list(values)
    if k == 1:
        return [values[0]]
    idx = [round(i * (len(values) - 1) / (k - 1)) for i in range(k)]
    return [values[i] for i in sorted(set(idx))]


def compose_group(members: list) -> dict:
    """그룹에서 사건 하나를 **결정적으로** 조립한다. 새 내용을 만들지 않는다.

    `evidence`는 멤버당 대표 1개를 뽑고 사전등록 규칙 1의 상한
    (`MAX_EVIDENCE_PER_EVENT`)을 넘으면 그룹 span에 고르게 분포하도록 고른다.
    이것은 R4(거부된 후보를 잘라 되살리기)가 아니라 **새로 합친 후보의 대표 근거를
    구성**하는 것이다 — 규격 §2-3.
    """
    if len(members) == 1:
        return dict(members[0])
    spans = [m["span"] for m in members if m.get("span")]
    span = [min(s[0] for s in spans), max(s[1] for s in spans)] if spans else []
    # 이름: span이 가장 긴 멤버. 동률이면 가장 앞선 것 — 지속이 긴 쪽이 주요 활동이다
    best = max(range(len(members)),
               key=lambda i: ((members[i]["span"][1] - members[i]["span"][0])
                              if members[i].get("span") else -1,
                              -i))
    descs = []
    for m in members:
        d = (m.get("description") or "").strip()
        if d and d not in descs:
            descs.append(d)
    reps = []
    for m in members:
        ev = sorted(m.get("evidence_segments") or [])
        if ev:
            reps.append(ev[0])
    reps = sorted(set(reps))
    if span:
        reps = [c for c in reps if span[0] <= c <= span[1]]
    return {"event": members[best].get("event", ""), "span": span,
            "evidence_segments": _spread(reps, m8_report.MAX_EVIDENCE_PER_EVENT),
            "description": " ".join(descs)}


def consolidate(candidates: list, llm) -> tuple:
    """후보를 major event로 수렴. 실패하면 **원본을 그대로 돌려준다.**"""
    diag = {"input_candidates": len(candidates), "output_events": len(candidates),
            "groups": 0, "singletons": 0, "merged_groups": 0,
            "largest_group": 0, "group_sizes": [], "invalid_grouping": 0,
            "applied": False}
    if len(candidates) < 2:
        return list(candidates), diag
    ids = candidate_ids(candidates)
    by_id = dict(zip(ids, candidates))
    try:
        groups = parse_groups(llm(build_consolidation_prompt(candidates, ids)), ids)
    except ConsolidateError as e:
        diag["invalid_grouping"] = 1
        diag["error"] = str(e)[:200]
        return list(candidates), diag
    out = [compose_group([by_id[i] for i in g]) for g in groups]
    # 시간순으로 되돌린다 — 모델이 낸 그룹 순서가 결과 순서를 바꾸면 안 된다
    out.sort(key=lambda e: (e["span"][0] if e.get("span") else 0,
                            e["span"][1] if e.get("span") else 0))
    sizes = [len(g) for g in groups]
    diag.update({"output_events": len(out), "groups": len(groups),
                 "singletons": sum(1 for s in sizes if s == 1),
                 "merged_groups": sum(1 for s in sizes if s > 1),
                 "largest_group": max(sizes) if sizes else 0,
                 "group_sizes": sizes, "applied": True})
    return out, diag
