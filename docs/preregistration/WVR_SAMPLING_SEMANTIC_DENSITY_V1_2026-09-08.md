# 사전등록 — WVR_SAMPLING_SEMANTIC_DENSITY_V1 (2026-09-08)

**이 문서는 결과를 보기 전에 쓴다.** 실행 후 파라미터·게이트·성공 문구를 고치지 않는다.
고치려면 새 사전등록 사건이다.

```
Stage 1  VISUAL_TEMPORAL_COVERAGE    모델 없음 · GPU 없음 · 결정적       실행 승인됨
Stage 2  PAIRED_OUTPUT_SENSITIVITY   0.5fps vs 0.25fps · GPU 6회        별도 승인 필요
HOLD     event extraction · chapter · highlight · report · submission ·
         flash-attn · 양자화 · chunk 축소 · STT diagnostic
```

이 사건은 **PASS/FAIL 사건이 아니라 characterization**이다. 여기서 나오는 어떤
결과도 "0.25fps가 충분하다"의 증거로 쓰지 않는다.

## 0. 왜 지금 이걸 하는가

```
capacity   10분이 4090에 들어가는가         → 닫혔다 (0.25fps에서 CAPACITY_PASS)
남은 질문   4초에 한 장으로 보고서에 필요한 장면을 볼 수 있는가  → 모른다
```

모르는 채로 Event → Chapter → Report로 가면, 나중에 보고서가 이상할 때
**모델 문제인지 0.25fps가 장면을 놓친 것인지 분리할 수 없다.**

## 1. 이름 규율 (중요)

```
Stage 1의 이름은 VISUAL_TEMPORAL_COVERAGE다.
SEMANTIC_SUFFICIENCY라고 부르지 않는다.
```

화면 변화가 작아도 의미상 중요할 수 있다(작은 물건을 잠깐 들어 보임 · 자막 한 줄이
잠깐 뜸 · 재료를 짧게 보여줌). 반대로 카메라를 크게 흔든 장면은 픽셀 변화가 커도
보고서에는 의미가 없을 수 있다. **픽셀 변화량은 의미가 아니다.**

```
0.5fps는 영상의 truth가 아니다.
0.5fps = 현재보다 높은 표집 밀도 reference (higher sampling-density reference)
```

2초 사이에 나타났다 사라지는 것은 0.5fps도 못 본다. Stage 2에서도
**0.5fps 출력을 ground truth로 부르지 않는다** — 둘 다 같은 Qwen3-VL 출력이다.

## 2. Stage 1 — 표집 부분집합 관계를 잠근다

기준 집합은 C01·A0가 쓴 0.5fps 300프레임이다. 새로 표집하지 않는다.

```
reference   F000 0.0초 · F001 2.0초 · F002 4.0초 · … · F299 598.0초   (300장)
KEEP        짝수 index → 0.0, 4.0, 8.0, …, 596.0                    (150장)
DROP        홀수 index → 2.0, 6.0, 10.0, …, 598.0                   (150장)
```

**KEEP은 B arm이 실제로 쓴 시각과 같아야 한다**(`capacity_sampling_B.json`의
`frame_times_first_last = [0.0, 596.0]` · 150장). 즉

```
0.25fps ⊂ 0.5fps
```

관계를 코드로 검사한다(`assert_subset`). 이걸 잠그지 않으면 표집 시각 차이가
confound가 된다.

프레임 추출은 `scripts/wvr_capacity_probe.py`의 `sample_frames`를 **그대로** 쓴다 —
capacity 사건과 같은 프레임이어야 한다(512×288 · bicubic · 각 시각 이상의 첫 디코드
프레임).

## 3. Stage 1 지표 — 임계값을 만들지 않는다

새 vision model을 쓰지 않는다. 결정적 image-change 지표만 쓴다.

```
luma_diff        평균 절대 휘도 차 (0~255)
hist_dist        64구간 휘도 히스토그램의 1 − 교집합 (0~1)
novelty          min(직전 KEEP과의 차, 직후 KEEP과의 차)
                 — 한쪽 이웃과 비슷하면 그 내용은 아직 보인다. 그래서 min이다
```

보고는 **분포만** 한다.

```
count · min · median · p75 · p90 · p95 · max · mean
novelty가 가장 큰 DROP 프레임 Top-15 (시각·이웃·값)
```

**임계값을 만들지 않고, 나중에 튜닝하지 않는다.** "변화 있음/없음"으로 이분하지
않는다.

## 4. Stage 2 창 선택 — 사람이 고르지 않는다

3분 구간을 눈으로 고르면 post-hoc selection이다. Stage 1 점수로만 결정한다.

```
창 길이     180.0초        stride 30.0초        창 수 15개 (start 0,30,…,420)
창 점수     그 창 안 DROP 프레임의 luma_novelty 합
D1          점수 최대       D2  중앙 순위        D3  점수 최소
동률        이른 창
```

각 창은 reference 90장 · KEEP 45장 · DROP 45장을 포함한다.

**이 180초 창은 chunk 길이 조정이 아니다.** 0.5fps가 600초에서 OOM이라 paired
비교가 가능한 짧은 구간을 쓰는 것이고, 생산 chunk는 600초 그대로다.

## 5. Stage 2 arm (GPU 6회 · 별도 승인)

```
S0   창 180초 · 0.5fps  · 90프레임
S1   같은 창 · 0.25fps · 45프레임 (S0의 KEEP 부분집합)
D1·D2·D3 × (S0·S1) = 6회
```

그 밖은 전부 동일하다.

