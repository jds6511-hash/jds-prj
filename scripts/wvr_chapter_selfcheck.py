"""SEMANTIC_CHAPTER_SHADOW_V1 self-check (GPU 없이 · 생성 전).

사전등록: `docs/preregistration/WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md`

동결 입력 해시 · 프롬프트 해시 · digest 무결성을 GPU를 쓰기 **전에** 확인한다.
불일치면 실패 종료하고 생성 단계로 넘어가지 않는다.

사용: `python scripts/wvr_chapter_selfcheck.py --runs runs/wvr_light_v1`
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_chapter_v1 as ch                                  # noqa: E402
import wvr_conservative_map_v1 as cmap                       # noqa: E402


class SelfCheckError(RuntimeError):
    """생성 전 계약 위반."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_map(runs: Path) -> dict:
    path = runs / ch.SOURCE_MAP_NAME
    if not path.is_file():
        raise SelfCheckError("SOURCE_MAP_HASH_MISMATCH: 입력 map이 없다")
    observed = sha256_file(path)
    if observed != ch.SOURCE_MAP_SHA256:
        raise SelfCheckError("SOURCE_MAP_HASH_MISMATCH: %s != %s"
                             % (observed, ch.SOURCE_MAP_SHA256))
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != cmap.SCHEMA:
        raise SelfCheckError("CONFIG_MISMATCH: map schema가 다르다")
    if document["lineage_summary"]["source_events_total"] \
            != ch.EXPECTED_SOURCE_EVENT_COUNT:
        raise SelfCheckError("CONFIG_MISMATCH: source event 수가 다르다")
    if len(document["regions"]) != ch.EXPECTED_REGION_COUNT:
        raise SelfCheckError("CONFIG_MISMATCH: region 수가 다르다")
    return document


def checks(runs: Path) -> dict:
    ch.assert_flags_closed()
    document = load_map(runs)
    prompt = ch.render_prompt(document)
    digest = ch.map_digest(document)
    events = cmap.all_members(document)
    return {
        "document": document,
        "prompt": prompt,
        "rows": {
            "source_map_hash_frozen":
                sha256_file(runs / ch.SOURCE_MAP_NAME) == ch.SOURCE_MAP_SHA256,
            "prompt_template_hash_frozen":
                ch.sha256_text(ch.CHAPTER_PROMPT_V1)
                == ch.PROMPT_TEMPLATE_SHA256,
            "rendered_prompt_hash_frozen":
                ch.sha256_text(prompt) == ch.RENDERED_PROMPT_SHA256,
            "digest_carries_every_region": all(
                "[REGION %s]" % row["region_id"] in digest
                for row in document["regions"]),
            "digest_marks_conflict_without_ranking":
                "do not choose" in digest
                and "observation set" in digest
                and "winner" not in digest.lower(),
            "digest_marks_unresolved_without_content":
                "no valid observation" in digest,
            "digest_has_no_event_ids": all(
                row["event_id"] not in digest for row in events),
            "instructions_have_no_expected_answer": all(
                phrase not in ch.CHAPTER_PROMPT_V1.lower() for phrase in
                ("food", "eat", "sew", "gift", "wrap", "cook", "garment",
                 "cloth")),
            "prompt_forbids_track_a":
                "STT" not in prompt and "caption" not in prompt,
            "runtime_frozen":
                ch.LLM_MODEL_ID == "Qwen/Qwen2.5-7B-Instruct"
                and ch.LLM_LOAD_4BIT is False
                and ch.LLM_DO_SAMPLE is False
                and ch.LLM_MAX_NEW_TOKENS == 4096
                and ch.GENERATION_ATTEMPTS == 1,
            "retry_closed": ch.RETRY_ALLOWED is False,
            "overview_closed": ch.OVERVIEW_GENERATION_ALLOWED is False
            and ch.REPORT_GENERATION_ALLOWED is False,
            "raw_not_yet_written": not (runs / "chapter_v1_raw.txt").is_file(),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="chapter self-check")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--write-prompt", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    result = checks(runs)
    rows = result["rows"]
    ok = all(rows.values())
    print("selfcheck=%s checks=%d/%d"
          % ("PASS" if ok else "FAIL",
             sum(1 for value in rows.values() if value), len(rows)))
    for name, value in rows.items():
        print("  check %-42s %s" % (name, value))
    print("prompt chars=%d sha256=%s"
          % (len(result["prompt"]), ch.sha256_text(result["prompt"])))
    if args.write_prompt and ok:
        (runs / "chapter_v1_prompt.txt").write_text(result["prompt"],
                                                    encoding="utf-8")
        print("wrote chapter_v1_prompt.txt")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
