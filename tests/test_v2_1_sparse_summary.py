"""TRI-005 remediation (C3) — sparse-evidence deterministic summary.

```
eligible 0   프롬프트가 거부한다 — safe mode에 들어오지 않는다 (ERR-009)
eligible 1   모델 요약의 정본 권한이 0이다 — 근거 원문이 정본이다
eligible 2+  기존 경로 그대로 — GRD-004 P1 한계가 남는다
```

사전등록의 T1~T7을 그대로 잰다.
`docs/finalization/V2_1_TRI_005_REMEDIATION_PREREG_2026-09-02.md`

counterexample 자체의 회귀 고정은 `test_v2_1_tri_005_gap.py`에 따로 있다. 이 파일은
**계약**을 재고, 그 파일은 **사건**을 잠근다 — 둘을 합치지 않는다.
"""
import json
from pathlib import Path

import pytest

from v2_1_aar import load_aar, serialize_aar, validate_aar
from v2_1_gate_b import run_pipeline
from v2_1_grounding import (
    FAIL_UNSUPPORTED,
    NOT_APPLICABLE,
    PASS,
    GroundedEpisode,
)
from v2_1_prompt import PromptError, build_episode_prompt, split_evidence
from v2_1_sparse_summary import (
    MODEL_ABSTRACTIVE,
    SPARSE_EVIDENCE_DETERMINISTIC,
    SUMMARY_MODES,
    sparse_claim_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
TWO = ((0, 5), (6, 11))

#: 유효 발화 한 건. 나머지는 공백이다.
SPARSE_ASR = {**{i: "" for i in range(12)}, 9: "남성이 문을 연다."}
EVIDENCE = "남성이 문을 연다."

#: 유효 한 건 + SUSPECT 다섯. **자격 있는 것은 여전히 하나뿐이다.**
#: 한자 3자 이상은 SUSPECT(foreign_script)이고 claim support가 아니다.
VALID_PLUS_SUSPECT = {
    **{i: "" for i in range(6)},
    6: "漢字漢字", 7: "漢字漢字", 8: "漢字漢字",
    9: EVIDENCE,
    10: "漢字漢字", 11: "漢字漢字",
}

#: 근거가 하나도 자격을 얻지 못하는 구간(전 채널 공백) — S5.
INVENTED = "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."
INVENTED_NUMBER = "남성이 문 3개를 연다."

#: 발화가 다듬어지지 않은 원문. 이 티켓에서 문법을 고치지 않는다.
AWKWARD_ASR = {**{i: "" for i in range(12)}, 9: "어 그 문 여는 거 그거 맞지 어"}


def _run(tmp_path, summary, *, asr=None, name="S4", dialogue=None, cites=()):
    payload = {"summary": summary}
    if dialogue is not None:
        payload["dialogue_note"] = dialogue
        if cites:
            payload["stt_cites"] = list(cites)
    return run_pipeline(tmp_path, ({"summary": "앞 구간."}, payload),
                        name=name, spans=TWO,
                        asr_overrides=SPARSE_ASR if asr is None else asr)


def _second(pipeline):
    return pipeline.document["episodes"][1]


# ── T1 · T2 서사와 수량 발명 ─────────────────────────────────────────────
@pytest.mark.parametrize("summary,invented", [
    (INVENTED, ("건물", "훔친", "달아난다")),
    (INVENTED_NUMBER, ("3개",)),
])
def test_t1_t2_invention_never_reaches_the_canonical_summary(
        tmp_path, summary, invented):
    episode = _second(_run(tmp_path, summary))
    assert episode["summary"] == EVIDENCE
    assert episode["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC
    for token in invented:
        assert token not in episode["summary"], token


def test_the_model_summary_is_never_compared_with_the_evidence(tmp_path):
    """의미 비교를 하지 않는다 — 같은 문장을 냈든 지어냈든 정본은 근거 원문이다.

    비교를 시작하면 C2(entailment verifier)의 축소판이 된다. 그래서 두 경우의
    정본이 **같은 문자열**이어야 한다.
    """
    same = _second(_run(tmp_path / "a", EVIDENCE))
    invented = _second(_run(tmp_path / "b", INVENTED))
    assert same["summary"] == invented["summary"] == EVIDENCE
    assert same["summary_mode"] == invented["summary_mode"] == \
        SPARSE_EVIDENCE_DETERMINISTIC


# ── T3 근거 범위 안의 내용은 사라지지 않는다 ─────────────────────────────
def test_t3_valid_sparse_content_is_not_over_isolated(tmp_path):
    episode = _second(_run(tmp_path, EVIDENCE))
    assert episode["summary"] == EVIDENCE
    assert episode["content_status"] == "VALID_PARSE"
    assert episode["grounding_status"] == NOT_APPLICABLE


def test_the_evidence_text_is_copied_verbatim(tmp_path):
    """어색한 발화도 다듬지 않는다 — 다듬으면 생성 권한이 다시 생긴다."""
    episode = _second(_run(tmp_path, INVENTED, asr=AWKWARD_ASR))
    assert episode["summary"] == AWKWARD_ASR[9]


def test_no_connective_or_lead_in_is_added(tmp_path):
    episode = _second(_run(tmp_path, INVENTED))
    for phrase in ("근거에 따르면", "영상에서는", "그리고", "그 후", "따라서",
                   "이후", "때문에", "이를 통해"):
        assert phrase not in episode["summary"], phrase


# ── T4 VALID + SUSPECT ───────────────────────────────────────────────────
def test_t4_only_the_eligible_evidence_gets_summary_authority(tmp_path):
    pipeline = _run(tmp_path, INVENTED, asr=VALID_PLUS_SUSPECT)
    episode = _second(pipeline)
    assert episode["summary"] == EVIDENCE
    assert "漢字" not in episode["summary"]
    assert episode["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC


def test_t4_suspect_evidence_is_still_preserved(tmp_path):
    """정본 문장에 쓰지 않는 것과 근거를 지우는 것은 다르다(OPEN-9)."""
    pipeline = _run(tmp_path, INVENTED, asr=VALID_PLUS_SUSPECT)
    suspect = [ref for entry in pipeline.timeline for ref in entry.asr_refs
               if ref.status == "SUSPECT"]
    assert len(suspect) == 5
    assert all(ref.preserved and not ref.usable_for_claims for ref in suspect)
    binding = pipeline.bindings[1]
    assert sum(1 for e in binding.evidence if e.sanitation_status == "SUSPECT") == 5


# ── T5 eligible 0은 다른 계약이다 ────────────────────────────────────────
def test_t5_zero_eligible_evidence_never_enters_safe_mode(tmp_path):
    """프롬프트가 먼저 거부한다 — safe mode가 ERR-009를 가로채지 않는다."""
    pipeline = _run(tmp_path, INVENTED, asr={i: "" for i in range(12)}, name="S5")
    for episode in pipeline.episodes:
        assert sparse_claim_evidence(episode, pipeline.timeline) is None
        with pytest.raises(PromptError):
            build_episode_prompt(episode, pipeline.timeline, pipeline.store)
    # harness는 프롬프트를 우회해 payload를 직접 넣는다. 그 경우에도 safe mode는
    # 개입하지 않고 출처 표기는 모델 그대로다.
    assert _second(pipeline)["summary_mode"] == MODEL_ABSTRACTIVE


# ── T6 구조 불변 ─────────────────────────────────────────────────────────
def test_t6_canonical_structure_is_untouched_by_safe_mode(tmp_path):
    plain = _run(tmp_path / "a", EVIDENCE, asr={i: "말." for i in range(12)})
    sparse = _run(tmp_path / "b", INVENTED)

    def projection(pipeline):
        return tuple((e["episode_id"], e["start_seg"], e["end_seg"],
                      e["start_sec"], e["end_sec"])
                     for e in pipeline.document["episodes"])

    assert projection(plain) == projection(sparse)
    assert validate_aar(sparse.document).ok
    assert _second(plain)["summary_mode"] == MODEL_ABSTRACTIVE
    assert _second(sparse)["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC


# ── T7 결정성 ────────────────────────────────────────────────────────────
def test_t7_the_sparse_summary_is_deterministic_across_reruns(tmp_path):
    seen = set()
    for index in range(3):
        episode = _second(_run(tmp_path / ("run%d" % index), INVENTED))
        seen.add((episode["summary"], episode["summary_mode"]))
    assert seen == {(EVIDENCE, SPARSE_EVIDENCE_DETERMINISTIC)}


# ── 경계: eligible 2+는 건드리지 않는다 ──────────────────────────────────
def test_two_eligible_refs_keep_the_model_summary(tmp_path):
    """v1은 일반 semantic entailment를 해결하지 않는다 — 여기서는 그대로 남는다."""
    two = {**{i: "" for i in range(12)}, 9: EVIDENCE, 10: "문이 닫힌다."}
    episode = _second(_run(tmp_path, INVENTED, asr=two))
    assert episode["summary"] == INVENTED
    assert episode["summary_mode"] == MODEL_ABSTRACTIVE


def test_the_count_comes_from_the_prompt_contract(tmp_path):
    """개수는 split_evidence로 센다 — timeline ref나 binding evidence가 아니다."""
    pipeline = _run(tmp_path, INVENTED, asr=VALID_PLUS_SUSPECT)
    episode = pipeline.episodes[1]
    claim, context = split_evidence(episode, pipeline.timeline)
    assert len(claim) == 1 and len(context) == 5
    assert sparse_claim_evidence(episode, pipeline.timeline) is claim[0]
    # 보존된 근거 전량은 6건이다. 그 수로 셌다면 sparse가 아니게 된다.
    assert len(pipeline.bindings[1].evidence) == 6


# ── summary_mode는 provenance이지 판정이 아니다 ─────────────────────────
def test_safe_mode_does_not_re_judge_grounding(tmp_path):
    """dialogue 실패는 그대로 실패다 — 근거 투영이 그것을 통과시키지 않는다."""
    pipeline = _run(tmp_path, INVENTED, dialogue="문 5개를 연다고 말한다.",
                    cites=(9,))
    episode = _second(pipeline)
    assert episode["grounding_status"] == FAIL_UNSUPPORTED
    assert episode["dialogue_note"] is None
    assert episode["summary"] == EVIDENCE
    assert episode["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC


def test_safe_mode_does_not_promote_a_failed_episode(tmp_path):
    """내용이 실패한 구간에는 손대지 않는다 — 실패는 상태로 남는다(B-04)."""
    pipeline = run_pipeline(tmp_path, ({"summary": "앞 구간."}, "{"),
                            name="S4", spans=TWO, asr_overrides=SPARSE_ASR)
    episode = _second(pipeline)
    assert episode["content_status"] == "PARSE_CONTRACT_FAILURE"
    assert episode["summary"] is None
    assert episode["summary_mode"] == MODEL_ABSTRACTIVE


def test_a_passing_dialogue_survives_safe_mode(tmp_path):
    pipeline = _run(tmp_path, INVENTED, dialogue="문을 연다고 말한다.", cites=(9,))
    episode = _second(pipeline)
    assert episode["grounding_status"] == PASS
    assert episode["dialogue_note"] == "문을 연다고 말한다."


# ── 정본 표기 계약 ───────────────────────────────────────────────────────
def test_the_mode_vocabulary_is_a_closed_set():
    assert SUMMARY_MODES == (MODEL_ABSTRACTIVE, SPARSE_EVIDENCE_DETERMINISTIC)


def test_the_grounding_default_matches_the_mode_vocabulary():
    """어휘의 주인은 sparse 모듈이다. grounding의 기본값이 그것과 갈리면 잡는다."""
    assert GroundedEpisode.__dataclass_fields__["summary_mode"].default == \
        MODEL_ABSTRACTIVE


def test_an_unknown_mode_is_refused_not_silently_downgraded(tmp_path):
    document = _run(tmp_path, INVENTED).document
    document["episodes"][1]["summary_mode"] = "SOMETHING_ELSE"
    verdict = validate_aar(document)
    assert not verdict.ok
    assert any("unknown summary_mode" in f for f in verdict.failures)


def test_the_mode_survives_serialization(tmp_path):
    document = _run(tmp_path, INVENTED).document
    restored = load_aar(serialize_aar(document))
    assert restored["episodes"][1]["summary_mode"] == SPARSE_EVIDENCE_DETERMINISTIC
    assert json.loads(serialize_aar(document)) == document


def test_the_mode_is_not_a_grounding_or_content_status():
    """세 축을 섞지 않는다 — 각각 다른 것을 말한다."""
    from v2_1_grounding import GROUNDING_STATUSES
    from v2_1_parse import PARSE_STATUSES

    assert not set(SUMMARY_MODES) & set(GROUNDING_STATUSES)
    assert not set(SUMMARY_MODES) & set(PARSE_STATUSES)


def test_the_prereg_and_the_implementation_agree_on_the_vocabulary():
    text = (ROOT / "docs/finalization/"
            "V2_1_TRI_005_REMEDIATION_PREREG_2026-09-02.md").read_text(
        encoding="utf-8")
    for mode in SUMMARY_MODES:
        assert mode in text, mode
