"""v2.1 episode content adapter — 호출 경계 (Gate B · B-02a).

```
invoke → raw persist → parse → merge
```

이 모듈은 **모델을 올리지 않는다.** 생성기는 `prompt -> raw text` 콜러블로 주입
받는다. 실제 백엔드 연결은 B-02b(서버)다. 그래야 호출 규약을 GPU 없이 결정적으로
검증할 수 있고, 백엔드를 바꿔도 이 계약이 흔들리지 않는다.

호출 자체가 실패하면 저장할 raw가 없다 — `MODEL_FAILURE`다. raw가 왔는데 구조가
깨졌으면 `PARSE_CONTRACT_FAILURE`이고, 그 raw는 남는다. 둘을 섞지 않는다.

### decoding 계약을 가장하지 않는다

SPEC §22는 `temperature: 0`을 적었지만 그것은 ollama 표기다. transformers에서
같은 의미를 내는 것은 **greedy decoding = `do_sample=False`**이므로 그렇게 적는다.
`temperature=0`이라고 써 두고 실제로는 다른 것을 하는 편이 더 나쁘다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from v2_1_content import merge_content
from v2_1_parse import model_failure, parse_json_payload

#: raw store에 쌓이는 채널. evidence modality가 아니다(A-03 EVIDENCE_MODALITIES 참조).
SOURCE_TYPE = "llm"


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """무엇으로 생성했는지. 재현에 필요한 값만 담고 이름을 바꾸지 않는다."""

    model_id: str
    do_sample: bool = False
    max_new_tokens: int = 512

    def __post_init__(self) -> None:
        if not str(self.model_id).strip():
            raise ValueError("model_id is required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "do_sample": self.do_sample,
            "max_new_tokens": self.max_new_tokens,
        }

    def signature(self) -> str:
        return "do_sample=%s max_new_tokens=%d" % (self.do_sample,
                                                   self.max_new_tokens)


@dataclass(frozen=True, slots=True)
class Invocation:
    """호출 한 번의 결과와 그 출처."""

    result: object
    prompt_version: str
    prompt_hash: str
    model_id: str
    generation: dict
    raw_ref: str | None


def invoke_episode(
    generate: Callable[[str], str],
    episode,
    bundle,
    store,
    registry,
    *,
    config: GenerationConfig,
) -> Invocation:
    """프롬프트를 보내고, raw를 먼저 남긴 뒤, 파싱해 구조에 붙인다.

    raw는 구간의 시작 segment 번호로 키를 잡는다 — 구간은 겹치지 않으므로 유일하다.
    """
    segment_id = episode.support_span["start_seg"]
    try:
        raw = generate(bundle.text)
    except Exception as exc:
        return Invocation(
            result=merge_content(episode, model_failure(exc)),
            prompt_version=bundle.prompt_version,
            prompt_hash=bundle.prompt_hash,
            model_id=config.model_id,
            generation=config.as_dict(),
            raw_ref=None,
        )

    outcome = store.store_then_parse(
        lambda text: parse_json_payload(text, registry),
        segment_id=segment_id,
        source_type=SOURCE_TYPE,
        producer=config.model_id,
        producer_version=config.signature(),
        payload=raw,
    )
    return Invocation(
        result=merge_content(episode, outcome.parsed),
        prompt_version=bundle.prompt_version,
        prompt_hash=bundle.prompt_hash,
        model_id=config.model_id,
        generation=config.as_dict(),
        raw_ref="%s:%06d" % (SOURCE_TYPE, outcome.record.segment_id),
    )
