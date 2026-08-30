"""BCS presentation layer — 정본을 형식만 바꿔 옮긴다.

결정: `docs/finalization/BCS_CORE_FREEZE_2026-08-29.md`

```
정본    runs/bcs/bcs_v0_reparsed/<vid>.json    검증을 통과한 사실
표현    블록 목록 → Markdown · HWPX             형식만 바꾼다
```

**새 사실을 만들지 않는다.** LLM 미사용, 생성 문장 무수정, 지표 재계산 없음.
표현이 실패해도 정본은 그대로다 — 과거에는 제목 하나가 빠지면 문서 전체가
무효였다(v3 title 12/16 · v4 · softyeon).

문체는 **레이블에서만** 통일한다. 생성된 문장의 어미를 고쳐 쓰지 않는다 —
고치는 순간 그것은 표현이 아니라 새 서술이다.

블록: `{"kind": "h1"|"h2"|"label"|"para"|"bullets", ...}`
"""
import bcs as B

# 표현 계층에서 통일하는 것은 이 레이블뿐이다.
L_CONTENT, L_DIALOGUE, L_EVIDENCE = "주요 내용", "대화 요지", "근거"
SECTIONS = ("영상 개요", "주요 흐름", "구간별 기록",
            "특이사항 및 확인 불가", "근거 및 생성 정보")


def _hhmm(sec: int) -> str:
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _span_label(e: dict, seg_len: int) -> str:
    return (f"{e['episode_id']}  {_hhmm(e['start_seg'] * seg_len)}~"
            f"{_hhmm((e['end_seg'] + 1) * seg_len)}")


def _cites(idxs) -> str:
    return " ".join(f"[seg#{c}]" for c in idxs)


def sections(doc: dict, segments=None, seg_len: int = 5) -> list:
    """정본이 무효면 표현하지 않는다 — fallback 문서를 만들지 않는다."""
    bad = B.validate(doc, doc.get("video_id"))
    if bad:
        raise B.ViewError(f"무효 정본은 표현하지 않는다: {bad}")
    eps = doc["episodes"]
    by_idx = {s["idx"]: s for s in (segments or [])}
    n = doc["n_segments"]
    counts = doc.get("stt_status_counts") or {}
    removed = sum(v for k, v in counts.items() if k not in ("USABLE", "EMPTY"))

    out = [{"kind": "h1", "text": SECTIONS[0]},
           {"kind": "para", "text":
            f"대상 {doc['video_id']} · 길이 {_hhmm(n * seg_len)} · "
            f"구간 {n}개 · 구간 기록 {len(eps)}개"},
           {"kind": "para", "text":
            "구간 경계는 화면 설명만으로 정한 heuristic segmentation이다 — "
            "정답 사건 경계가 아니다."},
           {"kind": "para", "text":
            "이 문서는 제품 prototype 산출물이며 M9 검증을 거친 최종 산출물이 "
            "아니다(M9는 미실행)."},
           {"kind": "h1", "text": SECTIONS[1]},
           {"kind": "bullets",
            "items": [_span_label(e, seg_len) for e in eps]},
           {"kind": "h1", "text": SECTIONS[2]}]

    for e in eps:
        out += [{"kind": "h2", "text": _span_label(e, seg_len)},
                {"kind": "label", "text": L_CONTENT},
                {"kind": "para", "text": e["summary"]}]
        if (e.get("dialogue_note") or "").strip():
            out += [{"kind": "label", "text": L_DIALOGUE},
                    {"kind": "para", "text": e["dialogue_note"]},
                    {"kind": "para", "text": "발화 근거 " + _cites(e["stt_cites"])}]
        out += [{"kind": "label", "text": L_EVIDENCE},
                {"kind": "para", "text": _cites(e["anchor_cites"])}]

    notes = []
    if removed:
        detail = " · ".join(f"{k} {v}" for k, v in sorted(counts.items())
                            if k not in ("USABLE", "EMPTY"))
        notes.append(f"오염으로 판정해 서술 입력에서 제외한 발화 {removed}건 "
                     f"({detail}). 원본은 보존돼 있다.")
    for e in eps:
        if e.get("dropped"):
            notes.append(f"{e['episode_id']} 대화 주장을 근거 미달로 제외했다 "
                         f"({e['dropped']}).")
    odd = [e["episode_id"] for e in eps
           if e.get("parse_mode") not in (None, "json")]
    if odd:
        notes.append(f"생성 출력 형식이 온전하지 않아 요약만 회수한 구간 "
                     f"{', '.join(odd)}.")
    if not any((e.get("dialogue_note") or "").strip() for e in eps):
        notes.append("이 영상에서는 근거를 갖춘 대화 기록이 생성되지 않았다.")
    out += [{"kind": "h1", "text": SECTIONS[3]},
            {"kind": "bullets", "items": notes or ["없음"]}]

    # **검증을 통과한 대화의 근거만 싣는다.** 버려진 주장의 인용을 부록에 남기면
    # 기각한 근거를 제시하는 꼴이다(EP15 cite_not_usable_stt 사례).
    cited = sorted({c for e in eps if (e.get("dialogue_note") or "").strip()
                    for c in (e.get("stt_cites") or [])})
    prov = doc.get("provenance") or {}
    model = (prov.get("effective_model_id") or prov.get("requested_model")
             or prov.get("model") or "-")
    rev = (prov.get("effective_model_revision") or "")[:12]
    info = [f"정본 {doc.get('run_kind')} · commit {doc.get('commit')}",
            f"모델 {model}" + (f" ({rev})" if rev else "")
            + (" · greedy" if prov.get("do_sample") is False else ""),
            "규격 docs/finalization/BCS_PROTOTYPE_SPEC_2026-08-29.md",
            "표현 계층은 LLM을 사용하지 않는다 — 형식 변환만 한다"]
    out += [{"kind": "h1", "text": SECTIONS[4]},
            {"kind": "bullets", "items": info}]
    if cited:
        out += [{"kind": "label", "text": "인용된 구간의 발화"},
                {"kind": "bullets",
                 "items": [f"seg#{c} "
                           f"{_hhmm(c * seg_len)}  "
                           f"{(by_idx.get(c, {}).get('clean_stt') or '').strip()}"
                           .rstrip() for c in cited]}]
    return out


def to_markdown(blocks: list) -> str:
    L = []
    for b in blocks:
        k = b["kind"]
        if k == "h1":
            L += [f"# {b['text']}", ""]
        elif k == "h2":
            L += [f"## {b['text']}", ""]
        elif k == "label":
            L += [f"**{b['text']}**", ""]
        elif k == "bullets":
            L += [f"- {x}" for x in b["items"]] + [""]
        else:
            L += [b["text"], ""]
    return "\n".join(L)
