# 최종 보고서 Source Pack (2026-08-26) — F5

최종 보고서 본문으로 **그대로 옮길 수 있는 재료**를 절 순서대로 모았다.
새 실험·새 지표·새 CI를 만들지 않았고, 모든 수치는 동결 산출물에서 읽었다.

```
기계 판독 fact index   docs/finalization/final_report_facts_2026-08-26.json
주장별 근거·표현 규칙    docs/finalization/CLAIM_EVIDENCE_MATRIX_2026-08-26.md  (C01~C20)
절별 개요 지도          docs/finalization/FINAL_REPORT_OUTLINE_2026-08-25.md
```

**문장 강도 규칙.** 근거보다 한 단계 세게 쓰지 않는다.

```
A  direct        "현재 deployment는 3B다"
B  measured      "해당 AI Hub 표본에서 4B 방향의 차이가 관찰됐다"
C  diagnostic    "소규모 dev에서는 반대 방향이 관찰됐다"
D  qualitative   "caption 정보 선택이 ranking에 전달되는 사례가 관찰됐다"
E  hypothesis    "query composition interaction이 기여했을 가능성이 있다"
```

---

## 1. 문제 정의

**한 문장.** 긴 한국어 영상에서 자연어로 원하는 순간을 찾아 **해당 timestamp부터
재생**하고, 필요하면 **근거를 추적할 수 있는 AAR**을 제공하는 시스템.

자막 검색만으로는 **아무도 말하지 않은 장면**을 찾지 못한다. 공식 test 39질의 중
장면형 13건에서 자막 단독 MRR은 **0.1741**이었다.

```
technical  Subtitle-only retrieval cannot reach visually-grounded moments that are
           never verbalized.
easy       말로 설명되지 않은 장면은 자막 검색으로 못 찾는다. 그래서 화면 설명을
           따로 만들어 두 채널로 찾는다.
근거        results/eval_test.json · README.md
```

시스템 목표는 세 가지다 — **찾기 · 근거 보이기 · 그 지점부터 재생하기.** 성능 우위를
주장하는 것이 목표가 아니다.

---

## 2. 최종 시스템 아키텍처

```
영상
 → M1  5초 분할 + 오디오 추출            src/m1_preprocess.py
 → M2  구간 대표 프레임                   src/m2_keyframe.py
 → M3  자막 Whisper large-v3 STT
       화면 캡션 Qwen2.5-VL-3B / P0 / 4bit   src/m3_generate.py
 → M4  KURE-v1 임베딩 (1024차원)          src/m4_index.py
 → M5  자막 채널 검색 + 캡션 채널 검색
       채널별 z-score 정규화 → α=0.5 가중합  src/m5_search.py
 → 순위가 매겨진 구간 + 자막·캡션 근거
 → M7  timestamp 재생 (Range 요청)        src/m7_webui.py
 → (선택) AAR 리포트                      src/m8_report.py → scripts/aar_view.py
```

| 단계 | 확정값 | 근거 |
|---|---|---|
| 분할 | `seg_len_sec 5` · `static_threshold 0`(치환 off) | `config.yaml` |
| STT | `large-v3` · 언어 ko · 크레딧 환각 자동 제거 | `config.yaml` · `common.is_subtitle_credit` |
| 캡션 | `Qwen/Qwen2.5-VL-3B-Instruct` · P0 · `vlm_4bit true`(NF4) | `config.yaml` |
| 임베딩 | `nlpai-lab/KURE-v1` · 1024차원 · 파인튜닝 없음 | `config.yaml` |
| 융합 | 채널별 z-score → α 가중합 · **α=0.5는 config에 없고 CLI 주입** | `src/m5_search.py` · `results/alpha_search_dev.json` |
| 저관련도 | 내부 키 `abstention_tau 0.55` · **동작은 배너 경고뿐, 랭킹·결과 불변** | `docs/DESIGN_SPEC.md §8-2` |
| 진입점 | `scripts/demo.py` — preflight 12항목 fail-closed | `scripts/demo.py` |

**α 확정 근거.** dev grid search · paired-diff bootstrap `B=2000 seed 42` ·
`alpha_star 0.5` · `tie_set [0.2, 0.4, 0.5]` · point best 0.4
(`results/alpha_search_dev.json`).

**production path에 없는 것** — 4B · P2 · P3 · external E2E · 캡션 케이스 스터디 ·
M8 research evaluation. 이것들을 아키텍처 그림에 넣지 않는다.

```
technical  The production path is frozen: 3B/P0/4bit captions, KURE-v1 embeddings,
           z-score late fusion at α=0.5.
easy       실제로 돌아가는 구성은 하나로 고정돼 있고, 연구용 비교 실험은 그 옆길이다.
```

---

## 3. 현재 배포 결정

> **현재 deployment는 incumbent `Qwen2.5-VL-3B`를 유지한다. 이는 3B가 4B보다 우월하다고
> 증명되었기 때문이 아니라, 4B로 교체할 충분한 fresh deployment-relevant evidence를
> 확보하지 못했기 때문이다.**

```
scientific superiority   unresolved
deployment decision      incumbent 3B retained
Qwen3-VL-4B              viable candidate · not adopted · operationally feasible
```

**금지 표현** — `3B winner` · `3B 승리` · `3B proven superior` ·
`4B failed` · `4B 실패` · `4B rejected` · `4B 기각` · `4B cheaper` ·
`계산적으로 더 효율적` · `P3를 못 해서 3B가 이겼다`.

```
technical  Scientific superiority between 3B and 4B remains unresolved.
easy       데이터를 바꾸면 결과 방향이 달라져서, 어느 모델이 항상 낫다고 결론내리지 못했다.
근거        MODEL_SELECTION_CASE_STUDY_2026-08-25.md · 매트릭스 C02
```

---

## 4. 3B vs 4B — model-selection evidence

기존 동결 결과만 정리한다. **캡션 단독(α=0.0)과 융합(α=0.5)은 다른 endpoint이고 섞어
인용하지 않는다.**

### 4-1. AI Hub (재사용 표본)

```
표본        1,086질의 / 194 video cluster / arm당 캡션 2,328 / 양 arm bf16 / 영상당 후보 12구간
caption-only Δ(4B/P0 − 3B/P0)   +0.0310
   query CI95   [+0.0080, +0.0536]
   cluster CI95 [+0.0101, +0.0533]
   macro CI95   [+0.0165, +0.0626]     p = 0.006 · BH q=0.05 유의
caption-only MRR   3B/P0 0.4773 · 4B/P0 0.5083
fusion α=0.5 Δ     +0.0191  (cluster에서 0 배제 · query CI는 0 포함)
subtitle-only MRR  0.4107 — 네 arm 전부 동일 (채널 격리의 기계적 확인)
prompt 효과        3B에서 +0.0046 · 4B에서 +0.0067 · 상호작용 +0.0021 — 전부 비유의
```

