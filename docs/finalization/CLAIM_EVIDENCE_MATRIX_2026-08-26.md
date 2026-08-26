# Claim–Evidence Matrix (2026-08-26) — F5

최종 보고서에서 **실제로 주장할 문장**을 행 단위로 고정한다. 각 행은 근거 artifact를 하나
이상 가지며, 허용 표현과 금지 표현을 함께 적는다. **주장 강도를 근거보다 한 단계 높게
쓰지 않는 것**이 이 문서의 목적이다.

기계 판독본: `docs/finalization/final_report_facts_2026-08-26.json`
서술본: `docs/finalization/FINAL_REPORT_SOURCE_PACK_2026-08-26.md`

## 강도 등급

```
direct        시스템·코드·설정이 그렇다는 사실. 확인만 하면 끝난다
measured      사전등록된 절차로 잰 결과. CI가 붙는다
diagnostic    쟀지만 확증 자격이 없다 (cluster 3 · 재사용 표본 · 사후 기술)
illustrative  사례로 보여주는 관찰. 표본이 작고 추정치가 아니다
contextual    외부 문헌·배경. 판단 게이트가 아니다
policy        측정값이 아니라 사전에 정한 결정 규칙
```

## 요약

| id | 절 | 유형 | 강도 | 상태 |
|---|---|---|---|---|
| C01 | 5-2 · 5-3 | system_fact | direct | READY |
| C02 | 5-3 | deployment_policy | policy | READY |
| C03 | 5-4 | measured_result | measured | READY |
| C04 | 5-4 | measured_result | diagnostic | READY |
| C05 | 5-5 | diagnostic_observation | diagnostic | READY |
| C06 | 5-6 | qualitative_observation | illustrative | READY |
| C07 | 5-6 | qualitative_observation | illustrative | READY |
| C08 | 5-7 | limitation | direct | READY |
| C09 | 5-8 | future_work | policy | READY |
| C10 | 5-9 | measured_result | measured | READY |
| C11 | 5-9 | measured_result | measured | READY |
| C12 | 5-10 | system_fact | direct | READY |
| C13 | 5-10 | limitation | direct | READY |
| C14 | 5-11 | limitation | measured | READY |
| C15 | 5-13 | system_fact | direct | READY |
| C16 | 5-15 · 15 | system_fact | direct | READY |
| C17 | 5-1 · 문제정의 | measured_result | measured | READY |
| C18 | 5-12 | system_fact | direct | READY |
| C19 | 5-12 | measured_result | measured | READY |
| C20 | 5-14 | limitation | direct | READY |

---

## C01 — 현재 production 구성

```
절            5-2 시스템 아키텍처 · 5-3 배포 결정
유형/강도      system_fact / direct
```

**주장.** production path는 `영상 → 5초 분할 → Whisper large-v3 STT →
Qwen2.5-VL-3B / P0 / 4bit 시각 캡션 → KURE-v1 임베딩 → 자막·캡션 각 채널 검색 →
z-score 정규화 후 α=0.5 late fusion → 순위·근거·timestamp 재생`이다.

```
primary      config.yaml · scripts/demo.py (preflight가 이 identity를 강제한다)
secondary    docs/finalization/SYSTEM_ARCHITECTURE_2026-08-25.md
exact        seg_len 5s · embedding_dim 1024 · static_threshold 0 · α=0.5 (config에 없음, CLI 주입)
             alpha_star 0.5 · tie_set [0.2, 0.4, 0.5] · best point 0.4 (results/alpha_search_dev.json)
             preflight 확인 12항목 · 단위테스트 1,757건
allowed      "현재 deployment는 3B/P0/4bit이고 α=0.5다"
             "α는 config에 없고 CLI로 주입한다 — 확정값 근거는 dev α 탐색이다"
forbidden    4B·P2·P3·external E2E·케이스 스터디를 production flow 안에 그리는 것
limitations  abstention_tau=0.55는 내부 config 키다. 실제 동작은 저관련도 배너 경고뿐이고
             랭킹·결과를 바꾸지 않는다 — 사용자 대면 기능처럼 쓰지 않는다
```

---

## C02 — 3B를 유지하는 이유

```
절            5-3
유형/강도      deployment_policy / policy
```

**주장.** 현재 deployment는 incumbent `Qwen2.5-VL-3B`를 유지한다. 이는 3B가 4B보다
우월하다고 증명되었기 때문이 아니라, **4B로 교체할 충분한 fresh deployment-relevant
evidence를 확보하지 못했기 때문**이다.

