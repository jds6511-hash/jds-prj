# v2.1 Gate A — 구현 티켓 분해 (2026-08-30)

```
대상    Gate A = SCH · RAW · SAN · EVT · BPI · FW · CAN 의 P0 전부
성격    작업 분해 문서
승인    implementation authorization GRANTED 2026-08-30
        (V2_1_IMPLEMENTATION_AUTHORIZATION_2026-08-30.md)
```

```
LLM 불필요 · GPU 불필요 · 서버 예약 불필요 — Gate A 전체가 로컬에서 돈다
```

각 티켓 = **커밋 1개**. TDD(실패 테스트 먼저) · 커밋 전 전체 테스트 통과.
티켓은 자기가 green으로 만드는 test id를 명시한다.

---

## 의존 순서

```
A-01 ─┬─ A-03 ─┬─ A-04 ─┬─ A-05 ─── A-06 ─┐
      │        │        │                  ├─ A-09 ─── A-11
      └─ A-02 ─┘        └─ A-10 ───────────┤
                                 A-07 ─ A-08 ┘
```

`A-10`(합성 fixture)은 A-04 이후 아무 때나 가능하고 A-08·A-09가 그것을 소비한다.

---

## A-01 canonical segment schema + ingest adapter  **COMPLETE — 7f5d0f9**

```
green    SCH-001 · SCH-002 · SCH-003     전부 PASS
크기     S
근거     ADDENDUM OPEN-1
산출물   src/v2_1_segments.py · tests/test_v2_1_segments.py (16 tests)
```

```
outputs/v2_1/<video_id>/ 아래에만 쓴다. work/<video_id>/를 수정하지 않는다.
adapter 1곳에서만 legacy→canonical 변환:
  segment_id := idx · start_sec := start · end_sec := end · duration_sec := end - start
adapter 밖에서 idx/start/end를 소비하면 contract violation
```

추가 테스트: adapter 왕복 · adapter 외부에서 legacy 필드 미사용(소스 스캔).

---

## A-02 run layout + manifest

```
green    (Gate A 직접 없음 · RPT-008 · RAW-006의 선행)
크기     S
```

```
manifest.json   video id · run id · analysis_mode · config hash · code git head
디렉터리        media / raw / evidence / structure / canonical / presentation / rendered
```

`analysis_mode`를 여기서 기록한다 — 렌더 인터록(RPT-008)이 이것을 읽는다.

---

## A-03 raw artifact store — raw-before-parse  **COMPLETE**

```
green    RAW-001 · RAW-002 · RAW-003 · RAW-004     전부 PASS
         RAW-005 · RAW-006 (P1) 도 함께 PASS
크기     M
산출물   src/v2_1_raw_store.py · tests/test_v2_1_raw_store.py (21 tests)
경계     run id·저장 위치는 호출자가 준다 — run layout은 A-02에 남겼다
         (소스 스캔 테스트가 A-02 책임 침범을 막는다)
```

```
저장 순서   invocation → raw atomic write → parse → parsed artifact → validate
추적       video id · segment id · modality · producer · producer version
           raw payload · run id
```

**소스 순서 테스트**를 포함한다(기존 `test_m8_hier`·`test_bcs`의 패턴 재사용:
`save(` 가 `parse` 보다 앞에 있는지 소스에서 확인). 2026-08-29 사고 2건 대응.

---

## A-04 parse contract layer  **COMPLETE**

```
green    SCH-004 · SCH-005 · SCH-007 · SCH-008 · SCH-009     전부 PASS
크기     M
산출물   src/v2_1_parse.py · tests/test_v2_1_parse.py (46 tests)
```

```
RAW → NORMALIZE → PARSE → RESOLVE → (SEMANTIC VALIDATION은 A-05 이후)
정규화   55 · "55" · "seg#55"  → 동일 canonical segment reference
금지     parse 단계에서 sanitation 판단
금지     구조 fallback — 깨진 JSON을 문장으로 건져 올리지 않는다
```

이 프로젝트 최악 사고 셋이 전부 표기를 계약으로 착각한 것이다
(v2 canary 맨 배열 · BCS `"seg#55"` · 깨진 JSON 폴백).

### parse 계층 status — 넷으로 고정

