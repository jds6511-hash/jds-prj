"""quality candidate 재렌더 — 확정된 S5 정본에 새 표현 계층만 다시 적용한다.

```
입력   <source_run>/S5/aar_canonical.json      확정 content artifact (그대로 읽는다)
출력   <out_dir>/S6/presentation.json · S7/report.hwpx · S7/report.md · manifest
```

**LLM을 부르지 않는다.** 요약 문장은 정본에 이미 있고, 이 스크립트가 바꾸는 것은
표현 계층뿐이다 — output quality interlock · 300초 grouping · 사유 표시.

원본 run에는 아무것도 쓰지 않는다. 기존 제출본은 rollback으로 남는다.

사용:
    python scripts/v2_1_quality_candidate.py --source-run runs/<arm>
        --out-dir runs/quality_candidate --pdf <경로>.pdf
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

from v2_1_highlight import HighlightSpec, build_highlights      # noqa: E402
from v2_1_lineage import build_lineage                          # noqa: E402
from v2_1_output_quality import (                               # noqa: E402
    QUALITY_POLICY_VERSION,
    evaluate_summary,
)
from v2_1_presentation import (                                 # noqa: E402
    PRESENTATION_GROUP_WINDOW_SEC,
    build_presentation,
    presentation_groups,
    serialize_presentation,
    validate_presentation,
)
from v2_1_presentation_input import (                           # noqa: E402
    exclusion_reasons,
    presentation_input,
    summary_eligible_for_presentation,
)
from v2_1_render import render_markdown                         # noqa: E402
from v2_1_run import Manifest                                   # noqa: E402
from v2_1_synthesis import build_synthesis, validate_synthesis   # noqa: E402


class CandidateError(RuntimeError):
    """재렌더 입력 계약 위반. 보정하지 않고 멈춘다."""


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def partition_hash(document: dict) -> str:
    """canonical episode 경계의 지문. 표현을 묶어도 이 값은 바뀌지 않아야 한다."""
    spans = [(episode["start_seg"], episode["end_seg"])
             for episode in document["episodes"]]
    return hashlib.sha256(
        json.dumps(spans, separators=(",", ":")).encode("utf-8")).hexdigest()


def policy_hash() -> str:
    """어느 품질 정책으로 걸렀는지 — 모듈 자체의 해시로 적는다."""
    return sha256_file(ROOT / "src/v2_1_output_quality.py")


def load_source(source_run: Path):
    """확정 정본과 그 run manifest를 읽는다. 없으면 만들지 않고 실패한다."""
    canonical = None
    for relative in ("S5/aar_canonical.json", "aar_canonical.json"):
        if (source_run / relative).is_file():
            canonical = source_run / relative
            break
    if canonical is None:
        raise CandidateError("%s: 확정 정본(aar_canonical.json)이 없다" % source_run)
    manifest_path = source_run / "run_manifest.json"
    if not manifest_path.is_file():
        raise CandidateError("%s: run_manifest.json이 없다" % source_run)
    return (json.loads(canonical.read_text(encoding="utf-8")),
            json.loads(manifest_path.read_text(encoding="utf-8")),
            canonical)


def quality_rows(presented) -> list:
    """episode별 품질 판정. 문장을 바꾸지 않고 판정만 적는다."""
    rows = []
    for episode in presented.episodes:
        verdict = evaluate_summary(episode.summary)
        rows.append({
            "episode_id": episode.episode_id,
            "content_status": episode.content_status,
            "quality_status": verdict.status,
            "quality_reasons": list(verdict.reasons),
            "eligible": summary_eligible_for_presentation(episode),
            "exclusion_reasons": list(exclusion_reasons(episode)),
            "longest_foreign_run": verdict.diagnostics.get("longest_foreign_run"),
        })
    return rows


def rerender(source_run: Path, out_dir: Path) -> dict:
    """표현 계층만 다시 만든다. 정본은 읽기만 한다."""
    document, source_manifest, canonical_path = load_source(source_run)
    presented = presentation_input(document)

    groups = presentation_groups(presented)
    highlights = build_highlights(presented, [HighlightSpec(g) for g in groups])
    lineage = build_lineage(presented, highlights)
    synthesis = build_synthesis(presented, lineage)
    records = build_presentation(presented, highlights)

    failures = (validate_presentation(records, presented)
                + validate_synthesis(synthesis, presented))
    if failures:
        raise CandidateError("표현 계층 검증 실패: %r" % failures)

    (out_dir / "S6").mkdir(parents=True, exist_ok=True)
    (out_dir / "S7").mkdir(parents=True, exist_ok=True)
    (out_dir / "S6/presentation.json").write_text(
        serialize_presentation(records), encoding="utf-8")

    manifest = Manifest(
        video_id=document["video_id"], run_id=document["run_id"],
        analysis_mode="report",
        config_hash=source_manifest["fingerprint"]["config_hash"][:16],
        code_git_head=source_manifest["fingerprint"]["code_revision"][:8])
    (out_dir / "S7/report.md").write_text(
        render_markdown(manifest, records, synthesis), encoding="utf-8")

    owpml = _module(ROOT / "scripts/v2_1_hwpx_owpml.py", "owpml_candidate")
    hwpx = out_dir / "S7/report.hwpx"
    owpml.render(document, hwpx, manifest=manifest, groups=groups)
    package_failures = owpml.validate_package(hwpx)
    if package_failures:
        raise CandidateError("HWPX 구조 검증 실패: %r" % package_failures)

    rows = quality_rows(presented)
    eligible = [row for row in rows if row["eligible"]]
    return {
        "source_run": str(source_run),
        "source_run_fingerprint": source_manifest["fingerprint"],
        "source_content_hash": sha256_file(canonical_path),
        "canonical_partition_hash": partition_hash(document),
        "canonical_episodes": len(document["episodes"]),
        "llm_rerun": False,
        "quality_policy_version": QUALITY_POLICY_VERSION,
        "quality_policy_hash": policy_hash(),
        "presentation_group_window_sec": PRESENTATION_GROUP_WINDOW_SEC,
        "presentation_groups": [list(group) for group in groups],
        "presentation_group_count": len(groups),
        "presentation_eligible": len(eligible),
        "quality_status_counts": _counts(row["quality_status"] for row in rows),
        "quality_excluded": [row for row in rows
                             if not row["eligible"] and row["exclusion_reasons"]],
        "episodes": rows,
        "artifact": {
            "hwpx": str(hwpx),
            "hwpx_sha256": sha256_file(hwpx),
            "hwpx_bytes": hwpx.stat().st_size,
            "md_sha256": sha256_file(out_dir / "S7/report.md"),
            "presentation_sha256": sha256_file(out_dir / "S6/presentation.json"),
        },
        "structural_validator": "PASS",
    }


def _counts(values) -> dict:
    result = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True,
                        help="확정 정본이 있는 run (읽기만 한다)")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--pdf", default=None,
                        help="한글 PDF export 경로 (주면 실물 확인까지 한다)")
    args = parser.parse_args(argv)

    source_run, out_dir = Path(args.source_run).resolve(), Path(args.out_dir)
    if out_dir.resolve() == source_run:
        raise CandidateError("출력 경로가 원본 run과 같다 — 덮어쓰지 않는다")
    report = rerender(source_run, out_dir)

    if args.pdf:
        submission = _module(ROOT / "scripts/v2_1_submission_manifest.py",
                             "submission_for_candidate")
        report["hangul"] = submission.hangul_check(
            Path(report["artifact"]["hwpx"]).resolve(), Path(args.pdf).resolve())

    (out_dir / "candidate_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "llm_rerun", "canonical_episodes", "canonical_partition_hash",
        "presentation_group_count", "presentation_eligible",
        "quality_status_counts", "quality_policy_version")},
        ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
