"""Tier 1 — `speech_overlap_ratio == 0` shadow abstention 계약.

사전등록: `docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`

```
SUSPECT_STT_VAD0 := existing status == VALID AND speech_overlap_ratio == 0
```

**production 판정을 mutate하지 않는다.** counterfactual 결과를 별도 객체로 만든다 —
shadow 버그가 production evidence로 새는 경로를 아예 만들지 않기 위해서다.

```
M1 overlap > 0인데 SUSPECT       RED
M2 overlap == 0인데 VALID 유지    RED
M3 원본 status를 실제로 변경      RED
M4 기본 flag가 ON                RED
M5 latin·repeat·gap을 조건에 추가 RED
```
"""
import importlib.util
from pathlib import Path

import pytest

from v2_1_fixtures import scenario
from v2_1_sanitation import SUSPECT, VALID, classify_channel

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/stt_vad0_shadow.py"


def _load():
    """dataclass가 모듈을 sys.modules에서 찾으므로 먼저 등록한다."""
    import sys

    spec = importlib.util.spec_from_file_location("stt_vad0_shadow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


shadow = _load()


@pytest.fixture
def judged():
    channel = {0: "안녕하세요 오늘은 요리를 합니다", 1: "", 2: "icular 볶고",
               3: "홈페이지 www.example.com", 4: "소금을 넣습니다"}
    return channel, classify_channel(channel, "asr")


# ── 규칙 ─────────────────────────────────────────────────────────────────
def test_zero_overlap_valid_becomes_shadow_suspect(judged):
    """**M2가 이 테스트를 깬다.**"""
    _, verdicts = judged
    overlaps = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.8}
    rows = shadow.shadow_rows(verdicts, overlaps)
    by_id = {row.segment_id: row for row in rows}
    assert by_id[0].shadow_status == SUSPECT
    assert by_id[0].shadow_usable_for_claims is False
    assert by_id[0].shadow_reason == "vad_zero_overlap"
    assert by_id[0].transitioned is True


def test_overlapping_speech_is_left_alone(judged):
    """**M1이 이 테스트를 깬다.**"""
    _, verdicts = judged
    overlaps = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.8}
    by_id = {row.segment_id: row for row in shadow.shadow_rows(verdicts, overlaps)}
    assert by_id[4].shadow_status == VALID
    assert by_id[4].shadow_usable_for_claims is True
    assert by_id[4].transitioned is False
    assert by_id[4].shadow_reason is None


@pytest.mark.parametrize("ratio", [1e-9, 0.01, 0.5, 1.0])
def test_any_positive_overlap_is_not_touched(judged, ratio):
    _, verdicts = judged
    rows = shadow.shadow_rows(verdicts, {0: ratio, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0})
    assert {row.segment_id: row.transitioned for row in rows}[0] is False


def test_non_valid_statuses_are_never_promoted_or_changed(judged):
    """EMPTY·REJECTED는 그대로 둔다 — 이 규칙은 VALID만 본다."""
    _, verdicts = judged
    rows = {row.segment_id: row for row in
            shadow.shadow_rows(verdicts, {i: 0.0 for i in range(5)})}
    assert rows[1].original_status == rows[1].shadow_status == "EMPTY"
    assert rows[3].original_status == rows[3].shadow_status == "REJECTED"
    assert rows[3].shadow_usable_for_claims is False
    assert rows[1].transitioned is False and rows[3].transitioned is False


def test_the_rule_uses_only_overlap(judged):
    """**M5가 이 테스트를 깬다.** 라틴·반복·gap은 판정에 들어가지 않는다."""
    _, verdicts = judged
    # seg2는 라틴을 담고 있지만 overlap이 있으면 건드리지 않는다.
    rows = {row.segment_id: row for row in
            shadow.shadow_rows(verdicts, {0: 0.9, 1: 0.0, 2: 0.9, 3: 0.0, 4: 0.9})}
    assert rows[2].transitioned is False
    code = SCRIPT.read_text(encoding="utf-8")
    body = code.split("def shadow_rows", 1)[1].split("\ndef ", 1)[0]
    for banned in ("latin", "repeat", "gap"):
        assert banned not in body, banned


