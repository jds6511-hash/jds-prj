# M8 REDESIGN ROUND 2 결과 — 2026-08-28 (개발 점수)

```
판정   REDESIGN_ROUND_LIMIT_REACHED
       동결 gate 6개 중 A·D 통과, B·C·E·F 실패
       ROUND 3 없다. fresh confirmation 열지 않는다
```

```
공식 결과 불변
  M8 evaluation COMPLETE · M8 acceptance FAIL
  C1 FAIL 4/8 · C2 0.3311 · C3 max 7.00
  official artifacts changed: NO
```

gate는 실행 전에 동결됐다(`M8_REDESIGN_R2_GATE_2026-08-28.md`, 커밋 `6aa8803`).
결과를 보고 기준을 고치지 않았다. baseline lineage 8/8 바이트 일치 확인 후 비교했다.

---

## 1. Candidate gate 판정

| # | 조건 | baseline | ROUND 2 | 결과 |
|---|---|---|---|---|
| A | unmatched GT < 22 | 22 | **10** | **PASS** |
| B | unmatched generated ≤ 47 | 47 | **76** | **FAIL** |
| C | C3 max ≤ 7.00 | 7.00 | **13.00** | **FAIL** |
| D | median alignment > 0.3311 | 0.3311 | **0.4498** | **PASS** |
| E | 새 `repetition_loop` 0편 | 0편 | **1편** | **FAIL** |
| F | 새 catastrophic 없음 | C1 4편 | **C1 5편** | **FAIL** |

---

## 2. 3-way 비교

```
metric                    baseline   ROUND1   ROUND2
unmatched GT                    22       10       10
short unmatched GT              18       10       10
generated total                 93      219      134
unmatched generated             47      161       76
raw events/chunk median        2.0      5.5      4.5
alignment median            0.3311   0.3892   0.4498
C3 max                        7.00    16.00    13.00
rejections                      11       44       21
zero-event chunks                1        3        5
chunk retries                    5        3        5
split attempts                   0        3        5
split recovered                  0        3        5
C1 PRESENT 편수                   4        3        5
repetition_loop 편수              0        1        1
non-Korean event titles          2        1        0
```

```
거부 사유
  baseline  too_many_evidence 6 · evidence_outside_span 4 · bad_span 1        (11)
  ROUND1    thin_description 25 · too_many_evidence 16 · bad_span 2 · outside 1 (44)
  ROUND2    thin_description 15 · too_many_evidence 4 · bad_span 2             (21)
```

### 2-1. 편별

```
video                    GT  생성B  생성2  미생B  미생2    alB    al2   cmB   cm2  C1
baekmansonghee_jirisan    7    15    15     9     8  0.520  0.588  2.14  2.14  ABS→PRE
softyeon_ceramics        12     6    20     0     8  0.217  0.578  0.50  1.67  ABS→PRE
jissi_farm               11    11    32     3    23  0.428  0.428  1.00  2.91  ABS→ABS
kbs_banff                10    14    18    12    11  0.102  0.398  1.40  1.80  PRE→PRE
wonyi_gyeongju           10    16    10     7     3  0.561  0.315  1.60  1.00  ABS→ABS
wonyi_geoje               8    10     8     3     1  0.547  0.661  1.25  1.00  PRE→ABS
m8c2_3I7oGwk6EaQ          1     7    13     6    12  0.225  0.347  7.00 13.00  PRE→PRE
m8c2_cIxG7OHYMPU          9    14    18     7    10  0.234  0.472  1.56  2.00  PRE→PRE
```

---

## 3. H1은 절반만 작동했다

### 3-1. 수렴은 실제로 일어났다

```
consolidation 합계
  후보 311 → 사건 172 (-45%)
  그룹 87 · 병합 그룹 60 · singleton 27 · 최대 그룹 15
  invalid grouping 4 / 54 호출 (7.4%) — 전부 fail-closed로 원본 유지
```

ROUND 1 대비 생성 219 → 134, 미매칭 생성 161 → 76, 거부 44 → 21로 전부 절반 수준이
됐다. alignment median은 0.3892 → 0.4498로 올랐고 **8편 중 6편에서 상승**했다
(baseline 대비로도 6편 상승).

`wonyi_gyeongju`·`wonyi_geoje`는 생성 수가 baseline **아래**로 내려가고
Compression이 1.00이 됐다 — 수렴이 의도대로 먹은 사례다.

### 3-2. 그러나 baseline 수준으로는 돌아오지 못했다

```
unmatched generated   47 → 76   (+62%)
C3 max              7.00 → 13.00
```

수렴 폭이 영상마다 크게 다르다.

```
잘 먹은 편    wonyi_gyeongju 28→10 · wonyi_geoje 17→9 · kbs_banff 55→22
덜 먹은 편    jissi_farm 59→42  → 최종 생성 32 (baseline 11의 3배)
              m8c2_3I7oGwk6EaQ 35→15 → Compression 13.00
```

