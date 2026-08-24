# P2 GT 표본 규모 amendment — **확정** (2026-08-24)

**사용자 승인으로 175를 확정했다.** 사전등록 본문(`부호역전_확증_사전등록_2026-08-18.md`)과
보충1~4는 **수정하지 않는다.** 이 문서는 이탈이 아니라 **표본 규모 하나에 대한
amendment**다.

```
확정        p2_175 — 35영상 × 5 = 175 (fixed N)
승인 시점    2026-08-24. P2 retrieval·평가 결과 미열람 상태
동결 mask    docs/P2_keepmask_175_2026-08-24.json
            sha256 f689a023215636022ab16e74a5eb55adf921962579af7293d88c4107376ff19b
기계 판독    docs/P2_활성설계_2026-08-24.json — intake·retrieval·평가의 단일 출처
```

DRAFT 원본은 이 파일로 승격됐다. §4의 진단 수치와 §5의 mask 절차는 승격 전과 같다 —
승인 근거를 사후에 고치지 않는다.

## 0. 이 문서가 다루는 것과 다루지 않는 것

```
다룬다      P2의 영상당 질의 수 m (9 → 5 → 4). 총 질의 수 315 / 175 / 140
다루지 않는다 PRIMARY estimand · alpha=0.0 · 후보 풀 정의 · cluster bootstrap ·
            exclusion 규칙 · half-width 0.04 · 판정 분기 · 35 video cluster
```

**변경 축은 cluster 수가 아니라 cluster당 질의 수다.** 영상 35편은 전부 유지한다.
영상을 빼지 않고, reserve로 교체하지 않고, 새 질의를 만들지 않는다.

## 1. 변경 이유

수작업 GT 비용이 초기 예상보다 높다. 315건은 영상당 9건이고, 각 건이
`컨택트시트 훑기 → 후보 구간 seek → 경계 확정(I/O) → 질의문 작성`이라
**사람 시간이 유일한 병목**이다. 색인·러너·평가기는 모두 준비돼 있다.

이유를 정확히 적는다.

> 라벨링이 힘들어서 통계 기준을 낮춘 것이 **아니다.** cluster 수를 유지한 채
> within-cluster 질의 수를 **P2 결과 미열람 상태에서** 비용-정밀도 trade-off로
> 재검토한 것이다.

## 2. 변경 시점 — P2-outcome-blind

```
P2 retrieval 실행         없음
P2 arm 산출물 열람         없음
P2 RR · MRR 계산          없음
p2_evaluate 실행          없음
P2 캡션 · 자막 열람        없음
```

현재 GT 상태: **첫 영상 9건 작성됨 / 315건 중 9건.** 나머지 306건 미작성.

이 amendment의 어떤 수치도 P2 산출물에서 오지 않았다. 사용한 자료는 과거 표본
(AI Hub 2×2)뿐이고, 그것은 **이미 알려진 과거 개발·재사용 표본**이지 fresh
evidence가 아니다.

## 3. 후보 설계 — Hamilton은 배정표가 선언한 기준으로 계산한다

기준 비율은 배정표의 `dev_proportions` = 복합 34 : 자막 24 : 장면 38이다.
achieved 315(111/79/125)를 기준으로 다시 계산하면 140이 49/35/56으로 갈리므로
기준을 고정한다.

| 설계 | 영상 | 영상당 | 총 | 복합 | 자막 | 장면 |
|---|---|---|---|---|---|---|
| 현행 315 | 35 | 9 | 315 | 111 | 79 | 125 |
| 후보 175 | 35 | 5 | 175 | 62 | 44 | 69 |
| 후보 140 | 35 | 4 | 140 | 50 | 35 | 55 |

세 설계 모두 **모든 영상에 복합·자막·장면 각 1건 이상**을 유지한다.
`scripts/p2_reduced_design.py`가 Hamilton과 제약을 재검산한다(테스트 48건).

## 4. 정밀도 진단 — 과거 자료, 진단 전용

`scripts/p2_sample_size_sensitivity.py` · 산출물
`docs/probes/_scratch/p2_sample_size_sensitivity.json`.

자료: AI Hub 2×2 캡션 단독 per-query RR, `qwen25_3b/P0` vs `qwen3vl_4b/P0`,
194영상 · 1,086질의.

분산 분해(불균형 일원 랜덤효과 적률):

```
σ²_within   0.1618
σ²_between  0.0        (ICC 0)
n0          5.59       영상당 질의 수 관측 min 2 · median 5 · max 14
```

k=35 투사와 경험적 재표집:

| 설계 | m | 총 질의 | 투사 half-width | m=9 대비 | 경험 median | p75 | p90 | 적격 영상 |
|---|---|---|---|---|---|---|---|---|
| p2_140 | 4 | 140 | 0.0666 | 1.500 | 0.0596 | 0.0646 | 0.0692 | 147 |
| p2_175 | 5 | 175 | 0.0596 | 1.342 | 0.0544 | 0.0584 | 0.0622 | 121 |
| p2_315 | 9 | 315 | 0.0444 | 1.000 | 추정 불가 | — | — | 21 |

`m=9` 경험 갈래는 **추정 불가**다 — 질의 9건 이상인 AI Hub 영상이 21편으로 cluster
목표 35편에 미달한다. 숫자를 만들기 위해 cluster 구조를 꾸미지 않았다.

### 4-1. ICC=0이 뜻하는 것 — cluster 유지가 정밀도를 지켜주지 않는다

이 표본에서 관측 ICC는 0이다. 그러면 half-width가 사실상 **총 질의 수**로만
결정되고(√(315/140)=1.5, √(315/175)=1.342 — 표의 상대값과 일치),
"영상 35편을 유지하니 정밀도가 비슷하다"는 주장은 **성립하지 않는다.**

단, AI Hub의 ICC=0은 그 표본의 성질일 수 있다. dev 3편의 영상별 `mean_delta`는
−0.0418 / −0.0276 / **−0.2112**로 흩어져 있어 장편에서는 between 분산이 0이 아닐
가능성이 있다. **cluster 3 · 자유도 2이므로 추정이 아니다.**
그래서 ICC를 가정값으로 훑는다.

| 가정 ICC | m=4 half-width | m=5 | m=9 | m=4/m=9 | m=5/m=9 |
|---|---|---|---|---|---|
| 0.00 | 0.0666 | 0.0596 | 0.0444 | 1.500 | 1.342 |
| 0.03 | 0.0696 | 0.0631 | 0.0495 | 1.406 | 1.275 |
| 0.10 | 0.0760 | 0.0705 | 0.0596 | 1.275 | 1.183 |
| 0.25 | 0.0882 | 0.0843 | 0.0769 | 1.146 | 1.095 |

ICC가 크면 m 축소의 손해가 작아진다. 즉 ICC=0 행은 **이 일원 랜덤효과 분산 모형
안에서 m=4·m=5의 m=9 대비 상대 손실의 상한**이다. **P2의 실제 자료생성 구조 전체에
대한 보편적 상한이 아니다** — 이 모형이 담지 못하는 구조(유형별 이질 분산, 영상×유형
상호작용, 후보 풀 크기 의존성)가 있으면 그 상한은 성립하지 않는다.
두 표본의 분산 성분을 섞어 하나의 점추정을 만들지 않았다.

### 4-2. 이 진단이 말하지 않는 것

```
P2의 실제 half-width를 예측하지 않는다
후보 풀 12구간(AI Hub) vs 약 260구간(P2) — RR 분포 스케일이 다르다
AI Hub arm은 bf16이고 P2 PRIMARY는 양 arm 4bit다
AI Hub 1,086질의는 모델 확증에 이미 쓰인 재사용 표본이다
경험 갈래는 질의 m건 이상인 영상만 쓰므로 질의 많은 영상 쪽 선택 편향이 있다
dev는 per-query 짝 RR 미저장 + cluster 3 → 이 분석에 사용 불가
dev와 AI Hub를 하나의 모집단으로 pool하지 않았다
```

### 4-3. 어느 설계도 0.04를 보장하지 않는다

투사값은 세 설계 모두 0.04를 넘는다(m=9도 0.0444). 절대값이 P2로 그대로 옮겨가지
않으므로 이것을 예측으로 읽으면 안 되지만, **`판정 불가`가 어느 설계에서도 살아있는
정상 출구**라는 점은 사전등록이 이미 규정한 바다. 315를 고른다고 판정이 보장되지
않고, 140을 고른다고 판정이 배제되지도 않는다.

## 5. 축소 시 keep-mask — 결정론적, 내용 무관

`scripts/p2_reduced_design.py` · 산출물
`docs/probes/_scratch/p2_keepmask_140.json` · `p2_keepmask_175.json`.

```
선택 입력   query_id · video_id · query_type · frozen allocation order · seed 20260820
금지 입력   text · gt_start · gt_end · note · 작성 완료 여부 · 사람이 느낀 난이도 ·
           caption · subtitle · retrieval 결과 · score · rank · index
```

절차:

```
1  영상마다 복합·자막·장면 각 1건을 필수 유지 (105건)
2  남은 extra를 **제약 흐름**으로 배정 — greedy가 아니다.
   특정 유형이 1건뿐인 영상에는 그 유형의 extra를 놓을 수 없어서
   순서대로 채우면 막판에 quota가 어긋난다. 흐름이 포화되지 않으면 fail-closed
3  (영상, 유형) 안에서는 blake2b(seed|query_id) 순으로 앞에서 필요한 만큼
4  결과는 query_id → keep/drop mask. 새 질의 생성 없음, 재번호 없음
```

