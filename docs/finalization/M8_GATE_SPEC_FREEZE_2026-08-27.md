# M8 관문 C1·C3 operationalization 동결 — 2026-08-27

사전등록 `M8_구조변경_사전등록_2026-08-16.md` §2-2·§2-3이 **지표와 임계는 정했지만
집행 방법을 비워 둔** 두 자리를 채운다. 이 문서는 사전등록을 수정하지 않는다 —
사전등록이 남긴 공백만 채우고, 사전등록과 충돌하는 결정은 **기각 사유와 함께** 적는다.

`m8_metrics.c3_verdict`가 집계 통계량 없이 호출되면 `GateSpecError`로 거부한다.
그 거부를 푸는 근거가 이 문서다.

---

## 0. 결과를 보기 전이라는 증거

```
확인 시점    2026-08-27
git HEAD    0e2f64a8e955ddbc074946b01692abd72d09ddcc
패널 8편 M8/M9 산출물          0건 (results/ · work/ 전수 glob)
패널 8편 GT 동결(FROZEN_*.json) 0편
Event Recall · Compression 실측값   없음
```

**즉 이 문서의 어떤 문장도 M8 수치를 보고 쓴 것이 아니다.** GT 라벨(8편 68건)은
DRAFT 상태로 존재하지만, 그것은 관문의 **분모**이고 M8 출력이 아니다.

C1·C3 코드 구현은 GT 동결 이후로 미룬다(순서는 §5). 구현이 늦어지는 것과 규격이
늦어지는 것은 다르다 — 규격은 여기서 닫힌다.

---

## 1. C1 — Catastrophic failure

사전등록 §2-2: "다른 언어 이탈·조기 종료·반복 루프 발생 **영상 수**", §2-3: "**0편**".
유형 3개와 임계 0은 이미 동결돼 있다. 비어 있던 것은 **각 유형을 무엇으로 판정하는가**다.

### 1-1. 판정 규격

```
catastrophic_video = 세 유형 중 하나라도 PRESENT
C1 PASS            = catastrophic_video 0 / 8
```

| 유형 | PRESENT 조건 | 판정 성격 |
|---|---|---|
| `language_drift` | 한국어 보고서를 생성해야 하는데, 하나 이상의 **완결된 문장 또는 연속 출력 구간**이 다른 언어로 전환되어 한국어 서술 기능을 상실 | categorical (사람) |
| `early_stop` | 정상 report completion 전에 생성이 종료되어 schema상 필요한 출력의 뒷부분이 만들어지지 않음 | 기계 우선 |
| `repetition_loop` | **정규화 후 완전 동일한** 보고서 문장이 연속 3회 이상 반복되어, 정상 서술 대신 생성 루프가 됨 | 기계 |

### 1-2. 새로 만들지 않는 것

**비한글 문자 비율 임계를 만들지 않는다.** "비한글 10%면 drift" 같은 규칙은 외부 근거가
없고, **간판·고유명사 때문에 오탐**한다. Qwen 캡션에서 이미 관측된 외국 문자 혼입은
C1이 잡을 실패가 아니다 — C1은 훨씬 큰 실패를 잡는 관문이다. 따라서
`language_drift`는 **문장 안에 외국 문자가 섞인 것**과 **생성 언어 자체가 바뀐 것**을
가르는 categorical 판정으로 둔다.

다음은 `language_drift`가 **아니다.**

```
고유명사 · 짧은 외국어 인용 · 화면 속 실제 문자 · 단일 외래어
```

**임베딩 유사도 임계를 만들지 않는다.** `repetition_loop`는 정규화 후 완전 일치만
본다. paraphrase 반복("비슷해 보인다" 수준)은 **diagnostic으로 기록하되 C1
catastrophic에 넣지 않는다** — 유사도 임계를 새로 도입하면 사전등록에 없는 규칙이
관문 안으로 들어온다.

`3회`만 숫자가 들어간다. "사건이 실제로 반복된다"와 "생성 루프"를 가르는 최소
operational boundary이고, **결과를 보기 전에** 여기서 고정한다.

### 1-3. 구현 요구사항 2건

```
① repetition_loop는 m8_report._merge_events **이전 raw generation**에서 판정한다.
```

`_merge_events`(src/m8_report.py:445)는 같은 이름 + span 인접인 사건을 합친다.
병합 후 산출물에서 반복을 세면 **파이프라인이 지워 준 파국을 PASS로 읽는다.**