```
primary      docs/finalization/MODEL_SELECTION_CASE_STUDY_2026-08-25.md
secondary    docs/작업현황_2026-08-25.md §2 · README.md §현재 연구 상태
exact        scientific superiority: unresolved
             4B: viable candidate · not adopted · operationally feasible
allowed      "교체할 근거가 부족해 현행을 유지한다" · "우열은 미해결이다"
forbidden    3B winner · 3B 승리 · 3B proven superior · 3B가 더 좋은 모델로 검증됐다
             4B loser · 4B failed · 4B 실패 · 4B rejected · 4B 기각
             "P3를 못 해서 3B가 이겼다"
limitations  이것은 측정 결과가 아니라 증거 상태에 따른 운영 결정이다
```

---

## C03 — AI Hub에서 4B 방향의 차이가 관찰됐다

```
절            5-4
유형/강도      measured_result / measured
```

**주장.** AI Hub 표본에서 캡션 단독(α=0.0) MRR이 4B 쪽으로 높게 관찰됐고 CI가 0을 배제했다.

```
primary      docs/재분석_2x2_2026-08-18.md §2 · §3
secondary    docs/probes/_scratch/aihub_caption_2x2_full_2026-08-17.json (동결 원자료)
exact        AI Hub reused sample · 1,086질의 / 194 video cluster / arm당 캡션 2,328 / 양 arm bf16
             caption-only Δ(4B/P0 − 3B/P0) = +0.0310
               query CI95 [+0.0080, +0.0536] · cluster CI95 [+0.0101, +0.0533]
               macro CI95 [+0.0165, +0.0626] · p=0.006 · BH q=0.05 유의
             caption-only MRR: 3B/P0 0.4773 · 4B/P0 0.5083
             fusion α=0.5 Δ = +0.0191 (cluster에서 0 배제 · query CI는 0 포함)
             subtitle-only MRR 0.4107 — 네 arm 전부 동일 (채널 격리 확인)
             prompt 효과 +0.0046 / +0.0067 · 상호작용 +0.0021 — 전부 비유의
allowed      "이 AI Hub 표본에서 4B 방향의 차이가 관찰됐다"
             "이 표본에서 효과는 주로 model effect로 귀속됐다"
forbidden    "4B가 더 좋은 모델임이 확증됐다" · 캡션 단독 Δ와 융합 Δ를 섞어 인용하는 것
limitations  재사용 표본이다 — 이미 4B/P1 vs 3B/P0 확증에 1회 썼으므로 확증이 아니라
             선택·추정이다. A/B half는 같은 194영상 코퍼스의 분할이므로 독립 확증이 아니다
```

---

## C04 — dev에서 반대 방향이 관찰됐다 (진단용)

```
절            5-4
유형/강도      measured_result / diagnostic
```

**주장.** deployment-like dev 표본에서는 캡션 단독 MRR이 현행 3B 쪽으로 높게 관찰됐다.
**방향이 AI Hub와 반대다.**

```
primary      docs/재분석_dev정밀도3arm_2026-08-18.md §2
secondary    docs/재분석_부호역전_2026-08-18.md
exact        dev diagnostic · 96질의 / 3 video cluster / 양 arm 실효 4bit
             caption-only MRR: 3B/P0 4bit 0.4644 · 4B/P0 4bit 0.3741 · 4B/P0 bf16 0.3650
             Δ_deploy = −0.0903 · CI95 [−0.2112, −0.0276] · ci_interpretation diagnostic_only
             Δ_quant  = +0.0091 · CI95 [−0.0406, +0.0656] — 양자화는 설명이 아니다
             fusion α=0.5 Δ = −0.0764 (산술 차이 · CI 미사전등록이라 CI를 붙이지 않는다)
             subtitle-only MRR 0.4144 — α=1.0에서 세 arm 전부 동일
allowed      "소규모 dev에서는 반대 방향이 관찰됐다" · "두 데이터에서 차이의 방향이 반대다"
forbidden    "dev가 3B 승리를 증명했다" · "두 데이터가 서로를 완전히 부정한다"
             "4B가 나쁘다" · dev Δ를 formal gate로 쓰는 것
limitations  cluster 3이다. paired video-cluster bootstrap에서 cluster 3은 CI를 진단용으로만
             쓸 수 있다(사전등록 보충 §1). 관측 ICC가 0이었지만 진실로 가정하지 않는다.
             dev 0.4144와 AI Hub 0.4107은 **다른 데이터셋의 값**이라 서로 비교하지 않는다
```

---

## C05 — 왜 방향이 갈리는가: 확인된 것과 가설의 분리

```
절            5-5
유형/강도      diagnostic_observation / diagnostic
```

**주장.** 두 표본은 구조가 다르고, 그 차이 일부는 실측으로 확인됐다. 다만 **어느 것도
부호 역전의 원인으로 확정되지 않았다.**

