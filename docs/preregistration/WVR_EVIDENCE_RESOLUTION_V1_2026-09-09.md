# WVR_SAMPLING_SEMANTIC_DENSITY_EVIDENCE_RESOLUTION_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — V2 = `CLOSED / PAIRED_OUTPUT_STABILITY_HOLD`,
후속으로 evidence resolution `NEXT / APPROVED FOR PREREG`.
**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

## 0. 이 사건이 답하는 질문 하나

```
V2에서 발견된 report-material 충돌에 대해,
채택 제출본의 canonical evidence 층은 어느 arm의 주장을 지지하는가?
```

답하지 않는 질문: 0.25fps가 의미상 충분한가 · 0.5fps가 옳은가 · 어느 arm이 참인가.

## 1. 선행 상태 (이 사건의 전제)

```
V2                CLOSED / PAIRED_OUTPUT_STABILITY_HOLD
                  reason REPORT_MATERIAL_CROSS_ARM_CONFLICT
                  게이트(arm validity 6/6 · pair evaluability 3/3)는 PASS로 유효하다
0.25fps           semantic sufficiency NOT ESTABLISHED
0.5fps            factual authority NO
event extraction  HOLD          현행 제출본  READ-ONLY / NO PROMOTION
```

110쌍 전량 adjudication은 하지 않는다. V2의 acceptance 조건이
`REPORT_MATERIAL CONFLICT = 0`이었고 D1에서 이미 깨졌으므로 나머지를 판정해도
PASS로 돌아갈 수 없다(리뷰어 결정). 이 사건은 **깨진 조건의 방향을 가리는 것**만 한다.

## 2. 실행 형태 — 새 추론 없음

```
새 Qwen 추론      없다. GPU를 쓰지 않는다
새 캡셔닝·재색인   없다
쓰는 것            frozen V2 산출물 6건 + 이미 존재하는 evidence 층
프롬프트 변경      없다 (V2 프롬프트도 재사용하지 않는다 — 출력이 이미 있다)
```

코드에서 `torch`·`transformers`를 import하지 않는 것이 계약이고 테스트로 강제한다
(WVR-E22).

## 3. 입력 (동결 · 읽기 전용 · 해시 검증)

```
V2 출력      runs/wvr_light_v1/density_v2_D{1,2,3}_S{0,1}.json
             arm_status == ARM_VALID인 것만 (아니면 실행 거부)
evidence     work_full/full_xekZO4n4QuE/segments.json
             sha256 aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
             485구간 · 5초 · 필드 caption · subtitle
canonical    runs/vad0_paired/s1_shadow/S5/aar_canonical.json
             채택 제출본(R1-VAD0-QUALITY) source_run · 41 episode · fixed_window_v1 60초
영상         data/videos/full_xekZO4n4QuE.mp4
             sha256 ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
```

`segments_sha256`은 `submission_manifest_quality.json`의 `input.segments_sha256`과
동일하다 — 즉 **제출본이 실제로 근거로 쓴 그 evidence 층**이다.
해시가 하나라도 다르면 실행을 중단한다(`ResolveError`).

창별 대응 episode:

```
D1  300–480초   EP06 · EP07 · EP08
D2   30–210초   EP01 · EP02 · EP03 · EP04
D3  120–300초   EP03 · EP04 · EP05
```

## 4. evidence로 쓰지 않는 것 (명시적 배제)

```
episode summary · dialogue_note    하류 LLM(Qwen2.5-7B) 생성물이다. 근거가 아니라 산출물
V1 · V1B 산출물                    다른 계측기의 출력
검색 결과 · dev/test 질의·라벨      이 사건과 무관하다. 접촉하지 않는다
프레임 실물                        이번 범위 밖(별도 승인 사건). §10 참조
```

episode의 `grounding_status`·`content_status`·`source`는 **문맥 표시로만** 기록하고
판정에 넣지 않는다.

## 5. evidence 층의 권위 — 사전 명시

```
caption   Qwen2.5-VL-3B-4bit 출력. 5초 구간의 대표 프레임 기반. 한국어
          → Qwen3-VL-8B 출력과의 일치는 **기기간 일치**이고 진리가 아니다
subtitle  Whisper ASR. 발화 채널이므로 시각 주장과 독립이지만 발화된 것만 덮는다
```

따라서 판정 어휘는 참·거짓이 아니라 `EVIDENCE_SUPPORTS` · `EVIDENCE_CONTRADICTS` ·
`EVIDENCE_UNRESOLVED`이며, **"evidence에 없음"은 절대 CONTRADICTS가 되지 않는다**
(WVR-E15). 두 채널 모두 caption·subtitle 단위로 어느 채널에서 맞았는지 기록한다.

