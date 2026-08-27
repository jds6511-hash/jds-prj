"""C1 파국 판정 — 규격 `docs/finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md` §1.

사전등록 §2-2가 유형 셋과 임계 0편을 동결했고, **각 유형을 무엇으로 판정하는가**를
2026-08-27에 M8 산출물 0건 시점에 채웠다. 이 모듈은 그 규격의 구현이다.

```
언어 이탈   생성 언어 자체가 바뀐 것만. 문장 안에 외국 문자가 섞인 것은 아니다
조기 종료   필요한 출력의 뒷부분이 만들어지지 않은 것. 기계 증거 우선
반복 루프   정규화 후 **완전 동일**한 단위가 연속 3회 이상
```

**판정을 canonical 생성 경로에 섞지 않는다.** 이 모듈은 이미 리포트에 들어 있는
진단 필드(`map_raw_outputs`·`truncated_tail`·`chunk_retries`)만 읽고, `m8_report`의
병합·출력 의미를 바꾸지 않는다.

**반복은 병합 전 원본에서 본다.** `m8_report.merge_events`가 같은 이름 + span 인접인
사건을 합치므로, 병합 후 산출물에서 세면 파이프라인이 지워 준 파국을 PASS로 읽는다.

3-state다. `PRESENT` / `ABSENT` / `UNCLEAR`이고 **`UNCLEAR`는 통과가 아니다** —
boolean 하나로는 "판정 못 했다"를 표현할 수 없고, 표현할 수 없으면 조용히 `ABSENT`가
된다.
"""
import re

C1_KINDS = ("language_drift", "early_stop", "repetition_loop")
STATUSES = ("PRESENT", "ABSENT", "UNCLEAR")

REPETITION_MIN_RUN = 3     # 규격 §1-2. "사건이 실제로 반복된다"와 생성 루프의 경계
_HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
_WS = re.compile(r"\s+")


class C1SpecError(RuntimeError):
    """규격에 없는 값·빠진 유형으로 판정하려 할 때. **조용히 채우지 않는다.**"""


def _norm(s: str) -> str:
    """정규화는 **공백까지다.** 의미 유사도 임계를 새로 만들지 않는다 — 규격 §1-2."""
    return _WS.sub(" ", str(s or "")).strip()


def premerge_units(rep: dict) -> list:
    """병합 전 생성 단위. 청크 원본을 생성 순서대로 다시 파싱한다.

    `map_raw_outputs`는 이미 리포트에 있는 필드다 — 새로 노출한 것이 없다.
    """
    from m8_report import parse_events            # torch 지연 로딩 경로를 피한다
    out = []
    for chunk_i, raw in enumerate(rep.get("map_raw_outputs") or []):
        for e in parse_events(raw):
            out.append({"chunk": chunk_i,
                        "event": _norm(e.get("event")),
                        "description": _norm(e.get("description"))})
    return out


def detect_repetition_loop(rep: dict, min_run: int = REPETITION_MIN_RUN) -> dict:
    """정규화 후 완전 동일한 단위가 **연속** `min_run`회 이상이면 PRESENT.

    청크 경계를 넘는 연속도 센다. 청크가 겹쳐 같은 사건이 두 번 나오는 것은 정상이라
    경계 하나만으로는 걸리지 않지만, 3회는 겹침으로 설명되지 않는다.

    원본이 없으면 **UNCLEAR**다 — 없는 것을 ABSENT로 쓰면 판정하지 않은 것을
    통과로 만든다.
    """
    units = premerge_units(rep)
    if not units:
        return {"status": "UNCLEAR",
                "evidence": ["map_raw_outputs가 비어 있어 병합 전 원본을 볼 수 없다"]}
    key = [f'{u["event"]}|{u["description"]}' for u in units]
    ev, run_start = [], 0
    for i in range(1, len(key) + 1):
        if i < len(key) and key[i] == key[run_start]:
            continue
        n = i - run_start
        if n >= min_run:
            ev.append({"unit": key[run_start][:120], "count": n,
                       "first_index": run_start,
                       "chunks": sorted({units[j]["chunk"]
                                         for j in range(run_start, i)})})
        run_start = i
    return {"status": "PRESENT" if ev else "ABSENT", "evidence": ev}


