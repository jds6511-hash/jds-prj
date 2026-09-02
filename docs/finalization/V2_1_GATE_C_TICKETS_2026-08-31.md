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
C-03  Highlight provenance             HLT-001 · RPT-002   COMPLETE
C-04  Global Synthesis contract        GLS-001 ~ 007
C-05  Presentation schema              REF-001 · 002 · 005 · 006   COMPLETE
                                       + SPEC §4 Highlight.summary compatibility mapping
C-06  Preview / Markdown renderer      RPT-001 · RPT-003 · RPT-008 + RPT-004 integration   COMPLETE
C-07  HWPX renderer                    RPT-003 · RPT-004   COMPLETE
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

---

## C-03 Highlight lineage  **COMPLETE**

```
산출물   src/v2_1_lineage.py
         tests/test_v2_1_lineage.py (21 tests)
```

```python
build_lineage(presented, highlights) -> tuple[HighlightLineage, ...]
validate_lineage(records, presented) -> list[str]
serialize_lineage / load_lineage        schema  highlight_lineage_v2_1
```

**문장을 만들지 않는다.** summary · dialogue · claim · analysis 어느 것도 여기서
생기지 않고, 필드 자체가 없다는 것을 테스트가 지킨다.

### lineage는 grouping에서 파생한다

label이나 display_range에서 역추론하지 않는다. 표현을 손볼 때마다 provenance가
따라 움직이면 안 되기 때문이다. 비연속 묶음이 그 차이를 드러낸다.

```
grouping    EP01 + EP03
display     [EP01.start , EP03.end]   ← 이 범위 안에 EP02가 들어 있다
lineage     ("EP01", "EP03")          ← 역추론했다면 EP02가 섞인다
```

### 겹쳐도 각각 남는다

```
H01 = EP01 + EP02      H02 = EP02 + EP03
EP02는 두 lineage에 각각 명시적으로 기록된다 (공유 참조 하나로 접지 않는다)
```

### RPT-002 — 표현을 바꿔도 identity는 그대로다

```
highlight 순서 교체    canonical identity 불변 · 같은 episode의 source record 동일
label 전면 교체        source_episode_ids · sources · canonical_span 전부 동일
```

`SourceEpisode`는 canonical identity(`episode_id · start_seg · end_seg · start_sec ·
end_sec`)만 담는다. 내용은 담지 않는다.

### 상류 식별자는 provenance가 될 수 없다

`llm:000001` · `raw:asr:3` · `seg#3` · `"3"` 을 source로 넣으면 거부한다. 정본
episode로 해석되지 않는 것은 출처가 아니다.

### 주입 시험 7종

```
grouping 대신 시간 범위로 역추론    RED
없는 episode를 조용히 건너뜀        RED
빈 lineage 허용                    RED
source 순서를 정렬                 RED
validate가 아무것도 안 봄           RED
직렬화가 sources를 버림             RED
lineage에 label 필드 추가           RED
```

### SPEC §4 `Highlight.summary` — compatibility mapping

스펙에 필드가 있다는 것이 C-03이 그것을 생성해야 한다는 뜻은 아니다. **schema
ownership과 content-generation ownership을 가른다.**

```
final presentation schema      존재한다
C-02 · C-03                    생성하지 않는다 (필드 자체를 두지 않았다)
C-05                           필드의 존재·optional 여부를 스키마로 확정
population rule                canonical episode summary들의 결정적 조합에서 시작
금지                           source_episode_ids 없는 독립 claim 생성
                               여기서 새 LLM 생성을 넣으면 Gate C가 별도 grounding
                               문제를 다시 만든다 — 필요하다고 판단되면 별도 contract
```

### RPT-002의 나머지

renderer 간 identity consistency는 C-06 · C-07에서 다시 확인한다. C-03은 그것을
**가능하게 하는 lineage contract**를 닫는 단계다.

---

## C-04 Global Synthesis contract  **COMPLETE**

```
산출물   src/v2_1_synthesis.py
         tests/test_v2_1_synthesis.py (23 tests)
```

