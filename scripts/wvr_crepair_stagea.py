"""BOUNDARY_REPAIR_V1 Stage A — 결정적 경계 추출 (LLM·GPU 없음).

사전등록:
`docs/preregistration/WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md`

```
입력   conservative_event_map_v1.json (해시 동결)
출력   chapter_repair_v1_candidates.json · chapter_repair_v1_boundaries.json
규칙   후보 시각은 event 시작 시각뿐 · region·격자 시각 주입 금지 · jitter 금지 ·
      conflict 안 경계는 두 관측 source의 공통 근거 필요
동결   boundaries 파일이 이미 있으면 덮어쓰지 않는다 (경계 동결)
```

사용: `python scripts/wvr_crepair_stagea.py --runs runs/wvr_light_v1`
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_chapter_repair_v1 as cr                           # noqa: E402
import wvr_chapter_selfcheck as v1check                      # noqa: E402

CANDIDATES_NAME = "chapter_repair_v1_candidates.json"
BOUNDARIES_NAME = "chapter_repair_v1_boundaries.json"


class StageAError(RuntimeError):
    """Stage A 계약 위반."""


def _git(*args) -> str:
    done = subprocess.run(["git"] + list(args), cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip()


def _write_text(path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline=chr(10)) as handle:
        handle.write(text)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_a(runs: Path) -> dict:
    try:
        cr.assert_flags_closed()
    except cr.RepairError as error:
        raise StageAError("%s" % error)
    try:
        document = v1check.load_map(runs)
    except v1check.SelfCheckError as error:
        raise StageAError("%s" % error)
    try:
        events = cr.source_events(document)
        rows = cr.candidates(events, document)
        selected = cr.select_boundaries(rows)
    except cr.RepairError as error:
        raise StageAError("%s" % error)
    # chapter 수 조건을 만족하지 못하면 **규칙을 완화하지 않고** blocker로 기록한다
    # (사전등록 §4·§16). 진단 산출물은 그대로 남긴다.
    blocker = None
    chapters = []
    supports = []
    try:
        chapters = cr.chapters_from_boundaries(selected)
        supports = [cr.chapter_support(chapter, document, events)
                    for chapter in chapters]
    except cr.RepairError as error:
        blocker = "%s" % error
    grid = cr.grid_audit(selected, document)
    provenance = {
        "prereg": cr.PREREG, "event": cr.EVENT,
        "prereg_commit": _git("log", "-1", "--format=%H", "--",
                              cr.PREREG) or "unknown",
        "code_git_head": _git("rev-parse", "HEAD") or "unknown",
        "source_map_sha256": cr.SOURCE_MAP_SHA256,
        "stage_a_rule": {
            "candidate_times": "source event start times only",
            "detect_window_sec": cr.DETECT_WINDOW_SEC,
            "sustain_window_sec": cr.SUSTAIN_WINDOW_SEC,
            "min_separation_sec": cr.MIN_SEPARATION_SEC,
            "min_separation_derivation": "video_length / MAX_CHAPTERS",
            "reasons": list(cr.BOUNDARY_REASONS),
            "region_boundary_injected": cr.REGION_BOUNDARY_AS_CANDIDATE_ALLOWED,
            "grid_boundary_injected": cr.GRID_BOUNDARY_AS_CANDIDATE_ALLOWED,
            "jitter_applied": cr.BOUNDARY_JITTER_ALLOWED,
            "llm_used": False},
        "new_vlm_inference_count": 0,
        "track_a_input_used": cr.TRACK_A_INPUT_ALLOWED,
    }
    candidates_doc = {
        "schema": "wvr_chapter_repair_v1_candidates", "event": cr.EVENT,
        "prereg": cr.PREREG, "provenance": provenance,
        "candidate_count": len(rows),
        "accepted_count": sum(1 for row in rows if row["excluded"] is None),
        "exclusion_counts": {name: sum(1 for row in rows
                                       if row["excluded"] == name)
                             for name in ("NO_EVIDENCE_ON_BOTH_SIDES",
                                          "NO_TRANSITION_EVIDENCE",
                                          cr.UNSUPPORTED_BY_CONFLICT)},
        "candidates": rows,
        "selected_boundaries": [row["boundary_sec"] for row in selected],
        "selectable_band": [cr.MIN_SEPARATION_SEC,
                            cr.VIDEO_END_SEC - cr.MIN_SEPARATION_SEC],
        "accepted_outside_band": [row["boundary_sec"] for row in rows
                                  if row["excluded"] is None
                                  and not (cr.MIN_SEPARATION_SEC
                                           <= row["boundary_sec"]
                                           <= cr.VIDEO_END_SEC
                                           - cr.MIN_SEPARATION_SEC)],
        "blocker": blocker,
        "stage_b_executed": False,
        "rule_relaxed": False,
    }
    boundaries_doc = {
        "schema": "wvr_chapter_repair_v1_boundaries", "event": cr.EVENT,
        "prereg": cr.PREREG, "provenance": provenance,
        "selected_count": len(selected),
        "boundaries": selected,
        "chapters": chapters,
        "chapter_support": supports,
        "grid_audit": grid,
        "frozen": True,
        "llm_may_change_boundaries": cr.LLM_MAY_CHANGE_BOUNDARIES_ALLOWED,
    }
    return {"candidates": candidates_doc,
            "boundaries": boundaries_doc if blocker is None else None,
            "blocker": blocker, "document": document, "events": events}


def write_artifacts(runs: Path, built: dict) -> list:
    written = []
    _write_text(runs / CANDIDATES_NAME,
                cr.canonical(built["candidates"]) + chr(10))
    written.append(CANDIDATES_NAME)
    if built["boundaries"] is None:
        return written          # blocker — 경계를 동결하지 않는다
    if (runs / BOUNDARIES_NAME).is_file():
        raise StageAError("경계가 이미 동결돼 있다 — 덮어쓰지 않는다: %s"
                          % BOUNDARIES_NAME)
    _write_text(runs / BOUNDARIES_NAME,
                cr.canonical(built["boundaries"]) + chr(10))
    written.append(BOUNDARIES_NAME)
    return written



def selected_times(built: dict) -> list:
    if built["boundaries"] is not None:
        return [row["boundary_sec"] for row in built["boundaries"]["boundaries"]]
    return built["candidates"]["selected_boundaries"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage A 경계 추출")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = stage_a(runs)
    candidates = built["candidates"]
    print("candidates=%d accepted=%d excluded=%s"
          % (candidates["candidate_count"], candidates["accepted_count"],
             candidates["exclusion_counts"]))
    print("selected=%d boundaries=%s"
          % (len(selected_times(built)), selected_times(built)))
    if built["blocker"]:
        print("BLOCKER %s" % built["blocker"])
        print("accepted 후보 %s · 선택 가능 구간 %s · 구간 밖 accepted %s"
              % ([row["boundary_sec"] for row in candidates["candidates"]
                  if row["excluded"] is None],
                 candidates["selectable_band"],
                 candidates["accepted_outside_band"]))
        for name in write_artifacts(runs, built):
            print("wrote %s" % name)
        print("Stage B는 실행하지 않는다 — 규칙을 완화하지 않고 멈춘다")
        return 2
    boundaries = built["boundaries"]
    print("chapters=%d spans=%s"
          % (len(boundaries["chapters"]),
             [[row["start_sec"], row["end_sec"]]
              for row in boundaries["chapters"]]))
    grid = boundaries["grid_audit"]
    print("grid audit: 24s=%d 48s=%d region=%d / %d (선택 기준 아님)"
          % (grid["on_24s_grid_count"], grid["on_48s_grid_count"],
             grid["equals_region_boundary_count"],
             grid["internal_boundary_count"]))
    for row in boundaries["boundaries"]:
        print("  %6.1f  %s" % (row["boundary_sec"], ", ".join(row["reason"])))
    if args.dry_run:
        print("dry-run — 파일을 쓰지 않았다")
        return 0
    for name in write_artifacts(runs, built):
        print("wrote %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
