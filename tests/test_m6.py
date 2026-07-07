import json, pytest
from m5_search import Result
from m6_evaluate import (hit_at_k, mrr, iou_recall_at_k, derive_gt_seg_idx,
                         load_queries, grid_search_alpha, evaluate, build_eval_result)

def _r(indexes):  # Result 리스트 헬퍼 (idx→start=idx*5)
    return [Result(i, 1.0 - n * 0.1, i * 5, i * 5 + 5) for n, i in enumerate(indexes)]

def test_hit_at_k():
    ranked = _r([3, 7, 1])
    assert hit_at_k(ranked, [7], k=1) == 0.0
    assert hit_at_k(ranked, [7], k=2) == 1.0
    assert hit_at_k(ranked, [9, 1], k=3) == 1.0       # 교집합 존재 여부

def test_mrr_first_gt_rank():
    assert mrr(_r([3, 7, 1]), [7]) == 0.5             # 첫 등장 랭크 2 → 1/2
    assert mrr(_r([3, 7, 1]), [1, 7]) == 0.5          # gt 중 처음 등장
    assert mrr(_r([3]), [9]) == 0.0

def test_iou_recall():
    ranked = _r([0])                                   # 예측 0~5초
    assert iou_recall_at_k(ranked, 0.0, 5.0, k=1, thr=0.5) == 1.0
    assert iou_recall_at_k(ranked, 3.0, 7.0, k=1, thr=0.5) == 0.0  # IoU 2/9

def test_derive_gt_seg_idx():
    assert derive_gt_seg_idx(3.0, 7.0, n_segments=3, seg_len=5) == [0, 1]   # 둘 다 2s 겹침 ≥1s
    assert derive_gt_seg_idx(4.8, 5.4, n_segments=3, seg_len=5) == [1]      # 최대 겹침 1개 보장
    assert derive_gt_seg_idx(33.0, 38.5, n_segments=10, seg_len=5) == [6, 7]

def test_load_queries_asserts_split_leak(tmp_path):
    p = tmp_path / "queries.jsonl"
    rows = [{"query_id": "q1", "video_id": "v1", "text": "t", "type": "자막형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "dev"},
            {"query_id": "q2", "video_id": "v1", "text": "t", "type": "장면형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "test"}]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    with pytest.raises(AssertionError, match="video_id"):        # 누수 차단 [5-1]
        load_queries(p)

def test_evaluate_empty_queries_raises_clear_error():
    with pytest.raises(ValueError, match="질의가 없습니다"):        # fail-fast, opaque IndexError 방지
        evaluate([], {}, 1.0, {"eval_k": [1, 5, 10], "iou_thresholds": [0.5, 0.3]})

def test_grid_search_tiebreak_larger_alpha():
    queries = [{"query_id": "q1", "video_id": "v1", "text": "t", "gt_seg_idx": [0],
                "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"}]
    cfg = {"alpha_grid": [0.0, 0.5, 1.0], "alpha_select_metric": "hit@5",
           "alpha_tiebreak": "larger", "eval_k": [1, 5, 10], "iou_thresholds": [0.5, 0.3]}
    fake_search = lambda q, video, alpha, cfg: _r([0, 1, 2])     # 모든 α 동률
    best, table = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    assert best == 1.0                                            # 동률 → α 큰 값 [9-1(a)]

def test_load_queries_asserts_text_present(tmp_path):
    # text 누락은 sentence-transformers 내부까지 들어가기 전에 fail-fast [리뷰 반영]
    p = tmp_path / "queries.jsonl"
    rows = [{"query_id": "q1", "video_id": "v1", "type": "자막형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "dev"}]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    with pytest.raises(AssertionError, match="text"):
        load_queries(p)

def test_build_eval_result_schema_and_alignment():
    # eval_test.json 조립 스키마 + baseline/proposed의 per_query가 같은 query_id로
    # 정렬되는지(zip의 positional 정합성) [리뷰 반영]
    test_queries = [
        {"query_id": "q1", "video_id": "v1", "text": "t1", "type": "자막형",
         "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "test"},
        {"query_id": "q2", "video_id": "v1", "text": "t2", "type": "장면형",
         "gt_start": 5.0, "gt_end": 10.0, "gt_seg_idx": [1], "split": "test"}]
    cfg = {"eval_k": [1, 5], "iou_thresholds": [0.5]}
    indexes = {"v1": None}
    fake_search = lambda q, video, alpha, cfg: _r([0, 1])
    base = evaluate(test_queries, indexes, 1.0, cfg, fake_search)
    prop = evaluate(test_queries, indexes, 0.5, cfg, fake_search)
    result = build_eval_result(test_queries, base, prop, alpha=0.5)
    assert set(result.keys()) == {"alpha_from_dev", "n_queries", "metrics", "per_query"}
    assert result["alpha_from_dev"] == 0.5
    assert result["n_queries"] == {"total": 2, "자막형": 1, "장면형": 1}
    assert set(result["metrics"].keys()) == {"baseline", "proposed"}
    assert len(result["per_query"]) == 2
    for row, q in zip(result["per_query"], test_queries):     # positional 정렬 고정
        assert row["query_id"] == q["query_id"]
        assert set(row.keys()) == {"query_id", "baseline_rank", "proposed_rank"}
