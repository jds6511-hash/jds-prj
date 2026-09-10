"""Build deterministic blinded inputs for boundary-candidate inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_boundary_candidate_v1 as bc  # noqa: E402


class BuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def build(runs: Path) -> dict:
    source = runs / bc.SOURCE_MAP_NAME
    if not source.is_file() or sha256_file(source) != bc.SOURCE_MAP_SHA256:
        raise BuildError("SOURCE_MAP_HASH_MISMATCH")
    bc.assert_flags_closed()
    document = json.loads(source.read_text(encoding="utf-8"))
    events = bc.source_events(document)
    candidates = bc.build_candidates(events, document)
    batch_rows = bc.batches(candidates)
    by_id = {row["candidate_id"]: row for row in candidates}
    prompts = {}
    for row in batch_rows:
        prompt = bc.render_prompt([by_id[value] for value in row["candidate_ids"]])
        prompts[row["batch_id"]] = prompt
        row["prompt_sha256"] = bc.sha256_text(prompt)
    audit = bc.leakage_audit(list(prompts.values()), events, candidates)
    if audit["violations"]:
        raise BuildError("PACKET_OR_GENERATION_FAILURE: %s" %
                         ",".join(audit["violations"]))
    return {"events": events, "candidates": candidates, "batches": batch_rows,
            "prompts": prompts, "blind_map": bc.blind_map_document(candidates),
            "leakage_audit": audit}


def write(runs: Path, built: dict) -> list[str]:
    rows = [
        ("bcand_v1_candidates.json", {
            "schema": "wvr_bcand_v1_candidates", "event": bc.EVENT,
            "source_map_sha256": bc.SOURCE_MAP_SHA256,
            "candidate_count": len(built["candidates"]),
            "candidates": built["candidates"]}),
        ("bcand_v1_blind_map.json", built["blind_map"]),
        ("bcand_v1_batches.json", {
            "schema": "wvr_bcand_v1_batches", "event": bc.EVENT,
            "batch_size": bc.BATCH_SIZE, "batch_count": len(built["batches"]),
            "prompt_template_sha256": bc.PROMPT_TEMPLATE_SHA256,
            "batches": built["batches"]}),
    ]
    written = []
    for name, payload in rows:
        _write_text(runs / name, bc.canonical(payload) + "\n")
        written.append(name)
    for batch_id, prompt in built["prompts"].items():
        name = "bcand_v1_prompt_%s.txt" % batch_id
        _write_text(runs / name, prompt)
        written.append(name)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    runs = Path(args.runs)
    built = build(runs)
    if not args.dry_run:
        write(runs, built)
    print("candidates=%d batches=%d leakage=%d" %
          (len(built["candidates"]), len(built["batches"]),
           len(built["leakage_audit"]["violations"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
