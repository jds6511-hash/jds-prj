# I1 detector candidate freeze (2026-08-20)

사전등록: `I1_detector_재설계_사전등록_2026-08-18.md`(`b5f5bd8`) +
`I1_detector_보충1_development절차_2026-08-20.md`(`3dbd9ef`, 탐색 전 커밋).
코드: `docs/probes/i1_detector_dev.py`. 산출: `docs/probes/_scratch/i1_detector_dev.json`.

> **이 문서는 development set에서 선택한 candidate를 고정하는 결정 기록이다.**
> 여기 나오는 수치는 **선택 근거**일 뿐 성능 판정이 아니다. 성능 판정은 fresh
> validation set에서 현행과 동시에, 한 번만 한다.

## 0. 대조군 재현 게이트 — 통과

새 추정량이 공표된 현행 수치를 재현하는지 먼저 확인했다.

| | 공표값 | 재계산 | |
|---|---|---|---|
| `precision_sample` | 0.9861 | 0.9861 | 일치 |
| `recall_est` | 0.0815 | 0.0815 | 일치 |

출처: `docs/재분석_I1검증셋B_2026-08-18.md`. **불일치 시 중단하도록 코드에 게이트가
걸려 있다.**

### 0-1. 게이트가 잡아낸 추정량 결함 2건

초안 추정량은 게이트를 통과하지 못했다. 두 가지를 고쳤다.

**(a) 전수 셀에 모집단 스케일링을 적용했다.** C4는 모집단 78 = 표집 78인데
`pop × drift/analyzable`로 곱했다. analyzable이 68(unclear 10건)이라 **관측하지 않은
10건을 관측률로 대입**하는 결과가 됐고, 대조군 recall이 **0.0815 → 0.0919로 부풀었다.**
전수 셀은 원 개수를 쓴다.

**(b) 대조군을 CJK 규칙만으로 세웠다.** 현행 detector는 `CJK 규칙 OR 반복 규칙`이다.
CJK 부분만 대조군으로 쓰면 반복 규칙 적중(C1)이 사라져 대조군 precision이 실제보다
좋아 보인다. 대조군을 **현행 detector 전체**(`i1a_hit`)로 바꾸고, 후보도 배포 형태인
**`language_drift(CJK) OR 반복`**으로 평가해 비교 대상을 맞췄다.

## 1. 표본과 참 라벨

```
인스턴스   130 arm-instances / 116 unique frames
참 라벨    drift 91 · not_cjk_drift 25 · excluded_unclear 14
전수 셀    C1(1/1) · C4(78/78) · C5(3/3)
표집 셀    C0(8,430중 24) · C2(800중 24)
A 라벨 SHA d7117c71…  (B 시트 생성 시점에 동결된 것과 동일)
```

`foreign_script_present`(CJK ≥1) 인스턴스 105건. **진단 축이고 재캡셔닝 트리거가
아니다.** 파라미터가 없다.

## 2. 격자 결과 요약

**선언된 60개 구성을 1회 계산했다.** precision 하한 0.95를 만족한 구성은 **21/60**.

| | 구성 | `recall_est` | `precision_weighted` | `precision_sample` |
|---|---|---|---|---|
| 대조군 | 현행 `is_corrupted_caption` | 0.0815 | 0.9861 | 0.9861 |
| **primary** | `R_or_T (R=2, T=0.02)` | **0.7704** | 0.9985 | 0.9885 |
| **fallback** | `R_only (R=2)` | 0.7692 | 0.9985 | 0.9884 |

```
R_or_T   longest_cjk_run >= 2  OR  cjk_ratio > 0.02
R_only   longest_cjk_run >= 2
둘 다 배포 형태는 위 조건 OR 기존 반복 규칙 (반복 규칙은 변경하지 않았다)
```

### 2-1. 선택 규칙 적용 — 그리고 규칙 artifact 1건

보충1 §5의 규칙(`recall_est` 최대화 → `precision_weighted ≥ 0.95` 제약 → 동률 시 단순한
규칙 우선)을 그대로 적용했다.

**두 후보의 recall 차이는 0.0012이고, 그 실체는 C4의 인스턴스 1건이다** — CJK가 3~9자인데
연쇄가 모두 1자로 흩어져 있고(`longest_cjk_run < 2`) 비율이 0.02를 넘는 캡션이다.
`T=0.02`가 그 1건을 잡는다.

> **규칙이 정렬을 recall 우선으로 정해뒀기 때문에, 인스턴스 1건 차이가 단순성보다
> 앞선다.** 이것은 사전등록한 정렬 순서의 artifact다. **규칙을 결과 보고 바꾸지
> 않았다** — 대신 단순한 `R_only`를 fallback으로 함께 가져간다. validation에서 둘을
> 같이 잰다.

