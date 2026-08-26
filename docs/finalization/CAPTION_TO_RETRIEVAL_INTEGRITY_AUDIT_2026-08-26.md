# 캡션→검색 정합성 감사 (2026-08-26)

**AUDIT ONLY.** 장면·질의·캡션·임베딩·인덱스·α·배포·프롬프트를 바꾸지 않았다. 새 metric을
만들지 않았고 Top-1을 재정의하지 않았다. 기존 15질의 순위와 `2/15 vs 2/15`는 그대로다.
test·M9·P2·P3 outcome에 접근하지 않았다. 기계 판독본:
`docs/finalization/caption_to_retrieval_integrity_2026-08-26.json`.

**목적.** `프레임 → target 구간 → 동결 질의 → 3B/4B 캡션 → 임베딩 → 캡션 인덱스 →
검색 순위 → 비-target 1위` 연결이 실제로 정합적인지만 확인한다.

---

## A. 종합 판정

```
integrity                 PASS_WITH_CAVEATS
case-study conclusion     SUPPORTED_WITH_CAVEATS
  "캡션의 정보 선택이 검색 순위로 전달된다"

CRITICAL 후보 5종 전부 통과
  잘못된 프레임          두 arm frame_manifest_sha256 동일 (2759ad9dd6ac86fd…)
  stale 캡션/인덱스      양 arm text_hash == index_text_hash(캡션) 재계산 일치
  query mismatch        frozen_queries_sha256 재현 · 검색 산출물 문구 == plan 문구
  seg_idx 어긋남         0..394 연속·유일 · 행 순서 비트 단위 검증
  arm 간 검색 조건 차이   config 차이가 caption_model·paths 두 개뿐

CRITICAL 0건 · HIGH 0건 · MEDIUM 2건 · LOW 2건 · INFO 4건
```

caveat는 전부 **해석 정밀화**에 해당하고, 결과를 폐기할 사유가 없다.

---

## B. 파이프라인 추적 — 실제 코드 기준

| stage | file · function | input | output | identity key | provenance | mismatch 위험 |
|---|---|---|---|---|---|---|
| 5초 분할 | `m1_preprocess.py` | mp4 | `segments.json` (idx·start·end) | `idx` · `start == idx*5` | `common.load_segments` 불변식 검증 | 낮음 — 로드마다 assert |
| 프레임 선택·추출 | `m2_keyframe.py:110-128` | mp4 | `frames/seg_NNNN.jpg` | 파일명 idx | `motion_score` · `is_static` | **선택 시각 미저장** (LOW-1) |
| VLM 입력 | `m3_generate.caption_frame:229-250` | 프레임 경로 1개 + `caption_prompt` | 캡션 문자열 | — | `prompt_sha256` · `frame_manifest_sha256` | 낮음 — 해시 대조 가능 |
| 캡션 저장 | `common.save_segments` | 캡션 | `segments[].caption` | `idx` | `caption_provenance` | 낮음 |
| 임베딩 | `m4_index.py:47-58` | `[s["caption"] for s in segments]` | `emb_cap.npy` | **행 순서 = segments 순서** | `meta.text_hash` | 낮음 — B-3에서 실측 검증 |
| 인덱스 로드 | `m5_search.VideoIndex.load` | npy + segments | `VideoIndex` | `text_hash` 대조 | ValueError로 차단 | 낮음 |
| 질의 임베딩 | `m4_index.embed_texts` | 질의 문자열 | 1024-d | — | `embed_model` 대조 | 낮음 |
| 점수·정렬 | `m5_search.combine_scores:30-39` | 두 채널 | `α·z(s_sub)+(1−α)·z(s_cap)` | — | α는 CLI 주입, 산출물에 기록 | 낮음 |
| seg_idx·시각 매핑 | `m5_search.search_with_stats:126-129` | 정렬 결과 | `Result(idx,score,start,end)` | `segments[i]` 직접 참조 | — | 낮음 |

### B-1. 5초 구간과 VLM 입력의 관계 (Q1)

**VLM은 5초 구간 전체를 보지 않는다. 구간당 대표 프레임 정확히 1장을 본다.**

