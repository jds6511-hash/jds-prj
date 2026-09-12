"""WVR_CHUNK_OVERVIEW_V2 — gate G1~G10 + §7 계측.

사전등록: `docs/preregistration/WVR_CHUNK_OVERVIEW_V2_C02_C05_2026-09-13.md`

**canary(C02) 후, 그리고 각 chunk 후 다시 돌린다.** 하나라도 FAIL이면 종료 코드 1로
멈춘다 — 다음 chunk를 실행하지 않는다.

gate는 **기술적 완주 여부만** 본다. 관찰 내용의 품질은 gate가 아니고, 이 스크립트는
어떤 품질 판정도 하지 않는다(사전등록 §11).

    python scripts/wvr_chunk_overview_v2_gate.py --chunk C02
    python scripts/wvr_chunk_overview_v2_gate.py --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_chunk_overview_v2 as cv  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402

RUNS_ROOT = ROOT / "runs" / "wvr_chunk_overview_v2"
C01_RUNS = ROOT / "runs" / "wvr_video_overview_preview_v2"
SUMMARY_FIELDS = ("BROAD_ACTIVITY", "OBSERVED_CHANGE",
                  "CONTEXT_INFERENCE", "UNCERTAINTY")
OK_STATUS = "GENERATED / REVIEW_REQUESTED"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def gate_chunk(chunk_id: str) -> dict:
    run = RUNS_ROOT / chunk_id
    checks: list[dict] = []

    def check(cid: str, desc: str, ok: bool, detail=None) -> bool:
        checks.append({"id": cid, "desc": desc,
                       "result": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    record_path = run / ov.RECORD_NAME
    result_path = run / ov.RESULT_NAME
    if not record_path.is_file():
        check("G1", "execution record 존재", False, str(record_path))
        return {"chunk_id": chunk_id, "gate": "FAIL", "checks": checks}

    record = jload(record_path)
    geometry = cv.plan_geometry(chunk_id)
    expected_windows = geometry["window_count"]

    check("G1", "status == GENERATED / REVIEW_REQUESTED",
          record.get("status") == OK_STATUS, record.get("status"))
    check("G2", "segment_count · segment_inference_count == 창 수",
          record.get("segment_count") == expected_windows
          and record.get("segment_inference_count") == expected_windows,
          {"segment_count": record.get("segment_count"),
           "segment_inference_count": record.get("segment_inference_count"),
           "expected": expected_windows})
    check("G3", "inference_count == 창 수 + 1 (chunk 합성 1회)",
          record.get("inference_count") == expected_windows + 1,
          record.get("inference_count"))

    prov = record.get("runtime_provenance") or {}
    check("G4", "runtime — 동결 모델·revision · bfloat16 · sdpa · 4090",
          prov.get("effective_model_id") == ov.MODEL_ID
          and prov.get("effective_model_revision") == ov.MODEL_REVISION
          and str(prov.get("effective_dtype", "")).lower().endswith("bfloat16")
          and str(prov.get("attn_implementation", "")).lower() == "sdpa"
          and "4090" in str(prov.get("device_name", "")),
          {k: prov.get(k) for k in ("effective_model_id", "effective_model_revision",
                                    "effective_dtype", "attn_implementation",
                                    "device_name")})

    summaries = jload(run / ov.SUMMARIES_NAME) if (run / ov.SUMMARIES_NAME).is_file() \
        else []
    fields_ok = (len(summaries) == expected_windows
                 and all(all(f in s for f in SUMMARY_FIELDS) for s in summaries))
    check("G5", "summary 개수 == 창 수 · 4개 필드 전부 보유", fields_ok,
          {"count": len(summaries)})

    labels = [label for s in summaries for label in s.get("BROAD_ACTIVITY", [])]
    stray = sorted(set(labels) - set(ov.ACTIVITY_LABELS))
    check("G6", "BROAD_ACTIVITY label이 동결 집합 안에 있다", not stray, stray)

    plan = jload(run / ov.PLAN_NAME) if (run / ov.PLAN_NAME).is_file() else []
    plan_ok = (plan == cv.segments(chunk_id))
    check("G7", "창 시각이 사전등록 §3 표와 일치", plan_ok,
          {"first": plan[0] if plan else None,
           "last": plan[-1] if plan else None} if plan else None)

    check("G8", "video_sha256 == 동결 원본",
          record.get("video_sha256") == cv.VIDEO_SHA256, record.get("video_sha256"))

    c01_hashes = {p.name: sha(p) for p in sorted(C01_RUNS.glob("*"))
                  if p.is_file()} if C01_RUNS.is_dir() else {}
    check("G9", "C01 산출물 존재 · 파일 수 불변(읽기 전용)",
          len(c01_hashes) > 0, {"file_count": len(c01_hashes)})

    forbidden = [ROOT / "results" / "eval_test.json", ROOT / "src" / "m9_report_eval.py"]
    base = run.stat().st_mtime
    touched = [str(p.relative_to(ROOT)) for p in forbidden
               if p.exists() and p.stat().st_mtime > base]
    check("G10", "official test 경로 미접근 · M9 미호출", not touched, touched)

    # ── §7 계측 (판정 아님) ────────────────────────────────────────
    metrics = record.get("runtime_metrics") or {}
    per_seg = metrics.get("segments") or []
    walls = sorted(float(s.get("infer_wall_sec", 0.0)) for s in per_seg)
    label_counts: dict[str, int] = {}
    for label in labels:
        label_counts[label] = label_counts.get(label, 0) + 1

    measurement = {
        "chunk_id": chunk_id,
        "geometry": geometry,
        "elapsed_sec": record.get("elapsed_sec"),
        "retry_count": record.get("retry_count"),
        "resumed_existing_segment_raw_count":
            record.get("resumed_existing_segment_raw_count"),
        "original_error": record.get("original_error"),
        "inference_count": record.get("inference_count"),
        "peak_vram_allocated_mib": metrics.get("peak_vram_allocated_mib"),
        "peak_vram_reserved_mib": metrics.get("peak_vram_reserved_mib"),
        "infer_wall_sec": ({"min": walls[0], "max": walls[-1],
                            "mean": round(sum(walls) / len(walls), 3)}
                           if walls else None),
        "input_tokens_total": sum(int(s.get("input_tokens", 0)) for s in per_seg),
        "output_tokens_total": sum(int(s.get("output_tokens", 0)) for s in per_seg),
        "broad_activity_label_counts": label_counts,
        "observed_change_count": sum(len(s.get("OBSERVED_CHANGE", []))
                                     for s in summaries),
        "context_inference_count": sum(len(s.get("CONTEXT_INFERENCE", []))
                                       for s in summaries),
        "uncertainty_count": sum(len(s.get("UNCERTAINTY", []))
                                 for s in summaries),
        "empty_broad_activity_windows": sum(1 for s in summaries
                                            if not s.get("BROAD_ACTIVITY")),
        "result_status": (jload(result_path).get("status")
                          if result_path.is_file() else None),
    }

    gate = "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL"
    return {"chunk_id": chunk_id, "gate": gate, "checks": checks,
            "measurement": measurement}


def whole_video_coverage() -> dict:
    """C01~C05 창이 원본 2424.186485초 중 얼마를 덮는지. 판정하지 않는다."""
    spans = []
    for chunk_id in cv.EXPECTED_WINDOW_COUNT:
        rows = cv.windows(chunk_id)
        spans.append([rows[0]["start_sec"], rows[-1]["end_sec"]])
    merged: list[list[float]] = []
    for span in sorted(spans):
        if merged and span[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], span[1])
        else:
            merged.append(list(span))
    covered = round(sum(e - s for s, e in merged), 6)
    overlaps = [round(a["end_sec"] - b["start_sec"], 6)
                for a, b in zip(cv.chunk_plan(), cv.chunk_plan()[1:])]
    return {
        "video_duration_sec": cv.VIDEO_DURATION_SEC,
        "covered_sec": covered,
        "uncovered_sec": round(cv.VIDEO_DURATION_SEC - covered, 6),
        "merged_spans": merged,
        "chunk_pair_overlap_sec": overlaps,
        "window_total": sum(cv.EXPECTED_WINDOW_COUNT.values()),
        "chunk_ids_with_summaries": [
            c for c in cv.EXPECTED_WINDOW_COUNT
            if (c == "C01" and (C01_RUNS / ov.SUMMARIES_NAME).is_file())
            or (RUNS_ROOT / c / ov.SUMMARIES_NAME).is_file()],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk", choices=list(cv.EXECUTED_CHUNK_IDS))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    targets = list(cv.EXECUTED_CHUNK_IDS) if args.all else [args.chunk]
    if not targets or targets == [None]:
        parser.error("--chunk 또는 --all 이 필요하다")
    targets = [c for c in targets if (RUNS_ROOT / c / ov.RECORD_NAME).is_file()]
    if not targets:
        print("실행된 chunk가 없다")
        return 1

    rows = [gate_chunk(c) for c in targets]
    overall = "PASS" if all(r["gate"] == "PASS" for r in rows) else "FAIL"

    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    (RUNS_ROOT / "chunk_gate.json").write_text(
        json.dumps({"event": cv.EVENT, "prereg": cv.PREREG,
                    "code_git_head": git_head(), "gate": overall,
                    "chunks": rows}, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    payload = {"event": cv.EVENT, "prereg": cv.PREREG,
               "status": "EXECUTED / REVIEW_PENDING",
               "note": ("관측값만 적는다. 관찰 품질 PASS·재실행 여부·"
                        "merge 방식은 executor가 판단하지 않는다 (§11)."),
               "chunks": {r["chunk_id"]: r["measurement"] for r in rows}}
    if args.all:
        payload["whole_video"] = whole_video_coverage()
    (RUNS_ROOT / "measurements.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")

    for row in rows:
        print(f"--- {row['chunk_id']}  {row['gate']}")
        for c in row["checks"]:
            mark = "" if c["result"] == "PASS" else f"   <- {c['detail']}"
            print(f"  {c['id']:4s} {c['result']:4s}  {c['desc']}{mark}")
    print(f"\nCHUNK GATE: {overall}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
