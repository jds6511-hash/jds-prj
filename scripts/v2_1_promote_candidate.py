"""quality candidate 승격 — 새 submission arm manifest를 만든다 (TRACK A · 2026-09-08).

```
OLD  runs/vad0_paired/s1_shadow/report.hwpx   4e10aaab…   rollback 유지
NEW  runs/quality_candidate/S7/report.hwpx    57320758…   새 submission arm
```

**생성을 다시 하지 않는다.** 이 스크립트는 두 artifact를 합치고, 그 정확한 파일에
대해 구조 검증·한글 열림·PDF export를 다시 해 보고 결과를 적는다.

사람이 숫자를 넣어 PASS를 만들 수 없다 — 값은 전부 artifact에서 파생한다.

사용:
    python scripts/v2_1_promote_candidate.py --candidate runs/quality_candidate
        --previous runs/vad0_paired/submission_manifest_vad0.json
        --pdf <경로>.pdf --out runs/quality_candidate/submission_manifest_quality.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SUBMISSION_ARM = "R1-VAD0-QUALITY"

#: 보존해야 하는 이전 제출본. 값이 달라지면 승격을 막는다.
ROLLBACK = {
    "submission_vad0_2026_09_07": (
        ROOT / "runs/vad0_paired/s1_shadow/report.hwpx",
        "4e10aaaba1d8a6e510c4749efc4a6e1bf5a5dbb5dba963403a84379bcd92ff90"),
    "submission_ready_2026_09_03": (
        ROOT / "runs/v3_paired/r1_v3/report.hwpx",
        "f874f643112704120cd3b043c3667b71ffd4f25105ca1fccf345b936d4e4a91d"),
}

NOT_CLAIMED = [
    "semantic entailment of the summaries is not automatically verified",
    "the abstention layer is not a verified hallucination detector",
    "the output quality gate judges the output language contract, "
    "not factual correctness",
    "GRD-004 remains P1 WAIVED",
    "v3 is not the repository default contract",
]


class PromotionError(RuntimeError):
    """승격 입력 계약 위반. 보정하지 않고 멈춘다."""


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rollback_intact() -> dict:
    """이전 제출본이 그대로인지 실제 파일에서 확인한다."""
    verdict = {}
    for name, (path, expected) in ROLLBACK.items():
        actual = sha256_file(path) if path.is_file() else None
        verdict[name] = actual
        verdict.setdefault("checks", {})[name] = {
            "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT)
                    else str(path),
            "expected": expected, "actual": actual, "match": actual == expected}
    verdict["intact"] = all(item["match"] for item in verdict["checks"].values())
    return verdict


def compose(candidate: dict, previous: dict) -> dict:
    """candidate + 직전 submission manifest를 합친다. 값을 새로 만들지 않는다."""
    if candidate.get("llm_rerun") is not False:
        raise PromotionError("candidate가 LLM 재실행을 주장한다 — 승격 대상이 아니다")
    if candidate["source_run_fingerprint"] != previous["fingerprint"]:
        raise PromotionError(
            "candidate의 source 지문이 직전 제출본과 다르다 — 다른 실행의 산출물이다")

    return {
        "submission_arm": SUBMISSION_ARM,
        "submission_contract": previous["submission_contract"],
        "prompt_hash": previous["prompt_hash"],
        "stt_evidence_policy": previous["stt_evidence_policy"],
        "stt_evidence_rule": previous["stt_evidence_rule"],
        "measurements_sha256": previous["measurements_sha256"],
        "output_quality_policy": candidate["quality_policy_version"],
        "output_quality_policy_hash": candidate["quality_policy_hash"],
        "presentation_group_window_sec": candidate[
            "presentation_group_window_sec"],
        "presentation_groups": candidate["presentation_groups"],
        "presentation_group_count": candidate["presentation_group_count"],
        "input": previous["input"],
        "fingerprint": previous["fingerprint"],
        "model_provenance": previous["model_provenance"],
        "generation": previous["generation"],
        "vad": previous["vad"],
        "stt_evidence": previous["stt_evidence"],
        "paired_result": previous["paired_result"],
        "source_content_hash": candidate["source_content_hash"],
        "canonical_partition_hash": candidate["canonical_partition_hash"],
        "canonical_episodes": candidate["canonical_episodes"],
        "presentation_eligible": candidate["presentation_eligible"],
        "quality_status_counts": candidate["quality_status_counts"],
        "excluded_summary_episodes": [
            {"episode_id": row["episode_id"],
             "reasons": list(row["exclusion_reasons"])}
            for row in candidate["quality_excluded"]],
        "unavailable_note": "%d episodes are not presented: %s" % (
            len(candidate["quality_excluded"]),
            ", ".join("%s (%s)" % (row["episode_id"],
                                   ", ".join(row["exclusion_reasons"]))
                      for row in candidate["quality_excluded"])),
        "renderer": previous["renderer"],
        "llm_rerun": False,
        "regenerated_by_rerun": False,
        "artifact": dict(candidate["artifact"]),
        "companions": previous["companions"],
        "default_contract_unchanged": True,
        "vad0_default_off": True,
        "supersedes": {
            "submission_arm": previous["submission_arm"],
            "hwpx": previous["artifact"]["hwpx"],
            "hwpx_sha256": previous["artifact"]["hwpx_sha256"],
            "presentation_eligible": previous["presentation_eligible"],
            "tag": "submission-vad0-2026-09-07",
            "role": "rollback artifact — 보존한다. 삭제·덮어쓰기 금지",
        },
        "not_claimed": list(NOT_CLAIMED),
    }


def verify_live(hwpx: Path, pdf: Path, expected_sha: str) -> dict:
    """그 정확한 파일에 대해 구조·한글·PDF를 다시 확인한다."""
    actual = sha256_file(hwpx)
    if actual != expected_sha:
        raise PromotionError("승격 대상 파일 해시가 manifest와 다르다: %s != %s"
                             % (actual, expected_sha))
    owpml = _module(ROOT / "scripts/v2_1_hwpx_owpml.py", "owpml_promote")
    failures = owpml.validate_package(hwpx)
    if failures:
        raise PromotionError("HWPX 구조 검증 실패: %r" % failures)
    submission = _module(ROOT / "scripts/v2_1_submission_manifest.py",
                         "submission_for_promote")
    hangul = submission.hangul_check(hwpx, pdf)
    return {"structural_validator": "PASS", "hangul": hangul,
            "hwpx_sha256_verified": actual}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True,
                        help="quality candidate run 디렉터리")
    parser.add_argument("--previous", required=True,
                        help="직전 submission manifest (rollback 대상)")
    parser.add_argument("--pdf", required=True, help="한글 PDF export 경로")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    candidate_dir = Path(args.candidate).resolve()
    candidate = json.loads(
        (candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
    previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))

    manifest = compose(candidate, previous)
    hwpx = candidate_dir / "S7/report.hwpx"
    manifest.update(verify_live(hwpx, Path(args.pdf).resolve(),
                                candidate["artifact"]["hwpx_sha256"]))

    rollback = rollback_intact()
    if not rollback["intact"]:
        raise PromotionError("이전 제출본이 변경됐다 — 승격을 멈춘다: %r"
                             % rollback["checks"])
    manifest["rollback_intact"] = rollback

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in (
        "submission_arm", "submission_contract", "stt_evidence_policy",
        "output_quality_policy", "presentation_group_window_sec",
        "presentation_eligible", "llm_rerun", "structural_validator",
        "hangul")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
