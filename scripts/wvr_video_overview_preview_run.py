"""Run the one-shot direct video-to-Overview Preview on Qwen3-VL."""
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

import wvr_capacity_probe as probe  # noqa: E402
import wvr_video_overview_preview_v1 as ov  # noqa: E402


class RunError(RuntimeError):
    pass


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_json(path: Path, value: dict | list) -> None:
    _write_text(path, ov.canonical(value) + "\n")


def _git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "UNKNOWN"


class QwenRuntime:
    def __init__(self):
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(
            ov.MODEL_ID, revision=ov.MODEL_REVISION, local_files_only=True)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            ov.MODEL_ID, revision=ov.MODEL_REVISION, local_files_only=True,
            dtype=getattr(torch, ov.DTYPE),
            attn_implementation=ov.ATTN_IMPLEMENTATION)
        self.model.to(ov.DEVICE)
        self.model.eval()
        torch.cuda.reset_peak_memory_stats()
        self._segment_metrics = []
        self._video_meta = None

    def _decode(self, inputs) -> tuple[str, int]:
        started = time.time()
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs, do_sample=ov.DO_SAMPLE, num_beams=ov.NUM_BEAMS,
                max_new_tokens=ov.MAX_NEW_TOKENS,
                repetition_penalty=1.0)
        new_tokens = generated[0][inputs["input_ids"].shape[-1]:]
        raw = self.processor.tokenizer.decode(new_tokens,
                                              skip_special_tokens=True)
        count = int(new_tokens.shape[-1])
        elapsed = round(time.time() - started, 3)
        del generated, new_tokens
        return raw, count, elapsed

    def observe(self, video: Path, segment: dict, prompt: str) -> str:
        from transformers.video_utils import VideoMetadata

        if self._video_meta is None:
            self._video_meta = probe.video_metadata(video)
        started = time.time()
        frames, indices, decoded_times, rate = probe.sample_frames(
            video, segment["frame_times"])
        messages = [{"role": "user", "content": [
            {"type": "video"}, {"type": "text", "text": prompt}]}]
        rendered = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        meta = self._video_meta
        metadata = VideoMetadata(
            total_num_frames=meta["nb_frames"], fps=rate,
            width=meta["width"], height=meta["height"],
            duration=meta["duration_sec"], video_backend="pyav",
            frames_indices=indices)
        inputs = self.processor(
            text=[rendered], videos=[frames], video_metadata=[metadata],
            do_sample_frames=False, do_resize=False, return_tensors="pt")
        inputs = inputs.to(ov.DEVICE)
        input_tokens = int(inputs["input_ids"].shape[-1])
        raw, output_tokens, infer_sec = self._decode(inputs)
        self._segment_metrics.append({
            "segment_id": segment["segment_id"],
            "frame_count": len(frames), "input_tokens": input_tokens,
            "output_tokens": output_tokens, "infer_wall_sec": infer_sec,
            "total_wall_sec": round(time.time() - started, 3),
            "decoded_times": decoded_times,
        })
        del inputs, frames
        self.torch.cuda.empty_cache()
        return raw

    def synthesize(self, prompt: str) -> str:
        messages = [{"role": "user", "content": [
            {"type": "text", "text": prompt}]}]
        rendered = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(text=[rendered], return_tensors="pt")
        inputs = inputs.to(ov.DEVICE)
        raw, output_tokens, infer_sec = self._decode(inputs)
        self._synthesis_metrics = {
            "input_tokens": int(inputs["input_ids"].shape[-1]),
            "output_tokens": output_tokens, "infer_wall_sec": infer_sec}
        del inputs
        self.torch.cuda.empty_cache()
        return raw

    def provenance(self) -> dict:
        config = self.model.config
        return {
            "effective_model_id": ov.MODEL_ID,
            "effective_model_revision": getattr(config, "_commit_hash", None),
            "effective_dtype": str(getattr(self.model, "dtype", None)),
            "attn_implementation": getattr(config, "_attn_implementation", None),
            "device_name": self.torch.cuda.get_device_name(0),
        }

    def metrics(self) -> dict:
        return {
            "peak_vram_allocated_mib": round(
                self.torch.cuda.max_memory_allocated() / 1024 ** 2, 1),
            "peak_vram_reserved_mib": round(
                self.torch.cuda.max_memory_reserved() / 1024 ** 2, 1),
            "segments": self._segment_metrics,
            "synthesis": getattr(self, "_synthesis_metrics", None),
        }


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


def run(video: Path, runs: Path, runtime_factory=QwenRuntime) -> dict:
    video, runs = Path(video), Path(runs)
    preexisting = list(runs.glob("video_overview_v1_*")) if runs.exists() else []
    if preexisting:
        raise RunError("preview artifact already exists: %s" % preexisting[0].name)
    if not video.is_file() or ov.sha256_file(video) != ov.VIDEO_SHA256:
        raise RunError("FROZEN_VIDEO_HASH_MISMATCH")
    runs.mkdir(parents=True, exist_ok=True)
    plan = ov.segments()
    _write_json(runs / ov.PLAN_NAME, plan)
    record = {
        "schema": "wvr_video_overview_preview_v1_record",
        "event": ov.EVENT, "code_git_head": _git_head(),
        "video_sha256": ov.sha256_file(video),
        "model_id": ov.MODEL_ID, "model_revision": ov.MODEL_REVISION,
        "segment_count": len(plan), "segment_inference_count": 0,
        "synthesis_inference_count": 0, "inference_count": 0,
        "retry_count": 0, "track_a_used": False,
        "event_map_used_for_synthesis": False,
        "raw_persisted_before_parse": True,
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
        for segment in plan:
            segment_id = segment["segment_id"]
            prompt_path = runs / ("video_overview_v1_segment_%s_prompt.txt" % segment_id)
            raw_path = runs / ("video_overview_v1_segment_%s_raw.txt" % segment_id)
            prompt = ov.segment_prompt(segment_id)
            _write_text(prompt_path, prompt)
            raw = runtime.observe(video, segment, prompt)
            record["inference_count"] += 1
            record["segment_inference_count"] += 1
            _write_text(raw_path, raw)
            record["segment_raw_sha256"][segment_id] = ov.sha256_file(raw_path)
            _write_json(runs / ov.RECORD_NAME, record)
            summaries.append(ov.parse_segment(raw, segment_id))
        _write_json(runs / ov.SUMMARIES_NAME, summaries)

        synth_prompt = ov.synthesis_prompt(summaries)
        _write_text(runs / ov.SYNTHESIS_PROMPT_NAME, synth_prompt)
        overview_raw = runtime.synthesize(synth_prompt)
        record["inference_count"] += 1
        record["synthesis_inference_count"] += 1
        _write_text(runs / ov.OVERVIEW_RAW_NAME, overview_raw)
        record["overview_raw_sha256"] = ov.sha256_file(
            runs / ov.OVERVIEW_RAW_NAME)
        _write_json(runs / ov.RECORD_NAME, record)
        overview = ov.parse_overview(overview_raw)
        result = {
            "schema": "wvr_video_overview_preview_v1_result",
            "event": ov.EVENT, "status": "GENERATED / REVIEW_REQUESTED",
            "overview": overview, "segment_summaries": summaries,
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
    parser.add_argument("--runs", default="runs/wvr_video_overview_preview_v1")
    args = parser.parse_args(argv)
    result = run(Path(args.video), Path(args.runs))
    print("status=%s segments=%d inference_count=25 retry_count=0" %
          (result["status"], len(result["segment_summaries"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
