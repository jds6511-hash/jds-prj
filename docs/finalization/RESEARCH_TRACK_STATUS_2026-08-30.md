# 트랙 상태 — 2026-08-30 종결·동결·다음 후보

한 화면에서 지금 무엇이 닫혔고 무엇이 열려 있는지 본다. 수치의 출처는 각 결과 문서다.

---

## 1. 상태

```
MODEL DIAGNOSTIC        CLOSED
  EXAONE-3.5              IMPLEMENTATION_BLOCKED · scientific result NONE
  Qwen vs Kanana          COMPLETE (4호출)
  추가 모델               NO

BCS v0 core             FROZEN
BCS HWPX                제품 prototype으로 유지
caption-only 일반화      철회

NEXT RESEARCH CANDIDATE  deterministic change-point (C)   C0 COMPLETE / MIXED_SIGNAL

v2.1 architecture        FROZEN        v2.1 planning         COMPLETE
v2.1 acceptance matrix   COMPLETE      Gate A tickets        READY
v2.1 implementation      IN PROGRESS   implementation auth   GRANTED 2026-08-30
Gate A                   IN PROGRESS   A-01·A-03·A-04·A-10   COMPLETE
NEXT TICKET              A-05 sanitation + claim eligibility
FINAL REPORT / PRESENTATION FINALIZATION   보류 (종료 아님)
Dual-stream 전면 (D)     불필요
모델 추가 비교           불필요

공식 M8                  FAIL · 불변      M9 · official test      HOLD · UNOPENED
M8 C2 라벨               RETIRED          push                    금지
```

---

## 2. 이번 진단의 결론 — 한 문장

> **자유형 LLM boundary selection은 모델 × 입력 채널 상호작용에 따라 경계 위치와
> 조각화 정도가 크게 흔들렸고, 정상으로 보이는 출력에서도 의미 기반 경계보다
> 균등 간격·번호 열거 패턴이 반복해 나타났다.**

"현재 모델만의 문제인가" → **아니다.**
"아키텍처만의 문제인가" → **단정할 수 없다.**

정확한 표현.

> Boundary selection failure는 model-specific한 방향성을 보였지만, 서로 다른 두
> 한국어 instruction model 모두 입력 조건에 따라 불안정한 위치 선택 또는 열거형
> 출력을 보여, **free-form LLM boundary selection 자체의 안정성 문제**가 더
> 일반적인 설계 위험으로 관찰되었다.

즉 **model × input interaction + task formulation problem**이다.

근거.

```
관측                                            의미
Qwen   full chunk5    42 boundaries · run1 26   full 입력에서 degeneracy
Kanana cap  chunk3    57 boundaries · run1 52   반대 조건에서도 degeneracy
Kanana cap  chunk5    40 boundaries · run1 23   재현
정상 arm에서도 step≈10 등차수열                 붕괴가 아니어도 위치 휴리스틱 의심
모든 Jaccard < 0.2                              경계 위치 안정성 매우 낮음
Kanana가 토큰 12~14% 적어도 붕괴                단순 context-length 설명 약함
네 arm 모두 PARSE_OK                            파서 문제 아님
```

---

## 3. BCS에 적용되는 좁힌 표현

```
철회   "caption-only boundary가 안정적이다"
```

> **BCS v0는 Qwen2.5-7B-Instruct와 해당 두 영상 조건에서 유효 문서를 생성한
> frozen product prototype이다. 후속 cross-model diagnostic에서는 caption-only
> boundary selection의 안정성이 다른 모델로 일반화되지 않았으므로, 해당 boundary
> mechanism을 일반적인 사건 검출 방법으로 주장하지 않는다.**

BCS v0를 폐기할 이유는 없다 — 유효 HWPX 두 편을 실제로 만들었고 제품형
prototype으로 작동했다. 바뀌는 것은 **일반화 범위**다.

---

## 4. 다음 후보 C — 방향

```
5초 caption
  ↓ caption embedding
  ↓ 인접·국소 의미 변화 신호
  ↓ 결정적 change-point detection
Episode spans
  ↓ caption + sanitized STT
  ↓ 내용 생성
AAR
```

LLM의 역할을 좁힌다.

```
경계 결정      NO
구간 내용 해석  YES
```

