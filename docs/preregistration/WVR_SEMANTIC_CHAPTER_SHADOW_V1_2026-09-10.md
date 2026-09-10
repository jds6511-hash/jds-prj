# WVR_SEMANTIC_CHAPTER_SHADOW_V1 사전등록 (2026-09-10)

**결과를 보기 전에** 동결한다. 실행 후 수정하지 않는다(오탈자 정정은 결과 산출 전에만).
Claude는 executor이며 **PASS/HOLD/INCONCLUSIVE를 계산하지 않는다.**

## 0. 동결된 선행 상태

```
WVR_EVENT_MAP_COVERAGE_SHADOW_V1        CLOSED / EVENT_MAP_SHADOW_HOLD
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1   CLOSED / EVENT_STITCHING_SHADOW_HOLD
WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1    CLOSED / CONSERVATIVE_EVENT_MAP_PASS
```

Conservative Event Map(입력): region 11개 · unresolved 24초 · single-source 48초 ·
conflict 240초 · stitchable 288초 · source event 160건(유실 0).
**region 경계를 chapter 경계로 복사하지 않는다.**

## 1. 질문 (PRIMARY)

> Conservative Event Map의 안정 관측과 명시적 conflict/unresolved 메타데이터를 써서,
> 중요한 activity transition을 보존하는 whole-video Semantic Chapter 구조를
> 만들 수 있는가?

원칙: `region boundary ≠ conflict boundary ≠ local window boundary ≠ event boundary
≠ chapter boundary`. chapter는 **의미 변화**로 만든다.

## 2. 입력 (해시 동결 · 불일치면 즉시 중단)

```
conservative_event_map_v1.json   ab1876fd8e2b5c41f6e2791a9e8c80656ba2d5ce296f8c197b6fea5db5ab3119
(파생 확인용)                     conservative_event_map_v1_summary.json
source event 총계                 160 · region 11
```

금지 입력: 원본 영상 재추론(VLM), Track A STT·caption, official test, 새 frame
adjudication, 이전 사건의 blind packet.

## 3. 생성 런타임 동결 (§4 프롬프트와 함께 freeze)

```
generator        Qwen/Qwen2.5-7B-Instruct   (text LLM · config.yaml report_model과 동일)
실행 위치         랩 서버 GPU (<LAB_MACHINE> RTX 4090 24GB) · HF_HOME=/ssd/<SERVER_USER>/cache
dtype            bfloat16 · llm_4bit=false
decoding         greedy (do_sample=false) · max_new_tokens=4096
생성 횟수         1회 — **재생성·retry 금지**(RETRY_ALLOWED=False)
raw 보존          파싱 **전에** raw 문자열을 파일로 남긴다 (raw-before-parse)
```

새 VLM 추론 0회. 실패하면 raw를 보존한 채 중단하고 blocker로 보고한다.

## 4. 동결 프롬프트 (`CHAPTER_PROMPT_V1`)

```
템플릿 sha256        b1448e5f16781acf2e6ab6450de5cb8a7f4d2960b72aad9a46d8743966a3b9b6
렌더된 프롬프트 sha256  ca7ec608894a7daee8ba9049f95fbdd6fe768edd04b07e9769055fa9ec882962
렌더 입력            위 §2 map만 (digest는 map을 그대로 펼친 것 · 요약·추가 없음)
```

전문(`src/wvr_chapter_v1.py`의 `CHAPTER_PROMPT_V1`과 바이트 동일):

