# v2.1 IMPLEMENTATION / ACCEPTANCE DECISION ADDENDUM (2026-08-30)

```
대상   V2_1_IMPLEMENTATION_PLAN_2026-08-30.md · V2_1_ACCEPTANCE_MATRIX_2026-08-30.md
상태   OPEN-1 · 2 · 5 · 6 · 7  CLOSED
       OPEN-3 · 4 는 앞서 본문 반영 완료
       OPEN-9 신규 — 결정 필요
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

## OPEN-9 — `SUSPECT`가 claim으로 승격되는가  **결정 필요 (신규)**

OPEN-7을 닫으면서 열린 구멍이다.

BCS에서 3I7의 오염 STT 29건이 제거돼 **서술 전파 0건**이었다. 그 29건의 근거를 다시
보면 두 갈래다.

```
"마포구청 인터넷 방송국 홈페이지"  x9    URL/방송국 패턴  → 독립 근거 있음 → REJECTED 유지
"다음 영상에서 만나요."           x20   독립 근거 없음
```

실측 확인.

```
"다음 영상에서 만나요."
  is_subtitle_credit    False      (크레딧 패턴은 "한글자막 by …" 완전일치만)
  is_corrupted_caption  False      (한자·가나 없음 · 구 반복 없음)
  URL/방송국 정규식      미적중
```

즉 이 문자열의 유일한 신호가 **반복 ≥8**이었다. OPEN-7 이후 이것은 `REJECTED`가
아니라 `SUSPECT`가 된다. softyeon `"다음 영상에서 만나요."` x22도 같다.

**따라서 `SUSPECT`가 claim 근거로 쓰일 수 있으면, 이번에 없앤 아웃트로 자막의
사건 승격이 되돌아온다.**

### 권고

```
SUSPECT  →  usable_for_claims = false
            텍스트는 보존하고 표시도 가능하나 claim 근거로 쓰지 않는다
REJECTED →  독립 근거가 있을 때만. 여전히 텍스트는 삭제하지 않는다
```

이러면 두 요구가 동시에 성립한다.

```
OPEN-7 요구   반복만으로 evidence를 삭제하지 않는다      → 삭제 안 함 (상태만 부여)
BCS 실측 보장  오염 STT가 사건 서술로 승격되지 않는다     → SUSPECT는 claim 불가
```

### 필요한 test

```
SAN-011  P0   repeat ≥ 8 문자열
              → status SUSPECT · usable_for_claims false
              → 텍스트는 artifact에 보존됨
GRD-011  P0   SUSPECT evidence만 인용한 dialogue claim
              → 승격 거부 (FAIL)
TRI-006  P0   3I7 "다음 영상에서 만나요."
              → canonical claim에 등장하지 않음   (BCS 실측 보장 회귀)
```

**미결이다. 승인 전에는 matrix에 반영하지 않았다.**

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
