# WVR_CAPACITY_ALLOC_V1 결과 (2026-09-08 · A0 · A1)

사전등록: `docs/preregistration/WVR_CAPACITY_ALLOC_V1_2026-09-08.md`
(commit `82d86a7` — 실행 전 freeze) · 실행 commit `2f9a4f98dfbb`

```
A0  default allocator          CAPACITY_FAIL
A1  expandable_segments:True   CAPACITY_FAIL      treatment_applied True
사건 판정                       CAPACITY_FAIL
SEMANTIC_RESULT                NOT_EVALUATED
다음 단계                       STOP — B축은 별도 사전등록 없이 실행 금지
```

normative source는 JSON이다 — `runs/wvr_light_v1/capacity_alloc_A0.json` ·
`capacity_alloc_A1.json`. 이 문서의 수치는 그 파일에서 왔고
`tests/test_wvr_capacity_alloc.py`가 대조한다.

## 1. 세 행 비교

```
| arm          | baseline VRAM | allocator   | peak allocated | free at OOM | result |
| Original C01 | 434.1 MiB     | default     | 21,890.1 MiB   | 108.75 MiB  | FAIL   |
| A0           | 434.1 MiB     | default     | 21,890.1 MiB   | 108.75 MiB  | FAIL   |
| A1           | 434.1 MiB     | expandable  | 23,323.8 MiB   | 478.75 MiB  | FAIL   |
```

primary 비교는 **A0 vs A1**이다. Original C01과 A1을 직접 인과 비교하지 않는다.

## 2. 내가 제기한 confound은 존재하지 않았다 (정정)

직전에 "historical C01 baseline 434.1 MiB vs 현재 40 MiB → 약 394 MiB 차이"를
confound로 적었다. **그 비교 자체가 틀렸다.**

```
40 MiB      nvidia-smi · process 시작 전 (CUDA context 없음)
434.1 MiB   probe · CUDA context 초기화 후
```

측정 시점이 다른 두 값을 비교한 것이다. 실제로 A0의 baseline은
**434.1 MiB로 C01과 정확히 같았고**, A1도 434.1 MiB였다. 즉 그 394 MiB는 다른
job의 점유가 아니라 **CUDA context 자체의 오버헤드**다.

따라서 `CONTROL_PASS_CONFUND_FOUND` 분기는 발생하지 않았고, "C01 당시 GPU가 더
지저분해서 실패했다"는 가설은 **성립하지 않는다** — 같은 baseline에서 같은
지점에서 같은 값으로 실패했다.

## 3. A0 — current-idle default control

```
allocator env                 "" (설정 없음)      backend native
expandable_segments_observed  False               segment_count 268
GPU idle 직전                  used 40.0 MiB · free 24,041.0 MiB · util 0% · 프로세스 0
baseline                      434.1 MiB (free 23,646.8 MiB)
post_load                     17,336.1 MiB        offloaded_params 0
peak allocated / reserved     21,890.1 / 23,460.0 MiB
device peak used              23,972.1 MiB
reserved − allocated          1,569.9 MiB
frames / tokens               300 · 512×288 · video 21,600 · input 23,463
wall                          load 11.66초 · video 38.44초 · total 54.69초
OOM                           요청 550.00 MiB · 잔여 108.75 MiB (부족 441.25 MiB)
memory_stats                  inactive_split peak 3,199,726,592 B · retries 1 · ooms 1
결과                          CAPACITY_FAIL (prefill · generate 미완주)
```

**C01과 소수점까지 같다** — peak allocated·reserved·device peak·OOM 요청량·잔여량이
모두 일치했다. 같은 실패가 재현됐다.

## 4. A1 — expandable_segments treatment

```
allocator env requested       expandable_segments:True
allocator env observed        expandable_segments:True
expandable_segments_observed  True   ← memory_snapshot의 segment별 is_expandable
segment_count                 2      (A0은 268)
allocator warning             0건
GPU idle 직전                  used 40.0 MiB · 프로세스 0
baseline                      434.1 MiB
post_load                     17,176.1 MiB        offloaded_params 0
peak allocated / reserved     23,323.8 / 23,466.0 MiB
device peak used              23,602.1 MiB
reserved − allocated          142.2 MiB           (A0 1,569.9 MiB)
frames / tokens               300 · 512×288 · video 21,600 · input 23,463  (A0과 동일)
wall                          load 3.60초 · video 38.34초 · total 48.63초
OOM                           요청 550.00 MiB · 잔여 478.75 MiB (부족 71.25 MiB)
memory_stats                  inactive_split peak 0 B · retries 4 · ooms 1
결과                          CAPACITY_FAIL
```

