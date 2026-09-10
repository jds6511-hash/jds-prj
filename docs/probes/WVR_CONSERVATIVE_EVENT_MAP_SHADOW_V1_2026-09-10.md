# WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1 결과 (2026-09-10)

사전등록: `docs/preregistration/WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1_2026-09-10.md`
(commit `061aacc`) · 구현 `7a568d7` · **새 VLM/LLM 추론 0회 · GPU 미사용**

```
executor 상태   EXECUTED / REVIEW_PENDING
입력            Local Event 160건(W01–W23) + 리뷰어 판정 22건 + frame bank (전부 해시 동결)
표현            region 11개로 0–600초 연속 · STITCHABLE은 상위 group · CONFLICT는 관측 2집합 보존
판정            executor가 PASS/HOLD/INCONCLUSIVE를 계산하지 않았다
validator       PASS 31/31 · 재계산 결정성 확인
```

## A. provenance

```
prereg commit          061aacc589cb5ea145ecdf3691b9e942e66f84b7
implementation         7a568d71ae342c4a9f5493be032e574d3bbfe414
source registry        1885cda9fd567ccfb9bea79383bcb89260225cafb228253e8efca2cf3cdc4073
stitch verdicts        b27ef299057e807174c2f12ddbee84e294e94482810881a29fda66b70071338b
revealed mapping       5b19b177efedaad1b989bf2b99be5f283096637a949bbd6a61b3993e6167aba9
frame bank             64fb207a0617a371385a3736c224c6983f82deb035401f68448ff042f1eefcd3
source manifest(46)    a0726a4b13b4bd0f6e1ea692eec55e8cd0343132e32b532283e6e68511680631
video                  ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
새 추론 / 새 LLM 호출    0 / 0 · gpu_used=false
```

네 입력 파일 모두 **실행 전 해시 대조**를 통과했다(불일치면 실행 거부).

## B. lineage (event 유실 0)

```
source event          160
표현됨                 160
유실                   0
invalid source 의존     0 (W00 event 0건 · [0,24)에 채운 event 0건)
member 행 총계          179 (같은 event가 두 node에 걸치면 양쪽에 등재)
  conflict 관측 행       68
  stitch group member   97
  single-source 행       14
primary lineage        stitch_group_member 87 · conflict_observation_member 59 ·
                       single_source_event 14   (합 160)
region 2개에 걸친 event  7건 (`also_in_regions`에 기록 · 어느 쪽에서도 삭제하지 않았다)
두 node 이상에 등재된 event 19건
```

lineage 규칙은 사전등록대로다 — primary_region은 **교차 길이 최대(동률이면 이른 region)**,
그 외 교차 region은 `also_in_regions`에 남긴다. event 텍스트·원본 시각은 무변경이고
clip된 행은 `(원본 46.0–49.0)`처럼 원본을 병기한다.

## C. map 구성

```
region              11
CONSENSUS_EVENT      6   (리뷰어 SAME_EVENT)
CONTINUATION_GROUP   5   (리뷰어 CONTINUATION)
TRANSITION           1   (리뷰어 TRANSITION)
  STITCH_GROUP 합     12  = STITCHABLE overlap 12개
CONFLICT_BLOCK      10   = MATERIAL_CONFLICT overlap 10개
CONFLICT_REGION      4
SINGLE_SOURCE        2 region (event 14건)
UNRESOLVED_GAP       1   ([0,24) · event 0건 · filled=false)
false_resolution     0
```

node type은 **리뷰어 relation에서 기계적으로** 나온다(SAME_EVENT→CONSENSUS_EVENT,
CONTINUATION→CONTINUATION_GROUP, TRANSITION→TRANSITION). executor가 새로 고른 것이 없다.

## D. whole-video region map (0–600초)