```
MODEL_FAILURE            producer 호출 자체가 실패했다
PARSE_CONTRACT_FAILURE   raw는 있지만 약속된 구조로 해석되지 않는다
EMPTY                    parse는 됐지만 semantic payload가 비어 있다
VALID_PARSE              형식적으로 정상 — 내용의 진위·오염은 아직 판단하지 않는다
```

SPEC §12의 taxonomy와의 관계를 명시한다. **SPEC은 FROZEN이므로 고치지 않는다.**

```
SPEC §12                        A-04
MODEL_OUTPUT_MISSING       ⊂    MODEL_FAILURE      (호출 실패까지 포함하는 상위 이름)
PARSE_CONTRACT_FAILURE     =    PARSE_CONTRACT_FAILURE
SEMANTIC_VALIDATION_FAILURE     A-05 소관 — parse 계층이 내지 않는다
GROUNDING_FAILURE               Gate B 소관 — parse 계층이 내지 않는다
(신설)                          EMPTY · VALID_PARSE   SCH-005가 요구하는 구분
```

`MODEL_FAILURE`는 **호출자가 알려줄 때만** 생긴다. parse 계층이 payload 내용을 보고
추론하지 않는다 — 빈 문자열은 `EMPTY`이지 호출 실패가 아니다.

A-03과 어휘를 잇는다.

```
RawStore PARSE_OK       → VALID_PARSE
RawStore PARSE_FAILED   → PARSE_CONTRACT_FAILURE
```

### reference 정규화는 존재를 만들지 않는다

```
표현 정규화   55 · "55" · " seg#55 " · "SEG # 55"   → 55
resolve      canonical segment registry(A-01)에 실재해야 한다
"seg#999999"  문법은 맞지만 실재하지 않는다 → PARSE_CONTRACT_FAILURE
              reason = unresolved_reference
금지         clamp · 최근접 매칭 · 없는 segment 생성
```

문법 통과를 parse 성공으로 흘려보내지 않는다. 표기를 받아들이는 것과 존재를
지어내는 것은 다르다.

---

## A-05 sanitation + claim eligibility

```
green    SAN-001 · SAN-002 · SAN-005 · SAN-007 · SAN-010 · SAN-011
크기     L
근거     ADDENDUM OPEN-7 · OPEN-9
```

```
상태            preserved   usable_for_claims
VALID              true          true
SUSPECT            true          false
REJECTED           true          false
EMPTY               -            false
PARSE_FAILED        -            false
```

```
반복 판정   영상 전체 exact normalized full text 출현 ≥ 8 → SUSPECT (삭제 아님)
           normalization은 whitespace·line-ending만. 유사도 매칭 금지
독립 근거   instruction echo · boilerplate · subtitle-credit · URL/방송국 · malformed
           → REJECTED (반복 횟수는 독립 근거가 아니다)
STT        is_corrupted_caption의 반복 규칙을 쓰지 않는다 — 실제 발화를 지운다
OCR        기본 UNKNOWN · usable_for_claims false
```

회귀 fixture: `"나 잡았어!!! 나 잡았어!!!"` 보존 · `"다음 영상에서 만나요."` SUSPECT.

---

## A-06 evidence timeline

```
green    EVT-001 · EVT-002 · EVT-003 · EVT-004 · EVT-007
크기     M
```

```
segment_id · start_sec · end_sec · asr_refs[] · caption_refs[] · ocr_refs[] · status
텍스트를 복제하지 않는다 — 참조로 간다
모든 ref는 실재 artifact로 resolve된다
segment 밖 timestamp 금지 · missing evidence ≠ parse failure
usable_for_claims를 downstream이 읽을 수 있게 보존
```

---

## A-07 BoundaryProvider interface + registry

```
green    BPI-001 · BPI-002 · BPI-003 · BPI-004 · BPI-005
크기     S
```

```python
BoundaryProvider(segments, caption_embeddings=None,
                 boundary_signal=None, config=None) -> boundary result
```

```
기록     provider_name · provider_version · provider_config · boundary_positions
default  fixed_window_v1 (명시적)
금지     provider 실패 시 다른 provider로 자동 fallback
명명     caption_embeddings — visual embedding으로 부르지 않는다 (소스 스캔 테스트)
```

