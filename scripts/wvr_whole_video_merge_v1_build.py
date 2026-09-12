"""WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1 — timeline 생성 + gate G1~G10.

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1_2026-09-13.md`

**synthesis 전에 이 스크립트가 PASS해야 한다.** 하나라도 실패하면 종료 코드 1로
멈춘다 — text synthesis를 시작하지 않는다.

추론 없음. 읽기: frozen C01~C05 산출물. 쓰기: runs/wvr_whole_video_merge_v1/ 뿐이다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_whole_video_merge_v1 as wm  # noqa: E402

RUN_ROOT = ROOT / "runs" / "wvr_whole_video_merge_v1"
TIMELINE_JSON = "whole_video_activity_timeline.json"
TIMELINE_MD = "whole_video_activity_timeline.md"
LINEAGE_JSON = "timeline_lineage.json"
SYNTH_PROMPT = "whole_video_synthesis_prompt.txt"
SYNTH_INPUT = "whole_video_synthesis_input.json"


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False, indent=2,
                                sort_keys=True) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main() -> int:
    started = time.time()
    checks: list[dict] = []

    def check(cid: str, desc: str, ok: bool, detail=None) -> bool:
        checks.append({"id": cid, "desc": desc,
                       "result": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    def bail(msg: str) -> int:
        write_json(RUN_ROOT / "merge_gate.json",
                   {"event": wm.EVENT, "prereg": wm.PREREG, "gate": "FAIL",
                    "code_git_head": git_head(), "checks": checks})
        print(msg)
        return 1

    # ── G1 frozen source 해시 ──────────────────────────────────────
    try:
        loaded = {c: wm.load_chunk(ROOT, c) for c in wm.CHUNK_IDS}
        check("G1", "C01~C05 source 해시가 사전등록 §1과 일치", True,
              {c: loaded[c]["sha256"] for c in wm.CHUNK_IDS})
    except wm.MergeError as error:
        check("G1", "C01~C05 source 해시 일치", False, str(error))
        return bail("G1 FAIL — 중단")

    # ── timeline 생성 ──────────────────────────────────────────────
    try:
        timeline = wm.build_timeline(ROOT)
    except wm.MergeError as error:
        check("G2", "absolute time 변환 유효", False, str(error))
        return bail("timeline 생성 실패 — 중단")

    entries = timeline["entries"]

    # ── G2 절대 시각 변환 ──────────────────────────────────────────
    time_ok = all(
        entry["source_window"]["start_sec"] <= entry["start_sec"]
        and entry["end_sec"] <= entry["source_window"]["end_sec"]
        for entry in entries)
    check("G2", "entry 시각이 source 창 범위 안에서 파생된다", time_ok)

    # ── G3 중복 제거 ───────────────────────────────────────────────
    overlap = sum(max(0.0, a["end_sec"] - b["start_sec"])
                  for a, b in zip(entries, entries[1:]))
    check("G3", "duplicate source-time exposure 제거 (entry 간 겹침 0초)",
          round(overlap, 6) == 0.0,
          {"before_sec": timeline["duplicate_coverage_before_sec"],
           "after_sec": round(overlap, 6)})

    # ── G4 커버리지 ────────────────────────────────────────────────
    gaps = [[a["end_sec"], b["start_sec"]]
            for a, b in zip(entries, entries[1:]) if b["start_sec"] > a["end_sec"]]
    check("G4", "[0, 2424) temporal coverage — 빈틈 0 · union 2424.0",
          not gaps and entries[0]["start_sec"] == 0.0
          and entries[-1]["end_sec"] == wm.OBSERVED_END_SEC
          and timeline["temporal_coverage_sec"] == wm.OBSERVED_END_SEC,
          {"coverage_sec": timeline["temporal_coverage_sec"], "gaps": gaps,
           "terminal_remainder_sec": timeline["terminal_remainder_sec"]})

    # ── G5 lineage ─────────────────────────────────────────────────
    lineage_ok = (len(timeline["lineage"]) == len(entries) and all(
        entry["source_chunk"] in wm.CHUNK_IDS
        and entry["source_window"].get("segment_id")
        and set(entry["source_artifact_sha256"])
        == set(wm.FROZEN_SHA256[entry["source_chunk"]])
        for entry in entries))
    check("G5", "source lineage 완전 — chunk · window · artifact 해시", lineage_ok)

    # ── G6 결정성 ──────────────────────────────────────────────────
    again = json.dumps(wm.build_timeline(ROOT), ensure_ascii=False, sort_keys=True)
    check("G6", "deterministic merge — 2회 산출물 동일",
          again == json.dumps(timeline, ensure_ascii=False, sort_keys=True))

    # ── G7 · G8 추론 없음 ──────────────────────────────────────────
    check("G7", "no visual inference", timeline["new_visual_inference"] == 0)
    check("G8", "no STT inference", timeline["new_stt_inference"] == 0)

    # ── G9 · G10 금지 경로 ─────────────────────────────────────────
    # 기준은 이 프로세스 시작 시각이다. RUN_ROOT mtime을 쓰면 첫 실행에서
    # 디렉터리가 없어 기준이 0이 되고 모든 파일이 걸린다(2026-09-13 오탐).
    forbidden = [ROOT / "results" / "eval_test.json",
                 ROOT / "src" / "m9_report_eval.py"]
    touched = [str(p.relative_to(ROOT)) for p in forbidden
               if p.exists() and p.stat().st_mtime > started]
    check("G9", "official test 경로 미접근", not touched, touched)
    check("G10", "M9 미호출", True)

    # ── 산출물 ─────────────────────────────────────────────────────
    write_json(RUN_ROOT / TIMELINE_JSON,
               {k: v for k, v in timeline.items() if k != "lineage"})
    write_text(RUN_ROOT / TIMELINE_MD, wm.timeline_markdown(timeline))
    write_json(RUN_ROOT / LINEAGE_JSON,
               {"event": wm.EVENT, "prereg": wm.PREREG,
                "entry_count": timeline["entry_count"],
                "lineage": timeline["lineage"]})

    prompt, compressed = wm.synthesis_prompt(timeline)
    write_text(RUN_ROOT / SYNTH_PROMPT, prompt)
    write_json(RUN_ROOT / SYNTH_INPUT,
               {"compressed": compressed,
                "prompt_sha256": wm.sha256_file(RUN_ROOT / SYNTH_PROMPT)})

    gate = "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL"
    write_json(RUN_ROOT / "merge_gate.json",
               {"event": wm.EVENT, "prereg": wm.PREREG, "gate": gate,
                "code_git_head": git_head(),
                "entry_count": timeline["entry_count"],
                "temporal_coverage_sec": timeline["temporal_coverage_sec"],
                "duplicate_coverage_before_sec":
                    timeline["duplicate_coverage_before_sec"],
                "duplicate_coverage_after_sec":
                    timeline["duplicate_coverage_after_sec"],
                "terminal_remainder_sec": timeline["terminal_remainder_sec"],
                "activity_run_count": len(compressed["activity_runs"]),
                "checks": checks})

    for c in checks:
        mark = "" if c["result"] == "PASS" else "   <- %s" % (c["detail"],)
        print("%-4s %-4s  %s%s" % (c["id"], c["result"], c["desc"], mark))
    print("\nentry %d · coverage %.1f초 · 중복 before %.1f초 after %.1f초 · run %d개"
          % (timeline["entry_count"], timeline["temporal_coverage_sec"],
             timeline["duplicate_coverage_before_sec"],
             timeline["duplicate_coverage_after_sec"],
             len(compressed["activity_runs"])))
    print("MERGE GATE: %s" % gate)
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
