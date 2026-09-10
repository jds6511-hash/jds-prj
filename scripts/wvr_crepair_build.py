"""BOUNDARY_REPAIR_V1 build — Stage B 파싱·evidence class·감사·packet (GPU 없이).

사전등록:
`docs/preregistration/WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md`

```
입력   chapter_repair_v1_boundaries.json (동결 경계) · _raw.txt · _record.json ·
      conservative_event_map_v1.json (해시 동결) · chapter_v1_chapters.json (V1 대조)
출력   chapter_repair_v1_chapters.json · _packet.md · _summary.json ·
      _v1_comparison.json
계약   LLM은 제목·요약만 · evidence class는 executor 계산 ·
      conflict 노출 필수 · unresolved 보존 · 위반은 고치지 않고 중단
```
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_chapter_repair_v1 as cr                           # noqa: E402
import wvr_chapter_selfcheck as v1check                      # noqa: E402
import wvr_crepair_run as runner                             # noqa: E402
import wvr_crepair_stagea as stagea                          # noqa: E402

CHAPTERS_NAME = "chapter_repair_v1_chapters.json"
PACKET_NAME = "chapter_repair_v1_packet.md"
SUMMARY_NAME = "chapter_repair_v1_summary.json"
COMPARISON_NAME = "chapter_repair_v1_v1_comparison.json"


class BuildError(RuntimeError):
    """build 계약 위반."""


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


def build(runs: Path) -> dict:
    try:
        cr.assert_flags_closed()
    except cr.RepairError as error:
        raise BuildError("%s" % error)
    if cr.OVERVIEW_GENERATION_ALLOWED or cr.REPORT_GENERATION_ALLOWED \
            or cr.ANALYSIS_GENERATION_ALLOWED:
        raise BuildError("이 단계에서 Overview·Analysis·리포트 생성은 금지다")
    for name in (runner.RAW_NAME, runner.RECORD_NAME,
                 stagea.BOUNDARIES_NAME):
        if not (runs / name).is_file():
            raise BuildError("RAW_NOT_PERSISTED: %s가 없다" % name)
    record = json.loads((runs / runner.RECORD_NAME).read_text(
        encoding="utf-8"))
    raw = (runs / runner.RAW_NAME).read_text(encoding="utf-8")
    if record.get("raw_sha256") != cr.sha256_text(raw):
        raise BuildError("RAW_NOT_PERSISTED: raw 해시가 record와 다르다")
    if record.get("source_map_sha256") != cr.SOURCE_MAP_SHA256:
        raise BuildError("SOURCE_MAP_HASH_MISMATCH: record의 map 해시가 다르다")
    if record.get("boundaries_sha256") != sha256_file(
            runs / stagea.BOUNDARIES_NAME):
        raise BuildError("BOUNDARY_SET_NOT_FROZEN: 경계 파일이 생성 이후 바뀌었다")
    if record.get("generation_attempts") != cr.GENERATION_ATTEMPTS:
        raise BuildError("CONFIG_MISMATCH: 생성 횟수가 %d이 아니다"
                         % cr.GENERATION_ATTEMPTS)
    effective = record.get("effective_runtime") or {}
    if effective.get("quantization_mismatch"):
        raise BuildError("CONFIG_MISMATCH: 양자화 요청·실효값 불일치")

    try:
        document, events, chapters, supports, frozen = \
            runner.frozen_boundaries(runs)
    except runner.RunError as error:
        raise BuildError("%s" % error)

    try:
        payload = cr.extract_json(raw)
        titles = cr.parse_titles(payload, chapters)
    except cr.RepairError as error:
        raise BuildError("%s" % error)

    rows = []
    classes = []
    disclosures = []
    for chapter, support in zip(chapters, supports):
        text = titles[chapter["chapter_id"]]
        merged = dict(chapter)
        merged.update(text)
        rows.append(merged)
        classes.append(cr.evidence_class(support))
        disclosures.append(cr.disclosure_audit(
            chapter, support, "%s %s" % (text["title"], text["summary"])))
    evidence = cr.evidence_audit(chapters, supports, classes)
    unresolved = cr.unresolved_audit(chapters, supports, document)
    grid = cr.grid_audit(frozen["boundaries"], document)
    if evidence["violations"]:
        raise BuildError("EVIDENCE_CLASS_VIOLATION: %r"
                         % evidence["violations"])
    if unresolved["violations"]:
        raise BuildError("UNRESOLVED_FILLED: %r" % unresolved["violations"])
    for row in disclosures:
        if row["disclosure_required"] and not row["conflict_disclosed"]:
            raise BuildError("CONFLICT_DISCLOSURE_MISSING: %s"
                             % row["chapter_id"])
    anomaly_rows = cr.anomalies(rows, supports, classes, disclosures, grid)

    v1_path = runs / cr.V1_CHAPTERS_NAME
    if not v1_path.is_file():
        raise BuildError("CONFIG_MISMATCH: V1 대조 파일이 없다: %s"
                         % cr.V1_CHAPTERS_NAME)
    comparison = cr.v1_comparison(
        json.loads(v1_path.read_text(encoding="utf-8")), rows, classes,
        disclosures, grid)

    provenance = {
        "prereg": cr.PREREG, "event": cr.EVENT,
        "prereg_commit": record.get("prereg_commit"),
        "generation_commit": record.get("code_git_head"),
        "build_commit": _git("rev-parse", "HEAD") or "unknown",
        "source_map_sha256": cr.SOURCE_MAP_SHA256,
        "boundaries_sha256": record.get("boundaries_sha256"),
        "prompt_name": cr.REPAIR_PROMPT_NAME,
        "prompt_sha256": record.get("prompt_sha256"),
        "prompt_template_sha256": record.get("prompt_template_sha256"),
        "raw_sha256": record.get("raw_sha256"),
        "raw_chars": record.get("raw_chars"),
        "generator": {
            "model_id": effective.get("effective_model_id")
            or cr.LLM_MODEL_ID,
            "model_revision": effective.get("effective_model_revision"),
            "dtype": effective.get("effective_dtype") or cr.LLM_DTYPE,
            "quantized": effective.get("effective_quantized"),
            "do_sample": effective.get("do_sample"),
            "max_new_tokens": effective.get("max_new_tokens"),
            "role": record.get("llm_role")},
        "stage_a_rule": frozen["provenance"]["stage_a_rule"],
        "elapsed_sec": record.get("elapsed_sec"),
        "vram": record.get("vram"),
        "new_vlm_inference_count": 0,
        "track_a_input_used": cr.TRACK_A_INPUT_ALLOWED,
        "generation_attempts": record.get("generation_attempts"),
        "retry_allowed": cr.RETRY_ALLOWED,
        "evidence_class_assigned_by": "executor",
    }
    chapters_doc = {
        "schema": cr.SCHEMA, "event": cr.EVENT, "prereg": cr.PREREG,
        "artifact_name": cr.ARTIFACT_NAME, "provenance": provenance,
        "policy": {
            "chapter_count_bounds": [cr.MIN_CHAPTERS, cr.MAX_CHAPTERS],
            "evidence_classes": list(cr.EVIDENCE_CLASSES),
            "evidence_priority": list(cr.EVIDENCE_PRIORITY),
            "boundary_reasons": list(cr.BOUNDARY_REASONS),
            "disclosure_terms": list(cr.DISCLOSURE_TERMS),
            "flags": {name: getattr(cr, name) for name in cr.FLAGS},
            "chapter_llm_allowed": cr.CHAPTER_LLM_ALLOWED,
            "blockers": list(cr.BLOCKERS),
            "final_verdict_vocabulary": cr.FINAL_VERDICT_VOCABULARY_LINE,
            "verdict_by_executor": cr.VERDICT_BY_EXECUTOR},
        "prior_state": dict(cr.PRIOR_STATE),
        "chapters": rows,
        "chapter_support": supports,
        "evidence": classes,
        "evidence_audit": evidence,
        "disclosure_audit": disclosures,
        "unresolved_audit": unresolved,
        "grid_audit": grid,
        "boundaries": frozen["boundaries"],
        "anomalies": anomaly_rows,
        "executor_state": cr.executor_state(rows, anomaly_rows),
    }
    summary = {
        "schema": "wvr_chapter_repair_v1_summary", "event": cr.EVENT,
        "prereg": cr.PREREG, "provenance": provenance,
        "chapter_count": len(rows),
        "chapter_spans": [[row["start_sec"], row["end_sec"]] for row in rows],
        "chapter_titles": [row["title"] for row in rows],
        "evidence_classes": [row["evidence_class"] for row in classes],
        "evidence_class_counts": evidence["class_counts"],
        "internal_boundaries": [row["boundary_sec"]
                                for row in frozen["boundaries"]],
        "on_24s_grid_count": grid["on_24s_grid_count"],
        "on_48s_grid_count": grid["on_48s_grid_count"],
        "equals_region_boundary_count": grid["equals_region_boundary_count"],
        "conflict_chapters": [row["chapter_id"] for row in disclosures
                              if row["conflict_present"]],
        "conflict_disclosed_by_generator": [
            row["chapter_id"] for row in disclosures
            if row["disclosed_by_generator"]],
        "evidence_violations": len(evidence["violations"]),
        "unresolved_violations": len(unresolved["violations"]),
        "unresolved_intervals": unresolved["unresolved_intervals"],
        "anomalies": anomaly_rows,
        "new_vlm_inference_count": 0,
        "generation_attempts": record.get("generation_attempts"),
        "executor_state": cr.executor_state(rows, anomaly_rows),
        "reviewer_final_verdict": None,
        "final_verdict_vocabulary": cr.FINAL_VERDICT_VOCABULARY_LINE,
    }
    packet = cr.packet(rows, supports, classes, disclosures,
                       frozen["boundaries"], grid, anomaly_rows, comparison,
                       provenance)
    return {"chapters_doc": chapters_doc, "summary": summary,
            "packet": packet, "comparison": comparison}


def write_artifacts(runs: Path, built: dict) -> list:
    written = []
    for name, payload in ((CHAPTERS_NAME, built["chapters_doc"]),
                          (SUMMARY_NAME, built["summary"]),
                          (COMPARISON_NAME, built["comparison"])):
        _write_text(runs / name, cr.canonical(payload) + chr(10))
        written.append(name)
    _write_text(runs / PACKET_NAME, built["packet"])
    written.append(PACKET_NAME)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="repair build")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = build(runs)
    summary = built["summary"]
    print("chapters=%d spans=%s" % (summary["chapter_count"],
                                    summary["chapter_spans"]))
    print("evidence=%s" % summary["evidence_class_counts"])
    print("boundaries=%s 24s=%d 48s=%d region=%d"
          % (summary["internal_boundaries"], summary["on_24s_grid_count"],
             summary["on_48s_grid_count"],
             summary["equals_region_boundary_count"]))
    print("conflict chapters=%s disclosed_by_generator=%s"
          % (summary["conflict_chapters"],
             summary["conflict_disclosed_by_generator"]))
    print("anomalies=%d" % len(summary["anomalies"]))
    if args.dry_run:
        print("dry-run — 파일을 쓰지 않았다")
        return 0
    for name in write_artifacts(runs, built):
        print("wrote %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
