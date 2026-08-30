# v2.1 IMPLEMENTATION / ACCEPTANCE DECISION ADDENDUM (2026-08-30)

```
대상   V2_1_IMPLEMENTATION_PLAN_2026-08-30.md · V2_1_ACCEPTANCE_MATRIX_2026-08-30.md
상태   OPEN-1 · 2 · 5 · 6 · 7  CLOSED
       OPEN-3 · 4 는 앞서 본문 반영 완료
       OPEN-9  CLOSED (2026-08-30 · 아래)
       OPEN-8  CLOSED — DEFER UNTIL FINALIZATION DELIVERABLES COMPLETE
```

---

## OPEN-1 — Legacy Segment Schema Boundary  **CLOSED**

v2.1은 기존 `work/<video_id>/` namespace를 수정하지 않고, v2.1 artifact 저장 위치로도
쓰지 않는다.

```
legacy   work/<video_id>/segments.json      idx · start · end
v2.1     outputs/v2_1/<video_id>/           segment_id · start_sec · end_sec · duration_sec
```

변환은 **v2.1 ingest boundary의 단일 adapter에서만** 수행한다.

```
segment_id   := idx
start_sec    := start
end_sec      := end
duration_sec := end - start
```

```
legacy work artifact → v2.1 ingest adapter → canonical v2.1 segment → outputs/v2_1/<video_id>/
```

`common.load_segments`와 `work/<video_id>/segments.json`의 schema를 v2.1 때문에
변경하지 않는다. downstream v2.1 component는 `idx`·`start`·`end`를 직접 소비하지
않는다. **adapter 외부에서 두 schema를 혼용하는 것은 contract violation이다.**

BCS 또는 기존 pipeline의 segment schema migration은 v2.1 범위 밖이다.

---

## OPEN-2 — Canonical `video_end` 정의  **CLOSED — option (a)**

```
canonical_video_start := first_segment.start_sec
canonical_video_end   := last_segment.end_sec
canonical coverage domain := [canonical_video_start, canonical_video_end)
```

CAN-004 · CAN-005는 이 값과의 일치를 검사한다.

`ffprobe` 등 container duration은 provenance/diagnostic으로 보존하되 **canonical
partition invariant의 equality target으로 쓰지 않는다.** 목적은 container duration ·
frame/sample rounding · segment extraction rounding · 마지막 부분 segment 표현
차이로 인한 **비결정적 P0 failure 제거**다.

segment list가 비어 있으면 별도의 invalid-input failure이며 `video_end`를 추론하지
않는다.

### 주의 — 이 검사는 구조 내적이다

episode를 같은 segment 목록에서 만들므로 CAN-005는 거의 항상 참이 된다.
**남는 검출력은 builder 결함**이다 — 마지막 segment 누락, off-by-one, tail 절단.
그것이 이 P0의 실질적 역할이다.

---

## OPEN-5 — P1 Gating Semantics  **CLOSED**

```
P0  hard gate
P1  PASS 또는 명시적으로 문서화된 WAIVER 필요
P2  non-gating diagnostic / quality
```

```
P0 FAIL                         → acceptance FAIL
P1 FAIL + waiver 없음            → acceptance BLOCKED
P1 FAIL + 명시적 waiver          → acceptance 가능 · limitation 기록 필수
P2 FAIL                         → 자동 차단하지 않음
```

### Final Acceptance Rule (개정)

```
Gate A PASS ∧ Gate B PASS ∧ Gate C PASS ∧ Gate D PASS
∧ all P0 PASS
∧ every P1 = PASS 또는 explicitly WAIVED
∧ regression PASS ∧ tree clean
```

waiver 기록 항목.

```
test id · failure description · reason waiver is acceptable · known impact · scope of limitation
```

**P1 test를 skip해서 waiver로 간주하지 않는다.** waiver 대장 위치를 고정한다.

```
docs/finalization/V2_1_P1_WAIVERS.md
```

---

## OPEN-6 — Renderer Isolation from Frozen BCS  **CLOSED**

v2.1 presentation/rendering은 **신규 namespace에서 신규 코드로** 구현한다.

```
수정 금지   src/bcs_present.py · scripts/bcs_hwpx.py
금지        공용화 목적의 함수·모듈 추출 refactor
허용        제3자 library · BCS와 무관하게 존재하는 general-purpose utility
```

```
BCS v0 core            unchanged
v2.1 canonical artifact → new v2.1 renderer code
```

두 경로는 코드 수정 의존성을 만들지 않는다. 향후 공용화가 필요하면 **BCS freeze
해제 이후 별도 변경**으로 다룬다.

REG-005의 의미.

> v2.1 구현으로 인해 frozen BCS protected paths에 변경이 없어야 한다.

비용은 HWPX·Markdown 렌더 로직의 중복이다. 의도된 비용으로 기록한다.

---

## OPEN-7 — Repetition Sanitation Rule  **CLOSED**

