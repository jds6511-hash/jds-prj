# AAR-v2 STEP B 사전등록 — Boundary → Event Proposal Feasibility (2026-08-29)

```
질문   STEP A의 high-recall boundary signal을 deterministic하게 정제하여,
       과도한 boundary 수를 줄이면서도 실제 GT 사건 span에 더 가까운
       flat event proposal을 만들 수 있는가

성격   development / architecture feasibility evidence
아님   fresh confirmation · performance estimate · M8-v1 재평가 · AAR-v2 성공
```

**결과를 보기 전에 쓴다.** 아래의 축소 규칙 계열·grid·대조군·지표·GO 기준·선택
규칙을 여기서 동결하고 실행 후 고치지 않는다.

```
새 라벨 0 · LLM 0 · generation 0 · GPU 0 · 새 embedding 0 · 모델 학습 0 · fresh data 0
M8-v1 판정 불변 · M9 HOLD · official test UNOPENED · push 없음
full AAR-v2 미구현 — STEP B는 STEP C(사건 서술) 착수 권한을 주지 않는다
```

---

## 0. STEP A에서 무엇이 남았나

```
확인된 것   embedding 국소 변화 신호가 GT 경계 근처에 존재한다
            pooled recall 0.5500 vs uniform 0.2500 · Δ +0.3000 · 적격 7/7편

남은 문제   경계 후보를 너무 많이 낸다
            예측 158개로 GT 경계 60개 중 33개 적중 → 예측당 적중률 0.209
```

질문이 **"신호가 있나"에서 "그 신호로 실제 사건 구조를 뽑아낼 수 있나"로 옮겨간다.**

---

## 1. 계층을 만들지 않는다

동결 GT는 **flat 68건**이다. 계층 출력을 flat GT에 맞추려면 어느 층을 평가할지
골라야 하고, 그 선택은 C2(짧은 사건 매칭)와 C3(압축률)를 반대로 당긴다.

```
STEP B    flat 단일 레벨만 만든다. 평가 레벨도 flat 하나로 고정
이후      micro / meso 2층은 STEP B 통과 후의 architecture 문제로 미룬다
```

---

## 2. 바꿀 수 있는 것은 하나뿐

```
동결 (STEP A에서 그대로 가져온다)
  primary change score   mean(percentile_norm(d_sub), percentile_norm(d_cap))
  유효성 규칙             transition 양쪽 중 하나라도 공백이면 d_sub invalid
  패널                   소비된 M8-v1 8편 · 기존 emb_sub / emb_cap
  GT 경계 구성            contiguous면 공유 경계 · gap이면 중점 · 60개
  경계 매칭               τ = ±10초 · 1:1 Hungarian · 최대 cardinality 우선

STEP B가 바꾸는 것
  후보 boundary를 결정적으로 줄이는 규칙 하나
```

**새 detector를 만들지 않는다.** 새 채널·새 정규화·새 임계 지표를 만들지 않는다.

---

## 3. 축소 규칙 — 단일 계열 + 사전 정의 grid

```
규칙 R(s, q)
  ① 점수 하위 절단        primary score의 percentile < q 인 transition 제거
  ② greedy NMS           남은 후보 중 최고 점수를 채택하고
                         그로부터 ±s초 안의 후보를 억제. 반복
  ③ 예산 상한             STEP A와 같은 K = max(1, round(duration / 60))까지만
                         (상한이며, 규칙이 그보다 적게 내면 적은 대로 둔다)
동점                     점수 동점은 transition 인덱스 오름차순으로 채택
```

STEP A는 NMS를 쓰지 않았다(그때는 radius가 하이퍼파라미터를 늘리기만 했다).
**STEP B의 연구 대상이 바로 그 축소이므로 여기서 도입한다.**

### 3-1. grid (동결)

```
s ∈ {30, 45, 60, 90, 120, 180} 초        6
q ∈ {0.00, 0.60, 0.80, 0.90}             4
                                  총 24개 config
```

