"""Blinded semantic boundary-candidate contract for the WVR shadow event.

This module performs deterministic construction and validation only.  Model
loading and filesystem writes live in ``scripts/wvr_bcand_*.py``.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

import wvr_chapter_v1 as v1
import wvr_conservative_map_v1 as cmap

EVENT = "WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1"
PREREG = ("docs/preregistration/"
          "WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1_2026-09-10.md")
SOURCE_MAP_NAME = v1.SOURCE_MAP_NAME
SOURCE_MAP_SHA256 = v1.SOURCE_MAP_SHA256
EXPECTED_SOURCE_EVENT_COUNT = cmap.EXPECTED_SOURCE_EVENT_COUNT
EXPECTED_CANDIDATE_COUNT = 144
VIDEO_START_SEC = cmap.VIDEO_START_SEC
VIDEO_END_SEC = cmap.VIDEO_END_SEC
CONTEXT_WINDOW_SEC = 30.0
BATCH_SIZE = 8
EXPECTED_BATCH_COUNT = 18
BLIND_SALT = EVENT + "|OBSERVATION_SET_V1"

LLM_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
LLM_MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
LLM_DTYPE = "bfloat16"
LLM_ATTN_IMPLEMENTATION = "sdpa"
LLM_LOAD_4BIT = False
LLM_DO_SAMPLE = False
LLM_MAX_NEW_TOKENS = 2048
GENERATION_ATTEMPTS = 1

CHAPTER_GENERATION_ALLOWED = False
TITLE_GENERATION_ALLOWED = False
SUMMARY_GENERATION_ALLOWED = False
OVERVIEW_GENERATION_ALLOWED = False
ANALYSIS_GENERATION_ALLOWED = False
CONCLUSION_GENERATION_ALLOWED = False
HWPX_GENERATION_ALLOWED = False
TRACK_A_INPUT_ALLOWED = False
NEW_VLM_INFERENCE_ALLOWED = False
EVENT_MAP_REBUILD_ALLOWED = False
LOCAL_EVENT_REEXTRACTION_ALLOWED = False
CONFLICT_RESOLUTION_ALLOWED = False
PREFERRED_SOURCE_ALLOWED = False
EVENT_TEXT_MUTATION_ALLOWED = False
MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED = False
TIMESTAMP_IN_PACKET_ALLOWED = False
GEOMETRY_IN_PACKET_ALLOWED = False
PRIOR_CHAPTER_INPUT_ALLOWED = False
RETRY_ALLOWED = False
VERDICT_BY_EXECUTOR = False
PRODUCTION_PROMOTION_ALLOWED = False
PROPOSER_LLM_ALLOWED = True
FLAGS = (
    "CHAPTER_GENERATION_ALLOWED", "TITLE_GENERATION_ALLOWED",
    "SUMMARY_GENERATION_ALLOWED", "OVERVIEW_GENERATION_ALLOWED",
    "ANALYSIS_GENERATION_ALLOWED", "CONCLUSION_GENERATION_ALLOWED",
    "HWPX_GENERATION_ALLOWED", "TRACK_A_INPUT_ALLOWED",
    "NEW_VLM_INFERENCE_ALLOWED", "EVENT_MAP_REBUILD_ALLOWED",
    "LOCAL_EVENT_REEXTRACTION_ALLOWED", "CONFLICT_RESOLUTION_ALLOWED",
    "PREFERRED_SOURCE_ALLOWED", "EVENT_TEXT_MUTATION_ALLOWED",
    "MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED",
    "TIMESTAMP_IN_PACKET_ALLOWED", "GEOMETRY_IN_PACKET_ALLOWED",
    "PRIOR_CHAPTER_INPUT_ALLOWED", "RETRY_ALLOWED", "VERDICT_BY_EXECUTOR",
    "PRODUCTION_PROMOTION_ALLOWED",
)

STRONG_TRANSITION_CANDIDATE = "STRONG_TRANSITION_CANDIDATE"
WEAK_TRANSITION_CANDIDATE = "WEAK_TRANSITION_CANDIDATE"
NO_CHAPTER_TRANSITION = "NO_CHAPTER_TRANSITION"
AMBIGUOUS = "AMBIGUOUS"
PROPOSALS = (STRONG_TRANSITION_CANDIDATE, WEAK_TRANSITION_CANDIDATE,
             NO_CHAPTER_TRANSITION, AMBIGUOUS)
REVIEWER_VERDICTS = ("CHAPTER_BOUNDARY", "NOT_CHAPTER_BOUNDARY", "UNRESOLVED")
NOT_ADJUDICATED = "NOT_ADJUDICATED"
EXECUTOR_STATE = "EXECUTED / REVIEW_PENDING"
FINAL_VERDICT_VOCABULARY_LINE = (
    "BOUNDARY_CANDIDATE_SHADOW_PASS / HOLD / INCONCLUSIVE")
TIME_FIELDS = ("start_sec", "end_sec", "boundary_sec", "timestamp", "time_sec")
FORBIDDEN_PROMPT_STRINGS = ("food preparation", "eating", "sewing",
                            "gift wrapping", "clothing", "400 sec",
                            "v1 chapter sequence")

PROPOSER_PROMPT_V1 = """You assess material changes in broad activity or task.

