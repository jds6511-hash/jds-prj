# WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1 사전등록 (2026-09-10)

승인: 리뷰어 결정 — **stitching rule 검증 probe (새 추론 0회 · GPU 불필요)**.
이 문서는 산출물 생성 전에 커밋한다. **결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

Event Map 전체를 다시 만들지 않는다. Semantic Chapter로 넘어가지 않는다.

## 0. 선행 판정 (동결)

```
WVR_EVENT_MAP_COVERAGE_SHADOW_V1   CLOSED / EVENT_MAP_SHADOW_HOLD
  Q1 FLOW_RECOVERABLE   COARSELY YES        (576초 coverage · 160 event 시간순 배치)
  Q2 GAP_MATERIALITY    NOT PRIMARY BLOCKER ([0,24) 24초 = 4% · [24,48)은 W01이 관찰)
  Q3 EVENT_MAP_USABLE   NO                  ← HOLD 사유
  근거   160 event → 159 group · SAME_EVENT 1 · CONFLICT 12 · UNRESOLVED 116
        overlap을 88% 확보했는데도 stitch가 사실상 되지 않았다
        chapter 후보 8개는 기술적 생성물이고 의미 있는 chapter 확인이 아니다
```

병목 위치:

```
Video → Local Events (확보) → ★ Event stitching (현재 병목) →
Event Map → Semantic Chapters → Overview
```

W00·fps·prompt로 돌아가지 않는다.

## 1. Primary question 하나

```
인접 local window의 공유 24초 overlap에서, 서로 다른 표현으로 기술된 Local Event를
의미적으로 SAME / CONTINUATION / TRANSITION / CONFLICT로 구분할 수 있는가?
```

비교 단위는 **event 한 줄 대 한 줄이 아니라 overlap-local event sequence**다.
문자열 완전일치를 PASS 기준으로 쓰지 않는다(이미 비현실적임이 실측됐다).

## 2. 입력 (읽기 전용 · 새 추론 0회)

```
source            runs/wvr_light_v1/shadow_v1_W01…W23.json (+ _raw.txt)
manifest sha      a0726a4b13b4bd0f6e1ea692eec55e8cd0343132e32b532283e6e68511680631
                  (EVENT_MAP_COVERAGE_SHADOW_V1과 같은 동결 manifest)
registry          runs/wvr_light_v1/event_map_v1_registry.json (event ID 계보 재사용)
frame bank        runs/wvr_light_v1/shadow_frame_bank.json (공유 프레임 traceability)
W00               invalid source — 이번에도 사용하지 않는다
```

새 Qwen visual inference · 새 STT · caption 입력 · 새 LLM 호출 없음.
raw artifact 수정 금지. 전체 600초 재생성 금지.

## 3. 대상 overlap 22개 (valid-valid adjacency)

```
O02 (W01,W02) [48,72)      O03 (W02,W03) [72,96)      …      O23 (W22,W23) [552,576)
개수    22        각 overlap 길이 24.0초        공유 0.5fps 프레임 12장
제외    O01 (W00,W01) — W00이 INVALID source다
```

각 overlap에서 두 창의 collapsed event 중 공유 구간과 교차하는 것만 그 구간으로 clip해
보여준다. 원본은 수정하지 않고 아래를 보존한다.

```
event_id · source_window(blind 대상) · original_start · original_end ·
clipped_start · clipped_end · actor · action · object_or_state
```

## 4. blinding (절차 동결)

overlap마다 두 창을 `Arm A` / `Arm B`로 가린다. 어느 쪽이 앞선 창인지 숨긴다.

```
label = sha256("<prereg_sha>|<overlap_id>").digest()[0] & 1
        flip=1 → earlier=B · later=A          flip=0 → earlier=A · later=B
```

같은 입력이면 같은 출력이고 실행 후 바뀌지 않는다. 절차적 blinding이다 — 산출물
파일명·mapping 파일에서 복원 가능하므로 packet만 읽는다는 규율에 의존한다.
**reviewer verdict 기록 전 reveal 금지.**

## 5. reviewer 어휘 (executor가 채우지 않는다)

overlap별 sequence relation:

```
SAME_EVENT · CONTINUATION · TRANSITION · CONFLICT · UNRESOLVED
```

overlap별 상위 판정:

```
STITCHABLE          두 arm 서술이 같은 사건 흐름으로 이어붙일 수 있다
MATERIAL_CONFLICT   같은 시간대에 report-material로 양립 불가한 서술이 있다
UNRESOLVED          packet 정보만으로는 판단할 수 없다
```

판정 기준은 **문자열 일치가 아니라 report-material contradiction**이다.
예: `자른다` vs `섞는다`는 연속 행동일 수 있다(→ CONTINUATION/STITCHABLE 후보).
`요리한다` vs `옷을 재봉한다`가 같은 시간대면 material conflict다.

## 6. executor가 하는 것 / 하지 않는 것

한다:

```
22 overlap의 blinded sequence packet 생성 (Arm A/B · clip · 공유 프레임 수)
결정적 audit 지표 계산 (AUDIT_DIAGNOSTIC_ONLY)
mapping 파일 봉인 저장 · verdict 기록 도구 제공 (입력이 있을 때만 기록)
```

하지 않는다:

```
relation·상위 판정 채우기 · 새 임계/유사도 점수 도입 · Event Map 재생성 ·
Adjudicated Event Map 생성 · Semantic Chapter · Overview · 새 추론 ·
event 텍스트 수정 · 부족한 구간 추정 보완
```

## 7. audit 지표 (AUDIT_DIAGNOSTIC_ONLY · 판정 authority 아님)

overlap마다 아래를 계산해 기록만 한다. **임계값·점수 컷을 만들지 않는다.**

