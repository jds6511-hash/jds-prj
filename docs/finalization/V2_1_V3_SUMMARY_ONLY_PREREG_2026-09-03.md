# summary-only 생성 계약(v3) 사전등록 + GEO 호환성 감사 (2026-09-03)

```
B2 operational status   COMPLETE
report usability        NOT READY
finding                 PRESENTATION_RECALL_COLLAPSE   실측 회수율 2 / 41
SUBMISSION_READY        NO

①  presentation eligibility 완화     REJECT as primary  (관측 후 frozen safety 완화)
②  summary-only 생성 계약            SELECTED           1차 remediation 후보
③  프롬프트로 dialogue 제약           DEFER              완화책이지 보장이 아니다
구현                                아직 하지 않는다
```

---

## 1. P1 — GEO-001 · GEO-004 호환성 감사 (실측)

소스를 읽고 추론하지 않았다. **프롬프트 계약을 실제로 summary-only로 바꿔 넣고**
매핑된 테스트를 돌렸다. 끝난 뒤 원본으로 되돌렸다(작업 트리 clean 확인).

주입한 v3 후보.

```
PROMPT_VERSION   episode_content_v2 → episode_content_v3_summary_only
rules            stt_cites 관련 2줄 제거
output           required ["summary"] · optional [] · omit_when_absent []
프롬프트 꼬리      "쓸 수 있는 키는 셋뿐이다" → "하나뿐이다" (summary만)
```

결과.

```
                          baseline            v3 주입
GEO-001·004 매핑 5건       5 passed            5 passed      ← 깨지지 않는다
GEO/TRI family 52건        52 passed           52 passed
grounding 35건             35 passed           35 passed
LLM P1 계약 12건           12 passed           12 passed
프롬프트 계약 26건          26 passed           **7 failed** / 19 passed
전체 suite                 3,884 passed        12 failed / 3,872 passed
```

깨진 것의 정체는 **GEO가 아니라 프롬프트 계약의 형태**다.

```
test_prompt_version_is_declared                    "episode_content_v2" 고정
test_llm_002_required_output_is_summary_only       optional == ["dialogue_note","stt_cites"]
test_llm_002_contract_fields_match_the_episode_schema
                                                   required+optional == MODEL_FIELDS
                                                   (v2_1_episode.MODEL_FIELDS 3종)
test_llm_002_prompt_states_the_output_shape        프롬프트 본문의 키 서술
test_open_10_optional_fields_are_omitted_not_filled
test_open_10_the_three_keys_are_still_named        summary·dialogue_note·stt_cites 명시
test_cites_are_restricted_to_claim_evidence        프롬프트에 stt_cites가 있어야 한다
```

그 밖에 B2 orchestrator 테스트 2건이 깨졌다 — 내 dry-run fixture가 dialogue를 넣고
manifest가 `episode_content_v2`를 못 박기 때문이다(계약 고정이 의도대로 작동한 것).
REG-004는 감사 중 트리가 더러웠기 때문이며 되돌린 뒤 사라진다.

**감사 결론.**

```
GEO-001   dialogue 생성에 의존하지 않는다
          성립 조건은 "자격 있는 발화가 근거 블록에 도달한다"이고 v3에서 그대로다
GEO-004   dialogue-heavy 구간의 처리·source 파생(speech)에 의존한다
          그것도 timeline·episode 계층 소관이라 v3에서 그대로다
충돌 대상   LLM-002 · OPEN-10 — **생성 계약의 형태**를 고정한 항목들이다
```

따라서 ②는 GEO governance 사건이 아니고, **프롬프트 계약 버전 관리 사건**이다.

---

## 2. 그래서 v2를 고치지 않는다 — 병행 계약으로 넣는다

위 7건이 깨진 것은 v2 계약을 **제자리에서 바꿨기** 때문이다. v3를 별도 계약으로 두면
그 7건은 v2를 계속 재고 통과한다.

```
src/v2_1_prompt.py       CONTRACT (v2)              그대로 · 수정 0
                         CONTRACT_V3 (신규)          summary-only
                         build_episode_prompt(..., contract=CONTRACT)  기본값 v2
PROMPT_VERSION           episode_content_v2          그대로
                         episode_content_v3_summary_only  신규 상수
prompt_hash              계약별로 따로 계산된다 — 정본에 어느 계약인지 남는다
```

```
금지   v2 계약 본문 수정 · MODEL_FIELDS 축소 · 기존 prompt_hash 재해석
허용   v3 계약 추가 · orchestrator가 어느 계약을 쓸지 선택(기본은 v2)
```

