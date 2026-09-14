"""Quality-focused direct video-to-Overview Preview V2 contract."""
from __future__ import annotations

import json
import re

import wvr_video_overview_preview_v1 as v1

EVENT = "WVR_VIDEO_TO_OVERVIEW_PREVIEW_V2"
MODEL_ID = v1.MODEL_ID
MODEL_REVISION = v1.MODEL_REVISION
VIDEO_SHA256 = v1.VIDEO_SHA256
DTYPE = v1.DTYPE
ATTN_IMPLEMENTATION = v1.ATTN_IMPLEMENTATION
DEVICE = v1.DEVICE
DO_SAMPLE = False
NUM_BEAMS = 1
MAX_NEW_TOKENS = 1024

PLAN_NAME = "video_overview_v2_segments.json"
SUMMARIES_NAME = "video_overview_v2_segment_summaries.json"
TIMELINE_NAME = "video_overview_v2_compressed_timeline.json"
SYNTHESIS_PROMPT_NAME = "video_overview_v2_synthesis_prompt.txt"
OVERVIEW_RAW_NAME = "video_overview_v2_overview_raw.txt"
RESULT_NAME = "video_overview_v2_result.json"
PACKET_NAME = "video_overview_v2_packet.md"
RECORD_NAME = "video_overview_v2_record.json"

ACTIVITY_LABELS = (
    "음식 준비 및 조리",
    "식사",
    "의류 작업 및 수선",
    "포장 작업",
    "외출 준비",
    "이동",
    "구매 또는 둘러보기",
    "정리 작업",
    "기타 명확한 주요 활동",
    "불명확",
)

SEGMENT_PROMPT_TEMPLATE = r'''이 영상 구간을 직접 관찰하여 전체 영상의 흐름에 남길 큰 활동만 한국어로 분류하십시오.

출력 항목의 역할:
- BROAD_ACTIVITY: 화면에서 직접 보이는 큰 활동만 기록합니다.
- OBSERVED_CHANGE: 구간 안에서 큰 활동 종류가 실제로 달라질 때만 기록합니다.
- CONTEXT_INFERENCE: 화면 행동 자체가 아니라 상황을 해석해야 얻는 정보는 여기에만 기록합니다.
- UNCERTAINTY: 객체, 장소, 상황 또는 행동이 명확하지 않으면 기록합니다. 불확실성이 없을 때만 빈 배열로 둡니다.

BROAD_ACTIVITY 허용 label:
__ACTIVITY_LABELS__

규칙:
- BROAD_ACTIVITY는 시간순으로 1~2개 label만 사용하십시오.
- 실제로 관찰되지 않은 label을 만들지 마십시오.
- 개별 식재료, 세부 요리명, 소스명, 조리도구명, 작은 손동작, OCR 문자열, 불안정한 객체 이름을 기록하지 마십시오.
- 요리의 종류를 맞히지 말고 필요하면 "음식 준비 및 조리"로 압축하십시오.
- OBSERVED_CHANGE는 허용 label 사이의 큰 전환만 "label → label" 형식으로 기록하십시오.
- 장소의 정체, 일정, 직업, 의료 상황, 계획 또는 의도처럼 해석이 필요한 내용은 BROAD_ACTIVITY나 OBSERVED_CHANGE에 넣지 마십시오.
- 불확실한 세부사항을 확정하지 마십시오.
- 감정, 평가, 분석, 결론을 추가하지 마십시오.
- Markdown fence와 추가 설명 없이 아래 네 field의 JSON object 하나만 출력하십시오.

{
  "BROAD_ACTIVITY": ["허용 label"],
  "OBSERVED_CHANGE": [],
  "CONTEXT_INFERENCE": [],
  "UNCERTAINTY": []
}
'''