For each opaque candidate, compare BEFORE and AFTER observations. Choose one
proposal label. A strong proposal requires clear evidence of a broad material
change. A weak proposal has limited evidence of change. Use NO_CHAPTER_TRANSITION
when the broad activity continues. Use AMBIGUOUS when observations differ or
are insufficient. Do not choose among alternative observation sets.

Allowed proposal labels:
STRONG_TRANSITION_CANDIDATE
WEAK_TRANSITION_CANDIDATE
NO_CHAPTER_TRANSITION
AMBIGUOUS

Return JSON only with this shape and no additional fields:
{"candidates":[{"candidate_id":"Cxxx","proposal":"LABEL","before_activity":"TEXT","after_activity":"TEXT","rationale":"TEXT"}]}

OBSERVATIONS
%(blocks)s
END OBSERVATIONS
"""


class CandidateError(RuntimeError):
    """The frozen boundary-candidate contract was violated."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PROMPT_TEMPLATE_SHA256 = (
    "7782ebb4925d924592c115c7664d6f54c49ba9a61667100f2cd31be6e0f5aa49")


def canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)


def assert_flags_closed() -> None:
    for name in FLAGS:
        if globals()[name] is not False:
            raise CandidateError("CONFIG_MISMATCH: prohibited flag open: %s" % name)
    if PROPOSER_LLM_ALLOWED is not True:
        raise CandidateError("CONFIG_MISMATCH: proposer LLM must be enabled")


def source_events(document: dict) -> list[dict]:
    if EVENT_TEXT_MUTATION_ALLOWED:
        raise CandidateError("CONFIG_MISMATCH: source text mutation enabled")
    index = {}
    for row in cmap.all_members(document):
        index.setdefault(row["event_id"], {
            "event_id": row["event_id"],
            "source_window": row["source_window"],
            "start_sec": float(row["original_start"]),
            "end_sec": float(row["original_end"]),
            "actor": row["actor"],
            "action": row["action"],
            "object_or_state": row["object_or_state"],
        })
    rows = sorted(index.values(), key=lambda row: (row["start_sec"],
                                                    row["event_id"]))
    if len(rows) != EXPECTED_SOURCE_EVENT_COUNT:
        raise CandidateError("CONFIG_MISMATCH: source event count %d" % len(rows))
    if any(row["source_window"] in cmap.INVALID_SOURCE_WINDOWS for row in rows):
        raise CandidateError("CONFIG_MISMATCH: invalid source event included")
    return rows


def _overlap(low: float, high: float, start: float, end: float) -> float:
    return max(0.0, min(high, end) - max(low, start))


def events_between(events: list[dict], start: float, end: float) -> list[dict]:
    return sorted((row for row in events
                   if _overlap(start, end, row["start_sec"], row["end_sec"]) > 0),
                  key=lambda row: (row["start_sec"], row["event_id"]))


def candidate_times(events: list[dict]) -> list[float]:
    assert_flags_closed()
    rows = sorted({round(float(row["start_sec"]), 3) for row in events
                   if VIDEO_START_SEC < float(row["start_sec"]) < VIDEO_END_SEC})
    if len(rows) != EXPECTED_CANDIDATE_COUNT:
        raise CandidateError("CONFIG_MISMATCH: candidate count %d" % len(rows))
    return rows


