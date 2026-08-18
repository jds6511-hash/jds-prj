# dev 정밀도 3-arm 동시점 배치 — 사전등록 (2026-08-18)

**이 문서는 결과를 본 뒤 고치지 않는다.** 이탈은 작업현황·결과 문서에 기록한다.

## 0. 이 배치가 답하는 것 — **채택 결정이 아니다**

이름을 `dev_precision_3arm`으로 둔다. **정밀도 장벽 하나를 닫는 실험**이다.

캡션 모델 상태는 **"탐색 종료, 채택 미완"**이다. model family는 `Qwen3-VL-4B`로
좁혀졌고 `P0`가 잠정 선호지만, 실제 배포 구성은 미확정이다(작업현황 §2-3).
남은 장벽 3개 중 이 배치가 닫는 것은 **2번(정밀도)** 하나뿐이다.

```
1. 표본 재사용 — AI Hub 1,086 두 번 사용. 새 표본 확증 필요   ← 이 배치와 무관
2. 정밀도     — 2×2는 전부 bf16, 배포는 6GB 노트북 4bit        ← 이 배치
3. I1 검출기 재설계 + A2                                      ← B단계 21건 남음
```

**이 배치 결과가 좋아도 캡션 모델 확정이 아니다.**

## 1. arm — 3개, 기존 키 그대로

| arm | 모델 키 × 프롬프트 | 역할 |
|---|---|---|
| `4B/P0/bf16` | `qwen3vl_4b` × P0 | 2×2 결과가 dev에서 재현되는가 |
| `4B/P0/4bit` | `qwen3vl_4b_q4` × P0 | **6GB 배포 경로의 실제 후보** |
| `3B/P0/4bit` | `qwen25_3b_4bit` × P0 | **동시점 대조군 — 현행 배포** |

`caption_model_sweep.py`의 기존 arm 정의를 쓴다. 새 캡션 코드를 만들지 않는다.

## 2. 주 판정 — caption-only MRR. **α가 들어가지 않는다**

α는 융합에서만 의미가 있으므로 주 판정에서 분리한다.

```
PRIMARY  (dev 96 질의, 캡션 단독 = α 미개입)
  A. 양자화 효과
     Δ_quant  = MRR_caption(4B/P0/4bit) − MRR_caption(4B/P0/bf16)

  B. 배포 교체 효과
     Δ_deploy = MRR_caption(4B/P0/4bit) − MRR_caption(3B/P0/4bit)

SECONDARY / calibration
  - 고정 α=0.5 융합 비교
  - dev α 곡선 (arm별)
  - τ 재조정
```

> **α·τ 결과는 PRIMARY의 정밀도 판정을 소급해서 바꾸지 않는다.**
> 그렇지 않으면 "4bit에서 모델 이득이 죽었는데 α를 새로 골라 살아난 점만 보고
> 채택"하는 새 선택 편향이 생긴다. calibration은 **별도 섹션**으로만 보고한다.

보고 형식: **point estimate + paired CI**(video 클러스터 부트스트랩, 질의를 영상으로
묶는다). dev 96·영상 3편의 검출 한계는 ±0.08 수준이므로 작은 효과는 애초에 검출되지
않는다 — **비유의를 "차이 없음"으로 쓰지 마라**(CLAUDE.md 판단기준).

## 3. 판정 구조 — **`p>0.05`를 동등성으로 쓰지 않는다**

비유의성은 동등성이 아니다. 그리고 **practical margin `δ`에 외부 근거가 없으므로
임의의 `δ`를 만들어 formal gate처럼 쓰지 않는다.**

이번 배치에서는 **point estimate + paired CI를 보고하고, "유사"를 formal branch로
쓰지 않는다.** dev 96은 확증용 새 표본이 아니므로 여기서 최종 adoption gate를
만들지 않는다(장벽 1번은 따로 남아 있다).

두 Δ의 **부호와 크기**로 다음 질문의 방향만 결정한다.

