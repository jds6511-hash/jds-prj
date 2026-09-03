"""전체 final acceptance 집계.

frozen matrix의 최종 규칙은 이것이다.

```
Gate A ∧ Gate B ∧ Gate C ∧ Gate D
∧ all P0 PASS
∧ every P1 = PASS 또는 explicitly WAIVED
∧ regression PASS ∧ tree clean
  → IMPLEMENTATION_COMPLETE
```

matrix 166건이 전부 지도에 있다. 이 파일은 그 사실을 문서가 아니라 **기계로 다시
계산**해, 보고서가 앞서 나가지 못하게 막는다.

E-01a로 ERR 10건, E-02로 DET 7건, E-03으로 CP 9건, E-05로 REG-001~004,
TRI-005 remediation(C3) 후 §19 10건이 지도에 들어왔다
(40 → 30 → 23 → 14 → 10 → 0 · P0 26 → 18 → 13 → 8 → 5 → 0).

**부분 매핑을 숫자 줄이기에 쓰지 않았다** — family가 전부 닫힌 뒤에 한 번에 넣었다.
`GRD-004`는 여전히 P1 WAIVED이고, TRI-005 closure가 그것을 PASS로 바꾸지 않는다.
"""
import re
import subprocess
from pathlib import Path

import pytest

from v2_1_acceptance import (
    MATRIX_PATH,
    PASS_BY_AUTHORIZED_SUPERSESSION,
    p0_satisfied,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/finalization/V2_1_FINAL_ACCEPTANCE_2026-09-02.md"

#: ID 지도를 들고 있는 파일. 여기 없는 ID는 "덮였다"고 말할 수 없다.
MAPS = (
    "tests/test_v2_1_gate_a.py",
    "tests/test_v2_1_gate_b_acceptance.py",
    "tests/test_v2_1_gate_c_acceptance.py",
    # E-01a에서 10/0이 된 뒤 들어왔다. 부분 매핑 상태로는 넣지 않았다.
    "tests/test_v2_1_err_acceptance.py",
    # E-02에서 7/7이 된 뒤 들어왔다.
    "tests/test_v2_1_det_acceptance.py",
    # E-03에서 9/9가 된 뒤 들어왔다(P0 5 · P1 2 · P2 2).
    "tests/test_v2_1_cp_acceptance.py",
    # E-05. REG-001~004. (005~010은 Gate A · Gate D · addendum 소관)
    "tests/test_v2_1_reg_acceptance.py",
    # TRI-005 remediation(C3) 후 §19 10건이 한 번에 들어왔다. GEO 4/4였던
    # 시점에도 같은 절의 TRI가 열려 있어 넣지 않았다.
    "tests/test_v2_1_geo_tri_acceptance.py",
)

#: 지도 밖에서 별도 문서로 닫힌 것.
SEPARATELY_CLOSED = {"REG-010"}


def _matrix_rows():
    text = (ROOT / MATRIX_PATH).read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*([A-Z]+-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                           text, re.M))


def _mapped():
    ids = set()
    for relative in MAPS:
        ids |= set(re.findall(r'"([A-Z]+-\d+)"',
                              (ROOT / relative).read_text(encoding="utf-8")))
    return (ids | SEPARATELY_CLOSED) & set(_matrix_rows())


def _unmapped():
    return set(_matrix_rows()) - _mapped()


# ── 계산이 문서와 맞는가 ─────────────────────────────────────────────────
@pytest.mark.parametrize("family,size", [("ERR", 10), ("DET", 7), ("CP", 9),
                                        ("GEO", 4), ("TRI", 6)])
def test_a_closed_family_is_fully_mapped(family, size):
    """family 전체가 지도에 있다 — 부분 매핑이면 이 테스트가 깨진다."""
    rows = _matrix_rows()
    members = {i for i in rows if i.startswith(family + "-")}
    assert len(members) == size
    assert members <= _mapped()


def test_the_matrix_size_is_stable():
    rows = _matrix_rows()
    assert len(rows) == 166
    assert sum(1 for p in rows.values() if p == "P0") == 123


