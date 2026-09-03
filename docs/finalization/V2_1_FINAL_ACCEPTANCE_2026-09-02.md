# v2.1 최종 acceptance 집계 (2026-09-02 · TRI-005 closure 반영 2026-09-03)

```
IMPLEMENTATION_COMPLETE = YES
```

frozen matrix의 최종 규칙 각 항을 채운 결과다. **Gate 통과 ≠ 구현 완료**라는 원칙은
그대로다 — 아래는 Gate 넷이 아니라 규칙 전체를 잰 것이다.

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

E-01 · E-01a  ERR 실패 의미론        CLOSED   PROVEN 10/10 (P0 8 · P1 2) · UNPROVEN 0
E-02          DET 결정성             CLOSED   PROVEN 7/7  (P0 5 · P1 2) · UNPROVEN 0
E-03          CP 비채택 안전장치       CLOSED   PROVEN 9/9  (P0 5 · P1 2 · P2 2) · UNPROVEN 0
E-04          GEO/TRI dataset regression  CLOSED   PROVEN 10/10 (P0 5 · P1 5) · UNPROVEN 0
E-05          REG 저장소 게이트         CLOSED   PROVEN 4/4  (P0 3 · P1 1) · UNPROVEN 0

REG-010                          PASS_BY_AUTHORIZED_SUPERSESSION
GRD-004                          P1 · WAIVED (유효 · TRI-005 closure가 이것을 바꾸지 않는다)
regression                       3,839 passed / 1 skipped / 0 xfailed
tree clean                       git status --porcelain 전체 0
```

---

## 2. 매핑 — 166/166

```
matrix 총계   166      지도에 있음  166      지도에 없음  0
```

```
family  건수   P0  P1  P2   편입 시점
ERR      10     8   2   -   E-01a (10/10이 된 뒤)
DET       7     5   2   -   E-02
CP        9     5   2   2   E-03
REG       4     3   1   -   E-05  (005~010은 Gate A · Gate D · addendum 소관)
GEO       4     2   2   -   §19 — TRI-005 closure와 함께 한 번에
TRI       6     3   3   -   §19 — 같은 시점
```

**부분 매핑을 숫자 줄이기에 쓰지 않았다.** GEO는 E-04 시점에 이미 4/4였지만 같은
절의 TRI-005가 열려 있어 넣지 않았고, family가 전부 닫힌 뒤 §19 10건을 한 번에
편입했다(40 → 30 → 23 → 14 → 10 → 0 · P0 26 → 18 → 13 → 8 → 5 → 0).

---

## 3. 마지막까지 막고 있던 것 — TRI-005

```
TRI-005   sparse evidence → narrative hallucination 금지        P0 · CLOSED (2026-09-03)
          classification   IMPLEMENTATION_GAP (감사 기록 유지)
          DECISION         C — 기준 축소(A)·P0 waiver(B) 모두 거부
          해결             C3 · sparse 구간에서 모델 요약에 정본 권한을 주지 않는다
          상세             V2_1_TRI_005_CLOSURE_2026-09-03.md
                          V2_1_TRI_005_REMEDIATION_PREREG_2026-09-02.md
```

```
근거 1건 "남성이 문을 연다."

이전   summary "…물건을 훔친 뒤 달아난다."   grounding PASS   ← 발명이 정본에 남았다
이후   summary "남성이 문을 연다."          summary_mode = SPARSE_EVIDENCE_DETERMINISTIC
이후   근거 범위 안의 요약                   그대로 유지       ← 과잉 격리 없음
```

두 counterexample은 `xfail(strict=True)`로 잠겨 있었고, 구현과 함께 XPASS로 실패하면서
marker를 제거하고 평범한 회귀 테스트가 됐다. **XPASS를 남긴 채 닫지 않았다.**

---

## 4. REG-010은 PASS가 아니라 supersession으로 센다

```
REG-010 ORIGINAL          P0 · push = NO           frozen matrix 그대로
REG-010 EFFECTIVE STATUS  PASS_BY_AUTHORIZED_SUPERSESSION
근거                      V2_1_REG_010_AUTHORIZATION_ADDENDUM_2026-09-02.md
허용 범위                 authorized_supersession_ids = { REG-010 }
```

---

## 5. 측정하지 않은 것 (통과로 적지 않는다)

```
한글(HWP) 실제 열림       측정했다 (2026-09-03) — 결과는 아래 결함 기록을 보라
                         이 항목은 matrix acceptance가 요구하는 것이 아니다
```

```
KNOWN OPERATIONAL DEFECT — src/v2_1_render_hwpx.py

  생성물은 ZIP·XML로는 유효하지만 **완전한 HWPX 패키지가 아니다.**
  한글에서 열리지 않는다.

  실측 (한글 Office 2024 COM)
      hand-built 산출물   open() = False
      한글이 저장한 파일    open() = True

  원인 (패키지 대조)
      META-INF/container.xml이 rootfile로 지목한 Contents/content.hpf가 없다
      META-INF/manifest.xml · settings.xml · container.rdf 없음
      Contents/header.xml이 135 B 스텁 — fontface · charPr · paraPr · style 0
      section0.xml은 그 정의를 전제로 참조한다

  영향 범위
      ZIP 무결성 · XML well-formedness · 본문 유니코드 보존은 전부 정상이다
      깨지는 것은 **패키지 완결성**이고, 그래서 glyph 렌더링은 검증 단계에
      도달조차 못 한다
      acceptance 판정은 바뀌지 않는다 — matrix에 HWPX 실제 열림 항목이 없고
      RPT-계열은 canonical 동일성·경계 생성 금지를 재는 계약이다

  현재 우회
      한글 COM 저장 경로(pyhwpx)로 만든 파일은 11파트로 열린다.
      en dash · « » · 박스 문자가 저장본에 원문 그대로 남는다.
      (cp949 TEXT 내보내기에서만 – → &#8211; · « → ≪ 로 바뀐다 — 문서 손상 아님)

  후속
      post-v2.1 트랙. baseline 6e79ac3의 판정을 소급 변경하지 않는다.
      제출용 우회 경로는 scripts/v2_1_hwpx_via_hangul.py로 만들었다.
      결과·잔여 결함: V2_1_HWPX_A1_RESULT_2026-09-03.md
```

```
skip 1건                 tests/test_publication_safety.py::
                         test_publishable_sources_are_actually_tracked
                         대상 파일이 이 작업 트리에 없을 때만 skip
                         v2.1 acceptance 매핑 테스트가 아니다 — P0·P1을 skip으로 닫은 것이 없다
```

```
KNOWN-LIMITATION-C09     grounding FAIL이 그 구간의 보존된 요약을 표현에서 가린다
                         정본에는 남는다. containment 실패가 아니라 recall trade-off.
KNOWN-GUARD-LIMITATION   A-11 REG-007은 파일 이름만 본다. Gate D가 경로 검사를 덧댔다.
GRD-004 (P1 · WAIVED)    일반 semantic entailment는 자동 검증되지 않는다.
                         TRI-005 closure는 **좁은 sparse 상태**만 막는다 —
                         eligible 2+ 구간에는 이 한계가 그대로 남는다.
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
general semantic entailment 해결 아님
GRD-004 waiver 해제 아님
```
