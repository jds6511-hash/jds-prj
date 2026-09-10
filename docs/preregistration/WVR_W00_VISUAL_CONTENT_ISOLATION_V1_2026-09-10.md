# WVR_W00_VISUAL_CONTENT_ISOLATION_V1 사전등록 (2026-09-10)

승인: 리뷰어 결정 — **한 칸만 채우는 최소 probe (새 inference 1회)**.
이 문서는 GPU 실행 전에 커밋한다. **결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

## 0. 선행 상태 (동결 · 재실행하지 않는다)

```
WVR_W00_TRIGGER_ISOLATION_V1                CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED
WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1   CLOSED / RECOVERY_FAIL
WVR_W00_SUBDIVISION_RECOVERY_V1             CLOSED / SUBDIVISION_RECOVERY_FAIL
WVR_W00_DEGENERACY_REPRO_V1                 CLOSED / REPRODUCIBLE
WVR_W00_DEGENERACY_FORENSIC_V1              CLOSED / MODEL_OUTPUT_DEGENERACY
WVR_EVENT_EXTRACTION_SHADOW_V1              CLOSED / INCONCLUSIVE
recursive subdivision hypothesis            STOPPED / NOT SUFFICIENT
```

TRIGGER_ISOLATION_V1의 정확한 관측(같은 W00 픽셀):

```
P0 M0 INVALID · P0 M1 INVALID · P1 M0 INVALID · P1 M1 VALID
한쪽 time channel만 바꿔서는 상태가 바뀌지 않았고, 둘을 함께 바꿨을 때만 바뀌었다
```

이것만으로는 두 설명을 구분하지 못한다.

```
가설 1   0–48이라는 absolute-time configuration 자체와 출력 degeneracy가 연관된다
가설 2   W00 초반 visual content × 0–48 time encoding의 특정 interaction이다
```

## 1. 2×2 표 — 세 칸은 이미 frozen이고 한 칸만 비어 있다

```
pixel source            time encoding T0 (0–48)      time encoding T1 (120–168)
W00 pixels 0–48         INVALID  = Trigger arm A      VALID = Trigger arm D
W05 pixels 120–168      미측정  ← 이번 사건(arm E)      VALID = SHADOW_V1 W05
```

기존 세 칸은 **재실행하지 않는다.** provenance 동일성만 실행 전에 확인한다.

```
Trigger A  trigger_v1_A.json      6de08ac56322a25edea8dd3294b039e8f942d5ec2ae63720b634074bcc2c0180
           trigger_v1_A_raw.txt   c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
Trigger D  trigger_v1_D.json      e406ae2520e63739d8758fa23590bbe0c443d6bc4f8a6512cee9f0de240a86b3
           trigger_v1_D_raw.txt   01496012501858fb0a6f3668194a5e936819d59efb588d5792680d55e591f1a5
SHADOW W05 shadow_v1_W05.json     ebcd438d8ccd91b248622a626c2932b26e2787a95e31aee8a332fc45a92ee241
           shadow_v1_W05_raw.txt  38caf8e6cfde38ce8da49bc6fcdd68e7c85454f8db828fdf27906843758564eb
원본 W00    shadow_v1_W00.json     c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e44daa074
           shadow_v1_W00_raw.txt  c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
```

## 2. Primary question 하나

```
동일한 0–48 absolute-time encoding에서, W00 초반 픽셀 대신 기존 W05 [120,168) 픽셀을
넣어도 degeneracy가 발생하는가?
```

## 3. normative authority 우선순위

```
① 이 사건 preregistration
② frozen model/prompt/runtime configuration
③ raw execution artifacts
④ prior trigger/forensic/repro/recovery 결과
⑤ PROJECT_OVERVIEW.md
```

## 4. arm E — 새 inference 1회

```
PIXELS        실제 120,122,…,166초 픽셀 24장 (0.5fps 격자 · 512×288)
              기존 SHADOW_V1 W05와 pixel-identical해야 한다
              (shadow_v1_W05.json의 frame_hashes 24개와 순서까지 일치)
PROMPT        start_sec=0.0 end_sec=48.0        (= Trigger arm A의 rendered prompt)
              rendered prompt hash가 Trigger A와 같아야 한다
METADATA      frames_indices = 0, 60, …, 1,380  (= t ∈ {0,2,…,46}에 round(t×rate))
              Trigger A의 indices와 같아야 한다
```

즉 `W05 pixels + P0M0`만 새로 측정한다.

## 5. 동결 (4개 이전 arm과 동일)

```
model            Qwen/Qwen3-VL-8B-Instruct · revision 0c351dd0…
prompt template  SAMPLING_DIAG_PROMPT_V2 (문구 불변 · hash 37f9588e…)
schema           start_sec · end_sec · actor · action · object_or_state
입력              video-only · English-only
sampling         0.5fps · 24프레임 · 512×288
런타임            bf16 · SDPA · default allocator · do_sample_frames False · do_resize False
생성              greedy · do_sample False · num_beams 1 ·
                 max_new_tokens 4096 · repetition_penalty 1.0
고정 metadata     total_num_frames 72,724 · fps 30.0000041251862 ·
                 duration 2424.186485 · width/height · video_backend pyav
runtime hash     cb43ffd357d771ff2923f2d3e0dec0f48f85bba660171cfc3832a298f4fef5aa
                 (Trigger arm 및 원본 W00과 동일해야 한다)
```

금지:

```
zero-duration 예시 수정 · prompt/schema 변경 · token cap 변경 ·
repetition penalty 변경 · subdivision 재개 · retry ·
Event extraction promotion · 기존 세 칸 재실행 · 다른 shift 추가
```

