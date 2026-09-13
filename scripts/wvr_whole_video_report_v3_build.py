"""Build the no-inference WVR V3 usability report from frozen sources."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import v2_1_hwpx_owpml as hwpx  # noqa: E402
import wvr_whole_video_report_v1 as v1  # noqa: E402
import wvr_whole_video_report_v3 as v3  # noqa: E402

OUT = ROOT / "runs" / "wvr_whole_video_report_v3"
TIMELINE = ROOT / "runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json"
LINEAGE = ROOT / "runs/wvr_whole_video_merge_v1/timeline_lineage.json"
FLOW = ROOT / "runs/wvr_overview_synthesis_v2/canonical_flow.json"
OVERVIEW = ROOT / "runs/wvr_overview_synthesis_v2/overview_result.json"
V2_RESULT = ROOT / "runs/wvr_whole_video_report_v2/result.json"
V2_REPORT = ROOT / "runs/wvr_whole_video_report_v2/final_report.md"
M3 = ROOT / "work_full/full_xekZO4n4QuE/segments.json"
RULE = ROOT / "docs/probes/WVR_WHOLE_VIDEO_REPORT_V3_USABILITY_SELECTION_RULE_2026-09-13.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()


def main() -> int:
    if OUT.exists():
        raise v3.V3Error(f"output already exists; no rerun allowed: {OUT}")
    inputs = [TIMELINE, LINEAGE, FLOW, OVERVIEW, V2_RESULT, V2_REPORT, M3, RULE]
    missing = [str(p) for p in inputs if not p.is_file()]
    if missing:
        raise v3.V3Error(f"frozen input missing: {missing}")
    before = {str(p.relative_to(ROOT)).replace("\\", "/"): v3.sha256(p) for p in inputs}
    timeline, flow, overview, baseline = load(TIMELINE), load(FLOW), load(OVERVIEW), load(V2_RESULT)
    allowed = set(flow["activity_phase_occurrences"])
    blocks = v3.build_blocks(timeline["entries"], allowed,
                             float(timeline["observed_end_sec"]))
    selected = v3.select_highlights(blocks, flow["final_phase_span"],
                                    float(timeline["observed_end_sec"]))
    highlights, highlight_lineage = v3.materialize(selected)
    one_line = ("이 영상은 음식 준비 및 조리와 식사를 비롯해 구매 또는 둘러보기, 이동, "
                "외출 준비, 포장 작업, 의류 작업 및 수선이 시간에 따라 전환되는 과정을 담고 있다.")
    report = v3.render_report(baseline, one_line, highlights)
    appendix = v3.render_appendix(before, baseline, git_head(), len(blocks), len(highlights))

    OUT.mkdir(parents=True)
    (OUT / "final_report_v3.md").write_text(report, "utf-8")
    (OUT / "final_report_v3_technical_appendix.md").write_text(appendix, "utf-8")
    (OUT / "highlights.json").write_text(v3.json_text(highlights), "utf-8")
    (OUT / "highlight_lineage.json").write_text(v3.json_text({
        "event": v3.EVENT, "selection_rule": str(RULE.relative_to(ROOT)).replace("\\", "/"),
        "items": highlight_lineage,
    }), "utf-8")
    rendered = OUT / "final_report_v3.hwpx"
    hwpx.write_hwpx(v1.report_lines(report), rendered, "영상 전체 보고서")
    package_errors = hwpx.validate_package(rendered)
    semantic_match = hwpx.semantic_text(rendered) == [x for x in v1.report_lines(report) if x.strip()]

    after = {str(p.relative_to(ROOT)).replace("\\", "/"): v3.sha256(p) for p in inputs}
    times = [(h["start_sec"], h["end_sec"]) for h in highlights]
    activity_vocabulary = set().union(*(set(h["activities"]) for h in highlights))
    exposed = re.findall(r"\b(?:seg#\d+|[CS]\d{2}|H\d{2})\b", report)
    checks = {
        "highlight_count_5_to_8": 5 <= len(highlights) <= 8,
        "timestamps_monotonic": times == sorted(times),
        "highlight_overlap_zero": all(a[1] <= b[0] for a, b in zip(times, times[1:])),
        "lineage_completeness": all(x["source_timeline_entry_ids"] and x["sources"] for x in highlight_lineage),
        "early_middle_late_coverage": min(h["start_sec"] for h in highlights) < 808 and any(808 <= h["start_sec"] < 1616 for h in highlights) and max(h["end_sec"] for h in highlights) > 1616,
        "unknown_activity_zero": not (activity_vocabulary - allowed),
        "internal_identifier_exposure_zero": not exposed,
        "context_intent_overclaim_zero": not any(x in report for x in ["의도", "감정", "생활 습관", "시장 방문", "여행 계획"]),
        "final_phase_consistency": highlights[-1]["activities"] == flow["final_phase_activities"] and highlights[-1]["start_sec"] == flow["final_phase_span"][0] and highlights[-1]["end_sec"] == flow["final_phase_span"][1],
        "frozen_overview_verbatim": baseline["short_overview"] in report and baseline["detailed_overview"] in report,
        "frozen_analysis_verbatim": baseline["analysis"] in report,
        "frozen_conclusion_verbatim": baseline["conclusion"] in report,
        "technical_metadata_moved": "OUTPUT_LANGUAGE_DRIFT" not in report and "eligible 36/41" not in report and "0c351dd" not in report,
        "source_hashes_unchanged": before == after,
        "hwpx_structural_errors_zero": not package_errors,
        "hwpx_semantic_text_match": semantic_match,
    }
    result = {
        "event": v3.EVENT, "status": "EXECUTED / REVIEW_PENDING",
        "one_line_summary": one_line, "highlights": highlights,
        "validation": checks, "all_checks_pass": all(checks.values()),
        "inference": {"visual": 0, "stt": 0, "beta_v3_regeneration": 0,
                      "text_generation": 0},
        "hwpx": {"generated": rendered.is_file(), "structural_errors": package_errors,
                 "semantic_text_match": semantic_match,
                 "gui_layout": "GUI_LAYOUT_UNVERIFIED"},
        "frozen_source_sha256": before,
        "artifact_sha256": {},
    }
    for name in ["final_report_v3.md", "final_report_v3.hwpx",
                 "final_report_v3_technical_appendix.md", "highlights.json",
                 "highlight_lineage.json"]:
        result["artifact_sha256"][name] = v3.sha256(OUT / name)
    (OUT / "result.json").write_text(v3.json_text(result), "utf-8")
    record = {"event": v3.EVENT, "status": result["status"],
              "selection_rule_commit": git_head(), "inference": result["inference"],
              "retry_count": 0, "official_test": "UNTOUCHED", "m9": "NOT_INVOKED",
              "frozen_source_sha256_before": before,
              "frozen_source_sha256_after": after,
              "validation": checks, "hwpx": result["hwpx"]}
    (OUT / "execution_record.json").write_text(v3.json_text(record), "utf-8")
    print(v3.json_text(result), end="")
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