def blind_ids(times: list[float]) -> list[dict]:
    keyed = sorted((sha256_text("%s|%s|%.3f" %
                                (EVENT, SOURCE_MAP_SHA256, float(value))),
                    float(value)) for value in times)
    return [{"candidate_id": "C%03d" % (index + 1),
             "boundary_sec": value, "blind_key_sha256": key}
            for index, (key, value) in enumerate(keyed)]


def set_labels(candidate_id: str, windows: list[str]) -> dict[str, str]:
    ordered = sorted(set(windows))
    if len(ordered) < 2:
        return {}
    joined = "+".join(ordered)
    keyed = sorted((sha256_text("%s|%s|%s|%s" %
                                (BLIND_SALT, candidate_id, joined, window)),
                    window) for window in ordered)
    return {window: chr(ord("A") + index)
            for index, (_, window) in enumerate(keyed)}


def _side(events: list[dict], candidate_id: str) -> dict:
    windows = sorted({row["source_window"] for row in events})
    labels = set_labels(candidate_id, windows)
    ordered = sorted(windows, key=lambda value: labels.get(value, ""))
    sets = []
    for window in ordered:
        rows = [dict(row) for row in events if row["source_window"] == window]
        sets.append({"label": labels.get(window, ""),
                     "source_window": window,
                     "event_ids": [row["event_id"] for row in rows],
                     "events": rows})
    return {"empty": not events, "windows": windows, "sets": sets}


def _in_conflict(document: dict, value: float) -> bool:
    return any(float(row["start_sec"]) <= value < float(row["end_sec"])
               for row in document["nodes"]["conflict_blocks"])


def build_candidates(events: list[dict], document: dict) -> list[dict]:
    assert_flags_closed()
    if PRIOR_CHAPTER_INPUT_ALLOWED:
        raise CandidateError("CONFIG_MISMATCH: prior chapter input enabled")
    rows = []
    for assigned in blind_ids(candidate_times(events)):
        value = assigned["boundary_sec"]
        before_events = events_between(
            events, max(VIDEO_START_SEC, value - CONTEXT_WINDOW_SEC), value)
        after_events = events_between(
            events, value, min(VIDEO_END_SEC, value + CONTEXT_WINDOW_SEC))
        rows.append({
            **assigned,
            "before_event_ids": [row["event_id"] for row in before_events],
            "after_event_ids": [row["event_id"] for row in after_events],
            "before": _side(before_events, assigned["candidate_id"]),
            "after": _side(after_events, assigned["candidate_id"]),
            "in_conflict_block": _in_conflict(document, value),
        })
    return rows


def _event_line(row: dict) -> str:
    return "%s | %s | %s" % (row["actor"], row["action"],
                              row["object_or_state"])


def _render_side(name: str, side: dict) -> list[str]:
    lines = [name]
    if side["empty"]:
        return lines + ["(no observation recorded on this side)"]
    for group in side["sets"]:
        if group["label"]:
            lines.append("Observation Set %s" % group["label"])
        lines.extend(_event_line(row) for row in group["events"])
    return lines


def render_block(candidate: dict) -> str:
    assert_flags_closed()
    if TIMESTAMP_IN_PACKET_ALLOWED or GEOMETRY_IN_PACKET_ALLOWED:
        raise CandidateError("CONFIG_MISMATCH: blinded packet leakage enabled")
    lines = ["Candidate %s" % candidate["candidate_id"]]
    lines.extend(_render_side("BEFORE", candidate["before"]))
    lines.extend(_render_side("AFTER", candidate["after"]))
    return "\n".join(lines)


