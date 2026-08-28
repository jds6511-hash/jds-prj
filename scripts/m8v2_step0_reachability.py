"""M8-v2 STEP 0 — trigger reachability pilot. **집합 연산만 한다.**

규격: `docs/finalization/M8V2_STEP0_SPEC_2026-08-28.md` (실행 전 동결).

질문 하나만 답한다.

    baseline 출력만으로 정의 가능한 **단일** trigger 중, 최소 5/22 unmatched GT에
    닿으면서 intervention 범위를 충분히 좁게 유지하는 규칙이 존재하는가.

성능을 재지 않는다. 새 라벨 0건, 새 생성 0건, GPU 0. M8-v1 판정을 바꾸지 않고
M9·official test에 접근하지 않는다. 여기 나온 숫자는 어떤 acceptance verdict에도
들어가지 않는다.

사용:
    python scripts/m8v2_step0_reachability.py
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
import m8_metrics as M                                              # noqa: E402
import m8_report                                                    # noqa: E402
from m8_gates import panel_videos, reference_events                 # noqa: E402

SPEC = "docs/finalization/M8V2_STEP0_SPEC_2026-08-28.md"
LINEAGE = ROOT / "docs/finalization/m8_official_report_lineage_2026-08-27.json"
OFFICIAL = ROOT / "results/m8_official_0827/m8_official_full.json"
OUT = ROOT / "results/m8v2_step0/m8v2_step0_reachability_2026-08-28.json"

UPPER_BOUND_NOTE = (
    "reachable은 상한이다 — 'trigger가 그 GT 위에서 발화한다'는 뜻이지 "
    "'rescue가 그 GT를 실제로 회수한다'는 뜻이 아니다. 필요조건 검사이며 "
    "실제 회수율은 이 상한보다 낮다.")
OUTCOME_INFORMED_NOTE = (
    "T2~T5와 그 threshold는 M8-v1 consumed panel의 unmatched GT 위치를 사용해 "
    "설계했으므로 outcome-informed이다. 따라서 본 pilot 수치는 성능 증거가 아니며, "
    "선택된 trigger는 fresh data에서 동결 후 평가한다.")

# GO 기준 — 규격 §5에서 동결. 결과를 보고 고치지 않는다.
GO_MIN_REACHABLE = 5
GO_MIN_VIDEOS = 2
GO_MAX_TRIGGERED = 12
GO_MAX_VIDEO_SHARE = 0.60

# 규격 §6. 파생량 개수 기준이며 **임의 선택임을 인정**한다 — 사후 변경을 막으려고 박는다.
SIMPLICITY_RANK = {"T3": 1, "T5a": 2, "T5b": 3, "T2": 4, "T4": 5}

# 규격 §3-1. 38개 전부의 결과를 저장한다 — 통과한 것만 남기면 sweep 은폐다.
GRID = {
    "T2":  [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90],
    "T3":  [1, 2, 3, 4, 5, 6],
    "T4":  [20, 30, 45, 60, 90, 120, 180, 240],
    "T5a": [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90],
    "T5b": [0.5, 1.0, 2.0, 3.0, 4.0, 5.0],
}
FAMILY_RULE = {
    "T2":  "accepted_span_coverage < X",
    "T3":  "raw_density_per60 < D",
    "T4":  "max_uncovered_gap_sec > G초",
    "T5a": "rejection_ratio >= R",
    "T5b": "rejections_per_10min >= K",
}


class Step0Error(RuntimeError):
    """전제가 안 맞으면 조용히 진행하지 않는다."""


# ── 청크 경계 ────────────────────────────────────────────────────────────
def chunk_spans(n_segments: int, chunk_size: int, overlap: int) -> list:
    """생성기의 while 루프와 **같은 경계**를 낸다(구간 인덱스, 양 끝 포함).

    어긋나면 feature가 조용히 다른 구간에서 계산되고 reachability가 통째로 틀린다.
    """
    if overlap >= chunk_size:
        raise Step0Error(f"overlap({overlap}) >= chunk_size({chunk_size})")
    spans, start = [], 0
    while start < n_segments:
        spans.append((start, min(start + chunk_size, n_segments) - 1))
        if start + chunk_size >= n_segments:
            break
        start += chunk_size - overlap
    return spans


# ── feature — GT를 쓰지 않는다 ───────────────────────────────────────────
def _covered_mask(events: list, span) -> list:
    s, e = span
    mask = [False] * (e - s + 1)
    for ev in events:
        a, b = ev["span"]
        for i in range(max(a, s), min(b, e) + 1):
            mask[i - s] = True
    return mask


def _longest_false_run(mask: list) -> int:
    best = cur = 0
    for v in mask:
        cur = 0 if v else cur + 1
        best = max(best, cur)
    return best


def chunk_features(report: dict, spans: list, seg_len_sec: int) -> list:
    """청크별 feature. **baseline 산출물만** 쓴다 — 그래야 fresh data에서 같은
    규칙을 그대로 적용할 수 있다. GT는 인자로도 받지 않는다."""
    events = report.get("events") or []
    raws = report.get("map_raw_outputs") or []
    rejected = report.get("rejected") or []
    out = []
    for i, span in enumerate(spans):
        mask = _covered_mask(events, span)
        n = len(mask)
        raw = len(m8_report.parse_events(raws[i])) if i < len(raws) else 0
        rej = sum(1 for r in rejected if r.get("chunk") == i)
        out.append({
            "chunk": i, "span": span, "len_segments": n,
            "raw_candidates": raw,
            "raw_density_per60": round(raw * 60 / n, 4),
            "accepted_span_coverage": round(sum(mask) / n, 4),
            "max_uncovered_gap_sec": _longest_false_run(mask) * seg_len_sec,
            "rejected": rej,
            # raw 0을 '거부 부하 최대'로 올리면 T5가 T1이 된다 — 0으로 둔다
            "rejection_ratio": round(rej / raw, 4) if raw else 0.0,
            "rejections_per_10min": round(rej / (n * seg_len_sec / 600), 4),
        })
    return out


# ── trigger ──────────────────────────────────────────────────────────────
def _fmt(t) -> str:
    return f"{t:g}"


def candidates() -> list:
    """단일 규칙만. OR 결합은 제공하지 않는다 — 합쳐서 5건을 넘기면 이 아이디어가
    충분히 단순하지 않다는 신호를 지우게 된다."""
    return [{"id": f"{fam}@{_fmt(t)}", "family": fam, "threshold": t,
             "rule": FAMILY_RULE[fam]}
            for fam, ts in GRID.items() for t in ts]


def fires(feat: dict, cand: dict) -> bool:
    fam, t = cand["family"], cand["threshold"]
    if fam == "T2":
        return bool(feat["accepted_span_coverage"] < t)
    if fam == "T3":
        return bool(feat["raw_density_per60"] < t)
    if fam == "T4":
        return bool(feat["max_uncovered_gap_sec"] > t)
    if fam == "T5a":
        return bool(feat["rejection_ratio"] >= t)
    if fam == "T5b":
        return bool(feat["rejections_per_10min"] >= t)
    raise Step0Error(f"모르는 trigger 계열: {fam}")


# ── reachability ─────────────────────────────────────────────────────────
def _overlaps(a, b) -> bool:
    return not (a[1] < b[0] or a[0] > b[1])


def evaluate(per_video: list) -> dict:
    """발화 청크와 unmatched GT의 **겹침만** 센다. 회수 성공을 가정하지 않는다."""
    reach_by_video, triggered, wasted = {}, 0, 0
    for v in per_video:
        fired = [c["span"] for c in v["chunks"] if c["flag"]]
        triggered += len(fired)
        hit = [g for g in v["unmatched"]
               if any(_overlaps(g, s) for s in fired)]
        wasted += sum(1 for s in fired
                      if not any(_overlaps(g, s) for g in v["unmatched"]))
        if hit:
            reach_by_video[v["video_id"]] = len(hit)
    total = sum(reach_by_video.values())
    return {"reachable_unmatched_gt": total,
            "reachable_videos": len(reach_by_video),
            "triggered_chunks": triggered,
            "wasted_triggers": wasted,
            "max_video_share": (round(max(reach_by_video.values()) / total, 4)
                                if total else 0.0),
            "reachable_by_video": reach_by_video}


def go_verdict(m: dict) -> dict:
    failed = []
    if m["reachable_unmatched_gt"] < GO_MIN_REACHABLE:
        failed.append("reachable_unmatched_gt")
    if m["reachable_videos"] < GO_MIN_VIDEOS:
        failed.append("reachable_videos")
    if m["triggered_chunks"] > GO_MAX_TRIGGERED:
        failed.append("triggered_chunks")
    if m["max_video_share"] > GO_MAX_VIDEO_SHARE:
        failed.append("max_video_share")
    return {"go": not failed, "failed": failed}


def select_best(evaluated: list):
    """규격 §6: burden 최소 → 영상 수 최대 → 규칙 단순 → id 사전순. 최대 1개."""
    ok = [c for c in evaluated if c.get("go")]
    if not ok:
        return None
    return sorted(ok, key=lambda c: (c["triggered_chunks"],
                                     -c["reachable_videos"],
                                     SIMPLICITY_RANK[c["family"]],
                                     c["id"]))[0]


# ── 패널 적재 ────────────────────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_panel(cfg: dict, work_root=None) -> list:
    """공식 baseline 8편 + 동결 GT. **해시가 안 맞으면 진행하지 않는다.**"""
    lineage = json.loads(LINEAGE.read_text(encoding="utf-8"))["report_sha256"]
    nseg = {r["video_id"]: r["n_segments"]
            for r in json.loads(OFFICIAL.read_text(encoding="utf-8"))["per_video"]}
    cs, ov = cfg["map_chunk_size"], cfg["map_chunk_overlap"]
    out = []
    for v in panel_videos():
        p = Path(work_root or common.work_dir(cfg, v)) / "report.json" \
            if work_root else Path(common.work_dir(cfg, v)) / "report.json"
        if not p.is_file():
            raise Step0Error(f"{v}: baseline report가 없다 — {p}")
        got = _sha(p)
        if got != lineage[v]:
            raise Step0Error(
                f"{v}: baseline 해시 불일치. 공식 8편이 아니다\n"
                f"  기대 {lineage[v]}\n  실제 {got}")
        rep = json.loads(p.read_text(encoding="utf-8"))
        refs = reference_events(v)
        match = M.match_events(refs, rep.get("events") or [])
        unmatched = [refs[i]["span"] for i, j in match.items() if j is None]
        spans = chunk_spans(nseg[v], cs, ov)
        if len(spans) != len(rep.get("map_raw_outputs") or []):
            raise Step0Error(
                f"{v}: 청크 경계 재현 실패 — 계산 {len(spans)} vs 실제 "
                f"{len(rep.get('map_raw_outputs') or [])}")
        out.append({"video_id": v, "n_segments": nseg[v],
                    "n_reference_events": len(refs),
                    "report_sha256": got,
                    "features": chunk_features(rep, spans, cfg["seg_len_sec"]),
                    "unmatched": unmatched})
    return out


def run_sweep(panel: list) -> list:
    """38개 후보 전부. frontier를 통째로 남긴다."""
    rows = []
    for cand in candidates():
        pv = [{"video_id": v["video_id"],
               "chunks": [{"span": f["span"], "flag": fires(f, cand)}
                          for f in v["features"]],
               "unmatched": v["unmatched"]} for v in panel]
        m = evaluate(pv)
        rows.append({**cand, **m, **go_verdict(m)})
    return rows


def t1_reference(panel: list) -> dict:
    """T1(zero-event rescue)은 후보가 아니라 **대조 기준**이다. 표에는 계속 싣는다."""
    pv = [{"video_id": v["video_id"],
           "chunks": [{"span": f["span"], "flag": f["raw_candidates"] == 0}
                      for f in v["features"]],
           "unmatched": v["unmatched"]} for v in panel]
    m = evaluate(pv)
    return {"id": "T1@zero_event", "family": "T1",
            "rule": "raw_candidates == 0 (H6a)", **m, **go_verdict(m),
            "status": "STRUCTURAL_NO_GO — 후보로 취급하지 않는다"}


def selected_diagnostic(panel: list, cand: dict) -> dict:
    """선택된 trigger가 **무엇 때문에 빈 청크를 골랐는지** 가른다.

    `raw_candidates == 0`(생성이 없었다)과 `rejected == raw_candidates`(생성은 됐는데
    검증에서 사라졌다)는 완전히 다른 원인이고, **필요한 개입도 다르다.** 이 구분이
    없으면 재생성으로 고칠 수 없는 것을 재생성으로 고치려 든다.
    """
    fired, raw, rej, no_gen, all_rej = 0, 0, 0, 0, 0
    for v in panel:
        for f in v["features"]:
            if not fires(f, cand):
                continue
            fired += 1
            raw += f["raw_candidates"]
            rej += f["rejected"]
            no_gen += int(f["raw_candidates"] == 0)
            all_rej += int(f["raw_candidates"] > 0
                           and f["rejected"] == f["raw_candidates"])
    p_raw = sum(f["raw_candidates"] for v in panel for f in v["features"])
    p_rej = sum(f["rejected"] for v in panel for f in v["features"])
    return {"candidate": cand["id"], "fired_chunks": fired,
            "raw_candidates": raw, "rejected": rej,
            "rejection_share": round(rej / raw, 4) if raw else None,
            "panel_rejection_share": round(p_rej / p_raw, 4) if p_raw else None,
            "chunks_with_no_generation": no_gen,
            "chunks_where_all_candidates_rejected": all_rej,
            "note": ("발화 청크의 거부 비율이 패널 전체보다 높으면, 그 공백은 "
                     "생성 실패가 아니라 **검증 탈락**이 만든 것이다 — "
                     "같은 validator로 재생성하면 같은 거부가 재현될 수 있다")}


def build_manifest(panel: list, frontier: list, t1: dict) -> dict:
    best = select_best(frontier)
    n_chunks = sum(len(v["features"]) for v in panel)
    n_unmatched = sum(len(v["unmatched"]) for v in panel)
    return {
        "record": "M8-v2 STEP 0 — trigger reachability pilot",
        "date": "2026-08-28", "spec": SPEC,
        "kind": "structural feasibility test — 성능 측정이 아니다",
        "boundary": {"new_labels": 0, "new_generation": 0, "llm_calls": 0,
                     "m8v1_verdict_changed": False,
                     "m9_or_official_test_touched": False,
                     "note": "M8-v1 REDESIGN ROUND 3가 아니다 — 집합 연산만 한다"},
        "upper_bound_note": UPPER_BOUND_NOTE,
        "outcome_informed_note": OUTCOME_INFORMED_NOTE,
        "panel": {"n_videos": len(panel), "n_chunks": n_chunks,
                  "n_unmatched_gt": n_unmatched,
                  "per_video": [{k: v[k] for k in
                                 ("video_id", "n_segments", "n_reference_events",
                                  "report_sha256")}
                                | {"n_chunks": len(v["features"]),
                                   "n_unmatched": len(v["unmatched"])}
                                for v in panel]},
        "go_criteria": {"reachable_unmatched_gt >=": GO_MIN_REACHABLE,
                        "reachable_videos >=": GO_MIN_VIDEOS,
                        "triggered_chunks <=": GO_MAX_TRIGGERED,
                        "max_video_share <=": GO_MAX_VIDEO_SHARE,
                        "burden_note": "30% 상한은 과학적 사실이 아니라 설계 제약이다"},
        "selection_rule": ["triggered_chunks 최소", "reachable_videos 최대",
                           f"규칙 단순성 {SIMPLICITY_RANK}", "id 사전순"],
        "t1_reference": t1,
        "frontier": frontier,
        "n_candidates": len(frontier),
        "n_go": sum(1 for c in frontier if c["go"]),
        "selected": best,
        "selected_diagnostic": selected_diagnostic(panel, best) if best else None,
        "verdict": ("GO" if best else
                    "NO-GO — M8-v2 NOT STARTED: no selective trigger with "
                    "sufficient structural reachability was identified"),
        "chunk_features": [{"video_id": v["video_id"], "features": v["features"],
                            "unmatched_spans": v["unmatched"]} for v in panel],
    }


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    panel = load_panel(cfg)
    frontier = run_sweep(panel)
    man = build_manifest(panel, frontier, t1_reference(panel))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(Path(a.out), man)

    print(f"패널 {man['panel']['n_videos']}편 · 청크 {man['panel']['n_chunks']} · "
          f"unmatched GT {man['panel']['n_unmatched_gt']}")
    t1 = man["t1_reference"]
    print(f"T1(H6a) 대조 — reachable {t1['reachable_unmatched_gt']} · "
          f"triggered {t1['triggered_chunks']} · {t1['status']}")
    print(f"후보 {man['n_candidates']} · GO {man['n_go']}")
    print(f"{'id':16s} {'reach':>5s} {'vid':>3s} {'trig':>4s} {'waste':>5s} "
          f"{'share':>5s}  go")
    for c in sorted(frontier, key=lambda c: (-c["go"], c["triggered_chunks"],
                                             -c["reachable_unmatched_gt"])):
        print(f"{c['id']:16s} {c['reachable_unmatched_gt']:5d} "
              f"{c['reachable_videos']:3d} {c['triggered_chunks']:4d} "
              f"{c['wasted_triggers']:5d} {c['max_video_share']:5.2f}  "
              f"{'GO' if c['go'] else ','.join(c['failed'])}")
    print(f"\n판정: {man['verdict']}")
    if man["selected"]:
        print(f"선택: {man['selected']['id']} — {man['selected']['rule']}")
    print(f"산출물: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
