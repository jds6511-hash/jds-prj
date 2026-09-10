# WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1 결과 (2026-09-10)

사전등록: `docs/preregistration/WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1_2026-09-10.md`
(commit `a502b8c`) · 구현 이 커밋 · **새 VLM 추론 0회 · Track A 입력 0건 ·
LLM 호출 0회 (Stage B 미실행) · GPU 미사용**

```
executor 상태   EXECUTED / REVIEW_PENDING
Stage A        실행 완료 (결정적 · LLM 없음)
Stage B        **실행하지 않았다** — Stage A가 blocker로 멈췄다
blocker        INSUFFICIENT_BOUNDARY_EVIDENCE (chapter 2개 < 최소 3개)
규칙 완화       없음 (rule_relaxed=false) · 경계 동결 파일 생성 안 함
validator      PASS 16/16 (Stage A + blocker 일관성)
```

## A. provenance

```
prereg              a502b8c
conservative map    0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c (LF · V1과 동일)
Stage A 규칙         후보=event 시작 시각만 · detect 30s · sustain 60s ·
                    min separation 60s (=600/10) · region·격자 주입 false ·
                    jitter false · llm_used false
Stage B 프롬프트      REPAIR_PROMPT_V1 · 템플릿 8a1a9c652dda1e7d24030652350fd29c77b0b0ec0945d6a43aa0e1fb7ae975ae
                    (렌더·생성 미실행)
새 VLM 추론 / LLM     0 / 0 · Track A 미사용
```

## B. Stage A 경계 후보

```
후보 시각 총계            144 (source event 시작 시각 · 0<t<600)
  선택 가능 밴드 안        115 (60 ≤ t ≤ 540)
  conflict block 내부      55
제외 NO_TRANSITION_EVIDENCE      137
제외 NO_EVIDENCE_ON_BOTH_SIDES     1
제외 BOUNDARY_UNSUPPORTED_BY_CONFLICT 0
accepted                           6
```

accepted 후보 전량:

```
  28.0  OBJECT_DOMAIN_CHANGE                                        breadth 22   밴드 밖
  34.0  ACTIVITY_DOMAIN_CHANGE                                      breadth 21   밴드 밖
 400.0  OBJECT_DOMAIN_CHANGE                                        breadth 15   밴드 안
 580.0  ACTIVITY_DOMAIN_CHANGE, SCENE_OR_TASK_CHANGE, OBJECT_...    breadth 18   밴드 밖
 585.0  OBJECT_DOMAIN_CHANGE                                        breadth 15   밴드 밖
 597.0  ACTIVITY_DOMAIN_CHANGE                                      breadth  3   밴드 밖
```

왜 137개가 전환 근거를 갖지 못했는지 — 동결 창(±30초) 아래의 데이터 성질:

```
전/후 30초의 (action+object) 공통 토큰 수   최소 1 · 중앙값 7 · 최대 13 (n=143)
공통 토큰이 0인 시각                        0개
```

즉 **이 영상의 Local Event 표현에서는 인접 30초 구간이 항상 최소 1개의 domain
토큰을 공유한다.** 전환은 action 단독 또는 object 단독 분리로만 잡혔고, 그런 시각이
6개였으며 그중 밴드 안(60–540)은 400.0초 하나였다.

## C. 선택된 경계

```
선택 1개   400.0초  OBJECT_DOMAIN_CHANGE (breadth 15 · conflict 밖)
chapter    2개 ([0,400) [400,600)) → 최소 3개 미달 → BLOCKER
```

사전등록 §4·§17대로 **규칙을 완화해 억지로 3개를 만들지 않았다.** 따라서
`chapter_repair_v1_boundaries.json`(경계 동결 파일)을 만들지 않았고 Stage B로
넘어가지 않았다.

## D. 격자·region 정렬 감사

선택 경계가 1개뿐이라 정렬 통계는 의미가 제한된다. 다만 이번 사건에서 확인된
구조적 사실 하나는 Q3 판단에 직접 관련된다.

```
region 경계         0 · 24 · 48 · 96 · 192 · 264 · 312 · 384 · 480 · 528 · 576 · 600
그중 event 시작 시각  24 · 48 · 96 · 192 · 264 · 312 · 384 · 480 · 528  (9/12)
선택 경계 400.0초    24초 격자 아님 · 48초 격자 아님 · region 경계 아님
jitter               적용 0 · 격자 선택 가중 0 (grid_used_for_selection=false)
```

