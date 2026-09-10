# WVR_EVENT_MAP_COVERAGE_SHADOW_V1 사전등록 (2026-09-10)

승인: 리뷰어 결정 — **deterministic post-processing probe (새 추론 0회 · GPU 불필요)**.
이 문서는 산출물 생성 전에 커밋한다. **결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

원래 프로젝트 목표(whole-video report pipeline)로 복귀하는 첫 사건이다. W00 failure
mechanism을 더 파지 않는다.

## 0. 목적

```
기존 SHADOW_V1의 23개 VALID local window event output만으로, 실패한 W00을 억지로
복구하지 않고 전체 10분 영상의 Event Map과 흐름을 어느 정도 복원할 수 있는지 검증한다
```

질문은 "모든 window가 성공했는가"가 아니라 "성공한 local observation만으로 whole-video
event structure를 얼마나 복원할 수 있는가"다.

## 1. 선행 상태 (동결 · 소급 변경 금지)

```
WVR_EVENT_EXTRACTION_SHADOW_V1        CLOSED / INCONCLUSIVE (W00 WINDOW_INVALID)
WVR_W00_TRIGGER_ISOLATION_V1          CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED
WVR_W00_VISUAL_CONTENT_ISOLATION_V1   CLOSED / VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED
SUBDIVISION family                    STOPPED / NOT SUFFICIENT
WVR_W00_ZERO_DURATION_EXEMPLAR_ISOLATION_V1
                                      NOT EXECUTED / SUPERSEDED
                                      (prereg commit 792d798만 존재 · 추론 0회 · 산출물 0건)
0.25fps semantic sufficiency          NOT ESTABLISHED
0.5fps                                PROVISIONAL WORKING DENSITY ONLY
```

## 2. 입력 (읽기 전용 · 수정 금지)

```
source          runs/wvr_light_v1/shadow_v1_W01…W23.json + _raw.txt  (23창 · 46파일)
manifest        docs/preregistration/WVR_EVENT_MAP_COVERAGE_SHADOW_V1_sources.json
manifest sha    a0726a4b13b4bd0f6e1ea692eec55e8cd0343132e32b532283e6e68511680631
                (valid source 46개 "name sha" 정렬 목록의 sha256)
W00             invalid source — event source로 쓰지 않는다. 해시 무변경만 확인한다
frame bank      runs/wvr_light_v1/shadow_frame_bank.json (0.5fps 300 stamp · traceability 전용)
video sha256    ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
```

새 Qwen 추론·새 STT·caption 입력을 쓰지 않는다. raw artifact를 수정하지 않는다.

## 3. partial-failure tolerance 원칙

```
VALID local window     사용 가능한 observation
INVALID local window   hallucinated replacement 금지 · unresolved coverage로 남긴다
```

실패 창을 재실행·재프롬프트·임의 생성·이웃 복사로 채우지 않는다. `[0,24)`처럼 관측이
없는 구간은 명시적으로 남긴다. **window coverage와 event coverage를 구분한다.**

## 4. 산출물 4종 (+ 요약)

```
1  Local Event Registry             event_map_v1_registry.json
2  Coverage Map                     event_map_v1_coverage.json
3  Candidate Event Map              event_map_v1_candidate_map.json
4  Semantic Chapter Candidate       event_map_v1_chapter_candidates.json
   whole-video flow reviewer packet event_map_v1_flow_packet.md
   요약·provenance                   event_map_v1_summary.json
```

Overview·Analysis·Conclusion 문장은 생성하지 않는다.

## 5. Local Event Registry (결정적)

W01→W23 순서로 각 record의 `parsed.collapsed`를 저장 순서대로 읽는다.

```
event_id   "%s_E%03d" % (window_id, index + 1)      예 W01_E001
보존 필드   source_window · start_sec · end_sec · actor · action · object_or_state
           collapsed_count · source_indices
lineage    source_raw_hash · source_collapse_hash · source_record_sha256
```

event text를 수정하지 않는다.

## 6. overlap relation candidate (결정적 · 판정 authority 아님)

