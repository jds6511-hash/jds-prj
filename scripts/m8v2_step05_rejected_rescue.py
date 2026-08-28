"""M8-v2 STEP 0.5 — rejected-candidate rescue reachability pilot.

질문 하나만 답한다.

    T2@0.7이 잡은 low-coverage 청크 안에서, baseline이 **이미 만들었다가**
    `too_many_evidence`로 거부된 후보를 출력 계약 안으로 결정적으로 복구하면,
    기존 unmatched GT 22건 중 5건 이상을 구조적으로 회수할 수 있는가.

**intervention은 하나다 — evidence cap repair.** evidence 길이만 4로 자르고
그 밖의 필드는 건드리지 않는다. relaxed validator를 만들지 않고 **현행 validator를
그대로 다시 태운다**. 통과 못 하면 STILL_REJECTED로 남긴다.

M8-v1 ROUND 3가 아니다. 새 생성·새 프롬프트·acceptance 재평가가 아니다.
새 라벨 0 · LLM 0 · GPU 0 · 판정 불변 · M9/official test 무접촉.

사용:
    python scripts/m8v2_step05_rejected_rescue.py
"""
import argparse
import collections
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
import m8_metrics as M                                              # noqa: E402
import m8_report                                                    # noqa: E402
import m8v2_step0_reachability as S0                                # noqa: E402
from m8_gates import panel_videos, reference_events                 # noqa: E402

DOC = "docs/finalization/M8V2_STEP05_REJECTED_RESCUE_2026-08-28.md"
STEP0_ARTIFACT = ROOT / "results/m8v2_step0/m8v2_step0_reachability_2026-08-28.json"
STEP0_COMMIT = "c654f39"
RUNDIR = ROOT / "runs/m8v2_step05"

# §23 — STEP 0의 선택 규칙이 고른 trigger. 결과를 보고 바꾸지 않는다.
TRIGGER = {"family": "T2", "threshold": 0.7, "id": "T2@0.7"}

# §3 — 이 사유 하나만 고친다. validate_events는 elif 체인이라 이 사유로 기록됐다는
# 것은 **그 앞 검사는 통과했고 뒤 검사는 평가된 적이 없다**는 뜻이다. 그래서
# "고쳤다고 치고" 통과시키지 않고 실제 validator를 다시 태운다(§7).
ELIGIBLE_REASON = "too_many_evidence"
MAX_EVIDENCE = m8_report.MAX_EVIDENCE_PER_EVENT

# §5 — evidence-order audit 결과 고정된 단일 규칙. 여러 규칙을 시험하고 제일 좋은
# 것을 고르면 rule shopping이다.
#   · candidate에 명시적 score/rank 필드가 없다
#   · parse_events가 모델 출력 순서를 보존하고 rejected에 그 순서 그대로 저장된다
#     (accepted만 sorted 처리)
#   · 따라서 canonical order = 생성 순서. 앞 4개를 남긴다. GT와 무관하다.
TRUNCATION_RULE = "generation_order_first_4"

GO_MIN_RECOVERED = 5
GO_MIN_VIDEOS = 2
GO_MAX_VIDEO_SHARE = 0.60

BOUNDARY = {"new_labels": 0, "new_gt": 0, "generation_calls": 0, "llm_calls": 0,
            "gpu_required": False, "m8v1_verdict_changed": False,
            "round3": False, "m9_touched": False, "official_test_touched": False,
            "fresh_data": False, "pushed": False,
            "note": "evidence cap repair only — 재병합하지 않고 ADD-ONLY다"}


class Step05Error(RuntimeError):
    """전제가 안 맞으면 조용히 진행하지 않는다."""


# ── intervention ─────────────────────────────────────────────────────────
def eligible(rejected_record: dict) -> bool:
    return rejected_record.get("reason") == ELIGIBLE_REASON