**제한.** 이 표본은 `4B/P1 vs 3B/P0` 확증에 이미 한 번 썼다. 따라서 **확증이 아니라
선택·추정**이다. A/B half는 같은 194영상 코퍼스의 분할이므로 독립 확증이 아니다.

출처: `docs/재분석_2x2_2026-08-18.md`

### 4-2. dev (배포 유사 조건)

```
표본        96질의 / 3 video cluster / 양 arm 실효 4bit
caption-only MRR   3B/P0 4bit 0.4644 · 4B/P0 4bit 0.3741 · 4B/P0 bf16 0.3650
Δ_deploy           −0.0903  CI95 [−0.2112, −0.0276]   ci_interpretation: diagnostic_only
Δ_quant            +0.0091  CI95 [−0.0406, +0.0656]   → 양자화는 설명이 아니다
fusion α=0.5 Δ     −0.0764  (산술 차이 · CI 미사전등록이라 CI를 붙이지 않는다)
subtitle-only MRR  0.4144 — α=1.0에서 세 arm 전부 동일
```

**제한.** cluster가 3이다. paired video-cluster bootstrap에서 cluster 3은 **CI를 진단용
으로만** 쓸 수 있다. 관측 ICC가 0이었지만 진실로 가정하지 않는다.

출처: `docs/재분석_dev정밀도3arm_2026-08-18.md`

### 4-3. 질의 유형별 방향 (dev · caption-only Δ)

```
복합형   −0.2407  (n=34)   ← 전체 −0.0903을 끌고 간다
자막형   −0.0412  (n=24)
장면형   +0.0132  (n=38)   ← 캡션 의존이 가장 큰 유형에서는 4B가 근소 우세
```

**AI Hub에는 유형 라벨이 없어** 유형 구성 차이를 검정할 수 없다.

### 4-4. 핵심 문장

> **두 데이터에서 차이의 방향이 반대로 나타났다.** 둘 다 CI가 0을 배제하지만 어느 쪽도
> 확증 자격이 없다 — 한쪽은 재사용 표본이고 한쪽은 cluster가 3이다.

**금지** — "두 데이터가 서로를 완전히 부정한다" · "dev가 3B 승리를 증명했다".

**두 subtitle-only 값을 헷갈리지 않는다.** `0.4107`은 AI Hub, `0.4144`는 dev다.
서로 다른 데이터셋의 값이므로 비교하지 않는다. 각 값의 의미는 같다 —
**캡션 arm만 바꿨고 자막 채널은 건드리지 않았다**는 기계적 확인이다.

---

## 5. 벤치마크 결과가 갈리는 이유 — 확인된 것과 가설

### CONFIRMED / OBSERVED

```
AI Hub는 짧은 clip 구조 · 영상당 후보 12구간          (본 배포는 영상당 약 150~400구간)
subtitle availability 차이
caption embedding pairwise 유사도   AI Hub 0.7603 vs 본 인덱스 0.5629
   → segment distinguishability가 다르다
dev는 영상 3편으로 cluster가 작다
AI Hub 1,086은 재사용 표본이다
dev 질의 유형별로 방향이 갈린다 (§4-3)
풀 크기 조작에서 I_pool 부호가 두 데이터셋 모두 예측대로 음수다
```

### PLAUSIBLE / UNCONFIRMED

```
query composition interaction          (AI Hub에 유형 라벨이 없어 검정 불가)
caption style ↔ query style 적합성
dataset domain composition 차이
공개 벤치마크 학습 노출 가능성
```

**남은 격차 약 0.067은 설명되지 않았다.** `I_pool`을 adoption gate로 승격하지 않는다 —
**plausible contributor까지이고 root-cause 증명이 아니다.**

```
technical  Candidate-pool size is a plausible contributor, not a demonstrated cause.
easy       후보 개수 차이가 영향을 줬을 가능성은 있지만, 그것이 원인이라고 증명한 것은 아니다.
근거        docs/재분석_P1풀크기_2026-08-18.md · 매트릭스 C05
```

---

## 6. 튜터 요청 케이스 스터디 — 캡션 → 검색

```
성격        qualitative / illustrative · one-video case study · outcome-blind query construction
영상        pland_costco_hosting · 395구간 (32:52)
장면        5개 (idx 0 / 79 / 158 / 237 / 316) — 시간 5등분, 프레임만 보고 선정
질의        장면당 3개(사물·행동·맥락) = 15개. 캡션·검색 결과를 보기 전에 작성·동결
검색        caption-only α=0.0 (자막 채널 끔) · 후보 395구간 전체 · alpha sweep 없음
대조        fresh 3B q4 vs fresh 4B q4 — 같은 프레임·기계·프롬프트·양자화, 모델만 다르다
동결 해시    질의 752e8fe3de1e3f06… · 장면 d41fe13c46e61efe…
```

### 6-1. scene02 — 같은 화면, 다른 선택, 1위가 뒤집힌다

| | 캡션에 담긴 것 |
|---|---|
| **3B** | 화면의 **배너 문구** 중심 — "'COSTCO'와 함께 한국어로 된 메시지", "'Join Now!'", 트럭 이미지 |
| **4B** | **냉장 진열대** 중심 — "코스트코 내부의 냉장고 진열대와 주변 상품들" |

| 같은 장면을 겨냥한 질의 | 3B | 4B |
|---|---|---|
| 대형 마트 안에 걸린 파란 광고 배너 | **1위** | 15위 |
| 냉장 진열장과 쌓인 상자가 있는 창고형 매장 내부 | 18위 | **1위** |

> 모델이 화면을 **맞게 보느냐 틀리게 보느냐**보다, 같은 화면에서 **무엇을 캡션에
> 남겼는지**가 검색 결과에 직접 영향을 줬다.

부수 관측 — 3B가 배너 글자를 그대로 옮겨 적은 것은 **P0 프롬프트가 금지한 동작**이다.
결과적으로 텍스트 질의에 유리했지만 **품질 우위로 읽지 않는다.**