```python
build_synthesis(presented, lineage) -> GlobalSynthesis
validate_synthesis(synthesis, presented) -> list[str]
```

**LLM을 부르지 않는다.** 여기서 생성을 다시 열면 Gate B에서 만든 grounding 경계를
표현 단계에서 되돌린다. 하는 일은 canonical에 남은 summary의 결정적 재배열·구조화
뿐이고, 모델 관련 식별자(`transformers · ollama · generator · prompt · model ·
invoke`)가 소스에 없다는 것을 AST로 검사한다.

### dialogue를 아예 쓰지 않는다

GLS-006의 가장 확실한 형태다. **통과한 dialogue조차 입력으로 쓰지 않는다.**

```
쓰면            "어떤 dialogue는 되고 어떤 것은 안 되는가"가 표현 계층의 판단이 된다
안 쓰면          grounding이 제거한 dialogue가 종합에 섞일 경로 자체가 없다
```

### 자격

```
usable   grounding_status가 FAIL로 시작하지 않고
         content_status == VALID_PARSE 이고
         summary가 비어 있지 않다
```

실패한 episode는 `excluded_episode_ids`에 남는다 — 버리지 않고, 제외됐다는 사실을
기록한다.

### 결정적 roll-up

```
overview     usable summary를 canonical 시간순으로 잇는다
analysis     lineage 한 줄당 "H01 (EP01 · EP02): <summary> / <summary>"
             연결어·인과·평가를 만들지 않는다 — 구조화만 한다
conclusion   "확인된 구간 N개를 시간순으로 정리하면 처음은 «…», 마지막은 «…»다."
```

`analysis`가 새 claim을 만들기 가장 쉬운 자리다. 그래서 문장을 합성하지 않고
**출처 표시 + 기존 summary 나열**로 고정했다.

### 상태 (GLS-007)

```
SUFFICIENT            제외된 episode 없음
LIMITED               일부만 usable
NO_RELIABLE_CONTENT   usable 0 — overview·analysis 비우고 결론을 적지 않는다
                      "근거가 확인된 구간이 없어 결론을 적지 않는다."
```

### GLS-004 — 완전 검증을 주장하지 않는다

```
항상 함께 싣는다   limitation = "semantic entailment not automatically verified"
금지               fully grounded · fully verified · entailment verified
                   fact checked · 완전 검증 · 전부 검증
```

만들지 않는 것에 더해, 들어오면 `validate_synthesis`가 보고한다.

### 주입 시험 8종

```
FAIL episode를 종합에 포함        RED
dialogue를 종합에 사용            RED
source 없이 종합문 생성 허용       RED
보증 문구 검사 제거               RED
limitation 생략                  RED
근거 0인데 구체 결론 생성          RED
canonical 순서 대신 입력 순서      RED
자격 검사 없이 source 승인         RED
```

두 항목(`source 없이 …` · `근거 0인데 …`)은 **처음에 GREEN이었다.** 테스트가 실패
사유를 특정하지 않아 다른 검사에 가려졌던 것이다. 코드가 아니라 **테스트를 좁혀**
다시 RED로 만들었다.

### 향후 LLM 도입은 별도 결정

deterministic synthesis가 사람이 읽기에 너무 기계적이라는 문제가 생기면 그때
**별도 티켓 · 별도 prompt contract · 별도 containment contract**로 세운다. Gate C
안에 몰래 넣지 않는다.

---

## C-05 Presentation schema  **COMPLETE**

```
산출물   src/v2_1_presentation.py
         tests/test_v2_1_presentation.py (26 tests)
스키마   presentation_highlights_v2_1
```

```python
build_presentation(presented, highlights) -> tuple[PresentationHighlight, ...]
validate_presentation(records, presented, format_reference=None) -> list[str]
serialize_presentation(records) -> str
```

lineage는 여기서 다시 만들지 않는다 — C-03의 `build_lineage`를 그대로 부른다.
호출자가 손댄 lineage를 끼워 넣을 자리를 두지 않기 위해서다.

### 두 lineage를 가른다

