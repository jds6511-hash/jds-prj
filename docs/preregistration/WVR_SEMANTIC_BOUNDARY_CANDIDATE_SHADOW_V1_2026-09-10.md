# WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1 사전등록 (2026-09-10)

**결과를 보기 전에** 동결한다(오탈자 정정은 결과 산출 전에만). Claude는 executor이며
**최종 boundary를 확정하지 않고 PASS/HOLD/INCONCLUSIVE를 계산하지 않는다.**
최종 boundary adjudication은 리뷰어 전용이다.

## 0. 동결된 선행 상태

```
WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1      CLOSED / CONSERVATIVE_EVENT_MAP_PASS
WVR_SEMANTIC_CHAPTER_SHADOW_V1            CLOSED / SEMANTIC_CHAPTER_SHADOW_HOLD
WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1   CLOSED / SEMANTIC_CHAPTER_REPAIR_HOLD
```

Repair V1 관측(변경하지 않는다):

```
event 시작 후보          144
전환 근거 accepted        6
선택 가능 밴드 안 accepted  1   (선택 경계 400초)
Stage B                 NOT EXECUTED (blocker INSUFFICIENT_BOUNDARY_EVIDENCE)
```

원인 해석: **action/object lexical overlap 기반 detector가 whole-video semantic
task transition을 찾기에 지나치게 보수적이었다.** 이것은 event data에 의미 전환이
없다는 증거가 아니다. 400초 경계는 24초·48초 격자도, region 경계도 아니었으므로
**event 수준 의미 경계를 만드는 것 자체는 가능하다.**

## 1. 질문 (PRIMARY)

> Conservative Event Map의 실제 event sequence로부터, lexical token overlap이 아니라
> semantic activity/task change 관점에서, 리뷰어가 판정할 수 있는 소수의
> chapter-boundary 후보를 만들 수 있는가?

목표는 Chapter 생성이 **아니다.** 이번 사건의 산출물은 **boundary 후보와 그 근거**뿐이다.

## 2. 이번 사건에서 바꾸는 것 (단 하나)

```
변경 대상   Chapter boundary candidate detection method
```

동결(변경 금지): Conservative Event Map · source Local Events · stitch verdicts ·
conflict regions · unresolved intervals · sampling · VLM outputs · Track A.
새 visual inference 없음.

Repair V1의 lexical transition detector(`wvr_chapter_repair_v1`의
`_reasons`/`select_boundaries`)는 이번 사건에서 **사용하지 않는다.** 그 모듈과
산출물은 historical record로 보존하고 수정하지 않는다.

## 3. 입력 (해시 동결 · 불일치면 즉시 중단)

```
conservative_event_map_v1.json   0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c (LF)
source event 160 · region 11 · conflict block 10 · unresolved [0,24)
```

금지 입력: 원본 영상 재추론(VLM), Track A STT·caption, Local Event 재추출,
Event Map 재생성, V1 chapter 산출물(제목·요약·경계), Repair V1 선택 경계, official test.

## 4. 두 단계 (Chapter 생성 없음)

```
A. deterministic packet construction   결정적 · LLM 없음
B. semantic candidate proposal         text LLM · 후보별 label + rationale만
```

Stage B 이후는 이번 사건에 없다. Chapter·title·summary·Overview를 만들지 않는다.

## 5. Candidate universe (동결)

후보 timestamp universe는 Repair V1과 동일하게 **source event 시작 시각**뿐이다.

```
포함   0 < start_sec < 600 인 source event start_sec (중복 제거)
제외   영상 시작 0.0 · 영상 종료 600.0
기대   144개 (동결값 · 다르면 CONFIG_MISMATCH로 중단)
```

결과를 보고 새 시각을 만들지 않는다. LLM은 timestamp를 만들 수 없고, 선택 가능한
boundary는 **기존 candidate 중 하나뿐**이다.

## 6. Candidate context (동결)

