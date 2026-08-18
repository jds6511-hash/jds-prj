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
| 실험 인터프리터는 `${EXP_PYTHON}` | precheck가 존재·실행·의존성까지 확인, 없으면 거부 |
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
# 2 (2026-08-18): plan_hash가 계획 **원문** 기준으로 바뀌었고(확장값 제외),
#                 마커에 실험 인터프리터 fingerprint가 추가됐다
VALIDATOR_VERSION = 2
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
    """계획 **파일 원문**의 해시. 마커에 남겨 어떤 계획이 이 결과를 만들었는지 고정한다.

    확장된 값(`${EXP_LOG_DIR}`·`${EXP_PYTHON}`의 실제 경로)은 넣지 않는다. 넣으면
    같은 계획 파일이 기계마다 다른 해시를 갖게 되고, 공개 이력과 대조할 수 없다."""
    return hashlib.sha256(plan["_raw"].encode("utf-8")).hexdigest()


def load_plan(path, root) -> dict:
    root = Path(root).resolve()
    raw = Path(path).read_text(encoding="utf-8")
    plan = json.loads(raw)
    plan["_raw"] = raw
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


# CANARY와 FULL은 **같은 run_id를 공유**한다. 파생 파일 이름이 stage에 귀속되지
# 않으면, FULL이 중간에 죽었을 때 CANARY 산출물(1편·2청크)이 full 결과 행세를 한다.
STAGES = ("CANARY", "FULL")


def expected_files(plan: dict, stage: str) -> list:
    """stage별 기대 산출물. 선언이 없으면 공통 `expected_files`로 떨어진다."""
    key = {"CANARY": "canary_expected_files", "FULL": "full_expected_files"}[stage]
    return list(plan.get(key) or plan["expected_files"])


def state_path(plan, run_id, root) -> Path:
    return run_dir(plan, run_id, root) / "_launcher_state.json"


def touches_protected(plan: dict, stage: str) -> list:
    """계획의 인자·경로에 protected split 이름이 섞여 있는가."""
    args = plan["command"] + plan.get(
        "canary_args" if stage == "CANARY" else "full_args", [])
    hay = " ".join(str(a) for a in args) + " " + str(plan.get("run_root", ""))
    return [p for p in plan["protected_splits"] if p in hay]


# ---- 실험 인터프리터 -------------------------------------------------------
#
# **launcher를 띄운 파이썬과 실험을 돌리는 파이썬은 다른 것이다.** 앞의 것으로
# 뒤의 것을 대신하면(= `sys.executable` 치환) launcher를 어떻게 호출했는지가
# 실험 환경을 바꾼다 — 2026-08-18에 `/usr/bin/python3`로 띄워 `numpy` 없는
# 인터프리터에서 M8이 죽었다. 실험 쪽은 `${EXP_PYTHON}`만 본다.
PY_TOKEN = "{experiment_python}"
DEFAULT_REQUIRED_MODULES = ("numpy", "torch", "transformers")

_PROBE = (
    "import importlib.util as u, json, sys\n"
    "req = json.loads(sys.argv[1])\n"
    "miss = [m for m in req if u.find_spec(m) is None]\n"
    "d = {'python_executable': sys.executable,\n"
    "     'python_version': sys.version.split()[0],\n"
    "     'missing_modules': miss,\n"
    "     'torch_version': None, 'cuda_version': None, 'gpu_name': None,\n"
    "     'transformers_version': None, 'numpy_version': None}\n"
    "if u.find_spec('numpy'):\n"
    "    import numpy; d['numpy_version'] = numpy.__version__\n"
    "if u.find_spec('torch'):\n"
    "    import torch; d['torch_version'] = torch.__version__\n"
    "    d['cuda_version'] = torch.version.cuda\n"
    "    d['gpu_name'] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None\n"
    "if u.find_spec('transformers'):\n"
    "    import transformers; d['transformers_version'] = transformers.__version__\n"
    "print(json.dumps(d))\n"
)


