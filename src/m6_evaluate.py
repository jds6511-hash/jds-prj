"""M6 평가: dev grid search로 α 고정 → test 평가. test로 α를 고르는 경로는
존재하지 않는다(누수 원천 차단). [DESIGN_SPEC 4-6, v2 9-1]"""
import argparse, json
from collections import defaultdict
from pathlib import Path
import numpy as np
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


def derive_gt_seg_idx(gt_start, gt_end, n_segments, seg_len: int) -> list[int]:
    """1초 이상 겹치는 모든 세그먼트, 없으면 최대 겹침 1개. [3-3]"""
    overlaps = []
    for i in range(n_segments):
        s, e = i * seg_len, (i + 1) * seg_len
        overlaps.append((i, max(0.0, min(e, gt_end) - max(s, gt_start))))
    idx = [i for i, ov in overlaps if ov >= 1.0]
    return idx if idx else [max(overlaps, key=lambda t: t[1])[0]]


def validate_gt_seg_idx(queries, indexes, seg_len: int) -> None:
    """gt_seg_idx가 gt_start/gt_end와 겹치는 세그먼트를 전부 포함하는지 검증(초집합 허용).
    같은 사실이 영상 뒷부분에 재언급돼 gt_seg_idx가 derive_gt_seg_idx 결과의 초집합인 경우가
    실제로 있다(예: wl_q03, data/queries/DRAFT_REVIEW.md 참조) — 그런 추가 포함은 허용하고,
    반대로 겹치는 세그먼트가 누락된 경우(라벨 오탈자)만 잡는다. [보완: gt_seg_idx 무결성 검증 부재]"""
    for q in queries:
        n_segments = len(indexes[q["video_id"]].segments)
        out_of_range = [i for i in q["gt_seg_idx"] if not (0 <= i < n_segments)]
        assert not out_of_range, (
            f"{q['query_id']}: gt_seg_idx에 범위 밖 인덱스 {out_of_range} "
            f"(세그먼트 수 {n_segments}) — 라벨 오탈자 [리뷰 2026-07-11]")
        expected = set(derive_gt_seg_idx(q["gt_start"], q["gt_end"], n_segments, seg_len))
        missing = expected - set(q["gt_seg_idx"])
        assert not missing, (
            f"{q['query_id']}: gt_seg_idx={q['gt_seg_idx']}가 gt_start/gt_end와 겹치는 "
            f"세그먼트 {sorted(missing)}를 누락함 — 라벨 오류 가능성")


def load_queries(path) -> list[dict]:
    qs = [json.loads(line) for line in
          Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    dev_v = {q["video_id"] for q in qs if q["split"] == "dev"}
    test_v = {q["video_id"] for q in qs if q["split"] == "test"}
    leak = dev_v & test_v
    assert not leak, f"dev/test에 같은 video_id 존재(누수): {leak}"   # [5-1]
    for q in qs:
        assert q["gt_seg_idx"], f"{q['query_id']}: gt_seg_idx 비어있음"
        assert q.get("text"), f"{q['query_id']}: text 없음"
        # 오탈자 split은 dev/test 어디에도 안 들어가 조용히 평가에서 빠진다 [리뷰 2026-07-11]
        assert q["split"] in ("dev", "test"), f"{q['query_id']}: split={q['split']!r} 미허용"
    return qs


def _rank_of(ranked, gt_seg_idx) -> int:
    gt = set(gt_seg_idx)
    for rank, r in enumerate(ranked, 1):
        if r.idx in gt:
            return rank
    return 0    # not found


def _mean_metrics(rows) -> dict:
    keys = [k for k in rows[0] if k not in ("query_id", "type", "rank")]
    return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in keys}


