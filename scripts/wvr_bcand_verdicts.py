"""Record reviewer boundary verdicts and enforce the mapping reveal gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_boundary_candidate_v1 as bc  # noqa: E402


class VerdictError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(bc.canonical(payload) + "\n")


def _packet_ids(runs: Path) -> list[str]:
    path = runs / "bcand_v1_packet_ids.json"
    if not path.is_file():
        raise VerdictError("review packet candidate ids are missing")
    return _load(path).get("packet_candidate_ids") or []


def record(runs: Path, payload: dict) -> dict:
    if bc.VERDICT_BY_EXECUTOR:
        raise VerdictError("executor cannot record verdicts")
    expected = _packet_ids(runs)
    rows = payload.get("verdicts") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise VerdictError("verdicts must be a list")
    index = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"candidate_id", "verdict"}:
            raise VerdictError("invalid reviewer verdict schema")
        if row["candidate_id"] in index:
            raise VerdictError("duplicate candidate verdict")
        index[row["candidate_id"]] = {"verdict": row["verdict"]}
    try:
        summary = bc.verdict_summary(index, expected)
    except bc.CandidateError as error:
        raise VerdictError(str(error)) from error
    document = {
        "schema": "wvr_bcand_v1_verdicts", "event": bc.EVENT,
        "recorded_by": "reviewer", "verdicts": rows,
        "complete": summary["reveal_allowed"], "summary": summary,
        "final_verdict": None, "final_verdict_by_executor": False,
        "mapping_revealed": False,
    }
    _write(runs / "bcand_v1_verdicts.json", document)
    return document


def reveal(runs: Path) -> dict[str, float]:
    verdict_path = runs / "bcand_v1_verdicts.json"
    if not verdict_path.is_file():
        raise VerdictError("reveal refused: reviewer verdicts are missing")
    expected = _packet_ids(runs)
    document = _load(verdict_path)
    index = {row["candidate_id"]: {"verdict": row["verdict"]}
             for row in document.get("verdicts", [])}
    try:
        summary = bc.verdict_summary(index, expected)
    except bc.CandidateError as error:
        raise VerdictError("reveal refused: %s" % error) from error
    if not summary["reveal_allowed"]:
        raise VerdictError("reveal refused: missing reviewer verdicts")
    mapping_path = runs / "bcand_v1_blind_map.json"
    if not mapping_path.is_file():
        raise VerdictError("reveal refused: sealed mapping is missing")
    return _load(mapping_path)["candidate_to_time"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", type=Path)
    group.add_argument("--reveal", action="store_true")
    args = parser.parse_args(argv)
    runs = Path(args.runs)
    if args.record:
        record(runs, _load(args.record))
        print("reviewer verdicts recorded")
    else:
        reveal(runs)
        print("mapping reveal gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
