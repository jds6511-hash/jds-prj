# v2.1 IMPLEMENTATION PLAN (2026-08-30)

```
Status                          IMPLEMENTATION PLAN
Architecture baseline           v2.1 specification FROZEN
Implementation status           NOT STARTED
Canonical boundary default      fixed_window_v1
Caption-text change-point       NOT ADOPTED
M9 / official test              HOLD / CLOSED
```

규격: `V2_1_ARCHITECTURE_SPEC_2026-08-30.md` · 관찰: `C0_BOUNDARY_SIGNAL_OBSERVATION_2026-08-30.md`
수용 기준: `V2_1_ACCEPTANCE_MATRIX_2026-08-30.md`

---

## 1. 목적

자유형 LLM boundary selection을 canonical path에서 제거하고, 영상 전체를 결정론적
canonical temporal partition으로 정확히 한 번 덮은 뒤, 각 구간에 검증 가능한 근거
기반 요약을 생성하고, 사람이 읽는 보고서 구조는 별도 presentation layer에서 만든다.

```
1  canonical temporal structure와 report presentation structure를 분리한다
2  canonical partition은 결정론적이어야 한다
3  상류 ASR/VLM/OCR 오염이 검증 없이 downstream claim으로 승격되지 않는다
4  LLM 출력 책임을 최소화한다
5  provenance·support는 가능한 한 코드에서 파생한다
6  structural failure를 presentation fallback으로 숨기지 않는다
7  raw artifact는 parse/sanitation 이전에 저장한다
8  preview와 final report가 동일 canonical artifact를 소비하도록 interlock한다
9  공식 test · M9 · BCS core · 새 human GT에 손대지 않는다
```

---

## 2. 범위

### 2.1 In Scope

```
Video → Canonical 5s Segments → ASR/VLM/OCR raw → Parse Contract → Sanitation
→ Evidence Timeline → Boundary Signal → BoundaryProvider → Canonical Episodes
→ Episode Content LLM → Grounding Validator → aar_canonical.json
→ Presentation Highlight Builder → Global Synthesis → Preview / MD / HWPX
```

### 2.2 Out of Scope — 명시적 제외

```
M9 실행 · official test 개방 · 기존 M8 acceptance 재평가
BCS v0 core 수정 · 새 human event GT 작성
wonyi_gyeongju 보고서를 GT처럼 사용
추가 LLM 모델 비교 · Qwen/Kanana boundary 재실험
C0 threshold / smoothing / min-gap tuning
caption change-point provider 자동 채택
visual embedding 기반 boundary provider 구현
global synthesis entailment의 완전 자동 검증 주장
canonical episode overlap·gap 허용
presentation highlight를 canonical partition으로 역승격
```

---

## 3. 우선순위 — 고정

```
P0  Schemas / Parse Contract        P7   Episode content generation
P1  Raw artifact persistence        P8   Grounding validator
P2  Sanitation                      P9   aar_canonical.json
P3  Evidence Timeline               P10  Presentation Highlight Builder
P4  BoundaryProvider interface      P11  Global Synthesis
P5  fixed_window_v1                 P12  Preview / MD / HWPX interlock
P6  Canonical partition validator   P13  End-to-end regression
```

**후속 단계가 선행 단계의 contract를 암묵적으로 재정의하지 않는다.**

---

## 4. Phase 0 — Contract·Schema 고정

```
segment · raw_asr · raw_caption · raw_ocr
sanitized_asr · sanitized_caption · sanitized_ocr
evidence_timeline · boundary_signal · canonical_episode
episode_content · grounding_result · aar_canonical
presentation_highlight · global_synthesis
```

### Segment

```
segment_id · start_sec · end_sec · duration_sec
```

5초 canonical segment가 기본이며 **마지막 segment만** 영상 길이에 따라 5초보다
짧을 수 있다.

v2.1 artifact는 `outputs/v2_1/<video_id>/`에 저장한다. legacy `work/<video_id>/`를
수정하지도 저장 위치로 쓰지도 않는다. legacy↔canonical 변환은 **ingest boundary의
단일 adapter에서만** 한다 (ADDENDUM OPEN-1).

```
segment_id := idx · start_sec := start · end_sec := end · duration_sec := end - start
```

### Evidence reference

downstream은 원문 중복 저장 대신 참조를 쓴다.

```
evidence_ref: source_type · segment_id · field/path
```

### Canonical Episode

```
필수 구조   episode_id · start_sec · end_sec · segment_ids
내용 결합 후 summary · support_refs
```

모델에게 자유 생성시키지 **않는** 값.

```
start_sec · end_sec · segment_ids · support_span · source provenance · episode_id
```

---

## 5. Phase 1 — Raw Artifact Persistence

```
model/tool invocation → raw output persist → parse → sanitized representation
```

parse 실패에도 raw는 남는다. 추적 항목.

```
video id · segment id · source modality · producer · producer version
raw payload · creation timestamp 또는 run id
```