```
primary      docs/재분석_P1풀크기_2026-08-18.md · docs/재분석_부호역전_2026-08-18.md
secondary    docs/finalization/MODEL_SELECTION_CASE_STUDY_2026-08-25.md
exact        CONFIRMED/OBSERVED
               AI Hub는 짧은 clip 구조 · 영상당 후보 12구간
                 (본 배포는 영상당 약 150~400구간)
               subtitle availability 차이 · caption embedding pairwise 유사도
                 AI Hub 0.7603 vs 본 인덱스 0.5629
               dev는 영상 3편으로 cluster가 작다 · AI Hub는 재사용 표본이다
               dev 질의 유형별 caption-only Δ:
                 복합형 −0.2407 (n=34) · 자막형 −0.0412 (n=24) · 장면형 +0.0132 (n=38)
               풀 크기 조작에서 I_pool 부호는 두 데이터셋 모두 예측대로 음수
             PLAUSIBLE/UNCONFIRMED
               query composition interaction · caption style ↔ query style 적합성
               dataset domain composition · 공개 벤치마크 학습 노출 가능성
             남은 격차 약 0.067은 설명되지 않았다
allowed      "…가 부호 역전에 기여했을 가능성이 있다" · "plausible contributor까지다"
forbidden    "풀 크기가 원인이다" · I_pool을 adoption gate로 승격하는 것
             확인되지 않은 mechanism을 원인으로 확정하는 것
limitations  AI Hub에는 질의 유형 라벨이 없어 유형 구성 차이를 검정할 수 없다
```

---

## C06 — 캡션의 정보 선택이 검색 순위로 전달된다

```
절            5-6
유형/강도      qualitative_observation / illustrative
```

**주장.** 같은 프레임을 두 모델이 설명할 때 **어떤 정보를 골라 남기느냐**가 달랐고, 그
차이가 실제 검색 순위까지 전달되는 사례를 확인했다.

```
primary      docs/finalization/caption_retrieval_casestudy_results.json
secondary    docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md
             docs/tutor/캡션검색_케이스스터디_1페이지.md
exact        영상 1편(pland_costco_hosting) · 395구간 · 장면 5개(idx 0/79/158/237/316)
             동결 질의 15개 · caption-only α=0.0 · fresh 3B q4 vs fresh 4B q4
             scene02 — 같은 프레임에서 3B는 배너 문구를, 4B는 냉장 진열대를 캡션에 남겼다
               "대형 마트 안에 걸린 파란 광고 배너"      3B 1위 · 4B 15위
               "냉장 진열장과 쌓인 상자가 있는 창고형 매장 내부"  3B 18위 · 4B 1위
             scene01 — target 캡션에 팬·기름·새우·튀기다가 없어 seg188이 1위가 됐다
allowed      "case study에서 caption 정보 선택이 ranking에 전달되는 사례가 관찰됐다"
             "정답을 못 찾았을 때 원인을 캡션 수준까지 추적할 수 있었다"
forbidden    성능 추정 · 모델 우열 · 채택 근거 · 통계적 유의성
             scene02의 3B 배너 전사를 품질 우위로 읽는 것 (P0가 금지한 동작이다)
limitations  one-video qualitative case study; not a general performance estimate;
             not adoption evidence. 두 arm 모두 dirty tree에서 실행됐고 동일성은 입증되지
             않았다 — "완전히 동일한 실행 환경"이라고 쓰지 않는다
```

---

## C07 — 같은 사례에서 top-1과 순위가 다른 이야기를 한다

```
절            5-6
유형/강도      qualitative_observation / illustrative
```

**주장.** 이 사례 연구에서 top-1 적중 수는 두 모델이 같았고, 정답 구간의 순위는 4B 쪽이
더 높은 질의가 많았다. **두 지표가 다른 이야기를 한다는 관측이지 우열 결론이 아니다.**

```
primary      docs/finalization/caption_retrieval_casestudy_results.json (case_study_counts)
secondary    docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_TABLE.md
exact        one-video case study · 15 illustrative query
             top-1 적중            3B 2/15 · 4B 2/15 (동일)
             정답 순위가 더 높은 질의  3B 4/15 · 4B 11/15 · 동률 0
             정답 순위 중위수        3B 31위 · 4B 10위
             평균 캡션 길이          3B 128.5자 · 4B 76.4자
allowed      "top-1 count는 같았고 target rank 방향에는 차이가 관찰됐다 — illustrative다"
forbidden    "4B가 순위를 더 잘 매긴다" · 이 count를 성능 추정치·benchmark로 제시하는 것
             15개 중 11개를 승률처럼 일반화하는 것
limitations  분모가 15다. 한 영상의 다섯 장면에서 나온 수이고 유의성 검정을 하지 않았다.
             먼저 2/15 vs 2/15(동일)를 말한 뒤 순위 관측을 덧붙이는 순서를 유지한다
```

