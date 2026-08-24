# P3 — 4B 배포 교체 확증 실험 **설계 DRAFT** (2026-08-24)

> **이 문서는 DRAFT다.** 사전등록이 아니고, 실행 승인이 아니다.
> **실행 상태: HOLD.** P3 retrieval·모델 추론·GT 생성·표본 수집·arm 비교를 하지 않았다.
>
> **2026-08-24 사용자 결정 반영분** — 경로는 **P3-A 승인**, 표본 출처는 **신규 한국어
> long-form fresh collection 기본 승인**. 아직 승인하지 않은 것은 half-width 임계 ·
> `k × m` · 총 GT 행 수 · 라벨 경로 · 실행 GO다. P3-C를 고르지 않았으므로 δ·secondary
> benefit 결정은 defer.

선행: `docs/P2_GT_sample_size_amendment_2026-08-24.md` · `docs/재분석_부호역전_2026-08-18.md`
· `docs/재분석_P1풀크기_2026-08-18.md` · `docs/preregistration/부호역전_확증_보충2_P2설계_2026-08-20.md`
· `docs/probes/_scratch/p2_annotation_hold_2026-08-24.json`

---

## 1. research question

```
아니다   "4B가 더 좋은 VLM인가"
이다     "현재 실제 배포 구성에서 3B를 4B로 교체할 근거가 fresh data에 있는가"
```

배포 구성은 `Qwen2.5-VL-3B / P0 / 4bit · KURE-v1(1024) · z-score 융합 · α=0.5`다.
4B는 **candidate이고 not adopted**다. 이 문서는 그 상태를 바꾸지 않는다.

---

## 2. P2 HOLD가 3B/4B를 정리해주지 않는 이유

P2는 표집·색인·프로토콜 준비를 마쳤고 GT 작성이 라벨 비용 때문에 20/175에서 멈췄다.
retrieval·evaluation은 **한 번도 실행하지 않았다**(`p2_annotation_hold_2026-08-24.json`
의 `outcome_access` 4항목 전부 false).

```
P2가 만든 것       long-form 2-arm 색인 (35편 9,115구간, run p2idx_0821d, validator 17항목 PASS)
P2가 만들지 않은 것  fresh 3B/4B 부호 증거
```

따라서 부호 역전은 **미해결로 남아 있다**.

| 표본 | Δ (캡션 단독) | CI | 성격 |
|---|---|---|---|
| AI Hub 1,086질의 (194 cluster) | **+0.0310** | [+0.0080, +0.0536] | 재사용 표본. 4B 우세 방향 |
| dev 96질의 (3 cluster) | **−0.0903** | [−0.2112, −0.0276] | cluster 3 — **진단용만** |

```
P2 HOLD는 3B 우세의 증거가 아니다
P2 HOLD는 4B 기각의 증거가 아니다
partial GT는 어떤 분석에도 쓰지 않는다
```

> Current deployment remains 3B because there is insufficient fresh
> deployment-relevant evidence to justify switching, not because 3B has been
> established as universally superior.

---

## 3. α=0.5가 deployment-relevant인 이유, 그리고 α=0.0을 반드시 함께 재는 이유

α는 config에 없고 CLI로 주입한다(`--alpha`). 확정값 α*=0.5는
`results/alpha_search_dev.json`의 `alpha_star`이고, **배포·웹 UI가 실제로 쓰는 값**이다
(`src/m7_webui.py --alpha 0.5`). 교체 판단의 대상은 배포 구성이므로 PRIMARY는 α=0.5다.

동시에 CLAUDE.md 후보검증 규약 1번은 **후보가 바꾸는 채널 단독 측정**을 요구한다.
융합이 개선분을 희석한 것이 실측으로 있다.

```
AI Hub 4B/P0   캡션 단독 α=0.0   +0.0310  [+0.0080, +0.0536]   0 배제
               융합    α=0.5     +0.0191  query CI가 0을 포함    비유의
```

그래서 α=0.0은 **선택적 exploratory가 아니라 반드시 계산·보고하는 key secondary**다.
채널 격리 요구는 이 mandatory endpoint로 충족한다.

**그러나 α=0.0이 α=0.5 PRIMARY의 실패를 구제하지 않는다.** 해석 규칙은 §7에 결과 전
고정한다.

α 재최적화 금지: P3에서 α curve를 다시 보고 유리한 α로 옮기지 않는다. α=0.5가 불리하게
나오는 것은 결과이지 설정 오류가 아니다.

---

## 4. 경로 비교 — P3-A / P3-B / P3-C (+ 진단 D·S)

### P3-A — fresh deployment-config comparison **(기본 추천)**

배포 구성 그대로 두 arm을 새 표본에서 비교한다. 교체 질문과 직접 일치한다.

고정 항목:

```
같게 두는 것   영상 · 질의 · 자막(STT) · 세그먼트 격자 · 프롬프트 · embedder ·
              양자화 class · α=0.5 · 하드웨어 · commit · 코드 경로
다른 것        caption_model 하나뿐
비교           paired (질의 단위) · cluster = 영상
```

