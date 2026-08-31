# v2.1 Gate C — preflight · 티켓 분해 (2026-08-31)

Gate C = **정본과 표현의 분리**. `HLT · REF · GLS · RPT`.

Gate A·B와 다른 점이 하나 있다. **여기서는 새 기능보다 우회 경로 차단이 먼저다.**
OPEN-11이 non-blocking인 것은 "grounding을 지나야만 내용이 밖으로 나간다"는 전제
위에서고, 그 전제를 깨는 코드가 들어올 수 있는 층이 바로 Gate C다.

---

## PREFLIGHT

### P1 저장소 상태

```
HEAD          2ace134  feat: v2.1 Gate B CLOSURE
tree          clean
tests         3211 passed / 1 skipped
Gate A · B    COMPLETE
push          2026-08-31 사용자 승인 1회 실행 (origin/master = 2ace134)
```

### P2 Gate C의 입력이 실재하는가

```
정본 문서     src/v2_1_aar.py  build_aar_canonical · validate_aar · load_aar
              schema  aar_canonical_v2_1
              episode key 14종 (episode_id … grounding_status · grounding_reasons)
표현 어휘 차단 _PRESENTATION_KEYS 7종이 정본에 못 들어오게 이미 막혀 있다
판정 상태     PASS · NOT_APPLICABLE · FAIL_{REFERENCE, OUTSIDE_EPISODE,
              INELIGIBLE_SUPPORT, NO_SUPPORT, UNSUPPORTED}
```

**중요 — 정본에는 이미 grounding이 적용된 상태로 실린다.** `apply_grounding`이
FAIL·NOT_APPLICABLE에서 `dialogue_note`를 제거하므로, 정본만 읽는 표현 계층은
제거된 dialogue를 **볼 수 없다.** 위험은 정본을 우회해 뒤로 손을 뻗는 경로다.

### P3 Gate C acceptance 규모

```
HLT   8      REF   6      GLS   7      RPT   8      합계 29
P0   19      P1   10
```

### P4 우회 가능 표면 — 표현 계층이 손대면 안 되는 것

```
v2_1_content     EpisodeContent · EpisodeResult    grounding 이전 원문
v2_1_binding     ContentBinding · CiteBinding      판정 이전 사실
v2_1_raw_store   RawStore                          모델 원출력
v2_1_parse       ParseResult                       구조만 통과한 값
v2_1_timeline    TimelineEntry                     자격 판정 전 근거
```

이 다섯이 **OPEN-11이 부활할 수 있는 경로 전부**다. C-01이 잠글 대상이다.

### P5 연구 경계 가드 (A-11) — 유효

```
REG-005 BCS core diff · REG-006 official test · REG-007 M9 artifact
REG-008 new human GT · REG-009 provider adoption · REF-003 gyeongju 자동 대조
```

`REF-003`은 matrix의 Gate C 항목이면서 **이미 A-11에서 기계 검증되고 있다.**
C-10에서 중복 구현하지 말고 그 가드를 근거로 집계한다.

### P6 형식 참조

```
docs/finalization/REPORT_FORMAT_REFERENCE_2026-08-30.md    존재
사용 범위   섹션 구조·표 형식만 (REF-006)
금지        행 수 목표 (REF-005) · boundary 튜닝 근거 (REF-004) · GT 취급 (REF-002)
```

---

## 티켓 분해

```
C-01  Presentation input contract      RPT-001 · RPT-005 · OPEN-11 interlock   COMPLETE
C-02  Highlight Builder core           HLT-002 · 003 · 004 · 005 · 006 · 007   COMPLETE
C-03  Highlight provenance             HLT-001 · RPT-002
C-04  Global Synthesis contract        GLS-001 ~ 007
C-05  Presentation schema              REF-001 · 002 · 005 · 006
C-06  Preview / Markdown renderer      RPT-001 · RPT-003 · RPT-008 + RPT-004 integration
C-07  HWPX renderer                    RPT-003 · RPT-004
C-08  Failure / fallback               RPT-006 · RPT-007 · HLT-008
C-09  OPEN-11 end-to-end regression    matrix ID 없음 — closure 조건
C-10  Gate C acceptance mapping        29건 집계 (REF-003 · 004는 기존 가드 인용)
                                       RPT-004 최종 PASS는 여기서 집계한다
```

