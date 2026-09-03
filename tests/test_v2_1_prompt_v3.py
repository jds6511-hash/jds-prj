"""summary-only 생성 계약(v3) — 병행 계약 · 합성 시나리오 · mechanism metric.

사전등록: `docs/finalization/V2_1_V3_SUMMARY_ONLY_PREREG_2026-09-03.md`

이 티켓은 **가드를 낮추지 않는다.** 선택 항목 하나(dialogue_note)의 grounding 실패가
그 구간 요약을 표현에서 지우는 결합(C-09 · 실측 회수율 2/41)을 끊기 위해, 생성 표면에서
그 항목을 없앤 계약을 v2 **옆에** 둔다.

```
C   계약     v2 무수정 · 기본값 v2 · 모르는 이름은 실패
S   합성     normal · rich-STT · dialogue-heavy · sparse · no-evidence · parse 실패 · v2 회귀
M   mutation M1 dialogue_note 복귀 · M2 stt_cites 복귀 · M3 기본값 v3 · M4 sparse 우회
```

합성 시나리오는 orchestrator 실경로로 돈다(raw 저장 → 실제 parser → binding →
grounding → sparse → AAR → presentation → A2'). 중간 객체를 손으로 만들면 계약이
아니라 손으로 만든 것을 재게 된다. 그래서 harness를 새로 쓰지 않고 B2 게이트의 것을
그대로 쓴다 — 두 벌이 되면 서로 다른 것을 재기 시작한다.
"""
import json

import pytest

from test_v2_1_b2_orchestrator import _Fake, _canonical, _hwpx_text, _run, b2
from v2_1_episode import MODEL_FIELDS
from v2_1_prompt import (
    CONTRACT,
    CONTRACT_V3,
    PROMPT_VERSION,
    PROMPT_VERSION_V3,
    PromptError,
    build_episode_prompt,
    contract_hash,
    resolve_contract,
)
from v2_1_scan import code_only
from test_v2_1_prompt import SRC, stocked  # noqa: F401  (fixture 재사용)

#: 2026-09-03 R0 실행이 기록한 값이다(`runs/b2_full_4090/aar_canonical.json`).
#: 이 상수가 흔들리면 이미 기록된 `prompt_hash`가 무엇을 가리켰는지 알 수 없게 된다.
V2_CONTRACT_HASH = "beaa322ea0200d3d1f6cdccc2da7421f7bb79c2024186e3df1b8c918e12d2725"

DIALOGUE_KEYS = ("dialogue_note", "stt_cites")


# ── C 계약: v2는 그대로다 ────────────────────────────────────────────────
def test_c_v2_contract_hash_is_the_one_already_recorded():
    """v3를 넣는 것이 v2 지문을 바꾸면 안 된다 — 과거 기록의 의미가 사라진다."""
    assert contract_hash(CONTRACT) == V2_CONTRACT_HASH
    assert PROMPT_VERSION == "episode_content_v2"


def test_c_v2_output_surface_is_untouched():
    assert CONTRACT["output"]["required"] == ["summary"]
    assert CONTRACT["output"]["optional"] == list(DIALOGUE_KEYS)
    assert CONTRACT["output"]["omit_when_absent"] == list(DIALOGUE_KEYS)
    assert MODEL_FIELDS == ("summary", "dialogue_note", "stt_cites")


def test_c_the_default_call_is_v2(stocked):
    """호출자가 계약을 명시하지 않으면 v2다. **M3가 이 테스트를 깬다.**"""
    store, timeline, episodes = stocked
    implicit = build_episode_prompt(episodes[1], timeline, store)
    explicit = build_episode_prompt(episodes[1], timeline, store,
                                    contract=CONTRACT)
    assert implicit.text == explicit.text
    assert implicit.prompt_version == PROMPT_VERSION
    assert implicit.prompt_hash == V2_CONTRACT_HASH
    for key in DIALOGUE_KEYS:
        assert key in implicit.text, key


def test_c_v2_prompt_text_is_byte_for_byte_the_v2_tail(stocked):
    """v2 프롬프트 꼬리를 문자열로 못 박는다 — 재배선이 문구를 흔들 수 있다."""
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[1], timeline, store).text
    assert text.endswith(
        "\n".join([
            "출력은 JSON 객체 하나다. 다른 말을 덧붙이지 않는다.",
            "쓸 수 있는 키는 셋뿐이다.",
            "- summary: 필수. 한 문장.",
            "- dialogue_note: 인용할 발화가 있을 때만. 없으면 키를 넣지 않는다.",
            "- stt_cites: 인용한 구간 번호의 배열. 없으면 키를 넣지 않는다.",
        ])
    )