---

## C08 — P2는 annotation-cost-driven HOLD

```
절            5-7
유형/강도      limitation / direct
```

**주장.** fresh confirmation을 시도했으나 human GT annotation 비용에서 병목이 생겨
**결과를 열지 않은 채 HOLD**로 전환했다.

```
primary      docs/P2_활성설계_2026-08-24.json
secondary    docs/작업현황_2026-08-24.md · docs/finalization/LIMITATIONS_FUTURE_WORK_2026-08-25.md
exact        영상 35편 준비 · two-arm captions/index 준비 완료
             active plan 175행 (영상당 5질의 · 쿼터 복합형 62 / 자막형 44 / 장면형 69)
             완료 20행 · 미완 155행 · fixed_n true · 결과 기반 top-up 금지
             retrieval 미실행 · evaluation 미실행 · outcome 미열람 · 부분 20행 미분석
allowed      "annotation-cost-driven HOLD" · "결과를 열지 않았다"
forbidden    "155 total" (전체는 175다) · "P2 result" · "partial performance"
             "failed experiment" · "P2 HOLD가 3B 우세/4B 기각의 증거"
limitations  병목은 도구가 아니라 라벨 작성 자체였다 — 이 사실을 그대로 적는다
```

---

## C09 — 더 강한 확인에 필요한 설계 (P3 동결)

```
절            5-8
유형/강도      future_work / policy
```

**주장.** 교체를 판단하려면 fresh deployment-like 표본이 필요하다. 그 설계는 결과 열람
전에 동결됐고, 실행은 HOLD다.

```
primary      docs/P3_설계민감도_2026-08-24.json (frozen_decision)
secondary    docs/P3_4B_deployment_confirmation_DRAFT_2026-08-24.md
             docs/P3_반출권한감사_2026-08-24.json
exact        PRIMARY endpoint rr_fus_alpha_0_5 · key secondary rr_cap_alpha_0_0 (co-primary 아님)
             minimum deployment-relevant gain MRR +0.02 (deployment policy threshold, 측정 상수 아님)
             PRIMARY half-width 목표 0.02 · 300영상 × 5질의 = 1,500 GT 행
             수학적 최소 273 cluster · 1,365행 · projected half-width PRIMARY 0.0191 / secondary 0.0204
             labeling route: external human annotator · 결과 확인 후 top-up 금지
             반출 권한 감사 35편 전부 unclear · 파일럿 코호트 0/10
             blocking_item: annotation_logistics
allowed      "1,500은 현재 설계·가정에서 정한 표본 규모다"
             "막는 것은 통계가 아니라 annotation logistics와 반출 권한이다"
forbidden    "1,500개면 반드시 결판난다" · "1,500행이면 +0.02를 반드시 검출한다"
             현재 프로젝트에서 실행하겠다는 약속처럼 쓰는 것
limitations  historical variance + ICC=0 근사에 기반한 목표치다. 실제 P3 cluster 구조에서는
             더 넓어질 수 있고 검출 보장이 아니다. 관측 ICC 0을 진실로 가정하지 않는다
```

---

## C10 — 6GB 배포 환경에서 4B의 deployment blocker가 관측되지 않았다

```
절            5-9
유형/강도      measured_result / measured
```

**주장.** 실제 배포 노트북(RTX 3060 Laptop 6GB)에서 양 arm 실효 4bit로 재보니 **OOM·실패
0건**이었고 deployment blocker는 관측되지 않았다.

```
primary      docs/probes/_scratch/p3_opcost_full.json · p3_opcost_verdict.json (동결)
secondary    docs/finalization/OPERATIONAL_PROFILE_SUMMARY_2026-08-25.md
exact        프레임 40장 · 영상 11편 · seed 20260824로 사전 동결 · 3b→4b→3b→4b 교대 2블록
             OOM 0 · 실패 0 (양 arm) · quantization_mismatch false
allowed      "deployment blocker는 관측되지 않았다"
forbidden    "4B는 6GB에서 문제없이 돌아간다"로 일반화하는 것 (40장 descriptive다)
limitations  40장은 통계적 모집단 추정이 아니라 descriptive measurement다.
             minimum_generation_free_vram은 generation loop 구간만 샘플링했고 model load
             구간의 free VRAM 수치는 없다 — 로드 성공 사실만 관측됐다
```

---

## C11 — 4B는 wall-clock이 더 짧게, 자원 발자국은 더 크게 관측됐다

```
절            5-9
유형/강도      measured_result / measured
```

**주장.** 동일 prompt/config에서 4B가 더 짧은 출력을 생성했고 그 결과 end-to-end caption
wall-clock이 더 짧게 관측됐다. 동시에 VRAM·저장 발자국은 더 컸다.