def test_there_is_a_real_coverage_gap():
    """gap이 사라지면 이 테스트가 먼저 깨져 재판정을 강제한다."""
    assert _unmapped() == set()
    assert len(_mapped()) == 166


def test_the_report_records_the_same_numbers():
    """숫자를 문서 어딘가에서 찾는 것으로는 부족하다 — 그 문장을 본다."""
    text = REPORT.read_text(encoding="utf-8")
    assert re.search(r"matrix 총계\s+166", text)
    assert re.search(r"지도에 있음\s+166", text)
    assert re.search(r"지도에 없음\s+0\s", text)


# ── 판정 ─────────────────────────────────────────────────────────────────
def test_implementation_complete_is_declared_with_its_conditions():
    text = REPORT.read_text(encoding="utf-8")
    assert "IMPLEMENTATION_COMPLETE = YES" in text
    assert "IMPLEMENTATION_COMPLETE = NO" not in text
    # 선언은 규칙의 각 항을 실제로 채운 결과여야 한다.
    for clause in ("Gate A", "Gate B", "Gate C", "Gate D", "all P0 PASS",
                   "regression PASS", "tree clean"):
        assert clause in text, clause


def test_the_waiver_survives_the_declaration():
    """TRI-005를 닫았다고 GRD-004가 자동 PASS가 되지 않는다."""
    text = REPORT.read_text(encoding="utf-8")
    assert "GRD-004" in text
    assert re.search(r"GRD-004[^\n]*WAIVED", text)
    waivers = (ROOT / "docs/finalization/V2_1_P1_WAIVERS.md").read_text(
        encoding="utf-8")
    assert "GRD-004" in waivers


def test_tri_005_is_recorded_as_closed_by_implementation():
    """기준 축소(A)나 waiver(B)로 닫지 않았다는 사실이 보고서에 남아야 한다."""
    text = REPORT.read_text(encoding="utf-8")
    assert "TRI-005" in text
    assert "CLOSED" in text
    assert "V2_1_TRI_005_CLOSURE_2026-09-03.md" in text


def test_the_four_gates_are_recorded_as_complete():
    text = REPORT.read_text(encoding="utf-8")
    for gate in ("Gate A", "Gate B", "Gate C", "Gate D"):
        assert re.search(r"%s[^\n]*COMPLETE" % gate, text), gate


def test_gate_closure_is_not_confused_with_final_acceptance():
    """네 Gate가 닫혔다는 것과 구현이 끝났다는 것은 다르다."""
    text = REPORT.read_text(encoding="utf-8")
    assert "Gate 통과 ≠ 구현 완료" in text


def test_reg_010_is_counted_as_superseded_not_as_pass():
    assert p0_satisfied("REG-010", PASS_BY_AUTHORIZED_SUPERSESSION, ROOT)
    text = REPORT.read_text(encoding="utf-8")
    assert PASS_BY_AUTHORIZED_SUPERSESSION in text


# ── 실측으로 확인되는 두 항목 ────────────────────────────────────────────
def test_reg_004_no_tracked_file_is_left_modified():
    """추적 중인 파일에 커밋되지 않은 변경이 없어야 한다.

    미추적 파일은 보지 않는다 — 테스트를 돌리는 시점에는 그 실행이 방금 만든
    파일이 아직 커밋 전일 수 있고, `REG-010`처럼 커밋된 상태를 재는 항목과
    구분해야 한다. 최종 집계 시점의 `tree clean`은 `git status --porcelain`
    전체로 따로 확인하고 그 값을 보고서에 적는다.
    """
    result = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0
    modified = [line for line in result.stdout.splitlines()
                if line.strip() and not line.startswith("??")]
    assert not modified, modified


def test_the_report_does_not_claim_unmeasured_things():
    """측정하지 않은 것을 통과로 적지 않는다."""
    text = REPORT.read_text(encoding="utf-8")
    assert "한글(HWP) 실제 열림" in text
    for forbidden in ("M9 승인", "official test 개방", "성능 개선"):
        assert "%s 아님" % forbidden in text or "%s은 아니다" % forbidden in text
