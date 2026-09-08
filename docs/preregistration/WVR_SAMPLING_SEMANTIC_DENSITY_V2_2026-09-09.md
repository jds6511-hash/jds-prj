# 사전등록 — WVR_SAMPLING_SEMANTIC_DENSITY_V2 (2026-09-09)

**이 문서는 결과를 보기 전에 쓴다.** 실행 후 파라미터·게이트·성공 문구를 고치지 않는다.
고치려면 새 사전등록 사건이다.

```
승인 범위    6회 실행 (D1·D2·D3 × S0·S1) + 결정적 요약
바뀌는 것    measurement instrument (프롬프트·파서·매처)
바뀌지 않는 것 창 선택 · 표집 · 해상도 · 모델 · dtype · attn · allocator · 토큰 상한
HOLD        repetition_penalty 변경 · 동일 프레임 반복 probe ·
            distinct_event_ratio 임계값 · event extraction · STT diagnostic ·
            submission promotion · QWEN_OUTPUT_LANGUAGE_STABILITY 별도 실험
```

## 0. 왜 계측기를 바꾸는가

```
V1  (1024 토큰)   CLOSED / INCONCLUSIVE   OUTPUT_TRUNCATION
V1B (4096 토큰)   CLOSED / INCONCLUSIVE   실행·게이트는 유효했으나
                                        MEASUREMENT_REPRESENTATION_DEGENERACY
                                        + TEMPORAL_ONLY_MATCHING
                                        + D2 LANGUAGE_CONFOUND
```

V1B가 실제로 한 일은 이렇다.

```
frames → 모델이 반복 observation 목록 생성 → timestamp로 record를 붙임
       → 그 차이를 event 차이로 계산
```

필요한 것은 이것이다.

```
frames → distinct temporal event representation → 같은 사건끼리 alignment
       → 표집 밀도에 따른 content divergence
```

**생성 penalty를 튜닝할 문제가 아니라 계측기를 고칠 문제다.**

## 1. 유지하는 것 (창을 다시 고르지 않는다)

```
D1  W11 300.0–480.0초   (Stage 1 점수 1411.2169)
D2  W02  30.0–210.0초   (1115.5522)
D3  W05 120.0–300.0초   ( 816.3476)
S0  0.5fps  · 90프레임        S1  0.25fps · 45프레임 (S0의 정확한 부분집합)
resolution      512 × 288     do_sample_frames False · do_resize False
model·snapshot  Qwen/Qwen3-VL-8B-Instruct · 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
dtype·attn      bfloat16 · sdpa    quantization none · offload 없음
allocator       default            device cuda:0 · device_map 없음
max_new_tokens  4096               do_sample False · num_beams 1
repetition_penalty 1.0             retry 0
허용오차         4.0초 primary · 8.0초 sensitivity
프로세스         창×arm 하나당 fresh process 1회
```

`repetition_penalty`를 바꾸지 않는 이유는 규율이다 — 바꾸면 Qwen의 생성 분포가
달라져 "repetition penalty를 주면 출력이 좋아지는가"를 재게 된다. 그것은
sampling-density 질문이 아니다.

## 2. 변경 1 — observation이 아니라 event interval을 요구한다

새 프롬프트를 쓴다. V1/V1B 프롬프트는 **동결 보존하고 재사용하지 않는다.**

```
SAMPLING_DIAG_PROMPT_V2
sha256  37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
파일     src/wvr_density_prompt_v2.py  (IS_PRODUCTION_CONTRACT = False)
```

요구 사항:

```
지속되는 동일 상태를 프레임마다 반복해 event로 쓰지 않는다
하나의 지속 행동·상태는 하나의 interval event로 합친다
같은 행동이 중간의 다른 사건 뒤에 다시 나타나면 새 event로 기록한다
화면에서 관찰 가능한 것만 기록한다 (소리·대사·자막 없음)
start_sec <= end_sec이고 둘 다 창 안에 있어야 한다
event 개수 상한은 두지 않는다
```

출력 형식:

```json
{"events": [{"start_sec": 0.0, "end_sec": 0.0, "actor": "...",
             "action": "...", "object_or_state": "..."}]}
```

## 3. 변경 2 — 진단 출력 언어를 English-only로 고정

```
OUTPUT_LANGUAGE = "en"
ENGLISH_ONLY 계약   content 필드에 한글·가나·한자 0자 · 라틴 문자 > 0
```