# ── production 무변경 ────────────────────────────────────────────────────
def test_production_judgements_are_not_mutated(judged):
    """**M3가 이 테스트를 깬다.**"""
    _, verdicts = judged
    before = {key: (value.status, value.usable_for_claims, value.text)
              for key, value in verdicts.items()}
    shadow.shadow_rows(verdicts, {i: 0.0 for i in range(5)})
    shadow.shadow_judgements(verdicts, {i: 0.0 for i in range(5)})
    after = {key: (value.status, value.usable_for_claims, value.text)
             for key, value in verdicts.items()}
    assert before == after


def test_shadow_judgements_are_new_objects_with_original_text(judged):
    _, verdicts = judged
    counterfactual = shadow.shadow_judgements(verdicts, {i: 0.0 for i in range(5)})
    assert counterfactual is not verdicts
    for key, value in counterfactual.items():
        assert value is not verdicts[key]
        assert value.text == verdicts[key].text          # 원문 보존
        assert value.preserved == verdicts[key].preserved
    assert counterfactual[0].status == SUSPECT
    assert counterfactual[0].usable_for_claims is False


def test_the_flag_defaults_to_off():
    """**M4가 이 테스트를 깬다.** 켜야만 적용된다."""
    assert shadow.SHADOW_VAD0_DEFAULT is False
    import inspect
    signature = inspect.signature(shadow.evaluate)
    assert signature.parameters["shadow_vad0"].default is False


def test_evaluate_without_the_flag_reports_no_transition(judged):
    channel, verdicts = judged
    result = shadow.evaluate(verdicts, {i: 0.0 for i in range(5)},
                             shadow_vad0=False)
    assert result["transitions"] == 0
    assert all(row.shadow_status == row.original_status
               for row in result["rows"])


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_the_module_does_not_edit_production_sanitation():
    """대입(=)만 금지한다. 비교(==)는 규칙 자체가 쓴다."""
    import re

    code = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("v2_1_sanitation.py", "object.__setattr__"):
        assert forbidden not in code, forbidden
    for attribute in ("status", "usable_for_claims", "text"):
        assert not re.search(r"\.%s\s*=(?!=)" % attribute, code), attribute


def test_missing_overlap_is_an_error_not_a_default(judged):
    """측정값이 없는 구간을 0으로 간주하면 조용히 SUSPECT가 늘어난다."""
    _, verdicts = judged
    with pytest.raises(KeyError):
        shadow.shadow_rows(verdicts, {0: 0.0})


# ── episode 계층 (ERR-009 예측) ─────────────────────────────────────────
def test_episode_counterfactual_reports_evidence_loss(tmp_path):
    """LLM 없이 '프롬프트가 거부될 구간'을 결정적으로 센다."""
    fixture = scenario("S1")
    legacy = [{"idx": segment.segment_id, "start": segment.start_sec,
               "end": segment.end_sec,
               "subtitle": fixture.asr.get(segment.segment_id, ""),
               "caption": fixture.caption.get(segment.segment_id, "")}
              for segment in fixture.segments]
    # 모든 ASR을 overlap 0으로 두면 ASR 근거는 전부 shadow에서 빠진다.
    overlaps = {segment.segment_id: 0.0 for segment in fixture.segments}
    report = shadow.episode_counterfactual(legacy, overlaps, window_sec=30.0)
    assert report["partition_equal"] is True
    assert report["episodes"]
    for row in report["episodes"]:
        assert row["shadow_asr_eligible"] == 0
        assert row["shadow_eligible"] <= row["original_eligible"]
    assert report["new_err_009"] == sum(
        1 for row in report["episodes"]
        if row["original_eligible"] > 0 and row["shadow_eligible"] == 0)


