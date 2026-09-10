"""TRIGGER_ISOLATION_V1 픽셀/metadata 분리 self-check (2026-09-10).

사전등록 §17 hard blocker. **모델을 올리지 않는다** — processor만 써서 4 arm 입력을
만들고 다음을 실측한다.

```
pixel_values 바이트가 4 arm 전부 동일한가            (조작이 픽셀을 건드리지 않는가)
<X.X seconds> 마커가 M0/M1에서 실제로 달라지는가      (조작이 실제로 걸리는가)
rendered prompt가 P0/P1에서만 달라지는가
```

하나라도 실패하면 0이 아닌 코드로 끝난다 — 그 상태로 추론하지 않는다
(`INCONCLUSIVE / IMPLEMENTATION_BLOCKED`).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_contract as contract                            # noqa: E402
import wvr_capacity_probe as probe                          # noqa: E402
import wvr_trigger_v1 as tg                                 # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md")
SELFCHECK_NAME = "trigger_v1_selfcheck.json"
MARKER_RE = re.compile(r"<(\d+(?:\.\d+)?) seconds>")


class SelfCheckError(RuntimeError):
    """분리 self-check 실패."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build(video: Path) -> dict:
    from transformers import AutoProcessor
    from transformers.video_utils import VideoMetadata

    if tg.PROCESSOR_MONKEY_PATCH_ALLOWED:
        raise SelfCheckError("processor monkey-patch는 금지돼 있다")

    processor = AutoProcessor.from_pretrained(
        contract.MODEL_ID, revision=contract.MODEL_REVISION,
        local_files_only=True)
    meta = probe.video_metadata(video)
    stamps = list(tg.pixel_times())
    frames, decoded_indices, _, rate = probe.sample_frames(video, stamps)
    pixel_hashes = [sha256_bytes(frame.tobytes()) for frame in frames]

    rows = {}
    for arm_id in tg.ARM_IDS:
        arm = tg.arm_plan(arm_id, rate)
        messages = [{"role": "user",
                     "content": [{"type": "video"},
                                 {"type": "text",
                                  "text": arm["rendered_prompt"]}]}]
        text = processor.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True)
        metadata = VideoMetadata(
            total_num_frames=meta["nb_frames"], fps=rate, width=meta["width"],
            height=meta["height"], duration=meta["duration_sec"],
            video_backend="pyav", frames_indices=list(arm["frames_indices"]))
        inputs = processor(text=[text], videos=[frames],
                           video_metadata=[metadata],
                           do_sample_frames=contract.DO_SAMPLE_FRAMES,
                           do_resize=contract.DO_RESIZE, return_tensors="pt")
        decoded = processor.tokenizer.decode(inputs["input_ids"][0])
        markers = MARKER_RE.findall(decoded)
        rows[arm_id] = {
            "prompt_mode": arm["prompt_mode"],
            "metadata_mode": arm["metadata_mode"],
            "prompt_window": arm["prompt_window"],
            "rendered_prompt_hash": arm["rendered_prompt_hash"],
            "frames_indices_first_last": [arm["frames_indices"][0],
                                          arm["frames_indices"][-1]],
            "pixel_values_sha256": sha256_bytes(
                inputs["pixel_values_videos"].numpy().tobytes()),
            "pixel_values_shape": list(inputs["pixel_values_videos"].shape),
            "input_token_count": int(inputs["input_ids"].shape[-1]),
            "timestamp_markers": markers,
            "marker_first_last": ([markers[0], markers[-1]] if markers
                                  else None),
            "text_sha256": sha256_bytes(text.encode("utf-8")),
        }

    pixel_values = {row["pixel_values_sha256"] for row in rows.values()}
    markers_by_mode = {mode: {tuple(row["timestamp_markers"])
                              for row in rows.values()
                              if row["metadata_mode"] == mode}
                       for mode in tg.METADATA_MODES}
    checks = {
        "pixel_values_identical_across_arms": len(pixel_values) == 1,
        "pixel_hashes_count": len(pixel_hashes) == tg.PIXEL_FRAME_COUNT,
        "markers_differ_between_M0_and_M1":
            len(markers_by_mode["M0"]) == 1 and len(markers_by_mode["M1"]) == 1
            and markers_by_mode["M0"] != markers_by_mode["M1"],
        "markers_same_within_mode":
            all(len(values) == 1 for values in markers_by_mode.values()),
        "prompt_A_equals_B": rows["A"]["rendered_prompt_hash"]
        == rows["B"]["rendered_prompt_hash"],
        "prompt_C_equals_D": rows["C"]["rendered_prompt_hash"]
        == rows["D"]["rendered_prompt_hash"],
        "prompt_A_differs_C": rows["A"]["rendered_prompt_hash"]
        != rows["C"]["rendered_prompt_hash"],
        "M0_indices_equal_decoded": rows["A"]["frames_indices_first_last"]
        == [decoded_indices[0], decoded_indices[-1]],
    }
    separable = all(checks.values())
    return {
        "schema": "wvr_trigger_v1_selfcheck", "event": tg.EVENT,
        "prereg": PREREG, "code_git_head": git_head(),
        "transformers_version": __import__("transformers").__version__,
        "video_sha256": None, "decoded_fps": rate,
        "pixel_frame_count": len(frames),
        "pixel_hashes": pixel_hashes,
        "decoded_frame_indices": list(decoded_indices),
        "arms": rows, "checks": checks,
        "separable": separable,
        "status": "SEPARABLE" if separable else tg.IMPLEMENTATION_BLOCKED,
        "note": ("do_sample_frames=False에서 processor는 프레임을 다시 뽑지 않고 "
                 "frames_indices를 덮어쓰지 않는다 — 이 파일이 그 실측이다"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="픽셀/metadata 분리 self-check")
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    video, runs = Path(args.video), Path(args.runs)
    if not video.is_file():
        raise SelfCheckError("영상이 없다: %s" % video)
    report = build(video)
    (runs / SELFCHECK_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("status=%s separable=%s" % (report["status"], report["separable"]))
    for name, value in report["checks"].items():
        print("  check %-38s %s" % (name, value))
    for arm_id, row in report["arms"].items():
        print("  %s %s/%s window=%s indices=%s markers=%s tokens=%s px=%s"
              % (arm_id, row["prompt_mode"], row["metadata_mode"],
                 row["prompt_window"], row["frames_indices_first_last"],
                 row["marker_first_last"], row["input_token_count"],
                 row["pixel_values_sha256"][:12]))
    return 0 if report["separable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