`jissi_farm`이 B·C 실패의 최대 기여자다. baseline에서 이미 `RELATIVELY_STABLE`
(생성 11 · Compression 1.00)이던 편이 R1의 고재현율 압력으로 59후보까지 늘고,
수렴이 42까지만 줄여 최종 32가 됐다. **원래 문제가 없던 영상을 망쳤다.**

`3I7`은 GT가 1건이라 어떤 수렴 폭으로도 Compression을 못 맞춘다 —
ROUND 1 분석의 H4 가설이 그대로 유지된다.

### 3-3. E·F 실패는 두 원인이다

```
repetition_loop   m8c2_cIxG7OHYMPU 1편. V3 규칙 10을 넣었지만 막지 못했다
early_stop        4편 — **전부 분할로 회수된 청크다**
```

```
video                    early_stop  splits  recovered
baekmansonghee_jirisan      PRESENT       1          1
softyeon_ceramics           PRESENT       1          1
kbs_banff                   PRESENT       2          2
m8c2_3I7oGwk6EaQ            PRESENT       1          1
```

`detect_early_stop`이 `chunk_retries`의 `recovered:false`만 보고 `chunk_splits`의
회수를 모른다 — ROUND 1에서 기록한 구현 결함 그대로다. **전향적 amendment를
적용하면 이 4편은 파국이 아니다.**

그 경우에도 F는 통과하지 못한다 — `repetition_loop`가 baseline 0편에서 1편으로
늘었고, 그것은 amendment와 무관한 새 파국이다. **판정을 구하려고 amendment를
당겨 적용하지 않는다.**

### 3-4. R6은 목표를 달성했다

```
비한국어 사건명 2 → 1 → 0
```

성공 기준에 넣지 않기로 한 항목이지만 결과는 기록한다.

---

## 4. 원인 해석

```
OBSERVED
  O1  수렴 후보 311→172(-45%). 그래도 최종 생성 134 > baseline 93
  O2  jissi_farm 생성 11→32, Compression 1.00→2.91 (원래 정상이던 편)
  O3  invalid grouping 4/54. fail-closed로 그 청크는 원본 유지
  O4  early_stop 4편이 전부 분할 회수분
  O5  repetition_loop 1편 잔존 (V3 규칙 10에도)
  O6  alignment 8편 중 6편 상승, wonyi_gyeongju만 0.561→0.315 하락

SUPPORTED INTERPRETATION
  S1  H1 방향은 옳다 — 같은 압력에서 수렴만 추가해 R1 대비 모든 과분할 지표가
      절반이 됐다. 그러나 **수렴 강도가 부족하고 영상별로 편차가 크다**
  S2  R1의 고재현율 압력은 **원래 정상이던 영상까지 악화시킨다**(O2).
      recall을 전역으로 올리는 방식 자체에 비용이 있다
  S3  프롬프트 규칙 한 줄로는 반복 생성을 막지 못한다(O5) — ROUND 1에서
      consolidation 없이 났던 문제가 규칙 추가 후에도 남았다
  S4  R5는 기능하지만 evaluator가 그 성과를 반영하지 못한다(O4)

HYPOTHESIS (검증 안 함)
  H5  수렴을 청크 단위가 아니라 영상 전체 후보에 한 번 더 적용해야 할 가능성
  H6  고재현율을 전역으로 켜지 말고 **짧은 사건이 실제로 누락된 구간에만**
      적용하는 선택적 방식이 필요할 가능성
  H7  반복 생성은 생성 파라미터(no_repeat_ngram 등)로 다뤄야 할 가능성
```

---

## 5. 이 결과로 하지 않은 것

```
gate 기준 변경                    하지 않았다
공식 결과·판정 변경                하지 않았다
prospective amendment 당겨 적용     하지 않았다 (§3-3)
추가 프롬프트·병합·임계 튜닝         하지 않았다
ROUND 3                          하지 않는다
fresh panel sourcing · 새 라벨      하지 않았다
M9 · official test · push          하지 않았다
```

---

## 6. 사용자 결정이 필요한 것

개발 라운드 상한(2회)에 도달했다. 규격 §18에 따라 다음 셋 중 하나를 선택해야 한다.

```
① M8 redesign 종료 — acceptance FAIL을 최종 결과로 확정하고 한계로 보고
② FAIL 상태를 유지한 채 M9까지 수행 (test-opening 별도 승인 사건)
③ 프로젝트 범위 재정의 — H5~H7을 별도 사전등록으로 다루거나 향후과제로 이관
```

**어느 쪽이든 지금 상태의 redesign 후보를 fresh confirmation에 보내지 않는다.**
gate 4개가 실패했고, 그중 B·C는 baseline보다 나쁘다.
