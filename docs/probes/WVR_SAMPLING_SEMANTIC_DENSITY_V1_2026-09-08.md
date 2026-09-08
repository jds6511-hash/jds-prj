# WVR_SAMPLING_SEMANTIC_DENSITY_V1 — Stage 1 결과 (2026-09-08)

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md`
(commit `2ebbe59` — 실행 전 freeze)

```
Stage 1  VISUAL_TEMPORAL_COVERAGE     완료 (모델 없음 · GPU 없음 · 41.24초)
Stage 2  PAIRED_OUTPUT_SENSITIVITY    미실행 — 별도 승인 대기
판정      없음. 이 사건은 characterization이고 PASS/FAIL을 내지 않는다
```

normative source는 `runs/wvr_light_v1/density_stage1.json`이다.

## 1. 표집 부분집합 관계 (잠금 확인)

```
reference   0.5fps · 300프레임 · 0.0 … 598.0초
KEEP        150프레임 · 0.0 … 596.0초        = B arm이 실제로 쓴 시각과 동일
DROP        150프레임 · 2.0 … 598.0초
frame_size  512 × 288                        디코드 rate 30.0000041251862
frame index 0 … 17,940
```

`0.25fps ⊂ 0.5fps`가 성립한다. 프레임 추출은 capacity 사건과 같은
`probe.sample_frames`를 그대로 썼다.

## 2. DROP 프레임의 화면 변화 분포

`novelty = min(직전 KEEP과의 차, 직후 KEEP과의 차)`. 한쪽 이웃과 비슷하면 그 내용은
아직 보이므로 min을 쓴다.

```
luma_novelty (0~255)   count 150 · min 5.7761 · median 22.038 · p75 33.5605
                       p90 49.466 · p95 58.2985 · max 81.8824 · mean 26.319
luma_diff_prev         median 36.5814 · p95 75.2525 · max 112.9318
hist_novelty (0~1)     min 0.0378 · median 0.136 · p75 0.1904 · p90 0.2454
                       p95 0.3317 · max 0.6063 · mean 0.1536
```

임계값을 만들지 않는다. 사실 관계만 적는다.

```
minimum luma novelty = 5.7761      (150개 DROP 프레임 중 최솟값)
```

**"near-duplicate가 없다"고 쓰지 않는다**(2026-09-09 정정) — 사전등록된
near-duplicate 임계값이 없으므로 그 표현은 근거보다 강하다. 관측값은
최솟값 5.7761 그 자체다.

**이것을 semantic loss라고도 부르지 않는다.** 픽셀 변화량은 의미가 아니다 — 카메라
흔들림도 크게 잡히고, 작은 물건을 잠깐 보여주는 장면은 작게 잡힌다.

novelty 상위 DROP 프레임:

```
10.0초   luma 81.8824 · hist 0.2683
374.0초  luma 78.1048 · hist 0.6063
382.0초  luma 71.3267 · hist 0.4954
598.0초  luma 63.2674 · hist 0.4098   (뒤 이웃이 없어 앞쪽만으로 계산)
30.0초   luma 61.8057 · hist 0.2396
322.0초  luma 59.5797 · hist 0.1726
```

## 3. 창 점수와 결정적 선택

3분 창 15개(start 0,30,…,420 · stride 30초). 각 창은 reference 90 · KEEP 45 ·
DROP 45장을 포함한다. 창 점수는 그 창 안 DROP 프레임의 luma_novelty 합이다.

```
W01 1344.9   W02 1115.6   W03 1009.7   W04  926.0   W05  816.3
W06  859.6   W07  935.2   W08 1079.2   W09 1178.5   W10 1278.0
W11 1411.2   W12 1342.2   W13 1235.3   W14 1057.6   W15 1133.5
```

```
D1_highest_change   W11   300.0 – 480.0초   score 1411.2169
D2_median_change    W02    30.0 – 210.0초   score 1115.5522
D3_lowest_change    W05   120.0 – 300.0초   score  816.3476
```

**사람이 내용을 보고 고르지 않았다** — 점수만으로 뽑았고 동률 규칙(이른 창)도
사전등록돼 있다.

최대/최소 비는 1411.2 / 816.3 ≈ 1.73이다. **이 비율 하나로 "변화가 몰려 있지
않다"고 결론하지 않는다**(2026-09-09 정정) — 180초 창이 30초 stride로 겹치므로
점수 자체가 평활화된다. descriptive observation으로만 쓴다.

창 세 개는 독립 표본이 아니다. **D2(30–210초)와 D3(120–300초)는 90초가 겹친다.**
Stage 2 결과를 `n=3` 독립 표본처럼 해석하지 않는다.

## 4. 계측 사고 1건 — provenance

```
RUN 1   INVALID / STALE_BYTECODE_EXECUTION      산출물 폐기 (파일 삭제)
RUN 2   VALID / AUTHORITATIVE                   위 §1~§3의 수치는 전부 이것이다
```

**"없었던 실행"으로 취급하지 않는다.** 무효 실행의 관측값·순서·수정 commit을
아래에 보존한다.

첫 실행 산출물은 `frame_size`가 512×288이 아니라 384×288로 기록됐다.

```
원인   뮤테이션 스크립트가 src/wvr_contract.py의 FRAME_WIDTH를 384로 바꿔 테스트를
      돌린 뒤 원본을 복원했다. 그런데 교체 문자열의 바이트 길이가 원본과 같고
      복원이 같은 초 안에 일어나 __pycache__의 .pyc가 무효화되지 않았다
      (.pyc 헤더의 mtime·size가 복원된 원본과 일치 — 실측 확인).
      그 뒤 실행된 Stage 1이 낡은 bytecode(384)를 읽었다.
