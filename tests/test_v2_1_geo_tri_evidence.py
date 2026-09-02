"""E-04 GEO/TRI 증거 — dataset regression을 그 결함 입력으로 잰다.

GEO는 geoje, TRI는 3I7 회귀다(`V2_1_IMPLEMENTATION_PLAN` §21).

```
geoje   풍부한 대화 STT · evidence integration · instruction-echo caption · grounding
3I7     sparse/invalid STT · 오염·외국어 caption · 검은 화면 전환 · evidence 희소
```

합성 fixture의 **문자열이 그 두 영상의 실측값**이다 — `INSTRUCTION_ECHO`는 geoje
chunk3 최대 peak, `FOREIGN_CAPTION`은 3I7 seg#1, `BOILERPLATE`는 3I7 반복 문구,
`EXCITED_SPEECH`는 반복 규칙으로 지워졌던 geoje 실제 발화다. 그래서 결함 의미론에
대해서는 이 fixture가 회귀 운반체다. **실제 영상 산출물을 읽지 않는다**(A-10 결정성).

```
TRI-005는 여기서 닫지 않는다 — evidence-gap이 아니라 implementation-gap이다.
상세는 감사 문서.
```
"""
import json
from pathlib import Path

import pytest

from v2_1_aar import validate_aar
from v2_1_fixtures import (
    BOILERPLATE,
    EXCITED_SPEECH,
    FOREIGN_CAPTION,
    INSTRUCTION_ECHO,
    scenario,
)
from v2_1_gate_b import run_pipeline
from v2_1_grounding import (
    FAIL_INELIGIBLE_SUPPORT,
    FAIL_NO_SUPPORT,
    NOT_APPLICABLE,
    PASS,
)
from v2_1_partition import validate_partition
from v2_1_presentation_input import presentation_input
from v2_1_sanitation import (
    REJECTED,
    SUSPECT,
    VALID,
    classify_channel,
    eligible_support,
)
from v2_1_timeline import build_timeline

ROOT = Path(__file__).resolve().parents[1]
C0_ARTIFACT = ROOT / "runs/c0/c0_boundary_signal.json"

TWO = ((0, 5), (6, 11))


# ── GEO-001 rich STT → dialogue evidence 사용 ────────────────────────────
def _geo_rich(tmp_path, *, asr_overrides=None, cites=(9,)):
    """S4 = ASR 단독 12발화. geoje의 '풍부한 대화 STT' 대응물이다."""
    payloads = ({"summary": "앞 구간 요약이다."},
                {"summary": "두 사람이 길을 정한다.",
                 "dialogue_note": "내려갈 길을 정한다고 말한다.",
                 "stt_cites": list(cites)})
    return run_pipeline(tmp_path, payloads, name="S4", spans=TWO,
                        asr_overrides=asr_overrides)


def test_geo_001_rich_stt_actually_becomes_the_dialogue_evidence(tmp_path):
    """"STT를 읽었다"가 아니라 **dialogue claim의 근거가 됐다**를 본다."""
    # 1. fixture가 실제로 rich STT다 — 유효 발화가 12건이고 캡션은 없다.
    s = scenario("S4")
    judged = classify_channel(s.asr, "asr")
    assert len(eligible_support(judged.values())) == 12
    assert not s.caption

    pipeline = _geo_rich(tmp_path / "rich")
    episode = pipeline.document["episodes"][1]

    # 2. dialogue가 근거와 함께 통과하고 정본에 남는다.
    assert episode["grounding_status"] == PASS
    assert episode["dialogue_note"] == "내려갈 길을 정한다고 말한다."
    binding = pipeline.bindings[1]
    assert [c.segment_id for c in binding.cites] == [9]
    assert binding.cites[0].sanitation_status == VALID
    assert binding.cites[0].usable_for_claims is True

    # 3. 그 ASR 근거를 없애면 같은 dialogue가 통과하지 못한다.
    blanked = _geo_rich(tmp_path / "blank", asr_overrides={9: ""})
    without = blanked.document["episodes"][1]
    assert without["grounding_status"] != PASS
    assert without["dialogue_note"] is None


def test_geo_001_a_dialogue_without_any_cite_does_not_pass(tmp_path):
    """근거 없이 대화를 적으면 통과하지 않는다 — 사용의 반대편을 고정한다."""
    payloads = ({"summary": "앞."},
                {"summary": "길을 정한다.", "dialogue_note": "내려갈 길을 말한다."})
    pipeline = run_pipeline(tmp_path, payloads, name="S4", spans=TWO)
    assert pipeline.grounding[1].status == FAIL_NO_SUPPORT


