"""실험 control plane — PRECHECK → CANARY → VALIDATE → [승인] → FULL → VALIDATE → REPORT.

**편의 스크립트가 아니라 차단 장치다.** 2026-08-17 사고 3건이 전부 "주의사항에는
적혀 있었는데 실행 시점에 아무도 막지 않았다"였다 — 자기 런처 셸을 `pgrep`으로
매칭해 GPU 8.5시간 유휴, 배타 플래그 조합, `/tmp` 경로 해석 차이로 **편집본 ≠
실행본**. 그리고 2×2 FULL 1차 기동은 `nohup` 리다이렉트가 repo 안에 로그를 만들어
`dirty=True`가 됐고, 6.5시간 뒤 validator에서 FAIL 날 뻔했다.

그래서 규칙을 문서가 아니라 **코드에 박는다.**

| 불변식 | 어디서 강제하나 |
|---|---|
| FULL은 자동 진입 없음 | `--approve-full <run_id>` — run_id가 일치해야 한다 |
| test 접촉은 **다른** 승인 | `--approve-test-open <run_id>`. FULL 승인이 이걸 대신하지 않는다 |
| 로그는 repo 밖 | `load_plan`이 거부 |
| 편집본 = 실행본 | precheck가 commit을 고정하고 validate가 대조 |
| 시작 직후 오염 감지 | spawn 후 한 번 더 dirty 확인 |
| `RUN_COMPLETE`는 PASS 뒤에만 | `finalize`가 유일한 기록 경로 |
| REPORT는 검증된 것만 | `report_inputs`가 마커 없으면 거부 |
| **재개하지 않는다** | 부분 산출물이 있으면 실패 → 새 run_id |

**재개(resume)를 넣지 않은 것은 누락이 아니라 결정이다.** 부분 재개는 provenance와
산출물 혼합 문제를 키운다. 필요성이 실제로 생기면 그때 별도 설계한다.

사용:
    python scripts/exp_launcher.py precheck --plan p.json --run-id r1
    python scripts/exp_launcher.py canary   --plan p.json --run-id r1
    python scripts/exp_launcher.py full     --plan p.json --run-id r1 --approve-full r1
    python scripts/exp_launcher.py validate --plan p.json --run-id r1
    python scripts/exp_launcher.py report   --plan p.json --run-id r1
"""
import argparse, datetime, hashlib, io, json, os, subprocess, sys, time
from pathlib import Path

# validator 로직이 바뀌면 올린다 — 어떤 판본이 이 결과를 승인했는지 마커에 남는다
VALIDATOR_VERSION = 1
REQUIRED_PLAN_KEYS = ("name", "command", "run_root", "log_dir", "expected_files")
# 이 문자열이 인자·경로에 있으면 test 접촉으로 본다. 넓게 잡는다 — 놓치는 쪽이
# 오탐보다 훨씬 비싸다(M9는 실행 자체가 test 접촉이다).
DEFAULT_PROTECTED = ("test",)
# 게이트는 REPORT 진입만 막는다. 사람이 파일을 직접 여는 것까지 기술적으로 막지는
# 않는다(OS 권한·암호화는 과하다). 대신 표식을 남기고 **정식 열람 경로는 REPORT뿐**
# 임을 문서·파일 양쪽에 박는다.
INSPECT_MARKER = "DO_NOT_INSPECT_BEFORE_INVENTORY_FREEZE.txt"


class LauncherError(RuntimeError):
    pass