# ── C 계약: v3의 형태 ────────────────────────────────────────────────────
def test_c_v3_version_and_hash_are_distinct():
    assert PROMPT_VERSION_V3 == "episode_content_v3_summary_only"
    assert CONTRACT_V3["version"] == PROMPT_VERSION_V3
    assert contract_hash(CONTRACT_V3) != contract_hash(CONTRACT)
    assert contract_hash(CONTRACT_V3) == contract_hash(CONTRACT_V3)


def test_c_v3_requires_summary_and_declares_no_optional_field():
    """**M1·M2가 이 테스트를 깬다.**"""
    assert CONTRACT_V3["output"]["required"] == ["summary"]
    assert CONTRACT_V3["output"]["optional"] == []
    assert CONTRACT_V3["output"]["omit_when_absent"] == []


def test_c_v3_prompt_never_names_the_dialogue_fields(stocked):
    """**M1·M2가 이 테스트를 깬다.**"""
    store, timeline, episodes = stocked
    bundle = build_episode_prompt(episodes[1], timeline, store,
                                  contract=CONTRACT_V3)
    assert bundle.prompt_version == PROMPT_VERSION_V3
    for key in DIALOGUE_KEYS:
        assert key not in bundle.text, key
    assert "summary" in bundle.text


def test_c_v3_does_not_ask_for_a_placeholder_value(stocked):
    """빈 배열·null·"없음"을 채우라고 하면 그 값 자체가 내용처럼 남는다(OPEN-10)."""
    store, timeline, episodes = stocked
    text = build_episode_prompt(episodes[1], timeline, store,
                               contract=CONTRACT_V3).text
    for forbidden in ("[]", "null", '""', "없음"):
        assert forbidden not in text, forbidden


def test_c_v3_keeps_the_evidence_block_split(stocked):
    """v3는 근거 분리를 바꾸지 않는다 — 바꾸면 OPEN-9로 되돌아간다."""
    store, timeline, episodes = stocked
    assert CONTRACT_V3["evidence_blocks"] == CONTRACT["evidence_blocks"]
    text = build_episode_prompt(episodes[1], timeline, store,
                               contract=CONTRACT_V3).text
    assert "[근거]" in text
    assert "근거 블록에 있는 것만 사실로 적는다." in text


def test_c_an_unknown_contract_name_is_an_error():
    """조용히 v2로 떨어지면 어느 계약으로 돌았는지 사후에 알 수 없다."""
    assert resolve_contract("v2") is CONTRACT
    assert resolve_contract("v3") is CONTRACT_V3
    with pytest.raises(PromptError, match="unknown prompt contract"):
        resolve_contract("v4")


def test_c_a_contract_without_output_instructions_is_refused(stocked):
    store, timeline, episodes = stocked
    invented = {**CONTRACT_V3, "version": "episode_content_v9"}
    with pytest.raises(PromptError, match="no output instructions"):
        build_episode_prompt(episodes[1], timeline, store, contract=invented)


def test_c_b03_still_does_not_call_a_model():
    """v3를 넣으면서 B-02 책임이 새어 들어오지 않았다."""
    code = code_only(SRC)
    for forbidden in ("transformers", "torch", "temperature", "max_new_tokens"):
        assert forbidden not in code, forbidden


# ── S 합성: normal ───────────────────────────────────────────────────────
V3_PAYLOADS = ({"summary": "두 여성이 해변에 앉아 주변을 둘러본다."},
               {"summary": "두 여성이 가방을 열고 음료를 나눠 마신다."})


def test_s_normal_v3_episodes_are_eligible_for_presentation(tmp_path):
    summary, fake, run = _run(tmp_path, payloads=V3_PAYLOADS,
                              contract_name="v3")
    document = _canonical(run)
    assert document["prompt"]["prompt_version"] == PROMPT_VERSION_V3
    assert document["prompt"]["prompt_hash"] == contract_hash(CONTRACT_V3)
    assert fake.calls == 2
    for episode in document["episodes"]:
        assert episode["content_status"] == "VALID_PARSE"
        assert episode["summary"]
        assert episode["dialogue_note"] is None
        assert episode["grounding_status"] == "NOT_APPLICABLE"
    metrics = summary["distributions"]["presentation"]
    assert metrics == {**metrics, "episodes": 2, "eligible": 2,
                       "excluded_by_dialogue_grounding": 0,
                       "dialogue_note_present": 0}
    assert V3_PAYLOADS[0]["summary"] in _hwpx_text(run)


