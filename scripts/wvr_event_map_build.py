"""EVENT_MAP_COVERAGE_SHADOW_V1 산출물 생성기 (2026-09-10).

사전등록: `docs/preregistration/WVR_EVENT_MAP_COVERAGE_SHADOW_V1_2026-09-10.md`

```
추론 없음 · GPU 없음 · 새 LLM 호출 없음. 기존 W01–W23 산출물을 읽기만 한다
생성    registry · coverage · candidate event map · chapter candidate · flow packet
금지    W00을 source로 쓰기 · synthetic event · silent concat ·
       raw artifact 수정 · semantic 최종 판정
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

import wvr_event_map_v1 as em                              # noqa: E402
import wvr_shadow_v1 as sh                                 # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_EVENT_MAP_COVERAGE_SHADOW_V1_2026-09-10.md")
SOURCE_MANIFEST = ("docs/preregistration/"
                   "WVR_EVENT_MAP_COVERAGE_SHADOW_V1_sources.json")
REGISTRY_NAME = "event_map_v1_registry.json"
COVERAGE_NAME = "event_map_v1_coverage.json"
CANDIDATE_NAME = "event_map_v1_candidate_map.json"
CHAPTER_NAME = "event_map_v1_chapter_candidates.json"
FLOW_NAME = "event_map_v1_flow_packet.md"
SUMMARY_NAME = "event_map_v1_summary.json"


class BuildError(RuntimeError):
    """생성 계약 위반."""


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


def load_sources(runs: Path) -> dict:
    """W01–W23 record를 읽고 해시를 모은다. W00은 무변경 확인만."""
    records, observed = {}, {}
    for window_id in em.VALID_SOURCE_WINDOWS:
        record_path = runs / ("%s_%s.json" % (sh.ARTIFACT_TAG, window_id))
        raw_path = runs / ("%s_%s_raw.txt" % (sh.ARTIFACT_TAG, window_id))
        if not record_path.is_file() or not raw_path.is_file():
            raise BuildError("source가 없다: %s" % window_id)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("event") != sh.EVENT:
            raise BuildError("SHADOW_V1 산출물이 아니다: %s" % record_path.name)
        record["source_record_sha256"] = sha256_file(record_path)
        records[window_id] = record
        observed[record_path.name] = record["source_record_sha256"]
        observed[raw_path.name] = sha256_file(raw_path)
    return {"records": records, "observed": observed}


def invalid_source_state(runs: Path) -> dict:
    rows = {}
    for window_id in em.INVALID_SOURCE_WINDOWS:
        path = runs / ("%s_%s.json" % (sh.ARTIFACT_TAG, window_id))
        record = json.loads(path.read_text(encoding="utf-8"))
        rows[window_id] = {
            "status": (record.get("validity") or {}).get("status"),
            "span": [record["window"]["start_sec"], record["window"]["end_sec"]],
            "record_sha256": sha256_file(path),
            "used_as_event_source": em.W00_AS_EVENT_SOURCE_ALLOWED,
            "rerun_allowed": em.W00_RERUN_ALLOWED,
        }
    return rows


def bank_times(runs: Path) -> list:
    path = runs / em.FRAME_BANK_MANIFEST
    if not path.is_file():
        return []
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return [round(float(row["time_sec"]), 3)
            for row in manifest.get("frames") or []]


def segment_status_at(coverage: dict, start: float, end: float) -> list:
    rows = [row["status"] for row in coverage["segments"]
            if row["start_sec"] < end and row["end_sec"] > start]
    return em.dedup(rows)


def flow_packet(groups, transitions, chapters, coverage, registry_rows,
                stamps) -> str:
    by_id = {row["event_id"]: row for row in registry_rows}
    lines = ["# EVENT_MAP_COVERAGE_SHADOW_V1 whole-video flow packet", "",
             "사전등록: `%s`" % PREREG, "",
             "```",
             "기존 SHADOW_V1의 23 VALID 창(W01–W23) event만으로 만든 후보다.",
             "W00 [0,48)은 INVALID source이므로 채우지 않고 남겨 뒀다.",
             "이것은 CANDIDATE_EVENT_MAP이고 verified factual Event Map이 아니다.",
             "relation·transition 라벨은 후보이며 판정 authority가 아니다.",
             "coverage percentage ≠ semantic correctness.",
             "reviewer 질문 Q1 FLOW_RECOVERABLE · Q2 GAP_MATERIALITY · "
             "Q3 EVENT_MAP_USABLE",
             "판정 어휘 EVENT_MAP_SHADOW_PASS / HOLD / INCONCLUSIVE — "
             "executor는 판정하지 않았다.",
             "```", "",
             "## coverage 요약", "", "```",
             "window coverage    %7.1f초  %5.2f%%"
             % (coverage["window_coverage_sec"],
                coverage["window_coverage_pct"]),
             "event coverage     %7.1f초  %5.2f%%"
             % (coverage["event_coverage_sec"],
                coverage["event_coverage_pct"]),
             "redundant (window) %7.1f초  %5.2f%%"
             % (coverage["redundant_window_coverage_sec"],
                coverage["redundant_window_coverage_pct"]),
             "redundant (event)  %7.1f초  %5.2f%%"
             % (coverage["redundant_event_coverage_sec"],
                coverage["redundant_event_coverage_pct"]),
             "unresolved         %7.1f초  %5.2f%%"
             % (coverage["unresolved_sec"], coverage["unresolved_pct"]),
             "```", "",
             "unresolved 구간:", "", "```"]
    lines += ["%6.1f – %6.1f초" % (row[0], row[1])
              for row in coverage["unresolved_intervals"]] or ["(없음)"]
    lines += ["```", "", "## chapter candidate별 흐름", ""]

    for chapter in chapters["chapters"]:
        chapter_groups = [group for group in groups
                          if group["group_id"] in chapter["group_ids"]]
        lines += ["### %s  %.1f – %.1f초  (%d group · 창 %s)"
                  % (chapter["chapter_id"], chapter["start_sec"],
                     chapter["end_sec"], chapter["group_count"],
                     ", ".join(chapter["source_windows"])), ""]
        signal = chapter["boundary_signal"]
        if isinstance(signal, dict):
            lines += ["```",
                      "boundary 신호  actor_changed=%s · sustained_content_change=%s"
                      % (signal["actor_changed"],
                         signal["sustained_content_change"]),
                      "```", ""]
        lines += ["```"]
        for group in chapter_groups:
            statuses = segment_status_at(coverage, group["start_sec"],
                                         group["end_sec"])
            frames = stamps.get(group["group_id"]) or []
            lines.append(
                "%6.1f–%6.1f | %-22s | %-12s | %-34s | %s | %s | frames %d"
                % (group["start_sec"], group["end_sec"],
                   group["actor"][:22], group["action"][:12],
                   group["object_or_state"][:34],
                   ",".join(group["source_windows"]),
                   "/".join(statuses), len(frames)))
            members = [by_id[event_id] for event_id in group["members"]]
            if len(members) > 1:
                lines.append("       members: %s"
                             % ", ".join("%s(%.0f–%.0f)"
                                         % (row["event_id"], row["start_sec"],
                                            row["end_sec"])
                                         for row in members))
        lines += ["```", ""]
        chapter_transitions = [row for row in transitions
                               if row["from_group"] in chapter["group_ids"]
                               and row["to_group"] in chapter["group_ids"]
                               and row["relation"] != em.SAME_EVENT]
        if chapter_transitions:
            lines += ["transition 후보:", "", "```"]
            lines += ["%6.1f초  %-22s  gap %.1f초  actor_changed=%s"
                      % (row["at_sec"], row["relation"], row["gap_sec"],
                         row["actor_changed"])
                      for row in chapter_transitions]
            lines += ["```", ""]

    lines += ["## chapter 경계 후보 (억제된 것 포함)", "", "```"]
    for signal in chapters["signals"]:
        if not signal["is_boundary_candidate"]:
            continue
        suppressed = any(row["group_id"] == signal["group_id"]
                         for row in chapters["suppressed"])
        lines.append("%6.1f초  %s  actor_changed=%s sustained=%s%s"
                     % (signal["at_sec"], signal["group_id"],
                        signal["actor_changed"],
                        signal["sustained_content_change"],
                        "  (MIN_CHAPTER_SEC로 억제)" if suppressed else ""))
    lines += ["```", "",
              "executor는 chapter 최종 경계·semantic 판정을 확정하지 않았다.", ""]
    return "\n".join(lines).rstrip() + "\n"


def build(runs: Path) -> dict:
    if em.NEW_INFERENCE_ALLOWED or em.SYNTHETIC_EVENT_ALLOWED:
        raise BuildError("새 추론·synthetic event는 금지돼 있다")
    sources = load_sources(runs)
    manifest = em.source_manifest(sources["observed"])
    if not manifest["unchanged"]:
        raise BuildError("source manifest가 동결값과 다르다: %s"
                         % manifest["manifest_sha256"])

    registry_rows = em.registry(sources["records"])
    relations = em.relation_candidates(registry_rows)
    groups = em.group_events(registry_rows, relations)
    transitions = em.group_transitions(groups)
    coverage = em.coverage_map(registry_rows)
    chapters = em.chapter_candidates(groups)
    bank = bank_times(runs)
    stamps = {group["group_id"]: em.frame_stamps(group["start_sec"],
                                                 group["end_sec"], bank)
              for group in groups}
    anomalies = em.anomalies(registry_rows, relations, groups, coverage)
    state = em.executor_state(registry_rows, groups, coverage)

    lineage = {
        "event": em.EVENT, "prereg": PREREG,
        "source_manifest_file": SOURCE_MANIFEST,
        "source_manifest": manifest,
        "derivation_script_commit": git_head(),
        "source_shadow_event": sh.EVENT,
        "source_records": {window_id: {
            "record_sha256": record["source_record_sha256"],
            "raw_output_hash": record.get("raw_output_hash"),
            "collapse_output_hash": record.get("collapse_output_hash"),
            "code_git_head": record.get("code_git_head"),
            "span": [record["window"]["start_sec"],
                     record["window"]["end_sec"]]}
            for window_id, record in sources["records"].items()},
        "video_sha256": next(iter({record.get("video_sha256")
                                   for record
                                   in sources["records"].values()})),
        "invalid_sources": invalid_source_state(runs),
        "new_inference_count": 0,
    }

    registry_doc = {
        "schema": "wvr_event_map_v1_registry", **lineage,
        "event_count": len(registry_rows),
        "events_per_window": {window_id: sum(
            1 for row in registry_rows if row["source_window"] == window_id)
            for window_id in em.VALID_SOURCE_WINDOWS},
        "events": registry_rows,
    }
    coverage_doc = {"schema": "wvr_event_map_v1_coverage", **lineage,
                    **coverage}
    candidate_doc = {
        "schema": "wvr_event_map_v1_candidate_map", **lineage,
        "artifact_name": em.ARTIFACT_NAME,
        "relation_role": em.RELATION_ROLE,
        "adjacent_window_pairs": em.adjacent_window_pairs(),
        "relation_count": len(relations),
        "relation_counts": {name: sum(1 for row in relations
                                      if row["relation"] == name)
                            for name in em.RELATIONS},
        "relations": relations,
        "group_count": len(groups), "groups": groups,
        "transitions": transitions,
        "frame_stamps": stamps,
        "frame_traceability_note": ("frame available = event supported로 "
                                    "판정하지 않는다"),
        "concat_fallback_allowed": em.CONCAT_FALLBACK_ALLOWED,
    }
    chapter_doc = {"schema": "wvr_event_map_v1_chapter_candidates", **lineage,
                   **chapters,
                   "chapter_count": len(chapters["chapters"]),
                   "chapter_frame_stamps": {
                       row["chapter_id"]: len(em.frame_stamps(
                           row["start_sec"], row["end_sec"], bank))
                       for row in chapters["chapters"]},
                   "chapter_unresolved_intervals": {
                       row["chapter_id"]: [
                           interval for interval
                           in coverage["unresolved_intervals"]
                           if interval[0] < row["end_sec"]
                           and interval[1] > row["start_sec"]]
                       for row in chapters["chapters"]},
                   "chapter_coverage_status": {
                       row["chapter_id"]: segment_status_at(
                           coverage, row["start_sec"], row["end_sec"])
                       for row in chapters["chapters"]}}
    summary_doc = {
        "schema": "wvr_event_map_v1_summary", **lineage,
        "executor_state": state,
        "inventory": {
            "total_windows": sh.EXPECTED_WINDOW_COUNT,
            "valid_source_windows": len(em.VALID_SOURCE_WINDOWS),
            "invalid_windows": len(em.INVALID_SOURCE_WINDOWS),
            "event_count": len(registry_rows),
            "group_count": len(groups),
            "chapter_candidate_count": len(chapters["chapters"]),
            "relation_counts": candidate_doc["relation_counts"],
        },
        "coverage": {key: coverage[key] for key in (
            "window_coverage_sec", "window_coverage_pct",
            "event_coverage_sec", "event_coverage_pct",
            "redundant_window_coverage_sec", "redundant_window_coverage_pct",
            "redundant_event_coverage_sec", "redundant_event_coverage_pct",
            "unresolved_sec", "unresolved_pct", "unresolved_intervals",
            "invalid_window_only_intervals", "status_seconds")},
        "anomalies": anomalies,
        "prior_state": em.PRIOR_STATE,
        "normative_authority": list(em.NORMATIVE_AUTHORITY),
        "blind_map_reveal_allowed": em.BLIND_MAP_REVEAL_ALLOWED,
        "note": ("deterministic post-processing이다. 새 추론·새 LLM 호출이 없고 "
                 "reviewer verdict를 계산하지 않았다."),
    }
    packet = flow_packet(groups, transitions, chapter_doc, coverage,
                         registry_rows, stamps)
    return {"registry": registry_doc, "coverage": coverage_doc,
            "candidate_map": candidate_doc, "chapters": chapter_doc,
            "summary": summary_doc, "packet": packet}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="event map 산출물 생성")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = build(runs)
    for name, key in ((REGISTRY_NAME, "registry"), (COVERAGE_NAME, "coverage"),
                      (CANDIDATE_NAME, "candidate_map"),
                      (CHAPTER_NAME, "chapters"), (SUMMARY_NAME, "summary")):
        (runs / name).write_text(
            json.dumps(built[key], ensure_ascii=False, indent=1),
            encoding="utf-8")
    (runs / FLOW_NAME).write_text(built["packet"], encoding="utf-8")

    summary = built["summary"]
    inventory, coverage = summary["inventory"], summary["coverage"]
    print("state=%s" % summary["executor_state"]["state"])
    print("windows=%s valid=%s invalid=%s events=%s groups=%s chapters=%s"
          % (inventory["total_windows"], inventory["valid_source_windows"],
             inventory["invalid_windows"], inventory["event_count"],
             inventory["group_count"], inventory["chapter_candidate_count"]))
    print("coverage window=%.1f초(%.2f%%) event=%.1f초(%.2f%%) "
          "redundant_event=%.1f초(%.2f%%) unresolved=%.1f초(%.2f%%)"
          % (coverage["window_coverage_sec"], coverage["window_coverage_pct"],
             coverage["event_coverage_sec"], coverage["event_coverage_pct"],
             coverage["redundant_event_coverage_sec"],
             coverage["redundant_event_coverage_pct"],
             coverage["unresolved_sec"], coverage["unresolved_pct"]))
    print("unresolved intervals=%s" % coverage["unresolved_intervals"])
    print("relations=%s" % inventory["relation_counts"])
    print("anomalies conflicts=%s unresolved_relations=%s "
          "single_window_only=%.1f초 mixed_groups=%s invalid_source_events=%s"
          % (summary["anomalies"]["conflicting_relation_count"],
             summary["anomalies"]["unresolved_relation_count"],
             summary["anomalies"]["single_window_only_sec"],
             len(summary["anomalies"]["mixed_signature_groups"]),
             len(summary["anomalies"]["invalid_source_dependencies"])))
    for row in built["chapters"]["chapters"]:
        print("  %s %6.1f-%6.1f groups=%2d windows=%s"
              % (row["chapter_id"], row["start_sec"], row["end_sec"],
                 row["group_count"], ",".join(row["source_windows"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