인접 VALID window 쌍 `(W_k, W_{k+1})`의 event 쌍에만 적용한다. 기존 frozen 규칙
`wvr_density_v2.semantic_relation`(정규화 signature 완전일치 → equivalent · 공통 토큰 0
→ different · 그 사이 → adjudication)을 그대로 쓴다. 새 유사도 임계를 만들지 않는다.

```
구간 교차(교집합 길이 > 0)
    signature 일치            POSSIBLE_SAME_EVENT
    토큰 완전 disjoint         POSSIBLE_CONFLICT
    부분 공유                  UNRESOLVED
구간 교차 없음 · 접함(gap == 0)
    signature 일치            POSSIBLE_CONTINUATION
    그 밖                     POSSIBLE_TRANSITION
gap > 0                      relation 행을 만들지 않는다
```

## 7. Candidate Event Map (단순 concat 금지)

```
Local Events → 시간 정렬 → overlap relation candidate →
duplicate/continuation grouping → transition candidate → CANDIDATE_EVENT_MAP
```

```
grouping   POSSIBLE_SAME_EVENT · POSSIBLE_CONTINUATION 관계의 union-find
group 구간  members의 [min start, max end)
group 정렬  (start_sec, 첫 event_id)
transition 연속 group 쌍에 §6 규칙을 적용해 후보 라벨과 시간 gap을 기록
```

명칭은 `CANDIDATE_EVENT_MAP`으로 유지한다 — verified factual Event Map이 아니다.

## 8. Coverage 계산 (600초 기준)

```
window coverage      VALID window 구간의 union (초 · %)
event coverage       registry event 구간의 union (초 · %)
redundant window     2개 이상 VALID window가 덮는 시간
redundant event      2개 이상 서로 다른 source window의 event가 덮는 시간
unresolved           valid local event evidence가 없는 시간
```

구간 상태 어휘(세그먼트 단위):

```
MULTI_WINDOW_OBSERVED    2개 이상 source window의 event가 덮는다
SINGLE_WINDOW_OBSERVED   1개 source window의 event만 덮는다
OBSERVED                 위 둘의 합 (상위 범주)
INVALID_WINDOW_ONLY      valid event 없음 · INVALID 창(W00) 구간에만 속한다
UNRESOLVED               valid event 없음 · INVALID 창 구간도 아니다
```

`coverage percentage ≠ semantic correctness`를 결과에 명시한다.

## 9. Semantic Chapter Candidate (결정적 · 후보만)

chapter 제목·narrative를 새로 생성하지 않는다. boundary는 **event 내용에서** 뽑고
local window 격자(24·48·72…)를 자동 boundary로 쓰지 않는다.

```
walk    §7의 정렬된 group 순서
boundary candidate at group k (k>=1) iff
    actor 변경 (정규화 문자열 불일치)  OR
    sustained content change —
      group k의 (action+object) 토큰 집합이 group k-1과 disjoint이고,
      k>=2면 group k-2와도 disjoint
MIN_CHAPTER_SEC = 60.0
    boundary를 적용하면 직전 chapter가 60초 미만이 되는 경우 그 boundary는
    suppressed로 기록하고 사용하지 않는다 (기록은 남긴다)
chapter 구간  [첫 group start, 마지막 group end)
```

각 chapter candidate에 time range · ordered candidate events · major transitions ·
source windows · coverage status · unresolved intervals를 붙인다.
**semantic final boundary는 executor가 확정하지 않는다.**

## 10. frame traceability (판정 아님)

각 candidate group·chapter에 구간 안의 0.5fps frame bank stamp 목록을 기계적으로
붙인다. `frame available = event supported`로 판정하지 않는다.

## 11. 기존 SHADOW blind packet

기존 23 overlap blind packet과 mapping은 이번 사건에서 semantic 판정용으로 열지 않는다.
기존 SHADOW_V1의 technical INCONCLUSIVE를 소급 PASS로 바꾸지 않는다.

## 12. reviewer 질문 (executor가 답하지 않는다)

