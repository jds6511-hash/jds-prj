"""Boundary-Content Split prototype v0 — 실행기.

규격: `docs/finalization/BCS_PROTOTYPE_SPEC_2026-08-29.md`

```
PASS 1  caption만 보고 Episode 경계 선택        (LLM · 청크당 1회)
PASS 2  span 구성 · 근거 앵커                   (코드)
PASS 3  Episode 내용 — caption + 사용가능 STT    (LLM · Episode당 1회)
PASS 4  렌더                                    (코드)
```

**공식 M8과 다른 산출물이다.** `work/<vid>/report.json`에 쓰지 않는다.
채점하지 않는다 — GT·C1/C2/C3 없음. degeneracy는 탐지만 하고 보정하지 않는다.

**LLM 호출 직후 raw를 먼저 디스크에 남긴다** — parse/validate 실패가 저장보다
앞에 오면 프로세스가 죽었을 때 원인을 못 밝힌다(2026-08-29 사고 2건).

사용:
    python scripts/bcs_prototype.py --config config_server.yaml \
        --video-id m8c2_3I7oGwk6EaQ
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import bcs as B                                                     # noqa: E402
import common                                                       # noqa: E402
import m8_report                                                    # noqa: E402
from m8_hier_prototype import chunks                                # noqa: E402

RUNDIR = ROOT / "runs/bcs"


def generate(segments: list, llm, size: int, overlap: int, save=None) -> dict:
    n = len(segments)
    by_idx = {s["idx"]: s for s in segments}
    raw = {"boundary": [], "content": []}
    state = {"stage": "boundary", "raw": raw}

    def flush():
        if save:
            save(state)

    # PASS 1 — caption만. 청크가 겹치므로 합집합.
    bounds, chunk_diag = set(), []
    for ch in chunks(segments, size, overlap):
        lo, hi = ch[0]["idx"], ch[-1]["idx"]
        r = llm(B.build_boundary_prompt(ch))
        raw["boundary"].append({"lo": lo, "hi": hi, "raw": r})
        flush()
        got = [b for b in B.parse_boundaries(r) if lo <= b <= hi]
        bounds |= set(got)
        chunk_diag.append({"lo": lo, "hi": hi, "n": len(got),
                           "boundaries": got,
                           "status": B.boundary_output_status(got)})
        flush()

    # PASS 2 — 코드가 span을 만든다. degenerate여도 자르지 않는다.
    eps = B.episode_spans(sorted(bounds), n)
    state.update(stage="content", episodes=eps, chunk_diag=chunk_diag)
    flush()

    # PASS 3 — Episode당 한 번. 사용 가능한 STT만 들어간다.
    out = []
    for e in eps:
        span = [by_idx[i] for i in range(e["start_seg"], e["end_seg"] + 1)]
        r = llm(B.build_content_prompt(span))
        raw["content"].append({"episode_id": e["episode_id"], "raw": r})
        flush()
        c = B.verify_content(B.parse_content(r), e, span)
        out.append({**e, **c})
        state["episodes"] = out + eps[len(out):]
        flush()

    state["stage"] = "complete"
    flush()
    return {"episodes": out, "chunk_diag": chunk_diag, "raw": raw,
            "overview": B.compose_overview(out)}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--run-kind", default="bcs_v0")
    ap.add_argument("--out", default=str(RUNDIR))
    ap.add_argument("--commit", default=None)
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))

    wdir = Path(common.work_dir(cfg, a.video_id))
    doc = common.load_segments(wdir / "segments.json",
                               require=["subtitle", "caption"],
                               seg_len=cfg["seg_len_sec"])
    segs = B.sanitize_stt(doc["segments"])
    stt_counts = {}
    for s in segs:
        stt_counts[s["stt_status"]] = stt_counts.get(s["stt_status"], 0) + 1

    from llm import make_llm
    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))

    out_dir = Path(a.out) / a.run_kind
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{a.video_id}.json"
    assert "report.json" not in p.name, "공식 산출물 경로에 쓰지 않는다"

    base = {"video_id": a.video_id, "schema": B.SCHEMA, "run_kind": a.run_kind,
            "n_segments": len(segs), "commit": a.commit,
            "stt_status_counts": stt_counts,
            "spec": "docs/finalization/BCS_PROTOTYPE_SPEC_2026-08-29.md"}
    ckpt = out_dir / f"{a.video_id}.checkpoint.json"
    res = generate(segs, llm, cfg["map_chunk_size"], cfg["map_chunk_overlap"],
                   save=lambda st: common.atomic_write_json(
                       ckpt, {**base, "checkpoint": st}))

    out = {**base, **{k: v for k, v in res.items() if k != "raw"}}
    failures = B.validate(out, a.video_id)
    out["prototype_status"] = "OK" if not failures else "INVALID"
    out["validation"] = {"passed": not failures, "failures": failures}
    out["provenance"] = m8_report.report_provenance(llm, cfg)
    out["raw"] = res["raw"]
    common.atomic_write_json(p, out)

    if not failures:
        (out_dir / f"{a.video_id}.md").write_text(
            B.render(out, seg_len=cfg["seg_len_sec"]), encoding="utf-8")

    eps = res["episodes"]
    lens = [e["end_seg"] - e["start_seg"] + 1 for e in eps]
    dropped = [e["episode_id"] for e in eps if e.get("dropped")]
    notes = sum(1 for e in eps if (e.get("dialogue_note") or "").strip())
    print(f"{a.video_id}  구간 {len(segs)}  Episode {len(eps)}")
    print(f"STT 상태: {json.dumps(stt_counts, ensure_ascii=False)}")
    print(f"Episode 길이(구간): {sorted(lens)}")
    print(f"1구간 {sum(1 for x in lens if x == 1)} · "
          f"≤2구간 {sum(1 for x in lens if x <= 2)}")
    print(f"dialogue_note {notes}건 · 근거 미달로 버림 {len(dropped)}건 {dropped}")
    for c in res["chunk_diag"]:
        print(f"  chunk {c['lo']}~{c['hi']}  경계 {c['n']}  {c['status']}")
    for e in eps:
        t = e["start_seg"] * cfg["seg_len_sec"]
        print(f"  {e['episode_id']}  {t // 60:02d}:{t % 60:02d}  "
              f"{e['summary'] or '(요약 없음)'}")
        if (e.get("dialogue_note") or "").strip():
            print(f"          대화: {e['dialogue_note']}  {e['stt_cites']}")
    print(f"상태: {out['prototype_status']}" + (f" — {failures}" if failures else ""))
    print(f"산출물: {p}")
    print("채점하지 않는다 — GT·C1/C2/C3 대조 없음")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
