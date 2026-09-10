"""TRIGGER_ISOLATION_V1 요약 · 조작 감사 · 2×2 verdict (2026-09-10).

사전등록: `docs/preregistration/WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md`

```
GPU 없음 · 추론 없음
verdict 우선순위  INCONCLUSIVE → CONTROL_NOT_REPRODUCED → 2×2 패턴 (결과 후 변경 금지)
교차 비교          AUDIT_DIAGNOSTIC_ONLY — semantic·사실성 판정 아님
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
import wvr_w00_forensic as fx                               # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md")
SUMMARY_NAME = "trigger_v1_summary.json"
SELFCHECK_NAME = "trigger_v1_selfcheck.json"


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


def load_arm(runs: Path, arm_id: str) -> dict:
    path = runs / ("%s_%s.json" % (tg.ARTIFACT_TAG, arm_id))
    if not path.is_file():
        raise SummaryError("산출물이 없다: %s" % path.name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != tg.EVENT:
        raise SummaryError("trigger 산출물이 아니다: %s" % path.name)
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


def arm_row(record: dict, runs: Path) -> dict:
    metrics = record.get("metrics") or {}
    shape = record.get("representation") or {}
    parsed = record.get("parsed") or {}
    validity = record.get("validity") or {}
    structure = raw_structure(record, runs)
    metadata = record.get("metadata") or {}
    indices = list(metadata.get("frames_indices") or [])
    markers = record.get("timestamp_markers") or []
    completed = structure.get("complete_object_count")
    zero = structure.get("zero_length_interval_count")
    raw_path = runs / (record.get("raw_path") or "")
    raw_text = (raw_path.read_text(encoding="utf-8")
                if raw_path.is_file() else "")
    return {
        "arm_id": record["arm"]["arm_id"],
        "prompt_mode": record["arm"]["prompt_mode"],
        "metadata_mode": record["arm"]["metadata_mode"],
        "prompt_window": record.get("prompt_window"),
        "rendered_prompt_hash": record.get("rendered_prompt_hash"),
        "prompt_template_hash": record.get("prompt_template_hash"),
        "frames_indices_first_last": ([indices[0], indices[-1]] if indices
                                      else None),
        "timestamp_marker_first_last": ([markers[0], markers[-1]] if markers
                                        else None),
        "duration": metadata.get("duration"),
        "total_num_frames": metadata.get("total_num_frames"),
        "fps": metadata.get("fps"),
        "width": metadata.get("width"), "height": metadata.get("height"),
        "video_backend": metadata.get("video_backend"),
        "frames": metrics.get("delivered_frame_count"),
        "pixel_identity": (record.get("pixel_identity") or {}).get(
            "identical"),
        "pixel_values_sha256": record.get("pixel_values_sha256"),
        "input_tokens": metrics.get("input_token_count"),
        "video_tokens": metrics.get("video_token_count"),
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
        "structure_source": structure.get("structure_source"),
        "raw_event_count": len(parsed.get("events", [])),
        "collapsed_event_count": shape.get("collapsed_event_count"),
        "unique_signature_count": shape.get("unique_signature_count"),
        "degenerate": shape.get("degenerate"),
        "parse_status": parsed.get("status"),
        "language_satisfied": (validity.get("language") or {}).get("satisfied"),
        "raw_persisted": record.get("raw_persisted"),
        "arm_status": record.get("arm_status"),
        "valid": validity.get("valid"),
        "status": validity.get("status"),
        "reasons": validity.get("reasons"),
        "blockers": validity.get("blockers"),
        "output_failures": validity.get("output_failures"),
        "raw_output_hash": record.get("raw_output_hash"),
        "runtime_config_hash": record.get("runtime_config_hash"),
        "infer_wall_sec": metrics.get("infer_wall_sec"),
        "peak_vram_allocated_mib": metrics.get("peak_vram_allocated_mib"),
        "code_git_head": record.get("code_git_head"),
    }


def cross_arm_audit(records: dict, runs: Path) -> dict:
    """AUDIT_DIAGNOSTIC_ONLY — 판정 authority가 아니다."""
    raws = {}
    for arm_id, record in records.items():
        path = runs / (record.get("raw_path") or "")
        raws[arm_id] = path.read_text(encoding="utf-8") if path.is_file() \
            else ""
    pairs = (("A", "B"), ("A", "C"), ("A", "D"), ("B", "D"), ("C", "D"))
    rows = {}
    for left, right in pairs:
        first, second = raws.get(left, ""), raws.get(right, "")
        divergence = None
        if first != second:
            limit = min(len(first), len(second))
            divergence = next((index for index in range(limit)
                               if first[index] != second[index]), limit)
        rows["%s_vs_%s" % (left, right)] = {
            "raw_identical": first == second,
            "first_divergence_offset": divergence,
            "raw_chars": [len(first), len(second)],
            "raw_hash": [records[left].get("raw_output_hash"),
                         records[right].get("raw_output_hash")],
        }
    return {"role": tg.AUDIT_ROLE, "pairs": rows,
            "note": "semantic 우열·사실성을 판정하지 않는다"}


def build(runs: Path) -> dict:
    records = {arm_id: load_arm(runs, arm_id) for arm_id in tg.ARM_IDS}
    rows = [arm_row(records[arm_id], runs) for arm_id in tg.ARM_IDS]
    manipulation = tg.manipulation_audit(records)
    pixels = tg.pixel_agreement(records)

    extra_blockers = list(manipulation["reasons"])
    if not pixels["identical"]:
        extra_blockers.append(tg.PIXEL_IDENTITY_FAILURE)
    if len({record.get("video_sha256") for record in records.values()}) != 1:
        extra_blockers.append(sh.PROVENANCE_MISMATCH)
    if len({record.get("runtime_config_hash")
            for record in records.values()}) != 1:
        extra_blockers.append(tg.CONFIG_MISMATCH)
    for record in records.values():
        change = record.get("inference_config_change") or {}
        if change.get("inference_config_change") != "NONE":
            extra_blockers.append(tg.CONFIG_MISMATCH)
        if not (record.get("frozen_artifacts_unchanged") or {}).get(
                "unchanged"):
            extra_blockers.append(tg.PRIOR_ARTIFACT_CHANGED)

    selfcheck_path = runs / SELFCHECK_NAME
    selfcheck = (json.loads(selfcheck_path.read_text(encoding="utf-8"))
                 if selfcheck_path.is_file() else None)
    if selfcheck is None or not selfcheck.get("separable"):
        extra_blockers.append(tg.IMPLEMENTATION_BLOCKED)

    verdict = tg.causal_pattern(rows, sd.dedup(extra_blockers))

    summary = {
        "schema": "wvr_trigger_v1_summary", "event": tg.EVENT,
        "prereg": PREREG, "code_git_head": git_head(),
        "event_kind": tg.EVENT_KIND,
        "source_window": tg.source_window(),
        "shift_sec": tg.SHIFT_SEC,
        "pixel_times": list(tg.pixel_times()),
        "arm_count": len(rows), "arms": rows,
        "manipulation_audit": manipulation,
        "pixel_agreement": pixels,
        "selfcheck": ({"status": selfcheck.get("status"),
                       "separable": selfcheck.get("separable"),
                       "checks": selfcheck.get("checks"),
                       "transformers_version":
                           selfcheck.get("transformers_version")}
                      if selfcheck else None),
        "extra_blockers": sd.dedup(extra_blockers),
        "verdict": verdict,
        "cross_arm_audit": cross_arm_audit(records, runs),
        "frozen_artifacts": tg.frozen_artifacts_unchanged(
            {name: sha256_file(runs / name)
             for name in tg.FROZEN_ARTIFACTS if (runs / name).is_file()}),
        "prior_state": tg.PRIOR_STATE,
        "normative_authority": list(tg.NORMATIVE_AUTHORITY),
        "forbidden_conclusions": list(tg.FORBIDDEN_CONCLUSIONS),
        "visual_content_manipulation_allowed":
            tg.VISUAL_CONTENT_MANIPULATION_ALLOWED,
        "recovery_attempt_allowed": tg.RECOVERY_ATTEMPT_ALLOWED,
        "note": ("behavioral trigger isolation이다. causal mechanism proof가 "
                 "아니며 recovery를 시도하지 않았다."),
    }
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="trigger 요약·verdict")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    summary = build(runs)
    (runs / SUMMARY_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    verdict = summary["verdict"]
    print("verdict=%s reason=%s" % (verdict["verdict"], verdict["reason"]))
    print("pattern=%s valid=%s blockers=%s"
          % (verdict["pattern"], verdict["valid_arms"] or "없음",
             verdict["blockers"] or "없음"))
    for row in summary["arms"]:
        print("  %s %s/%s win=%s idx=%s mark=%s in=%s gen=%s cap=%s obj=%s "
              "uniq=%s zero=%s json=%s px_ok=%s %s"
              % (row["arm_id"], row["prompt_mode"], row["metadata_mode"],
                 row["prompt_window"], row["frames_indices_first_last"],
                 row["timestamp_marker_first_last"], row["input_tokens"],
                 row["generated_tokens"], row["generation_cap_hit"],
                 row["completed_object_count"],
                 row["raw_unique_signature_count"], row["zero_duration_count"],
                 row["json_complete"], row["pixel_identity"], row["status"]))
    checks = summary["manipulation_audit"]["checks"]
    print("  manipulation ok=%s failed=%s"
          % (summary["manipulation_audit"]["ok"],
             [name for name, value in checks.items() if not value] or "없음"))
    print("  pixel_agreement identical=%s frames=%s"
          % (summary["pixel_agreement"]["identical"],
             summary["pixel_agreement"]["frame_count"]))
    return 0 if verdict["verdict"] not in (tg.INCONCLUSIVE,) else 1


if __name__ == "__main__":
    raise SystemExit(main())