```
Q1 FLOW_RECOVERABLE    23창 event만으로 주요 activity sequence · 큰 transition ·
                       전체 temporal progression을 식별할 수 있는가
Q2 GAP_MATERIALITY     unresolved 구간이 Overview를 왜곡할 정도로 중요한가
Q3 EVENT_MAP_USABLE    현재 Candidate Event Map이 Semantic Chapters 입력으로 쓸 만한가
```

## 13. reviewer verdict 어휘 (executor가 계산하지 않는다)

```
EVENT_MAP_SHADOW_PASS           주요 흐름 복원 · gap이 narrative를 붕괴시키지 않음 ·
                                candidate sequence가 chapter 입력으로 usable ·
                                명백한 material conflict 없음
EVENT_MAP_SHADOW_HOLD           주요 activity/순서 왜곡 · 중요 transition 통째 누락 ·
                                candidate map이 모순
EVENT_MAP_SHADOW_INCONCLUSIVE   unresolved coverage가 너무 커서 흐름 판단 자체가 어려움
```

임계 percentage를 결과 보고 사후에 만들지 않는다.

## 14. 해석 제한

PASS가 나와도 금지:

```
Event extraction solved · 0.5fps sufficient · all events factual · production ready
```

허용되는 최대 결론:

```
Existing valid C01 local-window observations were sufficient to construct a usable
shadow candidate of the video's global event flow despite explicitly preserved
unresolved coverage.
```

## 15. 하지 않을 것

```
W00 재실행 · zero-duration exemplar 실험 · prompt 변경 · token cap 변경 ·
subdivision 추가 · 다른 shift · retry policy ·
새 Qwen visual inference · 새 STT · caption을 report 입력으로 사용 ·
Overview / Analysis / Conclusion 문장 생성 · HWPX 생성
```

## 16. 구현 원칙

deterministic post-processing만 쓴다. 새 generative LLM을 쓰지 않는다. 사용 입력은
기존 W01–W23 output · timestamp · window provenance · frame bank metadata뿐이다.

## 17. provenance (모든 파생 산출물)

```
source SHADOW_V1 commit · source window id · source raw hash ·
source collapse hash · source record sha256 · video sha · derivation script commit ·
valid source manifest sha256
```

## 18. 최소 invariant (테스트로 고정)

```
W00이 valid source에서 제외된다
W01–W23 source artifact 무변경 (manifest sha a0726a4b…)
W00 자리를 채우는 synthetic event 0건
silent concat fallback 없음
시간 순서 보존 · coverage union 결정적 · overlap 쌍 수 결정적 ·
event ID 결정적 · group·chapter 결과 결정적 (같은 입력 → 같은 출력)
chapter candidate가 24/48초 고정 격자에 종속되지 않는다
unresolved interval 보존
official test 미접촉 · 현행 제출본 무변경 · SHADOW blind map 무변경
```

mutation suite RED 확인 + full suite 실행.

## 19. 실행 순서

```
1  prereg 작성        2  prereg commit        3  implementation/tests commit
4  source artifact 해시 검증                    5  Local Event Registry
6  Coverage Map       7  overlap relation candidate
8  Candidate Event Map                        9  Semantic Chapter Candidate packet
10 whole-video flow reviewer packet           11 deterministic validator
12 tests/mutations/full suite                 13 clean tree
14 result commit      15 STOP
```

GPU 추론은 필요하지 않다.

## 20. 실행 후 상태

executor는 다음까지만 기록한다.

```
WVR_EVENT_MAP_COVERAGE_SHADOW_V1   EXECUTED / REVIEW_PENDING
```

유지:

```
SHADOW_V1 CLOSED / INCONCLUSIVE · 0.25fps sufficiency NOT ESTABLISHED ·
0.5fps PROVISIONAL ONLY · production Event extraction HOLD
```

계속 HOLD:

```
Semantic Chapter production · Overview · Analysis · Conclusion · HWPX ·
submission promotion · official test · M9
```

리뷰어 PASS 시 다음 후보는 `WVR_SEMANTIC_CHAPTER_SHADOW_V1`이고, 그 다음에만
`WVR_OVERVIEW_SHADOW_V1`을 연다. 순서를 건너뛰지 않는다.

여기서 멈춘다.
