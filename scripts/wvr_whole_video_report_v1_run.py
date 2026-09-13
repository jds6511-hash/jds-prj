"""WVR_WHOLE_VIDEO_REPORT_V1 — Analysis/Conclusion + β/v3 + 최종 HWPX.

실행 전 `scripts/wvr_whole_video_report_v1_build.py`의 gate PASS가 필요하다.
Overview branch는 읽기만 하며, 각 생성 단계는 첫 호출 한 번만 수행한다.
"""
from __future__ import annotations

import gc
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import v2_1_hwpx_owpml as hwpx  # noqa: E402
import wvr_overview_synthesis_v2 as sv  # noqa: E402
import wvr_video_overview_preview_run as v1run  # noqa: E402
import wvr_whole_video_report_v1 as wr  # noqa: E402

MERGE_ROOT = ROOT / "runs" / "wvr_whole_video_merge_v1"
OV_ROOT = ROOT / "runs" / "wvr_overview_synthesis_v2"
RUN_ROOT = ROOT / "runs" / "wvr_whole_video_report_v1"
CONFIG = ROOT / "configs" / "wvr_whole_video_beta_v3.yaml"
BETA_RUN = RUN_ROOT / "b2run"
RECORD_PATH = RUN_ROOT / "execution_record.json"

FROZEN_PATHS = (
    MERGE_ROOT / "whole_video_activity_timeline.json",
    MERGE_ROOT / "timeline_lineage.json",
    OV_ROOT / "canonical_flow.json",
    OV_ROOT / "overview_result.json",
)
ENGINE_REQUIRED_HEADINGS = (
    "## 개요",
    "## 주요 사건 및 내용",
    "## 핵심 내용 분석",
    "## 결론",
    "## 근거 및 생성 정보",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            check=True, capture_output=True, text=True)
    return result.stdout.strip()


def release_runtime(runtime) -> None:
    del runtime
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


def beta_command(head: str) -> list[str]:
    return [
        sys.executable, str(ROOT / "scripts" / "v2_1_b2_orchestrate.py"),
        "--segments", str(RUN_ROOT / "segments.json"),
        "--run-dir", str(BETA_RUN),
        "--config", str(CONFIG),
        "--video-id", "wvr_whole_video",
        "--run-id", "wvr-whole-video-v1",
        "--producer-version", head,
        "--model-id", "Qwen/Qwen2.5-7B-Instruct",
        "--contract", "v3",
        "--poll-gpu",
        "--clean",
    ]