def test_s_normal_the_prompt_sent_to_the_model_is_summary_only(tmp_path):
    """계약이 아니라 **실제로 보낸 문자열**을 잰다."""
    sent = []

    class _Recording(_Fake):
        def __call__(self, prompt):
            sent.append(prompt)
            return super().__call__(prompt)

    _run(tmp_path, generate=_Recording(V3_PAYLOADS), contract_name="v3")
    assert sent
    for prompt in sent:
        for key in DIALOGUE_KEYS:
            assert key not in prompt, key


# ── S 합성: rich-STT (GEO-001) · dialogue-heavy (GEO-004) ────────────────
def test_s_rich_stt_speech_still_reaches_the_claim_block(tmp_path):
    """GEO-001 조건 — 자격 있는 발화가 근거로 도달하는 것은 v3에서도 그대로다."""
    speech = {i: "" for i in range(12)}
    speech.update({6: "소스를 두 큰술 넣으면 된다.", 7: "이제 뚜껑을 덮는다."})
    sent = []

    class _Recording(_Fake):
        def __call__(self, prompt):
            sent.append(prompt)
            return super().__call__(prompt)

    _, _, run = _run(tmp_path, asr=speech, payloads=V3_PAYLOADS,
                     generate=_Recording(V3_PAYLOADS), contract_name="v3")
    joined = "\n".join(sent)
    assert "소스를 두 큰술 넣으면 된다." in joined
    assert "seg#6 발화:" in joined
    document = _canonical(run)
    assert any(e["source"] == "stt" for e in document["episodes"])


def test_s_dialogue_heavy_episodes_are_still_processed(tmp_path):
    """GEO-004 조건 — 발화가 지배적인 구간도 처리되고 source 파생이 유지된다."""
    speech = {i: "말하는 사람이 계속 설명을 이어간다 %d." % i for i in range(12)}
    _, _, run = _run(tmp_path, asr=speech, payloads=V3_PAYLOADS,
                     contract_name="v3")
    document = _canonical(run)
    assert len(document["episodes"]) == 2
    assert all(e["content_status"] == "VALID_PARSE" for e in document["episodes"])
    assert all(e["source"] == "stt" for e in document["episodes"])
    assert all(e["grounding_status"] == "NOT_APPLICABLE"
               for e in document["episodes"])


# ── S 합성: sparse eligible == 1 (TRI-005가 v3에서도 최종 권한이다) ──────
def test_s_sparse_safe_mode_still_owns_the_sentence_under_v3(tmp_path):
    """**M4가 이 테스트를 깬다.**

    v3는 summary만 생성하지만, `eligible == 1`에서 모델 summary의 의미 권한은
    여전히 0이다. 정본 문장은 근거 원문이다.
    """
    evidence = "남성이 문을 연다."
    invented = "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."
    sparse = {**{i: "" for i in range(12)}, 9: evidence}
    _, _, run = _run(tmp_path, name="S4", asr=sparse,
                     payloads=({"summary": invented},), contract_name="v3")
    second = _canonical(run)["episodes"][1]
    assert second["summary"] == evidence
    assert second["summary_mode"] == "SPARSE_EVIDENCE_DETERMINISTIC"
    body = _hwpx_text(run)
    for token in ("건물", "훔친", "달아난다"):
        assert token not in body, token
    raw = "".join(path.read_text(encoding="utf-8")
                  for path in (run / "raw/llm").glob("*.raw"))
    assert invented in raw          # 기록은 지우지 않는다 — 권한만 없다


# ── S 합성: no-evidence · parse 실패 ─────────────────────────────────────
def test_s_no_evidence_refuses_the_prompt_under_v3(tmp_path):
    empty = {i: "" for i in range(12)}
    fake = _Fake(({"summary": "이 문장은 나오면 안 된다."},))
    summary, fake, run = _run(tmp_path, name="S5", asr=empty, caption=empty,
                              generate=fake, contract_name="v3")
    assert fake.calls == 0
    document = _canonical(run)
    assert all(e["content_status"] == "EMPTY" and e["summary"] is None
               for e in document["episodes"])
    assert summary["stages"]["S7"]["stage_complete"]
    assert summary["distributions"]["presentation"]["eligible"] == 0


