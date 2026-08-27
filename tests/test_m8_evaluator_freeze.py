"""evaluator 동결 artifact — M8 공식 생성 **전** 시점의 대조 가능성.

테스트는 pytest를 재귀 실행하지 않는다(`run_tests=False`).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import m8_evaluator_freeze as F                                    # noqa: E402


@pytest.fixture(scope="module")
def art():
    return F.build_artifact(run_tests=False)


def test_records_gt_aggregate_hash(art):
    assert len(art["aggregate_gt_sha256"]) == 64
    assert art["n_reference_events"] == 68 and art["n_videos"] == 8


def test_has_a_hash_per_gate(art):
    assert set(art["gate_implementation_sha256"]) == {"C1", "C2", "C3"}
    for v in art["gate_implementation_sha256"].values():
        assert len(v) == 64


def test_gate_hash_changes_when_its_functions_change():
    """구현이 바뀌면 해시가 움직여야 대조가 의미를 가진다."""
    a = F.gate_hash("C3")
    b = F.gate_hash("C3", extra_sources=["# 한 줄 추가"])
    assert a != b


def test_spec_docs_are_hashed(art):
    d = art["spec_doc_sha256"]
    assert d["gate_spec"] and d["gate_rules"] and d["event_metric_spec"]
    assert d["gt_freeze"]


def test_evaluator_sources_are_hashed(art):
    s = art["evaluator_source_sha256"]
    for k in ("m8_c1", "m8_metrics", "m8_gates", "event_inventory_kit"):
        assert len(s[k]) == 64


def test_official_output_not_viewed_is_evidenced(art):
    """선언이 아니라 실측이다 — 패널 8편에 리포트 파일이 없다는 것을 센다."""
    assert art["official_m8_output_viewed"] is False
    ev = art["official_output_evidence"]
    assert ev["report_files_found"] == 0 and ev["videos_scanned"] == 8


def test_c2_metric_and_unmatched_handling_are_recorded(art):
    """C2는 2026-08-27에 주지표로 확정됐다. **θ recall은 진단으로 분리 기록된다.**

    미매칭 정답 사건 처리(매칭 실패 = 0)도 artifact에 박는다 — 그 정의가
    값을 크게 바꾸므로 나중에 "그때 어느 쪽이었나"를 물을 수 있어야 한다.
    """
    assert art["c2_metric_decided"] is True
    assert art["c2_metric"] == "event_temporal_alignment"
    assert len(art["c2_diagnostics_only"]) == 3
    assert all(d.startswith("temporal_event_recall@") for d in art["c2_diagnostics_only"])
    assert "매칭 실패 = 0" in art["c2_unmatched_reference_handling"]


def test_frozen_gate_constants_are_recorded(art):
    g = art["frozen_gate_constants"]
    assert g["C1_threshold_videos"] == 0
    assert g["C1_statuses"] == ["PRESENT", "ABSENT", "UNCLEAR"]
    assert g["C1_repetition_min_run"] == 3
    assert g["C2_statistic"] == "median" and g["C2_threshold"] == 0.70
    assert g["C3_statistic"] == "max" and g["C3_threshold"] == 2.0


def test_verify_reports_no_drift_right_after_build(art):
    assert F.verify(art) == []


def test_verify_detects_drift(art):
    bad = {**art, "evaluator_source_sha256":
           {**art["evaluator_source_sha256"], "m8_metrics": "0" * 64}}
    diffs = F.verify(bad)
    assert any("m8_metrics" in d for d in diffs)


def test_build_refuses_when_gt_not_frozen(tmp_path):
    with pytest.raises(Exception):
        F.build_artifact(run_tests=False, gt_dir=tmp_path)


def test_file_hash_ignores_line_endings(tmp_path, monkeypatch):
    """**줄바꿈만으로 verify가 깨지면 대조 도구가 아니다.**

    Windows에서 git checkout이 LF를 CRLF로 바꾼다 — 같은 커밋을 되돌린 직후
    verify가 깨진 실측(2026-08-27)이 이 테스트의 이유다.
    """
    lf, crlf = tmp_path / "lf.md", tmp_path / "crlf.md"
    lf.write_bytes(b"a\nb\n")
    crlf.write_bytes(b"a\r\nb\r\n")
    monkeypatch.setattr(F, "ROOT", tmp_path)
    assert F._sha_file("lf.md") == F._sha_file("crlf.md")


def test_git_dirty_excludes_its_own_output(monkeypatch):
    """artifact는 쓰이는 순간 untracked다 — 자기 자신을 오염으로 세면 그 필드가
    항상 true가 되고, 항상 true인 필드로는 진짜 오염을 못 가린다."""
    own = F._rel_out()
    assert own.endswith("m8_evaluator_freeze_2026-08-27.json")
    monkeypatch.setattr(F, "_git", lambda *a: f"?? {own}")
    assert F.git_dirty(exclude=[own]) is False
    assert F.git_dirty(exclude=[]) is True


def test_git_dirty_parses_stripped_leading_space(monkeypatch):
    """`_git`이 stdout을 strip해서 첫 줄의 선행 공백이 사라진다.

    고정 인덱스로 자르면 경로 첫 글자를 먹어 제외가 조용히 실패했다(실측).
    """
    own = F._rel_out()
    monkeypatch.setattr(F, "_git", lambda *a: f"M {own}")     # ' M ' 아니라 'M '
    assert F.git_dirty(exclude=[own]) is False


def test_git_dirty_still_sees_real_changes(monkeypatch):
    own = F._rel_out()
    porcelain = f"?? {own}\n M src/m8_c1.py"
    monkeypatch.setattr(F, "_git", lambda *a: porcelain)
    assert F.git_dirty(exclude=[own]) is True
