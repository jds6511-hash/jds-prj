"""실험 launcher — 규율을 사람이 기억하지 않아도 강제하는가.

**실패가 정답인 케이스를 먼저 적는다.** 2026-08-17 사고 3건이 전부 "주의사항으로
적혀 있었지만 실행 시점에 아무도 막지 않았다"였다. 편의 스크립트가 아니라
**차단 장치**여야 한다.

  1. 더러운 작업 트리에서 시작
  2. 로그 경로가 repo 안 (nohup 리다이렉트가 트리를 더럽힌 사고)
  3. 이미 완료된 run_id 재사용
  4. validator FAIL인데 완료 마커 기록
  5. precheck 이후 HEAD가 움직임 (편집본 ≠ 실행본)
  6. protected split(test) 접촉 — FULL 승인과 **다른** 승인이 필요하다
  7. 산출물에 provenance 없음
  8. 같은 run_id에 부분 산출물 잔존 (재개하지 않는다 — 새 run_id)
  9. 승인 없이 FULL
 10. 다른 run_id의 승인 토큰으로 FULL
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import exp_launcher as L                                   # noqa: E402


# ---- 픽스처 -------------------------------------------------------------

def _git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True,
                          encoding="utf-8", errors="replace")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    (r / "docs" / "probe.py").write_text("print('x')\n", encoding="utf-8")
    # 실사용의 run_root(`docs/probes/_scratch`)가 gitignore인 것과 같은 조건.
    # 아니면 launcher 상태 파일만으로 트리가 dirty가 된다.
    (r / ".gitignore").write_text("out/\n", encoding="utf-8")
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "init")
    return r


def _plan(repo, tmp_path, **over):
    p = {"name": "demo",
         "command": [sys.executable, "-c", "print('ok')"],
         "canary_args": ["--canary"], "full_args": [],
         "run_root": "out", "log_dir": str(tmp_path / "logs"),
         "expected_files": ["result.json"],
         "provenance_key": "provenance",
         "protected_splits": ["test"]}
    p.update(over)
    # 계획 파일은 repo **밖**에 둔다 — 안에 두면 untracked라 트리가 dirty가 되고,
    # 정작 검사하려는 dirty 게이트를 테스트가 스스로 발동시킨다
    f = tmp_path / "plan.json"
    f.write_text(json.dumps(p), encoding="utf-8")
    return f


def _finish(repo, run_id, provenance=True):
    """실험이 산출물을 남긴 상태를 흉내낸다."""
    d = repo / "out" / run_id
    d.mkdir(parents=True, exist_ok=True)
    body = {"rows": [1, 2]}
    if provenance:
        body["provenance"] = {"git_head": "x"}
    (d / "result.json").write_text(json.dumps(body), encoding="utf-8")
    return d


# ---- 1. 더러운 트리 ------------------------------------------------------

def test_precheck_refuses_dirty_tree(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    (repo / "junk.txt").write_text("x", encoding="utf-8")
    with pytest.raises(L.LauncherError, match="dirty"):
        L.precheck(plan, "r1", root=repo)


def test_precheck_passes_on_clean_tree(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    assert st["execution_commit"] and st["plan_hash"]
    assert st["stage"] == "PRECHECK"


# ---- 2. repo 안 로그 경로 / 추적되는 산출물 경로 --------------------------

def test_plan_refuses_log_dir_inside_repo(repo, tmp_path):
    f = _plan(repo, tmp_path, log_dir=str(repo / "logs"))
    with pytest.raises(L.LauncherError, match="로그 경로"):
        L.load_plan(f, root=repo)


def test_plan_refuses_tracked_output_dir(repo, tmp_path):
    """산출물 경로가 gitignore가 아니면 launcher 상태 파일만으로 트리가 더러워지고,
    validate의 git_not_dirty가 항상 실패한다."""
    f = _plan(repo, tmp_path, run_root="tracked_out")
    with pytest.raises(L.LauncherError, match="gitignore"):
        L.load_plan(f, root=repo)


# ---- 3·8. run_id 재사용 / 부분 산출물 -------------------------------------

def test_precheck_refuses_completed_run_id(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    d = _finish(repo, "r1")
    (d / "RUN_COMPLETE.json").write_text("{}", encoding="utf-8")
    with pytest.raises(L.LauncherError, match="이미 완료"):
        L.precheck(plan, "r1", root=repo)


def test_precheck_refuses_partial_output_no_resume(repo, tmp_path):
    """재개하지 않는다 — 부분 재개는 provenance와 산출물 혼합 문제를 키운다."""
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    _finish(repo, "r1")                       # 마커 없는 부분 산출물
    with pytest.raises(L.LauncherError, match="부분 산출물"):
        L.precheck(plan, "r1", root=repo)


# ---- 4. validator FAIL이면 마커 없음 -------------------------------------

def test_no_marker_when_validation_fails(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1", provenance=False)     # provenance 누락 → FAIL
    ok, checks = L.validate(plan, "r1", st, root=repo)
    assert ok is False and checks["provenance_present"] is False
    with pytest.raises(L.LauncherError, match="PASS"):
        L.finalize(plan, "r1", st, checks, ok, root=repo)
    assert not (repo / "out" / "r1" / "RUN_COMPLETE.json").exists()


def test_marker_records_plan_hash_commit_validator_version(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1")
    ok, checks = L.validate(plan, "r1", st, root=repo)
    assert ok is True
    L.finalize(plan, "r1", st, checks, ok, root=repo)
    m = json.loads((repo / "out" / "r1" / "RUN_COMPLETE.json").read_text(encoding="utf-8"))
    assert m["result"] == "PASS"
    assert m["plan_hash"] == st["plan_hash"]
    assert m["execution_commit"] == st["execution_commit"]
    assert m["validator_version"] == L.VALIDATOR_VERSION
    assert m["validated_at"]


# ---- 5. HEAD 이동 --------------------------------------------------------

def test_validate_fails_when_head_moved(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1")
    (repo / "docs" / "probe.py").write_text("print('y')\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "moved")
    ok, checks = L.validate(plan, "r1", st, root=repo)
    assert ok is False and checks["execution_commit_unchanged"] is False


# ---- 6. protected split --------------------------------------------------

def test_test_split_needs_separate_approval(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path,
                             full_args=["--split", "test"]), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    with pytest.raises(L.LauncherError, match="test"):
        L.require_stage_approval(plan, "r1", st, stage="FULL",
                                 approve_full="r1", approve_test_open=None)


def test_full_approval_does_not_grant_test_open(repo, tmp_path):
    """일반 FULL 승인과 test 개방 승인을 같은 것으로 취급하면 안 된다."""
    plan = L.load_plan(_plan(repo, tmp_path,
                             full_args=["--queries", "queries_test.jsonl"]),
                       root=repo)
    st = L.precheck(plan, "r1", root=repo)
    L.require_stage_approval(plan, "r1", st, stage="FULL",
                             approve_full="r1", approve_test_open="r1")   # 통과


# ---- 7. provenance 부재 --------------------------------------------------

def test_validate_requires_provenance_in_output(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1", provenance=False)
    ok, checks = L.validate(plan, "r1", st, root=repo)
    assert checks["provenance_present"] is False and ok is False


def test_validate_requires_expected_files(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    (repo / "out" / "r1").mkdir(parents=True, exist_ok=True)
    ok, checks = L.validate(plan, "r1", st, root=repo)
    assert checks["expected_files_present"] is False and ok is False


# ---- 9·10. FULL 승인 -----------------------------------------------------

def test_full_refused_without_approval(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    with pytest.raises(L.LauncherError, match="승인"):
        L.require_stage_approval(plan, "r1", st, stage="FULL",
                                 approve_full=None, approve_test_open=None)


def test_full_refused_with_approval_for_other_run(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    with pytest.raises(L.LauncherError, match="승인"):
        L.require_stage_approval(plan, "r1", st, stage="FULL",
                                 approve_full="r2", approve_test_open=None)


def test_canary_needs_no_approval(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    L.require_stage_approval(plan, "r1", st, stage="CANARY",
                             approve_full=None, approve_test_open=None)


# ---- 실험별 validator 훅 -------------------------------------------------

def test_experiment_hook_can_fail_run_that_common_checks_pass(repo, tmp_path):
    """공통화가 검증을 약하게 만들면 안 된다 — 실험별 검사가 추가로 걸린다."""
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1")
    ok, checks = L.validate(plan, "r1", st, root=repo,
                            hook=lambda d: {"arm_count_is_4": False})
    assert ok is False and checks["arm_count_is_4"] is False


# ---- REPORT는 검증된 산출물만 -------------------------------------------

def test_report_refuses_unvalidated_run(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1")
    with pytest.raises(L.LauncherError, match="RUN_COMPLETE"):
        L.report_inputs(plan, "r1", root=repo)


def test_report_returns_validated_files(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1")
    ok, checks = L.validate(plan, "r1", st, root=repo)
    L.finalize(plan, "r1", st, checks, ok, root=repo)
    files = L.report_inputs(plan, "r1", root=repo)
    assert [f.name for f in files] == ["result.json"]


# ---- spawn 직후 dirty 재확인 ---------------------------------------------

def test_launch_aborts_when_tree_dirtied_by_spawn(repo, tmp_path):
    """리다이렉트·런타임 파일 생성으로 시작 직후 더러워지는 유형을 잡는다."""
    plan = L.load_plan(
        _plan(repo, tmp_path,
              command=[sys.executable, "-c",
                       "open('spawned.txt','w').write('x'); import time; time.sleep(5)"]),
        root=repo)
    st = L.precheck(plan, "r1", root=repo)
    with pytest.raises(L.LauncherError, match="시작 직후"):
        L.launch(plan, "r1", st, stage="CANARY", root=repo, dirty_recheck_sec=1.0)


# ---- 실험 인터프리터 -----------------------------------------------------
#
# 두 번 연달아 났다. ① 계획에 `python`을 박았는데 서버엔 `python3`만 있다.
# ② `{python}`을 launcher의 `sys.executable`로 두니, launcher를 `/usr/bin/python3`로
# 띄운 순간 실험이 의존성 없는 시스템 파이썬에서 돌아 `ModuleNotFoundError: numpy`.
#
# 그래서 **launcher를 띄운 파이썬과 실험을 돌리는 파이썬을 분리한다.** 실험 쪽은
# `${EXP_PYTHON}`만 본다 — 호출자가 무엇으로 launcher를 띄웠는지가 실험을 바꾸지 않는다.

def _pyplan(repo, tmp_path, **over):
    over.setdefault("command",
                    ["{experiment_python}", "-c", "open('out/x','w').write('1')"])
    over.setdefault("requires_modules", ["json"])
    return _plan(repo, tmp_path, **over)


def test_experiment_python_comes_from_env_not_launcher(repo, tmp_path, monkeypatch):
    """치환값은 launcher의 `sys.executable`이 아니라 `${EXP_PYTHON}`이어야 한다."""
    monkeypatch.setenv("EXP_PYTHON", sys.executable)
    plan = L.load_plan(_pyplan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    assert st["resolved_python"] == sys.executable
    r = L.launch(plan, "r1", st, stage="CANARY", root=repo, dirty_recheck_sec=0.1)
    assert r["argv"][0] == sys.executable and r["returncode"] == 0


def test_precheck_refuses_when_exp_python_unset(repo, tmp_path, monkeypatch):
    monkeypatch.delenv("EXP_PYTHON", raising=False)
    plan = L.load_plan(_pyplan(repo, tmp_path), root=repo)
    with pytest.raises(L.LauncherError, match="EXP_PYTHON"):
        L.precheck(plan, "r1", root=repo)


def test_precheck_refuses_relative_exp_python(repo, tmp_path, monkeypatch):
    """상대 경로는 cwd에 따라 다른 인터프리터를 가리킨다."""
    monkeypatch.setenv("EXP_PYTHON", "python3")
    plan = L.load_plan(_pyplan(repo, tmp_path), root=repo)
    with pytest.raises(L.LauncherError, match="절대경로"):
        L.precheck(plan, "r1", root=repo)


def test_precheck_refuses_missing_exp_python(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("EXP_PYTHON", str(tmp_path / "nope" / "python"))
    plan = L.load_plan(_pyplan(repo, tmp_path), root=repo)
    with pytest.raises(L.LauncherError, match="실행 가능"):
        L.precheck(plan, "r1", root=repo)


def test_precheck_refuses_when_required_module_missing(repo, tmp_path, monkeypatch):
    """`numpy` 없는 인터프리터로 FULL을 돌리면 모델 로드 뒤에야 죽는다."""
    monkeypatch.setenv("EXP_PYTHON", sys.executable)
    plan = L.load_plan(
        _pyplan(repo, tmp_path, requires_modules=["json", "no_such_module_xyz"]),
        root=repo)
    with pytest.raises(L.LauncherError, match="no_such_module_xyz"):
        L.precheck(plan, "r1", root=repo)


def test_precheck_records_python_fingerprint(repo, tmp_path, monkeypatch):
    """`같은 commit인데 왜 실행이 달랐나`를 인터프리터부터 볼 수 있어야 한다."""
    monkeypatch.setenv("EXP_PYTHON", sys.executable)
    plan = L.load_plan(_pyplan(repo, tmp_path), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    fp = st["python_fingerprint"]
    assert fp["python_executable"] and fp["python_version"]
    assert "torch_version" in fp and "gpu_name" in fp        # 없으면 None


def test_plan_without_token_needs_no_exp_python(repo, tmp_path, monkeypatch):
    """`${EXP_PYTHON}`은 쓰는 계획만 강제한다 — fail-closed의 범위를 넓히지 않는다."""
    monkeypatch.delenv("EXP_PYTHON", raising=False)
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    assert L.precheck(plan, "r1", root=repo)["resolved_python"] is None


def test_plan_hash_excludes_resolved_env_values(repo, tmp_path, monkeypatch):
    """서버 고유 경로가 plan_hash에 섞이면 안 된다 — 같은 계획 파일이 기계마다
    다른 해시를 갖게 되고, 공개 이력과 대조할 수 없다."""
    f = _plan(repo, tmp_path, log_dir="${EXP_LOG_DIR}")
    monkeypatch.setenv("EXP_LOG_DIR", str(tmp_path / "a"))
    h1 = L.plan_hash(L.load_plan(f, root=repo))
    monkeypatch.setenv("EXP_LOG_DIR", str(tmp_path / "b"))
    h2 = L.plan_hash(L.load_plan(f, root=repo))
    assert h1 == h2


# ---- 환경변수 로그 경로 (공개 저장소에 서버 계정명을 박지 않기 위함) ---------

def test_log_dir_env_var_is_expanded(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("EXP_LOG_DIR", str(tmp_path / "srvlogs"))
    plan = L.load_plan(_plan(repo, tmp_path, log_dir="${EXP_LOG_DIR}"), root=repo)
    assert plan["log_dir"] == str(tmp_path / "srvlogs")


def test_unexpanded_env_var_is_refused(repo, tmp_path, monkeypatch):
    """확장 실패를 조용히 넘기면 repo 안에 `${EXP_LOG_DIR}` 디렉터리가 생긴다."""
    monkeypatch.delenv("EXP_LOG_DIR", raising=False)
    with pytest.raises(L.LauncherError, match="확장되지 않았다"):
        L.load_plan(_plan(repo, tmp_path, log_dir="${EXP_LOG_DIR}"), root=repo)


# ---- REPORT 게이트: 정답 목록 동결 전에는 사람이 읽는 산출을 만들지 않는다 ----

def _frozen(repo, vid):
    d = repo / "out" / "inv"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"FROZEN_{vid}.json").write_text("{}", encoding="utf-8")


def _validated(repo, tmp_path, **over):
    plan = L.load_plan(_plan(repo, tmp_path, **over), root=repo)
    st = L.precheck(plan, "r1", root=repo)
    _finish(repo, "r1")
    ok, checks = L.validate(plan, "r1", st, root=repo)
    L.finalize(plan, "r1", st, checks, ok, root=repo)
    return plan


def test_report_refused_until_inventory_frozen(repo, tmp_path):
    """**M8 출력 → 사람 목록** 방향의 오염을 사람 주의가 아니라 코드로 막는다.
    실행은 병렬로 해도 되지만 사람이 읽는 단계는 동결 뒤에만 연다."""
    plan = _validated(repo, tmp_path,
                      requires_frozen_inventory=["A", "B"], inventory_dir="out/inv")
    _frozen(repo, "A")                                  # B는 아직 미동결
    with pytest.raises(L.LauncherError, match="동결"):
        L.report_inputs(plan, "r1", root=repo)


def test_report_allowed_once_all_frozen(repo, tmp_path):
    plan = _validated(repo, tmp_path,
                      requires_frozen_inventory=["A", "B"], inventory_dir="out/inv")
    _frozen(repo, "A")
    _frozen(repo, "B")
    assert [f.name for f in L.report_inputs(plan, "r1", root=repo)] == ["result.json"]


def test_report_gate_absent_when_not_declared(repo, tmp_path):
    """게이트를 선언하지 않은 실험은 영향을 받지 않는다."""
    plan = _validated(repo, tmp_path)
    assert L.report_inputs(plan, "r1", root=repo)


def test_precheck_marks_run_dir_when_inventory_gate_declared(repo, tmp_path):
    """게이트는 REPORT 진입만 막는다 — 사람이 파일을 직접 여는 것까지는 못 막는다.
    표식을 남겨 **정식 열람 경로는 REPORT뿐**임을 알린다."""
    plan = L.load_plan(_plan(repo, tmp_path, requires_frozen_inventory=["A"],
                             inventory_dir="out/inv"), root=repo)
    L.precheck(plan, "r1", root=repo)
    assert (repo / "out" / "r1" / L.INSPECT_MARKER).is_file()


def test_no_marker_when_gate_not_declared(repo, tmp_path):
    plan = L.load_plan(_plan(repo, tmp_path), root=repo)
    L.precheck(plan, "r1", root=repo)
    assert not (repo / "out" / "r1" / L.INSPECT_MARKER).exists()
