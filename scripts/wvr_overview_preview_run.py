"""Run WVR_OVERVIEW_PREVIEW_V1 exactly once and save raw before parsing."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_bcand_run as pinned_runtime  # noqa: E402
import wvr_overview_preview_v1 as ov  # noqa: E402


class RunError(RuntimeError):
    pass


def _write_text(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def runtime_spec() -> dict:
    return {"model_id": ov.LLM_MODEL_ID, "revision": ov.LLM_MODEL_REVISION,
            "dtype": ov.LLM_DTYPE,
            "attn_implementation": ov.LLM_ATTN_IMPLEMENTATION,
            "load_4bit": ov.LLM_LOAD_4BIT,
            "do_sample": ov.LLM_DO_SAMPLE,
            "max_new_tokens": ov.LLM_MAX_NEW_TOKENS}


def default_generator_factory(runtime: dict):
    return pinned_runtime.default_generator_factory(runtime)


def _validate_runtime(generator, requested: dict) -> tuple[dict, dict]:
    effective = getattr(generator, "provenance", None)
    metrics_fn = getattr(generator, "runtime_metrics", None)
    metrics = metrics_fn() if callable(metrics_fn) else None
    exact = (
        isinstance(effective, dict)
        and effective.get("effective_model_id") == requested["model_id"]
        and effective.get("effective_model_revision") == requested["revision"]
        and str(effective.get("effective_dtype", "")).lower().endswith("bfloat16")
        and str(effective.get("attn_implementation", "")).lower() == "sdpa"
        and effective.get("effective_quantized") is False
        and isinstance(metrics, dict) and metrics.get("cuda_available") is True
        and any("4090" in str(name) for name in metrics.get("device_names", []))
    )
    if not exact:
        raise RunError("RUNTIME_MISMATCH: frozen Qwen runtime or RTX 4090 unavailable")
    return effective, metrics


def run(runs: Path, generator_factory=default_generator_factory) -> dict:
    runs = Path(runs)
    for name in (ov.RAW_NAME, ov.RECORD_NAME, ov.RESULT_NAME, ov.PACKET_NAME):
        if (runs / name).exists():
            raise RunError("preview artifact already exists: %s" % name)
    source_path = runs / ov.SOURCE_MAP_NAME
    if ov.sha256_file(source_path) != ov.SOURCE_MAP_SHA256:
        raise RunError("SOURCE_MAP_HASH_MISMATCH")
    document = json.loads(source_path.read_text(encoding="utf-8"))
    generation_input = ov.build_generation_input(document)
    prompt = ov.render_prompt(generation_input)
    _write_text(runs / ov.PROMPT_NAME, prompt)

    requested = runtime_spec()
    generator = generator_factory(requested)
    effective, metrics = _validate_runtime(generator, requested)
    started = time.time()
    raw = generator(prompt)
    if not isinstance(raw, str) or not raw.strip():
        raise RunError("RUNTIME_FAILURE: empty raw output")
    _write_text(runs / ov.RAW_NAME, raw)
    if not (runs / ov.RAW_NAME).is_file():
        raise RunError("RAW_NOT_PERSISTED")
    metrics = generator.runtime_metrics()
    record = {
        "schema": "wvr_overview_preview_v1_record", "event": ov.EVENT,
        "source_map_sha256": ov.sha256_file(source_path),
        "prompt_template_sha256": ov.PROMPT_TEMPLATE_SHA256,
        "prompt_sha256": ov.sha256_file(runs / ov.PROMPT_NAME),
        "raw_sha256": ov.sha256_file(runs / ov.RAW_NAME),
        "requested_runtime": requested, "effective_runtime": effective,
        "runtime_metrics": metrics, "inference_count": 1,
        "generation_attempts": 1, "retry_count": 0,
        "raw_persisted_before_parse": True, "parsed_here": False,
        "new_vlm_inference_count": 0, "track_a_input_used": False,
        "unresolved_r01_synthesized": False,
        "conflicts_supplied_as_opaque_sets": True,
        "elapsed_sec": round(time.time() - started, 3),
    }
    _write_text(runs / ov.RECORD_NAME, ov.canonical(record) + "\n")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)
    record = run(Path(args.runs))
    print("inference_count=%d raw_saved=true parsed_here=false elapsed=%.3f" %
          (record["inference_count"], record["elapsed_sec"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
