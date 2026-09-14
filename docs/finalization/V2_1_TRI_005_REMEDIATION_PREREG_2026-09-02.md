# TRI-005 remediation 사전등록 — sparse-evidence deterministic summary (2026-09-02)

```
TRI-005          P0 · OPEN · IMPLEMENTATION_GAP · DECISION C
이 문서          사전등록. 구현 없음 · production 변경 0
선행 문서        V2_1_TRI_005_REMEDIATION_TICKET_2026-09-02.md (상태·counterexample 고정)
```

```
PRIMARY       C3   sparse 조건에서 abstractive summary에 정본 권한을 주지 않는다
SUPPLEMENTAL  C1   프롬프트 제약 — non-gating · v1에서는 적용하지 않는다(§7)
EXCLUDED      C2   semantic entailment verifier — 이번 scope 아님(§8)
```

**구현 승인은 아직 없다.** 이 문서가 고정하는 것은 sparse의 정의 · 판정 주체 ·
실패 시 동작 · 회귀 케이스 · mutation · closure 조건이다.

---

## 1. 설계 전에 실측한 것

추론이 아니라 코드에서 확인했다. 아래가 설계의 전제다.

```
binding.evidence   구간 안 근거 전량이 이미 바인딩에 있다 (v2_1_binding.EvidenceBinding)
                   ref_id · segment_id · source_type · sanitation_status · usable_for_claims
근거 자격           VALID + (asr | vlm) → usable_for_claims=True
                   OCR은 VALID이어도 False (SAN-007) · SUSPECT · REJECTED · EMPTY도 False
근거 원문           store.load(source_type, segment_id).read_text()
                   grounding._cited_text가 쓰는 것과 같은 경로다
정본 스키마         _EPISODE_KEYS는 **필수 키 검사**다 — 추가 키는 거부되지 않는다
                   (거부되는 것은 _PRESENTATION_KEYS뿐)
조립 지점           validate_grounding 호출부는 저장소 전체에서 tests/v2_1_gate_b.py 한 곳
```

가장 중요한 실측은 프롬프트 계약의 경계다.

```
v2_1_prompt.split_evidence        usable_for_claims로 claim / context를 가른다
v2_1_prompt.build_episode_prompt  claim이 비면 PromptError
                                  "no usable evidence ... refusing to ask for a summary"
```

즉 **eligible 0건은 이미 production 경로에서 막혀 있다.** 모델에게 묻지 않으므로
summary가 생길 수 없다(ERR-009가 잰 계약이 이것이다). 따라서 프롬프트가 허용하는
가장 희소한 상태는 **eligible 1건**이고, 그것이 TRI-005 counterexample의 상태다.

```
eligible 0    프롬프트 거부              이미 닫혀 있다 (ERR-009)
eligible 1    프롬프트 생성 · 요약 무제약   ← TRI-005 구멍
eligible 2+   프롬프트 생성 · 요약 무제약   GRD-004 P1 waiver 영역
```

counterexample fixture의 실측 상태도 확인했다.

```
S4 + SPARSE_ASR    fixture는 caption·OCR이 아예 없다(ASR 단독 시나리오)
EP02 evidence      1건 — asr:000009 · VALID · usable=True
grounding          PASS
canonical summary  발명된 서사가 그대로 남는다
```

부수 관측 하나를 기록한다 — **production 구멍으로 읽지 마라.**

```
S8(OCR only) EP02   evidence 0건인데 harness에서는 summary가 남는다
사유                harness가 payload를 직접 주입해 프롬프트 단계를 우회한다
production          같은 상태면 build_episode_prompt가 PromptError로 거부한다
```

---

## 2. SPARSE_V1 — 정의

```
SPARSE_V1(episode) :=
    len([e for e in binding.evidence if e.usable_for_claims]) == 1
    and content_status == "VALID_PARSE"
    and summary is not None
```

이 정의를 고른 이유는 실패 테스트에 맞춘 최소치가 아니라 **프롬프트 계약이 허용하는
경계값**이기 때문이다(§1). 0은 이미 닫혀 있고, 1이 열려 있는 첫 상태다.

```
새 임계값 없음   건수 규칙 하나 · threshold·비율·smoothing 없음
새 튜닝 없음     dev 실측으로 정하는 자유 변수가 아니다
판정 주체        결정적 규칙. 모델 호출 0
채널            asr · vlm 중 자격 있는 것. OCR은 자격이 없으므로 세지 않는다(SAN-007)
```

