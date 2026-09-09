#!/usr/bin/env bash
# SHADOW_V1 — C01 전체를 48초 창 · 24초 stride로 tile해 창마다 fresh process 1회.
#
# 사전등록: docs/preregistration/WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md
# inference 설정은 SHORT_WINDOW_V1 S0 대비 변경 없음(실행기 preflight가 검사한다).
# 실패한 창은 재시도하지 않는다 — INVALID provenance를 남기고 계속 진행한다.
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/jds-prj/scripts/wvr_shadow_batch.sh \
#       > /ssd/$USER/jds-prj/runs/wvr_light_v1/shadow_v1.log 2>&1 < /dev/null &
set -uo pipefail
set -x

BASE="${BASE:-/ssd/$USER/jds-prj}"
VIDEO="${VIDEO:-$BASE/data/videos/full_xekZO4n4QuE.mp4}"
OUT_DIR="${OUT_DIR:-$BASE/runs/wvr_light_v1}"
PY="${PY:-/ssd/$USER/envs/prj/bin/python}"

export HF_HOME="${HF_HOME:-/ssd/$USER/cache}"
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export WVR_CODE_GIT_HEAD="$(git -C "$BASE" rev-parse HEAD)"

echo "=== shadow batch 시작 ($(date)) commit $WVR_CODE_GIT_HEAD ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

failed=0
for index in $(seq -w 0 23); do
  window="W${index}"
  echo "=== $window 시작 ($(date)) ==="
  "$PY" "$BASE/scripts/wvr_shadow_run.py" \
    --video "$VIDEO" \
    --window "$window" \
    --out-dir "$OUT_DIR" || { failed=$((failed + 1)); \
      echo "=== $window INVALID (재시도하지 않는다) ==="; }
  echo "=== $window 완료 ($(date)) ==="
done

echo "=== shadow batch 완료 ($(date)) invalid_or_failed=$failed ==="
ls -l "$OUT_DIR"/shadow_v1_W*.json | wc -l
