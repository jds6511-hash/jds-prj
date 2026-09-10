# WVR_W00_ZERO_DURATION_EXEMPLAR_ISOLATION_V1 사전등록 (2026-09-10)

승인: 리뷰어 결정 — **최소 prompt-mutation probe (새 inference 1회)**.
이 문서는 GPU 실행 전에 커밋한다. **결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

production recovery 확정 실험이 아니다. 후속 SHADOW 재실행·Event extraction·Overview는
하지 않는다.

## 0. 선행 상태 (동결 · 재실행하지 않는다)

```
WVR_W00_TRIGGER_ISOLATION_V1          CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED
WVR_W00_VISUAL_CONTENT_ISOLATION_V1   CLOSED / VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED
SUBDIVISION family                    STOPPED / NOT SUFFICIENT
WVR_EVENT_EXTRACTION_SHADOW_V1        CLOSED / INCONCLUSIVE
```

현재 2×2:

```
pixel source     T0 (0–48)        T1 (120–168)
W00 pixels       INVALID          VALID
W05 pixels       VALID            VALID
```

허용되는 최대 결론은 "failure는 tested cell에서 W00 visual pixels와 원래 0–48
absolute-time representation이 결합된 조건에서만 관찰됐다"까지다. 근본 mechanism은
아직 모른다.

## 1. Primary question 하나

```
W00 pixels + T0(0–48)의 known-failing configuration에서, frozen prompt의
[Output format] example에 있는 zero-duration interval을 positive-duration interval로
바꾸는 것만으로 model-output degeneracy 상태가 달라지는가?
```

측정하지 않는 것:

```
prompt 전체가 나쁜가 · schema가 나쁜가 · 0초 자체가 문제인가 ·
4초 interval이 최적인가 · production prompt가 무엇이어야 하는가
```

## 2. historical control (재실행하지 않는다)

TRIGGER_ISOLATION_V1 arm A를 frozen historical control로 쓴다.

```
pixels          W00 [0,48) 24장          prompt window   0.0–48.0
metadata        T0 / original indices    prompt          SAMPLING_DIAG_PROMPT_V2
output example  start_sec 0.0 / end_sec 0.0
result          WINDOW_INVALID
raw             원본 W00 및 REPRO 3회와 byte-identical (c5e4f752…)
```

무변경 확인용 해시:

```
trigger_v1_A.json      6de08ac56322a25edea8dd3294b039e8f942d5ec2ae63720b634074bcc2c0180
trigger_v1_A_raw.txt   c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
trigger_v1_D.json      e406ae2520e63739d8758fa23590bbe0c443d6bc4f8a6512cee9f0de240a86b3
trigger_v1_D_raw.txt   01496012501858fb0a6f3668194a5e936819d59efb588d5792680d55e591f1a5
visual_v1_E.json       (실행 시점 해시를 구현 커밋에 기록한다)
shadow_v1_W05.json     ebcd438d8ccd91b248622a626c2932b26e2787a95e31aee8a332fc45a92ee241
shadow_v1_W05_raw.txt  38caf8e6cfde38ce8da49bc6fcdd68e7c85454f8db828fdf27906843758564eb
shadow_v1_W00.json     c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e44daa074
shadow_v1_W00_raw.txt  c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
```

control 상태를 소급 변경하지 않는다.

## 3. 신규 arm Z1 — 새 inference 정확히 1회

W00의 known-failing X0T0 configuration을 그대로 유지하고, frozen prompt의
`[Output format]` example 한 곳만 바꾼다.

```
기존   {"events": [{"start_sec": 0.0, "end_sec": 0.0, "actor": "...",
신규   {"events": [{"start_sec": 0.0, "end_sec": 4.0, "actor": "...",
```

intended mutation은

```
exemplar literal   "end_sec": 0.0  →  "end_sec": 4.0     (템플릿 내 유일 occurrence 1건)
```

하나뿐이다. actor/action/object 값 · JSON 구조 · 문구 · 들여쓰기는 byte 단위로 그대로
둔다. 변형 템플릿은 원본 문자열에서 **프로그램적으로 1회 치환해 생성**하며(수동 재작성
금지) 원본 모듈 `wvr_density_prompt_v2`는 수정하지 않는다.

