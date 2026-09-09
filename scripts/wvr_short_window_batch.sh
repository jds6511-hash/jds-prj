#!/usr/bin/env bash
# SHORT_WINDOW_V1 — 48초 창 3개 × arm 2개 = 6회. 창×arm마다 fresh process 1회.
#
# 사전등록: docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md
# 유일한 변경은 context 길이(180초 → 48초)다. V2 동결값이 하나라도 다르면
# 실행기가 GPU를 쓰기 전에 중단한다(preflight).
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/jds-prj/scripts/wvr_short_window_batch.sh \
#       > /ssd/$USER/jds-prj/runs/wvr_light_v1/short_window.log 2>&1 < /dev/null &
set -euo pipefail
set -x

BASE="${BASE:-/ssd/$USER/jds-prj}"
VIDEO="${VIDEO:-$BASE/data/videos/full_xekZO4n4QuE.mp4}"
OUT_DIR="${OUT_DIR:-$BASE/runs/wvr_light_v1}"
PY="${PY:-/ssd/$USER/envs/prj/bin/python}"

export HF_HOME="${HF_HOME:-/ssd/$USER/cache}"
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export WVR_CODE_GIT_HEAD="$(git -C "$BASE" rev-parse HEAD)"

echo "=== short window batch 시작 ($(date)) commit $WVR_CODE_GIT_HEAD ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

for window in P1 P2 P3; do
  for arm in S0 S1; do
    echo "=== $window $arm 시작 ($(date)) ==="
    "$PY" "$BASE/scripts/wvr_short_window_run.py" \
      --video "$VIDEO" \
      --window "$window" \
      --arm "$arm" \
      --out-dir "$OUT_DIR" || exit 1
    echo "=== $window $arm 완료 ($(date)) ==="
  done
done

echo "=== short window batch 완료 ($(date)) ==="
ls -l "$OUT_DIR"/short_window_P*_S*.json
