"""FRAME_ADJUDICATION_V1 packet — KEEP·DROP 프레임 실물 추출 (2026-09-09).

사전등록: `docs/preregistration/WVR_FRAME_ADJUDICATION_V1_2026-09-09.md`

```
추론 없음 · GPU 없음 · 프레임 추출과 대지(contact sheet) 조립만 한다
프레임    모델이 실제로 받은 것과 같은 512×288 (probe.sample_frames 경로 동일)
표시      각 프레임에 시각과 KEEP·DROP만 적는다 — 주장 문구는 대지에 넣지 않는다
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
import wvr_frame_adjudication as fa                         # noqa: E402
import wvr_short_window as sw                               # noqa: E402

PREREG = "docs/preregistration/WVR_FRAME_ADJUDICATION_V1_2026-09-09.md"
PACKET_NAME = "frame_adjudication_packet.md"
MANIFEST_NAME = "frame_adjudication_manifest.json"
FRAME_DIR_NAME = "frames_adjudication"
COLUMNS = 4
LABEL_HEIGHT = 26
PAD = 6


class PacketError(RuntimeError):
    """packet 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_frames(frames, rows, question_id: str) -> None:
    """개수와 크기를 계약과 대조한다 (모델이 받은 512×288과 같아야 한다)."""
    if len(frames) != len(rows):
        raise PacketError("프레임 수가 맞지 않는다: %s (%d != %d)"
                          % (question_id, len(frames), len(rows)))
    for frame in frames:
        if list(frame.size) != [fa.FRAME_WIDTH, fa.FRAME_HEIGHT]:
            raise PacketError("프레임 크기가 계약과 다르다: %r" % (frame.size,))


def claims_for(runs: Path, question: dict) -> dict:
    """해당 구간과 겹치는 두 arm의 frozen collapsed event를 원문 그대로 싣는다."""
    rows = {}
    for arm in sw.ARMS:
        path = runs / ("%s_%s_%s.json" % (sw.ARTIFACT_TAG,
                                          question["parent_window"], arm))
        record = json.loads(path.read_text(encoding="utf-8"))
        collapsed = (record.get("parsed") or {}).get("collapsed") or []
        rows[arm] = [row for row in collapsed
                     if float(row["start_sec"]) < question["end_sec"]
                     and float(row["end_sec"]) > question["start_sec"]]
    return rows