검산 결과 두 설계 모두 `ok`: 영상당 행 수 정확 · global quota 정확 · 영상마다 세 유형
존재 · cluster 35 유지 · 새 query_id 없음 · keep/drop이 315를 분할.

행 순서를 뒤집어도 mask가 같고, CSV의 사람 입력 칸을 어떻게 바꿔도 mask가 같다
(그 칸을 읽는 경로가 없다).

### 5-1. 이미 작성된 첫 영상 9건 — 편의 유지하지 않았다

```
p2_140   keep 4  q02 · q03 · q06 · q07          drop 5  q01 · q04 · q05 · q08 · q09
p2_175   keep 5  q01 · q02 · q03 · q06 · q07    drop 4  q04 · q05 · q08 · q09
```

**작성됐다는 사실을 유지 근거로 쓰지 않았다.** 9건을 다 살리는 설계를 만들지 않았고,
질의 내용·난이도를 보지 않았다(이 문서에 GT 내용을 싣지 않는다).

## 6. 노동량

측정된 것은 "9건 작성됨"뿐이고 **건당 소요 시간은 실측이 없다.** 그래서 행 수로만
적는다.

| 설계 | 총 | 이미 작성분 중 유지 | 남은 작성 | 현행 대비 |
|---|---|---|---|---|
| 315 | 315 | 9 | 306 | — |
| 175 | 175 | 5 | 170 | −44.4% |
| 140 | 140 | 4 | 136 | −55.6% |

## 7. 승인 시 적용 절차 (승인 전에는 실행하지 않는다)

```
1  사용자가 140 / 175 / 315 중 하나를 고른다
2  해당 keep-mask를 동결(sha256)한다
3  retained 행의 기존 사람 입력은 그대로 옮긴다
4  dropped 행은 **삭제하지 않고** audit record로 보존한다
   — 작성됐지만 분석 대상이 아님으로 표시한다. 흔적을 없애지 않는다
5  query_id를 재번호하지 않는다
6  dropped GT를 분석에 넣지 않는다
7  축소 intake로 나머지 행을 작성한다
8  전량 작성 → build PASS → 최종 GT 동결 → arm 2회 검색 → p2_evaluate
```

## 8. no outcome-based top-up

**이 조항이 이 amendment의 핵심 방어다.**

> 승인된 질의 수가 이 P2의 **fixed sample size**다. 결과가 나온 뒤 CI가 넓다거나,
> 0을 포함한다거나, `판정 불가`가 나왔다는 이유로 남은 GT를 더 작성해 같은 P2를
> 175 / 315로 확대하지 않는다.

확대하려면 **완전히 별도의 사전등록과 별개의 분석 사건**이 필요하다.
140 → 175 → 315 순차 증량 계획을 이 amendment에 포함하지 않는다.
그런 계획 자체가 significance chasing의 통로다.

## 9. 불변 확인

```
PRIMARY estimand          Δ_deploy = MRR_cap(4b/P0) − MRR_cap(3b/P0)      불변
alpha                     0.0 캡션 단독                                   불변
후보 풀                    질의 video_id의 세그먼트 전체                    불변
CI 방법                   paired video-cluster bootstrap, cluster=영상     불변
seed · B                  20260820 · 2000                                불변
half-width 목표            0.04 초과 → 판정 불가                           불변
k < 16                    기술용                                         불변
exclusion                 사전 정의 3종 closed list                        불변
video cluster             35편                                          불변
query_type 배정            영상별 유형 최소 1건 · global Hamilton quota      규칙 유지
```

## 10. 이 문서가 하지 않는 판단

설계 선택을 하지 않는다. 스크립트도 verdict를 만들지 않는다
(`decision: 사용자_승인_사항`).

특히 **과거 표본에서 어떤 설계가 유리한 부호·유의성을 더 잘 보이는지는 선택 근거가
아니다.** 근거는 정밀도-비용 trade-off뿐이다.

## 11. 확정 사항 (2026-08-24 승인)

```
설계            p2_175 — 35 videos 전부 유지 · 정확히 5 queries/video
global quota    복합 62 / 자막 44 / 장면 69
동결 mask        docs/P2_keepmask_175_2026-08-24.json (sha256 f689a023…)
첫 영상          q01 q02 q03 q06 q07만 분석 대상
                q04 q05 q08 q09는 삭제하지 않고 audit record로 보존
query_id        재번호 없음
fixed N         175. 결과를 본 뒤 315로 늘리지 않는다 (§8)
불변            PRIMARY · alpha=0.0 · 후보 풀 · cluster bootstrap · exclusion ·
                half-width 0.04 · k<16 기술용
```

