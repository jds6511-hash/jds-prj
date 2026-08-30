# v2.1 ACCEPTANCE / TEST MATRIX (2026-08-30)

```
Purpose                    v2.1 implementation acceptance gate
Canonical provider         fixed_window_v1
Caption change-point       non-gating / non-default
Official test              MUST NOT RUN
```

계획: `V2_1_IMPLEMENTATION_PLAN_2026-08-30.md`

```
P0  hard gate                                   1개라도 실패 시 acceptance FAIL
P1  PASS 또는 명시적 문서화된 WAIVER 필요          waiver 없는 FAIL → acceptance BLOCKED
P2  non-gating diagnostic / quality              자동 차단하지 않음

waiver 대장: docs/finalization/V2_1_P1_WAIVERS.md
  test id · failure description · reason · known impact · scope of limitation
  **skip을 waiver로 간주하지 않는다** (ADDENDUM OPEN-5)
```

---

## 2. Schema / Parse Contract

| ID | Pri | Test | 조건 | 기대 |
| --- | --: | --- | --- | --- |
| SCH-001 | P0 | canonical schema valid | 정상 artifact | validation PASS |
| SCH-002 | P0 | required field missing | `episode_id` 제거 | validation FAIL |
| SCH-003 | P0 | invalid type | `start_sec="five"` | validation FAIL |
| SCH-004 | P0 | malformed upstream raw | invalid JSON | raw 저장 후 `PARSE_FAILED` |
| SCH-005 | P0 | parse failure ≠ empty valid | malformed payload | `EMPTY`와 `PARSE_FAILED` 구분 |
| SCH-006 | P1 | unknown optional field | 신규 필드 | 보존 또는 명시적 ignore |
| SCH-007 | P0 | parser는 sanitation을 하지 않음 | 읽히는 instruction echo | parse PASS · sanitation이 처리 |
| SCH-008 | P0 | cite 표기 정규화 | `55` · `"55"` · `"seg#55"` | 동일 값으로 normalize |
| SCH-009 | P0 | 표기 실패 분류 | 파싱 불가 | `PARSE_CONTRACT_FAILURE` (≠ MODEL_FAILURE) |

## 3. Raw Persistence

| ID | Pri | Test | 조건 | 기대 |
| --- | --: | --- | --- | --- |
| RAW-001 | P0 | raw before parse | 정상 output | raw 저장 후 parse |
| RAW-002 | P0 | raw survives parse failure | malformed output | raw 원본 유지 |
| RAW-003 | P0 | modality identifiable | ASR/VLM/OCR | source modality 추적 가능 |
| RAW-004 | P0 | segment provenance | 특정 segment output | segment_id 역추적 |
| RAW-005 | P1 | producer metadata | model/version | metadata 보존 |
| RAW-006 | P1 | rerun separation | 동일 영상 2 run | 덮어쓰기 없음 |

## 4. Sanitation

| ID | Pri | Test | 조건 | 기대 |
| --- | --: | --- | --- | --- |
| SAN-001 | P0 | instruction echo 검출 | `"요청에 따라 한 문장의…"` | 정상 caption으로 통과하지 않음 |
| SAN-002 | P0 | empty caption | 공백/빈 문자열 | `EMPTY` |
| SAN-003 | P1 | 외국어 이상 | 주변과 무관한 중국어 caption | `SUSPECT` 또는 정책 상태 |
| SAN-004 | P1 | 반복 boilerplate | 영상 전체 exact normalized 출현 ≥8 | **SUSPECT만 부여** · 삭제 금지 (OPEN-7) |
| SAN-005 | P0 | parse failure 구분 | 파싱 불가 | `PARSE_FAILED` ≠ `REJECTED` |
| SAN-006 | P1 | 정상 caption 유지 | 객관적 caption | `VALID` |
| SAN-007 | P0 | OCR isolation | OCR 단독 strong claim | 단독 근거 승격 금지 |
| SAN-008 | P1 | 정상 ASR 유지 | 정상 대화 STT | downstream 사용 가능 |
| SAN-009 | P1 | 오염 STT | 무의미/오염 STT | 정상 대화와 동일 취급 금지 |
| SAN-010 | P0 | 실제 발화 보존 | 흥분한 반복 발화 | 반복만을 이유로 삭제 금지 (BCS 실측) |
| SAN-011 | P0 | 반복 suspect eligibility | exact normalized 출현 ≥8 | `SUSPECT` · `usable_for_claims=false` · 원문 보존 · 삭제 없음 |

## 5. Evidence Timeline

