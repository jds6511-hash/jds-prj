"""M8 실패 분해 — **진단 전용.** 공식 판정을 다시 계산하지 않는다.

```
공식 결과   evaluation COMPLETE · acceptance FAIL (C1·C2·C3 전부)
이 도구     그 FAIL이 어디서 생겼는지 사건 단위로 분해한다
읽기만      report.json · FROZEN_*.json · 공식 result JSON — 어느 것도 쓰지 않는다
```

**성공 기준은 FAIL을 PASS로 설명하는 것이 아니다.** 재현 가능한 산출물과 기존 동결
taxonomy로 왜 FAIL했는지 구체적으로 말할 수 있는가다.

정렬 유형(`m8_metrics.EVENT_ALIGNMENT_TYPES`)은 **사람이 붙이도록 동결된 라벨**이다.
여기서는 그 이름에 기계 규칙을 붙여 자동 배정하는데, 그 규칙 자체는 사전등록에 없다 —
**post-hoc operationalization이고 진단 전용이다.** 관문에 쓰지 않는다.

`Redundancy`는 사전등록에 "같은 정답 사건을 여러 문장이 중복 서술한 비율" 한 줄뿐이고
비율의 분자·분모가 없다. 임의 정의를 만들지 않고 `DEFINITION_AMBIGUOUS`로 보고한 뒤,
다른 이름의 기계적 관측치만 낸다.

사용:
    python scripts/m8_failure_analysis.py
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
import m8_report                                                   # noqa: E402
from event_inventory_kit import OUT, load_reference                 # noqa: E402
from m8_gates import panel_videos                                   # noqa: E402

OFFICIAL = ROOT / "docs" / "finalization" / "m8_official_result_2026-08-27.json"
REASONABLE_IOU = 0.5      # 진단 bucket 경계. **관문 임계가 아니다**
WIDE_FACTOR = 2.0         # 생성 span이 GT span의 몇 배부터 너무 넓다고 볼지 (진단)

REDUNDANCY_STATUS = "DEFINITION_AMBIGUOUS"
REDUNDANCY_NOTE = (
    "사전등록 M8_구조변경_2026-08-16 §2-2는 Redundancy를 '같은 정답 사건을 여러 "
    "문장이 중복 서술한 비율'로만 적었고 분자·분모를 특정하지 않았다. 임의 정의를 "
    "만들지 않는다. 아래 gt_events_with_multiple_overlapping_generated는 그 자리를 "
    "대신하는 값이 아니라 **다른 이름의 기계적 관측치**이며 진단 전용이다.")


def _span_len(s) -> int:
    return s[1] - s[0] + 1


def gen_events(rep: dict) -> list:
    return [e for e in (rep.get("events") or []) if e.get("span")]


def overlaps(a, b) -> bool:
    return min(a[1], b[1]) >= max(a[0], b[0])


SUBSTANTIAL_FRAC = 0.5    # 다른 GT를 이만큼 먹었을 때만 overmerge로 센다 (진단)


def overlap_len(a, b) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)


def n_gt_substantially_overlapped(refs: list, gen_span) -> int:
    """생성 span이 **실질적으로** 먹은 정답 사건 수.

    단순히 "겹치면 1건"으로 세면 과발동한다 — 이 패널의 GT는 대부분 연속이라
    생성 span이 2구간만 넘쳐도 옆 사건에 걸린다(실측: `softyeon` GT5는 IoU 0.95인데
    2구간 넘쳐 overmerge로 찍혔다). 그 GT 길이의 절반 이상을 먹었을 때만 센다.
    """
    if not gen_span:
        return 0
    return sum(1 for r in refs
               if overlap_len(r["span"], gen_span)
               >= SUBSTANTIAL_FRAC * _span_len(r["span"]))


def alignment_type(ref_span, gen_span, iou: float, n_gt_overlapped: int) -> str:
    """동결 taxonomy 이름에 기계 규칙을 붙인다. **규칙은 post-hoc이다.**"""
    if gen_span is None:
        return "missed_event"
    if n_gt_overlapped >= 2:
        return "overmerge"
    if iou >= REASONABLE_IOU:
        return "reasonable_match"
    if _span_len(gen_span) >= WIDE_FACTOR * _span_len(ref_span):
        return "boundary_too_wide"
    return "boundary_shift"


def event_rows(video_id: str, refs: list, gens: list) -> list:
    """정답 사건 68개를 한 줄씩. 미매칭은 IoU 0으로 남긴다(동결 정의)."""
    m = M.match_events(refs, gens)
    rows = []
    for i, r in enumerate(refs):
        j = m[i]
        gs = gens[j]["span"] if j is not None else None
        iou = M.temporal_iou(r["span"], gs) if gs else 0.0
        n_gt_ov = n_gt_substantially_overlapped(refs, gs)
        rows.append({
            "video_id": video_id, "gt_index": i, "gt_event": r["event"],
            "gt_span": r["span"], "gt_len": _span_len(r["span"]),
            "matched": j is not None, "matched_gen_index": j,
            "gen_span": gs, "gen_len": _span_len(gs) if gs else None,
            "matched_iou": round(iou, 4),
            "n_generated_overlapping": sum(
                1 for g in gens if overlaps(g["span"], r["span"])),
            "n_gt_substantially_overlapped_by_matched_gen": n_gt_ov,
            "n_gt_touched_by_matched_gen": (
                sum(1 for x in refs if gs and overlaps(x["span"], gs))),
            "alignment_type": alignment_type(r["span"], gs, iou, n_gt_ov),
            "bucket": ("UNMATCHED" if gs is None else
                       "HIGH" if iou >= 0.7 else "MID" if iou >= 0.3 else "LOW"),
        })
    return rows


def generated_rows(video_id: str, refs: list, gens: list) -> list:
    m = M.match_events(refs, gens)
    matched = {j: i for i, j in m.items() if j is not None}
    rows = []
    for j, g in enumerate(gens):
        ov = [i for i, r in enumerate(refs) if overlaps(r["span"], g["span"])]
        rows.append({"video_id": video_id, "gen_index": j, "event": g["event"],
                     "span": g["span"], "len": _span_len(g["span"]),
                     "n_evidence": len(g.get("evidence_segments") or []),
                     "matched": j in matched,
                     "matched_gt_index": matched.get(j),
                     "overlapping_gt": ov,
                     "type": "reasonable_match" if j in matched else "spurious_event"})
    return rows


def rejection_rows(video_id: str, refs: list, rep: dict, ev_rows: list) -> list:
    """거부된 후보를 GT 시간대와 연결한다.

    **되살려서 counterfactual 관문값을 계산하지 않는다.** "거부가 없었으면 PASS"는
    금지된 진술이고, 여기서 내는 것은 "미매칭 GT와 시간대가 겹쳤는가"뿐이다.
    """
    unmatched = {r["gt_index"] for r in ev_rows if not r["matched"]}
    rows = []
    for k, rj in enumerate(rep.get("rejected") or []):
        span = rj.get("span") or []
        ov = [i for i, r in enumerate(refs)
              if len(span) >= 2 and overlaps(r["span"], span[:2])]
        rows.append({"video_id": video_id, "rejection_index": k,
                     "chunk": rj.get("chunk"), "reason": rj.get("reason"),
                     "span": span, "event": (rj.get("event") or "")[:80],
                     "overlapping_gt": ov,
                     "overlapping_unmatched_gt": sorted(set(ov) & unmatched)})
    return rows


def chunk_rows(video_id: str, rep: dict) -> list:
    """청크별 원본 사건 수. `map_raw_outputs`를 다시 파싱한다(병합 전)."""
    retries = {r.get("chunk"): r.get("recovered")
               for r in (rep.get("chunk_retries") or [])}
    rows = []
    for i, raw in enumerate(rep.get("map_raw_outputs") or []):
        parsed = m8_report.parse_events(raw)
        rows.append({"video_id": video_id, "chunk": i,
                     "raw_events": len(parsed),
                     "zero_event_chunk": len(parsed) == 0,
                     "regeneration_attempted": i in retries,
                     "regeneration_recovered": retries.get(i)})
    return rows


def c1_semantic(video_id: str, rep: dict, chunks: list) -> dict:
    """C1 `early_stop` 4건이 꼬리 절단인지 중간 구멍인지 **사후** 분류.

    공식 C1을 다시 계산하지 않는다. 공식 verdict는 그대로 FAIL이다.
    """
    f = m8_c1.detect_early_stop(rep)
    failed = [r.get("chunk") for r in (rep.get("chunk_retries") or [])
              if not r.get("recovered")]
    last = len(chunks) - 1
    if f["status"] != "PRESENT":
        kind = "NOT_PRESENT"
    elif rep.get("truncated_tail"):
        kind = "TAIL_TERMINATION"
    elif failed and all(c != last for c in failed):
        kind = "MID_STREAM_EMPTY_CHUNK"
    elif failed:
        kind = "TAIL_TERMINATION"
    else:
        kind = "OTHER"
    return {"video_id": video_id, "official_early_stop": f["status"],
            "failed_chunks": failed, "n_chunks": len(chunks),
            "last_chunk_index": last, "post_hoc_kind": kind,
            "truncated_tail": bool(rep.get("truncated_tail"))}


def redundancy_diagnostic(ev_rows: list) -> dict:
    """사전등록 정의가 없으므로 **다른 이름으로만** 낸다."""
    multi = [r for r in ev_rows if r["n_generated_overlapping"] >= 2]
    dist = {}
    for r in ev_rows:
        dist[r["n_generated_overlapping"]] = dist.get(
            r["n_generated_overlapping"], 0) + 1
    return {"status": REDUNDANCY_STATUS, "note": REDUNDANCY_NOTE,
            "gt_events_with_multiple_overlapping_generated": len(multi),
            "n_gt_events": len(ev_rows),
            "overlapping_generated_per_gt_distribution":
                {str(k): v for k, v in sorted(dist.items())}}


def iou_distribution(ev_rows: list) -> dict:
    v = sorted(r["matched_iou"] for r in ev_rows)
    if not v:
        return {"n": 0}
    def q(p):
        return round(v[min(int(p * (len(v) - 1) + 0.5), len(v) - 1)], 4)
    return {"n": len(v), "min": v[0], "p25": q(0.25),
            "median": round(statistics.median(v), 4), "p75": q(0.75), "max": v[-1],
            "buckets": {b: sum(1 for r in ev_rows if r["bucket"] == b)
                        for b in ("HIGH", "MID", "LOW", "UNMATCHED")}}


def failure_mode(v: dict) -> dict:
    """설명용 grouping. **acceptance taxonomy가 아니다.** 근거 수치를 함께 낸다."""
    modes, why = [], []
    if v["n_sentences"] < v["n_reference_events"]:
        modes.append("UNDER_GENERATION_DOMINANT")
        why.append(f"생성 {v['n_sentences']} < GT {v['n_reference_events']}")
    if v["compression"] and v["compression"] > 2.0:
        modes.append("OVER_FRAGMENTATION_DOMINANT")
        why.append(f"compression {v['compression']}")
    if v["alignment"] is not None and v["alignment"] < 0.3 \
            and "UNDER_GENERATION_DOMINANT" not in modes:
        modes.append("SPAN_ALIGNMENT_DOMINANT")
        why.append(f"alignment {v['alignment']}")
    if v["rejections"] >= 3:
        modes.append("REJECTION_HEAVY")
        why.append(f"거부 {v['rejections']}건")
    if len(modes) > 1:
        modes = ["MIXED"] + modes
    if not modes:
        modes = ["RELATIVELY_STABLE"]
        why.append(f"alignment {v['alignment']} · compression {v['compression']}")
    return {"failure_modes": modes, "evidence": why}


def analyze(cfg, videos=None, official_path=OFFICIAL) -> dict:
    videos = videos or panel_videos()
    off = json.loads(Path(official_path).read_text(encoding="utf-8"))
    by_off = {r["video_id"]: r for r in off["per_video"]}
    per_video, ev_all, gen_all, rej_all, chunk_all, c1_all = {}, [], [], [], [], []
    for v in videos:
        rep = json.loads((Path(common.work_dir(cfg, v)) / "report.json")
                         .read_text(encoding="utf-8"))
        refs = load_reference(v, csv_path=OUT / f"{v}.csv")
        gens = gen_events(rep)
        ev = event_rows(v, refs, gens)
        gr = generated_rows(v, refs, gens)
        ch = chunk_rows(v, rep)
        rj = rejection_rows(v, refs, rep, ev)
        o = by_off[v]
        row = {"n_reference_events": len(refs),
               "n_sentences": len(rep.get("sentences") or []),
               "n_generated_events": len(gens),
               "compression": o["compression"],
               "alignment": o["c2_candidates"]["event_temporal_alignment"],
               "theta_recall": {k: val for k, val in o["c2_candidates"].items()
                                if k.startswith("temporal_event_recall")},
               "unmatched_gt": sum(1 for r in ev if not r["matched"]),
               "unmatched_generated": sum(1 for r in gr if not r["matched"]),
               "rejections": len(rj),
               "rejection_reasons": o["rejection_reasons"],
               "span_coverage": o["diagnostics"]["timeline_span_coverage"],
               "c1_status": o["c1_status"],
               "zero_event_chunks": sum(1 for c in ch if c["zero_event_chunk"]),
               "alignment_types": {t: sum(1 for r in ev if r["alignment_type"] == t)
                                   for t in M.EVENT_ALIGNMENT_TYPES
                                   if any(r["alignment_type"] == t for r in ev)},
               "iou_distribution": iou_distribution(ev),
               "redundancy_diagnostic": redundancy_diagnostic(ev)}
        row.update(failure_mode(row))
        per_video[v] = row
        ev_all += ev
        gen_all += gr
        rej_all += rj
        chunk_all += ch
        c1_all.append(c1_semantic(v, rep, ch))
    return {
        "record": "M8 실패 분해 (진단 전용)", "date": "2026-08-27",
        "official_result": {"evaluation": off["evaluation"],
                            "acceptance": off["acceptance"],
                            "c1": off["verdict"]["C1"], "c2": off["verdict"]["C2"],
                            "c3": off["verdict"]["C3"],
                            "changed_by_this_analysis": False},
        "operationalization_note": (
            "alignment_type은 동결 taxonomy 이름에 post-hoc 기계 규칙을 붙인 것이다 "
            f"(reasonable_match IoU>={REASONABLE_IOU}, boundary_too_wide >={WIDE_FACTOR}배, "
            f"overmerge는 다른 GT를 그 길이의 {SUBSTANTIAL_FRAC:.0%} 이상 먹었을 때). "
            "규칙 자체는 사전등록에 없고 진단 전용이다. "
            "bucket(HIGH/MID/LOW/UNMATCHED)도 관문 임계가 아니다."),
        "per_video": per_video, "event_level": ev_all,
        "generated_level": gen_all, "rejection_analysis": rej_all,
        "chunk_level": chunk_all, "c1_semantic_diagnostic": c1_all,
        "redundancy": {"status": REDUNDANCY_STATUS, "note": REDUNDANCY_NOTE},
        "overall_iou_distribution": iou_distribution(ev_all),
        "failure_mode_summary": {
            v: per_video[v]["failure_modes"] for v in per_video},
        "confirmation_consequence": {
            "current_panel_reusable_for_fresh_confirmation": False,
            "fresh_confirmation_needed_after_material_change": True,
            "note": ("N=8은 공식 결과를 본 순간 소비된 confirmation sample이다. "
                     "수정된 M8의 확증에 같은 8편을 다시 쓸 수 없다.")},
        "m9_status": "HOLD",
    }


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out",
                    default="docs/finalization/m8_failure_analysis_2026-08-27.json")
    a = ap.parse_args()
    d = analyze(common.load_config(str(ROOT / a.config)))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"작성: {a.out}")
    print(f"공식 결과 불변: acceptance {d['official_result']['acceptance']}")
    print(f"GT 사건 {len(d['event_level'])} · 생성 {len(d['generated_level'])} · "
          f"거부 {len(d['rejection_analysis'])} · 청크 {len(d['chunk_level'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
