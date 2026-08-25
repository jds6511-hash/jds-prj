#!/usr/bin/env bash
set -x
V=e2e_scene_fast
RUN=runs/e2e_external/e2e_external_core_2026-08-25/$V
echo "=== M1 시작 ($(date -Iseconds)) ==="
python src/m1_preprocess.py --config config.yaml --video-id $V || exit 1
echo "M1_DONE $(date -Iseconds)" > "$RUN/STAGE_m1_DONE"
echo "=== M2 시작 ($(date -Iseconds)) ==="
python src/m2_keyframe.py --config config.yaml --video-id $V || exit 1
echo "M2_DONE $(date -Iseconds)" > "$RUN/STAGE_m2_DONE"
echo "=== M3 시작 ($(date -Iseconds)) ==="
python src/m3_generate.py --config config.yaml --video-id $V || exit 1
echo "M3_DONE $(date -Iseconds)" > "$RUN/STAGE_m3_DONE"
echo "=== M4 시작 ($(date -Iseconds)) ==="
python src/m4_index.py --config config.yaml --video-id $V || exit 1
echo "M4_DONE $(date -Iseconds)" > "$RUN/STAGE_m4_DONE"
echo "=== 전체 완료 ($(date -Iseconds)) ==="