```
선택 규칙   3fps 샘플의 인접 프레임 차분 L2 → 가우시안 평활(sigma=1.0) → argmax
            motion_score < static_threshold 이면 중간 프레임 fallback
static_threshold = 0 · motion_score >= 0  →  is_static True 0/395
            즉 이 영상에서 fallback은 한 번도 발동하지 않았고 전건 argmax다
저장        frames/seg_NNNN.jpg 1장 · rep_frame 경로 · motion_score
미저장      선택된 프레임의 실제 시각 (LOW-1)
```

따라서 **"5초 장면을 모델이 설명했다"는 표현은 과하다.** 정확히는
**"5초 구간을 대표하는 프레임 1장의 캡션"**이다. 덱 문안을 그렇게 고쳤다(§I).

### B-2. Scene01~05 프레임 identity

| scene | seg | 구간 | frame | motion_score | is_static | frame sha256(앞 20) |
|---|---|---|---|---|---|---|
| scene01 | 0 | 0~5s | `frames/seg_0000.jpg` | 0.125593 | False | `c60877771caf840823c2` |
| scene02 | 79 | 395~400s | `frames/seg_0079.jpg` | 0.193624 | False | `8bbdda99413c7bf76052` |
| scene03 | 158 | 790~795s | `frames/seg_0158.jpg` | 0.099865 | False | `d87373593df546a8ffd0` |
| scene04 | 237 | 1185~1190s | `frames/seg_0237.jpg` | 0.136834 | False | `1b3c650d5b7d9275e6b3` |
| scene05 | 316 | 1580~1585s | `frames/seg_0316.jpg` | 0.092250 | False | `dfde42309b02c5821b12` |

프레임 27장(논의·발표용 사본)이 양 arm의 캡션 입력 프레임과 **전건 바이트 동일**이다.
장면 선택은 사전등록된 규칙 그대로다 — 구간 인덱스 5등분의 시작 idx(0·79·158·237·316)가
5개 모두 적격이라 전진하지 않았다(`scene_selection_rule.advancement_used: false`).

### B-3. 행 순서 정합성 (Q4) — 신규 임베딩 없이 검증

`m4_index`가 `[s["caption"] for s in doc["segments"]]` 순서로 임베딩하므로 행 N ↔ seg_idx N이
구조적으로 성립한다. 이것을 **기존 artifact만으로 실측 확인**했다.

```
두 arm의 subtitle 텍스트    전건 동일
  → emb_sub 행 비트동일      395/395    (같은 모델·같은 입력·같은 순서)
두 arm의 caption 텍스트     전건 상이 (동일 0건)
  → emb_cap 행 비트동일      0건
"캡션 동일 ⟺ emb_cap 동일"  395/395 일치 · 불일치 행 0
```

행이 하나라도 밀렸다면 이 대응이 깨진다. **매핑 완전.**

---

## C. 질의 감사 (Q2)

15개 동결 질의를 **수정하지 않고**, 각 target 대표 프레임 1장에서 얼마나 직접 관찰
가능한지만 분류했다. **이 분류로 순위·hit를 바꾸지 않는다.**

```
DIRECTLY_VISIBLE   10
WEAKLY_VISIBLE      4
CONTEXTUAL          1
질의 문구 변경        없음 (frozen_queries_sha256 재현)
```

| query | 분류 | 사유 |
|---|---|---|
| s01_q1 기름이 가득한 프라이팬 안의 새우 튀김 | WEAKLY | 팬·기름은 선명하나 **새우가 채널 인트로 로고에 부분 가려짐** |
| s01_q2 새우를 기름에 넣어 튀기는 장면 | WEAKLY | 우상단 손이 다음 조각을 들고 있어 추정은 되지만 "넣는" 순간은 단일 프레임에 없다 |
| s01_q3 주방에서 튀김 요리를 하는 장면 | CONTEXTUAL | 근접 촬영 — "주방"을 흰 타일·조리대에서 유추해야 한다 |
| s02_q1 대형 마트 안에 걸린 파란 광고 배너 | DIRECT | 배너가 화면 상단에 크게 |
| s02_q2 매장 안에서 사람이 지나가는 장면 | WEAKLY | 하단 가장자리 인물이 작게·일부 잘려 있고 "지나가는" 동작은 단일 프레임에 없다 |
| s02_q3 냉장 진열장과 쌓인 상자가 있는 창고형 매장 내부 | DIRECT | 진열장·상자·팔레트 모두 |
| s03_q1 나무 도마 위에 놓인 흰색 재료와 식칼 | DIRECT | 세 요소 선명 |
| s03_q2 칼로 재료를 썰고 있는 손 | DIRECT | 절단 중인 손 |
| s03_q3 주방 조리대에서 재료를 손질하는 사람 | DIRECT | 인물·조리대·식기건조대 |
| s04_q1 노란색 뚜껑이 있는 무쇠 냄비 | DIRECT | 뚜껑·본체 선명 |
| s04_q2 냄비 뚜껑을 손으로 들어 올리는 장면 | DIRECT | 장갑 낀 손이 뚜껑을 든 상태 |
| s04_q3 완성된 조림 요리를 냄비에서 확인하는 장면 | WEAKLY | 요리는 보이나 "완성"·"확인"은 해석 필요 |
| s05_q1 물방울 무늬가 있는 남색 천 | DIRECT | 손에 들려 있음 |
| s05_q2 재봉틀 앞에서 천을 손으로 잡고 있는 장면 | DIRECT | 재봉틀·손·천 |
| s05_q3 작업대 위에 재봉틀과 가위가 놓인 작업 공간 | DIRECT | 좌하단 가위 포함 |

