# WVR_SEMANTIC_CHAPTER_BOUNDARY_REPAIR_V1 사전등록 (2026-09-10)

**결과를 보기 전에** 동결한다(오탈자 정정은 결과 산출 전에만). Claude는 executor이며
**PASS/HOLD/INCONCLUSIVE를 계산하지 않는다.**

## 0. 동결된 선행 상태

```
WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1   CLOSED / CONSERVATIVE_EVENT_MAP_PASS
WVR_SEMANTIC_CHAPTER_SHADOW_V1         CLOSED / SEMANTIC_CHAPTER_SHADOW_HOLD
   V1 리뷰어 답: STRUCTURE COARSELY YES · BOUNDARY_QUALITY NO ·
                CONFLICT_SAFETY PARTIAL/NOT SUFFICIENT · OVERVIEW_INPUT NO
```

V1 chapter 산출물은 **historical comparison으로 보존**하고 수정하지 않는다.
교정 대상은 세 가지뿐이다 — ① 내부 경계 7/7이 region·24초 격자 정렬
② conflict 포함 chapter의 uncertainty 미노출 ③ single-source CH08이
STABLE_DOMINANT. 그 밖의 architecture는 확장하지 않는다.

## 1. 질문 (PRIMARY)

> 같은 Conservative Event Map에서 region/window 기하를 chapter segmentation의
> 실질적 proxy로 쓰지 않고, event 수준 activity transition을 근거로 Semantic
> Chapter를 만들며 conflict와 근거 강도를 정직하게 표시할 수 있는가?

## 2. 입력 (해시 동결 · 불일치면 즉시 중단)

```
conservative_event_map_v1.json   0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c (LF)
V1 대조용(읽기 전용)               chapter_v1_chapters.json
source event 160 · region 11
```

금지 입력: 원본 영상 재추론(VLM), Track A STT·caption, Local Event 재추출,
Event Map 재생성, official test.

## 3. 두 단계 분리 (V1의 실패 원인 교정)

```
Stage A  경계 후보 추출 · 선택 — **LLM 없음 · 결정적**
동결     선택된 경계 집합을 파일로 고정한 뒤에만 Stage B로 넘긴다
Stage B  제목·요약·dominant_activities만 LLM 1회 (경계 추가·삭제·이동 불가)
```

## 4. Stage A 규칙 (동결)

후보 시각은 **source event의 시작 시각뿐**이다. region 경계·24초/48초 배수 시각을
후보로 주입하지 않는다. jitter·인위적 shift도 금지한다.

```
DETECT_WINDOW_SEC   30.0   경계 전후 근거 창 (24의 배수가 아니다)
SUSTAIN_WINDOW_SEC  60.0   지속 전환 확인 창
MIN_SEPARATION_SEC  60.0   = 600 / MAX_CHAPTERS — 자유 선택이 아니라 상한에서 유도
chapter 수           3–10 (V1의 8을 목표로 하지 않는다)
```

근거(reason)는 **토큰 domain 분리**라는 구조 조건으로만 만든다(새 유사도 점수·임계
없음). 토큰은 기존 동결 모듈 `wvr_density_v2`의 정규화·불용어를 그대로 쓴다.

```
ACTIVITY_DOMAIN_CHANGE     전/후 30초의 action 토큰 교집합이 0
OBJECT_DOMAIN_CHANGE       전/후 30초의 object 토큰 교집합이 0
SCENE_OR_TASK_CHANGE       위 둘이 동시에 성립
SUSTAINED_ACTIVITY_CHANGE  전/후 60초의 (action+object) 토큰 교집합이 0이고
                           위 근거가 하나 이상 있을 때
```

후보 제외 사유:

```
NO_EVIDENCE_ON_BOTH_SIDES        한쪽에 event가 없다 (영상 시작·끝·unresolved)
NO_TRANSITION_EVIDENCE           근거 0개
BOUNDARY_UNSUPPORTED_BY_CONFLICT conflict block 안인데 두 관측 source가 공통
                                 근거를 갖지 않는다 (§7)
```

선택 규칙(결정적):

```
1) 제외되지 않은 후보 중 60 ≤ t ≤ 540 만 후보 풀에 넣는다
2) cursor=60에서 시작해 [cursor, cursor+60) 안의 후보 중
   (근거 개수 내림차순 → 전환 폭(후 토큰 − 전 토큰 개수) 내림차순 → 시각 오름차순)
   1위를 선택하고 cursor를 선택 시각+60으로 옮긴다
3) 후보가 없으면 다음 후보 시각으로 cursor를 옮긴다. 540 초과면 종료
```

격자·region 일치는 **선택 기준에 들어가지 않는다**(§8 감사 전용).
선택 결과가 chapter 3–10을 만족하지 못하면 `INSUFFICIENT_BOUNDARY_EVIDENCE`로
중단한다 — 규칙을 완화해 억지로 맞추지 않는다.

## 5. region 경계의 역할

