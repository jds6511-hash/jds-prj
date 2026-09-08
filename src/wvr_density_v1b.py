"""WVR_SAMPLING_SEMANTIC_DENSITY_V1B 상수 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1B_2026-09-09.md`

```
유일한 변경   max_new_tokens 1024 → 4096
동결          창 D1·D2·D3 · S0/S1 표집 · 512×288 · 모델·dtype·attn ·
             allocator default · 프롬프트 hash · 매칭 허용오차 (4.0, 8.0)
```

4096에서도 cap에 닿으면 그 결과로 닫는다. **즉석에서 8192로 올리지 않는다.**
프롬프트·schema·event 상한은 건드리지 않는다 — 그것을 바꾸면 V1 Stage 2와
다른 진단을 재게 된다.
"""
import wvr_contract as contract

EVENT_V1 = "V1"
EVENT_V1B = "V1B"

MAX_NEW_TOKENS = {EVENT_V1: contract.MAX_NEW_TOKENS, EVENT_V1B: 4096}
ARTIFACT_TAG = {EVENT_V1: "density_stage2", EVENT_V1B: "density_stage2b"}

# 사전등록된 두 값만 허용한다. 임의 값으로 돌릴 수 없다.
ALLOWED_MAX_NEW_TOKENS = tuple(sorted(MAX_NEW_TOKENS.values()))

ESCALATION_APPROVED = False        # 4096에서 또 절단되면 그대로 닫는다


class EventError(ValueError):
    """사건 계약 위반."""


def tokens_for(event: str) -> int:
    if event not in MAX_NEW_TOKENS:
        raise EventError("모르는 사건: %r" % event)
    return MAX_NEW_TOKENS[event]


def tag_for(event: str) -> str:
    if event not in ARTIFACT_TAG:
        raise EventError("모르는 사건: %r" % event)
    return ARTIFACT_TAG[event]


def assert_allowed(tokens: int) -> None:
    if tokens not in ALLOWED_MAX_NEW_TOKENS:
        raise EventError("사전등록되지 않은 max_new_tokens: %r" % tokens)
