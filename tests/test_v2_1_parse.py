"""A-04 parse contract layer — 표기는 받아들이고 존재는 지어내지 않는다.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-04
계약: SPEC §12 `RAW → NORMALIZE → PARSE → SEMANTIC VALIDATION`

이 프로젝트 최악 사고 셋이 전부 여기서 났다.

```
2026-08-29  v2 canary   모델이 맨 배열로 답해 경계 0개 → 영상 전체가 사건 하나
2026-08-29  BCS         "seg#55"를 못 읽어 dialogue_note 14건을 잘못 버림
2026-08-29  BCS         깨진 JSON이 문장 경로로 흘러 raw JSON이 summary에 실림
```

앞의 둘은 **표기를 계약으로 착각**한 것이고, 셋째는 **구조 fallback**이다.
A-04는 앞의 둘을 받아들이고 셋째를 금지한다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_parse import (
    EMPTY,
    MODEL_FAILURE,
    PARSE_CONTRACT_FAILURE,
    VALID_PARSE,
    SegmentRegistry,
    model_failure,
    normalize_segment_ref,
    parse_json_payload,
    parse_reference_list,
    status_for_store_outcome,
)
from v2_1_raw_store import RawStore
from v2_1_segments import legacy_segments_to_canonical

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_parse.py"
INSTRUCTION_ECHO = "네, 알겠습니다. 다음은 주어진 요청에 따라 한 문장의 한국어로 객관적인 묘사입니다."


@pytest.fixture
def registry():
    return SegmentRegistry(
        legacy_segments_to_canonical(
            [{"idx": i, "start": i * 5, "end": i * 5 + 5} for i in range(60)]
        )
    )


# ── SCH-008 표기 정규화 ──────────────────────────────────────────────────
@pytest.mark.parametrize(
    "value", [55, "55", " 55 ", "seg#55", "seg #55", " SEG # 55 ", "seg55"]
)
def test_sch_008_notation_variants_normalize_to_one_value(value):
    assert normalize_segment_ref(value) == 55


@pytest.mark.parametrize("value", [None, True, False, "", "seg#", "abc", 55.5, "5.5", []])
def test_sch_008_non_references_are_not_invented(value):
    assert normalize_segment_ref(value) is None


def test_sch_008_negative_reference_is_not_a_segment():
    assert normalize_segment_ref(-1) is None
    assert normalize_segment_ref("seg#-1") is None


def test_sch_008_normalized_cites_are_deduped_and_sorted(registry):
    result = parse_json_payload(
        json.dumps({"summary": "요약", "stt_cites": ["seg#12", 12, "3"]}),
        registry,
        reference_keys=("stt_cites",),
    )
    assert result.status == VALID_PARSE
    assert result.references["stt_cites"] == [3, 12]


# ── 정규화는 존재를 만들지 않는다 ────────────────────────────────────────
def test_syntactically_valid_but_nonexistent_reference_is_not_parse_success(registry):
    result = parse_json_payload(
        json.dumps({"summary": "요약", "stt_cites": ["seg#999999"]}),
        registry,
        reference_keys=("stt_cites",),
    )
    assert result.status == PARSE_CONTRACT_FAILURE
    assert result.reason == "unresolved_reference"
    assert result.unresolved == [999999]
    assert result.value is None


def test_registry_never_clamps_or_snaps(registry):
    with pytest.raises(KeyError):
        registry.resolve("seg#60")
    assert registry.resolve("seg#59") == 59
    assert 60 not in registry


def test_one_bad_reference_fails_the_whole_payload(registry):
    """일부만 살려 통과시키면 근거가 조용히 줄어든다."""
    result = parse_json_payload(
        json.dumps({"summary": "요약", "stt_cites": [3, "seg#999999"]}),
        registry,
        reference_keys=("stt_cites",),
    )
    assert result.status == PARSE_CONTRACT_FAILURE
    assert result.unresolved == [999999]


# ── SCH-004 malformed raw ────────────────────────────────────────────────
def test_sch_004_malformed_json_is_a_contract_failure(registry):
    result = parse_json_payload('{"summary": "잘린 JSON', registry)
    assert result.status == PARSE_CONTRACT_FAILURE
    assert result.reason == "not_json_object"
    assert result.value is None


def test_sch_004_no_structure_fallback(registry):
    """깨진 JSON을 문장으로 건져 올리지 않는다 — 2026-08-29 EP21 사고."""
    broken = '{"summary": "해변에서 소스를 넣었다", "dialogue_note": '
    result = parse_json_payload(broken, registry)
    assert result.status == PARSE_CONTRACT_FAILURE
    assert result.value is None
    assert "salvage" not in SRC.read_text(encoding="utf-8")


def test_sch_004_bare_sentence_is_not_an_object(registry):
    result = parse_json_payload("두 여성이 해변에 앉아 있습니다.", registry)
    assert result.status == PARSE_CONTRACT_FAILURE
    assert result.reason == "not_json_object"


def test_json_array_is_not_a_payload_object(registry):
    result = parse_json_payload('[{"summary": "요약"}]', registry)
    assert result.status == PARSE_CONTRACT_FAILURE


# ── SCH-005 EMPTY ≠ PARSE_FAILED ─────────────────────────────────────────
@pytest.mark.parametrize("raw", ["", "   ", "\n\t "])
def test_sch_005_blank_output_is_empty_not_a_failure(registry, raw):
    result = parse_json_payload(raw, registry)
    assert result.status == EMPTY
    assert result.status != PARSE_CONTRACT_FAILURE


def test_sch_005_empty_object_is_empty(registry):
    assert parse_json_payload("{}", registry).status == EMPTY


def test_sch_005_object_with_only_blank_values_is_empty(registry):
    result = parse_json_payload(json.dumps({"summary": "   ", "note": ""}), registry)
    assert result.status == EMPTY


def test_sch_005_empty_is_not_model_failure(registry):
    assert parse_json_payload("", registry).status != MODEL_FAILURE


# ── SCH-009 MODEL_FAILURE는 호출자만 낸다 ────────────────────────────────
def test_sch_009_model_failure_is_declared_never_inferred(registry):
    declared = model_failure(RuntimeError("CUDA out of memory"))
    assert declared.status == MODEL_FAILURE
    assert "CUDA" in declared.error
    assert declared.error_type == "RuntimeError"
    for raw in ("", "{}", "garbage", '{"a":'):
        assert parse_json_payload(raw, registry).status != MODEL_FAILURE


def test_sch_009_parse_contract_failure_is_not_model_failure(registry):
    assert PARSE_CONTRACT_FAILURE != MODEL_FAILURE
    result = parse_json_payload('{"a":', registry)
    assert result.status == PARSE_CONTRACT_FAILURE


def test_sch_009_status_vocabulary_is_closed():
    import v2_1_parse

    assert set(v2_1_parse.PARSE_STATUSES) == {
        MODEL_FAILURE,
        PARSE_CONTRACT_FAILURE,
        EMPTY,
        VALID_PARSE,
    }


def test_sch_009_store_outcome_maps_onto_the_contract_vocabulary(tmp_path):
    """A-03과 A-04가 서로 다른 어휘를 갖지 않도록 잇는다."""
    store = RawStore(tmp_path / "raw", run_id="r", video_id="v")
    ok = store.store_then_parse(
        json.loads, segment_id=1, source_type="llm", producer="p",
        producer_version="v", payload='{"a": 1}',
    )
    bad = store.store_then_parse(
        json.loads, segment_id=2, source_type="llm", producer="p",
        producer_version="v", payload='{"a":',
    )
    assert status_for_store_outcome(ok) == VALID_PARSE
    assert status_for_store_outcome(bad) == PARSE_CONTRACT_FAILURE


# ── SCH-007 parser는 sanitation을 하지 않는다 ────────────────────────────
def test_sch_007_instruction_echo_parses_fine(registry):
    """오염 판정은 A-05 소관이다. parse에서 걸러 버리면 근거가 사라진다."""
    result = parse_json_payload(json.dumps({"summary": INSTRUCTION_ECHO}), registry)
    assert result.status == VALID_PARSE
    assert result.value["summary"] == INSTRUCTION_ECHO


def test_sch_007_foreign_script_parses_fine(registry):
    payload = json.dumps({"summary": "夕阳西下，天空被染成了温暖的橙红色。"})
    assert parse_json_payload(payload, registry).status == VALID_PARSE


def test_sch_007_repeated_text_parses_fine(registry):
    payload = json.dumps({"summary": "나 잡았어!!! 나 잡았어!!!"})
    assert parse_json_payload(payload, registry).status == VALID_PARSE


def test_sch_007_parser_does_not_import_sanitation():
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("is_corrupted_caption", "is_subtitle_credit", "SUSPECT",
                      "REJECTED", "sanitize"):
        assert forbidden not in src, "parse 계층이 sanitation을 하고 있다: " + forbidden


def test_parser_does_not_modify_payload_text(registry):
    text = "  앞뒤 공백과 줄바꿈\r\n이 있는 요약  "
    result = parse_json_payload(json.dumps({"summary": text}), registry)
    assert result.value["summary"] == text


# ── 맨 배열 사고 — 표기로 받아들인다 ─────────────────────────────────────
def test_bare_array_is_accepted_as_notation(registry):
    """2026-08-29 v2 canary: 모델이 네 청크 전부 맨 배열로 답해 경계가 0개가 됐다."""
    wrapped = parse_reference_list(
        json.dumps({"atomic_start_segments": [0, "seg#7", "12"]}),
        "atomic_start_segments",
        registry,
    )
    bare = parse_reference_list(json.dumps([0, "seg#7", "12"]),
                                "atomic_start_segments", registry)
    assert wrapped.status == bare.status == VALID_PARSE
    assert wrapped.value == bare.value == [0, 7, 12]


def test_bare_array_with_unresolved_reference_still_fails(registry):
    result = parse_reference_list(json.dumps([0, 999999]),
                                  "atomic_start_segments", registry)
    assert result.status == PARSE_CONTRACT_FAILURE
    assert result.unresolved == [999999]


def test_empty_reference_list_is_empty_not_valid(registry):
    """경계 0개를 조용히 성공으로 넘기면 영상 전체가 사건 하나가 된다."""
    result = parse_reference_list(json.dumps({"atomic_start_segments": []}),
                                 "atomic_start_segments", registry)
    assert result.status == EMPTY


def test_missing_key_is_a_contract_failure(registry):
    result = parse_reference_list(json.dumps({"other": [1]}),
                                  "atomic_start_segments", registry)
    assert result.status == PARSE_CONTRACT_FAILURE
    assert result.reason == "missing_key"


# ── 계층 경계 ────────────────────────────────────────────────────────────
def test_a04_does_not_implement_later_tickets():
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("manifest", "analysis_mode", "outputs/v2_1",
                      "usable_for_claims", "episode_spans", "GROUNDING"):
        assert forbidden not in src, "다른 티켓 책임을 침범했다: " + forbidden


def test_a04_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)
