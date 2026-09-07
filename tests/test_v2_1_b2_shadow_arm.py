"""Tier 2 배선 — orchestrator의 VAD0 shadow arm 계약.

사전등록: `docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`

```
기본값        shadow_vad0 = OFF
정책 기록      S0/ingest.json · run_manifest · fingerprint(evidence_policy)
바뀌는 것      claim evidence 자격 하나뿐 — 계약·모델·경계는 동일
provenance    episode별 eligible_evidence_hash · rendered_prompt_hash
```

두 arm이 서로의 stage를 재사용하면 비교가 무의미해지므로 지문에 정책을 넣는다.
"""
import json

import pytest

from test_v2_1_b2_orchestrator import (_Fake, _canonical, _config, _run,
                                       _segments_file, b2)
from v2_1_llm_adapter import GenerationConfig

GENERATION = GenerationConfig(model_id="fixture/qwen-stub", do_sample=False,
                              max_new_tokens=128)
PAYLOADS = ({"summary": "앞 구간 요약이다."}, {"summary": "뒤 구간 요약이다."})


def _policy(overlaps: dict) -> dict:
    return {"shadow_vad0": True,
            "rule": "existing VALID AND speech_overlap_ratio == 0 -> SUSPECT",
            "measurements_sha256": "0" * 64,
            "overlaps": {str(k): v for k, v in overlaps.items()}}


def _arm(tmp_path, *, policy=None, run_dir="run", generate=None, name="S1"):
    segments = _segments_file(tmp_path, name)
    fake = generate or _Fake(PAYLOADS)
    summary = b2.orchestrate(
        tmp_path / run_dir, segments, _config(tmp_path), video_id=name,
        run_id="shadow-test", generate=fake, generation=GENERATION,
        producer_version="b1-code-head", window_sec=30.0,
        contract_name="v3", evidence_policy=policy)
    return summary, fake, tmp_path / run_dir


class _Recorder(_Fake):
    """모델에 실제로 간 프롬프트를 모은다."""

    def __init__(self, payloads):
        super().__init__(payloads)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return super().__call__(prompt)


# ── 기본값 ───────────────────────────────────────────────────────────────
def test_the_default_run_has_no_shadow_policy(tmp_path):
    summary, _, run = _run(tmp_path, payloads=PAYLOADS, contract_name="v3")
    ingest = json.loads((run / "S0/ingest.json").read_text(encoding="utf-8"))
    assert ingest["evidence_policy"] == {"shadow_vad0": False}
    assert summary["fingerprint"]["evidence_policy"] == "control"
    assert summary["evidence_policy"]["shadow_vad0"] is False


def test_the_policy_lives_in_the_s0_artifact(tmp_path):
    """실행 인자가 아니라 **산출물**에 적혀야 재개·재사용이 정합적이다."""
    _, _, run = _arm(tmp_path, policy=_policy({i: 0.0 for i in range(12)}))
    ingest = json.loads((run / "S0/ingest.json").read_text(encoding="utf-8"))
    assert ingest["evidence_policy"]["shadow_vad0"] is True
    assert ingest["evidence_policy"]["overlaps"]["0"] == 0.0


def test_the_manifest_does_not_carry_the_whole_overlap_table(tmp_path):
    summary, _, _ = _arm(tmp_path, policy=_policy({i: 0.0 for i in range(12)}))
    assert "overlaps" not in summary["evidence_policy"]
    assert summary["fingerprint"]["evidence_policy"] == "shadow_vad0"


# ── 규칙이 실제 프롬프트에 반영되는가 ────────────────────────────────────
def test_zero_overlap_speech_never_reaches_the_prompt(tmp_path):
    from v2_1_fixtures import scenario

    fixture = scenario("S1")
    spoken = {segment_id: text for segment_id, text in fixture.asr.items() if text}
    assert spoken, "fixture에 발화가 있어야 의미 있는 검사다"
    recorder = _Recorder(PAYLOADS)
    _arm(tmp_path, policy=_policy({i: 0.0 for i in range(12)}),
         generate=recorder)
    joined = "\n".join(recorder.prompts)
    for text in spoken.values():
        assert text not in joined, text


def test_positive_overlap_speech_still_reaches_the_prompt(tmp_path):
    from v2_1_fixtures import scenario

    fixture = scenario("S1")
    recorder = _Recorder(PAYLOADS)
    _arm(tmp_path, policy=_policy({i: 0.9 for i in range(12)}),
         generate=recorder)
    joined = "\n".join(recorder.prompts)
    assert any(text and text in joined for text in fixture.asr.values())


# ── 두 arm 비교 계약 ─────────────────────────────────────────────────────
def test_only_the_evidence_changes_between_arms(tmp_path):
    control, _, control_run = _arm(tmp_path, run_dir="s0")
    treatment, _, treatment_run = _arm(
        tmp_path, policy=_policy({i: 0.0 for i in range(12)}), run_dir="s1")

    # 계약·모델은 같다.
    for key in ("prompt_version", "prompt_hash", "model_id"):
        assert control["fingerprint"][key] == treatment["fingerprint"][key]
    assert control["fingerprint"]["evidence_policy"] != \
        treatment["fingerprint"]["evidence_policy"]

    # 경계는 ASR과 무관하다.
    left = json.loads((control_run / "S1/episodes.json").read_text(
        encoding="utf-8"))
    right = json.loads((treatment_run / "S1/episodes.json").read_text(
        encoding="utf-8"))
    assert left["spans"] == right["spans"]

    # 근거 집합만 달라진다.
    def digests(run):
        index = json.loads((run / "S2/raw_index.json").read_text(
            encoding="utf-8"))
        return {row["episode_id"]: (row.get("eligible_evidence_hash"),
                                    row.get("rendered_prompt_hash"))
                for row in index["episodes"] if row["raw"]}

    control_digests, treatment_digests = digests(control_run), digests(treatment_run)
    assert control_digests and treatment_digests
    changed = [key for key in control_digests
               if control_digests[key] != treatment_digests.get(key)]
    assert changed, "shadow가 어떤 episode의 근거도 바꾸지 않았다"


def test_the_provenance_hashes_are_recorded_for_every_generated_episode(tmp_path):
    _, _, run = _arm(tmp_path, policy=_policy({i: 0.0 for i in range(12)}))
    index = json.loads((run / "S2/raw_index.json").read_text(encoding="utf-8"))
    for row in index["episodes"]:
        if row["raw"]:
            assert len(row["eligible_evidence_hash"]) == 64
            assert len(row["rendered_prompt_hash"]) == 64
            assert row["eligible_evidence_count"] >= 1


def test_an_arm_does_not_reuse_the_other_arms_stages(tmp_path):
    """지문에 정책이 들어가야 재개가 arm을 섞지 않는다."""
    _arm(tmp_path, run_dir="mixed")
    summary, fake, _ = _arm(tmp_path, policy=_policy({i: 0.0 for i in range(12)}),
                            run_dir="mixed")
    assert all(not stage["reused"] for stage in summary["stages"].values())


def test_the_structure_survives_when_all_asr_is_abstained(tmp_path):
    """근거가 캡션만 남아도 구조는 살아 있어야 한다."""
    summary, _, run = _arm(tmp_path, policy=_policy({i: 0.0 for i in range(12)}))
    assert summary["stages"]["S7"]["stage_complete"]
    document = _canonical(run)
    assert len(document["episodes"]) == 2
    assert (run / "S7/report.hwpx").is_file()