# ── GEO-002 instruction echo vs 정상 caption ─────────────────────────────
def test_geo_002_the_echo_is_distinguished_from_normal_captions():
    """echo 단독 REJECTED로는 절반이다 — 정상 caption 비교 arm이 있어야 한다."""
    s = scenario("S6")
    judged = classify_channel(s.caption, "vlm")

    echo = judged[3]
    assert s.caption[3] == INSTRUCTION_ECHO           # geoje chunk3 최대 peak 실측값
    assert echo.status == REJECTED and echo.reason == "instruction_echo"
    assert echo.usable_for_claims is False

    # S6의 나머지 10건은 **같은 문장 반복**이므로 그 자체로 SUSPECT/repeated다
    # (fixture의 실제 성질이다). echo와는 상태도 사유도 다르다 —
    # 독립 근거로 걸린 것과 반복으로 의심된 것을 뭉치지 않는다.
    others = [judged[i] for i in judged if i not in (3, 7)]
    assert len(others) == 10
    assert {j.status for j in others} == {SUSPECT}
    assert {j.reason for j in others} == {"repeated"}
    assert echo.status != others[0].status and echo.reason != others[0].reason

    # 진짜 정상 caption(구간마다 다른 문장)은 VALID이고 근거로 쓸 수 있다.
    normal = classify_channel(scenario("S1").caption, "vlm")
    assert {j.status for j in normal.values()} == {VALID}
    assert len(eligible_support(normal.values())) == 12

    # 같은 채널 안에서 세 종류가 갈린다.
    assert judged[7].status == SUSPECT and judged[7].reason == "foreign_script"
    assert judged[7].reason != judged[0].reason


def test_geo_002_the_echo_is_preserved_not_deleted():
    """구분은 삭제가 아니다 — 원문이 그대로 남는다(OPEN-7)."""
    judged = classify_channel(scenario("S6").caption, "vlm")
    assert judged[3].preserved is True
    assert judged[3].text == INSTRUCTION_ECHO


# ── GEO-003 echo → fixed-window boundary 무영향 ──────────────────────────
def test_geo_003_is_measured_by_the_err_010_perturbation():
    """ERR-010이 만든 S6 echo perturbation 테스트를 그대로 잠근다.

    상태 참조가 아니라 **그 테스트가 실재하는지**를 본다 — 이름이 바뀌면 깨진다.
    """
    source = (ROOT / "tests/test_v2_1_err_evidence.py").read_text(encoding="utf-8")
    assert "def test_err_010_an_instruction_echo_peak_does_not_move_the_fixed_window(" \
        in source
    assert "INSTRUCTION_ECHO" in source
    assert "boundary_positions" in source


# ── GEO-004 dialogue-heavy episode 처리 ──────────────────────────────────
def test_geo_004_a_dialogue_heavy_episode_is_processed(tmp_path):
    """fixture가 dialogue-heavy임을 먼저 증명한다. 그 다음 '처리'만 본다."""
    s = scenario("S4")
    asr_usable = len(eligible_support(classify_channel(s.asr, "asr").values()))
    caption_usable = len(eligible_support(
        classify_channel(s.caption, "vlm").values())) if s.caption else 0
    assert asr_usable == 12 and caption_usable == 0     # 정보가 speech에 있다

    pipeline = _geo_rich(tmp_path)
    document = pipeline.document

    # 구조는 살아 있고 내용이 생성됐다.
    assert validate_aar(document).ok
    assert [e["episode_id"] for e in document["episodes"]] == ["EP01", "EP02"]
    assert all(e["content_status"] == "VALID_PARSE" for e in document["episodes"])
    assert all(e["summary"] for e in document["episodes"])
    # 근거가 붙은 dialogue는 통과한다. **dialogue 생성을 강제하지 않는다.**
    assert document["episodes"][1]["grounding_status"] == PASS
    assert document["episodes"][0]["grounding_status"] == NOT_APPLICABLE
    assert presentation_input(document).episodes[1].dialogue_note is not None


def test_geo_004_source_is_derived_as_speech_for_a_dialogue_heavy_episode(tmp_path):
    """dialogue-heavy가 파생 필드에도 반영된다."""
    pipeline = _geo_rich(tmp_path)
    assert [e["source"] for e in pipeline.document["episodes"]] == ["stt", "stt"]


