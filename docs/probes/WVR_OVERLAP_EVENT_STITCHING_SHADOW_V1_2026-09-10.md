# WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1 결과 (2026-09-10)

사전등록:
`docs/preregistration/WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md`
(commit `4108125`) · 구현 `872ef94` · **새 추론 0회 · 새 LLM 호출 0회 · GPU 미사용**

```
사건 상태        CLOSED / EVENT_STITCHING_SHADOW_HOLD (리뷰어 판정 · §I)
대상            valid-valid adjacency 22개 (O02…O23) · 각 24초 · 공유 프레임 12장
packet          blinded (Arm A/B) · 창 id·event id 미노출 · 판정 후 reveal (§D-2)
비교 단위        overlap-local event sequence (event 한 줄 매칭 아님)
판정             22/22 기록 · STITCHABLE 12 · MATERIAL_CONFLICT 10 · UNRESOLVED 0
validator       PASS (27/27) · 같은 입력 재계산 결과 동일
```

## A. provenance

```
prereg commit             41081254f9004d8bb4d9cfdd5b3bfaf5ee820165  (blinding salt)
implementation            872ef94fbb10dcfdefa2366d85adad93b734d9bf
registry source           event_map_v1_registry.json (160 event · EVENT_MAP_COVERAGE_V1)
source manifest sha       a0726a4b13b4bd0f6e1ea692eec55e8cd0343132e32b532283e6e68511680631
video sha256              ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
새 추론 / 새 LLM 호출       0 / 0
```

## B. packet 구성

```
overlap 22개        O02 [48,72) … O23 [552,576)   (O01 = W00–W01 제외)
arm event 총계       165건 (overlap마다 두 arm의 clip된 sequence)
arm별 event 수       최소 1 · 최대 7 · 두 arm 차이 최대 5
공유 프레임          overlap마다 12개 시각 (0.5fps) 병기 — traceability 전용
clip                공유 구간으로 자르고 원본 구간을 함께 표시 (`(원본 70.0–74.0)`)
blind               Arm A/B는 prereg SHA 기반 결정적 배정 · A/B 상보 ·
                   packet·pairs·audit 어디에도 창 id·event id 없음
mapping            runs/wvr_light_v1/stitch_v1_blind_map.json (봉인 · local_id 대응 포함)
```

packet 예 (O02 · 원문 그대로 · 판정 아님):

```
### Arm A  (event 7개)
  48.0– 52.0 | person | placing  | bread pieces into blender
  52.0– 55.0 | person | placing  | lid on blender
  55.0– 58.0 | person | pouring  | oil into bowl of breadcrumbs
  58.0– 62.0 | person | stirring | breadcrumbs with oil
  62.0– 66.0 | person | chopping | onion on cutting board
  66.0– 70.0 | person | chopping | carrot on cutting board
  70.0– 72.0 | person | placing  | ground beef into bowl   (원본 70.0–74.0)

### Arm B  (event 4개)
  48.0– 49.0 | person | blending | potato slices   (원본 46.0–49.0)
  49.0– 52.0 | person | pouring  | oil into bowl with curry powder
  52.0– 55.0 | person | mixing   | curry powder and oil
  …
```

이 예가 리뷰어가 판정할 전형적 모양이다 — 같은 24초를 두 창이 **다른 입도·다른 표현**으로
기술한다. 한 줄 대 한 줄로는 매칭되지 않지만 흐름으로 보면 이어질 수 있는지가 질문이다.

## C. audit 지표 (AUDIT_DIAGNOSTIC_ONLY · 임계 없음)

```
signature 완전일치 쌍 총계        1건 (22 overlap 전체에서)
쌍별 frozen relation 분포        EQUIVALENT 1 · DIFFERENT 44 · ADJUDICATION_REQUIRED 264
sequence 토큰 교집합 크기         최소 1 · 중앙값 5 · 최대 10
두 arm event 수 차이             최대 5
빈 arm이 있는 overlap            없음
토큰 교집합이 0인 overlap         없음
```

