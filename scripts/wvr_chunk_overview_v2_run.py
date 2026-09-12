"""WVR_CHUNK_OVERVIEW_V2 — chunk 하나를 V2 관찰 계약 그대로 실행한다.

사전등록: `docs/preregistration/WVR_CHUNK_OVERVIEW_V2_C02_C05_2026-09-13.md`

    python scripts/wvr_chunk_overview_v2_run.py --chunk C02
    python scripts/wvr_chunk_overview_v2_run.py --chunk C02 --plan-only   # GPU 미사용

`--plan-only`는 모델을 올리지 않고 창 계획과 기하만 쓴다. 정식 실행 전 검증용이다.

이 스크립트는 plan만 바꿔 `wvr_video_overview_preview_v2_run.run`에 넘긴다.
프롬프트·스키마·모델·표집·파싱은 **V2 모듈 그대로** 쓴다 — 여기서 재정의하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_chunk_overview_v2 as cv  # noqa: E402
import wvr_video_overview_preview_v2 as ov  # noqa: E402
import wvr_video_overview_preview_v2_run as v2run  # noqa: E402

DEFAULT_VIDEO = "data/videos/full_xekZO4n4QuE.mp4"
DEFAULT_RUNS = "runs/wvr_chunk_overview_v2"
GEOMETRY_NAME = "chunk_geometry.json"


class ChunkRunError(RuntimeError):
    pass


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(ov.canonical(value) + "\n")


def prepare(chunk_id: str, runs_root: Path) -> tuple[Path, list[dict], dict]:
    """chunk 디렉터리와 창 계획을 만든다. 모델을 올리지 않는다."""
    if chunk_id not in cv.EXECUTED_CHUNK_IDS:
        raise ChunkRunError(
            "이번 사건의 실행 대상이 아니다: %s (허용 %s · C01은 선행 산출물을 쓴다)"
            % (chunk_id, ", ".join(cv.EXECUTED_CHUNK_IDS)))
    plan = cv.segments(chunk_id)
    geometry = cv.plan_geometry(chunk_id)
    runs = Path(runs_root) / chunk_id
    runs.mkdir(parents=True, exist_ok=True)
    _write_json(runs / GEOMETRY_NAME, {
        "event": cv.EVENT, "prereg": cv.PREREG,
        "chunk": cv.chunk_by_id(chunk_id), "geometry": geometry,
        "video_sha256": cv.VIDEO_SHA256,
        "frozen_c01_runs": cv.FROZEN_C01_RUNS,
        "observation_contract": {
            "model_id": ov.MODEL_ID, "model_revision": ov.MODEL_REVISION,
            "prompt_sha256": ov.sha256_text(ov.segment_prompt()),
            "max_new_tokens": ov.MAX_NEW_TOKENS,
            "do_sample": ov.DO_SAMPLE, "num_beams": ov.NUM_BEAMS,
        },
    })
    return runs, plan, geometry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk", required=True, choices=list(cv.EXECUTED_CHUNK_IDS))
    parser.add_argument("--video", default=DEFAULT_VIDEO)
    parser.add_argument("--runs-root", default=DEFAULT_RUNS)
    parser.add_argument("--plan-only", action="store_true",
                        help="모델을 올리지 않고 창 계획·기하만 쓴다")
    parser.add_argument("--resume", action="store_true",
                        help="pre-synthesis 실패 실행만 이어붙인다 (V2 규칙 그대로)")
    args = parser.parse_args(argv)

    runs, plan, geometry = prepare(args.chunk, Path(args.runs_root))
    print("chunk    ", args.chunk, json.dumps(geometry, ensure_ascii=False))
    print("runs     ", runs)
    if args.plan_only:
        print("PLAN_ONLY_OK — 추론하지 않았다")
        return 0

    started = time.time()
    result = v2run.run(Path(args.video), runs, resume=args.resume, plan=plan)
    print("status   ", result["status"])
    print("segments ", len(result["segment_summaries"]))
    print("elapsed  ", round(time.time() - started, 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
