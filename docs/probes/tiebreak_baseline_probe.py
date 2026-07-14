"""[dev 전용 진단] 비평 3번 검증: baseline(α=1.0) 장면형 랭킹이 무발화 세그먼트
동일 벡터 + stable-sort 인덱스 tie-break 때문에 '질의-독립 고정순서 아티팩트'인지,
아니면 질의에 반응하는 실질 랭킹인지 실측한다.

핵심 질문:
  Q1. 장면형 질의에서 baseline top-1이 질의마다 바뀌는가?(질의-독립성)
      영상별 distinct top-1 수가 ~1이면 고정순서 아티팩트에 가깝다.
  Q2. GT가 동점 블록 안에 들어가 순위가 tie-break로 결정되는가?
  Q3. 무발화(빈 자막) 세그먼트 비율과 동일-벡터 블록 크기.

test 미접촉·config 불변·공식 결과 파일 미기록. 결과는 scratchpad JSON으로만 출력.
재현: python docs/probes/tiebreak_baseline_probe.py
"""
import json, sys
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex, search_with_stats, combine_scores

TIE = 1e-9


def main():
    cfg = common.load_config("config.yaml")
    qs = [json.loads(l) for l in
          Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = {q["video_id"] for q in dev}
    idx = {v: VideoIndex.load(cfg, v) for v in vids}

    # 무발화(빈 자막) 세그먼트 프로파일
    empty_profile = {}
    for v, vi in idx.items():
        subs = [s.get("subtitle", "") for s in vi.segments]
        empty = [i for i, t in enumerate(subs) if not t.strip()]
        # 동일 emb_sub 벡터 블록(빈 자막이면 같은 임베딩) — 행 해시로 군집
        rows = [vi.emb_sub[i].tobytes() for i in range(len(subs))]
        dup = Counter(rows)
        biggest = max(dup.values())
        empty_profile[v] = {"n_seg": len(subs), "n_empty_sub": len(empty),
                            "empty_frac": round(len(empty) / len(subs), 3),
                            "largest_identical_emb_block": biggest}

    per_type = defaultdict(list)
    top1_by_video_type = defaultdict(lambda: defaultdict(list))
    rows = []
    for q in dev:
        vi = idx[q["video_id"]]
        ranked, _ = search_with_stats(q["text"], vi, 1.0, cfg)  # baseline α=1.0
        score = np.array([r.score for r in ranked])  # 이미 내림차순
        top_score = score[0]
        top_tie = int(np.sum(np.abs(score - top_score) < TIE))
        # GT 순위와 GT 동점 블록
        gt = set(q["gt_seg_idx"])
        gt_rank = next((r for r, res in enumerate(ranked, 1) if res.idx in gt), 0)
        gt_in_tie = 0
        if gt_rank:
            gt_score = score[gt_rank - 1]
            gt_in_tie = int(np.sum(np.abs(score - gt_score) < TIE))
        rr = 1.0 / gt_rank if gt_rank else 0.0
        row = {"query_id": q["query_id"], "type": q["type"], "video": q["video_id"],
               "gt_rank": gt_rank, "rr": round(rr, 3),
               "top1_idx": ranked[0].idx, "top1_tie_block": top_tie,
               "gt_tie_block": gt_in_tie}
        rows.append(row)
        per_type[q["type"]].append(row)
        top1_by_video_type[q["video_id"]][q["type"]].append(ranked[0].idx)

    # 타입별 요약
    type_summary = {}
    for t, rs in per_type.items():
        type_summary[t] = {
            "n": len(rs),
            "baseline_mrr": round(sum(r["rr"] for r in rs) / len(rs), 4),
            "mean_top1_tie_block": round(sum(r["top1_tie_block"] for r in rs) / len(rs), 1),
            "queries_with_gt_in_tie>1": sum(1 for r in rs if r["gt_tie_block"] > 1),
            "mean_gt_tie_block": round(sum(r["gt_tie_block"] for r in rs) / len(rs), 1),
        }

    # 질의-독립성: 영상×타입별 distinct top-1 수 / 질의 수
    independence = {}
    for v, byt in top1_by_video_type.items():
        independence[v] = {t: {"n_queries": len(lst), "distinct_top1": len(set(lst)),
                               "top1_mode_share": round(Counter(lst).most_common(1)[0][1] / len(lst), 2)}
                           for t, lst in byt.items()}

    out = {"empty_subtitle_profile": empty_profile,
           "type_summary": type_summary,
           "query_independence_top1": independence,
           "rows": rows}
    scratch = Path(__file__).resolve().parent / "_scratch" / "tiebreak_probe.json"
    scratch.parent.mkdir(exist_ok=True)
    scratch.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", scratch)


if __name__ == "__main__":
    main()