읽는 방식: **문자열 일치(1건)는 사실상 없지만, 모든 overlap에 최소 1개 이상의 공통 토큰이
있다.** 즉 두 창이 완전히 무관한 장면을 말하는 경우는 자동 지표상 하나도 없다. 이 수치는
판정 authority가 아니며 임계·점수 컷을 만들지 않았다(`threshold_used: false`).

## D. 리뷰어 판정 (기록 완료 · 2026-09-10)

리뷰어가 blinded packet만 보고 22개를 독립 판정했고, executor는 그것을 그대로 기록했다
(`runs/wvr_light_v1/stitch_v1_verdicts.json` · `recorded_by: reviewer` ·
`final_verdict: null` — 산출물의 최종 verdict 필드는 **executor가 계산하지 않으므로
비워 둔다**. 리뷰어 최종 판정은 §I에 적는다).

```
adjudicated       22 / 22 (complete)
relation          SAME_EVENT 6 · CONTINUATION 5 · TRANSITION 1 · CONFLICT 10 · UNRESOLVED 0
상위 판정          STITCHABLE 12 · MATERIAL_CONFLICT 10 · UNRESOLVED 0
```

| overlap | relation | 상위 판정 | overlap | relation | 상위 판정 |
| --- | --- | --- | --- | --- | --- |
| O02 | CONFLICT | MATERIAL_CONFLICT | O13 | CONFLICT | MATERIAL_CONFLICT |
| O03 | CONFLICT | MATERIAL_CONFLICT | O14 | CONFLICT | MATERIAL_CONFLICT |
| O04 | SAME_EVENT | STITCHABLE | O15 | CONFLICT | MATERIAL_CONFLICT |
| O05 | CONTINUATION | STITCHABLE | O16 | SAME_EVENT | STITCHABLE |
| O06 | CONTINUATION | STITCHABLE | O17 | SAME_EVENT | STITCHABLE |
| O07 | CONTINUATION | STITCHABLE | O18 | SAME_EVENT | STITCHABLE |
| O08 | CONFLICT | MATERIAL_CONFLICT | O19 | TRANSITION | STITCHABLE |
| O09 | CONFLICT | MATERIAL_CONFLICT | O20 | CONFLICT | MATERIAL_CONFLICT |
| O10 | CONFLICT | MATERIAL_CONFLICT | O21 | CONFLICT | MATERIAL_CONFLICT |
| O11 | CONTINUATION | STITCHABLE | O22 | SAME_EVENT | STITCHABLE |
| O12 | CONTINUATION | STITCHABLE | O23 | SAME_EVENT | STITCHABLE |

기록·확인·reveal 방법:

```
python scripts/wvr_stitch_verdicts.py --runs runs/wvr_light_v1 --input <판정.json>
확인   python scripts/wvr_stitch_verdicts.py --runs runs/wvr_light_v1
reveal python scripts/wvr_stitch_verdicts.py --runs runs/wvr_light_v1 --reveal
```

## D-2. mapping reveal (판정 기록 후에만 실행)

22개 전부 기록돼 `reveal_allowed=True`가 된 뒤 실행했다. **판정은 reveal 전에 확정됐고
reveal 후 한 글자도 바꾸지 않았다.**

```
overlap  구간        Arm A  Arm B   판정
O02       48– 72     W02    W01    CONFLICT     / MATERIAL_CONFLICT
O03       72– 96     W02    W03    CONFLICT     / MATERIAL_CONFLICT
O04       96–120     W04    W03    SAME_EVENT   / STITCHABLE
O05      120–144     W04    W05    CONTINUATION / STITCHABLE
O06      144–168     W05    W06    CONTINUATION / STITCHABLE
O07      168–192     W07    W06    CONTINUATION / STITCHABLE
O08      192–216     W07    W08    CONFLICT     / MATERIAL_CONFLICT
O09      216–240     W08    W09    CONFLICT     / MATERIAL_CONFLICT
O10      240–264     W10    W09    CONFLICT     / MATERIAL_CONFLICT
O11      264–288     W11    W10    CONTINUATION / STITCHABLE
O12      288–312     W12    W11    CONTINUATION / STITCHABLE
O13      312–336     W13    W12    CONFLICT     / MATERIAL_CONFLICT
O14      336–360     W13    W14    CONFLICT     / MATERIAL_CONFLICT
O15      360–384     W15    W14    CONFLICT     / MATERIAL_CONFLICT
O16      384–408     W15    W16    SAME_EVENT   / STITCHABLE
O17      408–432     W17    W16    SAME_EVENT   / STITCHABLE
O18      432–456     W18    W17    SAME_EVENT   / STITCHABLE
O19      456–480     W19    W18    TRANSITION   / STITCHABLE
O20      480–504     W19    W20    CONFLICT     / MATERIAL_CONFLICT
O21      504–528     W20    W21    CONFLICT     / MATERIAL_CONFLICT
O22      528–552     W22    W21    SAME_EVENT   / STITCHABLE
O23      552–576     W23    W22    SAME_EVENT   / STITCHABLE
```

