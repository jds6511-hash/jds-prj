# 사전등록 — WVR_CAPACITY_ALLOC_V1 (2026-09-08)

**이 문서는 결과를 보기 전에 쓴다.** 실행 후 파라미터·게이트·성공 문구를 고치지 않는다.
고치려면 새 사전등록 사건이다.

```
승인 범위    A0 current-idle default control   1회
            A1 expandable_segments treatment  A0 == CAPACITY_FAIL일 때만 1회
HOLD        flash-attn 설치 · 표집 축소 · 양자화 · chunk 축소 ·
            event extraction · STT diagnostic · submission promotion
```

이번 사건의 질문은 두 단계다. **순서를 바꾸지 않는다.**

```
① 지금처럼 더 깨끗해진 GPU에서 default allocator로도 같은 C01 workload가 통과하는가
② (①이 실패할 때만) allocator 설정이 capacity behavior를 바꾸는가
```

## 1. historical C01 — 역사적 baseline (재해석·재실행 금지)

`runs/wvr_light_v1/capacity_C01.json` (commit `23acb16`). 이 결과는 **덮어쓰지
않고 재해석하지 않는다.**

```
model                Qwen/Qwen3-VL-8B-Instruct · snapshot 0c351dd01ed87e9c1…
dtype / attn         bfloat16 / sdpa            quantization none · offload none
chunk                C01 0.0–600.0초            frames 300 (요청 300 · 전달 300)
sampling             0.5 fps · 512×288          do_sample_frames False · do_resize False
tokens               video 21,600 · input 23,463
baseline_vram        434.1 MiB                  post_load 17,336.1 MiB
peak allocated       21,890.1 MiB               peak reserved 23,460.0 MiB
device peak used     23,972.1 MiB / 24,564 MiB
OOM                  요청 550.00 MiB · 잔여 108.75 MiB
결과                 CAPACITY_FAIL (prefill)
```

## 2. 새로 발견된 confound

지금 서버는 유휴다 — GPU used 약 40 MiB · utilization 0% · compute process 0건 ·
system RAM available 약 61 GiB.

```
historical C01 baseline   434.1 MiB
현재 baseline             약 40 MiB
차이                      약 394 MiB
C01 부족분                441.25 MiB (550.00 − 108.75)
```

**차이가 부족분과 같은 크기대다.** 따라서 아래 비교는 **금지**한다.

```
historical C01 (default · baseline 434.1 · FAIL)
   vs
현재 A1 (expandable · baseline 약 40 · PASS/FAIL)
→ "expandable_segments 때문에 성공했다"는 주장 금지
```

allocator 효과의 primary 비교는 **A0 vs A1**뿐이다.

## 3. 무엇을 재지 않는가

```
event · chapter · highlight · overview · analysis · conclusion 품질
보고서 가독성 · 사실 정확성 · 현행 submission 대비 품질
```

`SEMANTIC_RESULT = NOT_EVALUATED`를 유지한다. 텍스트가 생성돼도 event extraction·
chapter 생성·evidence·submission 비교에 쓰지 않는다. raw text는 provenance·debug
목적으로만 보존한다.

## 4. arm 정의 (freeze)

```
A0  CURRENT-IDLE CONTROL
    allocator        default (PYTORCH_CUDA_ALLOC_CONF에 expandable_segments 없음)
    workload         C01과 동일
    실행 횟수         정확히 1회

A1  ALLOCATOR TREATMENT
    실행 조건         A0 == CAPACITY_FAIL인 경우에만
    allocator        PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    workload         A0와 완전히 동일
    실행 횟수         정확히 1회
```

A0가 통과하면 `A1 = NOT_RUN_BY_PREREG_RULE`로 기록하고 STOP한다.

## 5. frozen workload

A0·A1에서 아래가 전부 동일해야 한다. `scripts/wvr_capacity_alloc.py`는 workload를
`scripts/wvr_capacity_probe.py`의 `probe()`를 **그대로 호출**해 만든다 — 같은 코드
경로여야 "allocator만 달랐다"고 말할 수 있다.

