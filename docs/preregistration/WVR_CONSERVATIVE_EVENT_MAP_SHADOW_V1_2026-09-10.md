# WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1 사전등록 (2026-09-10)

이 문서는 **결과를 보기 전에** 동결한다. 실행 후 수정하지 않는다(오탈자 정정은
결과 산출 전에만). Claude는 executor이며 **PASS/HOLD/INCONCLUSIVE를 계산하지 않는다.**

## 0. 동결된 선행 상태

```
WVR_EVENT_EXTRACTION_SHADOW_V1          CLOSED / INCONCLUSIVE
WVR_EVENT_MAP_COVERAGE_SHADOW_V1        CLOSED / EVENT_MAP_SHADOW_HOLD
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1   CLOSED / EVENT_STITCHING_SHADOW_HOLD
```

리뷰어 판정(동결 · 수정 금지 · reveal 전에 확정됨):

```
overlap 22개   STITCHABLE 12 · MATERIAL_CONFLICT 10 · UNRESOLVED 0
relation      SAME_EVENT 6 · CONTINUATION 5 · TRANSITION 1 · CONFLICT 10
```

W00은 valid Local Event source가 아니다(WINDOW_INVALID · 재실행 금지).

## 1. 질문 (PRIMARY)

> 리뷰어가 STITCHABLE로 판정한 관계는 상위 group으로 묶고 MATERIAL_CONFLICT는
> **해결하지 않고** alternative source observations로 보존하는 방식으로,
> Semantic Chapter의 입력이 될 수 있는 conservative whole-video event
> representation을 만들 수 있는가?

이 사건은 conflict의 정답을 찾지 않는다. **representation feasibility**만 만든다.

## 2. source authority (이 순서로 권위를 가진다)

```
1. 본 사전등록
2. runs/wvr_light_v1/stitch_v1_verdicts.json      (리뷰어 판정 · 동결)
3. runs/wvr_light_v1/stitch_v1_blind_map.json     (revealed mapping · 동결)
4. runs/wvr_light_v1/event_map_v1_registry.json   (W01–W23 Local Event 160건)
5. runs/wvr_light_v1/shadow_frame_bank.json       (frame stamp · traceability 전용)
6. EVENT_MAP_COVERAGE_SHADOW_V1 산출물 · SHADOW_V1 창 기하
```

동결 해시(실행 전 대조 · 불일치면 즉시 중단하고 INCONCLUSIVE 사유로 보고):

```
event_map_v1_registry.json  1885cda9fd567ccfb9bea79383bcb89260225cafb228253e8efca2cf3cdc4073
stitch_v1_verdicts.json     b27ef299057e807174c2f12ddbee84e294e94482810881a29fda66b70071338b
stitch_v1_blind_map.json    5b19b177efedaad1b989bf2b99be5f283096637a949bbd6a61b3993e6167aba9
shadow_frame_bank.json      64fb207a0617a371385a3736c224c6983f82deb035401f68448ff042f1eefcd3
event_map_v1_coverage.json  c7281388585d2c62a325e1bbd4ba65c4d8b813d1a91be340f1bd9e7942b41fdd
source manifest (46파일)     a0726a4b13b4bd0f6e1ea692eec55e8cd0343132e32b532283e6e68511680631
video                       ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
```

## 3. 절대 금지 (이 사건의 핵심)

```
MATERIAL_CONFLICT에서 승자 선택 — earlier 우선 · later 우선 · event 수 우선 ·
  구체성 우선 · 문자열 유사도 우선 · 자동 score · LLM 해결 · Track A evidence 해결 ·
  새 frame adjudication
새 VLM inference · 새 LLM inference (GPU 0회)
source event 삭제·수정·요약·재작성
[0,24) synthetic fill · W00 event 사용
새 semantic 판정 · 리뷰어 판정 수정
상위 narrative 문구 생성 (Chapter·Overview 문장)
사후 임계·퍼센트 게이트 생성
```

conflict는 **해결하지 않고 보존**한다. `hypothesis` `truth` `preferred` `winner`
`likely` 같은 필드·표현을 산출물에 쓰지 않는다.

## 4. node 어휘 (동결)

```
CONSENSUS_EVENT      리뷰어 SAME_EVENT   / STITCHABLE 인 overlap
CONTINUATION_GROUP   리뷰어 CONTINUATION / STITCHABLE 인 overlap
TRANSITION           리뷰어 TRANSITION   / STITCHABLE 인 overlap
CONFLICT_BLOCK       리뷰어 MATERIAL_CONFLICT 인 overlap (양쪽 관측 전부 보존)
SINGLE_SOURCE_EVENT  valid 창 하나만 관측한 구간의 event
UNRESOLVED_GAP       valid 관측 자체가 없는 구간 (현재 [0,24))
```