### ownership 정정 (2026-08-31 · 사용자)

```
RPT-004   C-05에서 닫지 않는다 — "MD와 HWPX의 formatting 차이 허용"은 renderer 간
          성질이라 두 renderer가 실재해야 확인된다
          C-06 · C-07에서 integration coverage · C-10에서 최종 PASS
RPT-003   C-06 · C-07 양쪽에서 확인한다 — renderer-side boundary 생성 금지는
          Markdown만 지켜서 되는 규칙이 아니다
          acceptance ID 하나에 테스트 둘이 붙는 것은 정상이다
RPT-001   C-01에서 architecture contract로 닫고, C-06에서 renderer integration
          regression으로 다시 본다
REF-003
REF-004   C-10에서 재구현하지 않는다 — A-11 가드가 해당 ID를 명시적으로 덮는다
```

구현 순서는 위 순서 그대로다. **C-01을 먼저 잠그지 않으면** 이후 builder·renderer가
실수로 pre-grounding 데이터를 읽어도 그것을 잡을 구조가 없다.

### C-01이 해야 하는 것 — 두 층

```
층 1  import 차단     표현 모듈은 P4의 다섯 모듈을 import조차 하지 않는다
                      (A-09가 A-08을 import하지 않게 한 것과 같은 논리)
층 2  데이터 차단     입력은 검증을 통과한 aar_canonical 문서 하나뿐이고,
                      grounding이 제거한 dialogue를 실은 문서는 **거부**한다
```

층 2가 필요한 이유는 층 1이 **정직한 코드만 막기 때문**이다. 정본을 손으로 고치거나
앞 계층 버그로 FAIL인데 dialogue가 남은 문서가 들어오면 import 가드는 아무것도
못 한다. 표현 계층 입구에서 그 조합 자체를 거부해야 한다.

### C-01이 하지 않는 것

```
highlight 생성 · label 생성 · 섹션 매핑 · 렌더링 · fallback 정책
analysis_mode interlock (RPT-008은 C-06 renderer 소관 — A-02에 이미 구현돼 있다)
```

---

## Gate C closure 조건 (미리 적는다)

```
matrix acceptance   P0 19/19 · P1 10건 (PASS 또는 등록된 waiver)
OPEN-11             C-09 회귀로 "제거된 dialogue가 표현에 재등장하지 않음" 확인
연구 경계           A-11 가드 전부 유지 · baseline 무수정
```

Gate B에서 배운 대로 **matrix 통과와 closure를 같은 것으로 취급하지 않는다.**

---

## C-01 Presentation input contract  **COMPLETE**

```
산출물   src/v2_1_presentation_input.py
         tests/test_v2_1_presentation_input.py (17 tests)
```

입구는 하나다.

```python
presentation_input(document) -> PresentationInput
```

`document`는 **검증을 통과한 aar_canonical 문서**여야 한다. 통과하지 못하면
`PresentationInputError`이고, 표현 계층은 시작조차 하지 않는다.

### 층 1 — import 차단

`FORBIDDEN_UPSTREAM` 다섯 모듈(`content · binding · raw_store · parse · timeline`)을
표현 모듈이 import하지 않는지 **AST의 import 문만 보고** 검사한다. 문자열 상수나
주석이 자기 가드를 건드리지 않게 하기 위해서다(A-10 · A-02에서 두 번 겪었다).

### 층 2 — 데이터 차단 (OPEN-11 interlock)

```
grounding_status != PASS  이고  dialogue_note is not None   →  거부
```

정본에는 이미 `apply_grounding`이 적용돼 실리므로 정상 경로에서는 이 조합이
나올 수 없다. **그래서 이 검사가 잡는 것은 정상 경로가 아니라 우회다** — 정본을
손으로 고쳤거나 앞 계층 버그로 dialogue가 살아남은 문서.

### 표현이 볼 수 있는 것

`PresentationEpisode` 필드 12종. `raw` · `raw_ref` · `store` · `timeline` ·
`binding` · `cites` · `evidence` · `parse_result` 같은 **되돌아갈 손잡이는 없고,
없다는 것을 테스트가 지킨다.**

### 판정하지 않는다

