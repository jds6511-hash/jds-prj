---
name: gpu-batch
description: 로컬 GPU(RTX 3060 6GB)에서 장시간 파이프라인 배치(M1~M6, 재캡셔닝, ablation)를 백그라운드로 실행하는 규약. 인덱싱·재실행·ablation 배치를 걸 때 사용.
---

# GPU 배치 실행 규약

## 작성

- bash 스크립트로 작성(scratchpad), `set -x` + 단계별 `echo "=== 단계명 ($(date)) ==="` +
  각 명령 `|| exit 1`. Bash 도구 `run_in_background: true`로 실행 — 완료 시 자동 알림.
- **순서 불변식**: m3(재캡셔닝 포함) → m4 → m6. 재캡셔닝 후 m4 생략 금지
  (text_hash가 M5 로드에서 ValueError로 차단하지만, 배치 안에서 m4까지 돌리는 게 규약).
- 변형(ablation) 실험은 반드시 격리 config(config_*.yaml, paths.work/results 분리) 사용.
  변형 config는 항상 config.yaml에서 재생성(수동 편집 금지 — threshold confound 사고 전례).

## 실행 중

- `sleep` 금지. 진행 확인은 출력 파일 tail. 주기 보고 요청 시 ScheduleWakeup/loop 사용,
  **재예약 누락 금지**(전례 있음).
- 콘솔 한글은 cp949로 깨진다 — 진행 판단은 "=== 마커·파일 존재"로, 수치는 UTF-8 JSON으로.

## 소요 기준 (실측)

- M1 수 초 / M2 ~25분(33분 영상) / M3 Whisper+캡션 ~75분(395세그) / m4 ~2분 / m6 ~2분
- VLM(Qwen2.5-VL-3B-4bit) 로드 ~30초 — 재캡셔닝은 영상당 로드 1회.
- 완료 후 반드시 pipeline-verify 스킬로 검증.
