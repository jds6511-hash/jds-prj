import json
import sys
import numpy as np
import pytest
import common
import m5_search
import m6_evaluate
from m5_search import Result, VideoIndex
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
    # [8-1] grid_search_alpha는 (best, table) 튜플 대신 alpha_search_dev.json 스키마
    # dict를 반환하도록 확장됨 — 이 테스트는 cfg에 seed/bootstrap_B를 추가하고
    # best 대신 alpha_star를 검증하도록 최소 수정했다(하강호환 시그니처 유지 불가,
    # 보고서에 근거 명시).
    queries = [{"query_id": "q1", "video_id": "v1", "text": "t", "gt_seg_idx": [0],
                "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"}]
    cfg = {"alpha_grid": [0.0, 0.5, 1.0], "alpha_select_metric": "hit@5",
           "alpha_tiebreak": "larger", "eval_k": [1, 5, 10], "iou_thresholds": [0.5, 0.3],
           "seed": 42, "bootstrap_B": 100}
    fake_search = lambda q, video, alpha, cfg: _r([0, 1, 2])     # 모든 α 동률
    result = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    assert result["alpha_star"] == 1.0                            # 동률 → α 큰 값 [9-1(a)]

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


def _dev_cfg(grid=None, metric="mrr", B=200):
    return {"alpha_grid": grid or [0.0, 0.3, 0.5, 0.7, 1.0],
            "alpha_select_metric": metric, "alpha_tiebreak": "larger",
            "eval_k": [1, 5, 10], "iou_thresholds": [0.5, 0.3],
            "seed": 42, "bootstrap_B": B}


def test_grid_search_alpha_paired_ci_all_tied():
    # 모든 α가 동일한 per-query 지표를 내는 스텁 → 차이가 항상 정확히 0이라
    # 재표집을 어떻게 하든 CI=[0,0], tie_set=전체 그리드, alpha_star=1.0(tiebreak) [8-1(b)]
    queries = [{"query_id": f"q{i}", "video_id": "v1", "text": "t", "gt_seg_idx": [0],
                "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"}
               for i in range(5)]
    cfg = _dev_cfg()
    fake_search = lambda q, video, alpha, cfg: _r([0, 1, 2])   # 모든 α 동일 결과
    result = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    for row in result["per_alpha"]:
        assert row["diff_vs_best_ci95"] == [0.0, 0.0]
    assert result["tie_set"] == cfg["alpha_grid"]
    assert result["alpha_star"] == 1.0


def test_grid_search_alpha_discriminates_single_alpha():
    # [리뷰 Major 1 재설계] 질의별 상관 노이즈(난이도) 주입: 질의 i의 기본 랭크
    # r_i = (i%10)+1 → per-query rr이 1.0~0.1로 넓게 분포. 모든 α가 같은 난이도
    # r_i를 공유하되 α=0.5만 전 질의에서 랭크 1 우위(r_i vs r_i+1). 쌍체 diff는
    # 전 질의 strict 음수 → 어떤 재표집에서도 평균이 음수 → diff CI가 0을 확실히
    # 배제해 tie_set={0.5} 단독. 반면 질의 간 분산이 커서 주변(marginal) CI는
    # 넓게 겹친다 — 아래에서 주변 방식 판정을 직접 계산해 동률 집합이 팽창함을
    # 함께 assert(변이 탐지력 자체 증명). [8-1(b)]
    n = 20
    queries = [{"query_id": f"q{i}", "video_id": "v1", "text": f"t{i}", "gt_seg_idx": [0],
                "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"}
               for i in range(n)]

    def fake_search(text, video, alpha, cfg):
        i = int(text[1:])
        base_rank = (i % 10) + 1                  # 질의 난이도: rr 1.0 ~ 0.1
        rank = base_rank if alpha == 0.5 else base_rank + 1
        return _r(list(range(1, rank)) + [0])     # gt(idx=0)를 해당 랭크에 배치

    cfg = _dev_cfg()
    result = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    assert result["alpha_best_point"] == 0.5
    assert result["tie_set"] == [0.5]
    assert result["alpha_star"] == 0.5

    # 주변(marginal) CI 겹침 방식이었다면: α별 평균 rr의 부트스트랩 CI가 best의
    # CI와 겹치는 α를 전부 동률 처리 → 이 데이터에서는 동률 집합이 2개 이상으로
    # 팽창한다(즉 구현이 주변 방식으로 변이되면 위 tie_set 단정이 실패).
    per_rr = {row["alpha"]: np.array(row["per_query_rr"]) for row in result["per_alpha"]}
    rng = np.random.default_rng(cfg["seed"])
    idx_b = rng.integers(0, n, size=(cfg["bootstrap_B"], n))
    marg_ci = {a: np.percentile(v[idx_b].mean(axis=1), [2.5, 97.5])
               for a, v in per_rr.items()}
    best = result["alpha_best_point"]
    marginal_tie = [a for a in cfg["alpha_grid"]
                    if marg_ci[a][0] <= marg_ci[best][1]
                    and marg_ci[best][0] <= marg_ci[a][1]]
    assert len(marginal_tie) >= 2   # 주변 방식은 이 데이터에서 오판 — 쌍체 방식 필요성 증명