```
You segment one video into a small number of semantic chapters.

You are given a CONSERVATIVE EVENT MAP built from overlapping local analysis
windows of a single %(video_end).0f-second video. It has four kinds of regions:

- STITCHABLE: two windows described the same span compatibly (reviewer-judged).
- CONFLICT: two windows described the same span in materially different ways.
  Both descriptions are kept. They are alternative observations, not ranked.
- SINGLE_SOURCE: only one window observed that span.
- UNRESOLVED: no valid observation exists for that span.

MAP
%(digest)s
END OF MAP

Task: return between %(min_chapters)d and %(max_chapters)d chapters that cover
%(video_start).1f to %(video_end).1f seconds continuously, in time order, with
no gaps and no overlaps.

Rules you must follow:
1. Put chapter boundaries where the observed activity, task, scene or object
   domain changes. Do not place boundaries just because the map lists a region
   or window boundary there. Region boundaries are analysis artifacts, not
   activity changes.
2. Never decide which side of a CONFLICT region is true. Never merge conflicting
   descriptions into one asserted fact. Never invent agreement that is not in
   the map. If two observations of the same span disagree on details, keep the
   details out of the title and say in the summary that local observations
   disagree.
3. For UNRESOLVED spans, do not invent content. A chapter may cover such a span,
   but its title and summary must not describe what happens there.
4. Titles: short, broad, observable activity phrases, for example
   "Food preparation" or "Garment handling". No emotion, no intent, no
   speculation about who the person is or why they act.
5. Summaries: one to three sentences about the recurring activity of the
   chapter. State disagreement where the map shows conflict.
6. confidence_class must be exactly one of: %(confidence)s.
   It describes evidence, not probability. Do not output numbers for it.
7. boundary_reason lists why the chapter starts where it starts. Use one or more
   of: %(reasons)s. The first chapter uses ["ACTIVITY_CHANGE"] only if it truly
   starts at an activity change; otherwise use ["SCENE_OR_TASK_CHANGE"].
8. Chapters shorter than %(short_sec).0f seconds need at least two
   boundary_reason values.

Return only JSON, no prose, no code fence, in exactly this form:

{"chapters": [{"start_sec": 0.0, "end_sec": 0.0, "title": "...",
"summary": "...", "dominant_activities": ["...", "..."],
"confidence_class": "...", "boundary_reason": ["..."]}]}
```

프롬프트에 **기대 답(macro-flow 문구)을 넣지 않는다** — 예시는 형식 예시뿐이다.

## 5. chapter 어휘·수량 동결

```
chapter 수          최소 3 · 최대 10 (특정 개수 강제 금지)
confidence_class    STABLE_DOMINANT · MIXED_EVIDENCE · LIMITED_EVIDENCE
                    (숫자 confidence 생성 금지 — 확률이 아니다)
boundary_reason     ACTIVITY_CHANGE · SCENE_OR_TASK_CHANGE ·
                    OBJECT_DOMAIN_CHANGE · SUSTAINED_TRANSITION (1개 이상)
hard minimum 길이    없음. 단 20초 미만 chapter는 boundary_reason 2개 이상을
                    요구하고, 못 채우면 **구조 이상으로 기록**한다(자동 수정·재생성 금지)
MIN_CHAPTER_SEC=60   이전 Event Map 실험 값은 이 사건의 authority가 아니다
```

## 6. UNRESOLVED 정책 (하나로 고정)

```
coverage_from_zero_with_unresolved_opening_metadata
  chapter 시간축은 0.0부터 유지한다
  [0,24)는 사실을 만들어 채우지 않는다 — 해당 chapter의 unresolved_intervals에
  [[0,24]]를 남기고, title·summary는 그 구간 내용을 기술하지 않는다
```

## 7. 출력 스키마 (모델) · 파생 필드 (executor)

모델이 반환하는 것만 파싱한다.

```
chapters[] = {start_sec, end_sec, title, summary, dominant_activities[],
              confidence_class, boundary_reason[]}
```

executor가 map에서 **결정적으로 파생**한다(모델이 event id를 말하지 않게 한다 —
환각 id 방지):

```
chapter_id (CH01…시간순) · source_regions · source_nodes ·
stable_source_events · conflict_source_events · conflict_regions ·
conflict_blocks · conflict_sources_preserved · unresolved_intervals ·
source_windows · source_event_count
boundary_evidence[] = {boundary_sec, boundary_reason, on_24s_grid,
   before_activity_evidence, after_activity_evidence,
   before/after_source_event_ids, source_regions,
   conflict_involved, unresolved_involved}
```

모델 출력에 event id류 필드가 섞여 있으면 **실재하는 id만** 허용하고, 하나라도
없는 id면 `LINEAGE_BROKEN`으로 중단한다.

## 8. 금지 (이 사건의 핵심)

```
conflict에서 한 관측을 승자로 선택 · 충돌 내용을 하나의 확정 사실로 합성 ·
없는 consensus 생성 · preferred/resolved/winner 필드 · 숫자 confidence
[0,24) 사실 생성 · region·창 격자를 chapter 경계로 복사
새 VLM 추론 · Track A 입력 · 재생성(retry) · raw 미보존
Overview·Analysis·Conclusion·HWPX 생성 (§18) · 제출본 승격 · official test · M9
executor의 최종 판정 계산 · 사후 임계·게이트·어휘 변경
```

## 9. 구조 안전 검사 (판정이 아니라 사실 기록)