```
model_id · snapshot        Qwen/Qwen3-VL-8B-Instruct · 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
dtype                      bfloat16          attn_implementation  sdpa
quantization               none              device               cuda:0
device_map                 사용하지 않음      CPU/disk offload      없음
video                      full_xekZO4n4QuE.mp4 (sha256 ea0e9f4866…)
video range                0.0–600.0초        effective duration   600.0초
sampling                   0.5 fps            requested frames     300
resolution                 512 × 288          do_sample_frames     False
do_resize                  False              video_metadata       필수
timestamps                 C01과 동일 결정적 시각 (0.0 … 598.0)
frame indices              C01과 동일 정책 (각 시각 이상의 첫 디코드 프레임)
prompt                     EVENT_PROMPT_V1 · hash a3c087d715b1dd49…
max_new_tokens             1024               do_sample            False
num_beams                  1                  repetition_penalty   1.0
retry                      0                  semantic evaluation  disabled
```

## 6. 변경 금지 축

```
10분 → 8분·5분 · 0.5 fps → 0.25 fps · 300프레임 축소 · 512×288 축소
bf16 → fp16 · bf16 → 8bit·4bit · sdpa → flash_attention_2
flash-attn·xformers·새 CUDA kernel 패키지 설치
CPU offload · device_map auto · max_new_tokens 축소 · prompt 축소
processor가 프레임을 조용히 자르는 것 · OOM 후 retry · OOM 후 다른 파라미터 자동 재시도
```

이번 사건의 **유일한 treatment 변수**는 `default allocator` vs
`expandable_segments allocator`다.

## 7. 독립 process 계약

A0·A1은 반드시 **서로 다른 fresh process**에서 돌린다. 한 process에서 A0를 돌린 뒤
환경변수만 바꿔 A1을 돌리는 것을 금지한다 — CUDA context가 초기화된 뒤에는 allocator
환경변수의 의미가 불명확해진다.

`PYTORCH_CUDA_ALLOC_CONF`는 **python 시작 전에 process environment에 있어야 한다.**
프로그램 안에서 torch import·CUDA 초기화 후 설정하는 것을 금지한다.
실행기는 진입 시 `torch.cuda.is_initialized()`가 False임을 확인한다.

## 8. GPU idle 전제조건

A0 직전·A1 직전에 각각 기록한다 — timestamp · GPU memory used/free ·
utilization · temperature · compute process 수 · 해당 프로세스 목록.

```
필요 조건   compute_process_count == 0
           다른 inference·training job 없음
           baseline VRAM을 정확히 기록
```

조건을 못 채우면 실행하지 않는다(`AllocError`).

## 8-1. 실행 직전 preflight (계측)

arm마다 실행 직전에 통째로 남긴다 — 나중에 "정말 allocator 말고 다른 게 달라진 게
없나"를 확인하기 위한 것이다.

```
GPU compute process 수 (0이어야 한다) · nvidia-smi baseline 전량
영상 sha256 · 모델 snapshot · git HEAD · tree clean 여부
실행 command 전체 · cwd · 기록 대상 환경변수
  (PYTORCH_CUDA_ALLOC_CONF · HF_HOME · CUDA_VISIBLE_DEVICES ·
   WVR_CODE_GIT_HEAD · LD_LIBRARY_PATH · CUDA_HOME)
```

## 9. baseline comparability gate

A1을 돌린 경우 `abs(A0 baseline_vram − A1 baseline_vram)`을 기록한다.

```
delta <= 128 MiB   → allocator 인과 비교 가능
delta >  128 MiB   → COMPARISON_INVALID
```

`COMPARISON_INVALID`면 A1 자체의 capacity PASS/FAIL은 기록하되 **"allocator 때문에
A0보다 개선됐다"는 인과 주장을 금지**한다.

이 128 MiB는 **과학적으로 도출한 임계값이 아니다.** 사전등록된 운영상 허용오차
(preregistered operational tolerance)이고, 실험 comparability를 지키기 위한
guard다. 129 MiB가 갑자기 물리적으로 비교 불가능해지는 것도 아니고 127 MiB가
완벽한 것도 아니다.

