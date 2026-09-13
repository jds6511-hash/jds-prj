"""One-shot executor for the frozen WVR grounded-evidence audit."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_grounded_report_evidence_v1 as ge


OUTPUT_REL = Path("runs/wvr_grounded_report_v1")
TIMELINE_REL = Path(
    "runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json"
)


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def execute(root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    output = root / OUTPUT_REL
    if output.exists():
        raise ge.GroundingError(f"one-shot output already exists: {output}")

    sources = ge.raw_universe(root)
    manifest = ge.manifest_sha256(sources)
    if manifest != ge.EXPECTED_RAW_MANIFEST_SHA256:
        raise ge.GroundingError(f"raw manifest drift: {manifest}")

    timeline = json.loads((root / TIMELINE_REL).read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=False)
    record = {
        "event": ge.EVENT,
        "code_head": _git_head(root),
        "raw_manifest_sha256": manifest,
        "raw_files_expected": ge.EXPECTED_RAW_COUNT,
        "raw_files_inspected": 0,
        "inference": dict(ge.ZERO_INFERENCE),
        "retry": 0,
        "audit_complete": False,
    }
    ge.write_json(output / "execution_record.json", record)

    audits = []
    for index, source in enumerate(sources, start=1):
        audit = ge.audit_one(source, Path(source["raw_abs"]).read_bytes(),
                             ge.ACTIVITY_LABELS)
        audit["observation"]["observation_id"] = f"GO{index:04d}"
        audits.append(audit)
        record["raw_files_inspected"] = index
        ge.write_json(output / "execution_record.json", record)
    if record["raw_files_inspected"] != ge.EXPECTED_RAW_COUNT:
        raise ge.GroundingError("incomplete raw audit")
    record["audit_complete"] = True
    decision = ge.evaluate_sufficiency(audits, timeline)
    if decision["branch"] == "SOURCE_INSUFFICIENT":
        return ge.write_source_insufficient_outputs(output, audits, record,
                                                    decision)
    raise ge.GroundingError("Branch A writer is not implemented")


def main() -> int:
    result = execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