def sheet(frames, rows, out_path: Path) -> None:
    from PIL import Image, ImageDraw

    width, height = frames[0].size
    columns = min(COLUMNS, len(frames))
    lines = (len(frames) + columns - 1) // columns
    sheet_width = columns * width + (columns + 1) * PAD
    sheet_height = lines * (height + LABEL_HEIGHT) + (lines + 1) * PAD
    canvas = Image.new("RGB", (sheet_width, sheet_height), (24, 24, 27))
    draw = ImageDraw.Draw(canvas)
    for index, (frame, row) in enumerate(zip(frames, rows)):
        column, line = index % columns, index // columns
        x = PAD + column * (width + PAD)
        y = PAD + line * (height + LABEL_HEIGHT + PAD)
        canvas.paste(frame, (x, y))
        colour = (250, 250, 250) if row["role"] == fa.KEEP else (255, 176, 46)
        draw.text((x + 4, y + height + 5),
                  "%.1fs  %s" % (row["time_sec"], row["role"]), fill=colour)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def build(video: Path, runs: Path) -> dict:
    frame_dir = runs / FRAME_DIR_NAME
    manifest, lines = [], [
        "# FRAME_ADJUDICATION_V1 packet — KEEP·DROP 프레임 실물", "",
        "사전등록: `%s`" % PREREG, "",
        "```",
        "프레임은 모델이 실제로 받은 것과 같은 512×288이다(원본 해상도가 아니다).",
        "KEEP  = S0·S1 공통 프레임 (0.25fps에도 들어간 것)",
        "DROP  = S0에만 있는 프레임 (0.25fps가 못 본 것)",
        "판정값 DROP_FRAMES_CARRY_MATERIAL_INFORMATION · KEEP_FRAMES_SUFFICIENT ·",
        "       GENERATION_ERROR_NOT_SAMPLING · FRAMES_INSUFFICIENT",
        "```", ""]

    for question in fa.QUESTIONS:
        rows = fa.frame_rows(question)
        fa.assert_expected_counts(question["question_id"], rows)
        fa.assert_keep_matches_s1(question, rows)
        stamps = [row["time_sec"] for row in rows]
        frames, indices, times, rate = probe.sample_frames(video, stamps)
        check_frames(frames, rows, question["question_id"])

        saved = []
        for frame, row, index, time in zip(frames, rows, indices, times):
            name = "%s_%06.1f_%s.png" % (question["question_id"],
                                         row["time_sec"], row["role"])
            path = frame_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.save(path)
            saved.append({**row, "frame_index": index,
                          "decoded_time_sec": time, "file": name,
                          "sha256": sha256_file(path)})

        sheet_path = frame_dir / ("%s_sheet.png" % question["question_id"])
        sheet(frames, rows, sheet_path)
        manifest.append({
            "question_id": question["question_id"],
            "parent_window": question["parent_window"],
            "span": [question["start_sec"], question["end_sec"]],
            "question": question["question"],
            "counts": fa.counts(rows), "frames": saved,
            "sheet": sheet_path.name, "sheet_sha256": sha256_file(sheet_path),
            "claims": claims_for(runs, question),
            "decoded_fps": rate,
        })

        lines += ["## %s  %s %.0f–%.0f초"
                  % (question["question_id"], question["parent_window"],
                     question["start_sec"], question["end_sec"]), "",
                  question["question"], "",
                  "```",
                  "KEEP  %s" % ", ".join("%.1f" % row["time_sec"]
                                         for row in rows
                                         if row["role"] == fa.KEEP),
                  "DROP  %s" % ", ".join("%.1f" % row["time_sec"]
                                         for row in rows
                                         if row["role"] == fa.DROP),
                  "```", "",
                  "대지: `runs/wvr_light_v1/%s/%s`"
                  % (FRAME_DIR_NAME, sheet_path.name), ""]
        claims = manifest[-1]["claims"]
        for arm in sw.ARMS:
            label = "S0 (0.5fps)" if arm == sw.ARM_S0 else "S1 (0.25fps)"
            lines += ["**%s 주장**" % label, "", "```"]
            lines += ["%.0f–%.0f | %s | %s | %s"
                      % (row["start_sec"], row["end_sec"], row["actor"],
                         row["action"], row["object_or_state"])
                      for row in claims[arm]] or ["(겹치는 event 없음)"]
            lines += ["```", ""]

    return {
        "packet": "\n".join(lines).rstrip() + "\n",
        "manifest": {
            "schema": "wvr_frame_adjudication_manifest_v1", "event": fa.EVENT,
            "prereg": PREREG, "code_git_head": git_head(),
            "new_inference_allowed": fa.NEW_INFERENCE_ALLOWED,
            "gt_label_use_allowed": fa.GT_LABEL_USE_ALLOWED,
            "semantic_sufficiency_claim_allowed":
                fa.SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED,
            "video_sha256": None, "frame_size": [fa.FRAME_WIDTH,
                                                 fa.FRAME_HEIGHT],
            "questions": manifest, "allowed_scope": fa.ALLOWED_SCOPE,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="KEEP·DROP 프레임 packet")
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    video, runs = Path(args.video), Path(args.runs)
    if not video.is_file():
        raise PacketError("영상이 없다: %s" % video)
    built = build(video, runs)
    built["manifest"]["video_sha256"] = hashlib.sha256(
        video.read_bytes()).hexdigest()
    (runs / PACKET_NAME).write_text(built["packet"], encoding="utf-8")
    (runs / MANIFEST_NAME).write_text(
        json.dumps(built["manifest"], ensure_ascii=False, indent=1),
        encoding="utf-8")

    print("packet=%s manifest=%s" % (PACKET_NAME, MANIFEST_NAME))
    for row in built["manifest"]["questions"]:
        print("  %s %s %.0f-%.0f KEEP=%d DROP=%d sheet=%s"
              % (row["question_id"], row["parent_window"], row["span"][0],
                 row["span"][1], row["counts"][fa.KEEP],
                 row["counts"][fa.DROP], row["sheet"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