따라서 최종 보고에서는 게이트 판정만 쓰지 않고 **숫자를 그대로 함께 제시**한다.

```
A0 baseline = …    A1 baseline = …    delta = …    preregistered gate = 128 MiB
```

경계값 자체를 성능 주장처럼 해석하지 않는다. 결과를 본 뒤 값을 바꾸지 않는다.

## 9-1. workload identity gate — 설정이 아니라 실측이 같아야 한다

두 arm이 모두 실행됐다면 아래 **실측값**이 정확히 같아야 한다. 설정 문자열이
같다는 것만으로는 부족하다.

```
delivered_frame_count · frame_size · frame_times_first_last
frame_indices_first_last · video_token_count · input_token_count
requested_timestamps · prompt hash · generation config (dtype·attn·토큰·표집 포함)
```

하나라도 다르면 `WORKLOAD_MISMATCH`로 기록하고 **인과 비교를 하지 않는다**
(사건 판정은 `COMPARISON_INVALID`, 사유는 `comparison_invalid_reason`에 남긴다).
예: A0가 23,463 token인데 A1이 23,319 token이면 그것은 allocator 비교가 아니다.

## 9-2. CAPACITY_PASS의 정의 — prefill 통과가 아니다

C01은 prefill에서 죽었지만, A0·A1은 prefill을 넘긴 뒤 decode에서 다시 OOM이
날 수 있다. 그래서 PASS는 아래를 **전부** 만족해야 한다.

```
model.generate()가 정상 종료          return code 0
oom == False                          generation_completed == True
finish_reason ∈ {EOS, MAX_NEW_TOKENS} generated_token_count > 0
```

`generated_token_count`·`finish_reason`을 기록한다. semantic 품질은 보지 않지만
**추론이 끝까지 완주했는지는 capacity 결과의 일부**다. 완주하지 못한 PASS는
`IMPLEMENTATION_DEFECT`로 판정한다.

## 9-3. 단편화 진단 계측 (실험 변수 아님)

`allocated / reserved` 외에 PyTorch의 읽기 전용 메모리 통계를 남긴다. 계측 추가일
뿐이고 workload·treatment를 바꾸지 않는다.

```
allocated_bytes.all.peak · reserved_bytes.all.peak · requested_bytes.all.peak
active_bytes.all.peak · inactive_split_bytes.all.peak
num_alloc_retries · num_ooms
torch.cuda.memory_summary() 전문
```

## 10. 분기 규칙

```
Case A   A0 == CAPACITY_PASS
         → 즉시 STOP · A1 실행 금지 · A1 = NOT_RUN_BY_PREREG_RULE
         → 사건 판정 CONTROL_PASS_CONFUND_FOUND
         허용 기록: "현재 cleaner idle baseline에서 historical C01과 동일한
                    default-allocator workload가 capacity를 통과했다"
                   "historical C01 failure를 allocator fragmentation에
                    귀속할 수 없다"
         진단 해석까지 허용: "historical C01의 더 높은 baseline GPU occupancy가
                    실패에 기여했을 가능성이 있다"
         금지: 그것이 유일한 원인이었다는 주장
         금지: "C01은 당시 394 MiB가 더 쓰이고 있어서 실패했다"는 확정
         남은 후보 원인(어느 것도 배제되지 않았다):
           baseline VRAM 차이 · allocator 상태 · CUDA context 상태 ·
           driver·runtime 상태 · run-to-run 메모리 레이아웃 차이

Case B   A0 == CAPACITY_FAIL  → A1 진행
```

## 11. A1 판정

```
A1 == PASS 이고 comparability PASS   → WVR_CAPACITY_ALLOC_V1 = CAPACITY_PASS
    허용: "현재 동일 idle 조건에서 default allocator control은 OOM이었으나,
           expandable_segments treatment는 동일 workload를 통과했다"
          "allocator configuration이 capacity behavior를 개선했다"
    금지: "fragmentation이 C01 failure의 유일한 원인이었다"

A1 == FAIL                            → WVR_CAPACITY_ALLOC_V1 = CAPACITY_FAIL
    허용: "expandable_segments 단독 변경만으로는 동일 10분 · 300프레임 · BF16
           workload를 RTX 4090 24GB에서 수용하기에 충분하지 않았다"
    금지: "10분 Qwen3-VL은 4090에서 불가능하다" · "Qwen3-VL-8B는 4090에서 못 쓴다"
          — 표집·양자화·chunk 축을 시험하지 않았다
```

