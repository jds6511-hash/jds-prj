"""데모 gallery — dev 전용 경계와 분류 계약."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import demo_gallery as G                                            # noqa: E402


class _R:
    def __init__(self, idx, start, end, score=0.5):
        self.idx, self.start, self.end, self.score = idx, start, end, score


def _q(qid, split="dev", vid="v", typ="장면형", gt=(3,)):
    return {"query_id": qid, "split": split, "video_id": vid, "type": typ,
            "text": "질의", "gt_seg_idx": list(gt), "gt_start": 15,
            "gt_end": 20}


def _jsonl(tmp_path, rows):
    p = tmp_path / "q.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def test_only_dev_queries_are_loaded(tmp_path):
    p = _jsonl(tmp_path, [_q("d1"), _q("t1", split="test", vid="gemini_promo")])
    rows = G.load_dev_queries(p)
    assert [r["query_id"] for r in rows] == ["d1"]


def test_dev_row_pointing_at_test_video_is_refused(tmp_path):
    p = _jsonl(tmp_path, [_q("bad", vid="panibottle_vietnam1")])
    with pytest.raises(G.GalleryError) as e:
        G.load_dev_queries(p)
    assert "test split" in str(e.value)


def test_empty_dev_set_is_refused(tmp_path):
    p = _jsonl(tmp_path, [_q("t1", split="test")])
    with pytest.raises(G.GalleryError):
        G.load_dev_queries(p)


def test_gt_rank_finds_first_matching_result():
    res = [_R(1, 5, 10), _R(3, 15, 20), _R(2, 10, 15)]
    assert G.gt_rank(res, [3]) == 2
    assert G.gt_rank(res, [99]) is None
    assert G.gt_rank(res, []) is None


def test_classify_labels_are_descriptive():
    assert G.classify({"gt_rank": 1}) == "성공(1위)"
    assert G.classify({"gt_rank": 4}) == "부분(4위)"
    assert G.classify({"gt_rank": None}) == "어려움(5위 밖)"
    assert G.classify({"gt_rank": 9}) == "어려움(5위 밖)"


def test_query_types_are_the_three_declared():
    assert G.QUERY_TYPES == ("장면형", "자막형", "복합형")


def test_build_refuses_test_split_video(tmp_path):
    p = _jsonl(tmp_path, [_q("d1")])
    with pytest.raises(G.GalleryError) as e:
        G.build({}, p, ["gemini_promo"], 0.5)
    assert "test split" in str(e.value)


def test_module_does_not_import_evaluation():
    import ast
    src = (ROOT / "scripts" / "demo_gallery.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m6_evaluate", "p2_evaluate", "m9_report_eval"} & mods)


def test_round_robin_spreads_cases_across_videos():
    rows = ([_q(f"a{i}", vid="a") for i in range(5)] +
            [_q(f"b{i}", vid="b") for i in range(5)])
    picked = G.pick_round_robin(rows, ["a", "b"], 4)
    assert [p["video_id"] for p in picked] == ["a", "b", "a", "b"]
    assert [p["query_id"] for p in picked] == ["a0", "b0", "a1", "b1"]


def test_round_robin_falls_back_when_a_video_runs_out():
    rows = [_q("a0", vid="a")] + [_q(f"b{i}", vid="b") for i in range(3)]
    picked = G.pick_round_robin(rows, ["a", "b"], 3)
    assert [p["video_id"] for p in picked] == ["a", "b", "b"]
