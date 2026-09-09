# WVR_SAMPLING_SEMANTIC_DENSITY_FRAME_ADJUDICATION_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — `NEXT / APPROVED FOR PREREG`.
**이 문서는 packet 생성·판정 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

## 0. 이 사건이 답하는 질문 하나

```
SHORT_WINDOW_V1의 material divergence 구간에서, S0에만 있는 DROP 프레임(추가 2초
중간 프레임)이 실제로 어떤 report-material 정보를 제공했는가.
```

답하지 않는 질문: 0.25fps가 보편적으로 충분한가 · 전체 파이프라인 품질 ·
어떤 프롬프트·모델이 더 좋은가.

## 1. 선행 상태

```
WVR_SHORT_WINDOW_V1              CLOSED / SHORT_WINDOW_PAIRED_STABILITY_HOLD
  P1 GRANULARITY_SHIFT · P2 MATERIAL_DIVERGENCE · P3 MATERIAL_DIVERGENCE
long-context-only-collapse 가설   NOT SUPPORTED (48초에서도 divergence가 남았다)
WVR_EVIDENCE_RESOLUTION_V1       CLOSED / BRANCH_C_EVIDENCE_INCONCLUSIVE
0.25fps semantic sufficiency     NOT ESTABLISHED  ·  0.5fps factual authority  NO
event extraction HOLD · 현행 제출본 READ-ONLY · official test UNOPENED · M9 HOLD
```

**더 이상 prompt·matcher·repetition penalty·context length를 손대지 않는다**(리뷰어 결정).

## 2. 실행 형태 — 추론 없음

```
새 추론      없다. 모델을 부르지 않는다. GPU를 쓰지 않는다
하는 일      프레임 추출 + 대지(contact sheet) 조립 + frozen 주장 병기
프레임 경로   scripts/wvr_capacity_probe.sample_frames — 실행 때와 같은 함수
프레임 크기   512×288 — **모델이 실제로 받은 것과 같은 픽셀**
```

원본 해상도가 아니라 모델 입력 해상도를 쓴다. 판정할 질문이 "모델이 볼 수 있었던
정보"이기 때문이다. 원본에서만 보이는 세부가 있을 수 있다는 것은 한계로 적는다(§7).

## 3. 대상 — 리뷰어가 지목한 3구간뿐 (합계 56초)

```
Q1  P2 448–464   garment/pajama sequence가 계속되는가, food-on-plate로 전환되는가?
Q2  P3 104–128   potato peeling인가, potato ricer/pressing/mixing인가?
Q3  P3 128–144   forming potato balls인가, gloves/mixing sequence인가?
```

전체 영상도, P1도 대상이 아니다(P1은 GRANULARITY_SHIFT로 창 PASS였다).

## 4. 프레임 구성 — KEEP·DROP은 부모 창 격자로 결정

```
S0 격자    2초 (reference_fps 0.5)
KEEP       (t − 부모창 start) % 4 == 0  → S1(0.25fps)에도 들어간 프레임
DROP       그 밖                        → S0에만 있는 프레임
```

파생 결과(결과를 보기 전에 기록):

```
Q1  KEEP 448 · 452 · 456 · 460            DROP 450 · 454 · 458 · 462          4+4
Q2  KEEP 104 · 108 · 112 · 116 · 120 · 124  DROP 106 · 110 · 114 · 118 · 122 · 126  6+6
Q3  KEEP 128 · 132 · 136 · 140            DROP 130 · 134 · 138 · 142          4+4
합계 28프레임 (KEEP 14 · DROP 14)
```

`assert_keep_matches_s1`이 KEEP ⊆ S1 입력, DROP ⊆ S0−S1을 실제 실행 산출물의
timestamp와 대조해 확인한다(WVR-F08). 프레임 수가 위 표와 다르면 실행을 중단한다.

## 5. packet 형식

```
대지        질문별 PNG 1장 — 프레임마다 시각과 KEEP·DROP만 적는다
개별 프레임  runs/wvr_light_v1/frames_adjudication/Q{n}_{시각}_{KEEP|DROP}.png
manifest    프레임별 sha256 · 디코드 프레임 index · 대지 해시 · 영상 sha256
주장 병기    두 arm의 frozen collapsed event를 구간과 겹치는 것만 원문 그대로
```

### blinding을 하지 않는다 — 그리고 그 이유

SHORT_WINDOW_V1 판정이 끝나 **A/B mapping이 이미 공개됐다**. 이 단계에서 다시 가리는
것은 형식만 blinding이고 실효가 없다. 따라서 주장을 `S0 (0.5fps)` · `S1 (0.25fps)`로
명시한다. 대신 대지에는 주장 문구를 넣지 않아 **프레임을 먼저 보고 나서 주장을 읽는
순서**가 가능하게 한다. 기대 편향 가능성은 한계로 남긴다(§7).