def repair(cand: dict) -> dict:
    """**evidence cap repair only.** 원본을 변형하지 않고 사본을 낸다.

    GT를 인자로 받지 않는다 — 받는 순간 '잘 맞는 4개 고르기'가 가능해진다.
    """
    ev = list(cand.get("evidence_segments") or [])
    return {**cand, "evidence_segments": ev[:MAX_EVIDENCE],
            "rescue": {"rule": TRUNCATION_RULE, "original": ev,
                       "retained": ev[:MAX_EVIDENCE], "dropped": ev[MAX_EVIDENCE:]}}


def revalidate(repaired: dict, chunk: list):
    """현행 validator 그대로. relaxed validator를 만들지 않는다."""
    cand = {k: v for k, v in repaired.items() if k != "rescue"}
    kept, rej = m8_report.validate_events([cand], chunk)
    if kept:
        return "VALID", None, kept[0]
    return "STILL_REJECTED", rej[0]["reason"], None


def add_only(b0_events: list, rescued: list) -> list:
    """§8 — B0는 IMMUTABLE. 뒤에 붙이기만 한다.

    `merge_events`를 다시 돌리지 않는다. 돌리면 B0 event의 span이 움직여
    '기존 event 불변' 계약이 깨진다. 실제 파이프라인이라면 병합이 일부를 흡수했을
    수 있고, 그만큼 이 추정은 **추가 사건 수를 과대**로 본다(진단에 기록한다).
    """
    return [dict(e) for e in b0_events] + [dict(e) for e in rescued]


# ── GT 매칭 — 동결된 matcher 그대로 ──────────────────────────────────────
def newly_matched(refs: list, b0: list, r1: list) -> dict:
    """B0에서 미매칭이던 GT 중 R1에서 매칭된 것만 센다.

    새 임계·새 규칙·수동 매핑을 만들지 않는다. 전체 acceptance를 재평가하지 않는다.
    """
    m0, m1 = M.match_events(refs, b0), M.match_events(refs, r1)
    un0 = [i for i, j in m0.items() if j is None]
    new = [i for i in un0 if m1[i] is not None]
    return {"b0_unmatched_idx": un0, "newly_matched_idx": new,
            "n_b0_unmatched": len(un0), "n_newly_matched": len(new)}


# ── 패널 적재 ────────────────────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def triggered_chunks(video_id: str, report: dict, n_segments: int, cfg: dict) -> list:
    """STEP 0과 **같은 코드**로 발화 청크를 다시 구한다 — 손으로 옮겨 적지 않는다."""
    spans = S0.chunk_spans(n_segments, cfg["map_chunk_size"], cfg["map_chunk_overlap"])
    feats = S0.chunk_features(report, spans, cfg["seg_len_sec"])
    return [f for f in feats if S0.fires(f, TRIGGER)]


def chunk_candidates(report: dict, chunk_i: int, span) -> tuple:
    """청크의 **완전한** 후보를 복원한다.

    저장된 `rejected` 레코드는 `description`이 없고 `event`가 120자로 잘려 있어
    그대로는 재검증할 수 없다. `map_raw_outputs`를 다시 파싱해 원본 후보를 얻고,
    같은 validator를 태워 저장본과 대조한다(fail-closed).
    """
    raw = (report.get("map_raw_outputs") or [])[chunk_i]
    parsed = m8_report.parse_events(raw)
    synth = [{"idx": i} for i in range(span[0], span[1] + 1)]
    kept, rej = m8_report.validate_events(parsed, synth)
    stored = [r for r in (report.get("rejected") or []) if r.get("chunk") == chunk_i]
    if collections.Counter(r["reason"] for r in rej) != \
            collections.Counter(r["reason"] for r in stored):
        raise Step05Error(
            f"청크 {chunk_i}: 재파싱 결과가 저장된 거부와 다르다 — "
            f"재현 {collections.Counter(r['reason'] for r in rej)} vs "
            f"저장 {collections.Counter(r['reason'] for r in stored)}")
    return parsed, kept, rej, synth


