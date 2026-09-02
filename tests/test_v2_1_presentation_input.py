"""C-01 표현 계층 입구 — 정본 하나만 들어온다 (Gate C).

Gate C에서 새 기능보다 먼저 잠가야 하는 것은 **우회 경로**다. OPEN-11이
non-blocking인 근거는 "grounding을 지나야만 내용이 밖으로 나간다"는 전제인데,
그 전제를 깨뜨릴 수 있는 층이 표현 계층이다.

```
층 1  import 차단   표현 모듈은 grounding 이전 모듈을 import조차 하지 않는다
층 2  데이터 차단   FAIL · NOT_APPLICABLE인데 dialogue가 실린 문서는 거부한다
```

층 1만으로는 부족하다 — **정직한 코드만 막기 때문**이다. 정본을 손으로 고치거나
앞 계층 버그로 dialogue가 남은 문서가 오면 import 가드는 아무것도 못 한다.
"""
import ast
import json
from pathlib import Path

import pytest

from v2_1_aar import SCHEMA
from v2_1_gate_b import run_pipeline
from v2_1_grounding import FAIL_NO_SUPPORT, NOT_APPLICABLE, PASS
from v2_1_presentation_input import (
    FORBIDDEN_UPSTREAM,
    PRESENTATION_SUMMARY_STATUSES,
    PresentationEpisode,
    PresentationInputError,
    presentation_input,
    summary_eligible_for_presentation,
)

MODULE = Path(__file__).resolve().parents[1] / "src/v2_1_presentation_input.py"

#: 두 상태를 한 문서에 담는다 — EP01은 dialogue 없음(NOT_APPLICABLE),
#: EP02는 근거 있는 dialogue(PASS). 한쪽만 있으면 interlock 검사가 헐거워진다.
CLEAN = ({"summary": "제나가 창고를 연다."},
         {"summary": "정리하고 나간다.", "dialogue_note": "다음 장소를 정한다.",
          "stt_cites": [9]})


def _document(tmp_path, payloads=CLEAN, **kwargs):
    return run_pipeline(tmp_path, payloads, **kwargs).document


# ── 정상 경로 ────────────────────────────────────────────────────────────
def test_a_validated_canonical_document_is_accepted(tmp_path):
    presented = presentation_input(_document(tmp_path))
    assert presented.schema == SCHEMA
    assert presented.video_id
    assert len(presented.episodes) == 2


def test_episodes_keep_canonical_order(tmp_path):
    presented = presentation_input(_document(tmp_path))
    ids = [e.episode_id for e in presented.episodes]
    assert ids == sorted(ids)


def test_lookup_by_episode_id(tmp_path):
    presented = presentation_input(_document(tmp_path))
    assert presented.episode("EP01").episode_id == "EP01"
    with pytest.raises(KeyError):
        presented.episode("EP99")


def test_the_document_is_not_mutated(tmp_path):
    document = _document(tmp_path)
    before = json.dumps(document, ensure_ascii=False, sort_keys=True)
    presentation_input(document)
    assert json.dumps(document, ensure_ascii=False, sort_keys=True) == before


# ── 정본이 아닌 것은 들어오지 못한다 ─────────────────────────────────────
def test_a_pre_grounding_object_is_refused(tmp_path):
    """binding·content 객체를 그대로 넘기는 것이 가장 흔한 우회다."""
    pipeline = run_pipeline(tmp_path, CLEAN)
    for upstream in (pipeline.bindings[0], pipeline.results[0], pipeline.grounded[0]):
        with pytest.raises(PresentationInputError):
            presentation_input(upstream)


def test_a_bare_episode_list_is_refused(tmp_path):
    document = _document(tmp_path)
    with pytest.raises(PresentationInputError):
        presentation_input(document["episodes"])


def test_a_foreign_schema_is_refused(tmp_path):
    document = _document(tmp_path)
    document["schema"] = "report_presentation_v1"
    with pytest.raises(PresentationInputError):
        presentation_input(document)


def test_an_invalid_canonical_document_is_refused(tmp_path):
    """정본 검증을 통과하지 못한 문서는 표현으로 넘어가지 않는다."""
    document = _document(tmp_path)
    document["episodes"] = document["episodes"][:1]
    with pytest.raises(PresentationInputError):
        presentation_input(document)


def test_the_refusal_names_the_canonical_failure(tmp_path):
    document = _document(tmp_path)
    document["episodes"] = document["episodes"][:1]
    with pytest.raises(PresentationInputError) as excinfo:
        presentation_input(document)
    assert "GAP" in str(excinfo.value) or "END_MISMATCH" in str(excinfo.value)


# ── OPEN-11 interlock ────────────────────────────────────────────────────
def test_dialogue_removed_by_grounding_may_not_return(tmp_path):
    """FAIL인데 dialogue가 실려 있으면 거부한다 — OPEN-11이 부활하는 지점이다."""
    document = _document(tmp_path)
    episode = document["episodes"][0]
    episode["grounding_status"] = FAIL_NO_SUPPORT
    episode["dialogue_note"] = "['seg#8', 'seg#10']"
    with pytest.raises(PresentationInputError) as excinfo:
        presentation_input(document)
    assert episode["episode_id"] in str(excinfo.value)


