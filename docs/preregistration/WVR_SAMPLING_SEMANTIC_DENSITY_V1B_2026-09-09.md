# 사전등록 — WVR_SAMPLING_SEMANTIC_DENSITY_V1B (2026-09-09)

**이 문서는 결과를 보기 전에 쓴다.** 실행 후 파라미터·게이트·성공 문구를 고치지 않는다.
고치려면 새 사전등록 사건이다.

```
승인 범위    Stage 2 재실행 6회 (D1·D2·D3 × S0·S1)
유일한 변경   max_new_tokens 1024 → 4096
HOLD        프롬프트·schema·event 상한 변경 · 8192 등 추가 상향 ·
            event extraction · STT diagnostic · submission promotion
```

## 1. 선행 사건 — 왜 다시 도는가

```
WVR_SAMPLING_SEMANTIC_DENSITY_V1 Stage 1   REVIEWED / PASS
WVR_SAMPLING_SEMANTIC_DENSITY_V1 Stage 2   CLOSED / INCONCLUSIVE
  root cause  OUTPUT_TRUNCATION_AT_GENERATION_CAP
  증상        6/6 PARSE_FAILURE (생성이 1,024에서 끊겨 JSON이 잘렸다)
  PAIRED_OUTPUT_SENSITIVITY  NOT MEASURED
```

측정 대상 자체에는 결함이 없었다. **출력을 담는 envelope가 작았던 계측 결함**이다.
그래서 프롬프트·schema를 줄이지 않는다 — 줄이면 V1 Stage 2와 **다른 진단**을
재게 된다. token cap만 올리는 것이 single-variable 원칙을 가장 잘 보존한다.

## 2. 유일한 변경

```
max_new_tokens   1024 → 4096
```

`src/wvr_density_v1b.py`에 두 값만 허용 목록으로 두고, 그 밖의 값으로는 실행할 수
없다(`assert_allowed`). 산출물 이름도 분리한다 —
`density_stage2b_D*_S*.json`(V1 산출물은 `density_stage2_*`로 그대로 남는다).

**4096에서도 cap에 닿으면 그 결과로 닫는다.** 즉석에서 8192로 올리지 않는다
(`ESCALATION_APPROVED = False`). 4096 승인 근거는 90프레임 arm의 peak가 약
19.0 GiB였고 입력 규모가 capacity 사건보다 작다는 것이며, **이것은 새 capacity
PASS 선언이 아니다.**

## 3. 그대로 두는 것 (freeze)

```
창                D1 W11(300–480) · D2 W02(30–210) · D3 W05(120–300)
                 Stage 1 점수로 이미 결정됐다. 다시 고르지 않는다
arm              S0 = 0.5fps 90프레임 · S1 = 0.25fps 45프레임 (S0의 KEEP 부분집합)
model·snapshot   Qwen/Qwen3-VL-8B-Instruct · 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
dtype·attn       bfloat16 · sdpa        quantization none · offload 없음
allocator        default (expandable_segments 사용 금지)
resolution       512 × 288              do_sample_frames False · do_resize False
video_metadata   필수                    do_sample False · num_beams 1
repetition_penalty 1.0                  retry 0
프롬프트           SAMPLING_DIAG_PROMPT_V1
                 sha256 7899dc460957fff6eef49ffb50ab15fb527436ec5008ee618772a232ce4350a4
                 (생산 계약 아님 · 본문 한 글자도 바꾸지 않는다)
매칭 허용오차       (4.0, 8.0) — 둘 다 보고. 결과를 본 뒤 하나를 고르지 않는다
프로세스           창×arm 하나당 fresh process 1회
```

## 4. arm-level validity (freeze)

```
valid  ==  parse_success  AND  observed_event_count >= 1  AND  not truncated_at_cap
```

`truncated_at_cap`은 `generated_token_count >= max_new_tokens`다. 위반 사유는
전부 기록한다(`PARSE_FAILURE` · `CONTRACT_VIOLATION` · `NO_EVENT` ·
`TRUNCATED_AT_CAP`).

**언어 계약 위반은 validity와 분리한다.** 프롬프트에 "한국어로만 쓴다"가 있으므로
`output_quality_v1`을 raw 출력에 적용해 `OUTPUT_LANGUAGE_CONTRACT_FAILURE`를
**별도 contract failure로 반드시 기록**한다. 이 위반이 있어도 arm validity 자체는
파싱·event 수·절단으로만 판정한다.

