# 사전등록 — WHOLE_VIDEO_REPORT_LIGHT_V1 (2026-09-08)

**이 문서는 결과를 보기 전에 쓴다.** 실행 후 파라미터·게이트·성공 문구를 고치지 않는다.
고치려면 새 사전등록 사건이다.

```
승인 범위    ① 이 사전등록 freeze·커밋
            ② 정확히 사전등록된 10분 capacity probe 1회 (C01 = 0.0–600.0초)
HOLD        event extraction 이후 전 단계 · candidate 생성 · SUBMISSION_PROMOTION
            PRESENTATION_SYNTHESIS_V1 · STT full 재전사 · query production 변경
            official test · M9
```

이번 사건에서 닫는 판정은 둘뿐이다.

```
MODEL_LOAD        Qwen3-VL-8B-Instruct가 이 라이브러리 조합에서 로드되는가
10MIN_CAPACITY    사전등록된 표집으로 10분 chunk 1개가 4090 24GB에서 추론되는가
```

## 1. 지금 상태

```
ENVIRONMENT_DISCOVERY     PASS   (torch 2.13.0+cu130 · transformers 5.14.1 · av 18.0.0)
MODEL_CACHE_AVAILABLE     PASS   (17G · snapshot 0c351dd0…)
MODEL_LOAD_COMPATIBILITY  UNVERIFIED
10MIN_CAPACITY            UNOPENED
```

`transformers 5.14.1`에 `Qwen3VLForConditionalGeneration`·`Qwen3VLProcessor`가
존재하는 것까지만 확인했다(클래스 유무). **실제 로드·processor·video 경로가
동작하는지는 probe에서 판정한다.**

## 2. 무엇을 재지 않는가

capacity probe는 의미 평가와 분리한다. 아래는 이번 사건에서 **판정하지 않는다.**

```
보고서 품질 · event 품질 · chapter 품질 · semantic correctness
프롬프트 적절성 · 다른 VLM과의 비교 · 기존 파이프라인과의 우열
```

probe가 만든 텍스트는 **event evidence로 재사용하지 않는다.** 용량 측정의
부산물이고, 파이프라인 산출물이 아니다(`SEMANTIC_RESULT = NOT_EVALUATED`).

## 3. 대상 영상 (freeze)

```
source_url        https://www.youtube.com/watch?v=xekZO4n4QuE
video_id          full_xekZO4n4QuE
file_sha256       ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
size              842,711,863 B
container/codec   mp4 / vp9
resolution        1920×1080          r_frame_rate 30/1
duration          2424.186485초 (40.4분)      nb_frames 72,724
```

## 4. 모델·런타임 (freeze)

```
model_id                  Qwen/Qwen3-VL-8B-Instruct
model_revision            0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
processor_revision        0c351dd01ed87e9c1b53cbc748cba10e6187ff3b   (동일 snapshot)
dtype                     bfloat16
quantization              none
device                    cuda:0                (단일 GPU · 명시 .to())
device_map                사용하지 않는다
max_memory / offload      설정하지 않는다
attn_implementation       sdpa
```

`device_map="auto"`를 쓰지 않는 이유는 규율이다 — accelerate가 CPU·디스크로
offload하면 24GB를 넘는 구성이 조용히 통과하고 capacity 판정이 무의미해진다.
실행 후 manifest에 **모든 파라미터가 cuda에 있는지**(`offloaded_params == 0`) 적는다.

resolved 값(`torch.__version__`·`transformers.__version__`·실제 dtype·실제
attn 구현·snapshot 경로)은 요청값과 **따로** 기록한다.

## 5. 청킹 (freeze)

```
chunk_length_sec   600.0
overlap_sec        120.0
stride_sec         480.0
꼬리 규칙          앞 chunk에 완전히 덮이는 꼬리 chunk는 만들지 않는다
```

이 영상(2424.186초)에 적용한 결정적 계획이다. `src/wvr_contract.chunk_plan`이 낸다.

```
C01   0.0    – 600.0      300 프레임
C02   480.0  – 1080.0     300
C03   960.0  – 1560.0     300
C04   1440.0 – 2040.0     300
C05   1920.0 – 2424.186   253
overlap pair   C01·C02 / C02·C03 / C03·C04 / C04·C05   각 120.0초 (마지막 120.0초)
```

**이번 probe 대상은 C01 = 0.0–600.0초 하나다.**

## 6. 프레임 표집 (freeze)

"10분 성공"만 적으면 재현 가능한 capacity 결과가 아니다 — 0.5 fps와 2 fps는
VRAM 조건이 전혀 다르다. 그래서 표집을 전부 고정한다.