## 4. `4.0`의 의미

production duration 권고가 아니다. `zero-duration exemplar → positive-duration
exemplar`로 바꾸기 위한 diagnostic 값이다. 결과가 좋아도 "4초 event가 적절하다"고
주장하지 않는다.

## 5. 고정할 입력 (known-failing cell 그대로)

```
video / sha256                동일
pixels                        W00 0,2,4,…,46초 24장
pixel values                  Trigger A와 hash-identical
prompt window                 0.0–48.0
VideoMetadata.frames_indices  Trigger A와 동일 (0 … 1,380)
duration · total_num_frames · fps · width · height · video_backend
                              Trigger A와 동일
```

## 6. 동결 model/runtime

```
Qwen/Qwen3-VL-8B-Instruct · revision 0c351dd0… · video-only · 0.5fps ·
24 frames · 512×288 · bf16 · SDPA · default allocator ·
max_new_tokens 4096 · repetition_penalty 1.0 · greedy ·
동일 parser · 동일 collapse rule · 동일 technical validity gate ·
동일 representation-degeneracy gate
```

변경 금지:

```
schema 변경 · event cap · token cap 변경 · repetition penalty 변경 ·
temperature 변경 · stop criterion 변경 · window 변경 · sampling 변경 ·
metadata 변경 · timestamp shift · 추가 retry
```

## 7. prompt provenance (별도 기록)

이번에는 prompt template 자체가 의도적으로 바뀐다. 따라서 다음을 나눠 기록한다.

```
old_prompt_template_hash   37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
new_prompt_template_hash   (구현 커밋·산출물에 기록)
old rendered prompt hash   c936901940b8… (Trigger A)
new rendered prompt hash   (산출물에 기록)
exact textual diff         사전등록된 exemplar 한 줄만
```

diff가 사전등록 mutation 외에 하나라도 있으면 **실행하지 않는다.**

## 8. GPU 전 mutation audit

validator가 실행 전에 확인한다.

```
pixel hash identity          PASS
metadata identity            PASS  (frames_indices · 고정 6필드)
prompt window identity       PASS  (0.0–48.0)
model/runtime identity       PASS
prompt textual diff          사전등록 mutation 1건뿐
```

다른 mutation이 있으면 `INCONCLUSIVE / MUTATION_SCOPE_VIOLATION`으로 멈추고 추론하지
않는다.

## 9. raw-before-parse

```
inference -> raw persist -> raw sha256 -> parse -> 구조 지표 -> frozen technical gate
```

raw salvage 금지 · unterminated output 수정 금지.

## 10. 기술 감사 (게이트 불변)

```
WINDOW_VALID / WINDOW_INVALID
generated tokens · finish reason · raw chars · completed objects ·
raw unique signatures · zero-duration count · positive-duration count ·
max signature repeat · max consecutive repeat · first repeat index/offset ·
JSON complete · collapsed event count · unique collapsed signatures
```

representation-degeneracy gate를 바꾸지 않는다.

## 11. exemplar-copy diagnostic (AUDIT_DIAGNOSTIC_ONLY)

parsed event마다 `duration_sec = end_sec - start_sec`를 계산해 아래만 보고한다.

```
duration 분포 · 정확히 4.0초인 event 수 · 전체가 정확히 4.0초인지 여부
```

이 진단으로 새 비율 임계를 만들지 않고, primary verdict를 사후 변경하지 않는다.

## 12. primary verdict 어휘 (사전 동결)

```
ZERO_DURATION_EXEMPLAR_INTERACTION_SUPPORTED
    historical X0T0 control INVALID  AND  Z1 WINDOW_VALID
    허용 최대 해석: "Within the known-failing W00 × T0 cell, replacing the
    zero-duration output exemplar with a positive-duration exemplar changed the
    technical generation outcome from INVALID to VALID."
    production fix 증명이 아니다.

ZERO_DURATION_EXEMPLAR_EFFECT_NOT_SUPPORTED
    Z1 WINDOW_INVALID이고 무관한 blocker가 없을 때
    의미: exemplar를 positive-duration으로 바꾸는 것만으로 known W00 × T0 failure를
    제거하지 못했다.

INCONCLUSIVE
    mutation scope violation · pixel identity failure · metadata identity failure ·
    wrong runtime · wrong rendered window values · infrastructure failure ·
    provenance failure
```