**금지**: `model output → parse → 성공분만 저장`. 실패 증거를 지우는 구조다.

---

## 6. Phase 2 — Parse Contract

판단하는 것.

```
형식적으로 읽을 수 있는가 · 필수 필드 존재 · 예상 타입 · 텍스트 정상 추출
```

판단하지 **않는** 것.

```
내용이 사실인가 · 영상과 일치하는가 · instruction echo인가 · OCR이 claim에 적합한가
```

parse 실패 시 raw 유지 · 명시적 failure state · **빈 정상 데이터로 위장 금지**.

---

## 7. Phase 3 — Sanitation

대상: instruction echo · boilerplate · 비정상 언어 전환 · empty/near-empty ·
malformed · refusal/meta-response · OCR 노이즈 · 반복 텍스트.

상태.

```
상태            preserved   usable_for_claims
VALID              true          true
SUSPECT            true          false      ← 보존하되 claim 근거 아님
REJECTED           true          false
EMPTY               -            false
PARSE_FAILED        -            false
```

`usable_for_claims`는 **코드가 결정한다** — LLM이 판단·변경하지 않는다.
`Preservation is not permission to claim.` (ADDENDUM OPEN-9)

OCR은 **존재만으로 episode claim의 근거가 되지 않는다.** 부가 context ·
표시 문구 존재 여부 · 다른 modality와 결합된 보조 evidence로만 쓴다.

---

## 8. Phase 4 — Evidence Timeline

```
segment_id · start_sec · end_sec · asr_refs[] · caption_refs[] · ocr_refs[] · status
```

```
모든 ref는 실재 artifact로 resolve된다
segment 밖 timestamp를 만들지 않는다
modality 없음은 빈 배열 허용
missing evidence와 parse failure를 구분한다
```

---

## 9. Phase 5 — BoundaryProvider Interface

```python
BoundaryProvider(segments, caption_embeddings=None,
                 boundary_signal=None, config=None) -> boundary result
```

`caption_embeddings`는 **caption-text embedding**이다. 저장된 `emb_cap.npy`는
KURE-v1 caption-text embedding이며 visual embedding으로 명명·취급하지 않는다.

결과 기록: `provider_name` · `provider_version` · `provider_config` ·
`boundary_positions`.

---

## 10. Phase 6 — fixed_window_v1

canonical default. 동일 입력·config에서 항상 동일 partition.
모델·caption·ASR·OCR 변경이 canonical boundary에 영향을 주지 않는다.

```
overlap = 0 · gap = 0 · coverage = exactly once
```

---

## 11. Phase 7 — change-point scaffold (candidate only)

C0 결과는 `MIXED_SIGNAL`이다. 전제.

```
peak가 실제 transition과 대응하는 경우가 있다
그러나 distribution separation이 충분하지 않다
max/top-K는 caption defect를 강하게 선택한다
caption QC 없이는 안전하지 않다
VLM 변경 시 embedding·boundary가 바뀐다
```

**금지**: threshold / min-gap / smoothing / GT recall optimization ·
human report matching · Qwen/Kanana boundary matching.
scaffold를 구현하더라도 disabled 또는 experimental 상태.

---

## 12. Phase 8 — Canonical Partition Validator (hard gate)

```
1 first episode start == canonical_video_start   6 exactly once assignment
2 last episode end == canonical_video_end        7 strictly monotonic order
3 episode[i].end == episode[i+1].start    8 no negative duration
4 no overlap                              9 no zero-duration episode
5 no gap                                 10 referenced segment exists
```

하나라도 실패하면 canonical artifact 생성을 중단한다. presentation fallback으로
숨기지 않는다.

---

## 13. Phase 9 — Episode Content LLM

모델 필수 출력은 원칙적으로 `summary` 하나. 입력은 해당 episode의 evidence timeline
subset(ASR / caption / OCR 보조로 구분).

코드가 결정하는 것.

```
episode boundaries · episode_id · support span · source attribution
segment membership · canonical ordering
```

모델 실패가 canonical structure failure가 되지 않는다.

---

## 14. Phase 10 — Grounding Validator

검증: reference validity · support coverage · unsupported named entity ·
unsupported concrete action/event · OCR-only claim escalation ·
outside-episode evidence 사용.

```
PASS · PASS_WITH_LIMITATION · FAIL_UNSUPPORTED · FAIL_REFERENCE
FAIL_INELIGIBLE_SUPPORT      ref는 실재하나 claim 근거가 될 수 없다 (OPEN-9)
```

```
eligible_support_refs := refs where usable_for_claims == true
모든 accepted claim은 eligible_support_ref_count >= 1
VALID + SUSPECT 동시 인용을 자동 PASS로 처리하지 않는다 —
VALID만으로 claim이 독립적으로 성립해야 한다
```

presentation layer가 실패한 summary를 고쳐 통과처럼 보이게 하지 않는다.