## 6. 충돌 후보 집합 — 두 출처의 합집합 (내가 고르지 않는다)

### 6-1. 결정적 selector `DETERMINISTIC_DOUBLY_DISJOINT`

frozen V2 collapsed event로부터, 다음을 **모두** 만족하는 (S0, S1) 쌍:

```
① v2.temporally_compatible (구간 겹침 또는 끝점 간격 ≤ 허용오차)
② action 토큰 집합이 서로 disjoint      (불용어 제거는 v2.STOPWORDS 그대로)
③ object_or_state 토큰 집합도 disjoint
```

②③을 함께 요구하는 이유는 표현 차이(`potato balls` ↔ `potato mixture`)를 제외하고
활동 자체가 갈리는 쌍(`eating breaded food` ↔ `sewing pajama pants`)만 남기기
위함이다. **새 임계값은 도입하지 않는다** — 구조적 disjoint 조건뿐이다.
허용오차는 4.0·8.0 둘 다 계산해 후보 수를 보고하고, 판정은 primary 4.0으로 한다.

### 6-2. 리뷰어 지목 `REVIEWER_NAMED` (원문 동결, 8건)

```
D1  (312,480) vs (380,390) · (420,450) · (450,460) · (470,480)
D2  ( 96,210) vs (104,112) · (112,120) · (128,136) · (136,152)
```

두 출처를 합집합으로 쓰고 각 행에 `source`를 태깅한다. 6-1이 6-2를 다 포함하지
않으면 `SELECTOR_INCOMPLETE`로 기록한다 — **실행을 무효화하지 않고, selector의 한계로
남긴다**(WVR-E21).

## 7. evidence 창 — 겹친 구간만 본다

```
겹치면    [max(start), min(end)]      예: (312,480) × (420,450) → 420–450
안 겹치면 두 구간의 hull
```

S0의 168초 단일 interval을 통째로 지지 여부 판정하면 어디서든 한 번 맞으면 지지가
되어 질문이 사라진다. 질문은 "**420–450초에 무엇이 있었나**"이므로 겹친 구간으로
자른다(WVR-E09). 대상 evidence 구간 = `start < window_end and end > window_start`.

## 8. claim 판정 규칙 (evidence를 읽기 전에 확정)

### 8-1. 이중언어 대조 사전 (동결)

V2 진단 출력은 English-only이고 evidence는 한국어다. 토큰 겹침이 원리적으로
불가능하므로, **frozen V2 claim 문자열만 보고** 한국어 표면형 집합을 사전등록한다.

```
모듈      src/wvr_evidence_lexicon.py
sha256    450f5dac163ba236e1af090e1cabdac49f1282e74d8fd3bc6491b79add486b1b
항목      action 25 · object 53
출처      frozen V2 collapsed claims만. evidence 본문을 보고 만들지 않았다
충돌 제거 "볼"은 bowl·balls 둘 다에 걸려 양쪽에서 삭제(COLLISION_DROPPED)
```

**evidence를 읽은 뒤 표면형을 추가·수정하는 것은 계약 위반이다.** 사전이 못 덮는
claim은 `LEXICON_UNCOVERED`로 표시되고 `EVIDENCE_UNRESOLVED`로 남는 것이 정상이다.
사전 해시가 바뀌면 테스트가 RED가 된다(WVR-E02).

### 8-2. 지지 판정

```
CLAIM_SUPPORTED
  같은 evidence 구간·같은 채널의 본문에 action 표면형 ≥ 1개와 object 표면형 ≥ 1개가
  함께 나온다
부분 일치(한 차원만)  partial로 기록하고 지지로 세지 않는다
```

object 차원은 의도적으로 관대하다(다중어 object의 토큰 합집합). 판별력은 action
차원이 담당한다(`먹` vs `재봉`). 또한 action·object 표면형이 같은 어휘일 때
(`sewing` ↔ `재봉틀`) 단독 일치로 지지가 성립할 수 있으므로 각 hit에
`shared_terms`·`independent`를 기록하고 `independent_support`를 보고한다 —
**게이트로 쓰지 않고 보고만 한다**(사후 임계값 도입 금지).

### 8-3. claim 판정값

```
EVIDENCE_SUPPORTS      본인 claim이 지지됨
EVIDENCE_CONTRADICTS   본인 claim은 지지 0 AND 경쟁 claim이 같은 창에서 지지됨
                       AND 본인 claim이 사전에 덮여 있음
EVIDENCE_UNRESOLVED    그 밖 전부 (양쪽 지지 0 · 부분 일치 · LEXICON_UNCOVERED)
```

`CONTRADICTS`는 경쟁 claim의 **적극적 지지**를 필요조건으로 한다(WVR-E16·E17).