**반복 자체는 contamination도 삭제 근거도 아니다.**

```
보존해야 하는 예   "나 잡았어!!! 나 잡았어!!!"
```

```
repetition_candidate := 영상 전체 exact normalized full text 출현 ≥ 8
```

normalization은 **최소한의 결정적 처리만** 한다.

```
허용   leading/trailing whitespace · line-ending 정규화
금지   semantic similarity · embedding similarity · paraphrase matching
```

상태 규칙.

```
repeat ≥ 8   →  SUSPECT          (DELETE / REJECTED 아님)
REJECTED로 승격하려면 독립 근거가 필요하다
             instruction echo · explicit boilerplate pattern · malformed producer output
8회 미만     →  반복만을 이유로 상태를 낮추지 않는다
```

```
SAN-004  video-wide exact normalized repetition ≥ 8   → SUSPECT 후보
SAN-010  자연스러운 강조·대화 반복                      → 보존
```

이 임계는 **boundary tuning parameter가 아니며** caption change-point provider
adoption에도 쓰지 않는다.

---

## OPEN-9 — SUSPECT Evidence Claim Eligibility  **CLOSED**

### 문제

OPEN-7 이후 반복 ≥8은 `SUSPECT`일 뿐 `REJECTED`가 아니다. 그런데 실측에서
**반복이 유일한 contamination signal인 사례가 존재**한다.

```
3I7       "다음 영상에서 만나요."  x20
softyeon  동종 반복 contamination  x22
```

실측 확인 — 다른 결정적 규칙에 하나도 적중하지 않는다.

```
is_subtitle_credit    False    크레딧 패턴은 "한글자막 by …" 완전일치만 잡는다
is_corrupted_caption  False    한자·가나 없음 · 구 반복 없음
URL/방송국 정규식      미적중
```

`SUSPECT`를 정상 claim support로 허용하면 OPEN-7이 보존한 오염이 다시 사건
서술로 승격된다.

### 결정 — 보존 상태와 claim eligibility를 분리한다

```
상태            preserved   usable_for_claims
VALID              true          true
SUSPECT            true          false
REJECTED           true          false
EMPTY               -            false
PARSE_FAILED        -            false
```

```
SUSPECT ≠ deleted
SUSPECT ≠ valid claim support
```

원문은 provenance·진단을 위해 보존하고 UI/debug에 표시할 수 있으나, canonical
episode claim을 지지하는 evidence reference로 쓰지 않는다.

### Grounding semantics

```
eligible_support_refs := refs where usable_for_claims == true
```

```
SUSPECT refs만으로 지지되는 claim    → grounding FAIL
REJECTED refs만으로 지지되는 claim   → grounding FAIL
```

**`VALID + SUSPECT` 동시 인용을 자동 PASS로 처리하지 않는다.**

```
허용    VALID evidence만으로도 그 claim이 독립적으로 성립한다
        → SUSPECT는 auxiliary/contextual reference로 보존 가능 · 성립 근거로 계산하지 않음
금지    SUSPECT ref가 있어야 claim이 참이 되는 경우
        → PASS 불가
```

이 단서가 없으면 SUSPECT를 VALID 옆에 붙여 우회 사용하는 통로가 생긴다.

### 왜 바로 REJECTED로 만들지 않는가

반복은 강한 신호일 수 있으나 항상 오염이 아니다 — 감정적 반복 발화 · 구호 · 후렴 ·
반복 안내 · 동일한 실제 대화가 존재한다.

`REJECTED`에는 **독립적인 결정적 근거**가 필요하다.

```
instruction echo pattern · known producer boilerplate · subtitle-credit pattern
URL/station boilerplate · malformed producer response · 기타 명시된 결정적 오염 규칙
```

**반복 횟수는 독립적인 rejection ground가 아니다.**

### SAN-004 / SAN-010 / OPEN-9 관계

```
SAN-004  영상 전체 exact normalized 출현 ≥8
         → SUSPECT · 텍스트 보존 · usable_for_claims false
SAN-010  자연스러운 강조·대화 반복
         → 반복 자체를 이유로 삭제하지 않음
```

SAN-010은 SAN-004의 claim eligibility 정책을 무효화하지 않는다. 자연 발화라고
판단할 추가 결정적 근거가 없으면 **보존하되 보수적으로 claim support에서 제외**한다.
정보 삭제가 아니라 **claim 승격 차단**이다.

### Evidence Timeline contract

```
evidence_ref · status · usable_for_claims
```

`usable_for_claims`는 downstream LLM이 판단하거나 바꾸는 필드가 아니다. sanitation
결과에서 **코드가 결정한다.** 입력 역할을 분리한다.

```
claim-generation evidence set   usable_for_claims == true 만
diagnostic/context evidence set  SUSPECT 포함 보존 evidence
```

### OCR 정책과 같은 방향

