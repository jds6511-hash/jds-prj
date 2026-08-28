# AAR-v2 STEP A 사전등록 — Boundary Detectability Probe (2026-08-28)

```
질문   이미 존재하는 subtitle/caption embedding의 인접 구간 변화량이
       GT 사건 경계 위치에 대해 균등 분할보다 유용한 신호를 담고 있는가

성격   development / architecture feasibility evidence
아님   fresh confirmation · performance estimate · M8-v1 재평가
```

**결과를 보기 전에 쓴다.** primary·K·τ·matcher·GO 기준을 여기서 동결하고 실행 후
고치지 않는다.

```
새 라벨 0 · LLM 0 · generation 0 · GPU 0 · 모델 학습 0 · 새 embedding 0 · fresh data 0
M8-v1 판정 불변 · ROUND 3 없음 · M9 HOLD · official test UNOPENED · push 없음
```

이 단계에서 **AAR-v2 아키텍처는 구현하지 않는다** — event proposal · hierarchy ·
merge · LLM 사건 서술 · evidence attachment · report assembly · synthesis 전부
하지 않는다. 최종 보고서 양식(개요/주요 사건/특징/결론)도 생성·평가·튜닝하지 않는다.

---

## 1. Preflight audit 결과 (실행 전 확정)

### 1-1. GT 경계 구성 규칙

동결 GT는 `{event, start_sec, end_sec, span, seg_idx}`이고 `span`은 구간 인덱스
양 끝 포함이다. 인접 사건의 `next.start - prev.end`를 전수 조사했다.

```
delta = 1  (contiguous)   51건
delta > 1  (gap)           8건    2 · 3 · 4 · 4 · 7 · 8 · 10 · 12 · 28
delta <= 0 (overlap)       0건    관측되지 않음
```

따라서 경계 시각은 다음 규칙으로 결정한다(구간 `i`는 `[i*5, (i+1)*5)`초).

```
contiguous   boundary_sec = (prev.end + 1) * 5          — 공유 경계
gap          boundary_sec = ((prev.end + 1) * 5 + next.start * 5) / 2   — 중점
overlap      관측 0건. 발생하면 overlap 중점을 쓰되 발생 사실을 기록한다
```

영상 시작(0초)·끝(duration)은 탐지 대상에서 제외한다.
같은 영상에서 동일 시각으로 중복되는 경계는 결정적으로 dedup한다.

```
GT 사건 68건 → GT 경계 60개
m8c2_3I7oGwk6EaQ 는 GT가 1건이라 경계가 0개다
```

**적격 영상은 7편이다.** 경계가 없는 영상은 recall이 정의되지 않으므로 per-video
gate(B·C)의 모집단에서 제외한다. 임계값 자체는 원안대로 절대 개수(≥5, ≤2)로
유지한다 — 분모가 8에서 7로 줄었으므로 이 처리는 **더 엄격한 쪽**이다.

### 1-2. embedding 의미

```
emb_sub · emb_cap   8편 전부 (n_segments, 1024) · float32 · L2 norm 1.0
NaN · zero · sentinel 없음
```

빈 subtitle 구간(무발화)은 **공백 문자열을 그대로 임베딩한 값**이며 sentinel이
아니다. 공백 문자열끼리도 미세하게 다른 벡터가 나온다(공백 개수 차이). 따라서
그 구간의 subtitle 거리는 의미가 없다.

```
d_sub[t] 유효 조건   구간 t와 t+1의 subtitle이 **둘 다** 비공백
                     하나라도 공백이면 그 transition의 d_sub는 invalid
d_cap[t]             캡션은 전 구간 비공백을 m4가 강제하므로 항상 유효로 본다.
                     그럼에도 공백이면 invalid 처리하고 건수를 기록한다
```

---

## 2. 입력

```
사용    M8-v1 consumed development panel 8편
        동결 GT · 기존 5초 분할 · emb_sub · emb_cap · 구간 타임스탬프
금지    official test · M9 · P2/P3 · fresh video · fresh GT
        human-reference contrast 결과를 threshold 조정에 사용
        AAR-v2 산출물
```

