"""CONSERVATIVE_EVENT_MAP_SHADOW_V1 생성기 (2026-09-10).

사전등록:
`docs/preregistration/WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1_2026-09-10.md`

```
입력   event_map_v1_registry.json · stitch_v1_verdicts.json ·
      stitch_v1_blind_map.json · shadow_frame_bank.json   (전부 해시 동결)
출력   conservative_event_map_v1{.json,.md,_chapter_input_packet.md,_summary.json}
계약   새 추론·새 LLM 호출 0회 · conflict 해결 금지 · event 유실 0 ·
      해시 drift·열린 플래그면 실행 거부
```

사용: `python scripts/wvr_cmap_build.py --runs runs/wvr_light_v1`
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_conservative_map_v1 as cm                         # noqa: E402
import wvr_shadow_v1 as sh                                   # noqa: E402
import wvr_stitch_v1 as st                                   # noqa: E402

REGISTRY_NAME = "event_map_v1_registry.json"
VERDICTS_NAME = "stitch_v1_verdicts.json"
MAPPING_NAME = "stitch_v1_blind_map.json"
BANK_NAME = "shadow_frame_bank.json"
REQUIRED_SOURCES = (REGISTRY_NAME, VERDICTS_NAME, MAPPING_NAME, BANK_NAME)
OPTIONAL_SOURCES = ("event_map_v1_coverage.json",)

MAP_NAME = "conservative_event_map_v1.json"
MAP_MD_NAME = "conservative_event_map_v1.md"
PACKET_NAME = "conservative_event_map_v1_chapter_input_packet.md"
SUMMARY_NAME = "conservative_event_map_v1_summary.json"


class BuildError(RuntimeError):
    """생성 계약 위반."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args) -> str:
    done = subprocess.run(["git"] + list(args), cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip()


def _load(runs: Path, name: str) -> dict:
    path = runs / name
    if not path.is_file():
        raise BuildError("입력 파일이 없다: %s" % name)
    return json.loads(path.read_text(encoding="utf-8"))


def assert_sources_frozen(runs: Path) -> dict:
    observed = {}
    for name in REQUIRED_SOURCES:
        path = runs / name
        if not path.is_file():
            raise BuildError("입력 파일이 없다: %s" % name)
        observed[name] = sha256_file(path)
        if observed[name] != cm.FROZEN_HASHES[name]:
            raise BuildError("동결 해시가 다르다 (%s): %s != %s"
                             % (name, observed[name],
                                cm.FROZEN_HASHES[name]))
    for name in OPTIONAL_SOURCES:
        path = runs / name
        if path.is_file():
            observed[name] = sha256_file(path)
            if observed[name] != cm.FROZEN_HASHES[name]:
                raise BuildError("동결 해시가 다르다 (%s)" % name)
    return observed


def assert_mapping_identity(mapping: dict) -> None:
    """revealed mapping의 창 쌍이 SHADOW_V1 기하와 같은지 확인한다."""
    rows = mapping.get("mapping") or {}
    expected = {row["overlap_id"]: {row["earlier"], row["later"]}
                for row in st.overlaps()}
    if set(rows) != set(expected):
        raise BuildError("mapping의 overlap 집합이 22개와 다르다")
    for overlap_id, pair in expected.items():
        if {rows[overlap_id]["A"], rows[overlap_id]["B"]} != pair:
            raise BuildError("mapping 창 쌍이 기하와 다르다: %s" % overlap_id)
        if rows[overlap_id]["start_sec"] != \
                sh.overlap_by_id(overlap_id)["start_sec"]:
            raise BuildError("mapping 구간이 기하와 다르다: %s" % overlap_id)


def build(runs: Path) -> dict:
    try:
        cm.assert_flags_closed()
    except cm.MapError as error:
        raise BuildError("%s" % error)
    if cm.NEW_INFERENCE_ALLOWED or cm.NEW_LLM_CALL_ALLOWED:
        raise BuildError("새 추론·LLM 호출은 금지돼 있다")
    if cm.CONFLICT_RESOLUTION_ALLOWED or cm.PREFERRED_SOURCE_ALLOWED:
        raise BuildError("conflict 해결·선호는 금지돼 있다")
    hashes = assert_sources_frozen(runs)
    registry = _load(runs, REGISTRY_NAME)
    verdicts = _load(runs, VERDICTS_NAME)
    mapping = _load(runs, MAPPING_NAME)
    bank = _load(runs, BANK_NAME)
    if registry.get("source_manifest", {}).get("unchanged") is not True:
        raise BuildError("registry의 source manifest가 drift했다")
    if registry.get("source_manifest", {}).get("manifest_sha256") \
            != cm.VALID_SOURCE_MANIFEST_SHA256:
        raise BuildError("source manifest 해시가 동결값과 다르다")
    if registry.get("video_sha256") != cm.VIDEO_SHA256:
        raise BuildError("video 해시가 동결값과 다르다")
    if registry.get("new_inference_count") != 0:
        raise BuildError("registry에 새 추론 기록이 있다")
    assert_mapping_identity(mapping)
    bank_times = tuple(row["time_sec"] for row in bank["frames"])
    if len(bank_times) != sh.BANK_FRAME_COUNT:
        raise BuildError("frame bank 크기가 %d가 아니다"
                         % sh.BANK_FRAME_COUNT)

    provenance = {
        "prereg": cm.PREREG,
        "event": cm.EVENT,
        "prereg_commit": _git("log", "-1", "--format=%H", "--",
                              cm.PREREG) or "unknown",
        "code_git_head": _git("rev-parse", "HEAD") or "unknown",
        "source_hashes": hashes,
        "source_manifest_sha256": cm.VALID_SOURCE_MANIFEST_SHA256,
        "source_registry_event_count": registry.get("event_count"),
        "source_shadow_event": registry.get("source_shadow_event"),
        "stitch_event": st.EVENT,
        "video_sha256": cm.VIDEO_SHA256,
        "new_inference_count": 0,
        "new_llm_call_count": 0,
        "gpu_used": False,
    }
    try:
        document = cm.build_document(registry["events"], verdicts, bank_times,
                                    provenance)
    except cm.MapError as error:
        raise BuildError("map 생성 계약 위반: %s" % error)
    return {"document": document,
            "summary": cm.summary_document(document),
            "markdown": cm.map_markdown(document),
            "packet": cm.chapter_input_packet(document)}


def write_artifacts(runs: Path, built: dict) -> list:
    written = []
    for name, payload in ((MAP_NAME, built["document"]),
                          (SUMMARY_NAME, built["summary"])):
        (runs / name).write_text(cm.canonical(payload) + "\n",
                                 encoding="utf-8")
        written.append(name)
    for name, text in ((MAP_MD_NAME, built["markdown"]),
                       (PACKET_NAME, built["packet"])):
        (runs / name).write_text(text, encoding="utf-8")
        written.append(name)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="conservative event map 생성")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    built = build(runs)
    counts = built["document"]["summary_counts"]
    print("regions=%d events=%d/%d missing=%d"
          % (counts["region_count"],
             built["summary"]["events_represented"],
             built["summary"]["source_events_total"],
             built["summary"]["events_missing"]))
    print("stitch_groups=%d (consensus=%d continuation=%d transition=%d) "
          "conflict_blocks=%d conflict_regions=%d single_source=%d gaps=%d"
          % (counts["stitch_group_count"], counts["consensus_event_count"],
             counts["continuation_group_count"], counts["transition_count"],
             counts["conflict_block_count"], counts["conflict_region_count"],
             counts["single_source_count"], counts["unresolved_gap_count"]))
    print("false_resolution=%d invalid_source_dependency=%d"
          % (counts["false_resolution_count"],
             counts["invalid_source_dependency_count"]))
    print("conflict=%.0fs stitchable=%.0fs single=%.0fs unresolved=%.0fs"
          % (built["summary"]["conflict_duration_sec"],
             built["summary"]["stitchable_duration_sec"],
             built["summary"]["single_source_duration_sec"],
             built["summary"]["unresolved_duration_sec"]))
    if args.dry_run:
        print("dry-run — 파일을 쓰지 않았다")
        return 0
    for name in write_artifacts(runs, built):
        print("wrote %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