**MEDIUM-1 — Scene01 target 프레임이 채널 인트로 로고로 부분 가려져 있다.**
`seg_0000.jpg`는 영상 0:00~0:05, 즉 인트로 구간이고 화면 중앙에 불투명한
`Plan:D VLOG` 타이틀 로고가 팬 안의 새우를 상당 부분 덮는다. 3B의 seg0 캡션이
`"노란색 그릇에 담긴 노란색 소스 … 작은 크림 요리"`로 완전히 어긋난 것은, 캡션 모델의
서술 선택 문제만이 아니라 **입력 프레임의 가림**도 함께 작용했을 수 있다.
사전등록된 제외 기준(black frame · transition · severe blur · decoding failure ·
정지화면 · 식별 불가)에 **인트로 타이틀 가림이 없었다.** 규칙 위반이 아니라
규칙의 공백이다.

**결과를 바꾸지 않는다** — 장면·질의를 교체하지 않고, Scene01 해석에 이 요인을 병기한다.

---

## D. 3B/4B 생성 조건 동일성 (Q3)

`caption_provenance` 27개 필드 대조.

| 동일 (22) | 값 |
|---|---|
| `frame_manifest_sha256` | `2759ad9dd6ac86fd3fea1e5769bb8a7d945f526aef688a0d7c123223d570645a` |
| `prompt_sha256` | `b7c2598ade97784d74967fc7859e2c32c4cf3c506351c386278ea5673590123b` |
| 양자화 | `config_vlm_4bit: true` · `nf4` · `double_quant: true` · compute `bfloat16` |
| 디코딩 | `max_new_tokens 128` · `rep_penalty 1.1` · `max_pixels 602112` |
| 커널·환경 | `attn sdpa` · `torch 2.12.0+cu130` · `transformers 5.9.0` · `CUDA 13.0` · RTX 3060 Laptop · `python 3.12.10` |
| 그 외 | `entrypoint m3_generate` · `effective_quantized true` · `quantization_mismatch false` |

| 다름 (5) | 3B | 4B |
|---|---|---|
| `caption_model` / `model_id` | Qwen2.5-VL-3B-Instruct | Qwen3-VL-4B-Instruct |
| `model_revision` | `66285546…` | `ebb281ec…` |
| `git_head` | `931b8acc…` | `105857e6…` |
| `generated_at` | 2026-08-25 22:38 | 2026-08-25 23:17 |

**디코딩은 greedy다** — `caption_frame`이 `do_sample=False`로 호출하고 `sample=True`
경로(오염 재시도)는 temperature/top_p를 쓰지만 이번 실행에서 오염 재시도가 걸린 흔적이 없다
(`caption_raw` 0건, 실패·공백 캡션 0건). greedy이므로 seed가 필요 없다. stop 기준은
기본 EOS + `max_new_tokens`.

**git_head 차이는 기존 known limitation이고 재확인했다.** 두 commit 사이 변경은
문서 1건 + 신규 프로브 스크립트 1건이며, 생성 경로 tracked 파일
(`m3_generate.py` · `m4_index.py` · `common.py` · `provenance.py` · `config.yaml` ·
`casestudy_make_config.py`)의 blob이 **양 commit에서 전부 동일**하다
(`caption_retrieval_casestudy_comparability_audit.json`).
`git_dirty`가 양쪽 True인 것은 그대로 남는 한계다 — untracked/미커밋 상태의 동일성은
증명되지 않는다.

