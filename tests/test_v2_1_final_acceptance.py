"""전체 final acceptance 집계 — 아직 선언하지 않는다.

frozen matrix의 최종 규칙은 이것이다.

```
Gate A ∧ Gate B ∧ Gate C ∧ Gate D
∧ all P0 PASS
∧ every P1 = PASS 또는 explicitly WAIVED
∧ regression PASS ∧ tree clean
  → IMPLEMENTATION_COMPLETE
```

네 Gate는 닫혔지만 **matrix 166건 중 23건이 어느 지도에도 없다**(P0 13건). 그래서
`IMPLEMENTATION_COMPLETE = NO`다. 이 파일은 그 사실을 기계로 다시 계산해, 문서가
앞서 나가지 못하게 막는다.

E-01a로 ERR 10건, E-02로 DET 7건이 지도에 들어왔다(40 → 30 → 23 · P0 26 → 18 → 13).
나머지 네 family는 그대로 열려 있다.
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
@pytest.mark.parametrize("family,size", [("ERR", 10), ("DET", 7)])
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
    unmapped = _unmapped()
    assert unmapped, "gap이 없어졌다면 최종 판정을 다시 해야 한다"
    rows = _matrix_rows()
    families = {i.split("-")[0] for i in unmapped}
    assert families == {"CP", "GEO", "TRI", "REG"}
    assert sum(1 for i in unmapped if rows[i] == "P0") == 13


def test_the_report_records_the_same_numbers():
    """숫자를 문서 어딘가에서 찾는 것으로는 부족하다 — 그 문장을 본다."""
    text = REPORT.read_text(encoding="utf-8")
    rows = _matrix_rows()
    unmapped = _unmapped()
    assert re.search(r"matrix 총계\s+166", text)
    assert re.search(r"지도에 없음\s+%d\s" % len(unmapped), text)
    assert re.search(r"P0 %d" % sum(1 for i in unmapped if rows[i] == "P0"), text)


@pytest.mark.parametrize("family", ["CP", "GEO", "TRI", "REG"])
def test_every_uncovered_family_keeps_its_row(family):
    """family 글자가 문서 어딘가에 있는 것으로는 부족하다 — 표의 행을 본다."""
    rows = _matrix_rows()
    unmapped = _unmapped()
    mine = [i for i in unmapped if i.startswith(family + "-")]
    total = len(mine)
    p0 = sum(1 for i in mine if rows[i] == "P0")
    text = REPORT.read_text(encoding="utf-8")
    assert re.search(r"^%s\s+%d\s+%d\s" % (family, total, p0), text, re.M), family


# ── 판정 ─────────────────────────────────────────────────────────────────
def test_implementation_complete_is_not_declared():
    text = REPORT.read_text(encoding="utf-8")
    assert "IMPLEMENTATION_COMPLETE = NO" in text
    assert "IMPLEMENTATION_COMPLETE = YES" not in text


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
