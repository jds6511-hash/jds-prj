#!/usr/bin/env bash
# W00 subdivision recovery — C0/C1/C2를 각각 fresh process로 1회.
#
# 사전등록: docs/preregistration/WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md
# 실패한 child는 재시도하지 않는다 — 그 상태를 그대로 기록한다(INVALID provenance).
# packet·frame audit은 technical recovery PASS일 때만 별도 단계에서 만든다.
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/jds-prj/scripts/wvr_subdiv_batch.sh \
#       > /ssd/$USER/jds-prj/runs/wvr_light_v1/subdiv_v1.log 2>&1 < /dev/null &
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

echo "=== subdivision validator ($(date)) commit $WVR_CODE_GIT_HEAD ==="
"$PY" "$BASE/scripts/wvr_subdiv_validate.py" --runs "$OUT_DIR" || exit 1

echo "=== subdivision 시작 ($(date)) ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

for child in C0 C1 C2; do
  echo "=== $child 시작 ($(date)) ==="
  "$PY" "$BASE/scripts/wvr_subdiv_run.py" \
    --video "$VIDEO" \
    --child "$child" \
    --runs-dir "$OUT_DIR" || echo "=== $child 실패 기록됨 (재시도하지 않는다) ==="
  echo "=== $child 완료 ($(date)) ==="
done

echo "=== subdivision 완료 ($(date)) ==="
ls -l "$OUT_DIR"/subdiv_v1_C*.json | wc -l
