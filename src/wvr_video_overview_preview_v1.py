"""Core contract for the direct video-to-Overview quality preview."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import wvr_contract as contract
import wvr_shadow_v1 as shadow

EVENT = "WVR_VIDEO_TO_OVERVIEW_PREVIEW_V1"
MODEL_ID = contract.MODEL_ID
MODEL_REVISION = contract.MODEL_REVISION
VIDEO_SHA256 = "ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc"
DTYPE = contract.DTYPE
ATTN_IMPLEMENTATION = contract.ATTN_IMPLEMENTATION
DEVICE = contract.DEVICE
DO_SAMPLE = False
NUM_BEAMS = 1
MAX_NEW_TOKENS = 1024
RETRY_COUNT = 0

PLAN_NAME = "video_overview_v1_segments.json"
SUMMARIES_NAME = "video_overview_v1_segment_summaries.json"
SYNTHESIS_PROMPT_NAME = "video_overview_v1_synthesis_prompt.txt"
OVERVIEW_RAW_NAME = "video_overview_v1_overview_raw.txt"
RESULT_NAME = "video_overview_v1_result.json"
PACKET_NAME = "video_overview_v1_packet.md"
RECORD_NAME = "video_overview_v1_record.json"

SEGMENT_PROMPT_TEMPLATE = r'''이 영상 구간을 직접 관찰하고, 전체 영상 Overview에 남길 가치가 있는 큰 활동만 한국어로 요약하십시오.

규칙:
- local event를 세세하게 나열하지 마십시오.
- 개별 재료, 작은 도구, 짧은 손동작, 한두 프레임의 객체, 불안정한 객체 분류나 세부 명칭은 전체 흐름에 필수적이지 않으면 생략하십시오.
- 작은 행동 여러 개가 하나의 넓은 활동이면 broad activity 하나로 압축하십시오.
- 주요 activity 종류, 작업 또는 장소 맥락의 중요한 변화는 보존하십시오.
- 확실하지 않은 object/action을 사실로 확정하지 말고 uncertain_or_ambiguous에 짧게 기록하십시오.
- 감정, 의도, 평가, 분석, 결론을 추가하지 마십시오.
- Markdown fence나 추가 설명 없이 JSON object 하나만 출력하십시오.

출력 형식:
{
  "segment_id": "__SEGMENT_ID__",
  "broad_activities": ["..."],
  "important_changes": ["..."],
  "notable_context": ["..."],
  "uncertain_or_ambiguous": ["..."]
}
'''

SYNTHESIS_PROMPT_TEMPLATE = r'''아래 자료는 원본 영상의 시간순 구간별 broad summary입니다. 이 자료만 사용하여 영상 전체의 자연스러운 한국어 Overview를 작성하십시오.

작성 질문:
"이 영상은 전체적으로 어떤 주요 활동들이 어떤 순서로 진행되는가?"

규칙:
- 겹치는 인접 구간에서 반복된 같은 활동은 하나의 broad phase로 합치십시오.
- 서로 다른 활동을 억지로 합치지 마십시오.
- 구간 번호나 구간 경계를 본문에 노출하지 마십시오.
- 주요 activity 변화와 작업·장소 맥락의 큰 변화를 균형 있게 반영하십시오.
- 개별 재료, 작은 도구, 손동작, 불안정한 세부 명칭을 나열하지 마십시오.
- uncertain_or_ambiguous의 세부사항은 전체 흐름에 중요하지 않으면 생략하십시오.
- 불확실한 내용을 확정하지 마십시오.
- SHORT와 DETAILED는 동일한 주요 활동 순서를 유지하십시오.
- event log, 감정, 의도, 평가, 분석, 결론을 작성하지 마십시오.
- 한국어 보고서에 바로 넣을 수 있는 자연스러운 문장으로 작성하십시오.
- Markdown fence, JSON, bullet, 추가 설명 없이 지정된 두 heading과 본문만 출력하십시오.

출력 형식:
SHORT OVERVIEW

<전체 흐름 중심 3~5문장>

DETAILED OVERVIEW

<Short와 동일한 흐름의 2~3개 단락>

시간순 broad summaries:
__SEGMENT_SUMMARIES_JSON__
'''

SEGMENT_KEYS = {
    "segment_id", "broad_activities", "important_changes",
    "notable_context", "uncertain_or_ambiguous",
}


class PreviewError(RuntimeError):
    """A generated artifact violated the minimal preview contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def segments() -> list[dict]:
    rows = []
    for index, window in enumerate(shadow.windows(), start=1):
        rows.append({
            "segment_id": "S%02d" % index,
            "start_sec": float(window["start_sec"]),
            "end_sec": float(window["end_sec"]),
            "frame_times": [float(value) for value in shadow.frame_times(window)],
        })
    return rows