def test_partition_is_independent_of_the_asr_channel(tmp_path):
    fixture = scenario("S1")
    legacy = [{"idx": s.segment_id, "start": s.start_sec, "end": s.end_sec,
               "subtitle": fixture.asr.get(s.segment_id, ""),
               "caption": fixture.caption.get(s.segment_id, "")}
              for s in fixture.segments]
    zero = shadow.episode_counterfactual(
        legacy, {s.segment_id: 0.0 for s in fixture.segments}, window_sec=30.0)
    full = shadow.episode_counterfactual(
        legacy, {s.segment_id: 1.0 for s in fixture.segments}, window_sec=30.0)
    assert zero["spans"] == full["spans"]
    assert zero["partition_equal"] and full["partition_equal"]


# ── GEO / TRI 회귀 — shadow 경로로 통과시킨다 ────────────────────────────
def _legacy(name):
    fixture = scenario(name)
    return fixture, [{"idx": s.segment_id, "start": s.start_sec, "end": s.end_sec,
                      "subtitle": fixture.asr.get(s.segment_id, ""),
                      "caption": fixture.caption.get(s.segment_id, "")}
                     for s in fixture.segments]


def test_geo_001_rich_stt_with_overlap_stays_usable_in_shadow():
    """발화가 VAD speech와 겹치면 shadow에서도 근거로 남는다."""
    fixture, legacy = _legacy("S4")
    overlaps = {s.segment_id: 0.9 for s in fixture.segments}
    report = shadow.episode_counterfactual(legacy, overlaps, window_sec=30.0)
    for row in report["episodes"]:
        assert row["shadow_asr_eligible"] == row["original_asr_eligible"]
        assert row["shadow_eligible"] == row["original_eligible"]
    assert report["new_err_009"] == 0


def test_geo_004_dialogue_heavy_episode_is_still_processed():
    """근거가 빠져도 구조는 산다 — 구간 수·경계가 그대로다."""
    fixture, legacy = _legacy("S4")
    control = shadow.episode_counterfactual(
        legacy, {s.segment_id: 0.9 for s in fixture.segments}, window_sec=30.0)
    shadowed = shadow.episode_counterfactual(
        legacy, {s.segment_id: 0.0 for s in fixture.segments}, window_sec=30.0)
    assert control["spans"] == shadowed["spans"]
    assert len(control["episodes"]) == len(shadowed["episodes"])
    assert shadowed["partition_equal"] is True


def test_err_009_entry_is_detected_without_an_llm():
    """근거가 0이 되는 구간을 결정적으로 센다 — 프롬프트를 만들지 않는다."""
    fixture, legacy = _legacy("S4")          # S4는 ASR 단독이라 전량 제거 시 0이 된다
    report = shadow.episode_counterfactual(
        legacy, {s.segment_id: 0.0 for s in fixture.segments}, window_sec=30.0)
    assert report["new_err_009"] >= 1
    for row in report["episodes"]:
        if row["lost_all_evidence"]:
            assert row["original_eligible"] > 0 and row["shadow_eligible"] == 0


def test_tri_005_shadow_can_only_shrink_evidence_never_invent():
    """shadow는 근거를 줄이기만 한다. 새 근거·새 문장을 만들지 않는다."""
    fixture, legacy = _legacy("S1")
    partial = {s.segment_id: (0.0 if s.segment_id % 2 else 0.9)
               for s in fixture.segments}
    report = shadow.episode_counterfactual(legacy, partial, window_sec=30.0)
    for row in report["episodes"]:
        assert row["shadow_eligible"] <= row["original_eligible"]
        assert row["shadow_asr_eligible"] <= row["original_asr_eligible"]
    # Tier 1은 생성 계층을 부르지 않는다(요약·정본·표현 전부).
    code = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("build_aar", "presentation_input", "build_presentation",
                      "render_markdown", "merge_content", "apply_grounding"):
        assert forbidden not in code, forbidden
