"""STITCHING_SHADOW_V1 리뷰어 판정 기록기 (2026-09-10).

사전등록:
`docs/preregistration/WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md`

```
executor는 판정을 채우지 않는다 — 입력 파일이 있을 때만 기록한다
어휘        relation 5개 · 상위 판정 3개 (그 밖은 거부)
미기록      NOT_ADJUDICATED로 남는다
reveal      22 overlap 전부 기록된 뒤에만 mapping reveal이 허용된다
```

사용:

```
python scripts/wvr_stitch_verdicts.py --runs runs/wvr_light_v1            # 현재 상태
python scripts/wvr_stitch_verdicts.py --runs ... --input verdicts.json    # 기록
python scripts/wvr_stitch_verdicts.py --runs ... --reveal                 # 조건 충족 시
```

입력 형식:

```json
{"verdicts": [{"overlap_id": "O02", "relation": "CONTINUATION",
               "top_verdict": "STITCHABLE", "note": "..."}]}
```
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_stitch_v1 as st                                 # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md")
VERDICTS_NAME = "stitch_v1_verdicts.json"
MAPPING_NAME = "stitch_v1_blind_map.json"


class VerdictError(RuntimeError):
    """판정 기록 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def current(runs: Path) -> dict:
    path = runs / VERDICTS_NAME
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema": "wvr_stitch_v1_verdicts", "event": st.EVENT,
            "prereg": PREREG, **st.parse_verdicts(None),
            "recorded_by": "reviewer", "code_git_head": git_head()}


def record(runs: Path, payload: dict) -> dict:
    if st.VERDICT_BY_EXECUTOR:
        raise VerdictError("executor는 판정을 채우지 않는다")
    state = st.parse_verdicts(payload)
    return {"schema": "wvr_stitch_v1_verdicts", "event": st.EVENT,
            "prereg": PREREG, **state, "recorded_by": "reviewer",
            "code_git_head": git_head()}


def reveal(runs: Path) -> dict:
    state = current(runs)
    gate = st.reveal_allowed(state)
    if not gate["allowed"]:
        raise VerdictError("mapping reveal 조건 미충족: %d/%d 판정 (%s)"
                           % (gate["adjudicated_count"],
                              gate["expected_count"], gate["reason"]))
    path = runs / MAPPING_NAME
    if not path.is_file():
        raise VerdictError("mapping 파일이 없다: %s" % MAPPING_NAME)
    mapping = json.loads(path.read_text(encoding="utf-8"))["mapping"]
    rows = []
    for row in state["verdicts"]:
        pair = mapping[row["overlap_id"]]
        rows.append({**row, "A": pair["A"], "B": pair["B"],
                     "start_sec": pair["start_sec"],
                     "end_sec": pair["end_sec"]})
    return {"revealed": True, "rows": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="stitching 판정 기록")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--input")
    parser.add_argument("--reveal", action="store_true")
    args = parser.parse_args(argv)

    runs = Path(args.runs)
    if args.reveal:
        revealed = reveal(runs)
        for row in revealed["rows"]:
            print("%s %5.0f-%5.0f  A=%s B=%s  %s / %s"
                  % (row["overlap_id"], row["start_sec"], row["end_sec"],
                     row["A"], row["B"], row["relation"], row["top_verdict"]))
        return 0

    if args.input:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        state = record(runs, payload)
        (runs / VERDICTS_NAME).write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        state = current(runs)

    print("adjudicated=%d/%d complete=%s"
          % (state["adjudicated_count"], state["expected_count"],
             state["complete"]))
    print("relation_counts=%s" % state["relation_counts"])
    print("top_verdict_counts=%s" % state["top_verdict_counts"])
    print("final_verdict=%s (executor 계산 안 함: %s)"
          % (state["final_verdict"], state["final_verdict_by_executor"]))
    gate = st.reveal_allowed(state)
    print("mapping reveal allowed=%s reason=%s"
          % (gate["allowed"], gate["reason"] or "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
