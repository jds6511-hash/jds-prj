# 사전등록 — WVR_CAPACITY_SAMPLING_V1 (2026-09-08)

**이 문서는 결과를 보기 전에 쓴다.** 실행 후 파라미터·게이트·성공 문구를 고치지 않는다.
고치려면 새 사전등록 사건이다.

```
승인 범위    B arm 1회 — fps 0.5 → 0.25 (150프레임) · allocator default
HOLD        flash-attn 설치 · 양자화 · chunk 축소 · 해상도 축소 ·
            event extraction · semantic 평가 · STT diagnostic · submission promotion
```

이번 사건의 질문은 하나다.

```
같은 10분 · 같은 모델 · 같은 해상도에서 시간 표집만 절반으로 줄이면
4090 24GB에 들어가는가
```

## 1. parent control — A0 (재실행하지 않는다)

`runs/wvr_light_v1/capacity_alloc_A0.json` (commit `66b2fe1`). 이미 같은 조건에서
측정됐으므로 control을 다시 돌리지 않는다.

```
allocator     default                    fps 0.5 · 300프레임 · 512×288
tokens        video 21,600 · input 23,463
baseline      434.1 MiB                  post_load 17,336.1 MiB
peak          allocated 21,890.1 / reserved 23,460.0 / device 23,972.1 MiB
OOM           요청 550.00 · 잔여 108.75 → 부족 441.25 MiB
결과           CAPACITY_FAIL (prefill · generate 미완주)
```

A1(expandable_segments)도 FAIL이었고 그 사건은 CLOSED다
(`docs/probes/WVR_CAPACITY_ALLOC_V1_2026-09-08.md`).

## 2. 유일한 변경

```
fps            0.5 → 0.25
frames         300 → 150
timestamps     0, 4, 8, …, 596  (구간 시작에서 4.0초 간격 · 결정적)
```

**allocator는 default로 되돌린다.** A1의 treatment를 물려받지 않는다 — expandable과
sampling을 같이 바꾸면 무엇이 통과시켰는지 분리할 수 없다.

```
parent control   default allocator · 0.5 fps  → FAIL
B treatment      default allocator · 0.25 fps → ?
```

## 3. 그대로 두는 것 (freeze)

```
model_id · snapshot      Qwen/Qwen3-VL-8B-Instruct · 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
dtype                    bfloat16          attn_implementation   sdpa
quantization             none              device                cuda:0
device_map               사용하지 않음      CPU/disk offload       없음
allocator                default (PYTORCH_CUDA_ALLOC_CONF에 expandable_segments 없음)
video                    full_xekZO4n4QuE.mp4 (sha256 ea0e9f4866…)
video range              0.0–600.0초        effective duration    600.0초
resolution               512 × 288          do_sample_frames      False
do_resize                False              video_metadata        필수
prompt                   EVENT_PROMPT_V1 · hash a3c087d715b1dd49…
max_new_tokens           1024               do_sample             False
num_beams                1                  repetition_penalty    1.0
retry                    0                  semantic evaluation   disabled
```

**해상도는 이 사건에서 바꾸지 않는다.** 앞서 후보로 적었던 `384×216`은 잘못이다 —
`216 / 32 = 6.75`로 processor의 32픽셀 격자(patch 16 × merge 2)를 만족하지 않는다.
그 문구는 `docs/probes/WVR_LIGHT_V1_CAPACITY_C01_2026-09-08.md`에서 정정했다.

## 4. 사전 계산 (판정 아님)

```
video token      150 / temporal 2 × 144  = 10,800   (control 21,600)
input token      텍스트·틀 1,863이 그대로라면 약 12,663
KV cache         144.0 KiB/token × 12,663 ≈ 1.74 GiB   (control 3.22 GiB)
절감              약 1.48 GiB
```

**실측은 probe가 기록한다.** 이 계산을 결과로 쓰지 않는다. vision·prefill 활성값도
줄어들 가능성이 있지만 그것은 재봐야 안다.

## 5. 단일 변경 게이트

control(A0)과 B에서 아래 밖의 차이가 있으면 `COMPARISON_INVALID`로 닫는다.

```
허용되는 차이   requested.chunk_fps
              표집·토큰 실측(프레임 수·시각·video/input token)
              메모리·시간 실측 · OOM 관련 값
그 밖의 차이   단일 변경 위반 (single_change_violations에 기록)
```

추가로 **표집이 실제로 줄었는지**(`delivered_frame_count < control` 그리고
`chunk_fps == 0.25`) 확인한다. 안 줄었으면 실험이 성립하지 않는다.

baseline VRAM은 `abs(control − B) <= 128 MiB`를 기록한다. 이 128 MiB는 앞 사건과
같은 **사전등록된 운영상 허용오차**이며 과학적 임계값이 아니다. 보고에는 원수치를
함께 적는다.

## 6. CAPACITY_PASS 정의 (앞 사건과 동일)

```
model.generate() 정상 종료 · return code 0 · oom False
generation_completed True · finish_reason ∈ {EOS, MAX_NEW_TOKENS}
generated_token_count > 0
```