### 11-1. 적용 결과 — 원본을 덮어쓰지 않았다

`scripts/p2_apply_reduced_design.py`로 반영했다.

```
label_kit/p2/p2_label_intake_315_archive.csv   315행 · 작성완료 9   (원본 복사, 불변)
label_kit/p2/p2_label_intake.csv               175행 · 작성완료 5   (작업 파일)
label_kit/p2/p2_dropped_audit.csv              140행               (status 표시)
   status = written_not_in_analysis  4건  ← 작성됐지만 분석 대상 아님
            blank_not_in_analysis  136건
```

검산: 작업 파일의 query_id 순서가 동결 mask와 완전 일치 · 영상 35편 · 영상당 5행 ·
유형 합 62/44/69 · 유지분의 사람 입력은 그대로 복사됨.

**archive가 이미 있으면 재적용을 거부한다** — 두 번 적용해서 축소본을 원본으로
기록하는 경로를 막는다.

### 11-2. 규모의 단일 출처

`315`를 여러 모듈에 상수로 박아 두면 amendment가 한 군데만 반영되고 나머지가 조용히
거짓말을 한다. 그래서 `docs/P2_활성설계_2026-08-24.json`을 단일 출처로 두고
`p2_active_design`이 읽을 때마다 mask 해시·영상당 행 수·quota·세 유형 존재·동결
배정표 부분집합을 전부 재검산한다.

```
p2_label_intake   active_allocation() · active_total()   ← make·build가 여기서 읽는다
                  load_allocation()은 동결 315 불변성 검사로 남는다
p2_retrieve       n_queries_required()
p2_evaluate       n_queries_required()
```

`fixed_n` 또는 `no_outcome_based_top_up` 플래그가 참이 아니면 로더가 거부한다 —
결과를 본 뒤 규모를 늘리는 설계를 코드가 받지 않는다.

## 12. FINAL GT 동결 시 이어야 할 provenance chain

GT 175/175 완성 후 동결할 때 아래를 **한 산출물에 묶는다.** 지금 실행하지 않는다 —
동결 시점에 할 일의 계약이다.

```
amendment          docs/P2_GT_sample_size_amendment_2026-08-24.md
활성 설계           docs/P2_활성설계_2026-08-24.json
keep_mask_sha256   f689a023215636022ab16e74a5eb55adf921962579af7293d88c4107376ff19b
채운 작업 CSV       label_kit/p2/p2_label_intake.csv        175행 sha256
build 산출물        label_kit/p2/p2_queries_staging.jsonl   sha256
원본 archive        label_kit/p2/p2_label_intake_315_archive.csv  sha256
drop audit         label_kit/p2/p2_dropped_audit.csv       sha256
PRE-GT freeze      docs/probes/_scratch/p2_gt_freeze.json  (참조만)
규모 확인           175/175 · build PASS
실행 상태           retrieval·evaluation 미실행
```

### 12-1. **하지 말아야 하는 검사**

> PRE-GT freeze가 찍은 **빈 315행 CSV의 sha256과 현재 175행 CSV가 같은지 검사하면
> 안 된다.** 그 둘은 같을 수 없고, 같아야 한다고 검사하는 순간 동결이 실패한다.

PRE-GT freeze는 "작성 시작 전 상태가 이랬다"는 provenance이고 "계속 같아야 하는 해시"가
아니다. 315와 175 사이를 잇는 것은 **amendment + 동결 keep-mask**다.

```
빈 315 CSV  ──(PRE-GT freeze)──▶ 작성 시작 전 상태 기록
    │
    └──(amendment 2026-08-24 + keep_mask f689a023…)──▶ 175 작업 CSV ──▶ 채운 175 ──▶ staging
```

동결 산출물은 이 사슬을 그대로 적고, 각 단계의 해시를 **각자의 시점 값으로** 남긴다.

## 13. 이월 — labeler의 stale-design write 방지

2026-08-24 적용 때 라벨러가 315행을 메모리에 들고 살아 있었다. 파일만 175로 바꾸면
다음 저장에서 되덮인다. 이번에는 중지 → 적용 → 재시작으로 처리했다.

**이월 개선안**(지금 진행 중인 라벨링을 멈춰서 넣지 않는다):

```
시작 시   활성 설계 sha256 + intake sha256을 기억한다
저장 직전 현재 활성 설계 sha256을 다시 읽어 다르면 저장을 거부한다
효과     설계 전환 뒤 stale writer가 사람 개입 없이도 파일을 덮지 못한다
```

기존 인프라 통합 대기 항목(canary_coverage 게이트 → marker/status → registry SoT)과
같은 줄에 둔다.
