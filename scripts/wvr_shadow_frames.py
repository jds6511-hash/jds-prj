"""SHADOW_V1 frame bank + 사전등록 7 overlap frame-audit 대지 (2026-09-09).

사전등록: `docs/preregistration/WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md`

```
추론 없음 · GPU 없음. inference 입력 경로를 바꾸지 않는다
bank      0,2,…,598초 300프레임 · 512×288 · 픽셀 sha256 전량 기록
PNG       사전등록 7 overlap의 공유 프레임(84장)만 저장한다 (저장소 크기 사유·사전 명시)
identity  window 실행이 실제로 먹인 픽셀 해시와 대조한다
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
import wvr_shadow_v1 as sh                                  # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md")
FRAME_DIR_NAME = "frames_shadow"
BANK_MANIFEST = "shadow_frame_bank.json"
AUDIT_MANIFEST = "shadow_frame_audit.json"
COLUMNS = 4
LABEL_HEIGHT = 26
PAD = 6


class FrameError(RuntimeError):
    """frame bank 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_times() -> dict:
    """사전등록 7 overlap의 공유 시각 (확장 금지)."""
    if sh.FRAME_AUDIT_EXPANSION_ALLOWED:
        raise FrameError("audit overlap 확장은 금지돼 있다")
    rows = {}
    for overlap_id in sh.AUDIT_OVERLAPS:
        overlap = sh.overlap_by_id(overlap_id)
        rows[overlap_id] = list(sh.shared_times(overlap))
    return rows


def sheet(frames, rows, out_path: Path) -> None:
    from PIL import Image, ImageDraw

    width, height = frames[0].size
    columns = min(COLUMNS, len(frames))
    lines = (len(frames) + columns - 1) // columns
    canvas = Image.new("RGB",
                       (columns * width + (columns + 1) * PAD,
                        lines * (height + LABEL_HEIGHT) + (lines + 1) * PAD),
                       (24, 24, 27))
    draw = ImageDraw.Draw(canvas)
    for index, (frame, row) in enumerate(zip(frames, rows)):
        column, line = index % columns, index // columns
        x = PAD + column * (width + PAD)
        y = PAD + line * (height + LABEL_HEIGHT + PAD)
        canvas.paste(frame, (x, y))
        draw.text((x + 4, y + height + 5),
                  "%.1fs  %s" % (row["time_sec"], row["pixel_sha256"][:10]),
                  fill=(250, 250, 250))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def window_frame_hashes(runs: Path) -> dict:
    """실행 산출물이 기록한 (시각 → 픽셀 해시) 표. identity 대조용."""
    table = {}
    for window in sh.windows():
        path = runs / ("%s_%s.json" % (sh.ARTIFACT_TAG, window["window_id"]))
        if not path.is_file():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        times = record.get("frame_times") or []
        hashes = record.get("frame_hashes") or []
        for time, digest in zip(times, hashes):
            table.setdefault(round(float(time), 3), {})[
                window["window_id"]] = digest
    return table


