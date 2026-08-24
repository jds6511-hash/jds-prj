"""coverage 선언 누락 = fail-closed — 계약 테스트.

`gate_for_full`이 "선언이 없으면 요구하지 않는다"로만 동작하면 **키를 빼는 것만으로
게이트를 우회**할 수 있다. 그래서 세 갈래로 갈라 둔다.

```
plan_schema_version >= 2   canary_coverage 선언 필수. 누락은 차단
그 이전 버전 + allowlist    명시적 legacy 면제 (요구 도입 전 계획만)
그 이전 버전 + allowlist 없음  **차단** — 모르는 계획을 조용히 통과시키지 않는다
```
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import canary_coverage as C     # noqa: E402
import exp_launcher as L        # noqa: E402

H = "c" * 64


def _exempt(tmp_path, entries) -> Path:
    p = tmp_path / "exempt.json"
    p.write_text(json.dumps({"required_from_plan_schema_version": 2,
                             "legacy_exempt": entries}, ensure_ascii=False),
                 encoding="utf-8")
    return p


def _rows():
    return [{"source_id": "aaa", "n_segments": 100, "pre_indexed": False,
             "speech_status": C.AUDIO_KNOWN},
            {"source_id": "-bbb", "n_segments": 200, "pre_indexed": True,
             "speech_status": "unknown"},
            {"source_id": "ccc", "n_segments": 300, "pre_indexed": False,
             "speech_status": C.AUDIO_KNOWN}]


CODECS = {"aaa": "native_h264", "-bbb": "transcoded_h264",
          "ccc": "native_h264"}


@pytest.fixture
def world(tmp_path):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"selected": _rows()}, ensure_ascii=False),
                      encoding="utf-8")
    d = tmp_path / "run"
    d.mkdir()
    (d / "batch_run_canary.json").write_text(
        json.dumps({"video_ids": ["aaa", "-bbb", "ccc"]}), encoding="utf-8")
    return {"sample": sample, "run_dir": d}


# ---- 새 스키마: 선언 누락은 차단 ------------------------------------------

def test_new_schema_without_declaration_is_blocked(tmp_path, world):
    plan = {"name": "newexp", "plan_schema_version": 2}
    with pytest.raises(C.CoverageError, match="선언"):
        C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=_exempt(tmp_path, []))


def test_new_schema_cannot_be_exempted_by_allowlist(tmp_path, world):
    """allowlist는 요구 도입 이전 계획용이다 — 새 스키마를 면제하지 못한다."""
    plan = {"name": "newexp", "plan_schema_version": 2}
    ex = _exempt(tmp_path, [{"plan_name": "newexp", "plan_hash": H,
                             "reason": "우회 시도"}])
    with pytest.raises(C.CoverageError):
        C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=ex)


def test_new_schema_with_declaration_runs_gate(tmp_path, world):
    plan = {"name": "newexp", "plan_schema_version": 2,
            C.COVERAGE_KEY: {"sample": str(world["sample"]),
                             "canary_result": "batch_run_canary.json"}}
    r = C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=_exempt(tmp_path, []))
    assert r["required"] is True and r["ok"] is True


def test_higher_schema_version_also_required(tmp_path, world):
    plan = {"name": "newexp", "plan_schema_version": 7}
    with pytest.raises(C.CoverageError):
        C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=_exempt(tmp_path, []))


# ---- 옛 스키마: allowlist에 있어야 통과 ------------------------------------

def test_legacy_plan_not_on_allowlist_is_blocked(tmp_path, world):
    """모르는 옛 계획을 조용히 통과시키지 않는다."""
    plan = {"name": "unknown_old"}
    with pytest.raises(C.CoverageError, match="면제 목록"):
        C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=_exempt(tmp_path, []))


def test_legacy_plan_on_allowlist_passes_as_exempt(tmp_path, world):
    plan = {"name": "old_plan", "_raw": "x"}
    ph = L.plan_hash(plan)
    ex = _exempt(tmp_path, [{"plan_name": "old_plan", "plan_hash": ph,
                             "reason": "요구 도입 이전"}])
    r = C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=ex)
    assert r["required"] is False
    assert r["legacy_exempt"] is True
    assert r["exempt_reason"]
    assert r.get("ok") is not True          # 면제는 통과가 아니다


def test_allowlist_entry_with_wrong_hash_is_blocked(tmp_path, world):
    """계획이 바뀌면 면제가 따라오지 않는다."""
    plan = {"name": "old_plan", "_raw": "changed"}
    ex = _exempt(tmp_path, [{"plan_name": "old_plan", "plan_hash": H,
                             "reason": "요구 도입 이전"}])
    with pytest.raises(C.CoverageError, match="plan_hash"):
        C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=ex)


def test_allowlist_entry_without_reason_is_blocked(tmp_path, world):
    plan = {"name": "old_plan", "_raw": "x"}
    ex = _exempt(tmp_path, [{"plan_name": "old_plan",
                             "plan_hash": L.plan_hash(plan)}])
    with pytest.raises(C.CoverageError, match="사유"):
        C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=ex)


def test_missing_allowlist_file_blocks(tmp_path, world):
    plan = {"name": "old_plan", "_raw": "x"}
    with pytest.raises(C.CoverageError):
        C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=tmp_path / "nope.json")


def test_legacy_declaring_coverage_still_runs_gate(tmp_path, world):
    """옛 계획이 선언했다면 면제가 아니라 검사한다."""
    plan = {"name": "old_plan", "_raw": "x",
            C.COVERAGE_KEY: {"sample": str(world["sample"]),
                             "canary_result": "batch_run_canary.json"}}
    r = C.gate_for_full(plan, run_dir=world["run_dir"], root=ROOT,
                        codec_of=CODECS, exempt_path=_exempt(tmp_path, []))
    assert r["required"] is True


# ---- 실제 allowlist -------------------------------------------------------

def test_real_allowlist_covers_existing_plans(tmp_path, monkeypatch):
    """지금 저장소에 있는 계획 4건이 전부 면제 목록과 해시까지 일치한다."""
    ex = json.loads(C.EXEMPT_PATH.read_text(encoding="utf-8"))
    by_name = {e["plan_name"]: e for e in ex["legacy_exempt"]}
    # repo 밖으로 잡는다 — load_plan은 repo 안 로그 경로를 거부한다(2026-08-17 사고).
    # setdefault로 두면 앞선 테스트가 심은 값에 따라 결과가 갈린다.
    monkeypatch.setenv("EXP_LOG_DIR", str(tmp_path / "logs"))
    for rel in ("docs/planning/p2_index_plan.json",
                "planning/exp_plans/alpha_curve.json",
                "planning/exp_plans/dev_precision_3arm.json",
                "planning/exp_plans/m8_dev_pilot.json"):
        plan = L.load_plan(ROOT / rel, root=ROOT)
        e = by_name[plan["name"]]
        assert e["plan_hash"] == L.plan_hash(plan), rel
        assert e["reason"]


def test_real_allowlist_declares_required_version():
    ex = json.loads(C.EXEMPT_PATH.read_text(encoding="utf-8"))
    assert ex["required_from_plan_schema_version"] == \
        C.COVERAGE_REQUIRED_FROM_SCHEMA


def test_p2_plan_still_has_no_declaration():
    """완료된 P2 계획은 여전히 손대지 않는다 (plan_hash 보존)."""
    plan = json.loads((ROOT / "docs" / "planning" / "p2_index_plan.json")
                      .read_text(encoding="utf-8"))
    assert C.COVERAGE_KEY not in plan
    assert "plan_schema_version" not in plan


# ---- launcher 경로 --------------------------------------------------------

def test_launcher_blocks_new_plan_missing_declaration(tmp_path, world):
    plan = {"name": "newexp", "plan_schema_version": 2, "command": ["echo"],
            "canary_args": [], "full_args": [], "run_root": "run",
            "log_dir": str(tmp_path), "protected_splits": ["test"],
            "expected_files": ["o.json"]}
    with pytest.raises((L.LauncherError, C.CoverageError)):
        L.require_stage_approval(plan, "r1", {"canary_validated": True},
                                 stage="FULL", approve_full="r1",
                                 approve_test_open=None, root=ROOT,
                                 run_dir=world["run_dir"], codec_of=CODECS)
