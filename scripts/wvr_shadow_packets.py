"""SHADOW_V1 요약 · blinded overlap packet · matcher audit (2026-09-09).

사전등록: `docs/preregistration/WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md`

```
GPU 없음 · 추론 없음
기술 게이트만 계산한다. semantic verdict는 비워 둔다 (reviewer 전용)
blinding    earlier/later를 prereg SHA 기반 결정적 규칙으로 Arm A/B로 가린다
matcher     4초/8초 시간 매처는 AUDIT_DIAGNOSTIC_ONLY로만 기록한다
```
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_density as density                               # noqa: E402
import wvr_density_v2 as v2                                 # noqa: E402
import wvr_shadow_v1 as sh                                  # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md")
SUMMARY_NAME = "shadow_v1_summary.json"
PACKET_NAME = "shadow_v1_overlap_packet.md"
MAPPING_NAME = "shadow_v1_blind_map.json"
MATCHER_NAME = "shadow_v1_matcher_audit.json"

# packet에 넣지 않는 것 (source window를 드러낸다)
LEAKING_FIELDS = ("earlier", "later", "window_id", "source_window",
                  "original_event_id")


class PacketError(RuntimeError):
    """packet 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def load_window(runs: Path, window_id: str) -> dict:
    path = runs / ("%s_%s.json" % (sh.ARTIFACT_TAG, window_id))
    if not path.is_file():
        raise PacketError("산출물이 없다: %s" % path.name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != sh.EVENT:
        raise PacketError("SHADOW 산출물이 아니다: %s" % path.name)
    return record


def window_row(record: dict) -> dict:
    metrics = record.get("metrics") or {}
    shape = record.get("representation") or {}
    parsed = record.get("parsed") or {}
    validity = record.get("validity") or {}
    return {
        "window_id": record["window"]["window_id"],
        "start_sec": record["window"]["start_sec"],
        "end_sec": record["window"]["end_sec"],
        "frames": metrics.get("delivered_frame_count"),
        "input_tokens": metrics.get("input_token_count"),
        "generated_tokens": metrics.get("generated_token_count"),
        "generation_cap_hit": metrics.get("generation_cap_hit"),
        "finish_reason": record.get("finish_reason"),
        "raw_event_count": len(parsed.get("events", [])),
        "collapsed_event_count": shape.get("collapsed_event_count"),
        "unique_signature_count": shape.get("unique_signature_count"),
        "degenerate": shape.get("degenerate"),
        "parse_status": parsed.get("status"),
        "language_satisfied": (validity.get("language") or {}).get("satisfied"),
        "raw_persisted": record.get("raw_persisted"),
        "arm_status": record.get("arm_status"),
        "valid": validity.get("valid"),
        "status": validity.get("status"),
        "reasons": validity.get("reasons"),
        "raw_output_hash": record.get("raw_output_hash"),
        "parsed_output_hash": record.get("parsed_output_hash"),
        "collapse_output_hash": record.get("collapse_output_hash"),
        "runtime_config_hash": record.get("runtime_config_hash"),
        "infer_wall_sec": metrics.get("infer_wall_sec"),
        "peak_vram_allocated_mib": metrics.get("peak_vram_allocated_mib"),
    }


def overlap_identity(records: dict) -> list:
    """공유 시각 12개와 그 픽셀 해시가 두 창에서 동일한지 확인한다."""
    rows = []
    for overlap in sh.overlaps():
        earlier = records[overlap["earlier"]]
        later = records[overlap["later"]]
        shared = list(sh.shared_times(overlap))
        table = {}
        for record in (earlier, later):
            times = [round(float(time), 3)
                     for time in (record.get("frame_times") or [])]
            hashes = record.get("frame_hashes") or []
            table[record["window"]["window_id"]] = dict(zip(times, hashes))
        earlier_map = table[overlap["earlier"]]
        later_map = table[overlap["later"]]
        missing = [time for time in shared
                   if time not in earlier_map or time not in later_map]
        mismatched = [time for time in shared
                      if time in earlier_map and time in later_map
                      and earlier_map[time] != later_map[time]]
        rows.append({
            "overlap_id": overlap["overlap_id"],
            "start_sec": overlap["start_sec"], "end_sec": overlap["end_sec"],
            "shared_expected": sh.SHARED_FRAMES_PER_OVERLAP,
            "shared_observed": len(shared) - len(missing),
            "missing_times": missing, "pixel_hash_mismatches": mismatched,
            "identity_ok": not missing and not mismatched,
        })
    return rows


def clipped_pairs(records: dict, overlap: dict) -> dict:
    earlier = (records[overlap["earlier"]].get("parsed") or {}).get(
        "collapsed") or []
    later = (records[overlap["later"]].get("parsed") or {}).get(
        "collapsed") or []
    return {
        "earlier": sh.clip_sequence(earlier, overlap["start_sec"],
                                    overlap["end_sec"]),
        "later": sh.clip_sequence(later, overlap["start_sec"],
                                  overlap["end_sec"]),
    }


def matcher_audit(pairs: dict) -> dict:
    """4초/8초 시간 매처 — AUDIT_DIAGNOSTIC_ONLY."""
    reference = [{"index": i, "start_sec": row["clipped_start"],
                  "end_sec": row["clipped_end"], "actor": row["actor"],
                  "action": row["action"],
                  "object_or_state": row["object_or_state"]}
                 for i, row in enumerate(pairs["earlier"])]
    arm = [{"index": i, "start_sec": row["clipped_start"],
            "end_sec": row["clipped_end"], "actor": row["actor"],
            "action": row["action"],
            "object_or_state": row["object_or_state"]}
           for i, row in enumerate(pairs["later"])]
    per_tolerance = {}
    for tolerance in density.MATCH_TOLERANCE_SEC:
        alignment = v2.align(reference, arm, tolerance)
        per_tolerance["tol_%.1f" % tolerance] = {
            "temporally_compatible_count":
                alignment["temporally_compatible_count"],
            "equivalent_count": alignment["equivalent_count"],
            "adjudication_count": alignment["adjudication_count"],
            "earlier_without_equivalent":
                len(alignment["reference_without_equivalent"]),
            "later_without_equivalent":
                len(alignment["arm_without_equivalent"]),
            "merge_candidates": len(alignment["merge_candidates"]),
            "split_candidates": len(alignment["split_candidates"]),
            "order_inversions": alignment["order_inversions"],
        }
    return {"role": sh.AUTOMATIC_MATCHER_ROLE, "per_tolerance": per_tolerance}


def build(runs: Path, prereg_sha: str) -> dict:
    records = {row["window_id"]: load_window(runs, row["window_id"])
               for row in sh.windows()}
    rows = [window_row(records[row["window_id"]]) for row in sh.windows()]
    identity = overlap_identity(records)
    failures = [row["overlap_id"] for row in identity
                if not row["identity_ok"]]
    gate = sh.technical_gate(rows, failures)

    mapping, packets, matcher = {}, [], {}
    for overlap in sh.overlaps():
        overlap_id = overlap["overlap_id"]
        pairs = clipped_pairs(records, overlap)
        labels = {role: sh.blind_label(overlap_id, role, prereg_sha)
                  for role in ("earlier", "later")}
        if set(labels.values()) != {"A", "B"}:
            raise PacketError("A/B 배정이 깨졌다: %s" % overlap_id)
        mapping[overlap_id] = {
            labels["earlier"]: overlap["earlier"],
            labels["later"]: overlap["later"],
            "start_sec": overlap["start_sec"], "end_sec": overlap["end_sec"],
        }
        packets.append({
            "overlap_id": overlap_id, "start_sec": overlap["start_sec"],
            "end_sec": overlap["end_sec"],
            "arms": {labels["earlier"]: pairs["earlier"],
                     labels["later"]: pairs["later"]},
            "identity_ok": next(row["identity_ok"] for row in identity
                                if row["overlap_id"] == overlap_id),
            "audit_overlap": overlap_id in sh.AUDIT_OVERLAPS,
        })
        matcher[overlap_id] = matcher_audit(pairs)

    lines = ["# SHADOW_V1 blinded overlap packet", "",
             "사전등록: `%s`" % PREREG, "",
             "```",
             "23개 인접 overlap. 각 overlap의 두 출력은 Arm A · Arm B로 가려져 있다.",
             "어느 쪽이 앞선 창인지는 reviewer 판정 전까지 공개되지 않는다.",
             "event는 overlap 범위로 clip해 보여주며 원본 구간은 산출물에 보존돼 있다.",
             "판정값 STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED",
             "자동 매처는 AUDIT_DIAGNOSTIC_ONLY다 — 판정 authority가 아니다.",
             "```", ""]
    for packet in packets:
        lines += ["## %s  %.0f–%.0f초%s"
                  % (packet["overlap_id"], packet["start_sec"],
                     packet["end_sec"],
                     "  (frame-audit overlap)" if packet["audit_overlap"]
                     else ""), ""]
        if not packet["identity_ok"]:
            lines += ["```", "공유 프레임 identity 실패 — 기술적으로 INVALID",
                      "```", ""]
        for label in ("A", "B"):
            rows_out = packet["arms"][label]
            lines += ["### Arm %s" % label, "", "```"]
            lines += ["%6.1f–%6.1f | %s | %s | %s%s"
                      % (row["clipped_start"], row["clipped_end"],
                         row["actor"], row["action"], row["object_or_state"],
                         "  (clipped)" if row["clipped"] else "")
                      for row in rows_out] or ["(겹치는 event 없음)"]
            lines += ["```", ""]

    summary = {
        "schema": "wvr_shadow_v1_summary", "event": sh.EVENT, "prereg": PREREG,
        "code_git_head": git_head(), "prereg_sha_used_for_blinding": prereg_sha,
        "window_count": len(rows), "overlap_count": len(identity),
        "windows": rows, "overlap_identity": identity,
        "technical_gate": gate,
        "semantic_verdict": None,
        "semantic_verdict_by_executor": sh.SEMANTIC_VERDICT_BY_EXECUTOR,
        "gate_scope": sh.GATE_SCOPE,
        "allowed_max_conclusion": sh.ALLOWED_MAX_CONCLUSION,
        "forbidden_conclusions": list(sh.FORBIDDEN_CONCLUSIONS),
        "event_map_production_approved": sh.EVENT_MAP_PRODUCTION_APPROVED,
        "stitching_production_allowed": sh.STITCHING_PRODUCTION_ALLOWED,
        "note": ("기술 게이트만 계산했다. 23 overlap semantic 판정과 7 frame-audit "
                 "support 판정은 reviewer 전용이다."),
    }
    return {
        "summary": summary, "packet": "\n".join(lines).rstrip() + "\n",
        "mapping": {"event": sh.EVENT, "prereg_sha": prereg_sha,
                    "prereg_sha_sha256": hashlib.sha256(
                        prereg_sha.encode("utf-8")).hexdigest(),
                    "mapping": mapping,
                    "note": ("절차적 blinding이다 — 산출물 파일명이 창 id를 담고 "
                             "있으므로 저장소에서 mapping을 복원할 수 있다. "
                             "packet만 읽는다는 규율에 의존한다.")},
        "matcher": {"event": sh.EVENT, "role": sh.AUTOMATIC_MATCHER_ROLE,
                    "tolerances": list(density.MATCH_TOLERANCE_SEC),
                    "overlaps": matcher,
                    "note": "semantic·materiality·PASS 계산 authority가 아니다."},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="shadow 요약·overlap packet")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--prereg-sha", required=True)
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = build(runs, args.prereg_sha)
    (runs / SUMMARY_NAME).write_text(
        json.dumps(built["summary"], ensure_ascii=False, indent=1),
        encoding="utf-8")
    (runs / PACKET_NAME).write_text(built["packet"], encoding="utf-8")
    (runs / MAPPING_NAME).write_text(
        json.dumps(built["mapping"], ensure_ascii=False, indent=1),
        encoding="utf-8")
    (runs / MATCHER_NAME).write_text(
        json.dumps(built["matcher"], ensure_ascii=False, indent=1),
        encoding="utf-8")

    gate = built["summary"]["technical_gate"]
    print("technical_verdict=%s reasons=%s" % (gate["technical_verdict"],
                                               gate["reasons"] or "없음"))
    print("invalid_windows=%s identity_failures=%s"
          % (gate["invalid_windows"] or "없음",
             gate["overlap_identity_failures"] or "없음"))
    for row in built["summary"]["windows"]:
        print("  %s %3.0f-%3.0f frames=%s in=%s gen=%s raw=%s coll=%s uniq=%s "
              "%s" % (row["window_id"], row["start_sec"], row["end_sec"],
                      row["frames"], row["input_tokens"],
                      row["generated_tokens"], row["raw_event_count"],
                      row["collapsed_event_count"],
                      row["unique_signature_count"], row["status"]))
    return 0 if gate["technical_verdict"] == sh.TECHNICAL_OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