```
primary      docs/probes/_scratch/p3_opcost_full.json (동결)
secondary    docs/finalization/OPERATIONAL_PROFILE_SUMMARY_2026-08-25.md
exact        frame당 wall-clock 중위수  3B 8.061s / 8.344s   4B 5.974s / 5.895s  (비 0.7411 / 0.7065)
             peak reserved VRAM        3B 2.637GB  4B 3.068GB  (+0.431GB)
             peak allocated VRAM       3B 2.440GB  4B 3.043GB  (+0.604GB)
             생성 중 최소 free VRAM      3B 2.338~2.420GB  4B 1.906GB
             모델 저장                  3B 7.00GB   4B 8.28GB   (+1.28GB)
             출력                      3B 133.6자·92.2토큰  4B 82.9자·59.7토큰
             wall-clock 대비 출력 토큰 rate  3B 11.05  4B 10.13 (비 0.9165)
             두 실행에서 출력 길이·토큰이 완전 동일 — timing만 3B +3.5% / 4B −1.3%
allowed      "동일 prompt/config에서 4B가 더 짧은 출력을 생성했고, 그 결과 end-to-end
              caption wall-clock이 더 짧게 관측됐다"
             "wall-clock 대비 출력 토큰 rate는 3B가 높게 관측됐다"
             "resource-footprint penalty가 관측됐다"
forbidden    4B cheaper · 4B가 운영비가 더 싸다 · 계산적으로 더 효율적 · 토큰당 처리속도
             "4B의 우위는 대부분 출력이 짧기 때문이다" · "decoder가 더 빠르다"
             "order effect 없음"
limitations  전력·금전 비용을 재지 않았고 generation kernel 속도를 분리 측정하지 않았다.
             출력 길이와 wall-clock의 인과관계를 확정하지 않는다. 블록이 2개다
```

---

## C12 — external E2E PHASE 1~4 functional PASS

```
절            5-10
유형/강도      system_fact / direct
```

**주장.** 저장소 밖 실제 영상 4편에서 **수집 → STT → 캡션 → 임베딩 → 색인 → 검색 →
timestamp 재생**까지 기능 경로가 끝까지 완주했다.

```
primary      docs/finalization/e2e_external_results.json
secondary    scripts/e2e_verify.py · planning/e2e_external_manifest.json
exact        PHASE 1 e2e_scene_fast    287.951s ·  58구간 · PASS · 파이프라인 538s
             PHASE 2 e2e_speech_medium 623.595s · 125구간 · PASS · 파이프라인 2,001s
             PHASE 3 e2e_cooking_1    1289.474s · 258구간 · PASS · 파이프라인 2,610s
             PHASE 4 e2e_interview    4115.992s · 824구간 · PASS · 파이프라인 8,468s
                                      (OPTIONAL_LONGFORM_STRESS — 필수 gate가 아니었으나 실행)
             단계: ingest · stt · caption · embedding · index · search · playback 전부 true
             재생 근거: Range 요청 206 · 잘못된 id 404 · seek == start
             provenance recorded · sha256 verified at M1
             제외: e2e_kfood (authentication required — 우회하지 않았다)
allowed      "short / speech / mixed / long-form external functional paths completed"
             "824구간 장편에서도 규모 관련 결함이 관측되지 않았다"
forbidden    external benchmark accuracy · generalization proven · model performance validation
limitations  functional validation이고 성능 평가가 아니다 (C13)
```

---

## C13 — E2E는 성능 benchmark가 아니다

```
절            5-10
유형/강도      limitation / direct
```

**주장.** external E2E는 시스템이 끝까지 동작하는지 확인한 것이고, 검색 정확도를 잰 것이
아니다. 이 스위트는 연구 지표를 생성하지 않는다.

```
primary      docs/finalization/e2e_external_results.json
               (research_metrics_generated false · test_split_used false · e2e_only true)
secondary    tests/test_e2e_external.py (플래그를 테스트로 강제)
exact        PHASE 4 level 1 anchor 2건이 REVIEW
             진단 — anchor 1465s의 실제 자막은 '뷔 만드는 과정', 1563s는 '쌀이 생긴 라면'
             분류 — external timestamp reference의 데이터 품질 문제
             조치 — anchor를 사후 수정하지 않고 REVIEW로 기록. functional FAIL이 아니다
allowed      "새 영상에서도 처리부터 검색·재생까지 끝까지 작동하는지 확인한 것이고,
              성능 점수를 잰 것이 아니다"
             "외부 전사의 timestamp가 이 영상 타임라인과 어긋난 데이터 품질 문제다"
forbidden    E2E 결과를 정확도·MRR·유의성으로 전환하는 것
             anchor 불일치를 검색 실패·검색 성공 어느 쪽 근거로도 쓰는 것
             결과에 맞춰 anchor를 사후 수정하는 것
limitations  이 영상들은 공개 데모 대상이 아니다 (eligible_for_public_demo false,
             진입점이 강제한다 — C18)
```

