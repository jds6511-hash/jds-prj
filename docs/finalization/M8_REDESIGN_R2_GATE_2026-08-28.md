# M8 REDESIGN ROUND 2 — development candidate gate (실행 전 동결)

**이 문서는 ROUND 2를 실행하기 전에 작성·커밋한다.** 결과를 본 뒤 기준을 고치지
않기 위해서다. ROUND 1 수치에 맞춰 기준을 만들지도 않았다 — 전부 **official
baseline** 대비다.

```
이것은 official acceptance gate가 아니다.
official gate는 C2 median >= 0.70 · C3 max <= 2.0 이고 그것은 fresh N=8만 판정한다.
이 gate는 "새 버전을 fresh confirmation에 보낼 가치가 있는가"만 본다.
```

---

## 1. FREEZE_CANDIDATE 조건 — 6개 전부 만족해야 한다

| # | 조건 | baseline | 의미 |
|---|---|---|---|
| A | `unmatched GT < 22` | 22 | short-event recall 개선 유지 |
| B | `unmatched generated <= 47` | 47 | fragmentation 악화 금지 |
| C | `C3 max <= 7.00` | 7.00 | compression 악화 금지 |
| D | `median event_temporal_alignment > 0.3311` | 0.3311 | alignment 개선 |
| E | 새 `repetition_loop` **0편** | 0편 | ROUND 1이 만든 파국 제거 |
| F | 새 catastrophic failure 없음 | — | 부작용 금지 |

하나라도 실패하면 판정은 **`REDESIGN_ROUND_LIMIT_REACHED`**이고 ROUND 3는 없다.

`0.70`·`2.0`을 이 단계에서 맞추려 하지 않는다. 소비된 패널에서 그 값을 맞추는 것은
확증이 아니고, 맞추려는 시도 자체가 튜닝이다.

ROUND 1은 이 기준으로 B(161 > 47) · C(16.00 > 7.00) · E(1편) 세 개가 실패했다.

---

## 2. ROUND 2에서 바꾸는 것

```
채택   H1  고재현율 추출 → **보수적 consolidation** → 기존 canonical 파이프라인
      R1  짧은 독립 사건 보존 (ROUND 1 그대로)
      R5  빈 청크 1단 분할 재시도 (ROUND 1 그대로) + split_recovered 기록
      R6  사건명 한국어 지시 유지 (성공 기준에 넣지 않는다)
      신규 pre-merge 중복 억제 규칙
보류   H2 개수 상한 · H3 2층 schema · R3 span · R4 거부→절단 · R7 C3 amendment
```

**외부 schema를 바꾸지 않는다.** `report.json` 계약과 M9의 `sent_id`·`cites`는 그대로다.

### 2-1. consolidation 위치

```
raw generation → parse_events → **CONSOLIDATION** → validate_events → merge_events → sentences
```

`validate_events`가 청크별로 `thin_description`·`too_many_evidence`를 거부하고,
ROUND 1에서 그 두 사유가 41건이었다. 그래서 consolidation을 **거부보다 앞**에 둔다.

**한계를 미리 적는다 — consolidation은 청크 안에서만 한다.** 청크를 넘는 통합은
기존 deterministic `merge_events`(이름 일치 + span 인접)가 담당하고, 그 규칙은
바꾸지 않는다. 청크 경계를 걸친 과분할은 이 라운드에서 해결되지 않는다.

### 2-2. consolidation 계약

새 사건을 발명하는 단계가 **아니다.** LLM은 후보 내용을 새로 쓰지 않고
**기존 후보 ID의 그룹만** 출력한다.

```
허용   시간적으로 인접·연속한 후보 중 같은 주요 활동의 내부 단계를 한 그룹으로
      명백한 중복 후보를 한 그룹으로
금지   새 사건 추가 · 후보 추가 분할 · 비인접 시간대 임의 병합 ·
      증거 밖으로 span 확장 · 임베딩/유사도 임계 신설 · 별도 judge 임계
```

**fail-closed.** 입력 후보는 정확히 한 그룹에 한 번씩 나와야 한다. 누락·중복·미지
ID가 있으면 그 청크의 consolidation을 **적용하지 않고**(전부 singleton) 진단에
기록한다.

### 2-3. 합쳐진 사건을 만드는 규칙 — 전부 deterministic

```
span         [min(member start), max(member end)]  — 멤버 범위 밖으로 나가지 않는다
title        span이 가장 긴 멤버의 이름 (동률이면 가장 앞선 것)
description  멤버 서술을 순서대로 이어 붙이고 완전 중복만 제거
evidence     멤버당 대표 1개를 뽑고, 4개를 넘으면 그룹 span에 고르게 분포하도록
             최대 4개를 고른다
```

**evidence 선택이 R4가 아니라는 것을 분명히 한다.**

```
R4 (보류)   이미 거부된 후보의 evidence를 잘라 **되살리는** 것
여기        새로 합쳐진 후보의 evidence를 사전등록 규칙 1
            ("대표 근거만 최대 4개, 범위 안 번호를 전부 나열하지 말 것")대로
            **구성하는** 것
```

전자는 validator 판정을 우회하고 후자는 생성 계약을 따른다. 다른 연산이다.

`validate_events` 의미는 그대로다 — 합친 결과가 거부되면 거부되고, 진단에 남는다.

### 2-4. 중복 억제 (신규)

ROUND 1에서 `wonyi_gyeongju`에 연속 4회·6회 동일 단위 반복이 생겼다.
consolidation으로 지울 수 있지만 **C1은 병합 전 원본을 보므로 숨겨지지 않는다.**
그래서 생성 계약에 한 줄을 넣는다.

```
"이미 출력한 것과 실질적으로 동일한 사건을 반복해서 다시 출력하지 않는다.
 새로운 독립 사건이 없으면 출력을 종료한다."
```

**C1 `repetition_loop` 기준은 바꾸지 않는다** — 병합 전 원본 · 정규화 완전일치 ·
연속 3회. post-consolidation으로 C1을 가리지 않는다.

### 2-5. R5 recovery semantics

```
retry 실패 → 1단 분할 → 분할이 회수 → split_recovered = true 기록
```

전향적 evaluator에서는 회수된 청크를 `early_stop`·`generation_hole` 실패로 세지
않는다. **공식 과거 C1은 변경하지 않는다**(공식 실행에는 분할이 없었다).
이 항목을 `M8_C1_PROSPECTIVE_AMENDMENT`에 추가한다.

---

## 3. 실행 경계

```
대상        소비된 N=8만 (development evidence)
run_kind    m8_redesign_dev_round2
금지        official path 덮어쓰기 · ROUND 1 산출물 덮어쓰기 ·
            fresh panel sourcing · 새 라벨 · M9 · official test · push
비교        baseline / ROUND 1 / ROUND 2  3-way
```

---

## 4. 판정

```
FREEZE_CANDIDATE                §1의 A~F **전부** 만족
REDESIGN_ROUND_LIMIT_REACHED    하나라도 실패
IMPLEMENTATION_BLOCKED          큰 재작성 없이는 §2-1을 만족할 수 없을 때
```

ROUND 3 자동 진행은 없다. 실패 시 추가 프롬프트·병합·임계 튜닝을 하지 않고
사용자 결정을 요청한다.
