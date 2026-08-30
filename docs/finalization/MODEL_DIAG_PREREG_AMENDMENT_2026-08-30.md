# 사전등록 개정 — 비교 모델 교체 (2026-08-30)

```
성격   prospective protocol amendment
원본   MODEL_DEGENERACY_DIAG_PREREG_2026-08-29.md  (commit 8975c74 · 덮어쓰지 않는다)
```

**결과를 보고 바꾼 것이 아니다.**

```
comparison arms executed   0
comparison result viewed   0
```

비교 모델의 진단 arm이 하나도 완료되기 전에, 결과 생성이 **불가능하다는 것**이
확인돼 교체한다.

---

## 1. EXAONE 시도 종결

```
Original comparison model   LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct
Status                      IMPLEMENTATION_BLOCKED
Scientific result           NONE
```

동결 런타임 `transformers 5.14.1`이 EXAONE-3.5의 vendored forward 경로를
네이티브로 지원하지 않는다(네이티브 지원은 `exaone4`·`exaone4_5`·`exaone_moe`).

```
1차 불일치   create_causal_mask(input_embeds=...)      5.x에서 inputs_embeds로 개명
             → 순수 별칭. git-tracked shim으로 처리했다(계산 불변)
2차 불일치   create_causal_mask(cache_position=...)    5.x 시그니처에서 제거됨
             → 별칭이 아니다. 인자를 버리는 것은 forward semantics를 내가
               추론해 고치는 것이다
```

**2차에서 멈췄다.** 이 진단의 질문 자체가 "모델이 이상 출력을 내는가"이므로,
손으로 적응시킨 forward 경로의 출력은 **마스크 결함이 degeneracy를 만들거나
지우는 경우와 구분되지 않는다.**

실행만 되게 하는 shim과 forward semantics를 추론해 고치는 것은 다르다. 후자는
하지 않는다.

### 격리 venv(transformers 4.57.6) 안을 택하지 않은 이유

```
Qwen     transformers 5.14.1
EXAONE   transformers 4.57.6
```

관측 대상이 **generation 경로의 degeneracy**다. 라이브러리 버전 차이를 "영향이
약할 것"이라고 가정할 수 없다. arm 간 런타임 동일성이 특정 모델보다 우선한다.

---

## 2. 교체

```
Replacement   kakaocorp/kanana-1.5-8b-instruct-2505
```

```
한국어 특화 instruct 모델        한국어 처리 능력 교란을 줄인다
비슷한 규모 (8B vs 7B)
다른 패밀리·다른 토크나이저       Qwen과 대조 목적 충족
동결 런타임에서 네이티브 지원      Llama 아키텍처 · 손 패치 0
서버 캐시에 이미 존재            다운로드 0
```

이로써 arm 간에 다음이 전부 같다.

```
transformers 5.14.1 · torch 2.13.0+cu130 · 동일 실행 코드
동일 task semantics · 동일 chunk · 동일 full/caption-only 조작
동일 decoding (greedy · max_new_tokens 16384 · bfloat16)
```

`trust_remote_code`와 호환 shim은 **끄고 실행한다**(`--compat-shim` /
`--trust-remote-code` 기본 off). 산출물의 `compat_shims`가 비어 있음으로
확인 가능하다.

---

## 3. 질문 재확인

원 질문은 특정 모델에 관한 것이 아니다.

> Qwen에서 관찰한 boundary-enumeration degeneracy가 **다른 한국어 가능 모델에서도
> 재현되는가.**

Kanana는 이 질문을 충족한다.

---

## 4. 바뀌지 않는 것

```
측정 항목      UNCHANGED   (원본 §4)
해석 판정표    UNCHANGED   (원본 §6 Case 1~4)
Qwen 저장 arm  UNCHANGED   재실행하지 않는다
공정성 규칙    UNCHANGED   task semantics 동일 · serialization은 model-native
parse 분리     UNCHANGED   PARSE_CONTRACT_FAILURE ≠ MODEL_FAILURE
호출 수        UNCHANGED   4회
대상 청크      UNCHANGED   geoje chunk3(110~169) · chunk5(220~279)
```

```
BCS v0 core         FROZEN
HWPX product path   FROZEN
model diagnostic    SEPARATE / NON-ADOPTIVE
```

결과가 무엇이든: BCS 변경 NO · 모델 교체 NO · 추가 모델 NO · prompt 수정 NO ·
M8/M9 판정 변경 NO · M9/test NO · push NO.

**4호출 뒤에 모델을 더 붙이지 않는다.**
