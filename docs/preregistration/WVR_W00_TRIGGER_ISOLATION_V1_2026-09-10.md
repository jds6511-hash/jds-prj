# WVR_W00_TRIGGER_ISOLATION_V1 사전등록 (2026-09-10)

승인: 리뷰어 결정 — **behavioral trigger isolation**. 이 문서는 GPU 실행 전에 커밋한다.
**결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

recovery 사건이 아니다. 결과를 보고 recovery·prompt 수정·추가 subdivision으로 넘어가지
않는다.

## 0. 선행 상태 (동결 · 바꾸지 않는다)

```
WVR_EVENT_EXTRACTION_SHADOW_V1              CLOSED / INCONCLUSIVE
WVR_W00_DEGENERACY_FORENSIC_V1              CLOSED / MODEL_OUTPUT_DEGENERACY
WVR_W00_DEGENERACY_REPRO_V1                 CLOSED / REPRODUCIBLE (3/3 + 원본 byte-identical)
WVR_W00_SUBDIVISION_RECOVERY_V1             CLOSED / SUBDIVISION_RECOVERY_FAIL
WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1   CLOSED / RECOVERY_FAIL
```

관측:

```
W00 [0,48) INVALID · C0 [0,24) INVALID · D0 [0,12) INVALID
0초에서 시작하는 세 depth 모두 cap-hit + zero-duration 지배 + 미완결
```

`start_sec=0이 원인` · `visual content가 원인` · `prompt가 원인` 중 어느 것도 아직
확정하지 않았다.

읽기 전용으로 무변경을 확인할 산출물:

```
shadow_v1_W00.json      c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e44daa074
shadow_v1_W00_raw.txt   c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
subdiv_v1_C0.json       7925172a83d3304730e6b21509bdc0c70dbe78ae0e5433e0809a7e074471d0f6
subdiv_v1_C0_raw.txt    7460a5b61821e41b15dd0281aa15580a2ac7752dab48be2bbf809f1d193105d0
subdiv_v1_C1.json       44b7f96c1f23a0760f6cc8fa975d058b86d813878c75898136bd368979d75f11
subdiv_v1_C1_raw.txt    9316f9f62b519ef0cc8a99a827fa71ed153b5efea3a673e5d53b2d084392f117
subdiv_v1_C2.json       cb77b4b283f988d150efcb1c780d4cc1c8c5ff6d7ce566517ca35b17cc68f126
subdiv_v1_C2_raw.txt    70815aeee2408bd174d0a031a08200bf9e6b12fdff6d46a9c8a0ec36ef453b10
```

## 1. Primary question 하나

```
동일한 W00 visual pixel에서 나는 model-output degeneracy가
(1) prompt 안 absolute-time encoding, (2) VideoMetadata.frames_indices 기반
absolute-time encoding, (3) 둘의 interaction에 따라 달라지는가?
```

prompt text · schema · token cap · sampling density · window length는 바꾸지 않는다.

## 2. normative authority 우선순위

```
① 이 사건 preregistration
② frozen model/prompt/runtime configuration
③ raw execution artifacts
④ prior forensic/repro/recovery 결과
⑤ PROJECT_OVERVIEW.md (지도이지 이 실험의 계약이 아니다)
```

## 3. 절대시각이 모델에 들어가는 두 경로

```
P channel   frozen prompt의 [Window] 줄
            "start_sec=%(window_start).1f end_sec=%(window_end).1f"
M channel   VideoMetadata.frames_indices
            원본 영상 기준 절대 frame index
```

기계적 확인(transformers 5.14.1 · 실행 환경): `do_sample_frames=False`이면
`BaseVideoProcessor`는 프레임을 다시 뽑지 않고 `metadata.frames_indices`를 덮어쓰지
않는다. `Qwen3VLProcessor.replace_video_token`이 그 indices와 fps로
`_calculate_timestamps`를 계산해 텍스트에 `<X.X seconds>` 마커로 넣는다. 픽셀은
전달된 PIL 목록에서만 온다 — **픽셀과 M channel은 분리 가능하다.**

고정하는 metadata(4 arm 동일): `total_num_frames · fps · width · height · duration ·
video_backend`. 조작하는 필드는 `frames_indices` **하나뿐**이다.

## 4. 고정할 visual input (4 arm 동일)

```
pixel source window   W00 [0,48)
sampling              0.5fps · 24프레임
pixel timestamps      0, 2, 4, … , 46
pixel size            512×288
```

**4 arm의 24장 픽셀 바이트가 완전히 동일해야 한다.** 픽셀 sha256은 원본 W00 record의
`frame_hashes`와도 일치해야 한다. 하나라도 불일치면 causal comparison을 하지 않는다.

## 5. time shift (사전 고정)

