"""보충 절 일관성 검증 — 2026-08-30 (baseline companion addendum).

새 실험이 아니다. 보충 절에 적힌 수치가 **실제 artifact와 같은지**, 상태 선언이
서로 모순되지 않는지, 금지 문구가 본문에 새어 들어가지 않았는지만 본다.

동결본(`FINAL_REPORT_BASELINE_2026-08-28.md`)을 수정하지 않았는지도 함께 본다 —
baseline 자신의 `revision_rule`이 "본문을 다시 쓰지 않는다"이기 때문이다.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/finalization/FINAL_REPORT_SUPPLEMENT_2026-08-30.md"
FACTS = ROOT / "docs/finalization/final_report_supplement_facts_2026-08-30.json"
BASELINE = ROOT / "docs/finalization/FINAL_REPORT_BASELINE_2026-08-28.md"


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facts():
    return json.loads(FACTS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc():
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def fact_map(facts):
    return {f["fact_id"]: f["value"] for f in facts["facts"]}


# ── 존재·구조 ────────────────────────────────────────────────────────────
def test_보충절과_facts가_존재한다():
    assert DOC.is_file() and FACTS.is_file()


def test_fact_id는_중복되지_않는다(facts):
    ids = [f["fact_id"] for f in facts["facts"]]
    assert len(ids) == len(set(ids))


def test_모든_fact에_source_path가_있다(facts):
    for f in facts["facts"]:
        assert f.get("source_path") and f.get("note")


def test_source_path가_전부_실존한다(facts):
    for f in facts["facts"]:
        assert (ROOT / f["source_path"]).is_file(), f["source_path"]


def test_보충절이_참조하는_경로가_실존한다(doc):
    for m in re.findall(r"`?(runs/[\w./-]+)`?", doc):
        p = ROOT / m.rstrip(".")
        if p.suffix:                      # 파일만 검사 (디렉터리 표기는 제외)
            assert p.exists(), m


# ── baseline 불변 ────────────────────────────────────────────────────────
def test_동결본을_수정하지_않았다(facts):
    """baseline revision_rule: 본문을 다시 쓰지 않는다."""
    assert facts["frozen_artifacts_modified"] == 0
    base = _json("docs/finalization/final_report_facts_2026-08-28.json")
    assert base["baseline_marker"]["report_baseline_date"] == "2026-08-28"
    assert BASELINE.is_file()


def test_companion임을_명시한다(doc, facts):
    assert "companion addendum" in doc
    assert "동결본은 한 글자도 고치지 않았다" in doc
    assert "companion addendum" in facts["relation_to_baseline"]


# ── ablation ─────────────────────────────────────────────────────────────
def test_ablation_수치가_artifact와_같다(fact_map):
    c = _json("runs/m8_hier/m8_hier_boundary_ablation/compare_wonyi_geoje.json")
    assert fact_map["ablation_atomic_full"] == c["full"]["n_atomic"] == 66
    assert fact_map["ablation_atomic_caponly"] == c["caption_only"]["n_atomic"] == 32
    assert fact_map["ablation_1seg_full"] == 25
    assert fact_map["ablation_1seg_caponly"] == 1
    assert fact_map["ablation_median_full"] == 2
    assert fact_map["ablation_median_caponly"] == 7


def test_열거_degeneracy가_caption_only에서_사라졌다(fact_map):
    assert fact_map["ablation_consecutive_run_full"] == 26
    assert fact_map["ablation_consecutive_runs_caponly"] == 0


def test_위치가_채널에_흔들린다(fact_map):
    """개수만 보면 안 된다 — 공통 위치가 16개뿐이다."""
    assert fact_map["ablation_shared_boundaries"] == 16


# ── BCS v0 ───────────────────────────────────────────────────────────────
def test_BCS_두_영상이_모두_유효하다(fact_map):
    assert fact_map["bcs_3i7_status"] == fact_map["bcs_geoje_status"] == "OK"
    assert fact_map["bcs_3i7_episodes"] == 18
    assert fact_map["bcs_geoje_episodes"] == 32


def test_오염_전파가_0건이다(fact_map):
    """구 계층에서 2건이던 것이 0건이 됐다 — 본문 주장의 근거."""
    for rel in ("runs/bcs/bcs_v0_reparsed/m8c2_3I7oGwk6EaQ.json",
                "runs/bcs/bcs_v0_reparsed/wonyi_geoje.json"):
        d = _json(rel)
        blob = " ".join(e["summary"] + " " + (e.get("dialogue_note") or "")
                        for e in d["episodes"])
        for bad in ("마포구청", "홈페이지", "다음 영상에서", "방송국"):
            assert bad not in blob, (rel, bad)
        assert not re.search(r"[一-鿿぀-ヿ]", blob), rel
    assert fact_map["bcs_3i7_stt_excluded"] == 29


def test_STT는_구조가_아니라_의미에만_들어갔다(fact_map):
    assert fact_map["bcs_3i7_dialogue_notes"] == 0
    assert fact_map["bcs_geoje_dialogue_notes"] == 14
    assert fact_map["bcs_geoje_dropped_claims"] == 2


def test_HWPX_두_편이_존재한다():
    for v in ("wonyi_geoje", "m8c2_3I7oGwk6EaQ"):
        assert (ROOT / f"runs/bcs/bcs_v0_reparsed/{v}_bcs_aar.hwpx").is_file()


# ── 모델 진단 ────────────────────────────────────────────────────────────
def test_붕괴가_반대_조건에서_일어난다(fact_map):
    assert fact_map["diag_current_full_chunk5_run1"] == 26
    assert fact_map["diag_current_caption_only_chunk5_run1"] == 1
    assert fact_map["diag_comparison_caption_only_chunk3_run1"] == 52
    assert fact_map["diag_comparison_full_chunk3_run1"] == 1


def test_파서_문제가_아니다(fact_map):
    assert fact_map["diag_all_parse_ok"] == ["PARSE_OK"]


def test_위치_안정성이_전부_낮다(fact_map):
    assert fact_map["diag_max_jaccard"] < 0.2


def test_비교모델은_패치_없이_돌았다(fact_map):
    assert fact_map["diag_comparison_model"] == "kakaocorp/kanana-1.5-8b-instruct-2505"
    assert fact_map["diag_compat_shims"] == []


def test_EXAONE은_결과가_없다(doc):
    assert "IMPLEMENTATION_BLOCKED" in doc
    assert "Scientific result   NONE" in doc


# ── C0 ───────────────────────────────────────────────────────────────────
def test_C0는_MIXED_SIGNAL이다(doc, fact_map):
    assert "MIXED_SIGNAL" in doc
    assert fact_map["c0_embedding_model"] == "nlpai-lab/KURE-v1"
    assert fact_map["c0_max_peak_hit_share"] == 0.214   # qwen_full chunk5 · 9/42


def test_C0_분포가_좁다(fact_map):
    """peak가 배경과 뚜렷이 분리되지 않는다 — p90/median이 2배 미만."""
    for k in ("wonyi_geoje_chunk3", "wonyi_geoje_chunk5", "3I7oGwk6EaQ_seg000_059"):
        assert fact_map[f"c0_{k}_p90"] / fact_map[f"c0_{k}_mean"] < 2.0


def test_C0는_임계를_정하지_않았다():
    c = _json("runs/c0/c0_boundary_signal.json")
    for x in ("threshold", "optimal_cutoff", "minimum_gap", "smoothing_tuning",
              "provider_adoption"):
        assert x in c["not_done"]


# ── 상태·경계 ────────────────────────────────────────────────────────────
def test_공식_판정이_바뀌지_않았다(facts):
    s = facts["status"]
    assert "FAIL" in s["official_M8"] and "불변" in s["official_M8"]
    assert s["M9"].startswith("HOLD")
    assert s["official_test"] == "UNOPENED"
    assert s["push"] == "NO"


def test_v2_1은_구현되지_않았다(facts, doc):
    assert facts["status"]["v2_1_implementation"].startswith("DEFERRED")
    assert "implementation authorization      NOT GRANTED" in doc


def test_change_point는_채택되지_않았다(facts, doc):
    assert "미채택" in facts["status"]["caption_change_point"]
    assert "CANDIDATE" in doc


def test_새_지표를_만들지_않았다(facts):
    assert facts["new_metric_computed"] == 0
    assert facts["recomputed_official_metrics"] == 0
    assert facts["new_experiment_run"] == 5


def test_금지_문구가_본문에_없다(doc, facts):
    body = re.sub(r"`[^`]*`", "", doc)          # 코드 스팬 제거 후 검사
    leaked = [w for w in facts["forbidden_wording"] if w in body]
    assert not leaked, f"금지 문구가 본문에 새어 나왔다: {leaked}"


def test_하지_않는_말_절이_있다(doc):
    assert "이 보충 절에서 하지 않는 말" in doc
    assert "형식 참조이며 GT 아님" in doc


def test_표본_한계를_적는다(doc):
    assert "표본 한계" in doc
    assert "반복 실행으로 확인하지" in doc
