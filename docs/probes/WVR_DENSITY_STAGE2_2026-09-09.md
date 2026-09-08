# WVR_SAMPLING_SEMANTIC_DENSITY_V1 — Stage 2 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md`
(commit `2ebbe59`) · 실행 코드 commit `37b7ddde65c6`

```
Stage 2 실행       6/6 완료 (D1·D2·D3 × S0·S1)
arm 상태           6/6  PARSE_FAILURE
판정               INCONCLUSIVE / OUTPUT_TRUNCATED_AT_CAP
PAIRED_OUTPUT_SENSITIVITY   측정되지 않았다
0.25fps 관련 결론   없음
```

**결과가 나빠서가 아니라 측정이 성립하지 않았다.** 여섯 실행 모두 생성이
`max_new_tokens = 1024`에서 끊겨 JSON이 중간에서 잘렸다. 비교를 하지 않았고,
파라미터를 바꿔 되살리지도 않았다.

## 1. 실측 — 여섯 arm 전부 cap에서 끊겼다

```
arm      frames  input tok  gen tok  cap 도달  infer(초)  peak alloc(MiB)  상태
D1 S0      90      7,197     1,024    예       37.8       18,953.0        PARSE_FAILURE
D1 S1      45      3,809     1,024    예       37.6       17,908.2        PARSE_FAILURE
D2 S0      90      7,178     1,024    예       38.0       18,948.5        PARSE_FAILURE
D2 S1      45      3,799     1,024    예       38.4       17,907.1        PARSE_FAILURE
D3 S0      90      7,197     1,024    예       37.7       18,953.0        PARSE_FAILURE
D3 S1      45      3,809     1,024    예       36.3       17,908.2        PARSE_FAILURE
```

파싱 실패 사유는 전부 같은 형태다 — 잘린 JSON.

```
D1 S0   Expecting ',' delimiter: line 39 column 45 (char 2624)
D1 S1   Expecting ',' delimiter: line 45 column 45 (char 2855)
D2 S0   Expecting ',' delimiter: line 32 column 190 (char 4215)
D2 S1   Expecting ',' delimiter: line 32 column 88 (char 2322)
D3 S0   Expecting ',' delimiter: line 30 column 55 (char 2265)
D3 S1   Expecting ',' delimiter: line 30 column 91 (char 2486)
```

출력 앞부분은 계약대로였다 — `{"observed_events": [{"approx_time": 300.0,
"event": …, "visible_entities": […], "activity": …}` 형태가 이어지다 끊겼다.
잘린 지점까지의 `approx_time` 등장 횟수는 11~17개인데, **이것을 event 수로
쓰지 않는다** — 절단 길이에 좌우되는 값이다.

용량은 문제가 아니었다. peak allocated 17.9~19.0 GiB로 24,564 MiB 대비 여유가
있었다(Stage 1 capacity 결과와 일관).

## 2. 이번 실행으로 말할 수 없는 것

```
0.25fps에서 event가 사라진다 / 유지된다      비교 자체를 하지 않았다
event 수 차이                              절단 때문에 정의되지 않는다
entity·activity 변화 · 순서 변화             매칭을 돌리지 않았다
D1/D2/D3 divergence와 화면 변화의 연동       위와 같다
4초 vs 8초 허용오차 민감도                   위와 같다
```

`PAIRED_OUTPUT_SENSITIVITY`는 **미측정**이다.

## 3. 부수 관측 1건 — 출력 언어 계약 위반 (절단과 무관)

`output_quality_v1`을 여섯 raw 출력에 적용했다.

```
arm      한글 문자  라틴 문자  quality
D1 S0      470       538     PASS
D1 S1      397       614     PASS
D2 S0        0     2,550     FAIL — OUTPUT_LANGUAGE_CONTRACT_FAILURE
D2 S1      465       652     PASS
D3 S0      542       424     PASS
D3 S1      429       599     PASS
```

