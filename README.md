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
→ 구간 관찰(보이는 것) + STT 발화(말한 것)
→ 두 채널을 같은 사건으로 묶기
→ 사건 단위 요약 · 근거 검증
→ 보고 개요 / 영상 개요 / 세부 관찰 내용
→ Markdown / HWPX
```

보고서는 화면 근거와 음성 근거를 함께 읽어 사건 단위로 정리합니다. 각 행은 자신이 나온 구간을 달고 나오며, **근거 검증을 통과하지 못한 사건은 보고서에 싣지 않습니다.**

발화 근거는 보고서 문장으로 다시 쓰고, 전사 원문을 그대로 옮기지 않습니다. 후보 문장이 전사에서 연속 토큰을 베끼거나 아직 말투로 읽히면(의문형 종결·1인칭 주어·담화 표지) 통과시키지 않고, 제약을 건 재생성 → 구분 범위 요약 → 음성 행 보류 순으로 물러섭니다. 판정 규칙은 닫힌 문법 범주만 쓰며 내용 단어 목록을 두지 않습니다.

시연 영상 40분(구간 478개)에서 측정한 값입니다.

| 항목 | 값 |
|---|---:|
| 근거 검증을 통과한 사건 | 21 / 21 |
| 제목·개요의 미지지 문장 | 0 |
| 가드가 막은 환각 (4편 합계) | 10 (최종 출력 0) |
| 전사 원문이 그대로 실린 행 (4편 합계) | 13 → **0** |

대표 산출물은 [`examples/multimodal_report.md`](examples/multimodal_report.md)이고, 그 판정 근거는 [`examples/multimodal_report_evidence_audit.json`](examples/multimodal_report_evidence_audit.json)과 [`examples/multimodal_report_style_audit.json`](examples/multimodal_report_style_audit.json)에 함께 둡니다.

이전 기준선인 관찰 전용 경로(`WVR_WHOLE_VIDEO_REPORT_V2`)도 [`examples/whole_video_report.md`](examples/whole_video_report.md)에 그대로 남겨 두었습니다. 현재 보고서 경로는 **기본 경로 후보**이며 production 기준선으로 선언하지 않습니다 — 근거가 희박한 영상에서 보고서가 거의 비는 한계가 남아 있습니다.

## 저장소 구조

```text
src/jds_video/scene_search.py        장면 검색 공개 진입점
src/jds_video/whole_video_report.py  관찰 전용 보고서 공개 진입점
src/jds_video/multimodal_report.py   화면+음성 보고서 공개 진입점
src/jds_video/_internal/             검증된 내부 구현
scripts/   재현·실행 진입점
tests/     공개 코드에 대응하는 단위·계약 테스트
results/   고정 검색 평가 결과
examples/  대표 보고서와 그 판정 근거
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