### P3-B — predeclared query router

`장면형 → 4B · 그 외 → 3B` 같은 hybrid system을 whole-system으로 비교한다.

**지금 이 규칙을 채택하면 post-hoc이다.** dev 층별 결과를 이미 봤다.

```
복합형 n=34  Δ −0.2407      자막형 n=24  Δ −0.0412      장면형 n=38  Δ +0.0132
(docs/재분석_부호역전_2026-08-18.md §4)
```

선택하려면 필요한 것: ① routing rule을 fresh 표집 **전에** 동결, ② routing feature가
모델 산출물(캡션·점수·순위)을 쓰지 않음, ③ whole-system 성능으로 비교, ④ 배포 복잡도·
지연을 함께 보고. **P3-A와 다른 estimand임을 명시한다** — "어느 모델이 나은가"가 아니라
"두 모델을 쓰는 시스템이 한 모델 시스템보다 나은가"다.

### P3-C — non-inferiority + predeclared secondary benefit

검색 우월이 아니라 **사전 정의된 허용 손실 + 사전 정의된 부수 이익**을 채택 논리로
쓰는 별도 framework.

```
Δ_retrieval > −δ   그리고   사전 정의된 secondary benefit 충족
```

**저비용 경로가 아니다.** 비열등성은 CI 하한이 −δ를 넘어야 성립하므로 우월성 검정과
같거나 **더 큰** 정밀도를 요구한다. 라벨을 아끼려고 이 경로를 고르면 δ 안쪽에서 CI가
걸쳐 판정_불가가 된다.

δ와 secondary benefit은 **결과 전에 운용적으로** 정한다. "4B가 더 똑똑해 보인다"는
근거로 쓰지 않는다. → §11 사용자 결정값.

### P3-D — zero-human-label proxy **(diagnostic 한정)**

이미 끝난 P2 색인(35편 2-arm, GPU 20.8h 지불 완료)을 재사용하고, 사람이 질의를 쓰지
않는 자동 질의로 두 arm을 비교한다. **사람 라벨 0건.**

강제 경계 — 이 경로의 결과는:

```
PRIMARY 자격 없음
deployment adoption evidence 자격 없음
test-opening 근거 자격 없음
실제 사용자 query estimand와 다름 (질의 분포가 사람 질의가 아니다)
P3-A의 endpoint·sample size·exclusion·α를 조정하는 근거로 쓰지 않음
outcome-dependent tuning source로 쓰지 않음
```

목적은 하나다 — **정식 fresh confirmation에 비용을 쓸 가치가 있는지 보는 저비용
diagnostic.** 자동 질의 생성 규칙은 실행 전에 동결하고, 순환 방지를 위해 질의 채널과
평가 채널을 분리해야 한다(예: 자막 파생 질의라면 캡션 채널로만 순위를 낸다). 규칙 확정은
경로 승인 후 별도 항목이다.

### P3-S — scene-only best-case diagnostic **(필요한 경우에만, appendix)**

이 도구 환경에서 AI 초안이 가능한 유형은 **장면형뿐**이다(mp4·음성을 읽지 못한다는
실측). 그런데 장면형은 dev에서 **4B에 유리한 층**(+0.0132)이다. 그래서 장면형 단독
표본을 일반 4B adoption 실험으로 쓰면 §5의 금지 첫 줄에 걸린다.

```
negative → 4B에 strongly unfavorable diagnostic (유리한 층에서도 못 이겼다)
positive → general deployment adoption evidence 아님 (층 편향)
```

**"negative면 결정적"이라고 쓰지 않는다.** scene-only 결과 하나가 전체 deployment에
대한 결정적 기각 증거가 되지는 않는다 — 강하게 불리한 진단까지다.
**정식 P3-A의 대체물로 쓰지 않는다.**

---

## 5. P3에서 하지 않는 것

```
현재 dev strata를 보고 유리한 query type만 선택
AI Hub와 dev 중 4B에 유리한 sample만 재사용
P2 partial GT 사용
P2 arm retrieval을 먼저 열어 sample size 결정
alpha curve를 다시 보고 alpha 최적화 · α=0.5가 불리하면 다른 α로 교체
outcome-dependent top-up · outcome-dependent exclusion
test를 P3 dev substitute로 사용
4B deployment를 먼저 바꾸고 평가
```

---

## 6. PRIMARY / KEY SECONDARY

```
PRIMARY (교체 질문)
  Δ_deployment = MRR_fusion(4B q4, α=0.5) − MRR_fusion(3B q4, α=0.5)

MANDATORY KEY SECONDARY (채널 격리)
  Δ_caption    = MRR_caption(4B q4, α=0.0) − MRR_caption(3B q4, α=0.0)

단위   질의 단위 paired · cluster = 영상 · 양 arm 4bit(배포 경로 정밀도)
```

