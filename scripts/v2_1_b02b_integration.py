"""B-02b — 실제 모델 integration 검증 (Gate B).

```
목적    transformers + Qwen/Qwen2.5-7B-Instruct 가 B-02a에서 닫은 contract를
        그대로 통과하는지 확인한다
아님    모델 성능 평가 · 모델 비교 · prompt 평가 · generation tuning
```

세 경로만 태운다.

```
S3  caption-only    LLM-006
S4  ASR-only        LLM-007
S1  rich dialogue   LLM-010
```

각 호출은 `invoke → raw persist → parse → merge`를 지나고, 그 결과를 그대로
기록한다. **출력이 이상해도 프롬프트를 고치지 않는다** — 그 순간 prompt tuning
실험이 된다. 현재 contract에서의 integration 결과로 남긴다.

```
model load 실패     ENVIRONMENT_FAILURE   (PARSE_CONTRACT_FAILURE가 아니다)
OOM                 ENVIRONMENT_BLOCKED   4bit로 자동 전환하지 않는다
```

silent fallback을 만들지 않는 이유는 BPI-005와 같다 — 무엇이 실행됐는지 사후에
알 수 없게 된다.

실행:

```
HF_HOME=/ssd/$USER/cache python3 scripts/v2_1_b02b_integration.py \
    --commit <sha> --out runs/v2_1/b02b_integration.json
```
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# fixture는 tests/에 있다. Gate B synthetic fixture를 그대로 쓰기 위한 것이고,
# 이 스크립트는 새 데이터를 만들지 않는다.
sys.path.insert(0, str(ROOT / "tests"))

from v2_1_episode import build_episodes                      # noqa: E402
from v2_1_fixtures import scenario                           # noqa: E402
from v2_1_llm_adapter import GenerationConfig, invoke_episode  # noqa: E402
from v2_1_parse import SegmentRegistry                       # noqa: E402
from v2_1_prompt import build_episode_prompt                 # noqa: E402
from v2_1_raw_store import RawStore                          # noqa: E402
from v2_1_sanitation import classify_channel                 # noqa: E402
from v2_1_timeline import build_timeline                     # noqa: E402

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

#: (시나리오, 구간, 이 실행이 확인하는 acceptance id)
CASES = (
    ("S3", (0, 11), "LLM-006"),
    ("S4", (0, 11), "LLM-007"),
    ("S1", (6, 11), "LLM-010"),
)


def build_world(tmp_root: Path, name: str, span):
    s = scenario(name)
    store = RawStore(tmp_root / name, run_id="b02b", video_id=name)
    judged = {}
    for source_type, channel in (("asr", s.asr), ("vlm", s.caption), ("ocr", s.ocr)):
        if not channel:
            continue
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="fixture", producer_version="0", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    timeline = build_timeline(s.segments, judged)
    episode = build_episodes([span], s.segments, timeline=timeline)[0]
    bundle = build_episode_prompt(episode, timeline, store)
    return store, SegmentRegistry(s.segments), episode, bundle


def make_generator(config: GenerationConfig):
    """transformers를 여기서만 import한다. dry-run은 모델을 올리지 않는다."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(config.model_id)
    model = AutoModelForCausalLM.from_pretrained(
        config.model_id, torch_dtype=torch.bfloat16, device_map="auto"
    )

    def generate(prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(**inputs, do_sample=config.do_sample,
                                    max_new_tokens=config.max_new_tokens)
        return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True)

    return generate, model


def gpu_facts() -> dict:
    try:
        query = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30, check=True)
        return {"nvidia_smi": query.stdout.strip()}
    except Exception as exc:
        return {"nvidia_smi_error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True,
                        help="실행된 코드의 commit SHA (서버 HEAD와 다를 수 있다)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--work", default="/tmp/v2_1_b02b")
    parser.add_argument("--dry-run", action="store_true",
                        help="모델을 올리지 않고 배선만 확인한다")
    args = parser.parse_args()

    work = Path(args.work)
    report = {
        "purpose": "B-02b integration — contract 확인. 성능 평가가 아니다.",
        "commit": args.commit,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": MODEL_ID,
        "quantization": "none (llm_4bit=false)",
        "dry_run": bool(args.dry_run),
        "hf_home": os.environ.get("HF_HOME"),
        "gpu": gpu_facts(),
        "cases": [],
    }

    config = GenerationConfig(model_id=MODEL_ID)
    report["generation"] = config.as_dict()

    generate = None
    if not args.dry_run:
        try:
            generate, _ = make_generator(config)
        except Exception as exc:
            report["status"] = ("ENVIRONMENT_BLOCKED"
                                if "out of memory" in str(exc).lower()
                                else "ENVIRONMENT_FAILURE")
            report["error"] = str(exc)
            report["error_type"] = type(exc).__name__
            _write(args.out, report)
            print("model load failed: %s" % report["status"])
            return 1

    for name, span, acceptance_id in CASES:
        store, registry, episode, bundle = build_world(work, name, span)
        case = {
            "scenario": name,
            "span": list(span),
            "acceptance_id": acceptance_id,
            "episode_id": episode.episode_id,
            "prompt_version": bundle.prompt_version,
            "prompt_hash": bundle.prompt_hash,
            "prompt_chars": len(bundle.text),
            "claim_cites": list(bundle.claim_cites),
            "source": episode.source,
        }
        if args.dry_run:
            case["status"] = "DRY_RUN"
            report["cases"].append(case)
            continue

        invocation = invoke_episode(generate, episode, bundle, store, registry,
                                    config=config)
        result = invocation.result
        case.update({
            "content_status": result.content_status,
            "raw_ref": invocation.raw_ref,
            "raw_chars": (len(store.load("llm", span[0]).read_text())
                          if invocation.raw_ref else None),
            "summary": result.content.summary if result.content else None,
            "dialogue_note": (result.content.dialogue_note
                              if result.content else None),
            "stt_cites": (list(result.content.stt_cites)
                          if result.content else None),
            "ignored_fields": list(result.ignored_fields),
            "reason": result.reason,
            "error": result.error,
            "error_type": result.error_type,
            "episode_structure_intact": (
                result.episode.episode_id == episode.episode_id
                and result.episode.support_span == episode.support_span
            ),
        })
        report["cases"].append(case)
        print("%s %s -> %s" % (name, acceptance_id, case["content_status"]))

    report["status"] = "DRY_RUN" if args.dry_run else "COMPLETE"
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    _write(args.out, report)
    return 0


def _write(path, report):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("wrote %s" % target)


if __name__ == "__main__":
    raise SystemExit(main())
