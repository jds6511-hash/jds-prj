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
