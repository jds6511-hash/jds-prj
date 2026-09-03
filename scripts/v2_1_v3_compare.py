"""v3 paired 비교 — R0(v2)와 R1(v3)의 manifest·정본을 나란히 읽는다.

지표를 여기서 새로 계산하지 않는다. orchestrator가 실행 시각에 기록한
`distributions`를 그대로 읽고, mechanism metric만 정본에서 재확인한다.
계산을 두 곳에 두면 어느 쪽이 맞는지 다시 다투게 된다.

사용:
    python scripts/v2_1_v3_compare.py --r0 runs/r0_v2 --r1 runs/r1_v3 \\
        --out results/v3_paired_compare.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FIXED = ("config_hash", "code_revision", "model_id")


def _canonical_path(run: Path) -> Path:
    """실행 디렉터리는 `S5/`에 두고, 회수한 사본은 평평하다. 둘 다 읽는다."""
    for candidate in (run / "S5/aar_canonical.json", run / "aar_canonical.json"):
        if candidate.is_file():
            return candidate
    raise SystemExit("정본을 찾지 못했다: %s" % run)


def arm(run: Path) -> dict:
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    document = json.loads(_canonical_path(run).read_text(encoding="utf-8"))
    episodes = document["episodes"]
    reasons: dict[str, int] = {}
    for episode in episodes:
        for reason in episode.get("grounding_reasons") or []:
            code = reason.get("code") if isinstance(reason, dict) else str(reason)
            reasons[code] = reasons.get(code, 0) + 1
    return {
        "run_dir": str(run),
        "fingerprint": manifest["fingerprint"],
        "generation": manifest["generation"],
        "model_provenance": manifest["model_provenance"],
        "gpu": manifest["gpu"],
        "distributions": manifest["distributions"],
        "prompt": document["prompt"],
        "grounding_reasons": dict(sorted(reasons.items())),
        "nonempty_canonical_summary": sum(
            1 for e in episodes if (e.get("summary") or "").strip()),
        "stage_wall_seconds": {
            stage: entry.get("wall_seconds")
            for stage, entry in manifest["stages"].items()},
    }


def _presentation(one: dict) -> dict:
    """지표는 실행이 기록한 것만 쓴다. 없으면 여기서 다시 계산하지 않고 멈춘다."""
    metrics = one["distributions"].get("presentation")
    if metrics is None:
        raise SystemExit(
            "%s: manifest에 presentation 지표가 없다(지표 도입 전 실행이다). "
            "사후 계산으로 채우지 않는다 — 같은 코드로 다시 실행해야 한다."
            % one["run_dir"])
    return metrics


def compare(r0: dict, r1: dict) -> dict:
    """무엇이 고정됐고 무엇이 바뀌었는지 명시한다."""
    held = {key: (r0["fingerprint"][key] == r1["fingerprint"][key])
            for key in FIXED}
    left, right = _presentation(r0), _presentation(r1)
    primary = {
        "metric": "presentation_eligible_episode_count",
        "r0": left["eligible"],
        "r1": right["eligible"],
        "episodes": right["episodes"],
    }
    mechanism = {
        "dialogue_note_present": {"r0": left["dialogue_note_present"],
                                   "r1": right["dialogue_note_present"]},
        "excluded_by_dialogue_grounding": {
            "r0": left["excluded_by_dialogue_grounding"],
            "r1": right["excluded_by_dialogue_grounding"]},
    }
    return {
        "held_constant": held,
        "changed": {
            "prompt_version": [r0["prompt"]["prompt_version"],
                               r1["prompt"]["prompt_version"]],
            "prompt_hash": [r0["prompt"]["prompt_hash"],
                            r1["prompt"]["prompt_hash"]],
        },
        "primary": primary,
        "mechanism": mechanism,
        "mechanism_closure": (
            mechanism["dialogue_note_present"]["r1"] == 0
            and mechanism["excluded_by_dialogue_grounding"]["r1"] == 0),
        "secondary": {
            key: {"r0": r0["distributions"].get(key),
                  "r1": r1["distributions"].get(key)}
            for key in ("parse_status", "content_status", "grounding_status",
                        "summary_mode", "counters", "raw_outputs_present",
                        "canonical_episodes", "episode_wall_seconds")},
        "grounding_reasons": {"r0": r0["grounding_reasons"],
                              "r1": r1["grounding_reasons"]},
        "nonempty_canonical_summary": {
            "r0": r0["nonempty_canonical_summary"],
            "r1": r1["nonempty_canonical_summary"]},
        "gpu": {"r0": r0["gpu"], "r1": r1["gpu"]},
        "arms": {"r0": r0, "r1": r1},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r0", required=True)
    parser.add_argument("--r1", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    report = compare(arm(Path(args.r0)), arm(Path(args.r1)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps({
        "held_constant": report["held_constant"],
        "primary": report["primary"],
        "mechanism": report["mechanism"],
        "mechanism_closure": report["mechanism_closure"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