> **문구 ↔ 의도 차이 (2026-08-26 기록, 미해결).** P0 프롬프트 문자열은
> *"화면에 자막이나 글자가 보이더라도 그 글자를 그대로 옮겨 적지 말고"* 로
> **화면 글자 전체**를 금지한다(`config.yaml:17`). 그러나 사용자가 의도한 기준은
> **영상 편집으로 덧씌운 자막만 제외하고, 장면 안에 실제로 존재하는 간판 · 배너 ·
> 메뉴판 · 상품 라벨은 시각 근거로 허용**하는 것이었다.
> seg79 프레임 실물 확인 결과 COSTCO 배너는 냉장창고 벽면에 부착된 **in-scene text**다.
> 즉 위 "부수 관측"은 **프롬프트 문구 기준으로는 성립하지만 의도 기준으로는 성립하지
> 않는다.** 어느 쪽을 규범으로 삼을지는 **별도 확인 대상**이다.
> **프롬프트는 수정하지 않았고 재캡셔닝 · 재색인도 하지 않았다** — 확정 인덱스의
> 캡션은 사전등록·승인된 절차 외에는 재생성하지 않는다는 규율에 따른다.
> 별도 사례: seg188(scene01)의 *"이대로 기름에 튀기듯 구워주면 끝!"* 은
> 화면 하단 고정 · 반투명 자막 박스 · 한국어+영어 번역 병기로
> **overlay subtitle임이 프레임에서 확인**됐다 — 두 사례를 같은 종류로 묶지 않는다.

### 6-2. scene01 — 정답이 아니라 다른 장면이 1위가 됐을 때

정답 장면(0:00~0:05)은 프라이팬에 기름이 차 있고 새우를 튀기는 화면이다.

```
3B가 그 장면에 쓴 캡션
  "노란색 그릇에 담긴 노란색 소스가 보입니다…"
  → 팬 · 기름 · 새우 · 튀기다 가 하나도 없다

대신 1위가 된 장면 (seg188 · 15:40)
  "두 개의 새우가 보입니다 … '이대로 기름에 튀기듯 구워주면 끝!'"
  → 질의의 "새우"·"기름에 튀기"와 직접 겹친다
```

**정답을 못 찾은 이유를 "검색 실패"로 끝내지 않고, 정답 캡션에서 무엇이 빠졌고 오답
1위 캡션에는 무엇이 있었는지까지 추적할 수 있었다.**

### 6-3. 숫자 — 보여주되 과장하지 않는다

```
Top-1 적중             3B 2/15     4B 2/15     같다
정답 순위가 더 높은 질의   3B 4/15     4B 11/15
정답 순위 중위수         3B 31위     4B 10위
평균 캡션 길이           3B 128.5자  4B 76.4자
```

> **Top-1만 보면 둘 다 2/15로 같다.** 순위를 비교하면 15개 중 11개에서 4B 쪽이 더
> 높았고 중위수도 31위 대 10위였다. **이 수치는 한 영상 15질의의 설명용 관찰일 뿐
> 일반 성능 추정치가 아니다.**

### 6-4. 필수 caveat

```
one-video qualitative case study; not a general performance estimate;
not adoption evidence.
```

한계 하나 더 — 두 arm을 오늘 같은 조건에서 새로 생성했지만, 두 실행 모두 dirty tree였고
**저장소 상태가 완전히 같았다는 것까지는 입증하지 못했다**(생성 코드·설정 경로에
차이가 없음은 확인했다).

```
technical  Caption content selection propagates to retrieval ranking; neither arm
           dominated across the fifteen frozen queries.
easy       같은 화면이라도 무엇을 적어 두느냐에 따라 검색 순위가 달라졌고, 한 모델이
           항상 유리하지는 않았다.
근거        caption_retrieval_casestudy_results.json · 매트릭스 C06 · C07
```

---

## 7. P2 — fresh confirmation 시도와 HOLD

```
준비 완료    영상 35편 · two-arm captions/index
active plan  175행 (영상당 5질의) · 쿼터 복합형 62 / 자막형 44 / 장면형 69
             fixed_n true · 결과 기반 top-up 금지
완료         20행
미완         155행
retrieval    미실행
evaluation   미실행
outcome      미열람
부분 20행     미분석
전환 사유     annotation-cost-driven HOLD — 병목은 도구가 아니라 라벨 작성 자체였다
```

**금지 표현** — `155 total`(전체는 175다) · `P2 result` · `partial performance` ·
`failed experiment` · "P2 HOLD가 3B 우세의 증거" · "P2 HOLD가 4B 기각의 증거".

```
technical  P2 was suspended on annotation cost before any outcome was accessed.
easy       새 데이터로 다시 확인하려 했지만, 정답 라벨을 사람이 만드는 비용에서 막혔고
           결과는 열지 않은 채 멈췄다.
근거        docs/P2_활성설계_2026-08-24.json · 매트릭스 C08
```

---

## 8. P3 — 더 강한 확인에 필요한 것 (설계 동결 · 실행 HOLD)

```
PRIMARY endpoint            rr_fus_alpha_0_5    (융합 α=0.5)
key secondary               rr_cap_alpha_0_0    (캡션 단독 — 반드시 보고하되 co-primary 아님)
minimum deployment gain     MRR +0.02           deployment policy threshold (측정 상수 아님)
PRIMARY half-width 목표      0.02
표본                         300영상 × 5질의 = 1,500 GT 행
수학적 최소                   273 cluster · 1,365행
projected half-width         PRIMARY 0.0191 · secondary 0.0204
라벨 경로                    external human annotator (arm identity·캡션·검색 결과 은닉)
결과 확인 후 top-up           금지
실행                         HOLD — blocking_item: annotation_logistics
반출 권한                    감사 35편 전부 unclear · 파일럿 코호트 0/10
```

> **1,500은 현재 설계와 가정(historical variance + ICC=0 근사)에서 정한 표본 규모다.**
> "1,500행이면 +0.02를 반드시 검출한다"가 아니다. 실제 P3 cluster 구조에서는 더 넓어질
> 수 있고 **검출 보장이 아니다.**

막는 것은 통계가 아니라 **annotation logistics와 영상 외부 반출 권한**이다.

```
technical  The confirmation design is frozen; execution is blocked by annotation
           logistics and export rights, not by unresolved statistics.
easy       제대로 결판내려면 새 영상 300편에 정답 1,500개가 필요한데, 라벨 작업과 영상을
           외부에 보낼 권한이 막혀서 실행을 보류했다.
근거        docs/P3_설계민감도_2026-08-24.json · 매트릭스 C09
```

---

## 9. 운영 실현 가능성