**P2의 frozen PRIMARY(캡션 단독 α=0.0)를 소급 변경하는 것이 아니다.** P2는 HOLD
상태로 그 규칙을 그대로 유지하고, P3는 별도 사전등록의 새 estimand를 갖는다.

---

## 7. 해석 규칙 — **결과 전 고정**

| PRIMARY (α=0.5) | KEY SECONDARY (α=0.0) | 해석 |
|---|---|---|
| 4B 지지 | 4B 지지 | 가장 강한 4B replacement evidence |
| 판정 불가 | 4B 지지 | caption-channel gain은 관측됐다. **deployment adoption evidence는 불충분**하고, 4B 기각도 아니다 |
| 3B 방향 | 4B 지지 | caption gain이 deployment benefit으로 전이되지 않는다. **3B를 교체할 근거 없음** |
| 4B 지지 | 판정 불가 | deployment benefit은 관측됐으나 채널 격리 기전이 불확실 |
| 판정 불가 | 판정 불가 | inconclusive |
| 3B 방향 | 3B 방향 | 4B replacement not supported |

"4B 지지 / 3B 방향 / 판정 불가"의 경계(유의 기준·CI half-width 임계)는 **§11 사용자
결정값**이다. 근거 없이 새로 발명하지 않는다.

---

## 8. 표본 출처 — **신규 한국어 long-form fresh collection (승인됨)**

정식 P3-A의 기본안은 **새로운 한국어 long-form deployment-like fresh 표본**이다.
다음과 중복을 금지한다.

```
AI Hub reused evaluation sample · dev · P2 · test/M9
```

배포 도메인에 최대한 가까운 표본으로 잡는다. 아래 조사 기록은 그 결정의 근거로 남긴다.

**조사 결과 문구는 절대 표현을 쓰지 않는다** — 검색이 전 세계 데이터셋의 부재를 증명한
것이 아니다. 정확한 진술은 이것이다.

> **현재 조사 범위에서 deployment-relevant한 적합 fresh temporal GT 후보를 찾지 못했다.**

영어·short-domain 벤치마크를 **비용 절감을 이유로 formal P3-A에 강제 채택하지 않는다.**

### 8-1. 한국어 long-form + temporal GT 공개 벤치마크 — 현재 조사 범위에서 적합 후보 없음

| 후보 | 언어·규모 | 판정 |
|---|---|---|
| AI Hub `003.비디오 장면 설명문 생성` **Validation** | 한국어 · 194편 1,086질의 | **소진** — 2×2 확증에 사용. A-half 459 / B-half 627 둘 다 씀 |
| 같은 데이터셋 **Training** split | 한국어 · 대규모 | **fresh하지만 부적합** — §8-3 |
| KMSAV (ETRI) | 한국어 · 150h 전사 | temporal GT가 **발화 전사**다. moment-retrieval 질의 GT가 아니다 |
| KEMDy20 · KETI 수어 | 한국어 | 과제 불일치 |

### 8-2. 영어 long-form: 존재하나 deployment relevance가 낮다

| 후보 | 규모 | 문제 |
|---|---|---|
| ExtremeWhenBench | 194편 2,273질의 · 평균 75.7분 | **영어.** 후보 풀 regime은 P2와 가장 가깝다. 질의 번역·격자 변환 규칙 동결 필요, 라이선스 미확인 |
| QVHighlights · Charades-STA · TACoS · DiDeMo | 3분 미만 | **후보 풀이 작다** — 4B가 이미 이긴 조건을 재생산한다(§8-4) |
| TVR / mTVR | TV 클립 · 한국어 없음 | 언어·도메인 불일치 |

**"라벨이 싸다"는 이유로 영어 벤치마크를 P3-A에 채택하지 않는다.** 파이프라인은 한국어
캡션 + KURE-v1 한국어 임베더다. 변환이 필요하면 ① 변환 규칙 사전 동결, ② language/
domain shift 명시, ③ **deployment-relevant evidence 강도 하향**을 함께 적는다.

### 8-3. AI Hub Training split을 P3-A로 쓰지 않는 이유

fresh 표본이고 사람 GT가 있어 라벨 비용이 0이다. 그런데 두 가지가 걸린다.

```
1  §5 금지 — AI Hub는 4B가 이긴 표본이다. 그쪽을 다시 고르는 것은
   "4B에 유리한 sample 재사용"이다
2  후보 풀이 영상당 12구간이다 — P1이 지목한 축(풀 크기)을 건드리지 못한다.
   배포는 영상당 약 150~400구간이다
```

쓸 수 있는 자리는 **replication diagnostic**이다(P3-D·P3-S와 같은 등급). PRIMARY 자격
없음. 쓰려면 그 등급을 명시해 별도 항목으로 사전등록한다.

### 8-4. 왜 풀 크기가 표본 선택의 핵심인가

P1은 양방향 조작에서 `I_pool < 0`을 관측했다 — **풀이 커지면 4B가 상대적으로 더 손해**다.

```
dev를 12로 줄이니        −0.0903 → −0.0559
AI Hub를 2,328로 늘리니   +0.0310 → +0.0112
남은 격차 0.067은 풀 크기로 설명되지 않았다
```