| ID | Pri | Test | 조건 | 기대 |
| --- | --: | --- | --- | --- |
| EVT-001 | P0 | segment alignment | multimodal evidence | 올바른 segment 연결 |
| EVT-002 | P0 | missing modality | ASR 없음 | 빈 refs 허용 · 구조 유지 |
| EVT-003 | P0 | invalid ref | 없는 artifact ref | validation FAIL |
| EVT-004 | P0 | out-of-range timestamp | 영상 밖 | reject/fail |
| EVT-005 | P1 | sparse evidence | 3I7류 | timeline 생성 성공 |
| EVT-006 | P1 | rich ASR | geoje류 | ASR refs 정상 |
| EVT-007 | P0 | sanitation state 보존 | suspect caption | downstream 식별 가능 |

## 6. BoundaryProvider Interface

| ID | Pri | Test | 조건 | 기대 |
| --- | --: | --- | --- | --- |
| BPI-001 | P0 | provider identity | fixed window 실행 | `provider_name=fixed_window_v1` |
| BPI-002 | P0 | config recorded | window config | config provenance 존재 |
| BPI-003 | P0 | caption embedding semantics | `emb_cap.npy` 경로 | visual embedding으로 표기 금지 |
| BPI-004 | P0 | provider explicit | provider 미지정 | default가 `fixed_window_v1` |
| BPI-005 | P0 | no silent substitution | provider error | 자동 fallback 금지 |
| BPI-006 | P1 | optional embedding | fixed window | embedding 없이 정상 실행 |

## 7. fixed_window_v1

| ID | Pri | Test | 조건 | 기대 |
| --- | --: | --- | --- | --- |
| FW-001 | P0 | deterministic rerun | 동일 영상/config N회 | boundary 완전 동일 |
| FW-002 | P0 | model independence | LLM 변경 | boundary 동일 |
| FW-003 | P0 | ASR independence | ASR 변경 | boundary 동일 |
| FW-004 | P0 | caption independence | caption 변경 | boundary 동일 |
| FW-005 | P0 | OCR independence | OCR 변경 | boundary 동일 |
| FW-006 | P0 | exact duration | 60s fixture | full coverage |
| FW-007 | P0 | partial tail | 62s fixture | 마지막 2s 포함 |
| FW-008 | P0 | very short video | <5s | 단일 short segment로 전체 coverage |
| FW-009 | P0 | zero-length handling | invalid zero duration | 명시적 FAIL |
| FW-010 | P1 | long input | 장시간 synthetic | deterministic |

## 8. Canonical Partition Invariants

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| CAN-001 | P0 | no overlap | overlap = 0 |
| CAN-002 | P0 | no gap | gap = 0 |
| CAN-003 | P0 | exactly-once assignment | 정확히 1 episode |
| CAN-004 | P0 | starts at canonical_video_start | `first_segment.start_sec` 일치 |
| CAN-005 | P0 | ends at canonical_video_end | `last_segment.end_sec` 일치 (ADDENDUM OPEN-2) |
| CAN-006 | P0 | monotonic order | 시간 순서 엄격 |
| CAN-007 | P0 | positive duration | `end > start` |
| CAN-008 | P0 | adjacent continuity | `end_i == start_{i+1}` |
| CAN-009 | P0 | valid segment refs | 모두 실재 |
| CAN-010 | P0 | forced overlap injection | validator FAIL |
| CAN-011 | P0 | forced gap injection | validator FAIL |
| CAN-012 | P0 | duplicate segment injection | validator FAIL |
| CAN-013 | P0 | unassigned segment injection | validator FAIL |

## 9. Caption Change-Point — non-adoption safeguard

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| CP-001 | P0 | not default | 일반 실행에서 선택되지 않음 |
| CP-002 | P0 | explicit enable only | flag 없으면 실행되지 않음 |
| CP-003 | P0 | no tuning embedded | C0 기반 tuned threshold 없음 |
| CP-004 | P0 | no human GT optimization | GT 기반 threshold 선택 없음 |
| CP-005 | P0 | no LLM agreement criterion | LLM boundary가 채택 기준 아님 |
| CP-006 | P1 | sanitation prerequisite 문서화 | caption QC 의존성 명시 |
| CP-007 | P1 | VLM dependence recorded | model/input 의존성 문서화 |
| CP-008 | P2 | diagnostic output | signal curve 저장 가능 |
| CP-009 | P2 | defect peak observation | 기록만 · acceptance와 분리 |

