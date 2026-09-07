# Tier 2 paired — S0(control) vs S1(shadow_vad0) 결과 (2026-09-07)

트랙: `STT_VAD_ONLY_SHADOW_V1` · 사전등록
`docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`

```
hard gate 전부 PASS
presentation eligible   39 → 40      (non-regression 조건 S1 ≥ S0 충족)
parse contract failure   2 → 1       (non-regression 조건 S1 ≤ S0 충족)
production 채택 · 제출본 재생성        HOLD 유지
```

## 1. 고정과 변수

두 arm 모두 `episode_content_v3_summary_only`로 돌렸다. 계약·모델·경계·표현·렌더러가
같고 **claim evidence 자격만** 다르다.

```
같은 것   b1_segments.json (source_segments_sha256 동일) · 41 fixed_window episode
         Qwen2.5-7B-Instruct · bf16 · do_sample false · max_new_tokens 512
         prompt_version episode_content_v3_summary_only · prompt_hash a08e3c3c…
         grounding · OPEN-12 표현 자격 · A2' 렌더러 · window_sec 60
다른 것   evidence_policy   control ↔ shadow_vad0
```

```
gate                        값
partition_equal             true
same_input                  true
same_contract               true
same_model                  true
policy_differs              true
no_evidence_growth          true      S1에서 근거가 늘어난 episode 0
llm_calls                   41 / 41
new_prompt_refusals         0         ERR-009 신규 진입 없음
llm_failures_s1             0
```

## 2. primary — non-regression

```
                       S0 control   S1 shadow
presentation eligible      39           40
parse contract failure      2            1
grounding NOT_APPLICABLE    41           41
claim evidence 합계        777          567   (−210)
```

historical 대조도 같이 적는다.

```
historical R1 (2026-09-03)   eligible 39 / 41 · parse failure 2
paired S0                    eligible 39 / 41 · parse failure 2    ← 재현됨
paired S1                    eligible 40 / 41 · parse failure 1
```

paired 비교의 authority는 같은 실행 환경의 **S0↔S1**이다. historical은 참고다.

S1에서 parse 실패가 1건 줄어 eligible이 1건 늘었다. 이것을 "요약 품질이 좋아졌다"로
읽지 않는다 — 근거 집합이 바뀌면 모델 출력이 바뀌고, 그중 하나가 파싱에 성공한 것뿐이다.

## 3. 내용 변화

```
summary 동일        6 / 41
summary 변경       35 / 41
evidence hash 변경 35 · rendered prompt hash 변경 35   (정확히 일치)
summary 길이 delta  min −67 · max +68 · mean −1.3
source 전환         stt → visual 21 · stt → stt 20
```

`evidence hash 변경 = prompt 변경 = summary 변경 = 35`가 정확히 맞아떨어진다. 즉
**계약·모델이 아니라 근거 집합만 달라졌고**, 근거가 그대로인 6구간은 요약도 글자 그대로
같다(do_sample=false 경로의 결정성 확인이기도 하다).

## 4. removed-ASR-only lexical carryover (evidence-dependence proxy)

정의는 셋뿐이며 사람이 문장을 고르지 않는다.

```
1  S1에서 빠진 ASR(=overlap 0)의 토큰
2  그 episode의 남은 근거(캡션 등)에는 없는 토큰
3  그 토큰이 요약에 문자열로 나타나는가
```

```
episodes with removed ASR      33
S0 요약에 나타난 토큰 수        17
S1 요약에 나타난 토큰 수         5
```

```
S0 예   아이스크림 · 계란후라이 · 고추튀김 · 소금 · 양념을
S1 잔여  EP01 "사용하여"·"준비" · EP02 "양파" · EP22 "모습을"·"보여준다."
```

S1 잔여 5개는 일반어에 가깝다 — 이 proxy는 문자열 일치라 **모델이 자기 어휘로 쓴 말과
근거에서 옮긴 말을 구분하지 못한다.** 그래서 이 수치는 evidence-dependence의 방향을
보여줄 뿐이고, `17−5 = 12건의 환각 제거`로 읽으면 안 된다.

## 5. 실물

```
                      S0        S1
구조 validator        PASS      PASS
한글 Open()           True      True
본문 길이(자)          14,500    14,460
NO_RELIABLE_CONTENT   2         1
```

## 6. 판정 — 세 층으로 나눈다

```
MECHANISM                zero-overlap STT의 claim 사용 = 0            PASS
                         (근거 777 → 567 · 증가한 episode 0)

OPERATIONAL NON-REGRESSION
                         presentation 39 → 40 · parse 2 → 1
                         ERR-009 신규 0 · 구조 실패 0 · partition 동일   PASS

SEMANTIC CORRECTNESS     실제 발화/비발화 사실성                        미검증 (GT 없음)
```

허용되는 주장은 이것뿐이다.

```
A deterministic abstention layer reduced the use of low-speech-confidence STT
as claim evidence without degrading the paired report pipeline.
```

## 7. 주장하지 않는 것

```
210건의 환각을 제거했다            아니다 — GT가 없다
carryover 12건이 환각이었다        아니다 — proxy는 문자열 일치일 뿐이다
보고서가 더 사실적이다             측정하지 않았다
39 → 40이 개선의 증거다            비퇴행 조건을 충족했다는 뜻이다. 성능 주장이 아니다
VAD0를 채택해도 된다               채택은 별도 승인 사건이다
```

## 8. 산출물

```
runs/vad0_paired/{s0_control,s1_shadow}/…            manifest·ingest·episodes·raw_index
                                                     canonical·presentation·report.md
runs/vad0_paired/paired_metrics.json                 gate·episode표·carryover
scripts/v2_1_vad0_paired_run.sh                      두 arm 연속 실행 launcher
scripts/v2_1_vad0_compare.py                         비교기
서버 원본  /ssd/daeseok/b2_20260903/runs/vad0_{s0_control,s1_shadow}/
```

```
production 채택        HOLD
제출본 재생성           HOLD · 현재 제출본 FROZEN (HWPX sha f874f643…)
M9 HOLD · official test UNOPENED
```