def leakage_audit(texts: list[str], events: list[dict],
                  candidates: list[dict]) -> dict:
    text = "\n".join(texts)
    violations = []
    geometry = (r"\bW\d{2}\b", r"\bR\d{2}\b", r"\bCH\d{2}\b",
                r"\bsource_window(?:_id)?\b", r"\bwindow_id\b",
                r"\bregion_(?:id|class|boundary)\b",
                r"\bchapter_id\b", r"\bprior_chapter\b",
                r"\bgrid_(?:24s|48s)\b",
                r"\b(?:earlier|later)_window\b",
                r"\b(?:24|48)-second grid\b")
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in geometry):
        violations.append("GEOMETRY_LEAKAGE")
    event_ids = [row["event_id"] for row in events]
    if any(value in text for value in event_ids):
        violations.append("EVENT_ID_LEAKAGE")
    time_metadata = (
        r"\b(?:start_sec|end_sec|boundary_sec|timestamp|time_sec)\b",
        r'["\'](?:time|start|end)["\']\s*:',
        r"(?<![\w.])\d+\.\d+(?![\w.])",
        r"\b\d+(?:\.\d+)?\s*(?:s|sec|secs|second|seconds)\b",
        r"\b\d{1,2}:\d{2}(?::\d{2})?\b",
        r"\bmove\s+the\s+boundary\s+start\s+time\b",
        r"\b(?:select|choose|create|move)\b[^\n]*\btimestamp\b",
    )
    if any(re.search(pattern, text, flags=re.IGNORECASE)
           for pattern in time_metadata):
        violations.append("TIMESTAMP_LEAKAGE")
    prior = ("chapter title", "chapter summary", "dominant_activities",
             "prior chapter", "v1 chapter")
    if any(value in text.lower() for value in prior):
        violations.append("PRIOR_CHAPTER_LEAKAGE")
    conflict_authority = (
        r"\bpreferred(?:\s+source)?\b", r"\bwinner\b", r"\btruth\b",
        r"\b(?:more|most)\s+reliable\b", r"\breliability\s+ranking\b",
    )
    if any(re.search(pattern, text, flags=re.IGNORECASE)
           for pattern in conflict_authority):
        violations.append("CONFLICT_RESOLUTION_VIOLATION")
    candidate_order = re.findall(r"C\d{3}", text)
    unique_order = list(dict.fromkeys(candidate_order))
    time_order = [row["candidate_id"] for row in
                  sorted(candidates, key=lambda row: row["boundary_sec"])]
    return {
        "violations": sorted(set(violations)),
        "candidate_id_order_differs_from_time_order": unique_order != time_order,
        "candidate_id_count": len(set(candidate_order)),
    }


def batches(candidates: list[dict]) -> list[dict]:
    if len(candidates) != EXPECTED_CANDIDATE_COUNT:
        raise CandidateError("CONFIG_MISMATCH: candidate count")
    rows = []
    for offset in range(0, len(candidates), BATCH_SIZE):
        group = candidates[offset:offset + BATCH_SIZE]
        rows.append({"batch_id": "B%02d" % (len(rows) + 1),
                     "candidate_ids": [row["candidate_id"] for row in group]})
    if len(rows) != EXPECTED_BATCH_COUNT or any(
            len(row["candidate_ids"]) != BATCH_SIZE for row in rows):
        raise CandidateError("CONFIG_MISMATCH: batch construction")
    return rows


def render_prompt(candidates: list[dict]) -> str:
    blocks = "\n\n".join(render_block(row) for row in candidates)
    return PROPOSER_PROMPT_V1 % {"blocks": blocks}


def extract_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise CandidateError("PARSE_FAILURE: JSON object not found")
    try:
        payload = json.loads(raw[start:end + 1])
    except (TypeError, json.JSONDecodeError) as error:
        raise CandidateError("PARSE_FAILURE: %s" % error) from error
    if not isinstance(payload, dict):
        raise CandidateError("PARSE_FAILURE: top level is not an object")
    return payload


