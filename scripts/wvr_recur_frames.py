"""RECURSIVE_SUBDIVISION_RECOVERY_V1 frame audit 대지 — 두 overlap의 공유 프레임.

사전등록:
`docs/preregistration/WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1_2026-09-09.md`

```
추론 없음 · GPU 없음. inference 입력 경로를 바꾸지 않는다
대상      RR-O1 [6,12) → 6,8,10 · RR-O2 [12,18) → 12,14,16 (각 3장)
픽셀      512×288 model-input 그대로. 라벨은 프레임 밖 여백에 쓴다(픽셀 미변경)
게이트    technical recovery PASS일 때만 생성한다
identity  child 실행이 실제로 먹인 픽셀 해시와 대조한다
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_capacity_probe as probe                          # noqa: E402
import wvr_recursive_v1 as rc                               # noqa: E402
import wvr_shadow_frames as fb                              # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1_2026-09-09.md")
FRAME_DIR_NAME = "frames_recur"
AUDIT_MANIFEST = "recur_v1_frame_audit.json"
SUMMARY_NAME = "recur_v1_summary.json"


class FrameError(RuntimeError):
    """frame audit 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def gate(runs: Path) -> dict:
    """PASS가 아니면 만들지 않는다 (사전등록 §13·§14)."""
    path = runs / SUMMARY_NAME
    if not path.is_file():
        raise FrameError("요약이 없다 — 먼저 게이트를 계산한다: %s" % path.name)
    summary = json.loads(path.read_text(encoding="utf-8"))
    verdict = (summary.get("recovery_gate") or {}).get("recovery_verdict")
    if verdict != rc.RECOVERY_PASS:
        raise FrameError("technical recovery가 PASS가 아니다(%s) — "
                         "frame packet을 만들지 않는다" % verdict)
    return summary


def child_frame_hashes(runs: Path) -> dict:
    table = {}
    for child_id in rc.CHILD_IDS:
        path = runs / ("%s_%s.json" % (rc.ARTIFACT_TAG, child_id))
        if not path.is_file():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        for time, digest in zip(record.get("frame_times") or [],
                                record.get("frame_hashes") or []):
            table.setdefault(round(float(time), 3), {})[child_id] = digest
    return table


def build(video: Path, runs: Path) -> dict:
    summary = gate(runs)
    audit = rc.audit_times()
    stamps = sorted({time for row in audit.values() for time in row})
    frames, indices, times, rate = probe.sample_frames(video, stamps)
    if len(frames) != len(stamps):
        raise FrameError("프레임 수가 %d가 아니다: %d" % (len(stamps), len(frames)))
    if list(frames[0].size) != [rc.FROZEN_FROM_C0["frame_width"],
                                rc.FROZEN_FROM_C0["frame_height"]]:
        raise FrameError("프레임 크기가 계약과 다르다: %r" % (frames[0].size,))

    frame_dir = runs / FRAME_DIR_NAME
    identity = child_frame_hashes(runs)
    by_time, rows, mismatches, checked = {}, [], [], 0
    for frame, stamp, index, decoded in zip(frames, stamps, indices, times):
        digest = sha256_bytes(frame.tobytes())
        path = frame_dir / ("R%06.1f.png" % stamp)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.save(path)
        row = {"time_sec": stamp, "frame_index": index,
               "decoded_time_sec": decoded, "pixel_sha256": digest,
               "file": path.name, "png_sha256": fb.sha256_file(path)}
        for child_id, child_digest in (identity.get(stamp) or {}).items():
            checked += 1
            if child_digest != digest:
                mismatches.append({"time_sec": stamp, "child_id": child_id,
                                   "sheet_sha256": digest,
                                   "child_sha256": child_digest})
        rows.append(row)
        by_time[stamp] = (frame, row)

    sheets = {}
    for overlap_id, row_times in audit.items():
        picked = [by_time[time] for time in row_times]
        out = frame_dir / ("%s_shared_sheet.png" % overlap_id)
        fb.sheet([frame for frame, _ in picked],
                 [row for _, row in picked], out)
        sheets[overlap_id] = {"sheet": out.name,
                              "sheet_sha256": fb.sha256_file(out),
                              "times": row_times,
                              "frames": [row for _, row in picked]}

    return {
        "schema": "wvr_recursive_v1_frame_audit", "event": rc.EVENT,
        "prereg": PREREG, "code_git_head": git_head(),
        "recovery_verdict": (summary.get("recovery_gate") or {}).get(
            "recovery_verdict"),
        "video_sha256": fb.sha256_file(video),
        "frame_size": [rc.FROZEN_FROM_C0["frame_width"],
                       rc.FROZEN_FROM_C0["frame_height"]],
        "sampling_fps": rc.SAMPLING_FPS, "decoded_fps": rate,
        "audit_overlaps": list(rc.AUDIT_OVERLAPS),
        "expansion_allowed": rc.FRAME_AUDIT_EXPANSION_ALLOWED,
        "frame_count": len(rows), "frames": rows,
        "annotation_policy": ("라벨은 프레임 아래 여백에만 그린다 — "
                              "512×288 원본 픽셀을 덮지 않는다"),
        "identity_checks": checked, "identity_mismatches": mismatches,
        "support_verdicts_by_executor": False,
        "support_verdict_vocabulary": list(rc.SUPPORT_VERDICTS),
        "sheets": sheets,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="recursive frame audit 대지")
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    video, runs = Path(args.video), Path(args.runs)
    if not video.is_file():
        raise FrameError("영상이 없다: %s" % video)
    built = build(video, runs)
    (runs / AUDIT_MANIFEST).write_text(
        json.dumps(built, ensure_ascii=False, indent=1), encoding="utf-8")
    print("frames=%s identity_checks=%s mismatches=%s"
          % (built["frame_count"], built["identity_checks"],
             len(built["identity_mismatches"])))
    for overlap_id, row in built["sheets"].items():
        print("  %s sheet=%s frames=%d" % (overlap_id, row["sheet"],
                                           len(row["frames"])))
    return 0 if not built["identity_mismatches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