# ── TRI-001 effectively absent STT → 구조적 성공 ─────────────────────────
def test_tri_001_an_episode_without_stt_still_succeeds_structurally(tmp_path):
    """STT가 사실상 없어도 **구조**는 성공한다. 내용 품질은 요구하지 않는다."""
    s = scenario("S3")                       # no STT · caption only (3I7류)
    assert not s.asr
    assert len(eligible_support(classify_channel(s.caption, "vlm").values())) == 12

    payloads = ({"summary": "산길을 오른다."}, {"summary": "정상에 도착한다."})
    pipeline = run_pipeline(tmp_path, payloads, name="S3", spans=TWO)
    document = pipeline.document

    assert validate_aar(document).ok
    assert validate_partition(list(TWO), s.segments).ok
    assert [(e["start_seg"], e["end_seg"]) for e in document["episodes"]] == list(TWO)
    assert all(e["content_status"] == "VALID_PARSE" for e in document["episodes"])
    # dialogue가 없으므로 grounding은 적용 대상이 아니다 — 실패가 아니다.
    assert {e["grounding_status"] for e in document["episodes"]} == {NOT_APPLICABLE}
    assert [e["source"] for e in document["episodes"]] == ["visual", "visual"]


# ── TRI-002 contaminated STT → meaningful dialogue 오인 금지 ─────────────
#: STT 쪽 오염. 무발화 구간에 STT가 만들어 내던 형태다.
CONTAMINATED_ASR = "한글자막 by 홍길동"


def test_tri_002_contaminated_stt_cannot_support_a_dialogue(tmp_path):
    """오염 STT는 보존되지만 dialogue의 근거가 되지 못한다."""
    overrides = {i: "" for i in range(12)}
    overrides[9] = CONTAMINATED_ASR
    payloads = ({"summary": "앞."},
                {"summary": "두 사람이 이야기한다.",
                 "dialogue_note": "다음 영상을 예고한다고 말한다.",
                 "stt_cites": [9]})
    pipeline = run_pipeline(tmp_path, payloads, name="S4", spans=TWO,
                            asr_overrides=overrides)

    verdict = pipeline.grounding[1]
    assert verdict.status == FAIL_INELIGIBLE_SUPPORT
    assert "ineligible_support" in {r.code for r in verdict.reasons}

    # 보존은 된다 — 삭제가 아니다.
    cite = pipeline.bindings[1].cites[0]
    assert cite.segment_id == 9
    assert cite.sanitation_status == REJECTED
    assert cite.usable_for_claims is False

    # 정본에서 dialogue는 제거되고 summary는 남는다.
    episode = pipeline.document["episodes"][1]
    assert episode["dialogue_note"] is None
    assert episode["summary"] == "두 사람이 이야기한다."


def test_tri_002_a_repeated_stt_line_is_also_ineligible(tmp_path):
    """반복 오염(3I7 문구)도 같은 결론이다 — 오염의 종류를 하나로 좁히지 않는다."""
    payloads = ({"summary": "앞.", "dialogue_note": "메모", "stt_cites": [0]},
                {"summary": "뒤."})
    pipeline = run_pipeline(tmp_path, payloads, name="S1", spans=TWO)
    assert pipeline.grounding[0].status == FAIL_INELIGIBLE_SUPPORT
    assert pipeline.bindings[0].cites[0].sanitation_status == SUSPECT


# ── TRI-003 외국어 caption → sanitation state 반영 ───────────────────────
def test_tri_003_the_foreign_caption_state_reaches_the_timeline():
    """기존 계약이 정한 상태를 따른다 — 외국어라는 이유로 새 규칙을 만들지 않는다."""
    s = scenario("S6")
    assert s.caption[7] == FOREIGN_CAPTION          # 3I7 seg#1 실측 캡션
    judged = classify_channel(s.caption, "vlm")
    assert judged[7].status == SUSPECT and judged[7].reason == "foreign_script"

    timeline = build_timeline(s.segments, {"vlm": judged})
    entry = next(e for e in timeline if e.segment_id == 7)
    refs = [r for r in entry.caption_refs]
    assert refs, "캡션 ref가 사라졌다 — 보존이 깨졌다"
    assert refs[0].status == SUSPECT
    assert refs[0].preserved is True
    assert refs[0].usable_for_claims is False

    # 사유가 구분된다 — S6의 다른 구간은 반복으로 SUSPECT이고 외국어가 아니다.
    other = next(e for e in timeline if e.segment_id == 0)
    assert other.caption_refs[0].status == SUSPECT
    assert judged[0].reason == "repeated" and judged[7].reason == "foreign_script"

    # 정상 caption(S1, 구간마다 다른 문장)은 timeline에서 근거로 쓸 수 있다.
    s1 = scenario("S1")
    s1_timeline = build_timeline(s1.segments,
                                 {"vlm": classify_channel(s1.caption, "vlm")})
    s1_ref = next(e for e in s1_timeline if e.segment_id == 7).caption_refs[0]
    assert s1_ref.status == VALID and s1_ref.usable_for_claims is True


