"""v2.1 episode content prompt — 계약을 고정하고 해시로 추적한다 (Gate B · B-03).

이 모듈은 **어디에 보낼지 모른다.** 호출·로딩·생성 파라미터는 B-02 소관이다.
그래야 backend를 바꿔도 prompt 계약이 흔들리지 않는다.

```
v2 (기본)   필수 summary · 선택 dialogue_note · stt_cites
v3          필수 summary — 선택 항목 없음 (post-v2.1 병행 계약)
```

두 계약은 **동시에 존재한다.** v2를 제자리에서 고치지 않는 이유는, 고치면 이미 기록된
`prompt_hash`가 무엇을 가리켰는지 사후에 알 수 없기 때문이다.

근거는 자격으로 **블록을 나눈다.**

```
근거 블록   usable_for_claims == true
참고 블록   preserved == true AND usable_for_claims == false   (기본값: 넣지 않는다)
```

같은 목록에 `usable=false` 플래그만 붙이면 옆문으로 인용된다. OPEN-9가 막으려던
것이 정확히 그것이다. 그래서 목록이 아니라 블록을 가르고, 기본값은 참고 블록을
아예 넣지 않는 것이다.

`prompt_hash`는 **계약의 지문**이다. 에피소드 내용·backend·실행 시각이 섞이지
않는다. 섞이면 "프롬프트가 언제 바뀌었는가"를 추적할 수 없다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

PROMPT_VERSION = "episode_content_v2"
#: post-v2.1. summary만 요구한다. v2를 **대체하지 않는다** — 병행 계약이다.
PROMPT_VERSION_V3 = "episode_content_v3_summary_only"

_CLAIM_HEADER = "[근거]"
_CONTEXT_HEADER = "[참고]"

#: 계약 본문. 이 사전이 곧 해시 대상이다.
CONTRACT = {
    "version": PROMPT_VERSION,
    "system": "너는 영상 구간 기록을 한국어로 정리하는 분석가다.",
    "task": "주어진 구간에서 무슨 일이 있었는지 한 문장으로 적는다.",
    "rules": [
        "근거 블록에 있는 것만 사실로 적는다.",
        "참고 블록은 맥락일 뿐이며 사실 주장의 근거로 쓸 수 없다.",
        "발화를 인용하면 그 구간 번호를 stt_cites에 적는다.",
        "인용은 근거 블록에 있는 구간 번호만 쓴다.",
        "적을 것이 없으면 지어내지 않는다.",
    ],
    "output": {
        "format": "JSON",
        "required": ["summary"],
        "optional": ["dialogue_note", "stt_cites"],
        # 값 예시를 두지 않는다. 2026-08-31 B-02b에서 모델이 예시의 자리표시자
        # "선택"을 dialogue_note 값으로 그대로 베꼈다(OPEN-10). 선택 항목은
        # 비워 두는 것이 아니라 **키 자체를 넣지 않는 것**으로 표현한다.
        "omit_when_absent": ["dialogue_note", "stt_cites"],
    },
    "evidence_blocks": {
        "claim": "usable_for_claims == true",
        "context": "preserved == true and usable_for_claims == false",
    },
}

#: v3 계약. `dialogue_note`·`stt_cites`를 **생성 표면에서 없앤다.**
#:
#: 이유는 품질이 아니라 결합이다. 선택 항목 하나가 grounding에서 실패하면 C-09가
#: 그 구간 요약을 표현에서 지운다(2026-09-03 실측 표현 회수율 2/41). 가드를 낮추는
#: 대신 불필요하게 가드를 발동시키는 출력 표면을 없앤다.
#:
#: v2를 제자리에서 고치지 않는다 — 고치면 기존 prompt_hash의 의미가 바뀐다.
CONTRACT_V3 = {
    "version": PROMPT_VERSION_V3,
    "system": CONTRACT["system"],
    "task": CONTRACT["task"],
    "rules": [
        "근거 블록에 있는 것만 사실로 적는다.",
        "참고 블록은 맥락일 뿐이며 사실 주장의 근거로 쓸 수 없다.",
        "적을 것이 없으면 지어내지 않는다.",
    ],
    "output": {
        "format": "JSON",
        "required": ["summary"],
        # 선택 항목이 없다. 빈 배열·null·"없음"으로 채우게 하지 않는다 —
        # OPEN-10에서 배운 자리표시자 혼동이 그렇게 다시 들어온다.
        "optional": [],
        "omit_when_absent": [],
    },
    "evidence_blocks": dict(CONTRACT["evidence_blocks"]),
}

#: 출력 지시문. **계약 사전 안에 두지 않는다** — 두면 v2의 prompt_hash가 바뀐다.
_TAIL = {
    PROMPT_VERSION: [
        "출력은 JSON 객체 하나다. 다른 말을 덧붙이지 않는다.",
        "쓸 수 있는 키는 셋뿐이다.",
        "- summary: 필수. 한 문장.",
        "- dialogue_note: 인용할 발화가 있을 때만. 없으면 키를 넣지 않는다.",
        "- stt_cites: 인용한 구간 번호의 배열. 없으면 키를 넣지 않는다.",
    ],
    PROMPT_VERSION_V3: [
        "출력은 JSON 객체 하나다. 다른 말을 덧붙이지 않는다.",
        "쓸 수 있는 키는 하나뿐이다.",
        "- summary: 필수. 한 문장.",
        "다른 키는 넣지 않는다.",
    ],
}

#: 이름으로 계약을 고른다. 모르는 이름은 조용히 v2로 떨어지지 않는다.
CONTRACTS = {"v2": CONTRACT, "v3": CONTRACT_V3}


class PromptError(RuntimeError):
    """프롬프트 구성 계약 위반."""


@dataclass(frozen=True, slots=True)
class PromptBundle:
    prompt_version: str
    prompt_hash: str
    text: str
    claim_cites: tuple[int, ...]
    context_cites: tuple[int, ...]


def contract_hash(contract: dict | None = None) -> str:
    """계약의 canonical 표현에 대한 지문. 키 순서에 영향받지 않는다."""
    payload = json.dumps(
        CONTRACT if contract is None else contract,
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _in_span(episode, entry) -> bool:
    return episode.start_seg <= entry.segment_id <= episode.end_seg


def split_evidence(episode, timeline):
    """자격으로 근거를 가른다. 정렬은 구간 번호 순이다."""
    claim, context = [], []
    for entry in timeline:
        if not _in_span(episode, entry):
            continue
        for ref in [*entry.asr_refs, *entry.caption_refs, *entry.ocr_refs]:
            if ref.usable_for_claims:
                claim.append(ref)
            elif ref.preserved:
                context.append(ref)
    key = lambda ref: (ref.segment_id, ref.source_type)
    return sorted(claim, key=key), sorted(context, key=key)


_LABEL = {"asr": "발화", "vlm": "화면", "ocr": "화면문자"}


def _lines(refs, store) -> list[str]:
    rendered = []
    for ref in refs:
        text = store.load(ref.source_type, ref.segment_id).read_text().strip()
        rendered.append("seg#%d %s: %s" % (ref.segment_id, _LABEL[ref.source_type],
                                           text))
    return rendered


def resolve_contract(name: str) -> dict:
    """이름으로 계약을 고른다. 모르는 이름은 실패다 — 기본값으로 떨어지지 않는다."""
    if name not in CONTRACTS:
        raise PromptError("unknown prompt contract %r (available: %s)"
                          % (name, ", ".join(sorted(CONTRACTS))))
    return CONTRACTS[name]


def build_episode_prompt(episode, timeline, store, include_context_only: bool = False,
                         *, contract: dict = CONTRACT) -> PromptBundle:
    """한 구간의 프롬프트를 만든다. 근거가 없으면 만들지 않는다.

    `contract`를 명시하지 않으면 **v2다.** 호출자가 모르는 채로 v3를 쓰는 일은
    없어야 한다 — 계약 변경은 호출 지점에 드러나야 한다.
    """
    if contract["version"] not in _TAIL:
        raise PromptError("no output instructions for contract %r"
                          % contract["version"])
    claim, context = split_evidence(episode, timeline)
    if not claim:
        raise PromptError(
            "no usable evidence in %s — refusing to ask for a summary"
            % episode.episode_id
        )

    parts = [
        contract["system"],
        "",
        contract["task"],
        "대상 구간: seg#%d ~ seg#%d" % (episode.start_seg, episode.end_seg),
        "",
        *["- " + rule for rule in contract["rules"]],
        "",
        _CLAIM_HEADER,
        *_lines(claim, store),
    ]
    if include_context_only and context:
        parts += [
            "",
            _CONTEXT_HEADER + " 아래는 맥락일 뿐이며 사실 주장의 근거로 쓸 수 없다.",
            *_lines(context, store),
        ]
    parts += ["", *_TAIL[contract["version"]]]
    return PromptBundle(
        prompt_version=contract["version"],
        prompt_hash=contract_hash(contract),
        text="\n".join(parts),
        claim_cites=tuple(ref.segment_id for ref in claim),
        context_cites=tuple(ref.segment_id for ref in context),
    )