`재분석_P1풀크기` 판정은 **plausible contributor**까지다. 그래도 표본 선택 기준으로는
분명하다 — **배포 regime(150~400구간)과 겹치는 long-form이어야 한다.**

### 8-5. 그래서 신규 수집이다 (승인된 기본안)

한국어 long-form을 새로 수집하고 GT를 만든다. P2가 이미 이 경로를 걸었고 라벨 비용에서
멈췄다. 그래서 §9가 설계 요구사항이고, **표본 수집보다 라벨 경로 확정이 먼저다** — 경로가
정해지지 않은 상태에서 영상을 먼저 모으면 P2의 병목이 그대로 반복된다.

---

## 9. 라벨 비용을 PRIMARY design requirement로 둔다

목표: **사람이 수백 질의를 처음부터 쓰지 않아도 되는 fresh evaluation.**

조사 순서(위에서부터):

```
1  기존 timestamp GT가 있는 외부 fresh dataset          → §8: 적합 후보 없음
2  공개 한국어 long-form 중 temporal GT 존재            → §8-1: 없음
3  outcome-blind AI 초안 + 사람 검증 필수               → 아래
4  적은 query/video로 cluster 수를 유지하는 설계        → 아래
5  필요하면 독립 외부 annotator                         → 사용자 결정
```

**3번의 실측 제약이 이 설계의 핵심 병목이다.**

```
이 도구 환경   JPG 읽기 가능 · mp4 "cannot read binary files" · 음성 없음
따라서        장면형만 AI 초안 가능. 자막형·복합형은 발화를 들어야 한다
그런데        장면형만 고르면 §5 위반 (4B에 유리한 층)
```

나가는 길은 셋이고 전부 대가가 있다.

| 길 | 사람 부담 | 대가 |
|---|---|---|
| (a) 오디오를 초안 루프에 넣어 전 유형 초안화 | 심사만 | 새 청취 채널 — 별도 amendment 필요. 파이프라인 STT를 보여주는 것은 여전히 금지 |
| (b) 유형 쿼터 유지 + 사람 작성 | 높음 | P2가 멈춘 지점으로 되돌아간다 |
| (c) 장면형 단독을 사전 선언 | 낮음 | estimand가 장면형 한정. **P3-S 등급** — 음수만 결정적 |

**비용을 줄이려고 통계 규칙을 완화하지 않는다.** half-width 임계를 낮추거나, 판정_불가를
"차이 없음"으로 바꾸거나, 표본을 결과 보고 늘리는 것은 전부 금지다.

### 9-1. 라벨 경로 제안 (outcome-blind) — 실행 전 확정 대상

**scene-only AI 생성을 일반 P3-A 라벨 경로로 쓰지 않는다.** 확정해야 하는 네 가지.

| 항목 | 경로 A: 전량 사람 | 경로 B: AI 초안 + 사람 확정 | 경로 C: 외부 annotator |
|---|---|---|---|
| 사전등록 전 유형 처리 가능? | 예 | **조건부** — 오디오를 초안 루프에 넣어야 자막·복합형이 가능 | 예 |
| 사람 최종 검증 범위 | 전건 작성 | **전건 확정 필수** (초안은 제안이고 GT가 아니다) | 표본 감사 + 불일치 재판정 |
| 도구 제약 | 없음 | 이 세션 환경은 mp4·음성을 못 읽는다(실측) — 장면형만 초안 가능 | 없음 |
| 새로 필요한 승인 | 없음 | **amendment** (새 청취 채널). 파이프라인 STT 노출은 계속 금지 | 외부 반출 범위 승인 |
| P2 대비 병목 | 그대로 | 완화되나 amendment 선행 | 완화. 비용·일정이 외부 의존 |

세 경로 모두 공통으로 지키는 것:

```
사람 최종 확정 없이 GT로 세지 않는다 (초안 = 제안)
label_origin·draft_action을 기록하되 PRIMARY의 selection·exclusion·weighting에 쓰지 않는다
질의 유형 쿼터는 표집 전에 동결한다
어떤 경로든 검색 결과·캡션·STT·arm 정체성을 라벨러에게 보여주지 않는다
```

기존 도구가 그대로 쓰인다 — `p2_ai_draft`(프롬프트 동결·스키마 검증·생성 진입점 없음) ·
`p2_adjudication`(label_origin·draft_action audit) · `p2_gt_labeler`(초안/행 값 분리,
행동 명시 없으면 저장 거부) · `label_guard` allowlist.

**expected GT row count는 §10의 정밀도 선택에서 파생된다.** 지금 행 수를 먼저 고르고
정밀도를 맞추는 순서가 아니다.

### 9-2. 라벨 경로가 정해지기 전에는 표본 수집도 하지 않는다

전 유형을 편향 없이 다룰 수 있는 GT 경로와 최종 N이 고정된 뒤에 수집을 시작한다.

---

## 10. 통계 설계 — 재사용할 것과 새로 정할 것

