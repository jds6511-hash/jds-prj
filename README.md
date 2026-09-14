# JDS Video Intelligence

긴 영상에서 사용자가 찾는 장면을 검색하고, 영상 전체의 주요 활동 흐름을 한국어 보고서로 정리하는 연구·구현 프로젝트입니다.

이 공개 저장소는 최종 발표와 재현에 필요한 코드, 검증 테스트, 대표 결과만 담은 정리본입니다. 개발 중 생성된 대규모 raw inference, 중간 probe, 폐기된 실험 산출물은 포함하지 않습니다. 주요 시행착오와 설계 전환은 [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md)에 요약했습니다.

처음 코드를 확인한다면 [`START_HERE.md`](START_HERE.md)에서 두 개의 최종 공개 진입점부터 보는 것을 권장합니다.

## 구성

### Track A — 자연어 장면 검색

```text
Video
→ 5초 구간 분할 및 대표 프레임 선택
→ Whisper STT + Qwen2.5-VL 장면 캡션
→ KURE-v1 임베딩
→ 채널별 z-score 정규화 및 융합
→ timestamp가 포함된 검색 결과
```

공식 고정 test 39질의에서 자막 단독 대비 자막+화면 융합 성능은 다음과 같습니다.

| 지표 | 자막 단독 | 자막+화면 |
|---|---:|---:|
| MRR | 0.649 | **0.829** |
| Hit@1 | 0.564 | **0.769** |
| Hit@5 | 0.769 | **0.872** |

특히 장면형 질의 13건의 Hit@1은 0.000에서 0.615로 개선되었습니다. 원본 측정값은 [`results/retrieval_eval_test.json`](results/retrieval_eval_test.json)에 보존했습니다.

### Track C — 영상 전체 보고서

```text
Video
→ Qwen3-VL 구간 관찰
→ overlap 중복을 제거한 canonical activity flow
→ Overview
→ Analysis / Conclusion
→ Markdown / HWPX
```

현재 공개 기준선은 reviewer가 `WHOLE_VIDEO_REPORT_PASS`로 판정한 `WVR_WHOLE_VIDEO_REPORT_V2`입니다. 보고서 생성은 관찰된 활동과 그 순서만 사용하며, 의도·감정·장소·원인 같은 비시각적 맥락 추론을 차단합니다. 대표 산출물은 [`examples/whole_video_report.md`](examples/whole_video_report.md)와 [`examples/whole_video_report.hwpx`](examples/whole_video_report.hwpx)에 있습니다.

## 저장소 구조

```text
src/jds_video/scene_search.py        장면 검색 공개 진입점
src/jds_video/whole_video_report.py  전체 영상 보고서 공개 진입점
src/jds_video/_internal/             검증된 내부 구현
scripts/   재현·실행 진입점
tests/     공개 코드에 대응하는 단위·계약 테스트
results/   고정 검색 평가 결과
examples/  reviewer-PASS 대표 보고서
docs/      최종 발표 자료와 개발 이력 요약
```

## 설치

Python 3.10 이상과 CUDA 지원 PyTorch 환경을 권장합니다.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
# 필요하면 config.yaml의 모델·경로 설정을 환경에 맞게 수정
```

모델 가중치와 원본 영상은 저장소에 포함하지 않습니다. 전체 영상 보고서 경로의 frozen vision model은 `Qwen/Qwen3-VL-8B-Instruct` revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`이며, 24GB급 GPU 환경을 기준으로 검증했습니다.

## 실행 예시

장면 검색 데모:

```bash
python scripts/demo.py --help
```

whole-video report 재현 진입점(고정 중간 산출물이 있는 환경에서 실행):

```bash
python scripts/wvr_whole_video_report_v2_run.py
```

## 테스트

```bash
python -m pytest -q
```

공식 test 결과는 이미 생성된 고정 artifact를 공개한 것이며, 저장소를 내려받는 것만으로 모델 가중치·원본 데이터·GPU inference가 자동 재실행되지는 않습니다.

## 공개 범위

- 포함: 최종 발표 코드, 검증 테스트, 고정 평가 JSON, reviewer-PASS 보고서 예시, 개발 이력 요약
- 제외: 원본 영상, 모델 가중치, 개인정보·비밀키, 대규모 raw output, 중간 실패 artifact, 사용하지 않는 과거 발표본
