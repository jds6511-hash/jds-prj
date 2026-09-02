# Query Abstraction / Expansion — search-research track 설계안 (2026-09-02)

```
Status                PROPOSAL / NOT ADOPTED
Production impact     NONE   (코드·config·인덱스 변경 0)
Experiment authorized NO     (E0 포함 · 실행 전 사전등록 필요)
Test access           NONE   (official test 39 UNOPENED 유지)
GPU used              NONE so far (no new batch, no recaption)
Decision              PREREG_DESIGN_READY
Gate chain            PREREG_DESIGN_READY → 명시적 승인 → E0 실행
```

검토 반영(2026-09-02): blocker 4건(원인 확정 표현 · E0-1 과해석 · E0-3 circularity ·
α 표기)과 보강 6건을 반영했다. 반영 전 판정은 `READY_FOR_E0_PREREGISTRATION`이었다.

이 문서는 **설계와 검증**만 담는다. 코드를 바꾸지 않았고, 인덱스·캡션을 건드리지
않았고, 검색 실험을 돌리지 않았다. v2.1 final acceptance는 E-02~E-05가 남아 있으므로
검색 개선 트랙은 아직 열지 않는다.

---

# A. Repository Facts

전부 이번에 소스·산출물에서 직접 확인했다. 추정한 항목은 "미확인"으로 적었다.

## A-1. 검색 점수 구조

`src/m5_search.py`

```
1  코사인            s_sub = emb_sub @ q      s_cap = emb_cap @ q
2  per-query z-score  zscore(s_sub) · zscore(s_cap)     (단일 영상 범위)
3  정적 치환          s_cap_n[static_mask] = s_sub_n[static_mask]
4  가중합            alpha * s_sub_n + (1 - alpha) * s_cap_n
```

```
채널 수    2 (자막 dense · 캡션 dense)
lexical    없음.  bm25 · rank_bm25 · okapi · tf-idf 어느 것도 소스에 없다(전수 grep)
α          config에 없다. CLI 주입. 확정값은 results/alpha_search_dev.json의 alpha_star
정규화     z-score (minmax에서 2026-07-13 개정)
순위       세그먼트 단위. `np.argsort(-score, kind="stable")`
```

## A-2. static caption replacement — 현재 배포에서 **발동하지 않는다**

```
config.yaml:3        static_threshold: 0
src/deployment.py:19 "static_threshold": 0
src/m5_search.py:118 static_mask = motion_score < static_threshold
```

work/ 전 영상 20편 6,502구간의 motion_score 실측.

```
음수 값            0건 (20편 전부)
정확히 0.0인 영상   2편   jissi_farm(211구간) · wonyi_geoje(327구간)
최솟값 범위        0.0 ~ 0.10491
```

비교는 **strict `<`**이므로 `0.0 < 0`은 False다. 따라서 `static_mask`는 전 영상에서
전부 False이고, 3단계 치환은 **한 번도 실행되지 않는다.**

```
정확한 진술    현재 배포 설정에서 정적 치환은 OFF다.
              최솟값이 "모두 0보다 크다"는 것은 사실이 아니다 — 2편은 정확히 0.0이고,
              `<=`로 바꾸면 그 2편에서 발동한다.
쓰면 안 되는 진술  "새우 검색 실패의 원인은 static replacement다"
              "soft blending λ를 grid search하면 개선된다"   (꺼진 규칙을 튜닝하는 셈)
```

부수 사실: `segments.json`에 저장된 `is_static`은 4편에서 0이 아니다(M2 실행 당시
threshold 산물). M5는 이 저장 필드를 쓰지 않고 메모리에서 재판정하므로 **랭킹에
무영향**이다. 즉 저장 필드와 실효 동작이 다르다 — dead code 성격이고, 정리는 final
acceptance 이후 maintenance 티켓이다.

## A-3. query synonym expansion — 구현돼 있고 기본 off

`src/m5_search.py:124` `expand_query(query, cfg)`

```
사전       cfg["query_synonyms"]  term → [동의어]
현재 상태   config.yaml에 key 자체가 없다 → 사전 {} → variants = [query] → 확장 off
성격       synonym substitution (문자열 치환).  hypernym expansion 아님
실측 근거   초밥 → 스시   rank 21 → 2
          cos(초밥,스시)=0.48 < cos(초밥,김밥)=0.75   (임베딩 동의어 갭)
```

**설계상 중요한 사실 두 개를 새로 확인했다.**

```
(1) 변형 결합은 max pooling이다
    src/m5_search.py:159-160
    s_sub = np.max(video.emb_sub @ qs.T, axis=1)
    s_cap = np.max(video.emb_cap @ qs.T, axis=1)
    정규화 이전 raw 코사인 max. 프로브에서 정규화 이후 풀링(21→10)보다 우세(21→2).
```

→ `query_synonyms`에 상위어를 넣으면 **그 즉시** `max(sim(새우), sim(재료))`가 된다.
즉 우려한 precision collapse 설계가 별도 구현 없이 곧바로 성립한다. 따라서 abstraction은
이 사전에 넣는 방식으로 시험해서는 안 되고, **별도 lane + provenance**로만 다뤄야 한다.

```
(2) 확장은 abstention 임계값과 결합돼 있다
    config.yaml:22  abstention_tau: 0.55  기준 = max(raw_sub_max, raw_cap_max)
    src/m5_search.py:166-167  stats의 raw_*_max는 **풀링 이후** 배열에서 계산된다
```