def detect_early_stop(rep: dict) -> dict:
    """필요한 출력의 뒷부분이 만들어지지 않았는가. **기계 증거만 쓴다.**

    새 임계를 만들지 않는다 — 이미 파이프라인이 남기는 세 흔적을 읽는다.
    """
    ev = []
    if rep.get("truncated_tail"):
        ev.append(f'truncated_tail: {str(rep["truncated_tail"])[:120]}')
    unrecovered = [r for r in (rep.get("chunk_retries") or [])
                   if not r.get("recovered")]
    if unrecovered:
        ev.append(f"재생성 실패 청크 {[r.get('chunk') for r in unrecovered]} — "
                  f"그 구간 출력이 만들어지지 않았다")
    if not (rep.get("sentences") or []):
        ev.append("sentences가 0건 — 필요한 출력이 없다")
    return {"status": "PRESENT" if ev else "ABSENT", "evidence": ev}


def detect_language_drift(rep: dict) -> dict:
    """**categorical 선별이다. 자동으로 PRESENT를 내지 않는다.**

    후보 = 한글이 **하나도 없는** 완결 서술 단위. 이렇게 두면 규격 §1-2가 제외한
    것들이 후보로도 올라오지 않는다 — 고유명사·짧은 외국어 인용·화면 속 문자·단일
    외래어는 모두 한글이 있는 문장 **안에** 있다.

    후보가 하나도 없으면 ABSENT다. 있으면 UNCLEAR로 두고 사람이 판정한다 —
    화면 문자를 그대로 옮긴 것일 수 있어서 후보를 곧 파국으로 읽으면 안 된다.
    """
    units = premerge_units(rep)
    if not units:
        return {"status": "UNCLEAR",
                "evidence": ["map_raw_outputs가 비어 있어 생성 단위를 볼 수 없다"]}
    cand = [u["description"][:160] for u in units
            if u["description"] and not _HANGUL.search(u["description"])]
    if not cand:
        return {"status": "ABSENT", "evidence": []}
    return {"status": "UNCLEAR", "evidence": cand}


def inspect_video(rep: dict, language_drift: str | None = None) -> dict:
    """영상 하나의 C1 소견. `language_drift`에 사람 판정을 주면 선별을 대체한다."""
    if language_drift is not None and language_drift not in STATUSES:
        raise C1SpecError(f"language_drift 값이 규격에 없다: {language_drift!r} — "
                          f"{STATUSES} 중 하나여야 한다")
    drift = ({"status": language_drift, "evidence": ["사람 판정"]}
             if language_drift is not None else detect_language_drift(rep))
    return {"language_drift": drift,
            "early_stop": detect_early_stop(rep),
            "repetition_loop": detect_repetition_loop(rep)}


def video_status(finding: dict) -> str:
    """영상 단위 상태. **PRESENT가 UNCLEAR를 이긴다** — 하나라도 났으면 이미 파국이다.

    유형이 빠진 채 들어오면 거부한다. 빠진 유형은 조용히 ABSENT가 되기 때문이다.
    """
    missing = [k for k in C1_KINDS if k not in finding]
    if missing:
        raise C1SpecError(f"C1 유형이 빠졌다: {missing} — 빠진 유형은 판정에서 "
                          f"조용히 ABSENT가 된다")
    st = []
    for k in C1_KINDS:
        s = (finding[k] or {}).get("status")
        if s not in STATUSES:
            raise C1SpecError(f"{k} 상태가 규격에 없다: {s!r} — {STATUSES}")
        st.append(s)
    if "PRESENT" in st:
        return "PRESENT"
    return "UNCLEAR" if "UNCLEAR" in st else "ABSENT"