def build(video: Path, runs: Path) -> dict:
    frame_dir = runs / FRAME_DIR_NAME
    stamps = list(sh.bank_times())
    frames, indices, times, rate = probe.sample_frames(video, stamps)
    if len(frames) != sh.BANK_FRAME_COUNT:
        raise FrameError("bank 프레임 수가 %d가 아니다: %d"
                         % (sh.BANK_FRAME_COUNT, len(frames)))
    if list(frames[0].size) != [sh.FROZEN_FROM_SHORT_WINDOW["frame_width"],
                                sh.FROZEN_FROM_SHORT_WINDOW["frame_height"]]:
        raise FrameError("프레임 크기가 계약과 다르다: %r" % (frames[0].size,))

    audit = audit_times()
    audit_all = sorted({time for row in audit.values() for time in row})
    bank, by_time = [], {}
    for frame, stamp, index, decoded in zip(frames, stamps, indices, times):
        digest = sha256_bytes(frame.tobytes())
        row = {"time_sec": stamp, "frame_index": index,
               "decoded_time_sec": decoded, "pixel_sha256": digest,
               "png_persisted": stamp in audit_all}
        if row["png_persisted"]:
            path = frame_dir / ("F%06.1f.png" % stamp)
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.save(path)
            row["file"] = path.name
            row["png_sha256"] = sha256_file(path)
        bank.append(row)
        by_time[stamp] = (frame, row)

    identity = window_frame_hashes(runs)
    mismatches, checked = [], 0
    for row in bank:
        observed = identity.get(row["time_sec"]) or {}
        for window_id, digest in observed.items():
            checked += 1
            if digest != row["pixel_sha256"]:
                mismatches.append({"time_sec": row["time_sec"],
                                   "window_id": window_id,
                                   "bank_sha256": row["pixel_sha256"],
                                   "window_sha256": digest})

    sheets = {}
    for overlap_id, row_times in audit.items():
        picked = [by_time[time] for time in row_times]
        out = frame_dir / ("%s_shared_sheet.png" % overlap_id)
        sheet([frame for frame, _ in picked], [row for _, row in picked], out)
        sheets[overlap_id] = {"sheet": out.name, "sheet_sha256":
                              sha256_file(out),
                              "times": row_times,
                              "frames": [row for _, row in picked]}

    return {
        "bank": {
            "schema": "wvr_shadow_frame_bank_v1", "event": sh.EVENT,
            "prereg": PREREG, "code_git_head": git_head(),
            "video_sha256": sha256_file(video),
            "frame_size": [sh.FROZEN_FROM_SHORT_WINDOW["frame_width"],
                           sh.FROZEN_FROM_SHORT_WINDOW["frame_height"]],
            "sampling_fps": sh.SAMPLING_FPS, "decoded_fps": rate,
            "frame_count": len(bank), "frames": bank,
            "png_persisted_count": sum(1 for row in bank
                                       if row["png_persisted"]),
            "png_policy": ("사전등록 7 overlap의 공유 프레임만 PNG로 저장한다 — "
                           "300장 전량 PNG는 저장소 크기 때문에 남기지 않고, "
                           "픽셀 sha256은 300장 전량 기록한다"),
            "identity_checks": checked,
            "identity_mismatches": mismatches,
        },
        "audit": {
            "schema": "wvr_shadow_frame_audit_v1", "event": sh.EVENT,
            "prereg": PREREG,
            "audit_overlaps": list(sh.AUDIT_OVERLAPS),
            "stress": list(sh.AUDIT_STRESS), "control": list(sh.AUDIT_CONTROL),
            "expansion_allowed": sh.FRAME_AUDIT_EXPANSION_ALLOWED,
            "gate_scope": sh.GATE_SCOPE,
            "support_verdicts_by_executor": False,
            "sheets": sheets,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="shadow frame bank · audit")
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    video, runs = Path(args.video), Path(args.runs)
    if not video.is_file():
        raise FrameError("영상이 없다: %s" % video)
    built = build(video, runs)
    (runs / BANK_MANIFEST).write_text(
        json.dumps(built["bank"], ensure_ascii=False, indent=1),
        encoding="utf-8")
    (runs / AUDIT_MANIFEST).write_text(
        json.dumps(built["audit"], ensure_ascii=False, indent=1),
        encoding="utf-8")
    bank = built["bank"]
    print("bank frames=%s png=%s identity_checks=%s mismatches=%s"
          % (bank["frame_count"], bank["png_persisted_count"],
             bank["identity_checks"], len(bank["identity_mismatches"])))
    for overlap_id, row in built["audit"]["sheets"].items():
        print("  %s sheet=%s frames=%d" % (overlap_id, row["sheet"],
                                           len(row["frames"])))
    return 0 if not bank["identity_mismatches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
