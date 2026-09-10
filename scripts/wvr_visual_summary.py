"""VISUAL_CONTENT_ISOLATION_V1 요약 · 2×2 표 · verdict (2026-09-10).

사전등록: `docs/preregistration/WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md`

```
GPU 없음 · 추론 없음 · 기존 세 칸은 읽기만 한다 (재실행 금지)
verdict 우선순위  INCONCLUSIVE → E 판정에 따른 두 어휘 (결과 후 변경 금지)
교차 비교          AUDIT_DIAGNOSTIC_ONLY
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

import wvr_shadow_v1 as sh                                  # noqa: E402
import wvr_subdivision_v1 as sd                             # noqa: E402
import wvr_trigger_v1 as tg                                 # noqa: E402
import wvr_visual_v1 as vc                                  # noqa: E402
import wvr_w00_forensic as fx                               # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md")
SUMMARY_NAME = "visual_v1_summary.json"
SELFCHECK_NAME = "visual_v1_selfcheck.json"
REFERENCE_RECORDS = {"X0T0": "trigger_v1_A.json",
                     "X0T1": "trigger_v1_D.json",
                     "X1T1": "shadow_v1_W05.json"}


class SummaryError(RuntimeError):
    """요약 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_arm(runs: Path) -> dict:
    path = runs / ("%s_%s.json" % (vc.ARTIFACT_TAG, vc.ARM_ID))
    if not path.is_file():
        raise SummaryError("산출물이 없다: %s" % path.name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != vc.EVENT:
        raise SummaryError("visual 산출물이 아니다: %s" % path.name)
    return record


def raw_structure(record: dict, runs: Path) -> dict:
    structure = record.get("structure")
    if structure:
        return {**structure, "structure_source": "record"}
    raw_path = runs / (record.get("raw_path") or "")
    if not record.get("raw_persisted") or not raw_path.is_file():
        return {"structure_source": "UNAVAILABLE"}
    return {**fx.raw_structure(raw_path.read_text(encoding="utf-8")),
            "structure_source": "raw_file_post_hoc",
            "raw_file_sha256": sha256_file(raw_path)}


def consecutive_repeats(raw: str) -> int:
    signatures = [(match.group(3), match.group(4), match.group(5))
                  for match in fx.OBJECT_RE.finditer(raw or "")]
    best, current, previous = 0, 0, None
    for signature in signatures:
        current = current + 1 if signature == previous else 1
        previous = signature
        best = max(best, current)
    return best


def structural_row(record: dict, structure: dict, label: str,
                   raw_text: str) -> dict:
    metrics = record.get("metrics") or {}
    shape = record.get("representation") or {}
    validity = record.get("validity") or {}
    completed = structure.get("complete_object_count")
    zero = structure.get("zero_length_interval_count")
    return {
        "label": label,
        "frames": metrics.get("delivered_frame_count"),
        "input_tokens": metrics.get("input_token_count"),
        "generated_tokens": metrics.get("generated_token_count"),
        "generation_cap_hit": metrics.get("generation_cap_hit"),
        "finish_reason": record.get("finish_reason"),
        "raw_chars": structure.get("raw_length"),
        "completed_object_count": completed,
        "raw_unique_signature_count": structure.get("unique_signature_count"),
        "zero_duration_count": zero,
        "positive_duration_count": (completed - zero
                                    if completed is not None
                                    and zero is not None else None),
        "max_signature_repeat": structure.get("max_signature_repeat"),
        "max_consecutive_repeat": consecutive_repeats(raw_text),
        "first_repeat": structure.get("first_repeat"),
        "top_signatures": structure.get("top_signatures"),
        "json_complete": structure.get("json_parse_ok"),
        "collapsed_event_count": shape.get("collapsed_event_count"),
        "unique_signature_count": shape.get("unique_signature_count"),
        "degenerate": shape.get("degenerate"),
        "status": validity.get("status"),
        "reasons": validity.get("reasons"),
        "raw_output_hash": record.get("raw_output_hash"),
        "structure_source": structure.get("structure_source"),
    }


def arm_row(record: dict, runs: Path) -> dict:
    structure = raw_structure(record, runs)
    raw_path = runs / (record.get("raw_path") or "")
    raw_text = (raw_path.read_text(encoding="utf-8")
                if raw_path.is_file() else "")
    metadata = record.get("metadata") or {}
    indices = list(metadata.get("frames_indices") or [])
    markers = record.get("timestamp_markers") or []
    validity = record.get("validity") or {}
    parsed = record.get("parsed") or {}
    row = structural_row(record, structure, "E (X1T0)", raw_text)
    row.update({
        "arm_id": record["arm"]["arm_id"], "cell": record["arm"]["cell"],
        "pixel_source": record["arm"]["pixel_source"],
        "time_encoding": record["arm"]["time_encoding"],
        "prompt_window": record.get("prompt_window"),
        "rendered_prompt_hash": record.get("rendered_prompt_hash"),
        "prompt_template_hash": record.get("prompt_template_hash"),
        "frames_indices_first_last": ([indices[0], indices[-1]] if indices
                                      else None),
        "timestamp_marker_first_last": ([markers[0], markers[-1]] if markers
                                        else None),
        "pixel_times_first_last": ([record["pixel_times"][0],
                                    record["pixel_times"][-1]]
                                   if record.get("pixel_times") else None),
        "pixel_identity": (record.get("pixel_identity") or {}).get(
            "identical"),
        "time_encoding_identity": (record.get("time_encoding_identity")
                                   or {}).get("identical"),
        "pixel_values_sha256": record.get("pixel_values_sha256"),
        "video_tokens": (record.get("metrics") or {}).get(
            "video_token_count"),
        "duration": metadata.get("duration"),
        "total_num_frames": metadata.get("total_num_frames"),
        "fps": metadata.get("fps"),
        "parse_status": parsed.get("status"),
        "raw_event_count": len(parsed.get("events", [])),
        "language_satisfied": (validity.get("language") or {}).get("satisfied"),
        "raw_persisted": record.get("raw_persisted"),
        "arm_status": record.get("arm_status"),
        "valid": validity.get("valid"),
        "blockers": validity.get("blockers"),
        "output_failures": validity.get("output_failures"),
        "runtime_config_hash": record.get("runtime_config_hash"),
        "infer_wall_sec": (record.get("metrics") or {}).get("infer_wall_sec"),
        "code_git_head": record.get("code_git_head"),
    })
    return row


def reference_rows(runs: Path) -> dict:
    """기존 세 칸의 구조 항목만 읽는다 (재실행하지 않는다)."""
    rows = {}
    for cell, name in REFERENCE_RECORDS.items():
        path = runs / name
        if not path.is_file():
            rows[cell] = {"label": cell, "available": False}
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        raw_name = (record.get("raw_path")
                    or name.replace(".json", "_raw.txt"))
        raw_path = runs / raw_name
        raw_text = (raw_path.read_text(encoding="utf-8")
                    if raw_path.is_file() else "")
        structure = (fx.raw_structure(raw_text) if raw_text else {})
        row = structural_row(record, structure, cell, raw_text)
        row["available"] = True
        row["source_record"] = name
        row["record_sha256"] = sha256_file(path)
        row["raw_sha256"] = (sha256_file(raw_path) if raw_path.is_file()
                             else None)
        rows[cell] = row
    return rows


def cross_comparison(arm: dict, references: dict) -> dict:
    """AUDIT_DIAGNOSTIC_ONLY — 구조 항목 나란히 보기."""
    fields = ("generated_tokens", "generation_cap_hit", "raw_chars",
              "completed_object_count", "raw_unique_signature_count",
              "zero_duration_count", "positive_duration_count",
              "max_signature_repeat", "json_complete",
              "collapsed_event_count", "unique_signature_count",
              "degenerate", "status", "raw_output_hash")
    rows = {"E (X1T0)": {name: arm.get(name) for name in fields}}
    for cell, row in sorted(references.items()):
        rows[cell] = ({name: row.get(name) for name in fields}
                      if row.get("available") else {"available": False})
    return {"role": tg.AUDIT_ROLE, "fields": list(fields), "rows": rows,
            "note": "semantic 우열·사실성을 판정하지 않는다"}


def build(runs: Path) -> dict:
    record = load_arm(runs)
    row = arm_row(record, runs)

    extra_blockers = []
    cells = vc.frozen_cells_unchanged(
        {name: sha256_file(runs / name) for name in vc.FROZEN_ARTIFACTS
         if (runs / name).is_file()})
    if not cells["unchanged"]:
        extra_blockers.append(vc.FROZEN_CELL_CHANGED)
    if not (record.get("frozen_cells_unchanged") or {}).get("unchanged"):
        extra_blockers.append(vc.FROZEN_CELL_CHANGED)
    change = record.get("inference_config_change") or {}
    if change.get("inference_config_change") != "NONE":
        extra_blockers.append(vc.CONFIG_MISMATCH)
    if not row.get("pixel_identity"):
        extra_blockers.append(vc.PIXEL_IDENTITY_FAILURE)
    if not row.get("time_encoding_identity"):
        extra_blockers.append(vc.TIME_ENCODING_MISMATCH)

    selfcheck_path = runs / SELFCHECK_NAME
    selfcheck = (json.loads(selfcheck_path.read_text(encoding="utf-8"))
                 if selfcheck_path.is_file() else None)
    if selfcheck is None or not selfcheck.get("ok"):
        extra_blockers.append(tg.IMPLEMENTATION_BLOCKED)

    references = reference_rows(runs)
    for cell, reference in references.items():
        if not reference.get("available"):
            extra_blockers.append(vc.FROZEN_CELL_CHANGED)
            continue
        expected = {"X0T0": sh.WINDOW_INVALID, "X0T1": sh.WINDOW_VALID,
                    "X1T1": sh.WINDOW_VALID}[cell]
        if reference.get("status") != expected:
            extra_blockers.append(vc.FROZEN_CELL_CHANGED)

    decision = vc.verdict(row, sd.dedup(extra_blockers))
    return {
        "schema": "wvr_visual_v1_summary", "event": vc.EVENT,
        "prereg": PREREG, "code_git_head": git_head(),
        "event_kind": vc.EVENT_KIND,
        "new_inference_count": vc.EXPECTED_ARM_COUNT,
        "arm": row,
        "reference_cells": references,
        "verdict": decision,
        "extra_blockers": sd.dedup(extra_blockers),
        "frozen_cells": cells,
        "selfcheck": ({"ok": selfcheck.get("ok"),
                       "checks": selfcheck.get("checks")}
                      if selfcheck else None),
        "cross_comparison": cross_comparison(row, references),
        "prior_state": vc.PRIOR_STATE,
        "normative_authority": list(vc.NORMATIVE_AUTHORITY),
        "forbidden_conclusions": list(vc.FORBIDDEN_CONCLUSIONS),
        "measurement_scope": vc.MEASUREMENT_SCOPE,
        "note": ("2×2의 남은 한 칸만 새로 측정했다. 기존 세 칸은 읽기만 했고 "
                 "재실행하지 않았다."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="visual isolation 요약")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    summary = build(runs)
    (runs / SUMMARY_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    decision = summary["verdict"]
    print("verdict=%s reason=%s" % (decision["verdict"], decision["reason"]))
    print("blockers=%s" % (decision["blockers"] or "없음"))
    print("claim=%s" % decision["allowed_claim"])
    table = decision["table"]
    for cell in ("X0T0", "X0T1", "X1T1", "X1T0"):
        row = table[cell]
        print("  %s  %-16s %-14s %s  (%s)"
              % (cell, row["pixels"], row["time"], row["status"],
                 row["source"]))
    arm = summary["arm"]
    print("  E gen=%s cap=%s obj=%s uniq=%s zero=%s json=%s coll=%s "
          "pixel_ok=%s time_ok=%s %s"
          % (arm["generated_tokens"], arm["generation_cap_hit"],
             arm["completed_object_count"], arm["raw_unique_signature_count"],
             arm["zero_duration_count"], arm["json_complete"],
             arm["collapsed_event_count"], arm["pixel_identity"],
             arm["time_encoding_identity"], arm["status"]))
    return 0 if decision["verdict"] != vc.INCONCLUSIVE else 1


if __name__ == "__main__":
    raise SystemExit(main())