**판정: 모델을 제외하면 충분히 비교 가능하다. severity LOW** (dirty tree 미증명 잔존).

---

## E. 캡션 길이 차이의 성질

```
        평균     중앙   최대   최소   종결부호 없이 끝남
3B     128.5자   129   237    13    57건 (14.4%)
4B      76.4자    70   179    22     2건 ( 0.5%)
공유 상한  vlm_max_new_tokens = 128 (양 arm 동일)
```

**절단 증거.** 3B의 미종결 57건은 평균 171.7자로 종결본(121.2자)보다 길고, 길이 180자
이상 41건 중 25건이 미종결이다. 최장 미종결 예 `seg71`(226자)은
`…prepping's done in 5 seconds.'이라는 자막이 나타` + **멀티바이트 문자가 중간에서
끊긴 상태**로 끝난다. 문체가 아니라 토큰 상한 도달이다. 4B는 최대 179자로 상한에
닿지 않는다.

**분류: B(max token truncation)가 3B 상단 꼬리에 실재한다.** 동시에 4B의 중앙값 70자는
어떤 상한과도 무관하므로, 차이 전체가 절단으로 설명되지는 않는다. 후처리는
발동하지 않았다(`caption_normalize_cjk`·`caption_truncate_incomplete` 모두 false,
`caption_raw` 0건).

```
허용   observed captions were shorter under the 4B run and longer under the 3B run;
      3B의 상단 꼬리는 공유 토큰 상한에 눌렸다
금지   4B intrinsically produces shorter captions
```

**INFO-1.** 128 토큰 상한은 현행 3B로 튜닝된 값이고, 이번 실행에서 상한에 닿은 쪽은
3B다. 즉 이 설정은 **현행 모델에게 불리하게** 작동했다. CLAUDE.md 후보 검증 규약 3
("현행 전용 설정 재탐색")이 가리키는 항목이며, 재탐색은 이번 감사 범위 밖이다.

**INFO-2.** 절단으로 깨진 멀티바이트 문자가 인덱스에 들어가 있다. `is_corrupted_caption`은
한자·가나 기준이라 이 유형을 flag하지 않는다. 기록만 한다(LIMITATIONS 11번과 같은 성질).

---

## F. 검색 조건 동일성 (Q5)

```
질의 문구        동일 (한 코드 경로에서 arm 루프)
KURE 모델        nlpai-lab/KURE-v1  양 arm 동일
질의 임베딩 절차   embed_texts 동일 · query_synonyms None → expand_query가 [query] 단일
후보 풀          395 · n_ranked 30개 (query×arm) 전부 395
alpha            0.0
자막 기여         0  (α=0 가중치 + static_threshold=0 이라 정적 치환 미발동)
정규화           per-query z-score, 양 채널 동일
정렬             np.argsort(-score, kind="stable")
tie-break        stable sort의 인덱스 순 — arm 무관
top_k 기록        3
후보 필터·제외     없음
config 차이       caption_model · paths 두 개뿐 (KEEP_IDENTICAL assert로 보장)
```

**동일하다.** 두 arm의 차이는 인덱스 내용(캡션)뿐이다.

---

## G. 비-target 1위 분류 (Q6)

target이 1위였던 쌍 4건(3B 2 · 4B 2)을 제외한 **26쌍 전수** 분류.
`SAME_EVENT_ADJACENT` 정의는 `|Δseg| ≤ 3` 이고 같은 연속 동작.

```
SAME_EVENT_NONADJACENT           9    같은 요리·작업의 다른 시점
SEMANTICALLY_RELATED_DISTRACTOR  8    관련 의미의 다른 사건
SAME_ACTION_DIFFERENT_OBJECT     5    같은 동작·다른 대상
SAME_EVENT_ADJACENT              4    Δ ≤ 3구간, 사실상 같은 순간
UNRELATED                        0
─────────────────────────────────────
secondary
TEXT_LEAKAGE_CANDIDATE           2    3B s01_q1 · s01_q2 (seg188 편집 자막 전사)
IN_SCENE_TEXT_SELECTION          2    3B s02_q2 'Easy Wash Plus' · 4B s02_q1 'KIRKLAN'
```

**핵심: UNRELATED 0건이다.** 26건 전부 같은 사건·같은 동작·의미 근접이다. 검색기가
무관한 장면을 올린 사례가 없다 — 이것이 `SUPPORTED_WITH_CAVEATS`의 근거이자
"오답" 표현을 완화한 근거다(§H).