def _git(root, *a) -> str:
    return subprocess.run(["git", *a], cwd=root, capture_output=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def repo_state(root) -> dict:
    return {"head": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain"))}


def plan_hash(plan: dict) -> str:
    """계획 내용의 해시. 마커에 남겨 **어떤 계획이 이 결과를 만들었는지** 고정한다."""
    body = {k: v for k, v in plan.items() if k != "_path"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def load_plan(path, root) -> dict:
    root = Path(root).resolve()
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_PLAN_KEYS if k not in plan]
    if missing:
        raise LauncherError(f"계획에 필수 키 누락: {missing}")
    # 서버 로그 경로에는 계정명이 들어가는데 계획 파일은 추적된다(공개 저장소).
    # `${EXP_LOG_DIR}` 같은 환경변수로 두고 실행 시점에 확장한다.
    plan["log_dir"] = os.path.expandvars(plan["log_dir"])
    if "$" in plan["log_dir"]:
        raise LauncherError(
            f"log_dir의 환경변수가 확장되지 않았다: {plan['log_dir']} — "
            f"실행 전에 export 하라")
    # nohup 리다이렉트가 repo 안에 로그를 만들어 트리를 더럽힌 사고(2026-08-17).
    # 주의사항이 아니라 여기서 막는다.
    log = Path(plan["log_dir"]).resolve()
    if log == root or root in log.parents:
        raise LauncherError(f"로그 경로가 repo 안이다: {log} — 작업 트리를 더럽힌다")
    # 산출물 경로가 repo 안이면서 추적 대상이면 **launcher 자신의 상태 파일만으로도**
    # 트리가 dirty가 되고, 그러면 validate의 git_not_dirty가 항상 실패한다.
    out = (root / plan["run_root"]).resolve()
    if out == root or root in out.parents:
        # 상대 경로로 묻는다 — Windows 절대 경로(역슬래시)는 check-ignore가 못 읽는다.
        # 후행 슬래시를 붙인 형태도 함께 본다: `out/` 같은 **디렉터리 전용 패턴**은
        # 디렉터리가 아직 없으면 슬래시 없는 질의에 매칭되지 않는다(실측).
        rel = out.relative_to(root).as_posix()
        ignored = any(
            subprocess.run(["git", "check-ignore", "-q", p],
                           cwd=root, capture_output=True).returncode == 0
            for p in (rel, rel + "/"))
        if not ignored:
            raise LauncherError(
                f"산출물 경로가 repo 안인데 gitignore되지 않았다: {out} — "
                f"launcher 상태 파일만으로도 트리가 dirty가 된다")
    plan.setdefault("protected_splits", list(DEFAULT_PROTECTED))
    plan.setdefault("canary_args", [])
    plan.setdefault("full_args", [])
    plan["_path"] = str(Path(path).resolve())
    return plan


def run_dir(plan: dict, run_id: str, root) -> Path:
    return Path(root) / plan["run_root"] / run_id


def state_path(plan, run_id, root) -> Path:
    return run_dir(plan, run_id, root) / "_launcher_state.json"


def touches_protected(plan: dict, stage: str) -> list:
    """계획의 인자·경로에 protected split 이름이 섞여 있는가."""
    args = plan["command"] + plan.get(
        "canary_args" if stage == "CANARY" else "full_args", [])
    hay = " ".join(str(a) for a in args) + " " + str(plan.get("run_root", ""))
    return [p for p in plan["protected_splits"] if p in hay]


# ---- 단계 ----------------------------------------------------------------

def precheck(plan: dict, run_id: str, root) -> dict:
    """실행 조건 고정. 여기서 통과하지 못하면 GPU를 쓰지 않는다."""
    root = Path(root)
    rs = repo_state(root)
    if rs["dirty"]:
        raise LauncherError(
            "작업 트리가 dirty — 편집본과 실행본이 갈린다. 커밋하거나 되돌린 뒤 시작하라")
    d = run_dir(plan, run_id, root)
    if (d / "RUN_COMPLETE.json").exists():
        raise LauncherError(f"run_id '{run_id}'는 이미 완료됐다 — 새 run_id를 써라")
    leftovers = [p.name for p in d.glob("*")
                 if p.name != "_launcher_state.json"] if d.is_dir() else []
    if leftovers:
        # 재개하지 않는다 — 부분 산출물과 새 산출물이 섞이면 provenance가 무의미해진다
        raise LauncherError(
            f"run_id '{run_id}'에 부분 산출물이 있다({leftovers[:3]}) — "
            f"재개하지 않는다. 새 run_id를 써라")
    d.mkdir(parents=True, exist_ok=True)
    Path(plan["log_dir"]).mkdir(parents=True, exist_ok=True)
    st = {"run_id": run_id, "stage": "PRECHECK", "plan_name": plan["name"],
          "plan_hash": plan_hash(plan), "execution_commit": rs["head"],
          "protected_touched": touches_protected(plan, "FULL"),
          "started_at": datetime.datetime.now().isoformat(timespec="seconds")}
    state_path(plan, run_id, root).write_text(
        json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    if plan.get("requires_frozen_inventory"):
        (d / INSPECT_MARKER).write_text("\n".join([
            "이 실행의 산출물은 정답 사건 목록이 **동결된 뒤에만** 열람한다.",
            f"대상 영상: {plan['requires_frozen_inventory']}",
            "먼저 보면 사람이 사건 단위를 모델 출력에 맞추게 되어 분모가 오염된다.",
            "정식 열람 경로는 `exp_launcher.py report`뿐이다 — 그것이 동결을 확인한다.",
        ]) + "\n", encoding="utf-8")
    return st


def require_stage_approval(plan, run_id, state, stage, approve_full, approve_test_open):
    """CANARY는 자동, FULL은 명시 승인. test 접촉은 **별도** 승인."""
    if stage == "FULL" and approve_full != run_id:
        raise LauncherError(
            f"FULL 승인이 없다 — `--approve-full {run_id}`가 필요하다"
            f"{'' if approve_full is None else f' (받은 값: {approve_full})'}")
    touched = touches_protected(plan, stage)
    if touched and approve_test_open != run_id:
        raise LauncherError(
            f"protected split 접촉 {touched} — FULL 승인으로는 열리지 않는다. "
            f"`--approve-test-open {run_id}`가 별도로 필요하다")


def launch(plan, run_id, state, stage, root, dirty_recheck_sec: float = 3.0):
    """실험 프로세스를 띄우고 **시작 직후 한 번 더** dirty를 확인한다.

    FULL 시작 시점에 깨끗해도, 리다이렉트나 런타임 파일 생성으로 **바로** 더러워지는
    유형이 있다(2×2 1차 기동의 `nohup` 로그). 6시간 뒤 validator에서 알면 늦다."""
    root = Path(root)
    args = plan["command"] + plan.get(
        "canary_args" if stage == "CANARY" else "full_args", [])
    # `{python}` — 계획 파일이 인터프리터 이름을 알면 안 된다. 노트북은 `python`,
    # 랩실 서버는 `python3`만 있어서 `python`을 박으면 `command not found`로 죽는다.
    args = [str(a).replace("{run_id}", run_id).replace("{python}", sys.executable)
            for a in args]
    log = Path(plan["log_dir"]) / f"{plan['name']}_{run_id}_{stage.lower()}.log"
    with open(log, "w", encoding="utf-8") as f:
        proc = subprocess.Popen(args, cwd=root, stdout=f, stderr=subprocess.STDOUT)
    time.sleep(dirty_recheck_sec)
    if repo_state(root)["dirty"]:
        proc.kill()
        proc.wait(timeout=30)
        raise LauncherError(
            f"시작 직후 작업 트리가 dirty가 됐다 — 프로세스를 죽였다. "
            f"산출물·로그가 repo 안에 쓰이고 있다. 로그: {log}")
    rc = proc.wait()
    return {"returncode": rc, "log": str(log), "argv": args}


def validate(plan, run_id, state, root, hook=None) -> tuple:
    """공통 검사 + 실험별 훅. **공통화가 검증을 약하게 만들면 안 되므로** 실험별
    검사(프롬프트 해시·arm 수·지표 스키마 등)는 훅에서 추가한다."""
    root, d = Path(root), run_dir(plan, run_id, root)
    rs = repo_state(root)
    files = [d / f for f in plan["expected_files"]]
    present = all(f.is_file() for f in files)
    checks = {
        "expected_files_present": present,
        "execution_commit_unchanged": rs["head"] == state["execution_commit"],
        "git_not_dirty": not rs["dirty"],
        "plan_hash_unchanged": plan_hash(plan) == state["plan_hash"],
        "no_stale_marker": not (d / "RUN_COMPLETE.json").exists(),
    }
    key = plan.get("provenance_key")
    if key:
        ok = present
        for f in files:
            if not f.is_file():
                continue
            try:
                ok = ok and bool(json.loads(f.read_text(encoding="utf-8")).get(key))
            except Exception:
                ok = False
        checks["provenance_present"] = ok
    if hook:
        for k, v in (hook(d) or {}).items():
            checks[k] = bool(v)
    return all(checks.values()), checks


def finalize(plan, run_id, state, checks, ok, root) -> Path:
    """**완료 마커를 쓰는 유일한 경로.** PASS가 아니면 쓰지 않는다 —
    "프로세스가 사라졌는가"가 아니라 이 마커가 완료 판정 근거다."""
    if not ok:
        failed = [k for k, v in checks.items() if not v]
        raise LauncherError(f"validator가 PASS가 아니다 {failed} — 완료 마커를 쓰지 않는다")
    m = run_dir(plan, run_id, root) / "RUN_COMPLETE.json"
    m.write_text(json.dumps(
        {"result": "PASS", "run_id": run_id, "plan_name": plan["name"],
         "plan_hash": state["plan_hash"],
         "execution_commit": state["execution_commit"],
         "validator_version": VALIDATOR_VERSION,
         "validated_at": datetime.datetime.now().isoformat(timespec="seconds"),
         "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8")
    return m


def report_inputs(plan, run_id, root) -> list:
    """REPORT가 읽어도 되는 파일. **검증된 산출물만** — 보고서를 만들다가 결과가
    바뀌는 일을 막는다(REPORT는 재생성·재평가를 하지 않는다).

    `requires_frozen_inventory`를 선언한 실험은 **정답 목록이 동결된 뒤에만** 읽을
    수 있다. `load_reference`는 목록→분석 방향만 막는데, 반대 방향(**모델 출력을
    먼저 보고 사람이 사건 단위를 정하는 것**)은 사람의 주의에 의존한다. 그쪽을
    여기서 막는다 — 실행은 병렬로 해도 되지만 사람이 읽는 단계는 동결 뒤에만 연다."""
    d = run_dir(plan, run_id, root)
    if not (d / "RUN_COMPLETE.json").is_file():
        raise LauncherError(f"RUN_COMPLETE.json이 없다 — 검증되지 않은 run은 읽지 않는다")
    need = plan.get("requires_frozen_inventory") or []
    if need:
        inv = Path(root) / plan.get("inventory_dir", "label_kit/event_inventory")
        missing = [v for v in need if not (inv / f"FROZEN_{v}.json").is_file()]
        if missing:
            raise LauncherError(
                f"정답 사건 목록이 아직 **동결**되지 않았다: {missing} — "
                f"결과를 먼저 보면 사람이 사건 단위를 그쪽에 맞추게 된다. "
                f"`event_inventory_kit.py freeze`를 먼저 하라")
    return [d / f for f in plan["expected_files"]]


# ---- CLI -----------------------------------------------------------------

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["precheck", "canary", "full", "validate", "report"])
    ap.add_argument("--plan", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--approve-full", default=None,
                    help="FULL 진입 승인. run_id와 정확히 일치해야 한다")
    ap.add_argument("--approve-test-open", default=None,
                    help="protected split 접촉 승인. FULL 승인과 별개다")
    a = ap.parse_args()
    root = Path(a.root)
    plan = load_plan(a.plan, root=root)

    if a.stage == "precheck":
        st = precheck(plan, a.run_id, root)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0

    sp = state_path(plan, a.run_id, root)
    if not sp.is_file():
        raise LauncherError("precheck를 먼저 실행하라 — 실행 조건이 고정돼 있지 않다")
    st = json.loads(sp.read_text(encoding="utf-8"))

    if a.stage in ("canary", "full"):
        stage = a.stage.upper()
        require_stage_approval(plan, a.run_id, st, stage,
                               a.approve_full, a.approve_test_open)
        r = launch(plan, a.run_id, st, stage, root)
        st["stage"] = stage
        sp.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["returncode"] == 0 else 1

    if a.stage == "validate":
        ok, checks = validate(plan, a.run_id, st, root)
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        m = finalize(plan, a.run_id, st, checks, ok, root)
        print(f"PASS — 완료 마커: {m}")
        return 0

    for f in report_inputs(plan, a.run_id, root):
        print(f)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LauncherError as e:
        print(f"차단: {e}", file=sys.stderr)
        sys.exit(2)