region 경계는 lineage·uncertainty 메타데이터일 뿐이다. 후보 생성기에 주입하지 않고
(`REGION_BOUNDARY_AS_CANDIDATE_ALLOWED=False`), 사후 감사에서 일치 여부만 적는다.

## 6. 경계 근거 기록 (모든 경계 필수)

```
boundary_sec · reason[] · before_event_ids · before_activity ·
after_event_ids · after_activity · in_conflict_block ·
conflict_source_reasons (conflict 안 경계일 때 source별 근거)
```

before·after **양쪽에 valid event 근거가 있어야** 한다. 예외는 영상 시작·끝·
unresolved 구간뿐이며, 그 예외는 내부 경계가 될 수 없다(내부 경계는 60–540 사이).

## 7. conflict 안 경계

CONFLICT block 내부 시각은 **두 관측 source가 공통 근거**를 가질 때만 후보다.
한쪽 관측만 전환을 보이면 `BOUNDARY_UNSUPPORTED_BY_CONFLICT`로 제외한다.
어느 관측이 맞다고 고르지 않는다.

## 8. 격자 누출 감사 (핵심 측정 · 판정 아님)

내부 경계마다 기록한다.

```
on_24s_grid · on_48s_grid · equals_region_boundary · reason ·
used_for_selection=False · jitter_applied=False
```

목표는 "격자 밖 숫자를 만드는 것"이 아니다. **event 전환 근거가 있는 시각만** 쓰며,
그 결과가 격자와 겹치면 겹친 대로 기록한다. 전량 정렬이면 구조 이상
(`ALL_BOUNDARIES_ON_24S_GRID` / `ALL_BOUNDARIES_EQUAL_REGION_BOUNDARIES`)으로
기록하되 자동 수정·재생성하지 않는다.

## 9. Stage B (생성 1회 · 경계 불변)

```
프롬프트   REPAIR_PROMPT_V1 · 템플릿 sha256
          8a1a9c652dda1e7d24030652350fd29c77b0b0ec0945d6a43aa0e1fb7ae975ae
          (렌더 결과는 Stage A 출력에 따라 결정되므로 record에 해시를 남기고
           재계산 동일성으로 검증한다)
generator Qwen/Qwen2.5-7B-Instruct · bfloat16 · 4bit=false · greedy ·
          max_new_tokens 4096 · 생성 1회 · 재생성 금지
반환 필드  chapter_id → {title, summary, dominant_activities}
거부       시각 필드(start_sec/end_sec/boundary_sec/time/start/end) ·
          confidence/evidence_class 지정 · chapters 배열 형태 ·
          chapter 집합 불일치 · overview/analysis/conclusion/report/boundaries/
          chapter_count 필드
raw 순서   렌더 프롬프트 저장 → raw 저장 → 해시 대조 → 파싱 (raw-before-parse)
```

## 10. 제목 원칙

관측 가능한 broad activity. 의도·감정·목적 추론·근거 없는 구체성 금지.

## 11. conflict 노출 (구조적 요구)

chapter가 MATERIAL_CONFLICT block을 하나라도 포함하면 불확실성이 **반드시 노출**돼야
한다. 구현은 다음과 같이 동결한다.

```
disclosure_required        conflict block 포함 여부
disclosed_by_generator     요약에 동결 어휘가 있는지
                           (disagree/disagreement/conflict/conflicting/
                            inconsistent/differ/differing/uncertain/uncertainty)
machine_disclosure         required면 executor가 고정 문장을 함께 기록한다
conflict_disclosed         required → (요약 노출 또는 machine disclosure 존재)
```

즉 **conflict가 있는데 노출이 없는 상태는 산출물에 존재할 수 없다**. 생성기가
노출하지 않았으면 그 사실 자체를 구조 이상
(`CONFLICT_NOT_DISCLOSED_BY_GENERATOR`)으로 기록하고 machine disclosure를 붙인다.
문구를 사후에 고쳐 쓰지 않고, 생성기 요약도 편집하지 않는다.

## 12. evidence class (executor가 결정적으로 계산 · LLM 금지)

```
MIXED_EVIDENCE     material conflict 포함
LIMITED_EVIDENCE   single_source_seconds ≥ multi_window_seconds 또는
                   unresolved_seconds > 0
STABLE_DOMINANT    multi-window 지지 있고 conflict 없고 unresolved 없음
우선순위            MIXED > LIMITED > STABLE
```

single-source 지배 chapter는 **절대 STABLE_DOMINANT가 될 수 없다.**
`evidence_audit`이 이 규칙 위반을 구조로 검사한다.

## 13. coverage

ordered chapter가 0–600초를 연속으로 덮는다. `[0,24)` unresolved는 보존하고 그
구간을 설명하는 synthetic activity를 만들지 않는다(V1과 같은 정책).

## 14. V1 대조 (V1을 정답으로 쓰지 않는다)

기록: chapter 수 · 내부 경계 시각 · region 경계 일치 · 격자 정렬 ·
evidence/confidence class · conflict 노출 강제 여부.

## 15. 산출물

