"""WVR_CAPACITY_SAMPLING_V1 실행기 (2026-09-08).

사전등록: `docs/preregistration/WVR_CAPACITY_SAMPLING_V1_2026-09-08.md`

```
parent control  runs/wvr_light_v1/capacity_alloc_A0.json  (0.5 fps · default · FAIL)
                재실행하지 않는다 — 이미 같은 조건에서 측정됐다
B arm           0.25 fps · 150프레임 · default allocator · 그 외 A0과 동일
실행 횟수        정확히 1회
```

allocator를 default로 되돌리는 이유는 규율이다 — expandable과 sampling을 같이
바꾸면 무엇이 통과시켰는지 분리할 수 없다.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_alloc as alloc                                  # noqa: E402
import wvr_capacity_alloc as alloc_run                     # noqa: E402
import wvr_capacity_probe as probe                          # noqa: E402
import wvr_sampling as sampling                             # noqa: E402

PREREG = "docs/preregistration/WVR_CAPACITY_SAMPLING_V1_2026-09-08.md"
CONTROL_ARTIFACT = "capacity_alloc_A0.json"

# capacity가 통과해도 event extraction으로 넘어가지 않는다. 의미 밀도는 별개 질문이다.
EVENT_EXTRACTION_APPROVED = False
SEMANTIC_EVALUATION_ENABLED = False


def run(video: Path, out_dir: Path, log_path=None) -> dict:
    import torch

    alloc.assert_fresh_process(torch.cuda.is_initialized())
    observed = sampling.assert_default_allocator(os.environ)
    out_path = out_dir / "capacity_sampling_B.json"
    alloc.assert_once(out_path.exists(), sampling.ARM_B)

    control = alloc_run.load_record(out_dir / CONTROL_ARTIFACT)
    if control is None:
        raise sampling.SamplingError("parent control(A0) 산출물이 없다")
    if alloc.arm_verdict(control) != alloc.ARM_FAIL:
        raise sampling.SamplingError("parent control이 CAPACITY_FAIL이 아니다")

    idle = alloc_run.gpu_snapshot()
    alloc.assert_idle(idle)
    flight = alloc_run.preflight(sampling.ARM_B, video, idle)

    meta = probe.video_metadata(video)
    chunk = probe.approved_chunk(meta["duration_sec"])
    stamps = sampling.sampling_frames(chunk)
    record = probe.probe(video, out_path, video_meta=meta,
                         sampling={"fps": sampling.SAMPLING_FPS,
                                   "timestamps": stamps})

    record["event"] = "WVR_CAPACITY_SAMPLING_V1"
    record["arm"] = sampling.ARM_B
    record["prereg"] = PREREG
    record["parent_control"] = {
        "artifact": CONTROL_ARTIFACT,
        "verdict": alloc.arm_verdict(control),
        "chunk_fps": control["requested"]["chunk_fps"],
        "delivered_frame_count": control["metrics"]["delivered_frame_count"],
        "input_token_count": control["metrics"]["input_token_count"],
        "baseline_vram_mib": control["metrics"]["baseline_vram_mib"],
    }
    record["semantic_evaluation_enabled"] = SEMANTIC_EVALUATION_ENABLED
    record["event_extraction_approved"] = EVENT_EXTRACTION_APPROVED
    record["allocator_env_observed"] = observed
    record["gpu_idle_before"] = idle
    record["preflight"] = flight
    record["expected_frames"] = sampling.EXPECTED_FRAMES
    record["expected_video_tokens"] = sampling.EXPECTED_VIDEO_TOKENS

    log_text = ""
    if log_path is not None and Path(log_path).is_file():
        log_text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    record["allocator_warnings"] = list(alloc.allocator_warnings(log_text))
    record["metrics"].update(alloc.parse_oom(
        (record.get("error") or {}).get("message", "")))
    record["metrics"]["reserved_minus_allocated_mib"] = round(
        (record["metrics"].get("peak_vram_reserved_mib") or 0)
        - (record["metrics"].get("peak_vram_allocated_mib") or 0), 1)

    sampling.assert_resolution_frozen(record)
    record["arm_verdict"] = alloc.arm_verdict(record)
    record["single_change_violations"] = list(
        sampling.single_change(control, record))
    record["sampling_changed"] = sampling.sampling_changed(control, record)
    record["token_reduction"] = sampling.token_reduction(control, record)
    record["baseline_delta_mib"] = alloc.baseline_delta_mib(control, record)
    record["comparability_gate_mib"] = alloc.COMPARABILITY_THRESHOLD_MIB
    record["comparability"] = alloc.comparability(record["baseline_delta_mib"])
    record["event_verdict"] = (
        "CAPACITY_PASS" if record["arm_verdict"] == alloc.ARM_PASS
        else "CAPACITY_FAIL" if record["arm_verdict"] == alloc.ARM_FAIL
        else "IMPLEMENTATION_DEFECT")
    if record["single_change_violations"] or not record["sampling_changed"]:
        record["event_verdict"] = "COMPARISON_INVALID"

    probe.write_record(record, out_path)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="WVR_CAPACITY_SAMPLING_V1")
    parser.add_argument("--video", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--log", default=None)
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise sampling.SamplingError("영상이 없다: %s" % video)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    record = run(video, out_dir, log_path=args.log)
    print("arm=B verdict=%s event=%s frames=%s input_tokens=%s stage=%s"
          % (record["arm_verdict"], record["event_verdict"],
             record["metrics"].get("delivered_frame_count"),
             record["metrics"].get("input_token_count"), record["stage"]))
    return 0 if record["arm_verdict"] == alloc.ARM_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
