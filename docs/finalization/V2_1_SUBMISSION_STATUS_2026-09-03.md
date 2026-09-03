# 제출 상태 — arm 확정 · SUBMISSION_READY (2026-09-03)

```
V2.1 IMPLEMENTATION_COMPLETE = YES      baseline 6e79ac3
B2   OPERATIONAL_COMPLETE    = YES
SUBMISSION ARM               = R1 / episode_content_v3_summary_only
SUBMISSION_READY             = YES

V3 SUMMARY-ONLY
  mechanism closure                PASS
  paired presentation eligibility  39 / 41
  v2 regression                    PASS
  default promotion                NOT ADOPTED
```

## 0. 두 상태를 구분해 보존한다

```
accepted v2 baseline        6e79ac3   태그 v2.1-accepted-baseline
                                      v2.1 공식 판정의 기준점. 소급 변경 금지
submission-ready state      HEAD      태그 submission-ready-2026-09-03
                                      제출본을 만든 저장소 상태
제출 artifact 생성 코드       f81be81   run_manifest.fingerprint.code_revision
                                      (이후 커밋은 문서·검증 전용이며 산출물을 바꾸지 않았다)
```

제출 편의로 baseline이나 prompt hash를 소급 변경하지 않았다. 두 상태를 다른 이름으로
남겨 "이 hwpx가 어느 상태의 산출물인가"를 나중에 다시 추측하지 않게 한다.

## 1. SUBMISSION_READY의 뜻은 좁다

```
SUBMISSION_READY means the selected v3 presentation artifact is
operationally complete, openable, and has adequate presentation recall
under the accepted project contracts.

It does not mean that all generated summaries have been independently
verified for semantic entailment or factual correctness.
```

**SUBMISSION_READY는 선택된 v3 보고서가 실행·렌더링·표현 회수율 측면에서 제출 가능한
상태라는 뜻이며, 모든 생성 요약의 의미적 사실성이 독립 검증되었다는 뜻은 아니다.**

GRD-004가 P1 WAIVED로 남아 있는 것과 정확히 일치한다.

## 2. 제출 profile — 명시적 선택이고 기본값 교체가 아니다

```
repository default contract   episode_content_v2        그대로
accepted v2 baseline          6e79ac3                  그대로
submission profile            episode_content_v3_summary_only
selection                     명시적 (--contract v3)
silent promotion              없음
```

`v3가 더 좋으니 default도 v3로 바꾼다`는 **별도 채택 사건**이며 이 문서는 그것을 하지
않는다. 기본값이 v2라는 것은 테스트로 잠겨 있다(`test_c_the_default_call_is_v2`,
mutation M3 RED).

## 3. 제출 artifact provenance

`runs/v3_paired/submission_manifest.json` — 수치를 손으로 적지 않고 실행 산출물에서
읽었고, 한글 열림·PDF export는 생성 시점에 **실제로 실행**해 기록했다
(`scripts/v2_1_submission_manifest.py`).

```
submission_contract      episode_content_v3_summary_only
prompt_hash              a08e3c3c4988daa6639cf0316f8b5d81f466685590fb54400eeda7d6ab6610d7
code_revision            f81be816c9903a66dec9d6a3a5aea73ec9d322c4
config_hash              bb0d2299aabab800ee71495478cb5df23676152f2b00cd93c78227dd4f32578d
input segments sha256    aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
segment_count            485
model                    Qwen/Qwen2.5-7B-Instruct · a09a35458c702b33… · bf16 · llm_4bit false
generation               do_sample false · max_new_tokens 512

episodes                 41
presentation_eligible    39
parse_contract_failure   2
renderer                 A2' pure-Python OWPML
structural_validator     PASS
hancom_open              PASS
pdf_export               PASS (134,938 B)
artifact                 report.hwpx · 15,824 B · sha256 f874f64311270412…
```

제출본 사본: `Desktop/v3_submission/` (hwpx · md · pdf · manifest). 사본의 HWPX
sha256이 manifest 값과 일치하는 것을 확인했다.

## 4. 41 = 39 + 2 — 숨기지 않는다

```
41  canonical episodes
39  presentation-eligible
 2  parse-contract failure   (EP35 · EP39)
```

```
EP35   summary 문자열 중간에서 중국어로 이탈한 뒤 JSON 블록을 두 번 냈다
EP39   summary 문자열 중간에서 중국어로 이탈하고 잘렸다(92 B에서 끝)
```

두 구간은 보고서에서 상태로만 남는다(`NO_RELIABLE_CONTENT`). manifest에
상태 문장 하나를 남겼다.

```
2 episodes unavailable due to parse-contract failure
```

renderer가 새 자연어 설명을 만들어 채우지 않는다. 억지 문장으로 메우지 않았다.

## 5. v2 → v3 parse 실패 1 → 2 는 known observation

```
v2 parse failures = 1
v3 parse failures = 2
```

n=41 · paired run 1회이므로 `v3 worsens parsing`은 **주장하지 않는다.** 제출 blocker도
아니다 — 39/41 사용 가능한 보고서가 나왔고 실패 상태는 명시적으로 보존된다.

## 6. 알려진 한계 (제출과 함께 남긴다)

```
2 / 41 parse-contract failures
GRD-004 P1 WAIVED — semantic entailment는 자동 검증되지 않는다
문자 그림 box 정렬은 표현 품질 diagnostic이며 P0가 아니다
M9 = HOLD
official test = UNOPENED (39건 · 재열람 금지)
```

## 7. 이 확정 뒤 하지 않는 것

```
v3를 repository default로 변경          하지 않는다
v2 프롬프트·hash 수정                    하지 않는다
OPEN-12 완화                            하지 않는다
EP35·EP39 때문에 프롬프트 재튜닝          하지 않는다
실패한 두 구간만 재생성해 cherry-pick     하지 않는다
summary semantic grounding 추가          하지 않는다
official test 접근 · M9 실행             하지 않는다
```

39/41을 41/41로 만들려고 두 구간만 다시 생성하지 않는다 — `do_sample=false`라도
입력·환경을 손대기 시작하면 제출 artifact가 paired 실험의 고정 조건에서 벗어난다.
