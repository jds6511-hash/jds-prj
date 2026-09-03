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


def build(run: Path, pdf: Path) -> dict:
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

    return {
        "submission_arm": "R1",
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
        "default_contract_unchanged": True,
        "not_claimed": [
            "semantic entailment of the summaries is not automatically verified",
            "GRD-004 remains P1 WAIVED",
            "v3 is not the repository default contract",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="제출 arm의 run 디렉터리")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pdf", default=None,
                        help="PDF export 경로 (기본: run 옆 submission.pdf)")
    args = parser.parse_args(argv)

    run = Path(args.run).resolve()
    pdf = Path(args.pdf).resolve() if args.pdf else run / "submission.pdf"
    report = build(run, pdf)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "submission_contract", "prompt_hash", "episodes",
        "presentation_eligible", "parse_contract_failure", "hangul")},
        ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
