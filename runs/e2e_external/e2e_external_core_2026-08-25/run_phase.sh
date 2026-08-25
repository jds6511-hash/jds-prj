#!/usr/bin/env bash
# 외부 E2E arm 실행 — 배포 config만 쓴다. 사용: bash run_phase.sh <e2e_id>
set -x
V=$1
RUN=runs/e2e_external/e2e_external_core_2026-08-25/$V
mkdir -p "$RUN"
for S in m1_preprocess m2_keyframe m3_generate m4_index; do
  N=${S%%_*}
  echo "=== ${N^^} 시작 ($(date -Iseconds)) ==="
  python src/$S.py --config config.yaml --video-id $V || exit 1
  echo "${N}_DONE $(date -Iseconds)" > "$RUN/STAGE_${N}_DONE"
done
echo "=== $V 완료 ($(date -Iseconds)) ==="