sparse로 남는 경우를 명시한다.

```
VALID 1 + SUSPECT 5   SPARSE다      SUSPECT는 보존되지만 claim support가 아니다(OPEN-9)
VALID 1 + OCR 3       SPARSE다      OCR 단독 승격 금지(SAN-007)
VALID 2               SPARSE 아님    v1 범위 밖 — GRD-004 영역
```

`eligible <= 1`로 넓히지 않는다. 0은 다른 계약(ERR-009)이고, 여기서 겹쳐 잡으면
"sparse ≠ absent"를 깨뜨린다.

---

## 3. C3 계약 — 의미 판정을 하지 않는다

핵심은 **모델 요약이 근거를 넘었는지 판정하지 않는 것**이다. 판정하면 C2가 되고
모델 의존이 하나 더 생긴다. 대신 sparse 조건에서는 정본 권한 자체를 주지 않는다.

```
SPARSE_V1 ?
 ├─ NO  → 기존 경로. 모델 요약이 정본 summary다
 └─ YES → 정본 summary := 자격 있는 근거 원문의 결정적 보존
```

```
accepted_summary = SUMMARY_SEPARATOR.join(
    store.load(e.source_type, e.segment_id).read_text().strip()
    for e in sorted(eligible, key=lambda e: (e.segment_id, e.source_type))
)
```

정렬 키는 `split_evidence`와 같다. v1에서 eligible은 정확히 1건이므로 실제로는
치환이지만, 규칙은 결합 형태로 고정해 둔다(향후 확장 시 접속어를 넣지 않기 위해).

```
넣지 않는다   그리고 · 그 후 · 따라서 · 결국 · 이후 · 때문에 · 이를 통해
넣지 않는다   요약·압축·재서술 — 새 rule-based 요약기를 만들지 않는다
넣는다       원문 그대로 · 공백 strip만
```

C-05의 표현 계층 원칙과 같다 — **composition은 허용하고 synthesis는 하지 않는다.**

counterexample에 적용한 결과.

```
evidence            "남성이 문을 연다."

raw model output    "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."
accepted summary    "남성이 문을 연다."

raw model output    "남성이 문 3개를 연다."
accepted summary    "남성이 문을 연다."

raw model output    "남성이 문을 연다."
accepted summary    "남성이 문을 연다."      ← 과잉 격리 없음
```

raw 모델 출력은 **지우지 않는다.** raw store에 이미 raw-before-parse로 남아 있고,
그 기록을 건드리지 않는다. 바뀌는 것은 정본 권한뿐이다.

`dialogue_note`는 이 계약이 다루지 않는다. dialogue는 이미 근거 자격으로 게이트되고
있고(FAIL_NO_SUPPORT · FAIL_UNSUPPORTED · FAIL_INELIGIBLE_SUPPORT), 그 판정을
바꾸지 않는다.

---

## 4. 상태 표기 — summary_mode

정본에서 "이 문장이 모델 생성인가, 근거 투영인가"를 사후에 가릴 수 있어야 한다.

```
summary_mode = MODEL_ABSTRACTIVE              기존 경로
             | SPARSE_EVIDENCE_DETERMINISTIC   C3가 정본을 세운 경우
```

```
위치     canonical episode의 새 필드 (정본이 단독으로 유효해야 한다 — AAR-005)
근거     _EPISODE_KEYS는 필수 키 검사이므로 추가는 거부되지 않는다
        _PRESENTATION_KEYS에 해당하지 않으므로 표현 어휘 침입도 아니다
금지     content_status · grounding_status에 새 값을 끼워 넣지 않는다
        (둘은 이미 다른 의미를 가진 닫힌 집합이고, allowlist가 기본 거부다)
v1 범위  정본까지. PresentationEpisode 전파는 v1 scope 밖으로 둔다
```

---

## 5. 실패·경계 동작

```
eligible 0    기존 ERR-009 경로 — 프롬프트 거부 · summary None · 표현에서 NO_RELIABLE_CONTENT
              변경 없음
eligible 1    SPARSE_V1 safe mode — §3의 결정적 요약 · grounding 판정은 그대로
eligible 2+   변경 없음 — TRI-005 v1은 일반 semantic entailment를 해결하지 않는다
```