---

## C14 — 캡션 QC 한계: 현행 규칙이 flag하지 않는 foreign-script candidate가 있다

```
절            5-11
유형/강도      limitation / measured
```

**주장.** `common.is_corrupted_caption`은 한자·가나 **3자 이상 또는 비율 20% 초과**로
판정하는데, 실제 혼입 상당수가 **2자 삽입**이라 임계값 아래로 빠져나간다.

```
primary      docs/probes/_scratch/caption_foreign_char_scan.json (측정 전용)
secondary    docs/finalization/LIMITATIONS_FUTURE_WORK_2026-08-25.md §11
             docs/probes/caption_foreign_char_scan.py (재현)
exact        work/ 인덱스 (스캔 시점 13영상 — test 4편·E2E 2편 포함)
               캡션 2,751건 · 현행 규칙 flag 4건(0.15%)
               현행 규칙이 flag하지 않은 추가 foreign-script candidate 227건(8.25%)
               구성: CJK/가나만 201 · 키릴 17 · 라틴 8 · 키릴+가나 1 (CJK/가나만 88.5%)
             AI Hub
               캡션 2,328건 · 현행 규칙 flag 0건 · 동일 기준 179건(7.69%)
             실제 예: "카모フラ주제 의상" · "훈련기가停박되어" · "금속 구조물이满了"
             별도 관측: external E2E PHASE 1 seg51에서 캡션이 지시문을 되받아 적었다
               (현행 오염 판정에 걸리지 않는다 — 보고만 한다)
allowed      "현행 규칙이 flag하지 않은 추가 foreign-script candidate 비율"
             "현행 detector 기준 flag 0"
forbidden    "captions X% are corrupted" · "detector miss rate = X%" · "미탐률 8.25%"
             "오염 0" (→ "현행 detector 기준 flag 0")
limitations  **오염 GT로 판정한 값이 아니다.** 후보 중 일부는 간판의 외국어를 따옴표로
             정확히 옮긴 정상 캡션이다('МАГАЗИН' · 'PHỞ CÀ'). 전면 차단 규칙은 정확한
             캡션을 부정확한 것으로 재생성한다.
             조치는 **기록만**이다 — detector·재캡셔닝 규칙·확정 인덱스를 바꾸지 않는다.
             바꾸면 재캡셔닝 → text_hash 변경 → 재임베딩 → test 39를 평가했던 그 인덱스가
             아니게 되므로 별도 승인 사건이다
```

---

## C15 — AAR demo functional path를 한 dev 영상에서 완주했다

```
절            5-13
유형/강도      system_fact / direct
상태          READY (2026-08-26 서버 1회 완주 · 검증 완료)
```

**주장.** 서버에서 AAR 리포트 artifact를 1회 생성해 노트북으로 반입하고, 문장 → 인용
구간 → 시각 → 재생 위치 → 근거까지 추적되는 것을 로컬 렌더로 확인했다.

```
primary      docs/finalization/final_report_facts_2026-08-26.json (aar.demo_run)
secondary    docs/finalization/AAR_SERVER_RUNBOOK_2026-08-26.md · scripts/aar_view.py
             docs/finalization/AAR_TRACEABILITY_2026-08-25.md
exact        대상 gwaktube_soviet_apartment · dev · 149구간
             서버 RTX 4090 24GB · llm_4bit false(bf16) · peak VRAM 18.1GB · 소요 212초
             모델 Qwen/Qwen2.5-7B-Instruct · map_chunk 60/overlap 5 · max_new_tokens 16384
             입력 segments.json sha256 4c37c1cc… (실행 후 불변) — M8은 이 파일만 읽는다
             코드 로컬 HEAD 7621fe1(clean) · src+scripts manifest 4e0193e8… 서버와 동일
             config base 72475952… → server d97570fe… · 변경 키 llm_4bit·paths · 불변 14키 PASS
             산출 report.json sha256 1a9e1429… · 서버↔로컬 해시 일치
             결과 schema v2 · 문장 83 · 인용 구간 121/149(0.8121)
                  인용 없는 문장 0 · 범위 밖 인용 0 · 문장 중복 0 · 최대 인용 13
             검증 생성기 자체 assert 4개 PASS · check_precomputed ok ·
                  traceability 10/10 PASS · demo preflight "사용 가능(문장 83·인용 121)"
allowed      "A validated dev/demo AAR report artifact was generated on the server
              and rendered locally with citation-to-segment traceability."
             "AAR demo functional path completed on one dev/demo video:
              server generation → artifact verification → local render → evidence trace."
forbidden    end-to-end AAR complete · AAR 완주 완료
             AAR research accuracy validated · M8 evaluation complete
             AAR quality proven · test AAR validated
             AAR demo generation과 M8 research evaluation을 같은 이름으로 쓰는 것
limitations  **functional completion이고 research evaluation이 아니다.** 리포트 내용이
             얼마나 정확한지 재지 않았다.
             관측 — timeline 앞 5건(위치 기준) 중 sent 0의 서술이 인용 구간 seg#0의
             캡션·자막 어느 쪽과도 대응하지 않는다. 나머지 4건은 대응했다. 이것을
             비율·지표로 계량하지 않았다(M8 research evaluation 영역 · HOLD).
             index_consistency 개수 대조는 수행되지 않았다 — report에 n_segments 필드가
             없기 때문이고, 대신 입력 segments.json 해시 일치로 판정했다.
             artifact와 렌더본은 영상 파생 텍스트라 저장소에 추적하지 않는다 —
             해시·수치만 남긴다. M8 research evaluation은 여전히 HOLD다
```