| scene | arm | rank | top1 | Δseg | primary | secondary |
|---|---|---|---|---|---|---|
| s01_q1 | 3B | 30 | seg188 (15:40) | +188 | SAME_EVENT_NONADJACENT | TEXT_LEAKAGE_CANDIDATE |
| s01_q1 | 4B | 3 | seg188 (15:40) | +188 | SAME_EVENT_NONADJACENT | — |
| s01_q2 | 3B | 31 | seg188 (15:40) | +188 | SAME_EVENT_NONADJACENT | TEXT_LEAKAGE_CANDIDATE |
| s01_q2 | 4B | **1** | seg0 | 0 | target 1위 | — |
| s01_q3 | 3B | 31 | seg189 (15:45) | +189 | SAME_EVENT_NONADJACENT | — |
| s01_q3 | 4B | 25 | seg175 (14:35) | +175 | SEMANTICALLY_RELATED_DISTRACTOR | — |
| s02_q1 | 3B | **1** | seg79 | 0 | target 1위 | — |
| s02_q1 | 4B | 15 | seg90 (7:30) | +11 | SEMANTICALLY_RELATED_DISTRACTOR | IN_SCENE_TEXT_SELECTION |
| s02_q2 | 3B | 46 | seg76 (6:20) | −3 | SAME_EVENT_ADJACENT | IN_SCENE_TEXT_SELECTION |
| s02_q2 | 4B | 2 | seg77 (6:25) | −2 | SAME_EVENT_ADJACENT | — |
| s02_q3 | 3B | 18 | seg80 (6:40) | +1 | SAME_EVENT_ADJACENT | — |
| s02_q3 | 4B | **1** | seg79 | 0 | target 1위 | — |
| s03_q1 | 3B | 59 | seg219 (18:15) | +61 | SAME_ACTION_DIFFERENT_OBJECT | — |
| s03_q1 | 4B | 40 | seg382 (31:50) | +224 | SEMANTICALLY_RELATED_DISTRACTOR | — |
| s03_q2 | 3B | 52 | seg287 (23:55) | +129 | SAME_ACTION_DIFFERENT_OBJECT | — |
| s03_q2 | 4B | 20 | seg353 (29:25) | +195 | SAME_ACTION_DIFFERENT_OBJECT | — |
| s03_q3 | 3B | 34 | seg21 (1:45) | −137 | SEMANTICALLY_RELATED_DISTRACTOR | — |
| s03_q3 | 4B | 170 | seg175 (14:35) | +17 | SEMANTICALLY_RELATED_DISTRACTOR | — |
| s04_q1 | 3B | **1** | seg237 | 0 | target 1위 | — |
| s04_q1 | 4B | 3 | seg193 (16:05) | −44 | SEMANTICALLY_RELATED_DISTRACTOR | — |
| s04_q2 | 3B | 3 | seg28 (2:20) | −209 | SAME_ACTION_DIFFERENT_OBJECT | — |
| s04_q2 | 4B | 10 | seg115 (9:35) | −122 | SAME_ACTION_DIFFERENT_OBJECT | — |
| s04_q3 | 3B | 5 | seg235 (19:35) | −2 | SAME_EVENT_ADJACENT | — |
| s04_q3 | 4B | 3 | seg175 (14:35) | −62 | SEMANTICALLY_RELATED_DISTRACTOR | — |
| s05_q1 | 3B | 181 | seg372 (31:00) | +56 | SEMANTICALLY_RELATED_DISTRACTOR | — |
| s05_q1 | 4B | 22 | seg342 (28:30) | +26 | SAME_EVENT_NONADJACENT | — |
| s05_q2 | 3B | 148 | seg280 (23:20) | −36 | SAME_EVENT_NONADJACENT | — |
| s05_q2 | 4B | 9 | seg303 (25:15) | −13 | SAME_EVENT_NONADJACENT | — |
| s05_q3 | 3B | 175 | seg278 (23:10) | −38 | SAME_EVENT_NONADJACENT | — |
| s05_q3 | 4B | 34 | seg311 (25:55) | −5 | SAME_EVENT_NONADJACENT | — |