```
BEFORE = [t-30, t)      AFTER = [t, t+30)
CONTEXT_WINDOW_SEC = 30.0   (Repair V1과 동일 · 24의 배수가 아니다)
```

각 side는 그 구간과 겹치는 source event를 시간순으로 제시한다. 각 줄은
`actor | action | object_or_state` 세 필드를 **원문 그대로** 쓴다(요약·수정·삭제 금지).

## 7. Blinding (핵심 · 동결)

proposer에게 다음을 보여주지 않는다.

```
absolute timestamp · window id · region id · region class ·
conflict-region boundary · 24초 격자 · 48초 격자 ·
prior chapter boundary · V1 chapter title · V1 chapter summary ·
Repair V1 선택 경계(400초) · event id
```

candidate는 `C001`…`C144` opaque ID만 쓴다. **ID 순서가 시간 순서와 같으면 그 자체가
상대적 시간 위치를 알려주므로**, ID는 다음 결정적 순열로 배정한다.

```
key(t)  = sha256("WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1|"
                 + SOURCE_MAP_SHA256 + "|" + "%.3f" % t)
순서     key(t) hex 오름차순 → C001, C002, …
```

같은 동결 입력에서 항상 같은 배정이 나오고, 시간 순서 정보는 packet에 남지 않는다.
실제 timestamp mapping은 §14의 봉인 대상이다.

## 8. Conflict 정보 (승자 없음 · 동결)

event text는 보존하되 proposer에게 `preferred source` · `winner` · `truth` ·
어느 쪽이 earlier/later window인지를 주지 않는다.

한 side에 **두 source window가 기여하면** 그 side를 두 관측 집합으로 나눠 제시한다.

```
표시      Observation Set A / Observation Set B
배정      sha256(BLIND_SALT + "|" + candidate_id + "|" + window_pair) 의
          마지막 hex nibble 홀짝으로 A/B 결정 (candidate 안에서 일관)
적용 범위  conflict 구간과 stitchable 구간에 **동일하게** 적용한다
```

두 경우를 같은 형식으로 제시하는 이유는, conflict 구간만 두 집합으로 보여주면
**region class 자체가 누출**되기 때문이다(§7). 한 window만 기여하는 side는 집합 라벨
없이 한 목록으로 제시한다.

## 9. Semantic proposal task (frozen prompt)

프롬프트가 묻는 것은 하나다.

> BEFORE와 AFTER를 비교했을 때, 영상의 broad activity/task/domain이 Chapter를 나눌
> 정도로 materially 변화했다고 볼 근거가 있는가?

판정 vocabulary(그 외 값은 VOCABULARY_VIOLATION):

```
STRONG_TRANSITION_CANDIDATE
WEAK_TRANSITION_CANDIDATE
NO_CHAPTER_TRANSITION
AMBIGUOUS
```

이것은 최종 리뷰어 verdict가 아니다.

## 10. Prompt neutrality (동결)

프롬프트에 이 영상의 예상 macro-flow를 넣지 않는다. 다음 문자열은 프롬프트에
존재해서는 안 되고, self-check가 **생성 전에** 검사한다.

```
food · eat · sew · gift · wrap · cook · cloth · garment · dress ·
kitchen · meal · 400 · chapter title · chapter summary · region · window · grid
```

전환 기준은 도메인 예시 없이 추상적으로만 기술한다. 세부 대상 변화(같은 종류의 일을
계속하면서 다루는 물건만 바뀜)는 chapter transition이 아니라고 명시하되, 그 예시도
이 영상의 활동을 지목하지 않는 추상 표현으로 쓴다.

## 11. Proposer 권한 제한 (동결)

proposer는 다음을 할 수 없다.

```
chapter 생성 · chapter title/summary 생성 · boundary timestamp 생성 ·
candidate timestamp 이동 · conflict resolution · source winner 선택 ·
candidate 추가·삭제
```

출력은 candidate별 label + 짧은 rationale + before/after activity 요지뿐이다.