이렇게 하면 **가드를 낮추지 않고, 가드를 불필요하게 발동시키는 출력 surface만 없앤다.**

---

## 3. 가설

```
H-R1  표현 회수율 붕괴의 주원인은 선택적 dialogue 생성이 episode 단위 grounding 실패를
      유발한 것이고, 쓸 수 있는 정본 요약의 부재가 아니다.

      실측 지지   canonical summary 40/41 존재 · presentation summary 2/41
                grounding FAIL 38/41 (unsupported_anchor 329 · no_support_ref 12 ·
                no_evidence_at_segment 8) · PASS 0

H-R2  요약 계약을 보존한 채 dialogue 생성을 제거하면, grounding·표현 자격 규칙을
      완화하지 않고도 표현 가능한 episode 수가 크게 늘어난다.
```

---

## 4. 실험 설계 — 같은 41 episode

새 human GT를 만들지 않는다. 같은 B1 입력·같은 서버·같은 모델 snapshot으로 두 arm만 비교한다.

```
R0  현행 v2      summary + dialogue        이미 실행됨 (2026-09-03 · 2/41)
R1  v3          summary only              신규
```

```
바꾸는 것   PROMPT_VERSION · 출력 schema · dialogue 생성 요구
고정하는 것  B1 input hash aa008317023c884a206c…
           canonical episode 41 · fixed_window_v1 · window_sec 60
           Qwen2.5-7B-Instruct · snapshot a09a35458c702b33… · bf16
           do_sample=false · max_new_tokens 512
           grounding 규칙 · OPEN-12 표현 자격 · presentation builder · A2' 렌더러
```

## 5. 지표

```
primary    표현 자격 episode 수 / 41        (R0 실측 baseline = 2 / 41)

보조       parse: VALID_PARSE · PARSE_CONTRACT_FAILURE
          grounding: PASS · NOT_APPLICABLE · FAIL_*
          presentation: AVAILABLE · NO_RELIABLE_CONTENT
          raw 보존 수 · summary 비어있지 않음 수 · summary_mode 분포
          episode별 wall time · VRAM peak/p95/median · LLM call·failure·retry
```

**주장하지 않을 것.**

```
"unsupported content가 줄었다"     아니다 — dialogue field 자체를 없앴으므로
                                 그 실패 표면이 사라진 것이다
"모든 요약이 grounded다"           아니다 — GRD-004는 P1 WAIVED 그대로다
"보고서 품질이 좋아졌다"            측정 대상이 아니다. 이번 건은 mechanism repair다
```

## 6. 절대 하지 않을 것 — summary 재grounding

②를 골랐다고 요약의 모든 사실을 semantic entailment로 검증하는 방향으로 넓히면
GRD-004를 다시 연다. v3의 범위는 정확히 셋이다.

```
dialogue 출력 제거
현행 summary 동작 보존
GRD-004 waiver 보존
```

TRI-005의 sparse safe mode(`eligible == 1` → 근거 원문)도 그대로 유지한다.

## 7. P3 — 합성 테스트 (서버 없이)

```
normal            다구간 · 요약만 · 표현 자격 통과
rich-STT          GEO-001 조건 · 자격 발화가 근거 블록에 도달한다
dialogue-heavy    GEO-004 조건 · source가 speech로 파생된다
sparse            eligible == 1 · SPARSE_EVIDENCE_DETERMINISTIC 유지
no-evidence       PromptError · EMPTY · 구조 유지
parse failure     raw 보존 · PARSE_CONTRACT_FAILURE
v2 계약 회귀       v2로 부르면 프롬프트 계약 26건이 그대로 통과한다
```

v3 프롬프트에 `dialogue_note`·`stt_cites` 문자열이 **없다**는 것도 계약으로 잰다.

## 8. closure 문구 (성공 시 이렇게만 쓴다)

```
Presentation eligibility no longer collapses because of an optional dialogue field.
```

```
쓰지 않는다   general entailment 해결 · GRD-004 해제 · 표현 자격 완화
             보고서 품질 개선 · unsupported content 감소
```

## 9. 승인이 필요한 것

```
1  §2 v3를 v2와 **병행 계약**으로 추가 (v2 본문 수정 0)
2  §4 R0 vs R1 비교 · 같은 41 episode · 서버 재실행 1회
3  §5 primary metric = 표현 자격 episode 수 / 41
4  §7 합성 테스트 통과 후에만 서버 실행
```

```
불변   v2.1 IMPLEMENTATION_COMPLETE = YES (baseline 6e79ac3)
      GRD-004 P1 WAIVED · M9 HOLD · official test UNOPENED
      B2 full run 기록(97bd0504 계열)은 그대로 남는다
```
