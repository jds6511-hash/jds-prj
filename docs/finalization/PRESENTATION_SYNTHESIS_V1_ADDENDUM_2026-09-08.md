# Decision addendum — PRESENTATION_SYNTHESIS_V1 (2026-09-08)

결과를 보기 **전에** 계약·형식·게이트를 고정한다. 실행 후 수정하지 않는다.

```
사건 분류   presentation-level hierarchical synthesis
입력        확정된 accepted episode summaries (재생성 없음)
출력        9 chapter summary + 짧은 overview · analysis points · conclusion
```

## 1. 계층 강제

```
episode summary   →  GroupSynthesizer   →  chapter (title + 1~2문장)
chapter           →  GlobalSynthesizer  →  overview(3~5문장) · analysis(3~6) · conclusion(1~2)
```

`episode → global` 직행은 금지다. GlobalSynthesizer의 입력은 chapter뿐이다.

## 2. freeze — 건드리지 않는 것

```
canonical episode 41 · fixed-window partition · partition hash · episode id·경계
presentation grouping 300초 · group membership
raw STT · B1 · caption · OCR artifact
STT_VAD0 · output_quality_v1 · repository default v2
현행 제출본·tag (submission-quality-2026-09-08 · submission-vad0-2026-09-07 ·
                submission-ready-2026-09-03)
```

`300초`를 결과를 보고 semantic boundary로 바꾸지 않는다. semantic chapter boundary
검출은 별도 연구 사건이다.

## 3. 기존 표현 객체는 그대로 둔다 (설계 제약)

`validate_presentation`은 `PresentationHighlight.summary`가 **source summary의 정확한
concat**인지 재구성으로 검증한다(src/v2_1_presentation.py). 합성문을 그 필드에 넣으면
frozen 계약이 깨진다.

```
PresentationHighlight.summary     그대로 concat 유지 — lineage 증거다
chapter 합성문                     새 객체(GroupSynthesisResult)에 담는다
보고서 본문                        chapter 합성문을 싣고, 상자에는 lineage를 함께 적는다
```

즉 **정본 표현 객체와 제출 문장을 분리**한다. 두 값이 다른 것은 결함이 아니라 계층
분리이며, manifest에 둘 다 남는다.

## 4. 신규 prompt contract (기존 계약 무수정)

```
PRESENTATION_SYNTHESIS_CONTRACT_V1   group 합성
GLOBAL_SYNTHESIS_CONTRACT_V1         global 합성
```

`CONTRACT`(v2) · `CONTRACT_V3`는 고치지 않는다. 두 신규 계약은 각자 version과
`contract_hash`를 갖고 manifest에 기록된다.

## 5. 입력 계약 (P0)

GroupSynthesizer가 받는 것은 그 group의 **표현 자격 있는** episode뿐이다.

```
허용   episode_id · 시간(mm:ss) · accepted summary
금지   raw STT · caption 원문 · OCR · frame · 영상 · YouTube metadata
       표현 자격 없는 episode의 summary·raw model output
```

실측 사례로 고정한다.

```
H03  입력 EP11 · EP12 · EP14 · EP15      제외 EP13 (OUTPUT_LANGUAGE_DRIFT)
H04  입력 EP16 · EP18 · EP19 · EP20      제외 EP17 (PARSE_CONTRACT_FAILURE)
```

## 6. 출력 형식 freeze

```
chapter    title 1줄 · summary_sentences 1~2개
           문장별 source_episode_refs (그 group의 eligible episode에서만)
global     overview_sentences 3~5개
           analysis_points 3~6개 (각 1문장 + source_highlight_refs)
           conclusion_sentences 1~2개
           global 계층은 highlight ref만 쓴다 (episode ref 금지)
```

입력 episode 수와 출력 문장 수를 1:1로 맞추지 않는다. **5 episode → 5문장은 FAIL**이다.

## 7. 생성 설정 (모델 비교 금지)

```
model            Qwen/Qwen2.5-7B-Instruct   (B2 episode 생성과 같은 family·snapshot)
do_sample        false (greedy)
max_new_tokens   512
호출 수           group 최대 9 · global 1  (합 10 내외)
episode 재생성    없음 — episode_llm_rerun = false
```

## 8. 실패는 실패로 남긴다

```
GROUP_SYNTHESIS_FAILURE     group 합성 실패
GLOBAL_SYNTHESIS_FAILURE    global 합성 실패
```