## 12. 출력 schema (동결)

```json
{"candidates": [{"candidate_id": "C001",
                 "proposal": "STRONG_TRANSITION_CANDIDATE",
                 "before_activity": "...", "after_activity": "...",
                 "rationale": "..."}]}
```

raw LLM output에 timestamp를 넣지 않는다. 숫자 시각 필드(`start_sec` · `end_sec` ·
`boundary_sec` · `time` · `start` · `end`)가 오면 SCHEMA_VIOLATION이다.

## 13. 생성 런타임 (동결 · 새 모델 비교 사건이 아니다)

```
model            Qwen/Qwen2.5-7B-Instruct (revision a09a35458c702b33eeacc393d103063234e8bc28)
dtype            bfloat16 · load_4bit false · attn SDPA
do_sample        false (greedy)
max_new_tokens   2048  (배치당 · 결과 보고 올리지 않는다)
배치당 시도       1회 (재생성 금지)
실행             랩실 4090 · HF_HOME=/ssd/<SERVER_USER>/cache · 프로젝트 venv
보존             배치별 렌더 프롬프트 → raw → 해시 → 파싱 → schema 검증 (raw-before-parse)
```

배치 raw가 이미 있으면 **그 배치는 다시 생성하지 않는다.** 중간에 실행이 죽으면
남은 배치만 생성하고, 그 사실(`resumed_batches`)을 record에 적는다.

## 14. Batch 설계 (동결)

candidate를 하나씩 독립 추론하지 않는다. §7의 순열 순서에서 연속 8개씩 묶는다.

```
BATCH_SIZE        8
배치 수            18 = 144 / 8   (나머지 없음)
배치 id            B01…B18
배치 membership    순열 순서의 [8k, 8k+8) — 결과를 보고 재배치하지 않는다
```

각 candidate block은 독립된 opaque 블록이며, 블록 사이에 시간·인접 관계를 적지 않는다.
순열 순서로 묶으므로 한 배치가 영상의 한 구간에 몰리지 않는다.

## 15. Candidate reduction (동결 · 사후 임계 없음)

```
reviewer packet   모든 STRONG_TRANSITION_CANDIDATE + 모든 AMBIGUOUS
appendix          모든 WEAK_TRANSITION_CANDIDATE (전량 보존)
artifact          NO_CHAPTER_TRANSITION은 count + 산출물에 전량 보존
```

STRONG이 많아도 executor가 임계를 만들어 자르지 않는다. 그대로 전달한다.

## 16. Candidate density guard

```
STRONG 0~1개   →  INSUFFICIENT_SEMANTIC_CANDIDATES 기록 (규칙 완화 없음)
STRONG 과다     →  임계 조정 없이 전량 전달
```

## 17. Mapping seal (동결)

semantic proposal이 끝난 뒤에도 `candidate_id → timestamp` 와
`Observation Set A/B → source window` 매핑은 **리뷰어 판정 전에 공개하지 않는다.**

```
reviewer packet에 들어가는 것
  Candidate Cxxx · BEFORE · AFTER · proposer label · rationale
들어가지 않는 것
  timestamp · window id · region id · region class · 격자 · 판정 · 통계적 힌트
```

executor 보고서에도 매핑과 시간 관련 서술을 쓰지 않는다.

## 18. 리뷰어 판정 (executor 계산 금지)

리뷰어는 packet의 각 candidate에 대해 다음 중 하나를 준다.

```
CHAPTER_BOUNDARY · NOT_CHAPTER_BOUNDARY · UNRESOLVED
```

리뷰어는 proposer label을 참고할 수 있으나 authority가 아니다.
수락 원칙: broad activity/task progression이 materially 변화하고 chapter-level 분리가
whole-video 이해에 도움이 되는 경우에만 `CHAPTER_BOUNDARY`. 단순 ingredient/object
변화는 보통 boundary가 아니다.

## 19. Reveal 게이트

