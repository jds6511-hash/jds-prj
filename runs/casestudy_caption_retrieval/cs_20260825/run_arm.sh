#!/usr/bin/env bash
# 케이스 스터디 arm 1개 생성 — 격리 config로만 돌린다. 본 인덱스를 건드리지 않는다.
# 사용: bash runs/casestudy_caption_retrieval/cs_20260825/run_arm.sh 3b|4b
set -x
ARM=$1
V=pland_costco_hosting
RD=runs/casestudy_caption_retrieval/cs_20260825
CFG=$RD/config_$ARM.yaml
[ -f "$CFG" ] || { echo "config 없음: $CFG"; exit 1; }
echo "=== M3($ARM, captions-only) 시작 ($(date -Iseconds)) ==="
# --captions-only 단독. m3가 전 구간 caption을 비우고 재생성한다(resume no-op 방지).
# --force는 STT까지 다시 도는 전체 재실행이라 쓰지 않는다(가드가 조합 자체를 막는다).
python src/m3_generate.py --config "$CFG" --video-id $V --captions-only || exit 1
echo "M3_DONE $(date -Iseconds)" > "$RD/STAGE_${ARM}_m3_DONE"
echo "=== M4($ARM) 시작 ($(date -Iseconds)) ==="
python src/m4_index.py --config "$CFG" --video-id $V || exit 1
echo "M4_DONE $(date -Iseconds)" > "$RD/STAGE_${ARM}_m4_DONE"
echo "=== $ARM 완료 ($(date -Iseconds)) ==="