상위 묶음(§7·§8):

```
STITCH_GROUP     STITCHABLE overlap 하나에 대응하는 상위 group (node_type은 relation)
CONFLICT_REGION  인접 CONFLICT_BLOCK들의 상위 region (내부 구조 유지)
```

## 5. region 유도 규칙 (verdict에서 결정적으로 계산)

```
1) 24초 격자 cell 25개: [0,24) [24,48) … [576,600)
2) cell 분류
   - valid 창이 덮지 않는 cell                  → UNRESOLVED
   - overlap 구간과 같은 cell                   → 그 overlap의 리뷰어 상위 판정
                                                (STITCHABLE / CONFLICT)
   - valid 창 하나만 덮는 cell (overlap 아님)     → SINGLE_SOURCE
3) 인접 cell 중 분류가 같은 것을 병합해 region으로 만든다
4) region id는 시간순 R01, R02, …
```

동결 기대 구조(위 규칙 + 동결 verdict에서 유도되며, 산출물이 이와 다르면 중단한다):

```
R01 [  0, 24) UNRESOLVED
R02 [ 24, 48) SINGLE_SOURCE
R03 [ 48, 96) CONFLICT      O02 O03
R04 [ 96,192) STITCHABLE    O04 O05 O06 O07
R05 [192,264) CONFLICT      O08 O09 O10
R06 [264,312) STITCHABLE    O11 O12
R07 [312,384) CONFLICT      O13 O14 O15
R08 [384,480) STITCHABLE    O16 O17 O18 O19
R09 [480,528) CONFLICT      O20 O21
R10 [528,576) STITCHABLE    O22 O23
R11 [576,600) SINGLE_SOURCE
region 11개 · 합 600.0초 · 경계는 모두 24의 배수 · 22 overlap 전부 배정
```

## 6. source event lineage 규칙 (event 유실 0)

```
primary_region  event 구간과 교차 길이가 가장 큰 region 하나 (동률이면 이른 region)
also_in_regions primary 외에 교차하는 region 전부 (숨기지 않는다)
lineage_type    primary_region의 분류에서 결정된다
                CONFLICT     → conflict_observation_member
                STITCHABLE   → stitch_group_member
                SINGLE_SOURCE→ single_source_event
membership      region 안에서 교차하는 모든 CONFLICT_BLOCK · STITCH_GROUP에 등재
                (하나의 event가 두 block/group에 걸치면 둘 다에 등재한다)
missing         primary_region이 없거나 membership이 0인 event 수 — 0이어야 한다
```

event는 **clip해서 보여주되 원본 시각을 함께 적는다**(`original_start/end`).
텍스트(actor·action·object_or_state)는 한 글자도 바꾸지 않는다.

## 7. CONFLICT_BLOCK 표현

```
node_id            CB001…  (MATERIAL_CONFLICT overlap 시간순)
time               overlap 구간
observation_set_1  source 창 id + 그 창의 관측 event 전량 (clip · 원본 시각 병기)
observation_set_2  다른 창 id + 그 창의 관측 event 전량
reviewer_relation  CONFLICT      (동결)
reviewer_status    MATERIAL_CONFLICT (동결)
resolution         NONE
preferred_source   null
ordering_basis     source 창 id 오름차순 — 선호·우선순위가 아니다
```

인접 CONFLICT_BLOCK은 CONFLICT_REGION(CR01…)으로 묶되 내부 block·event 구조를
그대로 유지한다.

## 8. STITCH_GROUP 표현

```
node_id             SG001…  (STITCHABLE overlap 시간순)
node_type           CONSENSUS_EVENT | CONTINUATION_GROUP | TRANSITION (relation에서)
sources             두 창 id
time                overlap 구간
ordered_members     양쪽 event를 clip 시각 순으로 나열 (원문 actor/action/object 그대로)
group_description   생성하지 않는다 (`description_generated: false`)
```

원본 event는 삭제하지 않는다 — 상위 group만 추가한다.

## 9. silent concat 금지

각 overlap 구간은 반드시 STITCH_GROUP 또는 CONFLICT_BLOCK에 연결돼야 한다.
창 출력을 시간순으로 이어붙인 것은 Conservative Event Map이 아니다.
예외는 single-source region뿐이다.

## 10. 산출물

```
runs/wvr_light_v1/conservative_event_map_v1.json
runs/wvr_light_v1/conservative_event_map_v1.md
runs/wvr_light_v1/conservative_event_map_v1_chapter_input_packet.md
runs/wvr_light_v1/conservative_event_map_v1_summary.json
```

