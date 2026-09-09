#!/usr/bin/env bash
# W00 재현성 — 동일 입력·동일 설정으로 fresh process 3회. retry가 아니다.
#
# 사전등록: docs/preregistration/WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md
# 세 실행 모두 사전등록된 관측이다. 성공 run을 골라 쓰지 않는다.
# 실패해도 다시 돌리지 않는다 — 그 run의 상태를 그대로 기록한다.
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/jds-prj/scripts/wvr_w00_repro_batch.sh \
#       > /ssd/$USER/jds-prj/runs/wvr_light_v1/w00_repro.log 2>&1 < /dev/null &
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

echo "=== w00 repro 시작 ($(date)) commit $WVR_CODE_GIT_HEAD ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

for run in R1 R2 R3; do
  echo "=== $run 시작 ($(date)) ==="
  "$PY" "$BASE/scripts/wvr_w00_repro_run.py" \
    --video "$VIDEO" \
    --run "$run" \
    --runs-dir "$OUT_DIR" || echo "=== $run 실패 기록됨 (재시도하지 않는다) ==="
  echo "=== $run 완료 ($(date)) ==="
done

echo "=== w00 repro 완료 ($(date)) ==="
ls -l "$OUT_DIR"/w00_repro_R*.json | wc -l
