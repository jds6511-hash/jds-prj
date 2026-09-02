# TRI-005 remediation ticket — sparse evidence narrative hallucination (2026-09-02)

```
TRI-005
severity = P0
status = OPEN
classification = IMPLEMENTATION_GAP
DECISION = C
```

```
A  REJECTED   실패한 P0의 acceptance criterion을 사후에 좁히지 않는다
B  REJECTED   실제 counterexample이 있는 P0를 waiver로 넘기지 않는다
C  SELECTED   implementation gap으로 유지 · 별도 remediation 계약/사전등록 필요
```

**지금 구현하지 않는다.** 이 문서는 상태·목표·회귀 fixture를 고정하고, 판정 방식을
`decision-open`으로 남긴다.

---

## 1. Observed failure

```
Matrix TRI-005 (P0)   sparse evidence → narrative hallucination 금지
```

실측 counterexample. 같은 경로·같은 sparse 근거에 payload만 바꿨다.

```
sparse admissible evidence   구간 9 ASR "남성이 문을 연다."  (유효 1건 · 0건이 아니다)

summary "남성이 문을 연다."                                   grounding_status = PASS
summary "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."   grounding_status = PASS
                                                            grounding_reasons = []
summary "남성이 문 3개를 연다."                                grounding_status = PASS
```

```
Observed failure
    Sparse admissible evidence does not constrain episode summary
    semantic entailment.

Current grounding
    dialogue claims are evidence-qualified,
    but summary semantics are not automatically entailed/verified.

Consequence
    Unsupported narrative continuation can survive with
    grounding_status = PASS.
```

지금 이미 막히는 것과 대비해 적는다 — 게이트가 전혀 없는 것이 아니라 **채널이 갈린다.**

```
막힌다     dialogue_note 근거 없는 수량      FAIL_UNSUPPORTED       (unsupported_anchor)
          dialogue_note 인용 없음          FAIL_NO_SUPPORT        (no_support_ref)
          오염·부적격 근거만 인용           FAIL_INELIGIBLE_SUPPORT
          구간 밖 인용                    FAIL_OUTSIDE_EPISODE
막히지 않는다 summary의 발명된 수량            PASS
          summary의 발명된 서사·후속 사건    PASS
```

---

## 2. GRD-004 waiver와의 관계 — 이번 감사에서 드러난 것

이 무능은 **이미 기록돼 있다.** 단, 다른 ID에서 다른 우선순위로.

```
GRD-004   P1 · WAIVED (2026-08-30 · 사용자 승인 · ADDENDUM OPEN-3에서 P0 → P1 강등)
          reason waiver is acceptable
              "semantic entailment / NLI가 필요하다. v2.1은 자동 entailment 검증을
               보장하지 않는다고 SPEC에 명시돼 있고, 이를 규칙으로 흉내내면 오탐이
               근거를 지우거나 미탐이 통과를 남발한다."
          known impact
              "참조 유효성·구간 소속·근거 자격 검사를 모두 통과한 문장에도
               의미 수준의 unsupported event가 남을 수 있다."

TRI-005   P0 · 요구 = sparse evidence → narrative hallucination 금지
```

즉 **§1의 counterexample은 GRD-004가 이미 적어 둔 `known impact`의 실례**다. 문제는
우선순위가 어긋나 있다는 것이다.

```
같은 무능이   GRD-004에서는 P1 · waived
            TRI-005에서는 P0 · hard gate
```

그래서 `semantic entailment not automatically verified`를 더 이상 품질 한계로만 둘 수
없다.

```
KNOWN LIMITATION
+
P0 ACCEPTANCE BLOCKER
```

**이 우선순위 불일치 자체를 여기서 해소하지 않는다.** GRD-004의 P1 강등은 승인된
결정이고, TRI-005의 P0는 frozen matrix다. 둘을 맞추는 것은 별도 governance 결정이다.

---

## 3. Remediation goal

```
Given sparse admissible evidence,
no accepted episode summary may assert a concrete event, action,
consequence, quantity, participant, location, or causal/temporal
continuation that is not supported by eligible episode evidence.
```

**판정 방식은 `decision-open`이다.** 아래 세 설계를 먼저 비교해야 하고, NLI verifier
추가로 곧바로 확정하지 않는다.