## 12. 기록할 capacity 지표

```
baseline_vram_used · baseline_vram_free · post_load_vram
peak_vram_allocated · peak_vram_reserved · device_peak_used
reserved_minus_allocated
requested_frame_count · delivered_frame_count · frame_size
frame_times_first_last · frame_indices_first_last
video_token_count · input_token_count · effective_video_duration
model_load_wall_sec · video_process_wall_sec · infer_wall_sec · total_wall_sec
oom(bool) · exception type · 정확한 OOM 메시지
실패 시 요청 할당 크기 · 실패 시 잔여 메모리 · return code
allocator_env_requested · allocator_env_observed
semantic_result = NOT_EVALUATED
```

## 13. allocator 활성 검증 — 환경변수 문자열로는 부족하다

`allocator_env_observed`만 보고 "적용됐다"고 하지 않는다. 아래를 모두 남긴다.

```
allocator_env_requested / allocator_env_observed      환경변수 문자열
torch.cuda.get_allocator_backend()                    allocator 구현
torch.cuda.memory_snapshot()의 segment별 is_expandable  ← 실제 적용 증거
segment_count · expandable_flags_head
로그 전문(stdout·stderr) 보존 + allocator 관련 warning·error 줄 추출
```

`is_expandable`은 실측으로 확인했다 — 환경변수를 준 process에서 True, 주지 않으면
False다. **A1에서 `expandable_segments_observed`가 False거나 allocator 관련
warning이 잡히면 `TREATMENT_NOT_APPLIED`로 기록하고, 사건 판정은
`IMPLEMENTATION_DEFECT`로 둔다** — 그 실행의 capacity PASS/FAIL을 해석하지 않는다.

## 14. historical C01의 역할

세 행을 함께 둔다. **Original C01과 A1의 직접 인과 비교는 하지 않는다.**

```
| arm          | baseline VRAM | allocator   | result |
| Original C01 | 434.1 MiB     | default     | FAIL   |
| A0           | 실측           | default     | ?      |
| A1           | 실측           | expandable  | ? / NOT RUN |
```

## 15. 산출물

```
runs/wvr_light_v1/capacity_alloc_A0.json · capacity_alloc_A0.log
(조건부) capacity_alloc_A1.json · capacity_alloc_A1.log
보고서   docs/probes/WVR_CAPACITY_ALLOC_V1_2026-09-08.md
```

**normative source는 JSON이다.** 문서 수치는 JSON에서 생성·검증하고, 문서와 JSON이
다르면 테스트가 실패한다.

## 16. 테스트 (P0)

```
WVR-A01 사전등록이 실행 전에 존재한다        WVR-A02 사전등록 커밋이 A0 실행보다 앞선다
WVR-A03 snapshot 무변경                    WVR-A04 dtype bf16 유지
WVR-A05 attention sdpa 유지                WVR-A06 quantization none 유지
WVR-A07 offload 비활성 유지                 WVR-A08 chunk 600초 유지
WVR-A09 fps 0.5 유지                       WVR-A10 frames 300 유지
WVR-A11 해상도 512×288 유지                 WVR-A12 timestamps 무변경
WVR-A13 video_metadata 필수                WVR-A14 prompt hash 무변경
WVR-A15 generation config 무변경           WVR-A16 A0 allocator는 default
WVR-A17 A1 allocator는 정확히 expandable_segments:True
WVR-A18 A0는 정확히 1회                    WVR-A19 A0가 통과하면 A1 실행 불가
WVR-A20 A1은 최대 1회                      WVR-A21 arm은 독립 process
WVR-A22 각 실행 전 GPU idle 기록            WVR-A23 각 실행 전 baseline VRAM 기록
WVR-A24 A1 실행 시 baseline delta 계산      WVR-A25 delta >128 MiB면 인과 비교 무효
WVR-A26 semantic 평가 비활성 유지           WVR-A27 capacity 지표 완비
WVR-A28 JSON이 normative                   WVR-A29 보고서가 JSON과 일치
WVR-A30 historical C01 artifact 무변경     WVR-A31 현행 submission 무변경
WVR-A32 A1 treatment 미적용이면 capacity 판정을 하지 않는다
WVR-A33 실측 workload가 다르면 인과 비교를 하지 않는다
WVR-A34 PASS는 generate 완주를 요구한다 (prefill 통과만으로는 PASS 아님)
WVR-A35 단편화 통계·memory_summary를 남긴다
WVR-A36 preflight(영상 sha·snapshot·git HEAD·command·env)를 남긴다
```