| Δ_quant | Δ_deploy | 뜻 |
|---|---|---|
| 손실 큼 | ≤ 0 | 4B의 검색 이득이 **bf16에서는 존재하지만 현 노트북 4bit 경로에서 보존되지 않는다** → 질문이 **서버 bf16 아키텍처 전환**으로 바뀐다 |
| 손실 작음 | > 0 | **노트북 4B 교체 경로 유지** → I1 B단계 → 새 표본 확증 |
| 손실 큼 | > 0 | 양자화 손실은 있으나 `3B/4bit`보다 여전히 우수 → **배포 후보 유지**, 비용·메모리는 별도 판단 |
| — | < 0 | **현 6GB 4bit 모델교체 경로 종료** |

"손실 큼/작음"의 경계는 **수치로 고정하지 않는다** — CI와 함께 서술로 판단하고,
그 판단이 갈리면 사용자 결정으로 올린다.

## 4. 실행 조건 — 동시점·동일 조건

| 항목 | 고정값 |
|---|---|
| 질의 | 동일 **dev 96** (`split == "dev"`). **test 미접촉** |
| 프롬프트 | 전 arm **P0** 동일 |
| 평가기 | 동일 `m6_evaluate` (같은 commit) |
| 임베더 | KURE-v1 1024차원, 전 arm 동일 |
| 자막 채널·구간 경계 | M1/M2 산출물 공유 — arm 간 상수 |
| 생성 파라미터 | greedy(`do_sample=False`), `vlm_max_pixels` 현행값 유지 |
| 하드웨어·commit | **같은 서버·같은 commit·같은 배치 안에서 연속 생성** |
| 대조군 | `3B/P0/4bit`를 **동시점**으로 함께 생성 |

**캡션 인덱스는 arm별로 따로 만든다**(캡션이 다르므로 임베딩이 다르다). 공유되는
것은 질의·평가기·임베더·자막·구간 경계다.

**과거 수치는 primary comparator로 쓰지 않는다.** historical context로만 병기한다.

| 과거 기록 | 출처 | 주의 |
|---|---|---|
| 4bit 손실 **−0.068** | 작업현황 §2-3 | **`4B/P1` 조건**의 기록이다. 최종 후보는 P0 |
| 4bit 손실 **−0.0604** | `caption_model_sweep.py` 주석 | 위와 수치가 다르다. 어느 지표·조건인지 재확인 없이 인용하지 마라 |
| 3B bf16 vs 4bit **Δ+0.0024 비유의** | 2026-08-07 | 3B 조건 |

## 5. provenance — 무엇이 실제로 돌았는지 기록한다

arm별로 다음을 산출물에 남긴다.

```
effective_model_id · effective_model_revision
effective_dtype · effective_quantized · quantization_mismatch
bnb 설정 (quant_type · compute_dtype · double_quant)
vlm_max_pixels · do_sample · max_new_tokens
peak VRAM · 생성 완료 구간 수 / 실패·OOM 건수
git commit · resolved_python fingerprint (launcher)
```

**생성 실패·OOM 자체가 배포 결과다.** 조용히 건너뛰지 말고 건수를 보고한다.

> **서버 4090에서 4bit가 도는 것은 6GB 적합성 증명이 아니다.**
> 이 배치는 **검색 품질의 정밀도 효과**를 답한다. 실제 6GB 메모리 적합성은
> **별도 deployment validation**이다(`laptop_4bit_feasibility.py` 계열).

## 6. 오염 경계

- **test 미접촉.** dev 96만 쓴다. launcher `protected_splits`가 막는다.
- **`results/alpha_search_dev.json`에 쓰지 않는다.** 확정 α\*=0.5가 바뀔 위험.
  arm별 α 곡선은 별도 `_scratch` 결과로만 남긴다.
- **본 config·본 인덱스를 건드리지 않는다.** 격리된 arm별 work/results를 쓴다.
- 캡션 전량 저장(규약 5항) — 다른 각도로 볼 때 GPU를 다시 쓰지 않기 위해.

## 7. 절차

```
PRECHECK → CANARY(소규모) → validator PASS → **FULL 사용자 승인** → validate → REPORT
```

FULL은 `--approve-full <run_id>`가 있어야 진입한다. 추정 2~2.5시간.
결과 판정은 **먼저 `Δ_quant`·`Δ_deploy`만** 보고, α·τ calibration은 그 뒤 별도
섹션에서 본다.