```
source_episode_ids            이 highlight가 무엇으로 구성됐는가
summary_source_episode_ids    그중 무엇이 문장에 쓰였는가
excluded_summary_episode_ids  쓰이지 않은 것 — 지우지 않는다
```

셋의 합집합이 항상 일치해야 하고, 어긋나면 검증기가 보고한다.

### summary는 조합이다 — 검증도 조합으로 한다

```
허용   기존 summary A  +  기존 summary B   →  "A / B"
금지   A + B  →  새 인과·평가·의도 문장
```

검증 방식이 핵심이다. 금지어 목록을 훑지 않고 **정확히 재구성되는지**로 판단한다.

```python
record.summary == " / ".join(사용된 source summary)
```

그래서 연결어를 하나 끼워 넣는 것만으로도 검증기가 걸린다. 구분자를 `" 이후 "`로
바꾸는 주입이 RED인 이유다.

### 중복은 제거하지 않는다

```
EP01 "문을 연다."   EP02 "문을 연다."   →   "문을 연다. / 문을 연다."
```

자동으로 하나를 지우면 **표현 계층이 의미 동일성을 판정하기 시작한다.** 보기 좋게
합치는 것은 나중에 별도 presentation-quality 규칙으로 다룬다.

### 근거가 없으면 자리표시자를 만들지 않는다

```
source_episode_ids            비어 있지 않음
summary_source_episode_ids    비어 있음
→ summary = None · summary_status = NO_RELIABLE_CONTENT
```

`"요약 없음"` · `"내용 확인 필요"` 같은 문장을 넣지 않는다 — canonical fact처럼
보이기 때문이다. OPEN-10에서 배운 것과 같은 부류다.

### 형식 참조의 신분 (REF-001 · 002)

```python
FORMAT_REFERENCE = {"author": "user", "role": "format_reference",
                    "is_ground_truth": False, "document": "…"}
```

직렬화된 산출물에 함께 실린다. 내용의 evidence가 아니라 **formatting provenance**다.
`is_ground_truth`를 뒤집으면 검증기가 보고한다.

### REF-005 · REF-006

```
REF-005   highlight 1개 · 3개 · 12개가 모두 같은 스키마로 직렬화된다
          FORMAT_REFERENCE에 행 수 필드가 없고, row_count 류 식별자도 없다
REF-006   가져오는 것은 절 이름 5개뿐
          "개요 · 주요 사건 및 내용 · 핵심 내용 분석 · 결론 · 근거 및 생성 정보"
          사람 보고서의 문장·고유명("연습생 시절" · "쪽샘" 등)이 생성물과 소스
          어디에도 없다는 것을 참조 문서를 실제로 읽어 대조한다
```

### 주입 시험 10종

```
failed episode summary를 문장에 포함     RED
summary_source 없이 문장 생성            RED   ← 처음 GREEN
출처 없는 독립 문장 삽입 허용             RED
canonical 순서 대신 묶음 입력 순서        RED
excluded를 lineage에서 삭제              RED
형식 참조 행 수를 highlight 수로 사용     RED
사람 보고서 문장을 생성물에 복사          RED
연결어를 새로 끼워 넣음                   RED
중복 summary를 자동 제거                 RED
GT 아님 표시를 뒤집음                     RED
```

`summary_source 없이 …`는 처음 GREEN이었다 — lineage 일관성 검사가 먼저 걸려서
가려졌다. C-04와 같은 부류의 결함이라 **테스트를 좁혀** 다시 RED로 만들었다.

### 관측 — 자격 기준이 C-04와 다르다

지시대로 C-05는 `grounding_status == PASS`만 문장에 쓴다. C-04는 `FAIL이 아님`
(즉 `NOT_APPLICABLE` 포함)을 쓴다. **두 기준이 다르다는 사실을 기록해 둔다.**

```
C-04 global synthesis   FAIL 아님        → NOT_APPLICABLE 구간의 summary도 쓴다
C-05 highlight summary  PASS 만          → NOT_APPLICABLE 구간은 제외된다
```

