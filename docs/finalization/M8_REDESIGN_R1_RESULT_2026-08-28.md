# M8 REDESIGN ROUND 1 결과 — 2026-08-28 (개발 점수)

```
판정   REDESIGN_RETHINK
       R1 성공 · R5 성공 · R6 부분 · **R2 실패** + **새 파국 1건 발생**
       fresh confirmation을 열지 않는다
```

```
공식 결과 불변
  M8 evaluation COMPLETE · M8 acceptance FAIL
  C1 FAIL 4/8 · C2 0.3311 · C3 max 7.00
  official artifacts changed: NO
```

이 실행은 **소비된 패널 8편의 개발 증거**다. 값이 좋아진 항목이 있어도 확증이 아니고
"통과"라고 쓰지 않는다. 기계 정본은 `m8_redesign_r1_compare_2026-08-27.json`.

baseline lineage 대조 통과 — 공식 리포트 8편의 바이트 해시가
`m8_official_report_lineage_2026-08-27.json`과 8/8 일치한다.

---

## 1. 표

```
항목                      baseline   redesign   방향
unmatched GT / 68              22         10    ↓  R1 성공
  그중 짧은 GT(<=10구간)         18         10    ↓  R1 성공
생성 사건 총수                  93        219    ✗  2.35배
unmatched generated            47        161    ✗  3.4배
raw events 총합               104        262    ✗
raw events/chunk median       2.0        5.5    ✗  극단 증가
alignment median           0.3311     0.3892    ↑  단 혼합 효과 (§2-2)
C3 max                       7.00      16.00    ✗  **8편 전부 악화**
rejections                     11         44    ✗
zero-event chunks               1          3    —  전부 분할로 회수
chunk retries                   5          3    ↓
chunk splits (R5)               0          3    회수 3/3
non-Korean event titles         2          1    ↓  부분 개선
C1 PRESENT 편수                 4          3    ↓  단 새 유형 발생 (§2-3)
편당 생성 시간                 45초      110초    ✗  약 2.3배
```

---

## 2. 무엇이 일어났나

### 2-1. R1은 작동했다

```
미매칭 GT 22 → 10 (-55%)
그중 짧은 GT(<=10구간) 18 → 10
softyeon_ceramics  미매칭 GT 6 → 2 · 문장 6 → 23
kbs_banff          미매칭 GT 8 → 3 · alignment 0.102 → 0.334
```

공식 실행에서 조직적으로 사라졌던 짧은 사건이 실제로 회수됐다.
`softyeon`의 under-generation은 명확히 완화됐다.

### 2-2. R2는 실패했다 — 정확히 우려한 패턴

```
unmatched GT      22 →  10   ↓
unmatched generated 47 → 161   ↑↑↑
```

과분할을 억제하라는 지시가 **전혀 먹지 않았고**, R1의 부작용만 그대로 나왔다.
생성 사건이 93 → 219로 늘고 그중 161건(73.5%)이 아무 정답 사건과도 매칭되지 않는다.

**Compression은 8편 전부 악화됐다.**

```
video                     baseline → redesign
baekmansonghee_jirisan       2.14  →   3.29
softyeon_ceramics            0.50  →   1.92
jissi_farm                   1.00  →   2.73
kbs_banff                    1.40  →   2.40
wonyi_gyeongju               1.60  →   3.60
wonyi_geoje                  1.25  →   3.38
m8c2_3I7oGwk6EaQ             7.00  →  16.00
m8c2_cIxG7OHYMPU             1.56  →   4.44
```

한 편의 예외도 없다. `3I7`의 단일 장기 사건 문제는 7 → 16으로 두 배 이상 나빠졌다.

**alignment median 상승은 개선이 아니라 혼합 효과다.**

```
상승  softyeon +0.237 · kbs_banff +0.232 · 3I7 +0.121 · cIxG +0.060
하락  wonyi_gyeongju -0.176 · wonyi_geoje -0.086 · baekmansonghee -0.051 · jissi -0.035
```

**baseline이 나빴던 4편은 올랐고 좋았던 4편은 내려갔다.** 중앙값이 0.331 → 0.389로
움직인 것은 그 교차의 결과이고, 균일한 개선이 아니다.

### 2-3. 새 파국이 생겼다 — `repetition_loop`

`wonyi_gyeongju`가 ABSENT → PRESENT로 바뀌었고 유형은 반복 루프다.

```
청크 2에서 정규화 완전일치 단위가 연속 4회
청크 2에서 정규화 완전일치 단위가 연속 6회
  단위: "식사 후 대화 | 여성들은 식사를 마친 후, 서로를 바라보며 대화를 나눕니다. …"
```

