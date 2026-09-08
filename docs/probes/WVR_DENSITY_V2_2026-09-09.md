# WVR_SAMPLING_SEMANTIC_DENSITY_V2 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V2_2026-09-09.md`
(commit `9c95729a3e08` — 실행 전 freeze) · 실행 코드 commit `336b7b6834ec`

```
게이트 1  arm validity        6/6 valid   (파싱 · collapsed ≥ 1 · 절단 없음 ·
                                          English-only · unique_signature ≥ 2)
게이트 2  pair evaluability   3/3 EVALUABLE
게이트 3  probe verdict       DECISION_ELIGIBLE
semantic sufficiency          주장 금지 (요약 JSON에 플래그로 고정)
```

계측기는 의도대로 작동했다 — 절단 0건, 언어 confound 0건, 반복은 collapse로
interval이 됐다. **다만 자동 의미 동등 판정이 거의 성립하지 않았다**(§4):
`SEMANTICALLY_EQUIVALENT` 0·0·1건, `ADJUDICATION_REQUIRED` 18·67·25건.

normative source는 `runs/wvr_light_v1/density_v2_summary.json`이다.

## 1. 실행 계측

```
arm     frames  input tok  gen tok  cap(4096)  raw events  collapsed  unique sig
D1 S0     90     7,235     ...       미도달        45          3          2
D1 S1     45     3,847     ...       미도달        18         14         14
D2 S0     90     7,216     ...       미도달        60         23         22
D2 S1     45     3,837     ...       미도달        22         22         14
D3 S0     90     7,235     ...       미도달        36          8          6
D3 S1     45     3,847     ...       미도달        23         13          7
```

English-only 계약은 6/6 만족(한글·한자 0자). V1·V1B에서 두 번 나온 D2 S0 영어
출력 문제는 **진단 언어를 영어로 고정해 제거**했다 — V1B 수치와 비교하지 않는다.

## 2. collapse가 실제로 한 일

```
D1 S0   45 raw → 3 interval   312.0–480.0초 하나가 42회 반복을 흡수했다
D3 S0   36 raw → 8 interval   185.0–300.0초 하나가 23회 반복을 흡수했다
D2 S1   22 raw → 22 interval  반복이 없었다
```

연속 반복만 합쳤고 비연속 재등장은 남겼다(계약 §5). 즉 V1B에서 해석을 막았던
반복은 **탈락 없이 표현으로 흡수**됐다.

## 3. 관측된 비대칭 — 프레임이 많은 arm이 더 거칠게 서술했다

```
pair   S0(90프레임) collapsed   S1(45프레임) collapsed   차이
D1              3                      14              +11
D2             23                      22               −1
D3              8                      13               +5
```

D1·D3에서 **표집이 적은 arm이 더 많은 distinct interval을 냈다.** 예를 들어 D1은

```
S0   300–308 eating breaded food · 308–312 drinking · 312–480 eating breaded food (x42)
S1   300–310 eating fried food · 310–320 drinking water · 320–330 eating rice ·
     330–340 eating noodle soup · 340–350 eating noodle soup with spoon ·
     350–370 preparing gimbap · 370–380 eating gimbap · 380–390 cooking chicken … (14개)
```

**이것을 "0.25fps가 더 좋다"로 읽지 않는다.** 두 arm은 입력 토큰이 약 2배 차이나고
(7,235 vs 3,847), S0 쪽에서 같은 문장 반복이 지배했다. 서술 granularity 차이의
원인은 이 사건에서 분리되지 않았다.

## 4. 자동 의미 동등 판정이 거의 성립하지 않았다

primary 허용오차 4.0초 기준.

```
pair  시간정렬 후보  EQUIVALENT  ADJUDICATION  S0 동등없음  S1 동등없음  순서뒤집힘
D1        18            0            18           3          14          0
D2        67            0            67          23          22          0
D3        26            1            25           7          12          0
```

허용오차 8.0초에서도 EQUIVALENT는 0·0·1로 같았다(후보만 19·88·33으로 늘었다).
`SEMANTICALLY_DIFFERENT`(공통 토큰 0)는 세 창 모두 0건이고, **시간 정렬된 쌍이
사실상 전부 adjudication 버킷에 들어갔다.**

이유는 표현 차이다.

