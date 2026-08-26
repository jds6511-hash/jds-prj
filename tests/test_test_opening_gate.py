"""test 39건 접촉이 **코드에서** 막히는지 본다.

CLAUDE.md 절대규칙 1은 test 재평가를 사용자 승인 사건으로 규정한다. 2026-08-26
감사까지 그 규칙은 **문서에만** 있었다.

```
m6_evaluate   --dev-only가 opt-in이라 기본 경로가 test 평가였다
m9_report_eval  split=="test" 하드코딩 — 실행 자체가 test 접촉인데 게이트가 없었다
```

둘 다 `python src/…py` 한 줄로 비가역 자원에 닿았다. 사유를 요구하고, 그 사유를
결과 JSON에 남긴다 — 접촉 이력이 산출물에서 재구성돼야 한다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import m6_evaluate  # noqa: E402
import m9_report_eval  # noqa: E402


def test_m6_refuses_test_evaluation_without_a_stated_reason(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["m6_evaluate.py"])
    with pytest.raises(SystemExit):
        m6_evaluate.main()
    assert "승인 사건" in capsys.readouterr().err


def test_m9_refuses_to_run_without_a_stated_reason(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["m9_report_eval.py", "--video-id", "v"])
    with pytest.raises(SystemExit) as e:
        m9_report_eval.main()
    assert "test 접촉" in str(e.value)


def test_m6_records_the_reason_in_the_result(tmp_path, monkeypatch):
    """사유가 결과에 남아야 '몇 번째 접촉이 왜 일어났는가'를 나중에 셀 수 있다."""
    import json
    import numpy as np
    import common
    import m5_search
    from m5_search import VideoIndex

    q = tmp_path / "queries.jsonl"
    rows = [{"query_id": "d1", "video_id": "v1", "text": "t", "type": "자막형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "dev"},
            {"query_id": "t1", "video_id": "v2", "text": "t", "type": "자막형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "test"}]
    q.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    cfg = {"embed_model": "m", "seg_len_sec": 5, "static_threshold": 0,
           "alpha_grid": [0.0, 0.5, 1.0], "alpha_select_metric": "mrr",
           "alpha_tiebreak": "larger", "bootstrap_B": 10, "eval_k": [1, 5],
           "iou_thresholds": [0.5], "seed": 42,
           "paths": {"work": str(tmp_path / "work"),
                     "results": str(tmp_path / "results")}}
    fake = VideoIndex(
        segments=[{"idx": 0, "start": 0.0, "end": 5.0, "subtitle": ""}],
        emb_sub=np.zeros((1, 2), dtype=np.float32),
        emb_cap=np.zeros((1, 2), dtype=np.float32),
        static_mask=np.array([False]))
    monkeypatch.setattr(common, "load_config", lambda path: cfg)
    monkeypatch.setattr(VideoIndex, "load",
                        classmethod(lambda cls, c, vid, static_threshold=None: fake))
    monkeypatch.setattr(m5_search, "embed_texts",
                        lambda texts, model: np.zeros((1, 2), dtype=np.float32))
    monkeypatch.setattr(sys, "argv",
                        ["m6_evaluate.py", "--queries", str(q),
                         "--test-opening", "감사용 스모크 — 실제 승인 아님"])
    m6_evaluate.main()
    saved = json.loads((tmp_path / "results" / "eval_test.json")
                       .read_text(encoding="utf-8"))
    assert saved["test_opening"] == "감사용 스모크 — 실제 승인 아님"


def test_help_text_names_the_rule():
    """규칙 번호가 도움말에 있어야 다음 사람이 근거를 찾는다."""
    for mod in (m6_evaluate, m9_report_eval):
        src = (ROOT / "src" / f"{mod.__name__}.py").read_text(encoding="utf-8")
        assert "절대규칙 1" in src, mod.__name__
