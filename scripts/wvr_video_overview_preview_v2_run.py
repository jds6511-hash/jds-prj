"""Run WVR_VIDEO_TO_OVERVIEW_PREVIEW_V2 once with deterministic compression."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_video_overview_preview_run as v1run  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402


class RunError(RuntimeError):
    pass


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_json(path: Path, value) -> None:
    _write_text(path, ov.canonical(value) + "\n")


def _git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "UNKNOWN"


def _validate_runtime(provenance: dict) -> None:
    exact = (
        provenance.get("effective_model_id") == ov.MODEL_ID
        and provenance.get("effective_model_revision") == ov.MODEL_REVISION
        and str(provenance.get("effective_dtype", "")).lower().endswith("bfloat16")
        and str(provenance.get("attn_implementation", "")).lower() == "sdpa"
        and "4090" in str(provenance.get("device_name", ""))
    )
    if not exact:
        raise RunError("RUNTIME_MISMATCH: frozen Qwen3-VL runtime unavailable")


def run(video: Path, runs: Path, runtime_factory=v1run.QwenRuntime) -> dict:
    video, runs = Path(video), Path(runs)
    preexisting = list(runs.glob("video_overview_v2_*")) if runs.exists() else []
    if preexisting:
        raise RunError("preview artifact already exists: %s" % preexisting[0].name)
    if not video.is_file() or ov.sha256_file(video) != ov.VIDEO_SHA256:
        raise RunError("FROZEN_VIDEO_HASH_MISMATCH")
    runs.mkdir(parents=True, exist_ok=True)
    plan = ov.segments()
    _write_json(runs / ov.PLAN_NAME, plan)
    record = {
        "schema": "wvr_video_overview_preview_v2_record",
        "event": ov.EVENT, "code_git_head": _git_head(),
        "video_sha256": ov.sha256_file(video),
        "model_id": ov.MODEL_ID, "model_revision": ov.MODEL_REVISION,
        "segment_count": len(plan), "segment_inference_count": 0,
        "synthesis_inference_count": 0, "inference_count": 0,
        "retry_count": 0, "track_a_used": False, "event_map_used": False,
        "raw_persisted_before_parse": True, "context_used_for_synthesis": False,
        "status": "RUNNING", "segment_raw_sha256": {},
    }
    _write_json(runs / ov.RECORD_NAME, record)
    runtime = None
    started = time.time()
    try:
        runtime = runtime_factory()
        record["runtime_provenance"] = runtime.provenance()
        _validate_runtime(record["runtime_provenance"])
        summaries = []
        prompt = ov.segment_prompt()
        for segment in plan:
            segment_id = segment["segment_id"]
            prompt_path = runs / ("video_overview_v2_segment_%s_prompt.txt" % segment_id)
            raw_path = runs / ("video_overview_v2_segment_%s_raw.txt" % segment_id)
            _write_text(prompt_path, prompt)
            raw = runtime.observe(video, segment, prompt)
            record["inference_count"] += 1
            record["segment_inference_count"] += 1
            _write_text(raw_path, raw)
            record["segment_raw_sha256"][segment_id] = ov.sha256_file(raw_path)
            _write_json(runs / ov.RECORD_NAME, record)
            summaries.append(ov.parse_segment(raw, segment_id))
        _write_json(runs / ov.SUMMARIES_NAME, summaries)

        compressed = ov.compress_activity_timeline(summaries)
        _write_json(runs / ov.TIMELINE_NAME, compressed)
        synth_prompt = ov.synthesis_prompt(compressed)
        _write_text(runs / ov.SYNTHESIS_PROMPT_NAME, synth_prompt)
        overview_raw = runtime.synthesize(synth_prompt)
        record["inference_count"] += 1
        record["synthesis_inference_count"] += 1
        _write_text(runs / ov.OVERVIEW_RAW_NAME, overview_raw)
        record["overview_raw_sha256"] = ov.sha256_file(runs / ov.OVERVIEW_RAW_NAME)
        _write_json(runs / ov.RECORD_NAME, record)

        overview = ov.parse_overview(overview_raw)
        result = {
            "schema": "wvr_video_overview_preview_v2_result",
            "event": ov.EVENT, "status": "GENERATED / REVIEW_REQUESTED",
            "overview": overview, "compressed_timeline": compressed,
            "context_inferences_excluded": ov.excluded_contexts(summaries),
            "uncertainties": ov.uncertainties(summaries),
            "segment_summaries": summaries,
        }
        record["status"] = result["status"]
        record["runtime_metrics"] = runtime.metrics()
        record["elapsed_sec"] = round(time.time() - started, 3)
        _write_json(runs / ov.RESULT_NAME, result)
        _write_json(runs / ov.RECORD_NAME, record)
        _write_text(runs / ov.PACKET_NAME, ov.packet_markdown(result, record))
        return result
    except Exception as error:
        record["status"] = "FAILED / REVIEW_REQUESTED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["elapsed_sec"] = round(time.time() - started, 3)
        if runtime is not None:
            record["runtime_metrics"] = runtime.metrics()
        _write_json(runs / ov.RECORD_NAME, record)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--runs", default="runs/wvr_video_overview_preview_v2")
    args = parser.parse_args(argv)
    result = run(Path(args.video), Path(args.runs))
    print("status=%s segments=%d inference_count=25 retry_count=0" %
          (result["status"], len(result["segment_summaries"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