def test_grid_search_alpha_deterministic():
    # 같은 cfg(같은 seed)로 2회 실행 시 alpha_search_dev.json 내용(dict)이 동일 [8-1(b)]
    n = 12
    queries = [{"query_id": f"q{i}", "video_id": "v1", "text": "t", "gt_seg_idx": [0],
                "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"}
               for i in range(n)]
    fake_search = (lambda q, video, alpha, cfg:
                    _r([0, 1, 2]) if alpha >= 0.5 else _r([2, 1, 0]))
    cfg = _dev_cfg()
    r1 = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    r2 = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    assert r1 == r2


def test_grid_search_alpha_schema_keys():
    n = 6
    queries = [{"query_id": f"q{i}", "video_id": "v1", "text": "t", "gt_seg_idx": [0],
                "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"}
               for i in range(n)]
    cfg = _dev_cfg()
    fake_search = lambda q, video, alpha, cfg: _r([0, 1, 2])
    result = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    assert set(result.keys()) == {"select_metric", "bootstrap", "alpha_best_point",
                                   "per_alpha", "by_video", "tie_set", "alpha_star"}
    assert result["select_metric"] == "mrr"
    assert result["bootstrap"] == {"B": cfg["bootstrap_B"], "seed": cfg["seed"],
                                    "method": "paired-diff"}
    assert len(result["per_alpha"]) == len(cfg["alpha_grid"])
    for row in result["per_alpha"]:
        assert {"alpha", "mrr", "hit@5", "diff_vs_best_ci95", "per_query_rr"} <= set(row.keys())
        assert len(row["per_query_rr"]) == n


def test_grid_search_alpha_by_video_breakdown():
    # dev 영상이 여럿이어도 by_video가 영상별로 분해되는지 확인(현재 dev 1영상이어도
    # 일반 구현이어야 한다는 요건). [8-1(c)]
    queries = (
        [{"query_id": f"a{i}", "video_id": "v1", "text": "t", "gt_seg_idx": [0],
          "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"} for i in range(3)]
        + [{"query_id": f"b{i}", "video_id": "v2", "text": "t", "gt_seg_idx": [0],
            "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"} for i in range(3)])
    cfg = _dev_cfg()
    fake_search = lambda q, video, alpha, cfg: _r([0, 1, 2])   # 모든 질의 mrr=1.0
    result = grid_search_alpha(queries, {"v1": None, "v2": None}, cfg, search_fn=fake_search)
    assert set(result["by_video"].keys()) == {"v1", "v2"}
    for table in result["by_video"].values():
        assert set(table.keys()) == {str(a) for a in cfg["alpha_grid"]}
        assert all(v == 1.0 for v in table.values())