```
장치     실제 6GB 배포 노트북 — RTX 3060 Laptop · vram_total 6.0GB
정밀도   양 arm 실효 4bit (quantization_mismatch false)
표본     프레임 40장 · 영상 11편 · seed 20260824로 사전 동결 (경로 해시 정렬, 내용 신호 미사용)
배치     3b → 4b → 3b → 4b 교대 · 블록 2개
```

| 항목 | 3B (배포) | 4B (후보) | 차이 |
|---|---|---|---|
| frame당 wall-clock 중위수 (1차 / 2차) | 8.061s / 8.344s | 5.974s / 5.895s | 비 0.7411 / 0.7065 |
| peak reserved VRAM | 2.637GB | 3.068GB | **+0.431GB** |
| peak allocated VRAM | 2.440GB | 3.043GB | +0.604GB |
| 생성 중 최소 free VRAM | 2.338 / 2.420GB | 1.906GB | 약 −0.45GB |
| 모델 저장 | 7.00GB | 8.28GB | **+1.28GB** |
| OOM · 실패 | 0 · 0 | 0 · 0 | 없음 |
| 출력 길이 · 토큰 | 133.6자 · 92.2 | 82.9자 · 59.7 | 토큰 비 0.6475 |
| wall-clock 대비 출력 토큰 rate | 11.05 | 10.13 | 비 0.9165 |

> **판정 — deployment blocker는 관측되지 않았고, resource-footprint penalty는 관측됐다.**

**표현 규칙 (동결).**

```
쓴다        "동일 prompt/config에서 4B가 더 짧은 출력을 생성했고, 그 결과 end-to-end
            caption wall-clock이 더 짧게 관측됐다"
           "wall-clock 대비 출력 토큰 rate는 3B가 높게 관측됐다"
쓰지 않는다  "4B가 운영비가 더 싸다"          (전력·금전 비용 미측정)
           "계산적으로 더 효율적이다"        (출력 길이 차이가 섞여 있다)
           "토큰당 처리속도"                (분모가 전체 caption wall-clock이다)
           "4B의 우위는 출력이 짧기 때문이다"  (generation kernel 속도 미분리)
           "order effect 없음"             (블록 2개)
```

**측정하지 않은 것** — retrieval 성능 · 캡션 품질 · MRR · 전력 · 금전 비용 ·
장기 안정성 · model load 구간 free VRAM · decoder 속도 분리 측정.
**40장은 통계적 모집단 추정이 아니라 descriptive measurement다.**

배포 모델 기준 처리 시간(33분 영상 395구간): `M1 수 초 · M2 약 25분 · M3 약 75분 ·
M4 약 2분 · M6 약 2분`. 디스크는 검색만 약 12GB, 산출물은 영상 1편당 약 75MB.

```
technical  No deployment blocker was observed for the 4B candidate on the actual
           6GB laptop; a resource-footprint penalty was.
easy       4B도 노트북에서 돌아가긴 한다. 다만 메모리와 저장 공간을 더 먹는다.
근거        OPERATIONAL_PROFILE_SUMMARY_2026-08-25.md · 매트릭스 C10 · C11
```

---

## 10. External E2E functional validation

| PHASE | 영상 | 성격 | 길이 | 구간 | 판정 | 파이프라인 소요 |
|---|---|---|---|---|---|---|
| 1 | `e2e_scene_fast` | 짧은 장면 중심 | 287.951s | 58 | **PASS** | 538s |
| 2 | `e2e_speech_medium` | 발화 중심 강연 | 623.595s | 125 | **PASS** | 2,001s |
| 3 | `e2e_cooking_1` | 장면+발화 혼합 | 1289.474s | 258 | **PASS** | 2,610s |
| 4 | `e2e_interview` | **OPTIONAL_LONGFORM_STRESS** | 4115.992s | 824 | **PASS** | 8,468s |

```
확인 단계    ingest · stt · caption · embedding · index · search · playback 전부 true
재생 근거    Range 요청 206 · 잘못된 id 404 · seek == 구간 시작
provenance  recorded · sha256 verified at M1
제외        e2e_kfood — authentication required. 우회하지 않았다
```

**PHASE 4는 functional closure의 필수 gate가 아니었지만 실제로 실행해 완주했다.**
824구간에서 규모 관련 색인·검색·seek·resume 결함이 관측되지 않았다.

### 핵심 표현

> **short / speech / mixed / long-form external functional paths completed.**

**금지** — external benchmark accuracy · generalization proven · model performance
validation. 이 스위트는 `research_metrics_generated: false`로 박혀 있고 테스트가 강제한다.

### anchor 이슈 (PHASE 4)

```
증상    level 1 anchor 2건이 모두 REVIEW
진단    anchor 1465s의 실제 자막은 '뷔 만드는 과정', 1563s는 '쌀이 생긴 라면' 내용이다
        외부 공개 전사의 timestamp가 이 영상 타임라인과 정렬되지 않는다(다른 편집본 가능성)
분류    external timestamp reference의 데이터 품질 문제 — 검색 품질 판정이 아니다
조치    anchor를 사후 수정하지 않고 REVIEW로 남겼다. 결과를 보고 라벨을 바꾸지 않는다
        이 REVIEW는 functional FAIL이 아니다
쓰지 않음  검색 정확도·성능 근거로 전환하는 것
```

발견해서 고친 결함 2건 — ① M1 provenance fail-closed가 미등록 영상을 막았다(정상 동작),
② level 1 anchor 경로 첫 실행에서 `semantic_observation`에 `(start, end)` 쌍 대신
시작값만 넘기던 검증기 버그가 드러나 고치고 재실행했다.

```
technical  External E2E validated functional completion, not retrieval accuracy.
easy       새 유튜브 영상에서도 영상 처리부터 검색·재생까지 시스템이 끝까지 작동하는지
           확인한 것이고, 성능 점수를 잰 것은 아니다.
근거        docs/finalization/e2e_external_results.json · 매트릭스 C12 · C13
```

---

## 11. 캡션 QC 한계

현행 `common.is_corrupted_caption`은 한자·가나 **절대 3자 이상 또는 비율 20% 초과**로
판정한다. 그런데 실제 혼입 상당수가 **2자 삽입**이라 임계값 아래로 빠져나간다.

```
work/ 인덱스 (스캔 시점 13영상 — test 4편·E2E 2편 포함)
   캡션 2,751건 · 현행 규칙 flag 4건(0.15%)
   현행 규칙이 flag하지 않은 추가 foreign-script candidate 227건(8.25%)
   구성: CJK/가나만 201 · 키릴 17 · 라틴 8 · 키릴+가나 1   (CJK/가나만 88.5%)

AI Hub
   캡션 2,328건 · 현행 규칙 flag 0건 · 동일 기준 179건(7.69%)

실제 예   "카모フラ주제 의상" · "훈련기가停박되어" · "금속 구조물이满了" · "잎っぱ라진"
```