→ 변형을 늘리면 raw max가 단조 증가하므로 **무관련 질의 경고가 조용히 약해진다.**
랭킹은 불변이지만 저관련 경고 감도는 변한다. query-side 실험은 이 결합을 반드시
같이 측정해야 한다(경고 발생률 전후 비교).

## A-4. α 확정값 — 이번에 실측했다

```
src/deployment.py:23           ALPHA = 0.5      배포 진입점 강제값(alpha_strict)
results/alpha_search_dev.json  alpha_star 0.5   best_point 0.4 · tie_set [0.2, 0.4, 0.5]
                               select_metric mrr · static_threshold 0 · dev 3영상
```

즉 **배포 α = 0.5는 코드와 결과 파일 두 곳에서 확인된다.** 다만 같은 디렉터리의
`results/alpha_search_dev_kure.json`은 `alpha_star 1.0` · tie_set 10개(0.5만 빠짐)를
기록한다. CLAUDE.md가 지정한 확정 출처는 `alpha_search_dev.json`이므로 0.5를 쓰되,
**두 파일의 불일치는 미해결 사항으로 남긴다**(E0와 무관한 별건).

변수 표기는 아래로 고정한다 — `0.5`를 "배포"라고 쓰지 않고 이름으로 부른다.

```
α = 1.0            subtitle isolation
α = 0.0            caption isolation
α = alpha_star     frozen dev-selected / deployed value (현재 실측 0.5)
α = 0.5            diagnostic only — alpha_star와 우연히 같더라도 별개 이름으로 둔다
```

## A-5. 임베딩 / 인덱스 구조

```
모델        nlpai-lab/KURE-v1        dim 1024        (work/*/meta.json 실측)
산출물      emb_sub.npy · emb_cap.npy · meta.json    영상별 디렉터리
표현        float32 · L2 정규화 완료(normalize_embeddings=True) → 내적 = 코사인
정합성 가드  embed_model 불일치 · text_hash 불일치 · n_segments 불일치 → 모두 ValueError
구조체 필드  VideoIndex(segments, emb_sub, emb_cap, static_mask)
```

`objects` 같은 구조화 필드는 **없다.** 캡션은 문장 하나(`caption`), 자막은 `subtitle`
하나다. entity list 필드는 production에 존재하지 않는다.

## A-6. 평가 자원 규모 — **이번에 발견한 제약**

`data/queries/queries.jsonl` 실측.

```
총 135질의     dev 96 · test 39(UNOPENED)
유형          장면형 51 · 복합형 48 · 자막형 36
영상          dev 3편(wilderness 36 · grave 30 · soviet 30)
              test 4편(panibottle 11 · tongyeong 10 · itsub 10 · gemini 8)
평균 어절 수    12.1
2어절 이하 질의  0건
```

세 유형 전부 `"…하는 장면"` 형태의 **긴 서술형 질의**다. 예:

```
장면형  "눈 덮인 설원에서 사람들이 빨간 텐트 안으로 들어가는 장면"
복합형  "몇 번을 놓친 끝에 맨손으로 물고기를 잡아 올려 환호하고 …"
자막형  "빨간 침낭 하나엔 만 달러, 두 개엔 오만 달러를 내라는 제안을 받고 고민하는 장면"
```

**즉 `"새우"` 같은 단일 entity 질의는 라벨된 평가 자원에 한 건도 없다.**

이것이 이 트랙의 최대 제약이다.

```
결과 1  H-QA1(granularity mismatch)은 **현재 dev 96으로 검증할 수 없다.**
       dev 96이 재는 것은 긴 서술형 질의의 성능이다.
결과 2  ENTITY 질의 벤치마크를 만들려면 GT가 필요하고, 새 human GT는 금지다.
       → E0는 GT를 요구하지 않는 characterization으로 설계해야 한다(§E).
결과 3  "새우 → 재료" 사례는 현재 **재현 가능한 실패 사례로 등록돼 있지 않다.**
       사용자 관측이고, 저장소에는 그 질의도 그 판정도 없다.
```

## A-7. 이번에 확인하지 못한 것

```
미확인   "새우" 사례의 원 영상·구간·캡션 원문      search_log.jsonl 미조회(실험 보류 지시)
미확인   dev 캡션의 상위어 일반화 빈도             E0 항목이며 실행하지 않았다
미확인   dev 96의 α별 실패 질의 분해               재실행 없이 결론 못 냄
```

---

# B. Literature Verification

각 논문 원문(arXiv abstract + 본문 HTML)에서 확인했다. **확인하지 못한 항목은
"원문 미확인"으로 적었다.**

## B-1. Dense Retrievers Can Fail on Simple Queries: Revealing The Granularity Dilemma of Embeddings

```
Xu, Su, Yu, Li, Meng, Zhou.  Findings of EMNLP 2025.  arXiv:2506.08592
```

**실제로 보인 것.**