**24개 전부의 결과를 저장한다.** 통과한 것만 보여주는 것은 grid 은폐다.
`q = 0.00 · s = 0`에 해당하는 STEP A 원본 설정도 대조로 함께 싣는다.

---

## 4. Event proposal 구성

선택된 경계와 영상 시작·끝으로 **flat interval**을 만든다.

```
boundaries b1 < b2 < ... < bn  (초)
proposals  [0, b1] · [b1, b2] · ... · [bn, duration]
개수        n + 1
```

구간 인덱스로 변환한다(구간 i는 `[i*5, (i+1)*5)`초).

```
경계 시각 b → 구간 경계 b/5
proposal   [start_idx, end_idx]  양 끝 포함 · GT span과 같은 표현
```

**사건 서술·제목·evidence를 만들지 않는다.** span만 만든다.

---

## 5. 대조군 — equal-count uniform (핵심)

**같은 영상에서 같은 개수의 proposal을 균등 분할로 만든다.**

```
새 방식이 그 영상에서 8개를 냈으면 uniform도 정확히 8개를 낸다
구간을 개수로 균등 분할 (나머지는 앞쪽 구간에 배분 — 결정적)
```

이래야 다음 둘이 분리된다.

```
경계 위치를 잘 골라서 좋아진 것        ← 보고 싶은 것
사건을 더 많이 만들어서 GT에 걸린 것    ← 배제해야 하는 것
```

STEP A의 uniform baseline보다 한 단계 엄격한 대조다.

---

## 6. 지표

### 6-1. 경계 층

```
boundary recall      matched / 60          τ=±10초 · 1:1
boundary precision   matched / n_predicted
```

STEP A 기준값: recall 0.5500 · precision 0.209 (예측 158).

### 6-2. 사건 층

```
event_temporal_alignment    src/m8_metrics.py — 동결 구현 그대로 사용
                            Hungarian 1:1 · 미매칭 GT는 0으로 센다
패널 집계                    영상 8편의 중앙값 (C2와 같은 집계 규약)
```

**기존 C2의 `0.70 PASS`를 가져오지 않는다.** 절대 임계 대신
**equal-count uniform과의 차이**를 본다.

```
Δ_align = median align(proposal) − median align(equal-count uniform)
```

### 6-3. 과생성 통제

```
패널 proposal 총수 / GT 사건 68
```

**영상별 상한을 두지 않는다.** `m8c2_3I7oGwk6EaQ`는 GT가 1건이라 per-video 배수
상한을 두면 어떤 분할로도 만족 불가가 되고, 그것은 C3 max가 이미 겪은 함정이다
(§C3 7.00은 그 영상 하나가 결정했다). **같은 실수를 반복하지 않는다.**
per-video 비율은 diagnostic으로만 기록한다.

### 6-4. 적격 영상

```
경계 지표(6-1)   적격 7편 · GT 경계 60개
                 (m8c2_3I7oGwk6EaQ는 GT 1건이라 내부 경계가 0개)
사건 지표(6-2)   8편 전부 — 사건이 1건이어도 alignment는 정의된다
과생성(6-3)      8편 전부
```

---

## 7. GO / NO-GO (동결)

네 조건을 **전부** 만족해야 GO.

```
A  Recall retention     pooled boundary recall  >=  0.40
                        STEP A 0.5500의 약 73%. 정제로 recall을 거의 다 잃으면 안 된다

B  Precision 개선        pooled boundary precision  >=  0.35
                        STEP A 0.209의 약 1.7배

C  Event span 품질       Δ_align  >=  +0.05
                        그리고 align(proposal) >= align(uniform) 인 영상 >= 6 / 8

D  과생성 통제           패널 proposal 총수  <=  1.5 x 68  =  102
```

**0.40 · 0.35 · +0.05 · 1.5는 통계적으로 검증된 임계가 아니라, 후속 architecture
작업을 정당화하기 위한 practical design threshold다.** p-value로 대체하지 않는다.
결과를 보고 바꾸지 않는다.

### 7-1. 선택 규칙 (동결)

GO 조건을 만족한 config 중:

```
1순위   Δ_align 최대
2순위   boundary precision 최대
3순위   proposal 총수 최소
4순위   (s, q) 오름차순              완전 결정성 확보용
```

**최종 후보는 최대 1개.** 선택은 소비된 패널에서 이뤄지므로 outcome-informed이며,
선택된 config는 향후 fresh 평가 전에 동결해야 한다.

---

## 8. kbs_banff를 특별 취급하지 않는다

STEP A에서 가장 약했던 영상(recall 0.222)이고 M8-v1 미매칭 정답 8건의 최대
기여자다. **그 영상을 살리기 위한 규칙을 만들지 않는다.** 규칙을 패널 전체에
동결한 뒤 그 영상에서도 나아졌는지 diagnostic으로 본다.

전체가 좋아졌는데 `kbs_banff`가 계속 약하면 그것도 결과다.

> boundary-first가 모든 failure mode를 해결하지는 못하며,
> rejection-heavy / span-alignment dominant 유형에는 별도 문제가 남는다.

---

## 9. 라운드 상한

```
ROUND 1    본 grid 24개
ROUND 2    허용. 단 **변경 하나만** — 사유를 outcome-informed amendment로 명시
ROUND 3    없음
```

ROUND 2를 쓰고도 GO가 아니면 `STEP B ROUND LIMIT REACHED / NO-GO`로 종료한다.
결과를 보고 임계·grid·지표·대조군을 바꾸지 않는다.

---

## 10. 해석 제한

STEP B GO가 뜻하는 것.

> STEP A의 boundary signal을 결정적 축소만으로 정제해, 경계 재현율을 상당 부분
> 유지하면서 정밀도를 높이고, 같은 개수의 균등 분할보다 GT 사건 span에 더 가까운
> flat proposal을 만들 수 있었다.

뜻하지 않는 것.

```
AAR-v2 성공 · 계층 표현의 타당성 · 사건 서술 품질 · evidence attachment 품질
보고서 품질 개선 · M8-v1 실패 해소 · fresh 일반화 · performance confirmation
STEP C(사건 서술) 착수 권한
```

STEP B NO-GO가 뜻하는 것.

> boundary signal은 존재하지만, 결정적 축소만으로는 실제 사건 구조로 변환하기에
> 충분한 정밀도·정렬을 확보하지 못했다.

**NO-GO면 임계를 바꿔 재시도하지 않고 AAR-v2를 종료한다.**

---

## 11. C1 · C3는 평가하지 않는다

```
C1   사건 서술을 생성하지 않으므로 적용 대상이 없다.
     아키텍처가 바뀌면 legacy C1 detector는 not directly applicable일 수 있다
C3   문장을 만들지 않으므로 문장 수 기반 압축률을 계산하지 않는다.
     과생성은 §6-3의 proposal 수로만 본다
```

---

## 12. 산출물

```
docs/finalization/AARV2_STEP_B_PREREG_2026-08-29.md      (이 문서)
docs/finalization/AARV2_STEP_B_RESULT_2026-08-29.md
runs/aarv2_step_b/
  manifest.json · grid_results.json · selected_config.json
  proposals.json · uniform_control.json · matching_results.json · summary.json
scripts/aarv2_step_b_event_proposal.py
tests/test_aarv2_step_b.py
```

결정적 · LLM 없음 · GPU 없음 · 생성 없음 · 동결 산출물 무변경.

---

## 13. 일정

```
Day 1   사전등록 + proposal 알고리즘 + 테스트
Day 2   실행 + audit + 결과 문서
Day 3   (필요 시) 사전 허용한 ROUND 2 한 번
```

이후:

```
NO-GO   AAR-v2 종료 → 산출물·시연·발표로 복귀
GO      full architecture 구현 여부를 **다시 결정**한다.
        STEP C(LLM 사건 서술)를 자동으로 열지 않는다
```

보고서 baseline은 `ea44f2f`로 이미 제출 가능한 상태다. STEP B 결과는 그 baseline의
**addendum 또는 revision**으로 명시 추가하며, baseline을 조용히 다시 쓰지 않는다.