분류   "편집본 ≠ 실행본" 사고와 같은 계열이다 (2026-08-17 사고 3건과 동일한 성격).
탐지   tests/test_wvr_density.py의 frame_size 대조가 잡았다.
조치   __pycache__ 제거 · 오염 산출물 삭제 · PYTHONDONTWRITEBYTECODE=1로 재실행 ·
      뮤테이션 스크립트 4종이 복원 후 해당 .pyc를 지우고 자식 프로세스에
      bytecode를 쓰지 않게 고침.
영향   Stage 1 재실행. 서버에서 돌린 C01·A0·A1·B는 별도 사본이라 영향 없다.
```

무효 실행(RUN 1)의 관측값 — 비교 목적으로만 보존한다.

```
frame_size        384 × 288        (사전등록은 512 × 288)
luma_novelty      min 5.6796 · median 22.0148 · p95 58.2682 · max 81.7139 · mean 26.1996
hist_novelty      median 0.1359 · max 0.607
창 점수            W11 1406.45 · W02 1110.14 · W05 811.15
창 선택            D1 W11 · D2 W02 · D3 W05   (RUN 2와 동일)
wall              37.73초
```

**RUN 1의 창 선택을 최종 선택으로 쓰지 않았다.** RUN 2가 자체 점수로 다시 뽑았고,
사람이 손으로 바꾼 것은 없다. 실험 조건(fps·창 길이·stride·해상도·선택 규칙)은
결과를 보고 바꾸지 않았다 — 사전등록된 512×288로 복구해 재실행한 것뿐이다.

```
실행 순서   RUN 1 (오염) → 테스트가 frame_size 불일치로 탐지 → 원인 특정 →
           캐시 제거·산출물 삭제 → RUN 2 (512×288 · PYTORCH bytecode 미기록)
수정 commit f0fccac (사고 기록·뮤테이션 스크립트 수정 포함)
```

## 5. 주장하지 않는 것

```
0.25fps에서 의미가 보존된다 / 손실된다      — Stage 2를 하지 않았다
novelty 22가 "작다" 또는 "크다"             — 기준이 없다. 임계값을 만들지 않았다
0.5fps가 영상의 truth다                    — 2초 사이 사건은 0.5fps도 못 본다
D1이 "가장 중요한" 구간이다                 — 픽셀 변화가 가장 큰 구간일 뿐이다
```

## 6. 다음 — Stage 2 (승인 대기)

```
S0  창 180초 · 0.5fps  · 90프레임
S1  같은 창 · 0.25fps · 45프레임 (S0의 KEEP 부분집합)
창   D1 W11(300–480) · D2 W02(30–210) · D3 W05(120–300)
합계 6회 · 진단 프롬프트 SAMPLING_DIAG_PROMPT_V1 (생산 계약 아님)
비교 event 수 · 사라진 event · entity·activity 변화 · 순서 변화
     매칭 허용오차 (4.0, 8.0) 두 값을 나란히 보고
```

용량은 문제되지 않는다 — 90프레임은 B arm(150프레임)보다 적다. 필요 시간은
arm당 약 1분 규모(B arm 실측 total 63.84초)이므로 6회에 10분 안쪽으로 본다.

```
event extraction · chapter · highlight · report   HOLD
STT_RETRANSCRIBE_DIAGNOSTIC_V1B                   HOLD
submission promotion                              HOLD
official test  UNOPENED        M9  HOLD
```

## 7. 산출물

```
runs/wvr_light_v1/density_stage1.json     150 DROP 행 · 15 창 · 분포 · 선택
scripts/wvr_density_stage1.py · src/wvr_density.py · src/wvr_density_prompt.py
tests/test_wvr_density.py (26건 · 뮤테이션 19건 전부 RED)
```
