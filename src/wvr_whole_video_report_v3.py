"""Deterministic usability layer over the frozen whole-video report V2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EVENT = "WVR_WHOLE_VIDEO_REPORT_V3_USABILITY"


class V3Error(RuntimeError):
    """The frozen source cannot satisfy the V3 usability contract."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_blocks(entries: list[dict], allowed: set[str], observed_end: float) -> list[dict]:
    """Merge adjacent entries only when their complete activity tuple matches."""
    blocks: list[dict] = []
    cursor = 0.0
    for row in entries:
        start, end = float(row["start_sec"]), float(row["end_sec"])
        if start != cursor:
            raise V3Error(f"timeline gap or overlap at {cursor}: next={start}")
        if end <= start:
            raise V3Error(f"non-positive timeline entry: {start}..{end}")
        activities = list(row["broad_activity"])
        unknown = set(activities) - allowed
        if unknown:
            raise V3Error(f"unknown activity: {sorted(unknown)}")
        source = {
            "entry_index": int(row["entry_index"]),
            "source_chunk": row["source_chunk"],
            "source_window": dict(row["source_window"]),
            "source_artifact_sha256": dict(row["source_artifact_sha256"]),
        }
        if blocks and blocks[-1]["activities"] == activities:
            blocks[-1]["end_sec"] = end
            blocks[-1]["entry_indices"].append(int(row["entry_index"]))
            blocks[-1]["sources"].append(source)
        else:
            blocks.append({
                "block_index": len(blocks),
                "start_sec": start,
                "end_sec": end,
                "duration_sec": end - start,
                "activities": activities,
                "entry_indices": [int(row["entry_index"])],
                "sources": [source],
            })
        blocks[-1]["duration_sec"] = blocks[-1]["end_sec"] - blocks[-1]["start_sec"]
        cursor = end
    if cursor != float(observed_end):
        raise V3Error(f"timeline gap at end: {cursor} != {observed_end}")
    return blocks


def _overlap(block: dict, start: float, end: float) -> float:
    return max(0.0, min(block["end_sec"], end) - max(block["start_sec"], start))


def select_highlights(blocks: list[dict], final_span: list[float],
                      observed_end: float) -> list[dict]:
    """Pick one maximal-overlap block per clock stratum, then the final phase."""
    selected: list[dict] = []
    selected_indices: set[int] = set()
    for stratum_index in range(6):
        start = observed_end * stratum_index / 6
        end = observed_end * (stratum_index + 1) / 6
        ranked = sorted(
            (b for b in blocks if b["block_index"] not in selected_indices),
            key=lambda b: (-_overlap(b, start, end), -b["duration_sec"],
                           b["start_sec"]),
        )
        if not ranked or _overlap(ranked[0], start, end) <= 0:
            raise V3Error(f"no highlight candidate for stratum {stratum_index}")
        selected.append(ranked[0])
        selected_indices.add(ranked[0]["block_index"])

    final = [b for b in blocks
             if [b["start_sec"], b["end_sec"]] == [float(x) for x in final_span]]
    if len(final) != 1:
        raise V3Error("canonical final phase does not match exactly one block")
    if final[0]["block_index"] not in selected_indices:
        selected.append(final[0])
    selected.sort(key=lambda b: b["start_sec"])
    if not 5 <= len(selected) <= 8:
        raise V3Error(f"highlight count outside 5..8: {len(selected)}")
    return selected


def clock(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def describe(activities: list[str], next_activities: list[str] | None) -> str:
    current = "과 ".join(activities)
    if next_activities:
        following = "과 ".join(next_activities)
        return f"{current} 활동이 이어지며, 이후 대표 구간에서는 {following} 활동으로 전환된다."
    return f"{current} 활동이 이어지며 영상의 관찰 구간이 마무리된다."


def materialize(selected: list[dict]) -> tuple[list[dict], list[dict]]:
    highlights, lineage = [], []
    for index, block in enumerate(selected):
        hid = f"H{index + 1:02}"
        next_activities = selected[index + 1]["activities"] if index + 1 < len(selected) else None
        highlights.append({
            "highlight_id": hid,
            "start_sec": block["start_sec"],
            "end_sec": block["end_sec"],
            "time_range": f"{clock(block['start_sec'])}–{clock(block['end_sec'])}",
            "activities": block["activities"],
            "description": describe(block["activities"], next_activities),
        })
        lineage.append({
            "highlight_id": hid,
            "start_sec": block["start_sec"],
            "end_sec": block["end_sec"],
            "activity": block["activities"],
            "source_timeline_entry_ids": block["entry_indices"],
            "sources": block["sources"],
        })
    return highlights, lineage


def render_report(baseline: dict, one_line: str, highlights: list[dict]) -> str:
    sections = ["# 영상 전체 보고서", "", "## 한 줄 요약", "", one_line.strip(),
                "", "## 개요", "", baseline["short_overview"].strip(),
                "", "## 주요 구간", ""]
    for item in highlights:
        sections.extend([
            f"### {clock(item['start_sec'])}–{clock(item['end_sec'])}", "",
            " · ".join(item["activities"]), "", item["description"], "",
        ])
    sections.extend([
        "## 상세 개요", "", baseline["detailed_overview"].strip(), "",
        "## 분석", "", baseline["analysis"].strip(), "",
        "## 결론", "", baseline["conclusion"].strip(), "",
        "## 생성 및 근거 요약", "",
        "- 전체 영상 약 40분의 동결 시각 관찰 timeline을 기반으로 작성했다.",
        "- 주요 구간은 timeline의 시간과 활동을 결정 규칙으로 압축했으며 새 영상·음성 추론은 하지 않았다.",
        "- 품질 기준을 충족하지 못한 보조 음성·생성 구간은 사실 근거에서 제외했다.",
    ])
    return "\n".join(sections).rstrip() + "\n"


def render_appendix(source_hashes: dict, baseline: dict, selection_commit: str,
                    blocks: int, highlights: int) -> str:
    exclusions = baseline["beta_v3"]["quality_exclusions"]
    rows = [
        "# WVR V3 기술 부록", "", "## 실행", "",
        f"- event: {EVENT}", "- visual inference: 0", "- STT inference: 0",
        "- β/v3 regeneration: 0", "- text generation inference: 0",
        f"- selection rule commit: {selection_commit}",
        f"- contiguous blocks: {blocks}", f"- selected highlights: {highlights}",
        "", "## 동결 입력 SHA256", "",
    ]
    rows.extend(f"- {name}: `{value}`" for name, value in source_hashes.items())
    rows.extend(["", "## β/v3 provenance", "",
                 f"- eligible: {baseline['beta_v3']['eligible']}/{baseline['beta_v3']['episodes']}",
                 f"- quality exclusions: {len(exclusions)}"])
    rows.extend(f"- {key}: {value}" for key, value in exclusions.items())
    rows.extend(["", "## 제한", "",
                 "- 하이라이트 설명은 broad activity와 시간 전환만 사용한다.",
                 "- 동결 소스가 안정적인 물체·장소 디테일을 제공하지 않는 구간에는 세부 묘사를 추가하지 않았다.",
                 "- terminal remainder 0.186485초에는 관찰 window가 없다."])
    return "\n".join(rows).rstrip() + "\n"


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
