"""handoff 생성기 — **수집기다. 해석기가 아니다.**

새 세션이 낡은 스냅샷을 읽고 이미 닫힌 결론으로 되돌아가는 문제를 줄이는 것이 목적이다.
그래서 여기서 고정하는 것은 서식이 아니라 두 가지다.

```
1  최신 작업현황을 **날짜 하드코딩 없이** 결정적으로 찾는다
2  수치를 보고 PASS/FAIL·승자를 새로 만들지 않는다 — 원문을 출처와 함께 옮긴다
```
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_handoff as H                                         # noqa: E402

SRC = (ROOT / "scripts" / "make_handoff.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)

DOC = """# 작업현황 2026-09-09

## 5. 현재 실행 상태

```
run_id      demo_run
```

## 6. GO / HOLD

**GO**

```
I1   라벨
P2   질의
```

**HOLD**

```
test 접촉
4B 채택
```

## 9. 다음 승인 지점

```
1  FULL 완주
```
"""


def _docs(tmp_path, names=("작업현황_2026-08-20.md", "작업현황_2026-09-09.md")):
    d = tmp_path / "docs"
    d.mkdir()
    for n in names:
        (d / n).write_text(DOC if "09-09" in n else "# 낡음\n", encoding="utf-8")
    return d


# ------------------------------------------------------- 해석하지 않는다

@pytest.mark.parametrize("token", ["mrr", "MRR", "precision", "recall",
                                   "alpha_star", "PASS", "FAIL"])
def test_it_does_not_compute_verdicts_or_metrics(token):
    """지표를 읽어 판정을 만들면 낡은 문서보다 위험하다 — 계산 코드 자체를 금지한다."""
    assert token not in CODE


def test_no_hardcoded_status_date():
    import re
    assert not re.search(r"2026-\d\d-\d\d", CODE)


# ------------------------------------------------------- 최신 문서 선택

def test_latest_status_doc_is_picked_by_date_in_filename(tmp_path):
    d = _docs(tmp_path)
    p = H.latest_status_doc(d)
    assert p.name == "작업현황_2026-09-09.md"


def test_unparseable_names_are_ignored(tmp_path):
    d = _docs(tmp_path, ("작업현황_초안.md", "작업현황_2026-09-09.md"))
    assert H.latest_status_doc(d).name == "작업현황_2026-09-09.md"


def test_missing_status_doc_fails_closed(tmp_path):
    (tmp_path / "docs").mkdir()
    with pytest.raises(H.HandoffError, match="작업현황"):
        H.latest_status_doc(tmp_path / "docs")


# ------------------------------------------------------- 원문 그대로 옮긴다

def test_go_and_hold_are_copied_verbatim(tmp_path):
    doc = _docs(tmp_path) / "작업현황_2026-09-09.md"
    got = H.sections(doc)
    assert "I1   라벨" in got["go"] and "P2   질의" in got["go"]
    assert "test 접촉" in got["hold"] and "4B 채택" in got["hold"]
    assert "다음 승인" in got["next_approval_heading"]
    assert "FULL 완주" in got["next_approval"]


def test_absent_section_is_null_not_invented(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    p = d / "작업현황_2026-09-09.md"
    p.write_text("# 작업현황 2026-09-09\n\n본문만 있다\n", encoding="utf-8")
    got = H.sections(p)
    assert got["go"] is None and got["hold"] is None
    assert got["next_approval"] is None


def test_every_collected_fact_carries_a_source(tmp_path):
    doc = _docs(tmp_path) / "작업현황_2026-09-09.md"
    facts = H.collect(status_doc=doc, run_root=tmp_path / "none",
                      test_result=None)
    for k, v in facts["facts"].items():
        assert "source" in v, k


def test_run_state_absent_is_reported_as_unobserved(tmp_path):
    doc = _docs(tmp_path) / "작업현황_2026-09-09.md"
    facts = H.collect(status_doc=doc, run_root=tmp_path / "none",
                      test_result=None)
    run = facts["facts"]["run_state"]
    assert run["value"] is None and "관측" in run["note"]


def test_run_state_reads_markers_without_declaring_completion(tmp_path):
    """마커 존재는 관측이고 완료 판정이 아니다 — RUN_COMPLETE만 완료 근거다."""
    rr = tmp_path / "runs" / "r1"
    rr.mkdir(parents=True)
    (rr / "STAGE_m2_frames_DONE").write_text("{}", encoding="utf-8")
    doc = _docs(tmp_path) / "작업현황_2026-09-09.md"
    facts = H.collect(status_doc=doc, run_root=tmp_path / "runs",
                      test_result=None)
    run = facts["facts"]["run_state"]["value"]
    assert run["run_id"] == "r1"
    assert run["markers_present"] == ["STAGE_m2_frames_DONE"]
    assert run["run_complete"] is False
    assert "완료 근거" in facts["facts"]["run_state"]["note"]


def test_render_includes_sources_for_each_block(tmp_path):
    doc = _docs(tmp_path) / "작업현황_2026-09-09.md"
    md = H.render(H.collect(status_doc=doc, run_root=tmp_path / "none",
                            test_result=None))
    assert "source:" in md and "작업현황_2026-09-09.md" in md
    assert "4B 채택" in md
