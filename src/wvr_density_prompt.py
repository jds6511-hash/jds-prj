"""Stage 2 진단 프롬프트 (2026-09-08 · freeze).

```
이것은 생산 계약이 아니다.
보고서를 쓰지 않고, 출력은 event evidence로 재사용하지 않는다.
production 8종(`wvr_prompts.CONTRACTS`)과 별도 파일에 둔 이유가 그것이다.
```

같은 프롬프트를 0.5fps arm과 0.25fps arm에 그대로 준다 — 유일한 차이는 표집이다.
"""
import hashlib

DIAG_CONTRACT_NAME = "SAMPLING_DIAG_PROMPT_V1"
IS_PRODUCTION_CONTRACT = False

SAMPLING_DIAG_PROMPT_V1 = """당신은 한 구간에서 뽑은 프레임을 시간순으로 본다.
보고서를 쓰지 않는다. 이 구간에서 무엇이 보였는지만 나열한다.

[규칙]
- 한국어로만 쓴다. 한자·가나·라틴 문자로 된 낱말을 섞지 않는다.
- JSON 하나만 출력한다. 설명·머리말·코드펜스를 붙이지 않는다.
- 화면에 보이는 것만 쓴다. 소리·대사·자막은 입력에 없으므로 말하지 않는다.
- approx_time은 영상 전체 기준 초 단위 실수로, 이 구간 안에 있어야 한다.
- 억지로 항목을 채우지 않는다. 빈 목록도 허용된다.
- 항목은 시간순으로 적는다.

[구간]
start_sec=%(window_start).1f end_sec=%(window_end).1f

[출력 형식]
{"observed_events": [{"approx_time": 0.0, "event": "...",
                      "visible_entities": ["..."], "activity": "..."}]}
"""


def prompt_hash() -> str:
    return hashlib.sha256(SAMPLING_DIAG_PROMPT_V1.encode("utf-8")).hexdigest()