```
SHIFT_SEC = +120.0
```

```
P1 prompt window        120.0 – 168.0
M1 frames_indices       index = int(round((t + 120.0) × rate))   t ∈ {0,2,…,46}
                        (rate = 원본 stream average_rate · M0와 같은 rate)
```

shifted metadata는 "다른 시각의 픽셀을 읽어라"가 아니라 **동일 픽셀에 다른
absolute-time identity를 부여하는 조작**이다. `duration`·`total_num_frames`는 shift하지
않는다.

## 6. 2×2 arm

```
            M0 (원본 indices)      M1 (+120초 indices)
P0 (0–48)   A                      B
P1 (120–168) C                     D
```

```
A   P0 M0   현행 control
B   P0 M1   prompt 원래 시간 · metadata만 +120
C   P1 M0   prompt만 +120 · metadata 원래 indices
D   P1 M1   둘 다 +120
```

## 7. 동결 inference configuration (4 arm 동일)

```
model                Qwen/Qwen3-VL-8B-Instruct · revision 0c351dd0…
prompt template      SAMPLING_DIAG_PROMPT_V2 (문구 불변 · hash 37f9588e…)
schema               start_sec · end_sec · actor · action · object_or_state
입력                  video-only · English-only
sampling             0.5fps 개념 · 24 입력 프레임 · 512×288
런타임                bf16 · SDPA · default allocator
생성                  greedy · do_sample False · num_beams 1 ·
                     max_new_tokens 4096 · repetition_penalty 1.0
processor/model 경로  동일 · do_sample_frames False · do_resize False
```

C/D에서 바뀌는 것은 `%` 치환으로 들어가는 **숫자값뿐**이다.

## 8. prompt hash 두 개를 분리 기록

```
prompt_template_hash   4 arm 동일해야 한다 (37f9588e…)
rendered_prompt_hash   A == B (0.0–48.0) · C == D (120.0–168.0)
                       두 값이 존재하는 것이 정상이며 prompt mutation이 아니다
```

## 9. metadata identity 기록·검증

각 arm에 `frames_indices · duration · total_num_frames · fps · width · height ·
video_backend`를 저장하고 아래를 검증한다.

```
A.indices == C.indices          B.indices == D.indices
A.indices != B.indices          (조작이 실제로 걸렸는지)
duration · total_num_frames · fps · width · height · backend   4 arm 동일
A/B는 frames_indices만 다르다     C/D도 frames_indices만 다르다
```

## 10. 실행

```
A ×1   B ×1   C ×1   D ×1        총 4회 fresh-process inference
```

반복 측정하지 않는다. 실패 arm을 retry하지 않는다.

## 11. raw-before-parse

```
inference -> raw persist -> raw sha256 -> parse -> 구조 지표 -> 기술 분류
```

unterminated JSON salvage 금지. raw 수정 금지.

## 12. arm 기술 분류 (기존 어휘 · 게이트 변경 없음)

각 arm은 `WINDOW_VALID` 또는 `WINDOW_INVALID`다. 최소 검사:

```
process complete · no OOM · no runtime failure · raw persisted ·
JSON parse · schema · language contract · generation cap ·
representation degeneracy · frame count 24 · pixel identity
```

구조 지표도 기록한다:

```
generated_tokens · finish_reason · raw_chars · completed_object_count ·
raw_unique_signature_count · zero_duration_count · positive_duration_count ·
max_signature_repeat · max_consecutive_repeat · first_repeat index/offset ·
json_complete
```

## 13. primary causal-pattern 어휘 (사전 동결)

```
PROMPT_TIME_EFFECT_SUPPORTED
    A invalid · B invalid · C valid · D valid          (P0 실패 · P1 회복)

METADATA_TIME_EFFECT_SUPPORTED
    A invalid · C invalid · B valid · D valid          (M0 실패 · M1 회복)

JOINT_OR_INTERACTION_EFFECT_SUPPORTED
    A invalid이고 B/C/D 중 하나 이상 valid인데 위 두 main-effect 패턴이 아닐 때.
    interaction 가능성만 기록하고 메커니즘을 단정하지 않는다.

ABSOLUTE_TIME_EFFECT_NOT_SUPPORTED
    A · B · C · D 모두 invalid

CONTROL_NOT_REPRODUCED
    A valid — B/C/D와 무관하게 여기서 종료하고 causal pattern을 해석하지 않는다

INCONCLUSIVE
    pixel identity failure · metadata 조작 실패 · rendered prompt 불일치 ·
    잘못된 runtime/config · 무관한 인프라 실패 · provenance 실패 ·
    픽셀과 metadata time을 분리할 수 없음(IMPLEMENTATION_BLOCKED)
```

## 14. verdict 계산 우선순위 (결과 후 변경 금지)