```
R01     0–  24  UNRESOLVED     overlap -            node UG01     valid 관측 없음(W00뿐)
R02    24–  48  SINGLE_SOURCE  overlap -            node SS01     W01 단독 8건
R03    48–  96  CONFLICT       O02,O03              CB001,CB002   CR01
R04    96– 192  STITCHABLE     O04,O05,O06,O07      SG001–SG004   SAME,CONT,CONT,CONT
R05   192– 264  CONFLICT       O08,O09,O10          CB003–CB005   CR02
R06   264– 312  STITCHABLE     O11,O12              SG005,SG006   CONT,CONT
R07   312– 384  CONFLICT       O13,O14,O15          CB006–CB008   CR03
R08   384– 480  STITCHABLE     O16,O17,O18,O19      SG007–SG010   SAME,SAME,SAME,TRANS
R09   480– 528  CONFLICT       O20,O21              CB009,CB010   CR04
R10   528– 576  STITCHABLE     O22,O23              SG011,SG012   SAME,SAME
R11   576– 600  SINGLE_SOURCE  overlap -            SS02          W23 단독 6건
```

```
conflict     240초    stitchable   288초
single-source 48초    unresolved    24초    합 600초 (구멍 없음)
```

이 길이는 **coverage일 뿐 semantic 정확도가 아니다**
(`semantic_truth_percentage: null` 고정).

## E. conflict region (해결하지 않음)

```
CR01 [ 48, 96)  CB001 O02 (W01↔W02) · CB002 O03 (W02↔W03)
CR02 [192,264)  CB003 O08 (W07↔W08) · CB004 O09 (W08↔W09) · CB005 O10 (W09↔W10)
CR03 [312,384)  CB006 O13 (W12↔W13) · CB007 O14 (W13↔W14) · CB008 O15 (W14↔W15)
CR04 [480,528)  CB009 O20 (W19↔W20) · CB010 O21 (W20↔W21)
```

각 CONFLICT_BLOCK은 다음을 그대로 가진다.

```
observation_set_1 / observation_set_2   서로 다른 창의 관측 event 전량 (양쪽 모두 비어 있지 않음)
reviewer_relation CONFLICT · reviewer_status MATERIAL_CONFLICT
resolution NONE · preferred_source null
ordering_basis  "source 창 id 오름차순 — 선호·우선순위가 아니다"
```

`hypothesis` `truth` `preferred` `winner` `likely` `score` `confidence` `best` 같은
필드명은 산출물 전체에서 0건이다(validator가 문자열로 확인).

## F. stable region (병합했지만 원문은 남는다)

```
R04 [ 96,192)  SG001 SAME_EVENT (W03+W04) · SG002~SG004 CONTINUATION_GROUP
R06 [264,312)  SG005,SG006 CONTINUATION_GROUP
R08 [384,480)  SG007~SG009 CONSENSUS_EVENT · SG010 TRANSITION
R10 [528,576)  SG011,SG012 CONSENSUS_EVENT
```

group에는 상위 설명 문장을 만들지 않았다(`description_generated: false` ·
`description` 키 없음). 양쪽 창의 event를 clip 시각 순 `ordered_members`로 나열만 한다.

## G. chapter-input packet

```
runs/wvr_light_v1/conservative_event_map_v1_chapter_input_packet.md
Q1 STRUCTURAL_USABILITY / Q2 CONFLICT_LOCALIZATION /
Q3 NO_FALSE_RESOLUTION / Q4 CHAPTER_INPUT_USABILITY  — 4개 모두 NOT_ADJUDICATED
최종 어휘 한 줄만 적혀 있다: CONSERVATIVE_EVENT_MAP_PASS / HOLD / INCONCLUSIVE
```

Chapter 후보·narrative 문구는 만들지 않았다.

## H. 검증