**silent fallback 금지.** 실패 시 예전 concat(`EP01 / EP02 / …`)으로 되돌리지 않는다.
raw model output·source episode·사유를 보존하고 그 상태로 표시한다.

특정 group만 다시 돌리거나 프롬프트를 바꿔 재시도하지 않는다 — 새 프롬프트는 새
version·hash 사건이다.

## 9. output_quality_v1 재사용

chapter title·문장과 global 문장에 기존 판정기를 그대로 적용한다.

```
PASS      정상
SUSPECT   diagnostic (자동 제외 아님 — 승격 금지)
FAIL      정상 content로 싣지 않는다
blocking  OUTPUT_LANGUAGE_DRIFT · OUTPUT_LANGUAGE_CONTRACT_FAILURE
```

## 10. GLS 테스트 계약 조정 (matrix 본문 무수정)

frozen acceptance matrix의 GLS-001 본문은
`| GLS-001 | P1 | overview generation | 개요 생성 |`뿐이다
(`V2_1_ACCEPTANCE_MATRIX_2026-08-30.md:207`). "모든 eligible episode summary가 개요에
포함"은 matrix 계약이 아니라 **regression test 구현**이다.

```
기존 test 계약   all eligible episode summaries appear in overview
새 test 계약     overview가 존재한다
                overview의 출처는 유효한 group synthesis 결과다
                overview는 3~5개 구조화 문장이다
```

matrix 원본은 수정하지 않는다. 기존 테스트는 **synthesis 경로에 대해서만** 새 계약을
쓰고, 기존 concat 경로의 테스트는 그대로 통과해야 한다(두 경로가 공존한다).

`GLS-002`(analysis generation) · `GLS-003`(conclusion)은 유지한다. analysis는
`H01: 구성 5구간 · 출처 5구간` 같은 lineage 나열이 아니라 **cross-chapter 흐름
3~6개**를 싣는다.

## 11. 보고서 구조 freeze

```
■ 개요                3~5문장
■ 주요 사건 및 내용     H01~H09 · title · 시간 · 1~2문장 · 구성 구간 · 요약 출처 · 제외 구간
■ 핵심 내용 분석        cross-chapter 3~6 points
■ 결론                1~2문장
■ 근거 및 생성 정보     provenance · 제외 · 한계
```

`구성 N구간 · 출처 N구간`을 분석 절에서 반복하지 않는다.

## 12. 진단 (threshold 아님)

```
episode summary 총 글자 수 · chapter 합성 총 글자 수 · overview 글자 수 · 보고서 글자 수
episode summary 원문 재인쇄 횟수
group 압축률 · global 압축률
동일 문장 수 · 근접 중복 진단
```

첫 버전에서는 전부 **diagnostic**이다. 이 값을 보고 형식 상한을 조정하지 않는다.

## 13. 산출물

```
runs/presentation_synthesis_v1/
  group_raw/ · group_parsed/ · global_raw/ · global_parsed/
  report.md · report.hwpx · manifest.json
```

기존 `runs/vad0_paired/` · `runs/quality_candidate/` · `Desktop/v3_submission_quality/`
· 제출 tag는 READ ONLY다.

## 14. provenance 최소 항목

```
source_episode_content_hash · source_quality_candidate_hash · canonical_partition_hash
presentation_group_window_sec = 300
group_synthesis_contract_version · group_prompt_hash
global_synthesis_contract_version · global_prompt_hash
model_id · model_snapshot · generation_config
episode_llm_rerun = false · group_llm_call_count · global_llm_call_count
excluded episodes · output_quality_policy_version/hash
final md/hwpx/pdf hashes
```

## 15. 주장하지 않는 것

```
영상의 모든 사실이 검증됐다 · semantic entailment가 해결됐다
환각이 제거됐다 · 영상 이해 정확도가 향상됐다
chapter boundary가 semantic하게 최적화됐다
```

이번 작업은 **presentation-level hierarchical synthesis**이며, source lineage는
제공하지만 semantic verification은 계속 별도 한계다.

## 16. 방법론 출처

hierarchical summarization · summarize-then-summarize · chapter-level presentation ·
source lineage preservation 원칙만 차용한다(Video ReCap · Summ^N · long-video
chaptering 계열). **논문 구현을 재현했다고 주장하지 않는다.**

## 17. 정지점

```
candidate 생성 후 SUBMISSION_PROMOTION = HOLD
```

현행 제출본을 자동 교체하지 않는다.
