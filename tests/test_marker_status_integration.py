"""marker/status 통합 — 이름공간 마커를 **쓰는 쪽**까지 붙였는지 검사한다.

`run_status`는 읽기만 하는 판독기였고, 배치는 여전히 이름공간 없는 `STAGE_<x>_DONE`을
썼다. 그 상태로는 2026-08-22 사고(CANARY 마커를 FULL 완료로 읽음)가 다시 난다.
여기서 검사하는 것은 세 가지다.

```
쓰는 쪽    배치가 mode 이름공간 마커를 쓴다 (run_status.write_marker 경유)
읽는 쪽    CANARY 마커가 FULL 완료로 세지지 않는다
완료 선언   마커 존재·해시 일치 모두 완료 근거가 아니다 — RUN_COMPLETE.json뿐이다
```
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import make_handoff as MH      # noqa: E402
import p2_index_batch as B     # noqa: E402
import run_status as S         # noqa: E402

RID, COMMIT = "rid1", "abc1234"


@pytest.fixture
def rd(tmp_path):
    d = tmp_path / RID
    d.mkdir()
    return d


# ---- 쓰는 쪽 --------------------------------------------------------------

def test_batch_writes_namespaced_marker(rd):
    p = B.stage_marker(rd, "m2_frames", mode="FULL", run_id=RID,
                       commit=COMMIT, elapsed_sec=1.5,
                       created_at="2026-08-24T00:00:00")
    assert p.name == S.marker_name("FULL", "m2_frames")
    body = json.loads(p.read_text(encoding="utf-8"))
    for k in ("mode", "run_id", "commit", "stage", "created_at"):
        assert k in body, k
    assert body["mode"] == "FULL" and body["run_id"] == RID
    assert body["elapsed_sec"] == 1.5


def test_canary_and_full_marker_names_differ(rd):
    a = B.stage_marker(rd, "m2_frames", mode="CANARY", run_id=RID,
                       commit=COMMIT, elapsed_sec=1.0,
                       created_at="2026-08-24T00:00:00")
    b = B.stage_marker(rd, "m2_frames", mode="FULL", run_id=RID,
                       commit=COMMIT, elapsed_sec=1.0,
                       created_at="2026-08-24T00:00:00")
    assert a.name != b.name


def test_unknown_stage_refused(rd):
    with pytest.raises(S.StatusError):
        B.stage_marker(rd, "not_a_stage", mode="FULL", run_id=RID,
                       commit=COMMIT, elapsed_sec=1.0,
                       created_at="2026-08-24T00:00:00")


def test_batch_no_longer_writes_legacy_marker_name():
    """이름공간 없는 마커를 새로 만들지 않는다 — 사고의 직접 원인이었다."""
    src = (ROOT / "scripts" / "p2_index_batch.py").read_text(encoding="utf-8")
    assert 'f"STAGE_' not in src
    assert "stage_marker(" in src


def test_batch_marker_goes_through_run_status():
    """마커 스키마를 배치가 따로 손으로 만들지 않는다."""
    src = (ROOT / "scripts" / "p2_index_batch.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert "run_status" in mods


def test_batch_stage_names_match_status_stages():
    """배치 단계 이름과 판독기 STAGES가 어긋나면 마커를 못 쓴다."""
    assert [st["name"] for st in B.STAGES] == list(S.STAGES)


# ---- 읽는 쪽 --------------------------------------------------------------

def test_canary_marker_not_counted_as_full(rd):
    B.stage_marker(rd, "m1_segments", mode="CANARY", run_id=RID,
                   commit=COMMIT, elapsed_sec=1.0,
                   created_at="2026-08-24T00:00:00")
    st = S.status(rd, run_id=RID, mode="FULL", commit=COMMIT)
    assert st["stages"]["m1_segments"] == "pending"
    assert any("mode CANARY" in m for m in st["ignored_markers"])


def test_other_run_id_ignored(rd):
    B.stage_marker(rd, "m1_segments", mode="FULL", run_id="other",
                   commit=COMMIT, elapsed_sec=1.0,
                   created_at="2026-08-24T00:00:00")
    st = S.status(rd, run_id=RID, mode="FULL", commit=COMMIT)
    assert st["stages"]["m1_segments"] == "pending"


def test_other_commit_ignored(rd):
    B.stage_marker(rd, "m1_segments", mode="FULL", run_id=RID,
                   commit="deadbee", elapsed_sec=1.0,
                   created_at="2026-08-24T00:00:00")
    st = S.status(rd, run_id=RID, mode="FULL", commit=COMMIT)
    assert st["stages"]["m1_segments"] == "pending"


def test_marker_presence_is_not_completion(rd):
    for st_name in S.STAGES:
        B.stage_marker(rd, st_name, mode="FULL", run_id=RID, commit=COMMIT,
                       elapsed_sec=1.0, created_at="2026-08-24T00:00:00")
    st = S.status(rd, run_id=RID, mode="FULL", commit=COMMIT)
    assert all(v == "complete" for v in st["stages"].values())
    assert st["run_complete"] is False
    assert st["validator"] == "pending"


def test_status_computes_no_hash_by_default(rd, monkeypatch):
    """기본 조회는 해시를 계산하지 않는다 — 상태 조회가 무거워지면 안 쓴다."""
    B.stage_marker(rd, "m1_segments", mode="FULL", run_id=RID, commit=COMMIT,
                   elapsed_sec=1.0, created_at="2026-08-24T00:00:00")
    called = []
    monkeypatch.setattr(S.hashlib, "sha256",
                        lambda *a, **k: called.append(1))
    S.status(rd, run_id=RID, mode="FULL", commit=COMMIT)
    assert called == []


def test_verify_reports_unverifiable_without_output_hash(rd):
    B.stage_marker(rd, "m1_segments", mode="FULL", run_id=RID, commit=COMMIT,
                   elapsed_sec=1.0, created_at="2026-08-24T00:00:00")
    v = S.verify(rd, run_id=RID, mode="FULL", commit=COMMIT)
    assert v["unverifiable"] == ["m1_segments"]
    assert v["checked"] == []


def test_verify_hash_match_is_not_completion(rd):
    out = rd / "o.json"
    out.write_text("x", encoding="utf-8")
    import hashlib
    h = hashlib.sha256(b"x").hexdigest()
    S.write_marker(rd, "m1_segments", mode="FULL", run_id=RID, commit=COMMIT,
                   created_at="2026-08-24T00:00:00", output_hash=h,
                   output_file="o.json")
    v = S.verify(rd, run_id=RID, mode="FULL", commit=COMMIT)
    assert v["ok"] is True
    assert "완료 선언이 아니다" in v["note"]
    assert S.status(rd, run_id=RID, mode="FULL",
                    commit=COMMIT)["run_complete"] is False


# ---- handoff의 마커 관측이 새 이름을 놓치지 않는다 --------------------------

def test_handoff_sees_namespaced_markers(rd):
    B.stage_marker(rd, "m2_frames", mode="FULL", run_id=RID, commit=COMMIT,
                   elapsed_sec=1.0, created_at="2026-08-24T00:00:00")
    names = MH.marker_names(rd)
    assert names == [S.marker_name("FULL", "m2_frames")]


def test_handoff_still_sees_legacy_markers(rd):
    (rd / "STAGE_m2_frames_DONE").write_text("{}", encoding="utf-8")
    assert MH.marker_names(rd) == ["STAGE_m2_frames_DONE"]
