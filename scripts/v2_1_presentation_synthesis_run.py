"""PRESENTATION_SYNTHESIS_V1 candidate 생성 — chapter · global 합성 (2026-09-08).

사전등록: `docs/finalization/PRESENTATION_SYNTHESIS_V1_ADDENDUM_2026-09-08.md`

```
확정 정본(S5)  →  group 합성 9회  →  global 합성 1회  →  report.md · report.hwpx
```

**episode 생성을 다시 하지 않는다.** 입력은 이미 확정된 episode summary이고, LLM
호출은 group·global 합성뿐이다(`episode_llm_rerun = false`).

**재시도하지 않는다.** 특정 group 결과가 마음에 들지 않아 다시 돌리는 경로가 없다 —
실패는 실패로 기록한다.

원본 run·제출 산출물에는 쓰지 않는다.

사용 (서버):
    python scripts/v2_1_presentation_synthesis_run.py
        --canonical runs/vad0_paired/s1_shadow/S5/aar_canonical.json
        --quality-candidate runs/quality_candidate
        --out-dir runs/presentation_synthesis_v1
        --model-id Qwen/Qwen2.5-7B-Instruct
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_highlight import HighlightSpec, build_highlights      # noqa: E402
from v2_1_lineage import build_lineage                          # noqa: E402
from v2_1_output_quality import (                               # noqa: E402
    QUALITY_POLICY_VERSION,
)
from v2_1_presentation import (                                 # noqa: E402
    PRESENTATION_GROUP_WINDOW_SEC,
    build_presentation,
    presentation_groups,
    validate_presentation,
)
from v2_1_presentation_input import presentation_input          # noqa: E402
from v2_1_presentation_synthesis import (                       # noqa: E402
    GLOBAL_CONTRACT_VERSION,
    GROUP_CONTRACT_VERSION,
    build_global_prompt,
    build_group_prompt,
    global_prompt_hash,
    group_inputs,
    group_prompt_hash,
    parse_global,
    parse_group,
    validate_global,
    validate_group,
)
from v2_1_render import render_markdown                         # noqa: E402
from v2_1_render_hwpx import write_hwpx                         # noqa: E402
from v2_1_run import Manifest                                   # noqa: E402
from v2_1_synthesis import build_synthesis                      # noqa: E402

#: 여기에 쓰면 안 되는 경로. 제출·rollback 산출물을 보호한다.
PROTECTED = ("runs/vad0_paired", "runs/quality_candidate", "runs/v3_paired",
             "work_full", "work_canary")


class RunError(RuntimeError):
    """합성 실행 계약 위반. 보정하지 않고 멈춘다."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_revision() -> str:
    result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def assert_writable(out_dir: Path) -> None:
    """제출·원본 경로에 쓰지 못하게 막는다."""
    resolved = out_dir.resolve()
    for protected in PROTECTED:
        candidate = (ROOT / protected).resolve()
        if resolved == candidate or candidate in resolved.parents:
            raise RunError("보호된 경로에 쓸 수 없다: %s" % resolved)
    return None


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator(model_id: str, max_new_tokens: int):
    """모델을 올린다. episode 생성 경로를 부르지 않는다."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.bfloat16, device_map="auto")
    model.eval()

    provenance = {
        "model_id": model_id,
        "resolved_revision": str(getattr(model.config, "_commit_hash",
                                         "unavailable")),
        "model_local_path": str(getattr(model.config, "_name_or_path",
                                        "unavailable")),
        "torch_dtype": str(getattr(model, "dtype", "unavailable")),
        "do_sample": False,
        "max_new_tokens": max_new_tokens,
    }

    def generate(prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        output = model.generate(**inputs, do_sample=False,
                                max_new_tokens=max_new_tokens)
        return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True)

    return generate, provenance


def synthesize(document: dict, generate, out_dir: Path) -> dict:
    """group 합성 → global 합성. 각 group은 **한 번만** 부른다."""
    presented = presentation_input(document)
    groups = presentation_groups(presented)
    inputs = group_inputs(presented, groups)

    (out_dir / "group_raw").mkdir(parents=True, exist_ok=True)
    (out_dir / "group_parsed").mkdir(parents=True, exist_ok=True)
    (out_dir / "global_raw").mkdir(parents=True, exist_ok=True)
    (out_dir / "global_parsed").mkdir(parents=True, exist_ok=True)

    chapters, group_calls = [], 0
    for item in inputs:
        prompt = build_group_prompt(item)
        raw = generate(prompt)                       # 호출은 group당 1회다
        group_calls += 1
        (out_dir / "group_raw" / ("%s.txt" % item.group_id)).write_text(
            raw, encoding="utf-8")
        chapter = parse_group(raw, item)
        failures = validate_group(chapter, item)
        payload = chapter.as_dict()
        payload["validation_failures"] = failures
        payload["input"] = {
            "member_episode_refs": list(item.member_episode_refs),
            "eligible_episode_refs": list(item.eligible_episode_refs),
            "excluded": [{"episode_id": ref, "reasons": list(reasons)}
                         for ref, reasons in item.excluded],
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        }
        (out_dir / "group_parsed" / ("%s.json" % item.group_id)).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        chapters.append(chapter)

    global_prompt = build_global_prompt(chapters)
    global_raw = generate(global_prompt)             # global은 1회다
    (out_dir / "global_raw/global.txt").write_text(global_raw, encoding="utf-8")
    global_result = parse_global(global_raw, chapters)
    global_payload = global_result.as_dict()
    global_payload["validation_failures"] = validate_global(global_result,
                                                            chapters)
    global_payload["prompt_sha256"] = hashlib.sha256(
        global_prompt.encode("utf-8")).hexdigest()
    (out_dir / "global_parsed/global.json").write_text(
        json.dumps(global_payload, ensure_ascii=False, indent=1),
        encoding="utf-8")

    return {"presented": presented, "groups": groups, "inputs": inputs,
            "chapters": chapters, "global": global_result,
            "group_calls": group_calls, "global_calls": 1}


def render(document: dict, state: dict, out_dir: Path, manifest: Manifest) -> dict:
    """두 출력을 같은 의미 계층에서 만든다."""
    presented = state["presented"]
    highlights = build_highlights(
        presented, [HighlightSpec(group) for group in state["groups"]])
    records = build_presentation(presented, highlights)
    legacy = build_synthesis(presented, build_lineage(presented, highlights))
    failures = validate_presentation(records, presented)
    if failures:
        raise RunError("표현 객체 검증 실패: %r" % failures)

    (out_dir / "report.md").write_text(
        render_markdown(manifest, records, legacy, chapters=state["chapters"],
                        global_synthesis=state["global"]), encoding="utf-8")
    write_hwpx(out_dir / "report.hwpx", manifest, records, legacy,
               chapters=state["chapters"], global_synthesis=state["global"])

    owpml = _module(ROOT / "scripts/v2_1_hwpx_owpml.py", "owpml_synthesis")
    package_failures = owpml.validate_package(out_dir / "report.hwpx")
    if package_failures:
        raise RunError("HWPX 구조 검증 실패: %r" % package_failures)
    return {"structural_validator": "PASS"}


def diagnostics(state: dict, out_dir: Path) -> dict:
    """압축 진단. **threshold가 아니다** — 첫 버전에서는 관찰값이다(addendum §12)."""
    episode_chars = sum(len(summary) for item in state["inputs"]
                        for summary in item.summaries)
    chapter_chars = sum(len(sentence.text) for chapter in state["chapters"]
                        for sentence in chapter.summary_sentences)
    overview_chars = sum(len(item.text)
                         for item in state["global"].overview_sentences)
    report = (out_dir / "report.md").read_text(encoding="utf-8")
    reprints = sum(1 for item in state["inputs"] for summary in item.summaries
                   if summary in report)
    sentences = [sentence.text for chapter in state["chapters"]
                 for sentence in chapter.summary_sentences]
    return {
        "episode_summary_chars": episode_chars,
        "chapter_summary_chars": chapter_chars,
        "overview_chars": overview_chars,
        "report_chars": len(report),
        "episode_summary_reprints": reprints,
        "group_compression_ratio": (round(chapter_chars / episode_chars, 4)
                                    if episode_chars else None),
        "global_compression_ratio": (round(overview_chars / chapter_chars, 4)
                                     if chapter_chars else None),
        "identical_chapter_sentences": len(sentences) - len(set(sentences)),
        "slash_concat_present": " / " in report,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", required=True,
                        help="확정 정본 aar_canonical.json (읽기 전용)")
    parser.add_argument("--quality-candidate", required=True,
                        help="현행 quality candidate 디렉터리 (읽기 전용 · provenance)")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    assert_writable(out_dir)
    canonical_path = Path(args.canonical).resolve()
    candidate_dir = Path(args.quality_candidate).resolve()
    document = json.loads(canonical_path.read_text(encoding="utf-8"))
    candidate = json.loads(
        (candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))

    generate, model_provenance = _generator(args.model_id, args.max_new_tokens)
    state = synthesize(document, generate, out_dir)

    manifest = Manifest(
        video_id=document["video_id"], run_id=document["run_id"],
        analysis_mode="report",
        config_hash=candidate["source_run_fingerprint"]["config_hash"][:16],
        code_git_head=code_revision()[:8])
    rendered = render(document, state, out_dir, manifest)

    payload = {
        "track": "PRESENTATION_SYNTHESIS_V1",
        "code_revision": code_revision(),
        "source_episode_content_hash": sha256_file(canonical_path),
        "source_quality_candidate_hash": candidate["artifact"]["hwpx_sha256"],
        "canonical_partition_hash": candidate["canonical_partition_hash"],
        "canonical_episodes": len(document["episodes"]),
        "presentation_group_window_sec": PRESENTATION_GROUP_WINDOW_SEC,
        "presentation_group_count": len(state["groups"]),
        "group_synthesis_contract_version": GROUP_CONTRACT_VERSION,
        "group_prompt_hash": group_prompt_hash(),
        "global_synthesis_contract_version": GLOBAL_CONTRACT_VERSION,
        "global_prompt_hash": global_prompt_hash(),
        "model_provenance": model_provenance,
        "episode_llm_rerun": False,
        "group_llm_call_count": state["group_calls"],
        "global_llm_call_count": state["global_calls"],
        "output_quality_policy": QUALITY_POLICY_VERSION,
        "chapters": [chapter.as_dict() for chapter in state["chapters"]],
        "global": state["global"].as_dict(),
        "excluded_summary_episodes": [
            {"group_id": item.group_id, "episode_id": ref,
             "reasons": list(reasons)}
            for item in state["inputs"] for ref, reasons in item.excluded],
        "diagnostics": diagnostics(state, out_dir),
        "artifact": {
            "md": str(out_dir / "report.md"),
            "md_sha256": sha256_file(out_dir / "report.md"),
            "hwpx": str(out_dir / "report.hwpx"),
            "hwpx_sha256": sha256_file(out_dir / "report.hwpx"),
            "hwpx_bytes": (out_dir / "report.hwpx").stat().st_size,
        },
        **rendered,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in (
        "presentation_group_count", "group_llm_call_count",
        "global_llm_call_count", "episode_llm_rerun", "diagnostics",
        "structural_validator")}, ensure_ascii=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
