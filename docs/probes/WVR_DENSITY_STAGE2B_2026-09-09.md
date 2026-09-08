# WVR_SAMPLING_SEMANTIC_DENSITY_V1B — Stage 2 재실행 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1B_2026-09-09.md`
(commit `78cefa378690` — 실행 전 freeze) · 유일한 변경 `max_new_tokens 1024 → 4096`

```
EXECUTION_INTEGRITY        PASS
ARM_VALIDITY               6/6 PASS      (파싱 OK · event ≥ 1 · 절단 없음)
PAIR_EVALUABILITY          3/3 PASS      (사전등록 게이트 기준)
PAIRED_OUTPUT_SENSITIVITY  MEASURED
SEMANTIC_DENSITY_DECISION  INCONCLUSIVE
  reason  MEASUREMENT_REPRESENTATION_DEGENERACY
          + TEMPORAL_ONLY_MATCHING_NOT_SEMANTIC_EVENT_MATCHING
          + D2 LANGUAGE_CONFOUND
언어 계약   D2 S0  OUTPUT_LANGUAGE_CONTRACT_FAILURE (V1에서도 같은 arm)
사건 상태   CLOSED / INCONCLUSIVE — 실행은 유효하고 게이트도 통과했으나,
          측정된 수치가 의미적 event retention을 나타내지 않는다
```

**그러나 출력 내용은 반복문이 지배한다**(§4). 게이트는 사전등록대로 섰고 판정도
그대로 두지만, **paired sensitivity 수치를 "event 발견 능력의 차이"로 읽을 수
없다.** 그 근거를 아래에 실측으로 적는다.

normative source는 `runs/wvr_light_v1/density_stage2b_summary.json`이다.

## 1. 절단 문제는 해소됐다

```
arm     frames  input tok  gen tok  cap(4096) 도달  infer(초)  parse
D1 S0     90     7,197     3,413    아니오          118.71     OK
D1 S1     45     3,809     2,414    아니오           85.28     OK
D2 S0     90     7,178     2,070    아니오           73.11     OK
D2 S1     45     3,799     2,841    아니오           97.99     OK
D3 S0     90     7,197     3,754    아니오          130.75     OK
D3 S1     45     3,809     1,192    아니오           42.47     OK
```

V1에서 6/6이 1,024에 걸렸던 것이 4096에서는 하나도 걸리지 않았다. 창 밖 시각
위반도 0건이다.

## 2. 게이트 결과

```
pair  창               stage1 score   S0 events  S1 events   상태
D1    W11 300–480초    1411.2169          46         37      EVALUABLE
D2    W02  30–210초    1115.5522          33         46      EVALUABLE
D3    W05 120–300초     816.3476          37         18      EVALUABLE
```

세 pair 모두 evaluable이므로 사건 판정은 `PAIRED_OUTPUT_SENSITIVITY_MEASURED`다.

## 3. paired sensitivity 실측 (허용오차 4.0 · 8.0)

```
pair  tol   matched  only S0  only S1  순서 뒤집힘  sim median  entity median
D1    4.0     37        9        0         0         0.125       0.4286
D1    8.0     37        9        0         0         0.125       0.4286
D2    4.0     25        8       21         0         0.0         0.0
D2    8.0     25        8       21         0         0.0         0.0
D3    4.0     18       19        0         0         0.1212      0.3333
D3    8.0     18       19        0         0         0.1212      0.3333
```

```
event 수 변화   D1 −9 · D2 +13 · D3 −19        방향이 일치하지 않는다
허용오차 민감도  4.0과 8.0의 결과가 세 창에서 전부 동일했다
순서            temporal alignment된 쌍의 순서 뒤집힘 0건 (세 창 전부)
D1·D3           사전등록 matcher가 S1-only record를 0건 산출했다
D2              S1-only record 21건 — 단 §4·§5를 함께 읽어야 한다
```

**용어를 제한한다.** 이 matcher는 시간으로 먼저 붙인다. 따라서 `matched`는
**semantic equivalence가 아니라 temporal candidate alignment**다.

```
D1·D3의 only S1 = 0        → "0.25fps가 새 event를 만들지 않았다"고 쓰지 않는다
                             허용 표현: "사전등록 matcher가 S1-only record를 0건 산출했다"
D2의 matched = 25          → "25개 event가 동일했다"가 아니다
                             허용 표현: "25 temporal candidate alignments"
```

D2에서는 영어 event와 한국어 event가 시간만으로 붙어 semantic similarity가 0인데,
그것을 `matched event`라고 부르면 측정 이름이 알고리즘보다 강해진다. 산출물
필드명(`pairs`·`matched_count`)은 그대로 두되 **해석에서 semantic equivalence로
읽지 않는다.**

## 4. 결정적 한계 — 출력이 반복문이다

각 arm의 event 문장을 세어 봤다.

```
arm     events  고유 문장  최다 반복  고유 비율
D1 S0     46        3         44      0.07
D1 S1     37        4         34      0.11
D2 S0     33       33          1      1.00     ← 유일하게 반복이 없다 (영어 출력)
D2 S1     46        1         46      0.02
D3 S0     37        5         29      0.14
D3 S1     18        7         12      0.39
```

`only S0`로 분류된 event가 실제로 사라진 내용인지 확인했다.

```
D1   only S0 9건 중 9건(100%)이 이미 매칭된 문장과 완전히 같은 문장이다
D3   only S0 19건 중 17건(89%)이 그렇다
D2   only S0 8건 중 0건 (S0가 영어 고유 문장 33건이라 중복이 없다)
```

즉 **D1·D3의 event 수 감소는 "사라진 사건"이 아니라 반복 문장 개수의 차이**다.
같은 문장을 44번 쓰는 arm과 34번 쓰는 arm을 비교한 것에 가깝다.

