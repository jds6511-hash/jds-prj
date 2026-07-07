"""M6 평가: dev grid search로 α 고정 → test 평가. test로 α를 고르는 경로는
존재하지 않는다(누수 원천 차단). [DESIGN_SPEC 4-6, v2 9-1]"""
import argparse, json
from collections import defaultdict
from pathlib import Path
import common
from m5_search import VideoIndex, search


def hit_at_k(ranked, gt_seg_idx, k: int) -> float:
    return 1.0 if set(r.idx for r in ranked[:k]) & set(gt_seg_idx) else 0.0


def mrr(ranked, gt_seg_idx) -> float:
    gt = set(gt_seg_idx)
    for rank, r in enumerate(ranked, 1):
        if r.idx in gt:
            return 1.0 / rank
    return 0.0


def _iou(a0, a1, b0, b1) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = (a1 - a0) + (b1 - b0) - inter
    return inter / union if union > 0 else 0.0


def iou_recall_at_k(ranked, gt_start, gt_end, k: int, thr: float) -> float:
    return 1.0 if any(_iou(r.start, r.end, gt_start, gt_end) >= thr
                      for r in ranked[:k]) else 0.0


def derive_gt_seg_idx(gt_start, gt_end, n_segments, seg_len: int = 5) -> list[int]:
    """1초 이상 겹치는 모든 세그먼트, 없으면 최대 겹침 1개. [3-3]"""
    overlaps = []
    for i in range(n_segments):
        s, e = i * seg_len, (i + 1) * seg_len
        overlaps.append((i, max(0.0, min(e, gt_end) - max(s, gt_start))))
    idx = [i for i, ov in overlaps if ov >= 1.0]
    return idx if idx else [max(overlaps, key=lambda t: t[1])[0]]


def load_queries(path) -> list[dict]:
    qs = [json.loads(line) for line in
          Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    dev_v = {q["video_id"] for q in qs if q["split"] == "dev"}
    test_v = {q["video_id"] for q in qs if q["split"] == "test"}
    leak = dev_v & test_v
    assert not leak, f"dev/test에 같은 video_id 존재(누수): {leak}"   # [5-1]
    for q in qs:
        assert q["gt_seg_idx"], f"{q['query_id']}: gt_seg_idx 비어있음"
    return qs


def _rank_of(ranked, gt_seg_idx) -> int:
    gt = set(gt_seg_idx)
    for rank, r in enumerate(ranked, 1):
        if r.idx in gt:
            return rank
    return 0    # not found


def evaluate(queries, indexes, alpha, cfg, search_fn=search) -> dict:
    """질의셋 평균 지표 + per_query 랭크. by_type 분리 집계 포함. [3-4]"""
    per_q, buckets = [], defaultdict(list)
    for q in queries:
        ranked = search_fn(q["text"], indexes[q["video_id"]], alpha, cfg) \
            if "text" in q else search_fn(None, indexes[q["video_id"]], alpha, cfg)
        row = {"query_id": q["query_id"], "type": q["type"],
               "rank": _rank_of(ranked, q["gt_seg_idx"]),
               **{f"hit@{k}": hit_at_k(ranked, q["gt_seg_idx"], k) for k in cfg["eval_k"]},
               "mrr": mrr(ranked, q["gt_seg_idx"]),
               **{f"iou@{t}_r@1": iou_recall_at_k(ranked, q["gt_start"], q["gt_end"], 1, t)
                  for t in cfg["iou_thresholds"]}}
        per_q.append(row); buckets[q["type"]].append(row)

    def _mean(rows):
        keys = [k for k in rows[0] if k not in ("query_id", "type", "rank")]
        return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in keys}

    metrics = _mean(per_q)
    metrics["by_type"] = {t: _mean(rows) for t, rows in buckets.items()}
    return {"metrics": metrics, "per_query": per_q}


def grid_search_alpha(dev_queries, indexes, cfg, search_fn=search):
    """dev 전용 α 탐색. 동률 시 α 큰 값(자막 우선). [4-6, v2 9-1(a)]"""
    metric = cfg["alpha_select_metric"]
    table = {}
    for alpha in cfg["alpha_grid"]:
        table[alpha] = evaluate(dev_queries, indexes, alpha, cfg, search_fn)["metrics"][metric]
    best = max(table, key=lambda a: (table[a], a))   # 동률 → larger
    assert cfg["alpha_tiebreak"] == "larger"
    return best, table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--queries", default="data/queries/queries.jsonl")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    queries = load_queries(args.queries)
    dev = [q for q in queries if q["split"] == "dev"]
    test = [q for q in queries if q["split"] == "test"]
    indexes = {vid: VideoIndex.load(cfg, vid) for vid in {q["video_id"] for q in queries}}
    rdir = Path(cfg["paths"]["results"]); rdir.mkdir(exist_ok=True)

    # ① dev grid search → 저장
    alpha, table = grid_search_alpha(dev, indexes, cfg)
    common.atomic_write_json(rdir / "alpha_search_dev.json",
                             {"best_alpha": alpha, "metric": cfg["alpha_select_metric"],
                              "table": {str(a): v for a, v in table.items()}})
    print(f"dev grid search: α*={alpha}")

    # ② test 평가는 그 α만 사용 (baseline=1.0 vs proposed=α*)
    base = evaluate(test, indexes, 1.0, cfg)
    prop = evaluate(test, indexes, alpha, cfg)
    n_by_type = defaultdict(int)
    for q in test:
        n_by_type[q["type"]] += 1
    common.atomic_write_json(rdir / "eval_test.json", {
        "alpha_from_dev": alpha,
        "n_queries": {"total": len(test), **n_by_type},
        "metrics": {"baseline": base["metrics"], "proposed": prop["metrics"]},
        "per_query": [{"query_id": b["query_id"],
                       "baseline_rank": b["rank"], "proposed_rank": p["rank"]}
                      for b, p in zip(base["per_query"], prop["per_query"])]})
    print(f"M6 완료: eval_test.json (baseline hit@5={base['metrics']['hit@5']}, "
          f"proposed hit@5={prop['metrics']['hit@5']})")


if __name__ == "__main__":
    main()