```
CapRetrieval   passage = 이미지 캡션, query = entity/event 개념을 노리는 구
언어           중국어 원본 + GPT-4o 영어 번역판(CapRetrievalEn).  한국어 없음
모델           BGE 0.1/0.3B · GTE 0.1/1.5/7B · E5 0.1/0.3/7B · Conan-v1 0.3B · Qwen3 0.6/8B
규모 결론       "model size is not the principal factor"
              GTE 0.1B이 GTE 1.5B를 앞선다. 7B와의 차이는 7%
BM25 대조       평가했다. 전체로는 dense가 BM25를 최소 10% 앞선다
              그러나 질의 유형별로 갈린다 (Table 3, E=embedding B=BM25)
                  Singleton Entity   E<B 40%    E>B 28%
                  Singleton Event    E<B 25%    E>B 50%
                  Conjunction        E<B 38%    E>B 38%
                  Simple Cond.       E<B 20%    E>B 58%
                  Complex Cond.      E<B  7%    E>B 73%
해결법          학습이다. LLM 생성 학습 질의로 finetune
                  SM(summaries) 전체 saliency · KW(keywords·hypernyms) 정밀 saliency
                  0.1B finetuned가 SOTA 7B를 앞선다
```

**우리 사례와 구조적으로 대응하는 실제 예 (Table 9).**

```
query      西瓜 (watermelon)
무관 passage  과일 바구니에 상추·키위·방울토마토      label 0    sim 0.50
관련 passage  수박을 가득 실은 삼륜차                label 2    sim 0.47
→ 무관 > 관련.  사용자가 말한 그 구조가 원문에 실재한다
```

```
안전한 주장
  fine-grained entity 질의에서 dense 임베딩이 관련 caption보다 무관 caption에
  더 높은 유사도를 주는 사례가 문헌에 실측으로 존재한다.
  encoder family나 model scale을 바꾸는 것만으로 granularity mismatch가 자동
  해결된다고 기대할 근거는 약하다(같은 계열 내 역전이 관측됐다).
  ENTITY 질의에서 lexical signal의 가치가 상대적으로 크다.
과장·오독
  "KURE가 나쁘다"        KURE는 이 논문에서 평가되지 않았다. 한국어 데이터가 없다
  "BM25가 dense보다 낫다"  전체로는 dense가 ≥10% 앞선다. 유형별 역전이다
  "encoder를 바꿔도 차이 없다"  "principal factor가 아니다"와 "차이 없다"는 다르다
  "이 논문이 우리 파이프라인의 실패 원인을 규명했다"  passage가 이미지 캡션인
      retrieval 벤치마크이고, 우리 시스템(2채널 융합·영상 구간)과 설정이 다르다
우리 프로젝트와의 관계
  진단(diagnosis)과 동기(motivation)는 가져온다.
  해결법(encoder finetuning)은 가져오지 않는다 — 현재 원칙이 pretrained embedding
  무학습이고, 학습을 열면 별도 사건이다.
주의   논문의 hypernym은 **생성된 학습 질의** 쪽에 있다. 추론 시점 질의 확장으로
      상위어를 쓰는 것을 이 논문이 입증한 것이 아니다.
```

## B-2. Query2doc: Query Expansion with Large Language Models

```
Wang, Yang, Wei.  EMNLP 2023.  arXiv:2303.07678
```

```
실제로 보인 것
  few-shot LLM으로 pseudo-document 생성 → 원 질의에 덧붙인다
  BM25   MS-MARCO · TREC DL에서 +3% ~ +15%
  dense도 개선된다. 단 **강한 retriever일수록 이득이 줄어든다**
      DPR    TREC DL19 nDCG@10  64.7 → 68.7   (+4.0)
      SimLM                     71.4 → 72.9   (+1.5)
      E5base+KD                 74.3 → 74.9   (+0.6)
  원문 인용: "the gain brought by query2doc tends to diminish when using
      intermediate pre-training or knowledge distillation from cross-encoder re-rankers"
한계(원문 명시)
  지연.  LLM 디코딩 + 확장으로 늘어난 term 수.  index search 16ms → 177ms,
      LLM API >2000ms.  550k 호출 약 $5k
  pseudo-document의 환각
안전한 주장   LLM 생성 pseudo-document 확장은 dense retrieval에서도 이득이 보고됐다.
            다만 retriever가 강해질수록 이득이 축소된다
과장·오독     "query expansion은 항상 성능을 개선한다"
```

## B-3. Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE)

```
Gao, Ma, Lin, Callan.  arXiv:2212.10496
```

```
구조   query → InstructGPT가 hypothetical document 생성 → Contriever로 임베딩
      → corpus dense 검색.  **원 질의 임베딩은 검색에 쓰지 않는다**
원문   생성 문서는 "unreal and may contain false details"이고, encoder의
      dense bottleneck이 잘못된 세부를 걸러 낸다. 사실 근거로 쓰지 않는다
안전한 주장  LLM 생성 표현을 **retrieval pivot**으로 쓰는 설계가 선행연구에 있고,
           그 문서를 evidence로 취급하지 않는 것이 원 논문의 태도다
과장·오독   "HyDE가 생성 문서를 근거로 쓴다"  반대다
우리와의 관계  이 철학은 우리 규율과 정확히 맞는다 —
           LLM 생성 질의 표현 ≠ evidence ≠ caption 수정
주의       원 질의 임베딩을 버리는 설계는 우리에게 위험하다. 우리는 ORIGINAL의
           semantic authority를 가장 높게 두기로 했으므로, 채택하더라도
           "원 질의 대체"가 아니라 "별도 lane"이어야 한다
```

## B-4. Query Expansion by Prompting Large Language Models

```
Jagerman, Zhuang, Qin, Wang, Bendersky.  arXiv:2305.03653
```