| 항목 | 값 | 출처 |
|---|---|---|
| candidate universe | **질의 자기 영상의 세그먼트** | 보충2 §2-1 · 사전등록 §40 P1-b · `src/m6_evaluate.py:94` |
| cluster 단위 | 영상 | 보충2 §2 |
| 추정량 | paired video-cluster bootstrap | 보충2 §2 |
| bootstrap B | 2000 | P2에서 동결된 값 — 재사용 근거 있음(같은 추정량) |
| bootstrap seed | **사전등록 동결 시 결정론적으로 고정** | 결과와 무관하다. 지금 임의의 숫자를 발명하지 않는다 |
| CI half-width 임계 | **미정** | 0.04는 **P2**의 규칙이다. P3에 자동 승계되지 않는다 → §11 |
| 유의 판정 | CI가 0을 배제하는지 | 보충2 §7 형태 재사용 |
| exclusion | 사전 정의 3종만 | 보충2 §5 — `gold_count_exceeds_pool` · `gold_span_incompatible_with_rule` · `caption_missing` |
| top-up | **금지** | outcome을 보고 규모를 늘리지 않는다 |
| 기록 요구 | model_id·revision·prompt_sha256·dtype·requested/effective_quantized·영상별 세그먼트 수(연속)·embedder·evaluator commit·seg_len | 보충2 §6 |
| 동시점 대조군 | 두 arm을 같은 하드웨어·commit·코드 경로에서 함께 생성 | CLAUDE.md 규약 4번 |
| 한 arm 미완주 | PRIMARY 계산 안 함 (부분집합 비교·RR=0 대입 금지) | 보충2 §6 |

**inconclusive 개념**: CI가 0을 포함하면 "차이 없음"이 아니라 **판정_불가**다. 달성
half-width가 임계를 넘으면 규모를 적고 멈춘다. `k`가 작으면(16 미만) 기술 통계로만
보고한다.

### 10-1. 설계 민감도 — 정밀도 목표별 필요한 라벨 행 수 (outcome-blind)

산출: `scripts/p3_design_sensitivity.py` → `docs/P3_설계민감도_2026-08-24.json`
(테스트 22건). **P3 자료를 만들지도 열지도 않았다.** 쓰는 자료는 과거 진단 표본 하나뿐
(AI Hub 2×2 full, n=1,086 · k=194).

관측 분산 성분 — **두 채널 모두 ICC = 0**:

```
PRIMARY   rr_fus (α=0.5)   σ²_b = 0.000000   σ²_w = 0.142003
SECONDARY rr_cap (α=0.0)   σ²_b = 0.000000   σ²_w = 0.161843
```

`k = ceil(Z²(σ²_b + σ²_w/m)/hw²)` · 총 행 수 = `k × m`

| 목표 half-width | m=3 | m=4 | m=5 | m=6 | m=9 | 총 행 수(≈) |
|---|---|---|---|---|---|---|
| **0.04** PRIMARY(α=.5) | k=114 | 86 | 69 | 57 | 38 | **≈ 343** |
| 0.04 SECONDARY(α=0) | k=130 | 98 | 78 | 65 | 44 | **≈ 391** |
| **0.05** PRIMARY | k=73 | 55 | 44 | 37 | 25 | **≈ 221** |
| 0.05 SECONDARY | k=83 | 63 | 50 | 42 | 28 | **≈ 251** |
| **0.06** PRIMARY | k=51 | 38 | 31 | 26 | 17 | **≈ 154** |
| 0.06 SECONDARY | k=58 | 44 | 35 | 29 | 20 | **≈ 176** |

교차 검증 — `0.06 · m=5` 행이 `k=35 · 175행 · 달성 0.0596`이다. P2의 35영상×5=175와
정확히 일치한다. **즉 P2 규모는 α=0 채널에서 half-width 0.06급 설계였다.**

### 10-2. 목표 half-width가 곧 **확증 가능한 최소 효과 크기**다

CI로 부호를 판정한다면 `Δ ± hw`가 0을 건너지 않아야 하므로 조건은 `|Δ| > hw`다.
따라서 `hw = 0.04`는 **0.04보다 작은 효과를 확증하지 못한다.**

과거 효과 크기는 **endpoint별로 분리해서** 본다 — 융합 값과 캡션 단독 값을 섞으면
계산이 틀린다.

| endpoint | 표본 | Δ | 근거 |
|---|---|---|---|
| **융합 α=0.5** (P3 PRIMARY) | AI Hub 1,086 | **+0.0191** | cluster에서 0 배제 · query CI는 0 포함 (`재분석_2x2 §3`) |
| 융합 α=0.5 | dev 96 | **−0.0764** | 산술 차이 · CI 미사전등록 (`작업현황_2026-08-18 §5-10`) |
| 캡션 α=0.0 (key secondary) | AI Hub 1,086 | **+0.0310** | [+0.0080, +0.0536] (`재분석_2x2 §3`) |
| 캡션 α=0.0 | dev 96 | **−0.0903** | [−0.2112, −0.0276] · cluster 3, 진단용 (`재분석_부호역전 §1`) |

