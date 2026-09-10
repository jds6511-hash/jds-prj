# WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1 결과 (2026-09-10)

사전등록:
`docs/preregistration/WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md`
(commit `4108125`) · 구현 `872ef94` · **새 추론 0회 · 새 LLM 호출 0회 · GPU 미사용**

```
executor 상태   EXECUTED / REVIEW_PENDING
대상            valid-valid adjacency 22개 (O02…O23) · 각 24초 · 공유 프레임 12장
packet          blinded (Arm A/B) · 창 id·event id 미노출 · mapping 봉인
비교 단위        overlap-local event sequence (event 한 줄 매칭 아님)
판정             relation·상위 판정·최종 verdict 모두 미기록 (전부 NOT_ADJUDICATED)
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

## D. 판정 상태 (미기록)

```
overlap 22개 전부   relation NOT_ADJUDICATED · top_verdict NOT_ADJUDICATED
adjudicated         0 / 22
final_verdict       null (executor 계산 금지)
mapping reveal      거부됨 (VERDICTS_INCOMPLETE) — 22개 전부 기록 후에만 허용
```

리뷰어 어휘:

```
relation      SAME_EVENT · CONTINUATION · TRANSITION · CONFLICT · UNRESOLVED
상위 판정      STITCHABLE · MATERIAL_CONFLICT · UNRESOLVED
최종           STITCHING_SHADOW_PASS / HOLD / INCONCLUSIVE
기준           문자열 일치가 아니라 report-material contradiction
```

기록 방법:

```
python scripts/wvr_stitch_verdicts.py --runs runs/wvr_light_v1 --input <판정.json>
형식  {"verdicts": [{"overlap_id": "O02", "relation": "CONTINUATION",
                    "top_verdict": "STITCHABLE", "note": "..."}]}
확인  python scripts/wvr_stitch_verdicts.py --runs runs/wvr_light_v1
reveal python scripts/wvr_stitch_verdicts.py --runs runs/wvr_light_v1 --reveal
       (22개 전부 기록됐을 때만 성공한다)
```

## E. 의미 / 비의미

말하는 것:

```
22개 overlap의 sequence-대-sequence 비교 재료가 blinded 상태로 준비됐다
자동 지표상 완전 무관(공통 토큰 0) overlap은 0개이고, 완전일치는 1건뿐이다
executor는 어떤 판정도 채우지 않았고 mapping은 봉인돼 있다
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
validator  scripts/wvr_stitch_validate.py  PASS 27/27
           (O01·W00 제외 · pairs에 창/event id 없음 · audit blind·임계 없음 ·
            판정 미기록 · reveal 거부 · 재계산 결정성 · Event Map 재생성 차단)
clean tree · HEAD == origin/master
경계 확인   SHADOW source 46파일 무변경 · W00 산출물 무변경 · registry 무변경 ·
           SHADOW_V1 blind map 미접촉 · 현행 제출본 5732075871fd… 불변 ·
           official test 미접촉
```

## G. 상태

```
WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1   EXECUTED / REVIEW_PENDING
WVR_EVENT_MAP_COVERAGE_SHADOW_V1        CLOSED / EVENT_MAP_SHADOW_HOLD (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1          CLOSED / INCONCLUSIVE (불변)
SUBDIVISION family                      STOPPED / NOT SUFFICIENT
ZERO_DURATION_EXEMPLAR_ISOLATION_V1     NOT EXECUTED / SUPERSEDED
0.25fps sufficiency NOT ESTABLISHED · 0.5fps PROVISIONAL ONLY
production Event extraction · Adjudicated Event Map · Semantic Chapter ·
Overview · Analysis · Conclusion · HWPX · submission promotion ·
official test · M9                      HOLD
```

리뷰어 PASS 후에만 Adjudicated Event Map을 만들고 그 다음
`WVR_SEMANTIC_CHAPTER_SHADOW_V1`로 간다.

## H. 산출물

```
runs/wvr_light_v1/stitch_v1_packet.md       blinded reviewer packet (22 overlap)
runs/wvr_light_v1/stitch_v1_pairs.json      arm sequence (local_id만 · 창/event id 없음)
runs/wvr_light_v1/stitch_v1_audit.json      AUDIT_DIAGNOSTIC_ONLY 지표 (임계 없음)
runs/wvr_light_v1/stitch_v1_blind_map.json  mapping (봉인 · local_id 대응 포함)
runs/wvr_light_v1/stitch_v1_summary.json    요약·계보·상태
src/wvr_stitch_v1.py · scripts/wvr_stitch_build.py ·
scripts/wvr_stitch_verdicts.py · scripts/wvr_stitch_validate.py ·
tests/test_wvr_stitch_v1.py
```

여기서 멈춘다. 리뷰어 판정 대기.
