"""F5 최종 보고서 source pack — fact index의 추적성·상태 정합 계약.

새 연구 수치를 만들지 않는다. 검사하는 것은 세 가지다.
  1. 인용한 근거 경로가 실재하는가 (없는 파일을 인용하지 않는다)
  2. 배포 identity·HOLD 상태가 실제 코드/설계 artifact와 같은가
  3. 근거보다 센 표현이 들어가지 않았는가 (금지 문구는 금지 목록 안에서만 등장한다)
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

FACTS = ROOT / "docs/finalization/final_report_facts_2026-08-26.json"
MATRIX = ROOT / "docs/finalization/CLAIM_EVIDENCE_MATRIX_2026-08-26.md"
PACK = ROOT / "docs/finalization/FINAL_REPORT_SOURCE_PACK_2026-08-26.md"

# _scratch는 .gitignore 대상이라 clone 직후 없을 수 있다. 존재 검사에서 면제하되
# 그 사실을 여기 명시해 둔다 — 동결 원자료의 로컬 위치이고 수치는 상위 문서에 전재돼 있다.
GITIGNORED_PREFIXES = ("docs/probes/_scratch/", "runs/")


@pytest.fixture(scope="module")
def facts():
    return json.loads(FACTS.read_text(encoding="utf-8"))


def _collect_paths(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("source_path", "frozen_raw", "secondary_sources"):
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend(x for x in v if isinstance(x, str))
            elif k == "sources" and isinstance(v, dict):
                out.extend(x for x in v.values() if isinstance(x, str))
            else:
                _collect_paths(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _collect_paths(x, out)


def _repo_path(cited: str) -> Path:
    """'docs/X.md §8-6' · 'tests/ (pytest ...)' 같은 주석 꼬리를 떼고 경로만 남긴다."""
    return ROOT / re.split(r"\s*[·(]|\s+§", cited)[0].strip()


# --- 1. 근거 경로 무결성 ------------------------------------------------------

def test_every_facts_source_path_exists(facts):
    """없는 파일을 근거로 인용하지 않는다."""
    cited = []
    _collect_paths(facts, cited)
    assert cited, "source_path가 하나도 수집되지 않았다 — 수집기가 깨졌다"
    missing = [c for c in cited
               if not c.startswith(GITIGNORED_PREFIXES) and not _repo_path(c).exists()]
    assert not missing, "broken evidence path: %s" % missing


def test_claim_matrix_primary_sources_exist():
    """matrix의 primary/secondary source 줄에 적힌 저장소 경로가 실재해야 한다."""
    text = MATRIX.read_text(encoding="utf-8")
    cited = set(re.findall(r"(?:docs|src|scripts|tests|results|planning)/[^\s·()`]+", text))
    cited |= {m for m in re.findall(r"\b(?:config\.yaml|README\.md|CLAUDE\.md|\.gitattributes)\b", text)}
    assert cited, "matrix에서 경로를 하나도 못 찾았다"
    missing = [c for c in sorted(cited)
               if not c.startswith(GITIGNORED_PREFIXES) and not _repo_path(c).exists()]
    assert not missing, "matrix broken evidence path: %s" % missing


def test_source_pack_and_matrix_reference_each_other(facts):
    pack = PACK.read_text(encoding="utf-8")
    assert "CLAIM_EVIDENCE_MATRIX_2026-08-26.md" in pack
    assert "final_report_facts_2026-08-26.json" in pack
    assert facts["sources"]["claim_matrix"].endswith("CLAIM_EVIDENCE_MATRIX_2026-08-26.md")
    assert facts["sources"]["source_pack"].endswith("FINAL_REPORT_SOURCE_PACK_2026-08-26.md")


# --- 2. 상태 정합 -------------------------------------------------------------

def test_deployment_identity_matches_code(facts):
    """fact index의 배포 identity가 진입점 preflight의 값과 같아야 한다."""
    import demo as D                                                # noqa: E402
    dep = facts["deployment"]
    assert dep["caption_model"]["value"] == D.DEPLOYMENT["caption_model"]
    assert dep["vlm_4bit"]["value"] == D.DEPLOYMENT["vlm_4bit"]
    assert dep["embed_model"]["value"] == D.DEPLOYMENT["embed_model"]
    assert dep["seg_len_sec"]["value"] == D.DEPLOYMENT["seg_len_sec"]
    assert dep["static_threshold"]["value"] == D.DEPLOYMENT["static_threshold"]
    assert dep["alpha"]["value"] == D.DEPLOYMENT_ALPHA
    assert dep["alpha"]["in_config"] is False, "α는 config에 없다 — CLI 주입이다"


def test_alpha_star_matches_frozen_search(facts):
    d = json.loads((ROOT / "results/alpha_search_dev.json").read_text(encoding="utf-8"))
    a = facts["deployment"]["alpha"]
    assert a["alpha_star"] == d["alpha_star"]
    assert a["tie_set"] == d["tie_set"]
    assert a["alpha_best_point"] == d["alpha_best_point"]


def test_official_test_numbers_match_frozen_result(facts):
    """공식 결과는 재계산하지 않는다 — frozen artifact에서 그대로 읽었는지만 본다."""
    src = json.loads((ROOT / "results/eval_test.json").read_text(encoding="utf-8"))
    got = facts["official_test_result"]
    assert got["n_queries"] == src["n_queries"]
    for arm, key in (("baseline", "baseline"), ("proposed", "proposed")):
        for m in ("mrr", "hit@1", "hit@5", "hit@10"):
            assert got[arm][m] == src["metrics"][key][m], (arm, m)
    for m, ci in src["diff_ci95"].items():
        assert got["diff_ci95"][m] == ci, m
    for t, v in got["by_type_mrr"].items():
        assert v["baseline"] == src["metrics"]["baseline"]["by_type"][t]["mrr"]
        assert v["proposed"] == src["metrics"]["proposed"]["by_type"][t]["mrr"]


def test_hit5_hit10_ci_include_zero_is_stated(facts):
    """CI가 0을 포함하는 지표를 유의한 개선처럼 쓰지 않는다."""
    for m in ("hit@5", "hit@10"):
        lo, hi = facts["official_test_result"]["diff_ci95"][m]
        assert lo <= 0 <= hi, "%s CI가 0을 배제한다면 서술을 다시 봐야 한다" % m
    assert "0을 포함" in facts["official_test_result"]["significance_note"]


def test_p2_hold_counts(facts):
    src = json.loads((ROOT / "docs/P2_활성설계_2026-08-24.json").read_text(encoding="utf-8"))
    p2 = facts["p2"]
    assert p2["planned_labels"] == src["total_queries"] == 175
    assert p2["completed_labels"] == 20
    assert p2["incomplete_labels"] == 155
    assert p2["planned_labels"] == p2["completed_labels"] + p2["incomplete_labels"]
    for k in ("retrieval_run", "evaluation_run", "outcome_opened", "partial_20_analyzed"):
        assert p2[k] is False, k


def test_p3_frozen_design_matches_source(facts):
    src = json.loads((ROOT / "docs/P3_설계민감도_2026-08-24.json").read_text(
        encoding="utf-8"))["frozen_decision"]
    p3 = facts["p3"]
    assert p3["video_clusters"] == src["video_clusters"] == 300
    assert p3["queries_per_video"] == src["queries_per_video"] == 5
    assert p3["total_gt_rows"] == src["total_gt_rows"] == 1500
    assert p3["minimum_deployment_relevant_gain"]["value"] == src["minimum_deployment_relevant_gain"]
    assert p3["minimum_deployment_relevant_gain"]["is_measured_constant"] is False
    assert "검출 보장이 아니" in p3["precision_claim_rule"]


def test_e2e_is_not_a_research_metric(facts):
    src = json.loads((ROOT / "docs/finalization/e2e_external_results.json").read_text(
        encoding="utf-8"))
    e = facts["e2e"]
    assert e["research_metric"] is False
    assert e["is_benchmark"] is False
    assert e["is_accuracy_evaluation"] is False
    assert src["suite_status"]["research_metrics_generated"] is False
    assert e["status"] == src["suite_status"]["functional_e2e"] == "COMPLETE"
    by_id = {r["e2e_id"]: r for r in src["runs"]}
    assert len(e["phases"]) == src["suite_status"]["core_videos_run"] == 4
    for ph in e["phases"]:
        run = by_id[ph["e2e_id"]]
        assert ph["duration_sec"] == run["identity"]["observed_duration_sec"]
        assert ph["segments"] == run["identity"]["segment_count"]
        assert ph["verdict"] == run["functional"]["verdict"] == "PASS"


def test_e2e_anchor_issue_is_not_retrieval_evidence(facts):
    a = facts["e2e"]["anchor_issue"]
    assert a["functional_fail"] is False
    assert "데이터 품질" in a["classification"]
    assert a["not_used_as"] == "검색 정확도·성능 근거"


def test_case_study_is_not_adoption_evidence(facts):
    src = json.loads((ROOT / "docs/finalization/caption_retrieval_casestudy_results.json")
                     .read_text(encoding="utf-8"))
    cs = facts["case_study"]
    assert cs["adoption_evidence"] is False is src["adoption_evidence"]
    assert cs["model_superiority_evidence"] is False
    assert cs["formal_model_selection_experiment"] is False
    assert cs["n_queries"] == 15 and cs["n_scenes"] == 5
    assert cs["n_segments"] == src["n_segments"] == 395
    c, s = cs["counts"], src["case_study_counts"]
    assert c["illustrative_top1_hit"]["3b"] == s["illustrative_top1_hit_count"]["3b"]
    assert c["illustrative_top1_hit"]["4b"] == s["illustrative_top1_hit_count"]["4b"]
    assert c["queries_with_higher_target_rank"]["4b"] == \
        s["queries_with_higher_target_rank"]["4b"]
    assert c["median_target_rank"] == s["median_target_rank"]


def test_caption_qc_rate_is_not_a_contamination_ground_truth(facts):
    q = facts["caption_qc_limitation"]
    assert q["is_contamination_ground_truth"] is False
    assert q["is_detector_miss_rate"] is False
    assert "미탐률 8.25%" in q["forbidden_wording"]
    assert "오염 0" in q["forbidden_wording"]


def test_caption_qc_counts_match_scan_when_available(facts):
    scan = ROOT / "docs/probes/_scratch/caption_foreign_char_scan.json"
    if not scan.is_file():
        pytest.skip("_scratch는 gitignore 대상 — clone 직후에는 없다")
    src = {s["label"]: s for s in json.loads(scan.read_text(encoding="utf-8"))["scans"]}
    got = {s["label"].split(" ")[0]: s for s in facts["caption_qc_limitation"]["scans"]}
    for label, key in (("배포 인덱스", "work/"), ("AI Hub", "AI")):
        a, b = src[label], got[key]
        assert b["n_captions"] == a["n_captions"]
        assert b["current_rule_flags"] == a["current_rule_hits"]
        assert b["additional_foreign_script_candidates"] == a["newly_flagged"]
        assert b["additional_candidate_ratio"] == a["newly_flagged_ratio"]
        assert b["script_buckets"] == a["script_buckets"]
        want = round(a["script_buckets"].get("CJK/KANA만", 0) / a["newly_flagged"], 4)
        assert b["cjk_kana_only_ratio"] == want


def test_limitations_doc_matches_scan_ratio():
    """실제 사고(F5 conflict CF-03): 활성 한계 문서의 CJK 비율이 원자료와 달랐다."""
    t = (ROOT / "docs/finalization/LIMITATIONS_FUTURE_WORK_2026-08-25.md").read_text(
        encoding="utf-8")
    assert "87.7%" not in t, "scan 원자료는 201/227 = 88.5%다"
    assert "88.5%" in t


def test_aar_status_is_partial_until_artifact_exists(facts):
    """artifact가 실제로 들어오면 이 fact를 갱신해야 한다 — 그때 이 테스트가 알려준다."""
    aar = facts["aar"]
    present = sorted(p.as_posix() for p in ROOT.glob("work/*/report.json"))
    assert aar["demo_report_artifact_obtained"] == bool(present), \
        "report.json 존재 여부와 fact가 어긋난다: %s" % present
    assert aar["local_generation_possible"] is False
    assert aar["renderer_ready"] and aar["server_runbook_ready"]
    assert "one server-generated demo artifact remains" in aar["status_wording"]
    assert "end-to-end AAR complete" in aar["forbidden_wording"]


def test_research_boundaries_all_preserved(facts):
    b = facts["boundaries_preserved"]
    assert set(b.values()) == {False}, "경계 위반 플래그가 켜져 있다: %s" % b


def test_no_new_research_metric_declared(facts):
    assert facts["new_experiment_run"] is False
    assert facts["new_metric_computed"] is False
    assert facts["recomputed_official_metrics"] is False


# --- 3. 표현 강도 -------------------------------------------------------------

FORBIDDEN = ("3B 승리", "3B가 이겼", "3B가 더 좋은 모델로 검증", "4B 실패", "4B가 실패",
             "4B 기각", "운영비가 더 싸", "운영비가 싸", "계산적으로 더 효율적",
             "미탐률", "cheaper", "3B winner", "4B failed", "4B rejected",
             "완벽히 재현 가능")
MARKERS = ("금지", "forbidden", "쓰지 않는", "쓰지 않음", "쓰지 마", "않는다", "아니다")


def _offending_lines(text):
    """금지 문구가 '금지 목록·부정문' 밖에서 단정문으로 쓰였는지 본다.

    빈 줄 · 제목 · 코드펜스에서 문맥을 초기화하고, 그 블록 안에서 한 번이라도
    금지 표시가 나오면 이후 줄은 계속 그 목록의 일부로 본다(줄바꿈된 목록 때문).
    """
    bad, in_list = [], False
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith("#") or line.startswith("```"):
            in_list = False
            continue
        if any(m in line for m in MARKERS):
            in_list = True
        if in_list:
            continue
        for f in FORBIDDEN:
            if f in line:
                bad.append((i, f, line.strip()))
    return bad


@pytest.mark.parametrize("doc", [MATRIX, PACK])
def test_f5_docs_do_not_assert_forbidden_wording(doc):
    bad = _offending_lines(doc.read_text(encoding="utf-8"))
    assert not bad, "%s: 금지 표현이 목록 밖에서 쓰였다 %s" % (doc.name, bad)


def test_incumbent_reason_is_stated_as_lack_of_evidence(facts):
    r = facts["deployment_decision"]
    assert r["scientific_superiority"] == "unresolved"
    assert "우월하다고 증명되어서가 아니라" in r["reason"]
    assert "fresh deployment-relevant evidence" in r["reason"]
    assert r["candidate_4b"]["status"] == "viable candidate · not adopted"
    pack = PACK.read_text(encoding="utf-8")
    assert "fresh deployment-relevant evidence" in pack


def test_operational_claims_stay_within_measurement(facts):
    op = facts["operational"]
    assert op["causal_claim_output_length_to_wallclock"] is False
    assert op["descriptive_not_population_estimate"] is True
    for missing in ("전력 소비", "금전 비용"):
        assert any(missing in x for x in op["not_measured"]), missing
    assert "deployment blocker는 관측되지 않았고" in op["verdict"]


def test_limitations_and_future_work_are_separate(facts):
    ids = [x["id"] for x in facts["limitations"]]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    for x in facts["limitations"]:
        assert x["source_path"], x["id"]
    for x in facts["future_work"]:
        assert x["commitment"] != "promised", x["id"]
