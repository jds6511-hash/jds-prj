"""WVR_WHOLE_VIDEO_REPORT_V2 — 사용자-facing report cleanup 첫 실행."""
from __future__ import annotations

import gc
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import v2_1_hwpx_owpml as hwpx  # noqa: E402
import wvr_video_overview_preview_run as runtime_module  # noqa: E402
import wvr_whole_video_report_v1 as v1  # noqa: E402
import wvr_whole_video_report_v2 as v2  # noqa: E402

RUN_ROOT = ROOT / "runs" / "wvr_whole_video_report_v2"
V1_ROOT = ROOT / "runs" / "wvr_whole_video_report_v1"
OV_ROOT = ROOT / "runs" / "wvr_overview_synthesis_v2"
MERGE_ROOT = ROOT / "runs" / "wvr_whole_video_merge_v1"
M3_PATH = ROOT / "work_full" / "full_xekZO4n4QuE" / "segments.json"
RECORD = RUN_ROOT / "execution_record.json"

FROZEN_TEXT = (
    OV_ROOT / "overview_result.json",
    OV_ROOT / "canonical_flow.json",
    MERGE_ROOT / "whole_video_activity_timeline.json",
    MERGE_ROOT / "timeline_lineage.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha(root: Path) -> str:
    """상대 경로와 각 파일 hash로 디렉터리 전체의 결정적 digest를 만든다."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha(path)))
        digest.update(b"\n")
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def release_runtime(runtime) -> None:
    for name in ("model", "processor", "tokenizer"):
        if hasattr(runtime, name):
            delattr(runtime, name)
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


def source_state() -> dict:
    m3_present = M3_PATH.is_file()
    return {
        "frozen_text_sha256": {
            str(path.relative_to(ROOT)): v1.frozen_text_sha(path)
            for path in FROZEN_TEXT
        },
        "beta_v3_tree_sha256": tree_sha(V1_ROOT / "b2run"),
        "m3_stt_mounted": m3_present,
        "m3_stt_sha256": sha(M3_PATH) if m3_present else v1.M3_SEGMENTS_SHA256,
    }


def validate_user_body(text: str, overview: dict) -> dict:
    checks = {
        "short_overview_verbatim": overview["short_overview"].strip() in text,
        "detailed_overview_verbatim": overview["detailed_overview"].strip() in text,
        "beta_highlight_headings_absent": not re.search(
            r"(?m)^###\s+H0[1-9]\b", text),
        "beta_narrative_section_absent": "## β/v3 보조 구간 요약" not in text,
        "seg_identifier_absent": "seg#" not in text,
        "analysis_present": bool(re.search(r"(?ms)^## 분석\s+\S", text)),
        "conclusion_present": bool(re.search(r"(?ms)^## 결론\s+\S", text)),
        "logical_section_count_five": len(re.findall(r"(?m)^## ", text)) == 5,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def main() -> int:
    if RECORD.exists():
        raise RuntimeError("V2 execution record가 이미 있다 — retry하지 않는다")
    required = [*FROZEN_TEXT, V1_ROOT / "result.json", V1_ROOT / "b2run"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("frozen input missing: %r" % missing)

    before = source_state()
    overview = json.loads((OV_ROOT / "overview_result.json").read_text("utf-8"))
    flow = json.loads((OV_ROOT / "canonical_flow.json").read_text("utf-8"))
    timeline = json.loads(
        (MERGE_ROOT / "whole_video_activity_timeline.json").read_text("utf-8"))
    beta = json.loads((V1_ROOT / "result.json").read_text("utf-8"))["beta_v3"]
    if beta["eligible"] != 36 or beta["episodes"] != 41:
        raise RuntimeError("frozen β/v3 metrics가 reviewer 입력과 다르다")

    record = {
        "event": v2.EVENT,
        "status": "RUNNING",
        "protection_before": before,
        "analysis_inference_count": 0,
        "conclusion_inference_count": 0,
        "visual_inference_count": 0,
        "stt_inference_count": 0,
        "beta_v3_regeneration_count": 0,
        "retry_count": 0,
        "official_test": "UNTOUCHED",
        "m9": "NOT_INVOKED",
        "started_epoch": time.time(),
    }
    write_json(RECORD, record)
    runtime = None
    try:
        runtime = runtime_module.QwenRuntime()
        record["runtime"] = runtime.provenance()

        analysis_prompt = v2.analysis_prompt(flow, overview, timeline)
        write_text(RUN_ROOT / "analysis_prompt.txt", analysis_prompt)
        analysis_raw = runtime.synthesize(analysis_prompt)
        record["analysis_inference_count"] = 1
        record["analysis_metrics"] = runtime.metrics().get("synthesis")
        write_text(RUN_ROOT / "analysis_raw.txt", analysis_raw)
        write_json(RECORD, record)
        analysis = v2.clean_body(analysis_raw, "ANALYSIS")

        conclusion_prompt = v2.conclusion_prompt(overview, analysis)
        write_text(RUN_ROOT / "conclusion_prompt.txt", conclusion_prompt)
        conclusion_raw = runtime.synthesize(conclusion_prompt)
        record["conclusion_inference_count"] = 1
        record["conclusion_metrics"] = runtime.metrics().get("synthesis")
        write_text(RUN_ROOT / "conclusion_raw.txt", conclusion_raw)
        write_json(RECORD, record)
        conclusion = v2.clean_body(conclusion_raw, "CONCLUSION")
        release_runtime(runtime)
        runtime = None

        semantic_checks = v2.machine_checks(
            flow, overview, analysis, conclusion)
        final_text = v2.final_report_markdown(
            overview, analysis, conclusion, timeline, beta)
        body_checks = validate_user_body(final_text, overview)
        write_text(RUN_ROOT / "final_report.md", final_text)

        final_hwpx = RUN_ROOT / "final_report.hwpx"
        hwpx.write_hwpx(v1.report_lines(final_text), final_hwpx,
                         "영상 전체 보고서")
        structural_errors = hwpx.validate_package(final_hwpx)
        expected_lines = [line for line in v1.report_lines(final_text) if line]
        semantic_match = hwpx.semantic_text(final_hwpx) == expected_lines

        after = source_state()
        protection = {
            "overview_hash_unchanged": (
                before["frozen_text_sha256"][
                    "runs/wvr_overview_synthesis_v2/overview_result.json"]
                == after["frozen_text_sha256"][
                    "runs/wvr_overview_synthesis_v2/overview_result.json"]),
            "canonical_flow_hash_unchanged": (
                before["frozen_text_sha256"][
                    "runs/wvr_overview_synthesis_v2/canonical_flow.json"]
                == after["frozen_text_sha256"][
                    "runs/wvr_overview_synthesis_v2/canonical_flow.json"]),
            "timeline_hash_unchanged": (
                before["frozen_text_sha256"][
                    "runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json"]
                == after["frozen_text_sha256"][
                    "runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json"]),
            "lineage_hash_unchanged": (
                before["frozen_text_sha256"][
                    "runs/wvr_whole_video_merge_v1/timeline_lineage.json"]
                == after["frozen_text_sha256"][
                    "runs/wvr_whole_video_merge_v1/timeline_lineage.json"]),
            "beta_v3_tree_hash_unchanged": (
                before["beta_v3_tree_sha256"] == after["beta_v3_tree_sha256"]),
            "m3_stt_hash_unchanged": (
                before["m3_stt_sha256"] == after["m3_stt_sha256"]),
        }
        protection["all_pass"] = all(protection.values())

        result = {
            "event": v2.EVENT,
            "status": "EXECUTED / REVIEW_PENDING",
            "analysis": analysis,
            "conclusion": conclusion,
            "short_overview": overview["short_overview"],
            "detailed_overview": overview["detailed_overview"],
            "semantic_checks": semantic_checks,
            "user_body_checks": body_checks,
            "protection": protection,
            "source_state": after,
            "beta_v3": beta,
            "hwpx": {
                "generated": True,
                "structural_errors": structural_errors,
                "semantic_text_match": semantic_match,
                "gui_layout": "GUI_LAYOUT_UNVERIFIED",
                "bytes": final_hwpx.stat().st_size,
            },
            "artifact_sha256": {
                "final_report_md": sha(RUN_ROOT / "final_report.md"),
                "final_report_hwpx": sha(final_hwpx),
                "analysis_raw": sha(RUN_ROOT / "analysis_raw.txt"),
                "conclusion_raw": sha(RUN_ROOT / "conclusion_raw.txt"),
            },
        }
        write_json(RUN_ROOT / "result.json", result)
        record["status"] = result["status"]
        record["semantic_checks"] = semantic_checks
        record["user_body_checks"] = body_checks
        record["protection_after"] = after
        record["protection"] = protection
        record["hwpx"] = result["hwpx"]
        record["elapsed_sec"] = round(time.time() - record["started_epoch"], 3)
        write_json(RECORD, record)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:  # noqa: BLE001
        if runtime is not None:
            release_runtime(runtime)
        record["status"] = "FAILED / REVIEW_REQUESTED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["elapsed_sec"] = round(time.time() - record["started_epoch"], 3)
        write_json(RECORD, record)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
