#!/usr/bin/env bash
# 실패 child C0 [0,24)의 12초 재분해 — D0/D1/D2를 각각 fresh process로 1회.
#
# 사전등록:
#   docs/preregistration/WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1_2026-09-09.md
# 실패한 child는 재시도하지 않는다 — 그 상태를 그대로 기록한다(INVALID provenance).
# 6초/3초로의 자동 재귀는 금지다. C1·C2는 재실행하지 않는다.
# packet·frame audit은 technical PASS일 때만 별도 단계에서 만든다.
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/jds-prj/scripts/wvr_recur_batch.sh \
#       > /ssd/$USER/jds-prj/runs/wvr_light_v1/recur_v1.log 2>&1 < /dev/null &
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

echo "=== recursive validator ($(date)) commit $WVR_CODE_GIT_HEAD ==="
"$PY" "$BASE/scripts/wvr_recur_validate.py" --runs "$OUT_DIR" || exit 1

echo "=== recursive 시작 ($(date)) ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

for child in D0 D1 D2; do
  echo "=== $child 시작 ($(date)) ==="
  "$PY" "$BASE/scripts/wvr_recur_run.py" \
    --video "$VIDEO" \
    --child "$child" \
    --runs-dir "$OUT_DIR" || echo "=== $child 실패 기록됨 (재시도하지 않는다) ==="
  echo "=== $child 완료 ($(date)) ==="
done

echo "=== recursive 완료 ($(date)) ==="
ls -l "$OUT_DIR"/recur_v1_D*.json | wc -l
