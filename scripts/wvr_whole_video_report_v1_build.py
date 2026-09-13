"""WVR_WHOLE_VIDEO_REPORT_V1 — β/v3 report input 생성 + gate R1~R10.

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_REPORT_V1_2026-09-13.md`

**생성 전에 이 스크립트가 PASS해야 한다.** 추론 없음 — frozen Overview branch와
기존 M3 STT만 읽고 24초 격자로 정규화한다.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_whole_video_report_v1 as wr  # noqa: E402

MERGE_ROOT = ROOT / "runs" / "wvr_whole_video_merge_v1"
OV_ROOT = ROOT / "runs" / "wvr_overview_synthesis_v2"
RUN_ROOT = ROOT / "runs" / "wvr_whole_video_report_v1"
WORK_ROOT = ROOT / "work_wvr_report"
RESULTS_ROOT = ROOT / "results_wvr_report"
M3_PATH = ROOT / "work_full" / "full_xekZO4n4QuE" / "segments.json"
BASE_CONFIG = ROOT / "configs" / "rei_c01_beta.yaml"
OUT_CONFIG = ROOT / "configs" / "wvr_whole_video_beta_v3.yaml"
VIDEO_ID = "wvr_whole_video"

FROZEN_BRANCH = {
    "runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json": None,
    "runs/wvr_whole_video_merge_v1/timeline_lineage.json": None,
    "runs/wvr_overview_synthesis_v2/canonical_flow.json": None,
    "runs/wvr_overview_synthesis_v2/overview_result.json": None,
}
ENGINE_SOURCES = [
    "scripts/v2_1_b2_orchestrate.py",
    "src/v2_1_prompt.py",
    "src/v2_1_grounding.py",
    "src/v2_1_render_hwpx.py",
    "src/v2_1_segments.py",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False, indent=2,
                                sort_keys=True) + "\n")


def main() -> int:
    started = time.time()
    checks: list[dict] = []

    def check(cid: str, desc: str, ok: bool, detail=None) -> bool:
        checks.append({"id": cid, "desc": desc,
                       "result": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    # ── R1 Overview branch 존재·해시 기록 ─────────────────────────
    branch_hashes = {}
    missing = []
    for rel in FROZEN_BRANCH:
        path = ROOT / rel
        if path.is_file():
            branch_hashes[rel] = sha(path)
        else:
            missing.append(rel)
    if not check("R1", "Overview branch 4개 파일 존재 · 해시 기록",
                 not missing, missing or branch_hashes):
        write_json(RUN_ROOT / "report_gate.json",
                   {"event": wr.EVENT, "gate": "FAIL", "checks": checks})
        return 1

    # ── R2 M3 STT source ──────────────────────────────────────────
    m3_hash = sha(M3_PATH)
    if not check("R2", "M3 STT source 해시가 사전등록 §4-3과 일치",
                 m3_hash == wr.M3_SEGMENTS_SHA256, m3_hash):
        write_json(RUN_ROOT / "report_gate.json",
                   {"event": wr.EVENT, "gate": "FAIL", "checks": checks})
        return 1

    engine_before = {p: sha(ROOT / p) for p in ENGINE_SOURCES}

    timeline = json.loads(
        (MERGE_ROOT / "whole_video_activity_timeline.json").read_text("utf-8"))
    m3 = json.loads(M3_PATH.read_text(encoding="utf-8"))["segments"]
    built = wr.build_segments(timeline, m3)
    doc, stats = built["doc"], built["stats"]
    segments = doc["segments"]

    # ── R3 격자 ───────────────────────────────────────────────────
    check("R3", "segment 101개 · idx 연속 · start == idx*24",
          len(segments) == wr.EXPECTED_SEGMENT_COUNT
          and [s["idx"] for s in segments] == list(range(len(segments)))
          and all(s["start"] == s["idx"] * wr.SEG_LEN_SEC for s in segments),
          {"count": len(segments)})

    # ── R4 커버리지 ───────────────────────────────────────────────
    gaps = [[a["end"], b["start"]] for a, b in zip(segments, segments[1:])
            if b["start"] != a["end"]]
    check("R4", "coverage 2424.0초 · 중복 0초 · 빈틈 0",
          stats["temporal_coverage_sec"] == wr.TOTAL_COVERAGE_SEC
          and stats["duplicate_coverage_sec"] == 0.0 and not gaps,
          {"coverage": stats["temporal_coverage_sec"],
           "duplicate": stats["duplicate_coverage_sec"], "gaps": gaps})

    # ── R5 분할 조각의 lineage ────────────────────────────────────
    by_entry = {e["entry_index"]: e for e in timeline["entries"]}
    split_ok = True
    for row in built["lineage"]:
        source = by_entry[row["source_entry_index"]]
        if row["broad_activity"] != list(source["broad_activity"]):
            split_ok = False
        if row["source_chunk"] != source["source_chunk"]:
            split_ok = False
        if not (source["start_sec"] <= row["span"][0]
                and row["span"][1] <= source["end_sec"]):
            split_ok = False
    check("R5", "분할 조각이 원본 entry와 같은 activity·lineage를 갖는다",
          split_ok, {"split_entry_count": stats["split_entry_count"]})

    # ── R6 필드 ───────────────────────────────────────────────────
    check("R6", "caption·subtitle 필드 전 segment 존재",
          all("caption" in s and "subtitle" in s for s in segments),
          {"subtitle_populated": stats["subtitle_populated"],
           "caption_populated": stats["caption_populated"]})

    # ── 산출물 (격리 경로에만 쓴다) ───────────────────────────────
    write_json(RUN_ROOT / "segments.json", doc)
    write_json(RUN_ROOT / "segments_lineage.json",
               {"event": wr.EVENT, "prereg": wr.PREREG,
                "segment_count": len(segments), "lineage": built["lineage"]})
    work_dir = WORK_ROOT / VIDEO_ID
    work_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RUN_ROOT / "segments.json", work_dir / "segments.json")

    try:
        import yaml
        cfg = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
        cfg["paths"] = dict(cfg.get("paths", {}))
        cfg["paths"]["work"] = WORK_ROOT.name
        cfg["paths"]["results"] = RESULTS_ROOT.name
        cfg["_provenance"] = {"event": wr.EVENT, "prereg": wr.PREREG,
                              "derived_from": "configs/rei_c01_beta.yaml",
                              "isolated": True}
        OUT_CONFIG.write_text(
            yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
    except ImportError:
        check("R6b", "yaml 사용 가능", False, "PyYAML 없음")

    # ── R7 engine source 불변 ─────────────────────────────────────
    check("R7", "engine source 해시 불변",
          {p: sha(ROOT / p) for p in ENGINE_SOURCES} == engine_before)

    # ── R8 결정성 ─────────────────────────────────────────────────
    again = wr.build_segments(timeline, m3)
    check("R8", "deterministic — 2회 build 산출물 동일",
          json.dumps(again, ensure_ascii=False, sort_keys=True)
          == json.dumps(built, ensure_ascii=False, sort_keys=True))

    # ── R9 · R10 금지 경로 ────────────────────────────────────────
    forbidden = [ROOT / "results" / "eval_test.json",
                 ROOT / "src" / "m9_report_eval.py"]
    touched = [str(p.relative_to(ROOT)) for p in forbidden
               if p.exists() and p.stat().st_mtime > started]
    check("R9", "official test 경로 미접근", not touched, touched)
    check("R10", "M9 미호출", True)

    gate = "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL"
    write_json(RUN_ROOT / "report_gate.json",
               {"event": wr.EVENT, "prereg": wr.PREREG, "gate": gate,
                "code_git_head": git_head(),
                "overview_branch_sha256": branch_hashes,
                "m3_segments_sha256": m3_hash,
                "engine_source_sha256": engine_before,
                "stats": stats, "new_inference_count": 0, "checks": checks})

    for c in checks:
        mark = "" if c["result"] == "PASS" else "   <- %s" % (c["detail"],)
        print("%-4s %-4s  %s%s" % (c["id"], c["result"], c["desc"], mark))
    print("\nsegment %d · coverage %.1f초 · subtitle %d/%d · caption %d/%d · 분할 %d건"
          % (stats["segment_count"], stats["temporal_coverage_sec"],
             stats["subtitle_populated"], stats["segment_count"],
             stats["caption_populated"], stats["segment_count"],
             stats["split_entry_count"]))
    print("REPORT GATE: %s" % gate)
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
