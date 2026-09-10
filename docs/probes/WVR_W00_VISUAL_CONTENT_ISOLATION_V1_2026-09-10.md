# WVR_W00_VISUAL_CONTENT_ISOLATION_V1 결과 (2026-09-10)

사전등록:
`docs/preregistration/WVR_W00_VISUAL_CONTENT_ISOLATION_V1_2026-09-10.md`
(commit `2024366` — GPU 실행 전 freeze) · 구현 `161227d` · 서버 RTX 4090

```
primary verdict   VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED   (reason E_VALID)
arm E             WINDOW_VALID — W05 [120,168) 픽셀 + T0(0–48) 시간 인코딩
blocker           없음 (self-check OK · 픽셀·시간 identity 통과 · frozen cell 무변경)
새 inference       1회 (기존 세 칸은 재실행하지 않았다)
```

## 2×2 표 (한 칸만 새로 측정)

```
pixel source            T0 (0–48)                     T1 (120–168)
W00 pixels 0–48         WINDOW_INVALID  trigger_v1_A   WINDOW_VALID  trigger_v1_D
W05 pixels 120–168      WINDOW_VALID    visual_v1_E    WINDOW_VALID  shadow_v1_W05
```

**네 칸 중 INVALID는 `W00 픽셀 × T0` 하나뿐이다.**

## A. provenance

```
prereg commit         2024366d021687e8e10516e2df8da2c22c0e661a
implementation        161227d5a8104c416de4303c3af1c06c3594d78b   (실행 commit)
video sha256          ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
model revision        0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt template hash  37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
rendered prompt hash  c936901940b8… (= Trigger arm A와 동일)
runtime config hash   cb43ffd357d771ff… (= Trigger arm · 원본 W00과 동일)
transformers          5.14.1 · do_sample_frames False · do_resize False
```

## B. arm E 입력

```
픽셀            실제 120,122,…,166초 24장 · 512×288
              기존 SHADOW_V1 W05의 frame_hashes 24개와 순서까지 일치
              pixel_values sha256 c200ea524221… (Trigger A의 860adccd…와 다름 = 픽셀이 실제로 바뀌었다)
prompt window  0.0 – 48.0            rendered prompt hash가 Trigger A와 일치
frames_indices 0, 60, …, 1,380       Trigger A의 indices와 일치
timestamp 마커  1.0 … 45.0            = T0 (M0 마커)
고정 metadata   duration 2424.186485 · total_num_frames 72,724 ·
              fps 30.0000041251862 · width/height · backend pyav (Trigger A와 동일)
입력 토큰        2,135 (video token 1,728) — Trigger A와 같은 값
```

GPU 사용 전 self-check(모델 없이 processor만) 8개 항목 전부 통과:
`pixels_match_w05` · `pixel_values_differ_from_trigger_A` · `markers_are_T0` ·
`rendered_prompt_matches_trigger_A` · `indices_match_trigger_A` ·
`pixel_times_are_120_to_166` · `decoded_indices_are_w05_range` · `pixel_count`.

## C. 출력 — 네 칸 구조 비교 (기존 세 칸은 읽기만)

```
                       X0T0 (A)        X0T1 (D)     X1T1 (W05)   X1T0 (E · 신규)
픽셀                    W00             W00          W05          W05
time encoding          T0              T1           T1           T0
status                 WINDOW_INVALID  VALID        VALID        VALID
generated tokens       4,096 (cap)     745          452          303
완성 object              95              16           10           7
raw unique signature   2               9            5            6
zero-duration          95              0            0            0
positive-duration      0               16           10           7
최대 signature 반복       48              6            —            2
JSON 완결                False           True         True         True
collapsed / unique     0 / 0           9 / 9        6 / 5        6 / 6
raw hash               c5e4f752…       01496012…    38caf8e6…    b4a30e0e…
```

arm E 출력 앞부분(참고 기록 · semantic 판정 아님):

```
0–3    person / grating / potato
3–7    person / grating / potato
7–11   person / mixing  / potato mixture
11–15  person / forming / potato balls …
```

E는 T0가 지시한 0–48 구간 안에 event를 넣었고(프롬프트 창을 따랐다), 실제 픽셀은
120–166초 장면이다. 시간 값과 픽셀 내용의 불일치 자체는 이번 설계의 조작이며 기술
게이트 항목이 아니다.

## D. primary verdict

```
VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED
reason    E_VALID
게이트      사전등록 §9·§10 그대로 — 우선순위 INCONCLUSIVE → E 판정.
          결과를 본 뒤 어휘·우선순위를 바꾸지 않았다.
허용 진술   "W00 초반 visual content 자체가 아니라 그것이 0–48 time encoding과
          결합될 때만 이번 failure가 관찰됨"
```

`ABSOLUTE_TIME_CONFIGURATION_EFFECT_SUPPORTED`는 **아니다** — 같은 T0 인코딩에서 픽셀만
W05로 바꾸자 VALID였다. 따라서 T0 인코딩 단독으로는 실패가 재현되지 않는다.