packet candidate **전부**에 판정이 기록된 뒤에만 `candidate_id → timestamp`를
공개한다. 공개 후 verdict 수정은 금지다. 구현은 기록 스크립트가 강제한다
(`--reveal`는 미기록 candidate가 있으면 거부).

## 20. Chapter 수 guard (reveal 후)

```
accepted internal boundary 2~9개   →  3~10 chapter 생성 가능 후보
2개 미만                            →  다음 Stage B(Chapter finalization) 실행 금지
9개 초과                            →  executor가 임의 제거하지 않는다 (리뷰어 결정)
```

이 판단은 리뷰어의 것이고 executor가 계산하지 않는다.

## 21. Technical gate (실패 시 INCONCLUSIVE / PACKET_OR_GENERATION_FAILURE)

```
same Conservative Event Map hash
candidate timestamps = source event starts only (144)
all expected candidate IDs represented · no invented ID · no missing ID
schema valid · allowed vocabulary only
raw persisted before parse (배치별)
mapping remained sealed
no timestamp leakage · no window/region/grid leakage in blinded packet
no VLM inference · no Track A input · no Overview artifact
submission unchanged · official test unopened
```

blocker는 고쳐서 통과시키지 않는다 — 중단하고 사실만 보고한다.

## 22. 누출 감사 (측정의 핵심)

blinded packet 텍스트에 대해 구조로 검사한다.

```
digit 검사        candidate id(C\d{3})를 제거한 뒤 남는 숫자 0개여야 한다
                 (source event text 160건에 숫자 0건임을 확인해 동결)
식별자 검사        W\d\d · R\d\d · CH\d\d · REGION · WINDOW · STITCHABLE ·
                 CONFLICT · SINGLE_SOURCE · UNRESOLVED · grid 문자열 0건
event id 검사      160개 event id 전부 미등장
순서 검사          candidate id 순서 ≠ 시간 순서 (§7 순열)
```

## 23. 산출물

```
runs/wvr_light_v1/bcand_v1_candidates.json     후보 144 전량(시각 포함 · packet 아님)
runs/wvr_light_v1/bcand_v1_blind_map.json      봉인 매핑 (판정 전 비공개)
runs/wvr_light_v1/bcand_v1_batches.json        배치 membership + 렌더 해시
runs/wvr_light_v1/bcand_v1_prompt_Bnn.txt      배치별 렌더 프롬프트 (blinded)
runs/wvr_light_v1/bcand_v1_raw_Bnn.txt         배치별 raw (파싱 전 보존)
runs/wvr_light_v1/bcand_v1_record.json         런타임·해시·VRAM·resumed 배치
runs/wvr_light_v1/bcand_v1_proposals.json      파싱된 label + rationale 전량
runs/wvr_light_v1/bcand_v1_leakage_audit.json  §22 감사
runs/wvr_light_v1/bcand_v1_packet.md           리뷰어 packet (STRONG + AMBIGUOUS)
runs/wvr_light_v1/bcand_v1_appendix_weak.md    WEAK 전량 appendix
runs/wvr_light_v1/bcand_v1_summary.json        요약 (판정 없음)
runs/wvr_light_v1/bcand_v1_verdicts.json       리뷰어 판정 기록 (executor 작성 금지)
```

## 24. 측정 blocker 어휘

```
SOURCE_MAP_HASH_MISMATCH · CONFIG_MISMATCH · RAW_NOT_PERSISTED ·
PARSE_FAILURE · SCHEMA_VIOLATION · VOCABULARY_VIOLATION ·
CANDIDATE_SET_MISMATCH · TIMESTAMP_LEAKAGE · GEOMETRY_LEAKAGE ·
MAPPING_PREMATURE_REVEAL · INSUFFICIENT_SEMANTIC_CANDIDATES ·
RUNTIME_FAILURE
```

## 25. 금지