```
새 테스트   tests/test_wvr_conservative_map_v1.py  WVR-T01~T40  40/40
뮤테이션    T-M1~T-M24 중 유효 23개 전부 RED (구멍 0)
           T-M9(총계 검사 제거)는 창별 census와 등가여서 mutation 목록에서 제외하고
           총계 검사 자체를 코드에서 제거했다 — 창별 census가 총계를 함의한다
           (import 시점에 `sum(창별)==160` 불일치를 예외로 막는다)
validator  scripts/wvr_cmap_validate.py  PASS 31/31
전체 스위트  4,907 passed · 2 skipped (porcelain·HEAD 4건은 결과 커밋 전 dirty 탓)
경계 확인   제출본 5732075871fd… 불변 · official test 미접촉 · M9 미실행 ·
           stitch verdicts·registry·revealed mapping·W00 산출물 무변경 ·
           SHADOW source 46파일 무변경
```

주요 mutation(전부 RED): CONFLICT→STITCHABLE 강제 · conflict 관측 한쪽 삭제 ·
source event 누락 · W00 event 삽입 · [0,24) synthetic fill · earlier-window-wins 삽입 ·
relation→node type 변경 · region 동결 대조 제거 · 창별 census 제거 ·
false_resolution/lineage 차단 제거 · conflict 이중표현 감지 제거 · 선호 source 감지 제거 ·
event 텍스트 수정 · 원본 시각 대체 · member 순서 역전 · description 생성 ·
semantic 퍼센트 생성 · primary region 동률 규칙 역전 · 미완결 판정 허용 ·
source 해시 검사 제거(=verdict 파일 변경 감지 불가) · validator 검사 무력화.

## I. 의미 / 비의미

말하는 것:

```
리뷰어 판정 22건만으로 0–600초 연속 region 구조가 기계적으로 유도된다
material conflict 10건이 CONFLICT_BLOCK 10개로 격리되고 양쪽 관측이 모두 남았다
source event 160건이 전부 표현되고 유실이 0이다
[0,24)는 채우지 않고 UNRESOLVED_GAP으로 남았다
어떤 창도 승자로 선택되지 않았다 (preferred_source 전부 null · resolution 전부 NONE)
```

말하지 않는 것(사전등록 §16):

```
conflict가 해결됐다 · Event Map이 검증됐다 · 어느 창이 맞다 · 0.5fps sufficient ·
Chapter/Overview를 만들어도 된다 · production ready · 정확도 수치
```

허용되는 최대 결론(리뷰어 PASS 후):

```
리뷰어가 PASS로 판정하면, 이 표현은 conflict를 숨기지 않은 채 Semantic Chapter
입력으로 쓸 수 있는 최소 조건을 만족한다.
```

## J. 산출물

```
runs/wvr_light_v1/conservative_event_map_v1.json                     map 전체(canonical)
runs/wvr_light_v1/conservative_event_map_v1.md                       사람이 읽는 region 맵
runs/wvr_light_v1/conservative_event_map_v1_chapter_input_packet.md  리뷰어 판정 packet
runs/wvr_light_v1/conservative_event_map_v1_summary.json             §20 필수 필드
src/wvr_conservative_map_v1.py · scripts/wvr_cmap_build.py ·
scripts/wvr_cmap_validate.py · tests/test_wvr_conservative_map_v1.py
```

## K. 상태

```
WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1     EXECUTED / REVIEW_PENDING
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1    CLOSED / EVENT_STITCHING_SHADOW_HOLD (불변)
WVR_EVENT_MAP_COVERAGE_SHADOW_V1         CLOSED / EVENT_MAP_SHADOW_HOLD (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1           CLOSED / INCONCLUSIVE (불변)
SUBDIVISION family                       STOPPED / NOT SUFFICIENT
0.25fps sufficiency NOT ESTABLISHED · 0.5fps PROVISIONAL ONLY
production Event extraction · Adjudicated Event Map · Semantic Chapter ·
Overview · Analysis · Conclusion · HWPX · submission promotion ·
official test · M9                       HOLD
```

여기서 멈춘다. 리뷰어 판정 대기.