def parse_batch(payload: dict, expected_ids: list[str]) -> dict[str, dict]:
    if set(payload) != {"candidates"} or not isinstance(payload["candidates"], list):
        raise CandidateError("SCHEMA_VIOLATION: top-level fields")
    required = {"candidate_id", "proposal", "before_activity",
                "after_activity", "rationale"}
    rows = payload["candidates"]
    ids = [row.get("candidate_id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or Counter(ids) != Counter(expected_ids):
        raise CandidateError("CANDIDATE_SET_MISMATCH")
    result = {}
    for row in rows:
        if set(row) != required:
            raise CandidateError("SCHEMA_VIOLATION: candidate fields")
        if row["proposal"] not in PROPOSALS:
            raise CandidateError("VOCABULARY_VIOLATION: %r" % row["proposal"])
        if any(not isinstance(row[name], str) or not row[name].strip()
               for name in required):
            raise CandidateError("SCHEMA_VIOLATION: empty or non-string field")
        result[row["candidate_id"]] = dict(row)
    return result


def packet_ids(proposals: dict[str, dict]) -> list[str]:
    return sorted(value for value, row in proposals.items()
                  if row["proposal"] in
                  (STRONG_TRANSITION_CANDIDATE, AMBIGUOUS))


def appendix_ids(proposals: dict[str, dict]) -> list[str]:
    return sorted(value for value, row in proposals.items()
                  if row["proposal"] == WEAK_TRANSITION_CANDIDATE)


def proposal_counts(proposals: dict[str, dict]) -> dict[str, int]:
    counts = {value: 0 for value in PROPOSALS}
    for row in proposals.values():
        if row["proposal"] not in counts:
            raise CandidateError("VOCABULARY_VIOLATION")
        counts[row["proposal"]] += 1
    return counts


def density_note(counts: dict[str, int]) -> dict:
    strong = counts.get(STRONG_TRANSITION_CANDIDATE, 0)
    return {"strong_count": strong,
            "blocker": "INSUFFICIENT_SEMANTIC_CANDIDATES" if strong <= 1 else None,
            "threshold_applied": False, "truncated": False}


def _candidate_index(candidates: list[dict]) -> dict[str, dict]:
    return {row["candidate_id"]: row for row in candidates}


def reviewer_packet(candidates: list[dict], proposals: dict[str, dict],
                    _metadata: dict | None = None) -> str:
    index = _candidate_index(candidates)
    lines = ["SEMANTIC BOUNDARY CANDIDATE REVIEW",
             "Allowed reviewer verdicts: " + " / ".join(REVIEWER_VERDICTS),
             "Current verdict: " + NOT_ADJUDICATED, ""]
    for candidate_id in packet_ids(proposals):
        row = proposals[candidate_id]
        lines.extend([render_block(index[candidate_id]),
                      "PROPOSER LABEL", row["proposal"],
                      "BEFORE ACTIVITY", row["before_activity"],
                      "AFTER ACTIVITY", row["after_activity"],
                      "RATIONALE", row["rationale"],
                      "REVIEWER VERDICT", NOT_ADJUDICATED, ""])
    return "\n".join(lines).rstrip() + "\n"


def weak_appendix(candidates: list[dict], proposals: dict[str, dict]) -> str:
    index = _candidate_index(candidates)
    lines = ["WEAK PROPOSAL APPENDIX", ""]
    for candidate_id in appendix_ids(proposals):
        row = proposals[candidate_id]
        lines.extend([render_block(index[candidate_id]),
                      "PROPOSER LABEL", row["proposal"],
                      "RATIONALE", row["rationale"], ""])
    return "\n".join(lines).rstrip() + "\n"


def blind_map_document(candidates: list[dict]) -> dict:
    observation_mapping = {}
    for row in candidates:
        for side_name in ("before", "after"):
            for group in row[side_name]["sets"]:
                if group["label"]:
                    observation_mapping["%s:%s:%s" %
                                        (row["candidate_id"], side_name,
                                         group["label"])] = group["source_window"]
    return {
        "schema": "wvr_bcand_v1_blind_map",
        "event": EVENT,
        "sealed": True,
        "reveal_before_verdicts_allowed": False,
        "candidate_to_time": {row["candidate_id"]: row["boundary_sec"]
                              for row in candidates},
        "observation_set_to_window": observation_mapping,
    }


def verdict_summary(verdicts: dict[str, dict], expected_ids: list[str]) -> dict:
    extras = sorted(set(verdicts) - set(expected_ids))
    if extras:
        raise CandidateError("CANDIDATE_SET_MISMATCH: invented verdict ids")
    counts = {value: 0 for value in REVIEWER_VERDICTS}
    for candidate_id, row in verdicts.items():
        value = row.get("verdict") if isinstance(row, dict) else None
        if value not in counts:
            raise CandidateError("VOCABULARY_VIOLATION: reviewer verdict")
        counts[value] += 1
    missing = sorted(set(expected_ids) - set(verdicts))
    return {"counts": counts, "missing": missing,
            "reveal_allowed": not missing and not extras}


def executor_state(proposals: dict[str, dict], packet_candidate_ids: list[str],
                   density: dict, leakage: dict) -> dict:
    return {
        "state": EXECUTOR_STATE,
        "verdict": None,
        "verdict_by_executor": False,
        "chapter_generated": False,
        "overview_generated": False,
        "mapping_revealed": False,
        "new_vlm_inference_count": 0,
        "track_a_input_used": False,
        "proposal_count": len(proposals),
        "packet_candidate_count": len(packet_candidate_ids),
        "density": density,
        "leakage_violations": list(leakage.get("violations", [])),
        "final_verdict_vocabulary": FINAL_VERDICT_VOCABULARY_LINE,
    }
