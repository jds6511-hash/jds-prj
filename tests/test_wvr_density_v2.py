"""V2 계측기 계약 (2026-09-09 · WVR-G01~G20).

```
event interval    프레임마다 반복하지 않는다
collapse          연속 반복만 합친다 (global dedupe 아님)
매칭              시간 정렬 → 의미 관계 · 확정 못 하면 adjudication
언어              English-only (진단 도구 한정)
```
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wvr_contract as contract
import wvr_density as density
import wvr_density_prompt_v2 as diag
import wvr_density_v1b as events
import wvr_density_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
PREREG = (ROOT / "docs/preregistration/"
          "WVR_SAMPLING_SEMANTIC_DENSITY_V2_2026-09-09.md")
RUNNER = ROOT / "scripts/wvr_density_stage2_v2.py"
SUMMARIZER = ROOT / "scripts/wvr_density_summarize_v2.py"
RUNS = ROOT / "runs/wvr_light_v1"
SUMMARY = RUNS / "density_v2_summary.json"
REPORT = ROOT / "docs/probes/WVR_DENSITY_V2_2026-09-09.md"
WINDOW = {"start_sec": 300.0, "end_sec": 480.0}
DOC = PREREG.read_text(encoding="utf-8")


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(RUNNER, "wvr_density_stage2_v2")


def _event(start, end, actor="a person", action="holds",
           thing="a bag", index=0):
    return {"index": index, "start_sec": start, "end_sec": end, "actor": actor,
            "action": action, "object_or_state": thing, "inside_window": True}


def _payload(rows):
    return json.dumps({"events": rows}, ensure_ascii=False)


def _row(start, end, actor="a person", action="holds", thing="a bag"):
    return {"start_sec": start, "end_sec": end, "actor": actor,
            "action": action, "object_or_state": thing}


# ── WVR-G01~G03 계약 동결 ─────────────────────────────────────────────
def test_wvr_g01_the_preregistration_is_committed():
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V2_2026-09-09.md"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert tracked.returncode == 0, "사전등록이 커밋되지 않았다"


def test_wvr_g02_the_v2_prompt_is_frozen_and_not_production():
    assert diag.prompt_hash() == (
        "37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273")
    assert diag.prompt_hash() in DOC
    assert diag.IS_PRODUCTION_CONTRACT is False
    assert diag.OUTPUT_LANGUAGE == "en"
    body = diag.SAMPLING_DIAG_PROMPT_V2
    assert "Write in English only" in body
    assert "Merge one continuing" in body
    assert "record\nit as a new event" in body or "as a new event" in body
    assert "no limit on how many events" in body


def test_wvr_g03_the_v1_prompts_are_not_reused():
    for source in (RUNNER, SUMMARIZER):
        text = source.read_text(encoding="utf-8")
        assert "SAMPLING_DIAG_PROMPT_V1" not in text
        assert "wvr_density_prompt as" not in text
    import wvr_density_prompt as old
    assert old.prompt_hash() != diag.prompt_hash()


# ── WVR-G04~G06 collapse ─────────────────────────────────────────────
def test_wvr_g04_the_signature_excludes_time():
    left, right = _event(300.0, 310.0), _event(400.0, 410.0)
    assert v2.signature(left) == v2.signature(right)
    source = (ROOT / "src/wvr_density_v2.py").read_text(encoding="utf-8")
    assert "CONTENT_FIELDS = (\"actor\", \"action\", \"object_or_state\")" \
        in source


def test_wvr_g05_only_consecutive_repeats_collapse():
    parsed = v2.parse_events(_payload([
        _row(300.0, 310.0), _row(310.0, 320.0), _row(320.0, 330.0,
                                                     action="puts down"),
        _row(330.0, 340.0)]), WINDOW)
    collapsed = parsed["collapsed"]
    assert [event["action"] for event in collapsed] == ["holds", "puts down",
                                                        "holds"]
    assert collapsed[0]["collapsed_count"] == 2
    assert collapsed[2]["collapsed_count"] == 1        # 다시 나타나면 새 event


def test_wvr_g06_the_collapsed_interval_keeps_the_span_and_sources():
    parsed = v2.parse_events(_payload([
        _row(300.0, 310.0), _row(305.0, 330.0), _row(320.0, 325.0)]), WINDOW)
    collapsed = parsed["collapsed"]
    assert len(collapsed) == 1
    assert collapsed[0]["start_sec"] == 300.0
    assert collapsed[0]["end_sec"] == 330.0
    assert collapsed[0]["source_indices"] == [0, 1, 2]
    assert collapsed[0]["collapsed_count"] == 3


def test_the_collapse_is_not_a_global_dedupe():
    """사이에 다른 사건이 끼면 같은 signature도 두 번 남는다."""
    parsed = v2.parse_events(_payload([
        _row(300.0, 305.0), _row(305.0, 310.0, action="walks"),
        _row(310.0, 315.0)]), WINDOW)
    signatures = [tuple(event["signature"]) for event in parsed["collapsed"]]
    assert len(signatures) == 3
    assert signatures[0] == signatures[2]


# ── WVR-G07 · G08 언어 계약 ──────────────────────────────────────────
def test_wvr_g07_the_english_contract_is_structural():
    good = v2.english_only([{"actor": "a person", "action": "holds",
                             "object_or_state": "a bag"}])
    assert good["satisfied"] is True and good["hangul_chars"] == 0
    empty = v2.english_only([])
    assert empty["satisfied"] is False and empty["latin_chars"] == 0
    mixed = v2.english_only([{"actor": "사람", "action": "holds",
                              "object_or_state": "a bag"}])
    assert mixed["satisfied"] is False and mixed["hangul_chars"] == 2


def test_wvr_g08_a_korean_arm_is_invalid():
    korean = _payload([{"start_sec": 300.0, "end_sec": 310.0,
                        "actor": "사람", "action": "든다",
                        "object_or_state": "봉지"}])
    record = {"raw_output": korean,
              "parsed": v2.parse_events(korean, WINDOW),
              "metrics": {"generated_token_count": 500},
              "requested": {"max_new_tokens": 4096}}
    verdict = v2.arm_validity(record)
    assert verdict["valid"] is False
    assert v2.LANGUAGE_CONTRACT_FAILURE in verdict["reasons"]


# ── WVR-G09~G11 매칭 ────────────────────────────────────────────────
def test_wvr_g09_temporal_compatibility_uses_intervals():
    left = _event(300.0, 320.0)
    assert v2.temporally_compatible(left, _event(310.0, 330.0), 4.0) is True
    assert v2.temporally_compatible(left, _event(324.0, 330.0), 4.0) is True
    assert v2.temporally_compatible(left, _event(324.1, 330.0), 4.0) is False
    assert v2.temporally_compatible(left, _event(324.1, 330.0), 8.0) is True
    with pytest.raises(v2.V2Error):
        v2.temporally_compatible(left, _event(310.0, 330.0), 0.0)


def test_wvr_g10_the_semantic_relation_has_three_outcomes():
    base = _event(300.0, 310.0)
    same = _event(400.0, 410.0)
    assert v2.semantic_relation(base, same)["relation"] \
        == v2.SEMANTICALLY_EQUIVALENT
    different = _event(300.0, 310.0, actor="a dog", action="sleeps",
                       thing="the floor")
    assert v2.semantic_relation(base, different)["relation"] \
        == v2.SEMANTICALLY_DIFFERENT
    assert v2.tokens(_event(300.0, 310.0, actor="a", action="the",
                            thing="of")) == set()      # 불용어만이면 빈 집합
    partial = _event(300.0, 310.0, action="opens")
    relation = v2.semantic_relation(base, partial)
    assert relation["relation"] == v2.ADJUDICATION_REQUIRED
    assert relation["field_equal"]["action"] is False
    assert relation["field_equal"]["actor"] is True


def test_wvr_g11_no_similarity_threshold_exists():
    source = (ROOT / "src/wvr_density_v2.py").read_text(encoding="utf-8")
    # 자기 문서 문구에 걸리지 않게 코드 구성만 본다
    for forbidden in ("SIMILARITY_THRESHOLD =", "distinct_event_ratio =",
                      ">= 0.3", ">= 0.5", ">= 0.7"):
        assert forbidden not in source
    assert "ADJUDICATION_REQUIRED" in source


# ── WVR-G12 · G13 merge·split·순서 ──────────────────────────────────
def test_wvr_g12_merge_and_split_candidates_are_kept():
    reference = [_event(300.0, 310.0, index=0), _event(311.0, 320.0, index=1)]
    arm = [_event(300.0, 320.0, index=0)]
    alignment = v2.align(reference, arm, 4.0)
    assert alignment["equivalent_count"] == 2          # 1:1 강제하지 않는다
    assert alignment["merge_candidates"] == [0]
    assert alignment["split_candidates"] == []
    flipped = v2.align(arm, reference, 4.0)
    assert flipped["split_candidates"] == [0]


def test_wvr_g13_the_order_is_counted_on_equivalent_pairs_only():
    reference = [_event(300.0, 305.0, action="holds", index=0),
                 _event(306.0, 310.0, action="opens", index=1)]
    arm = [_event(300.0, 305.0, action="opens", index=0),
           _event(306.0, 310.0, action="holds", index=1)]
    alignment = v2.align(reference, arm, 8.0)
    assert alignment["equivalent_count"] == 2
    assert alignment["order_inversions"] == 1
    assert v2.order_inversions([]) == 0
    # 순서가 그대로인 쌍에서는 0이어야 한다. 후보 전체를 세면 0이 아니게 된다.
    aligned = v2.align(reference, [
        _event(300.0, 305.0, action="holds", index=0),
        _event(306.0, 310.0, action="opens", index=1)], 8.0)
    assert aligned["equivalent_count"] == 2
    assert aligned["adjudication_count"] > 0
    assert aligned["order_inversions"] == 0
    assert v2.order_inversions(aligned["candidates"]) > 0


def test_the_field_divergence_counts_each_field():
    reference = [_event(300.0, 310.0, index=0)]
    arm = [_event(300.0, 310.0, action="opens", index=0)]
    divergence = v2.field_divergence(v2.align(reference, arm, 4.0))
    assert divergence["action"] == 1 and divergence["actor"] == 0


# ── WVR-G14~G16 게이트 ──────────────────────────────────────────────
def _record(rows, *, generated=800, cap=4096):
    raw = _payload(rows)
    return {"raw_output": raw, "parsed": v2.parse_events(raw, WINDOW),
            "metrics": {"generated_token_count": generated},
            "requested": {"max_new_tokens": cap}}


def test_wvr_g14_a_single_signature_window_is_degenerate():
    single = _record([_row(300.0, 310.0), _row(310.0, 320.0),
                      _row(320.0, 330.0)])
    shape = v2.representation(single["parsed"]["collapsed"])
    assert shape["unique_signature_count"] == 1
    assert shape["degenerate"] is True
    assert shape["reason"] == v2.REPRESENTATION_DEGENERACY
    varied = _record([_row(300.0, 310.0), _row(310.0, 320.0, action="opens")])
    assert v2.representation(varied["parsed"]["collapsed"])["degenerate"] \
        is False
    pair = v2.pair_evaluability(single, varied)
    assert pair["status"] == v2.PAIR_NON_EVALUABLE
    assert "S0:%s" % v2.REPRESENTATION_DEGENERACY in pair["reasons"]


def test_wvr_g15_all_three_pairs_are_required():
    assert v2.probe_verdict([v2.PAIR_EVALUABLE] * 3) == v2.DECISION_ELIGIBLE
    assert v2.probe_verdict([v2.PAIR_EVALUABLE] * 2) == v2.INCONCLUSIVE
    assert v2.probe_verdict([v2.PAIR_EVALUABLE, v2.PAIR_EVALUABLE,
                             v2.PAIR_NON_EVALUABLE]) == v2.INCONCLUSIVE


def test_wvr_g16_each_invalid_reason_is_recorded():
    varied = [_row(300.0, 310.0), _row(310.0, 320.0, action="opens")]
    assert v2.arm_validity(_record(varied))["valid"] is True
    truncated = v2.arm_validity(_record(varied, generated=4096))
    assert "TRUNCATED_AT_CAP" in truncated["reasons"]
    empty = v2.arm_validity(_record([]))
    assert "NO_EVENT" in empty["reasons"]
    broken = {"raw_output": "prose only",
              "parsed": v2.parse_events("prose only", WINDOW),
              "metrics": {"generated_token_count": 10},
              "requested": {"max_new_tokens": 4096}}
    assert "PARSE_FAILURE" in v2.arm_validity(broken)["reasons"]


def test_an_out_of_window_or_reversed_span_is_recorded():
    parsed = v2.parse_events(_payload([
        _row(300.0, 310.0), _row(700.0, 710.0), _row(320.0, 315.0)]), WINDOW)
    reasons = [violation["reason"] for violation in parsed["violations"]]
    assert "창 밖 구간" in reasons and "end < start" in reasons
    assert len(parsed["events"]) == 3                  # 조용히 버리지 않는다


# ── WVR-G17~G19 동결·경계 ───────────────────────────────────────────
def test_wvr_g17_the_runtime_matches_v1b():
    assert events.tokens_for("V2") == events.tokens_for("V1B") == 4096
    assert events.tag_for("V2") == "density_v2"
    stage1 = json.loads((RUNS / "density_stage1.json").read_text(
        encoding="utf-8"))
    assert [stage1["selection"][label]["window_id"]
            for label in density.SELECTION_LABELS] == ["W11", "W02", "W05"]
    for label in density.SELECTION_LABELS:
        window = runner.window_for(label, stage1)
        chosen = stage1["selection"][label]
        assert window["window_id"] == chosen["window_id"]      # 창 재선택 금지
        assert window["start_sec"] == chosen["start_sec"]
        assert window["stage1_score"] == chosen["score"]
        assert len(runner.arm_timestamps(window, "S0")) == 90
        assert len(runner.arm_timestamps(window, "S1")) == 45
    assert (contract.FRAME_WIDTH, contract.FRAME_HEIGHT) == (512, 288)
    assert v2.TOLERANCES == (4.0, 8.0)
    assert contract.REPETITION_PENALTY == 1.0


@pytest.mark.parametrize("name", [
    "density_stage2_D1_S0", "density_stage2_D2_S0", "density_stage2_D3_S0",
    "density_stage2b_D1_S0", "density_stage2b_D2_S0", "density_stage2b_D3_S0",
])
def test_wvr_g18_the_earlier_artifacts_are_untouched(name):
    done = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--",
         "runs/wvr_light_v1/%s.json" % name], cwd=str(ROOT))
    assert done.returncode == 0, "%s이 변경됐다" % name


def test_wvr_g19_no_sufficiency_claim_is_allowed():
    source = SUMMARIZER.read_text(encoding="utf-8")
    assert '"semantic_sufficiency_claim_allowed": False' in source
    assert "ground truth가 아니다" in source
    for forbidden in ("retry", "fallback", "device_map=", "load_in_8bit"):
        assert forbidden not in RUNNER.read_text(encoding="utf-8")


# ── 조건부: 실행 후 ─────────────────────────────────────────────────
def _v2_paths():
    return sorted(RUNS.glob("density_v2_D*_S*.json"))


@pytest.mark.skipif(not _v2_paths(), reason="V2 미실행")
def test_the_v2_artifacts_carry_the_frozen_contract():
    paths = _v2_paths()
    assert len(paths) == 6
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["event"] == "V2"
        assert record["prompt_hash"] == diag.prompt_hash()
        assert record["requested"]["max_new_tokens"] == 4096
        assert record["requested"]["frame_size"] == [512, 288]
        assert record["output_language"] == "en"


@pytest.mark.skipif(not SUMMARY.is_file(), reason="V2 요약 미실행")
def test_wvr_g20_the_report_agrees_with_the_summary():
    record = json.loads(SUMMARY.read_text(encoding="utf-8"))
    statuses = [record["pairs"][name]["evaluability"]["status"]
                for name in ("D1", "D2", "D3")]
    assert record["probe_verdict"] == v2.probe_verdict(statuses)
    assert record["semantic_sufficiency_claim_allowed"] is False
    if REPORT.is_file():
        text = REPORT.read_text(encoding="utf-8")
        assert record["probe_verdict"] in text
