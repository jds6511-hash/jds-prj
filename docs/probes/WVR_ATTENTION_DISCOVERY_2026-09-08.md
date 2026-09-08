# C축 사전 조사 — FlashAttention 2 compatibility discovery (2026-09-08)

읽기 전용 조사다. **패키지 설치 없음 · 모델 추론 없음 · 모델 snapshot 무변경.**
(SDPA 커널 적격성 질의에서만 8토큰짜리 더미 텐서를 GPU에 올렸다 — 추론이 아니다.)

```
결론   C축(sdpa → flash_attention_2)의 전제가 약하다.
       현재 sdpa가 이미 flash 커널에 적격이다.
판정   FA2 설치는 기술적으로 가능하나 비용이 크고 이득 근거가 없다.
       더 싼 단일 변수 축(C′ allocator)이 실측으로 드러났다.
```

## 1. 런타임 실측

```
python                3.12.13
torch                 2.13.0+cu130      (cuda_runtime 13.0 · cudnn 92000)
transformers          5.14.1
GPU                   RTX 4090 · compute capability (8, 9) · driver 595.84
flash_attn 설치        False
xformers 설치          False
kernels 설치           False             (triton 3.7.1 · accelerate 1.14.0 있음)
is_flash_attn_2_available()   False
```

```
nvcc                  /usr/local/cuda/bin/nvcc → CUDA 12.8 (cuda_12.8.r12.8)
설치된 toolkit         11.1 · 11.2 · 11.8 · 12 · 12.3 · 12.4 · 12.5 · 12.8
CUDA 13 toolkit        없음              ← torch는 cu130으로 빌드됐다
CUDA_HOME              비어 있음
g++ / gcc             11.4.0
코어 / RAM             8 / 62 GiB
PyPI flash-attn        최신 2.8.3.post1 (sdist 빌드 전제) · kernels 0.16.1
```

## 2. transformers 쪽 지원 여부

```
Qwen3VLForConditionalGeneration._supports_flash_attn    True
                                _supports_sdpa          True
                                _supports_flex_attn     False
modeling_qwen3_vl 안의 dispatch  ALL_ATTENTION_FUNCTIONS (구현 비의존 경로)
```

즉 모델 클래스는 FA2 경로를 **지원한다**. 막는 것은 모델이 아니라 빌드 환경이다.

## 3. 왜 C축의 전제가 약한가

`torch.backends.cuda.can_use_flash_attention`을 이 GPU·dtype·차원으로 질의한 결과다.

```
bf16 · heads 32 · head_dim 128     flash True   ·  mem_efficient True
bf16 · heads 16 · head_dim 128     flash True   ·  mem_efficient True
flash_sdp_enabled                  True
```

Qwen3-VL-8B 텍스트부는 `layers 36 · heads 32 · kv_heads 8 · head_dim 128 ·
hidden 4096`이다. **이 형상은 sdpa에서 flash 커널에 적격이다.** 따라서 C01이
쓴 `sdpa`가 이미 flash 커널로 내려갔을 가능성이 높고, `flash_attention_2`로
바꿔도 attention 자체의 메모리가 줄어들 여지는 크지 않다.

**단, "C01이 실제로 flash 커널을 탔다"고 단정하지는 않는다** — 적격성만 쟀고,
실행 중 dispatch 로그를 남기지 않았다. 확인하려면 별도 계측이 필요하다.

## 4. 그러면 무엇이 메모리를 먹었나 (C01 실측 + 계산)

```
가중치 (실측 post_load)                        16.93 GiB
KV cache (계산) 36×8×128×2×2 = 144.0 KiB/token
                × 23,463 token                 3.22 GiB
─────────────────────────────────────────────────────────
합                                             20.15 GiB
peak_vram_allocated (실측)                     21.38 GiB
차이 = vision tower·prefill 활성값 (추정)       약 1,254 MiB
```

```
peak_reserved − peak_allocated                 1,569.9 MiB   ← 단편화 여유
실패 시점 부족분 (550.00 − 108.75)               441.25 MiB
device 총량 − device_peak_used                   591.9 MiB
```

**단편화로 묶여 있던 양(1,569.9 MiB)이 부족분(441.25 MiB)보다 크다.** 실패
메시지도 그 시점에 "2.44 GiB reserved but unallocated"라고 적었다.

계산 항목은 계산이라고 표시했다 — KV·활성값은 실측이 아니라 형상에서 낸 값이다.

## 5. 축 재정렬 제안

```
C′  allocator 설정만 바꾼다                   PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    변경 범위  환경변수 1개. 모델·표집·프롬프트·토큰 전부 C01과 동일
    근거      단편화 여유 1,569.9 MiB > 부족분 441.25 MiB (실측)
    비용      설치 없음 · 실행 2~3분
    한계      단편화가 줄어도 뒤에 더 높은 peak가 있으면 여전히 OOM이다

C   flash_attention_2                          설치 필요
    걸림돌    torch가 cu130인데 시스템 nvcc는 12.8뿐이다. PyPI에 이 조합의
             prebuilt wheel이 있을 가능성이 낮아 sdist 빌드가 되는데, 8코어에서
             flash-attn 소스 빌드는 통상 1~3시간이고 실패 위험이 있다
    대안      `kernels`(0.16.1) + `kernels-community/flash-attn` — 빌드 없이
             prebuilt 커널을 받는 경로. 다만 이것도 설치 사건이다
    이득 근거  §3대로 약하다

B   표집 축소                                   시간 정보 밀도를 낮춘다
    fps 0.5 → 0.25면 token 21,600 → 10,800, KV 3.22 → 1.61 GiB
    (계산이다. 의미 손실 여부는 평가하지 않았다)

D   양자화                                      가중치 16.93 GiB가 지배항이다
    8bit면 절반 수준. precision이 바뀌므로 품질 판단이 따로 필요하다

A   chunk 축소                                  경계 문제가 커진다. 마지막
```

**권장: C′ → (필요하면) C → B → D → A.** C′는 사전등록의 단일 변수 규율에 가장
잘 맞는다 — 환경변수 하나만 다르고 나머지가 C01과 완전히 동일하다.

## 6. 무변경 확인

```
Qwen3-VL-8B snapshot   0c351dd01ed87e9c1b53cbc748cba10e6187ff3b  존재
캐시 크기               17,545,956,297 B
설치·업그레이드          없음
추론                    없음
```

## 7. 주장하지 않는 것

```
FA2가 도움이 안 된다                — 재지 않았다. 적격성만 봤다
C01이 flash 커널을 탔다             — dispatch를 계측하지 않았다
C′면 통과한다                       — 단편화 회수가 곧 완주는 아니다
FA2 빌드가 불가능하다               — 어렵다는 것이고, 시도하지 않았다
```
