"""M8 공식 생성 러너 — 실행 규율을 코드로 막는 부분만 검증한다. GPU 없이 돈다.

```
막는 것   pre-run 게이트 미통과 · 기존 report.json 덮어쓰기 · canary가 확정 경로에 쓰기
확인      구조 경로(events+span)를 쓴다 — reduce 경로는 span이 없어 C2/C3가 계산 불가
```
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m8_official as O                                            # noqa: E402


def segs(n, start_idx=0):
    return [{"idx": start_idx + i, "start": (start_idx + i) * 5.0,
             "end": (start_idx + i) * 5.0 + 5, "subtitle": f"발화{i}",
             "caption": f"화면{i}", "rep_frame": "f.jpg"} for i in range(n)]


def fake_llm(events_per_chunk=2):
    """청크마다 유효 사건 몇 개를 내는 가짜 모델. 프롬프트에서 seg 범위를 읽는다."""
    def gen(prompt, **kw):
        import re
        m = re.search(r"seg#(\d+)부터 seg#(\d+)", prompt)
        lo, hi = (int(m.group(1)), int(m.group(2))) if m else (0, 5)
        step = max((hi - lo + 1) // events_per_chunk, 1)
        out = []
        for k in range(events_per_chunk):
            a = lo + k * step
            b = min(a + step - 1, hi)
            if a > b:
                break
            out.append({"event": f"사건{a}", "span": [a, b],
                        "evidence_segments": [a],
                        "description": f"seg {a}에서 사람이 무언가를 한다"})
        return json.dumps(out, ensure_ascii=False)
    return gen


# ---------------------------------------------------------------- 생성 경로

def test_uses_structured_path_so_events_have_spans():
    """**reduce 경로를 쓰면 안 된다.** 그 경로의 문장에는 span이 없어 C2·C3가
    계산 불가고, 그러면 모델과 무관한 이유로 관문이 FAIL한다."""
    rep = O.generate_one(segs(120), fake_llm(), chunk_size=60, overlap=5)
    assert rep["events"] and all(e["span"] for e in rep["events"])
    assert all("span" in s for s in rep["sentences"])
    assert rep["map_raw_outputs"], "C1은 병합 전 원본이 있어야 판정한다"


def test_source_does_not_call_the_reduce_path():
    src = (ROOT / "scripts" / "m8_official.py").read_text(encoding="utf-8")
    assert "generate_report_structured" in src
    assert "generate_report(" not in src.replace("generate_report_structured(", "")


# ---------------------------------------------------------------- pre-run 게이트

def gate_kwargs(tmp_path, **over):
    d = {"videos": ["v1"], "work_root": tmp_path / "work",
         "verify_diffs": [], "git_dirty": False,
         "gt_sha256": "a" * 64, "expect_gt_sha256": "a" * 64,
         "freeze_id": "m8_evaluator_2026-08-27",
         "expect_freeze_id": "m8_evaluator_2026-08-27"}
    d.update(over)
    return d


def test_gate_passes_when_everything_matches(tmp_path):
    rec = O.prerun_gate(**gate_kwargs(tmp_path))
    assert rec["passed"] is True and rec["existing_reports"] == []


def test_gate_refuses_on_evaluator_drift(tmp_path):
    with pytest.raises(O.OfficialRunError, match="evaluator"):
        O.prerun_gate(**gate_kwargs(tmp_path, verify_diffs=["m8_metrics 바뀜"]))


def test_gate_records_dirty_but_does_not_refuse(tmp_path):
    """서버에는 push 없이 scp로 코드가 간다 — 트리는 항상 dirty다.
    그것을 조건으로 두면 정상 실행이 막힌다. 기록만 한다."""
    rec = O.prerun_gate(**gate_kwargs(tmp_path, git_dirty=True))
    assert rec["passed"] is True and rec["git_dirty"] is True


def test_gate_refuses_on_generator_source_drift(tmp_path):
    """실제로 필요한 보장은 **생성기 소스 동일성**이다 — 해시로 확인한다."""
    with pytest.raises(O.OfficialRunError, match="생성기 소스"):
        O.prerun_gate(**gate_kwargs(
            tmp_path, source_sha256={"src/m8_report.py": "a" * 64},
            expect_source_sha256={"src/m8_report.py": "b" * 64}))


def test_gate_passes_when_generator_source_matches(tmp_path):
    same = {"src/m8_report.py": "a" * 64, "src/llm.py": "b" * 64}
    rec = O.prerun_gate(**gate_kwargs(tmp_path, source_sha256=same,
                                      expect_source_sha256=same))
    assert rec["passed"] is True and rec["source_sha256"] == same


def test_source_sha_normalizes_line_endings(tmp_path):
    CR, LF = chr(13), chr(10)
    lf = f"x = 1{LF}y = 2{LF}"
    crlf = lf.replace(LF, CR + LF)
    assert crlf != lf                       # fixture가 실제로 다른 바이트여야 한다
    (tmp_path / "a.py").write_bytes(crlf.encode())
    (tmp_path / "b.py").write_bytes(lf.encode())
    h = O.source_sha256(root=tmp_path, files=("a.py", "b.py"))
    assert h["a.py"] == h["b.py"]


def test_gate_refuses_on_gt_hash_mismatch(tmp_path):
    with pytest.raises(O.OfficialRunError, match="GT"):
        O.prerun_gate(**gate_kwargs(tmp_path, gt_sha256="b" * 64))


def test_gate_refuses_on_freeze_id_mismatch(tmp_path):
    with pytest.raises(O.OfficialRunError, match="freeze_id"):
        O.prerun_gate(**gate_kwargs(tmp_path, freeze_id="다른것"))


def test_gate_refuses_when_official_report_already_exists(tmp_path):
    w = tmp_path / "work" / "v1"
    w.mkdir(parents=True)
    (w / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(O.OfficialRunError, match="report.json"):
        O.prerun_gate(**gate_kwargs(tmp_path))


def test_gate_allows_existing_reports_when_resuming(tmp_path):
    """실패 정책 B — 일부만 생성된 뒤 같은 config로 미완료분만 재시도한다."""
    w = tmp_path / "work" / "v1"
    w.mkdir(parents=True)
    (w / "report.json").write_text("{}", encoding="utf-8")
    rec = O.prerun_gate(**gate_kwargs(tmp_path, allow_existing=True))
    assert rec["passed"] is True and rec["existing_reports"] == ["v1"]


# ---------------------------------------------------------------- 쓰기 경계

def test_canary_never_writes_the_canonical_report(tmp_path):
    wdir = tmp_path / "work" / "v1"
    wdir.mkdir(parents=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    out = O.write_report("v1", wdir, run_dir, {"report_model": "m", "map_chunk_size": 60},
                         O.generate_one(segs(60), fake_llm(), 60, 5), 60,
                         provenance={}, canary=True)
    assert not (wdir / "report.json").exists()
    assert Path(out["path"]).name == "report_canary_v1.json"


def test_full_writes_the_canonical_report(tmp_path):
    wdir = tmp_path / "work" / "v1"
    wdir.mkdir(parents=True)
    out = O.write_report("v1", wdir, tmp_path / "run",
                         {"report_model": "m", "map_chunk_size": 60},
                         O.generate_one(segs(60), fake_llm(), 60, 5), 60,
                         provenance={}, canary=False)
    assert (wdir / "report.json").is_file()
    assert Path(out["path"]) == wdir / "report.json"
    d = json.loads((wdir / "report.json").read_text(encoding="utf-8"))
    assert d["video_id"] == "v1" and d["schema_version"] and d["events"]


def test_full_refuses_to_overwrite(tmp_path):
    """정상 report를 덮지 않는다 — 실패 정책 B."""
    wdir = tmp_path / "work" / "v1"
    wdir.mkdir(parents=True)
    (wdir / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(O.OfficialRunError, match="덮"):
        O.write_report("v1", wdir, tmp_path / "run",
                       {"report_model": "m", "map_chunk_size": 60},
                       O.generate_one(segs(60), fake_llm(), 60, 5), 60,
                       provenance={}, canary=False)


def test_structural_assert_is_recorded_not_swallowed(tmp_path):
    """`save_report`는 파일을 먼저 쓰고 검증한다 — 실패해도 리포트는 남고,
    그 사실이 manifest에 남아야 C1이 판정할 수 있다."""
    wdir = tmp_path / "work" / "v1"
    wdir.mkdir(parents=True)
    rep = O.generate_one(segs(60), fake_llm(), 60, 5)
    rep["sentences"] = [{"sent_id": 0, "text": "같은 문장", "cites": [0],
                         "event": "a", "span": [0, 1]} for _ in range(5)]
    out = O.write_report("v1", wdir, tmp_path / "run",
                         {"report_model": "m", "map_chunk_size": 60}, rep, 60,
                         provenance={}, canary=False)
    assert out["structural_assert"]
    assert (wdir / "report.json").is_file()


# ---------------------------------------------------------------- manifest

def test_manifest_has_no_report_content(tmp_path):
    """실행 중 내용을 보지 않는다 — manifest에 서술 문자열이 들어가면 그게 열람이다."""
    wdir = tmp_path / "work" / "v1"
    wdir.mkdir(parents=True)
    rep = O.generate_one(segs(60), fake_llm(), 60, 5)
    row = O.video_manifest_row("v1", rep, 60, {"path": "x", "structural_assert": None})
    blob = json.dumps(row, ensure_ascii=False)
    assert "사람이 무언가를" not in blob and "사건0" not in blob
    assert row["n_events"] and row["n_sentences"]
    assert "uncited_evaluable_sentences" in row


def test_manifest_row_reports_c1_status_without_evidence(tmp_path):
    rep = O.generate_one(segs(60), fake_llm(), 60, 5)
    row = O.video_manifest_row("v1", rep, 60, {"path": "x", "structural_assert": None})
    assert row["c1_status"] in ("PRESENT", "ABSENT", "UNCLEAR")
    assert set(row["c1_kind_status"]) == {"language_drift", "early_stop",
                                          "repetition_loop"}
    assert "evidence" not in json.dumps(row, ensure_ascii=False)