## E. 지금까지의 다섯 관측을 한 줄씩

```
W00 픽셀 × T0                          INVALID   (원본 W00 · repro 3/3 byte-identical)
W00 픽셀 × T1(prompt만)                 INVALID   (Trigger C — 빈 목록)
W00 픽셀 × T1(metadata만)               INVALID   (Trigger B — 단일 signature 반복)
W00 픽셀 × T1(양쪽)                      VALID     (Trigger D)
W05 픽셀 × T0                          VALID     (이번 arm E)
W05 픽셀 × T1                          VALID     (SHADOW W05)
```

즉 실패는 **W00 초반 픽셀과 0–48 시간 표현이 함께 있을 때만** 관측됐다. 어느 쪽 단독도
아니다.

## F. 의미 / 비의미

말하는 것:

```
같은 T0 시간 인코딩에서 픽셀만 W05로 바꾸면 유효한 출력이 나왔다 —
  0–48 time configuration 단독 효과로는 이번 실패가 설명되지 않는다
W00 초반 픽셀은 T1 인코딩에서 유효했다 (Trigger D) —
  그 픽셀 자체가 항상 실패를 만드는 것도 아니다
측정은 유효했다 — 픽셀은 W05와 해시 동일 · 시간 채널은 Trigger A와 동일 ·
  고정 metadata 6필드 동일 · 기존 세 칸 산출물 무변경 · 새 inference 1회
```

말하지 않는 것 (사전등록 §11):

```
0초 버그의 내부 원인을 증명했다 · Qwen 내부 메커니즘을 규명했다 ·
prompt가 잘못됐다 · metadata가 모델을 망가뜨린다 ·
"두 채널을 +120초로 옮기면 무조건 해결된다" · recovery 방법을 찾았다 ·
production Event extraction이 가능해졌다
```

측정 범위는 **pixel set 2개 · time encoding 2개 · shift 1개(+120초)**다. 다른 창·다른
영상·다른 shift로 일반화하지 않는다. 프롬프트의 zero-duration 예시는 이번에도 건드리지
않았으므로 그 요소와의 상호작용은 여전히 미측정이다.

## G. 검증

```
새 테스트   tests/test_wvr_visual_v1.py  WVR-P01~P33  33/33
뮤테이션    P-M1~P-M47 전부 RED (구멍 없음)
전체 스위트  4,801 passed · 2 skipped · 0 failed
clean tree · HEAD == origin/master
경계 확인   frozen cell 8개 무변경 — trigger_v1_A 6de08ac5·c5e4f752 ·
          trigger_v1_D e406ae25·01496012 · shadow_v1_W05 ebcd438d·38caf8e6 ·
          shadow_v1_W00 c8e65b74·c5e4f752
          기존 세 칸 재실행 없음 · SHADOW blind map 미접촉 ·
          현행 제출본 5732075871fd… 불변 · official test 미접촉
```

## H. 상태 (실행 후에도 유지)

```
WVR_W00_VISUAL_CONTENT_ISOLATION_V1  CLOSED / VISUAL_CONTENT_X_TIME_INTERACTION_SUPPORTED
TRIGGER_ISOLATION_V1  CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED (불변)
recursive subdivision  STOPPED / NOT SUFFICIENT
SUBDIVISION_RECOVERY FAIL · RECURSIVE FAIL · REPRO REPRODUCIBLE ·
FORENSIC MODEL_OUTPUT_DEGENERACY · SHADOW_V1 INCONCLUSIVE      전부 불변
original W00 WINDOW_INVALID 유지
production Event extraction · Overview / Analysis / Conclusion   HOLD
0.5fps    PROVISIONAL WORKING DENSITY ONLY
현행 제출본  READ-ONLY      official test UNOPENED      M9 HOLD
prompt/schema mutation(zero-duration 예시 포함) · token cap 변경 · 다른 shift ·
subdivision 재개 · retry/fallback 정책                리뷰어 승인 전 실행 금지
```

## I. 산출물

```
runs/wvr_light_v1/visual_v1_E.json          arm record (픽셀·시간 identity·판정)
runs/wvr_light_v1/visual_v1_E_raw.txt       raw 원문 (파싱 전 저장)
runs/wvr_light_v1/visual_v1_selfcheck.json  픽셀/시간 인코딩 실측
runs/wvr_light_v1/visual_v1_summary.json    2×2 표·verdict·교차 비교
runs/wvr_light_v1/visual_v1.log             배치 로그
src/wvr_visual_v1.py · scripts/wvr_visual_run.py ·
scripts/wvr_visual_summary.py · scripts/wvr_visual_selfcheck.py ·
scripts/wvr_visual_validate.py · scripts/wvr_visual_batch.sh ·
tests/test_wvr_visual_v1.py
```

여기서 멈춘다. 다음 설계는 리뷰어가 결정한다.