## 5. treatment는 실제로 적용됐고, 효과도 관측됐다

환경변수 문자열만 본 것이 아니다.

```
is_expandable            A0 False(268 segment 전부) → A1 True(2 segment)
inactive_split peak      3,199,726,592 B → 0 B          단편화가 사라졌다
reserved − allocated     1,569.9 MiB → 142.2 MiB
peak allocated 여력       21,890.1 → 23,323.8 MiB        1,433.7 MiB 더 담았다
OOM 시점 잔여            108.75 → 478.75 MiB
부족분                   441.25 → 71.25 MiB
```

allocator 설정은 **capacity behavior를 실제로 개선했다.** 그런데도 같은 550.00 MiB
요청을 감당하지 못했다.

## 6. gate 판정 (원수치 함께)

```
A0 baseline = 434.1 MiB    A1 baseline = 434.1 MiB    delta = 0.0 MiB
preregistered gate = 128 MiB (운영상 허용오차 · 과학적 임계값 아님)
→ COMPARABLE

workload identity          차이 0건 (실측 프레임 300·512×288·시각 0.0~598.0 ·
                           frame index 0~17,940 · video 21,600 · input 23,463 · 프롬프트 hash)
treatment_applied          True        allocator warning 0건
generate 완주              A0 False · A1 False  → 두 arm 모두 PASS 자격 없음
```

## 7. 허용 문구 / 금지 문구

허용:

```
expandable_segments 단독 변경만으로는 동일 10분 · 300프레임 · BF16 workload를
RTX 4090 24GB에서 수용하기에 충분하지 않았다.
allocator 설정은 단편화를 제거하고 약 1.4 GiB를 더 담게 했지만, 부족분 71.25 MiB를
넘기지 못했다.
```

금지(쓰지 않는다):

```
10분 Qwen3-VL은 4090에서 불가능하다
Qwen3-VL-8B는 4090에서 못 쓴다
fragmentation이 C01 failure의 유일한 원인이었다
71.25 MiB만 더 확보하면 완주한다     ← 그 뒤 peak가 더 높을 수 있다.
                                    A1은 여전히 첫 forward에서 멈췄다
```

표집·양자화·chunk 축을 아직 시험하지 않았다.

## 8. 이후 분기 (사전등록 §19)

```
A0 FAIL + A1 FAIL   → STOP · 그 자리에서 B축 실행 금지
다음 후보            WVR_CAPACITY_SAMPLING_V1 (fps 0.5 → 0.25 · 10분·모델·해상도 유지)
                    별도 사전등록 없이 실행 금지
flash-attn 설치      HOLD    quantization  HOLD    chunk 축소  HOLD
```

C축(flash_attention_2)의 우선순위는 조사에서 이미 내려갔다 — sdpa가 이 형상에서
flash 커널에 적격이다(`docs/probes/WVR_ATTENTION_DISCOVERY_2026-09-08.md`).
게다가 이번 A1의 peak allocated 23,323.8 MiB는 **가중치 17.2 GiB + KV 3.2 GiB +
활성값**이 이미 24 GiB 벽에 닿았다는 뜻이라, attention 커널 교체로 메울 폭이
남아 있는지도 불확실하다.

## 9. 계측 한계 (기록)

```
allocator warning 탐지    "warn"·"error" 문자열 기준이라 PyTorch의 [W...] 접두
                        경고 줄은 잡지 못한다. 이번 A1 로그의
                        "expandable_segments: memory mapping failed with OOM"은
                        treatment 미적용 경고가 아니라 OOM 자체의 보고다
                        (오히려 expandable 경로가 동작한 증거다)
tree_clean               서버 실행 디렉터리에 .git이 없어 호출자가 넘긴 값이다
                        (`tree_clean_source: env`)
```

## 10. 상태 (무변경)

```
Original C01 artifact            무변경 (git diff 없음)
R1-VAD0-QUALITY                  FROZEN
PRESENTATION_SYNTHESIS_V1        HOLD
STT_RETRANSCRIBE_V1              CLOSED / INCONCLUSIVE-DEGENERATE
STT_RETRANSCRIBE_DIAGNOSTIC_V1B  UNOPENED
WVR event extraction             HOLD
submission promotion             HOLD
official test                    UNOPENED        M9  HOLD
```