확증 가능성 (m=5 기준):

| Δ | endpoint | hw 0.04 | 0.05 | 0.06 | 확증에 필요한 총 행 수 |
|---|---|---|---|---|---|
| +0.0191 | 융합 | ✗ | ✗ | ✗ | **1,500행** (영상 300) |
| −0.0764 | 융합 | ✓ | ✓ | ✓ | 95행 (영상 19) |
| +0.0310 | 캡션 | ✗ | ✗ | ✗ | 650행 (영상 130) |
| −0.0903 | 캡션 | ✓ | ✓ | ✓ | 80행 (영상 16) |

**"hw 0.04면 AI Hub급 +0.031도 판정 가능"은 틀렸다 — 그 문장을 쓰지 않는다.**
0.031 ± 0.04 = [−0.009, +0.071]로 0을 포함한다.

각 목표가 허용하는 결론:

| 목표 | 허용되는 결론 |
|---|---|
| 0.04 | 0.04 초과 효과만 판정. **작은 양의 이득(+0.02~0.03급) 확증에는 여전히 거칠다** |
| 0.05 | 더 거칠다. dev급 큰 음의 효과는 판정 가능 |
| 0.06 | 큰 음의 효과는 잡히나 작은 양의 효과 확증에는 부적합 — "3B를 교체할 근거 없음"은 말할 수 있고 4B 우세 확증은 어렵다 |

**비용 때문에 임계를 고르지 않는다.** 각 목표가 어떤 결론을 허용하는지와 라벨 부담을
함께 보고 사전 결정한다. 결과를 본 뒤 임계를 바꾸는 것은 금지다.

### 10-3. 표본 규모를 무엇이 정하는가 — **secondary가 자동으로 지배하지 않는다**

α=0.0은 **mandatory key secondary이고 co-primary가 아니다.** 반드시 계산·보고하지만
PRIMARY 실패를 구제하지 않는다. 그래서 "두 endpoint를 다 요구하므로 391행"은 아직
성립하지 않는다 — 두 안을 나란히 두고 사용자가 고른다.

| 목표 hw (m=5) | A: PRIMARY 주도 | secondary 달성 hw | B: 양쪽 동일 임계 | 추가 행 |
|---|---|---|---|---|
| 0.04 | k=69 · **345행** | 0.0425 | k=78 · **390행** | +45 |
| 0.05 | k=44 · **220행** | 0.0532 | k=50 · **250행** | +30 |
| 0.06 | k=31 · **155행** | 0.0633 | k=35 · **175행** | +20 |

A안에서 secondary는 PRIMARY보다 약 **6% 넓다**(분산이 0.142 vs 0.162). 이것이 문제인지는
설계 판단이다 — **secondary도 같은 임계를 만족해야 한다는 규칙은 현재 승인되지 않았다.**
승인하지 않으면 secondary 때문에 N을 자동으로 늘릴 이유가 없다.

### 10-4. ICC robustness — 관측 ICC=0을 진실로 가정하지 않는다

**설계 강건성 진단이고 P3 예측이 아니다.** ICC=0으로 잡은 `hw=0.05` 설계(PRIMARY 채널)를
ICC가 실제로 0이 아닌 세계에 놓으면:

| m | ICC=0 설계 (k · 행) | ICC .03 실제 hw | .10 | .25 |
|---|---|---|---|---|
| 3 | 73 · 219 | 0.0514 | 0.0547 | 0.0611 |
| 4 | 55 · 220 | 0.0520 | 0.0568 | 0.0659 |
| 5 | 44 · 220 | 0.0527 | 0.0589 | 0.0704 |
| 6 | 37 · 222 | 0.0532 | 0.0607 | 0.0744 |
| **9** | 25 · 225 | 0.0548 | **0.0661** | **0.0853** |

같은 목표를 ICC 세계에서 맞추려면 필요한 총 행 수:

```
ICC 0.00   m3 219 · m4 220 · m5 220 · m6 222 · m9 225
ICC 0.03   m3 234 · m4 240 · m5 245 · m6 252 · m9 279
ICC 0.10   m3 264 · m4 284 · m5 310 · m6 330 · m9 396
ICC 0.25   m3 330 · m4 384 · m5 440 · m6 492 · m9 657
```

> **m을 늘려 영상 수를 줄이는 설계는 cluster 의존성에 취약하다.** ICC=0에서는 총 행
> 수가 m과 거의 무관하지만, ICC가 조금만 생기면 **같은 총 질의 수에서도 영상 수 k가 많은
> 설계가 유리해진다.** 따라서 m 선택을 "수집 비용 축"으로만 보면 안 된다.

dev 3편의 영상별 mean Δ가 −0.0418 / −0.0276 / −0.2112로 흩어져 있었다(cluster 3 ·
자유도 2라 추정이 아니다). 장편에서 ICC가 0이라고 볼 근거는 없다.

