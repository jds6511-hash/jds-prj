"""M8 hierarchical prototype 생성 — Observation → Atomic → Major → AAR.

규격: `docs/finalization/M8_HIER_PROTOTYPE_SPEC_2026-08-29.md`.

**제품 설계 prototype이다.** 채점하지 않고 judge도 없다. C1/C2/C3·Event Recall·
GT 대조를 계산하지 않으며 GT를 생성 입력으로 쓰지 않는다.

공식 산출물을 건드리지 않는다 — `work/<vid>/report.json`에 절대 쓰지 않고
prototype run 디렉터리에만 쓴다.

사용:
    python scripts/m8_hier_prototype.py --config config_server.yaml \
        --video-id m8c2_3I7oGwk6EaQ --run-kind m8_hier_prototype_canary
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
import m8_hier as H                                                 # noqa: E402
import m8_report                                                    # noqa: E402

RUNDIR = ROOT / "runs/m8_hier"


def chunks(segments: list, size: int, overlap: int):
    """생성기와 같은 경계 — stride = size - overlap, 마지막 청크에서 종료."""
    start = 0
    while start < len(segments):
        yield segments[start:start + size]
        if start + size >= len(segments):
            break
        start += size - overlap


def generate(segments: list, llm, size: int, overlap: int) -> dict:
    """3 pass. LLM은 의미만 정하고 시각·근거·포함관계는 코드가 정한다."""
    raw_atomic, atomics, rejected = [], [], []
    for ch in chunks(segments, size, overlap):
        raw = llm(H.build_atomic_prompt(ch))
        raw_atomic.append(raw)
        kept, bad = H.validate_atomic(H.parse_atomic(raw), ch)
        atomics += kept
        rejected += [{**b, "chunk": len(raw_atomic) - 1} for b in bad]
    atomics, n_dup = H.dedupe_atomic(atomics)
    atomics = H.assign_ids(atomics)

    raw_major = llm(H.build_major_prompt(atomics)) if atomics else ""
    majors, group_diag = H.compose_major(H.parse_major(raw_major), atomics) \
        if atomics else ([], {"ok": False, "reason": "no_atomic", "n_groups": 0})

    raw_overview = llm(H.build_overview_prompt(majors)) if majors else ""
    overview = H.compose_overview(raw_overview, majors) if majors else None

    return {"atomic_events": atomics, "major_events": majors,
            "overview": overview,
            "diagnostics": {"n_chunks": len(raw_atomic),
                            "n_atomic_rejected": len(rejected),
                            "rejection_reasons": _count(rejected),
                            "n_duplicate_removed": n_dup,
                            "grouping": group_diag},
            "rejected_atomic": rejected,
            "raw": {"atomic": raw_atomic, "major": raw_major,
                    "overview": raw_overview}}


def _count(rows: list) -> dict:
    out = {}
    for r in rows:
        out[r["reason"]] = out.get(r["reason"], 0) + 1
    return dict(sorted(out.items()))


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--run-kind", default="m8_hier_prototype_canary")
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

    res = generate(segs, llm, cfg["map_chunk_size"], cfg["map_chunk_overlap"])
    out_doc = {"video_id": a.video_id, "schema": H.SCHEMA,
               "run_kind": a.run_kind, "n_segments": len(segs),
               "provenance": m8_report.report_provenance(llm, cfg),
               **{k: v for k, v in res.items() if k != "raw"}}
    failures = H.validate_document(out_doc, a.video_id)
    out_doc["validation"] = {"passed": not failures, "failures": failures}
    out_doc["raw"] = res["raw"]

    out = Path(a.out) / a.run_kind
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{a.video_id}.json"
    assert "report.json" not in p.name, "공식 산출물 경로에 쓰지 않는다"
    common.atomic_write_json(p, out_doc)

    d = res["diagnostics"]
    print(f"{a.video_id}: 청크 {d['n_chunks']} · Atomic {len(res['atomic_events'])} "
          f"(거부 {d['n_atomic_rejected']} {d['rejection_reasons']} · "
          f"중복제거 {d['n_duplicate_removed']}) · Major {len(res['major_events'])}")
    print(f"grouping: {d['grouping']}")
    print(f"overview source: {(res['overview'] or {}).get('source')}")
    print(f"검증: {'PASS' if not failures else 'FAIL ' + str(failures)}")
    print(f"산출물: {p}")
    print("채점하지 않는다 — C1/C2/C3·GT 대조 없음")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
