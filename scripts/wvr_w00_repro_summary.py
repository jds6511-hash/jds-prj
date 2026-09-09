"""W00 재현성 요약 — identity 표 · run 표 · 교차 비교 · 게이트 (2026-09-09).

사전등록: `docs/preregistration/WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md`

```
GPU 없음 · 추론 없음
게이트는 사전등록 §9·§10 그대로 계산한다. semantic 판정은 하지 않는다
원본 W00은 소급 VALID로 바꾸지 않는다
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

import wvr_w00_repro as rp                                  # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md")
SUMMARY_NAME = "w00_repro_summary.json"


class SummaryError(RuntimeError):
    """요약 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_run(runs: Path, run_id: str) -> dict:
    path = runs / ("%s_%s.json" % (rp.ARTIFACT_TAG, run_id))
    if not path.is_file():
        raise SummaryError("run 산출물이 없다: %s" % path.name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != rp.EVENT:
        raise SummaryError("재현성 산출물이 아니다: %s" % path.name)
    return record


def run_row(record: dict) -> dict:
    metrics = record.get("metrics") or {}
    structure = record.get("structure") or {}
    validity = record.get("validity") or {}
    degeneracy = record.get("degeneracy") or {}
    return {
        "run_id": record["run_id"],
        "technical_status": record.get("arm_status"),
        "technical_valid": bool(validity.get("valid")),
        "validity_reasons": validity.get("reasons"),
        "identity_status": (record.get("identity") or {}).get("status"),
        "raw_persisted": record.get("raw_persisted"),
        "generated_tokens": metrics.get("generated_token_count"),
        "generation_cap_hit": metrics.get("generation_cap_hit"),
        "finish_reason": metrics.get("finish_reason"),
        "raw_chars": structure.get("raw_length"),
        "raw_output_hash": record.get("raw_output_hash"),
        "completed_objects": structure.get("complete_object_count"),
        "unique_signatures": structure.get("unique_signature_count"),
        "zero_length_intervals": structure.get("zero_length_interval_count"),
        "positive_duration_intervals":
            structure.get("positive_duration_interval_count"),
        "max_signature_repeat": structure.get("max_signature_repeat"),
        "max_consecutive_repeat":
            structure.get("max_consecutive_signature_repeat"),
        "first_repeat": structure.get("first_repeat"),
        "json_complete": structure.get("json_parse_ok"),
        "reference_signature_hits": structure.get("reference_signature_hits"),
        "degeneracy": degeneracy.get("classification"),
        "degeneracy_reasons": degeneracy.get("reasons"),
        "zero_progress": degeneracy.get("zero_progress"),
        "infer_wall_sec": metrics.get("infer_wall_sec"),
    }


def cross_run(rows, records) -> dict:
    hashes = [row["raw_output_hash"] for row in rows]
    prefixes = []
    for record in records:
        structure = record.get("structure") or {}
        top = structure.get("top_signatures") or []
        prefixes.append([entry["signature"] for entry in top])
    first_objects = []
    for record in records:
        raw = record.get("raw_output") or ""
        first_objects.append(raw[:400])
    return {
        "raw_hashes": hashes,
        "raw_hashes_identical": len(set(hashes)) == 1,
        "distinct_raw_hashes": len(set(hashes)),
        "first_400_chars_identical": len(set(first_objects)) == 1,
        "top_signature_sets_identical": len(
            {json.dumps(row, ensure_ascii=False) for row in prefixes}) == 1,
        "failure_structure_identical": len({
            (row["json_complete"], row["zero_progress"],
             row["degeneracy"]) for row in rows}) == 1,
        "generated_token_spread": [min(row["generated_tokens"] or 0
                                       for row in rows),
                                   max(row["generated_tokens"] or 0
                                       for row in rows)],
    }


def build(runs: Path) -> dict:
    records = [load_run(runs, run_id) for run_id in rp.RUN_IDS]
    rows = [run_row(record) for record in records]
    verdict = rp.repro_verdict(rows)
    determinism = rp.determinism_axis([row["raw_output_hash"] for row in rows],
                                      rows)
    original = rp.original_unchanged(sha256_file(runs / rp.ORIGINAL_RECORD),
                                     sha256_file(runs / rp.ORIGINAL_RAW))
    identity = {record["run_id"]: (record.get("identity") or {})
                for record in records}
    return {
        "schema": "wvr_w00_repro_summary_v1", "event": rp.EVENT,
        "prereg": PREREG, "code_git_head": git_head(),
        "run_count": len(rows), "runs": rows,
        "identity": identity,
        "cross_run": cross_run(rows, records),
        "reproducibility": verdict,
        "determinism_axis": determinism,
        "original_w00": original,
        "retry_allowed": rp.RETRY_ALLOWED,
        "production_selection_allowed": rp.PRODUCTION_SELECTION_ALLOWED,
        "recovery_experiment_allowed": rp.RECOVERY_EXPERIMENT_ALLOWED,
        "subdivision_inference_allowed": rp.SUBDIVISION_INFERENCE_ALLOWED,
        "mapping_reveal_allowed": rp.MAPPING_REVEAL_ALLOWED,
        "semantic_verdict_by_executor": rp.SEMANTIC_VERDICT_BY_EXECUTOR,
        "forbidden_conclusions": list(rp.FORBIDDEN_CONCLUSIONS),
        "note": ("primary verdict는 §9 게이트로만, determinism 축은 §10으로만 "
                 "계산했다. 원본 W00은 WINDOW_INVALID를 유지한다."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="W00 재현성 요약")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    record = build(runs)
    (runs / SUMMARY_NAME).write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    print("reproducibility=%s (%s) degenerate=%d/3"
          % (record["reproducibility"]["verdict"],
             record["reproducibility"]["reason"],
             record["reproducibility"]["degenerate_count"]))
    print("determinism_axis=%s raw_identical=%s distinct=%s"
          % (record["determinism_axis"]["axis"],
             record["determinism_axis"]["raw_hashes_identical"],
             record["determinism_axis"]["distinct_raw_hashes"]))
    print("original_w00_unchanged=%s" % record["original_w00"]["unchanged"])
    for row in record["runs"]:
        print("  %s %-16s gen=%-5s raw=%-6s obj=%-4s uniq=%-3s zero=%-4s "
              "rep=%-3s json=%-5s %s"
              % (row["run_id"], row["technical_status"],
                 row["generated_tokens"], row["raw_chars"],
                 row["completed_objects"], row["unique_signatures"],
                 row["zero_length_intervals"], row["max_signature_repeat"],
                 row["json_complete"], row["degeneracy"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
