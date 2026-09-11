"""WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1 adapter.

사전등록: `docs/preregistration/WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1_2026-09-11.md`

C01 frozen WVR broad visual summary + 기존 M3 STT를 보고서 엔진 입력
(`segments.json`)으로 결정적으로 변환한다. **새 inference를 하지 않는다** —
읽기만 하고 시간 구간을 재계산하며 기존 문자열을 재작성하지 않는다.

동결 규칙(§3~§5)은 여기서 상수로 박는다. 결과를 보고 바꾸지 않는다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EVENT = "WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1"
PREREG = ("docs/preregistration/"
          "WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1_2026-09-11.md")

# ── 동결 기하 (prereg §3) ────────────────────────────────────────────
RANGE_START_SEC = 0.0
RANGE_END_SEC = 600.0
WINDOW_SEC = 48.0
STRIDE_SEC = 24.0
EXPECTED_WINDOW_COUNT = 24

OVERLAP_VIEW = "OVERLAP_VIEW"
NONOVERLAP_VIEW = "NONOVERLAP_VIEW"
VIEWS = (OVERLAP_VIEW, NONOVERLAP_VIEW)

# ── 동결 caption 규칙 (prereg §4) ───────────────────────────────────
CAPTION_FIELDS = ("BROAD_ACTIVITY", "OBSERVED_CHANGE")
EXCLUDED_FIELDS = ("CONTEXT_INFERENCE", "UNCERTAINTY")
JOIN = " · "
CHANGE_PREFIX = " / 변화: "
EMPTY_CAPTION = "(관측 요약 없음)"

# ── 동결 source 해시 (prereg §2) ────────────────────────────────────
FROZEN_SHA256 = {
    "video_overview_v2_segment_summaries.json":
        "35c964e30c35d05957b717fd24aba3225ec2082c50addcebed61c081fc217edc",
    "video_overview_v2_segments.json":
        "b4dac6ce532f1a37bf31392fe14f7b557b2b9e3b786dbcd8d84d765f2068bef0",
    "work_full_segments.json":
        "aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92",
}


class AdapterError(RuntimeError):
    """동결 규칙 위반. 조용히 넘어가지 않는다."""


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ── 시간 구간 (prereg §3-1 · §3-2) ──────────────────────────────────
def interval(idx: int, view: str) -> tuple[float, float]:
    """adapter segment의 [start, end). 동결 규칙이므로 분기를 숨기지 않는다."""
    if view not in VIEWS:
        raise AdapterError(f"알 수 없는 view: {view}")
    if not 0 <= idx < EXPECTED_WINDOW_COUNT:
        raise AdapterError(f"idx 범위 밖: {idx}")
    start = idx * STRIDE_SEC
    if view == OVERLAP_VIEW:
        end = min(start + WINDOW_SEC, RANGE_END_SEC)
    else:
        last = idx == EXPECTED_WINDOW_COUNT - 1
        end = RANGE_END_SEC if last else start + STRIDE_SEC
    return start, end


def duplicate_coverage_sec(rows: list[dict]) -> float:
    """인접 segment 간 겹침 총합(초). NONOVERLAP_VIEW에서는 0이어야 한다."""
    total = 0.0
    for a, b in zip(rows, rows[1:]):
        total += max(0.0, a["end"] - b["start"])
    return round(total, 6)


def temporal_coverage_sec(rows: list[dict]) -> float:
    """중복을 제거한 실제 커버 시간(초)."""
    merged: list[list[float]] = []
    for r in sorted(rows, key=lambda x: x["start"]):
        if merged and r["start"] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], r["end"])
        else:
            merged.append([r["start"], r["end"]])
    return round(sum(e - s for s, e in merged), 6)


# ── caption (prereg §4) ─────────────────────────────────────────────
def build_caption(summary: dict) -> str:
    """broad visual summary만 쓴다. 원문을 재작성하지 않는다."""
    for field in EXCLUDED_FIELDS:
        if field not in summary:
            raise AdapterError(f"summary에 {field} 키가 없다 — source 스키마 불일치")
    broad = [str(x).strip() for x in summary.get("BROAD_ACTIVITY", []) if str(x).strip()]
    change = [str(x).strip() for x in summary.get("OBSERVED_CHANGE", []) if str(x).strip()]
    if not broad and not change:
        return EMPTY_CAPTION
    text = JOIN.join(broad)
    if change:
        text = (text + CHANGE_PREFIX + JOIN.join(change)) if text else \
            (CHANGE_PREFIX.strip() + " " + JOIN.join(change))
    return text


# ── subtitle (prereg §5) ────────────────────────────────────────────
def aggregate_subtitle(m3_segments: list[dict], start: float, end: float) -> list[dict]:
    """양의 겹침(접점 제외)만 포함. 원본 순서 유지. 문자열 수정 금지."""
    picked = []
    for s in m3_segments:
        sj, ej = float(s["start"]), float(s["end"])
        if min(ej, end) - max(sj, start) > 0:
            picked.append(s)
    picked.sort(key=lambda s: (float(s["start"]), int(s["idx"])))
    return picked


def subtitle_text(picked: list[dict]) -> str:
    parts = [str(s.get("subtitle", "")).strip() for s in picked]
    return " ".join(p for p in parts if p)


# ── 본체 ────────────────────────────────────────────────────────────
def build_view(summaries: list[dict], plan: list[dict],
               m3_segments: list[dict], view: str) -> dict:
    """한 view의 segments.json 문서 + lineage를 만든다."""
    if len(summaries) != EXPECTED_WINDOW_COUNT:
        raise AdapterError(f"summary 수가 {EXPECTED_WINDOW_COUNT}가 아니다: {len(summaries)}")
    if len(plan) != EXPECTED_WINDOW_COUNT:
        raise AdapterError(f"plan 수가 {EXPECTED_WINDOW_COUNT}가 아니다: {len(plan)}")

    by_id = {row["segment_id"]: row for row in plan}
    segments, lineage = [], []

    for idx, summary in enumerate(sorted(summaries, key=lambda s: s["segment_id"])):
        sid = summary["segment_id"]
        if sid not in by_id:
            raise AdapterError(f"plan에 {sid} 없음")
        window = by_id[sid]
        expected_start = idx * STRIDE_SEC
        if float(window["start_sec"]) != expected_start:
            raise AdapterError(
                f"{sid} 창 시작이 {window['start_sec']} — 동결 기하 {expected_start} 위반")

        start, end = interval(idx, view)
        picked = aggregate_subtitle(m3_segments, start, end)
        caption = build_caption(summary)

        segments.append({
            "idx": idx,
            "start": start,
            "end": end,
            "subtitle": subtitle_text(picked),
            "caption": caption,
        })
        lineage.append({
            "adapter_idx": idx,
            "wvr_window": {"segment_id": sid,
                           "start_sec": float(window["start_sec"]),
                           "end_sec": float(window["end_sec"])},
            "broad_visual_summary": {
                "BROAD_ACTIVITY": list(summary.get("BROAD_ACTIVITY", [])),
                "OBSERVED_CHANGE": list(summary.get("OBSERVED_CHANGE", [])),
            },
            "adapter_segment": {"idx": idx, "start": start, "end": end,
                                "caption": caption},
            "subtitle_source_m3_idx": [int(s["idx"]) for s in picked],
        })

    if [s["idx"] for s in segments] != list(range(EXPECTED_WINDOW_COUNT)):
        raise AdapterError("idx가 0부터 연속이 아니다")
    for s in segments:
        if s["start"] != s["idx"] * STRIDE_SEC:
            raise AdapterError(f"start 불변식 위반: idx={s['idx']} start={s['start']}")
        if s["end"] <= s["start"]:
            raise AdapterError(f"end <= start: idx={s['idx']}")

    doc = {
        "video_id": None,          # 호출자가 cell별로 채운다
        "duration_sec": RANGE_END_SEC,
        "fps": None,
        "n_segments": len(segments),
        "segments": segments,
        "provenance": {
            "event": EVENT,
            "prereg": PREREG,
            "view": view,
            "geometry": {"window_sec": WINDOW_SEC, "stride_sec": STRIDE_SEC,
                         "range": [RANGE_START_SEC, RANGE_END_SEC]},
            "new_inference_count": 0,
            "source_sha256": dict(FROZEN_SHA256),
        },
    }
    stats = {
        "view": view,
        "segment_count": len(segments),
        "temporal_coverage_sec": temporal_coverage_sec(segments),
        "duplicate_temporal_coverage_sec": duplicate_coverage_sec(segments),
        "subtitle_populated": sum(1 for s in segments if s["subtitle"]),
        "caption_populated": sum(1 for s in segments
                                 if s["caption"] and s["caption"] != EMPTY_CAPTION),
    }
    return {"doc": doc, "lineage": lineage, "stats": stats}


def load_sources(wvr_dir, m3_segments_path) -> dict:
    wvr = Path(wvr_dir)
    summaries_path = wvr / "video_overview_v2_segment_summaries.json"
    plan_path = wvr / "video_overview_v2_segments.json"
    m3_path = Path(m3_segments_path)

    actual = {
        "video_overview_v2_segment_summaries.json": sha256_file(summaries_path),
        "video_overview_v2_segments.json": sha256_file(plan_path),
        "work_full_segments.json": sha256_file(m3_path),
    }
    for name, expected in FROZEN_SHA256.items():
        if actual[name] != expected:
            raise AdapterError(
                f"frozen source 해시 불일치 {name}: {actual[name]} != {expected}")

    with open(summaries_path, encoding="utf-8") as f:
        summaries = json.load(f)
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    with open(m3_path, encoding="utf-8") as f:
        m3 = json.load(f)
    return {"summaries": summaries, "plan": plan,
            "m3_segments": m3["segments"], "source_sha256": actual}