한계(산출물 `limitations` 8항목 요지):

```
AI Hub 후보 풀은 영상당 12구간, P3는 약 150~400구간 — 절대 half-width 이전 불가
AI Hub arm은 bf16, P3는 양 arm 4bit — 생성 정밀도가 다르다
재사용 표본이다 — 분산 구조 진단으로만 쓰고 P3의 증거로 세지 않는다
도메인·질의 유형 라벨이 다르다 (AI Hub에는 type 라벨이 없다)
정규근사·balanced 가정 — bootstrap percentile CI와 정확히 같지 않다
ICC 훑기는 가정값이고 추정이 아니다
유형별 이질 분산·영상×유형 상호작용·풀 크기 의존성은 이 일원 모형 밖이다
이 표는 P3의 실제 half-width를 예측하지 않는다 — 계획 보조 자료다
```

---

## 11. 승인 상태

**확정됨 (2026-08-24)**

```
경로        P3-A. B/C는 alternative, D/S는 diagnostic only
PRIMARY     Δ_deployment (융합 α=0.5) · MANDATORY KEY SECONDARY Δ_caption (α=0.0)
표본 출처    신규 한국어 long-form fresh collection (AI Hub 재사용분·dev·P2·test와 중복 금지)
seed        사전등록 동결 시 결정론적 고정
δ           P3-C 미선택 — defer
```

**남은 사용자 결정 (실행 전)**

```
0  **최소 deployment-relevant gain / 채택 효용 기준**  ← A보다 먼저다 (§11-1)
A  half-width / precision rule       0.04 / 0.05 / 0.06 중 (§10-2 결론 표를 보고)
B  표본 규모 driver + k × m           §10-3의 A안(PRIMARY 주도) / B안(양쪽 동일) 중 하나
                                     + m 선택은 §10-4 ICC 강건성을 함께 본다
C  라벨 경로                          §9-1 경로 A / B(+amendment) / C
D  P3-A 실행 GO/HOLD
```

이 값들을 이 문서에서 발명하지 않았다.

### 11-1. half-width보다 먼저 답할 질문

> **어느 정도의 deployment gain이면 4B의 추가 운영 비용을 감수하고 교체할 가치가 있는가?**

§10-2가 그 이유를 숫자로 보여준다. 융합 채널의 과거 유사 효과는 **+0.0191**이고, 그것을
CI로 0과 구분하려면 **약 1,500행(영상 300편)**이 필요하다. P2가 175행에서 멈춘 사실을
생각하면 이 규모는 다른 종류의 결정이다.

그래서 P3-A가 답해야 하는 것은 `Δ > 0인가?`만이 아니다.

```
결과에 맞춰 정하면 안 된다 — 추론 전에 운영 기준으로 정한다
δ 형식일 필요는 없다. 다만 채택 결정 문서에는 있어야 한다
기준이 "+0.019급도 가치 있다"면 규모가 1,500행급으로 커진다
기준이 "그 정도면 교체할 가치 없다"면 목표 half-width를 그에 맞춰 크게 잡을 수 있고,
  그때 결론은 "작은 이득은 검출하지 않기로 사전에 정했다"가 된다 — 사후 변명이 아니다
```

이것은 P3-C(비열등성)를 고르는 것과 다르다. P3-C는 δ를 **채택 논리**로 쓰지만, 여기서는
**정밀도 목표를 정하는 근거**로만 쓴다.

### 11-2. 운영비 프로파일 — 결정 0의 입력 (outcome-blind, 새 GPU run 없음)

산출: `scripts/p3_operational_cost.py` → `docs/P3_운영비_2026-08-24.json` (테스트 17건).
**검색 성능을 읽지 않는다** — 읽는 최상위 키는 `provenance` · `i1.len_mean` · `n_segments`
뿐이고 `arms`(MRR)·`per_query`·`contrasts`는 구조적으로 배제한다.

자료는 AI Hub 2×2 full 하나다. 비교 조건 11개 필드가 **전부 일치**했다(GPU RTX 4090 ·
commit `85e47f72` · entrypoint · torch/transformers/python · attn · max_pixels ·
max_new_tokens · rep_penalty · prompt_sha256, 불일치 0).

| arm | s/segment | 총 소요 | 캡션 길이 | 정밀도 |
|---|---|---|---|---|
| 3B/P0 (기준) | **2.817** | 6,558.3s | 131.4자 | bf16 |
| 4B/P0 (후보) | **2.209** | 5,141.5s | 82.0자 | bf16 |

```
후보/기준 = 0.784  → **4B가 구간당 21.6% 빠르다**
길이비    = 0.624  → 캡션이 37.6% 짧다. 생성 토큰이 적어서 빠른 것이므로 함께 읽어야 한다
재캡셔닝 투사  배포 인덱스 2,568구간: 3B 2.01h vs 4B 1.58h
              P2 장편 9,115구간:    3B 7.13h vs 4B 5.59h
```