## 3. 셀별 — CJK 1–2자 영역을 분리해서 낸다

`est_drift` 합계는 세 구성 모두 871이다(C4 68 + C5 3 + C2 800).

| 셀 | 모집단 | 표집 | analyzable | drift | 대조군 tp | primary tp | fallback tp |
|---|---|---|---|---|---|---|---|
| C0 (CJK 0, 미적중) | 8,430 | 24 | 24 | 0 | 0 | 0 | 0 |
| C1 (CJK 0, 적중) | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| **C2 (CJK 1–2, 미적중)** | 800 | 24 | 20 | 20 | **0** | **15** | **15** |
| C4 (CJK 3–9) | 78 | 78 | 68 | 68 | 68 | 68 | 67 |
| C5 (CJK 10+) | 3 | 3 | 3 | 3 | 3 | 3 | 3 |

**C2에서 현행은 20건 중 0건에 발동했고, 두 후보는 20건 중 15건에 발동했다.**
가중 추정으로는 모집단 800 중 600이다.

### 3-1. 남는 5건 — 구조적으로 잡히지 않는다

C2 표집 24건의 `longest_cjk_run` 분포는 `run=2` 16건 · `run=1` 8건이다(`cjk_count`
분포와 동일 — 2자짜리는 모두 인접해 있다). **`R>=2`는 단일 CJK 문자를 원리상 잡을 수
없다.** C2에서 미발동한 5건은 전부 이 영역이다.

`R=1`은 격자에 없다. 보충1 §2에서 `R ∈ {2,3,4,5,6}`로 고정했고 **결과를 보고 격자를
확장하지 않는다.** 단일 문자까지 잡으려면 별도 사전등록이다.

## 4. false positive

```
scene_text                   0건  (세 구성 모두)
normal_foreign_expression    현 라벨 체계로 분리 불가 — 추정하지 않는다
선언 범주 밖                 1건  not_cjk_drift (C1)
```

**범주 밖 1건은 후보 때문이 아니다.** C1은 `cjk_count == 0`이라 어떤 CJK 후보도 발동할
수 없고, 이 적중은 **변경하지 않은 반복 규칙**에서 나온다. 대조군에도 같은 1건이 있다.

> 회계를 맞춰 적는다 — `n_fired − n_tp = FP(선언 범주) + FP(범주 밖)`.
> 범주로 걸러 버리면 이 1건이 사라진다.

**구조적 사실** — `cjk_count == 0`이면 어떤 후보도 발동할 수 없다. 따라서 CJK 축의
FP는 CJK가 있는 인스턴스에서만 나온다.

## 5. FREEZE

```
primary   language_drift = (longest_cjk_run >= 2) OR (cjk_ratio > 0.02)
fallback  language_drift = (longest_cjk_run >= 2)
진단 축   foreign_script_present = (cjk_count >= 1)          파라미터 없음
불변      기존 반복 규칙 (구 반복 · 어절 반복) — 이 사이클에서 건드리지 않았다
```

**이 시점부터 A116/B24를 detector 목적으로 다시 쓰지 않는다**(보충1 §6 종료 규칙).
격자 확장·새 특징 추가·선택 규칙 변경·미세조정 루프 전부 금지다.

## 6. 쓸 수 있는 문장 / 쓸 수 없는 문장

**쓸 수 있다**

> development set에서 `R_or_T (R=2, T=0.02)`가 선택 규칙을 만족해 primary candidate로,
> `R_only (R=2)`를 fallback으로 고정했다. C2 표본에서 현행은 0/20, 후보는 15/20에
> 발동했다.

**쓸 수 없다** — 보충1 §7

```
"recall이 개선됐다"
"현행보다 우월하다"
"precision을 유지하면서 recall을 올렸다"
"blind spot을 해결했다"
```

**이유는 순환이다.** 이 표본으로 후보를 골랐다. `0.7704`는 성능 추정이 아니라 선택
근거다.

## 7. 다음 단계

```
1  fresh validation 표집 설계 사전등록  ← 다음
2  [사용자 작업] 표집 · 라벨 (허용 도구만)
3  validation에서 현행 vs primary vs fallback 동시 평가, 한 번만
4  hard gate 승격 여부를 사용자와 판단 (확정 인덱스 영향 → 별도 승인·사전등록)
```

**hard gate 승격은 이 사이클에서 하지 않는다.** `language_drift`가 재캡셔닝을
트리거하게 만드는 것은 확정 인덱스에 영향을 주는 변경이다.

**P2 트랙과 분리 유지** — 이 결과로 P2의 estimand·CI 규칙·표집 규칙을 수정하지 않았다.