같은 이유로 `sim median 0.125` 같은 값도 event 발견 차이로 읽을 수 없다.

## 5. D2는 언어 confound가 겹쳐 있다

```
D2 S0   영어 · 고유 문장 33건 · 반복 없음 · OUTPUT_LANGUAGE_CONTRACT_FAILURE
D2 S1   한국어 · 같은 문장 46회 반복
```

D2의 `sim median 0.0` · `entity median 0.0`은 **언어가 달라서** 0이다. 표집
감소의 효과가 아니다. 매칭 자체는 시간만으로 하므로 matched 25건은 유효하지만,
**D2의 텍스트·entity 유사도는 sampling 효과로 해석하지 않는다.**

V1에서도 같은 arm(D2 S0)이 영어였다 — **두 번 재현**됐다. 프롬프트 첫 규칙이
"한국어로만 쓴다"이고 프롬프트는 한 글자도 바뀌지 않았다. 다만 표본이 창 하나이므로
빈도·원인을 주장하지 않는다.

## 6. 그래서 무엇을 말할 수 있나

허용되는 문장:

```
4096 토큰에서는 절단이 없었고 여섯 arm 모두 파싱됐다.
세 pair 모두 evaluable이었고 사건 판정은 PAIRED_OUTPUT_SENSITIVITY_MEASURED다.
매칭된 event의 시간 순서는 세 창 모두 유지됐다(뒤집힘 0).
허용오차 4.0과 8.0에서 결과가 동일했다 — 결론이 허용오차 선택에 민감하지 않다.
D1·D3에서 사전등록 matcher는 S1-only record를 0건 산출했다.
```

쓰지 않는 문장:

```
0.25fps가 새 event를 만들지 않았다            ← matcher 산출물에 대한 진술로만 쓴다
matched = 의미가 같은 event                   ← 시간 후보 정렬이다
0.25fps에서 event가 9건·19건 사라졌다        ← 대부분 반복 문장 개수 차이다
0.25fps가 의미를 보존한다 / 잃는다             ← 반복 지배 출력으로는 판정 불가
0.5fps 출력이 기준이다                        ← ground truth가 아니다
D2에서 sampling 감소가 entity를 바꿨다         ← 언어 confound다
세 창이 독립 표본이다                          ← D2·D3는 90초 겹친다
```

**semantic sufficiency 판정은 여전히 내려지지 않았다.**

## 7. 사전등록 결함 — 같은 계열 세 번째

```
STT_RETRANSCRIBE_V1 canary   전사 0발화       → 게이트 공허 통과
density Stage 2 (V1)         출력 절단        → 비교 불성립
density Stage 2B (V1B)       출력 반복 지배    → 비교는 성립하나 해석 불가
```

V1B의 validity 조건(파싱·event 수·절단)에 **비반복성 전제가 없었다.** event를
세는 지표는 같은 문장을 여러 번 쓰는 출력에서 의미를 잃는다.

**이번 실행분을 새 조건으로 재판정하지 않는다.** 게이트 판정은 사전등록대로
`MEASURED`로 남긴다. 다음 사건에서 쓸 전제조건을 제안만 한다.

```
후보 전제조건 (승인 필요 · 이번에 적용하지 않음)
  distinct_event_ratio = 고유 event 문장 수 / event 수
  두 arm 모두 일정 비율 이상일 때만 event-count 비교를 해석한다
  비율 자체는 사전등록에서 정해야 하고, 이번 실측(0.02~1.00)을 보고 고르면
  결과에 맞춘 임계값이 된다 — 리뷰어가 정하는 것이 맞다
```

반복 자체의 원인도 미분리다.

```
A  프롬프트가 "시간순으로 적는다"만 요구하고 중복 금지를 요구하지 않는다
B  4초·2초 간격 프레임에서 화면이 실제로 거의 같아 같은 문장을 반복한다
C  Qwen3-VL의 긴 video 입력에서 나타나는 생성 축퇴
```

`repetition_penalty = 1.0`(동결)이라는 사실만 기록한다. **이 값을 지금 바꾸지
않는다** — 결과를 보고 생성 파라미터를 바꾸는 것이 금지된 그 행위다.

## 8. 상태

```
WVR_SAMPLING_SEMANTIC_DENSITY_V1  Stage 1    REVIEWED / PASS
WVR_SAMPLING_SEMANTIC_DENSITY_V1  Stage 2    CLOSED / INCONCLUSIVE (절단)
WVR_SAMPLING_SEMANTIC_DENSITY_V1B Stage 2B   CLOSED / INCONCLUSIVE
  실행 유효 · paired output measured · semantic 해석은 event-representation
  degeneracy와 matcher 설계 때문에 막혔다
WVR_SAMPLING_SEMANTIC_DENSITY_V2             APPROVED — 새 event-interval 계측기
QWEN_OUTPUT_LANGUAGE_STABILITY               OBSERVED / REPRODUCED_ON_D2_S0 · HOLD
WVR event extraction                         HOLD
STT_RETRANSCRIBE_DIAGNOSTIC_V1B              HOLD
현행 제출본                                    READ-ONLY / NO PROMOTION
official test  UNOPENED        M9  HOLD
```

## 9. 산출물

```
runs/wvr_light_v1/density_stage2b_D1_S0.json … D3_S1.json   6건 (raw 전문 포함)
runs/wvr_light_v1/density_stage2b_summary.json              게이트·비교 요약
runs/wvr_light_v1/density_stage2b.log
scripts/wvr_density_summarize.py · src/wvr_density_v1b.py
V1 산출물 6건(density_stage2_*)은 무변경
```
