# I1 detector 보충 1 — development 격자·선택 규칙·종료 규칙 (2026-08-20)

**이 문서는 결과를 본 뒤 고치지 않는다.** 본 사전등록
(`I1_detector_재설계_사전등록_2026-08-18.md`, `b5f5bd8`)은 **수정하지 않고**, 그
문서가 "값을 적지 않고 절차만 고정한다"고 남겨둔 부분을 여기서 채운다.

**development 탐색을 실행하기 전에 커밋한다.** 격자와 선택 규칙을 결과 이후에 정하면
그 자체가 표본에 맞춘 설계다.

## 0. 이 단계의 목표는 승리 증명이 아니다

```
목표      validation에 가져갈 candidate + parameter를 **고정**하는 것
아님      새 detector가 현행보다 낫다는 것을 보이는 것
표본      A116 프레임 · B24 라벨 — **이미 소비된 development set**
소비 없음 새 라벨 0 · GPU 0 · test 접촉 0
```

**본 사전등록 §1의 표본 경계를 그대로 유지한다** — 이 24건으로 설계하고 이 24건으로
평가하면 순환이다.

## 1. 두 축 분리 — 본 사전등록 §2 그대로

| 축 | 이름 | 성격 | 이 문서에서 |
|---|---|---|---|
| 진단 | `foreign_script_present` | 관측만. 재캡셔닝 트리거 아님 | **파라미터 없음.** CJK ≥1자 고정 |
| 실패 | `language_drift` | hard fail 후보 | §2의 격자에서 탐색 |

**반복 규칙은 이 탐색의 범위 밖이다.** 현행 `is_corrupted_caption`의 구(句) 반복·어절
반복 규칙은 **변경하지 않고 그대로 둔다**. C1(1건, CJK 0인데 적중)은 그 규칙에서
나왔고, 이 문서는 CJK 축만 다룬다.

## 2. 격자 — **지금 고정한다**

```
축 R   longest_cjk_run >= R      R ∈ {2, 3, 4, 5, 6}
축 T   cjk_ratio > T             T ∈ {0.02, 0.05, 0.10, 0.15, 0.20}
결합   R_only · T_only · R_or_T · R_and_T
합계   5 + 5 + 25 + 25 = 60개 구성
대조   현행 규칙 (cjk_count >= 3 OR cjk_ratio > 0.2) — 같은 표에 함께 낸다
```

**절대 개수(`cjk_count >= N`) 축을 넣지 않는다.** 재설계의 전제가 "절대 개수보다
연쇄 길이가 구조적으로 더 나은 신호"라는 것이고(본 사전등록 §2), 개수 축을 다시
넣으면 현행 규칙의 변형을 탐색하는 것이 된다. 대조군으로만 등장한다.

**격자를 결과 보고 확장하지 않는다.** 새 특징(어절 경계·문장 위치·언어 판별기 등)도
추가하지 않는다. 필요하다고 판단되면 **별도 사전등록**이다.

## 3. 참 라벨과 추정량

### 3-1. 참 라벨 — 기존 도출 규칙 재사용

`docs/probes/i1_stage_b_analysis.py:true_label`을 **그대로 쓴다**. 새 규칙을 만들지
않는다.

```
캡션 CJK 0                                    → not_cjk_drift  (파생)
A cjk_text_present + B matches_screen         → scene_text
A cjk_text_present + B drift_despite_text     → drift
A korean_text_only·no_text (CJK 있음)         → drift
A 또는 B unclear                              → excluded_unclear (제외, 수 보고)
```

양성 = `drift`. 음성 = `not_cjk_drift` ∪ `scene_text`. 제외 = `excluded_unclear`.

### 3-2. **추정량을 새로 세운다** — 현행 estimator를 그대로 쓸 수 없다

현행 `i1a_recall`은 **적중을 전수로 취급**한다(C1·C4·C5는 모집단 전수). 그러나
**새 규칙은 표집 셀(C0·C2)에서도 발동한다.** 그래서 TP도 가중이 필요하다.

| 셀 | 모집단 | 표집 | 성격 |
|---|---|---|---|
| C0 | 8,430 | 24 | 표집. `cjk_count == 0`이라 어떤 후보도 발동 불가 |
| C1 | 1 | 1 | 전수 |
| C2 | 800 | 24 | 표집. **누출 지대** |
| C4 | 78 | 78 | 전수 |
| C5 | 3 | 3 | 전수 |

```
est_drift(c)  = pop(c) × (analyzable 표본에서 drift 비율)
est_TP(c)     = pop(c) × (analyzable 표본에서 drift ∧ 규칙발동 비율)
recall_est    = Σ est_TP(c) / Σ est_drift(c)

precision_sample    = #(drift ∧ 발동) / #(발동 ∧ analyzable)          가중 없음
precision_weighted  = Σ pop(c)·(drift ∧ 발동 비율) / Σ pop(c)·(발동 비율)
```

**둘 다 보고한다.** 가중 없는 precision은 전수 셀(C4 78건)이 지배하고, 가중
precision은 C2(800)가 지배한다 — 어느 하나만 보면 오독한다.

