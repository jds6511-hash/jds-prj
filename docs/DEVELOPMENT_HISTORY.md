# 개발 이력 요약

이 문서는 최종 결과에 이르기까지 수행한 주요 작업과 설계 변경을 기록합니다. 사건별 raw artifact를 모두 공개하는 대신, 재현과 평가에 필요한 결정·결과·한계를 시간순으로 정리했습니다.

## 1. 자연어 영상 검색 기준선 구축 — 2026년 7월

- 영상을 5초 고정 구간으로 분할하고 대표 프레임을 선택했습니다.
- Whisper `large-v3`의 STT와 Qwen2.5-VL의 시각 캡션을 각각 생성했습니다.
- 두 채널을 KURE-v1로 임베딩하고, 채널별 z-score 정규화 후 `alpha=0.5`로 결합했습니다.
- 무관 질의에는 결과를 강제하지 않도록 abstention gate를 추가했습니다.
- dev 96질의에서 설정을 고정한 뒤 test 39질의를 1회 평가했습니다.
- test 결과는 MRR `0.649 → 0.829`, Hit@1 `0.564 → 0.769`였고, 장면형 질의 Hit@1은 `0.000 → 0.615`였습니다.

## 2. 검색 파이프라인 무결성 강화 — 2026년 8월

- 캡션 생성, 재임베딩, 검색 평가 사이의 text hash와 provenance를 연결했습니다.
- 자막·캡션의 손상 탐지와 자동 복구 경계를 분리하고, 사람이 결과를 보고 임의로 캡션을 고치는 방식을 금지했습니다.
- timestamp 연결, 대표 프레임 선택, 무관 질의 처리, 출력 계약을 테스트로 고정했습니다.
- 로컬과 서버의 모델·revision·runtime 차이를 기록하도록 실행 provenance를 보강했습니다.
- HWPX 및 사용자-facing 출력 경로를 구현하고 회귀 테스트를 추가했습니다.

## 3. Local Event 기반 whole-video report 연구 — 2026년 9월 초

- 고정 window에서 Local Event를 추출하고 Event Map, stitching, chapter boundary를 거쳐 보고서를 만드는 구조를 실험했습니다.
- 보수적 Event Map과 conflict 보존, opaque identifier, mapping seal 등 누출 방지 계약을 도입했습니다.
- 이 구조는 세밀한 provenance에는 유리했지만, Overview가 event log처럼 길어지고 noisy object·작은 행동이 전체 사실로 승격되는 문제가 있었습니다.
- semantic boundary 후보 실험은 source-empty 구간과 non-empty schema의 충돌 때문에 semantic quality를 판정하지 않고 `INCONCLUSIVE`로 종료했습니다.
- 결과적으로 chapter/boundary 연구를 최종 보고서 경로에서 제외했습니다.

## 4. 영상 직접 관찰 기반 Overview — 2026년 9월 11일

- 구조를 `Video → Qwen3-VL broad segment observation → temporal compression → Overview`로 단순화했습니다.
- 48초 window, 24초 overlap, 0.5fps로 영상을 관찰하고, 연속 중복 활동은 deterministic하게 압축했습니다.
- 장소·상황·계획 같은 `CONTEXT_INFERENCE`는 Overview 입력에서 제외했습니다.
- Short와 Detailed Overview가 동일한 canonical activity sequence와 최종 phase를 공유하도록 검증했습니다.
- `WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2`가 reviewer 기준 `WHOLE_VIDEO_OVERVIEW_PASS`를 받았습니다.

## 5. Analysis·Conclusion 및 HWPX 통합 — 2026년 9월 12일

- frozen Overview와 canonical flow만 사용해 Analysis와 Conclusion을 생성했습니다.
- Analysis는 활동 반복·시간적 전환·배치 같은 구조적 패턴만 다루고 새 사건이나 의도를 추가하지 않도록 제한했습니다.
- Conclusion은 Overview와 Analysis의 정보만 압축하며 새로운 evidence를 추가하지 않도록 했습니다.
- 기존 β/v3 report engine은 수정하지 않고 adapter/input layer에서 연결했습니다.
- Markdown과 HWPX 생성 및 구조 검증을 완료했고, `WVR_WHOLE_VIDEO_REPORT_V2`는 reviewer 기준 `WHOLE_VIDEO_REPORT_PASS`를 받았습니다.

## 6. Grounded detail 확장 시도와 확인된 한계 — 2026년 9월 13~14일