def test_s_a_parse_failure_under_v3_keeps_the_raw(tmp_path):
    fake = _Fake(("{ 깨진 출력", {"summary": "정상 문장이다."}))
    summary, fake, run = _run(tmp_path, generate=fake, contract_name="v3")
    index = json.loads((run / "S2/raw_index.json").read_text(encoding="utf-8"))
    assert index["episodes"][0]["status"] == "PARSE_CONTRACT_FAILURE"
    assert (run / index["episodes"][0]["raw"]).read_text(
        encoding="utf-8") == "{ 깨진 출력"
    document = _canonical(run)
    assert document["episodes"][0]["content_status"] == "PARSE_CONTRACT_FAILURE"
    assert document["episodes"][1]["summary"] == "정상 문장이다."
    assert summary["distributions"]["presentation"]["eligible"] == 1


def test_s_an_extra_dialogue_key_under_v3_is_not_silently_taken(tmp_path):
    """모델이 계약에 없는 키를 내면 그것이 검증 없이 표현으로 새면 안 된다."""
    payloads = ({"summary": "정상 문장이다.",
                 "dialogue_note": "계약에 없는 값이다.", "stt_cites": [1]},
                {"summary": "두 번째 문장이다."})
    summary, _, run = _run(tmp_path, payloads=payloads, contract_name="v3")
    first = _canonical(run)["episodes"][0]
    # 계약에 없어도 **판정을 거친다.** v3가 검사를 우회하는 통로가 되지 않는다.
    assert first["grounding_status"].startswith("FAIL")
    assert first["dialogue_note"] is None            # 실패한 dialogue는 제거된다
    assert first["summary"] == "정상 문장이다."        # 요약은 지워지지 않는다
    # 그 결과 이 구간은 표현에서 빠진다 — v3에서 이 값이 0이어야 하는 이유다.
    assert summary["distributions"]["presentation"][
        "excluded_by_dialogue_grounding"] == 1


# ── S 합성: v2 회귀 ──────────────────────────────────────────────────────
def test_s_the_v2_arm_is_unchanged(tmp_path):
    """같은 코드에서 v2로 부르면 예전 동작이다 — dialogue를 생성하고 판정받는다."""
    payloads = ({"summary": "두 여성이 해변에 앉아 있다."},
                {"summary": "두 여성이 음료를 나눠 마신다.",
                 "dialogue_note": "소스를 넣으면 된다고 말한다.",
                 "stt_cites": [9]})
    summary, _, run = _run(tmp_path, payloads=payloads)      # 계약 미지정 = v2
    document = _canonical(run)
    assert document["prompt"]["prompt_version"] == PROMPT_VERSION
    assert document["prompt"]["prompt_hash"] == V2_CONTRACT_HASH
    assert document["episodes"][1]["dialogue_note"]
    assert summary["distributions"]["presentation"]["dialogue_note_present"] == 1


def test_s_the_mechanism_metric_is_not_vacuous(tmp_path):
    """지표가 늘 0이면 R1의 0은 아무 뜻이 없다. v2에서 실제로 세는지 잰다."""
    payloads = ({"summary": "두 여성이 해변에 앉아 있다.",
                 "dialogue_note": "근거에 없는 3시간 42분을 말한다.",
                 "stt_cites": [1]},
                {"summary": "두 여성이 음료를 나눠 마신다."})
    summary, _, _ = _run(tmp_path, payloads=payloads)
    metrics = summary["distributions"]["presentation"]
    assert metrics["excluded_by_dialogue_grounding"] == 1
    assert metrics["eligible"] == 1
    assert metrics["excluded_episode_ids"] == ["EP01"]


def test_s_the_metric_reproduces_the_r0_baseline():
    """실측 2/41을 이 지표로 재현한다 — 지표가 baseline과 같은 것을 재는가."""
    document = json.loads(
        (b2.ROOT / "runs/b2_full_4090/aar_canonical.json").read_text(
            encoding="utf-8"))
    metrics = b2._presentation_metrics(document)
    assert metrics["episodes"] == 41
    assert metrics["eligible"] == 2
    assert metrics["excluded_by_dialogue_grounding"] == 38