```
C1  Generation restriction
    producer contract 자체를 더 제한해 summary가 근거 범위를 넘지 않게 한다
    장점  새 모델 의존이 없다
    위험  프롬프트로 보장되지 않는다 — 지금 실패가 이미 그 증거다

C2  Post-generation verification
    summary claim → evidence entailment 검증. FAIL이면 표현 자격을 차단한다
    장점  요구를 직접 겨냥한다
    위험  **모델 의존이 하나 더 생긴다** (generator hallucination → verifier 판단)
          GRD-004 waiver가 거부한 바로 그 경로다

C3  Extractive / deterministic summary
    sparse 조건에서는 새 abstractive summary를 허용하지 않고
    검증된 근거 표현만 결정적으로 조합한다
    장점  새 모델 의존 없음 · v2.1의 표현 계층 철학(C-04/C-05)과 같은 형태
          근거가 부족하면 NO_RELIABLE_CONTENT로 떨어뜨리는 기존 어휘를 재사용한다
    위험  sparse 판정 임계가 새 자유 변수가 된다 · 보고서 문장이 기계적으로 변한다
```

현재 프로젝트 철학(표현 계층 LLM 도입 금지 · 결정적 조합)에 비추면 **C3 또는 C2+C3
hybrid를 먼저 검토할 가치가 크다.** 다만 이것도 권고이고 결정이 아니다.

사전등록에서 반드시 고정해야 하는 것.

```
sparse의 정의        무엇을 sparse로 볼 것인가 (근거 건수? 자격 근거 비율?)
판정 주체            결정적 규칙 · 기존 모델 · 신규 모델 중 무엇인가
실패 시 동작          summary 차단 · 표현 자격 박탈 · NO_RELIABLE_CONTENT 중 무엇인가
과잉 격리 방지        근거 범위 안의 요약은 계속 통과해야 한다
GRD-004과의 정합성    P1 waiver와 P0 요구의 우선순위를 어떻게 맞추는가
```

---

## 4. 회귀 fixture — 어떤 해결책을 택해도 RED → GREEN

`tests/test_v2_1_tri_005_gap.py`에 고정했다. 계약 테스트는 `xfail(strict=True)`이므로
remediation이 들어오면 XPASS가 실패로 잡히고, marker 제거 없이 지나갈 수 없다.

```
Evidence (sparse · 유효 1건)
    "남성이 문을 연다."

Forbidden accepted summary — ① 서사 발명
    "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."

Forbidden accepted summary — ② 수량 발명
    "남성이 문 3개를 연다."

Must keep passing — 근거 범위 안
    "남성이 문을 연다."
```

두 fixture를 **독립으로** 둔다. 숫자와 서사는 실패 양상이 다르고, 해결책에 따라
하나만 막힐 수 있다.

함께 고정한 것 — remediation 이후에도 참이어야 한다.

```
dialogue 인용 없음        FAIL_NO_SUPPORT
dialogue 수량 발명        FAIL_UNSUPPORTED · dialogue 제거
오염 근거만 인용          FAIL_INELIGIBLE_SUPPORT
sparse ≠ absent          유효 근거 1건 (0건이면 ERR-009이고 다른 계약이다)
근거 범위 안의 요약        PASS 유지 (과잉 격리로 닫는 것을 막는다)
```

---

## 5. 이 티켓이 하지 않는 것

```
지금 구현                 없음. production 변경 0
matrix 문구 수정           없음 (A를 거부했다)
P0 waiver 등록            없음 (B를 거부했다)
GRD-004 waiver 취소·변경   없음 (별도 governance 결정)
NLI/entailment 도입 결정   없음 (decision-open)
§19 편입                  없음 — TRI 5/6이므로 절 전체를 집계에 넣지 않는다
```

## 6. 다음 단계

```
1  remediation 사전등록  완료 — V2_1_TRI_005_REMEDIATION_PREREG_2026-09-02.md
                       C3 primary · C1 v1 미적용 · C2 제외 · SPARSE_V1 = eligible == 1
2  사용자 승인
3  구현 + 위 fixture RED → GREEN + xfail marker 제거
4  §19(GEO 4 + TRI 6) 한 번에 final tally 편입
5  전체 재집계
```

그때까지 최종 판정은 이것이다.

```
IMPLEMENTATION_COMPLETE = NO
사유 = TRI-005 P0 implementation gap (OPEN)
```
