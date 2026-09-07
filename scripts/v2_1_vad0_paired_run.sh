#!/usr/bin/env bash
# Tier 2 paired — S0(control) · S1(shadow_vad0)을 같은 코드·같은 입력으로 연속 실행한다.
#
#   S0  --contract v3                      shadow_vad0 OFF
#   S1  --contract v3 --shadow-vad0        shadow_vad0 ON
#
# 계약·모델·경계·표현·렌더러는 전부 같고, **claim evidence 자격만** 다르다.
# 두 arm은 별도 namespace에 clean run하며 S2 이후 산출물을 서로 재사용하지 않는다
# (지문에 evidence_policy가 들어가 재사용 자체가 막힌다).
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/b2_20260903/scripts/v2_1_vad0_paired_run.sh \
#       > /ssd/$USER/b2_20260903/vad0_paired.log 2>&1 < /dev/null &
set -euo pipefail
set -x

BASE="${BASE:-/ssd/$USER/b2_20260903}"
SEGMENTS="${SEGMENTS:-$BASE/b1_segments.json}"
CONFIG="${CONFIG:-$BASE/config_server.yaml}"
MEASUREMENTS="${MEASUREMENTS:-$BASE/runs/stt_sanitation_v1/full_xekZO4n4QuE/measurements.json}"
VIDEO_ID="${VIDEO_ID:-full_xekZO4n4QuE}"
PRODUCER="${PRODUCER:-be35249a}"
WINDOW_SEC="${WINDOW_SEC:-60}"
STAMP="${STAMP:-$(date +%Y%m%d)}"
PY="${PY:-/ssd/$USER/envs/prj/bin/python}"

export HF_HOME="${HF_HOME:-/ssd/$USER/cache}"
export PYTHONUNBUFFERED=1

run_arm() {
  local arm="$1"; shift
  echo "=== $arm 시작 ($(date)) ==="
  "$PY" "$BASE/scripts/v2_1_b2_orchestrate.py" \
    --segments "$SEGMENTS" \
    --run-dir "$BASE/runs/vad0_${arm}" \
    --config "$CONFIG" \
    --video-id "$VIDEO_ID" \
    --run-id "vad0-${arm}-${STAMP}" \
    --producer-version "$PRODUCER" \
    --model-id "Qwen/Qwen2.5-7B-Instruct" \
    --max-new-tokens 512 \
    --window-sec "$WINDOW_SEC" \
    --contract v3 \
    --poll-gpu \
    --clean \
    "$@" || exit 1
  echo "=== $arm 완료 ($(date)) ==="
}

echo "=== vad0 paired run 시작 ($(date)) ==="
"$PY" -c "import hashlib,sys;print('segments sha256', hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$SEGMENTS"
"$PY" -c "import hashlib,sys;print('measurements sha256', hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$MEASUREMENTS"
git -C "$BASE" rev-parse HEAD

run_arm s0_control
run_arm s1_shadow --shadow-vad0 --vad-measurements "$MEASUREMENTS"

echo "=== vad0 paired run 완료 ($(date)) ==="
