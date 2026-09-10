"""Body-only contract for WVR_OVERVIEW_PREVIEW_V2."""
from __future__ import annotations

import json
import re

import wvr_overview_preview_v1 as v1

EVENT = "WVR_OVERVIEW_PREVIEW_V2"
SOURCE_MAP_NAME = v1.SOURCE_MAP_NAME
SOURCE_MAP_SHA256 = v1.SOURCE_MAP_SHA256

LLM_MODEL_ID = v1.LLM_MODEL_ID
LLM_MODEL_REVISION = v1.LLM_MODEL_REVISION
LLM_DTYPE = v1.LLM_DTYPE
LLM_ATTN_IMPLEMENTATION = v1.LLM_ATTN_IMPLEMENTATION
LLM_LOAD_4BIT = v1.LLM_LOAD_4BIT
LLM_DO_SAMPLE = False
LLM_MAX_NEW_TOKENS = 4096

NEW_VLM_INFERENCE_ALLOWED = False
TRACK_A_INPUT_ALLOWED = False

PROMPT_NAME = "overview_preview_v2_prompt.txt"
RAW_NAME = "overview_preview_v2_raw.txt"
RECORD_NAME = "overview_preview_v2_record.json"
RESULT_NAME = "overview_preview_v2_result.json"
PACKET_NAME = "overview_preview_v2_packet.md"

PROMPT_TEMPLATE = r'''당신은 관찰 기록을 영상 전체의 자연스러운 한국어 Overview로 추상화하는 text-only generator입니다.

목표 질문은 하나뿐입니다.
"이 10분 영상에서 주요 활동이 어떤 순서로 진행되는가?"

작성 전에 입력을 내부적으로 다음처럼 정리하되 그 중간 결과는 출력하지 마십시오.
local actions / objects → broad activity phases → Overview

본문 작성 규칙:
- Overview에는 broad activity phase와 주요 활동 전환만 사용하십시오.
- 작은 행동을 차례로 나열하는 event log를 작성하지 마십시오.
- 개별 식재료, 개별 도구, 작은 손동작, 한 번만 등장하는 물체, 불안정한 요리명, 이상하거나 부자연스러운 local 명칭은 생략하십시오.
- 한 local observation의 구체성을 영상 전체의 사실로 승격하지 마십시오.
- event 수가 많다는 이유로 한 활동에 분량을 과도하게 배분하지 마십시오. 주요 activity 변화를 기준으로 균형 있게 다루십시오.
- 앞부분의 관찰이 많더라도 후반에 다른 주요 활동이 있으면 전체 흐름에 반드시 반영하십시오.
- SHORT와 DETAILED는 동일한 macro activity sequence를 가져야 합니다. 어느 한쪽에만 새로운 주요 활동을 추가하지 마십시오.
- 각 문장은 가능한 한 하나의 주요 활동 단계 또는 명확한 전환만 설명하십시오.
- 감정, 의도, 평가, 분석, 결론을 추가하지 마십시오.
- R01은 UNRESOLVED / NO_OBSERVATION입니다. 관측되지 않은 시작 장면을 만들지 마십시오.

Conflict 처리:
- Observation Set A와 Observation Set B 중 어느 한쪽도 winner로 선택하지 마십시오.
- 양쪽이 함께 지지하는 더 넓은 활동이 있을 때만 broad 표현을 사용하십시오.
- 공통 broad activity조차 확실하지 않으면 해당 세부사항을 Overview에서 생략하십시오.

출력 규칙:
- 자연스러운 한국어 보고서 문장만 작성하십시오.
- SHORT OVERVIEW는 정확히 4문장입니다.
- DETAILED OVERVIEW는 정확히 2개 단락이며, 각 단락은 2~4문장입니다.
- DETAILED는 SHORT와 같은 흐름을 조금 더 자연스럽게 설명하되 세부 목록으로 확장하지 마십시오.
- JSON, Markdown code fence, 번호, bullet, 추적 정보, event 식별자, source 식별자, 추가 설명을 출력하지 마십시오.
- 아래 두 heading은 철자와 순서를 그대로 사용하십시오.

출력 형식:
SHORT OVERVIEW

<정확히 4문장>

DETAILED OVERVIEW

<첫 번째 단락: 2~4문장>

<두 번째 단락: 2~4문장>

입력:
__GENERATION_INPUT_JSON__
'''
PROMPT_TEMPLATE_SHA256 = "064d3ea383a2785b33cf3b403ee72525c34c38a3c87ec5c630dac68ee1c0012e"

