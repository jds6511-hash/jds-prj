"""REG-010 authorization addendum — supersession을 좁게 연다.

```
REG-010 ORIGINAL          P0 · push = NO           frozen matrix 그대로
REG-010 EFFECTIVE STATUS  PASS_BY_AUTHORIZED_SUPERSESSION
```

`waiver`와 구분한다. waiver는 원 규칙이 그대로인 채 실패를 수용하는 것이고,
supersession은 후속 명시적 결정이 **그 범위의 운영 규칙 자체를** 바꾼 것이다.

이 파일이 지키는 것은 하나다 — **이 상태가 다른 P0의 우회로가 되지 않는 것.**
"""
import re
import shutil
from pathlib import Path

import pytest

from v2_1_acceptance import (
    ADDENDUM_PATH,
    AUTHORIZED_SUPERSESSION_IDS,
    FAIL,
    MATRIX_PATH,
    PASS,
    PASS_BY_AUTHORIZED_SUPERSESSION,
    REQUIRED_SECTIONS,
    WAIVED,
    authorization_recorded,
    frozen_criterion_intact,
    p0_satisfied,
)

ROOT = Path(__file__).resolve().parents[1]
ADDENDUM = ROOT / ADDENDUM_PATH


@pytest.fixture
def tree(tmp_path):
    """addendum과 matrix만 복사한 합성 트리. 실제 문서를 건드리지 않는다."""
    root = tmp_path / "repo"
    for relative in (ADDENDUM_PATH, MATRIX_PATH):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


# ── 원 기준은 그대로 있다 ────────────────────────────────────────────────
def test_the_frozen_criterion_is_still_recorded():
    """matrix 본문을 고치지 않았다."""
    assert frozen_criterion_intact(ROOT)
    matrix = (ROOT / MATRIX_PATH).read_text(encoding="utf-8")
    assert re.search(r"\|\s*REG-010\s*\|\s*P0\s*\|\s*push\s*\|\s*NO", matrix)


def test_overwriting_the_frozen_criterion_breaks_the_supersession(tree):
    """원 기준을 덮어쓰면 그것은 supersession이 아니라 rewrite다."""
    matrix = tree / MATRIX_PATH
    matrix.write_text(
        matrix.read_text(encoding="utf-8").replace(
            "| REG-010 | P0 | push | NO 유지",
            "| REG-010 | P0 | push | PASS"),
        encoding="utf-8")
    assert not frozen_criterion_intact(tree)
    assert not p0_satisfied("REG-010", PASS_BY_AUTHORIZED_SUPERSESSION, tree)


def test_deleting_the_historical_rule_breaks_it(tree):
    matrix = tree / MATRIX_PATH
    matrix.write_text(
        "\n".join(line for line in matrix.read_text(encoding="utf-8").splitlines()
                  if "REG-010" not in line),
        encoding="utf-8")
    assert not p0_satisfied("REG-010", PASS_BY_AUTHORIZED_SUPERSESSION, tree)


# ── addendum이 근거다 ───────────────────────────────────────────────────
def test_the_addendum_is_complete():
    assert authorization_recorded(ROOT)
    text = ADDENDUM.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text


def test_the_addendum_points_at_real_commits():
    """근거 pointer는 저장소에서 확인된 값이어야 한다."""
    import subprocess

    text = ADDENDUM.read_text(encoding="utf-8")
    shas = {s for s in re.findall(r"\b[0-9a-f]{7}\b", text)}
    assert shas, "commit pointer가 없다"
    resolved = [
        s for s in shas
        if subprocess.run(["git", "cat-file", "-e", "%s^{commit}" % s],
                          cwd=ROOT, capture_output=True).returncode == 0
    ]
    assert len(resolved) >= 2, "실재하는 커밋 pointer가 둘 이상이어야 한다: %r" % shas


def test_deleting_the_addendum_fails_final_acceptance(tree):
    (tree / ADDENDUM_PATH).unlink()
    assert not authorization_recorded(tree)
    assert not p0_satisfied("REG-010", PASS_BY_AUTHORIZED_SUPERSESSION, tree)


@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_a_missing_section_invalidates_the_authorization(tree, section):
    path = tree / ADDENDUM_PATH
    path.write_text(path.read_text(encoding="utf-8").replace(section, "…"),
                    encoding="utf-8")
    assert not authorization_recorded(tree)


def test_an_addendum_without_evidence_pointers_is_not_enough(tree):
    path = tree / ADDENDUM_PATH
    path.write_text(re.sub(r"\b[0-9a-f]{7,40}\b", "(생략)",
                           path.read_text(encoding="utf-8")),
                    encoding="utf-8")
    assert not authorization_recorded(tree)


# ── 상태 어휘를 뭉치지 않는다 ────────────────────────────────────────────
def test_supersession_is_not_recorded_as_an_ordinary_pass():
    text = ADDENDUM.read_text(encoding="utf-8")
    assert "not ordinary PASS" in text
    assert "REG-010 EFFECTIVE STATUS" in text
    assert PASS_BY_AUTHORIZED_SUPERSESSION in text


def test_supersession_is_not_recorded_as_a_waiver():
    text = ADDENDUM.read_text(encoding="utf-8")
    assert "not WAIVED" in text
    register = (ROOT / "docs/finalization/V2_1_P1_WAIVERS.md").read_text(
        encoding="utf-8")
    assert "REG-010" not in register


def test_a_waived_p0_does_not_satisfy_final_acceptance(tree):
    """P1 waiver 규칙을 P0로 끌어오지 않는다."""
    assert not p0_satisfied("REG-010", WAIVED, tree)
    assert not p0_satisfied("REG-010", FAIL, tree)


# ── 범위를 잠근다 ────────────────────────────────────────────────────────
def test_only_reg_010_may_use_the_supersession_status(tree):
    assert AUTHORIZED_SUPERSESSION_IDS == ("REG-010",)
    assert p0_satisfied("REG-010", PASS_BY_AUTHORIZED_SUPERSESSION, tree)
    for other in ("REG-005", "REG-006", "REG-007", "GRD-004", "RPT-008"):
        assert not p0_satisfied(other, PASS_BY_AUTHORIZED_SUPERSESSION, tree)


def test_an_ordinary_pass_still_works_for_everything(tree):
    for acceptance_id in ("REG-005", "RPT-008", "REG-010"):
        assert p0_satisfied(acceptance_id, PASS, tree)


def test_an_unknown_status_is_refused(tree):
    with pytest.raises(ValueError):
        p0_satisfied("REG-010", "PROBABLY_FINE", tree)


def test_unauthorized_push_is_still_prohibited():
    """승인 범위 밖의 push까지 허용한다고 읽으면 안 된다."""
    text = ADDENDUM.read_text(encoding="utf-8")
    assert "pushes without explicit authorization" in text
    assert "여전히 금지다" in text
    assert "authorization_scope" in text


def test_the_forbidden_readings_are_written_down():
    text = ADDENDUM.read_text(encoding="utf-8")
    for reading in ("이후 push는 전부 허용", "더 이상 적용되지 않음",
                    "사실 PASS였음"):
        assert reading in text


def test_the_guard_limitation_is_recorded_separately():
    """A-11 구멍은 이 addendum과 섞지 않는다 — 기록만 남긴다."""
    text = ADDENDUM.read_text(encoding="utf-8")
    assert "KNOWN-GUARD-LIMITATION" in text
    assert "check_no_m9_execution" in text
    assert "A-11을 지금 고치지 않는다" in text