```
content_status != VALID_PARSE   변경 없음 (실패는 상태로 남고 내용은 비어 있다 — B-04)
grounding FAIL                  변경 없음 — dialogue만 제거되고 summary·구조는 남는다
canonical 구조                   변경 없음 — episode_id · span · 시간 · 순서 · 개수 불변
```

**sparse를 이유로 summary를 None으로 떨어뜨리지 않는다.** 유효 근거 1건이 있는
상태에서 그렇게 하면 가진 정보를 버리는 과잉 격리이고, mutation 4가 그것을 잡는다.

---

## 6. GRD-004와의 정합

우선순위 불일치를 이렇게 해소한다 — waiver를 뒤집지 않고, 과장도 하지 않는다.

```
GRD-004 (P1 · WAIVED)   모든 summary/claim에 대한 자동 semantic entailment 검증 능력
                        → 없다. waiver 유지 · 취소하지 않는다

TRI-005 (P0)            위험도가 명백히 높은 좁은 구조적 상태에서
                        미검증 abstractive generator에게 summary 권한을 주지 않는다
                        → 결정적 방어책으로 닫는다
```

즉 TRI-005는 entailment verifier를 구현하는 것이 아니라 **generator에게 권한을 주지
않는 것**으로 닫는다. 두 항목은 서로를 부정하지 않는다.

---

## 7. C1 — 보조 · v1에서는 적용하지 않는다

프롬프트에 다음과 같은 제약을 넣는 안이다.

```
근거에 없는 행동 · 결과 · 수량 · 인물 · 장소 · 시간적 후속 사건을 추가하지 않는다.
```

```
가치      실패 빈도를 줄일 수는 있다
불가      acceptance evidence가 될 수 없다 — "프롬프트에 그렇게 쓰여 있다"는 증거가 아니다
         지금의 counterexample이 이미 프롬프트 제약이 보장이 아니라는 증거다
실측 비용  CONTRACT 변경 → contract_hash 변경 → PROMPT_VERSION 승격이 정직한 처리다
         현재 계약은 "episode_content_v2"로 테스트에 고정돼 있고, 기록된 산출물의
         prompt_version provenance와의 비교 가능성이 끊긴다
```

그래서 **v1에서는 적용하지 않고 별도 항목으로 남긴다.** 적용은 PROMPT_VERSION 승격을
포함한 별도 승인 사건이다. C3의 결정적 방어는 C1 유무와 무관하게 성립해야 하고,
mutation에서 C1을 제거해도 TRI-005 safety가 유지되는 것이 정상이다.

---

## 8. C2 — 이번 scope에서 제외

```
C2   summary → entailment verifier → evidence 대조 → 실패 시 표현 자격 차단
```

제외 사유.

```
모델 의존이 하나 더 생긴다      generator hallucination을 verifier 판단으로 막는 구조
GRD-004 waiver가 거부한 경로   "규칙으로 흉내내면 오탐이 근거를 지우고 미탐이 통과를 남발한다"
새로 정의해야 하는 계약         verifier failure semantics · prompt injection containment
                            false positive/negative 정책 · 결정성 · 모델 부재 시 동작
                            raw-before-verify · 표현 자격 연동
```

TRI-005 하나를 닫으려고 Gate B급 계약을 하나 더 만드는 셈이다. 별도 연구·architecture
티켓으로 남긴다.

---

## 9. 회귀 케이스 — 사전 고정

`tests/test_v2_1_tri_005_gap.py`에 이미 있는 두 strict xfail을 포함해 7건을 고정한다.

```
T1  서사 발명        evidence "남성이 문을 연다."
                   model    "…건물에 들어가 물건을 훔친 뒤 달아난다."
                   → 발명된 문자열이 accepted summary에 0

T2  수량 발명        model "남성이 문 3개를 연다."
                   → "3개"가 accepted summary에 0

T3  정상 sparse      model = evidence
                   → 과잉 격리 없이 해당 사실 유지 (accepted summary == evidence 원문)

T4  VALID + SUSPECT  deterministic summary에 VALID만 · SUSPECT는 보존되지만 제외

T5  eligible 0       ERR-009 semantics 불변 — 프롬프트 거부 · summary None

T6  canonical 불변    safe mode 전후 episode_id · span · 시간 · 순서 · 개수 동일

T7  재실행 결정성      같은 근거 → 같은 sparse summary (N≥3 · 시간 구조 projection 동시 확인)
```