> evidence가 존재하거나 보존된다는 사실은 그것이 canonical factual claim을 단독으로
> 지지할 수 있다는 뜻이 아니다.

evidence lifecycle 3단계를 구분한다.

```
preserved → available for inspection/context → eligible for factual claim support
```

### 추가 invariant

```
모든 accepted grounded claim에 대해   eligible_support_ref_count >= 1
기본 contract                        eligible_support_ref.status == VALID
```

다른 claim-eligible 상태를 도입하려면 **명시적 schema 변경**이 필요하다.

### 신설 failure class

```
FAIL_INELIGIBLE_SUPPORT
```

`FAIL_REFERENCE`를 재사용하지 않는다 — "ref가 없다/깨졌다"와 "ref는 실재하나
정책상 claim 근거가 될 수 없다"는 다른 실패이고, 회귀 원인 추적에서 차이가 크다.

### Architecture status

OPEN-9는 boundary architecture 변경이 아니다. canonical partition ·
`fixed_window_v1` · BoundaryProvider · Highlight 분리 · M9 · official test ·
BCS freeze · provider adoption status를 **바꾸지 않는다.**

sanitation → grounding 사이에 누락돼 있던 **claim eligibility contract를 명문화하는
correction**이며, frozen architecture의 normative contract correction으로 기록한다.

### 한 줄 규칙

> **Preservation is not permission to claim.**

```
SUSPECT evidence is preserved and inspectable,
but it cannot independently support a canonical factual claim.
```

---

## Acceptance Matrix Corrections — 반영 완료

```
GRD-004  unsupported concrete action/event   P1   (semantic entailment/NLI 필요)
GRD-005  unsupported named entity            P0   (deterministic string anchor)
GRD-010  claim without support ref           P0   신설 · FAIL_REFERENCE
DET-002  boundary list · episode temporal structure · segment membership 동일
         (run id·timestamp 때문에 artifact byte equality는 요구하지 않는다)
SCH-008  55 / "55" / "seg#55" → 단일 canonical segment reference 또는 명시적 parse failure
SCH-009  PARSE_CONTRACT_FAILURE는 sanitation/content failure와 독립 class
RPT-008  analysis_mode != report → final report renderer가 렌더 거부
SAN-010  자연스러운 강조·반복 발화 보존 · 반복만으로 evidence 삭제 금지
```

---

## OPEN-8 — Implementation Start Timing  **CLOSED**

```
v2.1 implementation start = DEFERRED
```

### A-01 착수 조건

```
1  최종 보고서 본문·보충 절 확정
2  발표 자료가 필요하다면 발표 자료 확정
3  FINALIZATION deliverable에 추가 코드 근거가 필요하지 않음을 확인
4  별도 implementation authorization 명시
```

### 그 전까지

```
source implementation   NO
Gate A execution        NO
ticket 수정             문서 결함 수정에 한해서만 허용
새 실험 · 튜닝 · GT 생성  NO
```

### 근거

지금 병목은 compute가 아니라 **주의력과 변경 관리**다. Gate A가 LLM/GPU 없이
저비용인 것은 맞지만, v2.1은 이미 spec·plan·matrix·addendum·tickets까지 닫혀 있어
**A-01을 지금 시작해도 최종 보고서의 핵심 결론을 강화하지 않는다.**

반대로 구현을 열면 코드 diff · 새 테스트 결과 · 구현 중 발견되는 contract
correction이 생기고, 그것이 **08-28 baseline을 다시 건드릴 유인**이 된다.

지금 Gate A를 PASS해도 보고서에서 말할 수 있는 것은 "canonical core software
contract가 구현됐다"뿐이다.

```
M8 FAIL        불변
M9             HOLD
provider 채택   없음
성능 개선 입증   없음
```

그런데 finalization 전에 새 코드를 여는 것은 **"어디까지가 연구 결과이고 어디부터가
후속 설계인가"의 경계를 흐린다.**

### 이것은 우선순위 강등이 아니다

sequencing 결정이다. 진입 비용은 이미 충분히 낮췄다 — A-01부터 11개 티켓 · 의존
순서 · P0 gate가 정리돼 있어 finalization 이후에는 **연구 판단을 다시 하지 않고
바로 구현으로 전환**할 수 있다.

---

## Implementation Authorization Boundary

```
v2.1 architecture specification   FROZEN
v2.1 implementation plan          DOCUMENTED
v2.1 acceptance/test matrix       DOCUMENTED
v2.1 implementation               NOT STARTED
implementation authorization      NOT GRANTED
```

Gate A가 LLM/GPU 없이 실행 가능하다는 사실은 **구현 순서상의 장점일 뿐 착수 승인이
아니다.** 별도의 implementation-start decision 전에는 source implementation을
시작하지 않는다.

```
push  NO   ·   M9  HOLD/NO   ·   official test  CLOSED/NO
BCS core modification  NO   ·   caption change-point adopt  NO
new human GT  NO   ·   additional model experiment  NO
```