`grounding_status`를 그대로 옮긴다. 실패한 episode를 버리지 않는다 — 구조와
summary는 유지되고 dialogue만 없다. A-06 timeline이 A-05 판정을 통과시키기만 한
것과 같은 규율이다.

### 중복 가드 하나를 제거했다

처음에 `schema` 검사를 입구에서 다시 했다. 주입 시험에서 **그 검사를 지워도
테스트가 green**이었다 — `validate_aar`가 이미 같은 것을 보기 때문이다. 규칙이
두 곳에 있으면 갈라지므로 지웠다. 주인은 `validate_aar` 하나다.

### 주입 시험 (가드에 이빨이 있는가)

```
interlock 제거              RED
validate_aar 생략           RED
상류 모듈 import 추가        RED
raw 손잡이 필드 노출         RED
schema 검사 제거            GREEN  → 중복이라 판단하고 제거 (위 참조)
```

### 하지 않은 것

```
highlight 생성 · label · 섹션 매핑 · 렌더링 · fallback 정책
RPT-008 analysis_mode interlock — C-06 renderer 소관 (A-02에 구현돼 있다)
```

---

## C-02 Highlight Builder core  **COMPLETE**

```
산출물   src/v2_1_highlight.py
         tests/test_v2_1_highlight.py (22 tests)
```

```python
build_highlights(presented: PresentationInput, specs) -> tuple[Highlight, ...]
```

입력은 `PresentationInput` **하나뿐**이다. C-01이 이미 pre-grounding 접근과 제거된
dialogue 재등장을 막았으므로, 타입만 강제하면 그 안전성이 상속된다. **그래서
C-02는 OPEN-11을 다시 검사하지 않는다.**

### 두 구조는 규칙이 다르다

```
canonical    overlap 0 · gap 0 · exactly once · 시간순
highlight    중첩 허용 · 같은 episode 다중 참여 · 개수 자유
```

이 모듈은 **A-09 partition 검증기를 부르지 않는다.** highlight의 중첩을 canonical
기준으로 재면 v2.1 설계가 무너진다(SPEC §2). 검증한 실제 형태는 이것이다.

```
canonical   EP01 [0,3]   EP02 [4,7]   EP03 [8,11]
highlight   H01 = EP01+EP02           H02 = EP02+EP03      →  시간 중첩 · 정상
```

### 정본 불변을 기능으로 잰다

소스에 mutation 함수가 없다는 스캔이 아니라, **builder 실행 전후의 정본 지문을
대조**한다.

```
(episode_id · start_seg · end_seg · start_sec · end_sec) 전건 동일
episode 목록의 순서·개수 동일
frozen dataclass이므로 경계 쓰기 시도 자체가 예외
```

### HLT-004 — 개수는 입력을 따른다

숫자 9를 소스에서 찾는 방식으로 막지 않았다. 기능으로 확인한다.

```
episode 3개 구성 → highlight 3   |  episode 4개 구성 → highlight 4
전체를 하나로 묶기 → 1           |  묶음 없음 → 0
같은 episode로 12개 → 12         ← 상한을 두면 여기서 걸린다
```

소스 스캔(`target_count` 류 식별자 부재)은 **보조 가드로만** 둔다.

### segment_refs는 구성원의 것만이다

연속하지 않은 묶음(EP01+EP03)에서 사이의 EP02 구간을 highlight가 자기 것으로
주장하지 않는다. display_range는 최소 시작 ~ 최대 끝이지만, segment 소유는 별개다.

### 주입 시험 7종

```
중복 episode 검사 제거            RED
PresentationInput 타입 검사 제거   RED
없는 episode를 조용히 건너뜀       RED
gap까지 segment로 주장            RED
빈 묶음 허용                      RED
9행 상한 도입                     RED
display_range를 canonical 폭으로   RED
```

### 하지 않은 것

```
label · summary 생성      묶음을 만들 뿐, 문구는 만들지 않는다 (label은 받은 문자열 그대로)
grouping 정책             무엇을 묶을지는 호출자가 준다 — 자동 grouping은 이 티켓 범위 밖
provenance 직렬화         C-03
렌더링 · 서식             C-05 이후
```

`Highlight`에는 SPEC §4의 `summary` 필드를 두지 않았다. 문구 생성 주체가 정해지기
전에 필드만 만들면 누가 채우는지가 흐려진다 — C-03 · C-04에서 정한다.
