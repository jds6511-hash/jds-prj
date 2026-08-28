"""최종 보고서 baseline 일관성 검증 — 2026-08-28.

새 실험이 아니다. 보고서에 적힌 수치가 **실제 artifact와 같은지**, 상태 선언이
서로 모순되지 않는지, 금지 문구가 본문에 새어 들어가지 않았는지만 본다.

수치가 바뀌면 이 테스트가 먼저 깨진다 — 보고서가 조용히 stale해지는 것을 막는다.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/finalization/FINAL_REPORT_BASELINE_2026-08-28.md"
FACTS = ROOT / "docs/finalization/final_report_facts_2026-08-28.json"


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facts():
    return json.loads(FACTS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report():
    return REPORT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def fact_map(facts):
    return {f["fact_id"]: f["value"] for f in facts["facts"]}


# ── 존재·구조 ────────────────────────────────────────────────────────────
def test_보고서와_facts가_존재한다():
    assert REPORT.is_file() and FACTS.is_file()


def test_fact_id는_중복되지_않는다(facts):
    ids = [f["fact_id"] for f in facts["facts"]]
    assert len(ids) == len(set(ids))


def test_모든_fact에_source_path가_있다(facts):
    for f in facts["facts"]:
        assert f.get("source_path"), f["fact_id"]
        assert f.get("status"), f["fact_id"]


def test_source_path가_전부_실존한다(facts):
    """source 없는 숫자는 보고서에서 제거한다 — broken path 0이 목표다."""
    missing = sorted({f["source_path"] for f in facts["facts"]
                      if not (ROOT / f["source_path"]).exists()})
    assert not missing, f"존재하지 않는 source: {missing}"


def test_보고서가_참조하는_경로가_실존한다(report):
    pat = re.compile(r"(?:docs|results|runs|scripts|src|tests)/[\w./가-힣-]+")
    missing = sorted({p for p in pat.findall(report)
                      if not (ROOT / p.rstrip(".")).exists()})
    assert not missing, f"보고서가 없는 경로를 가리킨다: {missing}"


# ── baseline freeze marker ───────────────────────────────────────────────
def test_baseline_marker가_박혀_있다(report, facts):
    assert "report_baseline_date      2026-08-28" in report
    assert "AAR-v2 STEP A" in report
    m = facts["baseline_marker"]
    assert m["report_baseline_date"] == "2026-08-28"
    assert m["includes_research_through"] == "AAR-v2 STEP A"
    assert "STEP B" in m["does_not_include"]


# ── 상태 선언이 artifact와 일치 ─────────────────────────────────────────
def test_M8_상태가_official_artifact와_같다(facts):
    o = _json("docs/finalization/m8_official_result_2026-08-27.json")
    s = facts["status"]
    assert o["evaluation"] == s["m8_evaluation"] == "COMPLETE"
    assert o["acceptance"] == s["m8_acceptance"] == "FAIL"
    assert o["all_passed"] is False


def test_M8_관문_수치가_artifact와_같다(fact_map):
    v = _json("docs/finalization/m8_official_result_2026-08-27.json")["verdict"]
    assert fact_map["m8.c1_catastrophic_videos"] == v["C1"]["n_catastrophic_videos"]
    assert fact_map["m8.c2_value"] == v["C2"]["value"]
    assert fact_map["m8.c3_value"] == v["C3"]["value"]
    assert v["C1"]["passed"] is False and v["C2"]["passed"] is False
    assert v["C3"]["passed"] is False


def test_ROUND3는_수행되지_않았다(facts):
    assert facts["status"]["m8_round3_performed"] is False
    closure = (ROOT / "docs/finalization/M8_REDESIGN_CLOSURE_2026-08-28.md") \
        .read_text(encoding="utf-8")
    assert "ROUND 3            NO" in closure


def test_3way_집계가_artifact와_같다(fact_map):
    """보고서의 baseline / ROUND1 / ROUND2 표는 per_arm에서 다시 계산해도 같아야 한다."""
    import statistics as st
    pa = _json("docs/finalization/m8_redesign_r2_threeway_2026-08-28.json")["per_arm"]

    def agg(arm, key):
        return sum(v[key] for v in pa[arm].values())

    assert agg("baseline", "n_reference_events") == fact_map["m8.gt_events"] == 68
    assert agg("baseline", "n_generated_events") == fact_map["m8.generated_events"]
    assert agg("baseline", "unmatched_gt") == fact_map["m8.unmatched_gt"] == 22
    assert agg("baseline", "unmatched_gt_short") == fact_map["m8.unmatched_gt_short"]
    assert agg("baseline", "unmatched_generated") == fact_map["m8.unmatched_generated"]
    assert agg("R1", "n_generated_events") == fact_map["m8.r1.generated_events"]
    assert agg("R1", "unmatched_generated") == fact_map["m8.r1.unmatched_generated"]
    assert agg("R2", "n_generated_events") == fact_map["m8.r2.generated_events"]
    assert agg("R2", "unmatched_generated") == fact_map["m8.r2.unmatched_generated"]
    assert round(st.median(v["alignment"] for v in pa["R2"].values()), 4) == \
        fact_map["m8.r2.alignment_median"]
    assert max(v["compression"] for v in pa["R2"].values()) == fact_map["m8.r2.c3_max"]


def test_matched_GT는_파생값이_맞다(fact_map):
    assert fact_map["m8.matched_gt"] == \
        fact_map["m8.gt_events"] - fact_map["m8.unmatched_gt"] == 46


def test_R2_gate_판정이_artifact와_같다(fact_map):
    g = _json("docs/finalization/m8_redesign_r2_threeway_2026-08-28.json")["gate_result"]
    got = fact_map["m8.r2.gate_result"]
    assert [got[k] for k in "ABCDEF"] == list(g.values())
    assert list(g.values()).count("FAIL") == 4


# ── 후속 feasibility ────────────────────────────────────────────────────
def test_STEP0_수치가_artifact와_같다(fact_map, facts):
    d = _json("results/m8v2_step0/m8v2_step0_reachability_2026-08-28.json")
    assert facts["status"]["step0_verdict"] == "GO" and d["selected"] is not None
    assert d["selected"]["id"] == fact_map["step0.selected"] == "T2@0.7"
    assert d["panel"]["n_chunks"] == fact_map["step0.chunks"] == 41
    assert d["t1_reference"]["reachable_unmatched_gt"] == fact_map["step0.t1_reachable"]
    m = fact_map["step0.selected_metrics"]
    assert d["selected"]["reachable_unmatched_gt"] == m["reachable"] == 10
    assert d["selected"]["triggered_chunks"] == m["triggered_chunks"] == 8
    assert d["selected_diagnostic"]["rejection_share"] == \
        fact_map["step0.rejection_share_in_triggered"]


def test_STEP05는_NO_GO다(fact_map, facts):
    d = _json("runs/m8v2_step05/step05_summary.json")
    assert d["go"] is False and facts["status"]["step05_verdict"] == "NO-GO"
    m = d["metrics"]
    assert m["newly_matched_gt"] == fact_map["step05.newly_matched_gt"] == 4
    assert m["eligible_for_repair"] == fact_map["step05.eligible_candidates"] == 6
    assert m["rescued_events"] == fact_map["step05.valid_after_truncation"] == 5
    assert m["rescued_unmatched"] == fact_map["step05.added_events_unmatched"] == 0
    assert m["max_video_share"] == 0.75


def test_STEPA는_GO다(fact_map, facts):
    d = _json("runs/aarv2_step_a/summary.json")
    assert d["go"] is True and facts["status"]["stepa_verdict"] == "GO"
    m = d["metrics"]
    assert m["gt_boundaries"] == fact_map["stepa.gt_boundaries"] == 60
    assert m["embedding_recall"] == fact_map["stepa.embedding_recall"]
    assert m["uniform_recall"] == fact_map["stepa.uniform_recall"]
    assert m["delta"] == fact_map["stepa.delta"]
    assert m["n_eligible_videos"] == 7


def test_STEPA는_아키텍처를_구현하지_않았다(facts):
    assert facts["status"]["aarv2_full_implemented"] is False
    assert facts["status"]["aarv2_stepb_started"] is False
    d = _json("runs/aarv2_step_a/manifest.json")
    assert d["provenance"]["boundary"]["aarv2_architecture_implemented"] is False


def test_후속단계는_라벨도_LLM도_쓰지_않았다(fact_map):
    assert fact_map["followups.new_labels"] == 0
    assert fact_map["followups.llm_calls"] == 0
    for p in ("results/m8v2_step0/m8v2_step0_reachability_2026-08-28.json",
              "runs/m8v2_step05/step05_summary.json",
              "runs/aarv2_step_a/summary.json"):
        d = _json(p)
        b = d.get("boundary") or d.get("provenance", {}).get("boundary") or {}
        if b:
            assert b.get("llm_calls", 0) == 0 and b.get("new_labels", 0) == 0


# ── 열지 않은 것 ────────────────────────────────────────────────────────
def test_official_test와_M9는_열리지_않았다(facts):
    s = facts["status"]
    assert s["official_test_opened"] is False
    assert s["test_39_to_72_expanded"] is False
    assert s["m9"] == "HOLD"
    fz = _json("docs/finalization/m8_evaluator_freeze_2026-08-27.json")
    assert json.dumps(fz).count("official_m8_output_viewed") >= 1


def test_baseline은_push되지_않았다(facts):
    assert facts["status"]["pushed"] is False


def test_frozen_artifact를_수정하지_않았다(facts):
    assert facts["frozen_artifacts_modified"] is False
    assert facts["new_experiment_run"] is False
    assert facts["recomputed_official_metrics"] is False


# ── 문구 규율 ───────────────────────────────────────────────────────────
def _strip_code(md: str) -> str:
    """금지 문구는 '쓰지 않는다' 목록 안에서는 나와야 한다 — 그 자리는 코드로 감쌌다."""
    md = re.sub(r"```.*?```", "", md, flags=re.S)
    return re.sub(r"`[^`]*`", "", md)


def test_금지_문구가_본문에_없다(report, facts):
    body = _strip_code(report)
    leaked = [w for w in facts["forbidden_wording"] if w in body]
    assert not leaked, f"금지 문구가 본문에 새어 나왔다: {leaked}"


def test_생성과_acceptance를_구분한다(report):
    assert "산출물 생성 자체에는 성공했지만" in report
    assert "acceptance" in report


def test_STEPA를_feasibility로_제한한다(report):
    assert "feasibility evidence" in report
    assert "정밀도는 재지 않았다" in report or "정밀도를 재지 않았다" in report


def test_모델_우열은_미결로_적는다(report, fact_map):
    assert fact_map["model.superiority"] == "unresolved"
    assert "우월하다고 증명되어서가 아니라" in report


def test_C2_임계의_한계를_명시한다(report, fact_map):
    assert fact_map["m8.c2_threshold_external_grounding"] == "limited"
    assert "외부 타당성 근거가 제한적" in report


def test_한계_절이_16개를_담는다(report):
    sec = report.split("## 21. 한계")[1].split("## 22.")[0]
    nums = re.findall(r"^\s*(\d+)\s{2}", sec, flags=re.M)
    assert len(nums) == 16, f"한계 항목 수가 {len(nums)}개다"
