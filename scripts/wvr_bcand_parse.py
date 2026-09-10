"""Parse persisted boundary-proposer raw batches and build reviewer materials."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_boundary_candidate_v1 as bc  # noqa: E402


class ParseError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse(runs: Path) -> dict:
    record_path = runs / "bcand_v1_record.json"
    if not record_path.is_file():
        raise ParseError("RAW_NOT_PERSISTED: execution record missing")
    record = _load(record_path)
    batches_doc = _load(runs / "bcand_v1_batches.json")
    candidates_doc = _load(runs / "bcand_v1_candidates.json")
    candidates = candidates_doc["candidates"]
    events_doc = _load(runs / bc.SOURCE_MAP_NAME)
    events = bc.source_events(events_doc)
    proposals = {}
    for batch in batches_doc["batches"]:
        batch_id = batch["batch_id"]
        raw_path = runs / ("bcand_v1_raw_%s.txt" % batch_id)
        if not raw_path.is_file():
            raise ParseError("RAW_NOT_PERSISTED: %s" % batch_id)
        if _sha256_file(raw_path) != record.get("raw_sha256", {}).get(batch_id):
            raise ParseError("RAW_NOT_PERSISTED: raw hash mismatch %s" % batch_id)
        raw = raw_path.read_text(encoding="utf-8")
        raw_leakage = bc.leakage_audit([raw], events, candidates)
        if raw_leakage["violations"]:
            raise ParseError("%s: raw %s" %
                             (",".join(raw_leakage["violations"]), batch_id))
        try:
            parsed = bc.parse_batch(
                bc.extract_json(raw),
                batch["candidate_ids"])
        except bc.CandidateError as error:
            raise ParseError(str(error)) from error
        overlap = set(proposals) & set(parsed)
        if overlap:
            raise ParseError("CANDIDATE_SET_MISMATCH: duplicate across batches")
        proposals.update(parsed)
    expected = {row["candidate_id"] for row in candidates}
    if set(proposals) != expected or len(proposals) != bc.EXPECTED_CANDIDATE_COUNT:
        raise ParseError("CANDIDATE_SET_MISMATCH: aggregate")
    counts = bc.proposal_counts(proposals)
    packet_candidate_ids = bc.packet_ids(proposals)
    appendix_candidate_ids = bc.appendix_ids(proposals)
    density = bc.density_note(counts)
    packet = bc.reviewer_packet(candidates, proposals)
    appendix = bc.weak_appendix(candidates, proposals)
    leakage = bc.leakage_audit([packet, appendix], events, candidates)
    if leakage["violations"]:
        raise ParseError("PACKET_OR_GENERATION_FAILURE: reviewer material leakage")
    state = bc.executor_state(proposals, packet_candidate_ids, density, leakage)
    proposal_doc = {
        "schema": "wvr_bcand_v1_proposals", "event": bc.EVENT,
        "candidate_count": len(proposals),
        "proposals": [proposals[value] for value in sorted(proposals)]}
    audit_doc = {"schema": "wvr_bcand_v1_leakage_audit", "event": bc.EVENT,
                 **leakage}
    packet_ids_doc = {"schema": "wvr_bcand_v1_packet_ids",
                      "packet_candidate_ids": packet_candidate_ids}
    summary = {
        "schema": "wvr_bcand_v1_summary", "event": bc.EVENT,
        "counts": counts, "density": density,
        "candidate_count": len(proposals),
        "packet_candidate_count": len(packet_candidate_ids),
        "weak_appendix_count": len(appendix_candidate_ids),
        "executor_state": state, "reviewer_final_verdict": None,
        "mapping_revealed": False, "chapter_generated": False,
        "overview_generated": False}
    for name, payload in (
            ("bcand_v1_proposals.json", proposal_doc),
            ("bcand_v1_leakage_audit.json", audit_doc),
            ("bcand_v1_packet_ids.json", packet_ids_doc),
            ("bcand_v1_summary.json", summary)):
        _write_text(runs / name, bc.canonical(payload) + "\n")
    _write_text(runs / "bcand_v1_packet.md", packet)
    _write_text(runs / "bcand_v1_appendix_weak.md", appendix)
    return {"proposals": proposals, "counts": counts,
            "packet_candidate_ids": packet_candidate_ids,
            "appendix_candidate_ids": appendix_candidate_ids,
            "density": density, "leakage": leakage, "executor_state": state}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)
    result = parse(Path(args.runs))
    print("proposals=%d packet=%d weak=%d leakage=%d" %
          (len(result["proposals"]), len(result["packet_candidate_ids"]),
           len(result["appendix_candidate_ids"]),
           len(result["leakage"]["violations"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