# ── TRI-004 black-screen transition → diagnostic 가능 ────────────────────
#: 3I7 검은 화면 캡션의 실측 표현.
BLACK_SCREEN = "완전히 검은색으로 가득 차 있으며"


def test_tri_004_the_black_screen_transition_is_observable_in_the_diagnostic():
    """계약은 "경계로 잡는다"가 아니라 **진단에서 관측·확인 가능**이다.

    C0 문서 §4 분류가 '검은 화면 전환 2'로 세었고, 그 2건이 산출물에 남아 있다.
    """
    artifact = json.loads(C0_ARTIFACT.read_text(encoding="utf-8"))
    window = next(w for w in artifact["windows"]
                  if w["video_id"] == "m8c2_3I7oGwk6EaQ")
    black = [p for p in window["peaks"]
             if BLACK_SCREEN in p["caption_prev"] or BLACK_SCREEN in p["caption_here"]]
    assert len(black) >= 2, [p["seg"] for p in window["peaks"]]

    # 관측에 필요한 값이 함께 남아 있다 — 이것이 "diagnostic 가능"의 내용이다.
    for peak in black:
        assert isinstance(peak["seg"], int)
        assert peak["distance"] > 0
        assert 0.0 <= peak["pct_rank"] <= 1.0
        assert peak["caption_prev"] and peak["caption_here"]

    # 전환의 두 방향이 모두 있다 — 검은 화면으로 들어가고 나온다.
    assert any(BLACK_SCREEN in p["caption_here"] for p in black)
    assert any(BLACK_SCREEN in p["caption_prev"] for p in black)


def test_tri_004_the_observation_is_not_wired_into_adoption():
    """관측했다는 것이 채택이 아니다 — CP-009와 같은 분리다."""
    artifact = json.loads(C0_ARTIFACT.read_text(encoding="utf-8"))
    assert "provider_adoption" in artifact["not_done"]
    for forbidden in ("adopted", "verdict", "selected"):
        assert forbidden not in artifact


# ── TRI-006 3I7 반복 문구 — 세 단계 전부 ─────────────────────────────────
def test_tri_006_the_boilerplate_is_preserved_suspect_and_never_sole_support(
        tmp_path):
    """OPEN-9 계약 세 단계를 한 자리에서 잰다."""
    s = scenario("S1")
    judged = classify_channel(s.asr, "asr")
    boilerplate = [j for j in judged.values() if j.text == BOILERPLATE]

    # 1. 삭제되지 않는다.
    assert len(boilerplate) == 8
    assert all(j.preserved and j.text == BOILERPLATE for j in boilerplate)

    # 2. SUSPECT다.
    assert {j.status for j in boilerplate} == {SUSPECT}
    assert {j.reason for j in boilerplate} == {"repeated"}
    assert all(j.usable_for_claims is False for j in boilerplate)
    # 실제 발화는 살아 있다 — 반복 규칙이 발화를 지우지 않는다.
    assert judged[8].status == VALID and judged[8].text == EXCITED_SPEECH

    # 3. 이것만으로 지지되는 claim은 통과하지 못한다.
    alone = run_pipeline(
        tmp_path / "alone",
        ({"summary": "앞.", "dialogue_note": "메모", "stt_cites": [0, 1, 2]},
         {"summary": "뒤."}),
        name="S1", spans=TWO)
    assert alone.grounding[0].status == FAIL_INELIGIBLE_SUPPORT

    # 통과한 claim에서 이 문구가 eligible support로 쓰인 건수는 0이다.
    passed = run_pipeline(
        tmp_path / "mixed",
        ({"summary": "앞."},
         {"summary": "뒤.", "dialogue_note": "메모", "stt_cites": [9, 6]}),
        name="S1", spans=TWO)
    verdict = passed.grounding[1]
    assert verdict.status == PASS
    eligible = [c for c in passed.bindings[1].cites if c.usable_for_claims]
    assert eligible, "통과했는데 eligible cite가 없다 — fixture가 무의미해졌다"
    assert all(c.segment_id != 6 for c in eligible)      # seg#6 = BOILERPLATE
    # 인용 사실은 지워지지 않는다.
    assert any(c.segment_id == 6 and not c.usable_for_claims
               for c in passed.bindings[1].cites)