```
actor    D1은 "a person"(S0) vs "person"(S1) — 관사 하나로 완전일치가 깨진다
         D2·D3는 actor가 전부 동일("person")했고 그래서 actor 불일치 0건이다
action   D2 67쌍 중 8쌍만 동일 · D3 25쌍 중 7쌍 동일
object   세 창 모두 모든 쌍이 불일치 ("potato mixture" vs "potato balls" 등)
```

**동결된 계약의 한계를 그대로 적는다** — `signature`는 정규화 후 완전일치만
동등으로 인정하고, 불용어 제거는 공통 토큰 판정에만 적용된다. 그래서 `a person`과
`person`이 다른 signature가 됐다. 이것을 지금 고쳐 재판정하지 않는다.

## 5. 그래서 이번 probe가 답한 것과 답하지 못한 것

답한 것:

```
계측기가 작동한다 — 절단 0 · 언어 confound 0 · 반복이 interval로 흡수됨 ·
                   세 pair 모두 게이트 통과 (DECISION_ELIGIBLE)
S0-only·S1-only(시간 정렬조차 안 된 event)는 세 창 모두 0건이다
순서 뒤집힘은 EQUIVALENT 쌍에서 0건 (단 EQUIVALENT가 0·0·1이라 근거가 약하다)
```

답하지 못한 것:

```
0.25fps가 의미를 보존하는가        자동 동등 판정이 0에 가까워 계산되지 않았다
event merge·split                  EQUIVALENT 기반이라 세 창 모두 0으로 나왔다 —
                                   "merge·split이 없었다"는 뜻이 아니다
actor·action·object divergence      adjudication 버킷 안의 값이라 사람 판정 전이다
```

**semantic sufficiency 판정은 여전히 내려지지 않았다.** `S0-only ≠ missed event`,
`S1-only ≠ hallucination`, `0.5fps ≠ truth` 계약도 그대로다.

## 6. 리뷰어에게 남기는 것 — adjudication 목록

`density_v2_summary.json`의 각 pair `per_tolerance.tol_4.0.adjudication`에
side-by-side 쌍이 전부 들어 있다(reference/arm의 세 필드·구간·필드별 동일 여부·
공통 토큰). 합계 110쌍(18 + 67 + 25).

```
D1  18쌍   actor 동일 0 · action 동일 8
D2  67쌍   actor 동일 67 · action 동일 8
D3  25쌍   actor 동일 25 · action 동일 7
```

자동 판정이 밀어붙이지 않은 상태로 남겼다(계약 §6·§9).

## 7. 다음 사건 후보 (승인 필요 · 이번에 실행하지 않음)

```
① adjudication 규칙을 사람 판정으로 채운다
   110쌍을 리뷰어가 동일/상이로 판정 → 그 결과로 divergence를 계산한다
   (라벨 작성 규율에 따라 판정 기준을 먼저 사전등록해야 한다)
② signature 정규화에 불용어 제거를 포함하는 V2B
   "a person" == "person"이 되게 한다. 유일한 변경이어야 한다
③ 진단 schema에 controlled vocabulary를 주는 V3
   actor·action을 열린 문장이 아니라 목록에서 고르게 한다
```

②·③은 계측기 변경이므로 새 사전등록 사건이고, **이번 결과를 보고 즉석에서
바꾸지 않는다.**

## 8. 상태

```
density Stage 1                   REVIEWED / PASS
density Stage 2 (V1)              CLOSED / INCONCLUSIVE (truncation)
density Stage 2B (V1B)            CLOSED / INCONCLUSIVE (representation·matcher)
density V2                        게이트 DECISION_ELIGIBLE ·
                                  semantic 판정은 adjudication 대기
QWEN_OUTPUT_LANGUAGE_STABILITY    OBSERVED / REPRODUCED_ON_D2_S0 · HOLD
WVR event extraction              HOLD
STT_RETRANSCRIBE_DIAGNOSTIC_V1B   HOLD
현행 제출본                         READ-ONLY / NO PROMOTION
official test  UNOPENED     M9  HOLD
```

## 9. 산출물

```
runs/wvr_light_v1/density_v2_D1_S0.json … D3_S1.json   6건 (raw·collapsed 포함)
runs/wvr_light_v1/density_v2_summary.json              게이트·정렬·adjudication
runs/wvr_light_v1/density_v2.log
src/wvr_density_v2.py · src/wvr_density_prompt_v2.py
scripts/wvr_density_stage2_v2.py · scripts/wvr_density_summarize_v2.py
V1·V1B 산출물 12건 무변경
```
