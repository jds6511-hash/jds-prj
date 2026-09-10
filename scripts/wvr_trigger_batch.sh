#!/usr/bin/env bash
# W00 trigger isolation — 동일 픽셀 2×2 (A P0M0 · B P0M1 · C P1M0 · D P1M1).
#
# 사전등록: docs/preregistration/WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md
# self-check(픽셀/metadata 분리)가 실패하면 추론하지 않고 끝낸다 — hard blocker다.
# 실패한 arm은 재시도하지 않는다. recovery·prompt 수정으로 넘어가지 않는다.
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/jds-prj/scripts/wvr_trigger_batch.sh \
#       > /ssd/$USER/jds-prj/runs/wvr_light_v1/trigger_v1.log 2>&1 < /dev/null &
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

echo "=== trigger validator ($(date)) commit $WVR_CODE_GIT_HEAD ==="
"$PY" "$BASE/scripts/wvr_trigger_validate.py" --runs "$OUT_DIR" || exit 1

echo "=== trigger self-check ($(date)) ==="
"$PY" "$BASE/scripts/wvr_trigger_selfcheck.py" --video "$VIDEO" \
  --runs "$OUT_DIR" || { echo "=== IMPLEMENTATION_BLOCKED — 추론하지 않는다 ==="; exit 1; }

echo "=== trigger 시작 ($(date)) ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

for arm in A B C D; do
  echo "=== $arm 시작 ($(date)) ==="
  "$PY" "$BASE/scripts/wvr_trigger_run.py" \
    --video "$VIDEO" \
    --arm "$arm" \
    --runs-dir "$OUT_DIR" || echo "=== $arm 실패 기록됨 (재시도하지 않는다) ==="
  echo "=== $arm 완료 ($(date)) ==="
done

echo "=== trigger 완료 ($(date)) ==="
ls -l "$OUT_DIR"/trigger_v1_[ABCD].json | wc -l
