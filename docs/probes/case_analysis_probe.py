"""[#4 정성적 오류분석 — 기존 확정 결과의 사례 근거 추출, 재평가 아님]
eval_test.json의 확정 per_query 순위(baseline_rank/proposed_rank)를 재현·대조하며,
선정 사례에서 '왜 이겼나/졌나'를 세그먼트 자막·캡션으로 설명하는 근거를 뽑는다.
MRR/hit 재계산·config 변경·results 기록 없음. 순위는 확정값과 일치해야 함(consistency).
출력: scratchpad JSON. 재현: python docs/probes/case_analysis_probe.py
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex, search

CASES = {
    "회귀": ["it_q07", "yn_q09"],
    "대개선": ["pb_q10", "gm_q04", "gm_q08", "it_q10", "it_q09"],
}


def seg_brief(seg):
    return {"idx": seg["idx"], "t": f'{seg["start"]}-{seg["end"]}s',
            "sub": (seg.get("subtitle") or "")[:60],
            "cap": (seg.get("caption") or "")[:70]}


def main():
    cfg = common.load_config("config.yaml")
    qs = {q["query_id"]: q for q in
          (json.loads(l) for l in
           Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
    ev = {r["query_id"]: r for r in json.load(open("results/eval_test.json", encoding="utf-8"))["per_query"]}

    want = [qid for group in CASES.values() for qid in group]
    vids = sorted({qs[qid]["video_id"] for qid in want})
    idx = {v: VideoIndex.load(cfg, v) for v in vids}

    out = {"note": "재평가 아님 — 확정 순위 재현·사례 근거만.", "cases": {}}
    mismatch = []
    for group, qids in CASES.items():
        for qid in qids:
            q = qs[qid]; vi = idx[q["video_id"]]
            base = search(q["text"], vi, 1.0, cfg)     # baseline
            prop = search(q["text"], vi, 0.5, cfg)      # proposed α*=0.5
            gt = set(q["gt_seg_idx"])
            b_rank = next((r for r, x in enumerate(base, 1) if x.idx in gt), 0)
            p_rank = next((r for r, x in enumerate(prop, 1) if x.idx in gt), 0)
            # 확정값 대조
            exp = ev[qid]
            if (b_rank, p_rank) != (exp["baseline_rank"], exp["proposed_rank"]):
                mismatch.append((qid, (b_rank, p_rank), (exp["baseline_rank"], exp["proposed_rank"])))
            segs = {s["idx"]: s for s in vi.segments}
            gt_idx = q["gt_seg_idx"][0]
            out["cases"][qid] = {
                "group": group, "type": q["type"], "video": q["video_id"],
                "query": q["text"], "gt_seg_idx": q["gt_seg_idx"],
                "baseline_rank": b_rank, "proposed_rank": p_rank,
                "gt_segment": seg_brief(segs[gt_idx]),
                "baseline_top1": seg_brief(segs[base[0].idx]),
                "proposed_top1": seg_brief(segs[prop[0].idx]),
                # baseline이 GT보다 위에 올린 세그먼트(회귀 진단용): proposed top1이 GT면 생략
                "baseline_above_gt": [seg_brief(segs[x.idx]) for x in base[:min(b_rank-1, 3)]] if b_rank > 1 else [],
                "proposed_above_gt": [seg_brief(segs[x.idx]) for x in prop[:min(p_rank-1, 3)]] if p_rank > 1 else [],
            }

    out["rank_consistency_with_eval_test"] = "OK" if not mismatch else mismatch
    dest = Path("C:/Users/UserK/AppData/Local/Temp/claude/"
                "c--Users-UserK-Desktop-prj/f443ead9-6036-4c8c-8abc-28dc150439d3/"
                "scratchpad/case_analysis.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest, "| consistency:", out["rank_consistency_with_eval_test"])


if __name__ == "__main__":
    main()