def needs_experiment_python(plan: dict) -> bool:
    args = plan["command"] + plan.get("canary_args", []) + plan.get("full_args", [])
    return any(PY_TOKEN in str(a) for a in args)


def resolve_experiment_python(plan: dict) -> tuple:
    """`${EXP_PYTHON}`을 해석하고 **실제로 쓸 수 있는지 실행해서** 확인한다.

    경로가 있다는 것만으로는 부족하다 — 의존성이 없는 인터프리터는 모델 로드
    직전까지 멀쩡해 보이다가 죽는다. GPU를 쓰기 전에 여기서 건다."""
    raw = os.environ.get("EXP_PYTHON")
    if not raw:
        raise LauncherError(
            "EXP_PYTHON이 설정되지 않았다 — 실험을 돌릴 인터프리터를 실행 환경에서 "
            "주입하라. 계획 파일에는 서버 경로를 박지 않는다")
    p = Path(raw)
    if not p.is_absolute():
        raise LauncherError(f"EXP_PYTHON이 절대경로가 아니다: {raw} — cwd에 따라 달라진다")
    if not (p.is_file() and os.access(p, os.X_OK)):
        raise LauncherError(f"EXP_PYTHON이 실행 가능한 파일이 아니다: {raw}")
    req = list(plan.get("requires_modules", DEFAULT_REQUIRED_MODULES))
    r = subprocess.run([str(p), "-c", _PROBE, json.dumps(req)],
                       capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise LauncherError(
            f"EXP_PYTHON으로 프로브를 실행하지 못했다: {raw}\n{r.stderr.strip()[-400:]}")
    fp = json.loads(r.stdout.strip().splitlines()[-1])
    if fp["missing_modules"]:
        raise LauncherError(
            f"EXP_PYTHON에 필수 모듈이 없다: {fp['missing_modules']} ({raw}) — "
            f"실험 환경이 아닌 인터프리터다")
    if os.path.realpath(fp["python_executable"]) != os.path.realpath(str(p)):
        raise LauncherError(
            f"EXP_PYTHON이 다른 인터프리터로 넘어갔다: 요청 {p} → 실제 "
            f"{fp['python_executable']}")
    return str(p), fp


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
    py, fp = resolve_experiment_python(plan) if needs_experiment_python(plan) \
        else (None, None)
    d.mkdir(parents=True, exist_ok=True)
    Path(plan["log_dir"]).mkdir(parents=True, exist_ok=True)
    st = {"run_id": run_id, "stage": "PRECHECK", "plan_name": plan["name"],
          "plan_hash": plan_hash(plan), "execution_commit": rs["head"],
          "protected_touched": touches_protected(plan, "FULL"),
          # 해석된 경로는 **state에만** 남긴다(gitignore된 run_root). 계획 파일과
          # plan_hash에는 토큰만 있으므로 서버 경로가 git 이력에 들어가지 않는다.
          "resolved_python": py, "python_fingerprint": fp,
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
    # 배관을 확인하지 않은 채 GPU를 몇 시간 태우지 않는다. 승인 검사 **뒤**에 둔다 —
    # 오염 위험(protected split)이 배관 순서보다 먼저 보고돼야 한다.
    if stage == "FULL" and not state.get("canary_validated"):
        raise LauncherError(
            "CANARY validator를 통과하지 않았다 — `validate`를 먼저 돌려라")


def launch(plan, run_id, state, stage, root, dirty_recheck_sec: float = 3.0):
    """실험 프로세스를 띄우고 **시작 직후 한 번 더** dirty를 확인한다.

    FULL 시작 시점에 깨끗해도, 리다이렉트나 런타임 파일 생성으로 **바로** 더러워지는
    유형이 있다(2×2 1차 기동의 `nohup` 로그). 6시간 뒤 validator에서 알면 늦다."""
    root = Path(root)
    if stage not in STAGES:
        raise LauncherError(f"알 수 없는 stage: {stage} — {STAGES} 중 하나여야 한다")
    d = run_dir(plan, run_id, root)
    # **stage별** 부분 산출물 검사. 정상적인 CANARY 산출물이 FULL을 막으면 안 되고,
    # 반대로 이전 FULL 산출물 위에 덮어쓰면 provenance가 섞인다.
    dup = [f for f in expected_files(plan, stage) if (d / f).exists()]
    if dup:
        raise LauncherError(
            f"{stage}의 부분 산출물이 이미 있다({dup[:3]}) — 재개하지 않는다. "
            f"새 run_id를 써라")
    args = plan["command"] + plan.get(
        "canary_args" if stage == "CANARY" else "full_args", [])
    # 실험 인터프리터는 precheck가 고정한 값만 쓴다 — launcher 자신의
    # `sys.executable`은 여기 들어오지 않는다.
    py = state.get("resolved_python")
    if needs_experiment_python(plan) and not py:
        raise LauncherError("precheck가 실험 인터프리터를 고정하지 않았다 — 다시 실행하라")
    args = [str(a).replace("{run_id}", run_id)
                  .replace("{run_dir}", str(d))
                  .replace("{stage}", stage.lower())
                  .replace(PY_TOKEN, py or "")
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


def validate(plan, run_id, state, root, hook=None, stage="FULL") -> tuple:
    """공통 검사 + 실험별 훅. **공통화가 검증을 약하게 만들면 안 되므로** 실험별
    검사(프롬프트 해시·arm 수·지표 스키마 등)는 훅에서 추가한다.

    stage를 받는 이유는 **CANARY 산출물이 full 산출물로 통과하면 안 되기** 때문이다."""
    root, d = Path(root), run_dir(plan, run_id, root)
    rs = repo_state(root)
    files = [d / f for f in expected_files(plan, stage)]
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


def finalize(plan, run_id, state, checks, ok, root, stage="FULL") -> Path:
    """**완료 마커를 쓰는 유일한 경로.** PASS가 아니면 쓰지 않는다 —
    "프로세스가 사라졌는가"가 아니라 이 마커가 완료 판정 근거다.

    CANARY는 공식 완료로 승격하지 않는다 — 1편·2청크짜리 배관 점검일 뿐이다."""
    if stage != "FULL":
        raise LauncherError(
            f"{stage}는 완료 마커를 만들지 않는다 — CANARY는 배관 점검이다")
    if not ok:
        failed = [k for k, v in checks.items() if not v]
        raise LauncherError(f"validator가 PASS가 아니다 {failed} — 완료 마커를 쓰지 않는다")
    m = run_dir(plan, run_id, root) / "RUN_COMPLETE.json"
    m.write_text(json.dumps(
        {"result": "PASS", "run_id": run_id, "plan_name": plan["name"],
         "plan_hash": state["plan_hash"],
         "execution_commit": state["execution_commit"],
         "validator_version": VALIDATOR_VERSION,
         # "같은 commit인데 왜 실행이 달랐나"를 인터프리터부터 확인할 수 있게 한다
         "resolved_python": state.get("resolved_python"),
         "python_fingerprint": state.get("python_fingerprint"),
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
    # CANARY 산출물은 정식 열람 대상이 아니다 — FULL 것만 낸다
    return [d / f for f in expected_files(plan, "FULL")]


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
        # 무엇을 검증하는지는 **직전에 무엇을 돌렸는지**로 정한다
        vstage = st.get("stage", "FULL")
        ok, checks = validate(plan, a.run_id, st, root, stage=vstage)
        print(json.dumps({"validated_stage": vstage, **checks},
                         ensure_ascii=False, indent=2))
        if vstage == "CANARY":
            if not ok:
                raise LauncherError(
                    f"CANARY validator FAIL {[k for k, v in checks.items() if not v]}")
            st["canary_validated"] = True
            sp.write_text(json.dumps(st, ensure_ascii=False, indent=2),
                          encoding="utf-8")
            print("CANARY PASS — 배관만 확인했다. 완료 마커는 만들지 않는다")
            return 0
        m = finalize(plan, a.run_id, st, checks, ok, root, stage=vstage)
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