**즉 "4B는 느려서 비싸다"는 전제는 캡션 생성 처리량에서는 지지되지 않는다.** 다만
**bf16 측정이고 배포는 4bit다** — 양자화가 두 모델에 같은 비율로 작용한다는 보장이 없어
상대 속도가 뒤집힐 수 있다.

**짝 맞춘 측정이 없는 항목 6건** (전부 결정 0에 직접 들어간다):

```
peak VRAM         배포가 6GB 노트북 4bit다. 4B가 들어가는지·여유가 얼마인지가 핵심.
                  부분 자료: 4B 4bit 노트북 3060 peak 3.27GB — **3B 짝이 없다**
4bit throughput   가진 비교는 bf16이다
load overhead     영상당 로드 1회 — 총비용에 직접 더해진다. 부분 자료: 4B 4bit 18.3초
storage delta     가중치·캐시 용량 (/ssd 제약)
OOM/실패          지연과 다른 종류의 비용
재색인 wall-clock  교체는 전 영상 재캡셔닝 + m4를 부른다. 부분 자료: P2 m4 921초
```

P2 FULL(양 arm 4bit, 같은 기기)의 단계 소요는 **모델 비교로 쓸 수 없다** —
`m3_base`(40,988s)는 Whisper STT + 기준 arm 캡션이고 `m3_captions`(28,808s)는 후보 arm
캡션만이다. 단계 의미가 비대칭이라 기준 arm 값(4.496 s/seg)은 **STT를 포함한 상한**이다.

빠진 측정을 위한 프로토콜 `p3_opcost_v1`을 문서로 동결했다 — 라벨 0건 · retrieval outcome
미열람 · 캡션 문자열 미저장(길이·토큰 수만) · 양 arm 동일 4bit · 교대 배치 · 프레임 목록
사전 동결. **실행하지 않았고 사용자 승인 사건이다.**

---

## 12. 채택 게이트 — experiment verdict ≠ deployment adoption

네 가지를 분리한다.

```
experiment verdict        P3 통계 판정
deployment recommendation 판정 + 운영 검토를 합친 권고
deployment adoption       실제 배포 교체
test-opening              test 접촉 승인
```

**P3 결과가 4B 방향이어도 자동 채택하지 않는다.** 채택 전 최소 검토 항목:

```
experiment validity (parity·provenance·arm 완주)
operational readiness (배포 경로에서 재현되는가)
I1 관련 장벽 (§13)
index regeneration implications — 전 영상 재캡셔닝 + m4 재실행 + 확정 인덱스 교체
latency / VRAM / throughput (배포는 6GB 노트북 4bit, 4B bf16은 서버 전제)
test 수치의 유효성 — test 39는 3B 캡션으로 공식 평가됐다. 캡션 모델 교체는 그 수치를
  무효화하고, 재평가는 **별도 test-opening 승인 사건**이다
```

---

## 13. I1 경계

I1 validation은 동결됐고 선택 규칙은 **fallback `R_only(2)`**다. 그것을 배포
recaption trigger나 hard gate로 승격한 것은 아니다.

**P3가 4B 방향이어도 I1 integration을 자동 승인하지 않는다.** 별도 사전등록·사용자
승인 사건이다.

---

## 14. test / M9 절대 경계

```
test 39 재평가              금지
39 → 72 신규 33건 사용       금지 (별도 test-opening 이벤트로 HOLD 상태)
M9 실행                     금지 (split=="test" 하드코딩 — 돌리는 것 자체가 test 접촉)
test-opening 사유 자동 승인   금지
"P2가 HOLD니까 test로 대신 확인"  금지
```

test-opening은 **사용자 명시 승인**이 있어야 하는 별도 사건이다.

---

## 15. 외부 타당성 한계 (지금 적어 둔다)

```
신규 수집을 쓰면      단일 라벨러·단일 도메인 편향. 라벨 경로 이질성(사람/AI초안 혼합)
외부 dataset을 쓰면   언어·도메인·후보 풀 regime 차이. deployment relevance 하향
P3-D를 쓰면          질의 분포가 사용자 질의가 아니다
P3-S를 쓰면          estimand가 장면형 한정. 양수 결과는 일반화 불가
어느 경로든          결과는 "이 표본·이 배포 구성에서"의 진술이다
```

---

## 16. 실행 상태

```
지금 GO   P3-A DRAFT finalization · outcome-blind sensitivity 산출 ·
          labeling-route 제안 · 인프라 보강 · 로컬 테스트/커밋
지금 HOLD  신규 P3 표본 수집 · GT 생성 · 모델 추론 · retrieval/evaluation ·
          P3-D·P3-S 실제 실행 · test/M9 · deployment 변경 · 4B 채택
```

```
P3-A / P3-B / P3-C / P3-D / P3-S   전부 미실행
P3 표본 수집 · GT 생성 · 모델 추론   미실행
3B/4B outcome 비교                  미실행
deployment 변경                     없음
```

**다음 단계는 §11의 남은 결정 4건이다. 승인 전 P3를 실행하지 않는다.**