## 10. Episode Content LLM

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| LLM-001 | P0 | boundary not model-generated | 모델이 start/end 결정하지 않음 |
| LLM-002 | P0 | required output minimal | 필수 생성은 `summary` 중심 |
| LLM-003 | P0 | episode_id derived | code value 사용 |
| LLM-004 | P0 | support span derived | code-derived span 우선 |
| LLM-005 | P0 | provenance derived | code-derived source refs |
| LLM-006 | P1 | no ASR case | summary 또는 명시적 insufficient |
| LLM-007 | P1 | no caption case | summary 또는 명시적 insufficient |
| LLM-008 | P1 | empty evidence | hallucinated event 생성 금지 |
| LLM-009 | P0 | model failure isolation | episode structure 유지 |
| LLM-010 | P1 | rich dialogue | dialogue evidence 활용 |

## 11. Grounding Validator

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| GRD-001 | P0 | valid refs | PASS |
| GRD-002 | P0 | nonexistent evidence ref | FAIL_REFERENCE |
| GRD-003 | P0 | outside-episode ref | FAIL |
| GRD-004 | **P1** | unsupported event (§OPEN-3) | 정책상 FAIL_UNSUPPORTED |
| GRD-005 | P0 | unsupported named entity | FAIL_UNSUPPORTED (문자열 앵커) |
| GRD-006 | P0 | OCR-only claim | strong event claim 승격 금지 |
| GRD-007 | P1 | partial support | 정책 일관 적용 |
| GRD-008 | P0 | validation status persisted | canonical JSON에 기록 |
| GRD-009 | P0 | failure not hidden | PASS처럼 표현 금지 |
| GRD-010 | P0 | claim without support ref | 무조건 FAIL (결정 가능) |
| GRD-011 | P0 | SUSPECT-only dialogue claim | `FAIL_INELIGIBLE_SUPPORT` (≠ FAIL_REFERENCE) |
| GRD-012 | P0 | VALID+SUSPECT 동시 인용 | VALID만으로 성립해야 PASS · 자동 PASS 금지 |

## 12. aar_canonical.json

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| AAR-001 | P0 | standalone schema | presentation 없이 유효 |
| AAR-002 | P0 | all episodes present | 전체 partition 포함 |
| AAR-003 | P0 | provenance present | source refs 추적 |
| AAR-004 | P0 | grounding state present | validator 상태 존재 |
| AAR-005 | P0 | presentation not canonicalized | canonical episode list 불변 |
| AAR-006 | P0 | rerun structural equality | episode boundaries 동일 |
| AAR-007 | P1 | serialization roundtrip | 의미 보존 |

## 13. Presentation Highlight Builder

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| HLT-001 | P0 | source lineage | source episode IDs 존재 |
| HLT-002 | P0 | overlap permitted | highlight overlap 허용 |
| HLT-003 | P0 | canonical untouched | canonical overlap 0 유지 |
| HLT-004 | P0 | no target row count | 특정 개수 강제 없음 |
| HLT-005 | P1 | merge episodes | 여러 episode → 1 highlight |
| HLT-006 | P1 | same episode reused | 다중 highlight 지원 |
| HLT-007 | P0 | no reverse boundary mutation | canonical boundary 변경 금지 |
| HLT-008 | P1 | empty/weak content | graceful degradation |

## 14. Human-authored Format Reference Safeguard

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| REF-001 | P0 | provenance label | 저자 = 사용자 명시 |
| REF-002 | P0 | not GT | GT로 표시되지 않음 |
| REF-003 | P0 | no pipeline comparison | `wonyi_gyeongju` 자동 성능 대조 없음 |
| REF-004 | P0 | no boundary optimization | boundary tuning에 미사용 |
| REF-005 | P0 | no row-count target | 행 수에 맞추지 않음 |
| REF-006 | P1 | format-only use | 섹션 구조 참고는 허용 |

## 15. Global Synthesis

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| GLS-001 | P1 | overview generation | 개요 생성 |
| GLS-002 | P1 | analysis generation | 핵심 내용 분석 생성 |
| GLS-003 | P1 | conclusion generation | 결론 생성 |
| GLS-004 | P0 | no false entailment claim | 자동 완전 검증 주장 없음 |
| GLS-005 | P0 | source episode existence | 참조 episode 실재 |
| GLS-006 | P0 | rejected episode handling | 사실처럼 종합 금지 |
| GLS-007 | P1 | no reliable evidence | 과도한 구체 결론 억제 |