---

## A-08 fixed_window_v1

```
green    FW-001 ~ FW-009
크기     M
의존     A-07 · A-10
```

```
동일 입력·config → 동일 partition
모델·caption·ASR·OCR 변경이 boundary에 영향 없음
마지막 segment만 5초보다 짧을 수 있다
영상 < 5초 → 단일 short segment로 전체 coverage
zero duration → 명시적 FAIL
```

---

## A-09 canonical partition validator

```
green    CAN-001 ~ CAN-013
크기     M
의존     A-08 · A-10
근거     ADDENDUM OPEN-2
```

```
canonical_video_start := first_segment.start_sec
canonical_video_end   := last_segment.end_sec
coverage domain       := [start, end)
```

주입 fixture 4종이 **반드시 FAIL**해야 한다: overlap · gap · duplicate segment ·
unassigned segment. hard gate이므로 실패 시 canonical artifact 생성을 중단한다.

---

## A-10 합성 fixture

```
green    A-05 · A-08 · A-09의 입력을 제공
크기     M
```

```
S1 exact 60s (12×5s)          S5 all modalities empty
S2 partial tail 62s (12×5s+2s) S6 instruction echo caption
S3 no STT (caption only)       S7 malformed parser payload
S4 no caption (ASR only)       S8 OCR-only assertion
+  corrupted partition 4종 (overlap · gap · duplicate · unassigned)
```

실제 영상 fixture(geoje · 3I7)는 **파생 artifact만** 쓴다. `work/`를 건드리지 않는다.

---

## A-11 research boundary guards

```
green    REG-005 · REG-006 · REG-007 · REG-008 · REG-009 (소스·트리 스캔)
크기     S
```

```
BCS protected paths 무변경         src/bcs*.py · scripts/bcs_*.py
official test 접근 흔적 없음
M9 실행 artifact 없음
새 human GT artifact 없음
change-point adoption marker 없음
wonyi_gyeongju 파이프라인 대조 artifact 없음   (REF-003)
```

기존 `test_m8_hier`·`test_bcs`의 소스 스캔 테스트와 같은 방식으로 구현한다.

---

## 첫 묶음 — 이것이 green이 되기 전에는 LLM·HWPX 작업을 시작하지 않는다

```
A-01 → A-03 → A-04 → A-10 → A-07 → A-08 → A-09
```

이 경로가 matrix §24의 최초 테스트 묶음을 전부 덮는다.

```
FW-001 · FW-006 · FW-007
CAN-001 · CAN-002 · CAN-003 · CAN-010 · CAN-011
RAW-002 · SAN-001 · BPI-005
```

(`SAN-001`은 A-05가 필요하므로 첫 묶음에 넣으려면 A-05를 A-10 앞으로 당긴다.)

---

## Gate A 완료 조건

```
위 11개 티켓의 P0 test 전부 PASS
기존 regression 무회귀 (현재 2,521 passed / 1 skipped)
tree clean
LLM·GPU 미사용
```

Gate A 통과는 **canonical core가 섰다**는 뜻일 뿐이다. Gate B(내용·근거) ·
Gate C(표현 분리) · Gate D(연구 경계)는 별개이며, `IMPLEMENTATION_COMPLETE`는
넷을 모두 통과해야 한다.

---

## 착수 승인 경계

```
v2.1 architecture specification   FROZEN
v2.1 implementation plan          DOCUMENTED
v2.1 acceptance/test matrix       DOCUMENTED
v2.1 decision addendum            DOCUMENTED (OPEN-1·2·5·6·7·9 CLOSED)
v2.1 Gate A ticket breakdown      DOCUMENTED  ← 이 문서
v2.1 implementation               IN PROGRESS
implementation authorization      GRANTED 2026-08-30
A-01                              COMPLETE   commit 7f5d0f9
A-03 · A-04                       COMPLETE
NEXT                              A-10  합성 fixture → A-07 → A-08 → A-09
```

착수 승인은 이 문서가 아니라 `V2_1_IMPLEMENTATION_AUTHORIZATION_2026-08-30.md`에
기록된 2026-08-30 사용자 승인 사건이다. 이 문서는 작업 분해로 남는다.
