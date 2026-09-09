"""SUBDIVISION_RECOVERY_V1 요약 · 기술 게이트 · blinded overlap packet (2026-09-09).

사전등록: `docs/preregistration/WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md`

```
GPU 없음 · 추론 없음
기술 recovery 게이트만 계산한다. semantic verdict는 비워 둔다 (reviewer 전용)
packet     3/3 VALID(PASS)일 때만 생성한다 — FAIL·INCONCLUSIVE면 만들지 않는다
blinding   earlier/later를 prereg SHA 기반 결정적 규칙으로 Arm A/B로 가린다
비교        48초 W00과의 비교는 구조 항목만. semantic 우열 주장 없음
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

import wvr_shadow_v1 as sh                                  # noqa: E402
import wvr_subdivision_v1 as sd                             # noqa: E402
import wvr_w00_forensic as fx                               # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md")
SUMMARY_NAME = "subdiv_v1_summary.json"
PACKET_NAME = "subdiv_v1_overlap_packet.md"
MAPPING_NAME = "subdiv_v1_blind_map.json"
SHADOW_MAP_NAME = "shadow_v1_blind_map.json"


class SummaryError(RuntimeError):
    """요약 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_child(runs: Path, child_id: str) -> dict:
    path = runs / ("%s_%s.json" % (sd.ARTIFACT_TAG, child_id))
    if not path.is_file():
        raise SummaryError("산출물이 없다: %s" % path.name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != sd.EVENT:
        raise SummaryError("subdivision 산출물이 아니다: %s" % path.name)
    return record


def raw_structure(record: dict, runs: Path) -> dict:
    """구조 요약. record에 없으면 보존된 raw 파일에서 사후 계산한다.

    추론을 다시 하지 않는다 — raw는 파싱 전에 저장된 원문 그대로다.
    """
    structure = record.get("structure")
    if structure:
        return {**structure, "structure_source": "record"}
    raw_path = runs / (record.get("raw_path") or "")
    if not record.get("raw_persisted") or not raw_path.is_file():
        return {"structure_source": "UNAVAILABLE"}
    return {**fx.raw_structure(raw_path.read_text(encoding="utf-8")),
            "structure_source": "raw_file_post_hoc",
            "raw_file_sha256": sha256_file(raw_path)}


def child_row(record: dict, runs: Path) -> dict:
    metrics = record.get("metrics") or {}
    shape = record.get("representation") or {}
    parsed = record.get("parsed") or {}
    validity = record.get("validity") or {}
    structure = raw_structure(record, runs)
    lineage = record.get("lineage") or {}
    return {
        "child_id": record["child"]["child_id"],
        "start_sec": record["child"]["start_sec"],
        "end_sec": record["child"]["end_sec"],
        "frames": metrics.get("delivered_frame_count"),
        "frame_times": record.get("frame_times"),
        "input_tokens": metrics.get("input_token_count"),
        "video_tokens": metrics.get("video_token_count"),
        "generated_tokens": metrics.get("generated_token_count"),
        "generation_cap_hit": metrics.get("generation_cap_hit"),
        "finish_reason": record.get("finish_reason"),
        "raw_chars": structure.get("raw_length"),
        "raw_event_count": len(parsed.get("events", [])),
        "completed_object_count": structure.get("complete_object_count"),
        "collapsed_event_count": shape.get("collapsed_event_count"),
        "unique_signature_count": shape.get("unique_signature_count"),
        "raw_unique_signature_count": structure.get("unique_signature_count"),
        "zero_duration_count": structure.get("zero_length_interval_count"),
        "max_signature_repeat": structure.get("max_signature_repeat"),
        "json_complete": structure.get("json_parse_ok"),
        "positive_duration_count": (
            structure["complete_object_count"]
            - structure["zero_length_interval_count"]
            if structure.get("complete_object_count") is not None
            and structure.get("zero_length_interval_count") is not None
            else None),
        "first_repeat": structure.get("first_repeat"),
        "top_signatures": structure.get("top_signatures"),
        "structure_source": structure.get("structure_source"),
        "degenerate": shape.get("degenerate"),
        "parse_status": parsed.get("status"),
        "language_satisfied": (validity.get("language") or {}).get("satisfied"),
        "raw_persisted": record.get("raw_persisted"),
        "arm_status": record.get("arm_status"),
        "valid": validity.get("valid"),
        "status": validity.get("status"),
        "reasons": validity.get("reasons"),
        "blockers": validity.get("blockers"),
        "output_failures": validity.get("output_failures"),
        "lineage_checked": lineage.get("checked"),
        "lineage_mismatches": len(lineage.get("mismatches") or []),
        "raw_output_hash": record.get("raw_output_hash"),
        "parsed_output_hash": record.get("parsed_output_hash"),
        "collapse_output_hash": record.get("collapse_output_hash"),
        "runtime_config_hash": record.get("runtime_config_hash"),
        "prompt_hash": record.get("prompt_hash"),
        "infer_wall_sec": metrics.get("infer_wall_sec"),
        "peak_vram_allocated_mib": metrics.get("peak_vram_allocated_mib"),
        "code_git_head": record.get("code_git_head"),
    }


def frame_tables(records: dict) -> dict:
    rows = {}
    for child_id, record in records.items():
        times = [round(float(time), 3)
                 for time in (record.get("frame_times") or [])]
        rows[child_id] = dict(zip(times, record.get("frame_hashes") or []))
    return rows


def parent_row(runs: Path) -> dict:
    """원본 48초 W00 record에서 구조 항목만 읽는다 (수정하지 않는다)."""
    path = runs / sd.ORIGINAL_RECORD
    if not path.is_file():
        return {"available": False}
    record = json.loads(path.read_text(encoding="utf-8"))
    metrics = record.get("metrics") or {}
    raw_path = runs / sd.ORIGINAL_RAW
    structure = fx.raw_structure(raw_path.read_text(encoding="utf-8")) \
        if raw_path.is_file() else {}
    validity = record.get("validity") or {}
    completed = structure.get("complete_object_count")
    zero = structure.get("zero_length_interval_count")
    return {
        "available": True, "window_id": sd.PARENT_WINDOW_ID,
        "start_sec": record["window"]["start_sec"],
        "end_sec": record["window"]["end_sec"],
        "frames": metrics.get("delivered_frame_count"),
        "input_tokens": metrics.get("input_token_count"),
        "generated_tokens": metrics.get("generated_token_count"),
        "generation_cap_hit": metrics.get("generation_cap_hit"),
        "raw_chars": structure.get("raw_length"),
        "completed_object_count": completed,
        "raw_unique_signature_count": structure.get("unique_signature_count"),
        "zero_duration_count": zero,
        "positive_duration_count": (completed - zero
                                    if completed is not None
                                    and zero is not None else None),
        "max_signature_repeat": structure.get("max_signature_repeat"),
        "json_complete": structure.get("json_parse_ok"),
        "status": validity.get("status"),
        "reasons": validity.get("reasons"),
        "raw_output_hash_file": sha256_file(raw_path) if raw_path.is_file()
        else None,
        "record_sha256": sha256_file(path),
    }


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


def packet_lines(packets) -> str:
    lines = ["# SUBDIVISION_RECOVERY_V1 blinded overlap packet", "",
             "사전등록: `%s`" % PREREG, "",
             "```",
             "24초 child 분해에서 나온 두 overlap이다. 각 overlap의 두 출력은",
             "Arm A · Arm B로 가려져 있고 어느 쪽이 앞선 child인지는 판정 전까지",
             "공개되지 않는다. event는 overlap 범위로 clip해 보여주며 원본 구간은",
             "산출물에 보존돼 있다.",
             "판정값 STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED",
             "frame audit 어휘 SUPPORTED · PARTIALLY_SUPPORTED · UNSUPPORTED ·",
             "                FRAMES_INSUFFICIENT",
             "executor는 어느 판정도 하지 않았다.",
             "```", ""]
    for packet in packets:
        lines += ["## %s  %.0f–%.0f초  (frame audit 대상)"
                  % (packet["overlap_id"], packet["start_sec"],
                     packet["end_sec"]), "",
                  "```",
                  "공유 프레임 %d개  %s"
                  % (len(packet["shared_times"]),
                     ", ".join("%.0f초" % time
                               for time in packet["shared_times"])),
                  "공유 프레임 픽셀 identity  %s"
                  % ("일치" if packet["identity_ok"] else "불일치 — 기술적 INVALID"),
                  "```", ""]
        for label in ("A", "B"):
            rows = packet["arms"][label]
            lines += ["### Arm %s" % label, "", "```"]
            lines += ["%6.1f–%6.1f | %s | %s | %s%s"
                      % (row["clipped_start"], row["clipped_end"],
                         row["actor"], row["action"], row["object_or_state"],
                         "  (clipped)" if row["clipped"] else "")
                      for row in rows] or ["(겹치는 event 없음)"]
            lines += ["```", ""]
    return "\n".join(lines).rstrip() + "\n"


def build(runs: Path, prereg_sha: str) -> dict:
    records = {child_id: load_child(runs, child_id)
               for child_id in sd.CHILD_IDS}
    rows = [child_row(records[child_id], runs) for child_id in sd.CHILD_IDS]
    tables = frame_tables(records)
    identity = sd.shared_frame_identity(tables)

    video_shas = {record.get("video_sha256") for record in records.values()}
    extra_blockers = []
    if len(video_shas) != 1:
        extra_blockers.append(sh.PROVENANCE_MISMATCH)
    prompt_hashes = {record.get("prompt_hash") for record in records.values()}
    runtime_hashes = {record.get("runtime_config_hash")
                      for record in records.values()}
    if len(prompt_hashes) != 1 or len(runtime_hashes) != 1:
        extra_blockers.append(sd.CONFIG_MISMATCH)
    for record in records.values():
        change = record.get("inference_config_change") or {}
        if change.get("inference_config_change") != "NONE" \
                or not change.get("geometry_as_declared"):
            extra_blockers.append(sd.CONFIG_MISMATCH)
        if not (record.get("original_w00_unchanged") or {}).get("unchanged"):
            extra_blockers.append("ORIGINAL_W00_CHANGED")
        lineage = record.get("lineage") or {}
        if lineage.get("mismatches"):
            extra_blockers.append("LINEAGE_PIXEL_MISMATCH")

    verdict = sd.recovery_verdict(rows, identity, sd.dedup(extra_blockers))
    coverage = sd.coverage()

    packets, mapping = [], {}
    if verdict["packet_generation_allowed"]:
        for overlap in sd.overlaps():
            overlap_id = overlap["overlap_id"]
            pairs = clipped_pairs(records, overlap)
            labels = {role: sd.blind_label(overlap_id, role, prereg_sha)
                      for role in ("earlier", "later")}
            if set(labels.values()) != {"A", "B"}:
                raise SummaryError("A/B 배정이 깨졌다: %s" % overlap_id)
            mapping[overlap_id] = {
                labels["earlier"]: overlap["earlier"],
                labels["later"]: overlap["later"],
                "start_sec": overlap["start_sec"],
                "end_sec": overlap["end_sec"]}
            packets.append({
                "overlap_id": overlap_id,
                "start_sec": overlap["start_sec"],
                "end_sec": overlap["end_sec"],
                "shared_times": list(sd.shared_times(overlap)),
                "arms": {labels["earlier"]: pairs["earlier"],
                         labels["later"]: pairs["later"]},
                "identity_ok": next(row["identity_ok"] for row in identity
                                    if row["overlap_id"] == overlap_id),
            })

    shadow_map = runs / SHADOW_MAP_NAME
    summary = {
        "schema": "wvr_subdivision_v1_summary", "event": sd.EVENT,
        "prereg": PREREG, "code_git_head": git_head(),
        "prereg_sha_used_for_blinding": prereg_sha,
        "parent_window": sd.parent_window(),
        "coverage": coverage,
        "architecture_change": sd.ARCHITECTURE_CHANGE,
        "child_count": len(rows), "children": rows,
        "overlap_identity": identity,
        "shared_frames_per_overlap": sd.SHARED_FRAMES_PER_OVERLAP,
        "recovery_gate": verdict,
        "extra_blockers": sd.dedup(extra_blockers),
        "parent_comparison": sd.parent_comparison(parent_row(runs), rows),
        "prior_state": sd.PRIOR_STATE,
        "normative_authority": list(sd.NORMATIVE_AUTHORITY),
        "branches": sd.BRANCHES,
        "branch_execution_allowed": sd.BRANCH_EXECUTION_ALLOWED,
        "shadow_v1_blind_map_sha256": (sha256_file(shadow_map)
                                       if shadow_map.is_file() else None),
        "shadow_v1_blind_map_reveal_allowed": sd.MAPPING_REVEAL_ALLOWED,
        "packet_generated": bool(packets),
        "note": ("기술 recovery 게이트만 계산했다. 두 overlap semantic 판정과 "
                 "frame support 판정은 reviewer 전용이다."),
    }
    built = {"summary": summary}
    if packets:
        built["packet"] = packet_lines(packets)
        built["mapping"] = {
            "event": sd.EVENT, "prereg_sha": prereg_sha,
            "prereg_sha_sha256": hashlib.sha256(
                prereg_sha.encode("utf-8")).hexdigest(),
            "mapping": mapping,
            "reveal_allowed_before_verdict": sd.MAPPING_REVEAL_ALLOWED,
            "note": ("절차적 blinding이다 — 산출물 파일명이 child id를 담고 있어 "
                     "저장소에서 mapping을 복원할 수 있다. packet만 읽는다는 "
                     "규율에 의존한다.")}
    return built


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="subdivision 요약·packet")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--prereg-sha", required=True)
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = build(runs, args.prereg_sha)
    (runs / SUMMARY_NAME).write_text(
        json.dumps(built["summary"], ensure_ascii=False, indent=1),
        encoding="utf-8")
    if "packet" in built:
        (runs / PACKET_NAME).write_text(built["packet"], encoding="utf-8")
        (runs / MAPPING_NAME).write_text(
            json.dumps(built["mapping"], ensure_ascii=False, indent=1),
            encoding="utf-8")

    gate = built["summary"]["recovery_gate"]
    print("recovery_verdict=%s reason=%s valid=%d/%d"
          % (gate["recovery_verdict"], gate["reason"],
             gate["valid_child_count"], gate["expected_child_count"]))
    print("blockers=%s invalid=%s packet=%s"
          % (gate["blockers"] or "없음", gate["invalid_children"] or "없음",
             built["summary"]["packet_generated"]))
    for row in built["summary"]["children"]:
        print("  %s %3.0f-%3.0f frames=%s in=%s gen=%s cap=%s raw=%s coll=%s "
              "uniq=%s zero=%s json=%s %s"
              % (row["child_id"], row["start_sec"], row["end_sec"],
                 row["frames"], row["input_tokens"], row["generated_tokens"],
                 row["generation_cap_hit"], row["raw_event_count"],
                 row["collapsed_event_count"], row["unique_signature_count"],
                 row["zero_duration_count"], row["json_complete"],
                 row["status"]))
    for row in built["summary"]["overlap_identity"]:
        print("  %s %3.0f-%3.0f shared=%s/%s mismatch=%s identity_ok=%s"
              % (row["overlap_id"], row["start_sec"], row["end_sec"],
                 row["shared_observed"], row["shared_expected"],
                 len(row["pixel_hash_mismatches"]), row["identity_ok"]))
    return 0 if gate["recovery_verdict"] == sd.RECOVERY_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
