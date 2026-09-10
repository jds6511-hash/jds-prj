# WVR_EVENT_MAP_COVERAGE_SHADOW_V1 결과 (2026-09-10)

사전등록: `docs/preregistration/WVR_EVENT_MAP_COVERAGE_SHADOW_V1_2026-09-10.md`
(commit `7ba58de`) · 구현 `6773988` · **새 추론 0회 · GPU 미사용**

```
executor 상태     EXECUTED / REVIEW_PENDING
source           SHADOW_V1 W01–W23 (23창 VALID) · manifest a0726a4b… 무변경
W00              WINDOW_INVALID 유지 · event source 제외 · 재실행 없음
산출물             registry · coverage map · CANDIDATE_EVENT_MAP ·
                 chapter candidate · whole-video flow packet
validator        PASS (28/28) · 같은 입력 재계산 결과 동일(결정적)
reviewer verdict  계산하지 않았다 (PASS/HOLD/INCONCLUSIVE는 리뷰어 몫)
```

## A. provenance

```
prereg commit             7ba58dea1246688568af05598a7be9c897237689
implementation            677398885a95bbcbcdf7abfd228f0087da555719
derivation script commit  7ba58dea… (산출물에 기록)
source event              WVR_EVENT_EXTRACTION_SHADOW_V1
valid source manifest     a0726a4b13b4bd0f6e1ea692eec55e8cd0343132e32b532283e6e68511680631
                          (W01–W23 record+raw 46파일 · 실행 전 게이트가 대조)
video sha256              ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
새 추론                    0회 (Qwen·STT·caption 입력 없음)
```

각 event 행에 `source_window · source_raw_hash · source_collapse_hash ·
source_record_sha256`이 붙어 있다.

## B. source inventory

```
전체 창          24
VALID source    23 (W01–W23)
INVALID         1  (W00 [0,48) — status WINDOW_INVALID 그대로)
collapsed event 160건 (창당 최소 2 · 최대 12)
event ID        W01_E001 … W23_Exxx (결정적)
synthetic event 0건 · concat fallback 없음
```

## C. coverage (600초 기준)

```
window coverage      576.0초   96.00%   (VALID 창 [24,600))
event coverage       576.0초   96.00%   (collapsed event 구간 union)
redundant (window)   528.0초   88.00%   (2창 이상이 보는 시간)
redundant (event)    518.0초   86.33%   (2창 이상의 event가 덮는 시간)
unresolved            24.0초    4.00%
```

```
unresolved 구간          [0.0, 24.0)   ← 전부 INVALID_WINDOW_ONLY (W00 실패분)
single-window-only      58.0초  [24,48) · [86,96) · [576,600) 등
상태별 합               MULTI 518.0 · SINGLE 58.0 · INVALID_WINDOW_ONLY 24.0 ·
                       UNRESOLVED 0.0   (합 600.0)
```

`coverage percentage ≠ semantic correctness`. W00이 실패했지만 **잃은 시간은 [0,24)
24초뿐**이다 — `[24,48)`은 W01이 관찰했다.

## D. Candidate Event Map

```
event 160 → group 159 (여러 창 event가 합쳐진 group 1개)
relation 후보 160쌍  POSSIBLE_SAME_EVENT 1 · POSSIBLE_CONTINUATION 0 ·
                    POSSIBLE_TRANSITION 31 · POSSIBLE_CONFLICT 12 · UNRESOLVED 116
group 간 transition 158  POSSIBLE_TRANSITION 77 · UNRESOLVED 75 · POSSIBLE_CONFLICT 6
```

읽어야 할 사실: **겹침 구간에서 두 창의 서술이 문자열로 일치하는 경우가 거의 없다**(동일
판정 1건, 부분 공유 116건). 즉 중복 제거가 signature 완전일치로는 사실상 작동하지 않고,
같은 시간대를 두 창이 서로 다른 표현으로 기술한다. 이것이 리뷰어 Q3(EVENT_MAP_USABLE)의
핵심 재료다. 자동 라벨은 후보이며 판정 authority가 아니다.

conflict 후보 예(같은 시각·공통 토큰 0):

```
W18_E002 ↔ W19_E001 (겹침 4.0초)   W18_E003 ↔ W19_E003 (4.0초)
W18_E003 ↔ W19_E004 (2.0초)        W19_E008 ↔ W20_E003 (2.0초)      … 총 12건
```

전문은 `runs/wvr_light_v1/event_map_v1_candidate_map.json`, 시간순 흐름은
`event_map_v1_flow_packet.md`에 있다.

