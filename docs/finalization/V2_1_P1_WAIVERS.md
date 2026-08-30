# v2.1 P1 WAIVER 대장

```
근거   V2_1_DECISION_ADDENDUM_2026-08-30.md OPEN-5
규칙   P1 FAIL + waiver 없음  → acceptance BLOCKED
       P1 FAIL + 명시적 waiver → acceptance 가능 · limitation 기록 필수
       **skip을 waiver로 간주하지 않는다**
```

기록 항목.

```
test id · failure description · reason waiver is acceptable · known impact · scope of limitation
승인자 · 날짜
```

---

## 현재 등록된 waiver

### GRD-004 — unsupported concrete action/event

```
test id              GRD-004
priority             P1 (ADDENDUM OPEN-3에서 P0 → P1 강등)
상태                 WAIVED
승인자               사용자
날짜                 2026-08-30
```

**failure description**

```
summary·dialogue의 구체적 행위·사건이 근거로 뒷받침되는지를
deterministic하게 완전 판정할 수 없다.
```

**reason waiver is acceptable**

```
semantic entailment / NLI가 필요하다. v2.1은 자동 entailment 검증을 보장하지
않는다고 SPEC에 명시돼 있고, 이를 규칙으로 흉내내면 오탐이 근거를 지우거나
미탐이 통과를 남발한다. 둘 다 판정 자체를 무의미하게 만든다.
```

**known impact**

```
참조 유효성·구간 소속·근거 자격 검사를 모두 통과한 문장에도
의미 수준의 unsupported event가 남을 수 있다.
```

**scope of limitation**

```
한정   Gate B episode grounding의 semantic event entailment
비한정 named entity 문자열 앵커 (GRD-005)  · reference validity (GRD-002)
       episode scope (GRD-003) · OCR-only (GRD-006)
       claim without support (GRD-010) · claim eligibility (GRD-011 · 012)
       — 전부 P0로 구현·검증됐고 waiver 대상이 아니다
```

**구현 측 표시**

`src/v2_1_grounding.py`는 `entailment`·`nli`·`semantic_support`를 소스 스캔으로
금지한다. 흉내내지 않는다는 것을 코드에서도 강제한다.