실행 전에 lineage/해시를 검증하고 불일치면 진행하지 않는다(fail-closed).

---

## 3. PRIMARY change score — 하나만 동결

인접 구간 코사인 거리.

```
d_sub[t] = 1 - cos(emb_sub[t], emb_sub[t+1])
d_cap[t] = 1 - cos(emb_cap[t], emb_cap[t+1])
```

**영상 안에서 채널별로 percentile rank 정규화**한다. 스케일 차이에 둔감하고
결정적이며 하이퍼파라미터가 없다.

```
norm_x[t] = rankdata(유효한 d_x, method="average")[t] / n_valid_x      ∈ (0, 1]
```

primary score:

```
sub·cap 둘 다 유효    score = (norm_sub + norm_cap) / 2
sub만 무효            score = norm_cap
cap만 무효            score = norm_sub
둘 다 무효            경계 후보 불가 (선택 대상에서 제외)
```

**결과를 본 뒤 max·가중평균·subtitle-heavy·caption-heavy로 바꾸지 않는다.**

---

## 4. SECONDARY diagnostics — 판정에 쓰지 않는다

```
subtitle-only   norm_sub 단독
caption-only    norm_cap 단독
```

어느 채널이 신호를 주는지 이해하기 위해서만 계산한다. **secondary가 더 좋아도
STEP A 판정을 바꾸지 않는다.**

---

## 5. Boundary budget K

GT 경계 수를 보고 K를 정하지 않는다. 실제 추론에서도 쓸 수 있는 duration 규칙만
쓴다.

```
K = max(1, round(duration_sec / 60))
duration_sec = n_segments * 5
```

60초는 consumed panel의 GT 길이 중앙값 약 62초를 참고한 **outcome-informed
architecture design choice**다. 성능 근거가 아니다. 결과를 보고 바꾸지 않는다.

---

## 6. 예측 경계

primary score 상위 K개 transition을 고른다.

```
정렬        (-score, transition index)   — 동점은 인덱스 오름차순으로 결정적
NMS         쓰지 않는다. radius가 하이퍼파라미터를 하나 더 만든다
            근접 후보 억제는 STEP B의 proposal 연구로 미룬다
중복        같은 transition 인덱스는 중복 선택 불가
경계 시각    transition t의 시각 = (t + 1) * 5 초
```

---

## 7. Tolerance τ

```
PRIMARY      ±10초   (5초 분할 기준 ±2구간)
SECONDARY    ±5초 · ±15초   민감도 진단 전용
```

GO/NO-GO는 **±10초만** 쓴다. 결과를 보고 바꾸지 않는다.

---

## 8. Matching — 1:1

예측 경계 하나가 GT 경계 여러 개를 동시에 맞힌 것으로 세면 recall이 부풀려진다.
GT 최소 길이가 2구간(10초)이라 τ=±10초에서 실제로 발생할 수 있다.

```
비용        |gt_sec - pred_sec|,  τ 초과 쌍은 BIG = τ * min(n_gt, n_pred) + 1
해법        linear_sum_assignment (Hungarian)
결과        BIG 사용을 최소화 → 최대 cardinality, 그 안에서 총 거리 최소
반환        비용 <= τ 인 쌍만 hit로 인정
```

**균등 baseline도 같은 matcher를 쓴다.**

---

## 9. PRIMARY metric

```
per video   matched_GT_boundaries / total_GT_boundaries
pooled      Σ matched / Σ total            ← 판정에 쓰는 값
```

per-video는 robustness 진단이다.

---

## 10. 균등 baseline (결정적)

embedding 결과만 보고 "recall이 높다"고 해석하지 않는다.

```
같은 K개를 영상 내부에 균등 배치
times[i] = duration_sec * i / (K + 1),   i = 1..K       시작·끝 제외
구간 경계로 snap하지 않는다 — τ=10초가 5초 해상도를 흡수한다
동일한 τ · matcher · GT 경계 · metric 사용
random baseline은 primary로 쓰지 않는다
```

---

## 11. GO / NO-GO (동결)

