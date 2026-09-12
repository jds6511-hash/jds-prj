#!/usr/bin/env bash
# WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1 — 서버 실행 (1 cell).
#
# 사전등록: docs/preregistration/WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md
# §3 invocation 동결. 유일한 변경점은 --contract v3 다.
# --max-new-tokens · --window-sec 은 **인자를 주지 않는다**(기본값 동결).
# 실행은 1회다. retry 금지. visual inference 없음.
#
# 사용 (서버, 격리 클론에서):
#   preflight:  bash scripts/rei_c01_beta_v3_run.sh preflight
#   본 실행:    setsid nohup bash scripts/rei_c01_beta_v3_run.sh run \
#                 > /ssd/$USER/logs/rei_c01_beta_v3.log 2>&1 < /dev/null &
#
# 비대화형 SSH는 .bashrc를 안 읽으므로 HF_HOME을 여기서 준다.
set -uo pipefail

MODE="${1:-preflight}"
BASE="${BASE:-/ssd/$USER/jds-prj-rei-c01}"
export BASE
PY="${PY:-/ssd/$USER/envs/prj/bin/python}"
CELL="$BASE/runs/rei_c01_beta_v3/b_beta_v3"
CFG="$BASE/configs/rei_c01_beta.yaml"
VIDEO_ID="rei_c01_nonoverlap"
PRODUCER="${PRODUCER:-18d9dce}"

export HF_HOME="${HF_HOME:-/ssd/$USER/cache}"
export PYTHONUNBUFFERED=1
export PYTHONPATH="$BASE/src:${PYTHONPATH:-}"

cd "$BASE"

if [ "$MODE" = "preflight" ]; then
  # 모델을 올리지 않는다. loader 계약과 contract 해석만 확인한다.
  "$PY" - <<'PYEOF'
import os, sys
base = os.environ["BASE"]
sys.path.insert(0, os.path.join(base, "src"))
import common, v2_1_prompt as vp

cfg = common.load_config("configs/rei_c01_beta.yaml")
wdir = common.work_dir(cfg, "rei_c01_nonoverlap")
doc = common.load_segments(wdir / "segments.json",
                           require=["subtitle", "caption"],
                           seg_len=cfg["seg_len_sec"])
contract = vp.resolve_contract("v3")
assert contract["version"] == vp.PROMPT_VERSION_V3, contract["version"]
assert list(contract["output"]["optional"]) == [], contract["output"]
print("PREFLIGHT_OK n_segments=%d seg_len=%s contract=%s"
      % (doc["n_segments"], cfg["seg_len_sec"], contract["version"]))
PYEOF
  exit $?
fi

T0="$(date -u +%FT%TZ)"
echo "=== b_beta_v3 (engine β · contract v3) 시작 $T0 ==="
git -C "$BASE" rev-parse HEAD
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

"$PY" "$BASE/scripts/v2_1_b2_orchestrate.py" \
    --segments "$CELL/segments.json" \
    --run-dir "$CELL/b2run" \
    --config "$CFG" \
    --video-id "$VIDEO_ID" \
    --run-id "rei-c01-b_beta_v3" \
    --producer-version "$PRODUCER" \
    --model-id "Qwen/Qwen2.5-7B-Instruct" \
    --contract v3 \
    --poll-gpu --clean \
    2>&1 | tee "$CELL/run.log"
CODE=${PIPESTATUS[0]}
T1="$(date -u +%FT%TZ)"

"$PY" - "$CODE" "$T0" "$T1" <<'PYEOF'
import json, os, subprocess, sys
code, t0, t1 = int(sys.argv[1]), sys.argv[2], sys.argv[3]
base = os.environ["BASE"]
head = subprocess.run(["git", "-C", base, "rev-parse", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
out = os.path.join(base, "runs", "rei_c01_beta_v3", "b_beta_v3",
                   "execution_record.json")
json.dump({"event": "WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1",
           "cell": "b_beta_v3", "view": "NONOVERLAP_VIEW", "contract": "v3",
           "exit_code": code, "started_utc": t0, "ended_utc": t1,
           "code_git_head": head, "host": os.uname().nodename,
           "model": "Qwen/Qwen2.5-7B-Instruct", "llm_4bit": False,
           "new_visual_inference": 0, "new_stt": 0, "retry_count": 0},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("RECORD", out, "exit", code)
PYEOF

echo "=== b_beta_v3 종료 exit=$CODE $T1 ==="