짧은 사건을 보존하라는 압력이 **거의 동일한 사건을 반복 생성**하는 형태로 나타났다.
이것은 R1의 직접적 부작용이고, 성공 기준 "새 부작용 없음"을 깬다.

### 2-4. 거부 구성이 뒤바뀌었다

```
baseline   too_many_evidence 6 · evidence_outside_span 4 · bad_span 1        (11)
redesign   thin_description 25 · too_many_evidence 16 · bad_span 2 ·
           evidence_outside_span 1                                          (44)
```

`thin_description`이 0 → 25로 새 최다 사유가 됐다. 사건을 많이 쪼개면 근거당 서술량
하한(`MIN_CHARS_PER_EVIDENCE`)에 걸린다. **과분할이 거부로 이어지는 새 경로**다.

### 2-5. R5는 작동했다 — 다만 C1에는 보이지 않는다

```
분할 3건 · 회수 3/3 (100%)
wonyi_gyeongju 청크 0: 재생성 0건 → 분할로 14건 회수
```

빈 청크 3건이 전부 회수됐다. 그런데 그 3편의 `early_stop`은 여전히 PRESENT다 —
`detect_early_stop`이 `chunk_retries`의 `recovered:false`만 보고 `chunk_splits`의
회수를 **모른다**.

```
구현 결함   R5로 구멍을 메웠는데 C1이 그것을 반영하지 않는다
```

전향적 C1 amendment에 이 항목을 함께 넣어야 한다(현재 문서는 mid-stream 구멍만
다룬다). **공식 C1은 이것과 무관하다** — 공식 실행에는 분할이 없었다.

### 2-6. R6은 부분 개선

```
비한국어 사건명 2 → 1
```

줄었지만 사라지지 않았다. 규칙 9만으로는 부족하다.

---

## 3. 원인 해석

```
OBSERVED
  O1  미매칭 GT 22 → 10, 짧은 GT 18 → 10
  O2  생성 219건 중 161건 미매칭. Compression 8/8 악화
  O3  raw events/chunk median 2.0 → 5.5
  O4  wonyi_gyeongju에 연속 4회·6회 동일 단위 반복
  O5  thin_description 거부 0 → 25
  O6  분할 3건 전부 회수. 그러나 early_stop은 여전히 PRESENT

SUPPORTED INTERPRETATION
  S1  같은 프롬프트에 양방향을 쓰는 것만으로는 입도 계약이 성립하지 않는다.
      모델은 "짧아도 보존"만 강하게 받아들이고 "과분할 금지"는 무시했다(O1+O2+O3)
  S2  R1의 압력이 임계를 넘으면 반복 생성으로 퇴화한다(O4) — 사건을 더 찾으라는
      요구에 실질적으로 새 사건이 없을 때 같은 사건을 다시 낸다
  S3  과분할은 서술량 하한과 충돌한다(O5). 즉 파이프라인의 다른 제약이
      과분할을 벌하고 있고, 그 벌이 다시 커버 손실로 돌아온다

HYPOTHESIS
  H1  분할 억제는 프롬프트 지시가 아니라 **출력 개수 제약**이나 후처리 병합으로
      다뤄야 할 가능성
  H2  청크당 사건 수 상한을 GT 밀도가 아닌 구간 길이로 주면 두 방향을 동시에
      제어할 수 있을 가능성
  H3  긴 지속 사건은 "하나의 사건 + 내부 단계"라는 2층 구조가 필요할 가능성
      (현재 스키마는 1층이라 조각이 곧 별개 사건이 된다)
```

---

## 4. 판정

```
FREEZE_CANDIDATE      아니다 — Compression 8/8 악화, 새 파국 1건
ROUND_2_R3            아니다 — 지금 지배 병목은 span이 아니라 과분할이다
REDESIGN_RETHINK      **이것이다**
```

R3(span 정밀도)로 넘어가는 것은 잘못된 순서다. R1을 켠 상태에서 **과분할을
실제로 억제하는 기제**를 찾지 못하면 어떤 span 개선도 Compression에 묻힌다.

ROUND 2는 R3가 아니라 **R2의 재설계**여야 한다. 후보는 §3의 H1~H3이고,
어느 것도 이번에 구현하지 않았다.

---

## 5. 경계

```
official artifacts changed        NO
official verdict changed          NO
fresh confirmation opened         NO
fresh panel sourcing              NO
fresh labels                      NO
M9 test opened                    NO
official test viewed              NO
R3 · R4 · R7                      손대지 않았다
push                              NO
```

개발 라운드는 최대 2회로 제한돼 있다. ROUND 2를 쓸지, 어떤 기제로 갈지는
**사용자 결정 사건**이다.