```
Chapter · title · summary · dominant activities · Overview · Analysis ·
Conclusion · HWPX 생성 (이번 사건에서 전부 금지)
LLM의 timestamp 생성·이동 · candidate 추가·삭제 · conflict 승자 선택
region·격자·window·prior chapter 정보를 proposer에게 제공
판정 전 mapping reveal · reveal 후 verdict 수정
결과를 보고 임계·배치·토큰 상한·어휘 변경 · 재생성(retry)
새 VLM 추론 · Track A 입력 · Local Event 재추출 · Event Map 재생성 ·
W00 복구 · sampling 변경 · 새 모델 비교
제출본 승격 · official test · M9 · production 승격
executor의 최종 판정 계산
결과가 나빠도 하위 layer로 회귀하지 않는다 — boundary candidate layer에서 멈춘다
```

## 26. 리뷰어 최종 어휘 (executor 계산 금지)

```
BOUNDARY_CANDIDATE_SHADOW_PASS
BOUNDARY_CANDIDATE_SHADOW_HOLD
BOUNDARY_CANDIDATE_SHADOW_INCONCLUSIVE
executor 상태 문자열: EXECUTED / REVIEW_PENDING
```

PASS 후보 조건(리뷰어 판단): 최소 2개 이상의 방어 가능한 internal chapter boundary ·
major activity transition 포착 · geometry leakage 없음 · conflict를 winner 선택으로
해결하지 않음.

## 27. 말할 수 있는 최대 결론 (리뷰어 판정 후)

리뷰어가 PASS로 판정하면, **event sequence에 semantic transition proposal을 붙이고
blinded human review로 boundary를 동결하는 경로**가 Chapter finalization의 입력으로
쓸 수 있다는 것까지다. 다음 사건은
`WVR_SEMANTIC_CHAPTER_FINALIZATION_SHADOW_V1`이며 리뷰어가 동결한 boundary만 쓴다.

금지되는 결론: "Chapter가 만들어졌다" · "conflict가 해결됐다" ·
"Repair V1 HOLD가 해소됐다" · "Event Map이 검증됐다" · "0.5fps sufficient" ·
"Overview를 만들어도 된다" · "production ready".

## 28. 실행 순서

```
1 prereg · 2 prereg commit · 3 candidate 구성 동결 · 4 프롬프트/schema 동결 ·
5 구현·테스트 · 6 map hash 검증 · 7 candidate packet 생성 · 8 blind mapping seal ·
9 proposer 추론 · 10 raw 보존/파싱 · 11 technical validation · 12 reviewer packet ·
13 mutation/전체 스위트 · 14 clean tree · 15 result commit · 16 STOP
```

보고 형식: A provenance · B candidate universe · C blind packet construction ·
D proposer output distribution · E STRONG/AMBIGUOUS reviewer packet ·
F leakage audit · G technical validation · H verification ·
I status `WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1 EXECUTED / REVIEW_PENDING`.
mapping reveal 금지 · Semantic Chapter/Overview 생성 금지 · 여기서 멈춘다.

## 29. 정정 (errata 1 · 2026-09-10 · 생성물 0건 시점)

Stage A 구성 중 §8이 다루지 않은 사례를 발견했다. 창 기하(길이 48초·stride 24초)
때문에 30초 side에 **최대 4개 source window가 기여**한다(실측 분포: 1창 13 · 2창 28 ·
3창 208 · 4창 38 · 0창 1 — side 288개 기준). §8은 "두 window가 기여하면"만 규정했으므로
일반 규칙을 여기서 동결한다. **아직 어떤 packet·프롬프트·생성물도 만들지 않았다.**

```
k = 그 side에 기여한 source window 수
k = 0   "(no observation recorded on this side)" 한 줄로 명시한다 (실측 1건)
k = 1   집합 라벨 없이 한 목록으로 제시한다
k >= 2  k개 집합으로 나눠 Observation Set A, B, C, D … 로 제시한다
라벨 순서  sort key = sha256(BLIND_SALT + "|" + candidate_id + "|" +
                          "+".join(sorted(windows)) + "|" + window) 의 hex 오름차순
           → 그 순서대로 A, B, C, D 배정 (창 id 순서·시간 순서를 드러내지 않는다)
적용      conflict 구간과 stitchable 구간에 동일하게 적용한다 (region class 누출 방지)
```