```
T1 · T2   현재 xfail(strict=True) → remediation 시 XPASS로 실패 → marker 제거 필수
          XPASS로 남기는 것은 closure가 아니다
```

## 10. mutation — 가드 유효성 확인

각 mutation은 사본에서 주입하고 RED를 확인한 뒤 되돌린다.

```
M1  sparse인데 모델 요약을 그대로 정본에 쓴다              RED
M2  수량 발명만 통과시킨다(서사만 막는다)                  RED
M3  SUSPECT를 deterministic summary에 포함한다            RED
M4  sparse면 summary를 무조건 None으로 떨어뜨린다          RED   ← 과잉 격리 방지
M5  근거 정렬을 비결정적으로 바꾼다                        RED
M6  safe mode가 episode span·id·순서를 바꾼다             RED
M7  raw 모델 출력을 지운다                               RED   ← raw 보존 유지
```

M4가 특히 중요하다. 안전을 이유로 유효 정보까지 버리는 해결은 이 계약의 답이 아니다.

---

## 11. 예상 변경 범위

```
신규   src/v2_1_sparse_summary.py         SPARSE_V1 판정 + 결정적 요약 (모델 호출 0)
      tests/test_v2_1_sparse_summary.py  T1~T7

수정   src/v2_1_aar.py                    summary_mode 필드 기록
                                        (필수 키 집합 확장 여부는 구현 시 판단)
      tests/v2_1_gate_b.py               grounding 뒤에 safe-mode 단계 삽입
      tests/test_v2_1_tri_005_gap.py     xfail marker 제거
      docs/finalization/ 집계·감사 문서    반영

변경 없음   grounding 판정 · binding 사실 기록 · 프롬프트 계약 · 표현 계층
          검색 파이프라인 · BCS core · config.yaml
```

blast radius 실측: sparse 상태를 만드는 기존 테스트는 `test_v2_1_tri_005_gap.py`
하나뿐이다(다른 fixture는 구간당 자격 근거 6건). 그래도 판정은 **전체 suite 실행**으로
한다 — 이 예상치를 근거로 쓰지 않는다.

---

## 12. closure 조건

```
T1 서사 counterexample      PASS
T2 수량 counterexample      PASS
T3 정상 sparse 내용 보존     PASS
T4 SUSPECT 제외             PASS
T5 eligible 0 · ERR-009 회귀 PASS
T6 canonical invariants     PASS
T7 결정성                   PASS
M1~M7 mutation              전부 RED 확인
남은 strict xfail            0
전체 suite                  green (skip 분류 포함)
```

closure 문구.

```
TRI-005 CLOSED — sparse-evidence episodes use a deterministic evidence-preserving
summary path, preventing unsupported narrative continuation in the registered
sparse regime. This does not establish general semantic entailment verification
and does not revoke the GRD-004 waiver.
```

## 13. 이 사전등록이 주장하지 않는 것

```
모든 summary가 evidence-entailment 검증을 받는다   아니다. eligible 2+는 그대로다
GRD-004가 해소된다                             아니다. P1 waiver 유지
프롬프트 제약이 보장이다                          아니다. C1은 v1에서 적용조차 하지 않는다
sparse 정의가 실측으로 튜닝된 값이다                아니다. 프롬프트 계약의 경계값이다
보고서 문장 품질이 좋아진다                        sparse 구간의 문장은 기계적으로 변한다
```

## 14. 승인이 필요한 것

```
1  C3 primary · C1 v1 미적용 · C2 제외                    이 문서의 설계
2  SPARSE_V1 = eligible == 1                            sparse 정의
3  canonical에 summary_mode 필드 추가                     정본 스키마 가산 변경
4  sparse 구간의 정본 summary가 모델 문장이 아니게 되는 것    production 동작 변경
```

승인 후 순서.

```
구현 → T1~T7 GREEN → M1~M7 RED 확인 → xfail marker 제거
→ §19(GEO 4 + TRI 6) 한 번에 final tally 편입 → 미매핑 0
→ 최종 HEAD 기준 전체 재집계 (skip 1건 분류 · tree clean · HEAD == origin/master 재확인)
```

집계 시 분류할 skip 1건은 이미 특정돼 있다.

```
tests/test_publication_safety.py::test_publishable_sources_are_actually_tracked
사유   대상 파일이 이 작업 트리에 없을 때만 skip · v2.1 acceptance 매핑 테스트 아님
```
