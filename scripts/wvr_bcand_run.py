"""Execute the frozen boundary proposer once and persist raw output only."""
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

import wvr_bcand_selfcheck as selfcheck  # noqa: E402
import wvr_boundary_candidate_v1 as bc  # noqa: E402

RECORD_NAME = "bcand_v1_record.json"


class RunError(RuntimeError):
    pass


def _git(*args) -> str:
    done = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True)
    return done.stdout.strip()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def runtime_spec() -> dict:
    return {"model_id": bc.LLM_MODEL_ID, "revision": bc.LLM_MODEL_REVISION,
            "dtype": bc.LLM_DTYPE,
            "attn_implementation": bc.LLM_ATTN_IMPLEMENTATION,
            "load_4bit": bc.LLM_LOAD_4BIT, "do_sample": bc.LLM_DO_SAMPLE,
            "max_new_tokens": bc.LLM_MAX_NEW_TOKENS}


def _runtime_metrics(torch_module) -> dict:
    available = bool(torch_module.cuda.is_available())
    count = int(torch_module.cuda.device_count()) if available else 0
    return {
        "cuda_available": available,
        "device_count": count,
        "device_names": [torch_module.cuda.get_device_name(index)
                         for index in range(count)],
        "max_memory_allocated_bytes": int(
            torch_module.cuda.max_memory_allocated()) if available else 0,
        "max_memory_reserved_bytes": int(
            torch_module.cuda.max_memory_reserved()) if available else 0,
    }


def _validated_runtime(generator, requested: dict) -> tuple[dict, dict]:
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
        and isinstance(metrics, dict)
        and metrics.get("cuda_available") is True
        and isinstance(metrics.get("device_count"), int)
        and metrics["device_count"] >= 1
        and any("4090" in str(name) for name in metrics.get("device_names", []))
    )
    if not exact:
        raise RunError("RUNTIME_MISMATCH: frozen model/runtime or 4090 unavailable")
    return effective, metrics


def default_generator_factory(runtime: dict):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        runtime["model_id"], revision=runtime["revision"])
    model = AutoModelForCausalLM.from_pretrained(
        runtime["model_id"], revision=runtime["revision"],
        torch_dtype=torch.bfloat16, device_map="auto",
        attn_implementation=runtime["attn_implementation"])

    def generate(prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([rendered], return_tensors="pt").to(model.device)
        with torch.inference_mode():
            output = model.generate(**inputs,
                                    max_new_tokens=runtime["max_new_tokens"],
                                    do_sample=runtime["do_sample"])
        return tokenizer.decode(
            output[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True).strip()

    config = model.config
    generate.provenance = {
        "effective_model_id": runtime["model_id"],
        "effective_model_revision": getattr(config, "_commit_hash", None),
        "effective_dtype": str(getattr(model, "dtype", None)),
        "attn_implementation": getattr(config, "_attn_implementation", None),
        "effective_quantized": getattr(config, "quantization_config", None) is not None,
    }
    generate.runtime_metrics = lambda: _runtime_metrics(torch)
    return generate


def run(runs: Path, generator_factory=default_generator_factory) -> dict:
    if bc.RETRY_ALLOWED:
        raise RunError("CONFIG_MISMATCH: retry enabled")
    if (runs / RECORD_NAME).is_file():
        raise RunError("boundary proposer execution is already complete")
    submission = ROOT / "runs/quality_candidate/S7/report.hwpx"
    gate = selfcheck.checks(runs, submission)
    if gate["status"] != "PASS":
        raise RunError("pre-inference selfcheck failed")
    batches_doc = json.loads((runs / "bcand_v1_batches.json").read_text(
        encoding="utf-8"))
    preexisting = []
    missing = []
    for row in batches_doc["batches"]:
        raw_path = runs / ("bcand_v1_raw_%s.txt" % row["batch_id"])
        (preexisting if raw_path.is_file() else missing).append(row["batch_id"])
    requested_runtime = runtime_spec()
    generator = generator_factory(requested_runtime) if missing else None
    effective = metrics = None
    if generator is not None:
        effective, metrics = _validated_runtime(generator, requested_runtime)
    elif preexisting:
        raise RunError("RUNTIME_MISMATCH: no runtime provenance for complete raw set")
    started = time.time()
    for batch_id in missing:
        prompt_path = runs / ("bcand_v1_prompt_%s.txt" % batch_id)
        raw_path = runs / ("bcand_v1_raw_%s.txt" % batch_id)
        raw = generator(prompt_path.read_text(encoding="utf-8"))
        if not isinstance(raw, str) or not raw.strip():
            raise RunError("RUNTIME_FAILURE: empty raw for %s" % batch_id)
        _write_text(raw_path, raw)
    raw_hashes = {}
    for row in batches_doc["batches"]:
        batch_id = row["batch_id"]
        path = runs / ("bcand_v1_raw_%s.txt" % batch_id)
        if not path.is_file():
            raise RunError("RAW_NOT_PERSISTED: %s" % batch_id)
        raw_hashes[batch_id] = _sha256_file(path)
    if generator is not None:
        metrics = generator.runtime_metrics()
    record = {
        "schema": "wvr_bcand_v1_record", "event": bc.EVENT,
        "prereg": bc.PREREG, "prereg_commit": _git("log", "-1", "--format=%H",
                                                     "--", bc.PREREG),
        "code_git_head": _git("rev-parse", "HEAD"),
        "previous_executor_agent": "Claude in VS Code",
        "current_executor_agent": "Codex in VS Code",
        "current_executor_model": "not exposed by runtime",
        "first_execution": True, "requested_runtime": requested_runtime,
        "effective_runtime": effective,
        "runtime_metrics": metrics,
        "prompt_template_sha256": bc.PROMPT_TEMPLATE_SHA256,
        "prompt_sha256": {row["batch_id"]: row["prompt_sha256"]
                          for row in batches_doc["batches"]},
        "raw_sha256": raw_hashes,
        "raw_persisted_before_parse": True, "parsed_here": False,
        "generation_attempts_per_batch": 1, "retry_allowed": False,
        "preexisting_raw_batches": preexisting,
        "resumed_batches": missing if preexisting else [],
        "generated_batches_this_process": missing,
        "elapsed_sec": round(time.time() - started, 3),
        "new_vlm_inference_count": 0, "track_a_input_used": False,
        "chapter_generated": False, "overview_generated": False,
        "mapping_revealed": False,
    }
    _write_text(runs / RECORD_NAME, bc.canonical(record) + "\n")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)
    record = run(Path(args.runs))
    print("raw_batches=%d preexisting=%d elapsed=%.3f" %
          (len(record["raw_sha256"]), len(record["preexisting_raw_batches"]),
           record["elapsed_sec"]))
    print("raw persisted; parsing not performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
