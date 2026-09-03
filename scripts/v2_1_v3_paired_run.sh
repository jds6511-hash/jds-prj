#!/usr/bin/env bash
# v3 paired 비교 — R0(v2)와 R1(v3)을 같은 코드·같은 입력으로 연속 실행한다.
#
#   R0  --contract v2   summary + dialogue
#   R1  --contract v3   summary only
#
# 계약 외에는 아무것도 바꾸지 않는다. R0를 보고 v3를 고쳐 R1을 돌리는 경로를 만들지
# 않으려고 한 스크립트에 묶었다 — 두 arm은 같은 실행에서 끝난다.
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/b2_20260903/scripts/v2_1_v3_paired_run.sh \
#       > /ssd/$USER/b2_20260903/v3_paired.log 2>&1 < /dev/null &
#
# 경로는 전부 절대경로다. 비대화형 SSH는 .bashrc를 읽지 않으므로 HF_HOME을 여기서 준다.
set -euo pipefail
set -x

BASE="${BASE:-/ssd/$USER/b2_20260903}"
SEGMENTS="${SEGMENTS:-$BASE/b1_segments.json}"
CONFIG="${CONFIG:-$BASE/config_server.yaml}"
VIDEO_ID="${VIDEO_ID:-full_xekZO4n4QuE}"
PRODUCER="${PRODUCER:-be35249a}"
WINDOW_SEC="${WINDOW_SEC:-60}"
STAMP="${STAMP:-$(date +%Y%m%d)}"
PY="${PY:-/ssd/$USER/envs/prj/bin/python}"

export HF_HOME="${HF_HOME:-/ssd/$USER/cache}"
export PYTHONUNBUFFERED=1

run_arm() {
  local arm="$1" contract="$2"
  echo "=== $arm ($contract) 시작 ($(date)) ==="
  "$PY" "$BASE/scripts/v2_1_b2_orchestrate.py" \
    --segments "$SEGMENTS" \
    --run-dir "$BASE/runs/${arm}_${contract}" \
    --config "$CONFIG" \
    --video-id "$VIDEO_ID" \
    --run-id "v3paired-${arm}-${STAMP}" \
    --producer-version "$PRODUCER" \
    --model-id "Qwen/Qwen2.5-7B-Instruct" \
    --max-new-tokens 512 \
    --window-sec "$WINDOW_SEC" \
    --contract "$contract" \
    --poll-gpu \
    --clean || exit 1
  echo "=== $arm ($contract) 완료 ($(date)) ==="
}

echo "=== paired run 시작 ($(date)) ==="
"$PY" -c "import hashlib,sys;print('segments sha256', hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$SEGMENTS"
git -C "$BASE" rev-parse HEAD

run_arm r0 v2
run_arm r1 v3

echo "=== paired run 완료 ($(date)) ==="
