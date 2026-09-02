# BloomIntent-inspired Semantic Highlight Grouping Design

```
Status                PROPOSAL / NOT ADOPTED
Production impact     NONE
Experiment authorized NO
Test access           NONE   (official test 39 UNOPENED)
Adopted into v2.1     NO
```

이 문서는 연구 제안이다. v2.1 production path에 도입되지 않았고, 실험도 승인되지
않았다. 채택은 별도 사전등록·승인 사건이다.

---

## 1. 문서 목적

이 문서는 현재 v2.1의 canonical 구조를 변경하지 않고, 향후 post-v2.1 / v2.2 연구 트랙에서 사람이 읽기 좋은 Highlight를 자동으로 제안하기 위한 `HighlightGroupingPolicy` 설계안을 기록한다.

핵심 원칙:

> 사건의 정답 경계를 다시 찾는 것이 아니라, 이미 검증된 Canonical Episode들을 presentation 목적에 맞게 의미적으로 묶는 proposal을 만든다.

본 설계는 현재 v2.1 production path에 즉시 도입하지 않는다. v2.1 final acceptance 완료 후 별도 research track으로 검토한다.

---

## 2. 문제 정의

현재 v2.1에서는 canonical temporal structure를 deterministic하게 만든다.

```text
Video
→ canonical segments
→ fixed_window_v1
→ Canonical Episodes
```

예:

```text
EP01  0~60
EP02  60~120
EP03  120~180
EP04  180~240
```

이 구조의 invariant:

```text
overlap = 0
gap = 0
exactly once
deterministic
model independent
```

그러나 사람이 읽는 보고서에서는 다음처럼 더 큰 의미 단위가 필요할 수 있다.

```text
Highlight 1 = EP01 + EP02 + EP03
Highlight 2 = EP04 + EP05
```

현재 C-02 Highlight Builder는 이런 grouping을 실행할 수 있지만, 무엇을 묶을지는 자동으로 결정하지 않는다. 따라서 별도의 presentation-only grouping policy가 필요하다.

---

## 3. 왜 canonical boundary detector로 만들지 않는가

과거 C0에서는 다음 접근을 시도했다.

```text
VLM caption
→ caption text embedding
→ adjacent embedding distance
→ local peak
→ change-point
```

하지만 실제 관측에서는 다음 문제가 있었다.

```text
embedding 변화
=
실제 사건 변화일 수도 있음
caption 표현 변화일 수도 있음
caption 오류일 수도 있음
정보량 변화일 수도 있음
```

따라서 다음 방향은 피한다.

```text
embedding
→ canonical boundary
```

대신 임베딩을 더 안전한 위치로 옮긴다.

```text
aar_canonical
→ presentation-eligible episode summaries
→ embedding
→ Highlight grouping proposal
```

이 경우 grouping이 부정확해도 canonical boundary, episode identity, grounding, evidence provenance, aar_canonical은 변하지 않는다.

---

## 4. BloomIntent에서 차용하는 핵심 아이디어

```text
Fine-grained units
→ semantic representation
→ agglomerative clustering
→ higher-level groups
→ human-readable interpretation
```

영상 시스템에서는 이를 다음처럼 변형한다.

```text
Canonical Episodes
→ grounded summaries
→ summary embeddings
→ temporal-constrained agglomerative clustering
→ Highlight Grouping Proposal
→ C-02 Highlight Builder
→ report
```

중요한 차이:

- 검색 intent에는 시간축이 없다.
- 영상 episode에는 시간 순서가 있다.
- 따라서 일반 clustering을 그대로 쓰지 않는다.
- 오직 시간적으로 인접한 cluster끼리만 merge할 수 있게 제한한다.

---

## 5. 권장 모듈명

권장:

```text
SemanticHighlightGrouping_v1
```

또는:

```text
HighlightGroupingPolicy_v1
```

권장하지 않음:

```text
EventDetector
GroundTruthEventBoundaryDetector
CanonicalBoundaryFinder
```

이 설계의 결과는 `presentation용 semantic grouping proposal`이다.

---

## 6. 입력 계약

입력은 C-01의 `PresentationInput`으로 제한한다.

```python
group_highlights(
    presentation_input: PresentationInput,
) -> GroupingProposal
```

사용 가능한 정보:

```text
episode_id
start_sec
end_sec
summary
content_status
grounding_status
presentation eligibility
```

접근 금지:

```text
raw
raw_store
ASR raw
VLM raw
OCR raw
parse result
evidence timeline
binding
pre-grounding EpisodeContent
dialogue_note
stt_cites
```

OPEN-11 containment boundary를 그대로 유지한다.

---

## 7. 임베딩 대상

임베딩 대상은 raw caption이 아니라 presentation-eligible canonical episode summary로 한다.

```text
VLM / ASR / OCR
→ sanitation
→ Episode Content
→ binding
→ grounding
→ aar_canonical
→ presentation eligibility
→ canonical episode summary
→ embedding
→ Highlight proposal
```

---

## 8. Presentation Summary Eligibility 재사용

새로운 eligibility rule을 만들지 않는다.

```text
content_status == VALID_PARSE
AND summary exists
AND grounding_status in {PASS, NOT_APPLICABLE}
```

즉:

```text
PASS + summary               사용 가능
NOT_APPLICABLE + summary     사용 가능
FAIL_* + summary             grouping signal로 사용 금지
PENDING / UNKNOWN / SKIPPED  사용 금지
empty summary                사용 금지
parse failure                사용 금지
```

`summary 사용 가능 == grounding PASS`라는 뜻은 아니다.

---

## 9. Episode Semantic Unit

```python
@dataclass(frozen=True)
class EpisodeSemanticUnit:
    episode_id: str
    start_sec: float
    end_sec: float
    text: str
    embedding: tuple[float, ...]
```

추가 metadata 후보:

```text
grounding_status
content_status
summary_hash
embedding_model_id
```

raw evidence handle은 넣지 않는다.

---

## 10. 핵심 알고리즘: Temporal-Constrained Agglomerative Clustering

### 10.1 초기 상태

```text
[EP01] [EP02] [EP03] [EP04] [EP05]
```

### 10.2 시간 제약

허용:

```text
[EP01] + [EP02]
[EP02] + [EP03]
```

금지:

```text
[EP01] + [EP04]
```

한 번 merge되면:

```text
[EP01] [EP02 EP03] [EP04] [EP05]
```

다음 후보는 인접 cluster 조합뿐이다.

이 제약으로 결과 highlight는 항상 temporal contiguous group이 된다.

---

## 11. Similarity

v1 baseline:

```text
canonical episode summary
→ text embedding
→ cosine similarity
```

예:

```text
EP01 "창고 문을 연다."
EP02 "창고 안으로 들어간다."
EP03 "상자를 옮긴다."
EP04 "자동차를 운전한다."
EP05 "식당에 들어간다."
```

가능한 결과:

```text
[EP01 EP02 EP03]
[EP04]
[EP05]
```

이 결과는 semantic event ground truth가 아니라 presentation grouping proposal이다.

---

## 12. Cluster Similarity 계산

v1 권장:

```text
cluster_embedding
=
mean(member episode embeddings)
```

그리고 인접 cluster 간 cosine similarity를 계산한다.

---

## 13. Cluster Count 선택

특정 Highlight 개수를 목표값으로 두지 않는다.

금지:

```text
target_count = 9
target_count = human_reference_rows
max_highlights = fixed reference count
```

대신 hierarchy를 여러 cluster 수에서 평가한다.

```text
k = N
k = N-1
...
k = 1
```

각 단계에서 within-cluster dispersion / semantic cohesion / merge cost를 계산하고 deterministic elbow/knee rule을 적용한다.

영상마다 결과 개수는 달라질 수 있다.

```text
video A → 3 highlights
video B → 7 highlights
video C → 12 highlights
```

---

## 14. Tie 처리

두 cluster count가 거의 동등하다면 더 적게 merge하는 쪽을 우선한다.

```text
4 highlights vs 5 highlights
→ 5 highlights 선택
```

이유:

```text
over-merge
→ 서로 다른 사건을 하나의 사건처럼 보이게 할 위험

under-merge
→ 같은 사건이 여러 highlight로 나뉠 뿐
```

현재 시스템 철학에서는 under-merge가 더 안전하다.

---

## 15. Reliable Summary가 없는 Episode

예:

```text
EP01 summary 있음
EP02 summary 없음
EP03 summary 있음
```

EP02를 건너뛰고 EP01 ↔ EP03를 직접 비교하지 않는다.

권장 정책:

```text
EP02 = semantic unknown singleton barrier
```

즉 자동으로 EP01 + EP03를 merge하지 않는다.

