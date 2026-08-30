"""경계 pass caption-only ablation — 자막 입력만 제거하고 나머지를 고정한다.

사전등록: `docs/finalization/M8_HIER_BOUNDARY_ABLATION_PREREG_2026-08-29.md`

```
성격   within-video causal diagnostic / ablation
아님   성능 실험 · acceptance · 공식 M8 판정
```

**PASS 1(경계)만 돈다.** describe·major·narration을 부르지 않는다 — 조작 대상은
경계 선택이고, 나머지를 같이 돌리면 무엇이 움직였는지 못 가른다.

동결: 모델 · 청킹 · `_ATOMIC_BOUNDARY_RULES` · 파서 · greedy.
바뀌는 것: `_fmt_seg`가 만드는 한 줄에서 자막 필드가 빠지고 머리말이 그에 맞춰 바뀐다.

사용:
    python scripts/m8_hier_boundary_ablation.py --config config_server.yaml \
        --video-id wonyi_geoje
"""
import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
import m8_hier as H                                                 # noqa: E402
import m8_report                                                    # noqa: E402
from m8_hier_prototype import chunks                                # noqa: E402

RUNDIR = ROOT / "runs/m8_hier"
RUN_KIND = "m8_hier_boundary_ablation"


def run(segments: list, llm, size: int, overlap: int, save=None) -> dict:
    """청크마다 경계만 고른다. **호출 직후 raw를 먼저 남기고** 그 다음 parse한다."""
    raw, per_chunk = [], []
    bounds = set()

    def flush():
        if save:
            save({"raw": raw, "per_chunk": per_chunk,
                  "boundaries": sorted(bounds)})

    for ch in chunks(segments, size, overlap):
        lo, hi = ch[0]["idx"], ch[-1]["idx"]
        r = llm(H.build_atomic_boundary_prompt(ch, caption_only=True))
        raw.append({"lo": lo, "hi": hi, "raw": r})
        flush()
        got = [b for b in H.parse_boundaries(r) if lo <= b <= hi]
        bounds |= set(got)
        per_chunk.append({"lo": lo, "hi": hi, "n": len(got), "boundaries": got,
                          "steps": [got[i + 1] - got[i]
                                    for i in range(len(got) - 1)]})
        flush()
    return {"raw": raw, "per_chunk": per_chunk, "boundaries": sorted(bounds)}


def spans_diagnostics(boundaries: list, n: int) -> dict:
    """사전등록한 지표만 계산한다. 새 지표를 여기서 만들지 않는다."""
    sp = H.build_atomic_spans(boundaries, n)
    lens = sorted(a["end_seg"] - a["start_seg"] + 1 for a in sp)
    q = lambda p: lens[int(round(p * (len(lens) - 1)))]              # noqa: E731
    return {"n_atomic": len(sp), "lengths": lens,
            "n_1seg": sum(1 for x in lens if x == 1),
            "n_le2seg": sum(1 for x in lens if x <= 2),
            "median": q(0.5), "p25": q(0.25), "p75": q(0.75),
            "mean": round(sum(lens) / len(lens), 2)}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--out", default=str(RUNDIR))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))

    wdir = Path(common.work_dir(cfg, a.video_id))
    doc = common.load_segments(wdir / "segments.json",
                               require=["subtitle", "caption"],
                               seg_len=cfg["seg_len_sec"])
    segs = doc["segments"]

    from llm import make_llm
    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))

    out = Path(a.out) / RUN_KIND
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{a.video_id}.json"
    assert "report.json" not in p.name, "공식 산출물 경로에 쓰지 않는다"

    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                             capture_output=True, text=True,
                             check=True).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        sha = "unknown"

    base = {"video_id": a.video_id, "schema": H.SCHEMA, "run_kind": RUN_KIND,
            "arm": "caption_only", "n_segments": len(segs), "commit": sha,
            "prereg": "docs/finalization/"
                      "M8_HIER_BOUNDARY_ABLATION_PREREG_2026-08-29.md"}
    ckpt = out / f"{a.video_id}.checkpoint.json"
    res = run(segs, llm, cfg["map_chunk_size"], cfg["map_chunk_overlap"],
              save=lambda st: common.atomic_write_json(ckpt, {**base,
                                                              "checkpoint": st}))
    res["diagnostics"] = spans_diagnostics(res["boundaries"], len(segs))
    common.atomic_write_json(
        p, {**base, **res, "provenance": m8_report.report_provenance(llm, cfg)})

    d = res["diagnostics"]
    print(f"{a.video_id} [caption_only] commit {sha[:7]}")
    print(f"청크 {len(res['per_chunk'])} · 경계 {len(res['boundaries'])} · "
          f"Atomic {d['n_atomic']} · 1구간 {d['n_1seg']} · ≤2구간 {d['n_le2seg']}")
    print(f"길이 median {d['median']} · p25 {d['p25']} · p75 {d['p75']} · "
          f"mean {d['mean']}")
    for c in res["per_chunk"]:
        print(f"  chunk {c['lo']}~{c['hi']}  경계 {c['n']}  간격 {c['steps']}")
    print(f"산출물: {p}")
    print(json.dumps({"boundaries": res["boundaries"]}, ensure_ascii=False))
    print("채점하지 않는다 — 서술·major pass를 돌리지 않았다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