blinding 실효성: 22개 중 **9개는 earlier 창이 Arm A**, **13개는 earlier 창이 Arm B**였다.
즉 Arm 라벨은 시간 순서와 일정한 관계가 없었고, 리뷰어가 라벨로 순서를 추정할 수 없었다.

reveal 후 계산한 **기술적 사실**(판정 아님):

```
MATERIAL_CONFLICT 구간(병합)   [48,96) [192,264) [312,384) [480,528)   총 240초
STITCHABLE 구간(병합)          [96,192) [264,312) [384,480) [528,576)  총 288초
                              (240+288 = 528 = 22 × 24초, 빠짐 없음)
conflict에 1회 이상 참여한 창    14 / 23 (W01–W03 · W07–W10 · W12–W15 · W19–W21)
conflict 무참여 창              9 / 23 (W04–W06 · W11 · W16–W18 · W22–W23)
```

자동 지표는 이 판정을 예측하지 못했다:

```
shared_token_count   STITCHABLE 최소3·중앙7·최대10   MATERIAL_CONFLICT 최소1·중앙3·최대10
event 수 차이 중앙값   STITCHABLE 1.5                MATERIAL_CONFLICT 2.5
완전일치 쌍 1건        O03(W02_E010 ↔ W03_E004) — 그 overlap의 판정은 MATERIAL_CONFLICT다
```

즉 **문자열 완전일치가 나온 유일한 overlap이 오히려 material conflict로 판정됐다.**
이 수치들은 임계로 쓰지 않는다(`threshold_used: false` 유지) — 판정 authority는 사람이다.

## E. 의미 / 비의미

말하는 것:

```
22개 overlap의 sequence-대-sequence 비교 재료가 blinded 상태로 준비됐고, 리뷰어가
  22개 전부를 판정했다 (STITCHABLE 12 · MATERIAL_CONFLICT 10 · UNRESOLVED 0)
비교 자체는 가능했다 — 판정 불가(UNRESOLVED)로 남은 overlap이 0개다
자동 지표상 완전 무관(공통 토큰 0) overlap은 0개이고, 완전일치는 1건뿐이며
  그 1건은 오히려 MATERIAL_CONFLICT 판정을 받았다
executor는 어떤 판정도 채우지 않았고 reveal은 22개 기록 후에 했다
새 추론·새 LLM 호출 없이 기존 23창 output만 사용했다
```

말하지 않는 것 (사전등록 §10):

```
Event Map이 검증됐다 · stitching이 해결됐다 · 0.5fps sufficient ·
Semantic Chapter로 바로 간다 · production ready ·
Local Event representation이 근본적으로 실패다 · 문자열 일치율이 곧 품질이다
```

허용되는 최대 결론(리뷰어 판정 후):

```
사람이 22개 overlap 대부분을 stitchable로 판정했다면, Local Event 표현은
Adjudicated Event Map 구축을 시도할 최소 조건을 만족한다.
```

## F. 검증