장점: 모델을 바꿔도 **Episode 시간축이 바뀌지 않는다.** 모델 비교가 그 뒤의
content quality 문제로 격리된다.

### 위험 — threshold tuning으로 바로 가면 안 된다

`0.55`·최소 간격·smoothing window를 결과를 보며 맞추기 시작하는 것이 이 트랙의
전형적 실패 경로다.

### 그래서 다음은 C0 diagnostic만

대상: geoje chunk3 · chunk5 · 3I7 일부 구간.

```
인접 코사인 거리 곡선
국소 peak
LLM이 찍었던 경계 (Qwen full / Qwen caption-only / Kanana 양쪽 — 이미 저장됨)
실제 프레임·캡션 변화
```

를 **나란히 본다.** 목적은 최적 threshold가 아니라 하나다.

> 의미적으로 그럴듯한 변화점이 결정적 신호의 peak에 실제로 모이는가.

그것이 확인된 뒤에야 outcome-independent rule을 동결하고 Episode generator로
승격시킨다.

**C0 완료 — `MIXED_SIGNAL`**(`C0_BOUNDARY_SIGNAL_OBSERVATION_2026-08-30.md`).
임계·최소간격·smoothing을 정하지 않았고 provider를 채택하지 않았다.

---

## 5. 발표용 — 실패에서 설계 전환으로

슬라이드 제목.

> **LLM 경계 선택은 모델과 입력 조건에 따라 반대 방향으로 붕괴했다**

```
                     Full            Caption-only
Qwen   chunk5    42 / run 26           10 / run 1
Kanana chunk5     5 / run 1            40 / run 23
Qwen   chunk3     5 / run 1             2 / run 1
Kanana chunk3     6 / run 1            57 / run 52
```

> 같은 입력 제거가 Qwen에서는 조각화를 완화했지만 Kanana에서는 오히려 조각화를
> 유발했다.

> 따라서 LLM의 자유 경계 선택을 사건 구조의 정본으로 사용하지 않고, 향후 결정적
> change-point detection과 내용 생성 모델을 분리하는 방향을 제안한다.

---

## 6. 최종 보고서 baseline과의 관계

`FINAL_REPORT_BASELINE_2026-08-28.md`(ea44f2f)는 08-28 동결본이고 이 트랙들보다
앞선다. caption-only 일반화 주장이 없어 **모순은 없다.**

08-29~30의 다섯 트랙(ablation · BCS v0 · HWPX · model diagnostic · C0)과 v2.1 설계는
**companion addendum**으로 추가했다 — `FINAL_REPORT_SUPPLEMENT_2026-08-30.md`.

baseline 자신의 규칙을 따른 것이다.

```
revision_rule: STEP B 결과는 addendum 또는 revision으로 별도 추가한다.
               이 baseline의 본문을 다시 쓰지 않는다.
```

**동결본은 한 글자도 고치지 않았다.**

---

## 7. 문서 지도

```
M8_HIER_BOUNDARY_ABLATION_PREREG / RESULT_2026-08-29     within-video ablation
BCS_PROTOTYPE_SPEC / RESULT_2026-08-29                   제품 prototype
BCS_CORE_FREEZE_2026-08-29                               동결 + 정본/표현 분리
MODEL_DEGENERACY_DIAG_PREREG_2026-08-29                  사전등록
MODEL_DIAG_PREREG_AMENDMENT_2026-08-30                   비교 모델 교체 (실행 전)
MODEL_DEGENERACY_DIAG_RESULT_2026-08-30                  Case 4
C0_BOUNDARY_SIGNAL_OBSERVATION_2026-08-30                MIXED_SIGNAL
REPORT_FORMAT_REFERENCE_2026-08-30                       사람 작성 형식 참조 (GT 아님)
V2_1_ARCHITECTURE_SPEC / IMPLEMENTATION_PLAN             v2.1 설계·계획
V2_1_ACCEPTANCE_MATRIX / DECISION_ADDENDUM               수용 기준 · 결정 이력
V2_1_GATE_A_TICKETS / P1_WAIVERS                         티켓 · waiver 대장
V2_1_IMPLEMENTATION_AUTHORIZATION_2026-08-30              착수 승인 사건 기록
FINAL_REPORT_SUPPLEMENT_2026-08-30                       baseline companion addendum
RESEARCH_TRACK_STATUS_2026-08-30                         이 문서
```