---

## 16. 대표 Episode / Outlier

```text
cluster_embedding
=
mean(member embeddings)
```

평균에 가장 가까운 실제 Episode:

```text
representative_episode_id
```

가장 먼 Episode:

```text
outlier_episode_id
```

용도는 diagnostic / cluster explanation / research inspection이다.

---

## 17. Highlight Label 생성

v1에서는 새 LLM을 붙이지 않는다.

초기 label:

```text
H01
H02
H03
```

실제 의미 내용은 기존 C-05의 deterministic summary composition을 사용한다.

향후 label 자동 생성이 필요하면 별도 `HighlightLabelGenerator` contract로 분리한다.

---

## 18. Overlap 정책

현재 C-02는 Highlight overlap과 episode reuse를 허용하지만 v1 automatic grouping에서는 우선 사용하지 않는다.

```text
H01 = EP01 EP02 EP03
H02 = EP04 EP05
H03 = EP06
```

향후 experimental version에서만 bridge overlap을 검토한다.

---

## 19. 권장 모듈 구조

```text
PresentationInput
      ↓
EpisodeSemanticUnitBuilder
      ↓
EpisodeEmbedder
      ↓
TemporalAgglomerativeClusterer
      ↓
ClusterCountSelector
      ↓
GroupingProposal
      ↓
C-02 build_highlights()
      ↓
C-03 lineage
      ↓
C-05 deterministic summary
      ↓
C-06 / C-07 renderers
```

기존 C-02에 clustering logic을 넣지 않는다.

---

## 20. GroupingProposal

```python
@dataclass(frozen=True)
class GroupingProposal:
    algorithm: str
    algorithm_version: str
    embedder_id: str
    input_fingerprint: str
    selected_cluster_count: int
    groups: tuple[tuple[str, ...], ...]
    merge_trace: tuple["MergeRecord", ...]
```

예:

```python
GroupingProposal(
    algorithm="semantic_highlight_grouping",
    algorithm_version="v1",
    embedder_id="...",
    input_fingerprint="...",
    selected_cluster_count=3,
    groups=(
        ("EP01", "EP02", "EP03"),
        ("EP04",),
        ("EP05", "EP06"),
    ),
    merge_trace=(...),
)
```

---

## 21. Merge Trace

예:

```text
EP01 + EP02       similarity = 0.88
EP04 + EP05       similarity = 0.83
EP01/02 + EP03    similarity = 0.79
```

권장 기록:

```text
left_cluster
right_cluster
similarity
result_cluster
step_index
```

용도:

```text
research reproducibility
debugging
proposal audit
```

---

## 22. Determinism

같은 입력, 같은 embedder, 같은 algorithm version이면 같은 grouping proposal이 나와야 한다.

fingerprint 후보:

```text
episode_id
summary text
grounding status
content status
embedder id
algorithm version
```

결과 fingerprint 후보:

```text
groups
merge_trace
selected_cluster_count
```

---

## 23. 기존 v2.1과의 경계

절대 변경하지 않는 것:

```text
fixed_window_v1
canonical partition
A-09 canonical invariants
aar_canonical
grounding semantics
presentation summary eligibility
C-02 Highlight Builder contract
C-03 lineage
C-05 deterministic summary
C-06/C-07 renderer semantics
```

새 grouping 결과는 presentation-only다.

금지:

```text
GroupingProposal → canonical boundary 변경
GroupingProposal → episode 삭제
GroupingProposal → episode 삽입
GroupingProposal → segment membership 변경
```

---

## 24. 기존 C0와의 차이

### C0

```text
caption text
→ caption embedding
→ adjacent distance
→ peak
→ canonical boundary candidate
```

### 새 설계

```text
grounded canonical summaries
→ embeddings
→ temporal clustering
→ Highlight proposal
```

문제가 생겨도 Highlight grouping만 영향받고 aar_canonical은 그대로다.

---

## 25. v1 최소 연구 범위

| 항목 | 결정 |
|---|---|
| 입력 | `PresentationInput` |
| 텍스트 | presentation-eligible canonical summary |
| embedding | text embedding |
| similarity | cosine |
| clustering | agglomerative |
| temporal constraint | adjacent contiguous cluster만 merge |
| cluster count | deterministic elbow/knee |
| target count | 없음 |
| unreliable episode | singleton barrier |
| overlap | 사용 안 함 |
| LLM label generation | 사용 안 함 |
| Highlight summary | 기존 C-05 deterministic composition |
| canonical 변경 | 절대 없음 |
| 결과 성격 | presentation-only proposal |

