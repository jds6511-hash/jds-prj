"""SEMANTIC_CHAPTER_SHADOW_V1 생성기 (서버 GPU · 생성 1회 · 재생성 금지).

사전등록: `docs/preregistration/WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md`

```
입력   conservative_event_map_v1.json (해시 동결) 하나뿐
생성   Qwen/Qwen2.5-7B-Instruct · bf16 · 4bit=false · greedy · max_new_tokens=4096
보존   파싱 전에 raw를 파일로 남긴다 (raw-before-parse)
거부   raw가 이미 있으면 실행하지 않는다 (retry 금지) · 해시 불일치면 실행하지 않는다
```

사용(서버):
```
HF_HOME=/ssd/$USER/cache python3 scripts/wvr_chapter_run.py --runs runs/wvr_light_v1
```
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import llm                                                   # noqa: E402
import wvr_chapter_selfcheck as selfcheck                    # noqa: E402
import wvr_chapter_v1 as ch                                  # noqa: E402

RAW_NAME = "chapter_v1_raw.txt"
RECORD_NAME = "chapter_v1_record.json"
PROMPT_NAME = "chapter_v1_prompt.txt"


class RunError(RuntimeError):
    """생성 계약 위반."""


def _git(*args) -> str:
    done = subprocess.run(["git"] + list(args), cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip()


def _vram() -> dict:
    try:
        import torch
        if not torch.cuda.is_available():
            return {"cuda": False}
        return {"cuda": True,
                "device": torch.cuda.get_device_name(0),
                "allocated_gb": round(torch.cuda.memory_allocated() / 2 ** 30,
                                      3),
                "max_allocated_gb": round(
                    torch.cuda.max_memory_allocated() / 2 ** 30, 3)}
    except Exception as error:                       # noqa: BLE001
        return {"cuda": "unknown", "error": str(error)}


def run(runs: Path) -> dict:
    if ch.RETRY_ALLOWED:
        raise RunError("재생성은 금지돼 있다")
    if (runs / RAW_NAME).is_file():
        raise RunError("raw가 이미 있다 — 재생성 금지: %s" % RAW_NAME)
    try:
        result = selfcheck.checks(runs)
    except selfcheck.SelfCheckError as error:
        raise RunError("self-check 실패: %s" % error)
    if not all(result["rows"].values()):
        failed = [name for name, value in result["rows"].items() if not value]
        raise RunError("self-check 항목 실패: %r" % failed)

    prompt = result["prompt"]
    _write_text(runs / PROMPT_NAME, prompt)

    generate = llm.make_llm(ch.LLM_MODEL_ID,
                            max_new_tokens=ch.LLM_MAX_NEW_TOKENS,
                            load_4bit=ch.LLM_LOAD_4BIT)
    started = time.time()
    raw = generate(prompt)
    elapsed = round(time.time() - started, 2)

    # raw-before-parse: 파싱하지 않고 먼저 남긴다
    _write_text(runs / RAW_NAME, raw or "")

    provenance = llm.llm_provenance(generate, role="chapter_generator",
                                    prompts={ch.CHAPTER_PROMPT_NAME: prompt})
    record = {
        "schema": "wvr_chapter_v1_record",
        "event": ch.EVENT, "prereg": ch.PREREG,
        "code_git_head": _git("rev-parse", "HEAD") or "unknown",
        "prereg_commit": _git("log", "-1", "--format=%H", "--",
                              ch.PREREG) or "unknown",
        "source_map": ch.SOURCE_MAP_NAME,
        "source_map_sha256": ch.SOURCE_MAP_SHA256,
        "prompt_name": ch.CHAPTER_PROMPT_NAME,
        "prompt_template_sha256": ch.PROMPT_TEMPLATE_SHA256,
        "prompt_sha256": ch.sha256_text(prompt),
        "prompt_chars": len(prompt),
        "requested_runtime": {
            "model_id": ch.LLM_MODEL_ID, "dtype": ch.LLM_DTYPE,
            "load_4bit": ch.LLM_LOAD_4BIT, "do_sample": ch.LLM_DO_SAMPLE,
            "max_new_tokens": ch.LLM_MAX_NEW_TOKENS,
            "attempts": ch.GENERATION_ATTEMPTS},
        "effective_runtime": provenance,
        "vram": _vram(),
        "elapsed_sec": elapsed,
        "raw_chars": len(raw or ""),
        "raw_sha256": ch.sha256_text(raw or ""),
        "raw_persisted_before_parse": True,
        "new_vlm_inference_count": 0,
        "track_a_input_used": ch.TRACK_A_INPUT_ALLOWED,
        "generation_attempts": ch.GENERATION_ATTEMPTS,
        "retry_allowed": ch.RETRY_ALLOWED,
        "parsed_here": False,
    }
    _write_text(runs / RECORD_NAME, json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True))
    return record


def _write_text(path, text: str) -> None:
    """산출물은 항상 LF로 쓴다 — 플랫폼별 CRLF 변환이 해시를 깨뜨린다."""
    with open(path, "w", encoding="utf-8", newline=chr(10)) as handle:
        handle.write(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="chapter 생성 (1회)")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    record = run(Path(args.runs))
    print("generated raw_chars=%d elapsed=%.1fs vram=%s"
          % (record["raw_chars"], record["elapsed_sec"],
             record["vram"].get("max_allocated_gb")))
    print("raw_sha256=%s" % record["raw_sha256"])
    print("effective model=%s revision=%s quantized=%s mismatch=%s"
          % (record["effective_runtime"].get("effective_model_id"),
             record["effective_runtime"].get("effective_model_revision"),
             record["effective_runtime"].get("effective_quantized"),
             record["effective_runtime"].get("quantization_mismatch")))
    print("파싱은 하지 않았다 — build 단계에서 한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