```
A   pooled recall(primary) - pooled recall(uniform)  >=  +0.15
B   embedding recall >= uniform recall 인 영상  >= 5   (적격 7편 중)
C   embedding recall <  uniform recall 인 영상  <= 2   (적격 7편 중)
```

셋을 **전부** 만족해야 GO. 하나라도 실패하면 NO-GO.

+0.15는 통계적으로 검증된 임계가 아니라 **"향후 1.5~2주의 아키텍처 작업을
정당화하기 위한 practical design threshold"**다. p-value로 대체하지 않는다.

---

## 12. duration 진단 — 판정 아님

경계 하나는 양쪽 사건과 연결되므로 binning 규칙을 먼저 고정한다.

```
규칙   경계 양쪽 사건 중 **짧은 쪽**의 길이로 분류
bins   short <=40초 · medium 45~180초 · long >180초
```

짧은 사건에 인접한 경계에서 신호가 아예 없는지 확인하는 용도다.
**GO 판정을 바꾸지 않는다.**

---

## 13. 해석 제한

STEP A GO가 뜻하는 것.

> 기존 subtitle/caption embedding의 국소 변화 신호가 균등 시간 분할보다 GT 사건
> 경계 위치에 대해 실용적으로 더 유용한 정보를 담고 있었다.

뜻하지 않는 것.

```
AAR-v2 성공 · event proposal 성공 · hierarchy 성공 · micro/meso 정확성
보고서 품질 개선 · M8-v1 실패 해소 · fresh 일반화 · performance confirmation
```

STEP A NO-GO가 뜻하는 것.

> 현재의 embedding-local-change 정식화로는 boundary-first 아키텍처를 시작할 만한
> 신호 우위를 이 consumed panel에서 확인하지 못했다.

**NO-GO면 임계를 바꿔 재시도하지 않는다.**

---

## 14. C1 · C3

STEP A에서는 평가하지 않는다.

```
C1   아키텍처가 바뀌면 repetition_loop · early_stop 검출기 자체가 적용 불가일 수
     있다. 그 경우 "C1 PASS"가 아니라 **legacy C1 not directly applicable**이다
C3   n_sentences / n_reference_events 는 GT가 매우 적은 영상에서 극단값을 갖는다.
     새 hierarchy 아키텍처의 success gate로 그대로 쓰지 않는다.
     필요하면 diagnostic only로 별도 사전등록한다
```

---

## 15. 과대 주장 금지

```
금지   "deterministic merge면 과분할이 해결된다"
사실   ROUND1→ROUND2에서 수렴은 부분적으로 작동했으나 영상별 편차가 컸다
       (후보 311→172, 그래도 생성 134 > baseline 93, C3 max 13.00)
기대   재현성 · 예측 가능성 · fail-closed · 분산 원인 분리
       — "merge 문제 해결 보장"이 아니다

금지   "STEP 0.5에서 5개 모두 정확한 좋은 사건이었다"
사실   거부 후보 6건 중 5건이 evidence 절단 후 valid해졌고
       추가된 5건 전부가 어떤 GT 사건과 IoU > 0으로 겹쳤다
       신규 회수 unmatched GT = 4건
```

---

## 16. 산출물

```
docs/finalization/AARV2_STEP_A_PREREG_2026-08-28.md          (이 문서)
docs/finalization/AARV2_STEP_A_RESULT_2026-08-28.md
runs/aarv2_step_a/
  manifest.json · gt_boundaries.json · change_scores.json
  predicted_boundaries.json · uniform_boundaries.json
  matching_results.json · summary.json
scripts/aarv2_step_a_boundary_probe.py
```

결정적 · LLM 없음 · GPU 없음 · 생성 없음 · 동결 산출물 무변경.

---

## 17. STEP A 이후

```
NO-GO   boundary-first 경로 종료 · 임계 변경 재시도 없음
        final report · demo · presentation으로 복귀

GO      full AAR-v2를 아직 구현하지 않는다
        다음은 별도 사전등록 — STEP B: boundary → event proposal / granularity
        STEP B 통과 전에는 LLM report generation · hierarchy 전체 구현 ·
        final report synthesis를 하지 않는다
```