def run(cfg: dict) -> dict:
    lineage = json.loads(
        (ROOT / "docs/finalization/m8_official_report_lineage_2026-08-27.json")
        .read_text(encoding="utf-8"))["report_sha256"]
    nseg = {r["video_id"]: r["n_segments"] for r in json.loads(
        (ROOT / "results/m8_official_0827/m8_official_full.json")
        .read_text(encoding="utf-8"))["per_video"]}

    audit, repairs, per_video = [], [], []
    for v in panel_videos():
        p = Path(common.work_dir(cfg, v)) / "report.json"
        if _sha(p) != lineage[v]:
            raise Step05Error(f"{v}: baseline 해시 불일치 — 공식 8편이 아니다")
        rep = json.loads(p.read_text(encoding="utf-8"))
        refs = reference_events(v)
        b0 = rep.get("events") or []
        rescued, still = [], []
        for f in triggered_chunks(v, rep, nseg[v], cfg):
            ci, span = f["chunk"], f["span"]
            parsed, kept, rej, synth = chunk_candidates(rep, ci, span)
            for k, r in enumerate(rej):
                # 재현된 거부 목록과 원본 후보를 사유·span으로 짝짓는다
                src = next((c for c in parsed
                            if (c.get("span") or []) == r["span"]
                            and (c.get("evidence_segments") or [])
                            == r["evidence_segments"]), None)
                row = {"video_id": v, "chunk": ci, "chunk_span": span,
                       "candidate": f"{v}#c{ci}#r{k}",
                       "reason": r["reason"],
                       "n_evidence": len(r["evidence_segments"]),
                       "span": r["span"], "eligible": eligible(r)}
                if not eligible(r) or src is None:
                    row["outcome"] = "NOT_ELIGIBLE" if src is not None else "UNRESOLVED"
                    audit.append(row)
                    continue
                fixed = repair(src)
                st, why, ev = revalidate(fixed, synth)
                row.update({"outcome": st, "still_rejected_reason": why,
                            "retained": fixed["rescue"]["retained"],
                            "dropped": fixed["rescue"]["dropped"]})
                audit.append(row)
                repairs.append(row)
                (rescued if st == "VALID" else still).append(ev if ev else row)
        r1 = add_only(b0, [e for e in rescued if isinstance(e, dict) and "span" in e])
        nm = newly_matched(refs, b0, r1)
        m1 = M.match_events(refs, r1)
        used = {j for j in m1.values() if j is not None}
        per_video.append({
            "video_id": v, "n_reference_events": len(refs),
            "n_b0_events": len(b0), "n_rescued_events": len(rescued),
            "n_still_rejected": len(still), "n_r1_events": len(r1),
            "inflation": round(len(r1) / len(b0), 4) if b0 else None,
            "rescued_unmatched": sum(1 for i in range(len(b0), len(r1))
                                     if i not in used),
            **nm})
    return {"audit": audit, "repairs": repairs, "per_video": per_video}


def summarize(per_video: list, audit: list) -> dict:
    rec = {v["video_id"]: v["n_newly_matched"] for v in per_video
           if v["n_newly_matched"]}
    total = sum(rec.values())
    m = {"newly_matched_gt": total,
         "out_of": sum(v["n_b0_unmatched"] for v in per_video),
         "videos_recovered": len(rec),
         "per_video": rec,
         "max_video_share": (round(max(rec.values()) / total, 4) if total else 0.0),
         "rescued_events": sum(v["n_rescued_events"] for v in per_video),
         "rescued_unmatched": sum(v["rescued_unmatched"] for v in per_video),
         "still_rejected": sum(v["n_still_rejected"] for v in per_video),
         "triggered_rejected_candidates": len(audit),
         "eligible_for_repair": sum(1 for a in audit if a["eligible"]),
         "multi_reason_or_other": sum(1 for a in audit if not a["eligible"]),
         "reason_breakdown": dict(collections.Counter(a["reason"] for a in audit))}
    return m