prefill 통과만으로는 PASS가 아니다. 미완주 PASS는 `IMPLEMENTATION_DEFECT`다.

## 7. GPU idle · preflight (앞 사건과 동일)

```
compute_process_count == 0                 baseline VRAM 기록
영상 sha256 · snapshot · git HEAD · tree clean · command 전체 · 환경변수
allocator backend · is_expandable · 로그 전문 보존
```

`is_expandable`이 True로 관측되면 default arm이 아니다 — 그 경우 실행 자체를 막는다.

## 8. 기록할 지표

앞 사건과 같은 목록에 아래를 더한다.

```
parent_control(artifact · verdict · fps · 프레임 수 · input token · baseline)
expected_frames · expected_video_tokens (계산값임을 명시)
token_reduction(video·input 실측 전후와 차이)
single_change_violations · sampling_changed
baseline_delta_mib · comparability
```

## 9. 판정 어휘

```
CAPACITY_PASS          B가 완주
CAPACITY_FAIL          B가 OOM
COMPARISON_INVALID     단일 변경 위반 · 표집이 실제로 줄지 않음
IMPLEMENTATION_DEFECT  OOM이 아닌 실패 · 미완주 PASS · allocator 계약 위반
```

## 10. PASS해도 다음으로 넘어가지 않는다

**capacity와 의미 밀도는 다른 질문이다.**

```
capacity    150프레임이면 4090에 들어가는가
semantics   4초에 한 장으로 보고서에 필요한 사건을 충분히 포착하는가
```

B가 PASS해도 event extraction을 시작하지 않는다(`EVENT_EXTRACTION_APPROVED = False`).
다음은 별도 사건인 **semantic-density probe**이고, 그것도 별도 사전등록이다.

```
B capacity  PASS
   ↓
B semantic characterization  (0.25 fps에서 짧은 사건이 얼마나 보존되는가)
   ↓
그 뒤에야 Event Map → Chapter → Highlight → Report
```

**"0.25 fps가 충분하다"·"의미 손실이 없다"고 이번 사건에서 주장하지 않는다.**
0.5 → 0.25는 시간 정보 밀도를 절반으로 낮추는 변경이고, 짧은 동작을 놓칠 수 있다.

## 11. 금지

```
해상도 축소 · chunk 축소 · 양자화 · flash-attn 설치 · attn 구현 변경
expandable_segments 사용 · CPU·device_map offload · max_new_tokens 축소
OOM 후 retry · OOM 후 다른 파라미터 자동 재시도 · control 재실행
semantic 품질 판정 · event extraction 착수
```

## 12. 테스트

```
WVR-S01 사전등록이 실행 전에 커밋돼 있다
WVR-S02 fps는 0.25 · 프레임 150 · 시각 0,4,…,596
WVR-S03 해상도 512×288 동결 (32 격자 · 384×216은 무효임을 명시)
WVR-S04 allocator는 default — expandable이면 실행 거부
WVR-S05 parent control이 CAPACITY_FAIL이 아니면 실행 거부
WVR-S06 control 산출물이 없으면 실행 거부
WVR-S07 단일 변경 위반을 잡는다 (허용 목록 밖 차이)
WVR-S08 표집이 줄지 않으면 COMPARISON_INVALID
WVR-S09 PASS는 generate 완주를 요구한다
WVR-S10 B arm은 정확히 1회
WVR-S11 GPU idle 기록 · 점유 시 실행 거부
WVR-S12 event extraction 승인 플래그가 False
WVR-S13 semantic 평가 비활성
WVR-S14 C01·A0·A1 artifact 무변경 · 현행 제출본 무변경
WVR-S15 보고서 수치가 JSON과 일치
WVR-S16 계산값(10,800·150)을 실측으로 표기하지 않는다
```

## 13. 뮤테이션 (전부 RED여야 한다)

```
N1  fps 0.25 → 0.5 (변경 없음)        N2  프레임 상한 150 → 300
N3  해상도 축소                        N4  allocator expandable 허용
N5  control PASS인데 실행              N6  control 없이 실행
N7  단일 변경 검사 제거                 N8  표집 감소 검사 제거
N9  prefill만으로 PASS                 N10 event extraction 승인
N11 semantic 평가 활성                 N12 dtype·attn·chunk 변경
N13 timestamps 간격 변경               N14 max_new_tokens 축소
```

## 14. 기존 상태 (무변경)

```
WVR_CAPACITY_ALLOC_V1            CLOSED / CAPACITY_FAIL (A0 FAIL · A1 FAIL)
WVR C01                          CLOSED / CAPACITY_FAIL
R1-VAD0-QUALITY                  FROZEN
PRESENTATION_SYNTHESIS_V1        HOLD
STT_RETRANSCRIBE_V1              CLOSED / INCONCLUSIVE-DEGENERATE
STT_RETRANSCRIBE_DIAGNOSTIC_V1B  UNOPENED
WVR event extraction             HOLD
submission promotion             HOLD
official test                    UNOPENED        M9  HOLD
```
