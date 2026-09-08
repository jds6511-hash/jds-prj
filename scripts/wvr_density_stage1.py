"""WVR_SAMPLING_SEMANTIC_DENSITY_V1 Stage 1 — VISUAL_TEMPORAL_COVERAGE.

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md`

```
모델 없음 · GPU 없음 · 결정적
프레임 추출은 probe.sample_frames를 그대로 쓴다 (같은 프레임이어야 한다)
```

이 단계는 **화면 변화**를 잰다. 의미 충분성을 판정하지 않는다.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_contract as contract                            # noqa: E402
import wvr_capacity_probe as probe                          # noqa: E402
import wvr_density as density                               # noqa: E402

STAGE2_APPROVED = False          # Stage 2(GPU 6회)는 별도 승인이다
EVENT_EXTRACTION_APPROVED = False


def _luma(image):
    """PIL 이미지 → 휘도 바이트열. 결정적 변환만 쓴다."""
    return image.convert("L").tobytes()


def measure(video_path, out_path) -> dict:
    started = time.time()
    reference = density.reference_timestamps()
    keep, drop = density.keep_drop(reference)

    frames, indices, times, rate = probe.sample_frames(video_path, reference)
    luma = {stamp: _luma(image) for stamp, image in zip(reference, frames)}
    hists = {stamp: density.histogram(values) for stamp, values in luma.items()}

    rows = []
    for stamp in drop:
        before, after = density.neighbours(stamp, keep)
        diff_prev = (density.luma_diff(luma[before], luma[stamp])
                     if before is not None else None)
        diff_next = (density.luma_diff(luma[stamp], luma[after])
                     if after is not None else None)
        hist_prev = (density.histogram_distance(hists[before], hists[stamp])
                     if before is not None else None)
        hist_next = (density.histogram_distance(hists[stamp], hists[after])
                     if after is not None else None)
        rows.append({
            "drop_sec": stamp, "prev_keep_sec": before, "next_keep_sec": after,
            "luma_diff_prev": diff_prev, "luma_diff_next": diff_next,
            "luma_novelty": density.novelty(diff_prev, diff_next),
            "hist_dist_prev": hist_prev, "hist_dist_next": hist_next,
            "hist_novelty": density.novelty(hist_prev, hist_next),
        })

    scores = [(row["drop_sec"], row["luma_novelty"]) for row in rows]
    scored = []
    for window in density.windows():
        counts = density.window_frames(window, keep, drop)
        scored.append({**window,
                       "score": density.window_score(window, scores),
                       "reference_frames": len(counts["reference"]),
                       "keep_frames": len(counts["keep"]),
                       "drop_frames": len(counts["drop"])})

    top = sorted(rows, key=lambda row: (-row["luma_novelty"], row["drop_sec"]))
    record = {
        "schema": "wvr_density_stage1_v1",
        "stage": density.STAGE1,
        "prereg": ("docs/preregistration/"
                   "WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md"),
        "note": ("0.5fps는 영상의 truth가 아니라 더 높은 표집 밀도 reference다. "
                 "이 단계는 화면 변화를 재고 의미 충분성을 판정하지 않는다."),
        "video": {"path": str(video_path), "sha256": probe._sha256(video_path)},
        "sampling": {"reference_fps": density.REFERENCE_FPS,
                     "density_fps": density.DENSITY_FPS,
                     "keep_stride": density.KEEP_STRIDE,
                     "reference_frames": len(reference),
                     "keep_frames": len(keep), "drop_frames": len(drop),
                     "keep_first_last": [keep[0], keep[-1]],
                     "drop_first_last": [drop[0], drop[-1]],
                     "frame_size": [contract.FRAME_WIDTH, contract.FRAME_HEIGHT],
                     "decoded_rate": rate,
                     "frame_index_first_last": [indices[0], indices[-1]],
                     "frame_time_first_last": [times[0], times[-1]]},
        "distribution": {
            "luma_novelty": density.distribution(
                [row["luma_novelty"] for row in rows]),
            "luma_diff_prev": density.distribution(
                [row["luma_diff_prev"] for row in rows]),
            "hist_novelty": density.distribution(
                [row["hist_novelty"] for row in rows]),
        },
        "top_drop_frames": top[:15],
        "windows": scored,
        "selection": density.select_windows(scored),
        "stage2_approved": STAGE2_APPROVED,
        "event_extraction_approved": EVENT_EXTRACTION_APPROVED,
        "rows": rows,
        "wall_sec": round(time.time() - started, 2),
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage 1 화면 변화 측정")
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise density.DensityError("영상이 없다: %s" % video)
    record = measure(video, Path(args.out))
    print("drop=%d luma_novelty median=%.3f p95=%.3f max=%.3f"
          % (record["sampling"]["drop_frames"],
             record["distribution"]["luma_novelty"]["median"],
             record["distribution"]["luma_novelty"]["p95"],
             record["distribution"]["luma_novelty"]["max"]))
    for label in density.SELECTION_LABELS:
        row = record["selection"][label]
        print("%s %s %.1f-%.1f score=%.2f"
              % (label, row["window_id"], row["start_sec"], row["end_sec"],
                 row["score"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