실측 영향은 작지 않다. **dialogue가 없는 구간은 grounding이 `NOT_APPLICABLE`**이므로,
요약만 있는 영상에서는 highlight summary가 전부 `NO_RELIABLE_CONTENT`가 된다.
실제로 C-05 테스트를 처음 쓸 때 이 상황이 그대로 나왔고, 인용이 자격을 갖추도록
fixture의 발화를 구간마다 다르게 준 뒤에야 `AVAILABLE`이 나왔다.

지시된 기준 그대로 구현했고 그때는 바꾸지 않았다. **이후 사용자 판단으로
`OPEN-12`에서 두 기준을 `{PASS, NOT_APPLICABLE}` allowlist로 통일했다** — 아래 절 참조.

---

## OPEN-12 — Presentation summary eligibility  **CLOSED (2026-09-02)**

```
Problem
C-04는 "FAIL이 아님", C-05는 "PASS만"을 자격으로 썼다. 기준이 갈라져 있었고,
dialogue가 없는 정상 구간(NOT_APPLICABLE)이 highlight summary에서 사라졌다.

Decision
summary is presentation-eligible iff
    content_status == VALID_PARSE
    AND summary exists
    AND grounding_status ∈ {PASS, NOT_APPLICABLE}

PASS and NOT_APPLICABLE remain semantically distinct.
This rule controls presentation eligibility only.
```

### 왜 갈라졌나 — 부작용이었지 정책이 아니었다

```
dialogue 없음  →  grounding = NOT_APPLICABLE  →  C-05가 제외  →  문장 없음
```

즉 **대화가 없다는 이유로 보고서 문장이 사라졌다.** 이것은 표현 정책이 아니라
grounding 상태의 의미가 잘못 옮겨진 결과다.

```
PASS             grounding 검사가 적용됐고 통과했다
NOT_APPLICABLE   그 검사의 적용 대상이 아니다 (검증할 dialogue claim이 없다)
```

**둘은 계속 구분된다.** 자격을 같이 준 것이 판정을 같게 만든 것은 아니고, 상태는
정본 그대로 provenance에 남는다. `summary를 썼다 = grounding PASS다`로 읽으면 안 된다.

### C-04도 함께 좁혔다

`!= FAIL`은 **새 상태가 생기면 자동으로 통과**한다. `PENDING · UNKNOWN · SKIPPED`가
추가되는 순간 조용히 종합문에 섞인다. allowlist로 바꿔 기본값을 "쓰지 않음"으로 뒀다.

### 정의는 한 곳에만 둔다

```
소유   src/v2_1_presentation_input.py
       PRESENTATION_SUMMARY_STATUSES · summary_eligible_for_presentation()
소비   v2_1_synthesis (C-04) · v2_1_presentation (C-05)
```

두 소비자 중 하나가 소유하면 다시 갈라진다. 표현 계층 입구(C-01)가 "표현이 무엇을
볼 수 있는가"의 주인이므로 거기에 뒀다.

### 주입 시험 6종

```
predicate를 PASS 전용으로 되돌림       RED
allowlist 대신 "FAIL 아님"             RED
content_status 검사 제거               RED
빈 summary도 자격 인정                 RED
C-05가 predicate를 우회해 PASS 전용     RED
C-04가 predicate를 우회해 "FAIL 아님"   RED
```

마지막 둘이 중요하다 — **소비자가 공통 규칙을 우회해 자기 조건식으로 돌아가는 것**이
OPEN-12를 만든 원인이고, 그 복귀가 실제로 RED가 되는지 확인했다.

### 테스트

```
PASS + summary              양쪽 사용        ✓
NOT_APPLICABLE + summary    양쪽 사용        ✓
FAIL_* + summary            양쪽 제외        ✓
알 수 없는 상태 + summary    양쪽 제외        ✓
빈 summary · 깨진 parse      양쪽 제외        ✓
대화 없는 영상 전체           문장 생성됨      ✓ (이전에는 전부 NO_RELIABLE_CONTENT)
```

---