## 16. Preview / MD / HWPX Interlock

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| RPT-001 | P0 | common canonical source | 동일 `aar_canonical` 기반 |
| RPT-002 | P0 | episode identity consistency | lineage 동일 |
| RPT-003 | P0 | no renderer-side boundary creation | 신규 boundary 생성 금지 |
| RPT-004 | P1 | formatting differences allowed | 표현 차이 허용 |
| RPT-005 | P0 | semantic source consistency | 다른 evidence pipeline 금지 |
| RPT-006 | P1 | presentation fallback | canonical 유지 |
| RPT-007 | P0 | structural fallback forbidden | 임의 보정 성공 처리 금지 |
| RPT-008 | P0 | analysis_mode interlock | `!= report` 이면 render 거부 |

## 17. Failure-mode

| ID | Pri | Injection | 기대 |
| --- | --: | --- | --- |
| ERR-001 | P0 | partition overlap | hard fail |
| ERR-002 | P0 | partition gap | hard fail |
| ERR-003 | P0 | invalid evidence ref | hard fail 또는 grounding fail |
| ERR-004 | P0 | caption parse failure | raw 유지 + explicit status |
| ERR-005 | P0 | LLM summary failure | structure 유지 + content failure |
| ERR-006 | P1 | highlight builder failure | canonical 유지 · fallback 가능 |
| ERR-007 | P1 | HWPX renderer failure | canonical/MD 영향 없음 |
| ERR-008 | P0 | provider unavailable | silent fallback 금지 |
| ERR-009 | P0 | all evidence absent | hallucinated event 금지 |
| ERR-010 | P0 | instruction echo top signal | fixed-window boundary 영향 없음 |

## 18. Determinism

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| DET-001 | P0 | same video + config | canonical partition 동일 |
| DET-002 | P0 | rerun N≥3 | **boundary list·episode 구조** 동일 (§OPEN-4) |
| DET-003 | P0 | different LLM | canonical partition 동일 |
| DET-004 | P0 | different VLM caption | fixed-window boundary 동일 |
| DET-005 | P0 | changed OCR | fixed-window boundary 동일 |
| DET-006 | P1 | serialization rerun | ids/ordering 안정 |
| DET-007 | P1 | parallel execution | race로 결과 변동 없음 |

## 19. Dataset Regression

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| GEO-001 | P1 | rich STT ingestion | dialogue evidence 사용 |
| GEO-002 | P0 | known instruction echo caption | 정상 caption과 구분 |
| GEO-003 | P0 | instruction echo effect | fixed-window boundary 무영향 |
| GEO-004 | P1 | content generation | dialogue-heavy episode 처리 |
| TRI-001 | P1 | effectively absent STT | 구조적 성공 |
| TRI-002 | P0 | contaminated STT | meaningful dialogue로 오인 금지 |
| TRI-003 | P1 | 외국어 caption 이상 | sanitation state 반영 |
| TRI-004 | P1 | black-screen transition | diagnostic 가능 |
| TRI-005 | P0 | sparse evidence | narrative hallucination 금지 |
| TRI-006 | P0 | 3I7 `"다음 영상에서 만나요."` | 보존 · `SUSPECT` · eligible support로 쓰인 accepted claim 0건 |

## 20. Non-regression / Repository Gate

| ID | Pri | Test | 기대 |
| --- | --: | --- | --- |
| REG-001 | P0 | pre-existing tests | regression 없음 |
| REG-002 | P0 | new v2.1 P0 suite | 전부 PASS |
| REG-003 | P1 | P1 suite | 전부 PASS 또는 명시적 blocker |
| REG-004 | P0 | tree status | clean |
| REG-005 | P0 | BCS core diff | 없음 |
| REG-006 | P0 | official test access | 없음 |
| REG-007 | P0 | M9 execution artifact | 없음 |
| REG-008 | P0 | new human GT artifact | 없음 |
| REG-009 | P0 | provider adoption marker | 없음 |
| REG-010 | P0 | push | NO 유지 |

---

## 21. Acceptance Gate

```
Gate A  Canonical Core          SCH·RAW·SAN·EVT·BPI·FW·CAN  의 P0 전부
Gate B  Grounded Content        LLM·GRD·AAR                 의 P0 전부
Gate C  Presentation Separation HLT·REF·GLS·RPT             의 P0 전부
Gate D  Research Boundary       M9 미실행 · official test 미개방 · BCS core 무변경
                                새 human GT 없음 · 추가 모델 비교 없음
                                change-point 미채택 · C0 tuning 없음
```

**Gate A는 LLM·GPU 없이 도달 가능하다**(Milestone I 전체가 LLM 무의존).

## 22. Final Acceptance Rule

```
Gate A ∧ Gate B ∧ Gate C ∧ Gate D
∧ all P0 PASS
∧ every P1 = PASS 또는 explicitly WAIVED
∧ regression PASS ∧ tree clean
  → IMPLEMENTATION_COMPLETE
```

