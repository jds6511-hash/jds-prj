"""제출 profile manifest — 어느 계약의 산출물인지 artifact 옆에 남긴다.

수치를 손으로 적지 않는다. 실행 manifest·정본·HWPX에서 읽고, 한글 열림·PDF export는
**여기서 실제로 해 보고** 그 결과를 적는다. "PASS"를 인자로 받지 않는 이유가 그것이다.

한글 COM이 없으면 실패한다 — 조용히 `unknown`을 적지 않는다.

사용:
    python scripts/v2_1_submission_manifest.py --run runs/v3_paired/r1_v3 \\
        --out runs/v3_paired/submission_manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SubmissionCheckError(RuntimeError):
    """제출 확인을 못 했다. 못 한 것을 통과로 적지 않는다."""


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _first(run: Path, *relatives: str) -> Path:
    for relative in relatives:
        if (run / relative).is_file():
            return run / relative
    raise SubmissionCheckError("%s: %r 를 찾지 못했다" % (run, relatives))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hangul_check(hwpx: Path, pdf: Path) -> dict:
    """실물 한글에서 열고 PDF로 내보낸다. 못 하면 예외다."""
    try:
        import win32com.client as com
    except ImportError as error:                        # noqa: BLE001
        raise SubmissionCheckError(
            "pywin32가 없어 한글 열림을 확인할 수 없다") from error
    app = com.gencache.EnsureDispatch("HWPFrame.HwpObject")
    app.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    try:
        opened = bool(app.Open(str(hwpx), "HWPX", "forceopen:true"))
        text = app.GetTextFile("TEXT", "")
        exported = bool(app.SaveAs(str(pdf), "PDF", ""))
    finally:
        app.Quit()
    if not opened:
        raise SubmissionCheckError("한글이 %s 를 열지 못했다" % hwpx)
    return {
        "hancom_open": opened,
        "pdf_export": exported,
        "pdf_bytes": pdf.stat().st_size if pdf.is_file() else 0,
        "text_chars": len(text),
        "box_glyphs": {glyph: text.count(glyph) for glyph in "■┌│└"},
    }


def policy_label(policy: dict) -> str:
    """제출본이 어느 claim evidence 정책으로 만들어졌는지.

    `shadow_vad0`을 켠 run은 **어느 측정으로 abstain했는지**를 같이 적어야 한다.
    측정 provenance가 없으면 제출 provenance가 성립하지 않으므로 거부한다.
    """
    if not policy.get("shadow_vad0"):
        return "RAW_STT_ALL_VALID"
    if not policy.get("measurements_sha256"):
        raise SubmissionCheckError(
            "shadow_vad0 run인데 measurements_sha256이 없다 — "
            "어느 측정으로 abstain했는지 적을 수 없다")
    return "STT_VAD0"


def vad_provenance(vad_manifest: dict) -> dict:
    """Phase A manifest에서 그대로 옮긴다. 값을 손으로 적지 않는다."""
    vad = dict(vad_manifest["vad"])
    params = dict(vad["vad_params_resolved"])
    # implicit default(None)를 제출본에 남기지 않는다 — 실효값으로 적는다.
    if params.get("max_speech_duration_s") is None:
        params["max_speech_duration_s"] = vad["max_speech_duration_s"]
    return {
        "phase_a_code_revision": vad_manifest["code_revision"],
        "audio_sha256": vad_manifest["inputs"]["audio_sha256"],
        "stt_cache_sha256": vad_manifest["inputs"]["stt_cache_sha256"],
        "faster_whisper_version": vad["faster_whisper_version"],
        "vad_model": vad["vad_model"],
        "vad_model_sha256": vad["vad_model_sha256"],
        "vad_params_resolved": params,
        "sampling_rate": vad["sampling_rate"],
        "speech_chunks": vad["speech_chunks"],
    }


def assert_promoted_from_paired(paired: dict, fingerprint: dict) -> None:
    """제출 artifact가 **그 paired run의 것**인지 확인한다.

    다른 실행의 산출물에 paired 수치를 붙이면 provenance가 거짓이 된다. 이 검사가
    통과해야 "재실행하지 않고 승격했다"고 적을 수 있다.
    """
    if paired["arms"]["s1"]["fingerprint"] != fingerprint:
        raise SubmissionCheckError(
            "제출 run의 지문이 paired S1과 다르다 — 다른 실행의 산출물이다")


def evidence_totals(paired: dict) -> dict:
    """paired 결과에서 근거 수를 센다. abstention은 one-way여야 한다."""
    original = sum(row.get("eligible_s0") or 0 for row in paired["episodes"])
    selected = sum(row.get("eligible_s1") or 0 for row in paired["episodes"])
    if selected > original:
        raise SubmissionCheckError(
            "선택된 근거가 늘었다 (%d > %d) — abstention이 아니다"
            % (selected, original))
    return {"original_claim_evidence": original,
            "selected_claim_evidence": selected}


def build(run: Path, pdf: Path, transcripts: list[Path] | None = None,
          *, arm: str = "R1", vad_manifest: Path | None = None,
          paired_metrics: Path | None = None,
          supersedes: Path | None = None) -> dict:
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    document = json.loads(
        _first(run, "S5/aar_canonical.json", "aar_canonical.json").read_text(
            encoding="utf-8"))
    hwpx = _first(run, "S7/report.hwpx", "report.hwpx")
    ingest = json.loads(
        _first(run, "S0/ingest.json", "ingest.json").read_text(encoding="utf-8"))
    presentation = manifest["distributions"]["presentation"]
    statuses: dict[str, int] = {}
    for episode in document["episodes"]:
        key = episode["content_status"]
        statuses[key] = statuses.get(key, 0) + 1

    owpml = _load(ROOT / "scripts/v2_1_hwpx_owpml.py", "owpml_submission")
    failures = owpml.validate_package(hwpx)
    if failures:
        raise SubmissionCheckError("HWPX 구조 검증 실패: %r" % failures)

    policy = manifest.get("evidence_policy") or {}
    extra: dict = {"stt_evidence_policy": policy_label(policy)}
    if policy.get("shadow_vad0"):
        extra["stt_evidence_rule"] = policy["rule"]
        extra["measurements_sha256"] = policy["measurements_sha256"]
        extra["vad0_default_off"] = True
    if vad_manifest is not None:
        extra["vad"] = vad_provenance(
            json.loads(vad_manifest.read_text(encoding="utf-8")))
    if paired_metrics is not None:
        paired = json.loads(paired_metrics.read_text(encoding="utf-8"))
        gates = paired["gates"]
        assert_promoted_from_paired(paired, manifest["fingerprint"])
        extra["stt_evidence"] = evidence_totals(paired)
        extra["paired_result"] = {
            "metrics": str(paired_metrics.relative_to(ROOT))
                       if paired_metrics.is_relative_to(ROOT)
                       else str(paired_metrics),
            "metrics_sha256": sha256_file(paired_metrics),
            "commit": _commit_of(paired_metrics),
            "presentation_eligible": {
                "s0": gates["presentation_eligible_s0"],
                "s1": gates["presentation_eligible_s1"]},
            "parse_contract_failure": {"s0": gates["parse_failure_s0"],
                                       "s1": gates["parse_failure_s1"]},
            "non_regression_gates": {
                "presentation_s1_ge_s0": gates["presentation_non_regression"],
                "parse_s1_le_s0": gates["parse_non_regression"],
                "no_evidence_growth": gates["no_evidence_growth"]},
        }
        # 이 스크립트는 생성을 하지 않는다. 지문 일치까지 확인했으므로
        # 제출본은 paired 실행에서 나온 그 파일이다.
        extra["regenerated_by_rerun"] = False
    if supersedes is not None:
        previous = json.loads(supersedes.read_text(encoding="utf-8"))
        extra["supersedes"] = {
            "manifest": str(supersedes.relative_to(ROOT))
                        if supersedes.is_relative_to(ROOT) else str(supersedes),
            "submission_arm": previous["submission_arm"],
            "hwpx": previous["artifact"]["hwpx"],
            "hwpx_sha256": previous["artifact"]["hwpx_sha256"],
            "presentation_eligible": previous["presentation_eligible"],
            "parse_contract_failure": previous["parse_contract_failure"],
            "role": "rollback artifact — 보존한다. 삭제·덮어쓰기 금지",
        }

    return {
        "submission_arm": arm,
        "submission_contract": document["prompt"]["prompt_version"],
        "prompt_hash": document["prompt"]["prompt_hash"],
        "input": {
            "segments_sha256": ingest["source_segments_sha256"],
            "segment_count": ingest["segment_count"],
        },
        "fingerprint": manifest["fingerprint"],
        "model_provenance": manifest["model_provenance"],
        "generation": manifest["generation"],
        "episodes": len(document["episodes"]),
        "presentation_eligible": presentation["eligible"],
        "content_status": statuses,
        "parse_contract_failure": statuses.get("PARSE_CONTRACT_FAILURE", 0),
        "unavailable_note": "%d episodes unavailable due to parse-contract failure"
                            % statuses.get("PARSE_CONTRACT_FAILURE", 0),
        "renderer": "A2' pure-Python OWPML (scripts/v2_1_hwpx_owpml.py)",
        "structural_validator": "PASS",
        "artifact": {
            "hwpx": str(hwpx.relative_to(ROOT)) if hwpx.is_relative_to(ROOT)
                    else str(hwpx),
            "hwpx_sha256": sha256_file(hwpx),
            "hwpx_bytes": hwpx.stat().st_size,
        },
        "hangul": hangul_check(hwpx, pdf),
        # 전사문은 보고서와 별개 파일이다. 요약이 아니라 원문이므로 따로 가리킨다.
        "companions": [
            {"name": path.name, "kind": "stt_transcript",
             "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in (transcripts or [])
        ],
        "default_contract_unchanged": True,
        "not_claimed": [
            "semantic entailment of the summaries is not automatically verified",
            "GRD-004 remains P1 WAIVED",
            "v3 is not the repository default contract",
        ] + (["the abstention layer is not a verified hallucination detector",
              "the parse-failure change is a non-regression observation, "
              "not a demonstrated improvement"]
             if extra["stt_evidence_policy"] == "STT_VAD0" else []),
        **extra,
    }


def _commit_of(path: Path) -> str:
    """그 artifact를 기록한 commit. 손으로 적지 않는다."""
    import subprocess
    result = subprocess.run(
        ["git", "-C", str(ROOT), "log", "-1", "--format=%H", "--", str(path)],
        capture_output=True, text=True, check=True)
    commit = result.stdout.strip()
    if not commit:
        raise SubmissionCheckError("%s 를 기록한 commit이 없다" % path)
    return commit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="제출 arm의 run 디렉터리")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pdf", default=None,
                        help="PDF export 경로 (기본: run 옆 submission.pdf)")
    parser.add_argument("--transcript", action="append", default=[],
                        help="동반 전사문 txt (여러 번 줄 수 있다)")
    parser.add_argument("--arm", default="R1", help="제출 arm 이름표")
    parser.add_argument("--vad-manifest", default=None,
                        help="Phase A VAD manifest (VAD0 제출본일 때)")
    parser.add_argument("--paired-metrics", default=None,
                        help="Tier 2 paired 결과 (근거 수·비퇴행 게이트 출처)")
    parser.add_argument("--supersedes", default=None,
                        help="이 제출본이 대체하는 이전 manifest (rollback)")
    args = parser.parse_args(argv)

    run = Path(args.run).resolve()
    pdf = Path(args.pdf).resolve() if args.pdf else run / "submission.pdf"
    transcripts = [Path(item).resolve() for item in args.transcript]
    for path in transcripts:
        if not path.is_file():
            raise SubmissionCheckError("전사문이 없다: %s" % path)
    optional = {name: Path(value).resolve() if value else None
                for name, value in (("vad_manifest", args.vad_manifest),
                                    ("paired_metrics", args.paired_metrics),
                                    ("supersedes", args.supersedes))}
    for name, path in optional.items():
        if path is not None and not path.is_file():
            raise SubmissionCheckError("%s 가 없다: %s" % (name, path))
    report = build(run, pdf, transcripts, arm=args.arm, **optional)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "submission_arm", "submission_contract", "stt_evidence_policy",
        "prompt_hash", "episodes", "presentation_eligible",
        "parse_contract_failure", "hangul")},
        ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
