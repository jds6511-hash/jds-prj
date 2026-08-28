"""M8 hierarchical prototype v2 생성 — boundary selection 계약.

규격: `docs/finalization/M8_HIER_PROTOTYPE_SPEC_2026-08-29.md` + structural repair.

**제품 설계 prototype이다.** 채점하지 않고 judge도 없다. C1/C2/C3·Event Recall·
GT 대조를 계산하지 않으며 GT를 생성 입력으로 쓰지 않는다.

3 pass. LLM은 **경계만 고르고** 확정된 span에 제목·서술을 붙인다. span 구성·
겹침 방지·분할 보장·시각·근거 앵커·개요는 전부 코드가 한다.

**fallback을 만들지 않는다.** 구조가 무효면 `prototype_status = CANARY_INVALID`로
끝내고 최종 AAR을 렌더하지 않는다 — 무효 원본은 그대로 저장한다.

공식 산출물을 건드리지 않는다 — `work/<vid>/report.json`에 절대 쓰지 않는다.

사용:
    python scripts/m8_hier_prototype.py --config config_server.yaml \
        --video-id m8c2_3I7oGwk6EaQ --run-kind m8_hier_prototype_canary_v2
"""
import argparse
import io
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
    n = len(segments)
    by_idx = {s["idx"]: s for s in segments}
    raw = {"atomic_boundaries": [], "describe": [], "major": ""}

    # PASS 1 — 경계만 고른다. 청크가 겹치므로 합집합을 취한다.
    bounds = set()
    for ch in chunks(segments, size, overlap):
        r = llm(H.build_atomic_boundary_prompt(ch))
        raw["atomic_boundaries"].append(r)
        lo, hi = ch[0]["idx"], ch[-1]["idx"]
        bounds |= {b for b in H.parse_boundaries(r) if lo <= b <= hi}
    atomics = H.build_atomic_spans(sorted(bounds), n)

    # PASS 2 — 확정된 span에만 제목·서술. 여기서 시간 구조를 바꿀 수 없다.
    described = []
    for a in atomics:
        seg = [by_idx[i] for i in range(a["start_seg"], a["end_seg"] + 1)]
        r = llm(H.build_describe_prompt(seg))
        raw["describe"].append({"event_id": a["event_id"], "raw": r})
        described.append(H.with_evidence({**a, **H.parse_describe(r)}))

    # PASS 3 — Major 경계만 고른다.
    raw["major"] = llm(H.build_major_boundary_prompt(described))
    ids, titles = H.parse_major_starts(raw["major"])
    majors = H.build_major_spans(ids, titles, described)

    return {"atomic_events": described, "major_events": majors,
            "overview": H.compose_overview(majors),
            "diagnostics": {"n_chunks": len(raw["atomic_boundaries"]),
                            "n_boundaries": len(bounds),
                            "n_atomic": len(described),
                            "n_major": len(majors),
                            "atomic_spans_segments":
                                [a["end_seg"] - a["start_seg"] + 1
                                 for a in described],
                            "major_sizes": [len(m["subevents"]) for m in majors]},
            "raw": raw}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--run-kind", default="m8_hier_prototype_canary_v2")
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

    out = Path(a.out) / a.run_kind
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{a.video_id}.json"
    assert "report.json" not in p.name, "공식 산출물 경로에 쓰지 않는다"
    base = {"video_id": a.video_id, "schema": H.SCHEMA, "run_kind": a.run_kind,
            "n_segments": len(segs),
            "provenance": m8_report.report_provenance(llm, cfg)}

    try:
        res = generate(segs, llm, cfg["map_chunk_size"], cfg["map_chunk_overlap"])
    except H.HierInvalid as e:
        common.atomic_write_json(p, {**base, "prototype_status": "CANARY_INVALID",
                                     "invalid_reason": e.reason,
                                     "invalid_detail": e.detail})
        print(f"CANARY_INVALID — {e.reason}: {e.detail}")
        print(f"산출물(무효 기록): {p}")
        print("fallback을 만들지 않는다 — 최종 AAR을 렌더하지 않는다")
        return 2

    out_doc = {**base, **{k: v for k, v in res.items() if k != "raw"}}
    failures = H.validate_document(out_doc, a.video_id)
    out_doc["prototype_status"] = "CANARY_OK" if not failures else "CANARY_INVALID"
    out_doc["validation"] = {"passed": not failures, "failures": failures}
    out_doc["raw"] = res["raw"]
    common.atomic_write_json(p, out_doc)

    d = res["diagnostics"]
    print(f"{a.video_id}: 청크 {d['n_chunks']} · 경계 {d['n_boundaries']} · "
          f"Atomic {d['n_atomic']} · Major {d['n_major']}")
    print(f"Atomic 길이(구간): {d['atomic_spans_segments']}")
    print(f"Major 크기(하위 수): {d['major_sizes']}")
    print(f"상태: {out_doc['prototype_status']}"
          + (f" — {failures}" if failures else ""))
    print(f"산출물: {p}")
    print("채점하지 않는다 — C1/C2/C3·GT 대조 없음")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