```
1  INCONCLUSIVE          2  CONTROL_NOT_REPRODUCED          3  2×2 패턴 분류
```

## 15. 해석 제한

어떤 패턴이 나와도 금지:

```
근본 원인을 규명했다 · Qwen 내부 메커니즘을 규명했다 ·
start_sec=0 bug를 증명했다 · metadata가 모델을 망가뜨린다 · prompt가 잘못됐다
```

이 사건은 behavioral trigger isolation이고 causal mechanism proof가 아니다.
허용되는 최대 진술은 "이번 W00 pixel set에서 <해당 채널> absolute-time encoding과
degeneracy 상태의 연관이 관찰됨"까지다.

## 16. 이번 사건에서 하지 않는 것

```
visual-content 조작 (다른 픽셀 + 0초 encoding)   후속 사건으로 분리
prompt output-format 예시 {"start_sec":0.0,"end_sec":0.0,…} 변경   금지 (4 arm 유지)
token cap 변경 · schema 변경 · sampling density 변경 · window length 변경 · retry
processor 내부 monkey-patch (필요한 최소 adapter는 구현 커밋에 명시하고 테스트한다)
```

## 17. 실행 전 hard blocker

GPU 사용 전에 확인한다.

```
동일 24 pixel bytes를 유지한 채 frames_indices만 독립적으로 바꿀 수 있는가?
```

NO이면 `INCONCLUSIVE / IMPLEMENTATION_BLOCKED`로 기록하고 추론하지 않는다.
확인은 모델 없이 processor만 올려 4 arm 입력을 만들고 `pixel_values` 바이트 동일성과
텍스트 `<X.X seconds>` 마커 차이를 실측하는 self-check로 한다.

## 18. audit diagnostic (authority 아님)

arm 간 raw hash 동일성 · 앞부분 object 일치 · top signature · 반복 시작 위치 ·
zero-duration 비율 · token 수를 계산하되 `AUDIT_DIAGNOSTIC_ONLY`로 표시한다.
semantic 우열·사실성을 판정하지 않는다.

## 19. 최소 invariant (테스트로 고정)

```
arm 정확히 4개 · A(P0M0) · B(P0M1) · C(P1M0) · D(P1M1)
SHIFT_SEC 정확히 +120.0
4 arm 동일: 24 pixel hash · 픽셀 순서 · model revision · prompt template ·
            generation config · runtime · duration · total_num_frames · fps ·
            width/height · backend
A prompt == B prompt · C prompt == D prompt
A indices == C indices · B indices == D indices · A indices != B indices
A/B는 frames_indices만 다르다 · C/D도 frames_indices만 다르다
A/C rendered prompt는 window 값만 다르다 · B/D도 같다
raw-before-parse · retry 없음 · 원본 W00 및 선행 산출물 무변경 ·
SHADOW blind map 무변경 · 현행 제출본 무변경 · official test 미개방
```

mutation suite에서 위 invariant 파괴 시 RED 확인 + full suite 실행.

## 20. 실행 순서

```
1  prereg      2  prereg commit      3  implementation/tests commit
4  validator   5  pixel/metadata 분리 self-check (GPU 없음)
6  A inference + raw persist          7  B inference + raw persist
8  C inference + raw persist          9  D inference + raw persist
10 parse + 구조 audit                 11 verdict 계산
12 tests/mutations/full suite         13 clean tree
14 result commit                      15 STOP
```

## 21. 산출물 이름

```
runs/wvr_light_v1/trigger_v1_{A,B,C,D}.json        arm record
runs/wvr_light_v1/trigger_v1_{A,B,C,D}_raw.txt     raw 원문 (파싱 전 저장)
runs/wvr_light_v1/trigger_v1_selfcheck.json        픽셀/metadata 분리 self-check
runs/wvr_light_v1/trigger_v1_summary.json          arm 표·조작 표·교차 비교·verdict
runs/wvr_light_v1/trigger_v1.log                   배치 로그
```

## 22. 실행 후 상태 (결과와 무관하게 유지)

```
SHADOW_V1 INCONCLUSIVE · W00_FORENSIC MODEL_OUTPUT_DEGENERACY ·
W00_REPRO REPRODUCIBLE · SUBDIVISION_RECOVERY FAIL ·
RECURSIVE_SUBDIVISION_RECOVERY FAIL
production Event extraction · Overview / Analysis / Conclusion       HOLD
0.5fps    PROVISIONAL WORKING DENSITY ONLY
현행 제출본  READ-ONLY      official test UNOPENED      M9 HOLD
후속 visual-content isolation · prompt/schema mutation · token-cap 변경 ·
retry/fallback 정책                                   리뷰어 승인 전 실행 금지
```

여기서 멈춘다.