**production 보고서 언어를 영어로 바꾸는 것이 아니다.** 이 프롬프트는 여전히
비생산 진단 도구이고, D2에서 같은 입력에 대해 두 번(V1·V1B) `S0=영어 / S1=한국어`가
재현돼 sampling sensitivity와 무관한 **output-language nuisance variable**이
생겼기 때문에 새 계측기에서 그것을 제거한다.

```
V1B와 수치를 비교하지 않는다. V2 안에서 S0 vs S1만 비교한다.
```

이것은 사후 데이터 수정이 아니라 **새 계측기의 사전등록 계약**이다.

## 4. 변경 3 — distinct_event_ratio 임계값을 만들지 않는다

```
distinct_event_ratio >= 0.3 / 0.5 / 0.7 같은 게이트는 만들지 않는다
```

180초 동안 사람이 물건 하나를 계속 들고 있으면 반복 관측 자체를 모델 오류라고
단정할 수 없다. 할 일은 반복률로 출력을 탈락시키는 것이 아니라 **지속 관측을 하나의
event interval로 표현하게 만드는 것**이다.

## 5. 변경 4 — parser 계약에 consecutive run collapse

프롬프트만 믿지 않는다. 파서가 결정적으로 합친다.

```
signature = normalize(actor) · normalize(action) · normalize(object_or_state)
normalize  소문자 · 구두점 제거 · 공백 정리      **시간 필드는 signature에서 제외**
정렬       (start_sec, 원래 index) 오름차순
합침       바로 앞 event와 signature가 같으면 하나의 interval로 합친다
          start = min, end = max, collapsed_count 증가, source_indices 보존
```

**global unique dedupe가 아니라 consecutive run collapse다.**

```
holds bag / holds bag / holds bag        → 하나의 interval
holds bag / puts bag down / holds bag    → holds bag 두 개로 남는다
```

## 6. 변경 5 — `matched`를 두 단계로 나눈다

시간이 맞았다는 이유만으로 같은 사건이라고 부르지 않는다.

```
1단  TEMPORALLY_COMPATIBLE     구간이 겹치거나 가장 가까운 끝점 간격 <= 허용오차
                              4.0초 primary · 8.0초 sensitivity
2단  SEMANTICALLY_EQUIVALENT   normalize 후 세 필드가 모두 같다
     SEMANTICALLY_DIFFERENT    세 필드 전체에서 공통 토큰이 0개다
     ADJUDICATION_REQUIRED     그 사이 — 사람이 볼 side-by-side 목록으로 남긴다
```

공통 토큰을 셀 때 **고정 불용어 목록**(a·an·the·of·in·on·at·to·and·with·is·
are·it·its·this·that 등 · `wvr_density_v2.STOPWORDS`)을 제외한다. 빼지 않으면
`a` 하나만 공유해도 공통 토큰이 0이 되지 않아 `SEMANTICALLY_DIFFERENT`가 사실상
발생하지 않는다. **이 목록은 결과를 보고 늘리지 않는다.**

**유사도 임계값을 만들지 않는다.** 완전일치와 공통 토큰 0은 구조적 조건이고,
그 사이를 자동으로 가르지 않는다. 1:1 강제 매칭도 하지 않는다(merge·split을
관측하기 위해서다).

## 7. 무엇을 보는가 (event 수 차이는 primary가 아니다)

D1·D2·D3 각각에 대해:

```
1  equivalent interval events            2  S0-only event candidates
3  S1-only event candidates              4  actor divergence
5  action divergence                     6  state·object divergence
7  temporal-order divergence             8  event merge (S1 하나에 S0 여럿)
9  event split (S0 하나에 S1 여럿)        + ADJUDICATION_REQUIRED 목록
```

계약은 그대로 유지한다.

```
S0-only ≠ true missed event          S1-only ≠ hallucination
0.5fps는 truth가 아니다               matched를 semantic equivalence로 읽지 않는다
D2·D3는 90초 겹친다 — n=3 독립 표본이 아니다
```

## 8. measurement-validity gate

```
arm    parse_success
       AND collapsed events >= 1
       AND truncated_at_cap == false
       AND ENGLISH_ONLY 계약 만족
       AND collapse 후 unique_signature_count >= 2
pair   두 arm 모두 valid
probe  세 pair 모두 EVALUABLE → DECISION_ELIGIBLE
       하나라도 아니면 INCONCLUSIVE
```

