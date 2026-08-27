"""baseline(공식) ↔ redesign(개발) 비교 — **개발 점수다.**

같은 8편·같은 동결 GT로 두 산출물을 같은 진단으로 잰다.

```
baseline   work/<vid>/report.json          공식 실행 m8_official_0827 (불변)
redesign   results/m8_redesign_<id>/report_dev_<vid>.json
```

**여기서 나오는 C1/C2/C3는 확증이 아니다.** 이 8편은 공식 결과를 본 순간 소비된
확증 표본이고, 값이 좋아져도 "통과했다"고 쓸 수 없다. 그래서 필드 이름에
`dev_`를 붙이고 `is_confirmation: false`를 박는다.

사용:
    python scripts/m8_redesign_compare.py --run-id r1
"""
import argparse
import io
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                      # noqa: E402
import m8_c1                                                       # noqa: E402
import m8_metrics as M                                             # noqa: E402
import m8_failure_analysis as FA                                   # noqa: E402
from event_inventory_kit import OUT, load_reference                 # noqa: E402
from m8_gates import panel_videos                                   # noqa: E402

SHORT_GT_MAX = 10     # 진단 bucket. 공식 실행에서 미매칭 GT 길이 median이 6구간이었다


def metrics(rep: dict, refs: list, n_segments: int) -> dict:
    gens = FA.gen_events(rep)
    ev = FA.event_rows("_", refs, gens)
    gr = FA.generated_rows("_", refs, gens)
    ch = FA.chunk_rows("_", rep)
    short = [r for r in ev if r["gt_len"] <= SHORT_GT_MAX]
    st = M.structural_summary(rep, n_segments)
    f = m8_c1.inspect_video(rep)
    return {
        "n_reference_events": len(refs),
        "n_sentences": len(rep.get("sentences") or []),
        "n_generated_events": len(gens),
        "raw_events_total": sum(c["raw_events"] for c in ch),
        "chunks": len(ch),
        "raw_events_per_chunk_median": (
            round(statistics.median([c["raw_events"] for c in ch]), 2) if ch else None),
        "unmatched_gt": sum(1 for r in ev if not r["matched"]),
        "unmatched_gt_short": sum(1 for r in short if not r["matched"]),
        "n_gt_short": len(short),
        "unmatched_generated": sum(1 for r in gr if not r["matched"]),
        "alignment": M.event_temporal_alignment(refs, gens),
        "theta_recall": M.temporal_event_recall(refs, gens),
        "compression": M.compression(len(rep.get("sentences") or []), len(refs)),
        "rejections": st["rejected_events"],
        "rejection_reasons": st["rejection_reasons"],
        "zero_event_chunks": sum(1 for c in ch if c["zero_event_chunk"]),
        "chunk_retries": len(rep.get("chunk_retries") or []),
        "chunk_splits": len(rep.get("chunk_splits") or []),
        "splits_recovered": sum(1 for s in (rep.get("chunk_splits") or [])
                                if s.get("recovered")),
        "span_coverage": M.timeline_span_coverage(gens, n_segments),
        "alignment_types": {t: sum(1 for r in ev if r["alignment_type"] == t)
                            for t in M.EVENT_ALIGNMENT_TYPES
                            if any(r["alignment_type"] == t for r in ev)},
        "c1_status": m8_c1.video_status(f),
        "c1_kind_status": {k: f[k]["status"] for k in m8_c1.C1_KINDS},
        "non_korean_event_titles": sum(
            1 for g in gens if g["event"] and not m8_c1._HANGUL.search(g["event"])),
        "iou_distribution": FA.iou_distribution(ev),
    }


def panel_dev_scores(rows: dict) -> dict:
    """개발 점수. **관문 판정이 아니다** — 이름에 dev를 박는다."""
    al = [v["alignment"] for v in rows.values() if v["alignment"] is not None]
    cm = [v["compression"] for v in rows.values() if v["compression"] is not None]
    st = [v["c1_status"] for v in rows.values()]
    return {"is_confirmation": False,
            "dev_c1_present_videos": st.count("PRESENT"),
            "dev_c1_unclear_videos": st.count("UNCLEAR"),
            "dev_c2_median_alignment": round(statistics.median(al), 4) if al else None,
            "dev_c3_max_compression": round(max(cm), 4) if cm else None,
            "note": ("소비된 패널의 개발 점수다. 확증이 아니며 통과/미달로 "
                     "표현하지 않는다.")}


def compare(cfg, run_dir, videos=None) -> dict:
    videos = videos or panel_videos()
    base, dev = {}, {}
    for v in videos:
        wdir = Path(common.work_dir(cfg, v))
        refs = load_reference(v, csv_path=OUT / f"{v}.csv")
        n = len(json.loads((wdir / "segments.json").read_text(
            encoding="utf-8"))["segments"])
        b = json.loads((wdir / "report.json").read_text(encoding="utf-8"))
        base[v] = metrics(b, refs, n)
        p = Path(run_dir) / f"report_dev_{v}.json"
        if p.is_file():
            dev[v] = metrics(json.loads(p.read_text(encoding="utf-8")), refs, n)
    return {"record": "M8 REDESIGN ROUND 1 — baseline vs development",
            "date": "2026-08-27", "is_confirmation": False,
            "baseline": {"source": "work/<vid>/report.json (공식 m8_official_0827)",
                         "per_video": base},
            "redesign_dev": {"source": str(run_dir), "per_video": dev},
            "baseline_panel_dev_scores": panel_dev_scores(base),
            "redesign_panel_dev_scores": panel_dev_scores(dev) if dev else None,
            "official_verdict_unchanged": True}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--run-id", default="r1")
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--out",
                    default="docs/finalization/m8_redesign_r1_compare_2026-08-27.json")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    run_dir = (Path(a.run_dir) if a.run_dir
               else ROOT / "results" / f"m8_redesign_{a.run_id}")
    d = compare(cfg, run_dir)
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"작성: {a.out}")
    b, r = d["baseline_panel_dev_scores"], d["redesign_panel_dev_scores"]
    if r:
        print(f"{'지표':<30}{'baseline':>10}{'redesign':>10}")
        for k in ("dev_c1_present_videos", "dev_c2_median_alignment",
                  "dev_c3_max_compression"):
            print(f"{k:<30}{str(b[k]):>10}{str(r[k]):>10}")
    print("개발 점수다 — 확증이 아니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