```
runs/wvr_light_v1/chapter_repair_v1_candidates.json   Stage A 후보 전량(제외 사유 포함)
runs/wvr_light_v1/chapter_repair_v1_boundaries.json   선택·동결된 경계 + 근거
runs/wvr_light_v1/chapter_repair_v1_prompt.txt        Stage B 렌더 프롬프트
runs/wvr_light_v1/chapter_repair_v1_raw.txt           생성 raw (파싱 전 보존)
runs/wvr_light_v1/chapter_repair_v1_record.json       런타임·해시·VRAM
runs/wvr_light_v1/chapter_repair_v1_chapters.json     chapter + 계보 + 감사
runs/wvr_light_v1/chapter_repair_v1_packet.md         리뷰어 packet
runs/wvr_light_v1/chapter_repair_v1_summary.json      요약
runs/wvr_light_v1/chapter_repair_v1_v1_comparison.json V1 대조
```

## 16. 측정 blocker (→ 리뷰어가 INCONCLUSIVE 사유로 쓸 수 있다)

```
SOURCE_MAP_HASH_MISMATCH · INSUFFICIENT_BOUNDARY_EVIDENCE ·
BOUNDARY_SET_NOT_FROZEN · RAW_NOT_PERSISTED · PARSE_FAILURE ·
SCHEMA_VIOLATION · COVERAGE_VIOLATION · LINEAGE_BROKEN ·
LLM_CHANGED_BOUNDARIES · EVIDENCE_CLASS_VIOLATION ·
CONFLICT_DISCLOSURE_MISSING · UNRESOLVED_FILLED · RUNTIME_FAILURE ·
CONFIG_MISMATCH
```

blocker는 고쳐서 통과시키지 않는다 — 중단하고 사실만 보고한다.

## 17. 금지

```
region·격자 시각을 후보로 주입 · 격자 회피용 jitter · 결과 보고 chapter 수 조정
LLM의 경계 추가·삭제·이동 · LLM의 evidence class 지정
conflict 승자 선택 · conflict 노출 은폐 · [0,24) 사실 생성
새 VLM 추론 · Track A 입력 · Local Event 재추출 · Event Map 재생성 · 재생성(retry)
Overview·Analysis·Conclusion·HWPX 생성 · 제출본 승격 · official test · M9
executor의 최종 판정 계산 · 사후 임계·게이트·어휘 변경
결과가 나빠도 Local Event 재추출·W00 복구·sampling 변경·프롬프트 exemplar 연구·
Track A conflict 해결·새 Event Map으로 회귀하지 않는다 — chapter layer에서 멈춘다
```

## 18. 리뷰어 질문 (executor는 답을 쓰지 않는다)

```
Q1 STRUCTURE · Q2 BOUNDARY_SEMANTICS · Q3 GEOMETRY_INDEPENDENCE ·
Q4 CONFLICT_SAFETY · Q5 EVIDENCE_CALIBRATION · Q6 OVERVIEW_READY
어휘: SEMANTIC_CHAPTER_REPAIR_PASS / HOLD / INCONCLUSIVE
executor 상태 문자열: EXECUTED / REVIEW_PENDING
```

## 19. 말할 수 있는 최대 결론 (리뷰어 판정 후)

```
리뷰어가 PASS로 판정하면, chapter 경계를 기하가 아니라 event 수준 전환에서 만들고
conflict·근거 강도를 정직하게 표시한 chapter sequence를 Overview Shadow 입력으로
쓸 수 있다.
```

말하지 않는 것: V1 HOLD 해소 · conflict 해결 · Event Map 검증 ·
0.5fps sufficient · Overview 생성 허가 · production ready.

## 20. 검증

```
tests/test_wvr_chapter_repair_v1.py        §21 항목 전부
mutation                                   §22 항목 전부 RED
scripts/wvr_crepair_validate.py            전 항목 PASS
python -m pytest tests/ -q                 전체 통과 · clean tree · HEAD==origin
경계 확인: 제출본 5732075871fd… 불변 · official test 미접촉 · M9 미실행 ·
          conservative map·V1 chapter 산출물·verdicts·registry 무변경 ·
          Overview/Analysis/Conclusion/HWPX 산출물 0건
```

## 21. 실행 순서

```
1 prereg → 2 prereg commit → 3 Stage A 규칙 freeze → 4 Stage B 프롬프트 freeze →
5 구현·테스트 commit → 6 map 해시 검증 → 7 Stage A 추출 → 8 경계 동결 →
9 Stage B 생성 1회 → 10 raw 보존·파싱 → 11 evidence class 결정적 배정 →
12 계보·conflict·격자 감사 → 13 리뷰어 packet → 14 mutation·전체 스위트 →
15 clean tree → 16 결과 commit → 17 STOP
```

## 22. 계속 HOLD

```
Production Event · Production Event Map · Production Chapters · Overview ·
Analysis · Conclusion · HWPX · submission promotion · official test · M9
V1 HOLD·CONSERVATIVE PASS·STITCHING HOLD·EVENT_MAP HOLD는 소급 변경하지 않는다
```

결과를 리뷰어에게 전달한 뒤 멈춘다.