def go_verdict(m: dict) -> dict:
    failed = []
    if m["newly_matched_gt"] < GO_MIN_RECOVERED:
        failed.append("A_recovered>=5")
    if m["videos_recovered"] < GO_MIN_VIDEOS:
        failed.append("B_videos>=2")
    if m["max_video_share"] > GO_MAX_VIDEO_SHARE:
        failed.append("C_share<=0.60")
    return {"go": not failed, "failed": failed}


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default=str(RUNDIR))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    res = run(cfg)
    m = summarize(res["per_video"], res["audit"])
    verdict = go_verdict(m)
    prov = {"source_commit": _git("rev-parse", "HEAD"),
            "step0_commit": STEP0_COMMIT,
            "step0_artifact_sha256": _sha(STEP0_ARTIFACT),
            "trigger": TRIGGER, "eligible_reason": ELIGIBLE_REASON,
            "truncation_rule": TRUNCATION_RULE,
            "max_evidence_per_event": MAX_EVIDENCE,
            "matcher": "m8_metrics.match_events (frozen)",
            "boundary": BOUNDARY}

    common.atomic_write_json(out / "candidate_audit.json",
                             {"provenance": prov, "candidates": res["audit"]})
    common.atomic_write_json(out / "repair_results.json",
                             {"provenance": prov, "repairs": res["repairs"]})
    common.atomic_write_json(out / "gt_reachability.json",
                             {"provenance": prov, "per_video": res["per_video"]})
    common.atomic_write_json(out / "step05_summary.json",
                             {"provenance": prov, "metrics": m, **verdict})
    common.atomic_write_json(out / "step05_manifest.json", {
        "record": "M8-v2 STEP 0.5 — rejected-candidate rescue reachability pilot",
        "date": "2026-08-28", "doc": DOC, "provenance": prov,
        "gate": {"A_recovered>=": GO_MIN_RECOVERED,
                 "B_videos>=": GO_MIN_VIDEOS,
                 "C_max_share<=": GO_MAX_VIDEO_SHARE},
        "metrics": m, **verdict, "per_video": res["per_video"],
        "interpretation": (
            "PASS는 성능 개선이 아니라 fresh evaluation을 정당화할 structural "
            "recovery capacity를 뜻한다. FAIL은 선택된 low-coverage 영역에서 "
            "지배적 거부 기전을 결정적으로 복구해도 최소 recall 목표에 필요한 "
            "구조적 도달을 확보하지 못했다는 뜻이다."),
        "out_of_scope": (
            "softyeon_ceramics의 short-GT swallowing(미매칭 6건)은 accepted span "
            "coverage가 1.0이라 T2가 발화하지 않는다. 이번 intervention 대상이 "
            "아니며, 주장 범위는 rejection-heavy / low-coverage 모드로 제한된다."),
    })

    print(f"거부 후보 {m['triggered_rejected_candidates']} "
          f"(eligible {m['eligible_for_repair']} · 기타 {m['multi_reason_or_other']}) "
          f"— {m['reason_breakdown']}")
    print(f"복구 시도 {len(res['repairs'])} → VALID {m['rescued_events']} · "
          f"STILL_REJECTED {m['still_rejected']}")
    print(f"신규 매칭 GT {m['newly_matched_gt']} / {m['out_of']} · "
          f"영상 {m['videos_recovered']} · share {m['max_video_share']:.2f} · "
          f"{m['per_video']}")
    print(f"추가 사건 {m['rescued_events']} (그중 GT 미매칭 {m['rescued_unmatched']})")
    for v in res["per_video"]:
        if v["n_rescued_events"] or v["n_still_rejected"]:
            print(f"  {v['video_id']:24s} B0 {v['n_b0_events']:2d} → R1 "
                  f"{v['n_r1_events']:2d} · 회수 {v['n_newly_matched']} / "
                  f"미매칭 {v['n_b0_unmatched']}")
    print(f"\nSTEP 0.5: {'GO' if verdict['go'] else 'NO-GO'}"
          + (f" — 미충족 {', '.join(verdict['failed'])}" if verdict["failed"] else ""))
    print(f"산출물: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
