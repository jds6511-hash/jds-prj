"""WHOLE_VIDEO_REPORT_LIGHT_V1 capacity probe (2026-09-08).

사전등록: `docs/preregistration/WHOLE_VIDEO_REPORT_LIGHT_V1_2026-09-08.md`

```
판정 대상   MODEL_LOAD · VIDEO_PROCESS · 10MIN_INFERENCE
판정 제외   보고서·event·chapter 품질 · semantic correctness
승인 범위   C01 = 0.0–600.0초 1회. 다른 chunk·전체 파이프라인은 승인되지 않았다
```

OOM이면 `CAPACITY_FAIL`을 기록하고 **멈춘다**. 같은 사건에서 chunk를 줄이거나
fps·해상도·max_new_tokens를 낮춰 다시 돌리지 않는다 — 그러면 capacity 측정과
parameter tuning이 섞인다.

`device_map`을 쓰지 않는다. accelerate가 CPU·디스크로 offload하면 24GB를 넘는
구성이 조용히 통과한다.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wvr_contract as contract          # noqa: E402
from wvr_prompts import EVENT_PROMPT_V1, contract_hashes   # noqa: E402

APPROVED_CHUNK_ID = "C01"
FULL_PIPELINE_APPROVED = False

VERDICT_PASS = "PASS"
VERDICT_CAPACITY_FAIL = "CAPACITY_FAIL"
VERDICT_IMPLEMENTATION_DEFECT = "IMPLEMENTATION_DEFECT"

SEMANTIC_RESULT = "NOT_EVALUATED"

REQUIRED_METRICS = (
    "baseline_vram_mib", "post_load_vram_mib", "peak_vram_allocated_mib",
    "peak_vram_reserved_mib", "device_peak_used_mib",
    "requested_timestamps", "delivered_frame_count", "frame_size",
    "input_token_count", "video_token_count", "output_token_count",
    "effective_video_duration_sec", "load_wall_sec", "infer_wall_sec",
    "total_wall_sec", "oom", "offloaded_params",
)


class ProbeError(RuntimeError):
    """probe 계약 위반. 조용히 넘기지 않는다."""


def classify_error(error, oom_types) -> str:
    """OOM만 capacity 판정이다. 나머지는 구현 결함이고 파라미터를 바꾸지 않는다."""
    kinds = tuple(kind for kind in oom_types if isinstance(kind, type))
    if kinds and isinstance(error, kinds):
        return VERDICT_CAPACITY_FAIL
    return VERDICT_IMPLEMENTATION_DEFECT


def write_record(record: dict, out_path) -> None:
    """실패도 남긴다. 누락 지표는 None으로 명시한다."""
    metrics = record.setdefault("metrics", {})
    for name in REQUIRED_METRICS:
        metrics.setdefault(name, None)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                        encoding="utf-8")


def approved_chunk(duration_sec: float) -> dict:
    """승인된 chunk 하나만 돌려준다."""
    for chunk in contract.chunk_plan(duration_sec):
        if chunk["chunk_id"] == APPROVED_CHUNK_ID:
            return chunk
    raise ProbeError("%s가 chunk 계획에 없다" % APPROVED_CHUNK_ID)


def build_prompt(chunk: dict) -> str:
    """probe도 본 파이프라인과 같은 계약을 쓴다 — 토큰 부하가 같아야 의미가 있다."""
    return EVENT_PROMPT_V1 % {"chunk_start": chunk["start_sec"],
                              "chunk_end": chunk["end_sec"]}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True,
                              cwd=str(Path(__file__).resolve().parents[1])
                              ).stdout.strip()
    except Exception:
        return "UNKNOWN"


def sample_frames(video_path, timestamps):
    """사전등록된 시각에서 프레임을 뽑는다. 재인코딩하지 않는다."""
    import av
    from PIL import Image

    frames, indices, times = [], [], []
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        rate = float(stream.average_rate)
        time_base = float(stream.time_base)
        for target in timestamps:
            container.seek(int(target / time_base), stream=stream)
            picked = None
            for frame in container.decode(stream):
                if frame.time is not None and frame.time >= target - 1e-6:
                    picked = frame
                    break
            if picked is None:
                raise ProbeError("%.3f초 프레임을 디코드하지 못했다" % target)
            image = picked.to_image().resize(
                (contract.FRAME_WIDTH, contract.FRAME_HEIGHT), Image.BICUBIC)
            frames.append(image)
            indices.append(int(round(picked.time * rate)))
            times.append(round(picked.time, 4))
    return frames, indices, times, rate


def _device_used_mib() -> float:
    import torch
    free, total = torch.cuda.mem_get_info()
    return round((total - free) / 1024 ** 2, 1)


def probe(video_path, out_path, *, video_meta):
    """C01 1회 실행. 실패도 JSON으로 남긴다."""
    import torch
    import transformers
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from transformers.video_utils import VideoMetadata

    chunk = approved_chunk(video_meta["duration_sec"])
    timestamps = contract.chunk_frames(chunk)
    prompt = build_prompt(chunk)

    record = {
        "schema": "wvr_capacity_probe_v1",
        "prereg": "docs/preregistration/WHOLE_VIDEO_REPORT_LIGHT_V1_2026-09-08.md",
        "chunk": chunk,
        "semantic_result": SEMANTIC_RESULT,
        "full_pipeline_approved": FULL_PIPELINE_APPROVED,
        "requested": {
            "model_id": contract.MODEL_ID,
            "model_revision": contract.MODEL_REVISION,
            "dtype": contract.DTYPE, "quantization": contract.QUANTIZATION,
            "device": contract.DEVICE, "device_map": contract.DEVICE_MAP,
            "attn_implementation": contract.ATTN_IMPLEMENTATION,
            "chunk_fps": contract.CHUNK_FPS,
            "frame_size": [contract.FRAME_WIDTH, contract.FRAME_HEIGHT],
            "do_sample_frames": contract.DO_SAMPLE_FRAMES,
            "do_resize": contract.DO_RESIZE,
            "do_sample": contract.DO_SAMPLE, "num_beams": contract.NUM_BEAMS,
            "max_new_tokens": contract.MAX_NEW_TOKENS,
            "repetition_penalty": contract.REPETITION_PENALTY,
        },
        "video": video_meta,
        "prompt_contract": "EVENT_PROMPT_V1",
        "prompt_hashes": contract_hashes(),
        "code_git_head": _git_head(),
        "code_sha256": _sha256(Path(__file__).resolve()),
        "contract_sha256": _sha256(Path(contract.__file__)),
        "metrics": {}, "resolved": {}, "stage": {},
    }
    metrics, stage = record["metrics"], record["stage"]
    metrics["requested_timestamps"] = len(timestamps)
    metrics["effective_video_duration_sec"] = round(
        chunk["end_sec"] - chunk["start_sec"], 3)

    started = time.time()
    try:
        torch.cuda.reset_peak_memory_stats()
        metrics["baseline_vram_mib"] = _device_used_mib()

        load_started = time.time()
        processor = AutoProcessor.from_pretrained(
            contract.MODEL_ID, revision=contract.MODEL_REVISION,
            local_files_only=True)
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            contract.MODEL_ID, revision=contract.MODEL_REVISION,
            local_files_only=True, dtype=getattr(torch, contract.DTYPE),
            attn_implementation=contract.ATTN_IMPLEMENTATION)
        model.to(contract.DEVICE)
        model.eval()
        metrics["load_wall_sec"] = round(time.time() - load_started, 2)
        metrics["post_load_vram_mib"] = _device_used_mib()
        metrics["offloaded_params"] = sum(
            1 for param in model.parameters() if param.device.type != "cuda")
        stage["MODEL_LOAD"] = "PASS"

        record["resolved"] = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "dtype": str(next(model.parameters()).dtype),
            "attn_implementation": str(
                getattr(model.config, "_attn_implementation", "UNKNOWN")),
            "device": str(next(model.parameters()).device),
            "patch_size": getattr(processor.video_processor, "patch_size", None),
            "merge_size": getattr(processor.video_processor, "merge_size", None),
            "temporal_patch_size": getattr(processor.video_processor,
                                           "temporal_patch_size", None),
            "hf_home": os.environ.get("HF_HOME", ""),
        }

        frames, indices, times, rate = sample_frames(video_path, timestamps)
        metrics["delivered_frame_count"] = len(frames)
        metrics["frame_size"] = list(frames[0].size)
        metrics["frame_times_first_last"] = [times[0], times[-1]]
        record["frame_indices_first_last"] = [indices[0], indices[-1]]

        messages = [{"role": "user", "content": [{"type": "video"},
                                                 {"type": "text",
                                                  "text": prompt}]}]
        text = processor.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True)
        metadata = VideoMetadata(
            total_num_frames=video_meta["nb_frames"], fps=rate,
            width=video_meta["width"], height=video_meta["height"],
            duration=video_meta["duration_sec"], video_backend="pyav",
            frames_indices=indices)
        inputs = processor(text=[text], videos=[frames],
                           video_metadata=[metadata],
                           do_sample_frames=contract.DO_SAMPLE_FRAMES,
                           do_resize=contract.DO_RESIZE, return_tensors="pt")
        inputs = inputs.to(contract.DEVICE)
        metrics["input_token_count"] = int(inputs["input_ids"].shape[-1])
        video_token_id = getattr(model.config, "video_token_id", None)
        if video_token_id is not None:
            metrics["video_token_count"] = int(
                (inputs["input_ids"] == video_token_id).sum().item())
        else:
            metrics["video_token_count"] = None
        stage["VIDEO_PROCESS"] = "PASS"

        infer_started = time.time()
        with torch.inference_mode():
            generated = model.generate(
                **inputs, do_sample=contract.DO_SAMPLE,
                num_beams=contract.NUM_BEAMS,
                max_new_tokens=contract.MAX_NEW_TOKENS,
                repetition_penalty=contract.REPETITION_PENALTY)
        metrics["infer_wall_sec"] = round(time.time() - infer_started, 2)
        new_tokens = generated[0][inputs["input_ids"].shape[-1]:]
        metrics["output_token_count"] = int(new_tokens.shape[-1])
        record["raw_output"] = processor.tokenizer.decode(
            new_tokens, skip_special_tokens=True)
        stage["10MIN_INFERENCE"] = "PASS"
        metrics["oom"] = False
        record["verdict"] = VERDICT_PASS

    except Exception as error:                      # noqa: BLE001 — 전부 기록한다
        record["verdict"] = classify_error(error, (
            getattr(torch, "OutOfMemoryError", None),
            getattr(torch.cuda, "OutOfMemoryError", None)))
        metrics["oom"] = record["verdict"] == VERDICT_CAPACITY_FAIL
        record["error"] = {"type": type(error).__name__,
                           "message": str(error)[:2000]}
        for name in ("MODEL_LOAD", "VIDEO_PROCESS", "10MIN_INFERENCE"):
            if name not in stage:                    # 처음 도달 못한 단계에 사유를 적는다
                stage[name] = record["verdict"]
                break
        for name in ("MODEL_LOAD", "VIDEO_PROCESS", "10MIN_INFERENCE"):
            stage.setdefault(name, "NOT_REACHED")
    finally:
        try:
            import torch as _torch
            metrics["peak_vram_allocated_mib"] = round(
                _torch.cuda.max_memory_allocated() / 1024 ** 2, 1)
            metrics["peak_vram_reserved_mib"] = round(
                _torch.cuda.max_memory_reserved() / 1024 ** 2, 1)
            metrics["device_peak_used_mib"] = _device_used_mib()
        except Exception:
            pass
        metrics["total_wall_sec"] = round(time.time() - started, 2)
        write_record(record, out_path)
    return record


def video_metadata(video_path) -> dict:
    """ffprobe 없이 컨테이너에서 읽는다."""
    import av
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        return {"path": str(video_path), "sha256": _sha256(Path(video_path)),
                "width": stream.codec_context.width,
                "height": stream.codec_context.height,
                "nb_frames": int(stream.frames),
                "avg_rate": float(stream.average_rate),
                "duration_sec": round(float(container.duration) / 1e6, 6)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="WVR capacity probe (C01만)")
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    video_path = Path(args.video)
    if not video_path.is_file():
        raise ProbeError("영상이 없다: %s" % video_path)
    meta = video_metadata(video_path)
    record = probe(video_path, Path(args.out), video_meta=meta)
    print("verdict=%s stage=%s" % (record["verdict"], record["stage"]))
    return 0 if record["verdict"] == VERDICT_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