- broad activity만으로는 보고서의 구체성이 부족해, 기존 raw에서 report-grade visual detail을 재사용할 수 있는지 감사했습니다.
- raw에 broad label 이상의 직접 시각 사실이 충분하지 않아 기존 정보만으로 detail layer를 만드는 경로는 source-insufficient로 판단했습니다.
- Qwen3-VL에 visual fact와 frame reference를 함께 생성시키는 preview를 수행했지만, reference frame이 claim을 지지하지 않는 사례와 형식 위반이 확인되었습니다.
- 여기서 `candidate claim 생성`과 `visual grounding verification`을 별도 단계로 분리해야 한다는 구조적 결론을 얻었습니다.
- 같은 모델의 자기검증을 피하고, claim을 `SUPPORTED_AT_REFERENCE / SUPPORTED_ELSEWHERE_ONLY / UNSUPPORTED_IN_WINDOW / UNCERTAIN`으로 분류하는 감사 계약을 설계했습니다.
- 이 진단 연구는 현재 reviewer-PASS V2 보고서 기준선을 변경하지 않았습니다.

## 7. 중요 구간 선택과 focused-observation 예산 연구 — 2026년 9월 14일

- C01 frozen timeline에서 새 inference 없이 대표 activity block 6개를 deterministic하게 선택했습니다.
- source activity 7종과 early/middle/late/final coverage는 확보했지만, 선택 block 합집합이 456/600초여서 focused-observation 예산으로는 비효율적이었습니다.
- 후속으로 기존 observation window 안에서 대표 target을 더 좁히는 localization을 구현·실행했습니다.
- 이 작업은 진단 단계이며 focused observation, grounding, 보고서 재생성 또는 다중 영상 확장을 승인한 결과가 아닙니다.

## 8. 화면 + 음성 보고서와 근거 검증 계층 — 2026년 9월 17~19일

관찰 전용 경로는 "무엇이 보였는가"는 정리했지만 영상에서 **말해진 내용**을 쓰지 못했습니다. 회의 영상처럼 정보가 발화에 몰려 있는 자료에서는 보고서가 거의 비었습니다.

발화를 쓰기로 하면서 세 가지 문제가 한꺼번에 나왔고, 각각을 결정적 규칙으로 막았습니다.

1. **환각** — 근거에 없던 사람·역할·기관·장소가 요약문에 새로 나타났습니다. 근거 문자열 대조와 고정 어휘집만 쓰는 grounding guard, 한국어 이외 문자를 거르는 언어 게이트, 생성 문장이 근거에서 지지되는지 보는 claim 검증을 차례로 두었습니다. 4편에서 10건이 막혔고 최종 출력에는 0건입니다.
2. **전사 노출** — 생성이 실패한 행이 발화 원문을 그대로 보여주고 있었습니다. 전사 복사(연속 토큰 run·부분 문자열·두 발화 이어붙이기)와 보고 문체(의문형 종결·1인칭 주어·담화 표지)를 닫힌 문법 범주만으로 판정하고, 실패하면 제약 재생성 → 구분 범위 요약 → 음성 행 보류로 물러서게 했습니다. 전사형 행 13개가 0개가 되었습니다.
3. **근거 추적 불능** — 행과 구간의 연결이 표시 계층에서 끊어졌습니다. 모든 행이 자신의 사건·구간을 달고 나오게 하고, 검증(`EPISODE_GROUNDED` / `PROVENANCE_ERROR` / `TEMPORAL_ERROR`)을 통과하지 못한 사건은 내보내지 않습니다.

개발에 쓰지 않은 영상 2편에서 코드 수정 없이 같은 기준을 통과했습니다. 다만 정보가 줄어든 행이 3개 생겼고, 음성 인식 오인식이 그대로 주제어가 되는 문제는 남아 있습니다.

## 현재 채택된 공개 기준선

```text
Track A: STT + visual caption 기반 자연어 장면 검색
Track C: 화면 관찰 + 발화를 사건으로 결합하고 근거를 검증하는 multimodal report
         (이전 기준선인 관찰 전용 whole-video report V2도 예시로 함께 보존)
```

multimodal report 경로는 **기본 경로 후보**이고 production 기준선이 아닙니다. 정확성 기준(근거 검증·제목/개요 지지·전사 비노출)은 4편에서 모두 통과했지만, 근거가 희박한 영상에서 보고서가 거의 비는 한계는 해결되지 않았습니다.

다음 내용은 최종 기준선에 포함하지 않습니다.

- 검증되지 않은 visual claim을 grounded fact로 사용하는 경로
- 진행 중인 focused-observation 진단을 production 기능으로 주장하는 것
- 모델이 생성한 의도·감정·장소·원인·계획 추론

## 재현성과 보존

- 모델 revision, prompt, runtime, source hash와 raw-before-parse 원칙을 각 실행 기록에 적용했습니다.
- GitHub 공개본에서는 대용량 raw와 중간 사건 문서를 제외했지만, 저장소 교체 전 전체 Git 이력은 로컬 bundle로 별도 보존했습니다.
- 공개 결과 JSON과 예시 보고서는 최종 발표에서 사용한 채택 기준선에 한정합니다.