SYNTHESIS_PROMPT_TEMPLATE = r'''아래 자료는 원본 영상 관찰을 시간순 broad activity run으로 중복 압축한 결과입니다.
오직 제공된 BROAD_ACTIVITY_SEQUENCE와 OBSERVED_CHANGES만 사용하여 자연스러운 한국어 Overview를 작성하십시오.

질문:
"이 영상에서는 전체적으로 어떤 주요 활동들이 어떤 순서로 이어지는가?"

규칙:
- broad activity의 순서와 주요 전환을 빠짐없이 설명하십시오.
- 세부 요리명, recipe, 식재료, 소스, 도구 또는 작은 행동을 추가하지 마십시오.
- 사람의 상황, 일정, 직업, 의료 정보, 계획, 감정, 의도를 추론하지 마십시오.
- 분석, 평가, 결론을 작성하지 마십시오.
- SHORT와 DETAILED는 같은 activity sequence를 유지하십시오.
- SHORT는 자연스러운 약 2~5문장으로 작성하되 문장 수보다 흐름 보존을 우선하십시오.
- DETAILED는 1~3개 단락으로 작성하고 event log처럼 나열하지 마십시오.
- 구간 번호, window 또는 phase 식별자를 본문에 노출하지 마십시오.
- Markdown fence, JSON, bullet 또는 추가 설명 없이 두 heading과 본문만 출력하십시오.

출력 형식:
SHORT OVERVIEW

<실제 본문>

DETAILED OVERVIEW

<실제 본문>

압축 입력:
__SYNTHESIS_INPUT_JSON__
'''

SEGMENT_KEYS = {
    "BROAD_ACTIVITY", "OBSERVED_CHANGE", "CONTEXT_INFERENCE", "UNCERTAINTY"
}


class PreviewError(RuntimeError):
    """Generated V2 artifact violated the minimal quality-path contract."""


sha256_file = v1.sha256_file
sha256_text = v1.sha256_text
canonical = v1.canonical
segments = v1.segments


def segment_prompt() -> str:
    labels = "\n".join("- %s" % label for label in ACTIVITY_LABELS)
    return SEGMENT_PROMPT_TEMPLATE.replace("__ACTIVITY_LABELS__", labels)


def _extract_json(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise PreviewError("SEGMENT_SCHEMA: empty output")
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
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
        raise PreviewError("SEGMENT_SCHEMA: object required")
    return value


def _text_list(value, field: str) -> list[str]:
    if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value):
        raise PreviewError("SEGMENT_SCHEMA: %s must contain text" % field)
    return [item.strip() for item in value]


def parse_segment(raw: str, segment_id: str) -> dict:
    value = _extract_json(raw)
    if set(value) != SEGMENT_KEYS:
        raise PreviewError("SEGMENT_SCHEMA: exact four fields required")
    activities = _text_list(value["BROAD_ACTIVITY"], "BROAD_ACTIVITY")
    if not activities or len(set(activities)) != len(activities):
        raise PreviewError("BROAD_ACTIVITY: unique canonical labels required")
    if any(activity not in ACTIVITY_LABELS for activity in activities):
        raise PreviewError("BROAD_ACTIVITY: non-canonical label")
    changes = _text_list(value["OBSERVED_CHANGE"], "OBSERVED_CHANGE")
    for change in changes:
        parts = [part.strip() for part in change.split("→")]
        if len(parts) != 2 or any(part not in ACTIVITY_LABELS for part in parts):
            raise PreviewError("OBSERVED_CHANGE: canonical label transition required")
    context = _text_list(value["CONTEXT_INFERENCE"], "CONTEXT_INFERENCE")
    uncertainty = _text_list(value["UNCERTAINTY"], "UNCERTAINTY")
    if "불명확" in activities and not uncertainty:
        raise PreviewError("UNCERTAINTY: required when activity is unclear")
    return {
        "segment_id": segment_id,
        "BROAD_ACTIVITY": activities,
        "OBSERVED_CHANGE": changes,
        "CONTEXT_INFERENCE": context,
        "UNCERTAINTY": uncertainty,
    }