> **이 8.25%는 오염 GT로 판정한 값이 아니다.** "한글·ASCII 외 글자를 포함한다"는 기계적
> 기준의 후보 비율이고, 그 안에 **정상 인용**이 섞여 있다 —
> `'МАГАЗИН'이라는 글자가 부착되어 있습니다` · 베트남 식당 간판 `'PHỞ CÀ'`.
> 전면 차단 규칙은 정확한 캡션을 부정확한 것으로 재생성한다.

**허용 표현** — "현행 규칙이 flag하지 않은 추가 foreign-script candidate 비율" ·
"현행 detector 기준 flag 0".
**금지 표현** — `captions X% are corrupted` · `detector miss rate = X%` ·
`미탐률 8.25%` · `오염 0`.

**관측된 다른 한계 하나** — external E2E PHASE 1 `segment 51`에서 캡션이 **지시문을
되받아 적었다**("네, 알겠습니다. 주문하신 내용을…"). 현행 오염 판정에 걸리지 않는다.
**보고만 한다.**

**조치는 기록만이다(2026-08-25 결정 A).** detector·재캡셔닝 규칙·확정 인덱스를 바꾸지
않는다. 바꾸면 227건이 새로 "오염"이 되어 재캡셔닝 → `text_hash` 변경 → 재임베딩 →
**test 39를 평가했던 그 인덱스가 아니게 된다.** 별도 승인 사건이다.

```
technical  A measurable class of foreign-script insertions falls below the current
           detector threshold; the measured rate is a candidate rate, not a
           contamination ground truth.
easy       검출기가 못 잡는 유형이 있다는 것은 재봤다. 다만 그 숫자가 곧 "오염된 캡션
           비율"은 아니다 — 간판 글자를 정확히 옮긴 정상 캡션도 섞여 있다.
재현        python docs/probes/caption_foreign_char_scan.py
근거        docs/probes/_scratch/caption_foreign_char_scan.json · 매트릭스 C14
```

---

## 12. 재현성 · fail-closed

> 성능 숫자만 만든 것이 아니라, **잘못된 run·config·artifact가 정상 결과처럼 쓰이는
> 것을 막는 장치**를 코드로 넣었다.

| 장치 | 막는 것 | 위치 |
|---|---|---|
| deployment preflight (12항목) | 잘못된 모델·양자화·임베딩·α·인덱스 조합으로 시작하는 것 | `scripts/demo.py` |
| α drift rejection | α≠0.5로 데모를 돌리는 것 | `scripts/demo.py` |
| `text_hash` | 재캡셔닝 후 m4 미실행 상태의 낡은 임베딩 | `common.index_text_hash` |
| embed_model 대조 | 다른 임베딩 모델로 만든 인덱스와 점수를 섞는 것 | `scripts/demo.py` |
| provenance 등록 | 미등록 영상 처리 (external E2E PHASE 1에서 실제 발동) | `src/provenance.py` |
| 자동 판정 전용 QC | 사람이 캡션을 보고 골라 고치는 것 | `common.is_corrupted_caption` · `is_subtitle_credit` |
| label allowlist | 라벨 도구가 캡션·자막·검색 결과를 보는 것 | `scripts/label_guard.py` |
| 마커 · RUN_COMPLETE · validator | "프로세스가 사라졌다"를 완료로 읽는 것 | `scripts/run_status.py` · `exp_launcher.py` |
| CANARY coverage 선언 | canary 없이 본 배치로 직행하는 것 | `scripts/canary_coverage.py` |
| 동결 바이트 고정 | 개행 변환으로 동결 artifact 해시가 흔들리는 것 | `.gitattributes` |
| AAR 추적 검증 | 인용 범위 밖·인용 없는 문장·video_id 불일치 | `scripts/aar_view.py` |
| test split guard | test 4편을 데모로 돌리는 것 | `scripts/demo.py` |
| E2E public-demo eligibility guard | 선언된 데모 부적격이 강제되지 않는 것 | `scripts/demo.py` (`demo_ineligible`) |

단위테스트 **1,757건**(GPU 불필요). `src/mN_*.py` ↔ `tests/test_mN_*.py` 1:1 대응.

### 생성 결정성 — 조건부다

```
같은 서버·commit·경로   AI Hub 2,328구간 재생성 → 상이 0건 · 완전일치 1.0
                      MRR도 소수 4자리까지 동일
p3_opcost 두 실행      출력 길이·토큰 완전 동일 (3B 133.6자·92.2 / 4B 82.9자·59.7)
기계를 건너면          캡션 완전일치율 25.6%(dev) · 23.2%(AI Hub A-half)
그럼에도 검색 성능      562질의 Δ −0.0046 · CI95 [−0.0267, +0.0174] (MDE ±0.036)
                      → 큰 방향성 환경 페널티는 재현되지 않았다
```

**문자열이 달라지는 것을 곧 성능 저하로 읽지 않는다.** 다만 2026-08-14↔08-17 dev
655구간에서 8건(1.2%)이 달라 MRR이 움직인 사례가 있고, 그 두 실행 사이의 **통제되지 않은
차이는 여전히 미확정**이다.

**금지** — "완벽히 재현 가능" · "fully reproducible".

---

## 13. AAR  **(READY — 2026-08-26 서버 1회 완주)**

```
renderer / traceability path   ready       scripts/aar_view.py (LLM 미사용 · 결정적 렌더)
server runbook                 ready       AAR_SERVER_RUNBOOK_2026-08-26.md
server config 생성기            ready       scripts/make_server_config.py (본 config 편집 금지)
로컬 full generation            불가        report_model 7B · 6GB에서 4bit로도 실행 불가(실측)
                                          3B 하향은 프롬프트 예시 복사 오염으로 2026-07-11 기각
precomputed report 로컬 렌더     가능
실제 report.json artifact       **확보**     work/gwaktube_soviet_apartment/report.json
```

### 실행 기록 (functional run)

