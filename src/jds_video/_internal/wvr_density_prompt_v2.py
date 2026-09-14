"""Stage 2 V2 진단 프롬프트 (2026-09-09 · freeze).

```
비생산 진단 도구다. 보고서를 쓰지 않고 출력을 event evidence로 재사용하지 않는다.
V1/V1B 프롬프트(SAMPLING_DIAG_PROMPT_V1)는 동결 보존하고 재사용하지 않는다.
출력 언어는 English-only — production 보고서 언어를 바꾸는 것이 아니라,
sampling-density 측정에서 output-language nuisance variable을 제거하기 위한 것이다.
```

핵심 차이는 **observation이 아니라 event interval을 요구**하는 것이다.
"""
import hashlib

DIAG_CONTRACT_NAME = "SAMPLING_DIAG_PROMPT_V2"
IS_PRODUCTION_CONTRACT = False
OUTPUT_LANGUAGE = "en"

SAMPLING_DIAG_PROMPT_V2 = """You watch frames sampled in order from one window of a video.
You do not write a report. You list the events you can see as time intervals.

[Rules]
- Write in English only. Do not use Korean, Chinese or Japanese characters.
- Output exactly one JSON object. No prose, no preamble, no code fence.
- Describe only what is visible in the frames. There is no audio, speech or
  subtitle input, so do not mention any.
- Do not repeat a continuing state once per frame. Merge one continuing
  action or state into a single interval event.
- If the same action appears again after a different event in between, record
  it as a new event.
- start_sec and end_sec are seconds on the whole-video clock and must lie
  inside this window. start_sec <= end_sec.
- Order the events by start_sec.
- Do not invent a shop name, product name or person name that is not written
  on screen.
- Do not pad the list. An empty list is allowed if nothing is visible.
- There is no limit on how many events you may report.

[Window]
start_sec=%(window_start).1f end_sec=%(window_end).1f

[Output format]
{"events": [{"start_sec": 0.0, "end_sec": 0.0, "actor": "...",
             "action": "...", "object_or_state": "..."}]}
"""


def prompt_hash() -> str:
    return hashlib.sha256(SAMPLING_DIAG_PROMPT_V2.encode("utf-8")).hexdigest()
