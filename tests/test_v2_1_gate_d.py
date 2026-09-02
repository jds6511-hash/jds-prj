"""D-02 Gate D — 연구 경계 최종 검증 (Gate D).

matrix가 요구하는 일곱 가지를 실제 저장소 상태에서 확인한다.

```
M9 미실행 · official test 미개방 · BCS core 무변경 · 새 human GT 없음
추가 모델 비교 없음 · change-point 미채택 · C0 tuning 없음
```

문서를 읽고 PASS하지 않는다. **금지된 변화를 합성 트리에 실제로 넣어** 검사가
깨지는지까지 본다 — A-11에서 쓴 방식 그대로다.
"""
import json
import shutil
from pathlib import Path

import pytest

from v2_1_gate_d import (
    CONDITIONS,
    build_inventory,
    check_no_c0_tuning,
    check_no_m9_execution,
    check_no_new_model_comparison,
    verify_research_boundary,
)
from v2_1_guards import BCS_PROTECTED

ROOT = Path(__file__).resolve().parents[1]
GATE_D_DOC = ROOT / "docs/finalization/V2_1_GATE_D_2026-09-02.md"

#: 조건 → 그것을 닫는 구체적 증거.
EVIDENCE = {
    "m9_not_executed": ("A-11 REG-007 + D-01 경로 검사", [
        "test_v2_1_guards.py::test_reg_007_no_m9_artifact_in_a_clean_tree",
        "test_v2_1_guards.py::test_reg_007_an_m9_run_artifact_fails",
        "test_v2_1_guards.py::test_reg_007_source_files_are_not_artifacts",
        "test_v2_1_gate_d.py::test_a_run_directory_named_m9_is_caught",
        "test_v2_1_gate_d.py::test_a_fake_m9_result_fails",
    ]),
    "official_test_unopened": ("A-11 REG-006", [
        "test_v2_1_guards.py::test_reg_006_clean_tree_passes",
        "test_v2_1_guards.py::test_reg_006_rewriting_the_official_result_fails",
        "test_v2_1_guards.py::test_reg_006_deleting_the_official_result_fails",
    ]),
    "bcs_core_unchanged": ("A-11 REG-005 + C-07 import 상한", [
        "test_v2_1_guards.py::test_reg_005_editing_a_frozen_file_fails",
        "test_v2_1_guards.py::test_reg_005_deleting_a_frozen_file_fails",
        "test_v2_1_render_hwpx.py::test_the_module_does_not_import_bcs_or_legacy_renderers",
    ]),
    "no_new_human_gt": ("A-11 REG-008 + C-05 REF-002", [
        "test_v2_1_guards.py::test_reg_008_a_new_label_file_fails",
        "test_v2_1_guards.py::test_reg_008_editing_an_existing_label_fails",
        "test_v2_1_presentation.py::test_ref_002_the_format_reference_is_not_ground_truth",
    ]),
    "no_additional_model_comparison": ("D-01", [
        "test_v2_1_gate_d.py::test_gate_d_no_additional_model_comparison",
        "test_v2_1_gate_d.py::test_a_new_model_comparison_artifact_fails",
        "test_v2_1_gate_d.py::test_historic_diagnostics_are_not_violations",
    ]),
    "change_point_not_adopted": ("A-11 REG-009 + A-07", [
        "test_v2_1_guards.py::test_reg_009_changing_the_default_provider_fails",
        "test_v2_1_guards.py::test_reg_009_adoption_marker_in_config_fails",
        "test_v2_1_boundary.py::test_bpi_004_default_provider_name_is_fixed_window_v1",
    ]),
    "no_c0_tuning": ("D-01", [
        "test_v2_1_gate_d.py::test_gate_d_no_c0_tuning",
        "test_v2_1_gate_d.py::test_a_tuning_artifact_fails",
    ]),
}


@pytest.fixture(scope="module")
def report():
    return verify_research_boundary(ROOT)