**region 경계 12개 중 9개가 실제 event 시작 시각과 겹친다.** 즉 event 전환만 써도
경계가 격자와 겹칠 수 있고, V1의 7/7 격자 정렬을 "격자를 복사했다"고만 읽을 수는
없다(V1이 실제로 무엇을 근거로 삼았는지는 이 사건이 밝히지 않는다).

## E. chapter

```
없음 — Stage B를 실행하지 않았다 (blocker)
```

## F. conflict 노출 감사

```
없음 — chapter가 없다
```

구현·검사는 존재한다: conflict 포함 chapter는 요약에 동결 어휘가 없으면
machine disclosure가 붙고, 그 사실이 `CONFLICT_NOT_DISCLOSED_BY_GENERATOR`로
기록된다. 노출 수단이 하나도 없는 상태는 산출물에 존재할 수 없다(WVR-V14·V26).

## G. evidence-class 감사

```
없음 — chapter가 없다
```

규칙과 검사는 동결·구현됐다: conflict 포함 → MIXED_EVIDENCE ·
single-source 지배 또는 unresolved 포함 → LIMITED_EVIDENCE · 그 밖에 multi-window
지지 → STABLE_DOMINANT · **single-source 지배 chapter는 STABLE_DOMINANT 불가** ·
배정자는 executor(LLM 금지). WVR-V10~V13이 고정한다.

## H. V1 대조

```
              V1                          V2 (이번)
chapter        8                           생성 안 됨 (blocker)
내부 경계       48·96·192·264·384·480·576   400.0 하나만 선택 (2 chapter → 미달)
격자 정렬       24초 격자 7/7               해당 없음
evidence 배정   생성기(LLM)                 executor(결정적) — 구현·검증 완료, 미적용
conflict 노출   강제 없음                    강제 구현 완료, 미적용
```

V1 산출물은 무변경이고 정답으로 쓰지 않았다.

## I. 검증

```
새 테스트    tests/test_wvr_chapter_repair_v1.py  WVR-V01~V27  27/27
뮤테이션     V-M1~V-M20 전부 RED (구멍 0)
validator   scripts/wvr_crepair_validate.py  PASS 16/16
전체 스위트  4,964 passed · 2 skipped (porcelain 2건은 결과 커밋 전 dirty 탓)
경계 확인    제출본 5732075871fd… 불변 · official test 미접촉 · M9 미실행 ·
            conservative map·V1 chapter·stitch verdicts·registry 무변경 ·
            Overview/Analysis/Conclusion/HWPX 산출물 0건 · 경계 동결 파일 0건
```

주요 mutation(전부 RED): region·격자 시각 주입 · 주입 차단 제거 · jitter 차단 제거 ·
+1초 jitter · LLM 경계 변경 허용 · LLM 시각/evidence 필드 감지 제거 ·
conflict 노출 판정 무조건 통과 · machine disclosure 제거 · conflict→MIXED 규칙 제거 ·
single-source→LIMITED 규칙 제거 · single-source STABLE 감지 제거 ·
conflict STABLE 감지 제거 · unresolved 소실 감지 제거 · chapter 수 blocker 제거 ·
conflict 한쪽 지지 경계 허용 · 선택에서 격자 우선 · 경계 해시 대조 제거 ·
재생성 거부 제거 · blocker인데 경계 동결.

## J. 상태

```
WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1   EXECUTED / REVIEW_PENDING
   Stage A 완료 · Stage B 미실행 · blocker INSUFFICIENT_BOUNDARY_EVIDENCE
WVR_SEMANTIC_CHAPTER_SHADOW_V1            CLOSED / SEMANTIC_CHAPTER_SHADOW_HOLD (불변)
WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1      CLOSED / CONSERVATIVE_EVENT_MAP_PASS (불변)
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1     CLOSED / EVENT_STITCHING_SHADOW_HOLD (불변)
WVR_EVENT_MAP_COVERAGE_SHADOW_V1          CLOSED / EVENT_MAP_SHADOW_HOLD (불변)
Production Event · Event Map · Chapters · Overview · Analysis · Conclusion ·
HWPX · submission promotion · official test · M9        HOLD
```

리뷰어 어휘: `SEMANTIC_CHAPTER_REPAIR_PASS / HOLD / INCONCLUSIVE`.
Q1~Q6은 판정 재료가 없으므로 전부 미판정 상태다. executor는 판정을 계산하지 않았고,
사전등록 §17대로 하위 layer(Local Event 재추출·W00 복구·sampling·Track A)로
회귀하지 않았다. 여기서 멈춘다.