## 6. 판정 어휘 (결과 보기 전 동결)

질문별 판정(넷 중 하나):

```
DROP_FRAMES_CARRY_MATERIAL_INFORMATION
    DROP 프레임에만 보이는 사건·상태가 있고, 그것이 보고서 내용을 바꾼다
KEEP_FRAMES_SUFFICIENT
    report-material 내용이 KEEP 프레임에서도 보인다 —
    즉 divergence를 표집 손실로 설명할 수 없다
GENERATION_ERROR_NOT_SAMPLING
    어느 arm의 주장도 프레임과 맞지 않는다(또는 불일치가 누락 프레임으로 설명되지 않는다)
FRAMES_INSUFFICIENT
    프레임만으로는 materiality를 결정할 수 없다
```

별도 축(사건 판정에 직접 쓰지 않고 기록만 한다):

```
S0_CLAIM_MATCHES · S1_CLAIM_MATCHES · BOTH_MATCH_PARTIALLY · NEITHER_MATCHES
```

사건 판정 우선순위:

```
① FRAMES_INSUFFICIENT 하나라도 → INCONCLUSIVE
② DROP_FRAMES_CARRY_MATERIAL_INFORMATION 하나라도 → SAMPLING_LOSS_CONFIRMED
③ GENERATION_ERROR_NOT_SAMPLING 하나라도 → GENERATION_ERROR_DOMINANT
④ 세 질문 모두 KEEP_FRAMES_SUFFICIENT → KEEP_SUFFICIENT_ON_TESTED_WINDOWS
```

세 질문 전부의 판정이 없으면 사건 판정을 계산하지 않는다(WVR-F17).

## 7. 결론 범위와 한계 (미리 적는다)

```
범위     영상 1편 · 48초 창 2개에서 뽑은 3구간(합계 56초)에 대한 판정이다.
         다른 영상·구간·전체 파이프라인으로 일반화하지 않는다
한계 ①   512×288은 모델 입력 해상도다. 원본에서만 식별되는 세부는 이 사건이 못 본다
한계 ②   A/B mapping이 이미 공개돼 blinding이 없다 → 기대 편향 가능
한계 ③   프레임 판정은 시각 채널만 본다. 자막·음성은 이 사건의 입력이 아니다
한계 ④   KEEP 14 · DROP 14장의 표본이다. 통계 추정이 아니라 사례 판정이다
```

`SAMPLING_LOSS_CONFIRMED`가 나와도 `0.25fps는 쓸 수 없다`가 아니라
**"이 구간들에서 0.25fps가 report-material 정보를 잃었다"**까지만 말한다.
`KEEP_SUFFICIENT_ON_TESTED_WINDOWS`가 나와도 `0.25fps semantic sufficiency`는
여전히 NOT ESTABLISHED다.

## 8. 금지 사항

```
새 추론 · 프롬프트·matcher·repetition penalty·context length 조정
프레임을 보고 dev·test 라벨을 만들거나 고치는 것 (이 판정은 GT가 아니다)
이 판정을 검색 질의·라벨·평가에 투입하는 것
구간 추가·교체 (Q1~Q3 외)
결과를 본 뒤 §4·§6의 규칙·우선순위 변경
event extraction 개시 · 제출본 승격 · official test 접촉 · M9 실행
```

`GT_LABEL_USE_ALLOWED = False`로 코드에 박고 테스트로 확인한다(WVR-F03).

## 9. 테스트 (WVR-F01~F20)

```
동결    F01 사전등록 커밋 · F02 질문 3개 · F03 추론·라벨 금지 · F04 프레임 기하 ·
        F05 범위 명시
파생    F06 프레임 수 · F07 부모 격자 · F08 KEEP=S1·DROP=S0−S1 · F09 오표기 거부 ·
        F10 부모창 밖 거부 · F11 half-open · F12 합계 56초
판정    F13 어휘 4값 · F14 불충분 최우선 · F15 DROP material 우선 ·
        F16 생성 오류 도달 가능 · F17 세 질문 필수
조립    F18 주장 원문 대조 · F19 크기·개수 검사 · F20 manifest 해시(실행 후)
```

## 10. 산출물

```
runs/wvr_light_v1/frame_adjudication_packet.md        리뷰어에게 제출
runs/wvr_light_v1/frame_adjudication_manifest.json    프레임별 sha256·provenance
runs/wvr_light_v1/frames_adjudication/                개별 PNG 28장 + 대지 3장
src/wvr_frame_adjudication.py · scripts/wvr_frame_packet.py
tests/test_wvr_frame_adjudication.py
```

SHORT_WINDOW·V2·Evidence Resolution 산출물은 변경하지 않는다.
