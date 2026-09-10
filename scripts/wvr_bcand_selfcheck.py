"""Pre-inference technical gate for boundary candidate V1."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_bcand_build as builder  # noqa: E402
import wvr_boundary_candidate_v1 as bc  # noqa: E402

SUBMISSION_SHA256 = (
    "5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca994e9cd7b")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def checks(runs: Path, submission: Path) -> dict:
    try:
        rebuilt = builder.build(runs)
    except Exception:
        return {"status": "FAIL", "checks": {"deterministic_rebuild": False},
                "candidate_count": 0, "batch_count": 0,
                "inference_count": len(list(runs.glob("bcand_v1_raw_B*.txt")))}
    candidates_path = runs / "bcand_v1_candidates.json"
    map_path = runs / "bcand_v1_blind_map.json"
    batches_path = runs / "bcand_v1_batches.json"
    expected_candidates = {
        "schema": "wvr_bcand_v1_candidates", "event": bc.EVENT,
        "source_map_sha256": bc.SOURCE_MAP_SHA256,
        "candidate_count": len(rebuilt["candidates"]),
        "candidates": rebuilt["candidates"]}
    expected_batches = {
        "schema": "wvr_bcand_v1_batches", "event": bc.EVENT,
        "batch_size": bc.BATCH_SIZE, "batch_count": len(rebuilt["batches"]),
        "prompt_template_sha256": bc.PROMPT_TEMPLATE_SHA256,
        "batches": rebuilt["batches"]}
    prompts_match = all(
        (runs / ("bcand_v1_prompt_%s.txt" % batch_id)).is_file()
        and (runs / ("bcand_v1_prompt_%s.txt" % batch_id)).read_text(
            encoding="utf-8") == prompt
        for batch_id, prompt in rebuilt["prompts"].items())
    blind = _load(map_path) if map_path.is_file() else {}
    checks_map = {
        "source_map_hash_match":
            builder.sha256_file(runs / bc.SOURCE_MAP_NAME) == bc.SOURCE_MAP_SHA256,
        "submission_hash_match":
            submission.is_file() and sha256_file(submission) == SUBMISSION_SHA256,
        "prompt_template_hash_frozen":
            bc.sha256_text(bc.PROPOSER_PROMPT_V1) == bc.PROMPT_TEMPLATE_SHA256,
        "candidate_artifact_matches_rebuild":
            candidates_path.is_file() and _load(candidates_path) == expected_candidates,
        "batch_artifact_matches_rebuild":
            batches_path.is_file() and _load(batches_path) == expected_batches,
        "rendered_prompts_match_rebuild": prompts_match,
        "candidate_count_frozen": len(rebuilt["candidates"]) == 144,
        "batch_count_frozen": len(rebuilt["batches"]) == 18,
        "candidate_ids_unique": len({row["candidate_id"]
                                     for row in rebuilt["candidates"]}) == 144,
        "mapping_sealed": blind == rebuilt["blind_map"]
            and blind.get("sealed") is True
            and blind.get("reveal_before_verdicts_allowed") is False,
        "blind_leakage_zero": rebuilt["leakage_audit"]["violations"] == [],
        "all_alternatives_preserved": all(
            len(side["sets"]) == len(side["windows"])
            for row in rebuilt["candidates"]
            for side in (row["before"], row["after"])),
        "no_downstream_artifact": not any(
            (runs / name).exists() for name in
            ("bcand_v1_chapters.json", "bcand_v1_overview.json",
             "bcand_v1_analysis.json", "bcand_v1_conclusion.json",
             "bcand_v1_report.json", "bcand_v1_report.hwpx")),
        "prohibitions_closed": all(getattr(bc, name) is False for name in bc.FLAGS),
    }
    return {"status": "PASS" if all(checks_map.values()) else "FAIL",
            "checks": checks_map, "candidate_count": len(rebuilt["candidates"]),
            "batch_count": len(rebuilt["batches"]),
            "inference_count": len(list(runs.glob("bcand_v1_raw_B*.txt")))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--submission", default="runs/quality_candidate/S7/report.hwpx")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = checks(Path(args.runs), Path(args.submission))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True))
    else:
        print("selfcheck=%s candidates=%d batches=%d inference=%d" %
              (report["status"], report["candidate_count"], report["batch_count"],
               report["inference_count"]))
        for name, value in report["checks"].items():
            print("  check %-44s %s" % (name, value))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
