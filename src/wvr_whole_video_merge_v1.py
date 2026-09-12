"""WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1 — 결정적 whole-video timeline merge.

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1_2026-09-13.md`

frozen C01~C05 WVR 관찰만 읽는다. **추론하지 않는다** — 시간 구간을 다시 계산하고
소유 chunk를 index로 고르며, 관찰 텍스트를 재작성하지 않는다.

중복 제거 규칙(§3)은 여기서 상수·함수로 박는다. 결과를 보고 바꾸지 않는다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import wvr_chunk_overview_v2 as cv
import wvr_video_overview_preview_v2 as ov

EVENT = "WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1"
PREREG = ("docs/preregistration/"
          "WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1_2026-09-13.md")

CHUNK_IDS = ("C01", "C02", "C03", "C04", "C05")
C01_RUNS = "runs/wvr_video_overview_preview_v2"
CHUNK_RUNS_ROOT = "runs/wvr_chunk_overview_v2"

VIDEO_DURATION_SEC = cv.VIDEO_DURATION_SEC          # 2424.186485
OBSERVED_END_SEC = 2424.0                           # C05 마지막 창의 끝
TERMINAL_REMAINDER = (OBSERVED_END_SEC, VIDEO_DURATION_SEC)

# §1 동결 source 해시
FROZEN_SHA256 = {
    "C01": {
        "video_overview_v2_segment_summaries.json":
            "35c964e30c35d05957b717fd24aba3225ec2082c50addcebed61c081fc217edc",
        "video_overview_v2_segments.json":
            "b4dac6ce532f1a37bf31392fe14f7b557b2b9e3b786dbcd8d84d765f2068bef0"},
    "C02": {
        "video_overview_v2_segment_summaries.json":
            "a91eb783b07b97d3781f99e9d3365404d69291842c340104c535db5f1642c4d0",
        "video_overview_v2_segments.json":
            "2a82080e3d3da802033fee228e40a3493c2630b6abb0e9bc510eb4d5e1f20947"},
    "C03": {
        "video_overview_v2_segment_summaries.json":
            "cc0a0ebaf906987ee4ebffb1983e97b6297cb4cee21d31bd4768fbbc753f6569",
        "video_overview_v2_segments.json":
            "6bc7380319fb62612f85e2a5e7183b82bec6e9970a7e4b38abbd152ed2697927"},
    "C04": {
        "video_overview_v2_segment_summaries.json":
            "06f3a17c95716da3418d59a879a3eae0dccc3d38bd0edc3c4bec6b12297ec8f3",
        "video_overview_v2_segments.json":
            "3bdb9e584fbbca7ef85fd0fa80dd61213fc587e62936244eef8ba837ed89828e"},
    "C05": {
        "video_overview_v2_segment_summaries.json":
            "d6e74b0652028d99165ade269bd5f3d2de9891163cf9f1ed5e288f2d9201e9b4",
        "video_overview_v2_segments.json":
            "5f1f4c7b7a53f0858be9618ea2adb12a1aefd78c8a867bf47bb247a1237059d6"},
}


class MergeError(RuntimeError):
    """merge 계약 위반. 조용히 넘어가지 않는다."""


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chunk_dir(root, chunk_id: str) -> Path:
    root = Path(root)
    if chunk_id == "C01":
        return root / C01_RUNS
    return root / CHUNK_RUNS_ROOT / chunk_id


# ── §3-2 chunk 소유 구간 ────────────────────────────────────────────
def ownership() -> dict[str, tuple[float, float]]:
    """절대 시각 t의 소유자는 t를 포함하는 최저 index chunk다.

    내용을 보지 않는다 — index만 본다.
    """
    plan = {row["chunk_id"]: row for row in cv.chunk_plan()}
    owned: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for chunk_id in CHUNK_IDS:
        start = max(float(plan[chunk_id]["start_sec"]), cursor)
        end = float(plan[chunk_id]["end_sec"])
        if chunk_id == CHUNK_IDS[-1]:
            end = min(end, OBSERVED_END_SEC)   # terminal remainder는 관찰이 없다
        if end <= start:
            raise MergeError("%s 소유 구간이 비었다" % chunk_id)
        owned[chunk_id] = (round(start, 6), round(end, 6))
        cursor = end
    return owned


# ── §3-1 window NONOVERLAP 정규화 ───────────────────────────────────
def nonoverlap_spans(chunk_id: str) -> list[tuple[float, float]]:
    """창 i는 [s_i, s_i+1) 를, 마지막 창만 [s_n-1, e_n-1) 를 대표한다."""
    rows = cv.windows(chunk_id)
    spans = []
    for index, row in enumerate(rows):
        start = float(row["start_sec"])
        end = (float(rows[index + 1]["start_sec"]) if index < len(rows) - 1
               else float(row["end_sec"]))
        if end <= start:
            raise MergeError("%s W%02d 구간이 비었다" % (chunk_id, index))
        spans.append((round(start, 6), round(end, 6)))
    return spans


def load_chunk(root, chunk_id: str) -> dict:
    """frozen 산출물을 읽고 §1 해시를 강제한다."""
    directory = chunk_dir(root, chunk_id)
    actual, payload = {}, {}
    for name in FROZEN_SHA256[chunk_id]:
        path = directory / name
        actual[name] = sha256_file(path)
        if actual[name] != FROZEN_SHA256[chunk_id][name]:
            raise MergeError("frozen source 해시 불일치 %s/%s: %s != %s"
                             % (chunk_id, name, actual[name],
                                FROZEN_SHA256[chunk_id][name]))
        payload[name] = json.loads(path.read_text(encoding="utf-8"))
    summaries = payload["video_overview_v2_segment_summaries.json"]
    plan = payload["video_overview_v2_segments.json"]
    if len(summaries) != len(plan) != cv.EXPECTED_WINDOW_COUNT[chunk_id]:
        raise MergeError("%s 창 수 불일치" % chunk_id)
    if plan != cv.segments(chunk_id):
        raise MergeError("%s 창 계획이 동결 기하와 다르다" % chunk_id)
    return {"summaries": summaries, "plan": plan, "sha256": actual}


def build_timeline(root=".") -> dict:
    """C01~C05 창 관찰을 절대 시각 timeline으로 합친다. 추론 없음."""
    owned = ownership()
    entries, lineage = [], []
    dup_before_total = 0.0

    for chunk_id in CHUNK_IDS:
        loaded = load_chunk(root, chunk_id)
        spans = nonoverlap_spans(chunk_id)
        plan = loaded["plan"]
        own_start, own_end = owned[chunk_id]

        # 정규화 전 노출: 원래 창은 48초씩이고 서로 겹친다
        dup_before_total += sum(float(w["end_sec"]) - float(w["start_sec"])
                                for w in plan)

        for index, (span, window, summary) in enumerate(
                zip(spans, plan, loaded["summaries"])):
            start, end = span
            if end <= own_start or start >= own_end:
                continue          # 다른 chunk가 소유한 시간 — 통째로 버린다
            if start < own_start or end > own_end:
                raise MergeError(
                    "%s W%02d 이 소유 경계를 가로지른다 %r vs %r — 동결 산술 위반"
                    % (chunk_id, index, span, (own_start, own_end)))
            if summary["segment_id"] != window["segment_id"]:
                raise MergeError("%s segment_id 짝이 어긋난다" % chunk_id)

            entry = {
                "entry_index": len(entries),
                "start_sec": start,
                "end_sec": end,
                "broad_activity": list(summary["BROAD_ACTIVITY"]),
                "source_chunk": chunk_id,
                "source_window": {
                    "segment_id": window["segment_id"],
                    "start_sec": float(window["start_sec"]),
                    "end_sec": float(window["end_sec"]),
                },
                "source_artifact_sha256": dict(loaded["sha256"]),
            }
            entries.append(entry)
            lineage.append({
                "entry_index": entry["entry_index"],
                "timeline_span": [start, end],
                "source_chunk": chunk_id,
                "source_window": dict(entry["source_window"]),
                "source_artifact_sha256": dict(loaded["sha256"]),
                "observation_fields_present": sorted(summary),
            })

    _validate(entries)
    covered = round(sum(e["end_sec"] - e["start_sec"] for e in entries), 6)
    return {
        "event": EVENT,
        "prereg": PREREG,
        "video_duration_sec": VIDEO_DURATION_SEC,
        "observed_end_sec": OBSERVED_END_SEC,
        "terminal_remainder_sec": round(VIDEO_DURATION_SEC - OBSERVED_END_SEC, 6),
        "terminal_remainder_span": list(TERMINAL_REMAINDER),
        "chunk_ownership": {k: list(v) for k, v in owned.items()},
        "entry_count": len(entries),
        "temporal_coverage_sec": covered,
        "duplicate_coverage_before_sec": round(dup_before_total - covered, 6),
        "duplicate_coverage_after_sec": 0.0,
        "new_visual_inference": 0,
        "new_stt_inference": 0,
        "entries": entries,
        "lineage": lineage,
    }


def _validate(entries: list[dict]) -> None:
    if not entries:
        raise MergeError("entry가 없다")
    if [e["entry_index"] for e in entries] != list(range(len(entries))):
        raise MergeError("entry_index가 0부터 연속이 아니다")
    cursor = 0.0
    for entry in entries:
        if entry["start_sec"] != round(cursor, 6):
            raise MergeError("빈틈 또는 겹침: %r 에서 %r 를 기대했다"
                             % (entry["start_sec"], cursor))
        if entry["end_sec"] <= entry["start_sec"]:
            raise MergeError("end <= start: %r" % entry["entry_index"])
        cursor = entry["end_sec"]
    if round(cursor, 6) != OBSERVED_END_SEC:
        raise MergeError("마지막 entry가 %r 에서 끝난다" % cursor)


def timeline_markdown(timeline: dict) -> str:
    """사람이 읽는 형태. 관찰 label을 재작성하지 않는다."""
    lines = [
        "# whole-video activity timeline (C01~C05 merge)",
        "",
        "- event: `%s`" % timeline["event"],
        "- 원본 길이: %.6f초 · 관찰 union: [0, %.1f)" % (
            timeline["video_duration_sec"], timeline["observed_end_sec"]),
        "- terminal remainder: %.6f초 [%.1f, %.6f) — 관찰된 창 없음" % (
            timeline["terminal_remainder_sec"], *timeline["terminal_remainder_span"]),
        "- entry %d개 · 커버리지 %.1f초 · 정규화 후 중복 %.1f초" % (
            timeline["entry_count"], timeline["temporal_coverage_sec"],
            timeline["duplicate_coverage_after_sec"]),
        "",
        "| # | start | end | broad activity | chunk | window |",
        "|---|-------|-----|----------------|-------|--------|",
    ]
    for entry in timeline["entries"]:
        lines.append("| %d | %.1f | %.1f | %s | %s | %s |" % (
            entry["entry_index"], entry["start_sec"], entry["end_sec"],
            " · ".join(entry["broad_activity"]) or "(없음)",
            entry["source_chunk"], entry["source_window"]["segment_id"]))
    return "\n".join(lines) + "\n"


def synthesis_summaries(timeline: dict) -> list[dict]:
    """V2 압축기가 받는 형태. `OBSERVED_CHANGE`는 빈 채로 넘긴다(§6)."""
    return [{"segment_id": "G%03d" % (entry["entry_index"] + 1),
             "BROAD_ACTIVITY": list(entry["broad_activity"]),
             "OBSERVED_CHANGE": []}
            for entry in timeline["entries"]]


def synthesis_prompt(timeline: dict) -> tuple[str, dict]:
    """V2 프롬프트를 그대로 쓴다. 새 프롬프트를 만들지 않는다(§5)."""
    compressed = ov.compress_activity_timeline(synthesis_summaries(timeline))
    return ov.synthesis_prompt(compressed), compressed