### 8-4. 쌍 판정값

```
BOTH_SUPPORTED_AT_DIFFERENT_SEGMENTS   둘 다 지지 — 세부화(granularity) 차이 신호
REFERENCE_ONLY_SUPPORTED               S0(0.5fps)만 지지
ARM_ONLY_SUPPORTED                     S1(0.25fps)만 지지
NEITHER_RESOLVED                       어느 쪽도 지지되지 않음
```

## 9. 사건 판정 — 분기를 미리 잠근다

```
BRANCH_A_HIGHER_DENSITY_COLLAPSE_SUPPORTED
    ARM_ONLY > 0 AND REFERENCE_ONLY == 0
BRANCH_B_REDUCED_SAMPLING_DETAIL_UNSUPPORTED
    REFERENCE_ONLY > 0 AND ARM_ONLY == 0
BRANCH_C_EVIDENCE_INCONCLUSIVE
    그 밖 전부 (양방향 혼재 · 전부 NEITHER_RESOLVED)
```

`BOTH_SUPPORTED`는 분기 계산에 넣지 않고 별도 수치로 보고한다 — S0의 장구간 주장과
S1의 세부 주장이 서로 다른 5초 구간에서 각각 지지되는 경우는 충돌이 아니라
**세부화 차이**이기 때문이다.

분기별 다음 방향(리뷰어 결정 그대로, 이 사건에서 실행하지 않는다):

```
A → 문제는 0.25fps의 정보 손실보다 90프레임 고밀도 입력에서의
    Qwen representation collapse 쪽. 다음은 short-window higher-density reference probe
B → 0.25fps는 semantic-density 후보로 HOLD/FAIL 방향
C → INCONCLUSIVE. 리뷰어가 짧은 동일-window paired probe를 새로 설계한다
```

## 10. 금지 사항

```
새 추론 실행 · 캡션 재생성 · 재색인
episode summary를 evidence로 사용
"evidence에 없음"을 반증으로 사용
사전 표면형을 evidence 열람 후 추가·수정
결과를 보고 §6~§9의 규칙·분기·허용오차 변경
"0.25fps PASS" · "0.5fps가 truth" · semantic sufficiency 주장
event extraction 개시 · 제출본 승격 · official test 접촉 · M9 실행
프레임 실물 열람으로 판정 격상 (별도 승인 사건이다 — 분기 C에서 리뷰어가 결정)
```

## 11. 공개 — 사전등록 전 열람한 evidence

정직성 기록: 이 사전등록을 쓰기 전 evidence 층의 구조를 확인하는 과정에서
**segment idx 60~63(300~320초)의 caption·subtitle 4건을 열람했다.**
사전(§8-1)은 frozen V2 claim만 보고 작성했으나, 해당 4구간은 산출물에
`pre_freeze_viewed = true`로 표시해 감사 가능하게 남긴다. 그 밖의 evidence 본문은
사전등록·커밋 이후에 처음 읽는다.

## 12. 테스트 (WVR-E01~E30)

```
동결        E01 사전등록 커밋 · E02 사전 해시 · E03 충돌 표면형 제거 · E04 금지 플래그
후보 선정   E05 허용오차 2개 · E06 이중 disjoint · E07 시간 호환 · E08 표현차 제외
            E09 겹친 구간만
evidence    E10 half-open 교집합 · E11 사전 열람 공개 · E12 summary 배제
지지 판정   E13 같은 구간·채널 동시 요구 · E14 공유 표면형 플래그
            E15 없음 ≠ 반증 · E16 경쟁 지지 필요 · E17 미덮 claim 반증 불가
판정        E18 4값 · E19 분기 동결 · E20 지목 8건 동결 · E21 selector 불완전 기록
실행기      E22 추론 스택 금지 · E23 무효 arm 거부 · E24 해시 검증
            E25 합집합 태깅 · E26 없는 구간 오류
실행 후     E27 한계 선언 · E28 모든 CONTRADICTS에 경쟁 지지 존재
            E29 라벨·합계 일관 · E30 입력 provenance = 채택 제출본 층
```

뮤테이션으로 각 테스트가 실제로 잡는지 확인하고, 구멍은 결과 보고에 적는다.

## 13. 산출물

```
runs/wvr_light_v1/evidence_resolution_v1.json     쌍별 판정 · 인용 원문 · 합계 · 분기
docs/probes/WVR_EVIDENCE_RESOLUTION_V1_2026-09-09.md
src/wvr_evidence_v1.py · src/wvr_evidence_lexicon.py
scripts/wvr_evidence_resolve.py · tests/test_wvr_evidence_v1.py
```

V2 산출물 6건·요약 1건은 변경하지 않는다.