---

## C16 — 연구 경계가 유지됐다

```
절            5-15 · 15 (연구 규율)
유형/강도      system_fact / direct
```

**주장.** finalization 기간에 test·P2 outcome·P3 outcome·M9·M8 research evaluation에
접근하지 않았고, 배포 구성을 바꾸지 않았다.

```
primary      docs/finalization/final_report_facts_2026-08-26.json (boundaries_preserved)
secondary    docs/작업현황_2026-08-25.md §3 · docs/DESIGN_SPEC.md §8-6 · CLAUDE.md
exact        test 접촉 — 튜닝 0회 · 확정 절차 공식 평가 7회(검색 M6 5회 + 리포트 M9 2회)
                        이번 기간 접촉 0회 · 39→72 확장 미개방
             M9 미실행 (split=="test" 하드코딩이라 실행 자체가 test 접촉)
             P2 outcome 미열람 · 부분 20행 미분석 · P3 outcome 미열람
             deployment·α·detector·확정 인덱스 변경 0 · frozen artifact 변경 0
allowed      "test는 열지 않았다" · "부분 GT는 어떤 분석에도 쓰지 않았다"
forbidden    경계 유지를 성능 성과처럼 쓰는 것 — 프로세스 품질로 표현한다
limitations  경계를 지켰다는 사실이 결과의 강도를 올려 주지는 않는다
```

---

## C17 — 문제 정의를 뒷받침하는 공식 결과

```
절            5-1 문제 정의 · 결과
유형/강도      measured_result / measured
```

**주장.** 자막만으로는 아무도 말하지 않은 장면을 찾지 못한다. 캡션 채널을 더한 융합이
공식 test에서 전체 MRR·Hit@1을 유의하게 올렸고, 장면형에서 가장 크게 올랐다.

```
primary      results/eval_test.json (frozen · 확정 배포 구성)
secondary    README.md · docs/DESIGN_SPEC.md §8-0
exact        공식 test 39질의 · 영상 4편 · α=0.5 (dev에서 확정)
             MRR    0.6489 → 0.8286   diff CI95 [+0.0583, +0.3098]
             Hit@1  0.5641 → 0.7692   diff CI95 [+0.0769, +0.3590]
             Hit@5  0.7692 → 0.8718   diff CI95 [−0.0256, +0.2564]   ← 0 포함
             Hit@10 0.7949 → 0.9231   diff CI95 [−0.0256, +0.2821]   ← 0 포함
             유형별 MRR  장면형 0.1741 → 0.7183 (n=13)
                        복합형 0.8246 → 0.8869 (n=14)
                        자막형 0.9583 → 0.8802 (n=12)  ← 유일한 하락
allowed      "전체 MRR·Hit@1이 올랐고 CI가 0을 배제한다"
             "자막형은 내려간다 — 트레이드오프다"
forbidden    Hit@5·Hit@10을 유의한 개선처럼 쓰는 것
             유형별 수치를 검정 결과처럼 쓰는 것
limitations  test는 질의 39건이지만 **영상은 4편**이다. 질의 단위 부트스트랩은 같은 영상 안
             질의들의 상관을 무시해 분산을 과소추정한다. 유형별 수치는 사후 부분집합이라
             다중비교 문제가 있고 검정하지 않았다 — 헤드라인은 전체 MRR·Hit@1이다
```

---

## C18 — fail-closed 안전장치

```
절            5-12
유형/강도      system_fact / direct
```

**주장.** 잘못된 run·config·artifact가 정상 결과처럼 쓰이는 것을 막는 장치를 코드로
넣었고, 실제로 발동한 사례가 있다.