def evaluate(queries, indexes, alpha, cfg, search_fn=search) -> dict:
    """질의셋 평균 지표 + per_query 랭크. by_type 분리 집계 포함. [3-4]"""
    if not queries:
        raise ValueError("평가할 질의가 없습니다 (queries 비어 있음)")
    per_q, buckets = [], defaultdict(list)
    for q in queries:
        ranked = search_fn(q["text"], indexes[q["video_id"]], alpha, cfg)
        row = {"query_id": q["query_id"], "type": q["type"],
               "rank": _rank_of(ranked, q["gt_seg_idx"]),
               **{f"hit@{k}": hit_at_k(ranked, q["gt_seg_idx"], k) for k in cfg["eval_k"]},
               "mrr": mrr(ranked, q["gt_seg_idx"]),
               **{f"iou@{t}_r@1": iou_recall_at_k(ranked, q["gt_start"], q["gt_end"], 1, t)
                  for t in cfg["iou_thresholds"]}}
        per_q.append(row); buckets[q["type"]].append(row)

    metrics = _mean_metrics(per_q)
    metrics["by_type"] = {t: _mean_metrics(rows) for t, rows in buckets.items()}
    return {"metrics": metrics, "per_query": per_q}


def _median_rank(rows):
    """rank=0(미발견)은 무한대로 취급 — 중앙값이 미발견 구간에 걸리면 None."""
    ranks = [r["rank"] if r["rank"] > 0 else float("inf") for r in rows]
    med = float(np.median(ranks))
    return None if med == float("inf") else round(med, 1)


def paired_diff_ci(base_pq, prop_pq, keys, B, seed) -> dict:
    """test 단발 평가의 proposed−baseline 차이에 대한 쌍체 부트스트랩 95% CI.
    α 재선택에는 쓰지 않는다(선택은 dev에서 종료) — 보고용 불확실성 정량화만. [8-7]"""
    n = len(base_pq)
    rng = np.random.default_rng(seed)
    idx_b = rng.integers(0, n, size=(B, n))
    out = {}
    for k in keys:
        b = np.array([r[k] for r in base_pq])
        p = np.array([r[k] for r in prop_pq])
        diffs = p[idx_b].mean(axis=1) - b[idx_b].mean(axis=1)
        out[k] = [round(float(x), 4) for x in np.percentile(diffs, [2.5, 97.5])]
    return out


def build_eval_result(test_queries, base, prop, alpha, cfg) -> dict:
    """eval_test.json 스키마 조립: baseline/proposed는 test_queries와 동일 순서라 zip으로
    query_id가 그대로 정렬된다. 경합/포화 분리·중앙값 랭크·차이 CI 포함. [3-4, 8-7]"""
    n_by_type = defaultdict(int)
    for q in test_queries:
        n_by_type[q["type"]] += 1

    pairs = list(zip(base["per_query"], prop["per_query"]))
    # 포화 = 양쪽 모두 rank 1 → 두 방법을 전혀 구분하지 못하는 질의. 나머지가 경합. [8-7]
    contested = [(b, p) for b, p in pairs if not (b["rank"] == 1 and p["rank"] == 1)]
    contested_block = {
        "n_saturated": len(pairs) - len(contested),
        "n_contested": len(contested),
        "query_ids": [b["query_id"] for b, _ in contested],
        "metrics": ({"baseline": _mean_metrics([b for b, _ in contested]),
                     "proposed": _mean_metrics([p for _, p in contested])}
                    if contested else None)}

    ci_keys = ["mrr"] + [f"hit@{k}" for k in cfg["eval_k"]]
    return {
        "alpha_from_dev": alpha,
        "n_queries": {"total": len(test_queries), **n_by_type},
        "metrics": {"baseline": base["metrics"], "proposed": prop["metrics"]},
        "diff_ci95": paired_diff_ci(base["per_query"], prop["per_query"],
                                    ci_keys, cfg["bootstrap_B"], cfg["seed"]),
        "rank_summary": {"baseline": {"median_rank": _median_rank(base["per_query"])},
                         "proposed": {"median_rank": _median_rank(prop["per_query"])}},
        "contested": contested_block,
        "per_query": [{"query_id": b["query_id"],
                       "baseline_rank": b["rank"], "proposed_rank": p["rank"]}
                      for b, p in pairs]}


