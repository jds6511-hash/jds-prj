"""Frozen, inference-free raw-detail audit for WVR grounded evidence V1."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable


EVENT = "WVR_GROUNDED_REPORT_EVIDENCE_V1"
EXPECTED_RAW_COUNT = 116
EXPECTED_RAW_MANIFEST_SHA256 = (
    "8c40bbe26b2e5e4e56800dbb5c87799e8d91c9df970bfac4a1e212c544cba485"
)
RAW_ROOTS = {
    "C01": "runs/wvr_video_overview_preview_v2",
    "C02": "runs/wvr_chunk_overview_v2/C02",
    "C03": "runs/wvr_chunk_overview_v2/C03",
    "C04": "runs/wvr_chunk_overview_v2/C04",
    "C05": "runs/wvr_chunk_overview_v2/C05",
}
EXPECTED_CHUNK_COUNTS = {"C01": 24, "C02": 24, "C03": 24,
                         "C04": 24, "C05": 20}
RAW_GLOB = "video_overview_v2_segment_S*_raw.txt"
PLAN_NAME = "video_overview_v2_segments.json"

ACTIVITY_LABELS = {
    "음식 준비 및 조리", "식사", "의류 작업 및 수선", "포장 작업",
    "외출 준비", "이동", "구매 또는 둘러보기", "정리 작업",
    "기타 명확한 주요 활동", "불명확",
}
ACTION_ROOTS = (
    "다루", "자르", "썰", "섞", "젓", "담", "넣", "꺼내", "놓", "집",
    "먹", "마시", "걷", "이동", "포장", "감싸", "접", "손질", "수선",
    "꿰매", "바느질", "정리", "씻", "조리", "착용", "벗",
)
MOVEMENT_ROOTS = ("걷", "이동")
VISIBLE_NOUNS = (
    "손", "사람", "재료", "음식", "그릇", "용기", "도구", "의류", "옷",
    "천", "물건", "포장재", "종이",
)
FORBIDDEN_MARKERS = (
    "불명확", "불확실", "애매", "추정", "가능성", "듯", "아마", "의도",
    "목적", "계획", "예정", "기분", "감정", "일상", "습관", "퇴원",
    "병원", "직장", "업무", "휴가", "여행", "방문 예정", "선물용",
)
CONTRACT_FIELDS = {
    "BROAD_ACTIVITY", "OBSERVED_CHANGE", "CONTEXT_INFERENCE", "UNCERTAINTY",
}
ZERO_INFERENCE = {
    "visual": 0,
    "stt": 0,
    "beta_v3_regeneration": 0,
    "text_generation": 0,
    "retry": 0,
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RAW_NAME = re.compile(r"^video_overview_v2_segment_(S\d+)_raw\.txt$")


class GroundingError(RuntimeError):
    """Frozen grounding contract was violated."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _load_plan(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GroundingError(f"invalid segment plan: {path}") from exc
    if not isinstance(value, list):
        raise GroundingError(f"segment plan must be a list: {path}")
    return value


