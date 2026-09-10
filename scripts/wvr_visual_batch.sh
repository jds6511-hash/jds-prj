#!/usr/bin/env bash
# visual content isolation — arm E 하나만 (W05 픽셀 + Trigger A 시간 인코딩).
#
# 사전등록: docs/preregistration/WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md
# 기존 세 칸(Trigger A · Trigger D · SHADOW W05)은 재실행하지 않는다.
# self-check가 실패하면 추론하지 않고 끝낸다. 실패해도 재시도하지 않는다.
#
# 사용 (서버):
#   setsid nohup bash /ssd/$USER/jds-prj/scripts/wvr_visual_batch.sh \
#       > /ssd/$USER/jds-prj/runs/wvr_light_v1/visual_v1.log 2>&1 < /dev/null &
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

echo "=== visual validator ($(date)) commit $WVR_CODE_GIT_HEAD ==="
"$PY" "$BASE/scripts/wvr_visual_validate.py" --runs "$OUT_DIR" || exit 1

echo "=== visual self-check ($(date)) ==="
"$PY" "$BASE/scripts/wvr_visual_selfcheck.py" --video "$VIDEO" \
  --runs "$OUT_DIR" || { echo "=== SELFCHECK 실패 — 추론하지 않는다 ==="; exit 1; }

echo "=== visual E 시작 ($(date)) ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

"$PY" "$BASE/scripts/wvr_visual_run.py" \
  --video "$VIDEO" \
  --runs-dir "$OUT_DIR" || echo "=== E 실패 기록됨 (재시도하지 않는다) ==="

echo "=== visual 완료 ($(date)) ==="
ls -l "$OUT_DIR"/visual_v1_E.json | wc -l