## 5. pair-level evaluability (freeze)

**비교 단위는 arm이 아니라 pair다.**

```
pair(D_i)  EVALUABLE      S0·S1 둘 다 valid
           NON_EVALUABLE  한쪽이라도 invalid → 그 pair 전체를 쓰지 않는다
```

한쪽 arm만 빼고 **다른 창의 arm과 섞지 않는다.** 살아남은 arm 하나로 부분 비교를
만들지도 않는다.

## 6. 사건 판정 (freeze)

```
PAIRED_OUTPUT_SENSITIVITY_MEASURED   D1·D2·D3 세 pair 모두 EVALUABLE
INCONCLUSIVE                          하나라도 NON_EVALUABLE
```

`INCONCLUSIVE`인 경우 **유효한 pair의 descriptive 결과는 보존**하되 사건 전체는
INCONCLUSIVE이고 **event extraction은 HOLD**다.

## 7. 무엇을 보고하는가 (판정이 선 뒤에만)

```
event 수 (S0 · S1 · 차이)
S0에만 나타난 event · S1에만 나타난 event (전문 그대로)
matched pair별 event_similarity · entity_jaccard · activity_similarity
순서 뒤집힘 수 (Kendall tau distance)
허용오차 4.0 · 8.0 각각의 결과
언어 계약 위반 arm 목록
```

해석 규칙은 V1 사전등록 §8(Case A·B·C)을 그대로 쓴다. 그리고:

```
D2(30–210초)와 D3(120–300초)는 90초 겹친다 — n=3 독립 표본으로 해석하지 않는다
0.5fps arm을 ground truth로 부르지 않는다
결과가 좋아도 "0.25fps = semantic sufficiency PASS"라고 쓰지 않는다
허용 표현은 PAIRED_OUTPUT_SENSITIVITY까지다
```

## 8. 금지

```
프롬프트·schema·event 상한 변경 · 4096 이후 즉석 상향(8192 등)
창 재선택 · S0/S1 표집 변경 · 해상도·모델·dtype·attn·allocator 변경
OOM·절단 후 retry · 한쪽 arm만으로 비교 · 창 간 arm 혼합
언어 위반을 프롬프트 수정으로 대응 · 결과를 본 뒤 허용오차 선택
event extraction·chapter·highlight·report 착수 · 제출본 변경
```

## 9. 테스트

```
WVR-F01 사전등록이 실행 전에 커밋돼 있다
WVR-F02 V1B의 max_new_tokens는 4096이고 V1은 1024로 남는다
WVR-F03 사전등록되지 않은 토큰 값은 거부된다
WVR-F04 산출물 이름이 V1과 분리된다 (density_stage2b_*)
WVR-F05 arm validity = 파싱 성공 + event ≥ 1 + 절단 없음
WVR-F06 언어 계약 위반은 validity와 분리돼 기록된다
WVR-F07 한쪽 arm이 invalid면 pair는 NON_EVALUABLE
WVR-F08 세 pair가 모두 evaluable일 때만 사건 판정이 MEASURED
WVR-F09 pair가 하나라도 빠지면 INCONCLUSIVE
WVR-F10 escalation 승인 플래그가 False
WVR-F11 프롬프트 hash가 V1과 같다
WVR-F12 창·표집·해상도가 V1과 같다
WVR-F13 V1 산출물 6건 무변경
WVR-F14 보고서 수치가 JSON과 일치
```

## 10. 뮤테이션 (전부 RED여야 한다)

```
R1  V1B 토큰 1024로 되돌림          R2  임의 토큰 값 허용
R3  산출물 이름을 V1과 공유          R4  절단을 validity에서 제외
R5  event 0을 valid로               R6  언어 위반을 validity에 포함
R7  한쪽 arm만으로 pair 구성          R8  2개 pair로 MEASURED 판정
R9  escalation 승인                 R10 프롬프트 본문 변경
R11 창 재선택                        R12 허용오차 1개
```

## 11. 상태 (무변경)

```
WVR_CAPACITY_SAMPLING_V1                  CLOSED / CAPACITY_PASS
density Stage 1                           REVIEWED / PASS
density Stage 2 (V1)                      CLOSED / INCONCLUSIVE
WVR event extraction                      HOLD
STT_RETRANSCRIBE_DIAGNOSTIC_V1B           HOLD
현행 제출본                                 READ-ONLY / NO PROMOTION
official test  UNOPENED       M9  HOLD
```
