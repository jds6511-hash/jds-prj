"""W00_DEGENERACY_FORENSIC_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_W00_DEGENERACY_FORENSIC_V1_2026-09-09.md`

```
추론 없음 · GPU 없음 · 기존 artifact는 읽기만 한다
질문      W00 실패가 입력 경로 문제인지, 생성 루프인지, 구분 불가인지
분류      A=INPUT_ANOMALY_FOUND · B=OUTPUT_DEGENERACY_CONFIRMED 두 축의 진리표
금지      raw salvage · W00 재실행 · prompt 수정 · token cap 상향
```
"""
import json
import re

import wvr_density_prompt_v2 as diag
import wvr_shadow_v1 as sh

EVENT = "WVR_EVENT_EXTRACTION_W00_DEGENERACY_FORENSIC_V1"
TARGET_WINDOW = "W00"
CONTROL_WINDOW = "W01"

NEW_INFERENCE_ALLOWED = False
RERUN_ALLOWED = False
RAW_SALVAGE_ALLOWED = False
TOKEN_CAP_INCREASE_APPROVED = False
MAPPING_REVEAL_ALLOWED = False
SEMANTIC_VERDICT_BY_EXECUTOR = False

# C4 시각 지표 임계 (사전등록에서 동결 · 분류 규칙에 들어가지 않는다)
BLACK_LUMA_THRESHOLD = 16.0
NEAR_STATIC_DIFF_THRESHOLD = 2.0
VISUAL_METRICS_IN_CLASSIFICATION = False

# C2에서 찾는 창 전용 분기 패턴 (문자열 탐색 · 발견은 증거 후보이고 자동 결론이 아니다)
WINDOW_SPECIFIC_PATTERNS = (
    "if start ==", "if start_sec ==", "if not start", "start or ",
    "start_sec or ", "if window_id ==", 'window_id == "W00"',
)

INPUT_ANOMALY = "INPUT_ANOMALY_FOUND"
OUTPUT_DEGENERACY = "OUTPUT_DEGENERACY_CONFIRMED"

INPUT_PIPELINE_DEFECT = "INPUT_PIPELINE_DEFECT"
MODEL_OUTPUT_DEGENERACY = "MODEL_OUTPUT_DEGENERACY"
MIXED = "MIXED"
UNRESOLVED = "UNRESOLVED"
CLASSIFICATIONS = (INPUT_PIPELINE_DEFECT, MODEL_OUTPUT_DEGENERACY, MIXED,
                   UNRESOLVED)

OBJECT_RE = re.compile(
    r'\{"start_sec":\s*(-?\d+(?:\.\d+)?),\s*"end_sec":\s*(-?\d+(?:\.\d+)?),'
    r'\s*"actor":\s*"(.*?)",\s*"action":\s*"(.*?)",'
    r'\s*"object_or_state":\s*"(.*?)"\}')


class ForensicError(RuntimeError):
    """forensic 계약 위반."""


def expected_prompt(window: dict) -> str:
    """창 프롬프트를 템플릿에서 다시 만든다 (실행기와 같은 식)."""
    return diag.SAMPLING_DIAG_PROMPT_V2 % {
        "window_start": float(window["start_sec"]),
        "window_end": float(window["end_sec"])}


def prompt_diff(left: str, right: str) -> dict:
    """두 프롬프트에서 다른 줄만 추린다."""
    left_lines, right_lines = left.split("\n"), right.split("\n")
    rows = []
    for index in range(max(len(left_lines), len(right_lines))):
        a = left_lines[index] if index < len(left_lines) else None
        b = right_lines[index] if index < len(right_lines) else None
        if a != b:
            rows.append({"line": index + 1, "target": a, "control": b})
    return {"differing_line_count": len(rows), "lines": rows,
            "same_line_count": len(left_lines) - len(rows)}


def grid_linearity(record: dict) -> dict:
    """frame_times가 start + 2·i이고 index가 time × rate와 맞는지 계산한다."""
    window = record["window"]
    expected = list(sh.frame_times(window))
    observed = [round(float(time), 3)
                for time in (record.get("frame_times") or [])]
    rate = record.get("decoded_fps")
    indices = record.get("frame_indices") or []
    index_ok, index_rows = True, []
    if rate and indices and len(indices) == len(observed):
        for time, index in zip(observed, indices):
            predicted = int(round(time * float(rate)))
            drift = abs(int(index) - predicted)
            index_rows.append({"time_sec": time, "index": int(index),
                               "predicted": predicted, "drift": drift})
            if drift > 1:
                index_ok = False
    else:
        index_ok = False
    return {"times_match_schedule": observed == expected,
            "expected_first_last": [expected[0], expected[-1]],
            "observed_first_last": ([observed[0], observed[-1]]
                                    if observed else None),
            "index_linear": index_ok,
            "max_index_drift": max((row["drift"] for row in index_rows),
                                   default=None),
            "linear": (observed == expected) and index_ok}