마지막 arm 조건이 축퇴 판정이다 — collapse 뒤에도 창 전체가 **단 하나의
signature**로 표현되면 비교할 divergence가 없다.

```
INCONCLUSIVE / EVENT_REPRESENTATION_DEGENERACY
```

**이것은 모델 오류 주장이 아니다.** 실제로 180초 내내 한 상태였다면 그 창에서는
비교가 성립하지 않는다는 뜻이고, 그 사실을 그대로 적는다. 비율이 아니라
`>= 2`라는 구조적 조건만 쓴다.

프롬프트가 또 반복을 생성해도 **collapse 후 정상적인 interval이 남으면 측정은
계속 가능하다.**

## 9. 금지

```
창 재선택 · 표집 변경 · 해상도·모델·dtype·attn·allocator 변경 · 토큰 상한 변경
repetition_penalty 변경 · 동일 프레임 반복 probe · distinct_event_ratio 임계값
V1B 수치와의 직접 비교 · 결과를 본 뒤 허용오차 선택 · 유사도 임계값 신설
ADJUDICATION_REQUIRED를 자동으로 동일·상이로 밀어 넣기
S0-only를 missed event로, S1-only를 hallucination으로 부르기
event extraction·chapter·highlight·report 착수 · 제출본 변경
semantic sufficiency PASS 선언
```

## 10. 테스트

```
WVR-G01 사전등록이 실행 전에 커밋돼 있다
WVR-G02 V2 프롬프트 hash가 이 문서와 일치하고 생산 계약이 아니다
WVR-G03 V1/V1B 프롬프트를 import하지 않는다
WVR-G04 signature에 시간이 들어가지 않는다
WVR-G05 연속 반복만 합쳐진다 (사이에 다른 사건이 끼면 남는다)
WVR-G06 collapse가 start=min·end=max·source_indices를 보존한다
WVR-G07 ENGLISH_ONLY 계약 — 한글·한자 0 · 라틴 > 0
WVR-G08 한국어 출력은 arm invalid가 된다
WVR-G09 시간 정렬은 구간 겹침 또는 끝점 간격 <= 허용오차
WVR-G10 완전일치 → EQUIVALENT · 공통 토큰 0 → DIFFERENT · 그 사이 → ADJUDICATION
WVR-G11 유사도 임계값이 코드에 없다
WVR-G12 merge·split 후보가 잡힌다 (1:1 강제 없음)
WVR-G13 순서 뒤집힘은 EQUIVALENT 쌍에서만 센다
WVR-G14 unique_signature_count <= 1이면 축퇴로 pair가 NON_EVALUABLE
WVR-G15 세 pair 전부 EVALUABLE일 때만 DECISION_ELIGIBLE
WVR-G16 절단·파싱 실패·event 0이 각각 invalid 사유로 남는다
WVR-G17 창·표집·해상도·토큰 상한이 V1B와 같다
WVR-G18 V1·V1B 산출물 12건 무변경 · 제출본 무변경
WVR-G19 semantic_sufficiency_claim_allowed == False
WVR-G20 보고서 수치가 요약 JSON과 일치
```

## 11. 뮤테이션 (전부 RED여야 한다)

```
S1  signature에 시간 포함           S2  global dedupe로 바꿈
S3  비연속 반복도 합침               S4  ENGLISH_ONLY 검사 제거
S5  한국어 출력을 valid로            S6  유사도 임계값 도입
S7  ADJUDICATION을 EQUIVALENT로     S8  1:1 강제 매칭
S9  축퇴 검사 제거                   S10 2개 pair로 DECISION_ELIGIBLE
S11 절단을 validity에서 제외          S12 허용오차 1개
S13 창 재선택                        S14 V1 프롬프트 사용
S15 토큰 상한 변경                    S16 순서를 후보 전체에서 계산
```

## 12. 상태

```
density Stage 1                   REVIEWED / PASS
density Stage 2 (V1)              CLOSED / INCONCLUSIVE (truncation)
density Stage 2B (V1B)            CLOSED / INCONCLUSIVE (representation·matcher)
QWEN_OUTPUT_LANGUAGE_STABILITY    OBSERVED / REPRODUCED_ON_D2_S0 · HOLD
WVR event extraction              HOLD
STT_RETRANSCRIBE_DIAGNOSTIC_V1B   HOLD
현행 제출본                         READ-ONLY / NO PROMOTION
official test  UNOPENED     M9  HOLD
```
