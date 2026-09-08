"""quality candidate 재렌더 — S5 정본을 그대로 쓰고 표현 계층만 다시 만든다.

```
LLM 재실행        금지 (llm_rerun = false)
canonical         무변경 (partition hash 대조)
기존 제출본        READ ONLY
```
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/v2_1_quality_candidate.py"
SOURCE_RUN = ROOT / "runs/vad0_paired/s1_shadow"


def _load():
    spec = importlib.util.spec_from_file_location("quality_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["quality_candidate"] = module
    spec.loader.exec_module(module)
    return module


candidate = _load()


def _canonical() -> dict:
    return json.loads((SOURCE_RUN / "S5/aar_canonical.json").read_text(
        encoding="utf-8"))


# ── provenance 규칙 ──────────────────────────────────────────────────────
def test_the_partition_hash_is_derived_from_the_canonical_spans():
    document = _canonical()
    spans = [(e["start_seg"], e["end_seg"]) for e in document["episodes"]]
    expected = hashlib.sha256(
        json.dumps(spans, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert candidate.partition_hash(document) == expected


def test_a_changed_partition_is_a_different_hash():
    document = _canonical()
    before = candidate.partition_hash(document)
    document["episodes"][0]["end_seg"] += 1
    assert candidate.partition_hash(document) != before


def test_the_policy_hash_is_the_quality_module_itself():
    digest = hashlib.sha256(
        (ROOT / "src/v2_1_output_quality.py").read_bytes()).hexdigest()
    assert candidate.policy_hash() == digest


def test_the_script_never_generates():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("v2_1_llm_adapter", "AutoModel", "torch",
                      "build_episode_prompt", "s2_raw"):
        assert forbidden not in source


def test_the_script_does_not_write_into_the_source_run():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "vad0_paired" not in source          # 경로를 코드에 박지 않는다
    assert "read_text" in source


def test_a_source_run_without_canonical_content_is_refused(tmp_path):
    with pytest.raises(candidate.CandidateError):
        candidate.load_source(tmp_path)