**MEDIUM-2 — Scene05의 두 arm 격차가 "동일 대상 다른 시점"으로 상당 부분 설명된다.**
4B의 1위 3건(seg342 · seg303 · seg311)은 전부 같은 재봉 작업의 인접~근접 시점이고,
seg303은 캡션이 `"점무늬가 있는 천 조각"`으로 target과 사실상 같은 천이다. 즉 4B가
`22 · 9 · 34위`인 것은 "정답을 놓쳤다"보다 **같은 천을 다룬 이웃 구간들이 target보다
앞섰다**에 가깝다. 반대로 3B는 target을 `"티셔츠"·"수영장"`으로 적어 `148~181위`다.
**strict target 기준 순위는 그대로 두되, 격차 해석에 이 구조를 병기해야 한다.**

### G-1. 오인 vs 환각 (§21)

Scene05 3B 캡션의 `"수영장"`·`"티셔츠"`를 프레임과 대조했다. 프레임에는 넓고 밝은
흰색 작업대 면과 반사광이 있고, 천은 남색 바탕에 회색 점무늬로 무늬 있는 상의로
오독될 여지가 있다. 같은 캡션의 `"커터가 놓여 있습니다"`는 좌하단 가위와 **맞다.**
따라서 근거 없는 생성이 아니라 **실제 시각 요소의 오해석**이다.

```
판정   MISRECOGNITION (오인) — HALLUCINATION 아님
덱 표현  "오인" 사용 중 · "환각" 표현 없음 (전수 검색 0건) → 수정 불필요
```

---

## H. 텍스트 처리 감사 연계 (§11)

`docs/finalization/CAPTION_TEXT_HANDLING_AUDIT_2026-08-26.md` 결과를 그대로 잇는다.

```
STT subtitle          α=0에서 점수 가중치 0 · 정적 치환 미발동 → 기여 0
editorial overlay     프롬프트 지시만 · 픽셀 제거 없음 → 캡션 채널로 유입 가능
in-scene text         의도상 허용 · 현행 P0 문구는 overlay와 구분하지 않음 (MISMATCH)
OCR/전사              문구상 전면 금지 · 강제력 없음 · 부분 완화
일반 시각 정보          포함

Scene01 seg188        overlay leakage candidate  (한/영 번역 병기 자막 축자 전사)
Scene02 seg79         in-scene text              (냉장창고 벽면 부착 비닐 배너)
```

**두 사례를 같은 failure mode로 묶지 않는다.** §G 표에서도 전자는
`TEXT_LEAKAGE_CANDIDATE`, 후자는 `IN_SCENE_TEXT_SELECTION`으로 분리했다.

`α=0`이 의미하는 것은 **"자막 검색 채널의 점수 가중치가 0"** 이고,
**"영상 프레임에 보이는 편집 자막 정보가 제거됨"이 아니다.**

---

## I. 실패 경로 분류 재검증 (§20)

증거가 있는 항목만 붙였다. 무리하게 채우지 않았다.

| category | 해당 | 증거 |
|---|---|---|
| KEY_INFO_OMISSION | s01 (3B) | target 캡션에 팬·기름·새우·튀기다 전무 |
| ELEMENT_SELECTION_DIFFERENCE | s02 | 같은 프레임에서 3B 배너 / 4B 진열대 |
| CONTEXT_OMISSION | s03 (4B q3) | 짧은 캡션에 주방·조리대 배경어 없음 |
| DIRECT_EXPRESSION_IN_DISTRACTOR | s01 · s04 | s04_q2 4B top1 `"뚜껑을 들어 올리는"` 축자 겹침 |
| VISUAL_MISRECOGNITION | s04 (4B, 냄비→주전자) · s05 (3B) | 프레임 대조로 오인 확인 |
| HALLUCINATION | 해당 없음 | s05도 오인으로 판정 (§G-1) |
| OVERLAY_SUBTITLE_LEAKAGE | s01 (3B seg188) | 한/영 번역 병기 자막 축자 전사 |
| IN_SCENE_TEXT_SELECTION | s02 (3B seg79 · 3B seg76) · s02 (4B seg90) | 배너·포장·로고 |
| REPEATED_ACTION_AMBIGUITY | s03 · s04 | "칼로 썬다"·"뚜껑을 든다"가 영상에 다수 존재, top1이 그 안에서 갈림 |
| SEGMENT_BOUNDARY_AMBIGUITY | s02_q3 (3B Δ+1) · s04_q3 (3B Δ−2) · s02_q2 (Δ−2·−3) | 인접 구간이 1위 |

