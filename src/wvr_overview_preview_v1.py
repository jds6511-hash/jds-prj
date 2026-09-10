"""Minimal contract for the one-shot WVR_OVERVIEW_PREVIEW_V1 text preview."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

EVENT = "WVR_OVERVIEW_PREVIEW_V1"
SOURCE_MAP_NAME = "conservative_event_map_v1.json"
SOURCE_MAP_SHA256 = "0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c"
SUBMISSION_SHA256 = "5732075871fd7902d52239cebcED28f9489a0f558dac67c61f5d2ca994e9cd7b".lower()

LLM_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
LLM_MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
LLM_DTYPE = "bfloat16"
LLM_ATTN_IMPLEMENTATION = "sdpa"
LLM_LOAD_4BIT = False
LLM_DO_SAMPLE = False
LLM_MAX_NEW_TOKENS = 4096

NEW_VLM_INFERENCE_ALLOWED = False
TRACK_A_INPUT_ALLOWED = False
ANALYSIS_ALLOWED = False
CONCLUSION_ALLOWED = False
HWPX_ALLOWED = False

PROMPT_NAME = "overview_preview_v1_prompt.txt"
RAW_NAME = "overview_preview_v1_raw.txt"
RECORD_NAME = "overview_preview_v1_record.json"
RESULT_NAME = "overview_preview_v1_result.json"
PACKET_NAME = "overview_preview_v1_packet.md"

PROMPT_TEMPLATE = r'''당신은 관찰 기록만으로 영상 전체의 Overview를 작성하는 text-only generator입니다.

아래 입력은 시간순으로 직렬화된 11개 region입니다. 한국어로만 작성하십시오.

작성 원칙:
- event log나 작은 행동의 나열이 아니라 영상 전체의 큰 활동 흐름을 자연스럽게 설명합니다.
- SHORT OVERVIEW는 3~5문장, DETAILED OVERVIEW는 1~3개 단락입니다.
- UNRESOLVED / NO_OBSERVATION 구간, 특히 R01에는 내용을 만들지 마십시오.
- CONFLICT에서는 Observation Set A나 B 중 하나를 사실로 선택하지 마십시오. 양측이 함께 지지하는 broad activity만 쓰거나 필요한 경우 짧게 불확실성을 표시하십시오.
- winner, preferred source, 원본 source/window의 정체를 추론하거나 언급하지 마십시오.
- 감정, 의도, 평가, 분석, 결론을 추가하지 마십시오.
- claim마다 실제 source_event_ids와 source_regions를 연결하십시오.
- CONFLICT_COMMON_DENOMINATOR claim은 관련 conflict block의 Observation Set A와 B에서 각각 최소 1개 event를 인용해야 합니다.
- 출력은 설명이나 Markdown fence 없이 아래 JSON object 하나만 반환하십시오.

출력 스키마:
{
  "short_overview": [
    {"sentence_id":"S01","text":"...","claim_ids":["OVC01"]}
  ],
  "detailed_overview": [
    {"paragraph_id":"D01","text":"...","claim_ids":["OVC01"]}
  ],
  "claim_trace": [
    {
      "claim_id":"OVC01",
      "claim":"...",
      "support_type":"STITCHABLE|CONFLICT_COMMON_DENOMINATOR|SINGLE_SOURCE",
      "source_event_ids":["..."],
      "source_regions":["R02"]
    }
  ]
}

입력:
__GENERATION_INPUT_JSON__
'''
PROMPT_TEMPLATE_SHA256 = "09a01e430f9cbe5521941dd0077061fc3c61bad08dd8f524ebc9b534e9d83cb9"

SUPPORT_BY_CLASS = {
    "STITCHABLE": "STITCHABLE",
    "SINGLE_SOURCE": "SINGLE_SOURCE",
    "CONFLICT": "CONFLICT_COMMON_DENOMINATOR",
}
ROLE_OR_OPENING_PATTERNS = (
    "분석", "결론", "의도", "감정", "평가", "좋은 결과", "나쁜 결과",
    "영상은 시작부터", "영상의 시작부터", "영상은 처음부터",
)


class PreviewError(RuntimeError):
    """Preview input or generated output violated the minimal contract."""


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


def _event(row: dict) -> dict:
    keys = ("event_id", "actor", "action", "object_or_state")
    event = {key: row.get(key) for key in keys}
    if any(not isinstance(value, str) or not value.strip()
           for value in event.values()):
        raise PreviewError("SOURCE_EVENT: missing frozen observation text")
    return event


def build_generation_input(document: dict) -> dict:
    if document.get("lineage_summary", {}).get("source_events_total") != 160:
        raise PreviewError("SOURCE_MAP: expected 160 source events")
    node_sets = {
        "single": {row["node_id"]: row for row in document["nodes"]["single_source"]},
        "stitch": {row["node_id"]: row for row in document["nodes"]["stitch_groups"]},
        "conflict": {row["node_id"]: row for row in document["nodes"]["conflict_blocks"]},
    }
    regions = []
    event_ids = set()
    for source_region in document["regions"]:
        region_id = source_region["region_id"]
        region_class = source_region["node_class"]
        if region_class == "UNRESOLVED":
            row = {"region_id": region_id, "region_class": region_class,
                   "status": "NO_OBSERVATION", "observations": []}
        elif region_class == "SINGLE_SOURCE":
            observations = []
            for node_id in source_region["node_ids"]:
                observations.extend(_event(event)
                                    for event in node_sets["single"][node_id]["events"])
            row = {"region_id": region_id, "region_class": region_class,
                   "observations": observations}
        elif region_class == "STITCHABLE":
            groups = []
            for node_id in source_region["node_ids"]:
                node = node_sets["stitch"][node_id]
                groups.append({"group_id": node_id,
                               "events": [_event(event)
                                          for event in node["ordered_members"]]})
            row = {"region_id": region_id, "region_class": region_class,
                   "groups": groups}
        elif region_class == "CONFLICT":
            blocks = []
            for node_id in source_region["node_ids"]:
                node = node_sets["conflict"][node_id]
                blocks.append({
                    "block_id": node_id,
                    "observation_sets": {
                        "A": [_event(event) for event in
                              node["observation_set_1"]["events"]],
                        "B": [_event(event) for event in
                              node["observation_set_2"]["events"]],
                    },
                })
            row = {"region_id": region_id, "region_class": region_class,
                   "blocks": blocks}
        else:
            raise PreviewError("SOURCE_MAP: unknown region class %r" % region_class)
        regions.append(row)
        event_ids.update(_region_event_ids(row))
    expected_regions = ["R%02d" % index for index in range(1, 12)]
    if [row["region_id"] for row in regions] != expected_regions:
        raise PreviewError("SOURCE_MAP: region order mismatch")
    if len(event_ids) != 160:
        raise PreviewError("SOURCE_MAP: expected 160 unique represented events")
    return {"schema": "wvr_overview_preview_v1_input",
            "source_event_count": len(event_ids), "regions": regions}


def _region_event_ids(region: dict) -> list[str]:
    if region["region_class"] == "SINGLE_SOURCE":
        return [row["event_id"] for row in region["observations"]]
    if region["region_class"] == "STITCHABLE":
        return [row["event_id"] for group in region["groups"]
                for row in group["events"]]
    if region["region_class"] == "CONFLICT":
        return [row["event_id"] for block in region["blocks"]
                for arm in ("A", "B")
                for row in block["observation_sets"][arm]]
    return []


def render_prompt(generation_input: dict) -> str:
    return PROMPT_TEMPLATE.replace(
        "__GENERATION_INPUT_JSON__", canonical(generation_input))


def _extract_json(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise PreviewError("OUTPUT_SCHEMA: empty raw output")
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        low, high = text.find("{"), text.rfind("}")
        if low < 0 or high <= low:
            raise PreviewError("OUTPUT_SCHEMA: JSON object not found")
        try:
            payload = json.loads(text[low:high + 1])
        except json.JSONDecodeError as exc:
            raise PreviewError("OUTPUT_SCHEMA: invalid JSON") from exc
    if not isinstance(payload, dict):
        raise PreviewError("OUTPUT_SCHEMA: top level must be object")
    return payload


def _nonempty_string(value, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PreviewError("OUTPUT_SCHEMA: non-empty %s required" % label)


def parse_and_validate(raw: str, generation_input: dict) -> dict:
    payload = _extract_json(raw)
    expected_top = {"short_overview", "detailed_overview", "claim_trace"}
    if set(payload) != expected_top:
        raise PreviewError("OUTPUT_SCHEMA: exact top-level fields required")
    short = payload["short_overview"]
    detailed = payload["detailed_overview"]
    traces = payload["claim_trace"]
    if not isinstance(short, list) or not 3 <= len(short) <= 5:
        raise PreviewError("OUTPUT_SCHEMA: SHORT OVERVIEW must have 3~5 sentences")
    if not isinstance(detailed, list) or not 1 <= len(detailed) <= 3:
        raise PreviewError("OUTPUT_SCHEMA: DETAILED OVERVIEW must have 1~3 paragraphs")
    if not isinstance(traces, list) or not traces:
        raise PreviewError("CLAIM_TRACE: at least one trace required")

    trace_index = {}
    used_claims = set()
    for row in traces:
        if not isinstance(row, dict) or set(row) != {
                "claim_id", "claim", "support_type",
                "source_event_ids", "source_regions"}:
            raise PreviewError("CLAIM_TRACE: exact trace fields required")
        claim_id = row["claim_id"]
        _nonempty_string(claim_id, "claim_id")
        _nonempty_string(row["claim"], "claim")
        if claim_id in trace_index or not re.fullmatch(r"OVC\d+", claim_id):
            raise PreviewError("CLAIM_TRACE: invalid or duplicate claim_id")
        trace_index[claim_id] = row

    for collection, id_key in ((short, "sentence_id"),
                               (detailed, "paragraph_id")):
        for row in collection:
            if not isinstance(row, dict) or set(row) != {id_key, "text", "claim_ids"}:
                raise PreviewError("OUTPUT_SCHEMA: exact overview unit fields required")
            _nonempty_string(row[id_key], id_key)
            _nonempty_string(row["text"], "overview text")
            if any(pattern in row["text"] for pattern in ROLE_OR_OPENING_PATTERNS):
                raise PreviewError("ROLE_OR_OPENING: prohibited generated assertion")
            claim_ids = row["claim_ids"]
            if not isinstance(claim_ids, list) or not claim_ids or \
                    any(claim_id not in trace_index for claim_id in claim_ids):
                raise PreviewError("CLAIM_TRACE: overview unit lacks valid trace")
            used_claims.update(claim_ids)
    if used_claims != set(trace_index):
        raise PreviewError("CLAIM_TRACE: every trace must support overview text")

    region_index = {row["region_id"]: row for row in generation_input["regions"]}
    event_region = {}
    conflict_arms = {}
    for region in generation_input["regions"]:
        for event_id in _region_event_ids(region):
            event_region[event_id] = region["region_id"]
        if region["region_class"] == "CONFLICT":
            conflict_arms[region["region_id"]] = [
                ({event["event_id"] for event in block["observation_sets"]["A"]},
                 {event["event_id"] for event in block["observation_sets"]["B"]})
                for block in region["blocks"]]

    for row in traces:
        event_ids = row["source_event_ids"]
        source_regions = row["source_regions"]
        if not isinstance(event_ids, list) or not event_ids or \
                not isinstance(source_regions, list) or not source_regions:
            raise PreviewError("CLAIM_SOURCE: non-empty sources required")
        if any(not isinstance(item, str) for item in event_ids + source_regions):
            raise PreviewError("CLAIM_SOURCE: source identifiers must be strings")
        if "R01" in source_regions:
            raise PreviewError("UNRESOLVED: R01 cannot support a claim")
        if any(event_id not in event_region for event_id in event_ids):
            raise PreviewError("CLAIM_SOURCE: unknown event")
        if any(region_id not in region_index for region_id in source_regions):
            raise PreviewError("CLAIM_SOURCE: unknown region")
        if any(event_region[event_id] not in source_regions for event_id in event_ids):
            raise PreviewError("CLAIM_SOURCE: event/region mismatch")
        classes = {region_index[region_id]["region_class"]
                   for region_id in source_regions}
        expected_supports = {SUPPORT_BY_CLASS.get(region_class)
                             for region_class in classes}
        if None in expected_supports or row["support_type"] not in expected_supports:
            raise PreviewError("CLAIM_SOURCE: support type/region mismatch")
        if row["support_type"] == "CONFLICT_COMMON_DENOMINATOR":
            cited = set(event_ids)
            for region_id in source_regions:
                if region_id not in conflict_arms:
                    continue
                if not any(cited & arm_a and cited & arm_b
                           for arm_a, arm_b in conflict_arms[region_id]):
                    raise PreviewError(
                        "CONFLICT_COMMON_DENOMINATOR: both observation arms required")
    return payload