```
chunk_fps            0.5          (2.0초마다 1프레임)
sparse_fps           0.05         (20.0초마다 1프레임 · 전체 영상 122프레임)
표집 시각            start + k/fps, k=0,1,…  (end 이전까지 · 반올림 소수 3자리)
프레임 선택          각 시각 이상(>=)의 첫 디코드 프레임
resize               512 × 288    (32의 배수 · 정확히 16:9)
resample             bicubic (PIL)
do_sample_frames     False        (processor가 다시 표집하지 않는다)
do_resize            False        (processor가 다시 리사이즈하지 않는다)
chunk_max_frames     300          (상한 초과는 예외 · 조용히 잘라내지 않는다)
sparse_max_frames    128
decoder              PyAV 18.0.0  (stream 0 · keyframe seek 후 순차 디코드)
video_metadata       fps=30.0 · frames_indices=원본 프레임 번호 · duration=2424.186485
                     (Qwen3-VL은 timestamp 정렬에 metadata를 요구한다. 없으면
                      fps=24를 가정해 시각이 어긋난다 — 넘기지 않는 것을 금지한다)
```

프레임을 파이프라인이 직접 뽑아 processor에 넘긴다. **영상을 재인코딩하지 않는다** —
재인코딩은 모델이 보는 픽셀을 바꾼다.

processor 실측 격자는 `patch_size=16 · merge_size=2 · temporal_patch_size=2`다.
즉 토큰 하나가 32×32 픽셀 × 2프레임을 덮는다. 프레임 크기를 32의 배수로 잡은 이유가
이것이고, 512×288은 1920×1080과 정확히 같은 16:9다.

사전 계산(참고, 판정 아님): 512×288은 프레임당 (512/32)×(288/32) = 144 토큰이고,
temporal patch 2로 300프레임 → 150 × 144 = 약 21,600 video token이다.
**실측 토큰 수는 probe가 기록한다** — 이 계산을 결과로 쓰지 않는다.

## 7. 생성 파라미터 (freeze)

```
do_sample            False
num_beams            1
temperature          전달하지 않는다 (do_sample=False)
top_p / top_k        전달하지 않는다
repetition_penalty   1.0
max_new_tokens       1024
```

probe는 **`EVENT_PROMPT_V1`을 그대로** 쓴다(토큰 부하가 본 파이프라인과 같아야
capacity 측정이 의미 있다). 출력은 §2에 따라 의미 평가하지 않는다.

## 8. 생성 계약 8종 (freeze)

`src/wvr_prompts.py`에 본문이 있고, 아래 sha256과 일치해야 한다
(`tests/test_wvr_contract.py`가 이 표와 모듈을 대조한다).

```
SPARSE_GLOBAL_PROMPT_V1    30595746f4a9db7b727cdd468f752e2cc49b35aa021ea8cb4fd2ab17615146ea
EVENT_PROMPT_V1            a3c087d715b1dd4914d670dbb254e5bdb012e5fcc17314ee95c7abdf8ea3a303
EVENT_MERGE_PROMPT_V1      75ec306ae705e1c2ff4a45753638b4c955c275ced2409d986e33dbb4bd122e22
CHAPTER_PROMPT_V1          e9eab9cc2b960711914a77a5cbe117fc7608a7234ab4282737d6cd1ee36c53ee
HIGHLIGHT_PROMPT_V1        98a3371c8ab60b6dbc50e0f0f9f893c92972404f8fa720494840cf6f19d2baa4
OVERVIEW_PROMPT_V1         aa8bcb8cafa84d3e951882e208e3f9a4b21db91ed4b6e616fe7595982feb0907
ANALYSIS_PROMPT_V1         4568e1e9bec6e3a4c989bc17ca73a04940d16a8d7f6d9607f61dd935d6b14893
CONCLUSION_PROMPT_V1       90e7ab949180df1d3d9a623da86942f953ed6c853e73ab642cd7a48a94209fe7
```

계약은 **8개**다. `Sparse Whole-Video Pass`도 Qwen3-VL이 생성하므로 별도 계약을
가진다(deterministic processor가 아니다).

프레임을 입력으로 받는 계약은 둘뿐이다 — `SPARSE_GLOBAL_PROMPT_V1`·`EVENT_PROMPT_V1`.
나머지 여섯은 앞 단계의 **텍스트만** 받는다(정보는 앞으로만 흐른다).

## 9. 입력 정책 — VIDEO ONLY

영상 이해 단계(`SPARSE_GLOBAL`·`EVENT`)에 아래를 넣지 않는다. 키 이름 기준으로
`wvr_contract.assert_video_only_inputs`가 막는다.

```
raw STT · sanitized STT · stt_utterances · stt_transcript
기존 episode summary · aar_canonical · 기존 report · 현행 제출본 hwpx
사람이 쓴 보고서 · YouTube 제목·설명 · 수동 주석 · 기존 caption
```

