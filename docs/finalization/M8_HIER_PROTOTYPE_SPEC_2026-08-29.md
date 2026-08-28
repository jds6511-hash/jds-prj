# M8_HIERARCHICAL_PROTOTYPE 규격 — 2026-08-29

```
성격   제품·설계 prototype. 사람이 실제 산출물을 읽고 판단한다
아님   평가 · 채점 · judge · M9 대체 · 공식 methodology 변경
질문   "이 보고서가 내가 실제로 만들고 싶었던 결과물에 가까운가?"
```

**공식 결과는 불변이다.**

```
M8 official evaluation   COMPLETE
M8 official acceptance   FAIL
M9                       HOLD
official test            UNOPENED
```

---

## 0. 왜 2층인가

M8-v1 실패의 핵심은 이것이었다.

```
짧은 사건은 큰 사건에 흡수되고
긴 사건은 여러 작은 사건으로 쪼개진다
```

`Event`가 한 층뿐이라, 긴 등산 장면 안의 `코스 설명`·`풍경 확인`·`계속 걷기`를
표현하려면 전부 별개 Event로 만들 수밖에 없다. R1(짧은 사건 보존)과 R2(과분할 억제)가
**같은 층에서 서로 충돌**한 이유다.

2층 구조는 그 충돌을 구조로 해소한다 — 짧은 사건을 Atomic에서 보존하고, 보고서는
Major 수준으로 낸다.

---

## 1. 계층

```
기존 5초 segments  (seg_idx · start · end · subtitle · caption)
        ↓   Observation layer — **새로 만들지 않는다. 이미 있다**
Atomic Event       짧아도 독립적인 상태 전이는 살린다
        ↓
Major Event        인접한 Atomic들을 하나의 지속 활동으로 묶는다
        ↓
AAR Report         사람이 읽는 문서
```

**새 VLM을 돌리지 않는다.** 기존 `segments.json`의 subtitle·caption이 Observation이다.

---

## 2. 넣지 않는 것 — 의도적 배제

```
Shot detection           문제는 shot boundary가 아니라 semantic granularity다.
                         넣으면 평가 변수만 늘어난다
Boundary score 수식       E = w1·A + w2·P … 는 weight·threshold·feature detector라는
                         새 튜닝 문제를 만든다
Importance 숫자           0.72 · 0.87 같은 값은 calibration 근거가 없으면 의미가 약하다
role categorical         MAJOR/SUPPORTING/MINOR도 v1에서는 넣지 않는다.
                         계층 자체가 이미 층을 준다 — 필요해지면 그때 추가한다
judge · 채점              이 프로토타입에는 없다
```

---

## 3. 스키마 — 기존 report.json과 **별도 파일**

`report.json`을 건드리지 않는다. M9 계약(`sent_id`·`cites`)도 바꾸지 않는다.

```json
{
  "video_id": "...",
  "schema": "m8_hier_prototype_v1",
  "run_kind": "m8_hier_prototype",
  "n_segments": 192,
  "atomic_events": [
    {"event_id": "E12", "start_seg": 120, "end_seg": 125,
     "title": "등산로를 걸음",
     "description": "...",
     "cites": [120, 123, 125]}
  ],
  "major_events": [
    {"major_event_id": "M03", "title": "산길을 따라 등산",
     "start_seg": 120, "end_seg": 180,
     "subevents": ["E12", "E13", "E14", "E15"],
     "summary": "...",
     "cites": [120, 127, 151, 176]}
  ]
}
```

---

## 4. 생성 — 2 pass

```
PASS 1  Atomic 추출
        기존 청크(60구간 · overlap 5)마다 사건 후보 생성
        R1 계약 유지 — 짧아도 독립적인 전이(이동·도착·출발·식사·입장·퇴장·
        작업 단계 변화)는 긴 사건에 흡수시키지 않는다
        단 "짧다"만으로 사건을 새로 만들지 않는다

PASS 2  Major 묶기
        영상 전체의 Atomic 목록(id · 시각 · 제목)만 주고
        **연속 구간으로 묶는 grouping + major 제목 + 요약**만 출력하게 한다
        새 사건 내용을 자유 생성시키지 않는다
```

### 4-1. Major grouping은 **연속**이어야 한다