def raw_structure(raw: str) -> dict:
    """raw를 구조적으로만 분석한다. 잘린 JSON을 복구하지 않는다."""
    if RAW_SALVAGE_ALLOWED:
        raise ForensicError("raw salvage는 금지돼 있다")
    objects = [{"index": index, "start_sec": float(match.group(1)),
                "end_sec": float(match.group(2)), "actor": match.group(3),
                "action": match.group(4), "object_or_state": match.group(5),
                "offset": match.start()}
               for index, match in enumerate(OBJECT_RE.finditer(raw))]
    signatures = [(row["actor"], row["action"], row["object_or_state"])
                  for row in objects]
    seen, first_repeat = {}, None
    for index, signature in enumerate(signatures):
        if signature in seen and first_repeat is None:
            first_repeat = {"object_index": index,
                            "first_seen_index": seen[signature],
                            "offset": objects[index]["offset"],
                            "signature": list(signature)}
        seen.setdefault(signature, index)
    counts = {}
    for signature in signatures:
        counts[signature] = counts.get(signature, 0) + 1
    top = sorted(counts.items(), key=lambda row: -row[1])[:3]
    try:
        json.loads(raw)
        parse_ok, parse_error = True, None
    except Exception as error:                     # noqa: BLE001
        parse_ok, parse_error = False, str(error)[:200]
    return {
        "raw_length": len(raw),
        "complete_object_count": len(objects),
        "unique_signature_count": len(set(signatures)),
        "zero_length_interval_count": sum(
            1 for row in objects if row["start_sec"] == row["end_sec"]),
        "first_repeat": first_repeat,
        "max_signature_repeat": max(counts.values(), default=0),
        "top_signatures": [{"signature": list(signature), "count": count}
                           for signature, count in top],
        "json_parse_ok": parse_ok, "json_parse_error": parse_error,
        "truncation_tail": raw[-120:],
        "ends_mid_object": not raw.rstrip().endswith("}")
        and not raw.rstrip().endswith("]"),
    }


def visual_metrics(frames) -> dict:
    """C4 지표 — descriptive diagnostic. 분류에 쓰지 않는다."""
    import numpy

    grays = [numpy.asarray(frame.convert("L"), dtype=numpy.float32)
             for frame in frames]
    luma = [float(gray.mean()) for gray in grays]
    diffs = [float(numpy.abs(grays[index + 1] - grays[index]).mean())
             for index in range(len(grays) - 1)]
    return {
        "frame_count": len(grays),
        "mean_luma": round(sum(luma) / len(luma), 3),
        "min_luma": round(min(luma), 3), "max_luma": round(max(luma), 3),
        "black_frame_ratio": round(
            sum(1 for value in luma if value < BLACK_LUMA_THRESHOLD)
            / len(luma), 4),
        "mean_adjacent_diff": round(sum(diffs) / len(diffs), 3) if diffs
        else None,
        "near_static_ratio": round(
            sum(1 for value in diffs
                if value < NEAR_STATIC_DIFF_THRESHOLD) / len(diffs), 4)
        if diffs else None,
        "thresholds": {"black_luma": BLACK_LUMA_THRESHOLD,
                       "near_static_diff": NEAR_STATIC_DIFF_THRESHOLD},
        "used_in_classification": VISUAL_METRICS_IN_CLASSIFICATION,
    }


def input_anomaly(evidence: dict) -> dict:
    """A 축 — W00에만 적용된 입력 경로 차이가 있는가."""
    reasons = []
    if not evidence["prompt_matches_template"]:
        reasons.append("PROMPT_NOT_FROM_TEMPLATE")
    if evidence["prompt_diff_outside_numbers"]:
        reasons.append("PROMPT_DIFF_BEYOND_TIME_VALUES")
    if evidence["window_specific_branches"]:
        reasons.append("WINDOW_SPECIFIC_CODE_BRANCH")
    if not evidence["grid_linear"]:
        reasons.append("FRAME_GRID_NOT_LINEAR")
    if not evidence["frame_hashes_match_bank"]:
        reasons.append("SAMPLED_PIXELS_DIFFER_FROM_BANK")
    if not evidence["runtime_config_hash_matches_controls"]:
        reasons.append("RUNTIME_CONFIG_HASH_DIFFERS")
    return {"axis": INPUT_ANOMALY, "found": bool(reasons), "reasons": reasons}


def output_degeneracy(structure: dict) -> dict:
    """B 축 — raw가 구조적으로 반복 생성이며 미완결인가."""
    repeated = structure["max_signature_repeat"] >= 2
    unterminated = not structure["json_parse_ok"]
    reasons = []
    if repeated:
        reasons.append("DOMINANT_SIGNATURE_REPEAT")
    if unterminated:
        reasons.append("JSON_UNTERMINATED")
    return {"axis": OUTPUT_DEGENERACY,
            "confirmed": repeated and unterminated, "reasons": reasons}


def classify(anomaly_found: bool, degeneracy_confirmed: bool) -> str:
    """사전등록 진리표 그대로."""
    if anomaly_found and not degeneracy_confirmed:
        return INPUT_PIPELINE_DEFECT
    if degeneracy_confirmed and not anomaly_found:
        return MODEL_OUTPUT_DEGENERACY
    if anomaly_found and degeneracy_confirmed:
        return MIXED
    return UNRESOLVED


def parser_responsibility(structure: dict) -> dict:
    """C6 — raw가 미완결이면 parser 탓으로 돌리지 않는다."""
    if not structure["json_parse_ok"]:
        return {"attributed_to": "MODEL_OUTPUT",
                "note": ("raw 자체가 미완결 JSON이다 — parser가 완결 출력을 "
                         "잘못 처리한 사례가 아니다")}
    return {"attributed_to": "PARSER_CANDIDATE",
            "note": "raw가 완결 JSON인데 파싱이 실패했다면 parser를 조사해야 한다"}
