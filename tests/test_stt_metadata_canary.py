"""Phase B canary — decoder metadata 회수의 **계측 품질** 계약.

사전등록: `docs/preregistration/STT_EVIDENCE_SANITATION_V1_2026-09-06.md`

```
B-C1 격리 namespace          B-C5 baseline transcript parity
B-C2 provenance 기록          B-C6 Phase-A join 완결
B-C3 metadata 유한·비결측     B-C7 기존 판정 무변경
B-C4 raw→merged lineage 완결  B-C8 제출 산출물 무변경
```

합격 기준은 **signal quality가 아니라 instrumentation quality**다. `no_speech_prob`가
overlap 0에서 높게 나오는지는 통과 조건이 아니다 — 그것을 조건으로 두면 canary를 보고
Phase C 실행 여부를 성능으로 고르는 bias가 생긴다.

aggregation 규칙(max·mean·duration-weighted)은 **이 단계에서 고르지 않는다.**
raw와 lineage를 전부 저장하고 D freeze에서 함께 고정한다.
"""
import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/stt_metadata_canary.py"


def _load():
    spec = importlib.util.spec_from_file_location("stt_metadata_canary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


canary = _load()

RAW = [
    {"id": 0, "text": " 오븐에 2분간 구워주세요 ", "start": 4.86, "end": 8.34,
     "avg_logprob": -0.31, "no_speech_prob": 0.02, "compression_ratio": 1.2},
    {"id": 1, "text": "   ", "start": 9.0, "end": 9.4,
     "avg_logprob": -1.9, "no_speech_prob": 0.8, "compression_ratio": 0.9},
    {"id": 2, "text": "크림치즈를 넣어주세요", "start": 10.8, "end": 12.74,
     "avg_logprob": -0.44, "no_speech_prob": 0.05, "compression_ratio": 1.1},
]
BASELINE = [
    {"text": "오븐에 2분간 구워주세요", "t0": 4.86, "t1": 8.34},
    {"text": "크림치즈를 넣어주세요", "t0": 10.8, "t1": 12.74},
]


# ── production 동등 경로 ─────────────────────────────────────────────────
def test_production_equivalent_strips_and_drops_blanks():
    """m3의 규칙과 같아야 baseline과 비교할 수 있다."""
    produced = canary.production_equivalent(RAW)
    assert [item["text"] for item in produced] == \
        ["오븐에 2분간 구워주세요", "크림치즈를 넣어주세요"]
    assert produced[0]["t0"] == 4.86 and produced[0]["t1"] == 8.34


# ── B-C5 parity ──────────────────────────────────────────────────────────
def test_parity_passes_when_text_matches():
    verdict = canary.parity(BASELINE, canary.production_equivalent(RAW))
    assert verdict["text_equal"] is True
    assert verdict["count_baseline"] == verdict["count_produced"] == 2
    assert verdict["timestamp_max_abs_diff"] == pytest.approx(0.0)
    assert verdict["first_mismatch"] is None


def test_parity_fails_on_any_text_difference():
    changed = [dict(BASELINE[0]), {**BASELINE[1], "text": "크림치즈를 넣어요"}]
    verdict = canary.parity(changed, canary.production_equivalent(RAW))
    assert verdict["text_equal"] is False
    assert verdict["first_mismatch"]["index"] == 1


def test_parity_fails_on_count_difference():
    verdict = canary.parity(BASELINE[:1], canary.production_equivalent(RAW))
    assert verdict["text_equal"] is False
    assert verdict["count_baseline"] == 1 and verdict["count_produced"] == 2


def test_timestamp_drift_is_reported_not_swallowed():
    drifted = [{**BASELINE[0], "t0": 4.8600001}, BASELINE[1]]
    verdict = canary.parity(drifted, canary.production_equivalent(RAW))
    assert verdict["text_equal"] is True
    assert 0 < verdict["timestamp_max_abs_diff"] < 1e-3


# ── B-C4 lineage ─────────────────────────────────────────────────────────
def test_lineage_covers_every_raw_segment_including_dropped():
    rows = canary.lineage(RAW)
    assert [row["raw_whisper_segment_id"] for row in rows] == [0, 1, 2]
    assert [row["merged_stt_id"] for row in rows] == [0, None, 1]
    assert rows[1]["dropped_reason"] == "blank_after_strip"


def test_lineage_carries_metadata_for_dropped_segments_too():
    """버려진 것의 metadata도 남긴다 — 나중에 다른 각도로 볼 때 GPU를 다시 쓰지 않는다."""
    rows = canary.lineage(RAW)
    assert rows[1]["no_speech_prob"] == 0.8


# ── B-C3 metadata 건전성 ─────────────────────────────────────────────────
def test_metadata_health_flags_missing_or_nonfinite():
    healthy = canary.metadata_health(RAW)
    assert healthy["missing"] == {} and healthy["nonfinite"] == {}
    broken = RAW + [{"id": 3, "text": "x", "start": 1.0, "end": 2.0,
                     "avg_logprob": float("nan"), "no_speech_prob": None,
                     "compression_ratio": 1.0}]
    verdict = canary.metadata_health(broken)
    assert verdict["nonfinite"]["avg_logprob"] == 1
    assert verdict["missing"]["no_speech_prob"] == 1


# ── 분포 (판정 아님) ─────────────────────────────────────────────────────
def test_crosstab_summarises_without_choosing_a_threshold():
    rows = [
        {"speech_overlap_ratio": 0.0, "no_speech_prob": 0.7, "avg_logprob": -1.2,
         "compression_ratio": 1.5, "latin_present": True,
         "normalized_repeat_count": 3},
        {"speech_overlap_ratio": 0.9, "no_speech_prob": 0.01, "avg_logprob": -0.2,
         "compression_ratio": 1.1, "latin_present": False,
         "normalized_repeat_count": 1},
    ]
    table = canary.crosstab(rows)
    assert table["by_overlap_bucket"]["0"]["n"] == 1
    assert table["by_overlap_bucket"]["(.75, 1.0]"]["n"] == 1
    stats = table["by_overlap_bucket"]["0"]["no_speech_prob"]
    assert set(stats) == {"median", "p10", "p90", "min", "max"}
    assert table["by_overlap_bucket"]["0"]["latin_present"] == 1
    # θ·판정 어휘가 결과에 없어야 한다.
    import json
    text = json.dumps(table, ensure_ascii=False)
    for banned in ("threshold", "suspect", "hallucination", "reject"):
        assert banned not in text.lower(), banned


# ── 게이트 ───────────────────────────────────────────────────────────────
def test_gates_are_instrumentation_only():
    names = canary.GATES
    assert names == ("B-C1", "B-C2", "B-C3", "B-C4", "B-C5", "B-C6", "B-C7", "B-C8")
    text = " ".join(canary.GATE_DESCRIPTIONS.values()).lower()
    for banned in ("no_speech_prob >", "separat", "잘 갈라", "signal quality"):
        assert banned not in text, banned


def test_a_failed_parity_forces_phase_c_hold():
    verdict = {"B-C5": False, **{name: True for name in canary.GATES
                                 if name != "B-C5"}}
    assert canary.phase_c_recommendation(verdict) == "HOLD"
    assert canary.phase_c_recommendation(
        {name: True for name in canary.GATES}) == "ELIGIBLE_FOR_APPROVAL"


# ── 경계 ─────────────────────────────────────────────────────────────────
def test_the_script_does_not_choose_an_aggregation_rule():
    """여러 raw segment가 한 evidence로 합쳐질 때 무엇을 쓸지는 D freeze 소관이다."""
    code = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("max(no_speech", "mean(no_speech", "duration_weighted",
                      "aggregate_no_speech"):
        assert forbidden not in code, forbidden


def test_the_script_keeps_production_decoding_parameters():
    code = SCRIPT.read_text(encoding="utf-8")
    for key in ("word_timestamps", "hallucination_silence_threshold",
                "condition_on_previous_text", "beam_size", "best_of"):
        assert key in code, key
    assert "vad_filter=True" not in code


def test_the_script_never_writes_into_the_confirmed_index():
    """확정 인덱스는 **읽기만** 한다 — B-C7이 그 해시를 확인하므로 읽기는 필요하다."""
    import re

    writes = re.compile(r"\.write_text\(|\.write_bytes\(|open\([^)]*[\"']w")
    for number, line in enumerate(SCRIPT.read_text(encoding="utf-8").splitlines(), 1):
        if writes.search(line):
            assert "work_full" not in line, line
            assert not re.search(r"[\"']work/", line), line
            assert "work_canary" not in line, line
    code = SCRIPT.read_text(encoding="utf-8")
    assert "usable_for_claims =" not in code
