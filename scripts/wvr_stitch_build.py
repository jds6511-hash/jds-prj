"""STITCHING_SHADOW_V1 blinded overlap packet 생성기 (2026-09-10).

사전등록:
`docs/preregistration/WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md`

```
추론 없음 · GPU 없음 · 새 LLM 호출 없음. registry(160 event)를 읽기만 한다
생성    22 overlap의 arm sequence · blinded packet · mapping(봉인) · audit 지표
금지    판정 채우기 · 임계 도입 · Event Map 재생성 · mapping 조기 reveal
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
import wvr_stitch_v1 as st                                 # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md")
REGISTRY_NAME = "event_map_v1_registry.json"
PAIRS_NAME = "stitch_v1_pairs.json"
PACKET_NAME = "stitch_v1_packet.md"
MAPPING_NAME = "stitch_v1_blind_map.json"
AUDIT_NAME = "stitch_v1_audit.json"
SUMMARY_NAME = "stitch_v1_summary.json"


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


def load_registry(runs: Path) -> dict:
    path = runs / REGISTRY_NAME
    if not path.is_file():
        raise BuildError("registry가 없다: %s" % REGISTRY_NAME)
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("event") != em.EVENT:
        raise BuildError("EVENT_MAP registry가 아니다: %s" % path.name)
    if not (registry.get("source_manifest") or {}).get("unchanged"):
        raise BuildError("registry의 source manifest가 동결값과 다르다")
    if registry.get("new_inference_count") != 0:
        raise BuildError("registry에 새 추론 기록이 있다")
    events = registry.get("events") or []
    if any(row["source_window"] in st.INVALID_SOURCE_WINDOWS
           for row in events):
        raise BuildError("invalid source event가 registry에 있다")
    registry["registry_sha256"] = sha256_file(path)
    return registry


def build(runs: Path, prereg_sha: str) -> dict:
    if st.NEW_INFERENCE_ALLOWED or st.NEW_LLM_CALL_ALLOWED:
        raise BuildError("새 추론·새 LLM 호출은 금지돼 있다")
    if st.EVENT_MAP_REBUILD_ALLOWED or st.ADJUDICATED_MAP_BUILD_ALLOWED:
        raise BuildError("Event Map 재생성·Adjudicated Map 생성은 금지돼 있다")
    registry = load_registry(runs)
    events = registry["events"]
    by_window = {}
    for row in events:
        by_window.setdefault(row["source_window"], []).append(row)

    pairs, audits, mapping, packets = [], [], {}, []
    for overlap in st.overlaps():
        overlap_id = overlap["overlap_id"]
        earlier_rows = st.clip_sequence(by_window.get(overlap["earlier"], []),
                                        overlap)
        later_rows = st.clip_sequence(by_window.get(overlap["later"], []),
                                      overlap)
        labels = {role: st.blind_label(overlap_id, role, prereg_sha)
                  for role in ("earlier", "later")}
        if set(labels.values()) != {"A", "B"}:
            raise BuildError("A/B 배정이 깨졌다: %s" % overlap_id)
        shared = list(st.shared_times(overlap))
        arm_rows = {labels["earlier"]: earlier_rows,
                    labels["later"]: later_rows}
        audit = st.pair_audit(arm_rows["A"], arm_rows["B"])
        # blind 산출물에는 창 id·event id를 남기지 않는다 (봉인 파일에만 둔다)
        blind_rows, id_map = {}, {}
        for label in ("A", "B"):
            blind_rows[label] = []
            for index, row in enumerate(arm_rows[label]):
                local_id = "%s_%s%02d" % (overlap_id, label, index + 1)
                id_map[local_id] = {"event_id": row["event_id"],
                                    "source_window": row["source_window"]}
                blind_rows[label].append({
                    "local_id": local_id,
                    "original_start": row["original_start"],
                    "original_end": row["original_end"],
                    "clipped_start": row["clipped_start"],
                    "clipped_end": row["clipped_end"],
                    "clipped": row["clipped"], "actor": row["actor"],
                    "action": row["action"],
                    "object_or_state": row["object_or_state"]})
        audit["overlap_id"] = overlap_id
        audit["shared_frame_times"] = shared
        audits.append(audit)
        mapping[overlap_id] = {labels["earlier"]: overlap["earlier"],
                               labels["later"]: overlap["later"],
                               "start_sec": overlap["start_sec"],
                               "end_sec": overlap["end_sec"],
                               "local_id_map": id_map}
        pairs.append({
            "overlap_id": overlap_id,
            "start_sec": overlap["start_sec"], "end_sec": overlap["end_sec"],
            "shared_frame_times": shared,
            "shared_frame_count": len(shared),
            "arms": blind_rows,
            "arm_event_counts": {label: len(blind_rows[label])
                                 for label in ("A", "B")},
            "comparison_unit": st.COMPARISON_UNIT,
        })
        packets.append({"overlap_id": overlap_id,
                        "start_sec": overlap["start_sec"],
                        "end_sec": overlap["end_sec"],
                        "shared": shared, "arms": blind_rows})

    lineage = {
        "event": st.EVENT, "prereg": PREREG,
        "prereg_sha_used_for_blinding": prereg_sha,
        "derivation_script_commit": git_head(),
        "registry_source": REGISTRY_NAME,
        "registry_sha256": registry["registry_sha256"],
        "registry_event_count": registry["event_count"],
        "source_manifest_sha256":
            registry["source_manifest"]["manifest_sha256"],
        "video_sha256": registry["video_sha256"],
        "source_shadow_event": sh.EVENT,
        "new_inference_count": 0, "new_llm_call_count": 0,
    }
    state = st.executor_state(pairs, audits)

    lines = ["# STITCHING_SHADOW_V1 blinded overlap packet", "",
             "사전등록: `%s`" % PREREG, "",
             "```",
             "인접 창의 공유 24초 overlap 22개다. 각 overlap의 두 창 출력은",
             "Arm A · Arm B로 가려져 있고 어느 쪽이 앞선 창인지는 판정 기록 전까지",
             "공개되지 않는다. event는 공유 구간으로 clip해 보여주며 원본 구간도 함께 적었다.",
             "",
             "비교 단위는 event 한 줄이 아니라 **overlap 안의 event sequence 전체**다.",
             "판정 기준은 문자열 일치가 아니라 report-material contradiction이다.",
             "  예) 자른다 vs 섞는다 → 연속 행동일 수 있다",
             "      요리한다 vs 옷을 재봉한다 (같은 시각) → material conflict",
             "",
             "relation 어휘   SAME_EVENT · CONTINUATION · TRANSITION · CONFLICT ·",
             "               UNRESOLVED",
             "상위 판정        STITCHABLE · MATERIAL_CONFLICT · UNRESOLVED",
             "executor는 어느 판정도 채우지 않았다.",
             "```", ""]
    for packet in packets:
        lines += ["## %s  %.0f–%.0f초  (공유 프레임 %d개: %s)"
                  % (packet["overlap_id"], packet["start_sec"],
                     packet["end_sec"], len(packet["shared"]),
                     ", ".join("%.0f" % time for time in packet["shared"])),
                  ""]
        for label in ("A", "B"):
            rows = packet["arms"][label]
            lines += ["### Arm %s  (event %d개)" % (label, len(rows)), "",
                      "```"]
            lines += ["%6.1f–%6.1f | %-20s | %-14s | %s%s"
                      % (row["clipped_start"], row["clipped_end"],
                         row["actor"], row["action"], row["object_or_state"],
                         "   (원본 %.1f–%.1f)"
                         % (row["original_start"], row["original_end"])
                         if row["clipped"] else "")
                      for row in rows] or ["(겹치는 event 없음)"]
            lines += ["```", ""]

    summary = {
        "schema": "wvr_stitch_v1_summary", **lineage,
        "executor_state": state,
        "overlap_count": len(pairs),
        "arm_event_total": sum(sum(row["arm_event_counts"].values())
                               for row in pairs),
        "audit_totals": {
            "exact_signature_pairs": sum(row["exact_signature_pair_count"]
                                         for row in audits),
            "pairwise_relations": {
                name: sum(row["pairwise_relation_counts"].get(name, 0)
                          for row in audits)
                for name in ("SEMANTICALLY_EQUIVALENT",
                             "SEMANTICALLY_DIFFERENT",
                             "ADJUDICATION_REQUIRED")},
            "overlaps_with_zero_shared_tokens": [
                row["overlap_id"] for row in audits
                if row["shared_token_count"] == 0],
            "overlaps_with_empty_arm": [
                row["overlap_id"] for row in audits
                if row["arm_a_event_count"] == 0
                or row["arm_b_event_count"] == 0],
            "max_event_count_difference": max(
                (row["event_count_difference"] for row in audits),
                default=0),
        },
        "prior_state": st.PRIOR_STATE,
        "normative_authority": list(st.NORMATIVE_AUTHORITY),
        "mapping_sealed": True,
        "mapping_reveal_before_verdicts_allowed":
            st.MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED,
        "note": ("blinded packet과 audit 지표만 만들었다. relation·상위 판정·최종 "
                 "verdict는 reviewer 전용이다."),
    }
    return {
        "pairs": {"schema": "wvr_stitch_v1_pairs", **lineage,
                  "overlap_count": len(pairs), "pairs": pairs},
        "audit": {"schema": "wvr_stitch_v1_audit", **lineage,
                  "role": st.AUDIT_ROLE, "threshold_used": False,
                  "overlaps": audits},
        "mapping": {"schema": "wvr_stitch_v1_blind_map", **lineage,
                    "prereg_sha_sha256": hashlib.sha256(
                        prereg_sha.encode("utf-8")).hexdigest(),
                    "mapping": mapping,
                    "reveal_allowed_before_verdicts":
                        st.MAPPING_REVEAL_BEFORE_VERDICTS_ALLOWED,
                    "note": ("local_id → 실제 event id·창 id 대응은 이 파일에만 "
                             "있다. 절차적 blinding이다 — 저장소에서 복원 가능하므로 "
                             "packet만 읽는다는 규율에 의존한다. 모든 22 overlap "
                             "판정 기록 전에는 reveal하지 않는다.")},
        "summary": summary,
        "packet": "\n".join(lines).rstrip() + "\n",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="stitching packet 생성")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--prereg-sha", required=True)
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = build(runs, args.prereg_sha)
    for name, key in ((PAIRS_NAME, "pairs"), (AUDIT_NAME, "audit"),
                      (MAPPING_NAME, "mapping"), (SUMMARY_NAME, "summary")):
        (runs / name).write_text(
            json.dumps(built[key], ensure_ascii=False, indent=1),
            encoding="utf-8")
    (runs / PACKET_NAME).write_text(built["packet"], encoding="utf-8")

    summary = built["summary"]
    totals = summary["audit_totals"]
    print("state=%s overlaps=%s arm_events=%s"
          % (summary["executor_state"]["state"], summary["overlap_count"],
             summary["arm_event_total"]))
    print("audit exact_pairs=%s relations=%s zero_shared_tokens=%s "
          "empty_arm=%s max_count_diff=%s"
          % (totals["exact_signature_pairs"], totals["pairwise_relations"],
             totals["overlaps_with_zero_shared_tokens"] or "없음",
             totals["overlaps_with_empty_arm"] or "없음",
             totals["max_event_count_difference"]))
    for row in built["audit"]["overlaps"]:
        print("  %s %5.0f-%5.0f  Arm A/B events %d/%d  exact %d  "
              "shared_tokens %d"
              % (row["overlap_id"],
                 next(pair["start_sec"] for pair in built["pairs"]["pairs"]
                      if pair["overlap_id"] == row["overlap_id"]),
                 next(pair["end_sec"] for pair in built["pairs"]["pairs"]
                      if pair["overlap_id"] == row["overlap_id"]),
                 row["arm_a_event_count"], row["arm_b_event_count"],
                 row["exact_signature_pair_count"],
                 row["shared_token_count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