`D2 S0`는 본문 전체가 영어였다(`"A hand holds a bag of potato chips in a green
basket."`). 프롬프트 첫 규칙이 "한국어로만 쓴다"인데도 그렇다. 라틴 문자가
다른 arm에서도 수백 개인 것은 JSON 키(`approx_time` 등) 때문이고, 판정을
가른 것은 **한글 0**이다.

이것은 절단과 독립된 사건이고, 다음 Stage 2 재실행에서도 볼 값이다. 다만
표본 1건이므로 빈도를 주장하지 않는다.

## 4. 사전등록의 결함 — 같은 구멍이 반복됐다

사전등록에 **비퇴화 전제조건이 없었다.** 파싱 가능한 JSON·절단되지 않은 생성을
요구하지 않았다.

```
STT_RETRANSCRIBE_V1 canary (2026-09-08)   전사 0발화 → 게이트가 공허하게 통과
WVR density Stage 2 (2026-09-09)          출력 절단 → 비교가 성립하지 않음
```

두 번 같은 계열의 구멍이 났다. 차이는 이번엔 게이트가 공허하게 **통과하지
않았다**는 점이다 — `PARSE_FAILURE`가 그대로 기록됐고 테스트가 그 사실을
검사한다.

`max_new_tokens = 1024`는 capacity 사건(C01·A0·A1·B)에서 온 값이다. capacity를
재는 데는 충분했지만, **진단 schema 전체를 담기에는 부족**했다. 그것을 결과를
본 뒤에 알았다.

**이번 실행분은 이 조건으로 재판정하지 않는다.** `INCONCLUSIVE /
OUTPUT_TRUNCATED_AT_CAP`으로 동결한다. 코드에는 다음 사건용 전제조건만 넣었다
(`wvr_density_compare.non_degenerate` · `truncated_at_cap` — 이번 6건이 전부
`non_degenerate == False`임을 테스트가 확인한다).

## 5. 다음 사건에 필요한 것 (승인 대기 · 이번에 실행하지 않음)

```
WVR_SAMPLING_SEMANTIC_DENSITY_V1B
변경    max_new_tokens 1024 → 더 큰 값 (예: 4096)  ← 유일한 변경
동결    창 D1·D2·D3 · S0/S1 표집 · 해상도 · 모델 · dtype · attn · allocator ·
        프롬프트 hash 7899dc46… · 매칭 허용오차 (4.0, 8.0)
전제    non_degenerate: 파싱 성공 + event ≥ 1 + 생성이 cap에 닿지 않음
        하나라도 어긋나면 그 arm은 비교에서 제외하고 사유를 기록한다
```

`max_new_tokens`를 올리는 것은 **파라미터 변경**이므로 새 사전등록 사건이다.
프롬프트를 짧게 고치거나 schema를 줄이는 것도 같은 범주이고, 이번 결과를 보고
프롬프트를 손보는 것은 하지 않는다.

## 6. 상태

```
WVR_SAMPLING_SEMANTIC_DENSITY_V1 Stage 1   REVIEWED / PASS (변경 없음)
WVR_SAMPLING_SEMANTIC_DENSITY_V1 Stage 2   INCONCLUSIVE / OUTPUT_TRUNCATED_AT_CAP
WVR_CAPACITY_SAMPLING_V1                   CLOSED / CAPACITY_PASS
WVR event extraction                       HOLD
STT_RETRANSCRIBE_DIAGNOSTIC_V1B            HOLD
현행 제출본                                  READ-ONLY / NO PROMOTION
official test  UNOPENED       M9  HOLD
```

## 7. 산출물

```
runs/wvr_light_v1/density_stage2_D1_S0.json … D3_S1.json   6건 (raw 출력 전문 포함)
runs/wvr_light_v1/density_stage2.log
src/wvr_density_compare.py · scripts/wvr_density_stage2.py
tests/test_wvr_density_stage2.py (28건 · 뮤테이션 18건 전부 RED)
```
