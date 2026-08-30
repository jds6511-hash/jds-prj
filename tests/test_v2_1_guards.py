"""A-11 research boundary guards — 지금 깨끗한지, 그리고 더럽혀지면 깨지는지.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-11

```
REG-005  BCS core diff              REG-008  new human GT artifact
REG-006  official test access       REG-009  provider adoption marker
REG-007  M9 execution artifact      REF-003  wonyi_gyeongju 자동 대조
```

각 가드마다 **실제 트리 통과**와 **합성 위반 검출**을 둘 다 본다. 통과만 보면
가드가 아무것도 안 해도 초록이다.
"""
import json
from pathlib import Path

import pytest

from v2_1_guards import (
    BASELINE_PATH,
    BCS_PROTECTED,
    build_baseline,
    check_bcs_unchanged,
    check_no_gyeongju_comparison,
    check_no_m9_artifacts,
    check_no_new_human_gt,
    check_no_provider_adoption,
    check_official_test_untouched,
    digest,
    load_baseline,
    run_all,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def baseline():
    return load_baseline(ROOT)


def _codes(failures):
    return {f.code for f in failures}


@pytest.fixture
def tree(tmp_path):
    """기준선을 갖춘 최소 합성 트리. 위반은 테스트가 직접 심는다."""
    for path in BCS_PROTECTED:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("frozen\n", encoding="utf-8")
    (tmp_path / "results").mkdir(exist_ok=True)
    (tmp_path / "results/eval_test.json").write_text('{"mrr": 0.5}', encoding="utf-8")
    (tmp_path / "label_kit/event_inventory").mkdir(parents=True)
    (tmp_path / "label_kit/event_inventory/FROZEN_a.json").write_text("[]",
                                                                     encoding="utf-8")
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src/v2_1_boundary.py").write_text(
        'DEFAULT_PROVIDER_NAME = "fixed_window_v1"\n', encoding="utf-8"
    )
    (tmp_path / "results/report_dev_wonyi_gyeongju.json").write_text("{}",
                                                                    encoding="utf-8")
    return tmp_path


@pytest.fixture
def tree_baseline(tree):
    return build_baseline(tree)


# ── 실제 트리 ────────────────────────────────────────────────────────────
def test_the_real_tree_passes_every_guard(baseline):
    report = run_all(ROOT, baseline)
    assert report.ok, [f"{f.code}: {f.detail}" for f in report.failures]


def test_baseline_is_committed_and_complete(baseline):
    assert (ROOT / BASELINE_PATH).is_file()
    assert len(baseline["bcs_protected"]) == len(BCS_PROTECTED)
    assert baseline["official_test"] and baseline["human_gt"]


def test_baseline_matches_the_current_tree(baseline):
    """기준선이 낡으면 가드가 통과해도 의미가 없다."""
    assert build_baseline(ROOT) == baseline


def test_baseline_records_the_preexisting_gyeongju_artifacts(baseline):
    """gyeongju는 dev 세트에 있어 정상 M8 산출물이 이미 있다 — 존재는 위반이 아니다."""
    assert baseline["gyeongju_artifacts"]
    assert all("m8_redesign" in p for p in baseline["gyeongju_artifacts"])


# ── REG-005 BCS core ─────────────────────────────────────────────────────
def test_reg_005_clean_tree_passes(tree, tree_baseline):
    assert check_bcs_unchanged(tree, tree_baseline) == []


def test_reg_005_editing_a_frozen_file_fails(tree, tree_baseline):
    (tree / "src/bcs.py").write_text("frozen\n# 한 줄 추가\n", encoding="utf-8")
    assert "BCS_CORE_DIFF" in _codes(check_bcs_unchanged(tree, tree_baseline))


def test_reg_005_deleting_a_frozen_file_fails(tree, tree_baseline):
    (tree / "scripts/bcs_hwpx.py").unlink()
    assert "BCS_CORE_MISSING" in _codes(check_bcs_unchanged(tree, tree_baseline))


def test_reg_005_line_ending_change_alone_is_not_a_diff(tree, tree_baseline):
    """Windows 체크아웃에서 CRLF가 되는 것을 변경으로 읽으면 매일 거짓 실패한다."""
    (tree / "src/bcs.py").write_bytes(b"frozen\r\n")
    assert check_bcs_unchanged(tree, tree_baseline) == []


# ── REG-006 official test ────────────────────────────────────────────────
def test_reg_006_clean_tree_passes(tree, tree_baseline):
    assert check_official_test_untouched(tree, tree_baseline) == []


def test_reg_006_rewriting_the_official_result_fails(tree, tree_baseline):
    (tree / "results/eval_test.json").write_text('{"mrr": 0.9}', encoding="utf-8")
    assert "OFFICIAL_TEST_MODIFIED" in _codes(
        check_official_test_untouched(tree, tree_baseline)
    )


def test_reg_006_deleting_the_official_result_fails(tree, tree_baseline):
    (tree / "results/eval_test.json").unlink()
    assert "OFFICIAL_TEST_MISSING" in _codes(
        check_official_test_untouched(tree, tree_baseline)
    )