@pytest.fixture
def tree(tmp_path):
    """합성 트리. 실제 연구 기록을 건드리지 않고 위반을 주입한다."""
    root = tmp_path / "repo"
    root.mkdir()
    for name in ("docs/finalization", "runs", "results", "label_kit/event_inventory",
                 "src", "scripts"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for relative in (*BCS_PROTECTED, "config.yaml"):
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, target)
        else:
            target.write_text("", encoding="utf-8")
    for relative in ("results/eval_test.json", "results/eval_test_kure.json",
                     "data/queries/queries.jsonl"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
    (root / "results/m8_redesign_r2").mkdir(parents=True, exist_ok=True)
    (root / "results/m8_redesign_r2/threeway.json").write_text(
        '{"record": "historic"}', encoding="utf-8")
    return root


def _state(root):
    from v2_1_guards import build_baseline

    baseline = build_baseline(root)
    inventory = build_inventory(root)
    (root / "docs/finalization").mkdir(parents=True, exist_ok=True)
    (root / "docs/finalization/v2_1_gate_d_inventory_2026-09-02.json").write_text(
        json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return baseline, inventory


# ── 일곱 조건 ────────────────────────────────────────────────────────────
def test_the_gate_has_exactly_seven_conditions():
    assert len(CONDITIONS) == 7
    assert set(CONDITIONS) == set(EVIDENCE)


@pytest.mark.parametrize("name", CONDITIONS)
def test_each_condition_passes_on_the_real_tree(report, name):
    condition = next(c for c in report.conditions if c.name == name)
    assert condition.ok, condition.failures


def test_gate_d_research_boundary_passes(report):
    assert report.ok
    assert report.failures() == []


def test_gate_d_m9_not_executed(report):
    """M9가 저장소에 없다가 아니라, M9가 실행되지 않았다."""
    assert (ROOT / "src/m9_report.py").is_file() or True
    condition = next(c for c in report.conditions if c.name == "m9_not_executed")
    assert condition.ok


def test_gate_d_no_additional_model_comparison(report):
    condition = next(c for c in report.conditions
                     if c.name == "no_additional_model_comparison")
    assert condition.ok


def test_gate_d_no_c0_tuning(report):
    condition = next(c for c in report.conditions if c.name == "no_c0_tuning")
    assert condition.ok


def test_historic_diagnostics_are_not_violations():
    """과거 진단 산출물은 보존 대상이지 위반이 아니다."""
    inventory = json.loads(
        (ROOT / "docs/finalization/v2_1_gate_d_inventory_2026-09-02.json")
        .read_text(encoding="utf-8"))
    recorded = inventory["model_comparison_artifacts"]
    assert recorded, "기록이 비면 이 검사는 아무것도 지키지 않는다"
    assert all((ROOT / relative).is_file() for relative in recorded)
    assert check_no_new_model_comparison(ROOT, inventory) == []


# ── 위반을 넣으면 깨진다 ─────────────────────────────────────────────────
def test_a_run_directory_named_m9_is_caught(tree):
    """A-11 REG-007은 파일 **이름**만 본다 — 디렉터리 표시는 여기서 잡는다.

    실제 M9 실행은 `runs/m9_official/report.json`처럼 남을 가능성이 높다.
    """
    (tree / "runs/m9_official").mkdir(parents=True)
    (tree / "runs/m9_official/report.json").write_text("{}", encoding="utf-8")
    from v2_1_guards import check_no_m9_artifacts

    assert check_no_m9_artifacts(tree) == [], "A-11은 이 형태를 놓친다 (기록된 사실)"
    assert check_no_m9_execution(tree)


def test_a_fake_m9_result_fails(tree):
    baseline, inventory = _state(tree)
    (tree / "runs/m9_official").mkdir(parents=True)
    (tree / "runs/m9_official/result.json").write_text("{}", encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert not report.ok
    assert any(c.name == "m9_not_executed" and not c.ok for c in report.conditions)


def test_touching_the_official_test_result_fails(tree):
    baseline, inventory = _state(tree)
    (tree / "results/eval_test.json").write_text('{"mrr": 0.9}', encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert any(c.name == "official_test_unopened" and not c.ok
               for c in report.conditions)


def test_editing_a_frozen_bcs_file_fails(tree):
    baseline, inventory = _state(tree)
    target = tree / BCS_PROTECTED[0]
    target.write_text(target.read_text(encoding="utf-8") + "\n# edit\n",
                      encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert any(c.name == "bcs_core_unchanged" and not c.ok
               for c in report.conditions)


def test_a_new_human_gt_file_fails(tree):
    baseline, inventory = _state(tree)
    (tree / "label_kit/event_inventory/new_video.json").write_text(
        '{"events": []}', encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert any(c.name == "no_new_human_gt" and not c.ok for c in report.conditions)


def test_a_new_model_comparison_artifact_fails(tree):
    baseline, inventory = _state(tree)
    (tree / "results/qwen3_vs_kanana_compare.json").write_text(
        '{"winner": "qwen3"}', encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert any(c.name == "no_additional_model_comparison" and not c.ok
               for c in report.conditions)


def test_rewriting_a_recorded_diagnostic_fails(tree):
    """역사를 다시 쓰는 것도 위반이다."""
    baseline, inventory = _state(tree)
    (tree / "results/m8_redesign_r2/threeway.json").write_text(
        '{"record": "rewritten"}', encoding="utf-8")
    assert check_no_new_model_comparison(tree, inventory)


def test_adopting_the_change_point_provider_fails(tree):
    baseline, inventory = _state(tree)
    (tree / "config.yaml").write_text(
        "boundary_provider: caption_text_change_point\n", encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert any(c.name == "change_point_not_adopted" and not c.ok
               for c in report.conditions)


def test_a_tuning_artifact_fails(tree):
    baseline, inventory = _state(tree)
    (tree / "runs/c0_threshold_sweep.json").write_text(
        '{"best_threshold": 0.42}', encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert any(c.name == "no_c0_tuning" and not c.ok for c in report.conditions)
    assert check_no_c0_tuning(tree, inventory)


def test_a_smoothing_sweep_is_also_caught(tree):
    baseline, inventory = _state(tree)
    (tree / "runs/boundary_smoothing_grid_search.json").write_text(
        "{}", encoding="utf-8")
    assert check_no_c0_tuning(tree, inventory)


def test_every_violation_names_its_path(tree):
    baseline, inventory = _state(tree)
    (tree / "runs/c0_min_gap_tuning.json").write_text("{}", encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    assert all(failure.detail for failure in report.failures())


def test_the_verifier_does_not_stop_at_the_first_failure(tree):
    baseline, inventory = _state(tree)
    (tree / "runs/m9_run").mkdir(parents=True)
    (tree / "runs/m9_run/report.json").write_text("{}", encoding="utf-8")
    (tree / "runs/c0_threshold_sweep.json").write_text("{}", encoding="utf-8")
    report = verify_research_boundary(tree, baseline, inventory)
    failed = {c.name for c in report.conditions if not c.ok}
    assert {"m9_not_executed", "no_c0_tuning"} <= failed


# ── 증거 지도 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(EVIDENCE))
def test_every_condition_names_existing_evidence(name):
    import re

    _, nodes = EVIDENCE[name]
    for node in nodes:
        filename, function = node.split("::")
        path = ROOT / "tests" / filename
        assert path.is_file(), node
        assert re.search(r"^def %s\(" % re.escape(function),
                         path.read_text(encoding="utf-8"), re.M), node


# ── 판정을 문서와 대조한다 ───────────────────────────────────────────────
def test_the_verdict_is_recorded():
    text = GATE_D_DOC.read_text(encoding="utf-8")
    assert "GATE D RESEARCH BOUNDARY = PASS" in text
    assert "GATE D CLOSURE = COMPLETE" in text


def test_completion_is_still_not_claimed():
    text = GATE_D_DOC.read_text(encoding="utf-8")
    assert "IMPLEMENTATION_COMPLETE = NO" in text
    assert "REG-010" in text


def test_gate_d_does_not_authorize_anything():
    text = GATE_D_DOC.read_text(encoding="utf-8")
    for line in ("M9 승인 아님", "official test 개방 아님"):
        assert line in text