## E. Semantic Chapter candidate

```
chapter 후보 8개 · boundary 후보 49개 중 7개 채택 · 42개는 MIN_CHAPTER_SEC(60초)로 억제
boundary 값  103 · 184 · 260 · 336 · 400 · 460 · 528초
             → 전부 group start에서 나왔고 24초 격자에 종속되지 않는다
```

```
CH01   24.0–104.0   group 30  창 W01–W04    상태 SINGLE+MULTI  frame 40
CH02  103.0–185.0   group 22  창 W03–W07    MULTI              frame 41
CH03  184.0–264.0   group 18  창 W06–W10    MULTI              frame 40
CH04  260.0–360.0   group 15  창 W10–W13    MULTI              frame 50
CH05  336.0–400.0   group 13  창 W14–W16    MULTI              frame 32
CH06  400.0–460.0   group 16  창 W15–W19    MULTI              frame 30
CH07  460.0–529.0   group 22  창 W18–W21    MULTI              frame 35
CH08  528.0–600.0   group 23  창 W21–W23    MULTI              frame 36
```

인접 chapter 구간이 1초씩 겹치는 것은 group 구간이 창 겹침 때문에 뒤 chapter 시작을 넘어
끝나기 때문이다(예: CH01 끝 104.0 · CH02 시작 103.0). 억지로 자르지 않고 그대로 남겼다.
**chapter 제목·narrative는 생성하지 않았고 semantic 경계는 확정하지 않았다**
(`semantic_boundary_confirmed: false`).

## F. whole-video flow packet

`runs/wvr_light_v1/event_map_v1_flow_packet.md` — 0–600초를 chapter candidate 단위로
시간순 정리했고 각 행에 `시간 · actor · action · object/state · source window(s) ·
coverage 상태 · frame 수`가 있다. 합쳐진 group은 member event id와 각자의 구간을 함께
적었다. transition 후보와 억제된 boundary도 같은 파일에 있다.

앞부분 예(원문 그대로 · 판정 아님):

```
 24.0– 28.0 | person | selecting | bottle of soy sauce      | W01 | SINGLE
 34.0– 37.0 | person | placing   | potatoes in steamer      | W01 | SINGLE
 55.0– 72.0 | person | chopping  | onion                    | W01 | MULTI
 58.0– 62.0 | person | stirring  | breadcrumbs with oil     | W02 | MULTI
 82.0– 88.0 | person | stirring  | breadcrumbs in bowl      | W02,W03 | MULTI  ← 합쳐진 group
```

## G. anomalies (리뷰어가 먼저 볼 것)

```
conflict 후보                12건 (전부 겹침 2–4초 구간)
UNRESOLVED relation         116건 (부분 토큰 공유 — 자동 판정 불가)
single-window-only 구간      58.0초 (교차 확인 불가)
uncovered 구간               [0,24) 24초 (W00 실패 · 추정으로 채우지 않았다)
invalid-source 의존 event     0건
mixed-signature group        0건
```

## H. 의미 / 비의미

말하는 것:

```
23창 VALID output만으로 [24,600) 576초(96%)에 대해 event 근거가 있고,
  518초(86.33%)는 2개 이상 창이 교차 관찰했다
W00 실패로 잃은 시간은 [0,24) 24초뿐이다 — 앞부분 전체를 잃지 않았다
결정적 후처리로 registry·coverage·candidate map·chapter 후보·flow packet이 만들어졌다
  (같은 입력 재계산 결과 동일)
겹침 구간의 서술 일치율이 매우 낮다 — 동일 판정 1건 대비 부분 공유 116건 · 충돌 후보 12건
```

말하지 않는 것 (사전등록 §14):

```
Event extraction solved · 0.5fps sufficient · all events factual · production ready
chapter 경계가 확정됐다 · candidate map이 사실이다 · SHADOW_V1이 PASS가 됐다
```

허용되는 최대 결론은 사전등록 문구 그대로다:

```
Existing valid C01 local-window observations were sufficient to construct a usable
shadow candidate of the video's global event flow despite explicitly preserved
unresolved coverage.
```

이 문장의 "usable" 여부도 executor가 아니라 리뷰어가 판정한다.

## I. 리뷰어 판정 (2026-09-10 · 접수)