def _dedup(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def compress_activity_timeline(summaries: list[dict]) -> dict:
    runs = []
    previous_activities = set()
    changes = []
    for summary in summaries:
        segment_id = summary["segment_id"]
        activities = _dedup(summary["BROAD_ACTIVITY"])
        for activity in activities:
            if activity in previous_activities:
                for run in reversed(runs):
                    if run["broad_activity"] == activity:
                        run["last_segment"] = segment_id
                        break
            else:
                runs.append({
                    "phase_id": "P%02d" % (len(runs) + 1),
                    "broad_activity": activity,
                    "first_segment": segment_id,
                    "last_segment": segment_id,
                })
        previous_activities = set(activities)
        changes.extend(summary["OBSERVED_CHANGE"])
    return {"activity_runs": runs, "observed_changes": _dedup(changes)}


def synthesis_input(compressed: dict) -> dict:
    return {
        "BROAD_ACTIVITY_SEQUENCE": [
            {"order": index, "activity": run["broad_activity"]}
            for index, run in enumerate(compressed["activity_runs"], start=1)
        ],
        "OBSERVED_CHANGES": list(compressed["observed_changes"]),
    }


def synthesis_prompt(compressed: dict) -> str:
    payload = json.dumps(synthesis_input(compressed), ensure_ascii=False,
                         sort_keys=True, indent=2)
    return SYNTHESIS_PROMPT_TEMPLATE.replace("__SYNTHESIS_INPUT_JSON__", payload)


def parse_overview(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise PreviewError("OVERVIEW_FORMAT: empty output")
    text = raw.strip().replace("\r\n", "\n")
    if text.count("SHORT OVERVIEW") != 1 or text.count("DETAILED OVERVIEW") != 1:
        raise PreviewError("OVERVIEW_FORMAT: exact headings required")
    prefix, remainder = text.split("SHORT OVERVIEW", 1)
    if prefix.strip():
        raise PreviewError("OVERVIEW_FORMAT: text before heading")
    short, detailed = remainder.split("DETAILED OVERVIEW", 1)
    short, detailed = short.strip(), detailed.strip()
    if not short or not detailed:
        raise PreviewError("OVERVIEW_FORMAT: both bodies required")
    paragraphs = [row.strip() for row in re.split(r"\n\s*\n", detailed)
                  if row.strip()]
    return {"short_overview": short, "detailed_overview": detailed,
            "detailed_paragraphs": paragraphs}


def excluded_contexts(summaries: list[dict]) -> list[dict]:
    return [{"segment_id": row["segment_id"], "items": row["CONTEXT_INFERENCE"]}
            for row in summaries if row["CONTEXT_INFERENCE"]]


def uncertainties(summaries: list[dict]) -> list[dict]:
    return [{"segment_id": row["segment_id"], "items": row["UNCERTAINTY"]}
            for row in summaries if row["UNCERTAINTY"]]


def packet_markdown(result: dict, record: dict) -> str:
    overview = result["overview"]
    lines = [EVENT, "", "SHORT OVERVIEW", "", overview["short_overview"], "",
             "DETAILED OVERVIEW", "", overview["detailed_overview"], "",
             "COMPRESSED ACTIVITY TIMELINE", ""]
    for run in result["compressed_timeline"]["activity_runs"]:
        lines.append("%s  %s~%s  %s" % (
            run["phase_id"], run["first_segment"], run["last_segment"],
            run["broad_activity"]))
    lines += ["", "CONTEXT INFERENCES EXCLUDED FROM OVERVIEW", ""]
    contexts = result["context_inferences_excluded"]
    lines.extend("%s  %s" % (row["segment_id"], " / ".join(row["items"]))
                 for row in contexts)
    if not contexts:
        lines.append("없음")
    lines += ["", "UNCERTAINTIES", ""]
    uncertain = result["uncertainties"]
    lines.extend("%s  %s" % (row["segment_id"], " / ".join(row["items"]))
                 for row in uncertain)
    if not uncertain:
        lines.append("없음")
    lines += ["", "TECHNICAL NOTES", "",
              "- segment inference count: %d" % record["segment_inference_count"],
              "- synthesis inference count: %d" % record["synthesis_inference_count"],
              "- retry count: %d" % record["retry_count"],
              "- raw persisted: true",
              "- Track A used: false",
              "- Event Map used: false", "", "STATUS", record["status"], ""]
    return "\n".join(lines)