라벨은 문자이므로 §22의 digit 감사에 영향이 없다. side가 비어 있는 candidate도
제외하지 않고 그대로 proposer에게 보낸다(제외하면 후보 집합이 사후에 바뀐다).

## 30. 정정 (errata 2 · 2026-09-10 · inference 0회/raw 0건 시점)

리뷰어가 `PREREG_TEST_CONTRACT_MISMATCH / CONFIRMED`로 판정하고
`MINIMAL PRE-INFERENCE ERRATA / APPROVED`를 승인했다. §6의 source observation 원문
보존과 §10의 rendered prompt 전체 activity-term 금지가 frozen input에서 동시에 성립하지
않는 모순만 교정한다. semantic acceptance threshold나 다른 실행 계약은 바꾸지 않는다.

정정 전 provenance:

```
original prereg commit       4ace1f224f141c51338ccca7eafa39745e9d9ec4
errata 1 commit              8c7df4c9538fb1de2c25f540f3627329f6b804dc
inherited test SHA256        6aa39751fb74baa9e2526af466800855e2f167b15c0e522bd872097d9c294b2f
inference                    0회
raw/result artifact          0건
```

### 30.1 Prompt guidance neutrality (정정된 §10 범위)

다음 video-specific expected-answer term 금지는 **executor가 작성한 고정 prompt
instruction/template prose/example/few-shot/task explanation/expected-answer hint**에 적용한다.

```
food preparation · eating · sewing · gift wrapping · clothing · 400 sec ·
V1 chapter sequence
```

즉 고정 guidance가 이 영상의 예상 macro-flow를 암시해서는 안 된다.

### 30.2 Frozen observation payload exemption

Conservative Event Map에서 그대로 복사되는 아래 세 필드는 §30.1 activity-term ban의
대상이 아니다.

```
actor · action · object_or_state
```

source-derived observation text에 같은 활동 단어가 자연스럽게 존재하면 원문 그대로
proposer input에 포함한다. 그 단어를 없애기 위한 수정·삭제·semantic masking·동의어
치환·generic placeholder 치환은 금지한다. 즉 `PROMPT GUIDANCE NEUTRALITY`와
`SOURCE OBSERVATION FIDELITY`를 동시에 유지한다.

### 30.3 Global leakage prohibition은 불변

다음 항목은 exemption이 아니며 rendered proposer prompt **전체**에서 계속 0건이어야 한다.

```
absolute timestamp · window id · region id · conflict-region id/boundary ·
24초/48초 grid metadata · prior chapter boundary/title/summary ·
earlier/later-window identity · event id
```

alternative observation 원문은 모두 보존하되 `Observation Set A/B/C/D` 같은 opaque
grouping만 쓴다. preferred/winner/truth/reliability 정보는 계속 금지한다.

### 30.4 WVR-B14 correction authorization

Inherited WVR-B14는 다음을 각각 독립적으로 검사하도록 고친다.

```
A fixed instruction/template/example에 video-specific expected-answer hint 없음
B source-derived payload의 동일 활동 단어 출현 허용
C actor/action/object_or_state 원문 보존
D B14 통과 목적의 삭제·치환·masking 없음
E timestamp/window/region/grid/prior-chapter 누출은 rendered prompt 전체에서 0
```

변경 전·후 test SHA256, exact diff, 변경 이유와 이 절 번호를 test integrity audit에
기록한다.

### 30.5 불변 계약

candidate universe · ±30초 context · opaque ID · mapping seal · proposer vocabulary ·
batching · conflict preservation · raw-before-parse · reviewer authority · STRONG 0~1
diagnostic · downstream generation prohibition은 전부 불변이다. 새 semantic threshold를
추가하지 않는다.

