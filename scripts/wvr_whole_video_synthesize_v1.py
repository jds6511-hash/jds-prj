"""WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1 — whole-video Overview synthesis 1회.

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1_2026-09-13.md`

**merge gate가 PASS한 뒤에만 돈다.** gate 파일이 PASS가 아니면 시작하지 않는다.

visual inference를 하지 않는다 — `runtime.synthesize(prompt)` 는 텍스트 전용
호출이고 영상 프레임을 넘기지 않는다. 프롬프트·압축·파싱은 V2 모듈 그대로다.
retry 금지: 실행 1회.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_video_overview_preview_run as v1run  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402
import wvr_whole_video_merge_v1 as wm  # noqa: E402

RUN_ROOT = ROOT / "runs" / "wvr_whole_video_merge_v1"
PROMPT_NAME = "whole_video_synthesis_prompt.txt"
RAW_NAME = "whole_video_overview_raw.txt"
RESULT_NAME = "whole_video_overview_result.json"
RECORD_NAME = "whole_video_synthesis_record.json"


class SynthesisError(RuntimeError):
    pass


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
        raise SynthesisError("RUNTIME_MISMATCH: frozen Qwen3-VL runtime unavailable")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="모델을 올리지 않고 gate·프롬프트만 확인한다")
    args = parser.parse_args(argv)

    gate_path = RUN_ROOT / "merge_gate.json"
    if not gate_path.is_file():
        raise SynthesisError("merge gate 산출물이 없다 — 먼저 build를 돌려라")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("gate") != "PASS":
        raise SynthesisError("merge gate가 PASS가 아니다: %r" % gate.get("gate"))

    prompt_path = RUN_ROOT / PROMPT_NAME
    if not prompt_path.is_file():
        raise SynthesisError("synthesis 프롬프트가 없다")
    prompt = prompt_path.read_text(encoding="utf-8")

    # 프롬프트가 지금 timeline에서 다시 만들어도 같은지 확인한다 — 동결 확인이다.
    timeline = wm.build_timeline(ROOT)
    rebuilt, compressed = wm.synthesis_prompt(timeline)
    if rebuilt != prompt:
        raise SynthesisError("프롬프트가 timeline에서 재현되지 않는다")

    if (RUN_ROOT / RAW_NAME).exists():
        raise SynthesisError("이미 synthesis 산출물이 있다 — retry 금지(§5)")

    print("gate      ", gate["gate"])
    print("entry     ", timeline["entry_count"])
    print("runs      ", len(compressed["activity_runs"]))
    print("prompt    ", len(prompt), "chars")
    if args.dry_run:
        print("DRY_RUN_OK — 추론하지 않았다")
        return 0

    record = {
        "event": wm.EVENT, "prereg": wm.PREREG,
        "code_git_head": git_head(),
        "model_id": ov.MODEL_ID, "model_revision": ov.MODEL_REVISION,
        "call": "runtime.synthesize (텍스트 전용 · 영상 프레임 없음)",
        "do_sample": ov.DO_SAMPLE, "num_beams": ov.NUM_BEAMS,
        "max_new_tokens": ov.MAX_NEW_TOKENS,
        "visual_inference_count": 0, "stt_inference_count": 0,
        "synthesis_inference_count": 0, "retry_count": 0,
        "timeline_entry_count": timeline["entry_count"],
        "activity_run_count": len(compressed["activity_runs"]),
        "prompt_sha256": wm.sha256_file(prompt_path),
        "status": "RUNNING",
    }
    write_json(RUN_ROOT / RECORD_NAME, record)

    started = time.time()
    runtime = None
    try:
        runtime = v1run.QwenRuntime()
        record["runtime_provenance"] = runtime.provenance()
        _validate_runtime(record["runtime_provenance"])

        raw = runtime.synthesize(prompt)
        record["synthesis_inference_count"] = 1
        write_text(RUN_ROOT / RAW_NAME, raw)          # 파싱 전에 원문을 남긴다
        record["raw_sha256"] = wm.sha256_file(RUN_ROOT / RAW_NAME)
        write_json(RUN_ROOT / RECORD_NAME, record)

        overview = ov.parse_overview(raw)
        result = {
            "event": wm.EVENT,
            "status": "GENERATED / REVIEW_REQUESTED",
            "overview": overview,
            "compressed_timeline": compressed,
            "timeline_entry_count": timeline["entry_count"],
            "temporal_coverage_sec": timeline["temporal_coverage_sec"],
            "terminal_remainder_sec": timeline["terminal_remainder_sec"],
            "context_inference_injected": False,
        }
        record["status"] = result["status"]
        record["elapsed_sec"] = round(time.time() - started, 3)
        if hasattr(runtime, "metrics"):
            record["runtime_metrics"] = runtime.metrics()
        write_json(RUN_ROOT / RESULT_NAME, result)
        write_json(RUN_ROOT / RECORD_NAME, record)
        print("status    ", result["status"])
        print("elapsed   ", record["elapsed_sec"])
        return 0
    except Exception as error:                         # noqa: BLE001
        record["status"] = "FAILED / REVIEW_REQUESTED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["elapsed_sec"] = round(time.time() - started, 3)
        if runtime is not None and hasattr(runtime, "metrics"):
            record["runtime_metrics"] = runtime.metrics()
        write_json(RUN_ROOT / RECORD_NAME, record)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
