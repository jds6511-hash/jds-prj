# REG-010 AUTHORIZATION ADDENDUM (2026-09-02)

frozen matrix를 **수정하지 않는다.** 원 기준은 그대로 두고, 후속 결정이 운영 제약을
어떻게 바꿨는지만 여기에 기록한다.

```
Original frozen criterion
  REG-010 | P0 | push | NO 유지
  출처  docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md

Historical state
  frozen criterion remains preserved unchanged.
```

---

## Subsequent decision

구현 기간의 `origin/master` push가 사용자에 의해 명시적으로 승인됐다.

```
2026-08-31   "끝나면 깃에 푸시해"
2026-08-31   "그리고 지금까지 한거 깃에 푸시해"
```

이후 각 티켓 완료 시점의 push도 같은 지시 아래 수행됐다.

### Evidence pointers (저장소 기록으로 확인된 값)

```
승인 이전 원격 head   528d488   2026-08-25
최초 승인 push        2ace134   2026-08-31   Gate B CLOSURE
현재 원격 head        c07e1f1   2026-09-02   Gate D
승인 범위 커밋 수      132       528d488..c07e1f1
```

추정값을 쓰지 않았다. 위 SHA·날짜는 `git log` 확인값이다.

---

## Effective interpretation

```
pushes covered by explicit authorization
  → REG-010 failure를 구성하지 않는다

pushes without explicit authorization
  → 여전히 금지다
```

**`push 금지`를 영구 폐기하지 않는다.** 승인의 범위만 supersede된다.

```
authorization_scope   구현 기간 · origin/master · 528d488..c07e1f1
그 밖의 push          승인이 없으면 FAIL
```

### 금지된 해석

```
"한 번 승인이 있었으니 이후 push는 전부 허용"        아니다
"REG-010은 더 이상 적용되지 않음"                   아니다
"frozen matrix의 NO는 사실 PASS였음"               아니다
```

---

## Acceptance status

```
REG-010 ORIGINAL          P0 · push = NO
REG-010 EFFECTIVE STATUS  PASS_BY_AUTHORIZED_SUPERSESSION

Classification
  not WAIVED                     원 규칙 위반을 그냥 수용하는 것이 아니다
  not ordinary PASS              문자 그대로 충족한 것이 아니다
  not a rewrite of the matrix    frozen 본문은 그대로다
```

waiver와 supersession의 차이를 유지한다.

```
waiver        원 규칙은 그대로 적용되고, 실패를 예외적으로 수용한다
supersession  후속 명시적 결정이 해당 범위의 운영 규칙 자체를 바꾼다
```

---

## 최종 acceptance 규칙 (frozen 문장을 고치지 않고 여기서 확장)

```
For final repository acceptance:

P0 item satisfied iff
  PASS
  OR
  PASS_BY_AUTHORIZED_SUPERSESSION
      where a documented later authorization
      explicitly supersedes that operational criterion.
```

이 상태를 쓸 수 있는 항목을 **하나로 잠근다.**

```
authorized_supersession_ids = { REG-010 }
```

다른 P0 실패를 supersession이라고 부르는 우회로를 막기 위해서다. 목록을 늘리는 것은
그 자체가 별도 승인 사건이다.

---

## KNOWN-GUARD-LIMITATION (별건 · 기록만)

```
A-11 REG-007 alone does not detect M9 markers appearing only in directory
components; Gate D adds an independent path-level check
(src/v2_1_gate_d.py :: check_no_m9_execution).
```

Gate D는 두 검사를 함께 써서 통과했다. **A-11을 지금 고치지 않는다** — 연구 경계
가드 변경은 별도 사건이고, 이 addendum과 섞지 않는다.

---

## 남은 것

```
전체 final acceptance 집계
  Gate A · B · C · D COMPLETE 재확인
  전체 P0 / P1 상태 · regression · tree clean · research-boundary guards
  known limitations
→ 그때 처음 IMPLEMENTATION_COMPLETE 판단
```