## 31. 정정 (errata 3 · 2026-09-10 · inference 0회/raw 0건 시점)

리뷰어가 두 번째 충돌을 `PREREG_TEST_CONTRACT_MISMATCH / SECOND PRE-INFERENCE
CONFLICT CONFIRMED`로 판정하고 `MINIMAL PRE-INFERENCE ERRATA #2 / APPROVED`를
승인했다. frozen observation의 자연어와 geometry/time control metadata를 일반 substring
검사로 구분할 수 없는 모순만 교정한다.

```
authority principle
LEAKAGE IS STRUCTURAL / IDENTIFIER-BASED,
NOT GENERIC NATURAL-LANGUAGE SUBSTRING-BASED.

errata 2 commit            a1e958a
original test SHA256       6aa39751fb74baa9e2526af466800855e2f167b15c0e522bd872097d9c294b2f
inference                  0회
raw/result artifact        0건
implementation commit      없음
```

### 31.1 Source semantic payload와 control metadata 분리

`actor` · `action` · `object_or_state`의 frozen 자연어는 source semantic payload다.
그 밖의 candidate/batch control, source identity, geometry, time, prior chapter 정보는
control metadata다. builder와 validator는 두 범주를 구조적으로 구분하며 최종 직렬화 전
범주별 검사를 수행한다.

source payload의 다음 원문은 허용하고 삭제·마스킹·치환하지 않는다.

```
train window showing cityscape
walking through train window
blending
bread pieces into blender
lid on blender
potato slices in blender
```

일반 단어 `window`와 `blender`/`blending` 안의 `end` substring은 그 자체로 leakage가
아니다.

### 31.2 Geometry leakage (rendered input 전체에서 계속 금지)

```
explicit identifiers   W\d{2} · R\d{2} · CH\d{2} · 실제 source event ID
metadata fields         source_window · source_window_id · window_id ·
                        region_id · region_class · region_boundary ·
                        chapter_id · prior_chapter · grid_24s · grid_48s ·
                        earlier_window · later_window
metadata prose          24-second grid · 48-second grid와 동등한 geometry 표현
prior chapter           boundary · title · summary · V1 chapter sequence
```

`source window W07`, `window_id: W07`, `region R05`, `region_id: R05`,
`prior chapter CH03`과 source event ID poison은 계속 RED여야 한다.

### 31.3 Time leakage의 구조 검사

계속 금지:

```
실제 timestamp 표현             48.0 · 192 sec · 00:48 등
machine-readable time metadata  start_sec · end_sec · boundary_sec ·
                                timestamp · time_sec
disallowed property key         "time" · "start" · "end"가 candidate timing을 운반
guidance                        timestamp 선택 또는 boundary start/end 이동 요구
```

모든 숫자를 timestamp로 보거나 일반 prose 안의 `start`/`end`/`time` substring만으로
leakage를 판정하지 않는다.

### 31.4 Test correction authorization

WVR-B11은 generic `window` ban을 제거하고 identifier/metadata 금지와 frozen `train window`
원문 보존을 검사한다. WVR-B12/leakage audit은 위 structural poison을 RED로 유지하면서
자연어 `train window showing cityscape`를 허용한다. WVR-B15는 generic substring 검사를
structured time field/key/guidance 검사로 바꾸고 `blender`/`blending`을 허용한다.

변경 후 test SHA256, B11/B12/B15 exact diff, 사유와 이 절을 integrity audit에 기록한다.
로컬 pytest temp permission은 contract와 별개이며 결과 독립적인 `--basetemp` 지정으로만
해결하고 실행 명령을 provenance에 남긴다.

### 31.5 불변 계약

candidate universe · ±30초 context · opaque ID · mapping seal · batching · proposer
vocabulary · alternative observation preservation · raw-before-parse · reviewer authority ·
semantic threshold · STRONG 0~1 diagnostic · downstream generation prohibition은 불변이다.
