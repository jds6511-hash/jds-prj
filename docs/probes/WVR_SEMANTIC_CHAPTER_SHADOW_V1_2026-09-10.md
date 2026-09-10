# WVR_SEMANTIC_CHAPTER_SHADOW_V1 결과 (2026-09-10)

사전등록: `docs/preregistration/WVR_SEMANTIC_CHAPTER_SHADOW_V1_2026-09-10.md`
(commit `9248116` · errata `6b5a314`·`05762ef`, **둘 다 생성 0회 시점**) ·
구현 `e3fcbed` · **새 VLM 추론 0회 · Track A 입력 0건 · text LLM 생성 1회**

```
executor 상태   EXECUTED / REVIEW_PENDING
입력            conservative_event_map_v1.json (LF 해시 동결) 하나뿐
생성            Qwen2.5-7B-Instruct · bf16 · 4bit=false · greedy · max_new_tokens 4096 · 1회
결과            chapter 8개 · 0–600초 연속 · source event 160/160 참조 · 구조 이상 1건
판정            executor가 PASS/HOLD/INCONCLUSIVE를 계산하지 않았다
validator       PASS 31/31 · 재계산 결정성 확인
```

## A. provenance

```
prereg               9248116 (+errata 6b5a314 · 05762ef)
implementation       e3fcbed
conservative map     0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c (LF)
chapter prompt       CHAPTER_PROMPT_V1 · 템플릿 032fa497… · 렌더 481a5f60…
raw                  590e81943ff1f69dc0acb48d78e50c5c4c0d939cc56fcbe4e0c2550ffa14bb3e (3,544자)
generator(실효)       Qwen/Qwen2.5-7B-Instruct · revision a09a35458c702b33eeacc393d103063234e8bc28
                     dtype torch.bfloat16 · quantized false · sdpa · do_sample false ·
                     max_new_tokens 4096 · 생성 1회
실행                  랩 서버 4090 · VRAM 최대 15.35GB · 34.1초 · HF_HOME=/ssd/<SERVER_USER>/cache
새 VLM 추론 / Track A  0 / 미사용
```

**생성 전 환경 실패 1건(모델 출력 0바이트):** 첫 호출을 서버 기본 `python3`로 했다가
`ModuleNotFoundError: No module named 'torch'`로 즉시 죽었다. 모델이 올라가지 않았고
raw 파일도 만들어지지 않았다(생성물 0). 이후 프로젝트 venv
(`/ssd/<SERVER_USER>/envs/prj/bin/python`)로 **한 번만** 생성했다. 즉 생성물을 보고
다시 돌린 retry가 아니다 — runner는 raw가 있으면 실행 자체를 거부한다.

## B. chapter inventory

```
CH01    0– 48   Food preparation - initial steps               MIXED_EVIDENCE
CH02   48– 96   Food preparation - chopping and mixing         MIXED_EVIDENCE
CH03   96–192   Food preparation - cooking and shaping         LIMITED_EVIDENCE
CH04  192–264   Food preparation - finalizing and serving      MIXED_EVIDENCE
CH05  264–384   Eating and food preparation continuation       MIXED_EVIDENCE
CH06  384–480   Clothing and household tasks                   LIMITED_EVIDENCE
CH07  480–576   Gift wrapping and personal care                LIMITED_EVIDENCE
CH08  576–600   Exiting and final actions                      STABLE_DOMINANT
```

```
chapter 수        8 (허용 3–10 · 특정 개수 강제 없음)
숫자 confidence    0건 · 어휘 위반 0건
boundary_reason   ACTIVITY_CHANGE 2 · SCENE_OR_TASK_CHANGE 5 · SUSTAINED_TRANSITION 1
                  (chapter마다 1개씩 · 20초 미만 chapter 없음)
```

리뷰어가 볼 사실 하나: **유일한 `STABLE_DOMINANT`(CH08)가 교차 검증이 없는
single-source region(R11 · W23 단독)에 놓였다.** 사전등록에 이 조합을 막는 조항이
없어 이상으로 기록하지는 않았다(사후 게이트 추가 금지). Q1·Q3 판단 재료로 적어 둔다.

## C. timeline (요약)

```
CH01  0– 48   region R01,R02   unresolved [[0,24]]   event 8   창 W01
CH02 48– 96   region R03       conflict CB001,CB002  event 22  창 W01,W02,W03
CH03 96–192   region R04       conflict 없음          event 27  창 W03…W07
CH04 192–264  region R05       conflict CB003–CB005  event 17  창 W07…W10
CH05 264–384  region R06,R07   conflict CB006–CB008  event 27  창 W10…W15
CH06 384–480  region R08       conflict 없음          event 27  창 W15…W19
CH07 480–576  region R09,R10   conflict CB009,CB010  event 33  창 W19…W23
CH08 576–600  region R11       conflict 없음          event 6   창 W23
source event 160/160이 chapter 계보에 나타난다 (유실 0)
```