## C-06 Preview / Markdown renderer  **COMPLETE**

```
산출물   src/v2_1_render.py
         tests/test_v2_1_render.py (26 tests)
```

```python
semantic_view(highlights, synthesis) -> dict      두 출력이 공통으로 담는 의미
render_preview(manifest, highlights, synthesis) -> str
render_markdown(manifest, highlights, synthesis) -> str    report 모드 전용
```

### 규칙을 지키는 대신, 지킬 수밖에 없게 만들었다

renderer는 **정본 episode를 인자로 받지 않는다.**

```
받지 않으면    경계를 다시 계산할 수 없다        (RPT-003)
              dialogue_note를 찾아 출력할 수 없다 (OPEN-11)
              grounding을 재판정할 수 없다
```

약속이 아니라 입력에 그것이 없다. 보조로 `min`·`max` 호출 부재를 AST로 확인한다.

### RPT-003 — 값이 이상해도 고쳐 주지 않는다

주입 시험이 이 계약의 정의다.

```
PresentationHighlight.start_sec = 100.0  (실제 구간 시작 20.0)
renderer가 20을 다시 계산하면            RED
renderer가 100을 그대로 표시하면          PASS
```

`_clock()`은 초를 `mm:ss`로 적기만 한다 — 표기이지 계산이 아니다.

### RPT-008 — A-02 계약을 그대로 쓴다

```
render_markdown   require_report_mode(manifest)  → 위반이면 RenderRefused
render_preview    preview 모드에서도 허용 (그것이 preview다)
금지              preview → report 자동 승격 · manifest rewrite · fallback
```

거부 후 manifest가 그대로인지도 검사한다.

### RPT-004 — 서식은 다르고 의미는 같다

```
같아야 함   highlight identity · source lineage · summary · 종합 출처 · limitation
달라도 됨   heading · bullet · 표 여부 · 간격 · 등장 횟수
```

Markdown은 분석 절에서 highlight id를 한 번 더 적는다. 그래서 비교를 **등장 횟수가
아니라 집합**으로 한다. 최종 PASS는 C-07의 HWPX가 생긴 뒤 C-10에서 집계한다.

### 문장을 만들지 않는다

```
허용   "시간:" · "요약:" · "구성 구간:" 같은 고정 UI 문구
금지   "중요한 전환점이다" 류의 내용 주장
       요약이 없을 때 "요약 없음 — 내용 확인 필요" 같은 문장
       → 상태 토큰 (NO_RELIABLE_CONTENT) 을 적는다
```

### 주입 시험 10종

```
renderer가 시간을 재계산            RED
preview → report 자동 승격          RED
어긋난 summary 상태를 보정           RED
lineage 불일치 통과                 RED
limitation을 출력에서 뺌            RED
요약 없음에 문장을 지어냄            RED
renderer가 의미 주장을 덧붙임        RED
종합 절을 요약해서 다시 씀           RED
preview가 행별 lineage를 뺌         RED   ← 처음 GREEN
알 수 없는 summary 상태를 통과       RED
```

`preview가 행별 lineage를 뺌`이 처음 GREEN이었다. 종합 절이 모든 구간 id를 한 번씩
적기 때문에 **문서 전체 검사만으로는 행별 출처가 빠져도 통과**했다. 행 단위로 보는
테스트를 추가해 RED로 만들었다. C-04 · C-05에 이어 세 번째 같은 부류다 — 문서 전역
문자열 검사는 약하다.

### 하지 않은 것

```
HWPX                 C-07
presentation fallback C-08
OPEN-11 end-to-end    C-09
acceptance 집계        C-10
```

`hwpx` · `fallback` 식별자가 소스에 없다는 것을 토큰 스캔으로 확인한다.

---

## C-07 HWPX renderer  **COMPLETE**

```
산출물   src/v2_1_render_hwpx.py
         tests/test_v2_1_render_hwpx.py (23 tests)
```

```python
render_hwpx(manifest, highlights, synthesis) -> bytes
write_hwpx(path, manifest, highlights, synthesis)
hwpx_text(payload) -> str        패키지 안의 본문을 읽는다 (검증용)
```