**신규: `REPEATED_ACTION_AMBIGUITY`와 `SEGMENT_BOUNDARY_AMBIGUITY`가 실재한다.**
기존 덱의 5경로(+편집 자막 1개)로는 이 둘이 명시되지 않았다. 덱의 경로 ④
"다른 장면의 더 직접적인 표현"이 부분적으로 덮지만 동일하지 않다. 다만 §23에 따라
덱에 새 숫자를 넣지 않고, 경계 슬라이드에 무관 장면이 없었다는 정성 문장만 추가했다.

---

## J. 발견 목록 (severity)

```
CRITICAL   0건

HIGH       0건

MEDIUM-1   Scene01 target 프레임(seg0)이 채널 인트로 로고로 부분 가려져 있다.
           3B의 seg0 오서술 해석에 이 요인을 병기해야 한다.
           사전등록 제외 기준에 인트로 가림 항목이 없었다(규칙 공백).
MEDIUM-2   Scene05의 arm 격차가 "같은 천을 다룬 이웃 구간이 앞섰다"로 상당 부분
           설명된다. strict target 순위는 유지하되 해석에 병기.

LOW-1      M2가 선택된 프레임의 실제 시각을 저장하지 않는다(rep_frame 경로·motion_score만).
           규칙은 재현 가능하나 timestamp를 사후 대조할 수 없다.
LOW-2      두 arm 모두 git_dirty=True다. tracked 생성 경로 파일은 blob 동일까지
           확인됐으나 미커밋 상태의 동일성은 증명되지 않는다(기존 한계 재확인).

INFO-1     공유 max_new_tokens=128에 닿은 쪽은 3B다 — 현행 모델에게 불리하게 작동했다.
INFO-2     절단으로 깨진 멀티바이트 문자가 인덱스에 있다. is_corrupted_caption은
           이 유형을 flag하지 않는다.
INFO-3     덱 Scene01 밴드가 "31위"만 적어 Q2·Q3 중 어느 질의인지 모호했다 → Q2 명시.
INFO-4     REPEATED_ACTION_AMBIGUITY · SEGMENT_BOUNDARY_AMBIGUITY가 실재하나
           기존 경로 목록에 명시돼 있지 않다.
```

---

## K. 문서·PPT 정합성 (§24 · §25)

전수 검색 결과와 조치.

| 확인 표현 | 상태 |
|---|---|
| "5초 장면을 설명" | 덱에 없었다. 슬라이드 5는 이미 `"같은 프레임 한 장을 두 모델이 이렇게 설명했다"`. **보강**: 슬라이드 3에 `"캡션은 5초 구간의 대표 프레임 1장에서 생성된다 — 모델이 구간 전체를 보지 않는다"` 추가 |
| "자막을 제거" | 없다. `"자막 검색 채널을 끄고"`로 이미 정정됨(2026-08-26) |
| "오답" | 3곳 → **완화**. 슬라이드 4 제목·⑥·슬라이드 14를 `"내가 고른 장면 / 1위 장면 / 1위가 된 다른 장면"`으로 |
| "환각" | 덱 전수 0건. §G-1대로 "오인"이 정확 → 조치 없음 |
| "4B가 더 좋음" | `"말할 수 없다"` 목록에만 존재(부정문). 숫자 슬라이드는 `"내가 고른 장면의 순위가 더 높았던 질문"`으로 이미 §22 권고 문구. 승/패 표현 0건 → 조치 없음 |
| "caption-only" | 의미 정정 완료(§H) |
| "배너 글자 금지" | 제거 완료(2026-08-26) |
| README `M2 대표 프레임` | 정확 → 조치 없음 |
| SOURCE_PACK `M2 구간 대표 프레임` | 정확 → 조치 없음 |

덱 변경 4건 + 1건 추가. **순위·질의·캡션 원문은 변경 없음**(테스트로 고정, §L).

---

## L. 추가한 guard (§28)

`tests/test_casestudy_integrity.py` — 18건. 연구 지표를 재계산하지 않고 동일성만 본다.

