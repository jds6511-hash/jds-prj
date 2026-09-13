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
V3_HIGHLIGHTS_REL = Path("runs/wvr_whole_video_report_v3/highlights.json")
PROTECTED_FILES = {
    "runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json":
        "ba43a395c26342b6e028b32e33db629c82bf08c3d74785e211c7b04fb5537937",
    "runs/wvr_whole_video_merge_v1/timeline_lineage.json":
        "23d9734363c5f98c507bce4b4c76ae913f9359d091d22204ebfa5261fb758e8e",
    "runs/wvr_overview_synthesis_v2/canonical_flow.json":
        "f1bb720e48b602030143eebd43a200098cc24a125176116e1ff7587295c2858f",
    "runs/wvr_overview_synthesis_v2/overview_result.json":
        "f5d9cc5efcbf1af70e453c7536468b861e2e5eb977604d0657f839dc101b4ba6",
}
PROTECTED_TREES = {
    "runs/wvr_whole_video_report_v2":
        "c30c209951b8a487bca7dbc4b6428762844b48407e85f1706ac2349d4438d2f9",
    "runs/wvr_whole_video_report_v3":
        "174ce25ba807e1f90b283547889911373f105eb13f1c584bbaba65a3bac5077a",
}
M3_RECORDED_SHA = "aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92"
BETA_V3_RECORDED_TREE = "63f7e620654376344cf7853023755512d0eeaa6384e22f4303eb36fc9fb5bf3a"


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def protected_state(root: Path) -> dict:
    files = ge.snapshot_sources(root, PROTECTED_FILES)
    trees = {relative: ge.tree_sha256(root / relative)
             for relative in PROTECTED_TREES}
    v2_result = json.loads(
        (root / "runs/wvr_whole_video_report_v2/result.json").read_text(
            encoding="utf-8"))
    return {
        "files": files,
        "trees": trees,
        "m3_recorded_sha256": v2_result["source_state"]["m3_stt_sha256"],
        "beta_v3_recorded_tree_sha256": v2_result["source_state"][
            "beta_v3_tree_sha256"],
    }


def assert_preregistered_state(state: dict) -> None:
    if state["files"] != PROTECTED_FILES:
        raise ge.GroundingError("preregistered protected file hash mismatch")
    if state["trees"] != PROTECTED_TREES:
        raise ge.GroundingError("preregistered protected tree hash mismatch")
    if state["m3_recorded_sha256"] != M3_RECORDED_SHA:
        raise ge.GroundingError("preregistered M3 reference mismatch")
    if state["beta_v3_recorded_tree_sha256"] != BETA_V3_RECORDED_TREE:
        raise ge.GroundingError("preregistered beta/v3 tree reference mismatch")


def execute(root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    output = root / OUTPUT_REL
    if output.exists():
        raise ge.GroundingError(f"one-shot output already exists: {output}")

    sources = ge.raw_universe(root)
    manifest = ge.manifest_sha256(sources)
    if manifest != ge.EXPECTED_RAW_MANIFEST_SHA256:
        raise ge.GroundingError(f"raw manifest drift: {manifest}")

    before = protected_state(root)
    assert_preregistered_state(before)

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
        "protected_state_before": before,
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
    after = protected_state(root)
    assert_preregistered_state(after)
    ge.assert_unchanged(before, after)
    post_manifest = ge.manifest_sha256(sources)
    if post_manifest != manifest:
        raise ge.GroundingError("raw source hash drift")
    record["protected_state_after"] = after
    record["source_hashes_unchanged"] = True
    record["raw_manifest_after_sha256"] = post_manifest
    if decision["branch"] == "SOURCE_INSUFFICIENT":
        return ge.write_source_insufficient_outputs(output, audits, record,
                                                    decision)
    observations, detail_store = ge.build_grounded_store(audits)
    candidates = ge.build_candidates(audits, timeline)
    final = next((row for row in candidates if row["is_final_phase"]), None)
    if final is None:
        raise ge.GroundingError("DIVERSITY_SELECTION_CONTRACT_UNSATISFIED: final")
    dominant = set(ge._dominant_activities(timeline))
    highlights = ge.select_highlights(
        candidates, [final["start_sec"], final["end_sec"]], dominant)
    v3_highlights = json.loads((root / V3_HIGHLIGHTS_REL).read_text(
        encoding="utf-8"))
    comparison = ge.compare_v3(highlights, v3_highlights, dominant)
    return ge.write_branch_a_outputs(
        output, audits, record, decision, observations, detail_store,
        candidates, highlights, comparison)


def main() -> int:
    result = execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