```
대상        gwaktube_soviet_apartment · dev · 149구간
서버        RTX 4090 24GB · /ssd · llm_4bit false(bf16) · peak VRAM 18.1GB
모델        Qwen/Qwen2.5-7B-Instruct · map_chunk 60/overlap 5 · max_new_tokens 16384
소요        212초 (2026-08-26 14:08:56 → 14:12:28 +09:00)
입력        segments.json sha256 4c37c1cc… · 91,711바이트 · 149구간 · 실행 후 불변
           M8은 segments.json만 읽는다 — 영상·프레임·임베딩·retrieval·test artifact 불필요
코드        로컬 HEAD 7621fe1 (clean) · src+scripts 69파일 manifest 4e0193e8… 서버와 동일
           (실행 시점 SHA는 e00603d였다 — 2026-08-26 히스토리 재작성으로 바뀌었고
            src·scripts 바이트는 동일하다. HISTORY_REWRITE_2026-08-26.md 참조)
config     base 72475952… → server d97570fe… · 변경 키는 llm_4bit·paths 둘뿐 · 불변 14키 assert PASS
산출        report.json sha256 1a9e1429… · 47,719바이트 · 서버↔로컬 해시 일치
결과        schema v2 · 문장 83 · 인용 구간 121/149(0.8121) · 인용 없는 문장 0 ·
           범위 밖 인용 0 · 문장 중복 0 · 한 문장 최대 인용 13(퇴화 상한 아래)
```

### 검증 결과

```
생성기 자체 검증 4개      PASS  (반복 루프 · 인용 범위 · 서술 공백 · reduce 퇴화)
                              save_report 직후 실행되므로 종료코드 0이 통과 증거다
check_precomputed        ok    사용 가능
demo.py preflight        AAR 사전 생성물 "없음/사용 불가" → **"사용 가능 (문장 83 · 인용 구간 121)"**
traceability 10항목       10/10 PASS
   모든 문장에 인용 · 인용 0<=idx<149 · timestamp <= duration · seek_to 유효 ·
   video_id 일치 · evidence lookup 가능 · schema 지원 · stale mismatch 없음 ·
   span == 인덱스 실측값 · evidence == 인덱스 원문(렌더가 지어내지 않았다)
```

`index_consistency.n_segments_checked`는 **false**다 — `report.json` provenance에
`n_segments`가 없기 때문이고 결함이 아니다(렌더러가 그 경우를 보고만 하도록 설계돼 있고
테스트도 있다). 인덱스 대응은 **생성 입력 `segments.json`의 sha256이 로컬 원본과 같음**으로
판정했다 — 구간 수만 세는 것보다 강한 검사다.

### 관측된 것 — 계량하지 않는다

> 리포트 서술과 인용 구간 근거가 어긋나는 문장이 있다. timeline 앞 5건(**위치 기준 ·
> 내용을 보고 고르지 않았다**) 중 `sent 0`의 서술 "남성이 창고에서 상자를 열어 내용물을
> 확인한다"가 `seg#0`의 캡션·자막 어느 쪽과도 대응하지 않는다. 나머지 4건은 인용 구간
> 근거와 대응했다.

**리포트 내용 품질 관측이고 기능 실패가 아니다.** 프롬프트·규칙을 바꾸지 않았고,
이 관측을 비율·지표로 계량하지 않았다 — **그것은 M8 research evaluation 영역이고 HOLD다.**

### 저장소 정책

`report.json`은 `work/` 아래라 이미 추적 대상이 아니다. **렌더본(`AAR_SAMPLE_*.md` ·
`aar_sample_*.json`)도 추적하지 않는다** — 인용 구간의 **자막·캡션 원문이 그대로 실린다**
(자막 99 · 캡션 121구간). `work/*/segments.json`을 공개하지 않는 것과 같은 이유다.
저장소에는 해시·수치만 남기고 재생성은 `scripts/aar_view.py`로 한다.

### 정확한 상태 문장

> **AAR demo functional path completed on one dev/demo video:
> server generation → artifact verification → local render → evidence trace.**

이것은 **functional completion**이지 **research evaluation이 아니다.**

**금지** — `end-to-end AAR complete` · "AAR 완주 완료" · `AAR research accuracy validated` ·
`M8 evaluation complete` · `AAR quality proven` · `test AAR validated`.

### 이름을 반드시 가른다

```
AAR demo generation using existing M8 pipeline   =  finalization functional run  (완료)
M8 research evaluation / taxonomy / human review =  HOLD (별도 사건)
```

산출물에 `run_kind: "aar_demo_render"` · `m8_research_evaluation: false` ·
`m9_evaluated: false` · `test_split_used: false`가 박혀 있어 파일만 봐도 구분된다.

추적 경로는 **문장 → 인용 segment → timestamp → seek → 근거(자막·캡션)**이고, 잇지
못하면 `TraceError`로 막는다.

```
technical  A validated dev/demo AAR report artifact was generated on the server and
           rendered locally with citation-to-segment traceability.
easy       리포트를 서버에서 한 번 만들어 노트북으로 가져왔고, 문장마다 근거 구간·시각·
           재생 위치까지 되짚어지는 것을 확인했다. 리포트 내용이 얼마나 정확한지를 잰
           것은 아니다.
근거        final_report_facts_2026-08-26.json (aar.demo_run) · 매트릭스 C15
```

---

## 14. 한계

`final_report_facts_2026-08-26.json`의 `limitations[]`에 id로 고정돼 있다.

```
L01  3B/4B superiority unresolved
L02  AI Hub external validity — 짧은 clip · 후보 12구간 · 유형 라벨 없음 · 재사용 표본
L03  deployment-like dev의 video cluster가 3 — CI는 진단용. ICC 0을 진실로 가정하지 않음
L04  P2 annotation 미완 (175행 설계 중 20행) — 병목은 라벨 작성 자체
L05  P3 규모·권리·logistics — 막는 것은 통계가 아니다
L06  질의 유형 이질성·풀 크기 효과는 plausible contributor까지
L07  test 미개방 — 최종 test 결과를 이번 기간에 새로 생산하지 않았다
L08  기계를 건너면 캡션 문자열이 달라진다 (성능 저하로 해석하지 않는다)
L09  AAR 생성은 서버 GPU 의존 (로컬 6GB 불가). demo artifact 1건 확보 · 내용 품질 미평가
L10  자막형 트레이드오프 (0.9583 → 0.8802)
L11  재현에 원본 영상이 필요 — 영상·파생 텍스트 비공개
L12  캡션 QC 검출기가 2자 삽입형을 flag하지 않는다 (후보 비율은 오염 GT가 아니다)
L13  external E2E는 functional validation이고 성능 평가가 아니다
L14  캡션→검색 사례 연구는 영상 1편·15질의의 정성 관찰 (실행 환경 동일성 미입증)
L15  평가 도메인이 좁다 — 한국어 vlog 계열 11편(그중 평가 대상 7편)
```