**파생 셀 처리는 기존과 같다** — `cjk_count == 0`인 셀은 표집 불확실성이 없다
(`uncertainty: none_by_derivation`, CI `[0,0]`). Wilson CI를 붙이면 모집단 8,430이
곱해져 허구의 상한이 생긴다(2026-08-18에 1553.6이 실측됐다).

### 3-3. CJK 1–2자 영역 — **후보별로 반드시 따로 낸다**

현행 blind spot이 여기다(C2, 모집단 800, drift 20/20). 후보가 이 영역을 어떻게
다루는지를 **셀별 표에 분리해 낸다.** 전체 recall 하나로 뭉개지 않는다.

## 4. false positive 형태 — 범주를 미리 정한다

```
scene_text                  A cjk_text_present + B matches_screen. **유일하게 식별 가능**
normal_foreign_expression   화면에 없는 정상 외국어 표현
                            → **현 라벨 체계로 분리 불가.** A는 화면만 보고 B는 화면
                              대조만 한다. 한계로 기록하고 추정하지 않는다
구조적 사실                 cjk_count == 0이면 어떤 후보도 발동할 수 없다
                            → FP는 CJK가 있는 인스턴스에서만 나온다
```

**FP를 눈으로 보고 새 범주를 만들지 않는다.** 위 세 줄 밖의 분류가 필요하면
별도 라벨 작업이고 별도 사전등록이다.

## 5. 선택 규칙 — **결과 보기 전에 고정**

```
목적    recall_est 최대화
제약    precision_weighted >= 0.95
동률    ① 파라미터가 적은 규칙  (R_only · T_only  >  R_or_T · R_and_T)
        ② R이 작은 쪽
        ③ T가 큰 쪽
후보 수 **최대 2개** — primary 1 + fallback 1. 그 이상 validation에 가져가지 않는다
```

**제약을 만족하는 구성이 없으면** 그 사실을 적고 **candidate를 고르지 않는다.**
제약을 결과 보고 완화하지 않는다(0.95 → 0.90 같은 조정 금지).

**0.95의 근거** — 현행 development set precision이 0.9861이고, `language_drift`는
재캡셔닝을 트리거하는 hard fail 후보다. FP는 GPU와 확정 인덱스 변경 위험을 쓴다.
0.95는 현행보다 약간의 여지를 두되 크게 물러서지 않는 선이다. **이 값은 지금 고정되고
결과에 따라 움직이지 않는다.**

## 6. 종료 규칙 — 미세조정 루프를 끊는다

```
1  §2의 60개 격자 + 대조군을 **1회** 계산한다
2  §5의 선택 규칙으로 candidate를 고른다 (최대 2개)
3  candidate + parameter를 **freeze 문서로 커밋**한다
4  그 뒤 A116/B24를 detector 목적으로 다시 쓰지 않는다
```

**금지**

```
결과가 좋아 보이는 후보를 계속 미세조정하는 루프
격자 확장 · 새 특징 추가 · 선택 규칙이나 제약 변경
freeze 후 development 라벨 재사용
2회차 탐색 (필요하면 새 사전등록 + 그 사실 명시)
```

## 7. 금지 표현 — 같은 표본에서 우열을 말하지 않는다

```
금지  "recall이 개선됐다"
금지  "현행보다 우월하다"
금지  "precision을 유지하면서 recall을 올렸다"
금지  "새 detector가 blind spot을 해결했다"
```

**이유는 순환이다.** 이 표본으로 후보를 골랐으므로 이 표본의 수치는 **선택 근거**일
뿐이고 성능 주장이 아니다. 허용되는 표현은 이 형태다.

> **development set에서 구성 X가 선택 규칙을 만족했고 candidate로 고정했다. 성능
> 판정은 fresh validation set에서 한 번만 한다.**

현행과의 비교는 **같은 validation set에서 동시에 잰 뒤에만** 쓴다(본 사전등록 §3).

## 8. 절차

```
이 문서 커밋
  → 탐색 코드 · TDD 커밋 (산출물 생성 전)
  → 격자 1회 실행
  → freeze 문서 커밋 (candidate + parameter)
  → fresh validation 표집 설계 사전등록
  → [사용자 작업] 표집 · 라벨
  → validation에서 현행 vs 신규 동시 평가, 한 번만
  → hard gate 승격 여부를 사용자와 판단
```

**hard gate 승격은 이 사이클에서 하지 않는다**(본 사전등록 §4). 확정 인덱스에 영향을
주는 변경이라 사용자 승인 + 별도 사전등록이 필요하다.

## 9. P2와의 분리

**이 트랙은 P2의 과학적 질문이나 사전등록을 바꾸지 않는다.** P2 PRIMARY는 그대로
fresh `Δ_deploy`, cluster = 영상이고, **I1 결과를 본 뒤 P2의 estimand·CI 규칙·표집
규칙을 수정하지 않는다.** 두 트랙은 분리 유지한다.