LOCAL_DETAIL_TERMS = (
    "치약", "감자 크루테크", "크림 카레", "potato", "blender",
    "toothpaste", "source_event", "event_id", "w01_e",
)


class PreviewError(RuntimeError):
    """Generated body violated the V2 preview contract."""


sha256_file = v1.sha256_file
sha256_text = v1.sha256_text
canonical = v1.canonical
build_generation_input = v1.build_generation_input


def render_prompt(generation_input: dict) -> str:
    return PROMPT_TEMPLATE.replace(
        "__GENERATION_INPUT_JSON__",
        json.dumps(generation_input, ensure_ascii=False, sort_keys=True,
                   indent=2))


def _sentences(text: str) -> list[str]:
    normalized = " ".join(text.split())
    matches = list(re.finditer(r"[^.!?]+[.!?](?=\s|$)", normalized))
    if not matches:
        return []
    remainder = normalized
    for match in reversed(matches):
        remainder = remainder[:match.start()] + remainder[match.end():]
    if remainder.strip():
        return []
    return [match.group(0).strip() for match in matches]


def sentence_count(text: str) -> int:
    return len(_sentences(text))


def parse_and_validate(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise PreviewError("OUTPUT_FORMAT: empty raw")
    text = raw.strip().replace("\r\n", "\n")
    lowered = text.lower()
    if ("```" in text or "claim" in lowered or "support_type" in lowered
            or "source_event" in lowered or re.search(r"\bOVC\d+\b", text)):
        raise PreviewError("OUTPUT_FORMAT: machine fields or extra format found")
    for term in LOCAL_DETAIL_TERMS:
        if term.lower() in lowered:
            raise PreviewError("LOCAL_DETAIL: unstable detail surfaced in Overview")
    if text.count("SHORT OVERVIEW") != 1 or text.count("DETAILED OVERVIEW") != 1:
        raise PreviewError("OUTPUT_FORMAT: exact headings required")
    short_heading, remainder = text.split("SHORT OVERVIEW", 1)
    if short_heading.strip():
        raise PreviewError("OUTPUT_FORMAT: text before SHORT OVERVIEW")
    short_text, detailed_text = remainder.split("DETAILED OVERVIEW", 1)
    short_sentences = _sentences(short_text)
    if len(short_sentences) != 4:
        raise PreviewError("SHORT_COUNT: exactly 4 sentences required")
    paragraphs = [row.strip() for row in re.split(r"\n\s*\n", detailed_text.strip())
                  if row.strip()]
    if len(paragraphs) != 2:
        raise PreviewError("DETAILED_COUNT: exactly 2 paragraphs required")
    for paragraph in paragraphs:
        if not 2 <= sentence_count(paragraph) <= 4:
            raise PreviewError("DETAILED_SENTENCE_COUNT: each paragraph needs 2~4 sentences")
    if any(re.match(r"^(?:[-*]|\d+[.)])\s", row)
           for row in short_sentences + paragraphs):
        raise PreviewError("OUTPUT_FORMAT: bullets or numbering forbidden")
    return {
        "schema": "wvr_overview_preview_v2_result",
        "event": EVENT,
        "short_overview": " ".join(short_sentences),
        "short_sentences": short_sentences,
        "detailed_overview": "\n\n".join(paragraphs),
        "detailed_paragraphs": paragraphs,
    }