# ── REG-007 M9 ───────────────────────────────────────────────────────────
def test_reg_007_no_m9_artifact_in_a_clean_tree(tree):
    assert check_no_m9_artifacts(tree) == []


def test_reg_007_an_m9_run_artifact_fails(tree):
    (tree / "results/m9_report_eval.json").write_text("{}", encoding="utf-8")
    assert "M9_ARTIFACT" in _codes(check_no_m9_artifacts(tree))


def test_reg_007_nested_m9_artifact_is_found(tree):
    nested = tree / "runs/some_run"
    nested.mkdir(parents=True)
    (nested / "M9_dryrun.json").write_text("{}", encoding="utf-8")
    assert "M9_ARTIFACT" in _codes(check_no_m9_artifacts(tree))


def test_reg_007_source_files_are_not_artifacts(tree):
    """`src/m9_report_eval.py`는 코드다 — 실행 흔적이 아니다."""
    (tree / "src/m9_report_eval.py").write_text("x = 1\n", encoding="utf-8")
    assert check_no_m9_artifacts(tree) == []


# ── REG-008 human GT ─────────────────────────────────────────────────────
def test_reg_008_clean_tree_passes(tree, tree_baseline):
    assert check_no_new_human_gt(tree, tree_baseline) == []


def test_reg_008_a_new_label_file_fails(tree, tree_baseline):
    (tree / "label_kit/event_inventory/FROZEN_new_video.json").write_text(
        "[]", encoding="utf-8"
    )
    assert "NEW_HUMAN_GT" in _codes(check_no_new_human_gt(tree, tree_baseline))


def test_reg_008_editing_an_existing_label_fails(tree, tree_baseline):
    (tree / "label_kit/event_inventory/FROZEN_a.json").write_text(
        '[{"gt_start": 0}]', encoding="utf-8"
    )
    assert "HUMAN_GT_MODIFIED" in _codes(check_no_new_human_gt(tree, tree_baseline))


# ── REG-009 provider adoption ────────────────────────────────────────────
def test_reg_009_clean_tree_passes(tree):
    assert check_no_provider_adoption(tree) == []


def test_reg_009_changing_the_default_provider_fails(tree):
    (tree / "src/v2_1_boundary.py").write_text(
        'DEFAULT_PROVIDER_NAME = "caption_text_change_point"\n', encoding="utf-8"
    )
    assert "DEFAULT_PROVIDER_CHANGED" in _codes(check_no_provider_adoption(tree))


def test_reg_009_adoption_marker_in_config_fails(tree):
    (tree / "config.yaml").write_text(
        "boundary:\n  provider: caption_text_change_point\n", encoding="utf-8"
    )
    assert "PROVIDER_ADOPTION_MARKER" in _codes(check_no_provider_adoption(tree))


def test_reg_009_adoption_marker_in_an_artifact_fails(tree):
    (tree / "results/run.json").write_text(
        '{"provider": "caption_text_change_point"}', encoding="utf-8"
    )
    assert "PROVIDER_ADOPTION_MARKER" in _codes(check_no_provider_adoption(tree))


# ── REF-003 gyeongju ─────────────────────────────────────────────────────
def test_ref_003_preexisting_artifact_is_not_a_violation(tree, tree_baseline):
    assert check_no_gyeongju_comparison(tree, tree_baseline) == []


def test_ref_003_a_new_comparison_artifact_fails(tree, tree_baseline):
    (tree / "results/wonyi_gyeongju_vs_human_report.json").write_text(
        '{"human_rows": 9, "pipeline_rows": 32}', encoding="utf-8"
    )
    assert "NEW_GYEONGJU_ARTIFACT" in _codes(
        check_no_gyeongju_comparison(tree, tree_baseline)
    )


# ── 종합 ─────────────────────────────────────────────────────────────────
def test_run_all_collects_every_violation(tree, tree_baseline):
    (tree / "src/bcs.py").write_text("changed\n", encoding="utf-8")
    (tree / "results/m9_out.json").write_text("{}", encoding="utf-8")
    (tree / "label_kit/event_inventory/FROZEN_new.json").write_text("[]",
                                                                   encoding="utf-8")
    report = run_all(tree, tree_baseline)
    assert not report.ok
    assert {"BCS_CORE_DIFF", "M9_ARTIFACT", "NEW_HUMAN_GT"} <= _codes(report.failures)


def test_every_failure_names_the_path(tree, tree_baseline):
    (tree / "src/bcs.py").write_text("changed\n", encoding="utf-8")
    for failure in run_all(tree, tree_baseline).failures:
        assert failure.detail


def test_digest_ignores_line_endings(tmp_path):
    unix, windows = tmp_path / "a", tmp_path / "b"
    unix.write_bytes(b"line\nline\n")
    windows.write_bytes(b"line\r\nline\r\n")
    assert digest(unix) == digest(windows)