def _main_cfg(tmp_path):
    return {"alpha_grid": [0.0, 0.5, 1.0], "alpha_select_metric": "mrr",
            "alpha_tiebreak": "larger", "eval_k": [1, 5, 10], "iou_thresholds": [0.5, 0.3],
            "seed": 42, "bootstrap_B": 50, "embed_model": "m",
            "paths": {"work": str(tmp_path / "work"), "results": str(tmp_path / "results")}}


def _write_dev_test_queries(tmp_path):
    p = tmp_path / "queries.jsonl"
    rows = [{"query_id": "d1", "video_id": "v1", "text": "t", "type": "자막형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "dev"},
            {"query_id": "t1", "video_id": "v2", "text": "t", "type": "자막형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "test"}]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return p


def _fake_video():
    return VideoIndex(segments=[{"idx": 0, "start": 0.0, "end": 5.0, "subtitle": ""}],
                      emb_sub=np.zeros((1, 2), dtype=np.float32),
                      emb_cap=np.zeros((1, 2), dtype=np.float32),
                      static_mask=np.array([False]))


def test_m6_main_dev_only_skips_test_eval(tmp_path, monkeypatch, capsys):
    # [8-5(2)] --dev-only: alpha_search_dev.json 생성 + eval_test.json 미생성,
    # 로그에 "dev-only: test 평가 생략" 출력.
    queries_path = _write_dev_test_queries(tmp_path)
    cfg = _main_cfg(tmp_path)
    monkeypatch.setattr(common, "load_config", lambda path: cfg)
    monkeypatch.setattr(VideoIndex, "load",
                        classmethod(lambda cls, cfg, vid, static_threshold=None: _fake_video()))
    monkeypatch.setattr(m5_search, "embed_texts",
                        lambda texts, model: np.zeros((1, 2), dtype=np.float32))
    monkeypatch.setattr(sys, "argv", ["m6_evaluate.py", "--config", "c.yaml",
                                      "--queries", str(queries_path), "--dev-only"])
    m6_evaluate.main()

    out = capsys.readouterr().out
    assert "dev-only: test 평가 생략" in out
    rdir = tmp_path / "results"
    assert (rdir / "alpha_search_dev.json").exists()
    assert not (rdir / "eval_test.json").exists()
    saved = json.loads((rdir / "alpha_search_dev.json").read_text(encoding="utf-8"))
    assert saved["static_threshold"] is None    # [8-1 스키마 확장]


def test_m6_static_threshold_requires_dev_only(monkeypatch):
    # [8-5(2)] --static-threshold 지정 시 --dev-only가 아니면 에러로 거부
    # (확정 config 값과 다른 threshold로 test를 평가하는 경로 차단).
    monkeypatch.setattr(sys, "argv", ["m6_evaluate.py", "--static-threshold", "0.05"])
    with pytest.raises(SystemExit):
        m6_evaluate.main()


def test_m6_static_threshold_passed_through_and_recorded(tmp_path, monkeypatch):
    # --static-threshold가 VideoIndex.load까지 관통하고 alpha_search_dev.json에
    # 재현성용으로 기록됨 [8-5(2)].
    queries_path = _write_dev_test_queries(tmp_path)
    cfg = _main_cfg(tmp_path)
    monkeypatch.setattr(common, "load_config", lambda path: cfg)
    calls = []

    def fake_load(cls, cfg, vid, static_threshold=None):
        calls.append(static_threshold)
        return _fake_video()

    monkeypatch.setattr(VideoIndex, "load", classmethod(fake_load))
    monkeypatch.setattr(m5_search, "embed_texts",
                        lambda texts, model: np.zeros((1, 2), dtype=np.float32))
    monkeypatch.setattr(sys, "argv", ["m6_evaluate.py", "--config", "c.yaml",
                                      "--queries", str(queries_path),
                                      "--dev-only", "--static-threshold", "0.05"])
    m6_evaluate.main()

    assert calls == [0.05, 0.05]   # dev(v1)·test(v2) 인덱스 모두 관통
    saved = json.loads((tmp_path / "results" / "alpha_search_dev.json")
                       .read_text(encoding="utf-8"))
    assert saved["static_threshold"] == 0.05