```
arm별 event 수 · clip된 event 수 · arm별 총 서술 시간
정규화 signature 완전일치 쌍 수 (기존 v2.signature)
기존 frozen v2.semantic_relation 분포 (equivalent / different / adjudication)
arm별 actor 집합 · action 집합 · object 토큰 집합
sequence 수준 토큰 교집합 크기 · 각 arm 고유 토큰 수
시간 정렬 상태 (arm별 event 수 차이 · 최초/최종 시각)
공유 프레임 시각 12개
```

`v2.semantic_relation`은 기존 동결 규칙(완전일치 / 공통 토큰 0 / 그 사이)이며 새 규칙을
추가하지 않는다.

## 8. verdict 기록 도구

`scripts/wvr_stitch_verdicts.py`는 리뷰어 입력 파일을 받아서만 기록한다.

```
어휘 검증      위 5개 relation · 3개 상위 판정만 허용
누락 허용      기록되지 않은 overlap은 NOT_ADJUDICATED로 남는다
executor 기본  아무 판정도 기록하지 않는다 (빈 상태로 시작)
reveal        모든 22 overlap 판정이 기록된 뒤에만 mapping reveal이 허용된다
```

## 9. 이번 사건의 상태 어휘

```
executor 상태   EXECUTED / REVIEW_PENDING
리뷰어 최종     STITCHING_SHADOW_PASS 후보  대부분 STITCHABLE이고
                                       material conflict가 report flow를 깨지 않음
              STITCHING_SHADOW_HOLD      material conflict가 많거나 flow를 깬다
              STITCHING_SHADOW_INCONCLUSIVE  packet만으로 판단 불가가 지배적
```

executor는 이 최종 판정을 계산하지 않는다. 임계 percentage를 결과 보고 만들지 않는다.

## 10. 해석 제한

PASS가 나와도 금지:

```
Event Map이 검증됐다 · stitching이 해결됐다 · 0.5fps sufficient ·
Semantic Chapter로 바로 간다 · production ready
```

허용되는 최대 결론:

```
사람이 22개 overlap 대부분을 stitchable로 판정했다면, Local Event 표현은
Adjudicated Event Map 구축을 시도할 최소 조건을 만족한다.
```

HOLD여도 `Local Event representation이 근본적으로 실패다`로 일반화하지 않는다 —
그때 무엇을 고칠지는 리뷰어가 정한다.

## 11. 하지 않을 것

```
W00 재실행·복구 · prompt/schema 변경 · token cap 변경 · fps 변경 ·
subdivision 재개 · 다른 shift · 새 Qwen/STT/LLM 호출 ·
Adjudicated Event Map 생성 · Semantic Chapter · Overview · Analysis ·
Conclusion · HWPX · submission promotion · official test 접촉 · M9
```

## 12. 최소 invariant (테스트로 고정)

```
overlap 정확히 22개 (O02…O23) · 각 24.0초 · 공유 프레임 12개
W00 및 O01은 대상에서 제외
clip은 원본 event를 수정하지 않고 original_start/end를 보존한다
비교 단위는 sequence — arm별 event 목록 전체를 함께 제시한다
blinding은 결정적이고 A/B가 상보적이다 · packet에 창 id가 노출되지 않는다
audit 지표에 임계값·점수 컷이 없다
executor가 relation·상위 판정을 채우지 않는다 (기본 NOT_ADJUDICATED)
verdict 도구는 동결 어휘 외 입력을 거부한다
모든 판정 기록 전에는 mapping reveal이 거부된다
source manifest 무변경 · 새 추론 0회 · registry event ID 계보 유지
현행 제출본 무변경 · official test 미개방 · SHADOW blind map 미접촉
```

mutation suite RED 확인 + full suite 실행.

## 13. 실행 순서

```
1  prereg 작성        2  prereg commit        3  implementation/tests commit
4  source manifest·registry 검증               5  22 overlap sequence 추출·clip
6  blinded packet 생성 · mapping 봉인 저장       7  audit 지표 계산
8  validator          9  tests/mutations/full suite
10 clean tree         11 result commit         12 STOP (리뷰어 판정 대기)
```

GPU 추론은 필요하지 않다.

## 14. 산출물 이름

```
runs/wvr_light_v1/stitch_v1_pairs.json      overlap별 arm sequence (blind 라벨 적용)
runs/wvr_light_v1/stitch_v1_packet.md       blinded reviewer packet (22 overlap)
runs/wvr_light_v1/stitch_v1_blind_map.json  mapping (봉인 · reveal 조건 §8)
runs/wvr_light_v1/stitch_v1_audit.json      AUDIT_DIAGNOSTIC_ONLY 지표
runs/wvr_light_v1/stitch_v1_summary.json    요약·계보·상태
runs/wvr_light_v1/stitch_v1_verdicts.json   리뷰어 판정 기록 (입력이 있을 때만)
```

## 15. 실행 후 상태

```
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1   EXECUTED / REVIEW_PENDING
WVR_EVENT_MAP_COVERAGE_SHADOW_V1        CLOSED / EVENT_MAP_SHADOW_HOLD (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1          CLOSED / INCONCLUSIVE (불변)
SUBDIVISION family                      STOPPED / NOT SUFFICIENT
0.25fps sufficiency NOT ESTABLISHED · 0.5fps PROVISIONAL ONLY
production Event extraction · Adjudicated Event Map · Semantic Chapter ·
Overview · Analysis · Conclusion · HWPX · submission promotion ·
official test · M9                      HOLD
```

리뷰어 PASS 후에만 `Adjudicated Event Map` 구축 → `WVR_SEMANTIC_CHAPTER_SHADOW_V1`로
간다. 순서를 건너뛰지 않는다. 여기서 멈춘다.