프롬프트의 `{"start_sec":0.0,"end_sec":0.0,…}` 예시는 **이번에도 건드리지 않는다** —
지금 바꾸면 time/content isolation과 prompt effect가 섞인다.

## 6. 실행

```
E ×1        총 1회 fresh-process inference
```

반복 측정하지 않는다. 실패해도 retry하지 않고 그 상태를 기록한다.

## 7. raw-before-parse

```
inference -> raw persist -> raw sha256 -> parse -> 구조 지표 -> 기술 분류
```

unterminated JSON salvage 금지. raw 수정 금지.

## 8. 기술 분류 (기존 어휘 · 게이트 변경 없음)

E는 `WINDOW_VALID` 또는 `WINDOW_INVALID`다. 최소 검사:

```
process complete · no OOM · no runtime failure · raw persisted ·
JSON parse · schema · language contract · generation cap ·
representation degeneracy · frame count 24 ·
pixel identity (W05 24 해시와 일치) ·
time encoding identity (rendered prompt hash·frames_indices가 Trigger A와 일치)
```

구조 지표(generated_tokens · finish_reason · raw_chars · completed_object_count ·
raw_unique_signature_count · zero_duration_count · positive_duration_count ·
max_signature_repeat · max_consecutive_repeat · first_repeat · json_complete)도 기록한다.

## 9. primary verdict 어휘 (사전 동결)

```
ABSOLUTE_TIME_CONFIGURATION_EFFECT_SUPPORTED
    E INVALID.
    → W00 pixels + T0 INVALID · W05 pixels + T0 INVALID ·
      W00 pixels + T1 VALID · W05 pixels + T1 VALID
    허용 진술: "이번 두 pixel set 범위에서 0–48 absolute-time configuration과
    degeneracy 상태의 연관이 관찰됨"

VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED
    E VALID.
    → W00 pixels + T0만 INVALID이고 나머지 세 칸 VALID
    허용 진술: "W00 초반 visual content 자체가 아니라 그것이 0–48 time encoding과
    결합될 때만 이번 failure가 관찰됨"

INCONCLUSIVE
    recovery efficacy와 무관한 실패 —
    pixel identity failure (W05 해시 불일치) · time encoding 불일치 ·
    runtime infrastructure failure · wrong frozen config · provenance failure ·
    기존 세 칸 산출물 변경 · 픽셀과 metadata 분리 불가
```

## 10. verdict 계산 우선순위 (결과 후 변경 금지)

```
1  INCONCLUSIVE          2  E의 기술 판정에 따른 위 두 어휘 중 하나
```

## 11. 해석 제한

어떤 결과가 나와도 금지:

```
0초 버그의 내부 원인을 증명했다 · Qwen 내부 메커니즘을 규명했다 ·
prompt가 잘못됐다 · metadata가 모델을 망가뜨린다 ·
"두 채널을 +120초로 옮기면 무조건 해결된다" · recovery 방법을 찾았다 ·
production Event extraction이 가능해졌다
```

측정 범위는 **pixel set 2개 · time encoding 2개 · shift 1개(+120초)**다. 다른 창·다른
영상·다른 shift로 일반화하지 않는다.

## 12. 최소 invariant (테스트로 고정)

```
새 arm 정확히 1개 (E)
E pixels = 120,122,…,166초 24장 · W05 frame_hashes와 순서까지 일치
E rendered prompt hash == Trigger A · frames_indices == Trigger A (0…1,380)
고정 metadata 6필드가 Trigger arm 값과 동일
prompt template hash 불변 · schema 불변 · max_new_tokens 4096 불변 ·
repetition_penalty 1.0 불변 · greedy 불변
raw-before-parse · retry 없음
기존 세 칸(Trigger A · Trigger D · SHADOW W05) 및 원본 W00 산출물 무변경 ·
기존 세 칸 재실행 없음 · SHADOW blind map 무변경 ·
현행 제출본 무변경 · official test 미개방
```

mutation suite RED 확인 + full suite 실행.

## 13. 실행 순서

```
1  prereg      2  prereg commit      3  implementation/tests commit
4  validator (기존 세 칸 해시·E 설계 확인)
5  self-check (모델 없이 processor만 — E 픽셀이 W05와 같고 marker가 T0인지)
6  E inference + raw persist          7  parse + 구조 audit
8  verdict 계산                        9  tests/mutations/full suite
10 clean tree                         11 result commit                12 STOP
```

## 14. 산출물 이름

```
runs/wvr_light_v1/visual_v1_E.json          arm record
runs/wvr_light_v1/visual_v1_E_raw.txt       raw 원문 (파싱 전 저장)
runs/wvr_light_v1/visual_v1_selfcheck.json  픽셀/시간 인코딩 실측
runs/wvr_light_v1/visual_v1_summary.json    2×2 표·verdict·교차 비교
runs/wvr_light_v1/visual_v1.log             배치 로그
```

## 15. 실행 후 상태 (결과와 무관하게 유지)

```
TRIGGER_ISOLATION_V1  CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED
recursive subdivision STOPPED / NOT SUFFICIENT
production Event extraction · Overview / Analysis / Conclusion   HOLD
0.5fps    PROVISIONAL WORKING DENSITY ONLY
현행 제출본  READ-ONLY      official test UNOPENED      M9 HOLD
prompt/schema mutation · token cap 변경 · 다른 shift · subdivision 재개 ·
retry/fallback 정책                                  리뷰어 승인 전 실행 금지
```

여기서 멈춘다.
