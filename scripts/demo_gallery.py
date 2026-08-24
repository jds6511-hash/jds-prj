"""데모 시나리오·성공/실패 gallery 생성기 — **dev 전용, descriptive**.

발표에서 보여줄 질의와, 시스템이 잘하는 것·어려워하는 것을 실제 실행 결과로 정리한다.

```
경계   dev split 질의·영상만. test 영상·질의는 fail-closed로 거부한다
성격   descriptive. 새 formal inference가 아니고 평가 결과로 주장하지 않는다
근거   현행 배포 구성(3B/P0/4bit · KURE-v1 · α=0.5)으로 실제 검색한 출력
```

"root cause 확정"을 쓰지 않는다 — 관측된 동작과 가능한 설명까지만 적는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
from demo import DEPLOYMENT_ALPHA, TEST_SPLIT_VIDEOS, preflight     # noqa: E402

DEV_SPLIT = "dev"
QUERY_TYPES = ("장면형", "자막형", "복합형")


class GalleryError(RuntimeError):
    pass


def load_dev_queries(path, video_ids=None) -> list:
    rows = [json.loads(l) for l in
            Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for r in rows:
        if r.get("split") != DEV_SPLIT:
            continue
        if r["video_id"] in TEST_SPLIT_VIDEOS:
            raise GalleryError(
                f"{r['query_id']}: dev로 표기됐는데 영상이 test split이다 "
                f"({r['video_id']}) — 질의셋을 확인해라")
        if video_ids and r["video_id"] not in video_ids:
            continue
        out.append(r)
    if not out:
        raise GalleryError("dev 질의가 없다")
    return out


def gt_rank(results, gt_seg_idx) -> int | None:
    """정답 구간이 몇 위에 있었나. 없으면 None."""
    gt = set(gt_seg_idx or [])
    for i, r in enumerate(results, 1):
        if r.idx in gt:
            return i
    return None


def run_query(q: dict, index, cfg: dict, alpha: float, top_k: int = 5) -> dict:
    from m5_search import search
    results = search(q["text"], index, alpha, cfg)
    rank = gt_rank(results, q.get("gt_seg_idx"))
    top = results[:top_k]
    segs = index.segments
    return {
        "query_id": q["query_id"], "video_id": q["video_id"],
        "type": q.get("type"), "query": q["text"],
        "gt_seg_idx": q.get("gt_seg_idx"),
        "gt_time": {"start": q.get("gt_start"), "end": q.get("gt_end")},
        "gt_rank": rank,
        "results": [{"rank": i, "idx": r.idx, "start": int(r.start),
                     "end": int(r.end), "score": round(r.score, 4),
                     "is_gt": r.idx in set(q.get("gt_seg_idx") or []),
                     "subtitle": segs[r.idx].get("subtitle", ""),
                     "caption": segs[r.idx].get("caption", "")}
                    for i, r in enumerate(top, 1)],
    }


def pick_round_robin(rows: list, video_ids: list, n: int) -> list:
    """영상을 돌아가며 앞에서부터 고른다 — 한 영상에 사례가 몰리지 않게.

    각 영상 안에서는 질의셋 순서를 지킨다. **결과를 보고 고르지 않는다.**
    """
    per_video = {v: [q for q in rows if q["video_id"] == v] for v in video_ids}
    out, i = [], 0
    while len(out) < n and any(per_video.values()):
        v = video_ids[i % len(video_ids)]
        if per_video[v]:
            out.append(per_video[v].pop(0))
        i += 1
        if i > len(video_ids) * (n + len(rows)):        # 안전 정지
            break
    return out[:n]


def classify(case: dict) -> str:
    """성공/부분/실패 — 발표 분류용 기술 라벨이고 평가 지표가 아니다."""
    r = case["gt_rank"]
    if r == 1:
        return "성공(1위)"
    if r is not None and r <= 5:
        return f"부분({r}위)"
    return "어려움(5위 밖)"


def build(cfg: dict, queries_path, video_ids: list, alpha: float,
          per_type: int = 3, top_k: int = 5) -> dict:
    from m5_search import VideoIndex
    for vid in video_ids:
        if vid in TEST_SPLIT_VIDEOS:
            raise GalleryError(f"{vid}는 test split 영상이다 — gallery에 쓰지 않는다")
        preflight(cfg, vid, alpha)          # 배포 구성·인덱스 정합 fail-closed

    qs = load_dev_queries(queries_path, video_ids)
    indexes = {v: VideoIndex.load(cfg, v) for v in video_ids}

    cases = []
    for t in QUERY_TYPES:
        for q in pick_round_robin([q for q in qs if q.get("type") == t],
                                  video_ids, per_type):
            c = run_query(q, indexes[q["video_id"]], cfg, alpha, top_k)
            c["outcome"] = classify(c)
            cases.append(c)

    by_type = {}
    for t in QUERY_TYPES:
        sub = [c for c in cases if c["type"] == t]
        by_type[t] = {"n": len(sub),
                      "outcomes": [c["outcome"] for c in sub]}

    return {
        "probe": "demo_gallery",
        "split": DEV_SPLIT,
        "videos": list(video_ids),
        "deployment": {"caption_model": cfg["caption_model"],
                       "vlm_4bit": cfg["vlm_4bit"],
                       "embed_model": cfg["embed_model"], "alpha": alpha},
        "n_cases": len(cases), "per_type": per_type, "top_k": top_k,
        "by_type": by_type, "cases": cases,
        "claim_grade": ("descriptive demonstration이다. 새 formal inference가 "
                        "아니고 평가 결과·벤치마크로 주장하지 않는다"),
        "selection_note": ("질의는 유형별로 dev 질의셋 순서대로 앞에서 골랐다 — "
                           "결과를 보고 고르지 않았다"),
        "causal_note": ("관측된 동작과 가능한 설명까지만 적는다. root cause를 "
                        "확정하지 않는다"),
        "test_split_used": False,
        "m6_evaluate_invoked": False,
    }


def to_markdown(doc: dict) -> str:
    d = doc["deployment"]
    L = ["# 데모 시나리오 · 성공/실패 gallery (dev 전용)", "",
         f"- 배포 구성: `{d['caption_model']}` 4bit · `{d['embed_model']}` · "
         f"α={d['alpha']}",
         f"- 영상 {len(doc['videos'])}편 · 사례 {doc['n_cases']}건 "
         f"(유형별 {doc['per_type']}건, Top-{doc['top_k']} 표시)",
         f"- {doc['claim_grade']}",
         f"- {doc['selection_note']}",
         f"- {doc['causal_note']}", ""]
    for t in QUERY_TYPES:
        L += [f"## {t}", ""]
        for c in [c for c in doc["cases"] if c["type"] == t]:
            g = c["gt_time"]
            L += [f"### {c['query_id']} — {c['outcome']}", "",
                  f"**질의** {c['query']}", "",
                  f"- 영상 `{c['video_id']}`",
                  f"- 정답 구간 {g['start']}s~{g['end']}s "
                  f"(seg {c['gt_seg_idx']})",
                  f"- 정답 순위 {c['gt_rank'] if c['gt_rank'] else '5위 밖'}", "",
                  "| 순위 | 구간 | 점수 | 정답 | 발화 | 화면 |",
                  "|---|---|---|---|---|---|"]
            for r in c["results"]:
                sub = (r["subtitle"] or "없음").replace("|", "／")[:40]
                cap = (r["caption"] or "없음").replace("|", "／")[:60]
                L.append(f"| {r['rank']} | {r['start']}~{r['end']}s | "
                         f"{r['score']:.3f} | {'O' if r['is_gt'] else ''} | "
                         f"{sub} | {cap} |")
            L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="dev 전용 데모·gallery 생성")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--queries", default="data/queries/queries.jsonl")
    ap.add_argument("--video-id", action="append", required=True)
    ap.add_argument("--alpha", type=float, default=DEPLOYMENT_ALPHA)
    ap.add_argument("--per-type", type=int, default=3)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--out-json")
    ap.add_argument("--out-md")
    a = ap.parse_args()

    cfg = common.load_config(a.config)
    try:
        doc = build(cfg, a.queries, a.video_id, a.alpha, a.per_type, a.top_k)
    except GalleryError as e:
        print(f"gallery 생성 거부 — {e}", file=sys.stderr)
        return 1
    print(f"사례 {doc['n_cases']}건 · " +
          " · ".join(f"{t} {doc['by_type'][t]['outcomes']}"
                     for t in QUERY_TYPES))
    if a.out_json:
        Path(a.out_json).write_text(json.dumps(doc, ensure_ascii=False,
                                               indent=2), encoding="utf-8")
        print(f"-> {a.out_json}")
    if a.out_md:
        Path(a.out_md).write_text(to_markdown(doc), encoding="utf-8")
        print(f"-> {a.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