def test_not_applicable_with_dialogue_is_refused(tmp_path):
    document = _document(tmp_path)
    episode = document["episodes"][0]
    episode["grounding_status"] = NOT_APPLICABLE
    episode["dialogue_note"] = "무발화 구간인데 발화가 있다"
    with pytest.raises(PresentationInputError):
        presentation_input(document)


def test_a_passing_episode_keeps_its_dialogue(tmp_path):
    document = _document(tmp_path)
    passing = [e for e in document["episodes"] if e["grounding_status"] == PASS]
    assert passing, "PASS 사례가 없으면 이 검사는 무의미하다"
    presented = presentation_input(document)
    for episode in passing:
        assert presented.episode(episode["episode_id"]).dialogue_note == \
            episode["dialogue_note"]


def test_failed_episodes_survive_without_dialogue(tmp_path):
    """실패했다고 episode를 버리지 않는다 — 구조는 유지하고 dialogue만 없다."""
    document = _document(tmp_path, ({"summary": "제나가 42번 상자를 연다."},
                                    {"summary": "정리한다."}))
    presented = presentation_input(document)
    assert len(presented.episodes) == len(document["episodes"])
    for episode in presented.episodes:
        if episode.grounding_status != PASS:
            assert episode.dialogue_note is None
        assert episode.summary


def test_grounding_status_is_carried_verbatim(tmp_path):
    document = _document(tmp_path)
    presented = presentation_input(document)
    for raw, episode in zip(document["episodes"], presented.episodes):
        assert episode.grounding_status == raw["grounding_status"]


# ── 표현이 볼 수 있는 것은 정본에 있는 것뿐이다 ─────────────────────────
def test_presentation_episode_exposes_no_upstream_surface():
    """raw·timeline·binding으로 되돌아갈 손잡이를 만들지 않는다."""
    fields = set(PresentationEpisode.__dataclass_fields__)
    assert not fields & {"raw", "raw_ref", "store", "timeline", "binding",
                         "cites", "evidence", "parse_result"}


def test_the_module_does_not_import_pre_grounding_layers():
    """A-09가 A-08을 import하지 않게 한 것과 같은 논리다.

    import 문만 본다 — 문자열 상수나 주석이 자기 가드를 건드리지 않게.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & set(FORBIDDEN_UPSTREAM), sorted(imported)


def test_the_forbidden_list_covers_every_pre_grounding_module():
    assert set(FORBIDDEN_UPSTREAM) == {
        "v2_1_content", "v2_1_binding", "v2_1_raw_store", "v2_1_parse",
        "v2_1_timeline",
    }


# ── OPEN-12 표현 자격 predicate ──────────────────────────────────────────
def _episode(grounding_status, summary="구간 요약.", content_status="VALID_PARSE"):
    return PresentationEpisode(
        episode_id="EP01", start_seg=0, end_seg=1, start_sec=0.0, end_sec=10.0,
        source="stt", content_status=content_status, summary=summary,
        dialogue_note=None, grounding_status=grounding_status,
        anchor_cites=(), provenance=(),
    )


def test_open_12_pass_summary_is_presentation_eligible():
    assert summary_eligible_for_presentation(_episode(PASS))


def test_open_12_not_applicable_summary_is_presentation_eligible():
    """dialogue가 없다는 이유로 보고서 문장이 사라지면 안 된다."""
    assert summary_eligible_for_presentation(_episode(NOT_APPLICABLE))


def test_open_12_failed_summary_is_not_eligible():
    for status in (FAIL_NO_SUPPORT, "FAIL_REFERENCE", "FAIL_UNSUPPORTED"):
        assert not summary_eligible_for_presentation(_episode(status))


def test_open_12_an_unknown_status_is_not_eligible():
    """allowlist다 — 새 상태가 생기면 기본값은 '쓰지 않음'이다."""
    for status in ("PENDING", "UNKNOWN", "SKIPPED", ""):
        assert not summary_eligible_for_presentation(_episode(status))


def test_open_12_an_empty_summary_is_not_eligible():
    for summary in (None, "", "   "):
        assert not summary_eligible_for_presentation(_episode(PASS, summary))


def test_open_12_a_broken_content_status_is_not_eligible():
    assert not summary_eligible_for_presentation(
        _episode(PASS, content_status="PARSE_CONTRACT_FAILURE")
    )


def test_open_12_eligibility_does_not_promote_not_applicable_to_pass():
    """자격이 같다고 판정이 같아진 것은 아니다 — 상태는 그대로 남는다."""
    episode = _episode(NOT_APPLICABLE)
    assert episode.grounding_status == NOT_APPLICABLE
    assert NOT_APPLICABLE in PRESENTATION_SUMMARY_STATUSES
    assert PASS != NOT_APPLICABLE
