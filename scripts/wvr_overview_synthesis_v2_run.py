"""WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2 — CANONICAL_FLOW + 계층적 synthesis.

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2_2026-09-13.md`

```
frozen timeline → CANONICAL_FLOW (추론 0) → DETAILED (1회) → SHORT (1회)
```

timeline을 수정·재생성하지 않는다. visual inference · STT 없음. retry 금지.

    python scripts/wvr_overview_synthesis_v2_run.py --flow-only   # 모델 미적재
    python scripts/wvr_overview_synthesis_v2_run.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_overview_synthesis_v2 as sv  # noqa: E402
import wvr_video_overview_preview_run as v1run  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402

MERGE_ROOT = ROOT / "runs" / "wvr_whole_video_merge_v1"
RUN_ROOT = ROOT / "runs" / "wvr_overview_synthesis_v2"
TIMELINE = MERGE_ROOT / "whole_video_activity_timeline.json"
LINEAGE = MERGE_ROOT / "timeline_lineage.json"
MERGE_GATE = MERGE_ROOT / "merge_gate.json"


class RunError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json(path: Path, obj) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2,
                                sort_keys=True) + "\n")


def _validate_runtime(provenance: dict) -> None:
    exact = (
        provenance.get("effective_model_id") == ov.MODEL_ID
        and provenance.get("effective_model_revision") == ov.MODEL_REVISION
        and str(provenance.get("effective_dtype", "")).lower().endswith("bfloat16")
        and str(provenance.get("attn_implementation", "")).lower() == "sdpa"
        and "4090" in str(provenance.get("device_name", "")))
    if not exact:
        raise RunError("RUNTIME_MISMATCH: frozen Qwen3-VL runtime unavailable")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow-only", action="store_true",
                        help="CANONICAL_FLOW만 만들고 추론하지 않는다")
    args = parser.parse_args(argv)

    # ── frozen input 확인 ──────────────────────────────────────────
    for path in (TIMELINE, LINEAGE, MERGE_GATE):
        if not path.is_file():
            raise RunError("frozen input 없음: %s" % path)
    gate = json.loads(MERGE_GATE.read_text(encoding="utf-8"))
    if gate.get("gate") != "PASS":
        raise RunError("merge gate가 PASS가 아니다: %r" % gate.get("gate"))

    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    source_sha = {"whole_video_activity_timeline.json": sha(TIMELINE),
                  "timeline_lineage.json": sha(LINEAGE)}

    # ── CANONICAL_FLOW (추론 0) ───────────────────────────────────
    flow = sv.canonical_flow(timeline)
    flow["source_sha256"] = source_sha
    write_json(RUN_ROOT / "canonical_flow.json", flow)
    write_text(RUN_ROOT / "canonical_flow.md", sv.canonical_markdown(flow))

    d_prompt = sv.detailed_prompt(flow)
    write_text(RUN_ROOT / "detailed_prompt.txt", d_prompt)

    print("timeline entry ", timeline["entry_count"])
    print("phase          ", flow["phase_count"])
    print("final phase    ", flow["final_phase_activities"], flow["final_phase_span"])
    print("repeated       ", flow["repeated_activities"])
    if args.flow_only:
        print("FLOW_ONLY_OK — 추론하지 않았다")
        return 0

    if (RUN_ROOT / "detailed_raw.txt").exists():
        raise RunError("이미 synthesis 산출물이 있다 — retry 금지(§6)")

    record = {
        "event": sv.EVENT, "prereg": sv.PREREG,
        "code_git_head": git_head(),
        "model_id": ov.MODEL_ID, "model_revision": ov.MODEL_REVISION,
        "call": "runtime.synthesize (텍스트 전용 · 영상 프레임 없음)",
        "do_sample": ov.DO_SAMPLE, "num_beams": ov.NUM_BEAMS,
        "max_new_tokens": ov.MAX_NEW_TOKENS,
        "source_sha256": source_sha,
        "canonical_flow_inference_count": 0,
        "visual_inference_count": 0, "stt_inference_count": 0,
        "timeline_regeneration_count": 0,
        "synthesis_inference_count": 0, "retry_count": 0,
        "status": "RUNNING",
    }
    write_json(RUN_ROOT / "synthesis_record.json", record)

    started = time.time()
    runtime = None
    try:
        runtime = v1run.QwenRuntime()
        record["runtime_provenance"] = runtime.provenance()
        _validate_runtime(record["runtime_provenance"])

        # ── DETAILED (1회) ────────────────────────────────────────
        detailed_raw = runtime.synthesize(d_prompt)
        record["synthesis_inference_count"] = 1
        write_text(RUN_ROOT / "detailed_raw.txt", detailed_raw)
        write_json(RUN_ROOT / "synthesis_record.json", record)
        detailed = sv.clean_body(detailed_raw, what="DETAILED_OVERVIEW")

        # ── SHORT (1회) — DETAILED만 본다 ─────────────────────────
        s_prompt = sv.short_prompt(detailed)
        write_text(RUN_ROOT / "short_prompt.txt", s_prompt)
        short_raw = runtime.synthesize(s_prompt)
        record["synthesis_inference_count"] = 2
        write_text(RUN_ROOT / "short_raw.txt", short_raw)
        write_json(RUN_ROOT / "synthesis_record.json", record)
        short = sv.clean_body(short_raw, what="SHORT_OVERVIEW")

        checks = sv.machine_checks(flow, detailed, short)
        write_json(RUN_ROOT / "machine_checks.json",
                   {"event": sv.EVENT, "prereg": sv.PREREG, "checks": checks})

        result = {
            "event": sv.EVENT,
            "status": "GENERATED / REVIEW_REQUESTED",
            "canonical_flow": {
                "phase_count": flow["phase_count"],
                "first_phase_activities": flow["first_phase_activities"],
                "final_phase_activities": flow["final_phase_activities"],
                "final_phase_span": flow["final_phase_span"],
                "repeated_activities": flow["repeated_activities"],
                "non_repeated_activities": flow["non_repeated_activities"],
                "phase_sequence": [p["activities"] for p in flow["phases"]],
            },
            "detailed_overview": detailed,
            "short_overview": short,
            "machine_checks_all_pass": checks["all_pass"],
            "source_timeline_entry_count": timeline["entry_count"],
            "source_temporal_coverage_sec": timeline["temporal_coverage_sec"],
        }
        record["status"] = result["status"]
        record["machine_checks_all_pass"] = checks["all_pass"]
        record["elapsed_sec"] = round(time.time() - started, 3)
        if hasattr(runtime, "metrics"):
            record["runtime_metrics"] = runtime.metrics()
        write_json(RUN_ROOT / "overview_result.json", result)
        write_json(RUN_ROOT / "synthesis_record.json", record)

        print("\nstatus         ", result["status"])
        print("machine checks ", "ALL PASS" if checks["all_pass"] else "FAIL 있음")
        for key, value in checks.items():
            if isinstance(value, dict) and "pass" in value:
                print("  %-46s %s" % (key, "PASS" if value["pass"] else "FAIL"))
        print("elapsed        ", record["elapsed_sec"])
        return 0
    except Exception as error:                          # noqa: BLE001
        record["status"] = "FAILED / REVIEW_REQUESTED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["elapsed_sec"] = round(time.time() - started, 3)
        if runtime is not None and hasattr(runtime, "metrics"):
            record["runtime_metrics"] = runtime.metrics()
        write_json(RUN_ROOT / "synthesis_record.json", record)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