```
② 세 유형 모두 PRESENT / ABSENT / UNCLEAR **3-state**로 저장한다.
   UNCLEAR는 PASS로 떨어지지 않는다.
```

boolean 하나로는 "판정 못 했다"를 표현할 수 없고, 표현할 수 없으면 조용히 ABSENT가
된다. `language_drift`가 사람 판정이라 이 자리가 실제로 생긴다.

---

## 2. C3 — Compression

### 2-1. 확정 규격

```
video_compression  = 해당 영상의 M8 리포트 문장 수 / 그 영상의 reference event 수
panel_statistic    = 8편 video_compression의 MAX
C3 PASS            = MAX <= 2.0
```

**지표 정의는 사전등록 §2-2 그대로다**(`리포트 문장 수 / 정답 사건 수`).
채운 것은 §2-3이 비워 둔 **8편 집계 통계량**뿐이고, 그것을 `MAX`로 둔다.

`MAX`인 이유: 사전등록 문구가 "정답 사건 하나를 두 문장 넘게 쓰지 않는다"이므로,
한 편이라도 넘으면 그 문구가 깨진다. 중앙값은 8편 중 최악을 숨긴다.

### 2-2. 기각 — per-event compression 재정의

2026-08-27에 `event_compression = 해당 reference event에 매칭된 문장 수`,
`video = max(event)`, `panel = max(video)` 안이 제시됐고 **기각했다.** 사유 둘.

**① 사전등록 공식을 바꾼다.** §2-2가 영상 단위 비율로 동결했고, §2-3 괄호는
근거 서술이지 공식이 아니다.

**② 관문을 무력화한다.**

```
src/m8_report.py:465   events_to_sentences   생성 사건 1개 = 문장 정확히 1개
src/m8_metrics.py:37   match_events          Hungarian 1:1 · 겹침 0이면 안 맺음
```

정답 사건 하나에 매칭되는 생성 사건이 최대 1개이므로 `event_compression ∈ {0, 1}`이고,
`max <= 2.0`은 **어떤 리포트에서도 무조건 PASS**다.

기각했지만 **문제의식은 실재한다.** 현 구조에서 그 현상은 "한 사건이 4~5문장으로
쪼개짐"이 아니라 **여러 생성 사건이 같은 정답 사건 시간대에 몰림**으로 나타나고,
1:1 매칭이 남는 것들을 미매칭으로 떨어뜨린다. 결과적으로 영상 전체 문장 수가 부풀고,
그것은 **사전등록 정의의 영상 단위 Compression에 그대로 잡힌다.**

### 2-3. 진단으로 옮긴 것

per-event 쪼개짐·중복은 관문이 아니라 **기존 지표로 보고**한다.

```
Redundancy                같은 정답 사건을 여러 문장이 중복 서술한 비율   (사전등록 §2-2)
event_alignment_types     overmerge · spurious_event                  (m8_metrics)
```

### 2-4. 기각 — median / mean

`c3_verdict`가 세 통계량을 받지만 `median`·`mean`은 쓰지 않는다. C2가 중앙값인 것은
**Event Recall의 영상 간 편차 ±48%p**가 근거이고(사전등록 §2-3), 그 근거가 C3로
전이되지 않는다. C2와 C3가 다른 통계량을 쓰는 것은 불일치가 아니라 근거가 다른 것이다.

---

## 2A. C2 — 판정 지표 명확화 (ambiguity resolution)

C1·C3를 구현하면서 **C2에 빈 연결고리가 있다는 것을 발견했다.** 임계·통계량은
동결됐지만 `median`에 넣을 per-video 값이 식으로 특정돼 있지 않았다.
아래는 그 해소 기록이고, **M8 공식 출력을 보기 전에 적었다**(§0 실측 참조).

### 2A-1. 무엇이 어긋나 있었나 — 그대로 남긴다

```
원 사전등록 §2-3   "C2 = Event Recall 중앙값 >= 0.70"   ← 이름만, 식 없음
보충 §3-3         주  event_temporal_alignment
                     = reference event별 매칭 temporal IoU의 macro 평균
                       (매칭 실패 = 0), 연속값 [0, 1]
                  부  IoU >= θ event recall — "θ = 0.3 · 0.5 · 0.7 **세 값 모두
                     보고**, 하나를 고르지 않는다"
```

**"원래부터 명백했다"고 쓰지 않는다.** §2-3이 지목한 `Event Recall`이라는 이름과
§3-3의 주지표/부지표 정의 사이에 용어 불일치가 실제로 있었다.

