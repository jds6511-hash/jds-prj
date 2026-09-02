# v2.1 최종 acceptance 집계 (2026-09-02)

```
IMPLEMENTATION_COMPLETE = NO
```

**Gate 통과 ≠ 구현 완료.** 네 Gate는 닫혔지만 frozen matrix의 최종 규칙은 그것보다
넓다.

```
Gate A ∧ Gate B ∧ Gate C ∧ Gate D
∧ all P0 PASS
∧ every P1 = PASS 또는 explicitly WAIVED
∧ regression PASS ∧ tree clean
  → IMPLEMENTATION_COMPLETE
```

---

## 1. 닫힌 것

```
Gate A  Canonical Core           COMPLETE   11/11 티켓 · P0 51/51 · P1 12/12
Gate B  Grounded Content         COMPLETE   P0 22/22 · P1 6 PASS + 1 WAIVED(GRD-004)
Gate C  Presentation Separation  COMPLETE   P0 19/19 · P1 10/10 · waiver 0
Gate D  Research Boundary        COMPLETE   7/7

REG-010                          PASS_BY_AUTHORIZED_SUPERSESSION
regression                       3,555 passed / 1 skipped
tree                             clean (실측)
```

---

## 2. 막는 것 — matrix 40건이 어느 지도에도 없다

```
matrix 총계   166      지도에 있음  126      지도에 없음  40  (그중 P0 26)
```

```
family  건수   P0  P1  P2   내용
CP        9     5   2   2   change-point provider (미채택 상태의 계약)
DET       7     5   2   -   결정성 (재실행 · 다른 LLM/VLM/OCR에서 경계 동일)
ERR      10     8   2   -   실패 의미론 (hard fail · silent fallback 금지)
GEO       4     2   2   -   instruction echo caption 구분·무영향
TRI       6     3   3   -   오염·희소 근거에서 서사 환각 금지
REG       4     3   1   -   REG-001 회귀 · 002 P0 suite · 003 P1 suite · 004 tree
```

이 항목들의 **동작이 없다는 뜻이 아니다.** Gate A~C 테스트가 상당 부분을 이미
덮고 있을 가능성이 크다. 그러나 **어느 테스트가 어느 ID를 닫는지 매핑된 적이 없다.**
Gate A·B·C에서 지켜 온 규칙이 그대로 적용된다.

> 테스트 하나가 green이라고 비슷해 보이는 acceptance ID를 근거 없이 PASS로 적지 않는다.

따라서 지금 상태에서 `all P0 PASS`를 주장할 수 없다.

---

## 3. REG-010은 PASS가 아니라 supersession으로 센다

```
REG-010 ORIGINAL          P0 · push = NO           frozen matrix 그대로
REG-010 EFFECTIVE STATUS  PASS_BY_AUTHORIZED_SUPERSESSION
근거                      V2_1_REG_010_AUTHORIZATION_ADDENDUM_2026-09-02.md
허용 범위                 authorized_supersession_ids = { REG-010 }
```

---

## 4. 남은 일

```
E-01  ERR   실패 의미론 10건 매핑        (P0 8)
E-02  DET   결정성 7건 매핑              (P0 5)
E-03  CP    change-point 계약 9건 매핑    (P0 5 · P2 2는 진단)
E-04  TRI · GEO  오염·echo 10건 매핑      (P0 5)
E-05  REG-001 ~ 004 매핑 + 전체 재집계
```

각 티켓은 **새 동작 구현이 아니라 기존 증거의 귀속**이다. 증거가 없는 ID가 나오면
그때는 해당 계약이 실제로 미구현이라는 뜻이므로 별도 티켓으로 올린다.

---

## 5. 측정하지 않은 것 (통과로 적지 않는다)

```
한글(HWP) 실제 열림       미검증 — HWPX 패키지 구조·본문 XML까지만 확인했다
                         제출 전 수동 open 확인 필요
```

```
KNOWN-LIMITATION-C09     grounding FAIL이 그 구간의 보존된 요약을 표현에서 가린다
                         정본에는 남는다. containment 실패가 아니라 recall trade-off.
KNOWN-GUARD-LIMITATION   A-11 REG-007은 파일 이름만 본다. Gate D가 경로 검사를 덧댔다.
```

---

## 6. 이 문서가 의미하지 않는 것

```
M8 실패 번복 아님
M9 승인 아님
official test 개방 아님
성능 개선 아님
change-point 채택 아님
general event detector 성립 아님
```
