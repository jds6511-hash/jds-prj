# WVR_LIGHT_V1 capacity probe 결과 — C01 (2026-09-08)

사전등록: `docs/preregistration/WHOLE_VIDEO_REPORT_LIGHT_V1_2026-09-08.md`
(commit `d6153ed` — 실행 전 freeze) · 실행 commit `8bc3fd0666e4c6c2…`

```
MODEL_LOAD          PASS
VIDEO_PROCESS       PASS
10MIN_INFERENCE     CAPACITY_FAIL          ← OOM (prefill)
SEMANTIC_RESULT     NOT_EVALUATED
판정                CAPACITY_FAIL → STOP
```

사전등록된 구성에서 OOM이 났다. **chunk를 줄이거나 fps·해상도·max_new_tokens를
낮춰 다시 돌리지 않았다**(사전등록 §11). 다음 실행은 별도 사전등록 사건이다.

## 1. 실측

```
baseline_vram              434.1 MiB      (모델 로드 전)
post_load_vram          17,336.1 MiB      (가중치 bf16 · 로드 35.12초)
offloaded_params                 0        CPU·디스크 offload 없음
peak_vram_allocated     21,890.1 MiB
peak_vram_reserved      23,460.0 MiB
device_peak_used        23,972.1 MiB / 24,564 MiB
```

```
requested_timestamps           300        (0.0 … 598.0초 · 2.0초 간격)
delivered_frame_count          300        누락 0
frame_size                 512 × 288
frame_times_first_last     0.0 · 598.0    요청 시각과 일치
frame_indices_first_last     0 · 17,940   (17,940 / 30fps = 598.0초)
video_token_count           21,600        사전 계산과 정확히 일치
input_token_count           23,463        (video 21,600 + 텍스트·틀 1,863)
effective_video_duration     600.0초
total_wall_sec                78.96
```

```
실패 지점    model.generate 첫 forward (prefill)
예외         torch.OutOfMemoryError
메시지       "Tried to allocate 550.00 MiB. GPU 0 has a total capacity of
             23.52 GiB of which 108.75 MiB is free."
```

resolved: `torch 2.13.0+cu130` · `transformers 5.14.1` · `bfloat16` · `sdpa` ·
`cuda:0` · `patch_size 16 · merge_size 2 · temporal_patch_size 2` ·
`HF_HOME=/ssd/<SERVER_USER>/cache`

산출물: `runs/wvr_light_v1/capacity_C01.json` · `capacity_C01.log`

## 2. 무엇이 확인됐고 무엇이 안 됐나

```
확인됨   transformers 5.14.1 + torch 2.13.0+cu130에서 Qwen3-VL-8B-Instruct가
        bf16으로 로드된다 (17.3GB · offload 0)
확인됨   video 경로가 동작한다 — 사전 표집한 300프레임 + video_metadata를
        processor가 받아 21,600 video token으로 만들었다
확인됨   토큰 예산 산식이 맞다 (512×288 → 프레임당 144 · temporal 2 → 150×144)
안 됨    10분 chunk 1개의 추론. prefill에서 VRAM이 모자랐다
```

**남은 여유는 처음부터 좁았다** — 가중치 17.3GB를 올리고 나면 24GB 중 약 6.6GB가
남고, 23.5k 토큰 prefill의 활성값·KV가 그 안에 들어가지 못했다. 사전등록 시점에
계산해 둔 것은 KV 크기였고, **prefill 활성값(특히 attention 중간 텐서)을 넣지
않았다.** 그것이 이번 CAPACITY_FAIL의 실질 원인이다.

## 3. 주장하지 않는 것

```
10분 chunk가 원리적으로 불가능하다        — 이 구성 하나에서만 쟀다
Qwen3-VL-8B이 4090에 부적합하다           — 양자화·attention 구현·표집을 안 바꿔봤다
0.5 fps가 과하다 / 부족하다               — 의미 평가를 하지 않았다
현행 파이프라인보다 낫다·못하다            — 비교하지 않았다
```

probe는 텍스트를 만들지 못했으므로 `raw_output`이 없다. 애초에 있었더라도
event evidence로 쓰지 않는다(사전등록 §2).

## 4. 다음 사건에서 고를 수 있는 축 (지금 실행하지 않음)

각각 **capacity 파라미터를 바꾸는 일**이므로 별도 사전등록이 필요하고, 하나만
바꿔야 무엇이 효과를 냈는지 갈린다.

권장 순서는 **C → B → D → A**다.

```
C  attention 구현을 바꾼다                 flash-attn 2 설치 여부 미확인.
                                        prefill 중간 텐서를 줄이는 축이고,
                                        300프레임을 그대로 유지할 수 있다
B  프레임 표집을 줄인다                    fps 0.5 → 0.25 (300 → 150프레임), 또는
                                        512×288 → 384×216 (32의 배수 유지 필요)
D  가중치를 양자화한다                     8bit·4bit. 17.3GB → 절반 이하면 작업공간이
                                        6.6GB에서 크게 늘어난다. precision이 바뀐다
A  chunk 길이를 줄인다                    이번 사건에서 금지된 그 축이고, 잘게 나눌수록
                                        경계 문제가 커지므로 마지막에 둔다
E  더 큰 VRAM                             랩실에 4090 24GB 외 선택지가 있는지 미확인
```

**속도가 아니라 용량이 막았다.** 축의 성격은 이렇게 갈린다 — D는 precision을 바꾸고,
B는 **시간 정보 밀도를 낮춘다**(4초에 한 장이면 짧은 동작을 놓칠 수 있다), C는 계산
경로만 바꾼다. **B·C를 "정확도 손실 없는 축"이라고 쓰지 않는다** — 의미 평가를 하지
않았으므로 근거가 없다(2026-09-08 정정).

여유가 얼마나 모자랐는지도 적어 둔다 — 실패 시점에 필요한 추가 할당은 550.00 MiB,
남은 여유는 108.75 MiB였다. **다만 550 MiB를 확보하면 끝까지 돈다는 뜻은 아니다** —
그 뒤에 더 높은 peak가 있을 수 있고, 이번 실행은 첫 forward에서 멈췄다.

## 5. 상태 (무변경)

```
R1-VAD0-QUALITY                  FROZEN — hwpx 5732075871fd… 무변경
PRESENTATION_SYNTHESIS_V1        HOLD / superseded-by-shadow-probe
STT_RETRANSCRIBE_V1              CLOSED / INCONCLUSIVE-DEGENERATE
STT_RETRANSCRIBE_DIAGNOSTIC_V1B  UNOPENED
WVR event extraction 이후 단계     미실행 (capacity가 닫히지 않았다)
SUBMISSION_PROMOTION             HOLD
OFFICIAL TEST                    UNOPENED        M9  HOLD
```
