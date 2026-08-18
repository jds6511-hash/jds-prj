"""M8 dev 예비 실행 — 순수 집계 로직. GPU 없이 검증한다.

사전등록: `docs/preregistration/M8_dev예비실행_사전등록_2026-08-18.md`.
관측만 하고 판정하지 않는 것이 요점이라, 여기서 검증하는 것은 **관측값이 맞게
집계되는가**와 **test를 건드리지 않는가**다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import m8_dev_pilot as P                                   # noqa: E402


def test_dev_video_ids_excludes_test_split(tmp_path):
    """**test 접촉 방지.** dev 질의가 붙은 영상만 고른다."""
    f = tmp_path / "q.jsonl"
    f.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in [
        {"video_id": "A", "split": "dev"}, {"video_id": "A", "split": "dev"},
        {"video_id": "B", "split": "test"}, {"video_id": "C", "split": "dev"},
    ]), encoding="utf-8")
    assert P.dev_video_ids(f) == ["A", "C"]


def test_catastrophic_detects_foreign_language_from_rejection():
    rep = {"events": [], "rejected": [{"reason": "foreign_language"}], "sentences": []}
    assert P.catastrophic_flags(rep)["foreign_language"] is True


def test_catastrophic_detects_foreign_language_in_kept_event():
    """기각되지 않고 살아남은 사건에 한자가 섞이는 경로도 본다."""
    rep = {"events": [{"event": "작업", "description": "女性が台所で料理をしている"}],
           "rejected": [], "sentences": []}
    assert P.catastrophic_flags(rep)["foreign_language"] is True


def test_catastrophic_flags_clean_report():
    rep = {"events": [{"event": "도착", "description": "사람들이 현장에 도착한다"}],
           "rejected": [],
           "sentences": [{"sent_id": 0, "text": "사람들이 현장에 도착한다 [seg#0]",
                          "cites": [0]}]}
    assert not any(P.catastrophic_flags(rep).values())


def test_catastrophic_no_events():
    assert P.catastrophic_flags({"events": [], "rejected": [],
                                 "sentences": []})["no_events"] is True


def test_run_stats_counts_parse_failures():
    rep = {"map_raw_outputs": ['[{"event":"a","span":[0,1],'
                               '"evidence_segments":[0],"description":"가"}]',
                               "쓰레기 출력"],
           "chunk_retries": [{"chunk": 1, "recovered": False}]}
    s = P.run_stats(rep)
    assert s["chunks"] == 2 and s["json_parse_failure_rate"] == 0.5
    assert s["chunk_retry_recovery_rate"] == 0.0


def test_run_stats_recovery_rate_none_when_no_retries():
    """재시도가 0건이면 비율은 0.0이 아니라 **측정 불가**다."""
    assert P.run_stats({"map_raw_outputs": ["x"],
                        "chunk_retries": []})["chunk_retry_recovery_rate"] is None