의미하는 것은 오직 **v2.1 아키텍처가 구현됐고 선언된 소프트웨어 계약이 통과했다**는
것뿐이다. M8 실패 번복 · M9 승인 · official test 승인 · 성능 개선 · change-point 검증 ·
general event detector 성립을 의미하지 않는다.

## 23. Test Suite 구조

```
tests/v2_1/
  test_schema_contract.py      test_grounding_validator.py
  test_raw_persistence.py      test_aar_canonical.py
  test_parse_contract.py       test_highlight_builder.py
  test_sanitation.py           test_global_synthesis.py
  test_evidence_timeline.py    test_report_interlock.py
  test_boundary_provider.py    test_failure_modes.py
  test_fixed_window_v1.py      test_determinism.py
  test_canonical_invariants.py test_research_boundary_guards.py
  test_episode_content_contract.py

tests/fixtures/v2_1/
  synthetic_exact_60s/        synthetic_empty_evidence/
  synthetic_partial_62s/      synthetic_instruction_echo/
  synthetic_no_stt/           synthetic_malformed_payload/
  synthetic_no_caption/       synthetic_ocr_only_claim/
```

## 24. 첫 번째 테스트 묶음

```
FW-001 deterministic rerun     CAN-010 forced overlap rejection
FW-006 exact duration          CAN-011 forced gap rejection
FW-007 partial tail            RAW-002 raw survives parse failure
CAN-001 no overlap             SAN-001 instruction echo detection
CAN-002 no gap                 BPI-005 no silent provider fallback
CAN-003 exactly once
```

이 묶음이 green이 되기 전에 LLM summary나 HWPX 작업부터 시작하지 않는다 —
presentation work가 structural defect를 가린다.

---

# OPEN DEFECTS

결정 이력: `V2_1_DECISION_ADDENDUM_2026-08-30.md`

```
OPEN-1  legacy segment schema 경계        CLOSED  v2.1 전용 namespace + 단일 ingest adapter
OPEN-2  canonical video_end 정의          CLOSED  video_end := last segment.end_sec
OPEN-3  GRD-004 결정 불가능               CLOSED  P1 강등 · GRD-010 P0 신설 (본문 반영)
OPEN-4  DET-002 byte equality 불가능      CLOSED  boundary·episode 구조로 한정 (본문 반영)
OPEN-5  P1 gating 지위                    CLOSED  P0 hard / P1 pass-or-waiver / P2 non-gating
OPEN-6  BCS renderer 재사용 충돌          CLOSED  v2.1 renderer 신규 구현 · BCS 수정·추출 금지
OPEN-7  반복 sanitation                   CLOSED  ≥8 → SUSPECT만 · 삭제 금지
OPEN-8  착수 시점                          CLOSED  DEFER UNTIL FINALIZATION DELIVERABLES COMPLETE
OPEN-9  SUSPECT의 claim 승격 가능 여부      CLOSED  보존≠승격 · FAIL_INELIGIBLE_SUPPORT 신설
```

## OPEN-9 — CLOSED

```
VALID     preserved · usable_for_claims true
SUSPECT   preserved · usable_for_claims false     ← 삭제 아님 · claim 근거 아님
REJECTED  preserved · usable_for_claims false     독립 근거 필요
```

`SUSPECT`만으로 지지되는 claim은 `FAIL_INELIGIBLE_SUPPORT`.
`VALID + SUSPECT` 동시 인용은 **VALID만으로 성립할 때만** PASS.
반영 test: SAN-011 · GRD-011 · GRD-012 · TRI-006. 상세는 ADDENDUM OPEN-9.

## OPEN-8 — CLOSED

```
v2.1 implementation start = DEFERRED
A-01 착수 조건   보고서 본문·보충 절 확정 · 발표 자료 확정
                추가 코드 근거 불필요 확인 · 별도 implementation authorization
그 전까지        source implementation NO · Gate A execution NO
                ticket 수정은 문서 결함 수정만 · 새 실험/튜닝/GT NO
```

우선순위 강등이 아니라 sequencing 결정이다. 상세는 ADDENDUM OPEN-8.

```
v2.1 architecture specification   FROZEN
v2.1 implementation plan          DOCUMENTED
v2.1 acceptance/test matrix       DOCUMENTED
v2.1 Gate A ticket breakdown      READY
v2.1 implementation               DEFERRED
implementation authorization      NOT GRANTED
NEXT PRIORITY                     FINAL REPORT / PRESENTATION FINALIZATION
```