```
실제로 보인 것
  retrieval system은 **BM25(Terrier) 단독**이다
  결합식 q' = Concat(q,q,q,q,q, LLM(prompt))   원 질의를 5회 반복해 가중
  MS MARCO  Recall@1K 87.82 → 89.30 (CoT/PRF, Flan-UL2), MRR@10 22.62
한계(원문 명시·직접 인용)
  "First, we only study sparse retrieval (BM25) which is where query expansion is
   important. Dense retrieval systems (e.g. dual encoders) are less prone to the
   vocabulary gap and, as a result, are less likely to benefit from a query expansion."
안전한 주장  이 논문의 결과는 sparse 전제이고, 저자 스스로 dense에서는 이득이
           작을 수 있다고 적었다
과장·오독   "모든 query expansion 연구가 BM25 전제다"  Query2doc은 dense도 다뤘다
우리와의 관계  우리 시스템은 dense 2채널이므로 이 논문은 **기대치를 낮추는 근거**로
           쓴다. 지지 근거로 쓰면 안 된다
```

## B-5. Take a Step Back: Evoking Reasoning via Abstraction in LLMs

```
Zheng et al.  ICLR 2024.  arXiv:2310.06117
```

```
실제로 보인 것
  구체 instance → 상위 개념·원리로 추상화한 뒤 그것으로 추론을 유도한다
  과제  MMLU(Physics·Chemistry) +7%/+11% · TimeQA +27% · MuSiQue +7%
        STEM · Knowledge QA · Multi-Hop
  모델  PaLM-2L · GPT-4 · Llama2-70B
  Knowledge QA·Multi-Hop에서 RAG를 쓴다. 원문: "we use retrieval augmentation (RAG)
        in combination with Step-Back Prompting. The step-back question is used to
        retrieve relevant facts"
  → step-back 질문이 **검색 질의로 쓰이는 것은 사실이다**
  그러나 **검색 품질 자체(recall·nDCG)는 측정하지 않는다.** 지표는 최종 QA 정확도뿐
  오류 분석  "the StepBack rarely fails".  추상화가 특정성을 잃어 해가 된 사례 분석은 없다
안전한 주장  Step-Back의 abstraction operator를 query-side retrieval transformation으로
           **차용**한다. 근거는 조작 정의이고 성능 근거는 아니다
과장·오독   "Step-Back이 video retrieval 개선을 입증했다"   영상은 다루지 않는다
           "Step-Back이 검색 recall을 올린다는 근거가 있다"  검색 지표를 재지 않았다
```

## B-6. GPTSee: Enhancing Moment Retrieval and Highlight Detection via Description-Based Similarity Features

```
Sun, Xu, Xie, Shu, Du.  IEEE Signal Processing Letters.  arXiv:2403.01437
```

```
실제로 보인 것
  MiniGPT-4가 프레임 상세 묘사와 **질의 재작성**을 함께 생성한다
  생성 묘사와 재작성 질의 사이 semantic similarity를 계산하고,
  연속 고유사도 프레임을 span anchor로 바꿔 decoder의 prior position으로 넣는다
  2단계 모델이며 **transformer encoder-decoder 학습이 필요하다**(training-free 아님)
원문 미확인  데이터셋(QVHighlights 등)·수치·질의 재작성 단독 ablation
안전한 주장  LLM 질의 재작성을 video moment retrieval에 쓴 선행 사례가 있다
과장·오독   "GPTSee가 abstraction의 효과를 입증했다"  재작성이며 상위어 추상화가 아니고,
           단독 ablation을 확인하지 못했다
우리와의 관계  "선행 사례 존재" 수준으로만 인용한다. 우리는 학습을 하지 않는다
```

## B-7. GQE / Bridging Information Asymmetry in Text-video Retrieval

```
Bai, Xiao, He, Wang, Zhang, Brox, Shou.  ICLR 2025.  arXiv:2408.07249
(arXiv 초판 제목 "GQE: Generalized Query Expansion for Enhanced Text-Video Retrieval")
```

```
실제로 보인 것
  문제 설정이 우리와 같다 — video는 정보가 풍부하고 text(질의·캡션)는 부분적이다
  학습 시점   영상을 event 단위 clip으로 나눠 zero-shot captioning으로 텍스트를 늘린다
  검색 시점   LLM이 의미적으로 다양한 질의 여러 개를 생성하고,
             **query selection 모듈이 relevance와 diversity로 걸러 낸다**
  MSR-VTT · MSVD · LSMDC · VATEX에서 SOTA 주장
원문 미확인  정확한 수치, 학습 없이 검색 시점 확장만 썼을 때의 이득
안전한 주장  다중 생성 질의를 **무조건 다 쓰지 않고 선별**하는 것이 이 계열의 핵심
           설계다. 우리 lane 설계에도 selection이 필요하다는 근거가 된다
과장·오독   "GQE가 우리 파이프라인에서도 통한다"  학습 시점 개입이 큰 비중이고,
           우리는 재캡셔닝·재학습을 하지 않는다
```

---

# C. Failure Model — `"새우 → 재료"`를 무엇으로 설명하는가

네 가지 후보를 **분리한다.** 복수 원인이고, 층이 다르다.

