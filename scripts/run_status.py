"""실행 상태 판독기 + 마커 스키마 — **마커 존재는 완료 근거가 아니다.**

2026-08-22 사고. 같은 run_id로 CANARY를 돌린 뒤 FULL을 시작했는데, CANARY가 남긴
`STAGE_m3_captions_DONE`·`STAGE_m4_index_DONE`이 그대로 있어서 FULL이 m2를 도는 중에
"m4까지 끝났다"로 읽혔다. 연구 결과는 오염되지 않았다.

```
단계 소요    배치 내부 time.time()에서 나온다 — 마커를 읽지 않는다
건너뛰기     없다. FULL은 전 단계를 다시 돈다 (no-resume by design)
리포트       validator hook이 *_full.json을 *_canary.json보다 우선한다
```

그래도 **사람이 상태를 잘못 읽었다.** 그래서 두 가지를 준다.

```
1  이름공간을 가진 마커  CANARY_STAGE_<stage>_DONE.json / FULL_STAGE_<stage>_DONE.json
   내용에 mode·run_id·commit·stage·created_at·산출물 해시를 담는다
2  읽기 전용 판독기      현재 run_id·mode·commit과 **맞는** 마커만 완료로 센다.
                        맞지 않는 것은 ignored_markers로, 옛 이름은 legacy_markers로
                        따로 적는다
```

지키는 경계.

```
완료 선언   RUN_COMPLETE.json이 있을 때만. 이 모듈은 그것을 쓰지 않는다(읽기만)
삭제        기존 마커를 지우거나 옮기지 않는다
연결        아직 launcher에 붙이지 않는다 — 실행 중인 FULL의 control flow를 바꾸지
            않기 위해서다. 통합은 FULL 종료 후 판단이다
```

재현:
  python scripts/run_status.py <run_dir> --run-id p2idx_0821d --mode FULL \
      --commit <sha>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

MODES = ("CANARY", "FULL")
STAGES = ("m1_segments", "m2_frames", "m3_base", "mirror_frames",
          "m3_captions", "m4_index")
LEGACY_PREFIX = "STAGE_"
RUN_COMPLETE = "RUN_COMPLETE.json"


class StatusError(RuntimeError):
    pass


def marker_name(mode: str, stage: str) -> str:
    if mode not in MODES:
        raise StatusError(f"알 수 없는 mode {mode!r} — {list(MODES)}만 쓴다")
    if stage not in STAGES:
        raise StatusError(f"알 수 없는 stage {stage!r} — {list(STAGES)}만 쓴다")
    return f"{mode}_{LEGACY_PREFIX}{stage}_DONE.json"


def write_marker(run_dir, stage: str, mode: str, run_id: str, commit: str,
                 created_at: str, output_hash: str = None,
                 elapsed_sec: float = None) -> Path:
    """단계 완료 마커. **판독기가 현재 실행의 것인지 확인할 수 있는 형태**로 쓴다."""
    p = Path(run_dir) / marker_name(mode, stage)
    body = {"mode": mode, "run_id": run_id, "commit": commit, "stage": stage,
            "created_at": created_at}
    if output_hash is not None:
        body["output_hash"] = output_hash
    if elapsed_sec is not None:
        body["elapsed_sec"] = elapsed_sec
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return p


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def status(run_dir, run_id: str, mode: str, commit: str,
           process_alive: bool = None) -> dict:
    """현재 실행 기준 상태. **읽기만 한다.**"""
    if mode not in MODES:
        raise StatusError(f"알 수 없는 mode {mode!r}")
    d = Path(run_dir)
    if not d.is_dir():
        raise StatusError(f"run 디렉터리가 없다: {d}")

    complete, ignored, legacy = set(), [], []
    for p in sorted(d.iterdir()):
        if p.name.startswith(LEGACY_PREFIX) and p.name.endswith("_DONE"):
            legacy.append(p.name)
            continue
        if not p.name.endswith("_DONE.json"):
            continue
        body = _read(p)
        if not body:
            ignored.append(f"{p.name} (읽을 수 없다)")
            continue
        why = None
        if body.get("mode") != mode:
            why = f"mode {body.get('mode')}"
        elif body.get("run_id") != run_id:
            why = f"run_id {body.get('run_id')}"
        elif body.get("commit") != commit:
            why = f"commit {str(body.get('commit'))[:7]}"
        if why:
            ignored.append(f"{p.name} ({why})")
        elif body.get("stage") in STAGES:
            complete.add(body["stage"])

    stages, seen_pending = {}, False
    for s in STAGES:
        if s in complete:
            stages[s] = "complete"
        elif not seen_pending and process_alive:
            stages[s] = "running"
            seen_pending = True
        else:
            stages[s] = "pending"
            seen_pending = True

    done = (d / RUN_COMPLETE).is_file()
    return {"run_id": run_id, "mode": mode, "commit": commit,
            "run_dir": str(d), "stages": stages,
            "process_alive": process_alive,
            "ignored_markers": ignored, "legacy_markers": legacy,
            "run_complete": done,
            "validator": "passed" if done else "pending",
            "note": (f"완료 근거는 {RUN_COMPLETE}뿐이다. 마커는 관측이고, "
                     f"mode·run_id·commit이 맞지 않는 마커는 세지 않았다"),
            "legacy_marker_note": ("이름공간 없는 마커는 어느 mode가 남긴 것인지 "
                                   "알 수 없어 완료로 세지 않는다")}


def render(st: dict) -> str:
    lines = [f"run_id: {st['run_id']}", f"mode: {st['mode']}",
             f"commit: {st['commit']}"]
    lines += [f"{s}: {v}" for s, v in st["stages"].items()]
    lines.append(f"validator: {st['validator']}")
    lines.append(f"RUN_COMPLETE: {'true' if st['run_complete'] else 'false'}")
    if st["ignored_markers"]:
        lines.append("ignored markers (현재 실행과 불일치):")
        lines += [f"  {m}" for m in st["ignored_markers"]]
    if st["legacy_markers"]:
        lines.append("legacy markers (이름공간 없음 — 완료로 세지 않는다):")
        lines += [f"  {m}" for m in st["legacy_markers"]]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--mode", required=True, choices=list(MODES))
    ap.add_argument("--commit")
    ap.add_argument("--process-alive", action="store_true")
    a = ap.parse_args()
    commit = a.commit
    if not commit:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           encoding="utf-8")
        commit = (r.stdout or "").strip()
    print(render(status(a.run_dir, run_id=a.run_id, mode=a.mode, commit=commit,
                        process_alive=a.process_alive)), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