```
Q1 FLOW_RECOVERABLE   COARSELY YES        576초 coverage · 160 event 시간순 배치 ·
                                          24초 격자와 독립적인 boundary 후보 생성
                                          단 "신뢰 가능한 event sequence"는 아니다
Q2 GAP_MATERIALITY    NOT PRIMARY BLOCKER [0,24) 24초는 전체 4% · [24,48)은 W01이 관찰 ·
                                          single-window-only 58초는 redundancy 부족일 뿐
                                          → Event Map 병목을 W00 gap으로 돌리면 안 된다
Q3 EVENT_MAP_USABLE   NO                  160 event → 159 group · SAME 1 · CONFLICT 12 ·
                                          UNRESOLVED 116 — overlap 88%를 확보했는데도
                                          stitch가 사실상 되지 않았다
                                          chapter 후보 8개는 기술적 생성물이다

FINAL   EVENT_MAP_SHADOW_HOLD
병목     Local Events → ★ Event stitching ← 여기 → Event Map → Semantic Chapters
후속     WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1 (승인 · 문자열 기반 stitching의 한계가
        설계 신호로 확인됨). W00·fps·prompt로 돌아가지 않는다.
```

## I-2. 원래의 리뷰어 질문 (판정 전 기록)

```
Q1 FLOW_RECOVERABLE   23창 event만으로 주요 activity sequence·큰 transition·
                      temporal progression을 식별할 수 있는가
Q2 GAP_MATERIALITY    [0,24) 24초 공백과 single-window-only 58초가 Overview를
                      왜곡할 정도로 중요한가
Q3 EVENT_MAP_USABLE   겹침 구간 서술 불일치(116 UNRESOLVED · 12 CONFLICT)를 안은
                      candidate map이 Semantic Chapters 입력으로 쓸 만한가
verdict 어휘           EVENT_MAP_SHADOW_PASS / HOLD / INCONCLUSIVE
```

## J. 검증

```
새 테스트   tests/test_wvr_event_map_v1.py  WVR-R01~R37  37/37
뮤테이션    R-M1~R-M46 전부 RED (구멍 없음)
전체 스위트  4,838 passed · 2 skipped · 0 failed
validator  scripts/wvr_event_map_validate.py  PASS 28/28
           (W00 배제 · synthetic 0 · unresolved 보존 · coverage 산술 일치 ·
            chapter boundary 격자 비종속 · 재계산 결정성 · 새 추론 0)
clean tree · HEAD == origin/master
경계 확인   SHADOW_V1 source 46파일 무변경 · W00 산출물 무변경 ·
           SHADOW blind map 미접촉(reveal 없음) ·
           현행 제출본 5732075871fd… 불변 · official test 미접촉
```

## K. 상태

```
WVR_EVENT_MAP_COVERAGE_SHADOW_V1   EXECUTED / REVIEW_PENDING
WVR_EVENT_EXTRACTION_SHADOW_V1     CLOSED / INCONCLUSIVE (불변)
TRIGGER_ISOLATION_V1 · VISUAL_CONTENT_ISOLATION_V1   불변
SUBDIVISION family                 STOPPED / NOT SUFFICIENT
ZERO_DURATION_EXEMPLAR_ISOLATION_V1  NOT EXECUTED / SUPERSEDED (추론 0회·산출물 0건)
0.25fps semantic sufficiency       NOT ESTABLISHED
0.5fps                             PROVISIONAL WORKING DENSITY ONLY
production Event extraction        HOLD
Semantic Chapter production · Overview · Analysis · Conclusion · HWPX ·
submission promotion · official test · M9                        HOLD
```

리뷰어 PASS 시 다음 후보는 `WVR_SEMANTIC_CHAPTER_SHADOW_V1`, 그 다음이
`WVR_OVERVIEW_SHADOW_V1`이다. 순서를 건너뛰지 않는다.

## L. 산출물

```
runs/wvr_light_v1/event_map_v1_registry.json            Local Event Registry (160건)
runs/wvr_light_v1/event_map_v1_coverage.json            Coverage Map (구간 상태 timeline)
runs/wvr_light_v1/event_map_v1_candidate_map.json       CANDIDATE_EVENT_MAP
runs/wvr_light_v1/event_map_v1_chapter_candidates.json  chapter 후보 8개 + 억제 기록
runs/wvr_light_v1/event_map_v1_flow_packet.md           whole-video flow packet
runs/wvr_light_v1/event_map_v1_summary.json             요약·anomaly·provenance
src/wvr_event_map_v1.py · scripts/wvr_event_map_build.py ·
scripts/wvr_event_map_validate.py · tests/test_wvr_event_map_v1.py
```

여기서 멈춘다. 리뷰어 판정 대기.