```
primary      scripts/demo.py · src/common.py · scripts/label_guard.py · scripts/aar_view.py
             scripts/exp_launcher.py · scripts/canary_coverage.py · src/provenance.py
secondary    docs/finalization/REPRODUCIBILITY_SUMMARY_2026-08-25.md
exact        preflight 12항목 fail-closed · α≠0.5 거부 · text_hash 불일치 거부
             인덱스 embed_model 불일치 거부 · test split 영상 거부
             E2E 전용 영상 거부 (2026-08-26 F4에서 선언만 있고 강제되지 않던 결함을 수정)
             provenance 미등록이면 M1에서 정지 — external E2E PHASE 1에서 실제 발동
             RUN_COMPLETE + validator PASS + plan_hash 불일치 시 REPORT 거부
             CANARY coverage 선언 누락 시 fail-closed (plan_schema_version ≥ 2)
             AAR 인용 범위 밖·인용 없는 문장·video_id 불일치 → TraceError
             동결 artifact 바이트 고정 (.gitattributes -text)
             단위테스트 1,752건 (GPU 불필요)
allowed      "선언된 경계를 코드가 강제한다" · "진행 판정을 프로세스 유무가 아니라
              완료 마커 + validator PASS로 한다"
forbidden    "완벽히 재현 가능" · "fully reproducible"
limitations  재현에 원본 영상이 필요하다. work/*/segments.json·임베딩이 저장소에 없으므로
             clone 직후 평가가 재현되지 않는다
```

---

## C19 — 생성의 결정성은 조건부다

```
절            5-12
유형/강도      measured_result / measured
```

**주장.** 통제된 조건(같은 서버·commit·경로)에서 캡션 생성은 결정적이었다. **다만 기계를
건너면 문자열은 대부분 달라진다 — 그것을 곧 성능 저하로 읽지 않는다.**

```
primary      docs/재분석_2x2_2026-08-18.md §8 · docs/probes/_scratch/aihub_env_check.json
secondary    docs/finalization/REPRODUCIBILITY_SUMMARY_2026-08-25.md · CLAUDE.md
exact        같은 서버·commit·경로에서 AI Hub 2,328구간 재생성 → 상이 0건 · 완전일치 1.0
               MRR도 소수 4자리까지 동일
             p3_opcost 두 실행에서 출력 길이·토큰 완전 동일 (3B 133.6자·92.2 / 4B 82.9자·59.7)
             노트북↔서버 캡션 완전일치율 25.6%(dev) · 23.2%(AI Hub A-half)
             그럼에도 AI Hub 562질의 검색 성능 차이 Δ −0.0046 · CI95 [−0.0267, +0.0174]
               (MDE ±0.036) — 큰 방향성 환경 페널티는 재현되지 않았다
allowed      "통제된 조건에서 결정적이었다" · "문자열 차이를 곧 성능 저하로 해석하지 않는다"
forbidden    2026-08-07의 Δ−0.0879를 운영 규칙 근거로 쓰는 것
             "생성이 흔들려서"를 재캡셔닝 사유로 쓰는 것
limitations  2026-08-14↔08-17 dev 655구간에서 8건(1.2%)이 달라 MRR이 움직인 사례가 있다.
             그 두 실행 사이의 통제되지 않은 차이는 **여전히 미확정**이다.
             AI Hub 562질의는 1,086질의의 부분집합이므로 독립 확증으로 세지 않는다
```

---

## C20 — 한계를 축소하지 않는다

```
절            5-14
유형/강도      limitation / direct
```

**주장.** 이 프로젝트의 결론은 한계와 함께만 성립한다. 한계 15항목을 `final_report_facts`
`limitations[]`에 id로 고정한다.

```
primary      docs/finalization/final_report_facts_2026-08-26.json (limitations[])
secondary    docs/finalization/LIMITATIONS_FUTURE_WORK_2026-08-25.md
exact        L01~L15 (각 항목에 source_path)
allowed      한계를 결론과 같은 자리에 적는 것
forbidden    한계를 "향후 과제"로 이름만 바꿔 옮기는 것 — 두 절을 분리한다
             현재 HOLD를 future work 약속처럼 쓰는 것
limitations  없음 — 이 행 자체가 한계 목록의 색인이다
```

---

## 근거 경로 무결성

`final_report_facts_2026-08-26.json`의 모든 `source_path`·`sources`가 실재하는지는
`tests/test_final_report_facts.py`가 검사한다. **없는 경로를 인용하지 않는다.**

`docs/probes/_scratch/`는 `.gitignore` 대상이라 clone 직후에는 없을 수 있다 —
해당 경로는 **동결 원자료의 로컬 위치**이고, 그 수치는 상위 분석 문서에 전재돼 있다.