def main() -> int:
    if RECORD_PATH.exists():
        raise RuntimeError(
            "execution_record.json이 이미 있다 — retry 없이 기존 기록을 검토한다")
    gate_path = RUN_ROOT / "report_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("gate") != "PASS":
        raise RuntimeError("report gate가 PASS가 아니다")

    frozen_before = {str(p.relative_to(ROOT)): sha(p) for p in FROZEN_PATHS}
    if frozen_before != gate["overview_branch_sha256"]:
        raise RuntimeError("gate 이후 Overview branch 해시가 달라졌다")

    head = git_head()
    timeline = json.loads(
        (MERGE_ROOT / "whole_video_activity_timeline.json").read_text("utf-8"))
    flow = json.loads((OV_ROOT / "canonical_flow.json").read_text("utf-8"))
    overview = json.loads((OV_ROOT / "overview_result.json").read_text("utf-8"))
    record = {
        "event": wr.EVENT,
        "prereg": wr.PREREG,
        "status": "RUNNING",
        "code_git_head": head,
        "overview_branch_sha256": frozen_before,
        "analysis_inference_count": 0,
        "conclusion_inference_count": 0,
        "beta_execution_count": 0,
        "visual_inference_count": 0,
        "stt_inference_count": 0,
        "timeline_regeneration_count": 0,
        "retry_count": 0,
        "started_epoch": time.time(),
    }
    write_json(RECORD_PATH, record)

    runtime = None
    try:
        # Analysis — 첫 호출 1회
        analysis_prompt = wr.analysis_prompt(flow, overview["detailed_overview"])
        write_text(RUN_ROOT / "analysis_prompt.txt", analysis_prompt)
        runtime = v1run.QwenRuntime()
        record["analysis_conclusion_runtime"] = runtime.provenance()
        analysis_raw = runtime.synthesize(analysis_prompt)
        record["analysis_inference_count"] = 1
        record["analysis_runtime_metrics"] = runtime.metrics().get("synthesis")
        write_text(RUN_ROOT / "analysis_raw.txt", analysis_raw)
        write_json(RECORD_PATH, record)
        analysis = sv.clean_body(analysis_raw, what="ANALYSIS")

        # Conclusion — 같은 runtime의 다음 첫 호출 1회
        conclusion_prompt = wr.conclusion_prompt(
            overview["short_overview"], overview["detailed_overview"], analysis)
        write_text(RUN_ROOT / "conclusion_prompt.txt", conclusion_prompt)
        conclusion_raw = runtime.synthesize(conclusion_prompt)
        record["conclusion_inference_count"] = 1
        record["conclusion_runtime_metrics"] = runtime.metrics().get("synthesis")
        write_text(RUN_ROOT / "conclusion_raw.txt", conclusion_raw)
        write_json(RECORD_PATH, record)
        conclusion = sv.clean_body(conclusion_raw, what="CONCLUSION")

        checks = wr.machine_checks(flow, overview, analysis, conclusion)
        write_json(RUN_ROOT / "machine_checks.json", {
            "event": wr.EVENT, "prereg": wr.PREREG, "checks": checks})

        release_runtime(runtime)
        runtime = None

        # β/v3 — 기존 engine을 수정하지 않고 격리 run에서 1회
        command = beta_command(head)
        write_json(RUN_ROOT / "beta_command.json", {"argv": command})
        beta_started = time.time()
        completed = subprocess.run(command, cwd=ROOT, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
        record["beta_execution_count"] = 1
        record["beta_exit_code"] = completed.returncode
        record["beta_wall_sec"] = round(time.time() - beta_started, 3)
        write_text(RUN_ROOT / "beta_stdout.txt", completed.stdout)
        write_text(RUN_ROOT / "beta_stderr.txt", completed.stderr)
        write_json(RECORD_PATH, record)
        if completed.returncode != 0:
            raise RuntimeError("β/v3 실행 실패(exit=%d)" % completed.returncode)

        canonical = json.loads(
            (BETA_RUN / "S5" / "aar_canonical.json").read_text("utf-8"))
        presentation = json.loads(
            (BETA_RUN / "S6" / "presentation.json").read_text("utf-8"))
        manifest = json.loads((BETA_RUN / "run_manifest.json").read_text("utf-8"))
        engine_report = (BETA_RUN / "S7" / "report.md").read_text("utf-8")
        support = wr.extract_beta_support(engine_report)
        beta = wr.beta_metrics(canonical, presentation, manifest)
        beta["section_completion"] = {
            heading: heading in engine_report for heading in ENGINE_REQUIRED_HEADINGS}

        stats = gate["stats"]
        final_markdown = wr.final_report_markdown(
            overview, analysis, conclusion, stats, beta_support=support)
        final_md_path = RUN_ROOT / "final_report.md"
        final_hwpx_path = RUN_ROOT / "final_report.hwpx"
        write_text(final_md_path, final_markdown)
        hwpx.write_hwpx(wr.report_lines(final_markdown), final_hwpx_path,
                         "영상 전체 보고서 — full_xekZO4n4QuE")
        hwpx_failures = hwpx.validate_package(final_hwpx_path)
        if hwpx_failures:
            raise RuntimeError("HWPX 구조 검증 실패: " + "; ".join(hwpx_failures))
        nonempty_markdown = [line for line in wr.report_lines(final_markdown) if line]
        if hwpx.semantic_text(final_hwpx_path) != nonempty_markdown:
            raise RuntimeError("HWPX semantic text가 final Markdown과 다르다")
        with zipfile.ZipFile(final_hwpx_path) as package:
            physical_sections = sum(
                1 for name in package.namelist()
                if name.startswith("Contents/section") and name.endswith(".xml"))

        frozen_after = {str(p.relative_to(ROOT)): sha(p) for p in FROZEN_PATHS}
        if frozen_after != frozen_before:
            raise RuntimeError("실행 중 Overview branch가 변경됐다")

        result = {
            "event": wr.EVENT,
            "status": "EXECUTED / REVIEW_PENDING",
            "short_overview": overview["short_overview"],
            "detailed_overview": overview["detailed_overview"],
            "analysis": analysis,
            "conclusion": conclusion,
            "machine_checks": checks,
            "beta_v3": beta,
            "hwpx": {
                "generated": True,
                "structurally_valid": True,
                "physical_section_count": physical_sections,
                "logical_section_count": sum(
                    1 for line in wr.report_lines(final_markdown)
                    if line.startswith("## ")),
                "bytes": final_hwpx_path.stat().st_size,
                "semantic_text_matches_markdown": True,
            },
            "artifacts": {
                "final_report_md": str(final_md_path.relative_to(ROOT)),
                "final_report_hwpx": str(final_hwpx_path.relative_to(ROOT)),
                "beta_engine_report_md": str(
                    (BETA_RUN / "S7" / "report.md").relative_to(ROOT)),
                "beta_engine_report_hwpx": str(
                    (BETA_RUN / "S7" / "report.hwpx").relative_to(ROOT)),
            },
            "artifact_sha256": {
                "final_report_md": sha(final_md_path),
                "final_report_hwpx": sha(final_hwpx_path),
            },
        }
        write_json(RUN_ROOT / "result.json", result)
        record["status"] = result["status"]
        record["machine_checks_all_pass"] = checks["all_pass"]
        record["beta_v3"] = beta
        record["hwpx"] = result["hwpx"]
        record["elapsed_sec"] = round(time.time() - record["started_epoch"], 3)
        write_json(RECORD_PATH, record)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:  # noqa: BLE001
        if runtime is not None:
            release_runtime(runtime)
        record["status"] = "FAILED / REVIEW_REQUESTED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["elapsed_sec"] = round(time.time() - record["started_epoch"], 3)
        write_json(RECORD_PATH, record)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