```
① caption bottleneck  (원인 · 정보 손실)
   시각에 새우가 있는데 생성 캡션이 "재료"로 압축한다.
   손실은 **인덱싱 이전**에 일어난다. 질의 쪽에서 무엇을 해도 복구되지 않는다.
   위치: M3 캡션 생성.  성격: 상위어 대체로 인한 entity 소실

② granularity mismatch (원인 · 표현 정렬)
   질의 "새우"(fine-grained)와 caption "재료를 볶고 있다"(generic)가
   임베딩 공간에서 충분히 가깝지 않다.
   ①이 없어도 발생할 수 있다(캡션에 새우가 있어도 문장 전체 의미가 질의를 압도).
   문헌 근거: B-1

③ dense retrieval salience failure (원인 · 순위 역전)
   ②의 결과로 **무관 구간이 관련 구간보다 높은 점수**를 받는다.
   B-1 Table 9 수박 사례가 이것이다. mismatch가 곧 역전은 아니므로 따로 센다

④ vocabulary gap (부분 원인 · 대부분 아님)
   "초밥 ↔ 스시"처럼 같은 지시 대상의 표기 차이. 이미 expand_query가 다루는 층이고,
   실측 근거도 그 형태였다(21→2).
   "새우 ↔ 재료"는 **표기 차이가 아니다** — 상위어 대체이고, 논리적으로 비대칭이다
```

**가장 그럴듯한 원인 모델 — 실측으로 확인된 1차 원인이 아니다.**

```
Primary upstream hypothesis      ① caption bottleneck
Secondary retrieval hypothesis   ② granularity mismatch → ③ salience failure로 관측된다
Current evidence status          UNVERIFIED ON PROJECT DATA
```

왜 아직 미검증인가 — 이 문서가 앞에서 이미 적은 사실 때문이다.

```
§A-6   ENTITY 질의 GT 0건            이 실패 유형이 라벨된 평가 자원에 없다
§A-6   "새우" 사례 미등록              재현 가능한 실패 사례로 저장소에 없다
§A-7   dev 캡션 일반화 빈도 미측정      ①의 규모를 아직 모른다
```

즉 ①②③의 순위는 **문헌(B-1)과 기전 추론에서 나온 것**이고, 이 저장소 데이터에서
확인된 것이 아니다. E0의 목적은 이 가설과 **일치하는 패턴이 관측되는지**를 보는
것이며, visual-entity ground truth를 세우는 것이 아니다.

배제 근거가 있는 것은 따로 적는다 — 이 둘은 추론이 아니라 실측이다.

```
원인 아님   ④ vocabulary gap             비대칭 상위어 대체다(동의어로 부르면 처방을 틀린다)
원인 아님   static caption replacement   §A-2 — 전 영상에서 발동하지 않는다
```

층이 다르므로 처방도 갈린다.

```
①은 query-side로 회복 불가          → 구조화 캡션 · 시각 채널 (재캡셔닝 사건)
②③은 query-side로 일부 회복 가능    → lexical hybrid · abstraction fallback
```

**비대칭을 보존한다.**

```
새우 → 해산물     category relation으로 성립할 수 있다
해산물 → 새우     성립하지 않는다

따라서 abstraction "재료"로 caption "재료를 볶는다"가 검색됐다는 것은
"새우가 등장한다"는 근거가 아니다. retrieval candidate이고 evidence가 아니다.
```

---

# D. Candidate Architecture 비교

```
후보                    기대 이득       semantic-drift  task-precision  신규 모델   reindex  학습  현 구조 영향                    평가 요구
─────────────────────── ─────────────── ─────────────── ─────────────── ────────── ─────── ──── ────────────────────────────── ─────────────────────
lexical / exact entity  ②③ 직접 완화     LOW             UNKNOWN         모델 NO    불필요   없음  combine_scores에 3번째 항 추가  ENTITY 질의셋 필요
hybrid                  ENTITY 질의 한정  원 term만 매칭   채널 의존적       역할 변경 없음                α 외 가중 1개 = 사전등록 사건   · 오탐 별도 집계
                        B-1 Table 3

query abstraction       ②③ 일부 회복     **HIGH**        **HIGH**        모델 NO    불필요   없음  별도 lane + provenance 필수     ABSTRACT_ONLY
fallback                recall 확대      상위어가 형제     형제 entity가     역할 YES                   query_synonyms에 넣으면 즉시     false positive 필수
                                        entity를 끌어온다  상위에 온다      승인 필요                   max-pooling이 된다(§A-3)       · abstention 감도 전후

descriptive query       ② 질의를 caption  MEDIUM          MEDIUM          모델 NO    불필요   없음  변형 lane. 문장화로 caption      Query2doc식 대조
expansion               분포에 근접       의미 이동                        역할 YES                   분포에 가까워진다               · 지연 측정

HyDE-style              ② 강하게 겨냥    MEDIUM~HIGH     UNKNOWN         모델 NO    불필요   없음  원 질의 임베딩을 버리는 원형은    pivot 대비 원 질의
pseudo-document                         환각 문서                        역할 YES                   우리 규율과 충돌 → 변형 필요      단독 대조 필수

structured objects      ① 근본 해결      LOW             LOW~MEDIUM      VLM 재실행  **필요**  없음  segments 스키마 + M4 재실행     재색인 전후 전면 비교
(recaption)             entity 보존                       캡션 품질 의존    GPU 필요                   인덱스 재생성 = 승인 사건       · 캡션 동일성 가드 재설정

visual retrieval        ① 우회          LOW             UNKNOWN         **필요**   **필요**  없음  3번째 채널. combine_scores 재설계 신규 모델 채택 사건
channel                 캡션 우회                         신규 채널        CLIP/SigLIP                α 구조 자체가 2채널 전제        별도 사전등록
```

