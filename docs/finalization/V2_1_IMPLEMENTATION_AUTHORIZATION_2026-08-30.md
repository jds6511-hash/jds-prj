# v2.1 Implementation Authorization — 2026-08-30

```
성격   승인 사건 기록 (authorization event record)
아님   설계 변경 · 연구 판정 변경 · 새 실험
```

OPEN-8은 착수를 무기한 금지한 것이 아니라 **sequencing 결정**이었고, 그 해제 조건은
`별도 implementation authorization 명시`였다. 그 사건이 2026-08-30에 발생했다.

---

## 1. 승인 사건

```
일시    2026-08-30
주체    사용자
형식    구현 파일(A-01) 전달 + 명시적 진행 지시
```

원문.

> "폴더에 구현을 위한 2.1py파일 2개 넣었다 **확인하고 진행해**"

> "**계속 진행한다.** 최종 보고서 쪽으로 돌아가지 않고 **Gate A 구현 트랙을 유지**하는
> 게 맞다."

두 번째 발화에서 승인 범위가 재확인됐다 — 단발 티켓이 아니라 Gate A 트랙 유지다.

---

## 2. 상태 전이

이전.

```
v2.1 implementation          DEFERRED
implementation authorization NOT GRANTED
OPEN-8                       CLOSED — DEFER UNTIL FINALIZATION DELIVERABLES COMPLETE
```

현재.

```
v2.1 implementation          IN PROGRESS
implementation authorization GRANTED
authorization date           2026-08-30
Gate A                       IN PROGRESS
A-01                         COMPLETE — commit 7f5d0f9
NEXT TICKET                  A-03  raw store — raw-before-parse
```

---

## 3. OPEN-8 — 덮어쓰지 않는다

당시 결정은 그 시점의 판단으로 **역사 기록으로 남긴다.** 삭제하면 왜 미뤘는지가
사라진다.

```
OPEN-8
Original decision (2026-08-30)
  DEFER UNTIL FINALIZATION DELIVERABLES COMPLETE
  근거: 병목은 compute가 아니라 주의력·변경 관리 · 구현이 baseline을 건드릴 유인

Subsequent authorization (2026-08-30)
  Implementation start explicitly authorized by user.

Result
  DEFERRED → AUTHORIZED / IN PROGRESS
```

OPEN-8이 걸었던 착수 조건 중 `1 보고서 본문·보충 절 확정`·`2 발표 자료 확정`은
**충족되지 않은 상태에서 사용자 판단으로 해제**됐다. 조건이 달성된 것이 아니라
**우선순위가 명시적으로 변경**된 것이다 — 이 구분을 기록한다.

따라서 finalization 트랙은 종료가 아니라 **보류**다.

---

## 4. 이 승인이 바꾸지 않는 것

```
M9                           HOLD / NO
official test                UNOPENED / NO
공식 M8 판정                  FAIL · 불변
BCS core modification        NO
caption change-point adopt   NO
new human GT                 NO
additional model experiment  NO
push                         NO
```

Gate A는 LLM·GPU·서버 예약을 쓰지 않는다. 이 승인은 **로컬 결정적 코드 작성 권한**만
연다.

---

## 5. A-01 acceptance record

```
commit                7f5d0f9
SCH-001               PASS   canonical schema valid
SCH-002               PASS   required legacy field missing
SCH-003               PASS   invalid type (bool 포함)
OPEN-1 contract       PASS   단일 adapter · schema 혼용 거부
adapter 왕복           PASS
adapter 외부 스캔      PASS   위반 파일 주입으로 실패 확인
full regression       2,566 passed / 1 skipped   (직전 2,550)
tree                  clean
```

산출물.

```
src/v2_1_segments.py          CanonicalSegment · legacy_segment(s)_to_canonical
tests/test_v2_1_segments.py   16 tests
```

`work/<video_id>/segments.json`·`common.load_segments` 무변경. A-01은 아무것도 쓰지
않는다 — run layout·manifest는 A-02 책임으로 남긴다.

---

## 6. 후속 티켓 경계

A-03은 raw store다. run identity·저장 위치가 필요해져도 **A-02의 manifest를 앞당겨
구현하지 않는다.** A-03에 필요한 최소 contract만 정의하고 run-layout 책임은 A-02에
남긴다.
