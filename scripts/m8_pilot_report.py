"""M8 pilot 보고 — 동결된 정답 사건 목록 대비 temporal 지표.

**결과를 열기 전에 커밋한다.** 분모(`FROZEN_*.json`)와 이 코드가 결과보다 먼저
이력에 있어야, 나중에 "보고 나서 정의를 맞춘 것"이 아니라고 말할 수 있다.
사전등록: `docs/preregistration/M8_event지표_보충_2026-08-18.md`,
`docs/preregistration/event_inventory_사전등록_2026-08-18.md`.

## 적격성을 positive로 정의한다

reference 지표는 **등록되고 동결된 영상만** 계산한다. 제외 영상의 값을 `0`으로
내면 "GT가 있었는데 하나도 못 맞췄다"는 전혀 다른 뜻이 된다 — `None`이다.

    reference_eligible(v) = v ∈ policy.requires_frozen_inventory
                            ∧ v ∉ policy.excluded_from_reference
                            ∧ FROZEN_{v}.json 존재

`_10_000`은 배관 진단 중 M8 사건 수가 로그에 노출돼(작업현황 §5-4) 독립
reference로 쓸 수 없다. 정책에 `excluded_from_reference`로 등록돼 있고, 그
영상은 **생성 쪽 구조 진단에만** 들어간다.

## 집계 가중

`event_temporal_alignment` = **모든 reference event를 동일 가중**한 macro mean이다
(영상 균등 평균이 아니다 — 사건 수가 많은 영상의 가중치가 달라진다). 영상별 값도
같이 내지만, 집계는 사건 균등 하나뿐이다.

**영상 2편이므로 CI를 내지 않는다**(작업현황 §5-3). 사례 진단이다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np                                          # noqa: E402
from m8_metrics import (IOU_THETAS, matched_ious, match_events,  # noqa: E402
                        structural_summary)
from m6_evaluate import derive_gt_seg_idx                   # noqa: E402

DEFAULT_INVENTORY_DIR = ROOT / "label_kit" / "event_inventory"
DEFAULT_POLICY_PATH = ROOT / "planning" / "report_access.json"
CI_REASON = "영상 2편 사례 진단이다 — 구간 추정을 하지 않는다 (작업현황 §5-3)"


# ---- 정책·reference -------------------------------------------------------

def policy(run_id: str, policy_path=None) -> dict:
    p = Path(policy_path or DEFAULT_POLICY_PATH)
    if not p.is_file():
        return {}
    for pol in json.loads(p.read_text(encoding="utf-8")).get("policies", []):
        if pol.get("run_id") == run_id:
            return pol
    return {}


def frozen(video_id: str, inventory_dir=None):
    p = Path(inventory_dir or DEFAULT_INVENTORY_DIR) / f"FROZEN_{video_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def reference_events(video_id: str, inventory_dir=None, policy_path=None) -> list:
    """동결본에서 reference를 읽는다. **span은 초에서 매번 재계산한다** —
    초가 원본이고 span은 `derive_gt_seg_idx`로 파생되는 값이다."""
    d = frozen(video_id, inventory_dir)
    if d is None:
        return []
    n, sl = d["n_segments"], d["seg_len"]
    out = []
    for e in d["events"]:
        span = derive_gt_seg_idx(e["start_sec"], e["end_sec"], n, sl)
        out.append({**e, "span": [min(span), max(span)]})
    return out


def reference_eligible(video_id: str, run_id: str,
                       inventory_dir=None, policy_path=None) -> bool:
    """**positive eligibility.** 등록·미제외·동결 셋을 전부 만족해야 한다."""
    pol = policy(run_id, policy_path)
    return (video_id in (pol.get("requires_frozen_inventory") or [])
            and video_id not in (pol.get("excluded_from_reference") or [])
            and frozen(video_id, inventory_dir) is not None)


def _reference_status(video_id, run_id, inventory_dir, policy_path) -> str:
    pol = policy(run_id, policy_path)
    if video_id in (pol.get("excluded_from_reference") or []):
        return "not_applicable"
    if frozen(video_id, inventory_dir) is None:
        return "no_frozen_reference"
    if video_id not in (pol.get("requires_frozen_inventory") or []):
        return "not_registered"
    return "eligible"


# ---- 영상별 ---------------------------------------------------------------

def video_metrics(video_id: str, report: dict, n_segments: int, run_id: str,
                  inventory_dir=None, policy_path=None) -> dict:
    """생성 쪽 구조 진단은 **항상** 낸다. reference 지표는 적격일 때만."""
    gens = report.get("events") or []
    out = {"video_id": video_id,
           "structural": structural_summary(report, n_segments),
           "reference_status": _reference_status(video_id, run_id,
                                                inventory_dir, policy_path)}
    ok = reference_eligible(video_id, run_id, inventory_dir, policy_path)
    out["reference_eligible"] = ok
    if not ok:
        out.update(n_reference_events=None, n_matched=None,
                   event_temporal_alignment=None, matched_ious=None,
                   temporal_event_recall={f"temporal_event_recall@IoU>={t}": None
                                          for t in IOU_THETAS})
        return out
    refs = reference_events(video_id, inventory_dir, policy_path)
    ious = matched_ious(refs, gens)
    out.update(
        n_reference_events=len(refs),
        n_matched=sum(1 for j in match_events(refs, gens).values() if j is not None),
        matched_ious=[round(float(x), 4) for x in ious],
        event_temporal_alignment=round(float(np.mean(ious)), 4) if refs else None,
        temporal_event_recall={
            f"temporal_event_recall@IoU>={t}":
                round(float(np.mean([x >= t for x in ious])), 4)
            for t in IOU_THETAS})
    return out


# ---- 집계 -----------------------------------------------------------------

def aggregate(per_video: dict) -> dict:
    """**모든 reference event를 동일 가중**한다. 영상 균등 평균은 내지 않는다."""
    elig = {v: m for v, m in per_video.items() if m["reference_eligible"]}
    ious = [x for m in elig.values() for x in (m["matched_ious"] or [])]
    agg = {
        "estimand": "동결된 정답 사건 목록 대비 temporal 정렬 — 사례 진단",
        "weighting": "reference event 균등 (영상 균등 아님)",
        "reference_videos": sorted(elig),
        "n_reference_videos": len(elig),
        "n_reference_events": len(ious),
        "excluded_videos": sorted(
            v for v, m in per_video.items()
            if m["reference_status"] == "not_applicable"),
        "event_temporal_alignment": round(float(np.mean(ious)), 4) if ious else None,
        "temporal_event_recall": {
            f"temporal_event_recall@IoU>={t}":
                (round(float(np.mean([x >= t for x in ious])), 4) if ious else None)
            for t in IOU_THETAS},
        "ci": None, "ci_reason": CI_REASON,
        "structural": {"n_videos": len(per_video),
                       "timeline_span_coverage_by_video": {
                           v: m["structural"]["timeline_span_coverage"]
                           for v, m in per_video.items()}},
    }
    return agg


# ---- CLI ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True,
                    help="exp_launcher.py report가 알려준 경로만 쓴다")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pilot = json.loads(Path(a.pilot).read_text(encoding="utf-8"))
    per = {}
    for v, s in pilot["per_video"].items():
        rep = json.loads((ROOT / "work" / v /
                          f"report_pilot_{pilot['run_id']}.json")
                         .read_text(encoding="utf-8"))
        per[v] = video_metrics(v, rep, s["n_segments"], a.run_id)
    body = {"probe": "m8_pilot_report", "run_id": a.run_id,
            "pilot_source": str(a.pilot),
            "pilot_provenance": pilot.get("provenance"),
            "per_video": per, "aggregate": aggregate(per)}
    Path(a.out).write_text(json.dumps(body, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"저장: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