```
model·snapshot  Qwen/Qwen3-VL-8B-Instruct · 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
dtype·attn      bfloat16 · sdpa            quantization none · offload 없음
allocator       default                    device cuda:0 · device_map 없음
resolution      512 × 288                  do_sample_frames False · do_resize False
video_metadata  필수                        do_sample False · num_beams 1
max_new_tokens  1024                       repetition_penalty 1.0 · retry 0
```

## 6. Stage 2 프롬프트 — 생산 계약이 아니다

보고서를 쓰지 않는다. 진단 schema만 출력시킨다.

```
SAMPLING_DIAG_PROMPT_V1
sha256  7899dc460957fff6eef49ffb50ab15fb527436ec5008ee618772a232ce4350a4
파일     src/wvr_density_prompt.py  (IS_PRODUCTION_CONTRACT = False)
출력     {"observed_events": [{"approx_time", "event",
                              "visible_entities", "activity"}]}
```

production 8종(`src/wvr_prompts.py`)과 **다른 파일**에 두고, 이 출력을 event
evidence·chapter·highlight·report에 재사용하지 않는다.

## 7. Stage 2 비교 지표

```
event 수                       S0 · S1 각각
S1에서 사라진 event 수          매칭 규칙 아래
entity·activity가 달라진 event
시간 순서가 크게 바뀐 사례
```

매칭 허용오차는 **하나로 고르지 않는다** — 사전등록된 두 값을 나란히 보고한다.

```
MATCH_TOLERANCE_SEC = (4.0, 8.0)
```

4.0초는 0.25fps 프레임 간격, 8.0초는 그 두 배다. 결과를 본 뒤 값을 고르지 않는다.
**두 arm의 출력 전문을 보존**해 독자가 직접 볼 수 있게 한다.

결과 이름은 `PAIRED_OUTPUT_SENSITIVITY`다. **`0.5fps output = ground truth`라고
쓰지 않는다.**

## 8. 해석 규칙 (결과를 보기 전에 고정)

```
Case A   DROP novelty 낮음 + 두 arm 출력 거의 동일
         → "0.25fps is promising for WVR"
         → "semantic sufficiency proven"이라고 쓰지 않는다

Case B   novelty는 큰데 event 출력이 거의 동일
         → 보고서 수준의 coarse event 이해에는 0.25fps가 견딜 가능성

Case C   0.25fps에서 주요 event가 반복적으로 사라짐
         → capacity는 PASS지만 report 입력으로는 표집 밀도가 위험
         → 그때 0.375fps · adaptive sampling · 양자화 후 0.5fps 복귀를
           **새 사건**으로 검토한다 (이번 사건에서 실행하지 않는다)
```

## 9. 금지

```
Stage 1 결과로 semantic 판정 · 0.5fps를 truth로 취급
사람이 창을 눈으로 고르기 · 결과를 본 뒤 창 재선택
임계값 신설·튜닝 · 매칭 허용오차 사후 선택
새 표집(0.25fps를 기준 집합 밖에서 다시 뽑기)
해상도·모델·dtype·attn·chunk·프롬프트 변경 (Stage 2 arm 간)
event extraction·chapter·highlight·report 착수
Stage 2 출력을 evidence로 재사용 · submission 변경
```

## 10. 테스트

```
WVR-D01 사전등록이 실행 전에 커밋돼 있다
WVR-D02 KEEP·DROP이 기준 집합의 분할이고 각각 150장이다
WVR-D03 KEEP == B arm이 쓴 시각 (0.25fps ⊂ 0.5fps)
WVR-D04 기준 집합 밖 시각은 assert_subset이 거부한다
WVR-D05 novelty는 두 이웃 차의 min이다
WVR-D06 창 15개 · 각 창 reference 90 · KEEP 45 · DROP 45
WVR-D07 D1·D2·D3 선택이 점수만으로 결정되고 동률은 이른 창
WVR-D08 분포 보고에 임계값·이분 판정이 없다
WVR-D09 Stage 1에 모델·GPU 호출이 없다
WVR-D10 Stage 2 승인 플래그가 False
WVR-D11 진단 프롬프트가 생산 계약이 아니고 hash가 이 문서와 일치
WVR-D12 매칭 허용오차가 (4.0, 8.0) 두 값이다
WVR-D13 문서에 "0.5fps는 truth가 아니다"가 남아 있다
WVR-D14 기존 artifact(C01·A0·A1·B·제출본) 무변경
WVR-D15 보고서 수치가 JSON과 일치
```

## 11. 뮤테이션 (전부 RED여야 한다)

```
P1  KEEP stride 2 → 3            P2  DROP을 기준 집합 밖에서 새로 표집
P3  novelty를 max로 바꿈          P4  창 길이 180 → 120
P5  창 stride 30 → 60            P6  D1 선택을 점수 아닌 순서로
P7  동률 처리 제거                P8  분포에 임계값 이분 판정 추가
P9  Stage 2 승인 플래그 True      P10 진단 프롬프트를 생산 계약으로 표시
P11 매칭 허용오차 1개로 축소       P12 해상도 변경
P13 assert_subset 제거            P14 percentile 계산 왜곡
```

## 12. 기존 상태 (무변경)

```
WVR C01                          CLOSED / CAPACITY_FAIL
WVR_CAPACITY_ALLOC_V1            CLOSED / CAPACITY_FAIL
WVR_CAPACITY_SAMPLING_V1         CLOSED / CAPACITY_PASS
WVR event extraction             HOLD
R1-VAD0-QUALITY                  FROZEN
PRESENTATION_SYNTHESIS_V1        HOLD
STT_RETRANSCRIBE_V1              CLOSED / INCONCLUSIVE-DEGENERATE
STT_RETRANSCRIBE_DIAGNOSTIC_V1B  HOLD (video-only 경로가 critical path다)
submission promotion             HOLD
official test                    UNOPENED        M9  HOLD
```