두 위험을 **가르는 이유**가 있다.

```
semantic-drift risk   질의의 의미가 바뀌는가
task-precision risk   사용자가 찾던 장면이 상위에 오는가
```

lexical hybrid는 앞쪽이 낮지만 뒤쪽은 **모른다.**

```
자막   "새우는 다음에 넣겠습니다."     exact "새우" hit 있음
화면   양파를 썰고 있다               사용자가 찾던 새우 장면은 아니다
```

그래서 자막 exact와 캡션 exact를 **같은 신호로 합치지 않는다.** 자막 exact는 "언급"의
증거이고 캡션 exact는 "묘사"의 증거이며, 사용자 의도(대개 시각 존재)와의 거리가 다르다.
가중을 하나로 두면 이 차이가 사라진다.

우선순위 판단.

```
가장 직접적   lexical / exact entity hybrid
             학습 없음 · 재색인 없음 · 원 term만 매칭하므로 의미 이동이 없다
             B-1 Table 3(Singleton Entity에서 E<B 40%)이 직접 근거다
가장 위험     query abstraction always-on scoring
             §A-3 (1)에 따라 기존 사전에 넣으면 곧바로 max-pooling이 된다
             "새우" 질의에 "양파를 볶는다"가 올라오는 것이 설계상 예상된다
근본적이나 비쌈  structured objects · visual channel
             둘 다 승인 사건이고, query-side로 얼마나 회복되는지 먼저 봐야 한다
```

## D-1. lane 계약 (채택 시)

```
ORIGINAL     원 질의.  semantic authority 최상
SYNONYM      lexical/semantic 등가.   초밥 ↔ 스시.   현재 query_synonyms
EXPANSION    의미 유지 + 문맥 구체화.  새우 → 새우를 조리하는 장면
ABSTRACTION  상위 개념으로 recall 확대. 새우 → 해산물 → 식재료

SYNONYM ≠ ABSTRACTION.   query_synonyms에 상위어를 넣지 않는다.
```

정책은 **always-on max-pooling이 아니라 progressive backoff**다.

```
Stage A   ORIGINAL + SYNONYM
          ↓ insufficient
Stage B   ABSTRACTION        fallback candidate only
```

`insufficient`를 **사전등록에서 고정한다.** 정의 없이 구현에 들어가면 threshold
tuning이 새 자유 변수로 들어오고, 그것은 §D 전체를 무의미하게 만든다.

가장 보수적인 첫 정의는 **기존 abstention 계약 재사용**이다. 새 임계값을 만들지 않는다.

```
base_score = max( base lane subtitle raw max , base lane caption raw max )
             base lane = ORIGINAL + SYNONYM 뿐   (abstraction 변형은 넣지 않는다)

if base_score < abstention_tau (= 0.55, 기존값):
    abstraction fallback 허용
else:
    base lane 결과만 쓴다
```

순서를 못 박는다.

```
base lane 실행  →  fallback 필요성 판정  →  fallback lane 실행
```

**abstraction 결과를 보고 abstraction을 켤지 결정하지 않는다.** 그러면 사후 선택이 되고,
어떤 질의에 fallback이 쓰였는지가 결과에 의존한다.

첫 실험은 Stage A/B 2단으로 시작한다. EXPANSION은 그 다음이다.

## D-1b. LLM은 "신규 모델 없음"이어도 "신규 역할"이다

```
New model        NO   — 기존 승인된 로컬 모델(Qwen 계열)을 재사용하는 한
New model role   YES  — episode content generation → query interpretation / abstraction
Authorization    REQUIRED
```

같은 artifact라도 **역할이 바뀌면 승인 사건**이다. 그리고 query-side로 LLM을 쓰면
새 공격면이 생긴다 — 사용자 질의가 프롬프트에 들어간다. 사전등록에 아래를 포함한다.

```
user query = untrusted quoted data      질의를 지시로 읽지 않는다
structured output only                  자유 문장 대신 고정 스키마
no instruction following from query      질의 내부 명령 무시
do_sample = False                       결정적 생성
generated abstraction ≠ evidence         §D-2 provenance 규칙 그대로
```

이 항목은 초안에 빠져 있었고 여기서 추가했다.

## D-2. provenance (채택 시)

```
RetrievalTrace(original_query, strategy, transformed_query, rank, score)
strategy ∈ { DIRECT, SYNONYM, EXPANSION, ABSTRACT_ONLY }

ABSTRACT_ONLY의 의미
  허용   "원 query의 상위 개념과 의미적으로 관련되어 fallback candidate로 검색됨"
  금지   "새우가 실제로 있다"
```

이 구분은 v2.1 grounding 규율과 같은 것이다 — `retrieval candidate ≠ evidence`,
`abstraction match ≠ entity verification`.

## D-3. architecture invariant — base abstention을 fallback이 덮지 못한다

§A-3 (2)에서 확인한 결합을 **측정 항목이 아니라 불변식으로** 올린다.

```
Query transformation MUST NOT erase
the confidence state of the original query.
```

변형은 raw 코사인 max를 단조 증가시키므로, 그대로 두면 무관련 질의 경고가 조용히
뒤집힌다.

```
query = 완전히 무관한 질의

DIRECT       raw_max 0.31    base_abstain = True
ABSTRACTION  raw_max 0.61    fallback candidate 발견
→ 이때 abstain = False 로 조용히 뒤집히면 안 된다
```

