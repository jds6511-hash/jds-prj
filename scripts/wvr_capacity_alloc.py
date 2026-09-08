"""WVR_CAPACITY_ALLOC_V1 실행기 (2026-09-08).

사전등록: `docs/preregistration/WVR_CAPACITY_ALLOC_V1_2026-09-08.md`

```
A0  default allocator                     항상 1회
A1  expandable_segments:True              A0 == CAPACITY_FAIL일 때만 1회
```

workload는 `scripts/wvr_capacity_probe.py`의 `probe()`를 **그대로** 호출해 만든다 —
같은 코드 경로여야 "allocator만 달랐다"고 말할 수 있다.

arm마다 **별도 process**로 돌린다. allocator 환경변수는 python 시작 전에 있어야
하므로 프로그램 안에서 설정하지 않는다.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_alloc as alloc                                  # noqa: E402
import wvr_capacity_probe as probe                          # noqa: E402

PREREG = "docs/preregistration/WVR_CAPACITY_ALLOC_V1_2026-09-08.md"
HISTORICAL_C01 = "runs/wvr_light_v1/capacity_C01.json"

# 나중에 "allocator 말고 다른 게 달라지지 않았나"를 확인하려면 실행 맥락이 필요하다.
ENV_KEYS_RECORDED = ("PYTORCH_CUDA_ALLOC_CONF", "HF_HOME", "CUDA_VISIBLE_DEVICES",
                     "WVR_CODE_GIT_HEAD", "LD_LIBRARY_PATH", "CUDA_HOME")

# 이번 사건에서 바꾸지 않는다. probe 쪽 상수를 그대로 쓴다는 뜻이다.
SEMANTIC_EVALUATION_ENABLED = False


def gpu_snapshot() -> dict:
    """nvidia-smi로 idle 상태를 기록한다. probe와 독립적인 관측이다."""
    query = subprocess.run(
        ["nvidia-smi",
         "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu,"
         "temperature.gpu", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True)
    total, used, free, util, temp = [
        field.strip() for field in query.stdout.strip().splitlines()[0].split(",")]
    apps = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
         "--format=csv,noheader"], capture_output=True, text=True, check=True)
    rows = [line for line in apps.stdout.strip().splitlines() if line.strip()]
    return {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "memory_total_mib": float(total), "memory_used_mib": float(used),
            "memory_free_mib": float(free), "utilization_pct": float(util),
            "temperature_c": float(temp), "compute_process_count": len(rows),
            "compute_apps": rows}


def preflight(arm: str, video: Path, idle: dict) -> dict:
    """실행 맥락을 통째로 남긴다. 계측이고 실험 변수가 아니다."""
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=str(ROOT),
                                  capture_output=True, text=True,
                                  check=True).stdout.strip()
        except Exception:
            return "UNKNOWN"

    return {"arm": arm, "gpu_idle": idle,
            "video_sha256": probe._sha256(video),
            "model_snapshot": probe.contract.MODEL_REVISION,
            "git_head": os.environ.get("WVR_CODE_GIT_HEAD") or git("rev-parse",
                                                                   "HEAD"),
            "tree_clean": git("status", "--porcelain") == "",
            "command": [sys.executable, *sys.argv],
            "cwd": os.getcwd(),
            "environment": {key: os.environ.get(key, "")
                            for key in ENV_KEYS_RECORDED}}


def load_record(path: Path):
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_arm(arm: str, video: Path, out_dir: Path, log_path=None) -> dict:
    """arm 하나. 게이트를 먼저 통과해야 GPU를 쓴다."""
    import torch

    alloc.assert_fresh_process(torch.cuda.is_initialized())
    observed = alloc.assert_allocator_env(arm, os.environ)
    out_path = out_dir / ("capacity_alloc_%s.json" % arm)
    alloc.assert_once(out_path.exists(), arm)

    a0_record = None
    if arm == alloc.ARM_A1:
        a0_record = load_record(out_dir / "capacity_alloc_A0.json")
        alloc.assert_a1_allowed(a0_record)

    idle = gpu_snapshot()
    alloc.assert_idle(idle)
    flight = preflight(arm, video, idle)

    meta = probe.video_metadata(video)
    record = probe.probe(video, out_path, video_meta=meta)

    record["event"] = "WVR_CAPACITY_ALLOC_V1"
    record["arm"] = arm
    record["prereg"] = PREREG
    record["semantic_evaluation_enabled"] = SEMANTIC_EVALUATION_ENABLED
    record["allocator_env_requested"] = (alloc.A1_ALLOC_VALUE
                                         if arm == alloc.ARM_A1 else "")
    record["allocator_env_observed"] = observed
    record["gpu_idle_before"] = idle
    record["preflight"] = flight
    log_text = ""
    if log_path is not None and Path(log_path).is_file():
        log_text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    record["allocator_warnings"] = list(alloc.allocator_warnings(log_text))
    record["arm_verdict"] = alloc.arm_verdict(record)
    record["metrics"].update(alloc.parse_oom(
        (record.get("error") or {}).get("message", "")))
    record["metrics"]["reserved_minus_allocated_mib"] = round(
        (record["metrics"].get("peak_vram_reserved_mib") or 0)
        - (record["metrics"].get("peak_vram_allocated_mib") or 0), 1)

    if arm == alloc.ARM_A1:
        record["treatment_applied"] = alloc.treatment_applied(record)
        record["arm_status"] = alloc.a1_status(record, log_text)
        delta = alloc.baseline_delta_mib(a0_record, record)
        record["baseline_delta_mib"] = delta
        record["comparability_gate_mib"] = alloc.COMPARABILITY_THRESHOLD_MIB
        record["comparability"] = alloc.comparability(delta)
        record["workload_differences"] = list(
            alloc.workload_identity(a0_record, record))
        record["comparison_invalid_reason"] = alloc.comparison_invalid_reason(
            a0_record, record)
        record["event_verdict"] = alloc.event_verdict(a0_record, record,
                                                      log_text)
    else:
        record["event_verdict"] = (
            alloc.EVENT_CONTROL_PASS
            if record["arm_verdict"] == alloc.ARM_PASS else "A1_PENDING")
        record["a1_status"] = (alloc.A1_NOT_RUN
                               if record["arm_verdict"] == alloc.ARM_PASS
                               else "REQUIRED_BY_PREREG_RULE")

    probe.write_record(record, out_path)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="WVR_CAPACITY_ALLOC_V1")
    parser.add_argument("--arm", required=True, choices=list(alloc.ARMS))
    parser.add_argument("--video", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--log", default=None,
                        help="이 실행의 stdout·stderr 로그 경로 (allocator 경고 검사)")
    args = parser.parse_args(argv)

    video = Path(args.video)
    if not video.is_file():
        raise alloc.AllocError("영상이 없다: %s" % video)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    record = run_arm(args.arm, video, out_dir, log_path=args.log)
    print("arm=%s verdict=%s event=%s stage=%s"
          % (record["arm"], record["arm_verdict"], record["event_verdict"],
             record["stage"]))
    return 0 if record["arm_verdict"] == alloc.ARM_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
