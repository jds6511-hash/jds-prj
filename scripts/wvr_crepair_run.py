"""BOUNDARY_REPAIR_V1 Stage B — 제목·요약 생성 1회 (서버 GPU).

사전등록:
`docs/preregistration/WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md`

```
전제   Stage A가 동결한 chapter_repair_v1_boundaries.json이 있어야 한다
생성   Qwen/Qwen2.5-7B-Instruct · bf16 · 4bit=false · greedy · 4096 · 1회
보존   렌더 프롬프트 저장 → raw 저장 → record 저장 (raw-before-parse · 파싱 안 함)
거부   raw가 이미 있으면 실행하지 않는다 · 경계 파일이 없거나 재계산과 다르면 중단
```

사용(서버):
```
HF_HOME=/ssd/$USER/cache python3 scripts/wvr_crepair_run.py --runs runs/wvr_light_v1
```
"""
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

import llm                                                   # noqa: E402
import wvr_chapter_repair_v1 as cr                           # noqa: E402
import wvr_chapter_selfcheck as v1check                      # noqa: E402
import wvr_crepair_stagea as stagea                          # noqa: E402

RAW_NAME = "chapter_repair_v1_raw.txt"
RECORD_NAME = "chapter_repair_v1_record.json"
PROMPT_NAME = "chapter_repair_v1_prompt.txt"


class RunError(RuntimeError):
    """Stage B 계약 위반."""


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


def _vram() -> dict:
    try:
        import torch
        if not torch.cuda.is_available():
            return {"cuda": False}
        return {"cuda": True, "device": torch.cuda.get_device_name(0),
                "max_allocated_gb": round(
                    torch.cuda.max_memory_allocated() / 2 ** 30, 3)}
    except Exception as error:                       # noqa: BLE001
        return {"cuda": "unknown", "error": str(error)}


def frozen_boundaries(runs: Path):
    """동결된 경계를 읽고 map에서 재계산한 결과와 같은지 확인한다."""
    path = runs / stagea.BOUNDARIES_NAME
    if not path.is_file():
        raise RunError("BOUNDARY_SET_NOT_FROZEN: %s가 없다"
                       % stagea.BOUNDARIES_NAME)
    frozen = json.loads(path.read_text(encoding="utf-8"))
    try:
        document = v1check.load_map(runs)
        events = cr.source_events(document)
        rebuilt = cr.select_boundaries(cr.candidates(events, document))
        chapters = cr.chapters_from_boundaries(rebuilt)
    except (v1check.SelfCheckError, cr.RepairError) as error:
        raise RunError("%s" % error)
    if [row["boundary_sec"] for row in rebuilt] \
            != [row["boundary_sec"] for row in frozen["boundaries"]]:
        raise RunError("BOUNDARY_SET_NOT_FROZEN: 재계산 경계가 파일과 다르다")
    if chapters != frozen["chapters"]:
        raise RunError("BOUNDARY_SET_NOT_FROZEN: 재계산 chapter가 파일과 다르다")
    supports = [cr.chapter_support(chapter, document, events)
                for chapter in chapters]
    return document, events, chapters, supports, frozen


def run(runs: Path) -> dict:
    if cr.RETRY_ALLOWED:
        raise RunError("재생성은 금지돼 있다")
    if (runs / RAW_NAME).is_file():
        raise RunError("raw가 이미 있다 — 재생성 금지: %s" % RAW_NAME)
    try:
        cr.assert_flags_closed()
    except cr.RepairError as error:
        raise RunError("%s" % error)
    document, events, chapters, supports, frozen = frozen_boundaries(runs)

    prompt = cr.render_prompt(chapters, supports, document, events)
    if cr.sha256_text(cr.REPAIR_PROMPT_V1) != \
            "8a1a9c652dda1e7d24030652350fd29c77b0b0ec0945d6a43aa0e1fb7ae975ae":
        raise RunError("CONFIG_MISMATCH: 프롬프트 템플릿이 동결값과 다르다")
    _write_text(runs / PROMPT_NAME, prompt)

    generate = llm.make_llm(cr.LLM_MODEL_ID,
                            max_new_tokens=cr.LLM_MAX_NEW_TOKENS,
                            load_4bit=cr.LLM_LOAD_4BIT)
    started = time.time()
    raw = generate(prompt)
    elapsed = round(time.time() - started, 2)
    _write_text(runs / RAW_NAME, raw or "")      # raw-before-parse

    provenance = llm.llm_provenance(generate, role="chapter_repair_generator",
                                    prompts={cr.REPAIR_PROMPT_NAME: prompt})
    record = {
        "schema": "wvr_chapter_repair_v1_record", "event": cr.EVENT,
        "prereg": cr.PREREG,
        "code_git_head": _git("rev-parse", "HEAD") or "unknown",
        "prereg_commit": _git("log", "-1", "--format=%H", "--",
                              cr.PREREG) or "unknown",
        "source_map_sha256": cr.SOURCE_MAP_SHA256,
        "boundaries_sha256": sha256_file(runs / stagea.BOUNDARIES_NAME),
        "boundary_count": len(frozen["boundaries"]),
        "chapter_count": len(chapters),
        "prompt_name": cr.REPAIR_PROMPT_NAME,
        "prompt_template_sha256": cr.sha256_text(cr.REPAIR_PROMPT_V1),
        "prompt_sha256": cr.sha256_text(prompt),
        "prompt_chars": len(prompt),
        "requested_runtime": {
            "model_id": cr.LLM_MODEL_ID, "dtype": cr.LLM_DTYPE,
            "load_4bit": cr.LLM_LOAD_4BIT, "do_sample": cr.LLM_DO_SAMPLE,
            "max_new_tokens": cr.LLM_MAX_NEW_TOKENS,
            "attempts": cr.GENERATION_ATTEMPTS},
        "effective_runtime": provenance,
        "vram": _vram(), "elapsed_sec": elapsed,
        "raw_chars": len(raw or ""), "raw_sha256": cr.sha256_text(raw or ""),
        "raw_persisted_before_parse": True, "parsed_here": False,
        "new_vlm_inference_count": 0,
        "track_a_input_used": cr.TRACK_A_INPUT_ALLOWED,
        "generation_attempts": cr.GENERATION_ATTEMPTS,
        "retry_allowed": cr.RETRY_ALLOWED,
        "llm_role": "title/summary/dominant_activities only",
        "llm_may_change_boundaries": cr.LLM_MAY_CHANGE_BOUNDARIES_ALLOWED,
        "llm_may_set_evidence_class": cr.LLM_MAY_SET_EVIDENCE_CLASS_ALLOWED,
    }
    _write_text(runs / RECORD_NAME,
                json.dumps(record, ensure_ascii=False, indent=1,
                           sort_keys=True))
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage B 생성 (1회)")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)
    record = run(Path(args.runs))
    print("generated raw_chars=%d elapsed=%.1fs vram=%s"
          % (record["raw_chars"], record["elapsed_sec"],
             record["vram"].get("max_allocated_gb")))
    print("raw_sha256=%s" % record["raw_sha256"])
    print("파싱은 하지 않았다 — build 단계에서 한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