## 17. 뮤테이션 (전부 RED여야 한다)

```
M1  chunk 10분 → 8분              M2  fps 0.5 → 0.25
M3  frame 수 감소                  M4  해상도 감소
M5  양자화 사용                    M6  flash_attention_2 사용
M7  flash-attn 설치를 사건에 포함   M8  CPU·device_map offload 사용
M9  max_new_tokens 축소            M10 OOM 후 retry
M11 A0 PASS인데 A1 실행            M12 같은 CUDA process 재사용
M13 CUDA 초기화 뒤 allocator 설정   M14 A1 allocator env 누락
M15 GPU에 연산 프로세스가 있는데 실행 M16 delta >128 MiB인데 개선 주장
M17 Original C01과 A1만 비교해 효과 주장
M18 생성 텍스트를 semantic PASS로 사용
M19 event extraction 자동 시작     M20 현행 submission artifact 수정
M21 treatment 미적용인데 PASS/FAIL 판정
M22 실측 token 수가 다른데 allocator 효과 주장
M23 prefill만 통과했는데 PASS
```

## 18. 사건 판정 어휘

```
CAPACITY_PASS               A0 FAIL · A1 PASS · comparability PASS
CAPACITY_FAIL               A0 FAIL · A1 FAIL
CONTROL_PASS_CONFUND_FOUND  A0가 현재 idle 환경에서 통과 (A1 미실행)
COMPARISON_INVALID          A1 PASS이지만 baseline delta > 128 MiB
IMPLEMENTATION_DEFECT       OOM이 아닌 실패 · allocator 적용 검증 불가 ·
                            generate 미완주 · TREATMENT_NOT_APPLIED
```

arm 상태 어휘는 별도다 — `CAPACITY_PASS` · `CAPACITY_FAIL` ·
`IMPLEMENTATION_DEFECT` · `TREATMENT_NOT_APPLIED` · `NOT_RUN_BY_PREREG_RULE`.
`COMPARISON_INVALID`의 사유는 `WORKLOAD_MISMATCH` 또는
`BASELINE_DELTA_ABOVE_GATE`로 구분해 적는다.

## 19. 이후 분기

```
A0 PASS             STOP · 다음 단계는 review 필요
A0 FAIL + A1 PASS   STOP · event pipeline 진행 여부는 별도 결정
A0 FAIL + A1 FAIL   STOP · 그 자리에서 B축 실행 금지
                    다음 후보 WVR_CAPACITY_SAMPLING_V1 (fps 0.5 → 0.25 ·
                    10분·모델·해상도 유지) — 별도 사전등록 없이 실행 금지
flash-attn 설치      HOLD        quantization  HOLD        chunk 축소  HOLD
```

## 20. 기존 상태 (무변경)

```
R1-VAD0-QUALITY                  FROZEN
PRESENTATION_SYNTHESIS_V1        HOLD
STT_RETRANSCRIBE_V1              CLOSED / INCONCLUSIVE-DEGENERATE
STT_RETRANSCRIBE_DIAGNOSTIC_V1B  UNOPENED
query production changes         HOLD
WVR event extraction             HOLD
submission promotion             HOLD
official test                    UNOPENED        M9  HOLD
```