```
동결 identity   scene 5 · query 15 · frozen_queries_sha256 재현 · frozen_scenes_sha256 재현
               검색 산출물 query 문구·target_segment == plan
검색 조건       alpha 0.0 · alpha_sweep False · n_ranked 전건 395 · pool 395
               arm config 차이가 {caption_model, paths} 정확히 두 개
캡션·인덱스      arm별 395건 · 공백 0 · seg_idx 0..394 연속 · start==idx*5
               meta.text_hash == index_text_hash(캡션)  ← stale 인덱스 차단
               emb (395,1024) × 2
행 순서         emb_sub 두 arm 비트동일 + "캡션 동일 ⟺ emb_cap 동일" 전건
생성 입력       frame_manifest_sha256 두 arm 동일 · prompt_sha256 == config 해시
               디코딩·환경 12개 필드 arm 간 동일
프레임          논의용 27장 == 캡션 입력 프레임 바이트 동일
덱 ↔ 산출물     전체표 15행 순위가 step6와 일치 · top1 적중 {3b:2, 4b:2} 일치
```

---

## M. 최종 답 (Q1~Q8)

```
Q1  5초 구간과 VLM 입력의 관계
    구간당 대표 프레임 정확히 1장. 3fps 샘플 차분 argmax(평활 sigma=1.0),
    static fallback은 이 영상에서 0회. 구간 전체를 보지 않는다.

Q2  15질의가 target 대표 프레임에서 직접 관찰 가능한가
    부분적으로만. DIRECTLY 10 · WEAKLY 4 · CONTEXTUAL 1.
    Scene01은 인트로 로고 가림까지 겹친다(MEDIUM-1).

Q3  3B/4B 생성 조건이 모델 외에 비교 가능한가
    가능하다. 프레임 해시·프롬프트 해시·양자화·디코딩·라이브러리·GPU 동일.
    잔존 한계는 git_dirty 양쪽 True(LOW-2).

Q4  caption→embedding→index→seg_idx 매핑이 완전한가
    완전하다. text_hash 일치 · seg_idx 연속 · 행 순서 비트 단위 검증.

Q5  3B/4B 검색 조건이 동일한가
    동일하다. config 차이가 caption_model·paths 두 개뿐.

Q6  비-target 1위는 어떤 종류인가
    SAME_EVENT_NONADJACENT 9 · SEMANTICALLY_RELATED_DISTRACTOR 8 ·
    SAME_ACTION_DIFFERENT_OBJECT 5 · SAME_EVENT_ADJACENT 4 · UNRELATED 0.
    부가로 TEXT_LEAKAGE_CANDIDATE 2 · IN_SCENE_TEXT_SELECTION 2.

Q7  덱의 "오답 / 환각 / 자막 제거" 표현이 정확한가
    "환각"은 애초에 없었고 "오인"이 정확하다. "자막 제거"는 이미 "자막 검색 채널"로
    정정됐다. "오답"은 과했다 — UNRELATED 0건이므로 "1위가 된 다른 장면"으로 완화했다.

Q8  "캡션의 정보 선택이 검색 순위로 전달된다"를 유지해도 되는가
    SUPPORTED_WITH_CAVEATS.
    근거: 프레임·프롬프트·디코딩·검색 조건이 동일하고 인덱스가 stale이 아니므로
          두 arm 순위 차이의 원인은 캡션 내용 차이로 좁혀진다(Scene02가 같은
          프레임에서 요소 선택만 달라 1위가 뒤집힌 직접 증거).
    caveat: ① 정성 사례 연구다(영상 1편·질의 15개). ② 비-target 1위가 전부 근접
            사례이므로 "찾지 못했다"보다 "이웃·유사 구간이 앞섰다"에 가깝다.
            ③ Scene01은 프레임 가림과 편집 자막 유입이 함께 걸려 있다.
            ④ 3B 상단 꼬리는 공유 토큰 상한에 눌렸다.
```

---

## N. 경계

```
new experiment          NO      new metric              NO
recaption               NO      reindex                 NO
new embedding           NO      prompt changed          NO
deployment changed      NO      alpha changed           NO
scene/query changed     NO      Top-1 redefined         NO
±1 segment accepted     NO      detector implemented    NO
test/M9 accessed        NO      P2/P3 accessed          NO
frozen artifact changed NO      metrics recomputed      NO
```

변경한 것은 감사 문서 2건, 활성 덱 문안 5건, 테스트 1파일이다.

## O. 결정 필요

```
NONE
```

사용자 결정이 필요한 항목은 없다. MEDIUM 2건은 해석 병기로 처리했고, LOW·INFO는
기록으로 남겼다. 케이스 스터디 쪽은 이 감사로 닫는다.