def raw_universe(root: Path) -> list[dict]:
    """Resolve the exact frozen raw universe without parsing raw semantics."""
    root = Path(root).resolve()
    rows: list[dict] = []
    counts: Counter[str] = Counter()
    for chunk, relative_root in RAW_ROOTS.items():
        raw_root = root / relative_root
        plan = _load_plan(raw_root / PLAN_NAME)
        plan_by_id: dict[str, dict] = {}
        for row in plan:
            if not isinstance(row, dict) or not isinstance(row.get("segment_id"), str):
                raise GroundingError(f"invalid source window in {chunk} plan")
            segment_id = row["segment_id"]
            if segment_id in plan_by_id:
                raise GroundingError(f"duplicate source window: {chunk}/{segment_id}")
            try:
                start, end = float(row["start_sec"]), float(row["end_sec"])
            except (KeyError, TypeError, ValueError) as exc:
                raise GroundingError(f"invalid source interval: {chunk}/{segment_id}") from exc
            if end <= start:
                raise GroundingError(f"invalid source interval: {chunk}/{segment_id}")
            plan_by_id[segment_id] = {"start_sec": start, "end_sec": end}

        files = sorted(raw_root.glob(RAW_GLOB), key=lambda p: p.name)
        observed_ids: set[str] = set()
        for path in files:
            match = RAW_NAME.fullmatch(path.name)
            if not match:
                raise GroundingError(f"invalid raw filename: {path.name}")
            window = match.group(1)
            if window not in plan_by_id:
                raise GroundingError(f"unknown source window: {chunk}/{window}")
            if window in observed_ids:
                raise GroundingError(f"duplicate raw source window: {chunk}/{window}")
            observed_ids.add(window)
            interval = plan_by_id[window]
            rows.append({
                "chunk": chunk,
                "window": window,
                "start_sec": interval["start_sec"],
                "end_sec": interval["end_sec"],
                "raw_path": path.relative_to(root).as_posix(),
                "raw_abs": str(path),
                "plan_window_ids": sorted(plan_by_id),
            })
            counts[chunk] += 1
        if observed_ids != set(plan_by_id):
            missing = sorted(set(plan_by_id) - observed_ids)
            raise GroundingError(f"missing raw source windows: {chunk}/{missing}")
    if dict(counts) != EXPECTED_CHUNK_COUNTS or len(rows) != EXPECTED_RAW_COUNT:
        raise GroundingError(f"raw universe count drift: {dict(counts)}")
    return rows


def manifest_sha256(sources: Iterable[dict]) -> str:
    digest = hashlib.sha256()
    ordered = sorted(sources, key=lambda row: f'{row["chunk"]}/{Path(row["raw_path"]).name}')
    for row in ordered:
        key = f'{row["chunk"]}/{Path(row["raw_path"]).name}'
        file_hash = sha256_file(Path(row["raw_abs"]))
        digest.update(key.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_hash))
        digest.update(b"\n")
    return digest.hexdigest()


