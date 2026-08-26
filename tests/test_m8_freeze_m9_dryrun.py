"""M8 동결 manifest와 M9 예비 점검.

두 도구가 막는 것은 하나다 — **test를 연 뒤에 M8을 고치는 것**.

```
m8_freeze.py   동결 시점의 config·프롬프트·스키마·validator·판정규칙 해시를 남기고
               --verify로 "지금이 그때와 같은가"를 되묻는다
m9_dryrun.py   공식 test를 열지 않고 합성 fixture로 M9 배선 전체를 지난다
               (M9는 split=="test" 하드코딩이라 실제 test로는 예비 실행이 불가능하다)
```
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import m8_freeze  # noqa: E402
import m9_dryrun  # noqa: E402


# ------------------------------------------------------------ freeze manifest

def test_manifest_records_everything_that_changes_m8_output():
    man = m8_freeze.build_manifest()
    assert man["test_opened"] is False
    assert man["git_commit"]
    assert man["report_schema_version"] >= 2
    for key in ("system", "build_map_prompt", "build_reduce_prompt",
                "build_event_prompt", "event_rules"):
        assert man["prompt_sha256"][key], key
    for name in ("m8_report", "m8_metrics", "aar_view", "llm", "common"):
        assert man["file_sha256"][name], name
    for key in ("report_model", "map_chunk_size", "judge_model", "same_model_judge"):
        assert key in man["config_frozen_keys"], key


def test_manifest_never_declares_test_opened():
    """이 스크립트는 test 개방을 기록하지 않는다 — 그것은 별도 승인 사건이다."""
    src = (ROOT / "scripts/m8_freeze.py").read_text(encoding="utf-8")
    assert '"test_opened": False' in src
    assert '"test_opened": True' not in src


def test_verify_detects_a_prompt_change(monkeypatch):
    man = m8_freeze.build_manifest()
    monkeypatch.setattr(m8_freeze.m8_report, "prompt_sources",
                        lambda: {**{k: "바뀐 프롬프트" for k in man["prompt_sha256"]}})
    diffs = m8_freeze.verify(man)
    assert diffs and any("prompt_sha256" in d for d in diffs)


def test_verify_detects_a_config_change(monkeypatch):
    man = m8_freeze.build_manifest()
    real = m8_freeze.common.load_config

    def fake(path):
        cfg = dict(real(path))
        cfg["map_chunk_size"] = 999
        return cfg

    monkeypatch.setattr(m8_freeze.common, "load_config", fake)
    diffs = m8_freeze.verify(man)
    assert any("config_sha256" in d for d in diffs)


def test_verify_is_quiet_when_nothing_changed():
    assert m8_freeze.verify(m8_freeze.build_manifest()) == []


def test_freeze_refuses_to_overwrite(tmp_path, monkeypatch, capsys):
    out = tmp_path / "m8_freeze.json"
    monkeypatch.setattr(sys, "argv", ["m8_freeze.py", "--out", str(out)])
    assert m8_freeze.main() == 0
    monkeypatch.setattr(sys, "argv", ["m8_freeze.py", "--out", str(out)])
    assert m8_freeze.main() == 2            # 동결본을 덮지 않는다
    assert "덮지 않는다" in capsys.readouterr().out


def test_verify_mode_reports_missing_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["m8_freeze.py", "--verify",
                                      "--out", str(tmp_path / "없다.json")])
    assert m8_freeze.main() == 2


# ------------------------------------------------------------ M9 dry-run

@pytest.fixture(scope="module")
def dryrun(tmp_path_factory):
    return m9_dryrun.run(tmp_path_factory.mktemp("m9dry"))


def test_dryrun_passes_every_wiring_check(dryrun):
    failed = [k for k, v in dryrun["checks"].items() if not v]
    assert failed == [], failed
    assert dryrun["ok"] is True


def test_dryrun_uses_a_synthetic_video_id(dryrun):
    """실제 영상 이름을 쓰면 산출물이 섞인다."""
    import eligibility
    assert dryrun["fixture_video"] not in eligibility.TEST_SPLIT_VIDEOS
    assert "synthetic" in dryrun["fixture_video"]


def test_dryrun_never_reads_the_real_query_file():
    src = (ROOT / "scripts/m9_dryrun.py").read_text(encoding="utf-8")
    assert "data/queries/queries.jsonl" not in src


def test_dryrun_does_not_load_a_real_judge_model():
    """GPU·모델 다운로드 없이 돌아야 예비 점검이 성립한다.

    문서 문자열에는 "make_llm을 부르지 않는다"가 있으므로 **실행되는 줄**만 본다.
    """
    src = (ROOT / "scripts/m9_dryrun.py").read_text(encoding="utf-8")
    code_lines = [ln for ln in src.splitlines()
                  if "make_llm" in ln and not ln.lstrip().startswith(("#", '"', "'"))
                  and "부르지 않는다" not in ln]
    assert code_lines == [], code_lines
    assert "from llm import" not in src and "import llm" not in src


def test_dryrun_rejects_out_of_range_citation(dryrun):
    assert dryrun["checks"]["structural_rejects_bad_citation"] is True


def test_the_two_validators_now_share_one_standard(dryrun):
    """D4(2026-08-26): 인용 없는 evaluable 문장은 **양쪽 모두 거부**한다.

    종전에는 `aar_view`가 거부하고 M9는 자동 ungrounded로 점수화해 같은 산출물에
    기준이 둘이었다. 판정 함수는 `common`에 하나만 둔다 — 사본을 만들면 다시 갈라진다.
    """
    import common
    import m9_report_eval
    assert dryrun["checks"]["uncited_sentence_is_structural_fail"] is True
    for mod in ("scripts/aar_view.py", "src/m9_report_eval.py"):
        src = (ROOT / mod).read_text(encoding="utf-8")
        assert "uncited_evaluable_sentences" in src, mod
    rep = {"sentences": [{"sent_id": 0, "text": "인용 없다", "cites": []}]}
    with pytest.raises(m9_report_eval.StructuralError):
        m9_report_eval.structural_precheck(rep, n_segments=3)
    assert common.uncited_evaluable_sentences(rep["sentences"]) == [0]


def test_dryrun_with_freeze_manifest(tmp_path):
    man = tmp_path / "freeze.json"
    man.write_text(json.dumps(m8_freeze.build_manifest(), ensure_ascii=False),
                   encoding="utf-8")
    res = m9_dryrun.run(tmp_path / "run", freeze_manifest=man)
    assert res["checks"]["freeze_match"] is True
    assert res["checks"]["freeze_test_unopened"] is True


def test_dryrun_fails_when_freeze_says_test_already_opened(tmp_path):
    man_path = tmp_path / "freeze_opened.json"
    man = m8_freeze.build_manifest()
    man["test_opened"] = True
    man_path.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    res = m9_dryrun.run(tmp_path / "run2", freeze_manifest=man_path)
    assert res["checks"]["freeze_test_unopened"] is False
    assert res["ok"] is False