summary 필수 필드:

```
source_events_total · events_represented · events_missing
consensus_event_count · continuation_group_count · transition_count ·
conflict_block_count · conflict_region_count · single_source_count ·
unresolved_gap_count · region_count
conflict_duration_sec · unresolved_duration_sec · stitchable_duration_sec ·
single_source_duration_sec
false_resolution_count · invalid_source_dependency_count
new_inference_count · new_llm_call_count (둘 다 0)
verdict/registry/mapping/frame-bank/video 해시 · commit
```

정의:

```
false_resolution_count          MATERIAL_CONFLICT overlap 중 (관측 집합이 2개가
                                아니거나 · 한쪽이 비었거나 · 선호 필드가 null이
                                아니거나 · stitch group으로 표현된) 것의 수
invalid_source_dependency_count W00 등 invalid source에서 온 member·node 수 +
                                [0,24)에 채워진 synthetic event 수
```

## 11. chapter-input packet (§13)

리뷰어가 다음을 판정할 재료만 만든다. **executor는 답을 쓰지 않는다.**

```
Q1 STRUCTURAL_USABILITY     whole-video temporal structure가 보이는가
Q2 CONFLICT_LOCALIZATION    material conflict가 명시적 block으로 격리됐는가
Q3 NO_FALSE_RESOLUTION      conflict가 consensus처럼 병합된 곳이 없는가
Q4 CHAPTER_INPUT_USABILITY  이 map으로 conflict를 숨기지 않은 Chapter 후보를
                            만들 수 있는가
```

Chapter·narrative 문구는 생성하지 않는다.

## 12. 결정성

같은 source + 같은 verdict 파일이면 node id · region 경계 · membership · coverage
수치가 동일해야 한다. 직렬화는 canonical(`sort_keys=True` · `ensure_ascii=False` ·
`indent=1`)로 하고, validator가 재계산 동일성을 확인한다.

## 13. 측정 blocker (→ INCONCLUSIVE 사유 · 리뷰어가 판정)

```
동결 해시 불일치 (registry · verdicts · mapping · frame bank · manifest · video)
verdict 22건 미완결 또는 어휘 위반
region 유도 결과가 §5 동결 구조와 불일치
lineage 누락 > 0 · false_resolution_count > 0 · invalid_source_dependency_count > 0
overlap-verdict 대응 실패 (22개 중 하나라도 node에 연결되지 않음)
```

blocker는 **executor가 고쳐서 통과시키지 않는다** — 중단하고 사실만 보고한다.

## 14. 검증

```
tests/test_wvr_conservative_map_v1.py   WVR-T## (§21 항목 전부)
mutation                                §22 항목 전부 RED
scripts/wvr_cmap_validate.py            전 항목 PASS
python -m pytest tests/ -q              전체 통과
clean tree · HEAD == origin/master
경계 확인: 제출본 5732075871fd… 불변 · official test 미접촉 · M9 미실행 ·
          SHADOW source 46파일 · registry · verdicts · mapping 무변경
```

## 15. 리뷰어 어휘 (executor 계산 금지)

```
CONSERVATIVE_EVENT_MAP_PASS / HOLD / INCONCLUSIVE
```

executor 상태 문자열은 `EXECUTED / REVIEW_PENDING` 하나뿐이다.

## 16. 말할 수 있는 최대 결론 (리뷰어 판정 후)

```
리뷰어가 PASS로 판정하면, 이 표현은 conflict를 숨기지 않은 채 Semantic Chapter
입력으로 쓸 수 있는 최소 조건을 만족한다.
```

말하지 않는 것:

```
conflict가 해결됐다 · Event Map이 검증됐다 · 어느 창이 맞다 · 0.5fps sufficient ·
Chapter/Overview를 만들어도 된다 · production ready · 정확도 수치
```

## 17. 계속 HOLD

```
Production Event Extraction · Adjudicated Event Map · Semantic Chapter · Overview ·
Analysis · Conclusion · HWPX · submission promotion · official test · M9
EVENT_MAP_COVERAGE_SHADOW HOLD · EVENT_STITCHING_SHADOW HOLD 불변
```

## 18. 실행 순서

```
1 prereg 작성 → 2 prereg commit → 3 source/verdict 해시 검증 →
4 구현·테스트 commit → 5 map 생성 → 6 region 계산 → 7 chapter-input packet →
8 validator → 9 mutation → 10 전체 스위트 → 11 clean tree → 12 결과 commit → 13 STOP
```

GPU inference 0회. 결과를 리뷰어에게 전달한 뒤 멈춘다.