**새 의미 계층이 아니라 같은 `semantic_view`의 두 번째 serializer다.** C-06과 같은
인자만 받고, 정본 episode·timeline·binding·raw는 받지 않는다.

### C-06에서 공유 계약을 꺼냈다

```
LABELS          시간 · 요약 · 구성 구간 · 요약 출처 · 종합 출처 구간 · 한계
format_clock    초 → mm:ss 표기
summary_cell    요약 부재를 어떻게 적는가
semantic_view   두 출력이 공통으로 담는 의미
```

서식은 renderer마다 달라도 되지만 **"무엇을 적었는가"를 읽는 이름까지 갈라지면
두 출력을 대조할 수 없다.** 부재 표기(`(NO_RELIABLE_CONTENT)`)를 공유하는 것도
같은 이유다 — 같은 부재가 문서마다 다르게 읽히면 안 된다.

### 검사는 패키지를 열어서 한다

함수 반환값이 아니라 `Contents/section0.xml`에서 실제 문단을 읽어 확인한다.

```
mimetype                  application/hwp+zip · ZIP_STORED
META-INF/container.xml
version.xml
Contents/header.xml
Contents/section0.xml     <hp:p><hp:run><hp:t>…
```

### RPT-003 — C-06과 같은 tamper 시험

```
확정값   H01.start_sec = 100.0 · end_sec = 150.0
실제     EP01의 구간 시작은 0.0
문서에    01:40 – 02:30 이 적혀야 한다.  00:00이 나오면 경계를 재구성한 것이다.
```

보조로 `min` · `max` · `sorted` 호출 부재를 AST로 확인한다.

### RPT-004 — 문자열 동일이 아니라 semantic projection 동일

```
projection(markdown) == projection(hwpx)

담는 것   highlight별 (시간 · 요약 · 구성 구간 · 요약 출처) · 종합 출처 · 한계
버리는 것 heading · bullet · 상자 글리프 · 줄바꿈 · 등장 횟수
```

`###`는 Markdown에만, `┌`는 HWPX에만 있다 — 서식은 실제로 다르다. 한쪽에서
highlight를 하나 빼면 projection이 달라져 RED다.

### 블록 단위로 본다 (C-06의 교훈)

문서 전체에서 `EP01`이 한 번 보이는 것으로는 부족하다. **id의 첫 등장부터 label
줄까지를 블록으로 잘라** 블록마다 자기 lineage가 있는지 본다. 종합 분석 절이 같은
id를 다시 적기 때문에, 첫 등장만 블록 시작으로 보고 label 없는 줄에서 닫는다.

### BCS 동결을 구조로 잡았다

```
허용 import   __future__ · re · zipfile · io · xml.sax.saxutils
              v2_1_render · v2_1_run
금지          bcs* · m8* · legacy* · pre-grounding 5종
```

허용 목록을 상한으로 검사한다 — "고치지 않았다"보다 강하게, **새 코드가 BCS
구현에 의존하지 않는다**까지 본다. A-11 가드도 통과(`ok = True`).

### 주입 시험 10종

```
시간을 재계산                RED      Markdown과 다른 lineage 출력   RED
블록에서 lineage 삭제        RED      interlock 우회                RED
요약 없음에 설명문 생성       RED      highlight 하나 누락            RED
종합 분석을 축약             RED      의미 주장 덧붙임               RED
limitation 삭제             RED      BCS renderer import           RED
```

### 검증되지 않은 것 — 한글에서의 열림

패키지 배치는 OWPML을 따라 작성했으나 **이 환경에는 한글이 없어 실제 열림 여부를
확인하지 못했다.** 구조 검사(zip 구성 · mimetype 저장 방식 · 본문 XML)까지가
여기서 할 수 있는 전부다. C-10 집계에 한계로 남긴다.

### 하지 않은 것

```
fallback   HWPX 생성 실패 시 무엇을 보존하고 무엇으로 대체하는지는 C-08(RPT-006/007)
```
