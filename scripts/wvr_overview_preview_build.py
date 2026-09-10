"""Parse saved WVR_OVERVIEW_PREVIEW_V1 raw and build the preview packet."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_overview_preview_v1 as ov  # noqa: E402


class BuildError(RuntimeError):
    pass


def _write_text(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def packet_markdown(result: dict) -> str:
    short_text = "\n".join(row["text"] for row in result["short_overview"])
    detailed_text = "\n\n".join(row["text"] for row in result["detailed_overview"])
    return ("SHORT OVERVIEW\n\n%s\n\nDETAILED OVERVIEW\n\n%s\n\n"
            "TECHNICAL NOTES\n\n"
            "- inference count: 1\n"
            "- input: reviewer-PASS Conservative Event Map (11 regions)\n"
            "- unresolved handling: R01 NO_OBSERVATION, 생성 내용 없음\n"
            "- conflict handling: 익명 Observation Set A/B, 공통 broad activity만 허용\n"
            "- raw saved: yes\n" % (short_text, detailed_text))


def build(runs: Path) -> dict:
    runs = Path(runs)
    source_path = runs / ov.SOURCE_MAP_NAME
    if ov.sha256_file(source_path) != ov.SOURCE_MAP_SHA256:
        raise BuildError("SOURCE_MAP_HASH_MISMATCH")
    record = json.loads((runs / ov.RECORD_NAME).read_text(encoding="utf-8"))
    if record.get("inference_count") != 1 or record.get("parsed_here") is not False:
        raise BuildError("EXECUTION_RECORD_MISMATCH")
    if ov.sha256_file(runs / ov.PROMPT_NAME) != record.get("prompt_sha256"):
        raise BuildError("PROMPT_HASH_MISMATCH")
    if ov.sha256_file(runs / ov.RAW_NAME) != record.get("raw_sha256"):
        raise BuildError("RAW_HASH_MISMATCH")
    document = json.loads(source_path.read_text(encoding="utf-8"))
    generation_input = ov.build_generation_input(document)
    if (runs / ov.PROMPT_NAME).read_text(encoding="utf-8") != \
            ov.render_prompt(generation_input):
        raise BuildError("PROMPT_CONTENT_MISMATCH")
    result = ov.parse_and_validate(
        (runs / ov.RAW_NAME).read_text(encoding="utf-8"), generation_input)
    _write_text(runs / ov.RESULT_NAME, ov.canonical(result) + "\n")
    _write_text(runs / ov.PACKET_NAME, packet_markdown(result))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)
    result = build(Path(args.runs))
    print("short_sentences=%d detailed_paragraphs=%d claim_trace=%d" %
          (len(result["short_overview"]), len(result["detailed_overview"]),
           len(result["claim_trace"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
