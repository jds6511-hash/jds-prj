# 결과 — 경계 열거 degeneracy 모델 대조 진단 (2026-08-30)

```
성격   diagnostic · SEPARATE / NON-ADOPTIVE
사전등록  MODEL_DEGENERACY_DIAG_PREREG_2026-08-29.md   (8975c74 · 실행 전)
개정     MODEL_DIAG_PREREG_AMENDMENT_2026-08-30.md    (ad75b5d · 실행 전 · 결과 미열람)
실행본   ad75b5d · transformers 5.14.1 · torch 2.13.0+cu130 · greedy · bf16
```

```
BCS v0 core / HWPX path   FROZEN — 이 결과로 바꾸지 않는다
```

---

## 1. 조건

```
현재 모델   Qwen/Qwen2.5-7B-Instruct         저장된 raw 재사용 · 재실행 없음
비교 모델   kakaocorp/kanana-1.5-8b-instruct-2505   신규 4호출
            compat_shims []  ·  trust_remote_code False   ← 패치 0
```

EXAONE-3.5는 `IMPLEMENTATION_BLOCKED`로 종결했다(scientific result NONE).
사유는 개정 문서 §1.

---

## 2. 측정 — 사전등록 §4 그대로

```
arm                        in_tok  out_tok   bnd  run1  arith@step  범위밖  parse
Qwen   full   chunk3         8063       34     5     1      5@10       0   PARSE_OK
Kanana full   chunk3         7045       23     6     1      4@10       0   PARSE_OK
Qwen   cap    chunk3         6397       19     2     1      2@59       0   PARSE_OK
Kanana cap    chunk3         5525      176    57    52      3@2        0   PARSE_OK   ←

Qwen   full   chunk5         8196      214    42    26     16@2        0   PARSE_OK   ←
Kanana full   chunk5         7081       23     5     1      4@10       1   PARSE_OK
Qwen   cap    chunk5         6421       50    10     1      4@5        0   PARSE_OK
Kanana cap    chunk5         5493      125    40    23      2@2        0   PARSE_OK   ←
```

`run1` = 연속 정수 최장 길이. `arith@step` = 간격이 일정한(≥2) 최장 부분열과 그 간격.
프롬프트 문자 수는 arm 간 동일하다(full 11767·12075 / caption-only 9500·9509) —
semantic input이 같았음을 확인했다.

**네 arm 모두 `PARSE_OK`다.** 파서 실패로 인한 오판이 아니다.

---

## 3. 판정 — Case 4

```
Case 1  둘 다 full에서 붕괴          NO   Kanana는 full에서 안정적이다
Case 2  Qwen만 붕괴 · Kanana 안정     NO   Kanana도 붕괴한다
Case 3  둘 다 full에 민감 · 정도 차이  NO
Case 4  다른 방식으로 불안정          YES
```

> **LLM free boundary selection 자체의 안정성이 낮다.**
> deterministic change-point detection(C)이 future work로 더 강해진다.

---

## 4. 핵심 관찰 — 붕괴가 **반대 조건**에서 일어난다

```
Qwen     full input에서 붕괴          chunk5 · 연속 정수 26개
Kanana   caption-only에서 붕괴        chunk3 연속 52개 · chunk5 연속 23개
```

Kanana의 caption-only chunk3 출력.

```json
{"atomic_start_segments": [110, 111, 113, 115, 116, 118, 119, 120, …, 168, 169]}
```

허용 범위 110~169의 **60개 중 57개**를 골랐다. 사실상 전 구간 열거다.

같은 조건에서 Qwen은 `[110, 169]` 두 개였다.

**입력 채널을 빼는 것이 열거를 막아주지 않는다.** Qwen에서는 막았고 Kanana에서는
유발했다.

---

## 5. 붕괴하지 않을 때도 등차수열이다

```
Qwen   full chunk3     [110, 120, 130, 140, 150]        간격 10
Kanana full chunk3     [110, 119, 137, 147, 157, 167]   간격 10 우세
Kanana full chunk5     [225, 245, 255, 265, 275]        간격 10
```

**두 모델 모두, 정상으로 보이는 출력에서도 거의 균등 간격을 낸다.** STEP A에서
결정적 caption 거리 신호가 uniform baseline을 이겼던 것(0.55 vs 0.25)과 합치면,
이 과제에서 LLM 경계 선택이 내용 판단보다 균등 분할에 가깝다는 쪽에 근거가 쌓인다.

---

## 6. 위치는 어디서도 안정적이지 않다

```
모델 내부 (full ↔ caption-only)          shared  Jaccard
  Qwen   chunk3                              1    0.167
  Qwen   chunk5                              7    0.156
  Kanana chunk3                              6    0.105
  Kanana chunk5                              3    0.071

모델 간 (같은 조건)                       shared  Jaccard
  full        chunk3                         1    0.100
  full        chunk5                         3    0.068
  caption-only chunk3                        2    0.035
  caption-only chunk5                        8    0.191
```

**Jaccard가 어느 쌍에서도 0.2를 넘지 않는다.** 개수가 비슷해도 어디를 자를지가
모델·채널에 따라 거의 공유되지 않는다.

---

## 7. 계약 위반 1건

```
Kanana full chunk5   범위 밖 경계 285 (허용 220~279)
```

코드가 범위 필터로 걸러냈다. 기록만 한다.

---

## 8. 토크나이저

```
같은 프롬프트 문자 수에서   Kanana가 Qwen보다 12~14% 적은 토큰
  full  11767자    Qwen 8063  ·  Kanana 7045
  cap    9500자    Qwen 6397  ·  Kanana 5525
```

**입력 토큰이 적은 쪽이 안정적이라는 관계는 관측되지 않았다.** Kanana는 토큰이
더 적은 caption-only 조건에서 붕괴했다.

---

## 9. 이것이 BCS에 주는 의미

```
BCS 변경   NO   (프로토콜대로 · core FROZEN)
```

다만 해석 하나를 **좁혀야 한다**.

```
지금까지의 표현   "STT를 경계 입력에서 빼면 조각화가 사라진다"
정확한 표현       "Qwen2.5-7B-Instruct에서 STT를 경계 입력에서 빼면
                  이 영상의 조각화가 사라졌다"
```

caption-only가 본질적으로 안전한 조건이 아니다. **Kanana를 경계 모델로 골랐다면
caption-only는 오히려 최악의 선택이었을 것이다.**

ablation 결과 자체는 유효하다 — 같은 모델·같은 영상에서 채널만 뺐고 조각화가
사라졌다. BCS는 그 실측 위에 서 있다. 바뀌는 것은 **일반화 범위**다.

---

## 10. 하지 않은 말

```
Kanana가 더 낫다 / 나쁘다        말하지 않는다 — 채점하지 않았다
Qwen을 교체해야 한다             말하지 않는다 — NON-ADOPTIVE diagnostic이다
2청크가 모델을 대표한다           말하지 않는다 — 청크 2개 · 영상 1편 · 1회 실행
caption-only가 위험하다          말하지 않는다 — Qwen에서는 6/6 청크가 안정적이었다
```

---

## 11. 경계

```
BCS 변경  NO   모델 교체  NO   추가 모델  NO   prompt 수정  NO
M8/M9 판정 변경  NO   M9·test  NO   push  NO
```

**4호출로 종결한다. 모델을 더 붙이지 않는다.**

산출물: `runs/model_diag/geoje_boundary_degeneracy.json` (raw 8건 · 토큰 수 ·
안정성 · provenance · commit).