---

## 15. 향후 과제

**현재 HOLD와 future work를 혼동하지 않는다.** 아래는 현재 프로젝트에서 하겠다는 약속이
아니다.

```
F01  rights-cleared 외부 annotation 경로 기반 fresh deployment-like P3 실행
F02  더 큰 한국어 long-form GT — dev cluster 3의 한계를 정면으로 푸는 길
F03  질의 유형 이질성 확증 (복합형 열세 · 장면형 우세의 재현 여부)
F04  유형별 캡션 모델 라우터 (P3-B 설계만 있음, 미실행)
F05  caption QC detector v2 — **별도 dev fixture에서** 개발. 확정 인덱스에 소급 적용 안 함
F06  I1 production 통합 — read-only diagnostic/warning부터 검토하고 별도 승인
F07  AAR / M8 research evaluation 계속 (6분류 taxonomy · human review) — 현재 HOLD
F08  M9 · test 확장 — 명시적 승인 하에서만
F09  4B 재검토 — fresh evidence가 뒷받침할 때
F10  회의록 생성 (Phase 4) — 설계만 있음
```

---

## 16. 최종 보고서의 중심 이야기

```
1  작동하는 Korean long-form moment retrieval system을 만들었다.
2  caption model을 3B에서 4B로 바꿀 가치가 있는지 검토했다.
3  AI Hub와 deployment-like dev에서 결과 방향이 달라 단순한 winner conclusion이
   불가능했다.
4  fresh confirmation을 시도했지만 human GT annotation 비용에서 현실적 병목이 생겼다.
5  더 강한 확인 실험을 설계했지만 시간·권리·annotation 제약 때문에 실행을 HOLD했다.
6  대신 finalization으로 전환해 검색·근거·재생·E2E·AAR path·reproducibility를
   제출 가능한 시스템 수준으로 정리했다.
7  추가 qualitative case study에서, 캡션 모델이 같은 화면에서 어떤 정보를 선택해
   쓰는지가 실제 retrieval ranking으로 전달되는 경로를 확인했다.
8  따라서 현재 결론은 — 3B incumbent 유지 · 4B candidate · superiority unresolved ·
   future fresh deployment-like evaluation 필요.
```

**이 이야기를 "연구 실패"로 쓰지 않는다.** 핵심은 문제를 발견하고, 검증 한계를
확인하고, 과도한 결론을 피한 뒤, **재현 가능한 시스템과 후속 설계를 남겼다**는 것이다.

---

## 17. 연구 규율도 결과로 포함한다

성능이 아니라 **프로세스 품질**로 표현한다.

```
outcome access 전 freeze          케이스 스터디 질의·장면 해시를 동결한 뒤 처음 열었다
partial GT 미분석                 P2 20행을 어떤 분석에도 쓰지 않았다
test unopened                    이번 기간 접촉 0회 · 39→72 확장 미개방 · M9 미실행
fail-closed provenance           미등록 영상은 M1에서 멈춘다 (실제 발동)
external rights audit            35편 전부 unclear로 그대로 기록했다
deployment / candidate 분리       배포 identity와 후보를 문서·코드·테스트에서 갈랐다
functional vs semantic E2E 분리   REVIEW는 functional FAIL이 아니다
사례 연구 scene/query 사전 동결     결과가 재미없어도 바꾸지 않았다
external anchor 미수정            결과에 맞춰 라벨을 고치지 않고 REVIEW로 남겼다
caption QC 자체 측정              규칙을 바꾸지 않고 기록만 하는 선택을 문서화했다
```

**금지** — 이것을 성능 성과처럼 쓰는 것. 경계를 지켰다는 사실이 결과의 강도를 올려주지
않는다.

---

## 18. 표·그림 후보

새 시각화를 만들지 않았다. **후보 목록과 필요한 수치만 정리한다.**

| id | 목적 | 출처 artifact | 필요한 수치 | 캡션 문구 | 상태 |
|---|---|---|---|---|---|
| T1 | 시스템 아키텍처 | `SYSTEM_ARCHITECTURE_2026-08-25.md` (mermaid) | 단계별 확정값 표 | "production path — 확정 배포 구성" | **READY** (기존 mermaid 재사용) |
| T2 | 부호 역전 대조 | `재분석_2x2` · `재분석_dev정밀도3arm` | AI Hub +0.0310 [+0.0080,+0.0536] / dev −0.0903 [−0.2112,−0.0276] · n·cluster·정밀도 | "두 표본에서 방향이 반대다. 어느 쪽도 확증 자격이 없다" | **READY** |
| T3 | 3B vs 4B 운영 프로필 | `OPERATIONAL_PROFILE_SUMMARY` | wall-clock 중위수 · reserved VRAM · 저장 · OOM 0 | "deployment blocker 없음 · resource-footprint penalty 있음" | **READY** |
| T4 | 케이스 스터디 scene02 | `CAPTION_RETRIEVAL_CASESTUDY_RESULTS` | 두 캡션 · 두 질의 순위(1↔15 · 18↔1) | "같은 프레임, 다른 선택, 1위가 뒤집힌다 — illustrative" | **READY** (프레임 이미지는 미추적·비공개) |
| T5 | wrong-top1 추적 (scene01) | 같음 | target 캡션 · seg188 캡션 · 순위 | "정답 캡션에 없던 단어가 오답 1위 캡션에는 있었다" | **READY** |
| T6 | P2/P3 진행과 HOLD | `P2_활성설계` · `P3_설계민감도` | 20/175 · 300×5=1,500 · blocking_item | "확인을 시도했고, 어디서 막혔는지" | **READY** |
| T7 | external E2E 커버리지 | `e2e_external_results.json` | 4 PHASE 길이·구간·PASS·소요 | "short / speech / mixed / long-form functional paths completed" | **READY** |
| T8 | 한계 · 향후 과제 | `final_report_facts` | L01~L15 · F01~F10 | "한계와 다음 단계를 분리한다" | **READY** |
| T9 | 공식 test 결과 | `results/eval_test.json` | MRR·Hit@1과 CI · 유형별 MRR | "Hit@5·Hit@10은 CI가 0을 포함한다" | **READY** |

프레임 이미지가 들어가는 T4·T5는 **원본 영상 프레임이라 저장소에 추적하지 않는다** —
보고서에 넣을 때 별도 판단이 필요하다.

---

## 19. Source conflict audit

같은 항목이 서로 다르게 적힌 곳을 찾아 기록했다. **frozen artifact는 수정하지 않았다.**

