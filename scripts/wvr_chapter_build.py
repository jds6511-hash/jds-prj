"""SEMANTIC_CHAPTER_SHADOW_V1 파싱·계보·packet 생성 (GPU 없이).

사전등록: `docs/preregistration/WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md`

```
입력   chapter_v1_raw.txt (보존된 생성물) · chapter_v1_record.json ·
      conservative_event_map_v1.json (해시 동결)
출력   chapter_v1_chapters.json · chapter_v1_packet.md · chapter_v1_summary.json
계약   파싱 실패·스키마·계보 위반은 고치지 않고 중단한다 (재생성 금지) ·
      executor는 판정을 쓰지 않는다
```

사용: `python scripts/wvr_chapter_build.py --runs runs/wvr_light_v1`
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_chapter_selfcheck as selfcheck                    # noqa: E402
import wvr_chapter_v1 as ch                                  # noqa: E402

RAW_NAME = "chapter_v1_raw.txt"
RECORD_NAME = "chapter_v1_record.json"
PROMPT_NAME = "chapter_v1_prompt.txt"
CHAPTERS_NAME = "chapter_v1_chapters.json"
PACKET_NAME = "chapter_v1_packet.md"
SUMMARY_NAME = "chapter_v1_summary.json"


class BuildError(RuntimeError):
    """파싱·계보 계약 위반."""


def _git(*args) -> str:
    done = subprocess.run(["git"] + list(args), cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip()


def build(runs: Path) -> dict:
    try:
        ch.assert_flags_closed()
    except ch.ChapterError as error:
        raise BuildError("%s" % error)
    if ch.OVERVIEW_GENERATION_ALLOWED or ch.REPORT_GENERATION_ALLOWED \
            or ch.ANALYSIS_GENERATION_ALLOWED:
        raise BuildError("이 단계에서 Overview·Analysis·리포트 생성은 금지다")
    raw_path = runs / RAW_NAME
    if not raw_path.is_file():
        raise BuildError("RAW_NOT_PERSISTED: %s가 없다" % RAW_NAME)
    record_path = runs / RECORD_NAME
    if not record_path.is_file():
        raise BuildError("RAW_NOT_PERSISTED: %s가 없다" % RECORD_NAME)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    raw = raw_path.read_text(encoding="utf-8")
    if record.get("raw_sha256") != ch.sha256_text(raw):
        raise BuildError("RAW_NOT_PERSISTED: raw 해시가 record와 다르다")
    if record.get("prompt_sha256") != ch.RENDERED_PROMPT_SHA256:
        raise BuildError("CONFIG_MISMATCH: 프롬프트 해시가 동결값과 다르다")
    if record.get("source_map_sha256") != ch.SOURCE_MAP_SHA256:
        raise BuildError("SOURCE_MAP_HASH_MISMATCH: record의 map 해시가 다르다")
    if record.get("generation_attempts") != ch.GENERATION_ATTEMPTS:
        raise BuildError("CONFIG_MISMATCH: 생성 횟수가 %d이 아니다"
                         % ch.GENERATION_ATTEMPTS)
    effective = record.get("effective_runtime") or {}
    if effective.get("quantization_mismatch"):
        raise BuildError("CONFIG_MISMATCH: 양자화 요청·실효값 불일치")

    try:
        document = selfcheck.load_map(runs)
    except selfcheck.SelfCheckError as error:
        raise BuildError("%s" % error)

    try:
        payload = ch.extract_json(raw)
        declared = ch.assert_declared_ids(payload, document)
        chapters = ch.parse_chapters(payload)
        lineage = ch.derive_lineage(chapters, document)
        boundaries = ch.boundary_evidence(chapters, document)
        conflict = ch.conflict_safety(chapters, lineage, document)
        unresolved = ch.unresolved_safety(chapters, lineage, document)
    except ch.ChapterError as error:
        raise BuildError("%s" % error)
    if conflict["violations"]:
        raise BuildError("CONFLICT_RESOLVED_BY_GENERATOR: %r"
                         % conflict["violations"])
    if unresolved["violations"]:
        raise BuildError("UNRESOLVED_FILLED: %r" % unresolved["violations"])

    anomaly_rows = ch.anomalies(chapters, lineage, document)
    grid = ch.grid_alignment(chapters)
    provenance = {
        "prereg": ch.PREREG, "event": ch.EVENT,
        "prereg_commit": record.get("prereg_commit"),
        "generation_commit": record.get("code_git_head"),
        "build_commit": _git("rev-parse", "HEAD") or "unknown",
        "source_map_sha256": ch.SOURCE_MAP_SHA256,
        "prompt_name": ch.CHAPTER_PROMPT_NAME,
        "prompt_sha256": record.get("prompt_sha256"),
        "prompt_template_sha256": ch.PROMPT_TEMPLATE_SHA256,
        "raw_sha256": record.get("raw_sha256"),
        "raw_chars": record.get("raw_chars"),
        "generator": {
            "model_id": effective.get("effective_model_id")
            or ch.LLM_MODEL_ID,
            "model_revision": effective.get("effective_model_revision"),
            "dtype": effective.get("effective_dtype") or ch.LLM_DTYPE,
            "quantized": effective.get("effective_quantized"),
            "do_sample": effective.get("do_sample"),
            "max_new_tokens": effective.get("max_new_tokens"),
            "attn_implementation": effective.get("attn_implementation")},
        "elapsed_sec": record.get("elapsed_sec"),
        "vram": record.get("vram"),
        "new_vlm_inference_count": 0,
        "track_a_input_used": ch.TRACK_A_INPUT_ALLOWED,
        "generation_attempts": record.get("generation_attempts"),
        "retry_allowed": ch.RETRY_ALLOWED,
        "declared_event_ids_in_output": declared,
    }
    chapters_doc = {
        "schema": ch.SCHEMA, "event": ch.EVENT, "prereg": ch.PREREG,
        "artifact_name": ch.ARTIFACT_NAME,
        "provenance": provenance,
        "policy": {
            "unresolved_opening_policy": ch.UNRESOLVED_OPENING_POLICY,
            "chapter_count_bounds": [ch.MIN_CHAPTERS, ch.MAX_CHAPTERS],
            "confidence_classes": list(ch.CONFIDENCE_CLASSES),
            "boundary_reasons": list(ch.BOUNDARY_REASONS),
            "short_chapter_sec": ch.SHORT_CHAPTER_SEC,
            "flags": {name: getattr(ch, name) for name in ch.FLAGS},
            "chapter_llm_allowed": ch.CHAPTER_LLM_ALLOWED,
            "blockers": list(ch.BLOCKERS),
            "final_verdict_vocabulary": ch.FINAL_VERDICT_VOCABULARY_LINE,
            "verdict_by_executor": ch.VERDICT_BY_EXECUTOR},
        "prior_state": dict(ch.PRIOR_STATE),
        "chapters": chapters,
        "lineage": lineage,
        "boundary_evidence": boundaries,
        "grid_alignment": grid,
        "conflict_safety": conflict,
        "unresolved_safety": unresolved,
        "anomalies": anomaly_rows,
        "executor_state": ch.executor_state(chapters, anomaly_rows),
    }
    summary = {
        "schema": "wvr_chapter_v1_summary", "event": ch.EVENT,
        "prereg": ch.PREREG, "provenance": provenance,
        "chapter_count": len(chapters),
        "chapter_spans": [[row["start_sec"], row["end_sec"]]
                          for row in chapters],
        "chapter_titles": [row["title"] for row in chapters],
        "confidence_classes": [row["confidence_class"] for row in chapters],
        "boundary_reasons": [row["boundary_reason"] for row in chapters],
        "internal_boundary_count": grid["internal_boundary_count"],
        "on_24s_grid_count": grid["on_24s_grid_count"],
        "off_grid_count": grid["off_grid_count"],
        "conflict_blocks_covered": len(conflict["conflict_blocks_covered"]),
        "conflict_block_total": conflict["conflict_block_total"],
        "conflict_violations": len(conflict["violations"]),
        "unresolved_violations": len(unresolved["violations"]),
        "unresolved_intervals": unresolved["unresolved_intervals"],
        "anomalies": anomaly_rows,
        "source_event_total": document["lineage_summary"][
            "source_events_total"],
        "source_events_referenced": len(sorted({
            event_id for row in lineage
            for event_id in row["stable_source_events"]
            + row["conflict_source_events"]})),
        "new_vlm_inference_count": 0,
        "generation_attempts": record.get("generation_attempts"),
        "executor_state": ch.executor_state(chapters, anomaly_rows),
        "reviewer_final_verdict": None,
        "final_verdict_vocabulary": ch.FINAL_VERDICT_VOCABULARY_LINE,
    }
    packet = ch.packet(document, chapters, lineage, boundaries, anomaly_rows,
                       provenance)
    return {"chapters_doc": chapters_doc, "summary": summary,
            "packet": packet}


def write_artifacts(runs: Path, built: dict) -> list:
    written = []
    for name, payload in ((CHAPTERS_NAME, built["chapters_doc"]),
                          (SUMMARY_NAME, built["summary"])):
        _write_text(runs / name, ch.canonical(payload) + "\n")
        written.append(name)
    _write_text(runs / PACKET_NAME, built["packet"])
    written.append(PACKET_NAME)
    return written


def _write_text(path, text: str) -> None:
    """산출물은 항상 LF로 쓴다 — 플랫폼별 CRLF 변환이 해시를 깨뜨린다."""
    with open(path, "w", encoding="utf-8", newline=chr(10)) as handle:
        handle.write(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="chapter 파싱·packet 생성")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = build(runs)
    summary = built["summary"]
    print("chapters=%d spans=%s" % (summary["chapter_count"],
                                    summary["chapter_spans"]))
    print("titles=%s" % summary["chapter_titles"])
    print("boundaries internal=%d on_grid=%d off_grid=%d"
          % (summary["internal_boundary_count"], summary["on_24s_grid_count"],
             summary["off_grid_count"]))
    print("conflict blocks covered=%d/%d violations=%d · unresolved violations=%d"
          % (summary["conflict_blocks_covered"],
             summary["conflict_block_total"],
             summary["conflict_violations"],
             summary["unresolved_violations"]))
    print("anomalies=%d" % len(summary["anomalies"]))
    if args.dry_run:
        print("dry-run — 파일을 쓰지 않았다")
        return 0
    for name in write_artifacts(runs, built):
        print("wrote %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
