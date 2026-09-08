"""PRESENTATION_SYNTHESIS_V1 실행 계약 (2026-09-08 · PSY-015 · 016).

```
LLM 호출   group당 1회 + global 1회        episode 재생성 없음
쓰기       격리 candidate 경로만            제출·원본은 보호
재시도     없다                            실패는 실패로 기록
```

GPU 없이 잰다 — `generate`는 fixture 콜러블이다.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/v2_1_presentation_synthesis_run.py"


def _load():
    spec = importlib.util.spec_from_file_location("presentation_synthesis_run",
                                                  SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["presentation_synthesis_run"] = module
    spec.loader.exec_module(module)
    return module


runner = _load()


def _document(count=15):
    episodes = []
    for index in range(1, count + 1):
        start, end = (index - 1) * 12, (index - 1) * 12 + 11
        episodes.append({
            "episode_id": "EP%02d" % index,
            "start_seg": start, "end_seg": end,
            "start_sec": (index - 1) * 60.0, "end_sec": index * 60.0,
            "support_span": [start, end],
            "anchor_cites": [], "source": "stt",
            "content_status": "VALID_PARSE",
            "summary": "구간 %d에서 재료를 다룬다." % index,
            "dialogue_note": None, "provenance": ["m3_generate"],
            "grounding_status": "NOT_APPLICABLE", "summary_mode":
            "MODEL_ABSTRACTIVE", "grounding_reasons": [],
        })
    return {"schema": "aar_canonical_v2_1", "video_id": "PS",
            "run_id": "run-psy", "segment_count": count * 12,
            "episodes": episodes, "quality_notes": {},
            "boundary": {"provider_name": "fixed_window_v1"},
            "prompt": {"prompt_version": "episode_content_v3_summary_only",
                       "prompt_hash": "0" * 64}}


class _Recorder:
    """호출을 세는 생성기. 같은 프롬프트를 두 번 받으면 드러난다."""

    def __init__(self):
        self.prompts = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "[장 요약]" in prompt:
            ids = [line.split()[0] for line in prompt.splitlines()
                   if line.startswith("H")]
            rows = [{"text": "흐름 %d이 이어진다." % index,
                     "source_highlight_refs": [ids[index % len(ids)]]}
                    for index in range(3)]
            return json.dumps({"overview_sentences": rows,
                               "analysis_points": rows,
                               "conclusion_sentences": rows[:1]},
                              ensure_ascii=False)
        refs = [word for word in prompt.split() if word.startswith("EP")]
        return json.dumps({"title": "장 제목", "summary_sentences": [
            {"text": "재료를 준비하고 조리를 이어간다.",
             "source_episode_refs": refs}]}, ensure_ascii=False)


# ── PSY-016 episode 재생성 없음 ─────────────────────────────────────────
def test_psy_016_the_episode_generation_is_never_rerun():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("build_episode_prompt", "s2_raw", "merge_content",
                      "resolve_contract", "CONTRACT_V3"):
        assert forbidden not in source


def test_the_call_count_is_one_per_group_plus_one(tmp_path):
    recorder = _Recorder()
    state = runner.synthesize(_document(), recorder, tmp_path)
    assert state["group_calls"] == len(state["groups"])
    assert state["global_calls"] == 1
    assert len(recorder.prompts) == len(state["groups"]) + 1
    assert len(set(recorder.prompts)) == len(recorder.prompts)   # 재호출 없음


def test_there_is_no_retry_path():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("retry", "attempt", "while True", "재시도한다"):
        assert forbidden not in source


# ── PSY-015 보호 경로 ───────────────────────────────────────────────────
@pytest.mark.parametrize("protected", [
    "runs/quality_candidate", "runs/vad0_paired", "runs/v3_paired",
    "runs/quality_candidate/S7", "work_full",
])
def test_psy_015_protected_paths_cannot_be_written(protected):
    with pytest.raises(runner.RunError):
        runner.assert_writable(ROOT / protected)


def test_a_fresh_candidate_path_is_allowed(tmp_path):
    assert runner.assert_writable(tmp_path / "presentation_synthesis_v1") is None
    assert runner.assert_writable(ROOT / "runs/presentation_synthesis_v1") is None


# ── 실패 처리 ───────────────────────────────────────────────────────────
def test_a_broken_group_output_is_recorded_not_retried(tmp_path):
    calls = {"n": 0}

    def flaky(prompt: str) -> str:
        calls["n"] += 1
        if "[장 요약]" in prompt:
            return _Recorder()(prompt)
        if calls["n"] == 1:
            return "망가진 출력"
        return _Recorder()(prompt)

    state = runner.synthesize(_document(), flaky, tmp_path)
    first = json.loads((tmp_path / "group_parsed/H01.json").read_text(
        encoding="utf-8"))
    assert first["content_status"] == "GROUP_SYNTHESIS_FAILURE"
    assert first["summary_sentences"] == []
    assert state["group_calls"] == len(state["groups"])      # 재호출 없음
    raw = (tmp_path / "group_raw/H01.txt").read_text(encoding="utf-8")
    assert raw == "망가진 출력"                                # raw 보존


def test_the_artifacts_are_written_under_the_candidate_path(tmp_path):
    runner.synthesize(_document(), _Recorder(), tmp_path)
    for name in ("group_raw", "group_parsed", "global_raw", "global_parsed"):
        assert (tmp_path / name).is_dir()
    assert (tmp_path / "global_parsed/global.json").is_file()


def test_the_group_record_keeps_the_exclusion_lineage(tmp_path):
    document = _document()
    document["episodes"][12]["content_status"] = "PARSE_CONTRACT_FAILURE"
    document["episodes"][12]["summary"] = None
    runner.synthesize(document, _Recorder(), tmp_path)
    third = json.loads((tmp_path / "group_parsed/H03.json").read_text(
        encoding="utf-8"))
    assert third["input"]["excluded"] == [
        {"episode_id": "EP13", "reasons": ["PARSE_CONTRACT_FAILURE"]}]
    assert "EP13" not in third["input"]["eligible_episode_refs"]
