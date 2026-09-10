# CONSERVATIVE_EVENT_MAP chapter-input packet

리뷰어 판정용 재료다. **executor는 답을 쓰지 않는다.** Chapter·narrative 문구는 생성하지 않았다.

## region 구조 (0–600초)

```
R01      0–    24  UNRESOLVED     overlap -                    node UG01
R02     24–    48  SINGLE_SOURCE  overlap -                    node SS01
R03     48–    96  CONFLICT       overlap O02,O03              node CB001,CB002
R04     96–   192  STITCHABLE     overlap O04,O05,O06,O07      node SG001,SG002,SG003,SG004
R05    192–   264  CONFLICT       overlap O08,O09,O10          node CB003,CB004,CB005
R06    264–   312  STITCHABLE     overlap O11,O12              node SG005,SG006
R07    312–   384  CONFLICT       overlap O13,O14,O15          node CB006,CB007,CB008
R08    384–   480  STITCHABLE     overlap O16,O17,O18,O19      node SG007,SG008,SG009,SG010
R09    480–   528  CONFLICT       overlap O20,O21              node CB009,CB010
R10    528–   576  STITCHABLE     overlap O22,O23              node SG011,SG012
R11    576–   600  SINGLE_SOURCE  overlap -                    node SS02
```

## 수치

```
source event 160 · 표현됨 160 · 유실 0
CONSENSUS_EVENT 6 · CONTINUATION_GROUP 5 · TRANSITION 1
CONFLICT_BLOCK 10 · CONFLICT_REGION 4 · SINGLE_SOURCE 2 · UNRESOLVED_GAP 1
conflict 240초 · stitchable 288초 · single-source 48초 · unresolved 24초
false_resolution 0 · invalid_source_dependency 0
```

## 판정 질문 (리뷰어 전용)

```
Q1 STRUCTURAL_USABILITY
whole-video temporal structure가 보이는가
판정: NOT_ADJUDICATED
```

```
Q2 CONFLICT_LOCALIZATION
material conflict가 명시적 block으로 격리됐는가
판정: NOT_ADJUDICATED
```

```
Q3 NO_FALSE_RESOLUTION
conflict가 consensus처럼 병합된 곳이 없는가
판정: NOT_ADJUDICATED
```

```
Q4 CHAPTER_INPUT_USABILITY
이 map으로 conflict를 숨기지 않은 Chapter 후보를 만들 수 있는가
판정: NOT_ADJUDICATED
```

## 최종 어휘 (리뷰어 전용)

```
CONSERVATIVE_EVENT_MAP_PASS / HOLD / INCONCLUSIVE
executor 상태: EXECUTED / REVIEW_PENDING · verdict NOT_ADJUDICATED
```

말할 수 있는 최대 결론: 리뷰어가 PASS로 판정하면, 이 표현은 conflict를 숨기지 않은 채 Semantic Chapter 입력으로 쓸 수 있는 최소 조건을 만족한다.