## D. boundary evidence

```
경계        reason                  앞 근거  뒤 근거  region        conflict/unresolved
0.0       ACTIVITY_CHANGE            0      0    R01           unresolved
48.0      SCENE_OR_TASK_CHANGE       5      8    R02,R03       conflict
96.0      SUSTAINED_TRANSITION       4      6    R03,R04       conflict
192.0     SCENE_OR_TASK_CHANGE       6      5    R04,R05       conflict
264.0     SCENE_OR_TASK_CHANGE       4      3    R05,R06       conflict
384.0     SCENE_OR_TASK_CHANGE       6      5    R07,R08       conflict
480.0     SCENE_OR_TASK_CHANGE       6      6    R08,R09       conflict
576.0     ACTIVITY_CHANGE            6      3    R10,R11       -
```

앞·뒤 근거는 경계 ±12초 안의 **map event 원문**이고 event id를 함께 기록했다
(executor가 결정적으로 파생 — 모델은 event id를 말하지 않았다: 출력에 등장한
event id 0건). 0.0 경계의 근거가 빈 것은 [0,24)에 valid 관측이 없기 때문이며
사전등록 §6이 그것을 채우는 것을 금지한다.

**구조 이상 1건 (자동 수정·재생성 없이 기록):**

```
ALL_BOUNDARIES_ON_24S_GRID — 내부 경계 7개가 전부 24초 격자에 있다
   경계 48·96·192·264·384·480·576 은 모두 region 경계와 일치한다
   (격자 밖 경계 0개)
```

사전등록 §2·§9는 격자 복사를 금지 사항으로 적었지만 **판정 게이트가 아니라 기록
대상**으로 동결했다. 그래서 executor는 이 결과를 고치거나 다시 생성하지 않고 그대로
올린다. Q2 `BOUNDARY_QUALITY` 판단은 리뷰어 몫이다.

## E. conflict handling

```
CONFLICT_BLOCK 10개 전부 chapter 계보에 포함 (CB001–CB010 · 미포함 0)
각 블록의 두 관측 source가 chapter 계보에 모두 남아 있다 (conflict_sources_preserved)
conflict 위반 0 · 승자 필드 0 · resolution 지정 0
```

생성물의 summary가 충돌을 어떻게 다뤘는지(원문 그대로):

```
CH01  "… Conflicting observations exist for subsequent steps."
CH02  "… Conflicting observations exist for some steps."
CH04  "… Conflicting observations exist for some steps."
CH05  "… Conflicting observations exist for some steps."
CH03/CH06/CH07  "Some steps are consistent across observations."
```

즉 conflict 구간을 덮는 chapter는 요약에서 불일치를 명시했고, 어느 창이 맞다고
쓰지 않았다. 다만 CH03·CH06·CH07의 "consistent across observations"는 리뷰어가
직접 확인할 문장이다(CH07은 CB009·CB010을 포함한다).

## F. unresolved handling

```
정책       coverage_from_zero_with_unresolved_opening_metadata (사전등록 §6 동결)
결과       CH01이 0–48을 덮고 unresolved_intervals [[0,24]]를 보존
내용       CH01 요약은 24초 이후의 관측(간장·카레·감자 선택)만 말한다 —
          [0,24)에 대한 서술 0건 · synthetic event 0건
검사       모든 member의 clip 시작이 24.0 이상 (validator)
```

## G. reviewer packet

```
runs/wvr_light_v1/chapter_v1_packet.md
  timeline · 격자 정렬 사실 · chapter별 근거·conflict·unresolved·창 목록 ·
  구조 이상 · Q1~Q4 (전부 NOT_ADJUDICATED) · 최종 어휘 1줄
runs/wvr_light_v1/chapter_v1_raw.txt        생성 raw (파싱 전 보존 · 해시 대조)
runs/wvr_light_v1/chapter_v1_prompt.txt     렌더된 프롬프트 전문
runs/wvr_light_v1/chapter_v1_record.json    런타임·해시·VRAM·소요
runs/wvr_light_v1/chapter_v1_chapters.json  chapter + 계보 + 안전검사 + 이상
runs/wvr_light_v1/chapter_v1_summary.json   요약
```

## H. 검증

```
self-check  scripts/wvr_chapter_selfcheck.py  PASS 13/13 (서버에서 GPU 전에 실행)
새 테스트    tests/test_wvr_chapter_v1.py  WVR-U01~U28  28/28
뮤테이션     U-M1~U-M22 전부 RED (구멍 0)
validator   scripts/wvr_chapter_validate.py  PASS 31/31
전체 스위트  4,936 passed · 2 skipped (porcelain 3건은 결과 커밋 전 dirty 탓)
경계 확인    제출본 5732075871fd… 불변 · official test 미접촉 · M9 미실행 ·
            conservative map·stitch verdicts·registry·mapping·W00 산출물 무변경 ·
            Overview·Analysis·Conclusion·HWPX 산출물 0건
```