시간순으로 정렬한 Atomic 목록을 **연속된 구간(run)들로 분할**한다. 떨어진 시간대를
임의로 묶지 않는다.

```
허용   [E12 E13 E14] [E15] [E16 E17]
금지   [E12 E14] [E13 E15]              — 연속이 아니다
금지   E13이 어느 그룹에도 없음           — 분할이 아니다
금지   E13이 두 그룹에 있음              — 분할이 아니다
```

**위반이면 fail-closed로 원본 유지**(Atomic 하나당 Major 하나로 떨어뜨린다).

### 4-2. 결정적으로 구성하는 것

LLM이 정하지 않고 코드가 정한다.

```
major.start_seg   그룹 멤버의 최소 start_seg
major.end_seg     그룹 멤버의 최대 end_seg
major.cites       멤버 cites의 합집합에서 **구간에 고르게** 최대 4개
                  (새 evidence를 발명하지 않는다)
```

LLM이 쓰는 것은 `title`과 `summary`뿐이다.

### 4-3. 개요(Overview)도 결정적

`영상 개요`는 **Major 제목들로 코드가 구성**하고, 근거는 각 Major의 첫 cite를 쓴다.
해석 문장을 생성하는 synthesis 층을 이번에 만들지 않는다 — provenance 규칙이
아직 없기 때문이다.

---

## 5. 검증 — 전부 결정적. judge 없음

```
1  모든 Major에 subevent가 1개 이상 있는가
2  모든 Atomic에 citation이 1개 이상 있는가
3  cite한 seg_idx가 실제로 존재하는가            0 <= idx < n_segments
4  Atomic의 cite가 자기 span 안에 있는가          start_seg <= c <= end_seg
5  Major span이 subevent 범위를 포함하는가
6  Major의 cite가 멤버 cites의 부분집합인가       (evidence 발명 금지)
7  같은 Atomic id가 두 번 쓰였는가                (중복·누락 = 분할 위반)
8  Atomic id가 유일한가
9  video_id가 일치하는가
10 Major grouping이 시간순 연속 분할인가
```

전부 PASS여야 렌더한다. 하나라도 실패하면 그 사실을 그대로 보고한다.

---

## 6. 대상 3편

각각 M8-v1의 서로 다른 실패 유형을 대표한다.

```
softyeon_ceramics        UNDER_GENERATION_DOMINANT   생성 6 · 미매칭 정답 6
baekmansonghee_jirisan   OVER_FRAGMENTATION_DOMINANT 생성 15 · 정답 7
m8c2_3I7oGwk6EaQ         장기 단일 사건               정답 1건(865초) · C3 max 7.00 결정
```

---

## 7. 경계

```
새 test · M9 · official test        접근하지 않는다
새 human GT                          만들지 않는다
judge · 채점                         하지 않는다
work/<vid>/report.json               덮어쓰지 않는다
공식 M8 · ROUND1 · ROUND2 산출물      수정하지 않는다
report.json 스키마 · M9 계약           변경하지 않는다
push                                 하지 않는다
```

**소비된 패널 3편을 쓴다.** 이 산출물은 development / product prototype이고
성능 증거가 아니다. 채점하지 않으므로 acceptance 판정도 내지 않는다.

---

## 8. 이 프로토타입이 답하는 것 / 답하지 않는 것

```
답한다      사람이 읽었을 때 원하던 AAR 형태에 가까운가
            2층 구조가 짧은 사건 보존과 상위 요약을 동시에 담을 수 있는가
            구조적 무결성(인용·포함관계·분할)이 결정적으로 보장되는가

답하지 않는다  사건 경계의 정확도 · coverage · groundedness
            M8-v1 실패의 해소 여부 · 일반화 · 성능
```

---

## 9. 이후

```
사람이 보기에 가깝다   이 구조를 기반으로 M8을 다시 설계할지 결정
가깝지 않다           H1 consolidation 방식으로 돌아가거나 여기서 종료
```

**어느 쪽이든 공식 M8/M9 판정은 바뀌지 않는다.** 이 결과로 M9 평가 규칙을
사후 변경하지 않는다 — 그것은 결과를 본 뒤 평가 규칙을 바꾸는 일이 된다.