따라서 네 값을 **분리해서 들고 다닌다.** 하나로 접으면 구분이 사라진다.

```
base_raw_max        base lane(ORIGINAL+SYNONYM)의 raw 최대
fallback_raw_max    fallback lane의 raw 최대
base_abstain        base_raw_max < abstention_tau
fallback_used       fallback lane이 실제로 실행됐는가
```

보고 규칙.

```
base_abstain = true 이고 fallback_used = true 인 결과는
"저관련 질의에 대한 fallback 후보"로 표시된다 — 경고가 사라진 결과가 아니다.
```

v2.1의 `preservation ≠ claim eligibility`와 같은 구조다 — 보존하되 승격시키지 않는다.

---

# E. Recommended First Experiment — E0

제약을 전부 만족하는 가장 작은 실험 하나.

```
official test 사용        없음
caption/index 재생성      없음
encoder 학습             없음
production config 변경    없음
new GPU batch processing 없음
recaption GPU inference  없음
query embedding          기존 encoder(KURE-v1) 추론만 — 환경에 따라 GPU를 쓸 수 있다
범위                     dev 전용 · query-side only + 저장된 캡션 읽기
```

`GPU를 절대 쓰지 않는다`가 요점이 아니다. 요점은 **대규모 재처리가 없다는 것**이다.

## E0 — genericization / cross-channel omission characterization

성능 실험이 아니다. 목적을 정확히 적는다.

> **캡션에서 fine-grained information loss와 일치하는 genericization / cross-channel
> omission 패턴이 얼마나 관측되는가.**

이것은 "캡션이 entity를 얼마나 잃는가"보다 약한 진술이다. 후자는 **시각 진실을 알아야**
말할 수 있고, 우리는 그것을 세울 수 없다(§A-6 · 새 human GT 금지).

```
E0-1  Generic-expression census                GT 불필요 · 임베딩 불필요
      저장된 dev 캡션에서 generic/superordinate 표현 출현률을 센다
      사전(사전등록 시 고정): 재료 · 음식 · 물건 · 사물 · 동물 · 무언가 · 사람 …
      출력: 영상별·구간별 비율

      **주의 — 이 비율은 entity loss rate가 아니다.**
      caption bottleneck의 크기를 직접 추정하지 않는다.
          "새우와 다른 재료를 팬에 볶는다"   generic 있음 · entity 소실 없음
          "팬에서 볶고 있다"                generic 없음 · entity 소실 있음
      즉 이 지표는 genericization indicator prevalence이며 상한도 하한도 아니다.

E0-2  자막-캡션 구체명 누락 대리율               GT 불필요 · 임베딩 불필요
      (subtitle-caption lexical entity omission proxy)
      같은 구간의 자막(ASR)에 나오는 구체 명사가 그 구간 캡션에도 있는가
      출력: 자막에 있고 캡션에 없는 구체명의 비율

      **주의 — visual entity loss를 측정하지 않는다.**
      자막 "아까 새우를 준비했죠." + 화면 "양파를 써는 장면"이 가능하다.
      자막 언급은 시각 존재의 증거가 아니고, 시간 정렬도 보장되지 않는다.

E0-3  채널 비대칭 프로브 (channel-asymmetry probe)
      이름을 낮춘다 — retrieval accuracy 실험이 **아니다.**

      circularity를 먼저 인정한다.
          자막에서 질의를 뽑고 · 그 자막이 있는 구간을 proxy target으로 삼고
          자막 채널로 다시 찾는다 → α=1.0 arm은 self-retrieval 성격이 강하다
      따라서 이 프로브가 재는 것은 하나로 고정한다.
          **동일 entity lexical cue를 caption channel이 subtitle channel보다
            얼마나 덜 보존하는가** (채널 간 비대칭)
      α=1.0 결과는 상한 기준선(self-retrieval)이고 성능 주장에 쓰지 않는다.

      proxy target 정의 — 사전등록에서 고정한다.
          entity가 여러 구간에서 언급되면 단일 target을 두지 않는다.
              새우 → 자막 언급 구간 {EP03, EP04, EP09}
          측정은 set 기준: best rank(=min rank) · set-based Hit@K
          언급 빈도가 높은 entity(예: 5구간 이상)는 **별도 계층으로 분리 보고**한다
          — 흔한 entity는 우연 적중률이 다르므로 한 평균에 섞지 않는다

      arm      α=1.0 subtitle isolation (상한 기준선)
               α=0.0 caption isolation  (관심 대상)
               α=alpha_star (현재 실측 0.5) frozen value
               α=0.5 diagnostic only — alpha_star와 값이 같아도 이름을 분리해 적는다
      부수 측정 필수: abstention 경고 발생률 (§A-3 (2) · §D-3 결합 때문)
```

E0가 답하는 것과 답하지 못하는 것.

```
답한다      generic 표현이 얼마나 흔한가
           자막에 있는 구체명이 캡션에 얼마나 안 남는가
           단어형 entity cue에서 caption 채널이 subtitle 채널보다 얼마나 약한가
답 못 한다   caption bottleneck의 크기(= entity loss rate)
           시각 존재 기준의 recall
           개선안이 효과가 있는가
           dev 96 지표가 올라가는가 (ENTITY 질의는 dev 96에 없다)
```