### 2A-2. 확정

```
per-video 지표   event_temporal_alignment
패널 통계량      8편의 중앙값        ← 변경 없음
임계            >= 0.70            ← 변경 없음
C2 PASS         median(event_temporal_alignment across 8) >= 0.70
```

θ별 recall 3종은 **전부 계산해 보고하되 acceptance verdict에 쓰지 않는다.**
`m8_gates.panel_verdict`에 넘기면 `GateSpecError`로 거부한다.

### 2A-3. 왜 θ recall을 쓰지 않는가

**① §3-3 문구와 직접 충돌한다.** "세 값을 모두 보고하고 하나를 고르지 않는다"가
동결돼 있는데 그중 하나를 관문에 쓰면 그 조항을 어긴다.

**② θ=0.3은 이미 값을 본 자리다.** 2026-08-18 dev 예비 실행에서 `0.3019`가
관측됐다. 다른 사유를 대더라도 사후에 특정 θ를 골랐다는 공격을 피할 수 없다.

**③ 사전등록 안에 이미 위계가 있다.** 새 지표를 발명하는 것이 아니라, §2-3의
모호한 shorthand를 뒤쪽의 더 구체적인 metric specification으로 해석하는 것이다.
연속값이라 기존 `0.70`과 수학적으로도 호환된다.

### 2A-4. 미매칭 정답 사건 처리 — 새로 고르지 않았다

macro 평균에서 미매칭을 0으로 넣는지, matched만 평균내는지에 따라 값이 크게
달라진다. **이 정의는 이미 존재했고 그대로 쓴다.**

```
docs/preregistration/M8_event지표_보충_2026-08-18.md §3-3   "(매칭 실패 = 0)"
src/m8_metrics.py:65  event_temporal_alignment            "매칭 실패는 0으로 센다"
src/m8_metrics.py:59  matched_ious                        미매칭에 0.0을 넣는다
```

문서와 구현이 일치한다. 테스트로 고정했다(`refs 2개 · 1개만 매칭 → 0.5`).
정답 사건이 0개면 `0.0`이 아니라 `None`(측정 불가)인 것도 기존 정의 그대로다.

### 2A-5. 이 결정의 성격

```
아님   임계 변경 · 통계량 변경 · 새 지표 발명 · 사전등록 수정
임     사전등록 내부의 주지표/부지표 위계를 따라 빈 연결고리를 채운 것
       (ambiguity resolution, methodology amendment 아님)
```

---

## 3. 임계의 근거가 약하다는 것을 다시 적는다

사전등록 §2-4가 이미 자백했다 — **0.70·2.0에 외부 근거가 없다.** 이 문서가 추가한
`MAX`와 `3회`에도 외부 근거가 없다. 결과와 함께 이 사실을 병기하고,
**결과가 나빠도 고치지 않는다.**

---

## 4. 이 문서가 정하지 않은 것

```
C2 임계·통계량               이미 동결 (0.70 · median)
M9 실행 권한                 test-opening 별도 승인 사건
39→72 확장                   HOLD
```

C2 판정 지표는 구현 중 미결로 발견했고 **같은 날 §2A에서 해소했다** —
M8 출력 0건 시점이다.

### 4-1. 미구현 — Redundancy

사전등록 §2-2의 부지표 `Redundancy`(같은 정답 사건을 여러 문장이 중복 서술한 비율)는
구현돼 있지 않다. `m8_gates`는 기계로 셀 수 있는 미매칭 수
(`unmatched_reference_events` · `unmatched_generated_events`)만 후보로 보고한다.
`EVENT_ALIGNMENT_TYPES`(overmerge·spurious_event 등)는 **사람이 붙이는 라벨**이고
자동 판정기가 아니다.

---

## 5. 순서 (확정)

```
1  사람 consistency review 1회        label_kit/event_inventory/consistency_review.md
2  명백한 rule-application error만 수정 → 재내보내기 → validate
3  8편 GT freeze                      FROZEN_{video_id}.json
4  per-file SHA256 + aggregate GT hash 기록
5  C1·C3 구현 + edge tests            규격은 이 문서 §1·§2
6  evaluator freeze / hash
7  M8 official generation             ← 여기서 처음으로 M8 출력을 본다
8  C1/C2/C3 판정
9  evaluation COMPLETE · acceptance PASS/FAIL 분리 기록
```

`evaluation COMPLETE`와 `acceptance PASS`는 분리한다
(`M8_M9_DECISIONS_2026-08-26.md` D2-1).