def _clean_fence_fragment(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_envelope(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise GroundingError("raw JSON object not found")
    low, high = raw.find("{"), raw.rfind("}")
    if low < 0 or high <= low:
        raise GroundingError("raw JSON object not found")
    try:
        value = json.loads(raw[low:high + 1])
    except json.JSONDecodeError as exc:
        raise GroundingError("invalid raw JSON object") from exc
    if not isinstance(value, dict):
        raise GroundingError("raw JSON object required")
    return {
        "json": value,
        "prefix": _clean_fence_fragment(raw[:low]),
        "suffix": _clean_fence_fragment(raw[high + 1:]),
    }


def classify_text(field: str, text: str) -> dict:
    source_text = text.strip() if isinstance(text, str) else ""
    base = {
        "eligible": False,
        "text": source_text,
        "source_text": source_text,
        "confidence": None,
        "rejection_reason": None,
    }
    field_reasons = {
        "BROAD_ACTIVITY": "broad_label_only",
        "OBSERVED_CHANGE": "canonical_transition_only",
        "CONTEXT_INFERENCE": "context_inference",
        "UNCERTAINTY": "uncertainty_only",
    }
    if field in field_reasons:
        base["rejection_reason"] = field_reasons[field]
        return base
    if not source_text:
        base["rejection_reason"] = "empty_or_boilerplate"
        return base
    if any(marker in source_text for marker in FORBIDDEN_MARKERS):
        base["rejection_reason"] = "forbidden_context_or_uncertainty"
        return base
    actions = [root for root in ACTION_ROOTS if root in source_text]
    if not actions:
        base["rejection_reason"] = "no_allowed_visible_action"
        return base
    if not any(root in source_text for root in MOVEMENT_ROOTS) and not any(
            noun in source_text for noun in VISIBLE_NOUNS):
        base["rejection_reason"] = "no_allowed_visible_noun"
        return base
    base.update({"eligible": True, "confidence": "high",
                 "rejection_reason": None})
    return base


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(_strings(item))
        return result
    return []


def _text_list(value, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise GroundingError(f"{field} must be a text list")
    return [x.strip() for x in value if x.strip()]


def validate_observation(observation: dict) -> None:
    source = observation.get("source")
    if not isinstance(source, dict):
        raise GroundingError("source lineage required")
    for key in ("chunk", "window", "raw_path", "raw_sha256"):
        if not source.get(key):
            raise GroundingError("source lineage incomplete")
    if not HEX64.fullmatch(str(source["raw_sha256"])):
        raise GroundingError("source lineage SHA256 invalid")
    start = float(observation["start_sec"])
    end = float(observation["end_sec"])
    if end <= start:
        raise GroundingError("invalid observation interval")
    for fact in observation.get("visual_facts", []):
        if fact.get("confidence") != "high" or not fact.get("source_text"):
            raise GroundingError("invalid visual fact")
        span = fact.get("source_span")
        if (not isinstance(span, list) or len(span) != 2 or
                float(span[0]) < start or float(span[1]) > end or
                float(span[1]) <= float(span[0])):
            raise GroundingError("visual fact outside source interval")


def audit_one(source: dict, raw_bytes: bytes,
              allowed: set[str] | None = None) -> dict:
    allowed = set(allowed or ACTIVITY_LABELS)
    if source.get("window") not in set(source.get("plan_window_ids", [])):
        raise GroundingError("unknown source window")
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GroundingError("raw is not UTF-8") from exc
    envelope = extract_envelope(raw)
    payload = envelope["json"]
    activities = _text_list(payload.get("BROAD_ACTIVITY"), "BROAD_ACTIVITY")
    if any(activity not in allowed for activity in activities):
        raise GroundingError("unknown activity")
    changes = _text_list(payload.get("OBSERVED_CHANGE"), "OBSERVED_CHANGE")
    context = _text_list(payload.get("CONTEXT_INFERENCE"), "CONTEXT_INFERENCE")
    uncertainty = _text_list(payload.get("UNCERTAINTY"), "UNCERTAINTY")

    dispositions: list[dict] = []
    for field, values in (
        ("BROAD_ACTIVITY", activities), ("OBSERVED_CHANGE", changes),
        ("CONTEXT_INFERENCE", context), ("UNCERTAINTY", uncertainty),
    ):
        for value in values:
            dispositions.append({"field": field, **classify_text(field, value)})
    for field, value in payload.items():
        if field not in CONTRACT_FIELDS:
            for text in _strings(value):
                dispositions.append({"field": f"EXTRA_JSON:{field}",
                                     **classify_text("RAW_EXTRA", text)})
    for label in ("prefix", "suffix"):
        if envelope[label]:
            dispositions.append({"field": f"RAW_{label.upper()}",
                                 **classify_text("RAW_EXTRA", envelope[label])})

    visual_facts = []
    for item in dispositions:
        if item["eligible"]:
            visual_facts.append({
                "text": item["text"], "source_text": item["source_text"],
                "confidence": "high",
                "source_span": [float(source["start_sec"]),
                                float(source["end_sec"])],
            })
    raw_hash = sha256_bytes(raw_bytes)
    observation = {
        "observation_id": None,
        "start_sec": float(source["start_sec"]),
        "end_sec": float(source["end_sec"]),
        "broad_activity": activities,
        "visual_facts": visual_facts,
        "observed_change": changes,
        "uncertainty": uncertainty,
        "source": {
            "chunk": source["chunk"], "window": source["window"],
            "raw_path": source["raw_path"], "raw_sha256": raw_hash,
        },
    }
    validate_observation(observation)
    return {
        "chunk": source["chunk"], "window": source["window"],
        "start_sec": float(source["start_sec"]),
        "end_sec": float(source["end_sec"]),
        "raw_path": source["raw_path"], "raw_sha256": raw_hash,
        "json_parse_status": "PASS", "json_keys": sorted(payload),
        "schema_drift": set(payload) != CONTRACT_FIELDS,
        "non_json_prefix": envelope["prefix"],
        "non_json_suffix": envelope["suffix"],
        "BROAD_ACTIVITY": activities, "OBSERVED_CHANGE": changes,
        "CONTEXT_INFERENCE": context, "UNCERTAINTY": uncertainty,
        "detail_candidates": dispositions,
        "eligible_visual_facts": visual_facts,
        "observation": observation,
    }


def _dominant_activities(timeline: dict) -> list[str]:
    coverage: defaultdict[str, float] = defaultdict(float)
    for entry in timeline.get("entries", []):
        duration = float(entry["end_sec"]) - float(entry["start_sec"])
        if duration < 0:
            raise GroundingError("invalid timeline interval")
        for activity in entry.get("broad_activity", []):
            coverage[activity] += duration
    return [item[0] for item in sorted(
        coverage.items(), key=lambda item: (-item[1], item[0]))[:2]]


def _fact_lineage_complete(audit: dict, fact: dict) -> bool:
    source = audit.get("observation", {}).get("source", {})
    span = fact.get("source_span")
    return bool(
        source.get("chunk") and source.get("window") and source.get("raw_path")
        and HEX64.fullmatch(str(source.get("raw_sha256", "")))
        and isinstance(span, list) and len(span) == 2
        and float(span[0]) >= float(audit["start_sec"])
        and float(span[1]) <= float(audit["end_sec"])
        and float(span[1]) > float(span[0])
        and fact.get("confidence") == "high" and fact.get("source_text")
    )


def evaluate_sufficiency(audits: list[dict], timeline: dict) -> dict:
    """Apply the four frozen Branch A thresholds as a conjunction."""
    usable: list[dict] = []
    all_safe = True
    for audit in audits:
        facts = list(audit.get("eligible_visual_facts", []))
        if not facts:
            continue
        if all(_fact_lineage_complete(audit, fact) for fact in facts):
            usable.append(audit)
        else:
            all_safe = False
    activities = {
        activity for audit in usable for activity in audit.get("BROAD_ACTIVITY", [])
    }
    dominant = set(_dominant_activities(timeline))
    non_dominant = activities - dominant
    metrics = {
        "usable_detail_windows": len({
            (row["chunk"], row["window"]) for row in usable
        }),
        "distinct_activities_with_detail": len(activities),
        "non_dominant_activities_with_detail": len(non_dominant),
        "lineage_complete_candidates": len(usable),
        "every_eligible_fact_safe": all_safe,
        "dominant_activities": sorted(dominant),
        "detail_activities": sorted(activities),
        "non_dominant_detail_activities": sorted(non_dominant),
    }
    passed = (
        metrics["usable_detail_windows"] >= 5
        and metrics["distinct_activities_with_detail"] >= 3
        and metrics["non_dominant_activities_with_detail"] >= 1
        and metrics["lineage_complete_candidates"] >= 5
        and metrics["every_eligible_fact_safe"] is True
    )
    return {
        "branch": "A" if passed else "SOURCE_INSUFFICIENT",
        "metrics": metrics,
        "thresholds": {
            "usable_detail_windows": 5,
            "distinct_activities_with_detail": 3,
            "non_dominant_activities_with_detail": 1,
            "lineage_complete_candidates": 5,
            "every_eligible_fact_safe": True,
        },
        "all_thresholds_pass": passed,
    }


def snapshot_sources(root: Path, targets: Iterable[str]) -> dict[str, str]:
    root = Path(root).resolve()
    result = {}
    for relative in targets:
        path = root / relative
        if not path.is_file():
            raise GroundingError(f"protected source missing: {relative}")
        result[Path(relative).as_posix()] = sha256_file(path)
    return result


def assert_unchanged(before: dict[str, str], after: dict[str, str]) -> None:
    if before != after:
        changed = sorted(set(before) | set(after))
        changed = [key for key in changed if before.get(key) != after.get(key)]
        raise GroundingError(f"source hash drift: {changed}")


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def write_source_insufficient_outputs(output_dir: Path, audits: list[dict],
                                      execution_record: dict,
                                      decision: dict) -> dict:
    """Write only the three preregistered Branch B artifacts."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_payload = {
        "event": EVENT,
        "raw_file_count": len(audits),
        "audits": audits,
    }
    result = {
        "event": EVENT,
        "decision": "GROUNDING_DETAIL_SOURCE_INSUFFICIENT",
        "branch": "SOURCE_INSUFFICIENT",
        "gate": decision,
        "new_visual_inference_required": "UNKNOWN",
        "downstream_grounded_store_executed": False,
        "highlight_selection_executed": False,
        "inference": dict(ZERO_INFERENCE),
        "status": "CLOSED / GROUNDING_DETAIL_SOURCE_INSUFFICIENT",
    }
    record = dict(execution_record)
    record["decision"] = result["decision"]
    record["status"] = result["status"]
    record["inference"] = dict(ZERO_INFERENCE)
    write_json(output_dir / "raw_detail_audit.json", audit_payload)
    write_json(output_dir / "execution_record.json", record)
    write_json(output_dir / "result.json", result)
    return result


def validate_detail(detail: dict) -> None:
    validate_observation(detail)


def validate_candidate(candidate: dict, allowed: set[str] | None = None) -> None:
    allowed = set(allowed or ACTIVITY_LABELS)
    activities = candidate.get("activities")
    if (not isinstance(activities, list) or not activities
            or any(activity not in allowed for activity in activities)):
        raise GroundingError("unknown activity in candidate")
    start, end = float(candidate["start_sec"]), float(candidate["end_sec"])
    if end <= start:
        raise GroundingError("invalid candidate interval")
    if abs(float(candidate.get("duration_sec", end - start)) - (end - start)) > 1e-6:
        raise GroundingError("candidate duration mismatch")
    sources = candidate.get("sources")
    if not isinstance(sources, list) or not sources:
        raise GroundingError("candidate source lineage required")
    for source in sources:
        if (not source.get("chunk") or not source.get("window")
                or not source.get("raw_path")
                or not HEX64.fullmatch(str(source.get("raw_sha256", "")))):
            raise GroundingError("candidate source lineage incomplete")
    for fact in candidate.get("visual_facts", []):
        if fact.get("confidence") != "high" or not fact.get("source_text"):
            raise GroundingError("candidate visual fact invalid")
        span = fact.get("source_span")
        if (not isinstance(span, list) or len(span) != 2
                or float(span[0]) < start or float(span[1]) > end
                or float(span[1]) <= float(span[0])):
            raise GroundingError("candidate visual fact outside interval")


def validate_highlights(rows: list[dict], allowed: set[str] | None = None) -> None:
    ids: set[str] = set()
    cursor = float("-inf")
    for row in rows:
        validate_candidate(row, allowed)
        identifier = row.get("highlight_id", row.get("candidate_id"))
        if not identifier or identifier in ids:
            raise GroundingError("duplicate highlight id")
        ids.add(identifier)
        if float(row["start_sec"]) < cursor:
            raise GroundingError("nonmonotonic highlight time")
        cursor = float(row["end_sec"])


def build_grounded_store(audits: list[dict]) -> tuple[list[dict], dict]:
    observations = []
    details = []
    for index, audit in enumerate(audits, start=1):
        observation = dict(audit["observation"])
        observation["observation_id"] = observation.get("observation_id") or f"GO{index:04d}"
        validate_observation(observation)
        observations.append(observation)
        for fact_index, fact in enumerate(observation["visual_facts"], start=1):
            details.append({
                "detail_id": f"GD{len(details) + 1:04d}",
                "observation_id": observation["observation_id"],
                "start_sec": observation["start_sec"],
                "end_sec": observation["end_sec"],
                "broad_activity": observation["broad_activity"],
                "visual_fact": fact,
                "source": observation["source"],
            })
    return observations, {
        "event": EVENT,
        "detail_count": len(details),
        "details": details,
    }


def _coverage_seconds(entries: list[dict]) -> dict[str, float]:
    coverage: defaultdict[str, float] = defaultdict(float)
    for entry in entries:
        duration = float(entry["end_sec"]) - float(entry["start_sec"])
        for activity in entry.get("broad_activity", []):
            coverage[activity] += duration
    return dict(coverage)


def _temporal_zone(start: float, end: float, total_end: float) -> str:
    midpoint = (start + end) / 2
    if midpoint < total_end / 3:
        return "early"
    if midpoint < total_end * 2 / 3:
        return "middle"
    return "late"


def build_candidates(audits: list[dict], timeline: dict) -> list[dict]:
    entries = list(timeline.get("entries", []))
    if not entries:
        raise GroundingError("timeline entries required")
    by_source = {(row["chunk"], row["window"]): row for row in audits}
    coverage = _coverage_seconds(entries)
    total_end = float(entries[-1]["end_sec"])
    blocks: list[dict] = []
    for entry in entries:
        signature = tuple(entry.get("broad_activity", []))
        if not signature or any(activity not in ACTIVITY_LABELS for activity in signature):
            raise GroundingError("unknown activity in timeline")
        start, end = float(entry["start_sec"]), float(entry["end_sec"])
        source_window = entry.get("source_window", {})
        key = (entry.get("source_chunk"), source_window.get("segment_id"))
        audit = by_source.get(key)
        if audit is None:
            raise GroundingError(f"timeline source missing from audit: {key}")
        facts = []
        for fact in audit.get("eligible_visual_facts", []):
            attached = dict(fact)
            attached["source_span"] = [start, end]
            facts.append(attached)
        source = dict(audit["observation"]["source"])
        observation_id = audit["observation"]["observation_id"]
        if (blocks and tuple(blocks[-1]["activities"]) == signature
                and abs(float(blocks[-1]["end_sec"]) - start) <= 1e-9):
            block = blocks[-1]
            block["end_sec"] = end
            block["timeline_entry_ids"].append(entry["entry_index"])
            if observation_id not in block["grounded_observation_ids"]:
                block["grounded_observation_ids"].append(observation_id)
            if source not in block["sources"]:
                block["sources"].append(source)
            for fact in facts:
                if fact not in block["visual_facts"]:
                    block["visual_facts"].append(fact)
        else:
            blocks.append({
                "start_sec": start, "end_sec": end,
                "activities": list(signature), "visual_facts": facts,
                "timeline_entry_ids": [entry["entry_index"]],
                "grounded_observation_ids": [observation_id],
                "sources": [source],
            })
    final_signature = tuple(entries[-1]["broad_activity"])
    final_start = float(entries[-1]["start_sec"])
    for entry in reversed(entries[:-1]):
        if (tuple(entry["broad_activity"]) == final_signature
                and abs(float(entry["end_sec"]) - final_start) <= 1e-9):
            final_start = float(entry["start_sec"])
        else:
            break
    candidates = []
    for block in blocks:
        is_final = (abs(block["start_sec"] - final_start) <= 1e-9
                    and abs(block["end_sec"] - total_end) <= 1e-9)
        if not block["visual_facts"] and not is_final:
            continue
        facts = block["visual_facts"]
        unique_facts = {fact["text"] for fact in facts}
        candidate = {
            "candidate_id": f"GC{len(candidates) + 1:04d}",
            **block,
            "duration_sec": block["end_sec"] - block["start_sec"],
            "temporal_zone": _temporal_zone(block["start_sec"], block["end_sec"],
                                             total_end),
            "visual_fact_count": len(facts),
            "unique_visual_fact_count": len(unique_facts),
            "activity_coverage_seconds": {
                activity: coverage[activity] for activity in block["activities"]
            },
            "activity_rarity_seconds": min(
                coverage[activity] for activity in block["activities"]),
            "is_final_phase": is_final,
        }
        validate_candidate(candidate)
        candidates.append(candidate)
    signatures = Counter(tuple(row["activities"]) for row in candidates)
    for candidate in candidates:
        candidate["activity_signature_repeat_count"] = signatures[
            tuple(candidate["activities"])]
    return candidates


def _candidate_rank(candidate: dict) -> tuple:
    rarity = min(candidate.get("activity_coverage_seconds", {"": float("inf")}).values())
    return (
        -int(bool(candidate.get("visual_facts"))),
        -int(candidate.get("unique_visual_fact_count", 0)),
        float(rarity),
        -float(candidate["duration_sec"]),
        float(candidate["start_sec"]),
        str(candidate["candidate_id"]),
    )


def _can_select(candidate: dict, selected: list[dict]) -> bool:
    signature = tuple(candidate["activities"])
    same = [row for row in selected if tuple(row["activities"]) == signature]
    if len(same) >= 2:
        return False
    fact_set = {fact["text"] for fact in candidate.get("visual_facts", [])}
    if any(fact_set == {fact["text"] for fact in row.get("visual_facts", [])}
           for row in same):
        return False
    start, end = float(candidate["start_sec"]), float(candidate["end_sec"])
    return not any(start < float(row["end_sec"]) and end > float(row["start_sec"])
                   for row in selected)


def select_highlights(candidates: list[dict], final_span: list[float],
                      dominant: set[str]) -> list[dict]:
    if not candidates:
        raise GroundingError("DIVERSITY_SELECTION_CONTRACT_UNSATISFIED")
    for candidate in candidates:
        validate_candidate(candidate)
    target = min(7, len(candidates))
    ranked = sorted(candidates, key=_candidate_rank)
    selected: list[dict] = []

    final = next((row for row in candidates
                  if [float(row["start_sec"]), float(row["end_sec"])]
                  == [float(final_span[0]), float(final_span[1])]), None)
    if final is None:
        raise GroundingError("DIVERSITY_SELECTION_CONTRACT_UNSATISFIED: final")
    selected.append(final)

    for zone in ("early", "middle", "late"):
        if any(row["temporal_zone"] == zone and row.get("visual_facts")
               for row in selected):
            continue
        choice = next((row for row in ranked
                       if row["temporal_zone"] == zone and row.get("visual_facts")
                       and row not in selected and _can_select(row, selected)), None)
        if choice is None:
            raise GroundingError(
                f"DIVERSITY_SELECTION_CONTRACT_UNSATISFIED: {zone}")
        selected.append(choice)

    while sum(bool(set(row["activities"]) - set(dominant))
              for row in selected) < 2:
        choice = next((row for row in ranked
                       if row not in selected
                       and bool(set(row["activities"]) - set(dominant))
                       and _can_select(row, selected)), None)
        if choice is None:
            break
        selected.append(choice)

    for candidate in ranked:
        if len(selected) >= target:
            break
        if candidate not in selected and _can_select(candidate, selected):
            selected.append(candidate)
    if len(selected) < 5:
        raise GroundingError("DIVERSITY_SELECTION_CONTRACT_UNSATISFIED: count")

    selected.sort(key=lambda row: (float(row["start_sec"]), row["candidate_id"]))
    highlights = []
    for index, candidate in enumerate(selected, start=1):
        item = copy_dict(candidate)
        item["highlight_id"] = f"H{index:02d}"
        item["description"] = render_highlight(item)
        highlights.append(item)
    validate_highlights(highlights)
    return highlights


def copy_dict(value: dict) -> dict:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _format_time(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def render_highlight(candidate: dict) -> str:
    time_range = f'{_format_time(candidate["start_sec"])}–{_format_time(candidate["end_sec"])}'
    activities = candidate["activities"]
    if len(activities) == 1:
        lead = f"{time_range}에는 {activities[0]}가 나타난다."
    else:
        lead = f"{time_range}에는 {' · '.join(activities)} 활동이 함께 나타난다."
    facts = [fact["text"].rstrip(".。") for fact in candidate.get("visual_facts", [])[:2]]
    return " ".join([lead] + [f"{fact}." for fact in facts])


def render_pair(left: dict, right: dict) -> str:
    adjacent = abs(float(left["end_sec"]) - float(right["start_sec"])) <= 1e-9
    different = tuple(left["activities"]) != tuple(right["activities"])
    if adjacent and different:
        return f"{' · '.join(left['activities'])}에서 {' · '.join(right['activities'])}로 전환된다."
    return f"{' · '.join(left['activities'])} 뒤 {' · '.join(right['activities'])}가 나타난다."


def compare_v3(highlights: list[dict], v3_highlights: list[dict],
               dominant: set[str]) -> dict:
    def metrics(rows: list[dict]) -> dict:
        signatures = [tuple(row.get("activities", [])) for row in rows]
        non_dominant = sum(bool(set(signature) - dominant) for signature in signatures)
        detail_bearing = sum(bool(row.get("visual_facts")) for row in rows)
        return {
            "highlight_count": len(rows),
            "distinct_activity_signatures": len(set(signatures)),
            "non_dominant_highlight_count": non_dominant,
            "grounded_detail_highlight_count": detail_bearing,
        }
    return {"v3": metrics(v3_highlights), "grounded_v1": metrics(highlights)}


def write_branch_a_outputs(output_dir: Path, audits: list[dict],
                           execution_record: dict, decision: dict,
                           observations: list[dict], detail_store: dict,
                           candidates: list[dict], highlights: list[dict],
                           comparison: dict) -> dict:
    """Write only the preregistered Branch A data layer plus audit records."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for observation in observations:
        validate_observation(observation)
    validate_highlights(highlights)
    detail_lineage = {
        "event": EVENT,
        "lineage": [{
            "detail_id": row["detail_id"],
            "observation_id": row["observation_id"],
            "source": row["source"],
        } for row in detail_store.get("details", [])],
        "lineage_completeness": 1.0 if detail_store.get("details") else 1.0,
    }
    highlight_lineage = {
        "event": EVENT,
        "lineage": [{
            "highlight_id": row["highlight_id"],
            "candidate_id": row["candidate_id"],
            "grounded_observation_ids": row["grounded_observation_ids"],
            "sources": row["sources"],
        } for row in highlights],
        "lineage_completeness": 1.0,
    }
    audit_payload = {"event": EVENT, "raw_file_count": len(audits),
                     "audits": audits}
    result = {
        "event": EVENT, "branch": "A", "gate": decision,
        "grounded_observation_count": len(observations),
        "grounded_detail_count": len(detail_store.get("details", [])),
        "highlight_candidate_count": len(candidates),
        "highlight_count": len(highlights),
        "lineage_completeness": 1.0,
        "comparison_v3": comparison,
        "new_visual_inference_required": "UNKNOWN",
        "downstream_grounded_store_executed": True,
        "highlight_selection_executed": True,
        "inference": dict(ZERO_INFERENCE),
        "status": "EXECUTED / REVIEW_PENDING",
    }
    record = dict(execution_record)
    record.update({"decision": "BRANCH_A", "status": result["status"],
                   "inference": dict(ZERO_INFERENCE)})
    payloads = {
        "raw_detail_audit.json": audit_payload,
        "execution_record.json": record,
        "result.json": result,
        "grounded_observations.json": {
            "event": EVENT, "observations": observations},
        "grounded_detail_store.json": detail_store,
        "grounded_detail_lineage.json": detail_lineage,
        "highlight_candidates.json": {
            "event": EVENT, "candidates": candidates},
        "highlights.json": highlights,
        "highlight_lineage.json": highlight_lineage,
        "comparison_v3.json": comparison,
    }
    for name, payload in payloads.items():
        write_json(output_dir / name, payload)
    return result


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in Path(root).rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
        digest.update(b"\n")
    return digest.hexdigest()