기존 1분 canonical episode(41개)는 **폐기하지 않는다.** 검색·증거·검증 단위로
그대로 남고, 이 track은 보고서 생성 경로만 바꾼다.

## 10. capacity probe가 기록할 값

```
baseline_vram_mib          모델 로드 전
post_load_vram_mib         로드 직후
peak_vram_mib              torch.cuda.max_memory_allocated / reserved 둘 다
requested_timestamps       300
delivered_frame_count      실측
frame_size                 실측 (w×h)
input_token_count          processor 출력 실측
video_token_count          실측 (vision 토큰 수)
output_token_count          실측
effective_video_duration    600.0
load_wall_sec / infer_wall_sec / total_wall_sec
return_code · oom (bool) · exception 유형
offloaded_params            0이어야 한다
resolved_*                  torch·transformers·dtype·attn·snapshot 경로
code_git_head · config sha256
```

수치는 UTF-8 JSON으로 남긴다(`runs/wvr_light_v1/capacity_C01.json`).
콘솔은 cp949로 깨지므로 판정에 쓰지 않는다.

## 11. 판정 어휘

```
PASS                  MODEL_LOAD PASS · VIDEO_PROCESS PASS · 10MIN_INFERENCE PASS
CAPACITY_FAIL         사전등록된 구성에서 OOM
IMPLEMENTATION_DEFECT OOM이 아닌 실패 (API 불일치·processor 오류·디코드 실패 등)
```

```
사전등록된 10분 구성
      ↓
OOM
      ↓
CAPACITY_FAIL 기록
      ↓
STOP

동일 사건에서 8분·5분으로 자동 재시도 금지
fps·해상도·max_new_tokens를 낮춰 성공시키는 것도 같은 금지에 해당한다
```

길이나 표집을 줄여 성공시키는 순간 capacity characterization과 parameter tuning이
섞인다. 줄인 구성으로 재시도하려면 **새 사전등록 사건**이다.

`IMPLEMENTATION_DEFECT`는 capacity 판정이 아니다 — 코드를 고쳐 다시 돌릴 수 있고,
그때 capacity 파라미터는 그대로 둔다.

## 12. 이후 단계 (이번 사건에서 실행하지 않음)

capacity가 닫힌 뒤의 순서만 미리 적어 둔다. 각 단계는 실행 전 별도 승인이다.

```
VIDEO
  ↓ SPARSE_GLOBAL      전체 영상 sparse pass
  ↓ EVENT              chunk별 사건 추출 (chunk 간 정보 전달 없음)
  ↓ EVENT_MERGE        overlap 구간 통합
  ↓ CHAPTER            의미 장
  ↓ HIGHLIGHT          대표 구간
  ↓ OVERVIEW / ANALYSIS / CONCLUSION     각각 독립 pass
  ↓ CLAIM_VERIFICATION 근거 없는 주장은 렌더하지 않는다
  ↓ report.hwpx        통합 1개 (section별 파일 분리 금지)
```

```
한 번에 보고서 전체를 생성하는 호출은 만들지 않는다
정보는 앞으로만 흐른다 (뒤 단계 결과를 앞 단계 입력에 넣지 않는다)
단계 실패는 명시 상태로 남긴다: OK · PARSE_FAILURE · CONTRACT_VIOLATION ·
                              CAPACITY_FAIL · RUNTIME_FAILURE
concat·retry·chunk 축소·다른 모델·STT 대체 fallback은 존재하지 않는다
모든 텍스트 계층에 output_quality_v1을 적용한다
단계별 raw 출력을 전량 저장한다
```

## 13. 기존 자산 상태 (무변경)

```
R1-VAD0-QUALITY                  FROZEN — hwpx 5732075871fd… 무변경
                                 tag submission-quality-2026-09-08
rollback                         4e10aaab… · f874f643…
PRESENTATION_SYNTHESIS_V1        HOLD / superseded-by-shadow-probe
STT_RETRANSCRIBE_V1              CLOSED / INCONCLUSIVE-DEGENERATE
STT_RETRANSCRIBE_DIAGNOSTIC_V1B  UNOPENED
QUERY PRODUCTION CHANGE          HOLD
OFFICIAL TEST                    UNOPENED
M9                               HOLD
SUBMISSION_PROMOTION             HOLD
```

## 14. 주장하지 않는 것

```
Qwen3-VL-8B이 현행 경로보다 낫다 — 재지 않았다
10분이 최적 chunk다 — 최적화를 하지 않았다. 사전등록된 하나의 값이다
0.5 fps가 충분하다 — 의미 평가를 하지 않았다
probe 출력이 이 영상의 사건이다 — capacity 부산물이고 evidence가 아니다
```