주요 mutation(전부 RED): conflict 관측 한쪽만 남기기 · conflict 소실 감지 제거 ·
승자 필드 감지 제거 · unresolved 구간만으로 chapter 만들기 · unresolved 소실 감지 제거 ·
source event 없는 chapter 허용 · node 계보 삭제 · 격자 이상 기록 제거 ·
격자 계산 왜곡 · 시간축 검사 제거 · chapter 순서 역전 · 어휘 검사 제거 ·
Overview 필드 허용 · 환각 event id 허용 · executor가 판정 채우기 · Q4 삭제 ·
boundary 근거 제거 · raw 해시 대조 제거 · 재생성 거부 제거 ·
프롬프트에 기대 답 삽입 · 짧은 chapter 이상 기록 제거 · validator 격자 검사 무력화.

### H-1. 생성 전 정정 2건 (사전등록 errata)

```
errata 1 (6b5a314)  프롬프트 title 예시 "Food preparation"·"Garment handling"이
                    사전등록 §12의 expected macro-flow와 겹쳤다 → 이 영상과 무관한
                    "Vehicle maintenance"·"Whiteboard writing"으로 교체.
                    템플릿 b1448e5f→032fa497 · 렌더 ca7ec608→481a5f60
errata 2 (05762ef)  최초 동결 map 해시 ab1876fd…는 Windows 텍스트 모드가 만든 CRLF
                    사본의 해시였고 git blob·서버 체크아웃(LF)은 0ebecf34…였다.
                    플랫폼 의존 값이라 동결 대상이 될 수 없어 LF 정규형으로 갱신하고
                    산출물을 항상 LF로 쓰게 고쳤다.
둘 다 chapter raw·산출물이 0건인 시점의 정정이다.
```

### H-2. 생성 후 validator 정정 2건 (사전등록을 authority로)

결과를 본 뒤 validator 검사식 2개를 고쳤다. **둘 다 내 validator가 동결된 사전등록과
어긋난 경우이고, 사전등록이 authority다.** 사실을 숨기는 방향이 아니라 사실을 보고하는
방향으로 고쳤음을 밝힌다.

```
① boundaries_not_all_on_the_24s_grid (통과 게이트)
   → grid_alignment_recorded_and_not_hidden (기록·은폐 금지 검사)
   이유: 사전등록 §9는 격자 정렬을 "기록만 한다"로 동결했고 §10 blocker 목록에도 없다.
   현재 결과는 "내부 경계 7/7이 격자 위"이므로 통과 게이트로 두면 이 사건이
   INCONCLUSIVE로 처리되어 **리뷰어가 판단해야 할 Q2 재료가 사라진다.**
   새 검사는 격자 사실이 산출물에 그대로 기록되고, 전량 정렬이면 반드시
   ALL_BOUNDARIES_ON_24S_GRID 이상이 함께 남아 있어야 통과한다(WVR-U27이 고정).
② boundary_evidence_is_complete에서 "뒤 근거 비어 있음"을 무조건 위반으로 본 부분
   → unresolved 구간에서만 빈 근거를 허용한다.
   이유: [0,24)에는 valid 관측이 0건이고 사전등록 §6이 채우는 것을 금지한다.
   다른 경계에서 근거가 비면 여전히 FAIL이다(WVR-U28이 고정).
```

임계·어휘·chapter 수·정책은 하나도 바꾸지 않았고, 생성물은 재생성하지 않았다.

## I. 상태

```
WVR_SEMANTIC_CHAPTER_SHADOW_V1           EXECUTED / REVIEW_PENDING
WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1     CLOSED / CONSERVATIVE_EVENT_MAP_PASS (불변)
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1    CLOSED / EVENT_STITCHING_SHADOW_HOLD (불변)
WVR_EVENT_MAP_COVERAGE_SHADOW_V1         CLOSED / EVENT_MAP_SHADOW_HOLD (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1           CLOSED / INCONCLUSIVE (불변)
SUBDIVISION family                       STOPPED / NOT SUFFICIENT
0.25fps sufficiency NOT ESTABLISHED · 0.5fps PROVISIONAL ONLY
Production Event Extraction · Production Event Map · Production Semantic Chapter ·
Overview · Analysis · Conclusion · HWPX · submission promotion ·
official test · M9                       HOLD
```

리뷰어 어휘: `SEMANTIC_CHAPTER_SHADOW_PASS / HOLD / INCONCLUSIVE`.
Q1~Q4는 전부 `NOT_ADJUDICATED`다. 여기서 멈춘다.