def segment_prompt(segment_id: str) -> str:
    return SEGMENT_PROMPT_TEMPLATE.replace("__SEGMENT_ID__", segment_id)


def _extract_json(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise PreviewError("SEGMENT_SCHEMA: empty output")
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        low, high = text.find("{"), text.rfind("}")
        if low < 0 or high <= low:
            raise PreviewError("SEGMENT_SCHEMA: JSON object not found")
        try:
            value = json.loads(text[low:high + 1])
        except json.JSONDecodeError as exc:
            raise PreviewError("SEGMENT_SCHEMA: invalid JSON") from exc
    if not isinstance(value, dict):
        raise PreviewError("SEGMENT_SCHEMA: top-level object required")
    return value


def parse_segment(raw: str, expected_segment_id: str) -> dict:
    value = _extract_json(raw)
    if set(value) != SEGMENT_KEYS:
        raise PreviewError("SEGMENT_SCHEMA: exact broad-summary fields required")
    if value["segment_id"] != expected_segment_id:
        raise PreviewError("SEGMENT_SCHEMA: segment_id mismatch")
    for key in SEGMENT_KEYS - {"segment_id"}:
        items = value[key]
        if not isinstance(items, list):
            raise PreviewError("SEGMENT_SCHEMA: %s must be a list" % key)
        if any(not isinstance(item, str) or not item.strip() for item in items):
            raise PreviewError("SEGMENT_SCHEMA: %s contains empty text" % key)
    if not value["broad_activities"]:
        raise PreviewError("SEGMENT_SCHEMA: broad_activities cannot be empty")
    return value


def synthesis_prompt(summaries: list[dict]) -> str:
    payload = json.dumps(summaries, ensure_ascii=False, sort_keys=True,
                         indent=2)
    return SYNTHESIS_PROMPT_TEMPLATE.replace(
        "__SEGMENT_SUMMARIES_JSON__", payload)


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


def parse_overview(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise PreviewError("OVERVIEW_FORMAT: empty output")
    text = raw.strip().replace("\r\n", "\n")
    if "```" in text or text.count("SHORT OVERVIEW") != 1 \
            or text.count("DETAILED OVERVIEW") != 1:
        raise PreviewError("OVERVIEW_FORMAT: exact headings required")
    prefix, remainder = text.split("SHORT OVERVIEW", 1)
    if prefix.strip():
        raise PreviewError("OVERVIEW_FORMAT: text before heading")
    short_text, detailed_text = remainder.split("DETAILED OVERVIEW", 1)
    short_sentences = _sentences(short_text)
    if not 3 <= len(short_sentences) <= 5:
        raise PreviewError("SHORT_COUNT: 3~5 sentences required")
    paragraphs = [row.strip() for row in re.split(r"\n\s*\n", detailed_text.strip())
                  if row.strip()]
    if not 2 <= len(paragraphs) <= 3:
        raise PreviewError("DETAILED_COUNT: 2~3 paragraphs required")
    if any(not _sentences(paragraph) for paragraph in paragraphs):
        raise PreviewError("DETAILED_FORMAT: complete sentences required")
    return {
        "short_overview": " ".join(short_sentences),
        "short_sentences": short_sentences,
        "detailed_overview": "\n\n".join(paragraphs),
        "detailed_paragraphs": paragraphs,
    }


def packet_markdown(result: dict, record: dict) -> str:
    overview = result["overview"]
    lines = [EVENT, "", "SHORT OVERVIEW", ""]
    lines.extend(overview["short_sentences"])
    lines += ["", "DETAILED OVERVIEW", "",
              "\n\n".join(overview["detailed_paragraphs"]), "",
              "BROAD SEGMENT SUMMARIES", ""]
    labels = (
        ("broad_activities", "broad activities"),
        ("important_changes", "important changes"),
        ("notable_context", "notable context"),
        ("uncertain_or_ambiguous", "uncertain or ambiguous"),
    )
    for summary in result["segment_summaries"]:
        lines += [summary["segment_id"], ""]
        for key, label in labels:
            text = " / ".join(summary[key]) if summary[key] else "없음"
            lines.append("- %s: %s" % (label, text))
        lines.append("")
    provenance = record.get("runtime_provenance") or {}
    lines += ["TECHNICAL NOTES", "",
              "- VLM model: %s" % MODEL_ID,
              "- revision: %s" % MODEL_REVISION,
              "- segment count: %d" % record["segment_count"],
              "- inference count: %d" % record["inference_count"],
              "- retry count: %d" % record["retry_count"],
              "- GPU: %s" % provenance.get("device_name", "UNKNOWN"),
              "- Track A used: false", "", "STATUS", record["status"], ""]
    return "\n".join(lines)
