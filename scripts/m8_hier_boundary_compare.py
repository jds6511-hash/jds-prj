"""full-input vs caption-only 경계 대조 — 사전등록한 지표만 계산한다.

사전등록: `docs/finalization/M8_HIER_BOUNDARY_ABLATION_PREREG_2026-08-29.md` §5

LLM을 부르지 않는다. 기준값(full input)은 **저장된 raw를 같은 파서로 재파싱**해
얻으므로 재실행이 없고 결정적이다.

`자막 변화 지점의 경계 소실`은 계산하지 않는다 — geoje에서 자막만 바뀌는 위치가
0건이라 기저율과 구분되지 않는다(사전등록 §3-1).

사용:
    python scripts/m8_hier_boundary_compare.py --video-id wonyi_geoje
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import m8_hier as H                                                 # noqa: E402

RUNDIR = ROOT / "runs/m8_hier"


def chunk_ranges(n: int, size: int, overlap: int) -> list:
    out, start = [], 0
    while start < n:
        out.append((start, min(start + size, n) - 1))
        if start + size >= n:
            break
        start += size - overlap
    return out


def parse_full_raw(doc: dict, size: int, overlap: int) -> list:
    """저장된 full-input raw를 같은 파서로 재파싱한다 — 모델이 고른 집합 그대로."""
    raws = ((doc.get("raw") or {}).get("atomic_boundaries")
            or ((doc.get("checkpoint") or {}).get("raw") or {})
            .get("atomic_boundaries") or [])
    rng = chunk_ranges(doc["n_segments"], size, overlap)
    if len(raws) != len(rng):
        raise SystemExit(f"청크 수 불일치 raw {len(raws)} vs 범위 {len(rng)}")
    out = []
    for (lo, hi), r in zip(rng, raws):
        got = [b for b in H.parse_boundaries(r) if lo <= b <= hi]
        out.append({"lo": lo, "hi": hi, "boundaries": got,
                    "steps": [got[i + 1] - got[i] for i in range(len(got) - 1)]})
    return out


def stats(boundaries, n) -> dict:
    sp = H.build_atomic_spans(sorted(set(boundaries)), n)
    lens = sorted(a["end_seg"] - a["start_seg"] + 1 for a in sp)
    q = lambda p: lens[int(round(p * (len(lens) - 1)))]              # noqa: E731
    return {"n_atomic": len(sp), "n_1seg": sum(1 for x in lens if x == 1),
            "n_le2seg": sum(1 for x in lens if x <= 2),
            "median": q(0.5), "p25": q(0.25), "p75": q(0.75),
            "mean": round(sum(lens) / len(lens), 2)}


def runs_of_consecutive(b: list, min_len: int = 5) -> list:
    """연속 정수 군집 — 열거 degeneracy(H2)의 관측 가능한 흔적."""
    b, out, run = sorted(b), [], []
    for x in b:
        if run and x == run[-1] + 1:
            run.append(x)
        else:
            if len(run) >= min_len:
                out.append([run[0], run[-1], len(run)])
            run = [x]
    if len(run) >= min_len:
        out.append([run[0], run[-1], len(run)])
    return out


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", default="wonyi_geoje")
    ap.add_argument("--full", default=None)
    ap.add_argument("--ablation", default=None)
    ap.add_argument("--chunk-size", type=int, default=60)
    ap.add_argument("--chunk-overlap", type=int, default=5)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    fp = Path(a.full or RUNDIR / "m8_hier_prototype_geoje" / f"{a.video_id}.json")
    cp = Path(a.ablation or RUNDIR / "m8_hier_boundary_ablation"
              / f"{a.video_id}.json")
    full = json.loads(fp.read_text(encoding="utf-8"))
    cap = json.loads(cp.read_text(encoding="utf-8"))
    n = full["n_segments"]
    if cap["n_segments"] != n:
        raise SystemExit("구간 수 불일치 — 같은 영상이 아니다")

    fchunks = parse_full_raw(full, a.chunk_size, a.chunk_overlap)
    fb = sorted({b for c in fchunks for b in c["boundaries"]})
    cb = sorted(set(cap["boundaries"]))
    cchunks = cap["per_chunk"]

    res = {"video_id": a.video_id, "n_segments": n,
           "full_source": str(fp).replace("\\", "/"),
           "ablation_source": str(cp).replace("\\", "/"),
           "ablation_commit": cap.get("commit"),
           "full": {"boundaries": fb, "n_boundaries": len(fb), **stats(fb, n),
                    "per_chunk": [{"lo": c["lo"], "hi": c["hi"],
                                   "n": len(c["boundaries"]),
                                   "steps": c["steps"]} for c in fchunks],
                    "consecutive_runs": runs_of_consecutive(fb)},
           "caption_only": {"boundaries": cb, "n_boundaries": len(cb),
                            **stats(cb, n),
                            "per_chunk": [{"lo": c["lo"], "hi": c["hi"],
                                           "n": c["n"], "steps": c["steps"]}
                                          for c in cchunks],
                            "consecutive_runs": runs_of_consecutive(cb)},
           "overlap": {"shared": sorted(set(fb) & set(cb)),
                       "full_only": sorted(set(fb) - set(cb)),
                       "caption_only_only": sorted(set(cb) - set(fb))}}
    o = res["overlap"]
    res["overlap"]["counts"] = {"shared": len(o["shared"]),
                                "full_only": len(o["full_only"]),
                                "caption_only_only": len(o["caption_only_only"])}

    F, C = res["full"], res["caption_only"]
    print(f"{a.video_id}  n={n}  ablation commit {str(cap.get('commit'))[:7]}")
    print(f"{'항목':<24}{'full':>10}{'caption-only':>16}")
    for k, lab in [("n_boundaries", "모델 경계 수"), ("n_atomic", "Atomic count"),
                   ("n_1seg", "1-segment Atomic"), ("n_le2seg", "≤2-segment"),
                   ("median", "median 길이"), ("p25", "p25"), ("p75", "p75"),
                   ("mean", "mean")]:
        print(f"{lab:<24}{F[k]:>10}{C[k]:>16}")
    print("\n청크별 경계 수")
    for x, y in zip(F["per_chunk"], C["per_chunk"]):
        print(f"  {x['lo']:>3}~{x['hi']:<3}  full {x['n']:>3}   "
              f"caption-only {y['n']:>3}")
    print("\n연속 정수 군집(≥5)")
    print(f"  full         {F['consecutive_runs']}")
    print(f"  caption-only {C['consecutive_runs']}")
    print("\n경계 집합 대조")
    print(f"  shared            {len(o['shared'])}")
    print(f"  full-only         {len(o['full_only'])}")
    print(f"  caption-only-only {len(o['caption_only_only'])}")

    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print(f"\n산출물: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