---

## 15. Phase 11 — aar_canonical.json

```
metadata · video · segments · episodes · validation · provenance
```

episode: `episode_id · start_sec · end_sec · segment_ids · summary ·
support_refs · grounding_status`

**보고서 구조(개요 / 핵심 내용 분석 / 결론)를 canonical structure처럼 저장하지 않는다.**

---

## 16. Phase 12 — Presentation Highlight Builder

여기서만 허용: 여러 episode 병합 · 부분 묶음 · 겹치는 highlight ·
nested highlight · 보고서 목적의 선택적 생략.

```
Canonical Episode ≠ Presentation Highlight
```

사람이 작성한 보고서의 행 수(9 등)를 목표로 삼지 않는다.
overlap은 허용하되 **source lineage는 끊기지 않는다.**

---

## 17. Phase 13 — Global Synthesis

개요 · 핵심 내용 분석 · 결론. episode-local grounding만으로 완전한 entailment를
보장할 수 없으므로 **"자동으로 완전 사실 검증됨"을 주장하지 않는다.**

가능한 검증: referenced episode 존재 · forbidden OCR-only source 사용 여부 ·
비어 있는 canonical artifact 참조 여부.

---

## 18. Phase 14 — Preview / MD / HWPX Interlock

**v2.1 renderer는 신규 코드다.** `src/bcs_present.py` · `scripts/bcs_hwpx.py`를
수정하지 않고, 공용화 목적의 추출 refactor도 하지 않는다 (ADDENDUM OPEN-6).
렌더 로직 중복은 의도된 비용이다.

```
aar_canonical.json → presentation model → preview · MD · HWPX
```

스타일 차이 허용, **semantic source difference 금지.**

---

## 19. Error Policy

```
A structural   partition gap/overlap · invalid reference · schema violation
               → HARD FAIL · fallback 금지
B evidence     summary 생성 실패 · unsupported summary · evidence 부족
               → canonical 구조 유지 · 명시적 status
C presentation highlight 실패 · formatting 실패 · HWPX 문제
               → presentation fallback 허용 · canonical 불변
```

---

## 20. Milestone

```
I   Canonical Core          schemas · raw persistence · parse contract · sanitation
                            evidence timeline · provider interface · fixed_window_v1
                            canonical validator      ← **LLM 없이 전부 테스트 가능**
II  Grounded Content        prompt/input builder · summary · support refs
                            grounding validator · failure state · aar_canonical.json
III Presentation            Highlight Builder · overlapping highlights
                            global synthesis · section mapping · 공통 소스
IV  Regression Hardening    deterministic rerun · malformed upstream
                            instruction-echo · sparse/rich/no STT · short video
                            partial tail · renderer consistency
```

---

## 21. Fixture 전략

```
geoje   풍부한 대화 STT · evidence integration · instruction-echo caption 회귀 · grounding
3I7     sparse/invalid STT · 오염·외국어 caption · 검은 화면 전환 · evidence 희소
```

합성 fixture.

```
S1 exact duration 60s (12×5s)      S5 all modalities empty
S2 partial tail 62s (12×5s + 2s)   S6 instruction echo caption
S3 no STT (caption only)           S7 malformed parser payload
S4 no caption (ASR only)           S8 OCR-only assertion
```

---

## 22. Definition of Done (20)

```
 1 fixed_window_v1 canonical path end-to-end 동작
 2 canonical partition overlap 0 / gap 0 / exactly once
 3 동일 입력·config repeated run에서 canonical boundary 동일
 4 LLM 변경이 canonical partition을 바꾸지 않음
 5 ASR/VLM/OCR raw가 parsing 전에 저장됨
 6 parse failure가 raw 손실로 이어지지 않음
 7 caption contamination이 정상 evidence와 구분됨
 8 OCR-only evidence가 사건 claim으로 자동 승격되지 않음
 9 모델 필수 생성 책임이 summary 수준으로 제한됨
10 provenance·support span이 코드에서 파생됨
11 grounding validation 실패가 숨겨지지 않음
12 aar_canonical.json이 presentation과 독립적으로 유효
13 highlight overlap이 canonical overlap으로 전파되지 않음
14 preview/MD/HWPX가 동일 canonical artifact 사용
15 presentation failure가 canonical structure를 바꾸지 않음
16 change-point provider가 default도 adoption 상태도 아님
17 official test 미실행
18 M9 미시작
19 BCS v0 core 미수정
20 새 human GT 미생성
```

---

## 23. Implementation Freeze Gate

```
all P0 acceptance tests pass · all canonical invariants pass
no unresolved structural failure · no hidden fallback
canonical rerun deterministic · tree clean · 기존 regression 무회귀
```

여기서의 완료는 **v2.1 implementation complete**만 의미한다.

```
M9 승인 · official test 개방 · 성능 개선 입증 · general event detector 성립
```

을 의미하지 않는다.