def grid_search_alpha(dev_queries, indexes, cfg, search_fn=search) -> dict:
    """dev 전용 α 탐색: 점 추정(선택 지표, 기본 MRR) 1위 α_best_point를 기준점으로
    쌍체 차이(paired-diff) 부트스트랩 95% CI를 α별로 계산한다. CI가 0을 포함하는
    α들(tie_set)에 tiebreak(자막 우선=값이 큰 α)를 적용해 alpha_star를 고른다.
    재검색 없음 — α별 evaluate()는 1회씩만 호출하고 재표집 인덱스는 전 α 공유.
    [DESIGN_SPEC 8-1]"""
    metric = cfg["alpha_select_metric"]
    grid = cfg["alpha_grid"]
    assert cfg["alpha_tiebreak"] == "larger"

    results = {a: evaluate(dev_queries, indexes, a, cfg, search_fn) for a in grid}
    per_query_vec = {a: np.array([row[metric] for row in results[a]["per_query"]])
                     for a in grid}

    # 기준점 선택은 반올림 전 원시 평균으로 — metrics의 round(4)값을 쓰면 미세 차이가
    # 동률로 붕괴해 tiebreak가 기준점을 옮길 수 있다 [리뷰 2026-07-11 Minor]
    alpha_best_point = max(grid, key=lambda a: (float(per_query_vec[a].mean()), a))

    n = len(dev_queries)
    rng = np.random.default_rng(cfg["seed"])
    B = cfg["bootstrap_B"]
    idx_b = rng.integers(0, n, size=(B, n))   # 재표집 인덱스 행렬 — 전 α 공유 [8-1(b)]
    best_vec = per_query_vec[alpha_best_point]

    per_alpha, diff_ci = [], {}
    for a in grid:
        if a == alpha_best_point:
            lo, hi = 0.0, 0.0                  # 기준점 자신
        else:
            diffs = per_query_vec[a][idx_b].mean(axis=1) - best_vec[idx_b].mean(axis=1)
            lo, hi = (float(x) for x in np.percentile(diffs, [2.5, 97.5]))
        # 판정은 원시 lo/hi로 — 반올림 후 판정은 CI 하한이 0에 근접한 유의 α를
        # 동률로 오분류할 수 있다. JSON 저장용 리스트만 반올림. [리뷰 Major 2]
        diff_ci[a] = (lo, hi)
        m = results[a]["metrics"]
        per_alpha.append({
            "alpha": a, "mrr": m["mrr"],
            **{f"hit@{k}": m[f"hit@{k}"] for k in cfg["eval_k"]},
            "diff_vs_best_ci95": [round(lo, 4), round(hi, 4)],
            # per_query_rr은 alpha_select_metric의 per-query 벡터 — 필드명은
            # metric="mrr"(reciprocal rank) 전제로 8-1 스키마에 고정돼 있다.
            "per_query_rr": per_query_vec[a].tolist()})

    tie_set = [a for a in grid if diff_ci[a][0] <= 0.0 <= diff_ci[a][1]]
    alpha_star = max(tie_set)   # 동률 → larger [v2 9-1(a)]

    by_video = {}
    for vid in dict.fromkeys(q["video_id"] for q in dev_queries):   # 등장 순서 보존
        idxs = [i for i, q in enumerate(dev_queries) if q["video_id"] == vid]
        by_video[vid] = {str(a): round(float(per_query_vec[a][idxs].mean()), 4)
                          for a in grid}

    return {"select_metric": metric,
            "bootstrap": {"B": B, "seed": cfg["seed"], "method": "paired-diff"},
            "alpha_best_point": alpha_best_point,
            "per_alpha": per_alpha,
            "by_video": by_video,
            "tie_set": tie_set,
            "alpha_star": alpha_star}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--queries", default="data/queries/queries.jsonl")
    ap.add_argument("--static-threshold", type=float, default=None,
                    help="지정 시 저장된 is_static 대신 motion_score<thr로 재계산 [8-5(2)]")
    ap.add_argument("--dev-only", action="store_true",
                    help="dev grid search + alpha_search_dev.json 저장까지만 실행, test 평가 생략")
    ap.add_argument("--recompute-gt-seg-idx", action="store_true",
                    help="저장된 gt_seg_idx를 무시하고 gt_start/gt_end에서 cfg seg_len_sec 기준 "
                         "재계산 — seg_len ablation 전용 [ablation_plan 1-4④]")
    args = ap.parse_args()
    if args.static_threshold is not None and not args.dev_only:
        # 확정 config 값과 다른 threshold로 test를 평가하는 경로 차단 [8-5(2)]
        ap.error("--static-threshold는 --dev-only와 함께만 사용할 수 있습니다 "
                 "(test 평가는 확정 static_threshold로만 수행)")
    if args.recompute_gt_seg_idx and not args.dev_only:
        # 공식 test 평가는 확정 5초 라벨(gt_seg_idx)로만 수행 [9-1]
        ap.error("--recompute-gt-seg-idx는 --dev-only와 함께만 사용할 수 있습니다")
    cfg = common.load_config(args.config)
    queries = load_queries(args.queries)
    dev = [q for q in queries if q["split"] == "dev"]
    test = [q for q in queries if q["split"] == "test"]
    indexes = {vid: VideoIndex.load(cfg, vid, static_threshold=args.static_threshold)
              for vid in {q["video_id"] for q in queries}}
    if args.recompute_gt_seg_idx:
        # 초 단위 라벨(gt_start/gt_end)이 원본 — 세그먼트 격자가 바뀌면 여기서 재계산.
        # 재언급 구간 수동 추가분(wl_q03류 초집합)은 유실되나 ablation 상대 비교에는 무해.
        for q in queries:
            q["gt_seg_idx"] = derive_gt_seg_idx(
                q["gt_start"], q["gt_end"],
                len(indexes[q["video_id"]].segments), cfg["seg_len_sec"])
    validate_gt_seg_idx(queries, indexes, cfg["seg_len_sec"])
    rdir = Path(cfg["paths"]["results"]); rdir.mkdir(exist_ok=True)

    # ① dev grid search(쌍체 부트스트랩) → 저장 [8-1]
    dev_result = grid_search_alpha(dev, indexes, cfg)
    # 재현성 기록: CLI 인자(null)가 아니라 실효 임계값 — static_mask가 로드 시점
    # config 재판정으로 바뀐 뒤 null은 "당시 config 값"이라 판별 불가 [리뷰 2026-07-11 Major]
    dev_result["static_threshold"] = (args.static_threshold
                                      if args.static_threshold is not None
                                      else cfg["static_threshold"])
    dev_result["recompute_gt_seg_idx"] = args.recompute_gt_seg_idx   # 변형 플래그 기록
    common.atomic_write_json(rdir / "alpha_search_dev.json", dev_result)
    alpha = dev_result["alpha_star"]
    print(f"dev grid search: α*={alpha} (tie_set={dev_result['tie_set']})")

    if args.dev_only:
        print("dev-only: test 평가 생략")
        return

    # ② test 평가는 그 α만 사용 (baseline=1.0 vs proposed=α*)
    base = evaluate(test, indexes, 1.0, cfg)
    prop = evaluate(test, indexes, alpha, cfg)
    result = build_eval_result(test, base, prop, alpha, cfg)
    result["static_threshold"] = cfg["static_threshold"]   # 재현성 기록 [리뷰 2026-07-11]
    common.atomic_write_json(rdir / "eval_test.json", result)
    c = result["contested"]
    print(f"M6 완료: eval_test.json (baseline mrr={base['metrics']['mrr']}, "
          f"proposed mrr={prop['metrics']['mrr']}, "
          f"포화 {c['n_saturated']}/경합 {c['n_contested']}, "
          f"mrr diff CI95={result['diff_ci95']['mrr']})")


if __name__ == "__main__":
    main()