---

## 26. 예상 실패 사례

### 26.1 같은 사건인데 문장 의미가 급변하는 경우

```text
EP01 차를 운전한다
EP02 차가 충돌한다
EP03 차에서 내린다
```

사람은 하나의 큰 사건으로 볼 수 있지만 text semantic similarity는 낮을 수 있다.

### 26.2 같은 주제지만 다른 사건

```text
EP01 첫 번째 식당에서 식사
...
EP20 두 번째 식당에서 식사
```

temporal constraint가 없으면 잘못 묶일 수 있다.

### 26.3 sparse/weak summaries

summary가 없는 episode가 많으면 singleton barrier가 많아져 Highlight가 지나치게 잘게 나뉠 수 있다.

이는 안전한 under-merge로 취급한다.

---

## 27. v2 Experimental 후보

v1 평가 후에만 다음을 검토한다.

```text
text semantic similarity
+
visual continuity
+
entity continuity
+
location continuity
+
ASR topic continuity
```

예:

```text
grouping_score =
w_text * text_similarity
+ w_visual * visual_continuity
+ w_entity * entity_continuity
```

weight tuning은 새 research experiment이므로 v1과 분리한다.

---

## 28. 권장 테스트

### Functional

```text
1. 동일 입력 rerun → 동일 groups
2. 인접 episode만 merge
3. 비인접 merge 절대 없음
4. target highlight count 없음
5. PASS summary 사용
6. NOT_APPLICABLE summary 사용
7. FAIL summary grouping signal 제외
8. summary 없는 episode singleton barrier
9. grouping proposal이 canonical을 mutate하지 않음
10. C-02가 proposal을 정상 소비
```

### Mutation

```text
1. temporal adjacency 검사 제거 → RED
2. FAIL episode도 embedding 대상으로 허용 → RED
3. unknown episode를 조용히 건너뜀 → RED
4. singleton barrier를 넘어 merge → RED
5. target_count=9 도입 → RED
6. grouping 결과로 canonical boundary 변경 → RED
7. merge trace 삭제 → RED
8. embedder/version fingerprint 삭제 → RED
9. grouping이 raw/timeline/binding 접근 → RED
10. C-02 내부에 clustering logic 직접 삽입 → architecture guard RED
```

---

## 29. 평가 관점

이 연구는 semantic event boundary accuracy를 바로 주장하지 않는다.

우선 평가 질문:

```text
Q1. 고정 Episode를 그대로 나열하는 것보다 사람이 읽기 쉬운가?
Q2. 동일 입력에서 grouping이 재현 가능한가?
Q3. 서로 다른 사건을 과도하게 merge하지 않는가?
Q4. weak evidence가 있을 때 안전하게 under-merge하는가?
Q5. 기존 canonical/provenance invariants가 완전히 보존되는가?
```

후속 연구에서만:

```text
Q6. text-only grouping보다 visual continuity 추가가 더 나은가?
```

를 본다.

---

## 30. 연구 위치

```text
v2.1 canonical feature     NO
Gate C requirement         NO
BoundaryProvider           NO
General event detector     NO

post-v2.1 research         YES
presentation automation    YES
Highlight proposal policy  YES
```

---

## 31. 도입 순서 권고

```text
1. 현재 v2.1 final acceptance 완료
2. 현재 architecture baseline 동결
3. SemanticHighlightGrouping_v1 별도 research ticket 생성
4. synthetic fixture로 algorithm contract 검증
5. non-official sample에서 report readability 관찰
6. canonical invariants 재검증
7. 별도 adoption decision
```

현재 v2.1 default를 자동 변경하지 않는다.

---

## 32. 핵심 방법론 한 문장

> 검증된 Canonical Episode의 summary를 의미적으로 표현한 뒤, 시간적으로 인접한 episode만 계층적으로 병합하여 canonical structure를 변경하지 않는 presentation-only Highlight grouping proposal을 생성한다.

---

## 33. 가장 중요한 안전 원칙

```text
Semantic grouping may be wrong.
Canonical truth must remain unchanged.
```

즉 grouping이 틀려도 보고서 묶음만 어색해야 하며, 정본 시간 구조·근거·grounding은 절대 흔들리면 안 된다.
