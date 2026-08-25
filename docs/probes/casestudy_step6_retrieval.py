"""STEP 6 — 동결 질의 15개 × fresh 3B / fresh 4B, caption-only alpha=0 검색.

**해석하지 않는다.** 숫자·순위만 기계 판독 형식으로 저장한다. 캡션 텍스트와 프레임은
STEP 7에서 별도로 연다. 이것이 계획 동결 이후 첫 outcome access다.

금지(계획·amendment에 동결): 질의 수정 · target scene 변경 · 결과 보고 질의 교체 ·
alpha sweep · 새 scene 추가 · 사례 교체 · deployment 판단 생성.

사용: python docs/probes/casestudy_step6_retrieval.py [--alpha 0.0]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import yaml  # noqa: E402
import m5_search  # noqa: E402

RD = ROOT / "runs/casestudy_caption_retrieval/cs_20260825"
PLAN = ROOT / "docs/finalization/caption_retrieval_casestudy_plan.json"
V = "pland_costco_hosting"
ARMS = ("3b", "4b")


def git_head() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    scenes = plan["scenes"]

    idx_by_arm, cfgs = {}, {}
    for arm in ARMS:
        cfg = yaml.safe_load((RD / ("config_%s.yaml" % arm)).read_text(encoding="utf-8"))
        cfgs[arm] = cfg
        idx_by_arm[arm] = m5_search.VideoIndex.load(cfg, V)

    n_seg = len(idx_by_arm["3b"].segments)
    rows = []
    for sc in scenes:
        tgt = sc["segment_idx"]
        for q in sc["queries"]:
            rec = {"query_id": q["query_id"], "query_type": q["type"],
                   "query": q["text"], "scene_id": sc["scene_id"],
                   "target_segment": tgt, "target_start": sc["start"],
                   "target_end": sc["end"], "arms": {}}
            for arm in ARMS:
                res = m5_search.search(q["text"], idx_by_arm[arm], a.alpha, cfgs[arm])
                pos = {r.idx: i + 1 for i, r in enumerate(res)}
                sc_by_idx = {r.idx: r.score for r in res}
                rec["arms"][arm] = {
                    "target_rank": pos.get(tgt),
                    "target_score": round(sc_by_idx.get(tgt, float("nan")), 6),
                    "top1_segment": res[0].idx,
                    "top1_score": round(res[0].score, 6),
                    "top1_start": res[0].start,
                    "top3": [{"rank": i + 1, "idx": r.idx, "start": r.start,
                              "end": r.end, "score": round(r.score, 6)}
                             for i, r in enumerate(res[:3])],
                    "n_ranked": len(res),
                }
            rows.append(rec)

    hit = {arm: sum(1 for r in rows if r["arms"][arm]["target_rank"] == 1) for arm in ARMS}
    out = {
        "step": "STEP6_retrieval_numbers_only",
        "note": "해석 없음. 캡션 텍스트·프레임은 STEP 7에서 연다.",
        "first_outcome_access_after_plan_freeze": True,
        "outcome_access_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_head_at_outcome_access": git_head(),
        "plan_commit": "31b5b02", "amendment_commit": "931b8ac",
        "comparability_audit_commit": "84ff245",
        "video_id": V, "n_segments": n_seg,
        "view": "caption-only" if a.alpha == 0.0 else ("fusion alpha=%.2f" % a.alpha),
        "alpha": a.alpha,
        "alpha_sweep": False,
        "frozen_queries_sha256": plan["frozen_queries_sha256"],
        "frozen_scenes_sha256": plan["frozen_scenes_sha256"],
        "arm_models": {arm: cfgs[arm]["caption_model"] for arm in ARMS},
        "illustrative_top1_hit_count": hit,
        "illustrative_top1_hit_count_caveat": (
            "한 영상의 5개 장면, 15개 illustrative query에서 나온 one-video "
            "qualitative case-study count다. 일반적인 모델 정확도·superiority "
            "estimate·benchmark·유의성 결과가 아니다."),
        "n_queries": len(rows),
        "results": rows,
    }
    dst = Path(a.out) if a.out else (
        RD / ("step6_retrieval_alpha%s.json" % ("0" if a.alpha == 0.0 else str(a.alpha))))
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote %s" % dst)
    print("queries: %d · segments: %d · alpha=%.2f" % (len(rows), n_seg, a.alpha))
    print("illustrative top-1 hit count: 3B %d/%d · 4B %d/%d"
          % (hit["3b"], len(rows), hit["4b"], len(rows)))
    for r in rows:
        print("  %-12s tgt=%-3d  3B rank %-4s top1 %-3d | 4B rank %-4s top1 %-3d"
              % (r["query_id"], r["target_segment"],
                 r["arms"]["3b"]["target_rank"], r["arms"]["3b"]["top1_segment"],
                 r["arms"]["4b"]["target_rank"], r["arms"]["4b"]["top1_segment"]))


if __name__ == "__main__":
    main()
