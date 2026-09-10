"""VISUAL_CONTENT_ISOLATION_V1 픽셀/시간 인코딩 self-check (2026-09-10).

사전등록 §13(5). **모델을 올리지 않는다** — processor만 써서 arm E 입력을 만들고
아래를 실측한다.

```
E 픽셀이 기존 W05 24 해시와 순서까지 같은가
E의 pixel_values가 Trigger arm A(=W00 픽셀)와 다른가        (픽셀이 실제로 바뀌었는가)
E의 <X.X seconds> 마커가 T0(1.0…45.0)인가                  (시간 인코딩은 A와 같은가)
E의 rendered prompt hash가 Trigger A와 같은가
```

하나라도 실패하면 0이 아닌 코드로 끝난다 — 그 상태로 추론하지 않는다.
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
import wvr_visual_v1 as vc                                  # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md")
SELFCHECK_NAME = "visual_v1_selfcheck.json"
MARKER_RE = re.compile(r"<(\d+(?:\.\d+)?) seconds>")


class SelfCheckError(RuntimeError):
    """self-check 실패."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def reference_pixel_values(runs: Path) -> str:
    """Trigger arm A가 기록한 pixel_values 해시 (W00 픽셀)."""
    path = runs / vc.TIME_REFERENCE_RECORD
    if not path.is_file():
        return ""
    return json.loads(path.read_text(encoding="utf-8")).get(
        "pixel_values_sha256") or ""


def reference_pixel_hashes(runs: Path) -> list:
    path = runs / vc.PIXEL_REFERENCE_RECORD
    if not path.is_file():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get(
        "frame_hashes") or [])


def build(video: Path, runs: Path) -> dict:
    from transformers import AutoProcessor
    from transformers.video_utils import VideoMetadata

    if vc.PROCESSOR_MONKEY_PATCH_ALLOWED:
        raise SelfCheckError("processor monkey-patch는 금지돼 있다")

    processor = AutoProcessor.from_pretrained(
        contract.MODEL_ID, revision=contract.MODEL_REVISION,
        local_files_only=True)
    meta = probe.video_metadata(video)
    stamps = list(vc.pixel_times())
    frames, decoded_indices, _, rate = probe.sample_frames(video, stamps)
    pixel_hashes = [sha256_bytes(frame.tobytes()) for frame in frames]

    arm = vc.arm_plan(rate)
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
    pixel_values = sha256_bytes(inputs["pixel_values_videos"].numpy().tobytes())

    w05_hashes = reference_pixel_hashes(runs)
    trigger_pixels = reference_pixel_values(runs)
    identity = vc.pixel_identity(pixel_hashes, w05_hashes)
    checks = {
        "pixels_match_w05": identity["identical"],
        "pixel_count": len(frames) == vc.PIXEL_FRAME_COUNT,
        "pixel_values_differ_from_trigger_A": bool(trigger_pixels)
        and pixel_values != trigger_pixels,
        "markers_are_T0": bool(markers) and markers[0] == "1.0"
        and markers[-1] == "45.0",
        "rendered_prompt_matches_trigger_A":
            arm["rendered_prompt_hash"]
            == tg.rendered_prompt_hash(tg.ARMS[0][1]),
        "indices_match_trigger_A": list(arm["frames_indices"])
        == list(tg.frame_indices("M0", rate)),
        "pixel_times_are_120_to_166": stamps[0] == 120.0
        and stamps[-1] == 166.0,
        "decoded_indices_are_w05_range": decoded_indices[0] >= 3600,
    }
    ok = all(checks.values())
    return {
        "schema": "wvr_visual_v1_selfcheck", "event": vc.EVENT,
        "prereg": PREREG, "code_git_head": git_head(),
        "transformers_version": __import__("transformers").__version__,
        "decoded_fps": rate, "pixel_frame_count": len(frames),
        "pixel_times_first_last": [stamps[0], stamps[-1]],
        "pixel_hashes": pixel_hashes,
        "pixel_values_sha256": pixel_values,
        "trigger_A_pixel_values_sha256": trigger_pixels,
        "decoded_frame_indices_first_last": [decoded_indices[0],
                                             decoded_indices[-1]],
        "metadata_frames_indices_first_last": [arm["frames_indices"][0],
                                               arm["frames_indices"][-1]],
        "timestamp_markers_first_last": ([markers[0], markers[-1]] if markers
                                         else None),
        "rendered_prompt_hash": arm["rendered_prompt_hash"],
        "input_token_count": int(inputs["input_ids"].shape[-1]),
        "pixel_identity_vs_w05": identity,
        "checks": checks, "ok": ok,
        "status": "OK" if ok else tg.IMPLEMENTATION_BLOCKED,
        "note": ("E는 W05 픽셀 + Trigger A의 시간 인코딩이다 — "
                 "픽셀은 바뀌고 시간 채널은 그대로여야 한다"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="visual isolation self-check")
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    video, runs = Path(args.video), Path(args.runs)
    if not video.is_file():
        raise SelfCheckError("영상이 없다: %s" % video)
    report = build(video, runs)
    (runs / SELFCHECK_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("status=%s ok=%s" % (report["status"], report["ok"]))
    for name, value in report["checks"].items():
        print("  check %-38s %s" % (name, value))
    print("  pixels=%s..%s markers=%s indices=%s tokens=%s px=%s"
          % (report["pixel_times_first_last"][0],
             report["pixel_times_first_last"][1],
             report["timestamp_markers_first_last"],
             report["metadata_frames_indices_first_last"],
             report["input_token_count"],
             report["pixel_values_sha256"][:12]))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