### CF-01 — preflight 확인 항목 수 (11 vs 12)

```
location A   docs/작업현황_2026-08-25.md:35, 46          항목 수를 11로 적었다
location B   scripts/demo.py · README.md · finalization 문서 7곳   12항목
authoritative  scripts/demo.py (코드) — CONFIG/DEPLOYMENT 우선순위 1위
사실           2026-08-26 F4에서 E2E 전용 영상 차단을 추가해 11 → 12가 됐다
action        작업현황_2026-08-25는 **그날의 스냅샷**이라 당시에는 맞았다.
              숫자를 고쳐 기록을 바꾸지 않고 **후속 변경 주석 1줄**을 달았다
```

### CF-02 — 단위테스트 수 (1,719 · 1,725 · 1,748)

```
location A   docs/tutor/튜터회의_2026-08-25.md:456   테스트 1,719건 통과 (08-25 기록)
location B   F4_DOCUMENTATION_AUDIT_2026-08-26.md    1,719 + 6 = 1,725 (08-26 F4 시점)
location C   README.md · 본 팩 §12                   1,757  (F5 23 + AAR 4 + 프레임 guard 5)
authoritative  pytest 실측 — 인용 시점의 값이 authoritative다
action        A·B는 preserved — 각각 그 시점의 기록이다(회의 기록·감사 기록). 고치지 않는다.
              현재 상태를 말하는 문서(README · source pack · matrix)만 1,748로 맞췄다.
              **테스트가 늘 때마다 바뀌는 값**이므로 fact index에 as_of를 붙였다
```

### CF-03 — 추가 foreign-script candidate의 CJK/가나 비율 (87.7% vs 88.5%)

```
location A   docs/finalization/LIMITATIONS_FUTURE_WORK_2026-08-25.md:56   "87.7%"
location B   docs/probes/_scratch/caption_foreign_char_scan.json   201 / 227 = 88.55%
authoritative  scan JSON (NUMERIC RESULT 우선순위 1위 — frozen raw artifact)
action        **활성 문서 LIMITATIONS를 88.5%로 정정했다.** scan JSON은 건드리지 않았다
```

### CF-04 — subtitle-only baseline 0.4107 vs 0.4144

```
검토 결과     충돌 아님. 서로 다른 데이터셋의 값이다
             0.4107 = AI Hub (네 arm 동일)   0.4144 = dev α=1.0 (세 arm 동일)
현재 표기     docs/tutor/튜터회의_2026-08-25.md가 이미 두 값을 구분해 적고 있다
action        no action. 본 source pack §4-4에 구분 규칙을 명시했다
```

### CF-05 — 금지 표현 스윕

```
금지 검색어   3B 승리 · 3B가 이겼 · 4B 실패 · 4B 기각 · 4B가 더 좋 · 운영비가 싸 ·
            cheaper · 더 효율적 · 미탐률 · 오염 0
결과        활성 문서에서 **전부 금지 목록 안 또는 부정문 안에서만** 등장한다
            (F4 감사 문서의 "이렇게 쓰지 않는다" 서술 포함)
action      no action
```

### CF-06 — AAR 완료 표현

```
검토        README 구현 상태표의 "M8~M9 구현 완료"가 artifact 확보로 읽히는지 확인했다
결과        같은 칸에 "로컬 6GB에서 생성 불가" · "M8 research evaluation HOLD"가 병기돼 있고,
            README §Quick Start는 서버 runbook을 가리킨다. artifact가 있다고 주장하지 않았다
action      2026-08-26에 artifact를 실제로 확보해 §13을 READY로 바꿨다.
            표현은 functional completion으로 한정한다 — research evaluation이 아니다
```

### CF-07 — runbook 초판 결함 3건 (2026-08-26 실행에서 드러남)

```
① 접속 주소   `<LAB_MACHINE>`(머신 라벨)을 호스트명처럼 써서 이름 해석에 실패했다.
             실제 계정명도 공개 저장소 문서에 그대로 노출돼 있었다
             → `<SERVER_USER>`·`<SERVER_HOST>` 자리표시자로 바꿨다(SERVER_LOCAL.md 규약)
② 인터프리터  runbook에 명시가 없었고 서버 system python3에는 torch가 없다
             → `/ssd/$U/envs/prj/bin/python`을 셸 변수로 고정했다
③ 검증 스니펫  `r["n_segments"]`를 assert하는데 `m8_report.save_report`는 그 필드를 쓰지 않는다.
             **정상 리포트에서도 반드시 실패하는 검사였다**
             → 실제 스키마(video_id·schema_version·인용 범위·인용 없는 문장)로 바꾸고,
               인덱스 대응은 segments.json 해시 일치로 판정하게 했다
authoritative  실제 코드(`src/m8_report.py`) · SERVER_LOCAL.md
action        runbook을 고쳤다. **생성 코드는 바꾸지 않았다** — 결과를 본 뒤 생성 조건을
              바꾸는 것이 되므로 별도 승인 사건이다
```

```
conflicts_found          7건 검토 (실질 충돌 4 · 무충돌 확인 3)
fixed_active_docs        3건 (CF-01 주석 · CF-03 수치 정정 · CF-07 runbook 3항목)
frozen_conflicts_preserved  1건 (CF-02 — 튜터 회의 기록)
remaining                0
frozen artifact modified  0
생성 코드 변경             0 (CF-07 ③은 문서만 고쳤다)
```

---

## 20. Source-of-truth 우선순위 (이 팩에서 적용한 규칙)

```
NUMERIC RESULT   ① frozen raw/result artifact
                 ② 해당 실험의 frozen analysis 문서
                 ③ current finalization summary
                 ④ README · tutor 요약

STATUS           ① current status / HOLD artifact
                 ② current finalization documentation
                 ③ README
                 ④ historical document

CONFIG/DEPLOYMENT ① 실제 config · 코드 · preflight
                 ② architecture / current deployment 문서
                 ③ README
```

README나 tutor 요약의 숫자가 frozen result와 다르면 **README를 source로 삼지 않는다.**

---

## 21. 이 작업에서 하지 않은 것

```
새 모델 실행 · 재평가 · metric 재계산       없음
새 bootstrap · CI · 유의성 · random baseline  없음
test / M9 접근                            없음
P2 / P3 outcome 접근                      없음
alpha sweep · deployment 변경              없음
contamination detector 변경                없음
case study scene/query 변경                없음
새 human labeling                         없음
frozen artifact rewrite                   없음
PPT 제작 · 발표 리허설 · push               없음
```
