"""세션 인수 문서를 만든다 — **사실을 모으는 도구이고 해석하지 않는다.**

문제는 새 세션이 낡은 스냅샷을 읽고 이미 닫힌 결론으로 되돌아가는 것이다. 그래서
이 스크립트는 **최신 작업현황·frozen 산출물·git 상태**를 모아 출처와 함께 한 파일에
적는다.

**하지 않는 것**을 먼저 적는다.

```
지표를 읽어 PASS/FAIL을 만들지 않는다
문서 여러 개를 비교해 모델 승자를 추론하지 않는다
날짜를 코드에 박지 않는다 — 최신 작업현황을 파일명 날짜로 결정적으로 찾는다
없는 항목을 채우지 않는다 — null로 두고 관측하지 못했다고 적는다
```

마커는 **관측**으로만 옮긴다. 마커가 있다고 단계가 끝난 것으로 쓰지 않는다(같은
run_id의 CANARY 마커를 FULL 완료로 오독한 전례가 있다). 완료 근거는 `RUN_COMPLETE.json`
하나다.

재현:
  python scripts/make_handoff.py                       # docs/HANDOFF_CURRENT.md
  python scripts/make_handoff.py --with-tests          # 테스트도 돌려 결과를 기록
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PREREG = DOCS / "preregistration"
RUN_ROOT = DOCS / "probes" / "_scratch" / "launcher_runs"
OUT = DOCS / "HANDOFF_CURRENT.md"
STATUS_GLOB = "작업현황_*.md"
STATUS_DATE = re.compile(r"(\d{4})-(\d\d)-(\d\d)")


class HandoffError(RuntimeError):
    pass


def latest_status_doc(docs=DOCS) -> Path:
    """파일명 날짜가 가장 큰 작업현황. **날짜를 코드에 박지 않는다.**"""
    cands = []
    for p in sorted(Path(docs).glob(STATUS_GLOB)):
        m = STATUS_DATE.search(p.name)
        if m:
            cands.append((m.group(0), p))
    if not cands:
        raise HandoffError(f"작업현황 파일을 찾지 못했다: {docs}/{STATUS_GLOB}")
    return max(cands, key=lambda t: (t[0], t[1].name))[1]


def _fenced_after(text: str, anchor: str) -> str:
    """`anchor` 뒤 첫 코드블록을 원문 그대로 돌려준다."""
    i = text.find(anchor)
    if i < 0:
        return None
    m = re.search(r"```[^\n]*\n(.*?)```", text[i:], re.S)
    return m.group(1).rstrip("\n") if m else None


def sections(status_doc: Path) -> dict:
    """작업현황에서 GO·HOLD·다음 승인 지점을 **원문 그대로** 뽑는다."""
    text = Path(status_doc).read_text(encoding="utf-8")
    head = re.search(r"^##[^\n]*다음 승인[^\n]*$", text, re.M)
    return {"go": _fenced_after(text, "**GO**"),
            "hold": _fenced_after(text, "**HOLD**"),
            "next_approval_heading": head.group(0).strip("# ") if head else None,
            "next_approval": (_fenced_after(text, head.group(0)) if head
                              else None)}


def _git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def _latest_run(run_root) -> dict:
    root = Path(run_root)
    if not root.is_dir():
        return None
    dirs = [d for d in sorted(root.iterdir()) if d.is_dir()]
    if not dirs:
        return None
    d = max(dirs, key=lambda p: (p.stat().st_mtime, p.name))
    state = d / "_launcher_state.json"
    return {"run_id": d.name,
            "launcher_state": (json.loads(state.read_text(encoding="utf-8"))
                               if state.is_file() else None),
            "markers_present": sorted(p.name for p in d.glob("STAGE_*")),
            "reports_present": sorted(p.name for p in d.glob("*.json")),
            "run_complete": (d / "RUN_COMPLETE.json").is_file()}


def _fact(value, source, note=None) -> dict:
    f = {"value": value, "source": source}
    if note:
        f["note"] = note
    return f


def collect(status_doc=None, run_root=RUN_ROOT, test_result=None) -> dict:
    doc = Path(status_doc) if status_doc else latest_status_doc()
    rel = str(doc.relative_to(ROOT)) if doc.is_relative_to(ROOT) else str(doc)
    sec = sections(doc)
    run = _latest_run(run_root)
    cfg = ROOT / "config.yaml"
    facts = {
        "git_head": _fact(_git("rev-parse", "HEAD"), "git rev-parse HEAD"),
        "git_dirty": _fact(bool(_git("status", "--porcelain")),
                           "git status --porcelain"),
        "recent_commits": _fact(_git("log", "-5", "--oneline").splitlines(),
                                "git log -5 --oneline"),
        "status_doc": _fact(rel, "scripts/make_handoff.py latest_status_doc()",
                            "파일명 날짜가 가장 큰 작업현황이다"),
        "go": _fact(sec["go"], f"{rel} **GO**"),
        "hold": _fact(sec["hold"], f"{rel} **HOLD**"),
        "next_approval": _fact(sec["next_approval"],
                               f"{rel} {sec['next_approval_heading']}"),
        "deployment_config": _fact(
            (cfg.read_text(encoding="utf-8").strip().splitlines()
             if cfg.is_file() else None), "config.yaml",
            "파일 내용을 옮긴 것이다. CLI 주입값은 여기에 없다"),
        "run_state": _fact(run, str(Path(run_root)),
                           ("마커는 관측일 뿐이다 — 완료 근거는 RUN_COMPLETE.json "
                            "하나이고, 같은 run_id의 CANARY 마커를 FULL 완료로 "
                            "읽지 마라")),
        "test_result": _fact(test_result, "python -m pytest tests/ -q",
                             ("이 실행에서 돌리지 않았으면 null이다 — 낡은 값을 "
                              "옮기지 않는다")),
        "frozen_documents": _fact(
            sorted(p.name for p in PREREG.glob("*.md")) if PREREG.is_dir()
            else None, "docs/preregistration/",
            "내용을 고치지 않는 문서다. 이탈은 보충으로 적는다"),
        "document_map": _fact("docs/README.md", "docs/README.md"),
    }
    return {"generator": "scripts/make_handoff.py",
            "role": "수집기다 — 해석하지 않는다",
            "facts": facts}


def render(collected: dict) -> str:
    f = collected["facts"]
    out = ["# 세션 인수 (자동 생성)", "",
           "> **직접 편집하지 마라.** `scripts/make_handoff.py`로 다시 생성한다. "
           "이 도구는 수집기이고 해석기가 아니다 — 수치를 보고 판정을 만들지 않고, "
           "각 항목에 출처를 붙인다.",
           "> 판정·근거는 출처 문서에서 읽어라.", ""]
    if f["git_dirty"]["value"]:
        out += ["> **작업 트리가 dirty다.** 아래 사실은 커밋되지 않은 변경을 포함한 "
                "상태에서 수집됐다 — 재현하려면 `git status`를 먼저 봐라.", ""]

    def block(title, key, fenced=True):
        fact = f[key]
        out.append(f"## {title}")
        out.append("")
        v = fact["value"]
        if v is None:
            out.append("관측하지 못했다 (null)")
        elif isinstance(v, (list, tuple)):
            out.append("```")
            out.extend(str(x) for x in v)
            out.append("```")
        elif isinstance(v, dict):
            out.append("```json")
            out.append(json.dumps(v, ensure_ascii=False, indent=2))
            out.append("```")
        elif fenced and "\n" in str(v):
            out.append("```")
            out.append(str(v))
            out.append("```")
        else:
            out.append(f"`{v}`")
        out.append("")
        out.append(f"source: {fact['source']}")
        if fact.get("note"):
            out.append(f"note: {fact['note']}")
        out.append("")

    block("git HEAD", "git_head")
    block("작업 트리 dirty", "git_dirty")
    block("최근 커밋", "recent_commits")
    block("기준 작업현황", "status_doc")
    block("GO", "go")
    block("HOLD", "hold")
    block("다음 승인 지점", "next_approval")
    block("현재 실행 상태", "run_state")
    block("테스트 결과", "test_result")
    block("배포 config", "deployment_config")
    block("고치지 않는 문서", "frozen_documents")
    block("문서 지도", "document_map")
    return "\n".join(out) + "\n"


def _run_tests() -> dict:
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                       cwd=ROOT, capture_output=True, encoding="utf-8",
                       errors="replace")
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-1:]
    return {"exit_code": r.returncode, "summary": tail[0] if tail else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--run-root", default=str(RUN_ROOT))
    ap.add_argument("--status-doc")
    ap.add_argument("--with-tests", action="store_true")
    a = ap.parse_args()
    collected = collect(status_doc=a.status_doc, run_root=a.run_root,
                        test_result=_run_tests() if a.with_tests else None)
    Path(a.out).write_text(render(collected), encoding="utf-8")
    print(f"{a.out} : {len(collected['facts'])}개 항목 "
          f"/ 기준 {collected['facts']['status_doc']['value']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