```
새 테스트   tests/test_wvr_stitch_v1.py  WVR-S01~S33  33/33
뮤테이션    S-M1~S-M46 전부 RED (구멍 없음)
전체 스위트  4,871 passed · 2 skipped · 0 failed
validator  scripts/wvr_stitch_validate.py  PASS 27/27 (판정 기록 **전**, commit ef5ccf7 시점)
           (O01·W00 제외 · pairs에 창/event id 없음 · audit blind·임계 없음 ·
            판정 미기록 · reveal 거부 · 재계산 결정성 · Event Map 재생성 차단)
clean tree · HEAD == origin/master
           판정 기록 후 다시 돌리면 `executor_filled_no_verdict`·`reveal_refused_now`
           2개가 False가 된다 — 이 두 검사는 **판정 기록 이전 상태**를 고정하는
           검사이고, 리뷰어가 22건을 기록하면 정의상 뒤집힌다. 결과를 본 뒤
           검사식을 고치지 않았다(사후 게이트 변경 금지). executor가 채우지
           않았다는 증거는 산출물 필드로 남는다 — `recorded_by: reviewer` ·
           `final_verdict: null` · `final_verdict_by_executor: false` ·
           mapping 파일 자체는 무변경(reveal은 읽기 전용 출력이다).
경계 확인   SHADOW source 46파일 무변경 · W00 산출물 무변경 · registry 무변경 ·
           SHADOW_V1 blind map 미접촉 · 현행 제출본 5732075871fd… 불변 ·
           official test 미접촉
```

## G. 상태

```
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1   CLOSED / EVENT_STITCHING_SHADOW_HOLD (§I)
WVR_EVENT_MAP_COVERAGE_SHADOW_V1        CLOSED / EVENT_MAP_SHADOW_HOLD (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1          CLOSED / INCONCLUSIVE (불변)
SUBDIVISION family                      STOPPED / NOT SUFFICIENT
ZERO_DURATION_EXEMPLAR_ISOLATION_V1     NOT EXECUTED / SUPERSEDED
0.25fps sufficiency NOT ESTABLISHED · 0.5fps PROVISIONAL ONLY
production Event extraction · Adjudicated Event Map · Semantic Chapter ·
Overview · Analysis · Conclusion · HWPX · submission promotion ·
official test · M9                      HOLD
```

## H. 산출물

```
runs/wvr_light_v1/stitch_v1_packet.md       blinded reviewer packet (22 overlap)
runs/wvr_light_v1/stitch_v1_pairs.json      arm sequence (local_id만 · 창/event id 없음)
runs/wvr_light_v1/stitch_v1_audit.json      AUDIT_DIAGNOSTIC_ONLY 지표 (임계 없음)
runs/wvr_light_v1/stitch_v1_blind_map.json  mapping (봉인 · local_id 대응 포함)
runs/wvr_light_v1/stitch_v1_summary.json    요약·계보·상태
runs/wvr_light_v1/stitch_v1_verdicts.json   리뷰어 판정 22건 (recorded_by: reviewer)
src/wvr_stitch_v1.py · scripts/wvr_stitch_build.py ·
scripts/wvr_stitch_verdicts.py · scripts/wvr_stitch_validate.py ·
tests/test_wvr_stitch_v1.py
```

## I. 리뷰어 판정 (2026-09-10)

```
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1   CLOSED / EVENT_STITCHING_SHADOW_HOLD
```

리뷰어 근거(원문 요지):

```
PASS 아님    22개 중 10개에서 report-material conflict가 났다. 이 상태로 자동 병합해
            Chapter로 올리면 잘못된 사건이 Overview에 섞일 위험이 크다.
INCONCLUSIVE 아님  비교는 충분히 가능했고(UNRESOLVED 0), 문제 위치가 명확히 측정됐다.
따라서 HOLD.
```

리뷰어가 제시한 후속 방향(**아직 사건으로 승인되지 않았다 — 설계는 리뷰어가 한다**):

```
10개 conflict의 "정답"을 찾으러 가지 않는다. STITCHABLE 구간만 병합하고
conflict 구간은 CONFLICT / UNRESOLVED로 보존하는 CONSERVATIVE_EVENT_MAP_V1을 만든 뒤
SEMANTIC_CHAPTER_SHADOW_V1 → OVERVIEW_SHADOW_V1로 간다.
W00 · sampling 원인 · prompt tuning 방향으로는 돌아가지 않는다.
```

executor 경계: 이 사건은 판정 기록과 reveal로 종료다. **Conservative Event Map ·
Adjudicated Event Map · Semantic Chapter · Overview는 승인 전까지 착수 금지**이고,
판정된 22건은 사후 수정하지 않는다.

여기서 멈춘다.