## 13. verdict 계산 우선순위 (결과 후 변경 금지)

```
1  INCONCLUSIVE     2  Z1 technical status     3  위 두 어휘 중 하나
```

## 14. 해석 제한

Z1이 VALID여도 금지:

```
문제 원인이 zero-duration example이었다 · prompt bug를 증명했다 ·
새 prompt를 production 채택한다 · 4초가 올바른 event duration이다 ·
전체 WVR이 해결됐다
```

측정 범위는 **pixel set 1개 · problematic time encoding 1개 · exemplar mutation 1개**다.

## 15. Z1이 VALID일 때

**추가 inference를 하지 않는다.** raw에서 parsed events · collapsed events ·
duration 분포 · 4초 복사 진단 · representation 지표를 저장하고 상태는

```
PROMPT_MUTATION_TECHNICALLY_RECOVERED + SHADOW REVALIDATION REQUIRED
```

수준으로만 기록한다. 전체 C01을 새 prompt로 재실행하지 않는다 — 재실행 여부는 리뷰어가
결정한다.

## 16. Z1이 INVALID일 때

다음도 하지 않는다.

```
다른 positive-duration example · 1초/2초/8초 example sweep ·
zero-duration 방지 rule 추가 · event cap 추가 · token cap 상향
```

실패를 그대로 가져온다. 후속 prompt/schema 설계는 리뷰어가 별도로 결정한다.

## 17. 최소 invariant (테스트로 고정)

```
새 inference 정확히 1회
W00 픽셀 불변 · 24 frame hash가 Trigger A와 동일
T0 prompt window 불변 (0.0–48.0) · T0 metadata indices 불변
model/runtime 불변 · 4096 불변 · 0.5fps 불변
prompt mutation은 정확히 example end_sec 0.0 → 4.0 · 그 밖의 prompt diff 없음
원본 템플릿 모듈 무변경 (기존 사건들의 prompt hash 37f9588e… 유지)
raw-before-parse · retry 없음
historical Trigger A · Trigger D · Visual E · SHADOW W05 · 원본 W00 무변경 ·
SHADOW blind map 무변경 · 현행 제출본 무변경 · official test 미개방
```

mutation suite RED 확인 + full suite 실행.

## 18. 실행 순서

```
1  prereg      2  prereg commit      3  implementation/tests commit
4  mutation-scope validator          5  pixel/metadata identity validator
6  Z1 fresh-process inference 1회     7  raw persist
8  parse/collapse                    9  구조 audit
10 exemplar-copy diagnostic          11 primary verdict
12 tests/mutations/full suite        13 clean tree
14 result commit                     15 STOP
```

## 19. 산출물 이름

```
runs/wvr_light_v1/exemplar_v1_Z1.json          arm record
runs/wvr_light_v1/exemplar_v1_Z1_raw.txt       raw 원문 (파싱 전 저장)
runs/wvr_light_v1/exemplar_v1_selfcheck.json   픽셀·시간·mutation scope 실측
runs/wvr_light_v1/exemplar_v1_summary.json     A vs Z1 비교·진단·verdict
runs/wvr_light_v1/exemplar_v1.log              배치 로그
```

## 20. 실행 후 정지선 (결과와 무관)

```
SHADOW_V1 CLOSED / INCONCLUSIVE
TRIGGER_ISOLATION_V1 JOINT_OR_INTERACTION_EFFECT_SUPPORTED
VISUAL_CONTENT_ISOLATION_V1 VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED
SUBDIVISION family STOPPED / NOT SUFFICIENT
```

리뷰어 승인 전 HOLD:

```
전체 C01 새 prompt 재실행 · SHADOW_V2 · Event extraction production ·
Semantic Chapters · Highlights · Overview · Analysis · Conclusion · HWPX ·
token cap 변경 · retry/fallback policy · 다른 prompt mutation
```

현행 제출본 READ-ONLY · official test UNOPENED · M9 HOLD. 여기서 멈춘다.