**E0 이후에야** 개입 실험(S2 lexical hybrid 등)을 설계할 수 있고, 그때는 ENTITY
질의셋 문제를 먼저 해결해야 한다 — 이것이 별도 승인 사건이다.

## 후속 실험 순서 (final acceptance 이후 · 별도 사전등록 필요)

```
S0 BASELINE       original dense                     현행
S1 SYNONYM        + 기존 query_synonyms
S2 LEXICAL HYBRID + exact entity signal              가장 직접적 · 무학습
S3 ABSTRACTION    S2 + abstraction **fallback**      always-on 아님
S4 EXPANSION      S3 + descriptive expansion
S5 ADAPTIVE       query type별 전략 선택
caption/index는 전 구간 동일하게 유지한다
```

## 평가 규율

```
지표     Hit@1 · Hit@5 · MRR
필수 병기  ABSTRACT_ONLY false positive
         (예: "새우" 질의에 "양파를 볶는 장면"이 올라온 건수)
필수 병기  이미 1위인 질의 수 · 남은 여지 · CI 폭         (후보 검증 규약 2)
필수 병기  abstention 경고 발생률 전후                    (§A-3 (2))
채널 격리  캡션 개입이면 α=0.0 단독, 자막 개입이면 α=1.0 단독도 함께 잰다
```

검출 한계를 미리 적는다.

```
dev 96 · 영상 3편에서 CI 폭 ±0.08 (기존 관측)
→ +0.02 ~ +0.03 수준의 평균 개선은 **검출되지 않는다.**
→ 초기 실험은 diagnostic / mechanism test로 정의하고,
  "유의하게 개선되었다"고 쓰지 않는다.
```

## Query Type taxonomy (연구 후보 · 라벨 확대 금지)

```
ENTITY · ACTION · SPEECH · SCENE · COMPOSITE

현재 라벨의 3유형(장면형 51 · 복합형 48 · 자막형 36)과 대응하지 않는다.
새 human GT를 만들지 않는다. 초기에는 deterministic rule 분류
(어절 수 · 종결 형태 · 발화 지시어 유무)나 명백한 diagnostic subset만 검토한다.
```

---

# F. Decision

```
PREREG_DESIGN_READY
```

검토 반영 전 판정은 `READY_FOR_E0_PREREGISTRATION`이었다. blocker 4건을 반영한
지금은 사전등록 초안의 기반으로 쓸 수 있는 상태이고, **그다음은 명시적 승인**이다.

```
PREREG_DESIGN_READY  →  명시적 승인  →  E0 실행
```

근거.

```
설계는 준비됐다      실패 모델이 층별로 분리됐고, 후보가 비용·위험으로 정렬됐다
                  E0가 금지 자원을 하나도 쓰지 않는다
그러나 실행 보류      v2.1 final acceptance에 E-02~E-05가 남아 있다
                  (E-01·E-01a로 ERR 10/10은 닫혔고 미매핑 30건 · P0 18건이 남았다)
그리고 사전등록 필요   §A-6 — ENTITY 질의 GT가 없다. E0의 target은 proxy이고
                  그 사실을 사전등록 문서에 박아야 사후 해석이 흔들리지 않는다
`READY_FOR_QUERY_SIDE_DIAGNOSTIC`이 아닌 이유
                  그것은 지금 실행 가능하다는 뜻이 된다. E-05 이전이고 승인도 없다
남은 blocker 없음   원인 확정 표현 · E0-1 과해석 · E0-3 circularity · α 표기
                  네 건 모두 반영했다(§C · §E · §A-4)
`DO_NOT_OPEN_SEARCH_TRACK_YET`이 아닌 이유
                  트랙 자체는 타당하다. 문헌 근거가 확인됐고 E0는 안전하다
```

## 이 문서가 승인하지 않는 것

```
production search code 수정        static threshold 변경
soft-blending λ tuning            query_synonyms에 hypernym 추가
encoder 교체 · 새 ablation          encoder fine-tuning
CLIP/SigLIP 도입                   recaption · structured objects 생성
index 재생성                       official test 접근 · test 39 재평가
M9                                dead code 정리(final acceptance 이후 별도 티켓)
```

## 금지 해석 (그대로 쓰면 안 되는 문장)

```
Granularity Dilemma가 KURE가 나쁘다는 것을 증명했다        KURE는 평가되지 않았다
BM25가 dense retrieval보다 항상 낫다                     전체로는 dense ≥10% 우세
Step-Back이 video retrieval 개선을 입증했다               영상을 다루지 않는다
새우 → 재료는 새우의 synonym이다                          상위어이며 비대칭이다
abstraction result는 entity 존재 증거다                   candidate이고 evidence가 아니다
query expansion은 항상 성능을 개선한다                     dense에서 축소·무이득 보고 있다
encoder를 바꿔도 절대 차이가 없다                          "principal factor 아님"과 다르다
static replacement가 새우 실패의 원인이다                  발동하지 않는다(§A-2)
caption bottleneck이 1차 원인으로 확인됐다                 가설이다. 미검증(§C)
generic 표현 비율이 entity 소실률이다                      아니다. indicator prevalence다(§E0-1)
자막에 있으면 화면에 있다                                 자막 언급은 시각 존재의 증거가 아니다
```

## 핵심 원칙

```
Query transformation may increase recall.
It must not silently change the meaning of the original query.

retrieval candidate  ≠  evidence
abstraction match    ≠  entity verification
```