```
grid_alignment       내부 경계 중 24초 격자 위/밖 개수 · 전부 격자면 구조 이상 기록
conflict_safety      chapter가 덮는 CONFLICT_BLOCK의 두 관측 source가 모두 남았는가
unresolved_safety    unresolved 구간이 계보에서 사라지지 않았는가 · 그 구간만으로
                     chapter 내용을 만들지 않았는가
anomalies            ALL_BOUNDARIES_ON_24S_GRID ·
                     SHORT_CHAPTER_WITHOUT_STRONG_TRANSITION ·
                     CONFLICT_BLOCK_NOT_COVERED ·
                     STABLE_LABEL_OVER_CONFLICT_REGION
```

이상은 **기록만** 한다. 자동 수정·재생성·프롬프트 수정 금지.

## 10. 측정 blocker (→ 리뷰어가 INCONCLUSIVE 사유로 쓸 수 있다)

```
SOURCE_MAP_HASH_MISMATCH · RAW_NOT_PERSISTED · PARSE_FAILURE ·
SCHEMA_VIOLATION · COVERAGE_VIOLATION · VOCABULARY_VIOLATION ·
LINEAGE_BROKEN · CONFLICT_RESOLVED_BY_GENERATOR · UNRESOLVED_FILLED ·
RUNTIME_FAILURE · CONFIG_MISMATCH
```

blocker는 executor가 고쳐서 통과시키지 않는다 — 중단하고 사실만 보고한다.

## 11. 산출물

```
runs/wvr_light_v1/chapter_v1_raw.txt            생성 raw (파싱 전 보존)
runs/wvr_light_v1/chapter_v1_record.json        provenance·런타임·프롬프트 해시
runs/wvr_light_v1/chapter_v1_prompt.txt         렌더된 프롬프트 전문
runs/wvr_light_v1/chapter_v1_chapters.json      chapter + 파생 계보 + 안전 검사
runs/wvr_light_v1/chapter_v1_packet.md          리뷰어 packet (Q1~Q4 미판정)
runs/wvr_light_v1/chapter_v1_summary.json       요약·이상 목록·상태
```

## 12. 리뷰어 질문 (executor는 답을 쓰지 않는다)

```
Q1 WHOLE_VIDEO_STRUCTURE     주요 활동 흐름이 이해되는가
Q2 BOUNDARY_QUALITY          경계가 격자가 아니라 의미 변화에 대응하는가
Q3 CONFLICT_SAFETY           conflict가 확정 사실로 잘못 해결되지 않았는가
Q4 OVERVIEW_INPUT_USABILITY  다음 Overview 입력으로 쓸 수 있는가
```

리뷰어 어휘: `SEMANTIC_CHAPTER_SHADOW_PASS / HOLD / INCONCLUSIVE`.
executor 상태 문자열은 `EXECUTED / REVIEW_PENDING` 하나뿐이다.

## 13. 말할 수 있는 최대 결론 (리뷰어 판정 후)

```
리뷰어가 PASS로 판정하면, Conservative Event Map은 conflict를 확정 사실로 바꾸지
않고도 whole-video Semantic Chapter 후보를 만들 수 있는 입력이다.
```

말하지 않는 것: Event extraction 해결 · 240초 conflict 해결 · 모든 event 사실 ·
0.5fps sufficient · production Event Map 승인 · Overview를 만들어도 된다.

## 14. 검증

```
tests/test_wvr_chapter_v1.py                §19 항목 전부
mutation                                    §20 항목 전부 RED
scripts/wvr_chapter_selfcheck.py            GPU 없이 프롬프트 해시·digest 대조
scripts/wvr_chapter_validate.py             전 항목 PASS
python -m pytest tests/ -q                  전체 통과 · clean tree · HEAD==origin
경계 확인: 제출본 5732075871fd… 불변 · official test 미접촉 · M9 미실행 ·
          conservative map·verdicts·registry·mapping·W00 산출물 무변경
```

## 15. 실행 순서

```
1 prereg 작성 → 2 prereg commit → 3 프롬프트·스키마 freeze(해시 기록) →
4 구현·테스트 commit → 5 map 해시 검증 → 6 chapter 생성(1회) →
7 raw 보존 → 8 파싱·스키마 검증 → 9 계보 검증 → 10 리뷰어 packet →
11 mutation → 12 전체 스위트 → 13 clean tree → 14 결과 commit → 15 STOP
```

## 16. 계속 HOLD

```
Production Event Extraction · Production Event Map · Production Semantic Chapter ·
Overview · Analysis · Conclusion · HWPX · submission promotion · official test · M9
EVENT_MAP_COVERAGE_SHADOW HOLD · EVENT_STITCHING_SHADOW HOLD 불변
CONSERVATIVE_EVENT_MAP PASS는 이 사건의 결과로 소급 변경되지 않는다
```

결과를 리뷰어에게 전달한 뒤 멈춘다.
