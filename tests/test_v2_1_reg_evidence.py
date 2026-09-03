"""E-05 REG-001~004 증거 — 저장소 게이트를 실측으로 잰다.

```
REG-001 P0  pre-existing tests    regression 없음
REG-002 P0  new v2.1 P0 suite     전부 PASS
REG-003 P1  P1 suite              전부 PASS 또는 명시적 blocker
REG-004 P0  tree status           clean
```

`REG-001`은 "테스트가 다 green이다"로 닫지 않는다. **v2.1이 기존 production 코드를
건드리지 않았다**는 것을 git으로 확인하고, 기존 테스트에 가한 변경을 전수로 본다.

`REG-002 · REG-003`은 "숫자가 크다"로 닫지 않는다. 지도에 있는 P0/P1 노드가 전부
실재하는지, 그리고 **skip·xfail로 닫힌 항목이 없는지**를 본다(waiver 대장 §규칙:
"skip을 waiver로 간주하지 않는다").
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"
WAIVERS = ROOT / "docs/finalization/V2_1_P1_WAIVERS.md"
AUDIT = ROOT / "docs/finalization/V2_1_E05_REG_AUDIT_2026-09-02.md"

#: v2.1 구현 착수 커밋. `V2_1_IMPLEMENTATION_AUTHORIZATION_2026-08-30.md`가 가리킨다.
V2_1_START = "7f5d0f9"

#: 지도 파일 전부. 노드 실재 검사는 이 합집합으로 한다.
MAP_FILES = (
    "tests/test_v2_1_gate_a.py",
    "tests/test_v2_1_gate_b_acceptance.py",
    "tests/test_v2_1_gate_c_acceptance.py",
    "tests/test_v2_1_err_acceptance.py",
    "tests/test_v2_1_det_acceptance.py",
    "tests/test_v2_1_cp_acceptance.py",
    "tests/test_v2_1_geo_tri_acceptance.py",
    "tests/test_v2_1_reg_acceptance.py",
)

#: **집계에 실제로 편입된** 지도. `tests/test_v2_1_final_acceptance.py::MAPS`와 같아야
#: 한다 — TRI-005 closure로 §19까지 들어와 이제 둘이 같다.
WIRED_MAP_FILES = MAP_FILES

#: 이 파일 자신은 marker 문자열을 데이터로 들고 있다 — 자기 검사에서 제외한다.
SELF = "tests/test_v2_1_reg_evidence.py"

#: v2.1 작업 중 변경이 허용된 기존 테스트. 하나뿐이고 사유가 있다.
ALLOWED_PREEXISTING_TEST_CHANGE = "tests/test_final_report_supplement.py"

#: 한때 xfail이 허용된 유일한 파일이었다(TRI-005 gap 고정용). C3 remediation으로
#: XPASS가 잡히면서 marker를 제거했고, 지금은 **어느 v2.1 테스트에도 marker가
#: 없다.** 예외 자리를 비워 두지 않고 계약을 0건으로 올린다.
FORMER_MARKER_FILE = "tests/test_v2_1_tri_005_gap.py"


def _git(*args) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stderr
    return result.stdout


def _matrix_rows():
    text = MATRIX.read_text(encoding="utf-8")
    return dict(re.findall(r"^\|\s*([A-Z]+-\d+)\s*\|\s*\*{0,2}(P\d)\*{0,2}\s*\|",
                           text, re.M))


def _mapped_nodes():
    nodes = set()
    for relative in MAP_FILES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        nodes |= set(re.findall(r'"(test_[a-z0-9_]+\.py::[^"]+)"', text))
    # `startswith` 검사용으로 적힌 **접두 문자열**은 노드가 아니다. 다른 노드의
    # 접두인 항목을 뺀다.
    return {node for node in nodes
            if not any(other != node and other.startswith(node)
                       for other in nodes)}


# ── REG-001 기존 코드에 regression을 넣지 않았다 ─────────────────────────
def test_reg_001_v2_1_did_not_touch_any_pre_existing_production_module():
    """v2.1은 production에서 **가산적**이었다. git으로 확인한다."""
    changed = [line for line in
               _git("diff", "--name-only", "%s~1..HEAD" % V2_1_START,
                    "--", "src/", "scripts/").splitlines() if line.strip()]
    assert changed, "변경 목록이 비었다 — 기준 커밋이 틀렸을 수 있다"
    foreign = [path for path in changed if "v2_1" not in path
               and "c0_boundary" not in path]
    assert not foreign, "기존 production 모듈을 건드렸다: %r" % foreign


def test_reg_001_only_one_pre_existing_test_file_changed_and_it_was_strengthened():
    """기존 테스트 변경은 한 건이고, 원 기록을 지우지 않고 강화한 것이다."""
    changed = [line for line in
               _git("diff", "--name-only", "%s~1..HEAD" % V2_1_START,
                    "--", "tests/").splitlines() if line.strip()]
    pre_existing = [path for path in changed if "v2_1" not in path]
    assert pre_existing == [ALLOWED_PREEXISTING_TEST_CHANGE], pre_existing

    # 작성 시점 기록("NOT GRANTED")이 지워지지 않았다.
    text = (ROOT / ALLOWED_PREEXISTING_TEST_CHANGE).read_text(encoding="utf-8")
    assert "implementation authorization      NOT GRANTED" in text
    assert "implementation authorization      GRANTED 2026-08-30" in text
    assert 'startswith("DEFERRED")' in text


def test_reg_001_the_frozen_modules_are_still_frozen():
    """BCS core는 v2.1 전 구간에서 diff 0이어야 한다(REG-005와 같은 대상)."""
    from v2_1_guards import BCS_PROTECTED

    changed = set(_git("diff", "--name-only", "%s~1..HEAD" % V2_1_START,
                       "--", *BCS_PROTECTED).split())
    assert not changed, changed


def test_reg_001_the_search_pipeline_is_untouched():
    """검색 파이프라인(M1~M7) 동결. config도 함께 본다."""
    targets = ["src/m1_%s" % "ingest.py"] + [
        "src/m%d_*.py" % n for n in range(2, 8)]
    changed = [line for line in
               _git("diff", "--name-only", "%s~1..HEAD" % V2_1_START,
                    "--", "src/", "config.yaml").splitlines()
               if re.match(r"src/m[1-7]_|config\.yaml", line)]
    assert not changed, changed
    assert targets                     # 목록이 비어 검사가 무의미해지지 않게


# ── REG-002 P0 suite ─────────────────────────────────────────────────────
def test_reg_002_every_mapped_node_exists():
    """지도에 적힌 노드가 전부 실재한다. 합집합으로 한 번 더 본다."""
    missing = []
    for node in sorted(_mapped_nodes()):
        filename, function = node.split("::")
        path = ROOT / "tests" / filename
        if not path.is_file() or not re.search(
                r"^def %s\(" % re.escape(function),
                path.read_text(encoding="utf-8"), re.M):
            missing.append(node)
    assert not missing, missing


def test_reg_002_no_p0_is_closed_by_a_skip_or_an_xfail():
    """skip은 waiver가 아니다 — P0를 marker로 닫는 경로를 막는다."""
    offenders = []
    for path in sorted((ROOT / "tests").glob("test_v2_1_*.py")):
        relative = "tests/%s" % path.name
        if relative == SELF:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ("pytest.mark.skip", "pytest.mark.xfail", "pytest.skip("):
            if marker in text:
                offenders.append((relative, marker))
    assert not offenders, offenders


def test_reg_002_the_former_marker_file_carries_no_marker_any_more():
    """TRI-005 xfail 2건은 remediation과 함께 제거됐다 — XPASS로 닫지 않았다."""
    text = (ROOT / FORMER_MARKER_FILE).read_text(encoding="utf-8")
    assert "pytest.mark.xfail" not in text
    assert "pytest.mark.skip" not in text
    # 계약은 사라지지 않았다. 같은 counterexample을 평범한 테스트로 잰다.
    assert "def test_tri_005_an_unsupported_continuation_must_not_be_accepted" in text
    assert "def test_tri_005_an_unsupported_quantity_must_not_be_accepted" in text


def test_reg_002_no_p0_is_left_unmapped():
    """P0 미매핑이 남아 있으면 REG-002를 다시 판정해야 한다."""
    rows = _matrix_rows()
    mapped_ids = set()
    for relative in WIRED_MAP_FILES:
        mapped_ids |= set(re.findall(
            r'"([A-Z]+-\d+)"', (ROOT / relative).read_text(encoding="utf-8")))
    mapped_ids |= {"REG-010"}
    unmapped_p0 = {i for i, p in rows.items()
                   if p == "P0" and i not in mapped_ids}
    assert unmapped_p0 == set()
    assert sum(1 for p in rows.values() if p == "P0") == 123


def test_reg_002_the_wired_map_list_matches_the_tally():
    """집계 대상 지도 목록이 실제 집계 파일과 어긋나면 숫자가 거짓이 된다."""
    final = (ROOT / "tests/test_v2_1_final_acceptance.py").read_text(
        encoding="utf-8")
    block = final.split("MAPS = (", 1)[1].split("\n)", 1)[0]
    wired = set(re.findall(r'"([^"]+)"', block))
    assert wired == set(WIRED_MAP_FILES), wired ^ set(WIRED_MAP_FILES)


# ── REG-003 P1 suite ─────────────────────────────────────────────────────
def test_reg_003_the_only_waived_item_is_grd_004():
    register = WAIVERS.read_text(encoding="utf-8")
    waived = re.findall(r"^### ([A-Z]+-\d+)", register, re.M)
    assert waived == ["GRD-004"], waived
    assert "WAIVED" in register


def test_reg_003_the_register_refuses_skip_as_a_waiver():
    register = WAIVERS.read_text(encoding="utf-8")
    assert "skip을 waiver로 간주하지 않는다" in register
    assert "P1 FAIL + waiver 없음" in register


def test_reg_003_the_waiver_records_every_required_field():
    """대장이 요구하는 항목이 실제로 채워져 있는가."""
    section = WAIVERS.read_text(encoding="utf-8").split("### GRD-004", 1)[1]
    for field in ("failure description", "reason waiver is acceptable",
                  "known impact", "scope of limitation"):
        assert field in section, field
    assert "승인자" in section and "날짜" in section


def test_reg_003_the_waived_id_is_p1_in_the_matrix():
    """P0를 waiver로 닫는 경로가 없다."""
    rows = _matrix_rows()
    assert rows["GRD-004"] == "P1"
    register = WAIVERS.read_text(encoding="utf-8")
    for acceptance_id, priority in rows.items():
        if priority == "P0":
            assert not re.search(r"^### %s" % acceptance_id, register, re.M), \
                acceptance_id


# ── REG-004 tree status ──────────────────────────────────────────────────
def test_reg_004_no_tracked_file_is_modified():
    porcelain = _git("status", "--porcelain").splitlines()
    modified = [line for line in porcelain
                if line.strip() and not line.startswith("??")]
    assert not modified, modified


def test_reg_004_the_full_porcelain_is_recorded_in_the_audit():
    """미추적 파일까지 포함한 실제 상태를 문서가 적고 있어야 한다.

    `clean`을 "추적 파일 무변경"으로만 읽고 미추적을 숨기지 않는다.
    """
    porcelain = [line for line in _git("status", "--porcelain").splitlines()
                 if line.strip()]
    text = AUDIT.read_text(encoding="utf-8")
    assert re.search(r"untracked\s+%d" % len([
        line for line in porcelain if line.startswith("??")]), text)
    assert re.search(r"tracked modified\s+%d" % len([
        line for line in porcelain if not line.startswith("??")]), text)


def test_reg_004_head_matches_the_remote():
    """push된 상태와 로컬이 갈라져 있지 않다."""
    local = _git("rev-parse", "HEAD").strip()
    remote = _git("rev-parse", "origin/master").strip()
    assert local == remote, (local, remote)


# ── 감사 문서 ────────────────────────────────────────────────────────────
def test_the_audit_declares_reg_closed():
    text = AUDIT.read_text(encoding="utf-8")
    assert "REG CLOSED" in text
    assert "PROVEN 4" in text and "UNPROVEN 0" in text


def test_the_audit_records_the_additive_only_finding():
    text = AUDIT.read_text(encoding="utf-8")
    assert V2_1_START in text
    assert "가산적" in text or "additive" in text
    assert ALLOWED_PREEXISTING_TEST_CHANGE in text


def test_the_audit_does_not_claim_implementation_complete():
    text = AUDIT.read_text(encoding="utf-8")
    assert "IMPLEMENTATION_COMPLETE = NO" in text
    assert "TRI-005" in text
