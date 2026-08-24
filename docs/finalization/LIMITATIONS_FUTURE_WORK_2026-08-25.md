# 한계와 향후 과제 (2026-08-25)

두 절을 명확히 분리한다. 향후 과제는 **"현재 프로젝트에서 반드시 못 끝낸 실패"가 아니다** —
현재 자원 경계 밖에 있는 다음 단계다.

## 현재 한계 (Current limitations)

**1. 캡션 모델 우열 미해결.** `Qwen2.5-VL-3B` ↔ `Qwen3-VL-4B`는 두 표본이 반대 방향이고
둘 다 CI가 0을 배제한다(AI Hub +0.0310 · dev −0.0903). AI Hub는 재사용 표본이고 dev는
cluster 3이라 어느 쪽도 확증 자격이 없다. 배포는 3B를 유지하되, 이유는 **4B가 incumbent를
교체할 fresh deployment-relevant evidence를 확보하지 못했기 때문**이다.

**2. 배포 유사 조건의 cluster 수가 작다.** dev는 영상 3편이다. 영상을 cluster로 잡는
paired bootstrap에서 cluster 3은 CI를 진단용으로만 쓸 수 있다. 관측 ICC가 0이었지만
**그것을 진실로 가정하지 않는다.**

**3. fresh annotation이 미완이다.** P2는 175행 설계에서 20행에서 멈췄고 retrieval·evaluation을
실행하지 않았다(outcome 미열람). 병목은 도구가 아니라 라벨 작성 자체였다.

**4. P3-A는 현재 자원으로 실행 불가.** 설계는 동결됐다 — 최소 가치 효과 MRR +0.02 초과,
PRIMARY half-width ≈0.02, 300영상 × 5질의 = 1,500 GT 행, 외부 human annotator. 막는 것은
통계가 아니라 **annotation logistics와 영상 외부 반출 권한**이다(현재 35편 전부 `unclear`,
파일럿 코호트 0/10).

**5. 일부 오류 유형이 descriptive에 머문다.** 질의 유형별 이질성(복합형 −0.2407 ↔ 장면형
+0.0132), 후보 풀 크기 효과(설명되지 않은 격차 0.067)는 **plausible contributor까지**이고
root cause로 확정하지 않았다.

**6. test를 열지 않았다.** test 39는 확정 config로 공식 평가가 끝났고 비가역 자원이다.
39→72 확장(신규 33건)은 준비돼 있으나 별도 test-opening 이벤트로 HOLD다. M9는
`split=="test"` 하드코딩이라 실행 자체가 test 접촉이다.

**7. 캡션은 기계를 건너면 달라진다.** 같은 모델·양자화·프롬프트로도 노트북↔서버 완전일치율이
25.6%(dev)·23.2%(AI Hub A-half)였다. 다만 **AI Hub 562질의 검색 성능 차이는 Δ−0.0046
CI[−0.0267, +0.0174]**로 큰 방향성 환경 페널티는 재현되지 않았다 — 문자열이 달라지는 것을
곧 성능 저하로 해석하지 않는다. 통제된 조건(같은 서버·commit·경로)에서는 2,328구간 재생성
결과가 **상이 0건, 완전일치 1.0**으로 결정적이었다.

**8. AAR는 로컬에서 돌지 않는다.** `report_model`이 7B이고 VRAM 20GB가 필요하다. 6GB 로컬
불가는 실측이고, 3B 하향은 프롬프트 예시 복사 오염으로 기각됐다. 서버 GPU 전용이다.

**9. 자막형에서 융합이 손해를 본다.** 공식 test에서 장면형 MRR 0.174 → 0.718로 크게
오르지만 자막형은 0.958 → 0.880으로 내려간다 — **트레이드오프이고 숨기지 않는다.**

**10. 재현에 원본 영상이 필요하다.** 코드·절차·평가 라벨은 공개, 데이터는 비공개다.
`work/*/segments.json`·임베딩이 저장소에 없으므로 clone 직후 평가가 재현되지 않는다.

## 향후 과제 (Future work)

```
1  rights-cleared 외부 annotation 기반 fresh P3-A
   — pilot-only 10편 확보 → 50행 유료 logistics 파일럿 → 1,500 GT
   — 막는 것: 영상 반출 권한(공공누리도 초상·개인정보는 허락 범위 밖) · 행당 소요 실측 부재

2  더 큰 한국어 long-form GT
   — dev cluster 3의 한계를 정면으로 푸는 유일한 길

3  질의 유형 이질성 확증
   — 복합형 열세 · 장면형 우세가 재현되는지. AI Hub에는 유형 라벨이 없다

4  모델 후보·라우터 조사
   — 유형별로 다른 캡션 모델을 쓰는 router는 P3-B로 설계만 있다(미실행)

5  I1 production 통합
   — 현재 R_only(2) 동결, validation까지. hard gate·자동 recaption trigger가 아니다.
     통합하려면 read-only diagnostic/warning부터 검토하고 별도 승인을 받는다

6  M8/M9 확장
   — M8 exploratory 6분류 미완(HOLD) · M9는 test-opening 승인 사건

7  회의록 생성 (Phase 4)
   — 설계만 있음 (docs/planning/phase4_회의록_설계.md)
```

## 경계 유지 선언

이 문서의 어떤 항목도 다음을 바꾸지 않는다.

```
deployment      Qwen2.5-VL-3B / P0 / 4bit · KURE-v1 · α=0.5
4B              viable candidate · not adopted · superiority unresolved
P2 / P3 / M8    HOLD
registry SoT    HOLD (read-only 어댑터)
test / M9       HOLD
```
