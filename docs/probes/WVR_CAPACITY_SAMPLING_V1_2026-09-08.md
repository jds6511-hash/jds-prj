# WVR_CAPACITY_SAMPLING_V1 결과 (2026-09-08 · B arm)

사전등록: `docs/preregistration/WVR_CAPACITY_SAMPLING_V1_2026-09-08.md`
(commit `c7f23aa` — 실행 전 freeze) · 실행 commit `7901d8e23196`

```
B  0.25 fps · 150프레임 · default allocator       CAPACITY_PASS
사건 판정                                          CAPACITY_PASS
generate 완주                                     True (1,024 토큰 · MAX_NEW_TOKENS)
SEMANTIC_RESULT                                   NOT_EVALUATED
다음 단계                                          STOP — event extraction 열지 않는다
```

normative source는 `runs/wvr_light_v1/capacity_sampling_B.json`이다. 이 문서의
수치는 그 파일에서 왔고 `tests/test_wvr_capacity_sampling.py`가 대조한다.

## 1. control 대비

parent control은 재실행하지 않았다 — 이미 같은 조건에서 측정된
`capacity_alloc_A0.json`(default allocator · 0.5 fps · CAPACITY_FAIL)이다.

```
| arm            | fps  | frames | video tok | input tok | peak alloc   | device peak  | result |
| A0 (control)   | 0.5  | 300    | 21,600    | 23,463    | 21,890.1 MiB | 23,972.1 MiB | FAIL   |
| B (treatment)  | 0.25 | 150    | 10,800    | 11,927    | 20,412.1 MiB | 21,834.1 MiB | PASS   |
```

## 2. B arm 실측

```
allocator          env "" · backend native · is_expandable False (268 segment) · warning 0건
GPU idle 직전       used 40.0 MiB · 프로세스 0
baseline           434.1 MiB (free 23,646.8) — control과 동일
post_load          17,336.1 MiB · offloaded_params 0
peak allocated     20,412.1 MiB      peak reserved 21,318.0 MiB
device peak used   21,834.1 MiB / 24,564 MiB   → 남은 여유 2,730 MiB
reserved−allocated 905.9 MiB
표집                150프레임 · 512×288 · 시각 0.0~596.0 · 원본 frame index 0~17,880
tokens             video 10,800 · input 11,927 · output 1,024
완주                generation_completed True · finish_reason MAX_NEW_TOKENS
wall               load 3.49초 · video 19.51초 · infer 40.12초 · total 63.84초
memory_stats       inactive_split peak 1,532,812,800 B · num_alloc_retries 0 · num_ooms 0
```

## 3. 게이트 판정

```
single_change_violations   0건        (requested·metrics 허용 목록 밖 차이 없음)
sampling_changed           True       (300 → 150프레임 · chunk_fps 0.25)
해상도                      512×288 동결 확인
allocator                  default (expandable 아님) — A1 treatment를 물려받지 않았다
baseline                   control 434.1 MiB · B 434.1 MiB · delta 0.0 MiB
                           preregistered gate 128 MiB (운영상 허용오차)  → COMPARABLE
PASS 정의                   oom False · 완주 True · finish_reason MAX_NEW_TOKENS ·
                           generated 1,024 > 0   → CAPACITY_PASS 자격 충족
```

즉 **유일한 변경이 fps였고, 그 변경으로 통과했다.**

## 4. 사전 계산 대비 실측 (한 가지 정정)

```
video token   계산 10,800 → 실측 10,800      일치
input token   계산 약 12,663 → 실측 11,927   736 토큰 적다
```

계산이 어긋난 이유는 **"텍스트·틀 토큰 1,863이 그대로"라고 가정한 것이 틀렸기
때문이다.** Qwen3-VL은 video placeholder에 프레임별 timestamp를 넣으므로 텍스트
토큰도 프레임 수에 따라 줄어든다.

```
input − video   control 23,463 − 21,600 = 1,863
                B       11,927 − 10,800 = 1,127
```

`1,863`은 상수가 아니라 프레임 수에 비례하는 부분을 포함한 값이었다.

## 5. 무엇이 확인됐나

```
확인됨   같은 10분 · 같은 모델 · 같은 해상도 · default allocator에서
        시간 표집을 절반으로 줄이면 4090 24GB에 들어간다
확인됨   generate가 끝까지 돌았다 (1,024 토큰 · 40.12초)
확인됨   여유 2,730 MiB가 남았다 (control은 부족 441.25 MiB였다)
확인됨   단편화가 남아 있어도(inactive_split 1.5 GiB) 통과했다 —
        이번 PASS는 allocator 덕이 아니다
```

## 6. 주장하지 않는 것

```
0.25 fps가 충분하다                     — 의미 평가를 하지 않았다
의미 손실이 없다                        — 4초에 한 장은 시간 정보 밀도를 절반으로
                                       낮춘 것이고, 짧은 동작을 놓칠 수 있다
보고서를 만들 준비가 됐다                — capacity만 통과했다
0.375 fps 같은 중간값이 최적이다         — 탐색하지 않았다
이 여유(2,730 MiB)면 다른 chunk도 된다   — C01만 쟀다
```

생성된 텍스트 4,005자는 provenance·debug 목적으로만 보존한다. event evidence로
쓰지 않는다(사전등록 §10 · `event_extraction_approved: false`).

## 7. 다음 — capacity와 의미 밀도는 다른 질문이다

```
capacity    150프레임이면 4090에 들어가는가          → 닫혔다 (PASS)
semantics   4초에 한 장으로 보고서에 필요한 사건을    → 열지 않았다
            충분히 포착하는가
```

다음 사건은 **semantic-density probe**이고 별도 사전등록이다. 그 전에는 Event Map ·
Chapter · Highlight · Report로 넘어가지 않는다.

```
flash-attn 설치   HOLD      양자화  HOLD      chunk 축소  HOLD
event extraction  HOLD      submission promotion  HOLD
official test     UNOPENED  M9  HOLD
```

## 8. 산출물

```
runs/wvr_light_v1/capacity_sampling_B.json · capacity_sampling_B.log
control  runs/wvr_light_v1/capacity_alloc_A0.json (무변경)
```

## 9. 상태 (무변경)

```
WVR C01                          CLOSED / CAPACITY_FAIL
WVR_CAPACITY_ALLOC_V1            CLOSED / CAPACITY_FAIL (A0 FAIL · A1 FAIL)
R1-VAD0-QUALITY                  FROZEN
PRESENTATION_SYNTHESIS_V1        HOLD
STT_RETRANSCRIBE_V1              CLOSED / INCONCLUSIVE-DEGENERATE
STT_RETRANSCRIBE_DIAGNOSTIC_V1B  UNOPENED
```
