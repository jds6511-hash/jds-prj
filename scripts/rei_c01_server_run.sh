#!/usr/bin/env bash
# WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1 — 서버 text generation.
#
# 사전등록: docs/preregistration/WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1_2026-09-11.md
# §6 동결 순서  Aα → Bα → Aβ → Bβ.  좋은 결과를 얻으려는 retry 금지.
# visual inference 없음 — 텍스트 생성(Qwen2.5-7B-Instruct)만 한다.
#
# 사용 (서버, 격리 클론에서):
#   preflight:  bash scripts/rei_c01_server_run.sh preflight
#   본 실행:    setsid nohup bash scripts/rei_c01_server_run.sh run \
#                 > /ssd/$USER/logs/rei_c01_run.log 2>&1 < /dev/null &
#
# 비대화형 SSH는 .bashrc를 안 읽으므로 HF_HOME을 여기서 준다.
set -uo pipefail

MODE="${1:-preflight}"
BASE="${BASE:-/ssd/$USER/jds-prj-rei-c01}"
export BASE
PY="${PY:-/ssd/$USER/envs/prj/bin/python}"
RUNS="$BASE/runs/rei_c01"
CFG_A="$BASE/configs/rei_c01_alpha.yaml"
CFG_B="$BASE/configs/rei_c01_beta.yaml"
# adapter(= β의 segments 생성자) code revision
PRODUCER="${PRODUCER:-18d9dce}"

export HF_HOME="${HF_HOME:-/ssd/$USER/cache}"
export PYTHONUNBUFFERED=1
export PYTHONPATH="$BASE/src:${PYTHONPATH:-}"

cd "$BASE"

if [ "$MODE" = "preflight" ]; then
  # 모델을 올리지 않는다. loader/schema 계약만 확인한다.
  "$PY" - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(os.environ["BASE"], "src"))
import common
for cfg_path, vid in (("configs/rei_c01_alpha.yaml", "rei_c01_overlap"),
                      ("configs/rei_c01_alpha.yaml", "rei_c01_nonoverlap"),
                      ("configs/rei_c01_beta.yaml", "rei_c01_overlap"),
                      ("configs/rei_c01_beta.yaml", "rei_c01_nonoverlap")):
    cfg = common.load_config(cfg_path)
    wdir = common.work_dir(cfg, vid)
    doc = common.load_segments(wdir / "segments.json",
                               require=["subtitle", "caption"],
                               seg_len=cfg["seg_len_sec"])
    print("PREFLIGHT_OK", cfg_path, vid, "n_segments=%d" % doc["n_segments"],
          "seg_len=%s" % cfg["seg_len_sec"])
PYEOF
  exit $?
fi

record() {  # cell exit_code start end
  "$PY" - "$1" "$2" "$3" "$4" <<'PYEOF'
import json, subprocess, sys, os
cell, code, t0, t1 = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
base = os.environ["BASE"]
head = subprocess.run(["git", "-C", base, "rev-parse", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
out = os.path.join(base, "runs", "rei_c01", cell, "execution_record.json")
json.dump({"event": "WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1",
           "cell": cell, "exit_code": code, "started_utc": t0, "ended_utc": t1,
           "code_git_head": head, "host": os.uname().nodename,
           "model": "Qwen/Qwen2.5-7B-Instruct", "llm_4bit": False,
           "new_visual_inference": 0, "retry_count": 0},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("RECORD", out, "exit", code)
PYEOF
}

run_alpha() {  # cell video_id
  local cell="$1" vid="$2"
  local t0 t1
  t0="$(date -u +%FT%TZ)"
  echo "=== $cell (engine α) 시작 $t0 ==="
  "$PY" "$BASE/src/m8_report.py" --config "$CFG_A" --video-id "$vid" \
      2>&1 | tee "$RUNS/$cell/run.log"
  local code=${PIPESTATUS[0]}
  t1="$(date -u +%FT%TZ)"
  if [ "$code" -eq 0 ]; then
    cp "$BASE/work_rei_c01/$vid/report.json" "$RUNS/$cell/report.json"
  fi
  record "$cell" "$code" "$t0" "$t1"
  echo "=== $cell 종료 exit=$code $t1 ==="
}

run_beta() {  # cell video_id
  local cell="$1" vid="$2"
  local t0 t1
  t0="$(date -u +%FT%TZ)"
  echo "=== $cell (engine β) 시작 $t0 ==="
  "$PY" "$BASE/scripts/v2_1_b2_orchestrate.py" \
      --segments "$RUNS/$cell/segments.json" \
      --run-dir "$RUNS/$cell/b2run" \
      --config "$CFG_B" \
      --video-id "$vid" \
      --run-id "rei-c01-$cell" \
      --producer-version "$PRODUCER" \
      --model-id "Qwen/Qwen2.5-7B-Instruct" \
      --poll-gpu --clean \
      2>&1 | tee "$RUNS/$cell/run.log"
  local code=${PIPESTATUS[0]}
  t1="$(date -u +%FT%TZ)"
  record "$cell" "$code" "$t0" "$t1"
  echo "=== $cell 종료 exit=$code $t1 ==="
}

echo "=== REI C01 본 실행 시작 $(date -u +%FT%TZ) ==="
git -C "$BASE" rev-parse HEAD
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

# 동결 순서. 한 cell이 실패해도 나머지는 그대로 돌린다(실패도 계측 대상).
run_alpha a_alpha rei_c01_overlap
run_alpha b_alpha rei_c01_nonoverlap
run_beta  a_beta  rei_c01_overlap
run_beta  b_beta  rei_c01_nonoverlap

echo "=== REI C01 본 실행 완료 $(date -u +%FT%TZ) ==="
