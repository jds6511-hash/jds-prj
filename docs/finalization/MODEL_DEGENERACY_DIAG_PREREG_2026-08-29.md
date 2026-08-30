# 사전등록 — 경계 열거 degeneracy 모델 대조 진단 (2026-08-29)

```
성격   diagnostic · SEPARATE / NON-ADOPTIVE
아님   성능 실험 · 모델 채택 절차 · BCS 변경 근거 · M8/M9 판정
작성   실행 전. 결과를 보고 고치지 않는다.
```

```
BCS v0 core         FROZEN
HWPX product path   FROZEN
model diagnostic    SEPARATE / NON-ADOPTIVE
```

**결과가 무엇이든**: BCS 자동 수정 NO · 모델 자동 교체 NO · prompt 수정 NO ·
M8/M9 판정 변경 NO.

---

## 1. 질문

> geoje 경계 pass에서 관측된 **열거 degeneracy**가 다른 한국어 가능 모델에서도
> 재현되는가.

관측된 현상(2026-08-29 ablation, Qwen2.5-7B-Instruct).

```
chunk5 full input   ["220","224","226",…,"254","255","256",…,"279"]
                    간격 2를 16회 → 1을 25회 → 허용 범위 끝에서 정지
chunk3 full input   [110,120,130,140,150,165]   간격 정확히 10
caption-only        두 청크 모두 해소
```

---

## 2. 조건 — 2 chunk × 2 input × 2 model

```
                현재 모델(Qwen2.5-7B-Instruct)      비교 모델(EXAONE-3.5-7.8B-Instruct)
full input              A  저장된 raw 재사용                B  신규 2호출
caption-only            C  저장된 raw 재사용                D  신규 2호출
```

A·C는 **이미 저장돼 있다**(`m8_hier_prototype_geoje` · `m8_hier_boundary_ablation`
의 chunk3·chunk5 원본 출력). 재실행하지 않는다. **신규 호출은 4회뿐이다.**

대상 청크는 관측이 가장 뚜렷했던 둘이다.

```
chunk3   seg#110~169
chunk5   seg#220~279
```

---

## 3. 공정성 규칙 — task semantics 동일, serialization은 model-native

```
동일    system/user task 내용 · chunk · full vs caption-only 조작
        greedy(do_sample=False) · max_new_tokens 16384 · bfloat16
다름    chat template — 각 모델의 공식/native 템플릿을 쓴다
```

**raw chat-template 문자열을 억지로 맞추지 않는다.** 모델마다 템플릿이 다른 것이
정상이고, 강제로 맞추면 그 모델의 정상 동작이 아닌 것을 재게 된다.

---

## 4. 측정 항목 — 실행 전 확정

```
rendered prompt chars       semantic input이 동일했는지 확인
input tokens                tokenizer 차이 관찰
output tokens
boundary count
out-of-range boundary       허용 범위 밖 번호를 골랐는가
1-step integer run max      연속 정수 최장 길이
arithmetic progression run  간격이 일정한(≥2) 최장 부분열 길이
parse status
```

`rendered prompt chars`는 chat template을 적용하기 **전**의 프롬프트 문자열 길이다.
`input tokens`는 각 모델의 native template을 적용한 **후**의 토큰 수다.

### parse status는 모델 실패와 분리한다

EXAONE 출력을 Qwen 파서에 억지로 끼워 맞추지 않는다. raw를 먼저 보존하고 같은
boundary-list 계약을 검사한다.

```
PARSE_OK                 계약대로 목록을 얻었다
EMPTY_LIST               목록은 얻었으나 비어 있다
PARSE_CONTRACT_FAILURE   표기 차이로 파서가 못 읽었다 — **MODEL_FAILURE가 아니다**
```

이 구분을 두는 이유는 같은 종류의 사고가 이미 세 번 있었기 때문이다
(v2 canary 맨 배열 · BCS `"seg#55"` cites · 깨진 JSON 폴백). 파서 실패를 모델
실패로 보고하면 결론이 뒤집힌다.

---

## 5. 위치 안정성 — 개수만 보지 않는다

ablation에서 얻은 관측.

```
chunk5 제외   full 24 · caption-only 20 · shared 8
```

개수가 비슷해도 위치가 크게 흔들리면 안정적이라고 하지 않는다. 따라서 기록한다.

```
모델 내부(full ↔ caption-only)   shared · full-only · caption-only-only · Jaccard
모델 간(같은 조건)               shared · Jaccard
```

---

## 6. 판정표 — 실행 전 고정

```
Case 1  EXAONE도 full에서 열거 붕괴 · caption-only에서 안정
        → 모델 특이 현상이라기보다 task/input architecture가 degeneracy를
          유발하는 쪽에 근거가 강해진다

Case 2  Qwen만 full에서 붕괴 · EXAONE은 두 조건 모두 안정
        → Qwen2.5-7B-Instruct 특이적 또는 model×input interaction 가능성
          BCS가 틀렸다는 뜻이 아니라 boundary model 선택이 결과에 크게 영향을
          준다는 의미다

Case 3  둘 다 full에 민감하지만 정도가 다름
        → model × input-channel interaction

Case 4  EXAONE도 전혀 다른 형태로 불안정
        → LLM free boundary selection 자체의 안정성이 낮다는 근거가 추가된다
          deterministic change-point(C)가 future work로 더 강해진다
```

---

## 7. 비교 모델 선정 근거

```
LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct
  한국어 특화 — 한국어 처리 능력 차이라는 큰 교란을 줄인다
  다른 패밀리·다른 토크나이저 (GPT2Tokenizer 계열, Qwen과 상이)
  비슷한 크기 (7.8B vs 7B) · bf16으로 24GB에 적재 가능
```

사전 점검(실행 전): config·tokenizer·chat template·remote code 전부 로드 확인.
게이트 없음. `trust_remote_code=True` 필요.

**4호출 뒤에 모델을 더 붙이지 않는다.** 이 실험의 질문은 "Qwen의 현상이 다른
한국어 가능 모델에서도 재현되는가"까지다.

---

## 8. 금지

```
3I7 추가        NO    다른 모델 추가   NO    prompt 수정      NO
rerun search    NO    조건 사후 변경   NO    BCS 수정         NO
model adoption  NO    M9 · test       NO    push            NO
```

산출물: `runs/model_diag/geoje_boundary_degeneracy.json` (raw 전량 · 토큰 수 ·
provenance · commit SHA).
