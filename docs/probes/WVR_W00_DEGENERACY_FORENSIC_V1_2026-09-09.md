# WVR_EVENT_EXTRACTION_W00_DEGENERACY_FORENSIC_V1 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_W00_DEGENERACY_FORENSIC_V1_2026-09-09.md`
(commit `c8458f2` — 분석 전 freeze) · 구현 `8118946` · 추론 0회 · GPU 미사용

```
분류        MODEL_OUTPUT_DEGENERACY
증거 축 A    INPUT_ANOMALY_FOUND = False   (사유 없음)
증거 축 B    OUTPUT_DEGENERACY_CONFIRMED = True
             DOMINANT_SIGNATURE_REPEAT · JSON_UNTERMINATED
진리표      ¬A ∧ B → MODEL_OUTPUT_DEGENERACY (사전등록 §5 그대로)
```

normative source는 `runs/wvr_light_v1/w00_forensic_v1.json`이다.
W00을 재실행하지 않았고 raw를 보정해 event를 복구하지 않았다.

## C1. serialized prompt 비교 (W00 vs W01 · 전 24창)

```
프롬프트 재구성       24/24 창 모두 `템플릿 % {window_start, window_end}`와 문자 단위 일치
W00 ↔ W01 diff       다른 줄 1개뿐 — 22행
                    target  start_sec=0.0 end_sec=48.0
                    control start_sec=24.0 end_sec=72.0
runtime config hash  24창 전부 동일 (distinct = 1)
input token count    W00 2,135 · W01 2,139 · … · W23 2,153
                    (Qwen3-VL의 프레임별 timestamp 텍스트 길이에 따라 단조 증가)
```

즉 **0초 창에만 붙는 지시문·placeholder·정규화는 없다.** 토큰 수 차이는 `0.0`이
`552.0`보다 짧다는 사실로 설명된다.

## C2. 입력 builder 코드 경로

```
스캔      src/wvr_shadow_v1.py · scripts/wvr_shadow_run.py ·
         scripts/wvr_capacity_probe.py · src/wvr_density_v2.py
패턴      if start == · if start_sec == · if not start · start or ·
         start_sec or · if window_id == · window_id == "W00"
결과      hits 0 — 창 전용 분기 없음
격자 확인  W00 frame_times = 일정과 일치(0.0…46.0) · index = round(time × rate) ·
         최대 drift 0 → 선형
```

## C3. W00 raw 구조 (salvage 없음)

```
raw 길이                11,533자          (대조군 672~2,180)
완성된 event object      95개              (대조군 6~16)
unique signature        2개               (대조군 2~12)
최대 signature 반복      48회              (대조군 최대 15 — W08)
zero-length interval    95/95 (전부 start == end)   (대조군 0건)
최초 반복                object index 2 · 문자 offset 254
JSON 파싱               실패 — 미완결 (대조군 파싱 실패 0건)
truncation 지점         … "liquid from a bottle into a bowl"}, {"start_sec":
```

반복은 **두 서술의 교대 루프**였다.

```
"a person" / "pouring" / "liquid from a bottle into a bowl"   48회
"a person" / "holding" / "a bottle"                           47회
```

전부 `start_sec == end_sec`이라 시간 축이 전진하지 않았다. 즉 상한 4096 도달은
**반복의 결과**이고 반복이 상한 때문에 생긴 것이 아니다.

## C4. 시각 지표 (descriptive · 분류에 사용하지 않음)

임계는 사전등록에서 동결(`black luma < 16.0` · `near-static diff < 2.0`).

```
지표                  W00        대조군(23창)
mean luma            145.98     140.5 ~ 159.9
min · max luma       112.7 · 164.0
black frame ratio    0.0        전 창 0.0
near-static ratio    0.0        전 창 0.0
mean adjacent diff   53.87      18.93 ~ 48.44
프레임 픽셀 해시        불일치 0 — 재계산·frame bank 모두 일치
```

**W00은 검은 화면·정지 화면 구간이 아니다.** 오히려 인접 프레임 변화량이 가장 큰
창이었다(53.87). 이 값은 맥락 기록이며 분류 축에 들어가지 않는다(계약·테스트로 강제).

## C5. 생성 결정성 조건

```
do_sample False · num_beams 1 · repetition_penalty 1.0 · max_new_tokens 4096
seed 지정 없음 · stopping criteria는 max_new_tokens 외 없음 · allocator native
재실행 없음 → **결정성을 실측하지 않았다**
```

2026-08-18 AI Hub 2,328구간 완전일치(greedy 결정성)는 참조일 뿐 이번 사건의 증거가
아니다.

## C6. parser 책임 분리

```
raw 자체가 미완결 JSON → attributed_to = MODEL_OUTPUT
parser가 완결 출력을 잘못 처리한 사례가 아니다
```

## 분류와 그 근거

```
A = INPUT_ANOMALY_FOUND         False
    프롬프트 템플릿 일치 · 창 전용 분기 0 · 격자·인덱스 선형 ·
    픽셀 해시 일치 · runtime config 해시 동일
B = OUTPUT_DEGENERACY_CONFIRMED True
    지배적 signature 반복(48·47회) + 미완결 JSON
→ MODEL_OUTPUT_DEGENERACY
```

## 이 결과가 말하는 것과 말하지 않는 것

말하는 것:

```
현재 artifact 범위에서 W00 실패를 입력 파이프라인 결함으로 설명할 근거는 없다
W00 출력은 두 서술이 교대하는 zero-length interval 루프였고 상한 도달은 그 결과다
같은 프롬프트·같은 설정·같은 격자에서 23창은 정상 종료했다 (raw 672~2,180자)
W00 구간은 시각적으로 검거나 정지된 구간이 아니었다
```

말하지 않는 것:

```
왜 그 창에서 루프에 들어갔는가          이 사건은 원인 메커니즘을 규명하지 않는다
재현되는가 · 결정적인가                 재실행하지 않았으므로 모른다
토큰 상한을 올리면 해결되는가            검증하지 않았고 상향은 승인되지 않았다
overlap semantic stability            NOT ADJUDICATED (봉인 유지)
frame-grounding                       NOT ADJUDICATED
```

## 검증

```
테스트     tests/test_wvr_w00_forensic.py  WVR-J01~J16  16/16 (실행 후 2건 포함)
뮤테이션    J-M1~M17 전부 RED (구멍 없음)
경계 확인   기존 산출물 쓰기 0건(결과 파일 1건만) · blind map·overlap packet 미접촉 ·
          현행 제출본 해시 5732075871fd… 불변
```

## 상태

```
W00_DEGENERACY_FORENSIC_V1     CLOSED / MODEL_OUTPUT_DEGENERACY
EVENT_EXTRACTION_SHADOW_V1     CLOSED / INCONCLUSIVE (불변)
                               overlap semantic · frame-grounding NOT ADJUDICATED
                               blinded mapping 봉인 유지 · W01~W23 raw·packet 보존
0.25fps semantic sufficiency   NOT ESTABLISHED
0.5fps                         PROVISIONAL WORKING DENSITY ONLY
production Event extraction    HOLD · Chapter·Highlight·Overview·Analysis·Conclusion HOLD
현행 제출본                      READ-ONLY        official test UNOPENED        M9 HOLD
token cap 4096 → 8192          승인되지 않았다
```

다음 사건(generation-recovery architecture 실험 여부·형태)은 **리뷰어가 이 결과를 보고
결정한다.** 이 사건은 여기서 멈춘다.
